"""Revisar la matriz: confirmar, corregir, quitar, restituir y agregar requisitos, y
resolver tramos pendientes (REQ-026, REQ-027, REQ-028; plan 003, "Revisión, validación y
versiones" y "Roles"; T-079).

- `confirm`: confirma uno o varios requisitos propuestos. Solo el evaluador.
- `correct`: en un formal o económico cambia la clase, los renglones o la cita (un
  fragmento literal de un tramo, comprobado con la misma regla que la del modelo); en un
  técnico suma o quita tramos citados. Pasar un formal o económico a técnico une su cita a
  la fila técnica de su renglón y deja quitado el requisito original. Lo corrige el
  operador o el evaluador. Un requisito confirmado que se corrige vuelve a quedar
  propuesto: la confirmación valía para lo de antes.
- `remove` y `restore`: el requisito queda `quitado`, visible y con su historia; restituirlo
  lo devuelve al estado que tenía.
- `add_requirement`: un formal o económico desde un tramo, con un fragmento literal, clase y
  renglones; si se agrega para resolver un pendiente, lo resuelve en la misma operación.
  `add_technical_row`: la fila técnica de un renglón que no la tiene, con sus tramos.
- `resolve_pending`: "revisado, sin requisitos". Solo el evaluador.
- `history`: lo propuesto originalmente y cada cambio, con quién, cuándo, antes y después.

Cada cambio deja una fila en `tenders_requirement_change` y el hecho `requirement_change`
(un pendiente resuelto, `segment_review`), en la misma transacción que el cambio. El rol se
comprueba antes de toda transacción, para que el hecho `rejected` no se pierda. Todo lo
demás se valida antes de escribir, porque el historial y el registro de hechos solo admiten
agregar filas: un cambio rechazado deja un hecho en resultado `rejected` con su motivo, y
nada más. Solo un borrador se revisa (`version_not_draft`); la base lo exige también.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    ChangeAction,
    MatrixVersion,
    PendingItem,
    PendingResolution,
    Requirement,
    RequirementChange,
    RequirementClass,
    RequirementOrigin,
    RequirementQuote,
    RequirementState,
    Segment,
    VersionStatus,
)
from evaluon.tenders.proposal import quotes as quote_rules

CONFIRM_OPERATION = "evaluon.tenders.services.review.confirm"
CORRECT_OPERATION = "evaluon.tenders.services.review.correct"
REMOVE_OPERATION = "evaluon.tenders.services.review.remove"
RESTORE_OPERATION = "evaluon.tenders.services.review.restore"
ADD_OPERATION = "evaluon.tenders.services.review.add_requirement"
ADD_TECHNICAL_OPERATION = "evaluon.tenders.services.review.add_technical_row"
RESOLVE_OPERATION = "evaluon.tenders.services.review.resolve_pending"
HISTORY_OPERATION = "evaluon.tenders.services.review.history"

SINGLE_QUOTE = (RequirementClass.FORMAL.value, RequirementClass.ECONOMICO.value)
TECHNICAL = RequirementClass.TECNICO.value


class ReviewRefused(ValueError):
    """No se hizo el cambio. `reason` es el motivo que queda en el registro y `field`, el
    dato que lo impidió, si hay uno. El mensaje es para la persona: español llano."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass(frozen=True)
class Reviewed:
    """Lo que devuelve una operación: los requisitos tocados, las filas de historial y los
    hechos registrados."""

    requirements: list
    changes: list = field(default_factory=list)
    events: list = field(default_factory=list)


# --- Utilidades ----------------------------------------------------------------------------------


def _refuse_record(error, action, channel, user, detail):
    audit.record(
        EventType.REQUIREMENT_CHANGE, outcome=Outcome.REJECTED, channel=channel,
        user=user, detail={**detail, "action": action, "reason": error.reason,
                           "message": str(error)},
    )


