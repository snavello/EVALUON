"""El ok de la Comisión al informe técnico (REQ-061; plan 004, "Ok del informe técnico"; ADR-0043;
T-168). La decisión literal: "la comision debiera dar el ok de que tiene el informe tecnico
aprobado". Caso chico inventado (P4); los resultados se guardan directo, sin el modelo."""

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, technical
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from tests.assessment.test_matrix import (
    DECLARATION,
    add_run,
    discard_of,
    page_of,
    requirement,
)
from tests.offers.conftest import make_offer
from tests.offers.test_screens import log_in, text_of

pytestmark = [pytest.mark.django_db, pytest.mark.decision_literal]

PENDING = ("no_determinado", "pendiente_informe_tecnico")


@pytest.fixture
def pending(procedure, operator_user):
    """Una oferta con las filas de los renglones 1, 2 y 3 pendientes del informe técnico y la
    declaración jurada cumplida."""
    offer = make_offer(procedure, operator_user, "Oferente Z",
                       {"oferta.pdf": [f"{DECLARATION}. Texto de la oferta."]})
    rows = {i: requirement(procedure, item=i) for i in (1, 2, 3)}
    declaration = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, offer,
            {declaration: "cumple", rows[1]: PENDING, rows[2]: PENDING, rows[3]: PENDING})
    return offer, rows


def current(offer, row):
    return evaluate.current_result(offer, row)


def test_the_evaluator_gives_the_ok_and_each_row_takes_what_the_report_says(
        pending, evaluator_user):
    """REQ-061: con el ok, la fila de cada renglón pasa a cumple o no cumple con el fundamento
    «informe técnico aprobado, ok de la Comisión por … el …»; el resultado anterior queda."""
    offer, rows = pending
    before = {i: current(offer, r) for i, r in rows.items()}
    applied = technical.give_ok(
        evaluator_user, offer, verdicts={1: "apto", 2: "no_apto", 3: "apto"},
        note="Informe del área técnica, expediente inventado")
    assert [r.outcome for r in applied.results] == ["cumple", "no_cumple", "cumple"]
    one, two = current(offer, rows[1]), current(offer, rows[2])
    assert (one.outcome, one.doubt, two.outcome, two.doubt) == ("cumple", "", "no_cumple", "")
    for result in (one, two):
        assert result.explanation.startswith(
            "informe técnico aprobado, ok de la Comisión por ")
        assert " el " in result.explanation
        assert result.facts["technical_ok"] == applied.ok.pk
    assert (one.previous_id, two.previous_id) == (before[1].pk, before[2].pk)
    assert am.Result.objects.filter(pk__in=[b.pk for b in before.values()]).count() == 3
    assert before[1].doubt == "pendiente_informe_tecnico"
    assert one.run.number > before[1].run.number
    assert one.run.request.cause == am.Cause.MANUAL


def test_the_ok_and_its_event_record_who_when_and_what(pending, evaluator_user):
    """REQ-061, P6: queda la fila del ok con usuario, momento, renglones, lo que dice el informe y
    nota, y el hecho `eval_decision` con `kind = technical_ok`."""
    offer, rows = pending
    applied = technical.give_ok(evaluator_user, offer, items=[1],
                                verdicts={1: "apto", 2: "no_apto"}, note="Aprobado")
    ok = am.TechnicalOk.objects.get()
    assert (ok.user, ok.offer, ok.items, ok.verdicts, ok.action, ok.note) == (
        evaluator_user, offer, [1], {"1": "apto"}, "dar_ok", "Aprobado")
    assert ok.at is not None and ok.event_id == applied.event.pk
    event = AuditEvent.objects.get(pk=ok.event_id)
    assert event.event_type == EventType.EVAL_DECISION
    assert event.outcome == AuditOutcome.OK
    assert event.detail["kind"] == "technical_ok"
    assert event.detail["offer"] == offer.pk and event.detail["items"] == [1]
    assert event.detail["user"] == evaluator_user.username


def test_the_ok_of_a_row_does_not_touch_another(pending, evaluator_user):
    """REQ-061: el ok de un renglón no afecta a otro; `ok_of` nombra solo al suyo."""
    offer, rows = pending
    technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "apto"})
    assert technical.ok_of(offer, 1).action == "dar_ok"
    assert technical.ok_of(offer, 2) is None
    assert current(offer, rows[1]).outcome == "cumple"
    assert current(offer, rows[2]).doubt == "pendiente_informe_tecnico"


