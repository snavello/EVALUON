"""Subsanación: pedirla, agregar el documento y evaluar de nuevo (REQ-060, REQ-056; plan 004,
"Subsanación" y "Decisiones del responsable", punto 1; ADR-0039; T-154).

El circuito sirve para dos resultados de un par: "no se encontró el documento" y "falta la hoja
de compliance" (no determinado, motivo `externo`): la hoja es un documento más de la oferta.

1. `request_remedy`: el evaluador, con una nota, pide la subsanación del resultado vigente.
   Queda una decisión `pedir_subsanacion` (con su hecho `eval_decision`); no cambia el estado
   del par.
2. `add_document`: el evaluador agrega a la oferta el documento (o la hoja, aunque diga "no
   cumple") con la carga de la 008 (`offers.load_document`: huella, original y lectura en la
   cola) y lo vincula con una decisión `subsanar`: documento, quién lo cargó y cuándo.
3. `reevaluate`: pide evaluar de nuevo ese requisito de esa oferta (causa `subsanacion`). La
   evaluación nueva lee todos los documentos, el agregado incluido, y crea un resultado con
   `previous` al anterior: las dos evaluaciones quedan. Mientras el documento se está leyendo, el
   pedido se rechaza (`reading_in_progress`) y se repite cuando termina.

4. `decline_remedy` (T-225, REQ-090): el evaluador, con un motivo, decide NO pedir la
   subsanación del resultado vigente. No cambia el estado del par ni crea una decisión sobre el
   resultado: queda solo el hecho `eval_decision` (acción `no_pedir_subsanacion`), que es de
   solo inserción (P6). `declined_for` y `state` lo leen de ahí. Una subsanación ya pedida o ya
   decidida no se vuelve a decidir.

5. `revert_decline` (T-227, REQ-090; decisión del 2026-10-10, «Reversible con motivo»): el
   evaluador, con un motivo obligatorio, revierte el «no pedir» vigente. Es otro hecho
   `eval_decision` (acción `revertir_no_pedir_subsanacion`) con quién, cuándo, por qué y el hecho
   que revierte; el hecho de «no pedir» no se borra ni se cambia (solo inserción, P6). Después de
   revertir, la subsanación vuelve a estar por decidir: se puede pedir o no pedir de nuevo.
   `declined_for` lee los dos hechos en orden y devuelve el «no pedir» que sigue vigente.

Solo el evaluador pide, agrega, reevalúa y decide no pedir o revertirlo (P3). El rol se comprueba antes de toda transacción.
Un resultado rechazado no rige (`effective_outcome` en `None`): no se subsana.
"""

from dataclasses import dataclass

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import Action, Cause, Decision, Doubt, Outcome, Result
from evaluon.assessment.services import evaluate, review
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.services import offers as offers_service

REQUEST_OPERATION = "evaluon.assessment.services.remedy.request_remedy"
ADD_OPERATION = "evaluon.assessment.services.remedy.add_document"
REEVALUATE_OPERATION = "evaluon.assessment.services.remedy.reevaluate"
DECLINE_OPERATION = "evaluon.assessment.services.remedy.decline_remedy"
# La acción del hecho que deja `decline_remedy` (no es una `Action` de `Decision`).
DECLINE_ACTION = "no_pedir_subsanacion"
REVERT_OPERATION = "evaluon.assessment.services.remedy.revert_decline"
REVERT_DECLINE_ACTION = "revertir_no_pedir_subsanacion"


