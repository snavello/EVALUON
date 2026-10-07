"""Estado de la etapa Evaluación del recorrido (REQ-066) y su avance (REQ-067)."""

import datetime

import pytest
from django.utils import timezone

from evaluon.journey import progress
from evaluon.journey.stages import base, evaluacion
from evaluon.tenders.models import Job, JobKind, JobStatus, Procedure
from tests.journey.conftest import make_run

pytestmark = pytest.mark.django_db


def test_without_a_validated_matrix_the_stage_is_pending(operator_user):
    """REQ-066: sin matriz validada la etapa está pendiente."""
    bare = Procedure.objects.create(
        number="SIN-MATRIZ-1", procedure_type="Contratación directa", subject="Inventado",
        authorization_date=datetime.date(2024, 5, 6), created_by=operator_user)
    stage = evaluacion.compute(operator_user, bare)
    assert stage.state == base.PENDIENTE
    assert "matriz validada" in stage.detail


def test_with_offers_but_no_evaluation_the_stage_is_pending(procedure, two_offers,
                                                            operator_user):
    """REQ-066: con matriz y ofertas, pero sin evaluar, está pendiente."""
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert stage.job is None and stage.pending == 0


def test_a_queued_request_is_in_progress_and_waiting(procedure, two_offers, simulate,
                                                     operator_user):
    """REQ-066/REQ-067: un pedido en espera pone la etapa en curso, marcado como espera."""
    simulate(two_offers, JobStatus.QUEUED)
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.EN_CURSO
    assert stage.progress["waiting"] is True


def test_a_running_request_shows_one_of_two_offers(procedure, two_offers, simulate,
                                                   operator_user):
    """REQ-067: en curso con 1 de 2 ofertas hechas, con la cuenta, el porcentaje y el tiempo."""
    simulate(two_offers, JobStatus.RUNNING, done=1)
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.EN_CURSO
    assert (stage.progress["done"], stage.progress["total"]) == (1, 2)
    assert stage.progress["percent"] == 50
    assert stage.progress["task"] == "Evaluando las ofertas"
    assert "1 de 2" in stage.progress["step"]
    assert stage.progress["elapsed_seconds"] >= 120
    assert "2 min" in stage.progress["elapsed_text"]


def test_a_finished_request_with_every_offer_evaluated_is_ready(procedure, two_offers,
                                                                simulate, operator_user):
    """REQ-066: terminada con todas las ofertas evaluadas con la matriz vigente, está lista."""
    simulate(two_offers, JobStatus.DONE, done=2)
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.LISTA


def test_a_finished_request_missing_an_offer_is_pending(procedure, two_offers, simulate,
                                                        operator_user):
    """REQ-066: si falta una oferta por evaluar la etapa no está lista."""
    simulate(two_offers, JobStatus.DONE, done=1)
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert "1 de 2" in stage.detail


def test_a_failed_request_shows_its_reason(procedure, two_offers, simulate, operator_user):
    """REQ-066/REQ-067: un pedido fallido pone la etapa con error y muestra el motivo."""
    simulate(two_offers, JobStatus.FAILED, done=1, error="se cortó la conexión con el motor")
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.CON_ERROR
    assert stage.error == "se cortó la conexión con el motor"


def test_a_later_result_supersedes_the_failure(procedure, two_offers, simulate,
                                               operator_user):
    """REQ-066: si hay un resultado posterior a la falla, la falla ya no cuenta."""
    failed = simulate(two_offers, JobStatus.FAILED, done=0)
    Job.objects.filter(pk=failed.job.pk).update(
        finished_at=timezone.now() - datetime.timedelta(hours=1))
    for offer in two_offers:
        make_run(failed.request, offer, failed.request.matrix_version)
    assert evaluacion.compute(operator_user, procedure).state == base.LISTA


def test_a_failure_after_the_last_result_still_counts(procedure, two_offers, simulate,
                                                      operator_user):
    """REQ-066: una falla posterior al último resultado se muestra aunque haya resultados."""
    simulate(two_offers, JobStatus.DONE, done=2)
    simulate(two_offers, JobStatus.FAILED, done=0, error="sin memoria")
    stage = evaluacion.compute(operator_user, procedure)
    assert stage.state == base.CON_ERROR and stage.error == "sin memoria"


def test_progress_of_other_kinds_has_only_time(procedure, operator_user):
    """REQ-067: los tipos sin cuenta propia muestran la tarea y el tiempo transcurrido."""
    job = Job.objects.create(kind=JobKind.BUILD_SHEET, procedure=procedure,
                             requested_by=operator_user, target_id=1,
                             status=JobStatus.RUNNING,
                             started_at=timezone.now() - datetime.timedelta(seconds=30))
    data = progress.progress_of(job)
    assert data["task"] and data["total"] is None
    assert data["elapsed_seconds"] >= 30 and data["waiting"] is False