def _quote_view(quote):
    return {"segment": quote.segment_id, "key": quote.segment.key,
            "char_start": quote.char_start, "char_end": quote.char_end,
            "text": quote.text, "scope": quote.scope, "flag": quote.quote_flag}


def _snapshot(requirement):
    """Clase, renglones, estado y citas del requisito, tal como están."""
    return {
        "category": requirement.category,
        "items": list(requirement.items),
        "state": requirement.state,
        "quotes": [_quote_view(q) for q in
                   requirement.quotes.select_related("segment").order_by("order")],
    }


def _lock_draft(version_id):
    """Bloquea la versión y exige que sea un borrador."""
    version = MatrixVersion.objects.select_for_update().get(pk=version_id)
    if version.status != VersionStatus.DRAFT:
        raise ReviewRefused(
            "La versión de la matriz ya está validada o descartada y no se puede "
            "cambiar: abra una versión nueva.",
            "version_not_draft",
        )
    return version


def _lock_requirement(requirement_id):
    """El requisito bloqueado, con su versión bloqueada y en borrador."""
    version_id = Requirement.objects.values_list("version_id", flat=True).get(
        pk=requirement_id)
    version = _lock_draft(version_id)
    return Requirement.objects.select_for_update().get(pk=requirement_id), version


def _items(value):
    """Lista de renglones (enteros) a partir de una lista o de un texto como "1, 2"."""
    if value is None:
        return None
    if isinstance(value, str):
        value = [part for part in value.replace(";", ",").replace(" ", ",").split(",")
                 if part]
    try:
        items = [int(v) for v in value]
    except (TypeError, ValueError):
        raise ReviewRefused("Los renglones son números, por ejemplo «1, 2».",
                            "invalid_items", "items")
    if any(i <= 0 for i in items):
        raise ReviewRefused("Los renglones son números positivos.", "invalid_items",
                            "items")
    return sorted(set(items))


def _category(value):
    if value not in RequirementClass.values:
        raise ReviewRefused("Elija la clase del requisito: formal, económico o técnico.",
                            "invalid_category", "category")
    return value


def _version_reading_ids(version):
    """Las lecturas del pliego de la versión: las de su propuesta o, sin propuesta, las
    vigentes de los documentos del procedimiento."""
    if version.run_id is not None:
        return {d["reading"] for d in version.run.documents}
    return set(Segment.objects.filter(
        reading__document__procedure_id=version.procedure_id
    ).values_list("reading_id", flat=True))


def _segment_of(version, segment_id, field_name="segment"):
    try:
        segment = Segment.objects.select_related("reading__document").get(
            pk=int(segment_id))
    except (Segment.DoesNotExist, TypeError, ValueError):
        raise ReviewRefused("Elija un tramo del pliego.", "segment_not_found",
                            field_name)
    if segment.reading_id not in _version_reading_ids(version):
        raise ReviewRefused("Ese tramo no es del pliego de esta matriz.",
                            "segment_not_in_tender", field_name)
    return segment


def _verified_quote(segment, text):
    """`(inicio, fin, recorte)` de `text` dentro del tramo, con las posiciones en el texto
    canónico de la lectura y el recorte exacto de ese texto. Lanza `ReviewRefused` si el
    fragmento no está en el tramo."""
    span = quote_rules.locate(segment.text, text)
    if span is None:
        raise ReviewRefused(
            "El fragmento no está en el tramo elegido: copie el texto tal como figura en "
            "el pliego.",
            "quote_not_in_segment", "quote",
        )
    start, end = quote_rules.absolute(segment, span)
    canonical = segment.reading.canonical_text
    if not (segment.char_start <= start < end <= segment.char_end):
        raise ReviewRefused("El fragmento queda fuera del tramo.",
                            "quote_not_in_segment", "quote")
    return start, end, canonical[start:end]


def _scope(segment, items):
    from evaluon.tenders.models import QuoteScope

    return (QuoteScope.PROPIA.value if set(segment.items) & set(items)
            else QuoteScope.GENERAL.value)


