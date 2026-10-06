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

Solo el evaluador pide, agrega y reevalúa (P3). El rol se comprueba antes de toda transacción.
Un resultado rechazado no rige (`effective_outcome` en `None`): no se subsana.
"""

from dataclasses import dataclass

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import Action, Cause, Decision, Doubt, Outcome, Result
from evaluon.assessment.services import evaluate, review
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.services import offers as offers_service

REQUEST_OPERATION = "evaluon.assessment.services.remedy.request_remedy"
ADD_OPERATION = "evaluon.assessment.services.remedy.add_document"
REEVALUATE_OPERATION = "evaluon.assessment.services.remedy.reevaluate"


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


# --- Estado ------------------------------------------------------------------------------------


def is_remediable(result):
    """El resultado vigente admite subsanación si rige como "no se encontró el documento" o
    como "falta la hoja de compliance" (no determinado `externo`). Rechazado: no rige."""
    effective = review.effective_outcome(result)
    if effective == Outcome.SIN_DOCUMENTO:
        return True
    return (effective == Outcome.NO_DETERMINADO == result.outcome
            and result.doubt == Doubt.EXTERNO)


def state(result):
    """El estado de la subsanación de `result` (sin comprobar roles: lo usa la pantalla)."""
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
        and reading == offers_service.STATE_READ)


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
