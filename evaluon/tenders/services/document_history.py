"""Historial de los documentos del pliego: reemplazar, retirar y restituir sin borrar nada
(REQ-099; ADR-0048; plan 014, "Modelo de datos"; T-199).

- `replace`: carga el archivo nuevo con la carga de siempre (`documents.load_document`: mismo
  tipo, título y fecha que el documento reemplazado, lectura encolada) y agrega el cambio
  `reemplazar` que une los dos documentos, con su hecho `document_change`.
- `withdraw` y `restore`: solo agregan un cambio (`retirar`, `restituir`) y su hecho.
- `history`: todos los cambios de las versiones de un documento, del más viejo al más nuevo,
  con quién y cuándo.
- `current_documents`, `withdrawn_documents` y `replaced_documents`: los documentos del
  procedimiento según su estado.

El estado se calcula del último cambio de cada documento (no se guarda): sin cambios o con
`restituir` es vigente; `reemplazar`, reemplazado; `retirar`, retirado. Solo un documento
vigente se reemplaza o se retira; solo uno retirado se restituye. Un documento reemplazado no
vuelve: la versión vigente es la nueva. Nada se modifica ni se borra: el documento, su
archivo y sus lecturas quedan, y la tabla de cambios solo admite inserciones (P6).

Lo retirado o reemplazado deja de usarse para proponer la matriz (`matrix.base_documents`) y
para evaluar (`assessment.documents`). Las versiones de la matriz ya validadas no cambian:
`versions_with_withdrawn` dice cuáles se armaron con un documento que ya no está vigente, para
que la sección 2 lo avise.

El rol (operador o evaluador) se comprueba antes de cualquier cambio; un rechazo por estado o
por datos deja el hecho `document_change` en resultado `rejected` con su motivo. Todo hecho
`ok` se escribe en la misma transacción que su cambio. En `replace`, la carga del archivo nuevo
y el vínculo van en una sola transacción: si algo falla no queda el documento nuevo; el
rechazo de la carga sí deja su hecho `tender_load`.
"""

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    Document,
    DocumentChange,
    DocumentChangeAction,
    MatrixVersion,
)
from evaluon.tenders.services import documents as documents_service

REPLACE_OPERATION = "evaluon.tenders.services.document_history.replace"
WITHDRAW_OPERATION = "evaluon.tenders.services.document_history.withdraw"
RESTORE_OPERATION = "evaluon.tenders.services.document_history.restore"

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


def _with_last_action(procedure):
    last = (DocumentChange.objects.filter(document=OuterRef("pk")).order_by("-id")
            .values("action")[:1])
    return Document.objects.filter(procedure=procedure).annotate(
        last_action=Subquery(last))


def current_documents(procedure):
    """Los documentos vigentes del procedimiento, en el orden de carga."""
    return (_with_last_action(procedure)
            .filter(Q(last_action__isnull=True) | Q(last_action=DocumentChangeAction.RESTITUIR))
            .order_by("loaded_at", "id"))


def withdrawn_documents(procedure):
    """Los documentos retirados del procedimiento (se pueden restituir)."""
    return (_with_last_action(procedure).filter(last_action=DocumentChangeAction.RETIRAR)
            .order_by("loaded_at", "id"))


def replaced_documents(procedure):
    """Los documentos que otro reemplazó."""
    return (_with_last_action(procedure).filter(last_action=DocumentChangeAction.REEMPLAZAR)
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
    detail = {"procedure": document.procedure_id, "document": document.pk,
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
    vigente en lugar de `document`. Los dos deben ser del mismo procedimiento y distintos;
    `document` debe estar vigente. Lo usa `replace`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REPLACE_OPERATION,
                            channel=channel)
    action = DocumentChangeAction.REEMPLAZAR
    note = (note or "").strip()
    if document.procedure_id != new_document.procedure_id:
        _refuse(user, channel, document, action, note, HistoryRefused(
            "El documento nuevo es de otro procedimiento: no puede reemplazar a este.",
            "other_procedure"), new_document)
    if document.pk == new_document.pk:
        _refuse(user, channel, document, action, note, HistoryRefused(
            "Un documento no se reemplaza a sí mismo.", "same_document"), new_document)
    _require_state(user, channel, document, action, note, STATE_CURRENT,
                   "Solo se reemplaza un documento vigente; este está {state}.",
                   new_document)
    return _add_change(user, channel, document, action, note, new_document)


def replace(user, document, *, data, file_name, note="", channel=Channel.SCREEN):
    """Reemplaza `document` por el archivo `data`: lo carga como documento nuevo del mismo
    procedimiento, tipo, título y fecha, y deja el cambio que los une. Devuelve
    `(cambio, carga)`. El archivo anterior queda. Lanza lo que lanza `load_document`
    (`DuplicateFile` si el archivo ya está cargado, `DocumentRefused`) y `HistoryRefused` si
    el documento no está vigente; sin rol, `RoleRejected`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REPLACE_OPERATION,
                            channel=channel)
    note = (note or "").strip()
    _require_state(user, channel, document, DocumentChangeAction.REEMPLAZAR, note,
                   STATE_CURRENT, "Solo se reemplaza un documento vigente; este está {state}.")
    # La carga y el vínculo van en una sola transacción: si el vínculo falla, no queda el
    # documento nuevo. Un rechazo de la carga (archivo repetido, formato) no deshace su hecho
    # de rechazo: se captura dentro, se cierra la transacción sin cambios y se vuelve a lanzar.
    refusal = None
    with transaction.atomic():
        try:
            loaded = documents_service.load_document(
                user, document.procedure, data=data, file_name=file_name, kind=document.kind,
                title=document.title, issued_on=document.issued_on, channel=channel)
        except documents_service.DocumentRefused as error:
            refusal = error
        else:
            change = link_replacement(user, document, loaded.document, note=note,
                                      channel=channel)
    if refusal is not None:
        raise refusal
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


def not_current_documents_of(version):
    """Los documentos con que se armó la propuesta de `version` (los que guardó su `run`)
    que hoy no están vigentes."""
    if version.run is None:
        return []
    ids = [entry["document"] for entry in version.run.documents]
    return list(_with_last_action(version.procedure)
                .filter(pk__in=ids, last_action__in=_NOT_CURRENT).order_by("id"))


def versions_with_withdrawn(procedure):
    """Las versiones de la matriz armadas con un documento que ya no está vigente, con esos
    documentos: `[(versión, [documentos])]`. Marca calculada: no cambia ninguna versión."""
    rows = []
    for version in MatrixVersion.objects.filter(procedure=procedure).select_related("run"):
        gone = not_current_documents_of(version)
        if gone:
            rows.append((version, gone))
    return rows
