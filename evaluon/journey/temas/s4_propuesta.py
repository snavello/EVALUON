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

El fundamento de cada celda se ve completo (P3, T-264): el dato del Portal con el enlace a su página y
la fecha en que se tomó, y la cita de una página leída por visión con la marca, el aviso de que
conviene que la Comisión la vuelva a chequear y el enlace a la imagen, como en la pantalla de la 004.
Las citas de todas las celdas se traen juntas, sin una consulta por celda (T-223).
"""

import dataclasses
from dataclasses import dataclass, field

from django.http import Http404
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.assessment import not_applicable
from evaluon.assessment.models import Decision, Doubt, Outcome, Result
from evaluon.assessment.services import evaluate, external_stages, review
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.journey import basis, external, memo, points, reading_note
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.stages import base as stage_base
from evaluon.journey.stages import evaluacion as evaluation_stage
from evaluon.journey.stages import stage_of
from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Tile, detail_id
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.window import plain_reason
from evaluon.tenders.models import RequirementClass

KEY = "s4_propuesta"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_propuesta.html"

TYPE_ORDER = (RequirementClass.FORMAL, RequirementClass.ECONOMICO, RequirementClass.TECNICO)
TYPE_LABELS = {
    RequirementClass.FORMAL: "Requisitos formales",
    RequirementClass.ECONOMICO: "Requisitos económicos",
    RequirementClass.TECNICO: "Requisitos técnicos por renglón",
}
EXTERNAL = "externo"
EXTERNAL_LABEL = "Requisitos que se cumplen con información externa"
TYPE_OPTIONS = (("formal", "Formales"), ("economico", "Económicos"),
                ("tecnico", "Técnicos por renglón"), (EXTERNAL, "Con información externa"))
SHOW_OPTIONS = (("", "Todos los requisitos"),
                ("sin-decidir", "Solo los pares por decidir (los del panel de pendientes)"),
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
# Resultado de cada condición del requisito -> (ícono, nombre) (T-237, REQ-104).
CONDITION_ICONS = {
    "cumple": ("cumple", "Cumple"),
    "no_cumple": ("nocumple", "No cumple"),
    "no_consta": ("nodet", "No consta"),
    "no_determinado": ("nodet", "No determinado"),
}
PENDING_ICON = ("pend", "Pendiente del informe técnico")
# Un requisito que no aplica a la oferta (forma de garantía no elegida u opción no usada, T-257): nunca
# «Cumple» (T-240).
NOT_APPLICABLE_ICON = ("na", not_applicable.LABEL)
REJECTED_ICON = ("pend", "Propuesta rechazada: sin resultado hasta que se evalúe de nuevo")
STATE_TEXT = {
    matrix_service.PENDING: "Propuesto, sin decidir",
    matrix_service.CONFIRMED: "Confirmado",
    matrix_service.CORRECTED: "Corregido",
    matrix_service.REJECTED: "Rechazado",
}
VERBS = {"confirmar": "Confirmado", "corregir": "Corregido", "rechazar": "Rechazado"}


# T-257: con qué resolvió el sistema una condición que el modelo dejó sin dato (`cubierta_por`).
COVERED_BY = {
    "portal": "dato del Portal de Compras",
    "iva_precio_final_portal": "criterio de la Comisión: el precio del Portal es final con IVA",
    "ausencia_verificada": "por ausencia: ningún documento leído lo contradice",
}


def condition_views(facts):
    """Las condiciones del requisito que revisó el modelo, una por una, para la celda (T-237,
    REQ-104): lo que exige cada una, su dato, su resultado y dónde está su cita. Vacía si el
    resultado no las trae (lo decidió una regla, o es anterior a `evaluacion-v6`)."""
    views = []
    for item in (facts or {}).get("condiciones") or []:
        icon, name = CONDITION_ICONS.get(item.get("resultado"), CONDITION_ICONS["no_determinado"])
        cite = item.get("cita") or {}
        if cite.get("tipo") == "oferta":
            where = f"{cite.get('documento', '')} · página {cite.get('pagina', '')}"
        elif cite.get("tipo") == "portal":
            where = "dato del Portal de Compras"
        else:
            where = ""
        # T-257: la condición que resolvió una regla dice con qué (el Portal o un criterio).
        covered = "ausencia_verificada" if item.get("por_ausencia") else item.get("cubierta_por")
        where = COVERED_BY.get(covered, where)
        views.append({"text": item.get("condicion", ""), "datum": item.get("dato", ""),
                      "icon": icon, "name": name, "where": where})
    return views


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
    conditions: list = field(default_factory=list)  # cada condición con su dato y su resultado
    quotes: list = field(default_factory=list)  # citas de la oferta (texto, documento, página)
    portal: list = field(default_factory=list)  # datos del Portal citados (con su página y fecha)
    read_note: str = ""  # sin cita de la oferta: qué documentos y páginas se leyeron (T-228)
    technical: bool = False
    counted: bool = False  # par por decidir: el que cuenta el panel de pendientes
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
    points: list = field(default_factory=list)  # el punto completo del pliego (T-228)
    external: tuple = ()  # consultas externas que lo cubren; vacío si se resuelve con la oferta


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


# Por qué importa cada pendiente (REQ-129; T-318 suma `Item.why`). Lo escribe el tema y no inventa
# nada del caso: dice qué es el renglón y qué pasa si se lo deja.
WHY_PAIR = ("Es una propuesta del sistema: no vale como resultado hasta que un evaluador la "
            "confirme, la corrija o la rechace.")
WHY_QUESTION = ("El sistema no pudo concluir este requisito y pide una respuesta de la Comisión; "
                "mientras no se responda, el par sigue abierto.")


def _with_why(why, **fields):
    """Un `Item` con su `why`, si `Item` ya tiene el campo (lo suma T-318); si no, sin él."""
    if "why" in {f.name for f in dataclasses.fields(Item)}:
        fields["why"] = why
    return Item(**fields)


def _items(page, procedure):
    """Cada cosa que la Comisión debe decidir en esta pestaña, con su ancla (y ninguna sugerencia:
    el descarte propuesto es decisión de la Comisión y lo lista `s4_descartes`, T-210). Los oks
    del informe técnico del área los lista `s4_informe` (T-209); entre los tres suman lo que
    cuenta la etapa `matriz_evaluacion`."""
    base = _tab(procedure)
    technical = _technical_cells(page)
    point_map = points.points_of_page(page)
    pending = []
    for requirement in page.requirements:
        for offer in page.offers:
            cell = page.cells[(offer.pk, requirement.pk)]
            if (cell.state == matrix_service.PENDING
                    and (offer.pk, requirement.pk) not in technical):
                pending.append(_with_why(
                    WHY_PAIR,
                    text=(f"Oferta {offer.number} · requisito {requirement.number}: "
                          f"{cell.effective_label.lower()} propuesto, sin decidir"),
                    url=f"{base}#ev-{requirement.number}", count=1, action="Resolver",
                    kind="par", noun="pares por decidir",
                    group_url=f"{base}?ver=sin-decidir#s4-propuesta",
                    points=tuple(point_map.get(requirement.pk, ()))))
    for status in page.statuses:
        for question in status.open_questions:
            pending.append(_with_why(
                WHY_QUESTION,
                text=(f"Oferta {status.offer.number} · requisito "
                      f"{question.requirement.number}: pregunta abierta"),
                url=f"{base}#preg-{question.pk}", count=1, action="Resolver",
                kind="pregunta", noun="preguntas abiertas",
                group_url=f"{base}?preg=abiertas#s4-preguntas", group_action="Responder",
                points=tuple(point_map.get(question.requirement_id, ()))))
    return pending, []


def status(user, procedure):
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
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
    # Las citas de la oferta (con la marca de visión) y los datos del Portal de todos los pares, de
    # una vez: `journey/basis.py`.
    offer_quotes, portal_data = basis.of_results(ids)
    last = {}
    for decision in (Decision.objects.filter(result_id__in=ids, action__in=review.STATE_ACTIONS)
                     .select_related("user").order_by("at", "pk")):
        last[decision.result_id] = decision
    is_evaluator = getattr(user, "commission_role", "") == CommissionRole.EVALUATOR
    views, unquoted = {}, []
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
        elif cell.effective_key == not_applicable.KEY:
            # T-257: el texto es el de la regla que lo dejó sin aplicar (forma de garantía u opción).
            view.icon, view.name = NOT_APPLICABLE_ICON[0], cell.effective_label
        else:
            view.icon, view.name = OUTCOME_ICONS[cell.effective_outcome]
            if cell.reason_label:
                view.name += f": {cell.reason_label}"
        decision = last.get(result.pk)
        view.decided = decision_line(decision) if decision else ""
        view.explanation = result.explanation
        view.conditions = condition_views(result.facts)
        view.quotes = offer_quotes.get(result.pk, [])
        view.portal = portal_data.get(result.pk, [])
        if not view.quotes:
            unquoted.append(result)
        view.technical = key in technical
        view.counted = cell.state == matrix_service.PENDING and not view.technical
        view.can_decide = is_evaluator and not view.technical
        view.options = [(value, label) for value, label in Outcome.choices
                        if value != result.outcome]
        view.pair_url = acciones.pair_url(page.procedure, cell.offer.pk, cell.requirement.pk)
    # Los resultados sin texto de la oferta dicen qué se leyó (T-228), con una sola consulta.
    notes = reading_note.notes_for(unquoted)
    for view in views.values():
        if view.cell.result is not None and view.cell.result.pk in notes:
            view.read_note = notes[view.cell.result.pk]
    return views


def _rows(page, user):
    views = _cell_views(page, user)
    quotes = points.quotes_of_page(page)
    texts = points.texts_of_page(page)
    point_map = points.points_of_page(page)
    flagged = {e.requirement.pk: e.checks for e in external.requirements_of_page(page)}
    rows = []
    for requirement in page.requirements:
        mine = quotes.get(requirement.pk, [])
        first = mine[0] if mine else None
        # El texto vigente después de las circulares, el que lee la evaluación.
        current = texts[requirement.pk].quotes
        now = current[0].text if current else ""
        items = ", ".join(str(i) for i in requirement.items)
        text = _excerpt(now) if first else "Sin cita"
        if requirement.category == RequirementClass.TECNICO:
            text = f"Renglón {items or '—'} · {text}"
        cells = [views[(offer.pk, requirement.pk)] for offer in page.offers]
        rows.append(Row(
            requirement=requirement, number=requirement.number, category=requirement.category,
            text=text, document=_where(first) if first else "Sin cita",
            quote=now, cells=cells,
            technical=any(c.technical for c in cells),
            points=point_map.get(requirement.pk, []),
            external=flagged.get(requirement.pk, ())))
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
        if kind == EXTERNAL and not row.external:
            continue
        if kind and kind != EXTERNAL and row.category != kind:
            continue
        if show == "sin-decidir" and not any(c.counted for c in row.cells):
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
    """Los requisitos que se cumplen con información externa, aparte y primero (T-228); después los
    de cada clase."""
    groups = []
    outside = [row for row in rows if row.external]
    if outside:
        groups.append({"category": EXTERNAL, "label": EXTERNAL_LABEL, "count": len(outside),
                       "rows": outside, "external": True})
    rows = [row for row in rows if not row.external]
    for category in TYPE_ORDER:
        mine = [row for row in rows if row.category == category]
        if mine:
            groups.append({"category": category, "label": TYPE_LABELS[category],
                           "count": len(mine), "rows": mine})
    return groups


def _progress(user, procedure):
    """El avance del pedido en curso o la falla del último, desde la etapa de la 013."""
    stage = stage_of(evaluation_stage, user, procedure)
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


def _externals(page):
    """Los requisitos que se cumplen con información externa, con su punto del pliego, y por
    oferta qué falta de la hoja de compliance (T-228). Se ven desde antes de evaluar."""
    found = external.requirements_of_page(page)
    if not found or not page.offers:
        return {"externals": [], "sheet_gaps": [], "can_upload_sheet": False}
    point_map = points.points_of_page(page)
    return {
        "externals": [{"requirement": e.requirement, "number": e.number,
                       "checks": ", ".join(e.checks), "points": point_map.get(e.requirement.pk, [])}
                      for e in found],
        "sheet_gaps": external.gaps_of_page(page),
        "can_upload_sheet": page.can_upload_sheet,
    }


def context(user, procedure, request):
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
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
        # Las cifras del tablero salen de la misma matriz, una sola vez por pedido (T-327).
        "tablero": figures_of(page) if evaluated else None,
        **_externals(page),
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


# --- El tablero: cifras y mosaicos (REQ-126, REQ-141; T-327) ---------------------------------------

DETAIL = detail_id(KEY)
MISSING = "Pendiente"
CLASS_LABELS = {RequirementClass.FORMAL: "Formales", RequirementClass.ECONOMICO: "Económicos",
                RequirementClass.TECNICO: "Técnicos"}


@dataclass(frozen=True)
class OfferFigures:
    """Cuántos requisitos de la oferta están en cada estado. `ok + no + nd + pe + na` es la
    cantidad de requisitos de la matriz; `na` (no aplica) no entra en ningún total."""

    number: int
    ok: int = 0
    no: int = 0
    nd: int = 0
    pe: int = 0
    na: int = 0

    @property
    def label(self):
        return f"Of. {self.number}"


@dataclass(frozen=True)
class Figures:
    """Las cifras del tablero de la propuesta. Solo de las celdas guardadas (P3): las ofertas con
    evaluación, su cuenta por estado y el cumplimiento por clase de requisito."""

    offers: tuple  # OfferFigures de las ofertas con evaluación, en el orden de la matriz
    unevaluated: tuple  # números de las ofertas sin evaluación
    total_offers: int
    requirements: int
    version: int
    heat: tuple  # (clase, (cumplen, total) o None por cada oferta evaluada)

    @property
    def no(self):
        return sum(o.no for o in self.offers)

    @property
    def nd(self):
        return sum(o.nd for o in self.offers)

    @property
    def na(self):
        return sum(o.na for o in self.offers)


def _bucket(cell):
    """En qué estado cuenta una celda: `ok`, `no`, `nd`, `pe` o `na`. Es la misma lectura que hace
    la tabla de la propuesta (`_cell_views`): sin resultado, rechazada o a la espera del informe
    técnico es pendiente; un requisito que no aplica nunca es «cumple» (T-240)."""
    if cell.result is None or cell.effective_outcome is None:
        return "pe"
    if cell.effective_key == not_applicable.KEY:
        return "na"
    if cell.reason == Doubt.PENDIENTE_INFORME_TECNICO:
        return "pe"
    if cell.effective_outcome == Outcome.CUMPLE:
        return "ok"
    if cell.effective_outcome in (Outcome.NO_CUMPLE, Outcome.SIN_DOCUMENTO):
        return "no"
    return "nd"


def _offer_figures(status, requirements):
    """La cuenta de una oferta desde `by_outcome` y `by_reason` de la matriz (ADR-0039): lo que no
    tiene resultado vigente, o espera el informe técnico, es pendiente."""
    by = status.by_outcome
    waiting = status.by_reason.get(Doubt.PENDIENTE_INFORME_TECNICO, 0)
    return OfferFigures(
        number=status.offer.number, ok=by.get(Outcome.CUMPLE, 0),
        no=by.get(Outcome.NO_CUMPLE, 0) + by.get(Outcome.SIN_DOCUMENTO, 0),
        nd=by.get(Outcome.NO_DETERMINADO, 0) - waiting,
        pe=requirements - sum(by.values()) + waiting, na=by.get(not_applicable.KEY, 0))


def figures_of(page):
    """Las cifras del tablero desde la matriz del pedido, o `None` si no hay evaluación (o no hay
    requisitos): entonces cada mosaico dice «Pendiente» y no muestra valor (REQ-141)."""
    evaluated = [s for s in page.statuses if s.evaluated]
    if not evaluated or not page.requirements:
        return None
    heat = []
    for category in TYPE_ORDER:
        mine = [r for r in page.requirements if r.category == category]
        if not mine:
            continue
        row = []
        for status in evaluated:
            buckets = [_bucket(page.cells[(status.offer.pk, r.pk)]) for r in mine]
            applicable = [b for b in buckets if b != "na"]
            row.append((applicable.count("ok"), len(applicable)) if applicable else None)
        heat.append((category, tuple(row)))
    return Figures(
        offers=tuple(_offer_figures(s, len(page.requirements)) for s in evaluated),
        unevaluated=tuple(s.offer.number for s in page.statuses if not s.evaluated),
        total_offers=len(page.offers), requirements=len(page.requirements),
        version=page.version.number if page.version else 0, heat=tuple(heat))


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def tiles(user, procedure, ctx):
    """Resultado por oferta, No cumple, No determinado y Cumplimiento por tipo; los cuatro abren
    el detalle de la propuesta (con su fundamento y su cita). Sin evaluación cada uno dice
    «Pendiente» y no dibuja cifra ni gráfico. Reusa las cifras que calculó `context()`; solo si no
    vienen (otro llamador) las arma de la matriz."""
    if ctx is not None and "tablero" in ctx:
        fig = ctx["tablero"]
    else:
        fig = figures_of(memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN))
    if fig is None:
        return [Tile(key=key, title=title, detail=DETAIL, width=width, missing=MISSING)
                for key, title, width in (
                    ("resultado", "Resultado por oferta", 2), ("nocumple", "No cumple", 1),
                    ("nodeterminado", "No determinado", 1),
                    ("tipo", "Cumplimiento por tipo y oferta", 2))]
    evaluated = len(fig.offers)
    sub = "Requisitos que cumple cada una, según el resultado vigente."
    if fig.unevaluated:
        word = "oferta" if len(fig.unevaluated) == 1 else "ofertas"
        sub += f" Sin evaluar: {word} {', '.join(str(n) for n in fig.unevaluated)}."
    if fig.na:
        sub += (f" {fig.na} no aplica y no se cuenta." if fig.na == 1
                else f" {fig.na} no aplican y no se cuentan.")
    scope = f"en {_plural(evaluated, 'oferta evaluada', 'ofertas evaluadas')}"
    donuts = charts.Donuts(
        uid="s4-resultado", title="Resultado por oferta",
        items=[charts.DonutItem(o.label, ok=o.ok, no=o.no, nd=o.nd, pe=o.pe) for o in fig.offers])
    heat = charts.Heat(
        uid="s4-tipo", title="Cumplimiento por tipo y oferta",
        columns=[o.label for o in fig.offers],
        rows=[charts.HeatRow(CLASS_LABELS[category], [
            None if cell is None else charts.HeatCell(cell[0], cell[1]) for cell in cells])
            for category, cells in fig.heat])
    unit = ("de 1 oferta evaluada" if fig.total_offers == 1
            else f"de {fig.total_offers} ofertas evaluadas")
    return [
        Tile(key="resultado", title="Resultado por oferta", detail=DETAIL, width=2,
             big=evaluated, unit=unit, sub=sub, chart=donuts, missing=MISSING),
        Tile(key="nocumple", title="No cumple", detail=DETAIL, big=fig.no, unit="requisitos",
             sub=f"Pares requisito-oferta que no cumplen {scope}", missing=MISSING),
        Tile(key="nodeterminado", title="No determinado", detail=DETAIL, big=fig.nd,
             unit="requisitos",
             sub=f"Pares que el sistema no pudo concluir {scope}; los resuelve la Comisión",
             missing=MISSING),
        Tile(key="tipo", title="Cumplimiento por tipo y oferta", detail=DETAIL, width=2,
             big=fig.requirements, unit="requisitos",
             sub=f"Cumplen / total, por tipo y oferta · matriz versión {fig.version}",
             chart=heat, missing=MISSING),
    ]


def opens(request):
    """Los filtros de la tabla de la propuesta (`?ver=`, `?tipo=`) abren su detalle. Un valor
    desconocido se ignora, igual que en la tabla (`_select`)."""
    show, kind = request.GET.get("ver", ""), request.GET.get("tipo", "")
    if (show and show in dict(SHOW_OPTIONS)) or (kind and kind in dict(TYPE_OPTIONS)):
        return DETAIL
    return None


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
    notes = ({} if page.offer_citations
             else reading_note.notes_for([page.result]))
    context = portada.shell(request, overview, active=SECTION)
    context.update({
        "section": overview.get(SECTION), "page": page, "stages": stages,
        "review": pair_review, "technical": technical,
        "can_decide": pair_review.can_decide and not technical,
        "aviso": acciones.unpack(request.GET.get("aviso")), "pid": procedure.pk,
        "tab_url": _tab(procedure), "built": when(page.run.built_at),
        "decided": decision_line(pair_review.decision) if pair_review.decision else "",
        "state_text": STATE_TEXT.get(pair_review.state, pair_review.state),
        "points": points.points_of([page.requirement])[page.requirement.pk],
        "read_note": notes.get(page.result.pk, ""),
        "conditions": condition_views(page.result.facts),
        "external_line": external_stages.line([page.run]),
    })
    return render(request, "journey/temas/s4_propuesta_par.html", context)


urlpatterns = [
    *acciones.urlpatterns,
    path("evaluacion/par/<int:offer_id>/<int:requirement_id>/", pair, name="s4_par"),
]
