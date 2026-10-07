"""Etapa 6, Matriz de evaluación (REQ-066, REQ-068, REQ-069, REQ-072; plan 013).

No tiene pedidos propios: las decisiones son de personas. Todo sale de
`assessment.services.matrix.matrix_page`, que ya calcula el estado de cada par (definición
única de "vigente", ADR-0039) y no se redefine acá:

- Pendiente: no hay ninguna evaluación.
- A decidir: pares `propuesto`, preguntas sin respuesta y ofertas con filas técnicas sin el ok
  del informe técnico. `pending` es la suma de los tres y el detalle los nombra por separado.
  Los pares de las filas técnicas (con el ok pendiente o ya dado) no se cuentan también como
  pares: la decisión de esas filas es el ok, no confirmar el par.
- Lista: ningún par `propuesto`, ninguna pregunta abierta y ningún ok técnico pendiente.

Sugerencias (aparte, REQ-072): los descartes que el sistema propone; son información y no
frenan la etapa.

La etapa solo lee. Los enlaces son la matriz (`assessment:matrix`) y, cuando lo único que falta
son preguntas, las preguntas (`assessment:questions`); solo el evaluador recibe el de decidir.
"""

from django.urls import reverse

from evaluon.assessment.services import matrix as matrix_service
from evaluon.journey.stages import base

KEY = "matriz_evaluacion"
LABEL = "Matriz de evaluación"


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


def _undecided_pairs(page):
    """Los pares `propuesto`, sin los de filas técnicas (cualquiera sea su resultado): la
    decisión de esas filas es el ok del informe técnico, que se cuenta aparte."""
    technical_cells = {(status.offer.pk, row.requirement.pk)
                       for status in page.statuses for row in status.technical}
    return sum(1 for key, cell in page.cells.items()
               if cell.state == matrix_service.PENDING and key not in technical_cells)


def _technical_pending_offers(page):
    """Las ofertas con alguna fila técnica ya evaluada y sin ok vigente del informe."""
    return sum(1 for status in page.statuses
               if any(not row.approved
                      and page.cells[(status.offer.pk, row.requirement.pk)].result is not None
                      for row in status.technical
                      if (status.offer.pk, row.requirement.pk) in page.cells))


def compute(user, procedure):
    page = matrix_service.matrix_page(user, procedure.pk)
    view_url = reverse("assessment:matrix", args=[procedure.pk])
    common = {"key": KEY, "label": LABEL, "view_url": view_url}
    suggestions = len(page.discards)
    hint = ""
    if suggestions:
        hint = (" Sugerencias del sistema: "
                + _plural(suggestions, "descarte propuesto", "descartes propuestos") + ".")

    if not any(status.evaluated for status in page.statuses):
        return base.Stage(state=base.PENDIENTE, suggestions=suggestions,
                          detail="Todavía no hay ninguna evaluación." + hint, **common,
                          decide_url=view_url if base.is_evaluator(user) else None)

    pairs = _undecided_pairs(page)
    questions = sum(len(status.open_questions) for status in page.statuses)
    reports = _technical_pending_offers(page)
    pending = pairs + questions + reports

    decide_url = None
    if base.is_evaluator(user):
        only_questions = questions and not pairs and not reports
        decide_url = (reverse("assessment:questions", args=[procedure.pk])
                      if only_questions else view_url)

    if pending == 0:
        return base.Stage(state=base.LISTA, suggestions=suggestions, decide_url=decide_url,
                          detail="No quedan pares por decidir ni preguntas abiertas." + hint,
                          **common)

    parts = []
    if pairs:
        parts.append(_plural(pairs, "par por decidir", "pares por decidir"))
    if questions:
        parts.append(_plural(questions, "pregunta abierta", "preguntas abiertas"))
    if reports:
        parts.append(_plural(reports, "oferta", "ofertas")
                     + " con el ok del informe técnico pendiente")
    return base.Stage(state=base.A_DECIDIR, pending=pending, suggestions=suggestions,
                      decide_url=decide_url, detail="Falta decidir: " + "; ".join(parts) + "."
                      + hint, **common)
