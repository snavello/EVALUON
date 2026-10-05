"""Corregir la ficha: confirmar, corregir, quitar, restituir y agregar fragmentos (REQ-042;
plan 008, "Revisión (REQ-042)" y "Roles"; ADR-0026; T-132).

- `confirm`: confirma una o varias filas de la ficha y sus fragmentos vigentes. Solo el
  evaluador.
- `correct`: cambia el pasaje y/o el recorte de un fragmento. Lo hace el operador o el
  evaluador.
- `remove` y `restore`: el fragmento queda `quitado`, visible en el historial; restituirlo
  lo devuelve a propuesto.
- `add`: agrega a una fila un fragmento de un pasaje de la oferta y, si se quiere, un recorte
  literal dentro de él.
- `history`: la fila con lo propuesto por el sistema y cada cambio, con quién, cuándo, antes
  y después.

**El texto es siempre un recorte del texto canónico** (P3): el recorte que escribe la persona
se busca dentro del pasaje elegido, con la misma regla que la 003, y el texto guardado es el
del texto canónico de la lectura, nunca lo que se escribió. Un recorte que no está en el
pasaje se rechaza. Los pasajes elegibles son los de las lecturas con que se armó la ficha.

Cada cambio deja una fila en `offers_change` y el hecho `sheet_change`, en la misma
transacción (P6). Una fila confirmada que se cambia vuelve a quedar propuesta: la
confirmación valía para lo de antes. Si a la fila sin fragmentos se le agrega uno, pasa a
"encontrado"; si se quita el último, vuelve a "no se encontró". El rol se comprueba antes
de toda transacción, para que el hecho `rejected` no se pierda; todo lo demás se valida
antes de escribir, y un cambio rechazado deja solo un hecho en resultado `rejected` con su
motivo. El fragmento anterior queda en `before` de la fila de historial.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import (
    Change,
    ChangeAction,
    EntryState,
    Fragment,
    FragmentOrigin,
    FragmentState,
    Passage,
    Sheet,
    SheetEntry,
)
from evaluon.offers.models import Outcome as EntryOutcome
from evaluon.offers.services import sheets as sheets_service
from evaluon.tenders.proposal import quotes as quote_rules

CONFIRM_OPERATION = "evaluon.offers.services.review.confirm"
CORRECT_OPERATION = "evaluon.offers.services.review.correct"
REMOVE_OPERATION = "evaluon.offers.services.review.remove"
RESTORE_OPERATION = "evaluon.offers.services.review.restore"
ADD_OPERATION = "evaluon.offers.services.review.add"
HISTORY_OPERATION = "evaluon.offers.services.review.history"
PAGE_OPERATION = "evaluon.offers.services.review.review_page"


class ReviewRefused(ValueError):
    """No se hizo el cambio. `reason` es el motivo que queda en el registro y `field`, el
    dato que lo impidió, si hay uno. El mensaje es para la persona: español llano."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass(frozen=True)
class Reviewed:
    """Lo que devuelve una operación: las filas tocadas, las filas de historial y los
    hechos registrados."""

    entries: list
    changes: list = field(default_factory=list)
    events: list = field(default_factory=list)


# --- Utilidades ----------------------------------------------------------------------------------


def _refuse_record(error, action, channel, user, detail):
    audit.record(
        EventType.SHEET_CHANGE, outcome=Outcome.REJECTED, channel=channel, user=user,
        detail={**detail, "action": action, "reason": error.reason,
                "message": str(error)},
    )


def _fragment_view(fragment):
    return {"fragment": fragment.pk, "passage": fragment.passage_id,
            "page": fragment.passage.page, "char_start": fragment.char_start,
            "char_end": fragment.char_end, "text": fragment.text, "state": fragment.state,
            "origin": fragment.origin}


def _entry_view(entry):
    return {"state": entry.state, "outcome": entry.outcome}


