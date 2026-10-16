"""Exportación de la evaluación: planilla por oferta y cuadro comparativo, en Excel y en PDF
(REQ-093; plan 014, T-212; ADR-0050; principio P4).

- **Planilla por oferta**: una hoja por oferta (en el PDF, una página por oferta) con cada
  requisito, el resultado que propone el sistema, su fundamento, la decisión de la Comisión (quién
  y cuándo) y los descartes con su decisión.
- **Cuadro comparativo**: ofertas por requisito y el orden económico (total y por renglón). Una
  oferta o un renglón con descarte CONFIRMADO figura como descartada; uno propuesto sin decidir se
  marca así y sigue ordenándose (los mismos números que la pantalla: sale de `discards.units`,
  `discards.confirmed_discards` y `ordering.economic_order`, sin cambiarlos).
- Todo es propuesta de evaluación del sistema: decide la Comisión (P3); los archivos lo rotulan.
- Un resultado que se apoya en una cita de una página leída por visión (ADR-0041) lo dice: el
  fundamento de la planilla suma que la página tiene dificultades de lectura, en qué documento y
  página está, y que conviene que la Comisión la vuelva a chequear con la imagen del original; el
  cuadro marca esa celda y lo explica en una nota al pie (decisión del responsable, 2026-10-13;
  T-264). Una consulta para todos los resultados (`vision_citations.results_on_vision_pages`), no
  una por fila.
- Todo dato del Portal que el archivo muestra dice de qué página sale y cuándo se tomó (P3,
  constitución 1.3, ADR-0053; T-264), lo mismo que las pantallas (`portal/_fuente_dato.html`) pero con
  la dirección escrita, porque el archivo se imprime: la planilla, una nota al pie de los requisitos
  de cada oferta con los requisitos que citan cada página del Portal; el cuadro, una nota al pie del
  orden económico con la página de la que salen los precios y totales y de qué ofertas. Las páginas
  se leen con una consulta para todos los resultados y otra para los datos de todas las ofertas
  (`portal_sources`), no una por fila.
- El Excel lo escribe XlsxWriter y el PDF WeasyPrint, los dos dentro del equipo y sin recursos de
  red (el PDF reutiliza el generador de la matriz, que rechaza todo recurso externo).
- Cada exportación deja el hecho `eval_export` con qué se exportó y de qué evaluación (el pedido
  de la última evaluación de cada oferta), el nombre, el tamaño y la huella del archivo; una que
  falla lo deja en resultado `failed` (P6). Las fechas salen en hora local.

Los datos salen de `matrix_page`, que comprueba el rol de la Comisión (el operador y el evaluador
pueden exportar).
"""

import hashlib
import html
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

import xlsxwriter
from django.utils import timezone

from evaluon.assessment import (
    not_applicable,
    ordering,
    portal_sources,
    situation,
    vision_citations,
)
from evaluon.assessment.models import Decision, Outcome
from evaluon.assessment.services import discards as discards_service
from evaluon.assessment.services import external_stages
from evaluon.assessment.services import matrix as matrix_service
from evaluon.assessment.services import review
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.services import sheets
from evaluon.portal.models import PortalLine, PortalOfferData, PortalQuote
from evaluon.tenders.export import ExportFailed, html_to_pdf

PLANILLA = "planilla"
CUADRO = "cuadro"
XLSX = "xlsx"
PDF = "pdf"
DOCUMENTS = (PLANILLA, CUADRO)
FORMATS = (XLSX, PDF)
CONTENT_TYPES = {
    XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    PDF: "application/pdf",
}
EXPORT_OPERATION = "evaluon.assessment.services.export.export"

NOTICE = ("Propuesta de evaluación del sistema: la decisión es de la Comisión Evaluadora. "
          "Los resultados sin decisión figuran como propuestos.")
