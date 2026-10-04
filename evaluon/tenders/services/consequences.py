"""Elegir la consecuencia de no cumplir un requisito (REQ-029; plan 003, "Consecuencias";
principio P3; T-081).

El sistema solo sugiere (T-080); la consecuencia la elige siempre un evaluador, con su nombre
y su momento registrados.

- `options`: las opciones de un requisito (las sugeridas por el sistema y las que ya propuso
  una persona), cada una con el texto literal de cada fundamento: el tramo del pliego con
  su ubicación o la unidad de la norma con su cita. El texto sale de la base, no de la opción.
- `choose`: el evaluador elige.
  * Una sugerencia del sistema (`option`, o el tipo de una sugerida): su fundamento es el
    motivo y no se escribe nada (`note` es optativa).
  * Otro tipo de la lista (todos menos «no determinada»): el motivo es obligatorio; en una
    aprobación condicionada, la condición, que ocupa el lugar del motivo en `chosen_note`;
    en `consultar_oferente` u `otra_pliego` sin sugerencia, el tramo del pliego y un
    fragmento literal con cita verificada, que queda como su fundamento.
  Elegir de nuevo reemplaza la elección anterior; la historia queda en el historial del
  requisito (`elegir_consecuencia`) y en el hecho `consequence_choice`.

Como en la revisión, el rol se comprueba antes de toda transacción; lo demás se valida antes
de escribir y un pedido rechazado deja solo un hecho `consequence_choice` en resultado
`rejected`. Solo un borrador cambia (la base lo exige también).
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Unit as NormUnit
from evaluon.tenders.models import (
    ChangeAction,
    Consequence,
    ConsequenceOrigin,
    ConsequenceType,
    RequirementChange,
    RequirementState,
    Segment,
)
from evaluon.tenders.services import review
from evaluon.tenders.services.matrix_page import _Pages, _place

CHOOSE_OPERATION = "evaluon.tenders.services.consequences.choose"

CHOOSABLE_TYPES = [t for t in ConsequenceType.values
                   if t != ConsequenceType.NO_DETERMINADA.value]
NEED_PLIEGO_QUOTE = (ConsequenceType.CONSULTAR_OFERENTE.value,
                     ConsequenceType.OTRA_PLIEGO.value)
CONDITIONAL = ConsequenceType.APROBACION_CONDICIONADA.value


class ChoiceRefused(review.ReviewRefused):
    """No se eligió. `reason` queda en el registro; el mensaje es para la persona."""


@dataclass
class GroundView:
    """Un fundamento con su texto literal tal como está en la base."""

    source: str          # "pliego" o "norma"
    text: str
    place: object = None  # pliego: `Place` (documento, página, cláusula)
    citation: str = ""   # norma: la norma y la unidad


@dataclass
class OptionView:
    consequence: Consequence
    label: str
    from_system: bool
    undetermined: bool
    chosen: bool
    grounds: list = field(default_factory=list)


def _ground_view(ground, pages):
    if ground.get("source") == "norma":
        unit = NormUnit.objects.select_related("reading__document__norm").filter(
            pk=ground.get("unit")).first()
        if unit is None:
            return GroundView("norma", "(la unidad ya no está en la base)")
        norm = unit.reading.document.norm
        return GroundView("norma", unit.text,
                          citation=f"{norm.citation} · {unit.path or unit.label}")
    segment = Segment.objects.select_related("reading__document").filter(
        pk=ground.get("segment")).first()
    if segment is None:
        return GroundView("pliego", "(el tramo ya no está en la base)")
    start, end = ground["char_start"], ground["char_end"]
    return GroundView("pliego", segment.reading.canonical_text[start:end],
                      place=_place(pages, segment, start, end))


def options(requirement, pages=None):
    """Las opciones de `requirement`: sugeridas por el sistema primero, después las de una
    persona. La «no determinada» se muestra como tal y no se puede elegir."""
    pages = pages or _Pages()
    rows = requirement.consequences.order_by("-origin", "id")
    return [OptionView(
        consequence=c,
        label=ConsequenceType(c.consequence_type).label,
        from_system=c.origin == ConsequenceOrigin.SISTEMA,
        undetermined=c.consequence_type == ConsequenceType.NO_DETERMINADA,
        chosen=c.chosen,
        grounds=[_ground_view(g, pages) for g in c.grounds],
    ) for c in rows]


def _summary(consequence):
    if consequence is None:
        return None
    return {"consequence": consequence.pk, "type": consequence.consequence_type,
            "grounds": consequence.grounds, "origin": consequence.origin,
            "note": consequence.chosen_note}


def _refuse_record(error, user, channel, detail):
    audit.record(EventType.CONSEQUENCE_CHOICE, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason,
                                    "message": str(error)})


def _pliego_ground(version, segment, quote):
    try:
        segment = review._segment_of(version, segment)
        if not (quote or "").strip():
            raise ChoiceRefused(
                "Indique el fragmento literal del pliego que sostiene esta consecuencia.",
                "quote_required", "quote")
        start, end, _ = review._verified_quote(segment, quote)
    except ChoiceRefused:
        raise
    except review.ReviewRefused as error:
        raise ChoiceRefused(str(error), error.reason, error.field) from error
    return {"source": "pliego", "reading": segment.reading_id, "segment": segment.pk,
            "key": segment.key, "char_start": start, "char_end": end}


def choose(user, requirement_id, *, option=None, consequence_type=None, note="",
           segment=None, quote="", channel=Channel.SCREEN):
    """El evaluador elige la consecuencia de `requirement_id`. Con `option` (id de una
    opción del requisito) elige esa; con `consequence_type`, un tipo de la lista (si el
    sistema ya lo sugirió, es esa sugerencia). Devuelve la consecuencia elegida."""
    detail = {"requirement": requirement_id}
    note = (note or "").strip()

    def work():
        try:
            requirement, version = review._lock_requirement(requirement_id)
        except review.ReviewRefused as error:
            raise ChoiceRefused(str(error), error.reason) from error
        if requirement.state == RequirementState.QUITADO:
            raise ChoiceRefused("El requisito está quitado: restitúyalo para elegir su "
                                "consecuencia.", "requirement_removed")
        existing = list(requirement.consequences.select_for_update())
        picked = None
        if option not in (None, ""):
            picked = next((c for c in existing if str(c.pk) == str(option)), None)
            if picked is None:
                raise ChoiceRefused("Esa opción no es de este requisito.",
                                    "option_not_found", "option")
        elif consequence_type not in (None, ""):
            if consequence_type == ConsequenceType.NO_DETERMINADA.value:
                raise ChoiceRefused(
                    "«No determinada» no se elige: es el estado de un requisito sin "
                    "fundamento. Elija otra consecuencia.", "undetermined_not_choosable",
                    "consequence_type")
            if consequence_type not in CHOOSABLE_TYPES:
                raise ChoiceRefused("Elija un tipo de consecuencia de la lista.",
                                    "invalid_type", "consequence_type")
            picked = next((c for c in existing if c.origin == ConsequenceOrigin.SISTEMA
                           and c.consequence_type == consequence_type), None)
        else:
            raise ChoiceRefused("Elija una de las consecuencias.", "nothing_selected",
                                "option")

        if picked is not None and picked.consequence_type == \
                ConsequenceType.NO_DETERMINADA.value:
            raise ChoiceRefused(
                "«No determinada» no se elige: es el estado de un requisito sin "
                "fundamento. Elija otra consecuencia.", "undetermined_not_choosable",
                "option")

        suggested = picked is not None and picked.origin == ConsequenceOrigin.SISTEMA
        if suggested:
            final_note = note  # el fundamento de la sugerencia es el motivo
            grounds = None
        else:
            kind = picked.consequence_type if picked else consequence_type
            if kind == CONDITIONAL:
                if not note:
                    raise ChoiceRefused(
                        "Una aprobación condicionada exige escribir la condición.",
                        "condition_required", "note")
                final_note = note
            else:
                if not note:
                    raise ChoiceRefused(
                        "Escriba el motivo de la elección: no es una sugerencia del "
                        "sistema.", "note_required", "note")
                final_note = note
            grounds = None
            if picked is None:
                grounds = (_pliego_ground(version, segment, quote)
                           if kind in NEED_PLIEGO_QUOTE else None)
                picked = next((c for c in existing if c.origin == ConsequenceOrigin.PERSONA
                               and c.consequence_type == kind
                               and c.grounds == ([grounds] if grounds else [])), None)
                if picked is None:
                    picked = Consequence.objects.create(
                        requirement=requirement, consequence_type=kind,
                        grounds=[grounds] if grounds else [],
                        origin=ConsequenceOrigin.PERSONA)
            elif kind in NEED_PLIEGO_QUOTE and not picked.grounds:
                raise ChoiceRefused("Esa opción no tiene el tramo del pliego que la "
                                    "sostiene.", "pliego_ground_required", "segment")

        previous = next((c for c in existing if c.chosen), None)
        before = _summary(previous)
        if previous is not None and previous.pk != picked.pk:
            previous.chosen = False
            previous.chosen_by = None
            previous.chosen_at = None
            previous.chosen_note = ""
            previous.save(update_fields=["chosen", "chosen_by", "chosen_at",
                                         "chosen_note"])
        picked.chosen = True
        picked.chosen_by = user
        picked.chosen_at = timezone.now()
        picked.chosen_note = final_note
        picked.save(update_fields=["chosen", "chosen_by", "chosen_at", "chosen_note"])
        after = {**_summary(picked), "suggested_by_system": suggested}
        event = audit.record(
            EventType.CONSEQUENCE_CHOICE, outcome=Outcome.OK, channel=channel, user=user,
            detail={"requirement": requirement.pk, "version": requirement.version_id,
                    "number": requirement.number, "type": picked.consequence_type,
                    "grounds": picked.grounds, "suggested_by_system": suggested,
                    "note": final_note, "before": before})
        RequirementChange.objects.create(
            requirement=requirement, action=ChangeAction.ELEGIR_CONSECUENCIA,
            before=before or {}, after=after, user=user, event=event)
        return picked

    require_commission_role(user, CommissionRole.EVALUATOR, operation=CHOOSE_OPERATION,
                            channel=channel)
    try:
        with transaction.atomic():
            return work()
    except ChoiceRefused as error:
        _refuse_record(error, user, channel, detail)
        raise
