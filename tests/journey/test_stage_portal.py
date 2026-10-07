"""Estado de la etapa Datos del Portal del recorrido (REQ-066, REQ-068, REQ-069, REQ-071,
REQ-072). Todo el material es inventado (P4)."""

import datetime
import itertools
from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from evaluon.journey.stages import base, portal, stages_for
from evaluon.portal import models as p
from evaluon.tenders.models import Document, Job, JobKind, JobStatus, Procedure

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


def _sha():
    return f"{next(_n):064x}"


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"PORTAL-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


@pytest.fixture
def link(bare, operator_user):
    return p.PortalLink.objects.create(
        url=f"https://portal.ejemplo.test/x.aspx?qs={next(_n)}", procedure=bare,
        created_by=operator_user)


def add_proposal(link, keys=(), exploration=1, kind=p.ItemKind.PROCEDIMIENTO):
    """Una propuesta con un ítem propuesto por cada clave."""
    proposal = p.PortalProposal.objects.create(
        link=link, exploration=exploration, origin=p.Origin.IMPORTACION)
    page = p.PortalPage.objects.create(
        link=link, exploration=exploration, kind=p.PageKind.PROCESO, url=link.url,
        sha256=_sha(), content=b"<html>inventado</html>")
    items = [p.PortalItem.objects.create(
        proposal=proposal, kind=kind, key=key, payload={"k": key},
        content_sha256=_sha(), page=page) for key in keys]
    return proposal, items


def mark_loaded(item, user, model, loaded_id):
    p.PortalItem.objects.filter(pk=item.pk).update(
        state=p.ItemState.CARGADO, decided_by=user, decided_at=timezone.now(),
        loaded_model=model, loaded_id=loaded_id)


def add_document(procedure, user, title="Pliego inventado"):
    return Document.objects.create(
        procedure=procedure, kind="pliego", title=title, file_name=f"{next(_n)}.pdf",
        file_format="pdf", file_size=10, file_sha256=_sha(), loaded_by=user)


def portal_job(link, user, status, kind=JobKind.PORTAL_EXPLORE, error=""):
    now = timezone.now()
    fields = {"status": status}
    if status != JobStatus.QUEUED:
        fields["started_at"] = now - timedelta(seconds=30)
    if status in (JobStatus.DONE, JobStatus.FAILED):
        fields["finished_at"] = now
    if status == JobStatus.FAILED:
        fields["error"] = error
    job = Job.objects.create(kind=kind, procedure=None, requested_by=user, target_id=link.pk)
    Job.objects.filter(pk=job.pk).update(**fields)
    job.refresh_from_db()
    return job


def test_without_a_link_the_stage_is_pending_and_optional(bare, operator_user):
    """REQ-066/REQ-071: sin enlace del Portal está pendiente, es opcional y enlaza a cargar."""
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and stage.optional is True
    assert stage.pending == 0 and stage.decide_url is None
    assert resolve(stage.view_url).view_name == "portal:links"


def test_an_optional_pending_portal_is_not_the_current_stage(procedure, operator_user):
    """REQ-066: sin enlace, la etapa actual no es la del Portal."""
    journey = stages_for(operator_user, procedure)
    assert journey.stages[0].key == "portal" and journey.stages[0].state == base.PENDIENTE
    assert journey.current is None or journey.current.key != "portal"


def test_a_link_never_explored_is_pending(bare, link, operator_user):
    """REQ-066: con enlace pero sin exploración, pendiente."""
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE and "no se exploró" in stage.detail


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
def test_an_active_exploration_is_in_progress(bare, link, operator_user, status):
    """REQ-066: un pedido del Portal en espera o en curso, hallado por el enlace aunque no
    tenga procedimiento, pone la etapa en curso."""
    job = portal_job(link, operator_user, status)
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.EN_CURSO and stage.job.pk == job.pk
    assert stage.progress is not None


def test_a_review_job_also_counts(bare, link, operator_user):
    """REQ-066: la revisión periódica es un pedido de la etapa."""
    portal_job(link, operator_user, JobStatus.RUNNING, kind=JobKind.PORTAL_REVIEW)
    assert portal.compute(operator_user, bare).state == base.EN_CURSO


def test_a_job_of_another_link_does_not_count(bare, link, operator_user):
    """REQ-066: solo cuentan los pedidos de los enlaces del procedimiento."""
    other = p.PortalLink.objects.create(
        url="https://portal.ejemplo.test/otro.aspx?qs=9", created_by=operator_user)
    portal_job(other, operator_user, JobStatus.RUNNING)
    assert portal.compute(operator_user, bare).state == base.PENDIENTE