VERBS = {"confirmar": "Confirmado", "corregir": "Corregido", "rechazar": "Rechazado"}
DISCARD_STATES = {
    discards_service.PROPOSED: "Propuesto, sin decidir",
    discards_service.CONFIRMED: "Confirmado",
    discards_service.REJECTED: "Rechazado",
}
EXCERPT = 400
# El resultado se apoya en una cita de una página leída por visión (decisión del 2026-10-13). El
# aviso de la planilla nombra el documento y la página; el del cuadro es general.
_VISION_ONE = ("Se apoya en una página con dificultades de lectura, leída por visión{where}: "
               "conviene que la Comisión la vuelva a chequear con la imagen del original.")
_VISION_MANY = ("Se apoya en páginas con dificultades de lectura, leídas por visión{where}: "
                "conviene que la Comisión las vuelva a chequear con las imágenes del original.")
VISION_NOTE = _VISION_ONE.format(where="")
VISION_MARK = "(*)"


class ExportRefused(ValueError):
    """Pedido de exportación inválido (documento o formato desconocido)."""


# --- Textos ---------------------------------------------------------------------------------------


def when(moment):
    """Fecha y hora local: `07/10/2026 16:40`."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


def _number(value):
    """Un decimal en formato argentino, igual que la pantalla."""
    value = Decimal(value)
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    whole, _, decimals = f"{value.normalize():f}".partition(".")
    return f"{int(whole):,}".replace(",", ".") + "," + decimals


def _money(value, currency=""):
    if value is None:
        return "—"
    symbol = "$" if (currency or "").strip().upper() in ("", "ARS", "$") else currency.strip()
    return f"{symbol} {_number(value)}"


def _clean(text, limit=None):
    text = " ".join((text or "").split())
    if limit and len(text) > limit:
        return text[:limit].rstrip() + "…"
    return text


def _decision_line(decision):
    """«Corregido por X el 07/10/2026 16:40 · resultado: No cumple · motivo: …»."""
    if decision is None:
        return ""
    who = decision.user.username if decision.user_id else "—"
    line = f"{VERBS.get(decision.action, decision.get_action_display())} por {who} el " \
           f"{when(decision.at)}"
    if decision.outcome_after:
        line += f" · resultado: {Outcome(decision.outcome_after).label}"
    if decision.note:
        line += f" · motivo: {decision.note}"
    return line


def _discard_decision(decision):
    if decision is None:
        return ""
    who = decision.user.username if decision.user_id else "—"
    verb = "Confirmado" if decision.action == "confirmar" else "Rechazado"
    line = f"{verb} por {who} el {when(decision.at)}"
    if decision.note:
        line += f" · nota: {decision.note}"
    return line


def _scope(unit):
    return "Oferta completa" if unit.is_whole else f"Renglón {unit.line}"


# --- Los datos ------------------------------------------------------------------------------------


@dataclass
class RequirementRow:
    number: int
    category: str
    text: str
    proposed: str
    effective: str
    state: str
    basis: str
    decision: str


@dataclass
class DiscardLine:
    scope: str
    state: str
    grounds: str
    decision: str


@dataclass
class OfferSheet:
    offer: object
    evaluated: bool
    rows: list = field(default_factory=list)
    discards: list = field(default_factory=list)
    portal: list = field(default_factory=list)  # notas: de qué página del Portal sale cada dato
    request_id: int | None = None
    matrix_version: int | None = None


@dataclass
class Totals:
    position: str
    offer: str
    lines: str
    total: str
    situation: str


@dataclass
class ExportData:
    procedure: object
    version: object
    offers: list
    requirements: list
    sheets: list
    grid: list  # (requisito, qué exige, [texto por oferta])
    totals: list
    line_rows: list  # (renglón, cantidad, [(texto, descartada)])
    columns: int
    warnings: list
    generated: str
    grid_note: str = ""  # nota al pie del cuadro: qué significa la marca de visión, o vacía
    price_sources: list = field(default_factory=list)  # notas: de qué página salen los precios
    external_line: str = ""  # «Etapas fuera del equipo: …» (REQ-122, T-300)


def _last_decisions(results):
    found = {}
    if not results:
        return found
    for decision in (Decision.objects.filter(result__in=results,
                                             action__in=review.STATE_ACTIONS)
                     .select_related("user").order_by("at", "pk")):
        found[decision.result_id] = decision
    return found


def _rests_on_vision(cell, on_vision):
    """El resultado vigente del par se apoya en una cita de una página leída por visión."""
    return (cell.result is not None and cell.effective_outcome is not None
            and cell.result.pk in on_vision)


def _cell_text(cell, on_vision=frozenset()):
    """Qué dice el cuadro de un par: el resultado vigente, si falta decidirlo y, si se apoya en
    una página leída por visión, la marca (la nota al pie dice qué significa)."""
    if cell.result is None:
        return "Sin evaluar"
    if cell.effective_outcome is None:
        return "Propuesta rechazada, sin resultado"
    text = cell.effective_label
    if cell.state == matrix_service.PENDING:
        text += " (propuesto)"
    elif cell.state == matrix_service.CORRECTED:
        text += " (corregido)"
    if _rests_on_vision(cell, on_vision):
        text += f" {VISION_MARK}"
    return text


def _vision_note(places):
    """El aviso de la planilla para un resultado que se apoya en páginas leídas por visión: dice
    cuáles son (documento y página) para que la Comisión las encuentre y mire la imagen del original.
    `places`: `[(título del documento, página)]`."""
    where = "; ".join(f"{_clean(title)}, página {number}" if title else f"página {number}"
                      for title, number in places)
    template = _VISION_ONE if len(places) == 1 else _VISION_MANY
    return template.format(where=f" ({where})")


def _basis(result, on_vision):
    """El fundamento de la planilla: la explicación del sistema y, si el resultado se apoya en una
    cita de una página leída por visión, el aviso de que conviene chequearla y dónde está."""
    text = _clean(result.explanation)
    if result.pk in on_vision:
        text = f"{text} {_vision_note(on_vision[result.pk])}".strip()
    return text


def _portal_source(url, fetched_at):
    """De dónde sale un dato del Portal, como lo dicen las pantallas (`portal/_fuente_dato.html`):
    la página del Portal y cuándo se consultó. La dirección va escrita porque el archivo se imprime:
    «fuente: Portal · página del Portal: <dirección> · página consultada el 09/10/2026 14:30»."""
    return (f"fuente: Portal · página del Portal: {url} · "
            f"página consultada el {when(fetched_at)}")


def _portal_note(numbers, source):
    """La nota de la hoja de una oferta: qué requisitos tienen un resultado que cita esa página del
    Portal y de dónde sale."""
    if len(numbers) == 1:
        which = f"el requisito {numbers[0]}"
    else:
        which = f"los requisitos {', '.join(map(str, numbers[:-1]))} y {numbers[-1]}"
    return f"Datos del Portal citados en {which} · {_portal_source(source.url, source.fetched_at)}"


def collect(user, procedure_id, *, channel=Channel.SCREEN):
    """Reúne lo que exportan los cuatro archivos. Lanza `RoleRejected` sin rol de la Comisión y
    `Procedure.DoesNotExist` si no existe."""
    page = matrix_service.matrix_page(user, procedure_id, channel=channel)
    found = discards_service.units(page)
    results = [c.result for c in page.cells.values() if c.result is not None]
    decisions = _last_decisions(results)
    # Los resultados que citan una página leída por visión y las páginas del Portal que citan, cada
    # cosa de una vez para todos los resultados (T-264).
    on_vision = vision_citations.results_on_vision_pages([r.pk for r in results])
    portal = portal_sources.cited_pages([r.pk for r in results])
    texts = {r.pk: _clean(sheets.requirement_text(r), EXCERPT) for r in page.requirements}

    by_offer = {}
    for unit in found:
        by_offer.setdefault(unit.offer.pk, []).append(unit)

    offer_sheets = []
    for status in page.statuses:
        sheet = OfferSheet(offer=status.offer, evaluated=status.evaluated)
        if status.run is not None:
            sheet.request_id = status.run.request_id
            sheet.matrix_version = status.run.matrix_version.number
        cited = {}  # página del Portal -> números de los requisitos cuyo resultado la cita
        for requirement in page.requirements:
            cell = page.cells[(status.offer.pk, requirement.pk)]
            result = cell.result
            for source in portal.get(result.pk, ()) if result else ():
                cited.setdefault(source, []).append(requirement.number)
            sheet.rows.append(RequirementRow(
                number=requirement.number, category=requirement.get_category_display(),
                text=texts[requirement.pk],
                proposed=not_applicable.result_label(result) if result else "Sin evaluar",
                effective=(cell.effective_label if result and cell.effective_outcome else "—"),
                state=cell.state_label, basis=_basis(result, on_vision) if result else "",
                decision=_decision_line(decisions.get(result.pk)) if result else ""))
        sheet.portal = [_portal_note(numbers, source) for source, numbers in cited.items()]
        for unit in by_offer.get(status.offer.pk, []):
            grounds = " | ".join(
                f"Requisito {g.requirement.number}"
                + (f" · renglón {g.item}" if g.item is not None else "")
                + f": {_clean(g.requirement_text, 200)}"
                for g in unit.grounds)
            sheet.discards.append(DiscardLine(
                scope=_scope(unit), state=DISCARD_STATES[unit.state], grounds=grounds,
                decision=_discard_decision(unit.decision)))
        offer_sheets.append(sheet)

    grid = [(r, texts[r.pk],
             [_cell_text(page.cells[(o.pk, r.pk)], on_vision) for o in page.offers])
            for r in page.requirements]
    marked = any(_rests_on_vision(cell, on_vision) for cell in page.cells.values())
    totals, line_rows, warnings, price_sources = _economic(page, found, by_offer)
    return ExportData(
        procedure=page.procedure, version=page.version, offers=page.offers,
        requirements=page.requirements, sheets=offer_sheets, grid=grid, totals=totals,
        line_rows=line_rows, columns=len(page.offers), warnings=warnings,
        generated=when(timezone.now()),
        grid_note=f"{VISION_MARK} {VISION_NOTE}" if marked else "",
        price_sources=price_sources,
        external_line=external_stages.line([s.run for s in page.statuses if s.run is not None]))


def _economic(page, found, by_offer):
    """El orden económico con solo los descartes confirmados, como la pantalla. Devuelve los totales,
    el orden por renglón, los avisos y las notas de qué página del Portal da los precios y totales."""
    confirmed = discards_service.confirmed_discards(found)
    order = ordering.economic_order(page.procedure, page.offers, confirmed)
    # Con el ítem de origen y su página (la dirección y la fecha del Portal), sin la página bajada.
    data = {d.offer_id: d for d in (PortalOfferData.objects.filter(offer__in=page.offers)
                                    .select_related("item__page")
                                    .defer("item__page__content", "item__payload"))}
    quotes = {(q.offer_id, q.line.number): q for q in
              PortalQuote.objects.filter(offer__in=page.offers).select_related("line")}
    line_count = PortalLine.objects.filter(procedure=page.procedure).count()
    quoted = {}
    for (offer_id, _), quote in quotes.items():
        if quote.price is not None:
            quoted[offer_id] = quoted.get(offer_id, 0) + 1

    def lines_text(offer):
        return f"{quoted.get(offer.pk, 0)} de {line_count}" if line_count else "—"

    observed = situation.observations(page)
    totals = []
    for row in order.totals:
        mine = by_offer.get(row.offer.pk, [])
        notes = []
        for unit in mine:
            if unit.is_whole and unit.state == discards_service.PROPOSED:
                notes.append("Descarte propuesto, sin decidir")
            elif unit.is_whole and unit.state == discards_service.REJECTED:
                notes.append("Descarte rechazado por la Comisión")
            elif not unit.is_whole and unit.state == discards_service.CONFIRMED:
                notes.append(f"Renglón {unit.line} descartado")
            elif not unit.is_whole and unit.state == discards_service.PROPOSED:
                notes.append(f"Descarte propuesto del renglón {unit.line}, sin decidir")
        notes.extend(observed.get(row.offer.pk, ()))
        if row.position is None and row.note:
            notes.append(row.note)
        totals.append(Totals(
            position=str(row.position) if row.position is not None else "—",
            offer=f"{row.offer.number} · {row.offer.bidder}", lines=lines_text(row.offer),
            total=_money(row.amount, row.currency),
            situation=" · ".join(notes) if notes else "Sin observaciones"))
    for offer in page.offers:
        whole = next((u for u in by_offer.get(offer.pk, [])
                      if u.is_whole and u.state == discards_service.CONFIRMED), None)
        if whole is None:
            continue
        info = data.get(offer.pk)
        totals.append(Totals(
            position="—", offer=f"{offer.number} · {offer.bidder}", lines=lines_text(offer),
            total=_money(info.total, info.currency) if info else "—",
            situation=f"Descartada. {_discard_decision(whole.decision)}"))

    line_rows = []
    for line_order in order.lines:
        number = line_order.line.number
        description = _clean(line_order.line.description, 120)
        label = f"Renglón {number}"
        if description and description != label:
            label += f" · {description}"
        quantity = (_number(line_order.line.quantity)
                    if line_order.line.quantity is not None else "—")
        cells = []
        for item in line_order.rows:
            price = item.unit_price if item.unit_price is not None else item.amount
            cells.append((f"Of. {item.offer.number} · {_money(price, item.currency)}"
                          if price is not None else f"Of. {item.offer.number} · sin precio",
                          False))
        for offer in page.offers:
            dropped = any(u.state == discards_service.CONFIRMED and (u.is_whole or u.line == number)
                          for u in by_offer.get(offer.pk, []))
            if not dropped:
                continue
            quote = quotes.get((offer.pk, number))
            if quote is not None and quote.price is not None:
                info = data.get(offer.pk)
                cells.append((f"Of. {offer.number} · "
                              f"{_money(quote.price, info.currency if info else '')}", True))
            else:
                cells.append((f"Of. {offer.number} · sin precio", True))
        line_rows.append((label, quantity, cells))
    warnings = [w for w in [order.warning] + [lo.warning for lo in order.lines] if w]
    sources = []
    for group in portal_sources.price_sources(page.offers, data):
        origin = group["item"].page
        sources.append(f"Precios y totales de {group['offers']} · "
                       f"{_portal_source(origin.url, origin.fetched_at)}")
    return totals, line_rows, warnings, sources


# --- Excel ----------------------------------------------------------------------------------------


def _sheet_name(offer, used):
    base = re.sub(r"[\[\]:*?/\\]", "-", f"Oferta {offer.number}")[:31]
    name, n = base, 2
    while name.lower() in used:
        name = f"{base[:28]} {n}"
        n += 1
    used.add(name.lower())
    return name


def _formats(book):
    return {
        "title": book.add_format({"bold": True, "font_size": 14}),
        "notice": book.add_format({"italic": True, "font_color": "#7A4B00"}),
        "head": book.add_format({"bold": True, "bg_color": "#E8EEF4", "border": 1,
                                 "text_wrap": True, "valign": "top"}),
        "cell": book.add_format({"border": 1, "text_wrap": True, "valign": "top"}),
        "struck": book.add_format({"border": 1, "text_wrap": True, "valign": "top",
                                   "font_strikeout": True, "font_color": "#7A7A7A"}),
        "sub": book.add_format({"bold": True, "font_size": 12}),
    }


def _table(sheet, fmt, row, headers, body, widths=None):
    """Escribe una tabla y devuelve la fila siguiente. `body`: filas de textos."""
    for col, header in enumerate(headers):
        sheet.write(row, col, header, fmt["head"])
    for line in body:
        row += 1
        for col, value in enumerate(line):
            sheet.write(row, col, value, fmt["cell"])
    return row + 1


def _header(sheet, fmt, data, title):
    sheet.write(0, 0, title, fmt["title"])
    sheet.write(1, 0, f"Procedimiento {data.procedure.number} · matriz "
                      f"v{data.version.number if data.version else '—'} · exportado el "
                      f"{data.generated}")
    sheet.write(2, 0, NOTICE, fmt["notice"])
    sheet.write(3, 0, data.external_line)
    return 4


def build_xlsx(data, document):
    """El libro `.xlsx` (bytes) de la planilla o del cuadro."""
    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {"in_memory": True})
    fmt = _formats(book)
    if document == PLANILLA:
        used = set()
        for sheet_data in data.sheets:
            sheet = book.add_worksheet(_sheet_name(sheet_data.offer, used))
            row = _header(sheet, fmt, data,
                          f"Oferta {sheet_data.offer.number} · {sheet_data.offer.bidder}")
            if not sheet_data.evaluated:
                sheet.write(row, 0, "Esta oferta todavía no se evaluó.", fmt["cell"])
                row += 2
            headers = ["Requisito", "Clase", "Qué exige el pliego", "Resultado propuesto",
                       "Resultado vigente", "Estado", "Fundamento (explicación del sistema)",
                       "Decisión de la Comisión"]
            body = [[r.number, r.category, r.text, r.proposed, r.effective, r.state, r.basis,
                     r.decision] for r in sheet_data.rows]
            table_row = row
            row = _table(sheet, fmt, table_row, headers, body)
            sheet.freeze_panes(table_row + 1, 1)
            for note in sheet_data.portal:
                sheet.write(row, 0, note, fmt["notice"])
                row += 1
            sheet.write(row + 1, 0, "Descartes", fmt["sub"])
            if sheet_data.discards:
                _table(sheet, fmt, row + 2,
                       ["Alcance", "Estado", "Motivos", "Decisión de la Comisión"],
                       [[d.scope, d.state, d.grounds, d.decision] for d in sheet_data.discards])
            else:
                sheet.write(row + 2, 0, "Sin descartes propuestos.")
            for col, width in enumerate([12, 12, 50, 18, 18, 14, 60, 50]):
                sheet.set_column(col, col, width)
        if not data.sheets:
            sheet = book.add_worksheet("Planilla")
            row = _header(sheet, fmt, data, "Planilla por oferta")
            sheet.write(row, 0, "El procedimiento no tiene ofertas cargadas.")
    else:
        sheet = book.add_worksheet("Cuadro comparativo")
        row = _header(sheet, fmt, data, "Cuadro comparativo")
        headers = ["Requisito", "Clase", "Qué exige el pliego"] + [
            f"Oferta {o.number} · {o.bidder}" for o in data.offers]
        body = [[r.number, r.get_category_display(), text] + cells
                for r, text, cells in data.grid]
        table_row = row
        row = _table(sheet, fmt, table_row, headers, body)
        sheet.freeze_panes(table_row + 1, 3)
        if data.grid_note:
            sheet.write(row, 0, data.grid_note, fmt["notice"])
            row += 1
        for warning in data.warnings:
            sheet.write(row, 0, warning, fmt["notice"])
            row += 1
        sheet.write(row + 1, 0, "Orden económico total", fmt["sub"])
        row = _table(sheet, fmt, row + 2, ["Orden", "Oferta", "Renglones", "Total", "Situación"],
                     [[t.position, t.offer, t.lines, t.total, t.situation] for t in data.totals])
        sheet.write(row + 1, 0, "Orden económico por renglón (precio unitario, menor primero)",
                    fmt["sub"])
        head = ["Renglón", "Cantidad"] + [f"{n}.º" for n in range(1, data.columns + 1)]
        row += 2
        for col, header in enumerate(head):
            sheet.write(row, col, header, fmt["head"])
        for label, quantity, cells in data.line_rows:
            row += 1
            sheet.write(row, 0, label, fmt["cell"])
            sheet.write(row, 1, quantity, fmt["cell"])
            for col in range(data.columns):
                if col < len(cells):
                    text, dropped = cells[col]
                    sheet.write(row, 2 + col, text + (" (descartada)" if dropped else ""),
                                fmt["struck"] if dropped else fmt["cell"])
                else:
                    sheet.write(row, 2 + col, "—", fmt["cell"])
        row += 2
        for note in data.price_sources:
            sheet.write(row, 0, note, fmt["notice"])
            row += 1
        for col, width in enumerate([34, 14, 50] + [26] * data.columns):
            sheet.set_column(col, col, width)
    book.close()
    return buffer.getvalue()


# --- PDF ------------------------------------------------------------------------------------------

PDF_CSS = """
@page { size: A4 landscape; margin: 14mm 12mm; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 8.5pt; color: #1b1b1b; }
h1 { font-size: 14pt; margin: 0 0 2mm; } h2 { font-size: 11pt; margin: 5mm 0 2mm; }
.meta { color: #444; margin: 0 0 1mm; }
.aviso { font-style: italic; color: #7a4b00; margin: 0 0 3mm; overflow-wrap: anywhere; }
table { border-collapse: collapse; width: 100%; margin-bottom: 3mm; }
th, td { border: 0.4pt solid #888; padding: 1.2mm 1.6mm; vertical-align: top; text-align: left; }
th { background: #e8eef4; } tr { page-break-inside: avoid; }
.oferta { page-break-before: always; } .oferta:first-of-type { page-break-before: auto; }
.tachada { text-decoration: line-through; color: #666; }
"""


def _e(value):
    return html.escape(str(value), quote=True)


def _html_table(headers, rows, struck=()):
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = ""
    for index, row in enumerate(rows):
        klass = ' class="tachada"' if index in struck else ""
        body += f"<tr{klass}>" + "".join(f"<td>{_e(c)}</td>" for c in row) + "</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _page(title, data, body):
    version = data.version.number if data.version else "—"
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f"<title>{_e(title)}</title><style>{PDF_CSS}</style></head><body>"
            f"<h1>{_e(title)}</h1><p class=\"meta\">Procedimiento {_e(data.procedure.number)} · "
            f"matriz v{_e(version)} · exportado el {_e(data.generated)}</p>"
            f'<p class="meta">{_e(data.external_line)}</p>'
            f'<p class="aviso">{_e(NOTICE)}</p>{body}</body></html>')


def build_html(data, document):
    if document == PLANILLA:
        parts = []
        for sheet in data.sheets:
            part = (f'<section class="oferta"><h2>Oferta {_e(sheet.offer.number)} · '
                    f"{_e(sheet.offer.bidder)}</h2>")
            if not sheet.evaluated:
                part += "<p>Esta oferta todavía no se evaluó.</p>"
            part += _html_table(
                ["Req.", "Clase", "Qué exige el pliego", "Propuesto", "Vigente", "Estado",
                 "Fundamento", "Decisión de la Comisión"],
                [[r.number, r.category, r.text, r.proposed, r.effective, r.state, r.basis,
                  r.decision] for r in sheet.rows])
            part += "".join(f'<p class="aviso">{_e(note)}</p>' for note in sheet.portal)
            part += "<h2>Descartes</h2>"
            if sheet.discards:
                part += _html_table(["Alcance", "Estado", "Motivos", "Decisión"],
                                    [[d.scope, d.state, d.grounds, d.decision]
                                     for d in sheet.discards])
            else:
                part += "<p>Sin descartes propuestos.</p>"
            parts.append(part + "</section>")
        body = "".join(parts) or "<p>El procedimiento no tiene ofertas cargadas.</p>"
        return _page("Planilla por oferta", data, body)
    body = _html_table(
        ["Req.", "Clase", "Qué exige el pliego"]
        + [f"Oferta {o.number} · {o.bidder}" for o in data.offers],
        [[r.number, r.get_category_display(), text] + cells for r, text, cells in data.grid])
    if data.grid_note:
        body += f'<p class="aviso">{_e(data.grid_note)}</p>'
    body += "".join(f'<p class="aviso">{_e(w)}</p>' for w in data.warnings)
    body += "<h2>Orden económico total</h2>" + _html_table(
        ["Orden", "Oferta", "Renglones", "Total", "Situación"],
        [[t.position, t.offer, t.lines, t.total, t.situation] for t in data.totals],
        struck={i for i, t in enumerate(data.totals) if t.situation.startswith("Descartada")})
    line_body = []
    for label, quantity, cells in data.line_rows:
        texts = [t + (" (descartada)" if d else "") for t, d in cells]
        texts += ["—"] * (data.columns - len(texts))
        line_body.append([label, quantity] + texts)
    body += "<h2>Orden económico por renglón (precio unitario, menor primero)</h2>" + \
        _html_table(["Renglón", "Cant."] + [f"{n}.º" for n in range(1, data.columns + 1)],
                    line_body)
    body += "".join(f'<p class="aviso">{_e(note)}</p>' for note in data.price_sources)
    return _page("Cuadro comparativo", data, body)


# --- Entrega y registro ---------------------------------------------------------------------------


def file_name(data, document, fmt):
    number = re.sub(r"[^A-Za-z0-9._-]+", "-", str(data.procedure.number)).strip("-") \
        or "sin-numero"
    return f"{document}-{number}.{fmt}"


def export(user, procedure_id, document, fmt, *, channel=Channel.SCREEN):
    """Genera el archivo y deja el hecho `eval_export`. Devuelve `(bytes, nombre, tipo)`. Lanza
    `ExportRefused` ante un documento o formato desconocido, `RoleRejected` sin rol de la
    Comisión, `Procedure.DoesNotExist` y `ExportFailed` si el generador falla."""
    if document not in DOCUMENTS or fmt not in FORMATS:
        raise ExportRefused("Documento o formato desconocido.")
    data = collect(user, procedure_id, channel=channel)
    detail = {
        "procedure": data.procedure.pk, "document": document, "format": fmt,
        "matrix_version": data.version.number if data.version else None,
        "offers": [{"offer": s.offer.number, "request": s.request_id,
                    "matrix_version": s.matrix_version} for s in data.sheets],
        "offer_count": len(data.offers), "requirement_count": len(data.requirements),
        "sheets": len(data.sheets) if document == PLANILLA else 1,
    }
    try:
        if fmt == XLSX:
            content = build_xlsx(data, document)
        else:
            content, detail["pages"] = html_to_pdf(build_html(data, document))
    except ExportFailed as error:
        audit.record(EventType.EVAL_EXPORT, outcome=EventOutcome.FAILED, channel=channel,
                     user=user, detail={**detail, "reason": error.reason,
                                        "message": str(error)})
        raise
    except Exception as error:  # noqa: BLE001 - toda falla del generador se informa igual
        audit.record(EventType.EVAL_EXPORT, outcome=EventOutcome.FAILED, channel=channel,
                     user=user, detail={**detail, "reason": "render_failed",
                                        "message": str(error)})
        raise ExportFailed(f"No se pudo generar el archivo: {error}") from error
    name = file_name(data, document, fmt)
    audit.record(EventType.EVAL_EXPORT, outcome=EventOutcome.OK, channel=channel, user=user,
                 detail={**detail, "file_name": name, "size": len(content),
                         "sha256": hashlib.sha256(content).hexdigest()})
    return content, name, CONTENT_TYPES[fmt]
