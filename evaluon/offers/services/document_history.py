"""Historial de los documentos de una oferta: reemplazar, retirar y restituir sin borrar nada
(REQ-099; ADR-0048; plan 014, "Modelo de datos"; T-199). Gemelo de
`tenders.services.document_history`, con las mismas reglas.

- `replace`: carga el archivo nuevo con la carga de siempre (`offers.load_document`: misma
  oferta, mismo tipo y título, lectura encolada) y agrega el cambio `reemplazar` que une los
  dos documentos, con su hecho `document_change`.
- `withdraw` y `restore`: solo agregan un cambio (`retirar`, `restituir`) y su hecho.
- `history`, `current_documents`, `withdrawn_documents` y `replaced_documents`.

El estado se calcula del último cambio de cada documento. Nada se modifica ni se borra (P6).
Lo retirado o reemplazado deja de usarse para evaluar (`assessment.documents`). Las
evaluaciones ya hechas no cambian: `runs_with_withdrawn` dice cuáles usaron un documento que
ya no está vigente, para pedir evaluar de nuevo (no se recalcula sola). En `replace`, la carga
del archivo nuevo es su propia transacción (deja su hecho `offer_load`) y el cambio va después.
"""

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import Document, DocumentChange, DocumentChangeAction
from evaluon.offers.services import offers as offers_service

REPLACE_OPERATION = "evaluon.offers.services.document_history.replace"
WITHDRAW_OPERATION = "evaluon.offers.services.document_history.withdraw"
RESTORE_OPERATION = "evaluon.offers.services.document_history.restore"

STATE_CURRENT = "vigente"
STATE_REPLACED = "reemplazado"
STATE_WITHDRAWN = "retirado"

_STATE_OF = {
    None: STATE_CURRENT,
    DocumentChangeAction.REEMPLAZAR: STATE_REPLACED,
    DocumentChangeAction.RETIRAR: STATE_WITHDRAWN,
    DocumentChangeAction.RESTITUIR: STATE_CURRENT,
}

_NOT_CURRENT = [DocumentChangeAction.REEMPLAZAR, DocumentChangeAction.RETIRAR]


class HistoryRefused(ValueError):
    """No se hizo el cambio. `reason` es el motivo que queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


def state(document):
    """Vigente, reemplazado o retirado, según el último cambio del documento."""
    last = (DocumentChange.objects.filter(document=document).order_by("-id")
            .values_list("action", flat=True).first())
    return _STATE_OF[last]


def _with_last_action(offer):
    last = (DocumentChange.objects.filter(document=OuterRef("pk")).order_by("-id")
            .values("action")[:1])
    return Document.objects.filter(offer=offer).annotate(
        last_action=Subquery(last))


def current_documents(offer):
    """Los documentos vigentes de la oferta, en el orden de carga."""
    return (_with_last_action(offer)
            .filter(Q(last_action__isnull=True) | Q(last_action=DocumentChangeAction.RESTITUIR))
            .order_by("loaded_at", "id"))


def withdrawn_documents(offer):
    """Los documentos retirados de la oferta (se pueden restituir)."""
    return (_with_last_action(offer).filter(last_action=DocumentChangeAction.RETIRAR)
            .order_by("loaded_at", "id"))


def replaced_documents(offer):
    """Los documentos que otro reemplazó."""
    return (_with_last_action(offer).filter(last_action=DocumentChangeAction.REEMPLAZAR)
            .order_by("loaded_at", "id"))


def history(document):
    """Todos los cambios de las versiones de `document` (la cadena de reemplazos a la que
    pertenece), del más viejo al más nuevo, cada uno con su usuario y su momento."""
    chain = {document.pk}
    for source, target in (("new_document_id", "document_id"),
                           ("document_id", "new_document_id")):
        cursor = {document.pk}
        while cursor:
            found = set(DocumentChange.objects.filter(
                **{f"{source}__in": cursor}, action=DocumentChangeAction.REEMPLAZAR)
                .values_list(target, flat=True)) - chain
            chain |= found
            cursor = found
    return list(DocumentChange.objects.filter(document_id__in=chain)
                .select_related("document", "new_document", "user").order_by("id"))


def _detail(document, action, note, new_document=None):
    detail = {"procedure": document.offer.procedure_id, "offer": document.offer_id, "document": document.pk,
              "action": action, "note": note, "file_sha256": document.file_sha256}
    if new_document is not None:
        detail["new_document"] = new_document.pk
        detail["new_file_sha256"] = new_document.file_sha256
    return detail


def _refuse(user, channel, document, action, note, error, new_document=None):
    detail = {**_detail(document, action, note, new_document),
              "reason": error.reason, "message": str(error)}
    audit.record(EventType.DOCUMENT_CHANGE, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail=detail)
    raise error


def _add_change(user, channel, document, action, note, new_document=None):
    """Agrega el cambio y su hecho en una transacción. El documento se bloquea y su estado se
    vuelve a comprobar, para que dos cambios simultáneos no se pisen."""
    expected = {DocumentChangeAction.RESTITUIR: STATE_WITHDRAWN}.get(action, STATE_CURRENT)
    with transaction.atomic():
        Document.objects.select_for_update().get(pk=document.pk)
        if state(document) != expected:
            raise HistoryRefused("El documento cambió de estado mientras tanto.", "changed")
        event = audit.record(
            EventType.DOCUMENT_CHANGE, outcome=Outcome.OK, channel=channel, user=user,
            detail=_detail(document, action, note, new_document))
        return DocumentChange.objects.create(
            document=document, action=action, new_document=new_document, note=note,
            user=user, event=event)


def _require_state(user, channel, document, action, note, expected, message,
                   new_document=None):
    actual = state(document)
    if actual != expected:
        _refuse(user, channel, document, action, note,
                HistoryRefused(message.format(state=actual), f"not_{expected}"),
                new_document)


def link_replacement(user, document, new_document, *, note="", channel=Channel.SCREEN):
    """Agrega el cambio `reemplazar`: `new_document` ya existe y pasa a ser la versión
    vigente en lugar de `document`. Los dos deben ser del mismo oferta y distintos;
    `document` debe estar vigente. Lo usa `replace`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REPLACE_OPERATION,
                            channel=channel)
    action = DocumentChangeAction.REEMPLAZAR
    note = (note or "").strip()
    if document.offer_id != new_document.offer_id:
        _refuse(user, channel, document, action, note, HistoryRefused(
            "El documento nuevo es de otra oferta: no puede reemplazar a este.",
            "other_offer"), new_document)
    if document.pk == new_document.pk:
        _refuse(user, channel, document, action, note, HistoryRefused(
            "Un documento no se reemplaza a sí mismo.", "same_document"), new_document)
    _require_state(user, channel, document, action, note, STATE_CURRENT,
                   "Solo se reemplaza un documento vigente; este está {state}.",
                   new_document)
    return _add_change(user, channel, document, action, note, new_document)


