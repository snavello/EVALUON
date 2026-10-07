"""Estado de la etapa Pliego y circulares del recorrido (REQ-066, REQ-068, REQ-069, REQ-072).
Todo el material es inventado (P4)."""

import datetime
import itertools
from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from evaluon.journey.stages import base, pliego
from evaluon.tenders.models import (
    Document,
    Job,
    JobKind,
    JobStatus,
    Procedure,
    Reading,
)

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"PLIEGO-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


def add_document(procedure, user, title="Pliego inventado"):
    n = next(_n)
    return Document.objects.create(
        procedure=procedure, kind="pliego", title=title, file_name=f"{n}.pdf",
        file_format="pdf", file_size=10, file_sha256=f"{n:064x}", loaded_by=user)


def add_reading(document, created_at=None):
    reading = Reading.objects.create(
        document=document, sequence=document.readings.count() + 1, pages=[],
        canonical_text="texto inventado", canonical_sha256="0" * 64, tool_versions={},
        report={})
    if created_at:
        Reading.objects.filter(pk=reading.pk).update(created_at=created_at)
    return reading


def read_job(document, user, status, error=""):
    now = timezone.now()
    fields = {"status": status}
    if status != JobStatus.QUEUED:
        fields["started_at"] = now - timedelta(seconds=20)
    if status in (JobStatus.DONE, JobStatus.FAILED):
        fields["finished_at"] = now
    if status == JobStatus.FAILED:
        fields["error"] = error
    job = Job.objects.create(kind=JobKind.READ_DOCUMENT, procedure=document.procedure,
                             document=document, requested_by=user)
    Job.objects.filter(pk=job.pk).update(**fields)
    job.refresh_from_db()
    return job


def test_without_documents_the_stage_is_pending(bare, operator_user):
    """REQ-066: sin documentos del pliego, pendiente."""
    stage = pliego.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and "documentos del pliego" in stage.detail
    assert stage.pending == 0 and stage.suggestions == 0 and stage.optional is False


def test_a_document_not_yet_read_is_pending(bare, operator_user):
    """REQ-066: con un documento sin lectura y sin pedido, pendiente con la cuenta."""
    add_reading(add_document(bare, operator_user, "Uno"))
    add_document(bare, operator_user, "Dos")
    stage = pliego.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and "1 de 2" in stage.detail


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
def test_an_active_reading_is_in_progress(bare, operator_user, status):
    """REQ-066: un pedido de lectura en espera o en curso pone la etapa en curso."""
    document = add_document(bare, operator_user)
    job = read_job(document, operator_user, status)
    stage = pliego.compute(operator_user, bare)
    assert stage.state == base.EN_CURSO and stage.job.pk == job.pk


def test_a_failed_reading_shows_its_reason_and_the_document(bare, operator_user):
    """REQ-066: el último pedido de un documento falló: con error, con motivo."""
    document = add_document(bare, operator_user, "Anexo ilegible")
    read_job(document, operator_user, JobStatus.FAILED, error="archivo dañado")
    stage = pliego.compute(operator_user, bare)
    assert stage.state == base.CON_ERROR and stage.error == "archivo dañado"
    assert "Anexo ilegible" in stage.detail


def test_a_later_reading_supersedes_the_failure(bare, operator_user):
    """REQ-066: una lectura posterior a la falla la supera."""
    document = add_document(bare, operator_user)
    job = read_job(document, operator_user, JobStatus.FAILED, error="falló")
    add_reading(document, created_at=job.finished_at + timedelta(minutes=1))
    assert pliego.compute(operator_user, bare).state == base.LISTA


def test_all_documents_read_is_ready(bare, operator_user):
    """REQ-066: todos con lectura, lista."""
    for title in ("Pliego", "Circular 1"):
        add_reading(add_document(bare, operator_user, title))
    stage = pliego.compute(operator_user, bare)
    assert stage.state == base.LISTA and stage.pending == 0
    assert "2 documentos" in stage.detail


def test_the_view_link_resolves_and_nobody_gets_a_decide_link(bare, operator_user,
                                                              evaluator_user):
    """REQ-068/REQ-069: el enlace va a `tenders:procedure`; la lectura es automática, así que
    ni siquiera el evaluador recibe un enlace de decisión."""
    add_reading(add_document(bare, operator_user))
    for user in (operator_user, evaluator_user):
        stage = pliego.compute(user, bare)
        assert resolve(stage.view_url).view_name == "tenders:procedure"
        assert resolve(stage.view_url).kwargs == {"procedure_id": bare.pk}
        assert stage.decide_url is None


def test_the_case_with_the_read_pliego_is_ready(procedure, operator_user):
    """REQ-066: el caso chico (pliego leído) está listo."""
    assert pliego.compute(operator_user, procedure).state == base.LISTA