def _record(entry, action, before, after, user, channel, fragment=None):
    """La fila de historial y el hecho `sheet_change` de un cambio."""
    event = audit.record(
        EventType.SHEET_CHANGE, outcome=Outcome.OK, channel=channel, user=user,
        detail={"action": action, "sheet": entry.sheet_id, "entry": entry.pk,
                "requirement": entry.requirement_id,
                "fragment": None if fragment is None else fragment.pk,
                "before": before, "after": after},
    )
    change = Change.objects.create(entry=entry, fragment=fragment, action=action,
                                   before=before, after=after, user=user, event=event)
    return change, event


def _run(user, role, operation, action, channel, detail, work):
    """Comprueba el rol, corre `work` en una transacción y, si lo rechaza con
    `ReviewRefused`, deja el hecho `rejected` fuera de ella."""
    require_commission_role(user, role, operation=operation, channel=channel)
    try:
        with transaction.atomic():
            return work()
    except ReviewRefused as error:
        _refuse_record(error, action, channel, user, detail)
        raise


def _lock_entry(entry_id):
    try:
        return SheetEntry.objects.select_for_update(of=("self",)).select_related(
            "sheet").get(pk=int(entry_id))
    except (SheetEntry.DoesNotExist, TypeError, ValueError):
        raise ReviewRefused("No hay una fila de la ficha con ese número.",
                            "entry_not_found", "entry")


def _lock_fragment(fragment_id):
    """La fila bloqueada y su fragmento bloqueado. Devuelve `(fila, fragmento)`."""
    try:
        entry_id = Fragment.objects.values_list("entry_id", flat=True).get(
            pk=int(fragment_id))
    except (Fragment.DoesNotExist, TypeError, ValueError):
        raise ReviewRefused("No hay un fragmento con ese número.", "fragment_not_found",
                            "fragment")
    entry = _lock_entry(entry_id)
    fragment = Fragment.objects.select_for_update(of=("self",)).select_related(
        "passage").get(pk=int(fragment_id))
    return entry, fragment


def _passage_of(entry, passage_id):
    """El pasaje elegido, que debe ser de una lectura con que se armó la ficha."""
    try:
        passage = Passage.objects.select_related("reading__document").get(
            pk=int(passage_id))
    except (Passage.DoesNotExist, TypeError, ValueError):
        raise ReviewRefused("Elija un pasaje de la oferta.", "passage_not_found",
                            "passage")
    if passage.reading_id not in {r["reading"] for r in entry.sheet.readings}:
        raise ReviewRefused("Ese pasaje no es de los documentos con que se armó la ficha.",
                            "passage_not_in_offer", "passage")
    return passage


def _verified_span(passage, text):
    """`(inicio, fin, recorte)` en el texto canónico de la lectura. Sin `text`, el pasaje
    entero. El recorte se busca dentro del pasaje y lo que se guarda es el del texto
    canónico, no lo que se escribió (P3)."""
    canonical = passage.reading.canonical_text
    if not (text or "").strip():
        return (passage.char_start, passage.char_end,
                canonical[passage.char_start:passage.char_end])
    span = quote_rules.locate(passage.text, text)
    if span is None:
        raise ReviewRefused(
            "El recorte no está en el pasaje elegido: copie el texto tal como figura en la "
            "oferta.", "quote_not_in_passage", "text")
    start, end = passage.char_start + span[0], passage.char_start + span[1]
    return start, end, canonical[start:end]


def _alive(entry):
    return entry.fragments.exclude(state=FragmentState.QUITADO)


def _touch_entry(entry):
    """Tras un cambio de fragmentos: la fila vuelve a propuesta y su resultado sigue a lo
    que tiene."""
    entry.state = EntryState.PROPUESTO
    entry.outcome = (EntryOutcome.ENCONTRADO if _alive(entry).exists()
                     else EntryOutcome.NO_ENCONTRADO)
    entry.save(update_fields=["state", "outcome"])


# --- Confirmar -----------------------------------------------------------------------------------


