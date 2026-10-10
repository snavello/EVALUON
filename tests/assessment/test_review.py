"""Revisión de cada propuesta: confirmar, corregir, rechazar e historial (REQ-053, REQ-056;
plan 004, "Revisión y decisión"; ADR-0039; T-153). Caso chico, textos inventados (P4); el
modelo es un guion y no hay GPU."""

import pytest
from django.db import ProgrammingError, connection, transaction

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, review
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import DECLARATION, requirement_of, run_all

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposal(offer, operator_user, procedure, model):
    """El resultado vigente "cumple" del requisito de la declaración jurada."""
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION),
                                      explanation="Lo declara el oferente.")
                    if "declaración jurada" in call.requirement else None)
    run_all(operator_user, procedure)
    return evaluate.current_result(offer, requirement_of(procedure, "declaración jurada"))


def test_correcting_keeps_the_original_proposal_with_author_and_date(
        proposal, evaluator_user):
    """REQ-056: corregir deja la propuesta original, la corrección, el autor y la fecha."""
    decided = review.correct(evaluator_user, proposal.pk, "no_cumple", "La firma no es válida.")
    proposal.refresh_from_db()
    assert proposal.outcome == "cumple"  # la propuesta no se pisa
    decision = decided.decision
    assert decision.result_id == proposal.pk and decision.action == "corregir"
    assert decision.outcome_after == "no_cumple" and decision.note == "La firma no es válida."
    assert decision.user == evaluator_user and decision.at is not None
    assert review.state_of(proposal) == "corregido"
    assert review.effective_outcome(proposal) == "no_cumple"
    event = AuditEvent.objects.get(pk=decision.event_id)
    assert event.event_type == EventType.EVAL_DECISION and event.outcome == EventOutcome.OK
    assert event.user == evaluator_user
    assert event.detail["outcome_before"] == "cumple"
    assert event.detail["outcome_after"] == "no_cumple"


def test_confirm_and_reject_set_the_state(proposal, evaluator_user):
    """REQ-056: sin decisión la propuesta está propuesta; confirmar la confirma (el resultado
    rige tal cual); rechazar exige motivo y deja sin resultado que rija."""
    assert review.state_of(proposal) == "propuesto"
    assert review.effective_outcome(proposal) == "cumple"
    review.confirm(evaluator_user, proposal.pk)
    assert review.state_of(proposal) == "confirmado"
    review.reject(evaluator_user, proposal.pk, "No corresponde al requisito.")
    assert review.state_of(proposal) == "rechazado"
    assert review.effective_outcome(proposal) is None
    assert am.Decision.objects.filter(result=proposal).count() == 2  # nada se pisó


def test_only_the_evaluator_decides(proposal, operator_user, no_commission_user):
    """P3, REQ-056: el operador y quien no es de la Comisión no deciden; queda el hecho
    `rejected` y ninguna decisión."""
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            review.confirm(user, proposal.pk)
    assert not am.Decision.objects.exists()
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() >= 2


@pytest.mark.parametrize("action,outcome", [("corregir", "no_cumple"), ("rechazar", "")])
def test_changing_or_rejecting_needs_a_note(proposal, evaluator_user, action, outcome):
    """REQ-056: corregir y rechazar sin motivo se rechazan, con su hecho `rejected`."""
    with pytest.raises(review.ReviewRefused) as caught:
        review.decide(evaluator_user, proposal.pk, action, outcome_after=outcome, note="  ")
    assert caught.value.reason == "note_required"
    assert not am.Decision.objects.exists()
    event = AuditEvent.objects.filter(event_type=EventType.EVAL_DECISION).get()
    assert event.outcome == EventOutcome.REJECTED and event.detail["reason"] == "note_required"


def test_a_correction_needs_a_different_valid_outcome(proposal, evaluator_user):
    """REQ-056: corregir pide uno de los resultados y distinto del propuesto."""
    for outcome, reason in (("", "outcome_required"), ("quizás", "outcome_required"),
                            ("cumple", "outcome_unchanged")):
        with pytest.raises(review.ReviewRefused) as caught:
            review.correct(evaluator_user, proposal.pk, outcome, "Motivo.")
        assert caught.value.reason == reason
    with pytest.raises(review.ReviewRefused):
        review.decide(evaluator_user, proposal.pk, "pedir_subsanacion", note="x")
    assert not am.Decision.objects.exists()


def test_a_decision_on_a_replaced_result_does_not_change_the_new_proposal(
        offer, procedure, proposal, evaluator_user, operator_user, model):
    """REQ-056, ADR-0039: una decisión sobre un resultado reemplazado por uno nuevo no cambia
    la nueva propuesta; y sobre el reemplazado ya no se decide."""
    review.correct(evaluator_user, proposal.pk, "no_cumple", "Motivo.")
    requirement = requirement_of(procedure, "declaración jurada")
    run_all(operator_user, procedure, requirements=[requirement.pk],
            cause=am.Cause.MANUAL)
    newer = evaluate.current_result(offer, requirement)
    assert newer.pk != proposal.pk
    assert review.state_of(newer) == "propuesto"
    assert review.effective_outcome(newer) == "cumple"
    assert review.state_of(proposal) == "corregido"
    with pytest.raises(review.ReviewRefused) as caught:
        review.confirm(evaluator_user, proposal.pk)
    assert caught.value.reason == "result_replaced"


def test_decisions_are_insert_only(proposal, evaluator_user):
    """ADR-0039: una decisión no se modifica ni se borra (triggers de la base)."""
    decision = review.confirm(evaluator_user, proposal.pk).decision
    for sql in ("UPDATE assessment_decision SET note = 'otro' WHERE id = %s",
                "DELETE FROM assessment_decision WHERE id = %s"):
        with pytest.raises(ProgrammingError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [decision.pk])


def test_history_lists_the_whole_path_with_grounds_by_kind(
        offer, procedure, proposal, evaluator_user, operator_user):
    """REQ-056: el historial lista cada propuesta (más antigua primero), sus decisiones con
    autor y fecha; las citas de la oferta son solo las de la oferta y el pliego va aparte."""
    review.correct(evaluator_user, proposal.pk, "no_cumple", "Motivo uno.")
    requirement = requirement_of(procedure, "declaración jurada")
    run_all(operator_user, procedure, requirements=[requirement.pk], cause=am.Cause.MANUAL)
    review.confirm(evaluator_user, evaluate.current_result(offer, requirement).pk)
    stages = review.history(operator_user, offer.pk, requirement.pk)
    assert [s.run.number for s in stages] == [1, 2]
    assert [s.is_current for s in stages] == [False, True]
    assert [s.state for s in stages] == ["corregido", "confirmado"]
    assert stages[0].decisions[0].user == evaluator_user
    assert stages[0].decisions[0].note == "Motivo uno."
    first = stages[0].citations
    assert [c.text for c in first["oferta"]] == [DECLARATION + "."]
    assert first["pliego"] and all(c.kind == "pliego" for c in first["pliego"])
    assert DECLARATION + "." not in [c.text for c in first["pliego"]]
    assert stages[0].result.explanation not in [c.text for c in first["oferta"]]


def test_history_of_a_pair_never_evaluated_is_not_found(offer, operator_user, procedure):
    with pytest.raises(am.Result.DoesNotExist):
        review.history(operator_user, offer.pk, requirement_of(procedure, "sesenta días").pk)