class RemedyRefused(ValueError):
    """No se hizo. `reason` es el motivo que queda en el registro; el mensaje es para la
    persona."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass
class RemedyState:
    """Dónde está la subsanación de un resultado, para la pantalla."""

    applicable: bool
    requested: Decision | None
    added: Decision | None
    reading: str
    can_reevaluate: bool
    declined: AuditEvent | None = None  # el hecho de «no pedir», si se decidió


# --- Estado ------------------------------------------------------------------------------------


def is_remediable(result):
    """El resultado vigente admite subsanación si rige como "no se encontró el documento" o
    como "falta la hoja de compliance" (no determinado `externo`). Rechazado: no rige."""
    effective = review.effective_outcome(result)
    if effective == Outcome.SIN_DOCUMENTO:
        return True
    return (effective == Outcome.NO_DETERMINADO == result.outcome
            and result.doubt == Doubt.EXTERNO)


def declined_for(result_ids):
    """`{resultado: hecho}` de los resultados de `result_ids` para los que la Comisión decidió no
    pedir la subsanación y no lo revirtió (el primer hecho `ok` de cada uno, salvo que un hecho
    posterior lo haya revertido), en una sola consulta."""
    found = {}
    events = (AuditEvent.objects.filter(
        event_type=EventType.EVAL_DECISION, outcome=EventOutcome.OK,
        detail__action__in=(DECLINE_ACTION, REVERT_DECLINE_ACTION),
        detail__result__in=list(result_ids))
        .select_related("user").order_by("pk"))
    for event in events:
        if event.detail["action"] == REVERT_DECLINE_ACTION:
            found.pop(event.detail["result"], None)
        else:
            found.setdefault(event.detail["result"], event)
    return found


def reverted_for(result_ids):
    """`{resultado: hecho}` con la última reversión de «no pedir» de cada resultado de
    `result_ids` (para mostrar quién, cuándo y por qué), en una sola consulta."""
    found = {}
    events = (AuditEvent.objects.filter(
        event_type=EventType.EVAL_DECISION, outcome=EventOutcome.OK,
        detail__action=REVERT_DECLINE_ACTION, detail__result__in=list(result_ids))
        .select_related("user").order_by("pk"))
    for event in events:
        found[event.detail["result"]] = event
    return found


_LOOK_UP = object()


def state(result, *, declined=_LOOK_UP):
    """El estado de la subsanación de `result` (sin comprobar roles: lo usa la pantalla).
    `declined` es el hecho de «no pedir» si quien llama ya lo buscó con `declined_for`."""
    is_current = evaluate.current_result(result.offer, result.requirement).pk == result.pk
    applicable = is_current and is_remediable(result)
    decisions = list(Decision.objects.filter(
        result=result, action__in=(Action.PEDIR_SUBSANACION, Action.SUBSANAR))
        .select_related("document", "user").order_by("at", "pk"))
    requested = next((d for d in decisions if d.action == Action.PEDIR_SUBSANACION), None)
    added = next((d for d in reversed(decisions) if d.action == Action.SUBSANAR), None)
    reading = ""
    if added is not None:
        reading = offers_service.document_row(added.document).state
    return RemedyState(
        applicable=applicable, requested=requested, added=added, reading=reading,
        can_reevaluate=applicable and added is not None
        and reading == offers_service.STATE_READ,
        declined=(declined_for([result.pk]).get(result.pk) if declined is _LOOK_UP
                  else declined))


# --- Acciones ----------------------------------------------------------------------------------


def _refuse_record(error, user, channel, detail):
    audit.record(EventType.EVAL_DECISION, outcome=EventOutcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason, "message": str(error)})


def _result_for_remedy(result_id):
    try:
        result = Result.objects.select_related("offer__procedure", "requirement", "run").get(
            pk=int(result_id))
    except (Result.DoesNotExist, TypeError, ValueError):
        raise RemedyRefused("No hay un resultado con ese número.", "result_not_found",
                            "result")
    if evaluate.current_result(result.offer, result.requirement).pk != result.pk:
        raise RemedyRefused(
            "Hay una evaluación más nueva de este requisito: revise la propuesta nueva.",
            "result_replaced", "result")
    if not is_remediable(result):
        raise RemedyRefused(
            "Solo se subsana un resultado «no se encontró el documento» o «falta la hoja de "
            "compliance» que rija.", "not_remediable", "result")
    return result


def request_remedy(user, result_id, note, *, channel=Channel.SCREEN):
    """El evaluador pide que se subsane el resultado `result_id`, con una nota."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REQUEST_OPERATION,
                            channel=channel)
    detail = {"result": result_id, "action": Action.PEDIR_SUBSANACION}
    note = (note or "").strip()
    try:
        with transaction.atomic():
            result = _result_for_remedy(result_id)
            if not note:
                raise RemedyRefused("Escriba el motivo del pedido.", "note_required", "note")
            event = audit.record(
                EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
                detail={**detail, "result": result.pk, "offer": result.offer_id,
                        "requirement": result.requirement_id,
                        "outcome_before": result.outcome, "doubt": result.doubt,
                        "note": note})
            decision = Decision.objects.create(
                result=result, action=Action.PEDIR_SUBSANACION, note=note, user=user,
                event=event)
    except RemedyRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
    return review.Decided(decision=decision, event=event)


