"""Tema s4_propuesta: la propuesta de evaluación por oferta y requisito de la sección «Evaluación y
dictamen» (REQ-089, REQ-097; plan 014, T-207).

Muestra «Evaluar todas las ofertas», el avance del pedido y la tabla de requisitos por ofertas con
lo que el sistema propone (cumple, no cumple, no determinado) y su fundamento: cada fila se abre y
dice, por oferta, el fundamento, el estado de la propuesta y, si la Comisión decidió, quién, cuándo
y con qué motivo. El evaluador confirma, corrige o rechaza desde la fila o desde el detalle del par
(que se abre dentro de la pestaña, con su historial); un operador ve el estado y no los botones.
Todo sale de `matrix_page` (la definición única de «vigente» y del estado de un par, ADR-0039): el
tema no los redefine ni decide nada (P3). Las acciones están en `s4_propuesta_acciones`.

Las cuentas de pendientes y sugerencias las suma la etapa `matriz_evaluacion` de la 013; este tema
las lista una por una, con su enlace a esta pestaña, y coinciden con las de la barra.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from django.http import Http404
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.assessment.models import Citation, CitationKind, Decision, Outcome, Result
from evaluon.assessment.services import evaluate, review
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.stages import base as stage_base
from evaluon.journey.stages import evaluacion as evaluation_stage
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.window import plain_reason
from evaluon.tenders.models import RequirementClass, RequirementQuote

KEY = "s4_propuesta"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_propuesta.html"

TYPE_ORDER = (RequirementClass.FORMAL, RequirementClass.ECONOMICO, RequirementClass.TECNICO)
TYPE_LABELS = {
    RequirementClass.FORMAL: "Requisitos formales",
    RequirementClass.ECONOMICO: "Requisitos económicos",
    RequirementClass.TECNICO: "Requisitos técnicos por renglón",
}
TYPE_OPTIONS = (("formal", "Formales"), ("economico", "Económicos"),
                ("tecnico", "Técnicos por renglón"))
SHOW_OPTIONS = (("", "Todos los requisitos"),
                ("abiertas", "Solo lo abierto (sin decidir, no determinado o rechazado)"),
                ("nocumple", "Solo los que no cumplen"))
EXCERPT = 200

# Resultado -> (ícono, nombre). «Pendiente» es lo que espera el informe técnico o un documento.
OUTCOME_ICONS = {
    Outcome.CUMPLE: ("cumple", "Cumple"),
    Outcome.NO_CUMPLE: ("nocumple", "No cumple"),
    Outcome.SIN_DOCUMENTO: ("nocumple", "No se encontró el documento"),
    Outcome.NO_DETERMINADO: ("nodet", "No determinado"),
}
PENDING_ICON = ("pend", "Pendiente del informe técnico")
REJECTED_ICON = ("pend", "Propuesta rechazada: sin resultado hasta que se evalúe de nuevo")
STATE_TEXT = {
    matrix_service.PENDING: "Propuesto, sin decidir",
    matrix_service.CONFIRMED: "Confirmado",
    matrix_service.CORRECTED: "Corregido",
    matrix_service.REJECTED: "Rechazado",
}
VERBS = {"confirmar": "Confirmado", "corregir": "Corregido", "rechazar": "Rechazado"}


@dataclass
class CellView:
    """Un par de la tabla, con lo que se muestra y lo que se puede hacer."""

    offer: object
    cell: object
    icon: str = ""
    name: str = ""
    state_text: str = ""
    decided: str = ""  # «Corregido por … el 07/10/2026 16:40 · motivo: …»
    explanation: str = ""
    quotes: list = field(default_factory=list)  # citas de la oferta (texto, documento, página)
    technical: bool = False
    can_decide: bool = False
    options: list = field(default_factory=list)  # resultados a los que se puede corregir
    pair_url: str = ""

    @property
    def result(self):
        return self.cell.result

    @property
    def open(self):
        """Algo que la Comisión debe mirar: sin decidir, no determinado o rechazado."""
        if self.cell.result is None:
            return False
        return (self.cell.state in (matrix_service.PENDING, matrix_service.REJECTED)
                or self.cell.effective_outcome == Outcome.NO_DETERMINADO)


@dataclass
class Row:
    requirement: object
    number: int
    category: str
    text: str
    document: str
    quote: str
    cells: list
    technical: bool


def _day(moment):
    """La fecha en hora local (America/Argentina/Buenos_Aires), no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y}"