def _technical_row(version, items, exclude=None):
    rows = version.requirements.filter(category=TECHNICAL, items=items)
    if exclude is not None:
        rows = rows.exclude(pk=exclude)
    return rows.order_by("number").first()


def _record(requirement, action, before, after, user, channel, detail=None):
    """La fila de historial y el hecho `requirement_change` de un cambio."""
    event = audit.record(
        EventType.REQUIREMENT_CHANGE, outcome=Outcome.OK, channel=channel, user=user,
        detail={"action": action, "requirement": requirement.pk,
                "version": requirement.version_id, "number": requirement.number,
                "before": before, "after": after, **(detail or {})},
    )
    change = RequirementChange.objects.create(
        requirement=requirement, action=action, before=before, after=after, user=user,
        event=event)
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


# --- Confirmar -----------------------------------------------------------------------------------


def confirm(user, requirement_ids, *, channel=Channel.SCREEN):
    """Confirma los requisitos propuestos de `requirement_ids` (de una sola versión).
    Los que ya estaban confirmados no cambian; uno quitado se rechaza. Solo el evaluador."""
    ids = sorted({int(i) for i in requirement_ids})

    def work():
        if not ids:
            raise ReviewRefused("Marque al menos un requisito para confirmar.",
                                "nothing_selected", "requirements")
        versions = set(Requirement.objects.filter(pk__in=ids).values_list(
            "version_id", flat=True))
        if len(versions) != 1 or Requirement.objects.filter(pk__in=ids).count() != len(ids):
            raise ReviewRefused("Los requisitos a confirmar son de una sola versión.",
                                "requirement_not_found", "requirements")
        _lock_draft(versions.pop())
        locked = list(Requirement.objects.select_for_update().filter(
            pk__in=ids).order_by("number"))
        if any(r.state == RequirementState.QUITADO for r in locked):
            raise ReviewRefused("Un requisito quitado no se confirma: restitúyalo antes.",
                                "requirement_removed", "requirements")
        done = Reviewed(requirements=[])
        for requirement in locked:
            if requirement.state == RequirementState.CONFIRMADO:
                continue
            before = {"state": requirement.state}
            requirement.state = RequirementState.CONFIRMADO
            requirement.save(update_fields=["state"])
            change, event = _record(requirement, ChangeAction.CONFIRMAR, before,
                                    {"state": requirement.state}, user, channel)
            done.requirements.append(requirement)
            done.changes.append(change)
            done.events.append(event)
        return done

    return _run(user, CommissionRole.EVALUATOR, CONFIRM_OPERATION,
                ChangeAction.CONFIRMAR, channel, {"requirements": ids}, work)


# --- Corregir ------------------------------------------------------------------------------------


def correct(user, requirement_id, *, category=None, items=None, segment=None, quote=None,
            add_segments=(), remove_quotes=(), channel=Channel.SCREEN):
    """Corrige un requisito.

    - Formal o económico: `category` (formal, económico o técnico), `items` (renglones) y
      la cita, con `quote` (el fragmento) y, si cambia de tramo, `segment`. Con
      `category="tecnico"` la cita se une a la fila técnica del renglón y el requisito
      queda quitado.
    - Técnico: `add_segments` (ids de tramos que se suman, citados enteros) y
      `remove_quotes` (ids de citas que se sacan; no se saca la última).
    """
    detail = {"requirement": requirement_id}

    def work():
        requirement, version = _lock_requirement(requirement_id)
        if requirement.state == RequirementState.QUITADO:
            raise ReviewRefused("El requisito está quitado: restitúyalo para corregirlo.",
                                "requirement_removed")
        before = _snapshot(requirement)
        if requirement.category == TECHNICAL:
            touched = _correct_technical(requirement, version, add_segments,
                                         remove_quotes, category)
        else:
            touched = _correct_single(requirement, version, category, items, segment,
                                      quote)
        after = _snapshot(requirement)
        if touched is None and after == before:
            raise ReviewRefused("No hay nada que cambiar: el requisito queda igual.",
                                "nothing_to_change")
        if requirement.state == RequirementState.CONFIRMADO:
            requirement.state = RequirementState.PROPUESTO
            requirement.save(update_fields=["state"])
            after = _snapshot(requirement)
        change, event = _record(requirement, ChangeAction.CORREGIR, before, after, user,
                                channel)
        changes, events, requirements = [change], [event], [requirement]
        if touched is not None:  # la fila técnica que recibió la cita
            target, target_before = touched
            change, event = _record(target, ChangeAction.CORREGIR, target_before,
                                    _snapshot(target), user, channel,
                                    {"joined_from": requirement.pk})
            changes.append(change)
            events.append(event)
            requirements.append(target)
        return Reviewed(requirements=requirements, changes=changes, events=events)

    return _run(user, CommissionRole.OPERATOR, CORRECT_OPERATION, ChangeAction.CORREGIR,
                channel, detail, work)


