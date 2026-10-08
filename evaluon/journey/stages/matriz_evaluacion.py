"""Etapa 6, Matriz de evaluación (REQ-066, REQ-068, REQ-069, REQ-072; plan 013).

No tiene pedidos propios: las decisiones son de personas. Todo sale de
`assessment.services.matrix.matrix_page`, que ya calcula el estado de cada par (definición
única de "vigente", ADR-0039) y no se redefine acá:

- Pendiente: no hay ninguna evaluación.
- A decidir: pares `propuesto`, preguntas sin respuesta, ofertas con filas técnicas sin el ok
  del informe técnico y descartes propuestos sin decidir (REQ-091: el descarte lo decide la
  Comisión). `pending` es la suma de los cuatro y el detalle los nombra por separado.
  Los pares de las filas técnicas (con el ok pendiente o ya dado) no se cuentan también como
  pares: la decisión de esas filas es el ok, no confirmar el par.
- Lista: ningún par `propuesto`, ninguna pregunta abierta, ningún ok técnico pendiente y ningún
  descarte sin decidir.

Sin sugerencias propias: el descarte propuesto es una decisión pendiente, no una sugerencia
(T-210; antes REQ-072 lo contaba aparte).

La etapa solo lee. Los enlaces son la matriz (`assessment:matrix`) y, cuando lo único que falta
son preguntas, las preguntas (`assessment:questions`); solo el evaluador recibe el de decidir.
"""

from django.urls import reverse

from evaluon.assessment.services import discards as discards_service
from evaluon.assessment.services import matrix as matrix_service
from evaluon.journey import memo
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


def _technical_pending_offer_statuses(page):
    """Los estados de las ofertas con alguna fila técnica ya evaluada y sin ok vigente."""
    return [status for status in page.statuses
            if any(not row.approved
                   and page.cells[(status.offer.pk, row.requirement.pk)].result is not None
                   for row in status.technical
                   if (status.offer.pk, row.requirement.pk) in page.cells)]


def _technical_pending_offers(page):
    """Cuántas ofertas tienen alguna fila técnica ya evaluada y sin ok vigente del informe."""
    return len(_technical_pending_offer_statuses(page))


def compute(user, procedure):
    page = memo.matrix_page(user, procedure.pk)
    view_url = reverse("assessment:matrix", args=[procedure.pk])
    common = {"key": KEY, "label": LABEL, "view_url": view_url}
    suggestions = 0
    hint = ""

    if not any(status.evaluated for status in page.statuses):
        return base.Stage(state=base.PENDIENTE, suggestions=suggestions,
                          detail="Todavía no hay ninguna evaluación." + hint, **common,
                          decide_url=view_url if base.is_evaluator(user) else None)

    pairs = _undecided_pairs(page)
    questions = sum(len(status.open_questions) for status in page.statuses)
    reports = _technical_pending_offers(page)
    discards = sum(1 for u in discards_service.units(page)
                   if u.state == discards_service.PROPOSED)
    pending = pairs + questions + reports + discards

    decide_url = None
    if base.is_evaluator(user):
        only_questions = questions and not pairs and not reports and not discards
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
        pending_offers = _technical_pending_offer_statuses(page)
        without = sum(1 for status in pending_offers if not status.reports)
        if without:
            parts.append(_plural(without, "oferta", "ofertas") + " sin informe técnico")
        if reports - without:
            parts.append(_plural(reports - without, "oferta", "ofertas")
                         + " con el ok del informe técnico pendiente")
    if discards:
        parts.append(_plural(discards, "descarte propuesto", "descartes propuestos"))
    return base.Stage(state=base.A_DECIDIR, pending=pending, suggestions=suggestions,
                      decide_url=decide_url, detail="Falta decidir: " + "; ".join(parts) + "."
                      + hint, **common)