def decline_remedy(user, result_id, note, *, channel=Channel.SCREEN):
    """El evaluador decide no pedir la subsanación del resultado `result_id`, con un motivo.
    Devuelve el hecho `eval_decision` que lo registra. Lanza `RemedyRefused` sin motivo, si el
    resultado no se puede subsanar, si ya se pidió (`already_requested`) o si ya se decidió no
    pedirla (`already_declined`); sin el rol de evaluador, `RoleRejected`."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=DECLINE_OPERATION,
                            channel=channel)
    detail = {"result": result_id, "action": DECLINE_ACTION}
    note = (note or "").strip()
    try:
        with transaction.atomic():
            result = _result_for_remedy(result_id)
            # Se bloquea el resultado para que dos decisiones simultáneas no se pisen.
            Result.objects.select_for_update().filter(pk=result.pk).first()
            if not note:
                raise RemedyRefused("Escriba el motivo para no pedir la subsanación.",
                                    "note_required", "note")
            if Decision.objects.filter(result=result,
                                       action=Action.PEDIR_SUBSANACION).exists():
                raise RemedyRefused("La subsanación de este resultado ya se pidió.",
                                    "already_requested", "result")
            if declined_for([result.pk]):
                raise RemedyRefused("Ya se decidió no pedir la subsanación de este resultado.",
                                    "already_declined", "result")
            event = audit.record(
                EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
                detail={**detail, "result": result.pk, "offer": result.offer_id,
                        "requirement": result.requirement_id,
                        "outcome_before": result.outcome, "doubt": result.doubt,
                        "note": note})
    except RemedyRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
    return event


def revert_decline(user, result_id, note, *, channel=Channel.SCREEN):
    """El evaluador revierte el «no pedir» vigente del resultado `result_id`, con un motivo
    obligatorio. Devuelve el hecho `eval_decision` que lo registra. Lanza `RemedyRefused` sin
    motivo (`note_required`), si el resultado no se puede subsanar o si no hay un «no pedir»
    vigente (`not_declined`); sin el rol de evaluador, `RoleRejected`."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REVERT_OPERATION,
                            channel=channel)
    detail = {"result": result_id, "action": REVERT_DECLINE_ACTION}
    note = (note or "").strip()
    try:
        with transaction.atomic():
            result = _result_for_remedy(result_id)
            # Se bloquea el resultado para que dos decisiones simultáneas no se pisen.
            Result.objects.select_for_update().filter(pk=result.pk).first()
            if not note:
                raise RemedyRefused("Escriba el motivo para revertir «no pedir».",
                                    "note_required", "note")
            declined = declined_for([result.pk]).get(result.pk)
            if declined is None:
                raise RemedyRefused("Este resultado no tiene una decisión de no pedir la "
                                    "subsanación para revertir.", "not_declined", "result")
            event = audit.record(
                EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
                detail={**detail, "result": result.pk, "offer": result.offer_id,
                        "requirement": result.requirement_id, "declined_event": declined.pk,
                        "declined_by": declined.user.username if declined.user_id else "",
                        "declined_note": declined.detail.get("note", ""), "note": note})
    except RemedyRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
    return event


def add_document(user, result_id, *, data, file_name, title="", note="",
                 channel=Channel.SCREEN):
    """El evaluador agrega el documento `data` (bytes, con su nombre `file_name`) a la oferta del
    resultado `result_id`, que ya tiene el pedido de subsanación. Lanza lo de la carga de la
    008 (`OfferRefused`, `DuplicateFile`) si el archivo no se acepta."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=ADD_OPERATION,
                            channel=channel)
    detail = {"result": result_id, "action": Action.SUBSANAR}
    try:
        result = _result_for_remedy(result_id)
        if not Decision.objects.filter(result=result,
                                       action=Action.PEDIR_SUBSANACION).exists():
            raise RemedyRefused("Primero pida la subsanación de este resultado.",
                                "remedy_not_requested", "result")
    except RemedyRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
    # La carga deja su propio hecho (también si se rechaza); después se vincula.
    loaded = offers_service.load_document(user, result.offer, data=data, file_name=file_name,
                                          title=title, channel=channel)
    with transaction.atomic():
        event = audit.record(
            EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
            detail={**detail, "result": result.pk, "offer": result.offer_id,
                    "requirement": result.requirement_id,
                    "document": loaded.document.pk,
                    "file_sha256": loaded.document.file_sha256,
                    "load_event": loaded.event.pk, "note": (note or "").strip()})
        decision = Decision.objects.create(
            result=result, action=Action.SUBSANAR, document=loaded.document,
            note=(note or "").strip(), user=user, event=event)
    return review.Decided(decision=decision, event=event)


def reevaluate(user, result_id, *, channel=Channel.SCREEN):
    """Pide evaluar de nuevo el requisito del resultado `result_id` para su oferta (causa
    `subsanacion`). Lanza `RemedyRefused` si no hay documento agregado y `EvaluationRefused`
    (`reading_in_progress`) si el documento todavía se está leyendo."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REEVALUATE_OPERATION,
                            channel=channel)
    detail = {"result": result_id, "action": "reevaluar"}
    try:
        result = _result_for_remedy(result_id)
        added = (Decision.objects.filter(result=result, action=Action.SUBSANAR)
                 .order_by("-at", "-pk").first())
        if added is None:
            raise RemedyRefused("Todavía no se agregó el documento de la subsanación.",
                                "document_not_added", "result")
    except RemedyRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
    return evaluate.request_evaluation(
        user, result.offer.procedure, offers=[result.offer.pk],
        requirements=[result.requirement_id], cause=Cause.SUBSANACION, decision=added,
        channel=channel)