def _correct_single(requirement, version, category, items, segment, quote):
    """Corrige un formal o económico. Devuelve `(fila técnica, su estado de antes)` si lo
    unió a una fila técnica, o `None`."""
    new_items = _items(items)
    new_items = list(requirement.items) if new_items is None else new_items
    new_category = _category(category) if category else requirement.category
    current = requirement.quotes.select_related("segment__reading").get()
    changed_quote = bool(quote and quote.strip()) or segment not in (None, "")
    if changed_quote:
        target_segment = (_segment_of(version, segment) if segment not in (None, "")
                          else current.segment)
        text = quote if quote and quote.strip() else current.text
        start, end, cut = _verified_quote(target_segment, text)
        if target_segment.pk == current.segment_id and (
                (start, end) == (current.char_start, current.char_end)
                or " ".join(cut.split()) == " ".join(current.text.split())):
            # El mismo fragmento que ya tenía (el formulario lo reenvía): no cambia.
            changed_quote = False
            target_segment, start, end, cut = (current.segment, current.char_start,
                                               current.char_end, current.text)
    else:
        target_segment, start, end, cut = (current.segment, current.char_start,
                                           current.char_end, current.text)

    if new_category == TECHNICAL:
        if len(new_items) > 1:
            raise ReviewRefused("Un técnico es la fila de un solo renglón.",
                                "technical_one_item", "items")
        row = _technical_row(version, new_items)
        if row is None or row.state == RequirementState.QUITADO:
            raise ReviewRefused(
                "No hay una fila técnica para ese renglón: agréguela y después sume el "
                "tramo.", "no_technical_row", "items")
        if row.quotes.filter(segment=target_segment).exists():
            raise ReviewRefused("La fila técnica de ese renglón ya cita ese tramo.",
                                "quote_duplicate", "quote")
        row = Requirement.objects.select_for_update().get(pk=row.pk)
        row_before = _snapshot(row)
        order = (row.quotes.aggregate(m=Max("order"))["m"] or 0) + 1
        RequirementQuote.objects.create(
            requirement=row, order=order, segment=target_segment, char_start=start,
            char_end=end, text=cut, scope=_scope(target_segment, new_items),
            quote_flag="")
        if row.state == RequirementState.CONFIRMADO:
            row.state = RequirementState.PROPUESTO
            row.save(update_fields=["state"])
        # El formal pasa a técnico: la fila del renglón tiene ahora su cita y el requisito
        # original queda quitado, con su clase, su cita y su historia.
        requirement.state = RequirementState.QUITADO
        requirement.save(update_fields=["state"])
        return row, row_before

    requirement.category = new_category
    requirement.items = new_items
    requirement.save(update_fields=["category", "items"])
    if changed_quote:
        current.segment = target_segment
        current.char_start, current.char_end, current.text = start, end, cut
        current.quote_flag = ""
        current.save()
    return None


