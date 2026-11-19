"""Las filas técnicas por renglón se deciden solo con el ok del informe técnico (REQ-159,
REQ-160, REQ-161; plan 019; T-364). Caso chico inventado (P4): el de `test_technical_ok.py`."""

import re
import time
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import evaluon
from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, review, technical
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.offers.services import sheets
from evaluon.tenders import models as tm
from tests.assessment.test_matrix import add_run, requirement
from tests.assessment.test_technical_ok import pending  # noqa: F401  (fixture)
from tests.journey.proceso.test_sin_esquema import ULTIMAS
from tests.journey.temas.test_s4_propuesta import notice
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db

VIAS = ("via1", "via2")
ACTIONS = ("confirmar", "corregir", "rechazar")
SITUACIONES = ("sin-ok", "con-ok")
VERDICTS = {1: "apto", 2: "no_apto", 3: "apto"}
MESSAGE_PART = "ok del informe técnico"


def current(offer, row):
    return evaluate.current_result(offer, row)


def post_data(action):
    data = {"action": action}
    if action == "corregir":
        data.update(outcome_after="no_cumple", note="Motivo inventado")
    if action == "rechazar":
        data["note"] = "Motivo inventado"
    return data


def send(client, via, procedure, result, action):
    """Envía el pedido por la vía y devuelve `(rechazado, texto del mensaje)`."""
    if via == "via1":
        url = reverse("expedientes:s4_decidir", args=[procedure.pk, result.pk])
        ok, text = notice(client, client.post(url, post_data(action)))
        return (not ok), text
    response = client.post(reverse("assessment:decide", args=[result.pk]), post_data(action))
    return response.status_code == 422, text_of(response)


def refused_facts(result):
    return AuditEvent.objects.filter(
        event_type=EventType.EVAL_DECISION, outcome=AuditOutcome.REJECTED,
        detail__reason="technical_row", detail__result=result.pk)


@pytest.mark.parametrize("situacion", SITUACIONES)
@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("via", VIAS)
def test_every_request_on_a_technical_row_is_refused(
        client, pending, procedure, evaluator_user, via, action, situacion):
    """REQ-159: por las dos vías, las tres acciones, con y sin ok: se rechaza y no se guarda
    ninguna decisión (12 de 12)."""
    offer, rows = pending
    if situacion == "con-ok":
        technical.give_ok(evaluator_user, offer, verdicts=VERDICTS)
    result = current(offer, rows[1])
    before = am.Decision.objects.count()
    log_in(client, evaluator_user)
    refused, text = send(client, via, procedure, result, action)
    assert refused and MESSAGE_PART in text
    assert am.Decision.objects.count() == before == 0


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("via", VIAS)
def test_requests_are_refused_after_the_ok_is_given_and_withdrawn(
        client, pending, procedure, evaluator_user, via, action):
    """REQ-159: con el ok dado y después retirado, el pedido también se rechaza."""
    offer, rows = pending
    technical.give_ok(evaluator_user, offer, verdicts=VERDICTS)
    technical.withdraw_ok(evaluator_user, offer, note="El informe volvió a revisión")
    result = current(offer, rows[2])
    log_in(client, evaluator_user)
    refused, text = send(client, via, procedure, result, action)
    assert refused and MESSAGE_PART in text
    assert am.Decision.objects.count() == 0


def test_a_request_on_a_replaced_technical_result_gives_the_same_reason(
        pending, evaluator_user):
    """REQ-159: un pedido sobre el resultado viejo de la fila da el mismo motivo, no
    `result_replaced`."""
    offer, rows = pending
    old = current(offer, rows[1])
    technical.give_ok(evaluator_user, offer, verdicts=VERDICTS)
    assert current(offer, rows[1]).pk != old.pk
    with pytest.raises(review.ReviewRefused) as refused:
        review.confirm(evaluator_user, old.pk)
    assert refused.value.reason == "technical_row"
    assert am.Decision.objects.count() == 0


