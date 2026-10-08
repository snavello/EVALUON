"""Estado de la etapa Ofertas del recorrido (REQ-066), sus enlaces (REQ-068) y los roles
(REQ-069). Sugerencias y pendientes van por separado (REQ-072). Datos inventados (P4)."""

import datetime
import hashlib
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.journey.stages import base, ofertas
from evaluon.offers import models as om
from evaluon.tenders.models import Job, JobKind, JobStatus, Procedure
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


def make_sheet(offer, version, user, *, entries=0, confirmed=0, channel="screen"):
    """Una ficha con `entries` filas propuestas y `confirmed` confirmadas."""
    sheet = om.Sheet.objects.create(
        offer=offer, matrix_version=version, number=offer.sheets.count() + 1,
        channel=channel, readings=[], models_used={}, parameters={}, prompt_versions={},
        requested_by=user)
    requirements = list(version.requirements.order_by("number"))
    for i in range(entries + confirmed):
        om.SheetEntry.objects.create(
            sheet=sheet, requirement=requirements[i], outcome="no_encontrado",
            state="propuesto" if i < entries else "confirmado")
    return sheet


def make_job(procedure, kind, target, status, user, *, error="", ago=0):
    job = Job.objects.create(kind=kind, procedure=procedure, requested_by=user,
                             target_id=target.pk)
    now = timezone.now() - timedelta(seconds=ago)
    fields = {"status": status}
    if status != JobStatus.QUEUED:
        fields["started_at"] = now - timedelta(seconds=30)
    if status in (JobStatus.DONE, JobStatus.FAILED):
        fields["finished_at"] = now
    if error:
        fields["error"] = error
    Job.objects.filter(pk=job.pk).update(**fields)
    job.refresh_from_db()
    return job


def unread_document(offer, user):
    return om.Document.objects.create(
        offer=offer, title="nuevo.pdf", file_name="nuevo.pdf", file_format="pdf", file_size=1,
        file_sha256=hashlib.sha256(b"nuevo").hexdigest(), loaded_by=user)


def test_without_offers_the_stage_is_pending(procedure, operator_user):
    """REQ-066: sin ofertas la etapa está pendiente."""
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert "no hay ofertas" in stage.detail
    assert (stage.pending, stage.suggestions) == (0, 0)
    assert stage.view_url == reverse("offers:procedure_offers", args=[procedure.pk])


def test_offers_without_documents_leave_the_stage_pending(procedure, operator_user):
    """REQ-066: una oferta sin documentos no pasa la etapa."""
    om.Offer.objects.create(procedure=procedure, number=1, bidder="Sin papeles",
                            created_by=operator_user)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert "documentos cargados" in stage.detail


def test_a_document_not_read_yet_leaves_the_stage_pending(procedure, offer, operator_user):
    """REQ-066: con un documento sin lectura ni pedido, pendiente, con la cuenta."""
    unread_document(offer, operator_user)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert "1 de 3" in stage.detail


def test_a_reading_in_progress_puts_the_stage_in_progress(procedure, offer, operator_user):
    """REQ-066/REQ-067: un pedido de lectura en curso pone la etapa en curso."""
    document = offer.documents.first()
    job = make_job(procedure, JobKind.READ_OFFER_DOCUMENT, document, JobStatus.RUNNING,
                   operator_user)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.EN_CURSO
    assert stage.job == job and stage.progress is not None


def test_a_sheet_request_waiting_puts_the_stage_in_progress(procedure, offer, operator_user):
    """REQ-066: un pedido de ficha en espera también es en curso."""
    make_job(procedure, JobKind.BUILD_SHEET, offer, JobStatus.QUEUED, operator_user)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.EN_CURSO
    assert stage.progress["waiting"] is True


def test_a_failed_reading_is_an_error_with_its_reason(procedure, offer, operator_user):
    """REQ-066: la lectura que falló muestra el motivo y qué documento."""
    document = offer.documents.first()
    make_job(procedure, JobKind.READ_OFFER_DOCUMENT, document, JobStatus.FAILED,
             operator_user, error="el archivo está dañado", ago=-60)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.CON_ERROR
    assert stage.error == "el archivo está dañado"
    assert document.title in stage.detail


def test_a_failed_reading_followed_by_a_reading_is_not_an_error(procedure, offer,
                                                                operator_user):
    """REQ-066: si una lectura posterior lo superó, la falla ya no cuenta."""
    document = offer.documents.first()
    make_job(procedure, JobKind.READ_OFFER_DOCUMENT, document, JobStatus.FAILED,
             operator_user, error="falló", ago=3600)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.LISTA


def test_a_failed_sheet_is_an_error_until_a_later_sheet(procedure, offer, matrix,
                                                        operator_user):
    """REQ-066: la ficha que falló es error; una ficha posterior lo supera."""
    make_job(procedure, JobKind.BUILD_SHEET, offer, JobStatus.FAILED, operator_user,
             error="el modelo no respondió", ago=-60)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.CON_ERROR and stage.error == "el modelo no respondió"
    make_sheet(offer, matrix.version, operator_user)
    Job.objects.update(finished_at=timezone.now() - timedelta(minutes=5))
    assert ofertas.compute(operator_user, procedure).state == base.LISTA


