"""Decisión de la Comisión sobre los descartes propuestos (REQ-091; plan 014, T-210).

`ordering.propose_discards` propone qué descartar y el sistema no decide nada (P3): cada descarte
lo confirma o lo rechaza un evaluador, con una nota opcional, y queda quién y cuándo.

- **Unidad de decisión**: la oferta completa (`line` nulo) o un renglón. Si una oferta tiene un
  motivo que la descarta entera, esa es la única unidad de la oferta (los renglones quedan
  incluidos en ella).
- **Estado**: `propuesto` (sin decisión), `confirmado` o `rechazado`: el de la última decisión
  sobre la evaluación vigente de la oferta (el pedido de su última evaluación). Si la oferta se
  evalúa de nuevo, hay otro pedido y el descarte vuelve a quedar sin decidir; las decisiones
  anteriores quedan en el registro.
- `decide`, `confirm`, `reject`: insertan la fila de `assessment_discard_decision` (tabla de solo
  inserción) y el hecho `discard_decision` en la misma transacción (P6). El rol se comprueba
  antes de toda transacción; cualquier otro rechazo deja solo un hecho `discard_decision` en
  resultado `rejected` con su motivo.
- `confirmed_discards`: los descartes confirmados con la forma que espera
  `ordering.economic_order`, para ordenar respetando solo lo que la Comisión confirmó.
"""

from dataclasses import dataclass

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment import ordering
from evaluon.assessment.models import DiscardAction, DiscardDecision
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome

DECIDE_OPERATION = "evaluon.assessment.services.discards.decide"

PROPOSED = "propuesto"
CONFIRMED = "confirmado"
REJECTED = "rechazado"
_STATES = {DiscardAction.CONFIRMAR: CONFIRMED, DiscardAction.RECHAZAR: REJECTED}


class DiscardRefused(ValueError):
    """No se guardó la decisión. `reason` es el motivo que queda en el registro; el mensaje es
    para la persona, en español llano."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


@dataclass
class DiscardUnit:
    """Un descarte a decidir: la oferta completa (`line` nulo) o un renglón, con sus motivos y la
    evaluación vigente (`request_id`) sobre la que se decide."""

    offer: object
    line: int | None
    grounds: list
    request_id: int | None
    decision: DiscardDecision | None = None
    state: str = PROPOSED

    @property
    def is_whole(self):
        return self.line is None

    @property
    def key(self):
        return (self.offer.pk, self.line)


@dataclass
class Decided:
    decision: DiscardDecision
    event: object


# --- Estado --------------------------------------------------------------------------------


def _request_of(statuses, offer):
    """El pedido de la evaluación vigente de la oferta (el de su última evaluación)."""
    for status in statuses:
        if status.offer.pk == offer.pk and status.run is not None:
            return status.run.request_id
    return None


def units(page):
    """Los descartes propuestos de la página de la matriz, con su estado. Una oferta con motivo
    de descarte completo es una sola unidad; si no, hay una por renglón."""
    found = []
    for discard in page.discards:
        request_id = _request_of(page.statuses, discard.offer)
        if discard.is_whole:
            found.append(DiscardUnit(discard.offer, None, list(discard.whole), request_id))
            continue
        for line in discard.items:
            found.append(DiscardUnit(discard.offer, line, list(discard.by_item[line]),
                                     request_id))
    decisions = {}
    if found:
        for decision in (DiscardDecision.objects
                         .filter(procedure=page.procedure,
                                 request_id__in={u.request_id for u in found if u.request_id},
                                 offer_id__in={u.offer.pk for u in found})
                         .select_related("user").order_by("at", "pk")):
            decisions[(decision.offer_id, decision.line, decision.request_id)] = decision
    for unit in found:
        decision = decisions.get((unit.offer.pk, unit.line, unit.request_id))
        if decision is not None:
            unit.decision = decision
            unit.state = _STATES[decision.action]
    return found


def confirmed_discards(found):
    """`{id de la oferta: Discard}` solo con lo que la Comisión confirmó, para
    `ordering.economic_order`: una oferta completa confirmada sale del orden y un renglón
    confirmado sale del orden de ese renglón."""
    discards = {}
    for unit in found:
        if unit.state != CONFIRMED:
            continue
        discard = discards.setdefault(unit.offer.pk, ordering.Discard(offer=unit.offer))
        if unit.is_whole:
            discard.whole = list(unit.grounds)
        else:
            discard.by_item[unit.line] = list(unit.grounds)
    return discards


# --- Decidir -------------------------------------------------------------------------------


def _refuse_record(error, user, channel, detail):
    audit.record(
        EventType.DISCARD_DECISION, outcome=EventOutcome.REJECTED, channel=channel, user=user,
        detail={**detail, "reason": error.reason, "message": str(error)})


def decide(user, procedure_id, offer_id, line, action, *, note="", channel=Channel.SCREEN):
    """Registra la decisión `action` (confirmar o rechazar) del evaluador sobre el descarte de
    la oferta `offer_id` (`line` nulo: la oferta completa; si no, el renglón). Lanza
    `RoleRejected` sin el rol de evaluador, `DiscardRefused` si no hay tal descarte propuesto o
    ya está decidido de la misma manera, y `Procedure.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=DECIDE_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    detail = {"procedure": procedure_id, "offer": offer_id, "line": line,
              "action": str(action)}
    try:
        with transaction.atomic():
            return _decide(user, procedure_id, offer_id, line, action, note, channel)
    except DiscardRefused as error:
        _refuse_record(error, user, channel, detail)
        raise


def _decide(user, procedure_id, offer_id, line, action, note, channel):
    if action not in _STATES:
        raise DiscardRefused("Elija confirmar o rechazar el descarte.", "unknown_action")
    page = matrix_service.matrix_page(user, procedure_id, channel=channel)
    unit = next((u for u in units(page) if u.key == (offer_id, line)), None)
    if unit is None or unit.request_id is None:
        raise DiscardRefused("Ese descarte ya no está propuesto: la evaluación cambió. "
                             "Revise los descartes propuestos.", "discard_not_found")
    if unit.state == _STATES[action]:
        raise DiscardRefused("Ese descarte ya tiene esa decisión.", "already_decided")
    event = audit.record(
        EventType.DISCARD_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
        detail={"procedure": page.procedure.pk, "offer": offer_id, "line": line,
                "request": unit.request_id, "action": str(action), "note": note})
    decision = DiscardDecision.objects.create(
        procedure=page.procedure, offer=unit.offer, line=line, request_id=unit.request_id,
        action=action, note=note, user=user, event=event)
    return Decided(decision=decision, event=event)


def confirm(user, procedure_id, offer_id, line, *, note="", channel=Channel.SCREEN):
    return decide(user, procedure_id, offer_id, line, DiscardAction.CONFIRMAR, note=note,
                  channel=channel)


def reject(user, procedure_id, offer_id, line, *, note="", channel=Channel.SCREEN):
    return decide(user, procedure_id, offer_id, line, DiscardAction.RECHAZAR, note=note,
                  channel=channel)
