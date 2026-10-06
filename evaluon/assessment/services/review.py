"""Revisión de cada propuesta: confirmar, corregir y rechazar (REQ-053, REQ-056; plan 004,
"Revisión y decisión" y "Roles"; ADR-0039; T-153).

- `confirm`, `correct`, `reject`: la decisión del evaluador sobre el resultado vigente de un par.
  Cada una inserta su fila en `assessment_decision` (quién, cuándo, qué) y deja el hecho
  `eval_decision`, en la misma transacción (P6). La propuesta original no se toca: la
  corrección es otra fila que la nombra (tablas de solo inserción).
- `state_of` y `current_decision`: el estado de un par sale de la última decisión entre
  confirmar, corregir y rechazar sobre el resultado vigente; pedir la subsanación y subsanar
  (T-154) son recorrido y no cambian el estado. Es la única definición de "estado".
- `history`: todo el recorrido del par (propuestas, decisiones, autor, fecha).

Solo el evaluador decide (P3). El rol se comprueba antes de toda transacción, para que el
hecho `rejected` del rol no se pierda; todo lo demás se valida antes de escribir, y una
decisión rechazada deja solo un hecho `eval_decision` en resultado `rejected` con su motivo.
Se decide sobre el resultado vigente: si hay una evaluación más nueva del par, la decisión se
rechaza (la persona debe ver la propuesta nueva); una decisión sobre un resultado no pasa a la
propuesta que lo reemplaza.
"""

from dataclasses import dataclass, field

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import (
    Action,
    Citation,
    CitationKind,
    Decision,
    Outcome,
    Result,
)
from evaluon.assessment.services.evaluate import current_result
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome

DECIDE_OPERATION = "evaluon.assessment.services.review.decide"
HISTORY_OPERATION = "evaluon.assessment.services.review.history"

# Las acciones que fijan el estado de un par (las otras dos son el recorrido de la subsanación).
STATE_ACTIONS = (Action.CONFIRMAR, Action.CORREGIR, Action.RECHAZAR)

PROPOSED = "propuesto"
_STATES = {Action.CONFIRMAR: "confirmado", Action.CORREGIR: "corregido",
           Action.RECHAZAR: "rechazado"}


class ReviewRefused(ValueError):
    """No se guardó la decisión. `reason` es el motivo que queda en el registro y `field`, el
    dato que lo impidió. El mensaje es para la persona: español llano."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass(frozen=True)
class Decided:
    decision: Decision
    event: object


@dataclass
class Stage:
    """Una etapa del recorrido de un par: una propuesta del sistema y lo que se hizo con ella."""

    result: Result
    run: object
    is_current: bool
    state: str
    decisions: list
    citations: dict = field(default_factory=dict)


# --- Estado --------------------------------------------------------------------------------


def current_decision(result):
    """La última decisión de confirmar, corregir o rechazar sobre `result`, o `None`."""
    return (Decision.objects.filter(result=result, action__in=STATE_ACTIONS)
            .select_related("user").order_by("-at", "-pk").first())


def state_of(result):
    """«propuesto» (sin decisión), «confirmado», «corregido» o «rechazado»."""
    decision = current_decision(result)
    return PROPOSED if decision is None else _STATES[decision.action]


def effective_outcome(result):
    """El resultado que rige: el corregido si hay corrección, el propuesto si está propuesto o
    confirmado, y `None` si la propuesta fue rechazada (no hay resultado hasta decidir)."""
    decision = current_decision(result)
    if decision is None or decision.action == Action.CONFIRMAR:
        return result.outcome
    return decision.outcome_after or None


# --- Decidir -------------------------------------------------------------------------------


def _refuse_record(error, action, channel, user, detail):
    audit.record(
        EventType.EVAL_DECISION, outcome=EventOutcome.REJECTED, channel=channel, user=user,
        detail={**detail, "action": action, "reason": error.reason, "message": str(error)})


def decide(user, result_id, action, *, outcome_after="", note="", channel=Channel.SCREEN):
    """Registra la decisión `action` (confirmar, corregir o rechazar) del evaluador sobre el
    resultado `result_id`. Corregir pide el resultado nuevo y la nota; rechazar pide la nota."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=DECIDE_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    detail = {"result": result_id}
    try:
        with transaction.atomic():
            return _decide(user, result_id, action, outcome_after, note, channel)
    except ReviewRefused as error:
        _refuse_record(error, str(action), channel, user, detail)
        raise


