"""«No pedir» una subsanación desde la pestaña Evaluación y dictamen (REQ-090; maqueta aprobada,
bloque de preguntas y subsanaciones; T-225). Resultados guardados directo, sin el modelo; todo el
material es inventado (P4)."""

import pytest
from django.urls import reverse

from evaluon.assessment.services import remedy
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from tests.assessment.test_matrix import evaluated, three  # noqa: F401  (fixtures)
from tests.journey.temas.test_s4_preguntas import block, log_in, missing, notice

pytestmark = pytest.mark.django_db


def decline_url(procedure, result):
    return reverse("expedientes:s4_no_pedir_subsanacion", args=[procedure.pk, result.pk])


def test_the_evaluator_sees_no_pedir_next_to_pedir_and_the_operator_does_not(
        client, evaluated, procedure, evaluator_user, operator_user):
    """REQ-090: la subsanación por decidir tiene «Pedir que se subsane» y «No pedir» (con su
    motivo obligatorio) para el evaluador; el operador no ve ninguno."""
    result = missing(evaluated, procedure)
    log_in(client, evaluator_user)
    html = block(client, procedure)
    assert "No pedir" in html and decline_url(procedure, result) in html
    assert "Motivo para no pedirla (obligatorio)" in html
    client.logout()
    log_in(client, operator_user)
    html = block(client, procedure)
    assert "No pedir" not in html and decline_url(procedure, result) not in html


def test_declining_returns_to_the_tab_with_notice_and_the_pending_disappears(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: no pedir vuelve a la pestaña con el aviso; la fila deja de estar por decidir y
    muestra quién, cuándo y el motivo; la cuenta de por decidir baja en uno."""
    result = missing(evaluated, procedure)
    log_in(client, evaluator_user)
    before = block(client, procedure)
    to_decide = int(before.split(" por decidir")[0].rsplit(">", 1)[1])
    ok, text = notice(client, client.post(decline_url(procedure, result),
                                          {"note": "El faltante no es esencial."}))
    assert ok and "no pedir la subsanación" in text
    assert f"oferta {result.offer.number}" in text
    html = block(client, procedure)
    row = html[html.index(f'id="sub-{result.pk}"'):]
    row = row[:row.index("</tr>")]
    assert "No se pide" in row and "Por decidir" not in row
    assert f"Se decidió no pedirla: {evaluator_user.username} el " in row
    assert "motivo: El faltante no es esencial." in row
    assert "Pedir que se subsane" not in row and "No pedir" not in row
    assert f"{to_decide - 1} por decidir" in html
    event = AuditEvent.objects.get(event_type=EventType.EVAL_DECISION,
                                   detail__action=remedy.DECLINE_ACTION,
                                   outcome=AuditOutcome.OK)
    assert event.user == evaluator_user and event.channel == "screen"


def test_declining_without_a_reason_changes_nothing_and_says_why(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: sin motivo no se registra la decisión y el aviso lo dice."""
    result = missing(evaluated, procedure)
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(decline_url(procedure, result), {"note": " "}))
    assert not ok and "motivo" in text.lower()
    assert remedy.state(result).declined is None


def test_the_operator_cannot_decline_and_the_refusal_is_recorded(
        client, evaluated, procedure, operator_user):
    """P3, P6: sin el rol de evaluador da 403 y queda el rechazo."""
    result = missing(evaluated, procedure)
    log_in(client, operator_user)
    before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    response = client.post(decline_url(procedure, result), {"note": "No es esencial."})
    assert response.status_code == 403
    assert remedy.state(result).declined is None
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == before + 1