def test_a_failed_exploration_shows_its_reason(bare, link, operator_user):
    """REQ-066: el último pedido fallido, sin propuesta posterior, deja la etapa con error y
    su motivo."""
    portal_job(link, operator_user, JobStatus.FAILED, error="el Portal no respondió")
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.CON_ERROR and stage.error == "el Portal no respondió"


def test_a_later_proposal_supersedes_the_failure(bare, link, operator_user):
    """REQ-066: una propuesta posterior a la falla la supera."""
    job = portal_job(link, operator_user, JobStatus.FAILED, error="falló")
    proposal, _ = add_proposal(link, ["procedimiento"])
    p.PortalProposal.objects.filter(pk=proposal.pk).update(
        created_at=job.finished_at + timedelta(minutes=1))
    assert portal.compute(operator_user, bare).state == base.A_DECIDIR


def test_proposed_items_are_decisions_pending_with_their_count(bare, link, operator_user):
    """REQ-066/REQ-072: los ítems propuestos de la última propuesta son la cuenta a decidir;
    el Portal no aporta sugerencias."""
    add_proposal(link, ["a", "b", "c"])
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.A_DECIDIR and stage.pending == 3 and stage.suggestions == 0
    assert "3 datos esperan" in stage.detail


def test_only_the_latest_proposal_counts(bare, link, operator_user):
    """REQ-066: las propuestas anteriores no suman a la cuenta."""
    add_proposal(link, ["a"], exploration=1)
    add_proposal(link, ["a", "b"], exploration=2)
    assert portal.compute(operator_user, bare).pending == 2


def test_everything_decided_is_ready_and_links_to_the_import(bare, link, operator_user):
    """REQ-066/REQ-068: sin ítems propuestos la etapa está lista y enlaza a lo importado."""
    _, (item,) = add_proposal(link, ["a"])
    mark_loaded(item, operator_user, p.LoadedModel.PROCEDURE, bare.pk)
    stage = portal.compute(operator_user, bare)
    assert stage.state == base.LISTA and stage.pending == 0
    assert resolve(stage.view_url).view_name == "portal:imported"
    assert resolve(stage.view_url).kwargs == {"link_id": link.pk}


def test_the_view_link_to_the_proposal_resolves(bare, link, operator_user):
    """REQ-068: con ítems propuestos el enlace va a la propuesta del enlace."""
    add_proposal(link, ["a"])
    stage = portal.compute(operator_user, bare)
    assert resolve(stage.view_url).view_name == "portal:proposal"
    assert resolve(stage.view_url).kwargs == {"link_id": link.pk}


def test_operator_gets_no_decide_link_and_evaluator_does(bare, link, operator_user,
                                                         evaluator_user):
    """REQ-069: solo el evaluador recibe `decide_url`; el operador, solo `view_url`."""
    add_proposal(link, ["a"])
    as_operator = portal.compute(operator_user, bare)
    as_evaluator = portal.compute(evaluator_user, bare)
    assert as_operator.decide_url is None and as_operator.view_url
    assert as_evaluator.decide_url == as_evaluator.view_url


def test_no_decide_link_when_nothing_waits(bare, link, evaluator_user):
    """REQ-069: sin decisiones pendientes tampoco hay enlace de decisión."""
    add_proposal(link, [])
    assert portal.compute(evaluator_user, bare).decide_url is None


def test_the_stage_separates_what_the_portal_brought_from_what_was_uploaded_by_hand(
        bare, link, operator_user):
    """REQ-071: el detalle dice aparte lo que trajo el Portal y lo subido a mano."""
    from_portal = add_document(bare, operator_user, "Pliego del Portal")
    add_document(bare, operator_user, "Anexo a mano")
    add_document(bare, operator_user, "Otro a mano")
    _, (item,) = add_proposal(link, ["doc"], kind=p.ItemKind.DOCUMENTO)
    mark_loaded(item, operator_user, p.LoadedModel.DOCUMENT, from_portal.pk)
    detail = portal.compute(operator_user, bare).detail
    assert "Trajo el Portal: 1 documento." in detail
    assert "Subido a mano: 2 documentos." in detail


def test_without_a_link_it_still_shows_what_was_uploaded_by_hand(bare, operator_user):
    """REQ-071: un procedimiento cargado a mano muestra su material como subido a mano."""
    add_document(bare, operator_user)
    detail = portal.compute(operator_user, bare).detail
    assert "Trajo el Portal: nada todavía." in detail
    assert "Subido a mano: 1 documento." in detail


def test_the_stage_does_not_change_any_data(bare, link, operator_user):
    """REQ-069: la etapa solo lee."""
    add_proposal(link, ["a"])
    before = (Job.objects.count(), p.PortalItem.objects.filter(state="propuesto").count())
    portal.compute(operator_user, bare)
    assert (Job.objects.count(),
            p.PortalItem.objects.filter(state="propuesto").count()) == before