def confirm(user, entry_ids, *, channel=Channel.SCREEN):
    """Confirma las filas `entry_ids` (de una sola ficha) y sus fragmentos vigentes. Las ya
    confirmadas no cambian. Solo el evaluador."""
    try:
        ids = sorted({int(i) for i in entry_ids})
    except (TypeError, ValueError):
        ids = []

    def work():
        if not ids:
            raise ReviewRefused("Marque al menos una fila para confirmar.",
                                "nothing_selected", "entries")
        rows = list(SheetEntry.objects.select_for_update().filter(pk__in=ids)
                    .order_by("pk"))
        if len(rows) != len(ids) or len({r.sheet_id for r in rows}) != 1:
            raise ReviewRefused("Las filas a confirmar son de una sola ficha.",
                                "entry_not_found", "entries")
        done = Reviewed(entries=[])
        for entry in rows:
            if entry.state == EntryState.CONFIRMADO:
                continue
            fragments = list(_alive(entry).order_by("order"))
            before = {**_entry_view(entry),
                      "fragments": [{"fragment": f.pk, "state": f.state}
                                    for f in fragments]}
            entry.state = EntryState.CONFIRMADO
            entry.save(update_fields=["state"])
            for fragment in fragments:
                fragment.state = FragmentState.CONFIRMADO
                fragment.save(update_fields=["state"])
            after = {**_entry_view(entry),
                     "fragments": [{"fragment": f.pk, "state": f.state}
                                   for f in fragments]}
            change, event = _record(entry, ChangeAction.CONFIRMAR, before, after, user,
                                    channel)
            done.entries.append(entry)
            done.changes.append(change)
            done.events.append(event)
        return done

    return _run(user, CommissionRole.EVALUATOR, CONFIRM_OPERATION, ChangeAction.CONFIRMAR,
                channel, {"entries": ids}, work)


# --- Corregir, quitar, restituir, agregar --------------------------------------------------------


def correct(user, fragment_id, *, passage_id=None, text="", channel=Channel.SCREEN):
    """Cambia el fragmento por un recorte de un pasaje de la oferta (el mismo si no se indica
    otro; sin `text`, el pasaje entero). El fragmento anterior queda en el historial."""

    def work():
        entry, fragment = _lock_fragment(fragment_id)
        if fragment.state == FragmentState.QUITADO:
            raise ReviewRefused("Un fragmento quitado no se corrige: restitúyalo antes.",
                                "fragment_removed", "fragment")
        passage = _passage_of(entry, passage_id or fragment.passage_id)
        start, end, snippet = _verified_span(passage, text)
        before = _fragment_view(fragment)
        fragment.passage = passage
        fragment.char_start, fragment.char_end, fragment.text = start, end, snippet
        fragment.state = FragmentState.PROPUESTO
        fragment.save()
        _touch_entry(entry)
        change, event = _record(entry, ChangeAction.CORREGIR, before,
                                _fragment_view(fragment), user, channel, fragment)
        return Reviewed(entries=[entry], changes=[change], events=[event])

    return _run(user, CommissionRole.OPERATOR, CORRECT_OPERATION, ChangeAction.CORREGIR,
                channel, {"fragment": fragment_id}, work)


def remove(user, fragment_id, *, channel=Channel.SCREEN):
    """Quita el fragmento: queda visible en el historial y se puede restituir."""

    def work():
        entry, fragment = _lock_fragment(fragment_id)
        if fragment.state == FragmentState.QUITADO:
            raise ReviewRefused("El fragmento ya está quitado.", "fragment_removed",
                                "fragment")
        before = _fragment_view(fragment)
        fragment.state = FragmentState.QUITADO
        fragment.save(update_fields=["state"])
        _touch_entry(entry)
        change, event = _record(entry, ChangeAction.QUITAR, before,
                                _fragment_view(fragment), user, channel, fragment)
        return Reviewed(entries=[entry], changes=[change], events=[event])

    return _run(user, CommissionRole.OPERATOR, REMOVE_OPERATION, ChangeAction.QUITAR,
                channel, {"fragment": fragment_id}, work)


