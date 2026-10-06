"""Preguntas a la Comisión y sus respuestas (REQ-055, REQ-056; plan 004, "Preguntas a la
Comisión"; ADR-0009, ADR-0040; T-154). Caso chico inventado (P4); el modelo es un guion."""

import pytest
from django.db import ProgrammingError, connection, transaction

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, questions, review
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import number_of, requirement_of, run_all
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

DAYS = "sesenta días"


def ask_about_days(call):
    if DAYS in call.requirement:
        return says("no_consta", exigence="condicion",
                    question="¿Desde cuándo corre el plazo de sesenta días?")


@pytest.fixture
def asked(offer, operator_user, procedure, model):
    """Una evaluación en la que el requisito del plazo queda "no determinado" con pregunta."""
    model.evaluates(ask_about_days)
    run_all(operator_user, procedure)
    return am.Question.objects.get(requirement__number=number_of(procedure, DAYS))


@pytest.fixture
def other_offer(procedure, operator_user):
    return make_offer(procedure, operator_user, "Otro oferente", {
        "oferta.pdf": ["La oferta mantiene su validez por sesenta días corridos."]})


def test_an_unanswered_question_leaves_the_requirement_undetermined_and_is_no_ground(
        asked, offer, operator_user, procedure, model):
    """REQ-055: un dato que no está en la oferta ni en la normativa deja el requisito "no
    determinado" con una pregunta; sin respuesta no entra como fundamento al evaluar de nuevo."""
    result = evaluate.current_result(offer, asked.requirement)
    assert result.outcome == "no_determinado" and result.doubt == "sin_dato"
    assert questions.question_list(operator_user, procedure)[0].is_open
    model.calls.clear()
    run_all(operator_user, procedure, cause=am.Cause.MANUAL)
    asking = [c for c in model.calls if DAYS in c.requirement]
    assert asking and all(not c.answers for c in asking)
    assert not am.Citation.objects.filter(kind="respuesta").exists()


def test_only_the_evaluator_answers(asked, operator_user, no_commission_user):
    """P3, REQ-056: el operador y quien no es de la Comisión no responden; queda el hecho
    rechazado y ninguna respuesta."""
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            questions.answer(user, asked.pk, "Desde la apertura.")
    assert not am.Answer.objects.exists()
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() >= 2


def test_an_answer_keeps_who_when_scope_and_leaves_its_fact(asked, evaluator_user):
    """REQ-056, P6: la respuesta queda con autor, fecha, alcance (por omisión, el requisito) y
    el hecho `eval_answer`."""
    answer = questions.answer(evaluator_user, asked.pk, "  Desde la apertura de ofertas. ").answer
    assert answer.text == "Desde la apertura de ofertas." and answer.scope == "requisito"
    assert answer.answered_by == evaluator_user and answer.answered_at is not None
    event = AuditEvent.objects.get(pk=answer.event_id)
    assert event.event_type == EventType.EVAL_ANSWER and event.outcome == EventOutcome.OK
    assert event.user == evaluator_user and event.detail["scope"] == "requisito"
    assert event.detail["answer_text"] == "Desde la apertura de ofertas."


@pytest.mark.parametrize("text,scope,reason", [
    ("  ", "requisito", "text_required"), ("Algo.", "todo", "invalid_scope")])
def test_an_answer_needs_text_and_a_valid_scope(asked, evaluator_user, text, scope, reason):
    """REQ-056: sin texto o con un alcance que no existe se rechaza, con su hecho."""
    with pytest.raises(questions.AnswerRefused) as caught:
        questions.answer(evaluator_user, asked.pk, text, scope)
    assert caught.value.reason == reason
    assert not am.Answer.objects.exists()
    event = AuditEvent.objects.filter(event_type=EventType.EVAL_ANSWER).get()
    assert event.outcome == EventOutcome.REJECTED and event.detail["reason"] == reason


def test_a_requirement_scope_answer_is_used_for_another_offer_and_shown_with_who_and_when(
        asked, other_offer, operator_user, evaluator_user, procedure, model):
    """REQ-055, REQ-056, ADR-0009: una respuesta de alcance `requisito` llega al modelo en otra
    oferta del mismo requisito y, si la usa, se muestra con quién y cuándo."""
    answer = questions.answer(evaluator_user, asked.pk, "Desde la apertura.").answer
    model.calls.clear()
    model.evaluates(lambda call: says("no_consta", exigence="condicion",
                                      supports=list(call.answers))
                    if DAYS in call.requirement else None)
    run_all(operator_user, procedure, offers=[other_offer.pk], cause=am.Cause.RESPUESTA,
            answer=answer)
    seen = [c for c in model.calls if DAYS in c.requirement]
    assert seen and all(list(c.answers.values())[0][0] == evaluator_user.username
                        for c in seen)
    result = evaluate.current_result(other_offer, asked.requirement)
    cite = result.citations.get(kind="respuesta")
    assert cite.answer == answer and cite.answer.answered_by == evaluator_user
    assert cite.answer.answered_at is not None