def _correct_technical(requirement, version, add_segments, remove_quotes, category):
    if category and category != TECHNICAL:
        raise ReviewRefused("Una fila técnica no cambia de clase: quítela y agregue el "
                            "requisito.", "technical_class_fixed", "category")
    add_segments = [s for s in add_segments if s not in (None, "")]
    remove_quotes = [int(q) for q in remove_quotes if q not in (None, "")]
    if not add_segments and not remove_quotes:
        raise ReviewRefused("Elija qué tramos sumar o quitar.", "nothing_to_change")
    own = {q.pk: q for q in requirement.quotes.all()}
    for quote_id in remove_quotes:
        if quote_id not in own:
            raise ReviewRefused("Esa cita no es de esta fila técnica.",
                                "quote_not_found", "remove_quotes")
    to_add = []
    for segment_id in add_segments:
        segment = _segment_of(version, segment_id, "add_segments")
        if segment.pk in {s.pk for s in to_add} or any(
                q.segment_id == segment.pk and q.pk not in remove_quotes
                for q in own.values()):
            raise ReviewRefused("La fila técnica ya cita ese tramo.", "quote_duplicate",
                                "add_segments")
        to_add.append(segment)
    if len(own) - len(set(remove_quotes)) + len(to_add) < 1:
        raise ReviewRefused(
            "La fila técnica no puede quedar sin ningún tramo: quite el requisito.",
            "last_quote", "remove_quotes")
    RequirementQuote.objects.filter(pk__in=remove_quotes).delete()
    order = (requirement.quotes.aggregate(m=Max("order"))["m"] or 0)
    for segment in to_add:
        order += 1
        RequirementQuote.objects.create(
            requirement=requirement, order=order, segment=segment,
            char_start=segment.char_start, char_end=segment.char_end, text=segment.text,
            scope=_scope(segment, requirement.items), quote_flag="")
    return None


# --- Quitar y restituir --------------------------------------------------------------------------


def remove(user, requirement_id, *, channel=Channel.SCREEN):
    """Deja el requisito `quitado`: sigue visible y con su historia."""

    def work():
        requirement, _ = _lock_requirement(requirement_id)
        if requirement.state == RequirementState.QUITADO:
            raise ReviewRefused("El requisito ya está quitado.", "requirement_removed")
        before = {"state": requirement.state}
        requirement.state = RequirementState.QUITADO
        requirement.save(update_fields=["state"])
        change, event = _record(requirement, ChangeAction.QUITAR, before,
                                {"state": requirement.state}, user, channel)
        return Reviewed([requirement], [change], [event])

    return _run(user, CommissionRole.OPERATOR, REMOVE_OPERATION, ChangeAction.QUITAR,
                channel, {"requirement": requirement_id}, work)


def restore(user, requirement_id, *, channel=Channel.SCREEN):
    """Devuelve un requisito quitado al estado que tenía cuando se quitó."""

    def work():
        requirement, _ = _lock_requirement(requirement_id)
        if requirement.state != RequirementState.QUITADO:
            raise ReviewRefused("El requisito no está quitado.", "requirement_not_removed")
        last = requirement.changes.filter(action=ChangeAction.QUITAR).order_by("-id").first()
        state = (last.before or {}).get("state") if last else None
        if state not in (RequirementState.PROPUESTO, RequirementState.CONFIRMADO):
            state = RequirementState.PROPUESTO
        if requirement.category in SINGLE_QUOTE and not requirement.quotes.exists():
            raise ReviewRefused("El requisito no tiene cita: no se puede restituir.",
                                "no_quote")
        before = {"state": requirement.state}
        requirement.state = state
        requirement.save(update_fields=["state"])
        change, event = _record(requirement, ChangeAction.RESTITUIR, before,
                                {"state": state}, user, channel)
        return Reviewed([requirement], [change], [event])

    return _run(user, CommissionRole.OPERATOR, RESTORE_OPERATION,
                ChangeAction.RESTITUIR, channel, {"requirement": requirement_id}, work)