def test_proposed_rows_make_the_stage_decidable_with_the_count(procedure, two_offers, matrix,
                                                               operator_user):
    """REQ-066/REQ-068: las filas propuestas de la última ficha de cada oferta se suman, y el
    detalle dice cuántas tiene cada oferta; las confirmadas no cuentan."""
    first, second = two_offers
    make_sheet(first, matrix.version, operator_user, entries=3, confirmed=2)
    make_sheet(second, matrix.version, operator_user, entries=1)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert stage.pending == 4
    assert f"Oferta {first.number} ({first.bidder}): 3 filas" in stage.detail
    assert f"Oferta {second.number} ({second.bidder}): 1 fila " in stage.detail


def test_only_the_latest_sheet_of_each_offer_counts(procedure, offer, matrix, operator_user):
    """REQ-066: una ficha vieja con filas propuestas no cuenta si hay una más nueva."""
    make_sheet(offer, matrix.version, operator_user, entries=4)
    make_sheet(offer, matrix.version, operator_user, confirmed=2)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.LISTA and stage.pending == 0


def test_a_sheet_of_the_evaluation_channel_is_not_reviewed_here(procedure, offer, matrix,
                                                                operator_user):
    """REQ-066: la ficha que arma la evaluación no es la que revisa la Comisión."""
    make_sheet(offer, matrix.version, operator_user, entries=5, channel="eval")
    assert ofertas.compute(operator_user, procedure).pending == 0


def test_read_documents_and_no_proposed_rows_make_the_stage_ready(procedure, offer,
                                                                  operator_user):
    """REQ-066: con todos los documentos leídos y sin filas propuestas, lista."""
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.LISTA
    assert stage.pending == 0 and stage.decide_url is None


def test_a_missing_sheet_is_a_suggestion_not_a_pending_decision(procedure, two_offers,
                                                                matrix, operator_user):
    """REQ-072: la ficha no es obligatoria; armarla es una sugerencia aparte de lo
    pendiente, y no frena la etapa."""
    make_sheet(two_offers[0], matrix.version, operator_user, confirmed=1)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.LISTA
    assert (stage.pending, stage.suggestions) == (0, 1)
    assert "no es obligatoria" in stage.detail


def test_pending_and_suggestions_are_both_reported(procedure, two_offers, matrix,
                                                   operator_user):
    """REQ-072: las dos cuentas conviven en la misma etapa."""
    make_sheet(two_offers[0], matrix.version, operator_user, entries=2)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert (stage.pending, stage.suggestions) == (2, 1)


def test_an_unfinished_reading_comes_before_proposed_rows(procedure, offer, matrix,
                                                          operator_user):
    """REQ-066: un documento sin leer manda sobre las filas pendientes (pendiente)."""
    make_sheet(offer, matrix.version, operator_user, entries=2)
    unread_document(offer, operator_user)
    stage = ofertas.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE and stage.pending == 2


def test_the_evaluator_gets_the_sheet_link_and_the_operator_does_not(
        procedure, two_offers, matrix, operator_user, evaluator_user, client):
    """REQ-068/REQ-069: el evaluador va a la primera ficha con filas por confirmar (200); el
    operador solo recibe el enlace de ver."""
    first, second = two_offers
    make_sheet(first, matrix.version, operator_user, confirmed=1)
    pending_sheet = make_sheet(second, matrix.version, operator_user, entries=2)
    as_operator = ofertas.compute(operator_user, procedure)
    as_evaluator = ofertas.compute(evaluator_user, procedure)
    assert as_operator.decide_url is None
    assert as_evaluator.decide_url == reverse("offers:sheet", args=[pending_sheet.pk])
    assert as_operator.view_url == as_evaluator.view_url
    client.force_login(evaluator_user)
    assert client.get(as_evaluator.decide_url).status_code == 200
    assert client.get(as_evaluator.view_url).status_code == 200


def test_with_nothing_pending_nobody_gets_a_decide_link(procedure, offer, evaluator_user):
    """REQ-069: sin filas por confirmar no hay enlace de decisión ni para el evaluador."""
    assert ofertas.compute(evaluator_user, procedure).decide_url is None


def test_jobs_of_another_procedure_do_not_count(procedure, offer, matrix, operator_user):
    """REQ-066: un pedido de otro procedimiento no cambia esta etapa."""
    other = Procedure.objects.create(
        number="OTRO-3", procedure_type="Contratación directa", subject="Inventado",
        authorization_date=datetime.date(2024, 5, 6), created_by=operator_user)
    other_offer = make_offer(other, operator_user, "Otro oferente", {"a.pdf": ["Texto."]})
    make_job(other, JobKind.BUILD_SHEET, other_offer, JobStatus.RUNNING, operator_user)
    assert ofertas.compute(operator_user, procedure).state == base.LISTA
