"""Lo que una circular no tocó llega confirmado a la versión nueva (REQ-085; decisión del
responsable del 2026-10-10, «Lo no tocado confirmado»; principios P3 y P6).

Cuando la propuesta incluye circulares y el procedimiento ya tiene una versión validada,
cada requisito de la versión nueva que ninguna circular alcanzó (sin fuentes de circular y
sin marca de revisión obligatoria) y que es el mismo que ya validó la Comisión (misma clase,
mismos renglones y mismas citas, en las mismas posiciones del mismo tramo) hereda su estado
(confirmado o quitado), su consecuencia elegida y el requisito de origen (`previous`). Los
pendientes ya resueltos sobre un tramo que las circulares no tocaron siguen resueltos.

Lo que cambió una circular, lo que agregó y sus consecuencias quedan como una propuesta
nueva: la Comisión los decide y valida la versión completa. Este módulo no decide nada:
repite una decisión que una persona ya tomó, con el rastro de dónde viene, y deja en cada
requisito heredado la fila de historial y el hecho de auditoría con `carried_over_from`.
"""

from evaluon.audit import services as audit
from evaluon.audit.models import EventType, Outcome
from evaluon.tenders.models import (
    ChangeAction,
    Consequence,
    PendingItem,
    RequirementChange,
    RequirementState,
    VersionStatus,
)


def _signature(requirement):
    quotes = [(q.segment_id, q.char_start, q.char_end)
              for q in requirement.quotes.order_by("order")]
    return requirement.category, tuple(requirement.items), tuple(quotes)


def _decider(old):
    """Quién y cuándo confirmó `old`, o quién validó su versión si no hay una confirmación."""
    change = (old.changes.filter(action=ChangeAction.CONFIRMAR)
              .select_related("user").order_by("-id").first())
    if change is not None and change.user_id is not None:
        return change.user, change.at
    version = old.version
    return version.validated_by, version.validated_at


def carry_over(version, created, anomalies, channel, user):
    """Hereda a `version` (borrador recién armado) lo que la circular no tocó. `created` es
    `{número: Requirement}`. Devuelve cuántos requisitos y pendientes heredó."""
    source = (version.procedure.matrix_versions
              .filter(status=VersionStatus.VALIDATED, number__lt=version.number)
              .order_by("-number").first())
    done = {"requirements": 0, "consequences": 0, "pending": 0}
    if source is None:
        return done
    review = {number for anomaly in anomalies if anomaly.get("review_required")
              for number in anomaly.get("requirements", [])}
    old_by_signature = {}
    for old in source.requirements.order_by("number"):
        old_by_signature.setdefault(_signature(old), []).append(old)

    touched_segments = set()
    for requirement in created.values():
        if requirement.sources.exists() or requirement.number in review:
            touched_segments.update(q.segment_id for q in requirement.quotes.all())
            continue
        candidates = old_by_signature.get(_signature(requirement))
        if not candidates:
            continue
        old = candidates.pop(0)
        if old.state not in (RequirementState.CONFIRMADO, RequirementState.QUITADO):
            continue
        before = requirement.state
        requirement.previous = old
        requirement.state = old.state
        requirement.save(update_fields=["previous", "state"])
        done["requirements"] += 1
        chosen = old.consequences.filter(chosen=True).first()
        if chosen is not None:
            requirement.consequences.filter(consequence_type=chosen.consequence_type,
                                            origin=chosen.origin).delete()
            Consequence.objects.create(
                requirement=requirement, consequence_type=chosen.consequence_type,
                grounds=chosen.grounds, origin=chosen.origin, step=chosen.step, chosen=True,
                chosen_by=chosen.chosen_by, chosen_at=chosen.chosen_at,
                chosen_note=chosen.chosen_note)
            done["consequences"] += 1
        if old.state == RequirementState.CONFIRMADO:
            who, when = _decider(old)
            detail = {"carried_over_from": old.pk, "from_version": source.pk}
            after = {"state": RequirementState.CONFIRMADO, **detail}
            event = audit.record(
                EventType.REQUIREMENT_CHANGE, outcome=Outcome.OK, channel=channel, user=user,
                detail={"action": ChangeAction.CONFIRMAR, "requirement": requirement.pk,
                        "version": version.pk, "number": requirement.number,
                        "before": {"state": before}, "after": after,
                        "decided_by": who.username if who else "", **detail})
            RequirementChange.objects.create(
                requirement=requirement, action=ChangeAction.CONFIRMAR,
                before={"state": before}, after=after, user=who or user, event=event,
                **({"at": when} if when is not None else {}))

    resolved = {item.segment_id: item
                for item in source.pending_items.filter(resolved_at__isnull=False)}
    for item in version.pending_items.filter(resolved_at__isnull=True):
        old = resolved.get(item.segment_id)
        if old is None or item.segment_id in touched_segments:
            continue
        PendingItem.objects.filter(pk=item.pk).update(
            resolved_by=old.resolved_by, resolved_at=old.resolved_at,
            resolution=old.resolution)
        done["pending"] += 1
    return done
