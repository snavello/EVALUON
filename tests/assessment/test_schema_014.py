"""Esquema de la 014 en `assessment` (T-193; plan 014, "Modelo de datos"; REQ-091): la
decisión de la Comisión sobre cada descarte propuesto, de solo inserción. Textos inventados
(P4)."""

import pytest
from django.db import IntegrityError, connection, transaction

from evaluon.assessment import models as am
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from tests.assessment.conftest import (  # noqa: F401 - fixtures de la 004 y la 008
    evaluator_user,
    expected,
    matrix,
    offer,
    operator_user,
    procedure,
    rows,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def decide(rows, evaluator_user):
    event = audit.record(EventType.DISCARD_DECISION, outcome=Outcome.OK,
                         channel=Channel.SCREEN, user=evaluator_user)

    def make(**fields):
        values = {"procedure": rows.request.procedure, "offer": rows.run.offer,
                  "line": None, "request": rows.request,
                  "action": am.DiscardAction.CONFIRMAR, "user": evaluator_user,
                  "event": event}
        values.update(fields)
        return am.DiscardDecision.objects.create(**values)

    return make


def test_a_decision_records_who_and_when(decide, evaluator_user):
    """REQ-091: la decisión queda con quién y cuándo, sobre la oferta o un renglón."""
    whole = decide()
    line = decide(line=2, action=am.DiscardAction.RECHAZAR, note="la oferta lo cubre")
    assert (whole.user, whole.line, line.line) == (evaluator_user, None, 2)
    assert whole.at is not None and whole.event_id
    assert am.DiscardDecision.objects.count() == 2


@pytest.mark.parametrize("statement", [
    "UPDATE assessment_discard_decision SET note = 'x'",
    "DELETE FROM assessment_discard_decision"])
def test_the_decision_table_is_insert_only(decide, statement):
    """REQ-091 (P3, P6): UPDATE y DELETE se rechazan, también por SQL."""
    decide()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(statement)


def test_a_decision_cannot_be_modified_from_the_model(decide):
    row = decide()
    row.action = am.DiscardAction.RECHAZAR
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        row.save()


def test_a_later_decision_does_not_overwrite_the_earlier_one(decide):
    """REQ-091: confirmar y luego rechazar son dos filas; la última manda."""
    first = decide()
    second = decide(action=am.DiscardAction.RECHAZAR, note="se revisó")
    last = am.DiscardDecision.objects.order_by("-id").first()
    assert last == second and am.DiscardDecision.objects.filter(pk=first.pk).exists()


def test_an_unknown_action_is_rejected(decide):
    with pytest.raises(IntegrityError), transaction.atomic():
        decide(action="postergar")


def test_a_decision_belongs_to_one_evaluation_request(decide, rows):
    """REQ-091: la decisión nombra el pedido de evaluación sobre el que se tomó."""
    assert decide().request == rows.request
    with pytest.raises(IntegrityError), transaction.atomic():
        decide(request_id=None)


def test_a_decision_needs_its_audit_event(decide):
    with pytest.raises(IntegrityError), transaction.atomic():
        decide(event_id=None)


def test_the_two_actions_are_the_plans():
    assert set(am.DiscardAction.values) == {"confirmar", "rechazar"}
