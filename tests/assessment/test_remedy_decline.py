"""La Comisión decide NO pedir la subsanación de un resultado (REQ-090; maqueta aprobada de la 014,
«No pedir»; T-225). Caso chico inventado (P4); el modelo es un guion."""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import remedy, review
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from tests.assessment.fakes import model  # noqa: F401 - fixture
from tests.assessment.test_remedy import external, missing  # noqa: F401 - fixtures

pytestmark = pytest.mark.django_db


def declines():
    return AuditEvent.objects.filter(event_type=EventType.EVAL_DECISION,
                                     detail__action=remedy.DECLINE_ACTION)


def test_declining_needs_a_reason_and_leaves_who_when_and_the_fact(missing, evaluator_user):
    """REQ-090, P6: no pedir exige motivo; queda el hecho `eval_decision` con quién, cuándo y
    el motivo, y el estado de la subsanación lo muestra. No cambia el estado del par ni crea
    decisiones sobre el resultado."""
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.decline_remedy(evaluator_user, missing.pk, "  ")
    assert caught.value.reason == "note_required"
    assert not declines().filter(outcome=EventOutcome.OK).exists()
    assert declines().filter(outcome=EventOutcome.REJECTED).count() == 1
    event = remedy.decline_remedy(evaluator_user, missing.pk, "El faltante no es esencial.")
    assert (event.event_type, event.outcome) == (EventType.EVAL_DECISION, EventOutcome.OK)
    assert event.user == evaluator_user and event.occurred_at is not None
    assert event.detail["result"] == missing.pk and event.detail["offer"] == missing.offer_id
    assert event.detail["note"] == "El faltante no es esencial."
    assert event.detail["outcome_before"] == "sin_documento"
    state = remedy.state(missing)
    assert state.declined == event and state.requested is None
    assert not am.Decision.objects.exists()
    assert review.state_of(missing) == "propuesto"


def test_a_declined_remedy_cannot_be_declined_again_nor_one_already_requested(
        missing, external, evaluator_user):
    """REQ-090: una subsanación ya decidida no se vuelve a decidir: ni no pedir dos veces, ni
    no pedir lo que ya se pidió."""
    remedy.decline_remedy(evaluator_user, missing.pk, "No es esencial.")
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.decline_remedy(evaluator_user, missing.pk, "Otra vez.")
    assert caught.value.reason == "already_declined"
    remedy.request_remedy(evaluator_user, external.pk, "Se pide la hoja.")
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.decline_remedy(evaluator_user, external.pk, "No.")
    assert caught.value.reason == "already_requested"
    assert declines().filter(outcome=EventOutcome.OK).count() == 1


def test_only_the_evaluator_declines(missing, operator_user, no_commission_user):
    """P3: el operador y quien no es de la Comisión no deciden; el rechazo queda registrado."""
    before = AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count()
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            remedy.decline_remedy(user, missing.pk, "No es esencial.")
    assert not declines().filter(outcome=EventOutcome.OK).exists()
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() == before + 2


def test_only_a_remediable_result_is_declined(missing, evaluator_user):
    """REQ-090: un resultado rechazado no rige y no se subsana: tampoco se decide no pedirlo."""
    review.reject(evaluator_user, missing.pk, "No corresponde.")
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.decline_remedy(evaluator_user, missing.pk, "No es esencial.")
    assert caught.value.reason == "not_remediable"


def test_declined_for_returns_the_decision_of_each_result_in_one_query(
        missing, external, evaluator_user, django_assert_num_queries):
    """REQ-090: la pestaña pide las decisiones de no pedir de todos sus resultados juntas."""
    event = remedy.decline_remedy(evaluator_user, missing.pk, "No es esencial.")
    with django_assert_num_queries(1):
        found = remedy.declined_for([missing.pk, external.pk])
    assert found == {missing.pk: event}


def reverts():
    return AuditEvent.objects.filter(event_type=EventType.EVAL_DECISION,
                                     detail__action=remedy.REVERT_DECLINE_ACTION)


def test_a_decline_is_reverted_with_a_reason_and_leaves_who_when_and_why(
        missing, evaluator_user):
    """REQ-090, P6: «No pedir» se revierte con un motivo obligatorio; queda un hecho propio con
    quién, cuándo y por qué, el hecho de «no pedir» se conserva y la subsanación vuelve a quedar
    por decidir."""
    declined = remedy.decline_remedy(evaluator_user, missing.pk, "No es esencial.")
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.revert_decline(evaluator_user, missing.pk, " ")
    assert caught.value.reason == "note_required"
    assert not reverts().filter(outcome=EventOutcome.OK).exists()
    event = remedy.revert_decline(evaluator_user, missing.pk, "El área técnica la considera esencial.")
    assert (event.event_type, event.outcome) == (EventType.EVAL_DECISION, EventOutcome.OK)
    assert event.user == evaluator_user and event.occurred_at is not None
    assert event.detail["result"] == missing.pk and event.detail["declined_event"] == declined.pk
    assert event.detail["note"] == "El área técnica la considera esencial."
    assert remedy.state(missing).declined is None
    assert declines().filter(outcome=EventOutcome.OK).count() == 1
    assert not am.Decision.objects.exists()


def test_a_reverted_decline_can_be_requested_or_declined_again_and_reverted_again(
        missing, evaluator_user):
    """REQ-090: después de revertir se puede pedir la subsanación o volver a no pedirla (y
    revertir otra vez); cada cambio queda registrado."""
    remedy.decline_remedy(evaluator_user, missing.pk, "Primera decisión.")
    remedy.revert_decline(evaluator_user, missing.pk, "Me equivoqué.")
    second = remedy.decline_remedy(evaluator_user, missing.pk, "Segunda decisión.")
    assert remedy.state(missing).declined == second
    remedy.revert_decline(evaluator_user, missing.pk, "Otra vez.")
    assert remedy.state(missing).declined is None
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide el documento.")
    assert remedy.state(missing).requested is not None
    assert reverts().filter(outcome=EventOutcome.OK).count() == 2


def test_only_a_declined_remedy_is_reverted_and_only_by_the_evaluator(
        missing, evaluator_user, operator_user):
    """REQ-090, P3: sin «no pedir» vigente no hay nada que revertir; el operador no revierte y
    el rechazo queda registrado."""
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.revert_decline(evaluator_user, missing.pk, "Nada que revertir.")
    assert caught.value.reason == "not_declined"
    remedy.decline_remedy(evaluator_user, missing.pk, "No es esencial.")
    before = AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count()
    with pytest.raises(RoleRejected):
        remedy.revert_decline(operator_user, missing.pk, "Quiero revertir.")
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() == before + 1
    assert remedy.state(missing).declined is not None