def restore(user, fragment_id, *, channel=Channel.SCREEN):
    """Devuelve un fragmento quitado a propuesto; la fila deja de estar confirmada."""

    def work():
        entry, fragment = _lock_fragment(fragment_id)
        if fragment.state != FragmentState.QUITADO:
            raise ReviewRefused("Solo se restituye un fragmento quitado.",
                                "fragment_not_removed", "fragment")
        before = _fragment_view(fragment)
        fragment.state = FragmentState.PROPUESTO
        fragment.save(update_fields=["state"])
        _touch_entry(entry)
        change, event = _record(entry, ChangeAction.RESTITUIR, before,
                                _fragment_view(fragment), user, channel, fragment)
        return Reviewed(entries=[entry], changes=[change], events=[event])

    return _run(user, CommissionRole.OPERATOR, RESTORE_OPERATION, ChangeAction.RESTITUIR,
                channel, {"fragment": fragment_id}, work)


def add(user, entry_id, *, passage_id, text="", channel=Channel.SCREEN):
    """Agrega a la fila un fragmento de un pasaje de la oferta; con `text`, solo ese recorte
    literal. Es un fragmento de origen `persona`."""

    def work():
        entry = _lock_entry(entry_id)
        passage = _passage_of(entry, passage_id)
        start, end, snippet = _verified_span(passage, text)
        order = (entry.fragments.aggregate(m=Max("order"))["m"] or 0) + 1
        fragment = Fragment.objects.create(
            entry=entry, order=order, passage=passage, char_start=start, char_end=end,
            text=snippet, origin=FragmentOrigin.PERSONA, state=FragmentState.PROPUESTO)
        _touch_entry(entry)
        change, event = _record(entry, ChangeAction.AGREGAR, None,
                                _fragment_view(fragment), user, channel, fragment)
        return Reviewed(entries=[entry], changes=[change], events=[event])

    return _run(user, CommissionRole.OPERATOR, ADD_OPERATION, ChangeAction.AGREGAR,
                channel, {"entry": entry_id}, work)


# --- Historial y pantalla ------------------------------------------------------------------------


@dataclass
class HistoryPage:
    """La fila con su historial: lo propuesto por el sistema, lo vigente, lo quitado y cada
    cambio, del más antiguo al más reciente, y los pasajes elegibles."""

    entry: SheetEntry
    sheet: Sheet
    offer: object
    requirement: object
    text: str
    proposed: list
    current: list
    removed: list
    changes: list
    passages: list


def history(user, entry_id, *, channel=Channel.SCREEN):
    """El historial de una fila. Lanza `SheetEntry.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=HISTORY_OPERATION,
                            channel=channel)
    entry = SheetEntry.objects.select_related(
        "sheet__offer__procedure", "requirement").get(pk=entry_id)
    fragments = list(entry.fragments.select_related("passage__reading__document")
                     .order_by("order"))
    reading_ids = [r["reading"] for r in entry.sheet.readings]
    passages = list(Passage.objects.filter(reading_id__in=reading_ids)
                    .select_related("reading__document")
                    .order_by("reading__document_id", "order"))
    return HistoryPage(
        entry=entry, sheet=entry.sheet, offer=entry.sheet.offer,
        requirement=entry.requirement,
        text=sheets_service.requirement_text(entry.requirement),
        proposed=[f for f in fragments if f.proposed],
        current=[f for f in fragments if f.state != FragmentState.QUITADO],
        removed=[f for f in fragments if f.state == FragmentState.QUITADO],
        changes=list(entry.changes.select_related("user").order_by("at", "id")),
        passages=passages)


@dataclass
class ReviewPage:
    """La ficha de `sheets.sheet_page`, con los fragmentos quitados de cada fila en
    `row.removed`, y si quien mira puede confirmar."""

    page: object
    can_confirm: bool


def review_page(user, sheet_id, *, channel=Channel.SCREEN):
    """La ficha con sus acciones. Lanza `RoleRejected` sin rol de la Comisión y
    `Sheet.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    page = sheets_service.sheet_page(user, sheet_id, channel=channel)
    for row in page.rows:
        row.removed = [
            sheets_service.FragmentView(f, f.passage.reading.document, f.passage.page)
            for f in row.entry.fragments.filter(state=FragmentState.QUITADO)
            .select_related("passage__reading__document").order_by("order")]
    return ReviewPage(page=page,
                      can_confirm=user.commission_role == CommissionRole.EVALUATOR)