def test_an_ok_for_the_whole_report_names_every_row(pending, evaluator_user):
    """REQ-061: sin renglones, el ok es de todo el informe y nombra a todos."""
    offer, rows = pending
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    assert technical.ok_of(offer, 1).items is None
    assert technical.has_ok(offer, 2)


def test_a_not_fit_row_enters_the_discard_by_item_only(pending, evaluator_user, procedure):
    """REQ-061, REQ-059: un "no cumple" técnico entra al descarte propuesto por renglón, sin
    descartar la oferta entera; un "cumple" no descarta."""
    offer, rows = pending
    assert discard_of(page_of(evaluator_user, procedure), offer) is None
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "no_apto", 3: "apto"})
    discard = discard_of(page_of(evaluator_user, procedure), offer)
    assert discard.is_partial and discard.items == [2]
    ground = discard.by_item[2][0]
    assert ground.result.explanation.startswith("informe técnico aprobado")
    assert ground.requirement_text  # el pliego sigue como fundamento


def test_withdrawing_the_ok_needs_a_note_and_returns_the_row_to_pending(
        pending, evaluator_user, procedure):
    """REQ-061: retirar el ok sin nota se rechaza (y se registra); con nota, la fila vuelve a
    pendiente del informe técnico y deja el descarte."""
    offer, rows = pending
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "no_apto", 3: "apto"})
    with pytest.raises(technical.TechnicalRefused) as refused:
        technical.withdraw_ok(evaluator_user, offer, note="  ")
    assert refused.value.reason == "note_required"
    assert AuditEvent.objects.filter(
        event_type=EventType.EVAL_DECISION, outcome=AuditOutcome.REJECTED,
        detail__kind="technical_ok", detail__reason="note_required").count() == 1
    assert current(offer, rows[2]).outcome == "no_cumple"
    technical.withdraw_ok(evaluator_user, offer, note="El informe volvió a revisión")
    for row in rows.values():
        assert current(offer, row).doubt == "pendiente_informe_tecnico"
    assert discard_of(page_of(evaluator_user, procedure), offer) is None
    assert technical.ok_of(offer, 1).action == "retirar_ok"
    assert not technical.has_ok(offer, 1)
    assert am.TechnicalOk.objects.count() == 2


def test_withdrawing_without_an_ok_is_refused(pending, evaluator_user):
    """REQ-061: no se retira lo que no se dio."""
    offer, _ = pending
    with pytest.raises(technical.TechnicalRefused) as refused:
        technical.withdraw_ok(evaluator_user, offer, note="No corresponde")
    assert refused.value.reason == "no_ok"
    assert not am.TechnicalOk.objects.exists()