# --- Agregar -------------------------------------------------------------------------------------


def _resolve(item, user, resolution, channel, detail=None):
    item.resolution = resolution
    item.resolved_by = user
    item.resolved_at = timezone.now()
    item.save(update_fields=["resolution", "resolved_by", "resolved_at"])
    return audit.record(
        EventType.SEGMENT_REVIEW, outcome=Outcome.OK, channel=channel, user=user,
        detail={"pending": item.pk, "version": item.version_id,
                "segment": item.segment_id, "reason": item.reason,
                "resolution": resolution, **(detail or {})},
    )




def add_requirement(user, version_id, *, segment, quote, category, items=None,
                    pending=None, channel=Channel.SCREEN):
    """Agrega un requisito formal o económico desde un tramo, con un fragmento literal.
    Origen `agregado`. Con `pending` (id de un pendiente de la versión, del mismo tramo) lo
    resuelve como «requisito agregado» en la misma operación."""
    detail = {"version": version_id}

    def work():
        version = _lock_draft(version_id)
        category_ = _category(category)
        if category_ not in SINGLE_QUOTE:
            raise ReviewRefused(
                "Aquí se agregan requisitos formales o económicos; el técnico es una "
                "fila por renglón.", "invalid_category", "category")
        target = _segment_of(version, segment)
        item = None
        if pending not in (None, ""):
            try:
                item = PendingItem.objects.select_for_update().get(
                    pk=int(pending), version=version)
            except (PendingItem.DoesNotExist, ValueError):
                raise ReviewRefused("No hay ese pendiente en esta matriz.",
                                    "pending_not_found", "pending")
            if item.resolved_at is not None:
                raise ReviewRefused("Ese pendiente ya está resuelto.",
                                    "pending_resolved", "pending")
            if item.segment_id != target.pk:
                raise ReviewRefused("El requisito se agrega desde el tramo pendiente.",
                                    "pending_other_segment", "segment")
        new_items = _items(items)
        new_items = list(target.items) if new_items is None else new_items
        start, end, cut = _verified_quote(target, quote)
        number = (version.requirements.aggregate(m=Max("number"))["m"] or 0) + 1
        requirement = Requirement.objects.create(
            version=version, number=number, category=category_, items=new_items,
            origin=RequirementOrigin.AGREGADO, state=RequirementState.PROPUESTO,
            proposed={}, passes=[])
        RequirementQuote.objects.create(
            requirement=requirement, order=1, segment=target, char_start=start,
            char_end=end, text=cut, scope="", quote_flag="")
        change, event = _record(requirement, ChangeAction.AGREGAR, None,
                                _snapshot(requirement), user, channel)
        events = [event]
        if item is not None:
            events.append(_resolve(item, user, PendingResolution.REQUISITO_AGREGADO,
                                   channel, {"requirement": requirement.pk}))
        return Reviewed([requirement], [change], events)

    return _run(user, CommissionRole.OPERATOR, ADD_OPERATION, ChangeAction.AGREGAR,
                channel, detail, work)


