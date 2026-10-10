"""Hoja de compliance por oferta (REQ-073 de la 013; REQ-063 de la 004; ADR-0043; T-189).

La Comisión valida varios chequeos en sistemas externos (Registro de Proveedores, REPSAL, deuda,
Superintendencia de Seguros, habilidad para contratar). Ese resultado consta en un documento, la
hoja de compliance, y es **uno por oferta**: se sube una vez (también una que diga que no cumple)
y rige para todos los requisitos externos de la oferta.

1. `upload_sheet`: el evaluador sube la hoja. Queda como documento de la oferta, de tipo
   `compliance`, con la carga de la 008 (huella, original y lectura en la cola) y un hecho
   `eval_decision` (P6). Sube desde la matriz de evaluación; la vía por requisito (`remedy.py`)
   sigue andando.
2. Cuando la lectura de la hoja termina, `after_read` (lo llama la cola, ya cerrado el pedido de
   lectura) pide evaluar de nuevo **todos** los requisitos externos de la oferta, con la causa
   `subsanacion`: la evaluación nueva lee la hoja y cita su texto (cumple o no cumple, con cita
   literal) o, si la hoja no trata ese chequeo, deja «no determinado» (`externals.py`).
3. `reevaluate_externals`: lo mismo a mano, si el pedido automático no pudo encolarse (por
   ejemplo, otra evaluación en curso). Sin avance fino en la cola: el pedido es el de la 004.

Solo el evaluador sube la hoja y pide la reevaluación (P3). El rol se comprueba antes de todo.
"""

from dataclasses import dataclass

from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import Cause, Doubt, Outcome, Result
from evaluon.assessment.services import evaluate, review
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.models import Document, DocumentKind, Offer
from evaluon.offers.services import offers as offers_service

UPLOAD_OPERATION = "evaluon.assessment.services.compliance.upload_sheet"
REEVALUATE_OPERATION = "evaluon.assessment.services.compliance.reevaluate_externals"


class ComplianceRefused(ValueError):
    """No se hizo. `reason` es el motivo que queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


@dataclass
class Uploaded:
    document: Document
    event: object
    external_pending: int


def sheets_of(offer):
    """Las hojas de compliance de la oferta, de la más vieja a la más nueva."""
    return list(offer.documents.filter(kind=DocumentKind.COMPLIANCE)
                .order_by("loaded_at", "id"))


def sheets_by_offer(offers):
    """`{id de la oferta: sus hojas de compliance}` con una sola consulta (T-223)."""
    found = offers_service.documents_of_kind(offers, DocumentKind.COMPLIANCE)
    return {offer.pk: found.get(offer.pk, []) for offer in offers}


def external_results(offer):
    """Los resultados vigentes de la oferta que rigen como «falta la hoja de compliance»
    (no determinado `externo`, no rechazados): lo que la hoja deja por resolver."""
    return external_results_by_offer([offer])[offer.pk]


def external_results_by_offer(offers):
    """`{id de la oferta: external_results(oferta)}` con dos consultas en total (T-223)."""
    candidates = [r for r in evaluate.current_results(offers).values()
                  if r.outcome == Outcome.NO_DETERMINADO and r.doubt == Doubt.EXTERNO]
    decisions = review.current_decisions(candidates)
    found = {offer.pk: [] for offer in offers}
    for r in candidates:
        if review.outcome_from(r, decisions.get(r.pk)) == Outcome.NO_DETERMINADO:
            found[r.offer_id].append(r)
    return {pk: sorted(rows, key=lambda r: r.requirement.number)
            for pk, rows in found.items()}


def _offer(offer_id):
    try:
        return Offer.objects.select_related("procedure").get(pk=int(offer_id))
    except (Offer.DoesNotExist, TypeError, ValueError):
        raise ComplianceRefused("No hay una oferta con ese número.", "offer_not_found")


def upload_sheet(user, offer_id, *, data, file_name, title="", note="",
                 channel=Channel.SCREEN):
    """El evaluador sube la hoja de compliance (`data`, con su nombre `file_name`) de la oferta.
    Lanza lo de la carga de la 008 (`OfferRefused`, `DuplicateFile`) si el archivo no se
    acepta."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=UPLOAD_OPERATION,
                            channel=channel)
    offer = _offer(offer_id)
    title = (title or "").strip() or (
        f"Hoja de compliance · {offers_service._title_from(file_name)}")
    loaded = offers_service.load_document(
        user, offer, data=data, file_name=file_name, title=title,
        kind=DocumentKind.COMPLIANCE, channel=channel)
    pending = len(external_results(offer))
    with transaction.atomic():
        event = audit.record(
            EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
            detail={"action": "hoja_compliance", "offer": offer.pk,
                    "procedure": offer.procedure_id, "document": loaded.document.pk,
                    "file_sha256": loaded.document.file_sha256,
                    "load_event": loaded.event.pk, "externals_pending": pending,
                    "note": (note or "").strip()})
    return Uploaded(document=loaded.document, event=event, external_pending=pending)


def _request(user, offer, channel):
    """Pide evaluar de nuevo los requisitos externos de la oferta; `None` si no hay ninguno."""
    results = external_results(offer)
    if not results:
        return None
    return evaluate.request_evaluation(
        user, offer.procedure, offers=[offer.pk],
        requirements=[r.requirement_id for r in results], cause=Cause.SUBSANACION,
        channel=channel)


def reevaluate_externals(user, offer_id, *, channel=Channel.SCREEN):
    """Pide evaluar de nuevo todos los requisitos externos de la oferta, leyendo su hoja.
    Lanza `ComplianceRefused` si no hay hoja o no hay requisitos externos por resolver y
    `EvaluationRefused` si no se puede pedir (documentos en lectura, pedido en curso)."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REEVALUATE_OPERATION,
                            channel=channel)
    offer = _offer(offer_id)
    detail = {"action": "reevaluar_externos", "offer": offer.pk}
    refusal = None
    if not sheets_of(offer):
        refusal = ComplianceRefused("La oferta todavía no tiene hoja de compliance.",
                                    "sheet_not_uploaded")
    elif not external_results(offer):
        refusal = ComplianceRefused(
            "La oferta no tiene requisitos «falta la hoja de compliance» por resolver.",
            "nothing_to_evaluate")
    if refusal is not None:
        audit.record(EventType.EVAL_REQUEST, outcome=EventOutcome.REJECTED, channel=channel,
                     user=user, detail={**detail, "reason": refusal.reason,
                                        "message": str(refusal)})
        raise refusal
    return _request(user, offer, channel)


def after_read(job):
    """Paso posterior de la lectura de un documento (lo llama la cola con el pedido ya
    cerrado): si era una hoja de compliance, pide evaluar de nuevo los requisitos externos de
    su oferta. Si el pedido no se pudo encolar, queda el hecho rechazado (P6) y la Comisión lo
    pide a mano desde la matriz."""
    document = Document.objects.select_related("offer__procedure", "loaded_by").filter(
        pk=job.target_id, kind=DocumentKind.COMPLIANCE).first()
    if document is None or document.loaded_by is None:
        return None
    try:
        return _request(document.loaded_by, document.offer, Channel.COMMAND)
    except evaluate.EvaluationRefused:
        return None  # `request_evaluation` ya dejó el hecho rechazado con su motivo
