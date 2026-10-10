"""Los requisitos que se cumplen con información externa, a la vista desde el principio (plan 014,
T-228; REQ-089; P9).

Un requisito es externo si su texto del pliego coincide con el catálogo de `assessment.externals`
(la misma regla que usa la evaluación) o si el modelo ya lo marcó «falta la hoja de compliance»
en alguna oferta. La Comisión necesita saberlo antes de evaluar: esos requisitos no se resuelven
con la oferta sino con la hoja de compliance de cada oferta, y mientras falte la hoja quedan «no
determinado». Este módulo los lista y dice, por oferta, qué falta. Solo lee; no infiere ninguna
consulta ni completa ninguna hoja (P9) y no cambia ningún resultado: el catálogo es el de la
evaluación.

El texto que se mira es el vigente después de las circulares, con el título del tramo, el mismo que
lee la evaluación (`grounds.requirement_text(...).context`): una circular puede volver externo un
requisito o dejar de serlo. Se calcula una vez por pedido (`memo.once`) y con las citas y circulares
que la pantalla ya cargó.
"""

from dataclasses import dataclass, field

from evaluon.assessment import externals
from evaluon.assessment.models import Doubt, Outcome
from evaluon.journey import memo, points

MODEL_FLAGGED = "marcado por el sistema al evaluar"


@dataclass(frozen=True)
class ExternalRequirement:
    """Un requisito externo y qué consulta lo cubre."""

    requirement: object
    checks: tuple  # las consultas del catálogo que lo reconocen, o el aviso del modelo

    @property
    def number(self):
        return self.requirement.number


@dataclass
class SheetGap:
    """Qué falta de la hoja de compliance de una oferta."""

    offer: object
    has_sheet: bool
    count: int  # requisitos externos del procedimiento
    numbers: tuple = field(default=())
    pending: int = 0  # requisitos que siguen «falta la hoja» pese a tenerla

    @property
    def missing_text(self):
        return f"Falta la hoja de compliance de la oferta {self.offer.number}"


def _checks_of(text):
    """Las consultas del catálogo que reconocen el texto vigente del requisito (`RequirementText`)."""
    return tuple(c.label for c in externals.match(text.context))


def requirements_of_page(page):
    """`[ExternalRequirement]` de la matriz de evaluación `page`, en el orden de la matriz."""

    def compute():
        texts = points.texts_of_page(page)
        flagged = {cell.requirement.pk for cell in page.cells.values()
                   if cell.result is not None and cell.result.outcome == Outcome.NO_DETERMINADO
                   and cell.result.doubt == Doubt.EXTERNO}
        found = []
        for requirement in page.requirements:
            checks = _checks_of(texts[requirement.pk])
            if checks:
                found.append(ExternalRequirement(requirement, checks))
            elif requirement.pk in flagged:
                found.append(ExternalRequirement(requirement, (MODEL_FLAGGED,)))
        return found

    return memo.once(("externals", page.procedure.pk, page.version.pk if page.version else None),
                     compute)


def gaps_of_page(page):
    """Por oferta, si tiene su hoja de compliance y cuántos requisitos externos dependen de ella."""
    mine = requirements_of_page(page)
    numbers = tuple(e.number for e in mine)
    return [SheetGap(offer=status.offer, has_sheet=bool(status.sheets), count=len(mine),
                     numbers=numbers, pending=status.externals_pending)
            for status in page.statuses]