def _decide(user, result_id, action, outcome_after, note, channel):
    if action not in STATE_ACTIONS:
        raise ReviewRefused("Elija confirmar, corregir o rechazar.", "unknown_action",
                            "action")
    try:
        result = Result.objects.select_related("offer", "requirement").get(pk=int(result_id))
    except (Result.DoesNotExist, TypeError, ValueError):
        raise ReviewRefused("No hay un resultado con ese número.", "result_not_found",
                            "result")
    if current_result(result.offer, result.requirement).pk != result.pk:
        raise ReviewRefused(
            "Hay una evaluación más nueva de este requisito: revise la propuesta nueva.",
            "result_replaced", "result")
    outcome_after = outcome_after or ""
    if action == Action.CORREGIR:
        if outcome_after not in Outcome.values:
            raise ReviewRefused("Elija el resultado correcto.", "outcome_required",
                                "outcome_after")
        if outcome_after == result.outcome:
            raise ReviewRefused("El resultado elegido es el mismo que propuso el sistema: "
                                "confirme la propuesta o elija otro.", "outcome_unchanged",
                                "outcome_after")
    else:
        outcome_after = ""
    if action in (Action.CORREGIR, Action.RECHAZAR) and not note:
        raise ReviewRefused("Escriba el motivo de la decisión.", "note_required", "note")
    event = audit.record(
        EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
        detail={"result": result.pk, "offer": result.offer_id,
                "requirement": result.requirement_id, "action": action,
                "outcome_before": result.outcome, "outcome_after": outcome_after,
                "note": note})
    decision = Decision.objects.create(
        result=result, action=action, outcome_after=outcome_after, note=note, user=user,
        event=event)
    return Decided(decision=decision, event=event)


def confirm(user, result_id, *, note="", channel=Channel.SCREEN):
    return decide(user, result_id, Action.CONFIRMAR, note=note, channel=channel)


def correct(user, result_id, outcome_after, note, *, channel=Channel.SCREEN):
    return decide(user, result_id, Action.CORREGIR, outcome_after=outcome_after, note=note,
                  channel=channel)


def reject(user, result_id, note, *, channel=Channel.SCREEN):
    return decide(user, result_id, Action.RECHAZAR, note=note, channel=channel)


# --- Historial -----------------------------------------------------------------------------


def history(user, offer_id, requirement_id, *, channel=Channel.SCREEN):
    """El recorrido del par, del resultado más antiguo al vigente: cada propuesta con sus
    fundamentos agrupados por clase y sus decisiones con autor y fecha. Lanza `RoleRejected`
    sin rol de la Comisión y `Result.DoesNotExist` si el par no se evaluó."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=HISTORY_OPERATION,
                            channel=channel)
    results = list(Result.objects.filter(offer_id=offer_id, requirement_id=requirement_id)
                   .select_related("run__matrix_version", "offer", "requirement")
                   .order_by("run__number", "pk"))
    if not results:
        raise Result.DoesNotExist("El par no se evaluó.")
    steps = []
    for result in results:
        rows = list(Citation.objects.filter(result=result).select_related(
            "document", "requirement_quote", "answer__answered_by").order_by("order"))
        steps.append(Stage(
            result=result, run=result.run, is_current=result is results[-1],
            state=state_of(result),
            decisions=list(Decision.objects.filter(result=result).select_related("user")
                           .order_by("at", "pk")),
            citations={kind: [c for c in rows if c.kind == kind]
                       for kind in CitationKind.values}))
    return steps


# --- Lo que la página de un par agrega ------------------------------------------------------


@dataclass
class PairReview:
    state: str
    decision: Decision | None
    can_decide: bool
    outcomes: list


def pair_review(user, page):
    """El estado de la propuesta vigente y si `user` puede decidir sobre ella."""
    decision = current_decision(page.result)
    return PairReview(
        state=PROPOSED if decision is None else _STATES[decision.action], decision=decision,
        can_decide=getattr(user, "commission_role", "") == CommissionRole.EVALUATOR,
        outcomes=[(value, label) for value, label in Outcome.choices
                  if value != page.result.outcome])
