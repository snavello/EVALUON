"""Decisión de la Comisión sobre los descartes propuestos (REQ-091; plan 014, T-210). Caso chico
y cotizaciones inventadas (P4); los resultados se guardan directo, sin el modelo."""

from decimal import Decimal

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment import ordering
from evaluon.assessment.services import discards
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    open_matrix,
    page_of,
    requirement,
    three,
)
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401  (fixtures y ayudas)

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposed(three, portal, procedure, operator_user):  # noqa: F811
    """B con un motivo que la descarta entera; C con un motivo que descarta solo el renglón 2;
    A sin motivos. Con cotizaciones del Portal."""
    a, b, c = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    add_run(operator_user, procedure, b, {declaration: "no_cumple"})
    add_run(operator_user, procedure, c, {requirement(procedure, item=2): "no_cumple",
                                          requirement(procedure, item=1): "cumple"})
    quote_data(portal, procedure, a, total=Decimal("900"), prices={1: (Decimal("10"), 1),
                                                                 2: (Decimal("10"), 1)})
    quote_data(portal, procedure, b, total=Decimal("100"), prices={1: (Decimal("5"), 1),
                                                                 2: (Decimal("5"), 1)})
    quote_data(portal, procedure, c, total=Decimal("500"), prices={1: (Decimal("7"), 1),
                                                                 2: (Decimal("7"), 1)})
    return three


def units_of(user, procedure):
    return {u.key: u for u in discards.units(page_of(user, procedure))}


def decide_events(outcome):
    return AuditEvent.objects.filter(event_type=EventType.DISCARD_DECISION, outcome=outcome)


def test_each_proposed_discard_is_a_unit_to_decide_and_starts_without_decision(
        proposed, procedure, operator_user):
    """REQ-091: la oferta con motivo completo es una unidad; la de un renglón, otra; sin decidir."""
    a, b, c = proposed
    found = units_of(operator_user, procedure)
    assert set(found) == {(b.pk, None), (c.pk, 2)}
    assert all(u.state == discards.PROPOSED and u.decision is None for u in found.values())
    assert found[(b.pk, None)].grounds and found[(c.pk, 2)].grounds[0].item == 2


def test_the_evaluator_confirms_and_it_is_recorded_with_who_and_when(
        proposed, procedure, evaluator_user):
    """REQ-091: confirmar deja la fila (quién, cuándo, nota) y el hecho `discard_decision`."""
    b = proposed[1]
    request = b.assessment_runs.get().request
    done = discards.confirm(evaluator_user, procedure.pk, b.pk, None, note="  Falta la DJ.  ")
    row = am.DiscardDecision.objects.get()
    assert (row.offer_id, row.line, row.request_id, row.action) == (
        b.pk, None, request.pk, am.DiscardAction.CONFIRMAR)
    assert row.user == evaluator_user and row.note == "Falta la DJ." and row.at
    assert row.event_id == done.event.pk
    event = decide_events(AuditOutcome.OK).get()
    assert event.user == evaluator_user and event.detail["offer"] == b.pk
    assert event.detail["action"] == "confirmar" and event.detail["request"] == request.pk
    found = units_of(evaluator_user, procedure)
    assert found[(b.pk, None)].state == discards.CONFIRMED
    assert found[(b.pk, None)].decision.user == evaluator_user
    assert found[(proposed[2].pk, 2)].state == discards.PROPOSED


def test_the_evaluator_rejects_a_discard_with_an_optional_note(
        proposed, procedure, evaluator_user):
    """REQ-091: rechazar el descarte también queda registrado; la nota es opcional."""
    c = proposed[2]
    discards.reject(evaluator_user, procedure.pk, c.pk, 2)
    row = am.DiscardDecision.objects.get()
    assert (row.action, row.line, row.note) == (am.DiscardAction.RECHAZAR, 2, "")
    assert decide_events(AuditOutcome.OK).filter(detail__action="rechazar").count() == 1
    assert units_of(evaluator_user, procedure)[(c.pk, 2)].state == discards.REJECTED


def test_an_operator_is_refused_with_the_attempt_recorded(proposed, procedure, operator_user):
    """REQ-091: solo el evaluador decide; el operador es rechazado y queda el registro."""
    b = proposed[1]
    with pytest.raises(RoleRejected):
        discards.confirm(operator_user, procedure.pk, b.pk, None)
    assert am.DiscardDecision.objects.count() == 0
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED, user=operator_user,
                                     detail__operation=discards.DECIDE_OPERATION).exists()