def test_the_service_refuses_without_going_through_a_view(pending, evaluator_user):
    """REQ-159: la llamada directa al servicio también se rechaza, en las cuatro formas."""
    offer, rows = pending
    result = current(offer, rows[3])
    calls = (
        lambda: review.decide(evaluator_user, result.pk, "confirmar"),
        lambda: review.confirm(evaluator_user, result.pk),
        lambda: review.correct(evaluator_user, result.pk, "no_cumple", "Motivo inventado"),
        lambda: review.reject(evaluator_user, result.pk, "Motivo inventado"),
    )
    for call in calls:
        with pytest.raises(review.ReviewRefused) as refused:
            call()
        assert refused.value.reason == "technical_row" and refused.value.field == "result"
    assert am.Decision.objects.count() == 0


def test_the_role_and_unknown_cases_keep_their_own_refusals(
        pending, evaluator_user, operator_user):
    """REQ-161: sin rol de evaluador sigue el `RoleRejected`; acción desconocida y resultado
    inexistente conservan su motivo."""
    offer, rows = pending
    result = current(offer, rows[1])
    with pytest.raises(RoleRejected):
        review.confirm(operator_user, result.pk)
    with pytest.raises(review.ReviewRefused) as refused:
        review.decide(evaluator_user, result.pk, "otra")
    assert refused.value.reason == "unknown_action"
    with pytest.raises(review.ReviewRefused) as refused:
        review.confirm(evaluator_user, 10 ** 9)
    assert refused.value.reason == "result_not_found"


def test_a_refused_request_changes_nothing(pending, evaluator_user):
    """REQ-160: resultado, estado, historial y cuenta de decisiones iguales antes y después."""
    offer, rows = pending
    result = current(offer, rows[1])

    def state():
        steps = review.history(evaluator_user, offer.pk, rows[1].pk)
        return (current(offer, rows[1]).pk, current(offer, rows[1]).outcome,
                review.state_of(result),
                [(s.result.pk, [d.pk for d in s.decisions]) for s in steps],
                am.Decision.objects.count(), am.Result.objects.count())

    before = state()
    with pytest.raises(review.ReviewRefused):
        review.correct(evaluator_user, result.pk, "no_cumple", "Motivo inventado")
    assert state() == before


def test_a_refused_request_leaves_its_fact(pending, evaluator_user):
    """REQ-160, P6: un hecho `eval_decision` rechazado con usuario, fecha, resultado, oferta,
    requisito, acción y motivo."""
    offer, rows = pending
    result = current(offer, rows[1])
    with pytest.raises(review.ReviewRefused):
        review.correct(evaluator_user, result.pk, "no_cumple", "Motivo inventado")
    event = refused_facts(result).get()
    assert event.user == evaluator_user and event.occurred_at is not None
    assert event.outcome == AuditOutcome.REJECTED
    detail = event.detail
    assert (detail["result"], detail["offer"], detail["requirement"]) == (
        result.pk, offer.pk, rows[1].pk)
    assert detail["action"] == "corregir" and detail["reason"] == "technical_row"
    assert MESSAGE_PART in detail["message"]
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_DECISION,
                                     outcome=AuditOutcome.OK).count() == 0


def test_other_refusals_keep_the_same_detail(pending, procedure, evaluator_user):
    """REQ-161: un rechazo de otro motivo deja el mismo detalle de siempre, sin `offer` ni
    `requirement`."""
    offer, rows = pending
    result = current(offer, requirement(procedure, "declaración jurada"))
    with pytest.raises(review.ReviewRefused):
        review.reject(evaluator_user, result.pk, "")
    detail = AuditEvent.objects.get(detail__reason="note_required").detail
    assert set(detail) == {"result", "action", "reason", "message"}


@pytest.mark.parametrize("via", VIAS)
def test_the_message_names_the_technical_report_ok(
        client, pending, procedure, evaluator_user, via):
    """REQ-160: el texto de ambas vías nombra el ok del informe técnico y no trae términos
    técnicos."""
    offer, rows = pending
    result = current(offer, rows[1])
    log_in(client, evaluator_user)
    refused, text = send(client, via, procedure, result, "confirmar")
    assert refused and MESSAGE_PART in text
    with pytest.raises(review.ReviewRefused) as error:
        review.confirm(evaluator_user, result.pk)
    message = str(error.value)
    assert MESSAGE_PART in message and message in text
    for word in ("technical_row", "result", "reason", "id"):
        assert not re.search(rf"\b{word}\b", message)