def test_the_operator_cannot_give_or_withdraw_the_ok(pending, operator_user, evaluator_user):
    """REQ-061, P3: solo el evaluador da o retira el ok; el rechazo por rol queda registrado y
    no se guarda nada."""
    offer, rows = pending
    with pytest.raises(RoleRejected):
        technical.give_ok(operator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    with pytest.raises(RoleRejected):
        technical.withdraw_ok(operator_user, offer, note="Quiero retirarlo")
    assert am.TechnicalOk.objects.count() == 1
    assert current(offer, rows[1]).outcome == "cumple"
    assert AuditEvent.objects.filter(
        outcome=AuditOutcome.REJECTED, user=operator_user).count() == 2


@pytest.mark.parametrize("verdicts,reason", [
    ({1: "apto"}, "verdict_required"),
    ({1: "apto", 2: "quizas"}, "verdict_invalid"),
])
def test_every_row_needs_what_the_report_says(pending, evaluator_user, verdicts, reason):
    """REQ-061: el ok lleva por renglón apto o no apto; sin eso no se guarda."""
    offer, _ = pending
    with pytest.raises(technical.TechnicalRefused) as refused:
        technical.give_ok(evaluator_user, offer, verdicts=verdicts)
    assert refused.value.reason == reason
    assert not am.TechnicalOk.objects.exists()


def test_a_row_that_is_not_pending_is_not_touched(procedure, operator_user, evaluator_user):
    """REQ-061: el ok solo cambia filas pendientes del informe técnico: una que ya tiene otro
    resultado queda como está y se informa."""
    offer = make_offer(procedure, operator_user, "Oferente Y",
                       {"oferta.pdf": [f"{DECLARATION}. Texto."]})
    one, two = requirement(procedure, item=1), requirement(procedure, item=2)
    add_run(operator_user, procedure, offer, {one: PENDING, two: "sin_documento"})
    applied = technical.give_ok(
        evaluator_user, offer, verdicts={1: "apto", 2: "no_apto", 3: "apto"})
    assert applied.skipped == [2, 3]
    assert current(offer, one).outcome == "cumple"
    assert current(offer, two).outcome == "sin_documento"


def test_the_matrix_shows_each_reason_and_the_counts_without_changing_discards_or_order(
        pending, evaluator_user, procedure, operator_user):
    """REQ-061, REQ-063, REQ-064: la celda muestra el motivo del «no determinado» y la oferta
    cuenta por motivo; la matriz no cambia descartes ni orden."""
    offer, rows = pending
    other = make_offer(procedure, operator_user, "Oferente W",
                       {"oferta.pdf": [f"{DECLARATION}. Otra."]})
    add_run(operator_user, procedure, other, {
        requirement(procedure, "declaración jurada"): ("no_determinado", "externo"),
        rows[1]: ("no_determinado", "no_se_pudo_leer"),
        rows[2]: ("no_determinado", "en_portal")})
    page = page_of(operator_user, procedure)
    cell = page.cells[(other.pk, rows[1].pk)]
    assert cell.reason_label == "No se pudo leer"
    assert page.cells[(other.pk, rows[2].pk)].reason_label == "El documento está en el Portal"
    status = next(s for s in page.statuses if s.offer.pk == other.pk)
    assert dict(status.by_reason_rows) == {
        "Falta la hoja de compliance": 1, "No se pudo leer": 1,
        "El documento está en el Portal": 1}
    assert page.discards == []
    assert page.cells[(offer.pk, rows[1].pk)].reason == "pendiente_informe_tecnico"
    before_order = [r.offer.pk for r in page.order.totals]
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    after = page_of(operator_user, procedure)
    assert after.discards == []
    assert [r.offer.pk for r in after.order.totals] == before_order


def test_the_matrix_page_shows_the_ok_with_who_and_when_and_the_buttons(
        pending, evaluator_user, operator_user, procedure, client):
    """REQ-061: la pantalla muestra por oferta y renglón el estado del ok con quién y cuándo, y
    los botones solo al evaluador."""
    offer, _ = pending
    url = reverse("assessment:matrix", args=[procedure.pk])
    log_in(client, operator_user)
    text = text_of(client.get(url))
    assert "Pendiente del informe técnico" in text
    assert "Dar el ok del informe técnico" not in text
    technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "no_apto"},
                      note="Visto bueno inventado")
    log_in(client, evaluator_user)
    text = text_of(client.get(url))
    assert "Dar el ok del informe técnico" in text and "Retirar el ok" in text
    assert "Informe técnico aprobado (No apto), ok de" in text
    assert "Visto bueno inventado" in text
    assert "ok de la Comisión al informe técnico" in text


def test_the_screen_gives_and_withdraws_the_ok(pending, evaluator_user, operator_user,
                                                procedure, client):
    """REQ-061: el evaluador da y retira el ok desde la pantalla; el operador recibe 403; un ok
    sin lo que dice el informe vuelve con el motivo."""
    offer, rows = pending
    give = reverse("assessment:technical_give", args=[offer.pk])
    withdraw = reverse("assessment:technical_withdraw", args=[offer.pk])
    log_in(client, operator_user)
    assert client.post(give, {"all": "1", "verdict_1": "apto", "verdict_2": "apto"}) \
        .status_code == 403
    log_in(client, evaluator_user)
    missing = client.post(give, {"item": ["1"], "verdict_1": ""})
    assert missing.status_code == 422
    assert "apto o no apto" in text_of(missing)
    response = client.post(give, {"item": ["1", "2"], "verdict_1": "apto",
                                  "verdict_2": "no_apto", "note": "ok"})
    assert response.status_code == 302
    assert current(offer, rows[2]).outcome == "no_cumple"
    assert client.post(withdraw, {"all": "1"}).status_code == 422
    assert client.post(withdraw, {"all": "1", "note": "Se revisa"}).status_code == 302
    assert current(offer, rows[2]).doubt == "pendiente_informe_tecnico"