def replace(user, document, *, data, file_name, note="", channel=Channel.SCREEN):
    """Reemplaza `document` por el archivo `data`: lo carga como documento nuevo del misma oferta, tipo y título, y deja el cambio que los une. Devuelve
    `(cambio, carga)`. El archivo anterior queda. Lanza lo que lanza `load_document`
    (`DuplicateFile` si el archivo ya está cargado, `OfferRefused`) y `HistoryRefused` si
    el documento no está vigente; sin rol, `RoleRejected`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REPLACE_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    _require_state(user, channel, document, DocumentChangeAction.REEMPLAZAR, note,
                   STATE_CURRENT, "Solo se reemplaza un documento vigente; este está {state}.")
    loaded = offers_service.load_document(
        user, document.offer, data=data, file_name=file_name, kind=document.kind,
        title=document.title, channel=channel)
    change = link_replacement(user, document, loaded.document, note=note, channel=channel)
    return change, loaded


def withdraw(user, document, note="", *, channel=Channel.SCREEN):
    """Retira un documento vigente: deja de usarse, pero se conserva y se puede restituir."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=WITHDRAW_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    action = DocumentChangeAction.RETIRAR
    _require_state(user, channel, document, action, note, STATE_CURRENT,
                   "Solo se retira un documento vigente; este está {state}.")
    return _add_change(user, channel, document, action, note)


def restore(user, document, *, note="", channel=Channel.SCREEN):
    """Devuelve a vigente un documento retirado."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=RESTORE_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    action = DocumentChangeAction.RESTITUIR
    _require_state(user, channel, document, action, note, STATE_WITHDRAWN,
                   "Solo se restituye un documento retirado; este está {state}.")
    return _add_change(user, channel, document, action, note)


def runs_with_withdrawn(offer):
    """Las evaluaciones de la oferta hechas con un documento que hoy no está vigente:
    `[(evaluación, [documentos])]`. Marca calculada: la evaluación no cambia ni se recalcula
    sola; la Comisión decide evaluar de nuevo."""
    from evaluon.assessment.models import Run

    gone = {d.pk: d for d in _with_last_action(offer).filter(last_action__in=_NOT_CURRENT)}
    rows = []
    for run in Run.objects.filter(offer=offer).order_by("id"):
        used = [gone[entry["document"]] for entry in run.documents
                if entry.get("document") in gone]
        if used:
            rows.append((run, used))
    return rows
