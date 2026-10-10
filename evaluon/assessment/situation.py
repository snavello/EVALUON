"""La situación de cada oferta en el orden económico (REQ-059, REQ-091; plan 014, T-231, E-9).

Una oferta no figura «Sin observaciones» si tiene algo por resolver: sin evaluar, un «no se
encontró el documento», una subsanación pedida o por decidir. Esta función junta esas
observaciones para la pantalla y la exportación, con la misma cuenta. Solo lee; no decide nada
(P3): la subsanación y el descarte siguen siendo de la Comisión.
"""

from evaluon.assessment.models import Doubt, Outcome
from evaluon.assessment.services import remedy

NOT_EVALUATED = "Sin evaluar"


def _list(numbers):
    shown = [str(n) for n in numbers]
    if len(shown) == 1:
        return f"requisito {shown[0]}"
    return f"requisitos {', '.join(shown[:-1])} y {shown[-1]}"


def _remediable(result, effective):
    if effective == Outcome.SIN_DOCUMENTO:
        return True
    return (effective == Outcome.NO_DETERMINADO == result.outcome
            and result.doubt == Doubt.EXTERNO)


def observations(page):
    """`{id de la oferta: [observación]}` de la matriz `page`: lo que impide decir «Sin
    observaciones» de esa oferta. Con una consulta para las decisiones de subsanación de todos los
    resultados subsanables."""
    cells = [cell for cell in page.cells.values()
             if cell.result is not None and _remediable(cell.result, cell.effective_outcome)]
    ids = [cell.result.pk for cell in cells]
    declined = remedy.declined_for(ids) if ids else {}
    path = remedy.path_decisions_for(ids) if ids else {}
    notes = {}
    for status in page.statuses:
        if not status.evaluated:
            notes[status.offer.pk] = [NOT_EVALUATED]
            continue
        missing, asked, to_decide = [], [], []
        for requirement in page.requirements:
            cell = page.cells[(status.offer.pk, requirement.pk)]
            if cell.result is None:
                continue
            if cell.effective_outcome == Outcome.SIN_DOCUMENTO:
                missing.append(requirement.number)
            if not _remediable(cell.result, cell.effective_outcome):
                continue
            state = remedy.state(cell.result, declined=declined.get(cell.result.pk),
                                 applicable=True, decisions=path.get(cell.result.pk, []))
            if state.requested is not None:
                asked.append(requirement.number)
            elif state.declined is None:
                to_decide.append(requirement.number)
        found = []
        if missing:
            found.append(f"No se encontró el documento ({_list(missing)})")
        if asked:
            found.append(f"Subsanación pedida ({_list(asked)})")
        if to_decide:
            found.append(f"Subsanación por decidir ({_list(to_decide)})")
        notes[status.offer.pk] = found
    return notes
