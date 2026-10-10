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
from evaluon.assessment.models import (
    Answer,
    AnswerScope,
    Cause,
    Outcome,
    Question,
    Request,
    Result,
)
from evaluon.assessment.services import evaluate, review
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.tenders.models import Job, JobKind, JobStatus

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
    currents = evaluate.current_results({q.offer_id for q in questions},
                                        {q.requirement_id for q in questions})
    rows = []
    for question in questions:
        given = by_question.get(question.pk, [])
        rows.append(QuestionRow(
            question=question, answer=given[-1] if given else None,
            previous_answers=list(reversed(given[:-1])),
            current=currents.get((question.offer_id, question.requirement_id))))
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


def _scope_pairs(answer):
    """Todos los pares `(oferta, requisito)` con resultado vigente a los que alcanza el alcance
    de la respuesta."""
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


def _is_decided(offer, requirement):
    return review.state_of(evaluate.current_result(offer, requirement)) != review.PROPOSED


def affected_pairs(answer):
    """Los pares a los que la respuesta aplica y que se pueden evaluar de nuevo: par de la
    pregunta (`par`), ofertas evaluadas de ese requisito (`requisito`) o pares hoy "no
    determinado" (`procedimiento`). Un par que la Comisión ya decidió (confirmado, corregido o
    rechazado) no entra: la evaluación nueva no se pone encima sin que lo pida (ver
    `decided_pairs`)."""
    return [p for p in _scope_pairs(answer) if not _is_decided(*p)]


def decided_pairs(answer):
    """Los pares que la respuesta alcanza pero que la Comisión ya decidió: se avisan y no se
    evalúan de nuevo."""
    return [p for p in _scope_pairs(answer) if _is_decided(*p)]


def is_rectangular(pairs):
    """Si el pedido por ofertas y requisitos evalúa exactamente `pairs` (sin pares de más)."""
    offers = {o.pk for o, _ in pairs}
    requirements = {r.pk for _, r in pairs}
    return len(pairs) == len(offers) * len(requirements)


def _refuse(user, channel, error, detail):
    _record_refusal(error, user, channel, detail)
    raise error


