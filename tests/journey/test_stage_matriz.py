"""Estado de la etapa Matriz del recorrido (REQ-066, REQ-068, REQ-069, REQ-072). Todo el
material es inventado (P4)."""

import datetime
import itertools
from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from evaluon.journey.stages import base, matriz
from evaluon.tenders.models import (
    Document,
    Job,
    JobKind,
    JobStatus,
    MatrixVersion,
    PendingItem,
    Procedure,
    Reading,
    Requirement,
    RequirementState,
    VersionStatus,
)
from evaluon.tenders.services import validation

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


def _job(procedure, user, status, error=""):
    now = timezone.now()
    fields = {"status": status}
    if status != JobStatus.QUEUED:
        fields["started_at"] = now - timedelta(seconds=20)
    if status in (JobStatus.DONE, JobStatus.FAILED):
        fields["finished_at"] = now
    if status == JobStatus.FAILED:
        fields["error"] = error
    job = Job.objects.create(kind=JobKind.PROPOSE_MATRIX, procedure=procedure,
                             requested_by=user)
    Job.objects.filter(pk=job.pk).update(**fields)
    job.refresh_from_db()
    return job


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"MATRIZ-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


@pytest.fixture
def draft(procedure, matrix, operator_user):
    """Un borrador (versión 2) abierto sobre la validada del caso chico, con sus requisitos
    copiados."""
    opened = validation.open_new_version(operator_user, procedure.pk)
    return opened if isinstance(opened, MatrixVersion) else procedure.matrix_versions.get(
        status=VersionStatus.DRAFT)


def test_without_a_version_and_without_the_pliego_it_is_pending(bare, operator_user):
    """REQ-066: sin versión ni pliego leído, pendiente y lo dice."""
    stage = matriz.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and "pliego" in stage.detail
    assert resolve(stage.view_url).view_name == "expedientes:pliego"


def test_the_ready_pliego_without_a_version_is_pending_for_lack_of_a_request(
        bare, operator_user):
    """REQ-066: con el pliego leído pero sin versión ni pedido, pendiente por falta de pedido."""
    document = Document.objects.create(
        procedure=bare, kind="pliego", title="Pliego inventado", file_name="p.pdf",
        file_format="pdf", file_size=10, file_sha256="a" * 64, loaded_by=operator_user)
    Reading.objects.create(
        document=document, sequence=1, pages=[], canonical_text="texto inventado",
        canonical_sha256="0" * 64, tool_versions={}, report={})
    stage = matriz.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and "propuesta" in stage.detail


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
def test_an_active_proposal_is_in_progress(bare, operator_user, status):
    """REQ-066: un pedido `propose_matrix` en espera o en curso pone la etapa en curso."""
    job = _job(bare, operator_user, status)
    stage = matriz.compute(operator_user, bare)
    assert stage.state == base.EN_CURSO and stage.job.pk == job.pk
    assert stage.progress["task"] == "Proponiendo la matriz"


def test_a_failed_proposal_shows_its_reason(bare, operator_user):
    """REQ-066: pedido fallido sin versión posterior: con error y su motivo."""
    _job(bare, operator_user, JobStatus.FAILED, error="el modelo no respondió")
    stage = matriz.compute(operator_user, bare)
    assert stage.state == base.CON_ERROR and stage.error == "el modelo no respondió"


def test_a_later_version_supersedes_the_failure(procedure, matrix, operator_user):
    """REQ-066: una versión creada después de la falla la supera."""
    job = _job(procedure, operator_user, JobStatus.FAILED, error="falló")
    Job.objects.filter(pk=job.pk).update(
        finished_at=matrix.version.created_at - timedelta(minutes=1))
    assert matriz.compute(operator_user, procedure).state == base.LISTA


def test_a_validated_version_is_ready(procedure, matrix, operator_user):
    """REQ-066: versión validada, lista, sin pendientes ni sugerencias."""
    stage = matriz.compute(operator_user, procedure)
    assert stage.state == base.LISTA and stage.pending == 0 and stage.suggestions == 0
    assert resolve(stage.view_url).view_name == "expedientes:pliego"
    assert resolve(stage.view_url).kwargs == {"procedure_id": procedure.pk, "key": "pliego"}


def test_a_draft_with_proposed_requirements_and_open_segments_counts_both(
        procedure, draft, operator_user):
    """REQ-066/REQ-072: borrador: requisitos propuestos más tramos sin resolver son la cuenta
    a decidir; los sugeridos se cuentan aparte."""
    requirements = list(draft.requirements.order_by("number"))
    assert len(requirements) >= 4
    Requirement.objects.filter(pk__in=[r.pk for r in requirements]).update(
        state=RequirementState.CONFIRMADO)
    Requirement.objects.filter(pk__in=[r.pk for r in requirements[:3]]).update(
        state=RequirementState.PROPUESTO)
    segment = requirements[0].quotes.first().segment
    PendingItem.objects.create(version=draft, segment=segment, reason="tabla")
    PendingItem.objects.create(
        version=draft, segment=segment, reason="marcadores", resolution="sin_requisitos",
        resolved_by=operator_user, resolved_at=timezone.now())
    Requirement.objects.filter(pk=requirements[3].pk).update(
        state=RequirementState.SUGERIDO, doubt_reason="duda")
    stage = matriz.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert stage.pending == 3 + 1
    assert stage.suggestions == 1
    assert "3 requisitos" in stage.detail and "1 tramo" in stage.detail


def test_a_draft_with_nothing_left_only_needs_validation(procedure, draft, operator_user):
    """REQ-066: un borrador sin nada que confirmar sigue a decidir (falta validarlo), con 0."""
    draft.requirements.update(state=RequirementState.CONFIRMADO)
    stage = matriz.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR and stage.pending == 0
    assert "validar" in stage.detail


def test_the_latest_non_discarded_version_is_the_one_that_counts(procedure, draft,
                                                                 operator_user):
    """REQ-066: el borrador pesa más que la validada anterior; descartado, vuelve la validada."""
    assert matriz.compute(operator_user, procedure).state == base.A_DECIDIR
    MatrixVersion.objects.filter(pk=draft.pk).update(
        status=VersionStatus.DISCARDED, discarded_at=timezone.now(),
        discarded_by=operator_user)
    assert matriz.compute(operator_user, procedure).state == base.LISTA


def test_only_the_evaluator_gets_the_decide_link_on_a_draft(procedure, draft, operator_user,
                                                            evaluator_user):
    """REQ-069: el operador ve la matriz (`view_url`) pero no recibe `decide_url`; el
    evaluador sí, y ambos enlaces resuelven."""
    as_operator = matriz.compute(operator_user, procedure)
    as_evaluator = matriz.compute(evaluator_user, procedure)
    assert as_operator.decide_url is None
    assert as_evaluator.decide_url == as_evaluator.view_url
    assert resolve(as_evaluator.view_url).view_name == "expedientes:pliego"
    assert resolve(as_evaluator.view_url).kwargs == {"procedure_id": procedure.pk, "key": "pliego"}


def test_no_decide_link_on_a_validated_matrix(procedure, matrix, evaluator_user):
    """REQ-069: validada no hay nada que decidir, ni para el evaluador."""
    assert matriz.compute(evaluator_user, procedure).decide_url is None