def add_technical_row(user, version_id, *, item, segments, channel=Channel.SCREEN):
    """Agrega la fila técnica de un renglón que no la tiene, con sus tramos citados
    enteros. Una segunda fila para el mismo renglón se rechaza."""
    detail = {"version": version_id, "item": item}

    def work():
        version = _lock_draft(version_id)
        items = _items([item]) if item not in (None, "") else []
        if not items:
            raise ReviewRefused("Indique el renglón de la fila técnica.", "invalid_items",
                                "item")
        known = set()
        for reading_items in m_reading_items(version):
            known.update(i.get("number") for i in reading_items)
        if items[0] not in known:
            raise ReviewRefused(
                f"El renglón {items[0]} no figura en el pliego de esta matriz.",
                "item_unknown", "item")
        existing = _technical_row(version, items)
        if existing is not None:
            raise ReviewRefused(
                f"El renglón {items[0]} ya tiene su fila técnica"
                + (" (quitada: restitúyala)." if existing.state == RequirementState.QUITADO
                   else ": sume los tramos a esa fila."),
                "technical_row_exists", "item")
        ids = [s for s in segments if s not in (None, "")]
        if not ids:
            raise ReviewRefused("Elija al menos un tramo para la fila técnica.",
                                "nothing_selected", "segments")
        chosen = []
        for segment_id in ids:
            segment = _segment_of(version, segment_id, "segments")
            if segment.pk in {s.pk for s in chosen}:
                raise ReviewRefused("Un tramo se cita una sola vez.", "quote_duplicate",
                                    "segments")
            chosen.append(segment)
        number = (version.requirements.aggregate(m=Max("number"))["m"] or 0) + 1
        requirement = Requirement.objects.create(
            version=version, number=number, category=TECHNICAL, items=items,
            origin=RequirementOrigin.AGREGADO, state=RequirementState.PROPUESTO,
            proposed={}, passes=[])
        for order, segment in enumerate(chosen, start=1):
            RequirementQuote.objects.create(
                requirement=requirement, order=order, segment=segment,
                char_start=segment.char_start, char_end=segment.char_end,
                text=segment.text, scope=_scope(segment, items), quote_flag="")
        change, event = _record(requirement, ChangeAction.AGREGAR, None,
                                _snapshot(requirement), user, channel)
        return Reviewed([requirement], [change], [event])

    return _run(user, CommissionRole.OPERATOR, ADD_TECHNICAL_OPERATION,
                ChangeAction.AGREGAR, channel, detail, work)


# --- Resolver un pendiente -----------------------------------------------------------------------


def resolve_pending(user, pending_id, *, channel=Channel.SCREEN):
    """Marca un pendiente como «revisado, sin requisitos». Solo el evaluador. Para
    resolverlo agregando un requisito, ver `add_requirement(pending=...)`."""

    def work():
        try:
            version_id = PendingItem.objects.values_list("version_id", flat=True).get(
                pk=pending_id)
        except PendingItem.DoesNotExist:
            raise ReviewRefused("No hay ese pendiente.", "pending_not_found", "pending")
        _lock_draft(version_id)
        item = PendingItem.objects.select_for_update().get(pk=pending_id)
        if item.resolved_at is not None:
            raise ReviewRefused("Ese pendiente ya está resuelto.", "pending_resolved",
                                "pending")
        event = _resolve(item, user, PendingResolution.SIN_REQUISITOS, channel)
        return Reviewed(requirements=[], events=[event])

    return _run(user, CommissionRole.EVALUATOR, RESOLVE_OPERATION, "resolver_pendiente",
                channel, {"pending": pending_id}, work)


# --- Historial -----------------------------------------------------------------------------------


@dataclass
class HistoryPage:
    requirement: Requirement
    version: MatrixVersion
    proposed: dict
    current: dict
    changes: list


def history(user, requirement_id, *, channel=Channel.SCREEN):
    """El historial de un requisito: lo propuesto originalmente, su estado actual y cada
    cambio, del más antiguo al más reciente. Lanza `Requirement.DoesNotExist` si no
    existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=HISTORY_OPERATION,
                            channel=channel)
    requirement = Requirement.objects.select_related("version__procedure").get(
        pk=requirement_id)
    changes = list(requirement.changes.select_related("user").order_by("at", "id"))
    return HistoryPage(requirement=requirement, version=requirement.version,
                       proposed=requirement.proposed, current=_snapshot(requirement),
                       changes=changes)


def m_reading_items(version):
    """Los renglones reconocidos en cada lectura del pliego de la versión."""
    from evaluon.tenders.models import Reading

    return list(Reading.objects.filter(pk__in=_version_reading_ids(version)).values_list(
        "items", flat=True))
