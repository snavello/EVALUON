"""Las filas que el sistema descartó: listarlas y devolverlas a la matriz (REQ-033, REQ-026;
plan 003, "La lista de descartadas y cómo se devuelve"; ADR-0021; T-104).

- `list_discarded`: las descartadas de una versión, con su estado derivado: `devuelta` si
  hay en esa versión un requisito con `restored_from` apuntando a ella, `descartada` si no.
  Una versión abierta sobre una validada ve las de su propuesta original, por la cadena
  `based_on`. Se puede ver en cualquier versión.
- `restore`: el operador o el evaluador (devolver equivale a agregar un requisito). Crea el
  requisito con la clase, los renglones y las citas de la descartada (la principal y las
  repetidas), origen `devuelto`, estado `propuesto`; deja la fila `devolver` del historial
  con el motivo y el indicio del descarte, y el hecho `requirement_change`. Solo en un
  borrador; una descartada se devuelve una sola vez por versión. Todo o nada.

La tabla de descartadas es de solo inserción: devolver no la modifica.
"""

from dataclasses import dataclass

from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.tenders.models import (
    ChangeAction,
    DiscardedRow,
    MatrixVersion,
    Requirement,
    RequirementOrigin,
    RequirementQuote,
    RequirementState,
    Segment,
)
from evaluon.tenders.services import review
from evaluon.tenders.services.review import ReviewRefused, Reviewed

RESTORE_OPERATION = "evaluon.tenders.services.discarded.restore"

DISCARDED = "descartada"
RESTORED = "devuelta"


@dataclass(frozen=True)
class DiscardedView:
    """Una descartada y su estado en la versión que se mira. `requirement` es el requisito
    devuelto, si lo hay."""

    row: DiscardedRow
    state: str
    requirement: Requirement = None


def chain_version_ids(version):
    """Los ids de la versión y de las anteriores de las que se abrió (`based_on`)."""
    ids, current = [], version
    while current is not None and current.pk not in ids:
        ids.append(current.pk)
        current = current.based_on
    return ids


def rows_of(version):
    """Las descartadas de la versión y de su cadena, por versión de origen y orden."""
    ids = chain_version_ids(version)
    return list(DiscardedRow.objects.filter(version_id__in=ids).select_related(
        "segment", "evidence_segment").order_by("version__number", "order", "id"))


def list_discarded(version):
    """Las descartadas de `version` (y de su cadena) con su estado derivado."""
    rows = rows_of(version)
    returned = {r.restored_from_id: r for r in Requirement.objects.filter(
        version=version, restored_from__in=rows)}
    return [DiscardedView(row, RESTORED if row.pk in returned else DISCARDED,
                          returned.get(row.pk)) for row in rows]


def counts(version):
    """`(descartadas totales, devueltas)` de la versión, para el hecho de validación."""
    rows = rows_of(version)
    restored = Requirement.objects.filter(version=version,
                                          restored_from__in=rows).count()
    return len(rows), restored


def _info(row):
    """El motivo y el indicio del descarte, tal como quedan en el historial."""
    return {
        "discarded": row.pk, "reason": row.reason,
        "evidence": {"segment": row.evidence_segment_id,
                     "char_start": row.evidence_start, "char_end": row.evidence_end,
                     "text": row.evidence_text},
    }


def restore(user, version_id, row_ids, *, channel=Channel.SCREEN):
    """Devuelve a la matriz las descartadas `row_ids` de la versión `version_id`.
    Devuelve un `Reviewed` con los requisitos creados, en el orden pedido."""
    try:
        ids = list(dict.fromkeys(int(i) for i in row_ids))
    except (TypeError, ValueError):
        ids = []
    detail = {"version": version_id, "discarded": ids}

    def work():
        version = review._lock_draft(version_id)
        if not ids:
            raise ReviewRefused("Marque al menos una fila descartada para devolver.",
                                "nothing_selected", "discarded")
        rows = {r.pk: r for r in DiscardedRow.objects.filter(
            pk__in=ids, version_id__in=chain_version_ids(version))}
        if len(rows) != len(ids):
            raise ReviewRefused("Esa fila no está entre las descartadas de esta matriz.",
                                "discarded_not_found", "discarded")
        if Requirement.objects.filter(version=version, restored_from__in=ids).exists():
            raise ReviewRefused("Esa fila ya se devolvió a esta versión de la matriz.",
                                "already_restored", "discarded")
        number = (version.requirements.aggregate(m=Max("number"))["m"] or 0)
        done = Reviewed(requirements=[])
        for pk in ids:
            number += 1
            requirement, change, event = _create(version, rows[pk], number, user, channel)
            done.requirements.append(requirement)
            done.changes.append(change)
            done.events.append(event)
        return done

    return review._run(user, CommissionRole.OPERATOR, RESTORE_OPERATION,
                       ChangeAction.DEVOLVER, channel, detail, work)


def _create(version, row, number, user, channel):
    requirement = Requirement.objects.create(
        version=version, number=number, category=row.category, items=list(row.items),
        origin=RequirementOrigin.DEVUELTO, state=RequirementState.PROPUESTO,
        restored_from=row, proposed={}, passes=list(row.passes))
    RequirementQuote.objects.create(
        requirement=requirement, order=1, segment=row.segment, char_start=row.char_start,
        char_end=row.char_end, text=row.text, scope="", quote_flag="")
    for order, extra in enumerate(row.extra_quotes, start=2):
        RequirementQuote.objects.create(
            requirement=requirement, order=order,
            segment=Segment.objects.get(pk=extra["segment"]),
            char_start=extra["char_start"], char_end=extra["char_end"],
            text=extra["text"], scope="repetida", quote_flag="")
    after = review._snapshot(requirement)
    requirement.proposed = after
    requirement.save(update_fields=["proposed"])
    info = _info(row)
    change, event = review._record(requirement, ChangeAction.DEVOLVER, info, after, user,
                                   channel, info)
    return requirement, change, event