def reevaluate(user, answer_id, *, offer_id=None, channel=Channel.SCREEN):
    """Pide evaluar de nuevo exactamente los pares que `affected_pairs` muestra (causa
    `respuesta`), o los de una sola oferta si se da `offer_id`. Lo pide el evaluador. Lo evaluado
    antes no se toca. El pedido es por ofertas y requisitos: si los pares no forman un
    rectángulo, se rechaza y se pide oferta por oferta. Todo rechazo queda registrado (P6)."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REEVALUATE_OPERATION,
                            channel=channel)
    detail = {"answer": answer_id, "operation": "reevaluate", "offer": offer_id}
    try:
        found = Answer.objects.select_related("question__procedure").get(pk=int(answer_id))
    except (Answer.DoesNotExist, TypeError, ValueError):
        _refuse(user, channel, AnswerRefused(
            "No hay una respuesta con ese número.", "answer_not_found", "answer"), detail)
    pairs = affected_pairs(found)
    if offer_id is not None:
        pairs = [p for p in pairs if str(p[0].pk) == str(offer_id)]
    if not pairs:
        _refuse(user, channel, AnswerRefused(
            "La respuesta no alcanza a ningún requisito que se pueda evaluar de nuevo.",
            "no_affected_pairs", "answer"), detail)
    if not is_rectangular(pairs):
        _refuse(user, channel, AnswerRefused(
            "Los requisitos alcanzados no son los mismos en todas las ofertas: pida la "
            "evaluación oferta por oferta.", "not_rectangular", "answer"), detail)
    offers = list(dict.fromkeys(o.pk for o, _ in pairs))
    requirements = list(dict.fromkeys(r.pk for _, r in pairs))
    return evaluate.request_evaluation(
        user, found.question.procedure, offers=offers, requirements=requirements,
        cause=Cause.RESPUESTA, answer=found, channel=channel)


# --- Evaluar de nuevo los pares respondidos, de una vez (T-231, E-3) ----------------------------


@dataclass(frozen=True)
class AnsweredPairs:
    """Los pares que la Comisión respondió y que siguen con el resultado de antes de la respuesta,
    sin decisión de la Comisión encima: `pairs` son `(oferta, requisito, respuesta)`."""

    pairs: list

    def __len__(self):
        return len(self.pairs)

    @property
    def offers(self):
        return list(dict.fromkeys(o for o, _, _ in self.pairs))

    @property
    def requirements(self):
        return list(dict.fromkeys(r for _, r, _ in self.pairs))

    @property
    def last_answer(self):
        return max((a for _, _, a in self.pairs), key=lambda a: (a.answered_at, a.pk))


def answered_pairs(procedure):
    """Los pares alcanzados por la respuesta vigente de alguna pregunta cuyo resultado vigente es
    anterior a esa respuesta (la evaluación nueva todavía no la tuvo) y que la Comisión no decidió.
    Con pocas consultas: las respuestas, los resultados vigentes y sus decisiones."""
    latest = {}
    for found in (Answer.objects.filter(question__procedure=procedure)
                  .select_related("question").order_by("answered_at", "pk")):
        latest[found.question_id] = found
    if not latest:
        return AnsweredPairs([])
    offers = list(procedure.offers.order_by("number"))
    by_offer = {o.pk: o for o in offers}
    results = evaluate.current_results(offers)
    decisions = review.current_decisions(results.values())
    requirements = {r.requirement_id: r.requirement for r in results.values()}
    found = {}
    for answer in sorted(latest.values(), key=lambda a: (a.answered_at, a.pk)):
        question = answer.question
        if answer.scope == AnswerScope.PAR:
            keys = [(question.offer_id, question.requirement_id)]
        elif answer.scope == AnswerScope.REQUISITO:
            keys = [(o.pk, question.requirement_id) for o in offers]
        else:
            keys = [key for key, r in results.items() if r.outcome == Outcome.NO_DETERMINADO]
        for key in keys:
            result = results.get(key)
            if (result is None or result.run.built_at >= answer.answered_at
                    or review.state_from(decisions.get(result.pk)) != review.PROPOSED):
                continue
            found[key] = (by_offer[key[0]], requirements[key[1]], answer)
    return AnsweredPairs(sorted(found.values(), key=lambda p: (p[0].number, p[1].number)))


NOT_ANSWERED = "No hay respuestas de la Comisión pendientes de evaluar de nuevo."


def _pending_job(procedure):
    return Job.objects.filter(kind=JobKind.EVALUATE_OFFERS, procedure=procedure,
                              status__in=[JobStatus.QUEUED, JobStatus.RUNNING]).first()


def _waiting_covers(job, pairs):
    """Si el pedido en espera (todavía sin empezar) evalúa los pares respondidos: la evaluación
    lee las respuestas vigentes al armar cada oferta, así que los suma cuando corra."""
    if job.status != JobStatus.QUEUED:
        return False
    request = Request.objects.filter(job=job).first()
    if request is None:
        return False
    offers = set(request.offers)
    wanted = None if request.requirements is None else set(request.requirements)
    return all(o.pk in offers and (wanted is None or r.pk in wanted)
               for o, r, _ in pairs.pairs)


def reevaluate_answered(user, procedure, *, channel=Channel.SCREEN):
    """Pide, en un solo pedido, evaluar de nuevo todos los pares respondidos (`answered_pairs`),
    con la causa `respuesta`. Lo pide el evaluador. Si ya hay un pedido en espera o en curso,
    no pide nada y dice qué pasa con los pares respondidos. El pedido es por ofertas y requisitos:
    si alcanzara un par que la Comisión ya decidió, se rechaza para no ponerle una evaluación
    nueva encima. Todo rechazo queda registrado (P6)."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REEVALUATE_OPERATION,
                            channel=channel)
    detail = {"procedure": procedure.pk, "operation": "reevaluate_answered"}
    pairs = answered_pairs(procedure)
    if not len(pairs):
        _refuse(user, channel, AnswerRefused(NOT_ANSWERED, "no_affected_pairs", "answer"), detail)
    job = _pending_job(procedure)
    if job is not None:
        if _waiting_covers(job, pairs):
            message = ("Ya hay una evaluación en espera; los pares respondidos se suman cuando "
                       "termine.")
        else:
            message = ("Ya hay una evaluación en curso; evaluá de nuevo los pares respondidos "
                       "cuando termine.")
        _refuse(user, channel, AnswerRefused(message, "request_in_progress", "answer"), detail)
    offers, requirements = pairs.offers, pairs.requirements
    covered = {(o.pk, r.pk) for o, r, _ in pairs.pairs}
    results = evaluate.current_results(offers, requirements)
    decisions = review.current_decisions(results.values())
    decided = [key for key, result in results.items() if key not in covered
               and review.state_from(decisions.get(result.pk)) != review.PROPOSED]
    if decided:
        _refuse(user, channel, AnswerRefused(
            f"El pedido evaluaría también {len(decided)} pares que la Comisión ya decidió. "
            "Pedí la evaluación de nuevo desde la respuesta de cada pregunta, oferta por oferta.",
            "decided_pairs_included", "answer"), detail)
    return evaluate.request_evaluation(
        user, procedure, offers=[o.pk for o in offers], requirements=[r.pk for r in requirements],
        cause=Cause.RESPUESTA, answer=pairs.last_answer, channel=channel)