def when(moment):
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


def _excerpt(text):
    text = " ".join((text or "").split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"


def _tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def _technical_cells(page):
    """Los pares de las filas técnicas: se deciden con el ok del informe del área, no acá."""
    return {(status.offer.pk, row.requirement.pk)
            for status in page.statuses for row in status.technical}


# --- Estado y lista de pendientes ----------------------------------------------------------------


def _items(page, procedure):
    """Cada cosa que la Comisión debe decidir en esta pestaña y cada sugerencia del sistema, con
    su ancla. Los oks del informe técnico del área los lista `s4_informe` (T-209); entre los dos
    suman lo mismo que cuenta la etapa `matriz_evaluacion`."""
    base = _tab(procedure)
    technical = _technical_cells(page)
    pending = []
    for requirement in page.requirements:
        for offer in page.offers:
            cell = page.cells[(offer.pk, requirement.pk)]
            if (cell.state == matrix_service.PENDING
                    and (offer.pk, requirement.pk) not in technical):
                pending.append(Item(
                    f"Oferta {offer.number} · requisito {requirement.number}: "
                    f"{cell.effective_label.lower()} propuesto, sin decidir",
                    f"{base}#ev-{requirement.number}", 1, "Resolver"))
    for status in page.statuses:
        for question in status.open_questions:
            pending.append(Item(
                f"Oferta {status.offer.number} · requisito {question.requirement.number}: "
                "pregunta abierta", f"{base}#ev-{question.requirement.number}", 1, "Resolver"))
    suggestions = []
    for discard in page.discards:
        scope = ("completa" if discard.is_whole else
                 "renglones " + ", ".join(str(i) for i in sorted(discard.by_item)))
        suggestions.append(Item(f"Descarte propuesto: oferta {discard.offer.number} ({scope})",
                                f"{base}#s4-descartes", 1, "Ver"))
    return pending, suggestions


def status(user, procedure):
    page = matrix_service.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    runs = [s.run for s in page.statuses if s.evaluated]
    if not runs:
        return TemaStatus(detailed_stages=("matriz_evaluacion",))
    latest = max(run.built_at for run in runs)
    source = (f"Propuesta del sistema: {len(runs)} de {len(page.offers)} ofertas evaluadas con "
              f"la matriz versión {page.version.number}, la última el {_day(latest)}.")
    pending, suggestions = _items(page, procedure)
    return TemaStatus(sources=(source,), pending_items=tuple(pending),
                      suggestion_items=tuple(suggestions),
                      detailed_stages=("matriz_evaluacion",))


# --- La tabla --------------------------------------------------------------------------------------


def _quotes_of(requirement_ids):
    found = defaultdict(list)
    for quote in (RequirementQuote.objects.filter(requirement_id__in=requirement_ids)
                  .select_related("segment__reading__document")
                  .order_by("requirement_id", "order")):
        found[quote.requirement_id].append(quote)
    return found


def _where(quote):
    segment = quote.segment
    document = segment.reading.document.title
    return f"{document} › {segment.path}" if segment.path else document


def decision_line(decision):
    """«Corregido por X el 07/10/2026 16:40 · resultado: No cumple · motivo: …» (hora local)."""
    who = decision.user.username if decision.user_id else "—"
    verb = VERBS.get(decision.action, decision.get_action_display())
    line = f"{verb} por {who} el {when(decision.at)}"
    if decision.outcome_after:
        line += f" · resultado: {Outcome(decision.outcome_after).label}"
    if decision.note:
        line += f" · motivo: {decision.note}"
    return line


def _cell_views(page, user):
    """Una `CellView` por par, con el fundamento y la decisión, en pocas consultas."""
    technical = _technical_cells(page)
    ids = [cell.result.pk for cell in page.cells.values() if cell.result is not None]
    offer_quotes = defaultdict(list)
    for citation in (Citation.objects.filter(result_id__in=ids, kind=CitationKind.OFERTA)
                     .select_related("document").order_by("order")):
        offer_quotes[citation.result_id].append(citation)
    last = {}
    for decision in (Decision.objects.filter(result_id__in=ids, action__in=review.STATE_ACTIONS)
                     .select_related("user").order_by("at", "pk")):
        last[decision.result_id] = decision
    is_evaluator = getattr(user, "commission_role", "") == CommissionRole.EVALUATOR
    views = {}
    for key, cell in page.cells.items():
        view = CellView(offer=cell.offer, cell=cell)
        views[key] = view
        if cell.result is None:
            continue
        result = cell.result
        view.state_text = STATE_TEXT[cell.state]
        if cell.effective_outcome is None:
            view.icon, view.name = REJECTED_ICON
        elif cell.reason == "pendiente_informe_tecnico":
            view.icon, view.name = PENDING_ICON
        else:
            view.icon, view.name = OUTCOME_ICONS[cell.effective_outcome]
            if cell.reason_label:
                view.name += f": {cell.reason_label}"
        decision = last.get(result.pk)
        view.decided = decision_line(decision) if decision else ""
        view.explanation = result.explanation
        view.quotes = offer_quotes.get(result.pk, [])
        view.technical = key in technical
        view.can_decide = is_evaluator and not view.technical
        view.options = [(value, label) for value, label in Outcome.choices
                        if value != result.outcome]
        view.pair_url = acciones.pair_url(page.procedure, cell.offer.pk, cell.requirement.pk)
    return views


def _rows(page, user):
    views = _cell_views(page, user)
    quotes = _quotes_of([r.pk for r in page.requirements])
    rows = []
    for requirement in page.requirements:
        mine = quotes.get(requirement.pk, [])
        first = mine[0] if mine else None
        items = ", ".join(str(i) for i in requirement.items)
        text = _excerpt(first.text) if first else "Sin cita"
        if requirement.category == RequirementClass.TECNICO:
            text = f"Renglón {items or '—'} · {text}"
        cells = [views[(offer.pk, requirement.pk)] for offer in page.offers]
        rows.append(Row(
            requirement=requirement, number=requirement.number, category=requirement.category,
            text=text, document=_where(first) if first else "Sin cita",
            quote=first.text if first else "", cells=cells,
            technical=any(c.technical for c in cells)))
    return rows


def _select(rows, query):
    """Aplica los filtros de la dirección. Un valor desconocido se ignora."""
    kind = query.get("tipo", "")
    show = query.get("ver", "")
    if kind not in dict(TYPE_OPTIONS):
        kind = ""
    if show not in dict(SHOW_OPTIONS):
        show = ""
    chosen = []
    for row in rows:
        if kind and row.category != kind:
            continue
        if show == "abiertas" and not any(c.open for c in row.cells):
            continue
        if show == "nocumple" and not any(
                c.cell.effective_outcome in (Outcome.NO_CUMPLE, Outcome.SIN_DOCUMENTO)
                for c in row.cells):
            continue
        chosen.append(row)
    return chosen, kind, show


def _groups(rows):
    groups = []
    for category in TYPE_ORDER:
        mine = [row for row in rows if row.category == category]
        if mine:
            groups.append({"category": category, "label": TYPE_LABELS[category],
                           "count": len(mine), "rows": mine})
    return groups


def _progress(user, procedure):
    """El avance del pedido en curso o la falla del último, desde la etapa de la 013."""
    stage = evaluation_stage.compute(user, procedure)
    return {
        "running": stage.state == stage_base.EN_CURSO,
        "failed": stage.state == stage_base.CON_ERROR,
        "detail": stage.detail,
        "error": plain_reason(stage.error) if stage.error else "",
        "progress": stage.progress,
    }


def _why_not(page):
    """Por qué no se puede pedir la evaluación (vacío si se puede)."""
    if page.can_request:
        return ""
    if page.pending_job is not None:
        return "Ya hay una evaluación en espera o en curso."
    if not page.offers:
        return "Todavía no hay ofertas cargadas."
    if len(page.without_documents) == len(page.offers):
        return "Ninguna oferta tiene documentos cargados."
    return "Falta una matriz de cumplimiento validada."


def context(user, procedure, request):
    page = matrix_service.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    evaluated = any(s.evaluated for s in page.statuses)
    base = {
        "pid": procedure.pk, "aviso": acciones.unpack(request.GET.get("aviso")),
        "types": TYPE_OPTIONS, "shows": SHOW_OPTIONS, "offers": page.offers,
        "progress": _progress(user, procedure), "can_request": page.can_request,
        "why_not": _why_not(page), "evaluated": evaluated, "version": page.version,
        "newer_version": page.newer_version, "without_documents": page.without_documents,
        "pliego_url": reverse("expedientes:pliego", args=[procedure.pk]),
        "ofertas_url": reverse("expedientes:ofertas", args=[procedure.pk]),
        "is_evaluator": getattr(user, "commission_role", "") == CommissionRole.EVALUATOR,
        "groups": [], "shown": 0, "total": 0, "kind": "", "show": "",
    }
    if not evaluated or not page.requirements:
        return base
    rows = _rows(page, user)
    chosen, kind, show = _select(rows, request.GET)
    return {
        **base, "groups": _groups(chosen), "shown": len(chosen), "total": len(rows),
        "kind": kind, "show": show, "colspan": 3 + len(page.offers),
        "open_pairs": sum(c.open for row in rows for c in row.cells),
        "undetermined": sum(1 for row in rows for c in row.cells
                            if c.cell.effective_outcome == Outcome.NO_DETERMINADO),
    }


# --- Detalle de un par, dentro de la pestaña ------------------------------------------------------


@require_GET
def pair(request, procedure_id, offer_id, requirement_id):
    """El par abierto dentro de la pestaña: lo que exige el pliego, lo que presentó la oferta, la
    propuesta, la decisión y todo el recorrido (propuestas y decisiones, con quién y cuándo)."""
    from evaluon.journey.views import portada

    overview = portada.overview_of(request, procedure_id)
    procedure = overview.procedure
    try:
        page = evaluate.pair_page(request.user, offer_id, requirement_id,
                                  channel=Channel.SCREEN)
        stages = review.history(request.user, offer_id, requirement_id,
                                channel=Channel.SCREEN)
    except Result.DoesNotExist:
        raise Http404("Ese requisito todavía no se evaluó para esa oferta.")
    if page.offer.procedure_id != procedure.pk:
        raise Http404("Esa oferta no es de este procedimiento.")
    pair_review = review.pair_review(request.user, page)
    matrix = matrix_service.matrix_page(request.user, procedure.pk, channel=Channel.SCREEN)
    technical = (page.offer.pk, page.requirement.pk) in _technical_cells(matrix)
    for stage in stages:
        stage.lines = [decision_line(d) for d in stage.decisions]
    context = portada.shell(request, overview, active=SECTION)
    context.update({
        "section": overview.get(SECTION), "page": page, "stages": stages,
        "review": pair_review, "technical": technical,
        "can_decide": pair_review.can_decide and not technical,
        "aviso": acciones.unpack(request.GET.get("aviso")), "pid": procedure.pk,
        "tab_url": _tab(procedure), "built": when(page.run.built_at),
        "decided": decision_line(pair_review.decision) if pair_review.decision else "",
        "state_text": STATE_TEXT.get(pair_review.state, pair_review.state),
    })
    return render(request, "journey/temas/s4_propuesta_par.html", context)


urlpatterns = [
    *acciones.urlpatterns,
    path("evaluacion/par/<int:offer_id>/<int:requirement_id>/", pair, name="s4_par"),
]
