"""Pantalla del par con las acciones de la Comisión y el historial (REQ-053, REQ-056,
REQ-057; plan 004, "Pantalla"; T-153). Caso chico inventado; el modelo es un guion."""

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import DECLARATION, requirement_of, run_all
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposal(offer, operator_user, procedure, model):
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION),
                                      explanation="Lo declara el oferente.")
                    if "declaración jurada" in call.requirement else None)
    run_all(operator_user, procedure)
    return evaluate.current_result(offer, requirement_of(procedure, "declaración jurada"))


def page_url(proposal):
    return reverse("assessment:pair", args=[proposal.offer_id, proposal.requirement_id])


def decide_url(proposal):
    return reverse("assessment:decide", args=[proposal.pk])


def test_the_evaluator_sees_the_actions_with_the_grounds(client, proposal, evaluator_user):
    """REQ-053, REQ-056: el evaluador ve el pliego, la cita de la oferta y las tres
    acciones."""
    log_in(client, evaluator_user)
    page = text_of(client.get(page_url(proposal)))
    assert "Presentar la declaración jurada" in page and DECLARATION in page
    assert "Decisión de la Comisión" in page and "propuesto" in page
    for button in ("Confirmar", "Corregir", "Rechazar"):
        assert button in page
    assert "Ver el historial" in page


def test_the_operator_does_not_get_the_actions_nor_can_post(client, proposal, operator_user):
    """P3: sin el rol de evaluador no hay botones y el POST es 403, sin decisión."""
    log_in(client, operator_user)
    assert "Rechazar" not in text_of(client.get(page_url(proposal)))
    response = client.post(decide_url(proposal), {"action": "confirmar"})
    assert response.status_code == 403
    assert not am.Decision.objects.exists()


def test_correcting_from_the_screen_shows_it_with_author_and_date(
        client, proposal, evaluator_user):
    """REQ-056: la corrección queda y la página muestra la propuesta original, la
    corrección y quién la hizo."""
    log_in(client, evaluator_user)
    response = client.post(decide_url(proposal), {
        "action": "corregir", "outcome_after": "no_cumple", "note": "La firma no vale."})
    assert response.status_code == 302 and response["Location"] == page_url(proposal)
    page = text_of(client.get(page_url(proposal)))
    assert "corregido" in page and "«No cumple»" in page
    assert evaluator_user.username in page and "La firma no vale." in page
    assert "Cumple" in page  # la propuesta original sigue a la vista
    history = text_of(client.get(reverse("assessment:history", args=[
        proposal.offer_id, proposal.requirement_id])))
    assert "Evaluación 1 (vigente)" in history and DECLARATION in history
    assert "el sistema había propuesto «Cumple»" in history


def test_a_refused_decision_comes_back_with_its_reason(client, proposal, evaluator_user):
    """REQ-056: sin motivo la corrección se rechaza con 422 y el mensaje; no queda decisión."""
    log_in(client, evaluator_user)
    response = client.post(decide_url(proposal), {
        "action": "corregir", "outcome_after": "no_cumple", "note": ""})
    assert response.status_code == 422
    assert "Escriba el motivo de la decisión" in text_of(response)
    assert not am.Decision.objects.exists()


def test_the_page_shows_the_matrix_version_next_to_the_actions(client, proposal,
                                                               evaluator_user):
    """REQ-057: la página dice con qué versión de la matriz se armó la evaluación."""
    log_in(client, evaluator_user)
    page = text_of(client.get(page_url(proposal)))
    assert "armada con la matriz versión 1" in page and "Decisión de la Comisión" in page