@pytest.mark.parametrize("via", VIAS)
def test_non_technical_rows_are_decided_as_before(
        client, pending, procedure, evaluator_user, via):
    """REQ-161: en una fila que no es técnica, confirmar, corregir con motivo y rechazar con
    motivo guardan la decisión y el hecho `ok`; también en una fila de clase técnica sin
    renglón."""
    offer, rows = pending
    declaration = requirement(procedure, "declaración jurada")
    version = tm.MatrixVersion.objects.create(
        procedure=procedure, number=2, created_by=evaluator_user)
    loose = tm.Requirement.objects.create(
        version=version, number=900, category="tecnico", origin="propuesto",
        state="confirmado")
    assert not sheets.is_item_row(loose) and not sheets.is_item_row(declaration)
    add_run(evaluator_user, procedure, offer, {loose: "cumple"}, version=version)
    log_in(client, evaluator_user)
    for row in (declaration, loose):
        for action in ACTIONS:
            before = am.Decision.objects.count()
            facts = AuditEvent.objects.filter(
                event_type=EventType.EVAL_DECISION, outcome=AuditOutcome.OK).count()
            refused, text = send(client, via, procedure, current(offer, row), action)
            assert not refused, text
            assert am.Decision.objects.count() == before + 1
            assert AuditEvent.objects.filter(
                event_type=EventType.EVAL_DECISION,
                outcome=AuditOutcome.OK).count() == facts + 1
            assert am.Decision.objects.latest("pk").action == action
    assert not AuditEvent.objects.filter(detail__reason="technical_row").exists()


def test_the_ok_still_decides_the_technical_row(pending, evaluator_user):
    """REQ-161: dar el ok deja el cruce en cumple o no cumple con `technical_ok`, y retirarlo
    lo devuelve a pendiente; ninguno crea una `Decision`."""
    offer, rows = pending
    applied = technical.give_ok(evaluator_user, offer, verdicts=VERDICTS)
    assert [current(offer, rows[i]).outcome for i in (1, 2, 3)] == [
        "cumple", "no_cumple", "cumple"]
    for i in (1, 2, 3):
        assert current(offer, rows[i]).facts["technical_ok"] == applied.ok.pk
    technical.withdraw_ok(evaluator_user, offer, note="El informe volvió a revisión")
    for i in (1, 2, 3):
        assert current(offer, rows[i]).doubt == "pendiente_informe_tecnico"
    assert am.Decision.objects.count() == 0


def test_the_control_adds_no_query_and_takes_less_than_0_1_s(pending):
    """RNF de la 019: con el requisito ya cargado, la comprobación no hace consultas y tarda
    menos de 0,1 s."""
    offer, rows = pending
    result = am.Result.objects.select_related("offer", "requirement").get(
        pk=current(offer, rows[1]).pk)
    started = time.perf_counter()
    with CaptureQueriesContext(connection) as queries:
        assert sheets.is_item_row(result.requirement)
    assert time.perf_counter() - started < 0.1
    assert len(queries) == 0


def test_no_new_migration_and_screen_unchanged(client, pending, procedure, evaluator_user):
    """REQ-161: sin migraciones nuevas, y la página del par técnico no ofrece decidir."""
    found = {}
    for folder in sorted(Path(evaluon.__file__).parent.glob("*/migrations")):
        names = sorted(p.stem for p in folder.glob("[0-9][0-9][0-9][0-9]_*.py"))
        found[folder.parent.name] = (names[-1], len(names))
    assert found == ULTIMAS
    offer, rows = pending
    log_in(client, evaluator_user)
    page = client.get(reverse("expedientes:s4_par", args=[procedure.pk, offer.pk, rows[1].pk]))
    assert page.status_code == 200
    html = page.content.decode()
    assert "Confirmar" not in html and "Rechazar" not in html
