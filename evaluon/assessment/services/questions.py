"""Preguntas a la Comisión y sus respuestas (REQ-055, REQ-056; plan 004, "Preguntas a la
Comisión" y "Roles"; ADR-0009, ADR-0040; T-154).

- `question_list`: las preguntas de un procedimiento, abiertas (sin respuesta) y respondidas, con
  su respuesta vigente (la última) y las anteriores. Lo ven el operador y el evaluador.
- `answer`: responde una pregunta; solo el evaluador (P3). Quien responde elige el alcance:
  `par`, `requisito` (por omisión) o `procedimiento`. Una respuesta nueva a la misma pregunta
  reemplaza a la anterior como vigente y la anterior queda (tablas de solo inserción). Deja el
  hecho `eval_answer` (P6) en la misma transacción. Una pregunta que no se responde sigue
  abierta y no es fundamento de nada (P3, ADR-0009).
- `affected_pairs` y `reevaluate`: responder no cambia lo ya evaluado; ofrece "evaluar de nuevo"
  los pares a los que la respuesta aplica. `reevaluate` pide la evaluación con la causa
  `respuesta` y la respuesta como origen. El pedido es por ofertas y requisitos: evalúa el
  producto de los afectados, que puede incluir algún par más.
- Una respuesta sola no basta para un "cumple" (ADR-0038): lo asegura la evaluación, no este
  módulo.
"""

from dataclasses import dataclass, field

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import Answer, AnswerScope, Cause, Outcome, Question, Result
from evaluon.assessment.services import evaluate
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome

ANSWER_OPERATION = "evaluon.assessment.services.questions.answer"
LIST_OPERATION = "evaluon.assessment.services.questions.question_list"
REEVALUATE_OPERATION = "evaluon.assessment.services.questions.reevaluate"


class AnswerRefused(ValueError):
    """No se guardó la respuesta. `reason` es el motivo que queda en el registro y `field`, el
    dato que lo impidió. El mensaje es para la persona."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass(frozen=True)
class Answered:
    answer: Answer
    event: object
    replaced: Answer | None


@dataclass
class QuestionRow:
    question: Question
    answer: Answer | None
    previous_answers: list = field(default_factory=list)
    # El resultado vigente del par de la pregunta (puede ser posterior al de origen).
    current: Result | None = None

    @property
    def is_open(self):
        return self.answer is None


def question_list(user, procedure, *, channel=Channel.SCREEN):
    """Las preguntas del procedimiento: primero las abiertas y después las respondidas, cada
    grupo de la más nueva a la más antigua."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=LIST_OPERATION,
                            channel=channel)
    questions = list(Question.objects.filter(procedure=procedure).select_related(
        "offer", "requirement", "result").order_by("-created_at", "-pk"))
    by_question = {}
    for answer in (Answer.objects.filter(question__in=questions)
                   .select_related("answered_by").order_by("answered_at", "pk")):
        by_question.setdefault(answer.question_id, []).append(answer)
    rows = []
    for question in questions:
        given = by_question.get(question.pk, [])
        rows.append(QuestionRow(
            question=question, answer=given[-1] if given else None,
            previous_answers=list(reversed(given[:-1])),
            current=evaluate.current_result(question.offer, question.requirement)))
    return sorted(rows, key=lambda row: not row.is_open)


def _record_refusal(error, user, channel, detail):
    audit.record(EventType.EVAL_ANSWER, outcome=EventOutcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason, "message": str(error)})


def answer(user, question_id, text, scope=AnswerScope.REQUISITO, *, channel=Channel.SCREEN):
    """Responde la pregunta `question_id` con `text` y el alcance `scope`. Lanza `RoleRejected`
    si no es evaluador y `AnswerRefused` si falta el texto, el alcance no es válido o la
    pregunta no existe."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=ANSWER_OPERATION,
                            channel=channel)
    detail = {"question": question_id}
    try:
        with transaction.atomic():
            return _answer(user, question_id, (text or "").strip(), scope or "", channel)
    except AnswerRefused as error:
        _record_refusal(error, user, channel, detail)
        raise


def _answer(user, question_id, text, scope, channel):
    try:
        question = Question.objects.select_for_update().get(pk=int(question_id))
    except (Question.DoesNotExist, TypeError, ValueError):
        raise AnswerRefused("No hay una pregunta con ese número.", "question_not_found",
                            "question")
    if not text:
        raise AnswerRefused("Escriba la respuesta.", "text_required", "text")
    if scope not in AnswerScope.values:
        raise AnswerRefused("Elija a qué se aplica la respuesta.", "invalid_scope", "scope")
    replaced = question.answers.order_by("-answered_at", "-pk").first()
    event = audit.record(
        EventType.EVAL_ANSWER, outcome=EventOutcome.OK, channel=channel, user=user,
        detail={"question": question.pk, "question_text": question.text,
                "offer": question.offer_id, "requirement": question.requirement_id,
                "answer_text": text, "scope": scope,
                "replaces": replaced.pk if replaced else None})
    created = Answer.objects.create(question=question, text=text, scope=scope,
                                    answered_by=user, event=event)
    return Answered(answer=created, event=event, replaced=replaced)


# --- Evaluar de nuevo --------------------------------------------------------------------------


def _current_results(offer):
    latest = {}
    for result in (Result.objects.filter(offer=offer).select_related("requirement", "run")
                   .order_by("run__number", "pk")):
        latest[result.requirement_id] = result
    return list(latest.values())


def affected_pairs(answer):
    """Los pares `(oferta, requisito)` con resultado vigente a los que la respuesta aplica: el
    par de la pregunta (`par`), todas las ofertas evaluadas de ese requisito (`requisito`) o
    los pares hoy "no determinado" del procedimiento (`procedimiento`)."""
    question = answer.question
    if answer.scope == AnswerScope.PAR:
        return [(question.offer, question.requirement)]
    pairs = []
    for offer in question.procedure.offers.order_by("number"):
        if answer.scope == AnswerScope.REQUISITO:
            requirements = [question.requirement]
        else:
            requirements = [r.requirement for r in _current_results(offer)
                            if r.outcome == Outcome.NO_DETERMINADO]
        for requirement in requirements:
            if evaluate.current_result(offer, requirement) is not None:
                pairs.append((offer, requirement))
    return pairs


def reevaluate(user, answer_id, *, channel=Channel.SCREEN):
    """Pide evaluar de nuevo los pares afectados por la respuesta `answer_id` (causa
    `respuesta`). Lo pide el evaluador. Lo evaluado antes no se toca: la evaluación nueva es
    otro resultado del par."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REEVALUATE_OPERATION,
                            channel=channel)
    try:
        found = Answer.objects.select_related("question__procedure").get(pk=int(answer_id))
    except (Answer.DoesNotExist, TypeError, ValueError):
        raise AnswerRefused("No hay una respuesta con ese número.", "answer_not_found",
                            "answer")
    pairs = affected_pairs(found)
    if not pairs:
        raise AnswerRefused("La respuesta no aplica a ningún requisito evaluado.",
                            "no_affected_pairs", "answer")
    offers = list(dict.fromkeys(o.pk for o, _ in pairs))
    requirements = list(dict.fromkeys(r.pk for _, r in pairs))
    return evaluate.request_evaluation(
        user, found.question.procedure, offers=offers, requirements=requirements,
        cause=Cause.RESPUESTA, answer=found, channel=channel)