@pytest.mark.parametrize("offer, line, action, reason", [
    ("A", None, "confirmar", "discard_not_found"),  # una oferta sin descarte propuesto
    ("B", 3, "confirmar", "discard_not_found"),  # un renglón que no se propone
    ("B", None, "aprobar", "unknown_action"),
])
def test_a_decision_without_a_proposed_discard_or_with_a_bad_action_is_refused_and_recorded(
        proposed, procedure, evaluator_user, offer, line, action, reason):
    """REQ-091: no se decide lo que no está propuesto; el rechazo deja su hecho `rejected`."""
    a, b, c = proposed
    offer_id = b.pk if offer == "B" else a.pk
    with pytest.raises(discards.DiscardRefused) as error:
        discards.decide(evaluator_user, procedure.pk, offer_id, line, action)
    assert error.value.reason == reason
    assert am.DiscardDecision.objects.count() == 0
    assert decide_events(AuditOutcome.REJECTED).filter(detail__reason=reason).count() == 1


def test_repeating_a_decision_is_refused_but_changing_it_is_a_new_row(
        proposed, procedure, evaluator_user):
    """REQ-091: la misma decisión dos veces no duplica la fila; la contraria se suma y rige la
    última, sin tocar la anterior (tabla de solo inserción)."""
    b = proposed[1]
    discards.confirm(evaluator_user, procedure.pk, b.pk, None)
    with pytest.raises(discards.DiscardRefused) as error:
        discards.confirm(evaluator_user, procedure.pk, b.pk, None)
    assert error.value.reason == "already_decided"
    discards.reject(evaluator_user, procedure.pk, b.pk, None, note="Se subsanó.")
    assert am.DiscardDecision.objects.count() == 2
    assert units_of(evaluator_user, procedure)[(b.pk, None)].state == discards.REJECTED


def test_a_new_evaluation_of_the_offer_resets_the_state(
        proposed, procedure, evaluator_user, operator_user):
    """REQ-091: si se evalúa de nuevo, el descarte vuelve a quedar sin decidir y la decisión
    anterior queda en el registro."""
    b, c = proposed[1], proposed[2]
    discards.confirm(evaluator_user, procedure.pk, b.pk, None)
    discards.confirm(evaluator_user, procedure.pk, c.pk, 2)
    add_run(operator_user, procedure, b, {requirement(procedure, "declaración jurada"):
                                          "no_cumple"})
    found = units_of(evaluator_user, procedure)
    assert found[(b.pk, None)].state == discards.PROPOSED
    assert found[(c.pk, 2)].state == discards.CONFIRMED  # su oferta no se evaluó de nuevo
    assert am.DiscardDecision.objects.count() == 2
    discards.confirm(evaluator_user, procedure.pk, b.pk, None)  # decidir sobre la nueva
    assert am.DiscardDecision.objects.count() == 3


def test_the_economic_order_leaves_out_only_the_confirmed_discards(
        proposed, procedure, evaluator_user):
    """REQ-091: el orden respeta lo CONFIRMADO: la oferta completa sale del orden total y el
    renglón confirmado sale del orden de ese renglón; lo solo propuesto o rechazado sigue.
    `propose_discards` y `economic_order` no cambian."""
    a, b, c = proposed
    page = page_of(evaluator_user, procedure)
    before = ordering.economic_order(procedure, page.offers, discards.confirmed_discards(
        discards.units(page)))
    assert [r.offer.number for r in before.totals] == [b.number, c.number, a.number]
    discards.confirm(evaluator_user, procedure.pk, b.pk, None)
    discards.confirm(evaluator_user, procedure.pk, c.pk, 2)
    page = page_of(evaluator_user, procedure)
    found = discards.units(page)
    confirmed = discards.confirmed_discards(found)
    assert set(confirmed) == {b.pk, c.pk}
    order = ordering.economic_order(procedure, page.offers, confirmed)
    assert [(r.offer.number, r.position) for r in order.totals] == [
        (c.number, 1), (a.number, 2)]
    lines = {line.line.number: line for line in order.lines}
    assert [r.offer.number for r in lines[1].rows] == [c.number, a.number]
    assert [r.offer.number for r in lines[2].rows] == [a.number]
    # Lo propuesto por el sistema es lo mismo que antes de decidir.
    assert [(d.offer.pk, d.is_whole) for d in page.discards] == [(b.pk, True), (c.pk, False)]
    # Rechazar lo devuelve al orden.
    discards.reject(evaluator_user, procedure.pk, b.pk, None)
    page = page_of(evaluator_user, procedure)
    again = ordering.economic_order(procedure, page.offers, discards.confirmed_discards(
        discards.units(page)))
    assert b.number in [r.offer.number for r in again.totals]