def test_a_par_scope_answer_does_not_reach_another_offer(
        asked, other_offer, operator_user, evaluator_user, procedure, model):
    """ADR-0040: el alcance `par` no sale de esa oferta y ese requisito."""
    questions.answer(evaluator_user, asked.pk, "Solo para la primera.", "par")
    model.calls.clear()
    run_all(operator_user, procedure, offers=[other_offer.pk], cause=am.Cause.MANUAL)
    assert all(not c.answers for c in model.calls if DAYS in c.requirement)


def test_an_answer_alone_does_not_make_a_cumple(
        asked, offer, operator_user, evaluator_user, procedure, model):
    """ADR-0038, P3: si el modelo se apoya solo en la respuesta de la Comisión no hay "cumple"."""
    answer = questions.answer(evaluator_user, asked.pk, "Se cumple siempre.").answer
    model.evaluates(lambda call: says("cumple", supports=list(call.answers))
                    if DAYS in call.requirement else None)
    run_all(operator_user, procedure, cause=am.Cause.RESPUESTA, answer=answer)
    result = evaluate.current_result(offer, asked.requirement)
    assert result.outcome == "no_determinado"


def test_a_new_answer_replaces_the_previous_one_and_the_previous_stays(
        asked, evaluator_user, operator_user, procedure):
    """REQ-056, ADR-0040: la respuesta nueva es la vigente y la anterior queda, con su autor
    y su fecha; las filas son de solo inserción."""
    first = questions.answer(evaluator_user, asked.pk, "Primera.").answer
    second = questions.answer(evaluator_user, asked.pk, "Segunda.", "procedimiento")
    assert second.replaced == first
    row = questions.question_list(operator_user, procedure)[0]
    assert row.answer == second.answer and row.previous_answers == [first]
    assert am.Answer.objects.filter(question=asked).count() == 2
    for sql in ("UPDATE assessment_answer SET text = 'otra' WHERE id = %s",
                "DELETE FROM assessment_answer WHERE id = %s"):
        with pytest.raises(ProgrammingError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [first.pk])


def test_answering_does_not_change_what_was_evaluated_and_offers_to_evaluate_again(
        asked, offer, evaluator_user, procedure):
    """ADR-0009: responder no cambia lo evaluado; "evaluar de nuevo" pide otra evaluación, con
    la causa `respuesta` y la respuesta de origen; el resultado anterior sigue como estaba."""
    before = evaluate.current_result(offer, asked.requirement)
    answer = questions.answer(evaluator_user, asked.pk, "Desde la apertura.").answer
    assert evaluate.current_result(offer, asked.requirement).pk == before.pk
    assert questions.affected_pairs(answer) == [(offer, asked.requirement)]
    request = questions.reevaluate(evaluator_user, answer.pk).request
    assert request.cause == "respuesta" and request.answer == answer
    assert request.requirements == [asked.requirement_id]
    assert evaluate.current_result(offer, asked.requirement).pk == before.pk


def test_only_the_evaluator_asks_to_evaluate_again(asked, evaluator_user, operator_user):
    """P3: el operador no pide evaluar de nuevo por una respuesta."""
    answer = questions.answer(evaluator_user, asked.pk, "Desde la apertura.").answer
    with pytest.raises(RoleRejected):
        questions.reevaluate(operator_user, answer.pk)


def test_a_rejected_result_has_no_effective_outcome_and_its_question_still_lists(
        asked, offer, evaluator_user, operator_user, procedure):
    """Aviso de T-153: un resultado rechazado deja `effective_outcome` en `None`; la lista de
    preguntas lo tolera y sigue mostrando la pregunta abierta."""
    result = evaluate.current_result(offer, asked.requirement)
    review.reject(evaluator_user, result.pk, "No corresponde.")
    assert review.effective_outcome(result) is None
    row = questions.question_list(operator_user, procedure)[0]
    assert row.is_open and row.current.pk == result.pk


def test_open_questions_come_first_and_answered_ones_follow(
        asked, evaluator_user, operator_user, procedure, model):
    """REQ-055: la lista pone las preguntas abiertas antes que las respondidas."""
    model.evaluates(lambda call: says("no_consta", exigence="condicion", question="¿Cuál?")
                    if "declaración jurada" in call.requirement or DAYS in call.requirement
                    else None)
    run_all(operator_user, procedure, cause=am.Cause.MANUAL)
    other = am.Question.objects.exclude(pk=asked.pk).get(
        requirement=requirement_of(procedure, "declaración jurada"))
    questions.answer(evaluator_user, other.pk, "Sí.")
    rows = questions.question_list(operator_user, procedure)
    assert rows[0].is_open and rows[0].question == asked
    assert rows[-1].question == other and not rows[-1].is_open
