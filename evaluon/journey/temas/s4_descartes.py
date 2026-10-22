"""Tema s4_descartes: resultado por oferta, orden económico y descartes propuestos de la sección
«Evaluación y dictamen» (REQ-091; plan 014, T-210).

Dos bloques, en el orden de la maqueta aprobada:

- **Resultado por oferta y orden económico** (`#s4-resultado`): cuántos requisitos cumple cada
  oferta, el orden económico por renglón y el total. Sale de `ordering.economic_order` (no se
  cambia), alimentado solo con los descartes que la Comisión CONFIRMÓ: una oferta o un renglón
  con descarte confirmado figura como «descartada», no entra en el orden; uno propuesto sin decidir
  sigue ordenándose y se marca como propuesto.
- **Descartes propuestos** (`#s4-descartes`): cada descarte de `propose_discards` con sus motivos y
  fundamentos, su estado y, si la Comisión decidió, quién y cuándo. El evaluador lo confirma o lo
  rechaza (nota opcional) con `assessment.services.discards`; el operador ve el estado y no los
  botones. El sistema propone; no decide nada (P3).

Los descartes sin decidir son pendientes de la sección (REQ-097), con su enlace «Resolver» a la
fila. La etapa `matriz_evaluacion` los cuenta como pendientes (no como sugerencias) y este tema
los lista uno por uno. Las acciones vuelven a la pestaña con el mensaje de lo hecho.

El fundamento de cada motivo se ve completo (P3, T-264): la cita de la oferta, con la marca «leída
por visión» si su página se leyó por visión, y el dato del Portal en que se apoya, con su enlace y la
fecha en que se tomó; y el orden económico dice de qué página del Portal salen los precios. Las
citas de todos los motivos se traen juntas, con su documento (`journey/basis.py`): una consulta por
pantalla y no una por motivo (T-223).
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.http import Http404
from django.urls import path
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.assessment import not_applicable, ordering, portal_sources, situation
from evaluon.assessment.models import DiscardAction, Outcome
from evaluon.assessment.services import discards as service
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.journey import basis, memo
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.tablero.tiles import Tile, detail_id
from evaluon.journey.temas import s1_datos
from evaluon.journey.temas import s4_propuesta_acciones as base
from evaluon.journey.temas.s4_propuesta import _excerpt, when
from evaluon.portal.models import PortalLine, PortalOfferData, PortalQuote
from evaluon.tenders.models import Procedure

KEY = "s4_descartes"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_descartes.html"
CHANNEL = Channel.SCREEN

STATE_VIEW = {
    service.PROPOSED: ("nodet", "Propuesto, sin decidir"),
    service.CONFIRMED: ("cumple", "Confirmado"),
    service.REJECTED: ("nocumple", "Rechazado"),
}
VERBS = {service.CONFIRMED: "Confirmado", service.REJECTED: "Rechazado"}
DONE = {DiscardAction.CONFIRMAR: "Se confirmó", DiscardAction.RECHAZAR: "Se rechazó"}


@dataclass
class GroundView:
    """Un motivo de descarte: el requisito, lo que dice la oferta y la consecuencia prevista."""

    title: str
    requirement: str
    offer_text: str
    consequences: str
    url: str
    quote: object = None  # la cita de la oferta que se muestra
    by_vision: bool = False  # su página se leyó por visión (P3, ADR-0041)
    portal: list = field(default_factory=list)  # los datos del Portal en que se apoya


@dataclass
class DiscardRow:
    anchor: str
    title: str
    bidder: str
    grounds: list
    icon: str
    state_name: str
    decided: str  # «Confirmado por X el 07/10/2026 16:40 · nota: …»
    offer_id: int
    line: int | None
    can_decide: bool
    state: str


@dataclass
class TotalRow:
    position: str
    label: str
    lines: str
    total: str
    situation: str
    struck: bool = False


@dataclass
class LineRow:
    label: str
    quantity: str
    cells: list = field(default_factory=list)  # (texto, descartada)
    pad: object = ()  # celdas vacías para completar las columnas


# --- Textos y números -----------------------------------------------------------------------------


def _number(value):
    return s1_datos._number(Decimal(value))


def _money(value, currency=""):
    if value is None:
        return "—"
    symbol = "$" if (currency or "").strip().upper() in ("", "ARS", "$") else currency.strip()
    return f"{symbol} {_number(value)}"


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


def _anchor(unit):
    return f"desc-{unit.offer.number}" + ("" if unit.is_whole else f"-{unit.line}")


def _title(unit):
    if unit.is_whole:
        return f"Oferta {unit.offer.number} completa"
    return f"Oferta {unit.offer.number} · renglón {unit.line}"


def _scope(unit):
    return "completa" if unit.is_whole else f"renglón {unit.line}"


def _grounds(unit, procedure, cited, portal):
    """Los motivos del descarte. `cited` y `portal` son las citas de la oferta y los datos del Portal
    de cada resultado (`basis.of_results`), traídos de una vez para todos los motivos."""
    views = []
    for ground in unit.grounds:
        title = f"Requisito {ground.requirement.number}"
        if ground.item is not None:
            title += f" · renglón {ground.item}"
        quotes = cited.get(ground.result.pk, [])
        quote = quotes[0] if quotes else None
        offer_text = ""
        if quote is not None:
            where = quote.document.title if quote.document_id else ""
            page = f" · página {quote.page}" if quote.page else ""
            offer_text = f"«{_excerpt(quote.text)}» ({where}{page})"
        views.append(GroundView(
            title=title, requirement=_excerpt(ground.requirement_text), offer_text=offer_text,
            consequences=", ".join(ground.consequences),
            url=base.pair_url(procedure, unit.offer.pk, ground.requirement.pk),
            quote=quote, by_vision=quote is not None and quote.by_vision,
            portal=portal.get(ground.result.pk, [])))
    return views


def _decided(decision):
    if decision is None:
        return ""
    who = decision.user.username if decision.user_id else "—"
    verb = VERBS[service._STATES[decision.action]]
    line = f"{verb} por {who} el {when(decision.at)}"
    if decision.note:
        line += f" · nota: {decision.note}"
    return line


# --- Estado y pendientes --------------------------------------------------------------------------

# Por qué importa cada descarte por decidir (REQ-129, T-328). Dice lo que el sistema hace y no
# hace: no inventa nada del caso.
WHY_DISCARD = ("El sistema lo propone con su fundamento; solo vale cuando la Comisión lo confirma "
               "o lo rechaza, y mientras tanto la oferta sigue en el orden económico.")


def status(user, procedure):
    """Lista cada descarte sin decidir como pendiente; la cuenta la hace la etapa
    `matriz_evaluacion`."""
    page = memo.matrix_page(user, procedure.pk, channel=CHANNEL)
    found = service.units(page)
    undecided = [u for u in found if u.state == service.PROPOSED]
    items = tuple(
        Item(f"Descarte propuesto por decidir: oferta {u.offer.number} ({_scope(u)})",
             f"{base.tab_url(procedure)}#{_anchor(u)}", 1, "Resolver", kind="descarte",
             noun="descartes propuestos por decidir", why=WHY_DISCARD,
             group_url=f"{base.tab_url(procedure)}#s4-descartes") for u in undecided)
    return TemaStatus(pending_items=items)


# --- Resultado por oferta y orden económico -------------------------------------------------------


def _results(page):
    rows = []
    for status_ in page.statuses:
        if not status_.evaluated:
            rows.append({"offer": status_.offer, "evaluated": False})
            continue
        outcomes = status_.by_outcome
        rows.append({
            "offer": status_.offer, "evaluated": True,
            "meets": outcomes.get(Outcome.CUMPLE, 0),
            "fails": outcomes.get(Outcome.NO_CUMPLE, 0) + outcomes.get(Outcome.SIN_DOCUMENTO, 0),
            "undetermined": outcomes.get(Outcome.NO_DETERMINADO, 0),
            # Los requisitos que no aplican a la oferta (forma de garantía no elegida) no son
            # «cumple» ni «no determinado»: se informan aparte (T-240).
            "not_applicable": outcomes.get(not_applicable.KEY, 0),
            "pending": status_.by_state.get(matrix_service.PENDING, 0),
            "confirmed": (status_.by_state.get(matrix_service.CONFIRMED, 0)
                          + status_.by_state.get(matrix_service.CORRECTED, 0)),
        })
    return rows


def _situation(units_of, questions, row_note, observed=()):
    """Qué pasa con una oferta que sigue en el orden: sus descartes y sus preguntas abiertas."""
    parts = []
    for unit in units_of:
        if unit.is_whole:
            if unit.state == service.PROPOSED:
                parts.append("Descarte propuesto, sin decidir")
            elif unit.state == service.REJECTED:
                parts.append("Descarte rechazado por la Comisión")
        elif unit.state == service.CONFIRMED:
            parts.append(f"Renglón {unit.line} descartado")
        elif unit.state == service.PROPOSED:
            parts.append(f"Descarte propuesto del renglón {unit.line}, sin decidir")
    parts.extend(observed)  # sin evaluar, no se encontró el documento, subsanación (T-231, E-9)
    if questions:
        parts.append(_plural(questions, "pregunta abierta", "preguntas abiertas"))
    if row_note:
        parts.append(row_note)
    return " · ".join(parts) if parts else "Sin observaciones"


def _economic(page, found):
    """El orden económico con solo los descartes confirmados. Devuelve el total, el orden por
    renglón y los avisos."""
    confirmed = service.confirmed_discards(found)
    order = ordering.economic_order(page.procedure, page.offers, confirmed)
    by_offer = {}
    for unit in found:
        by_offer.setdefault(unit.offer.pk, []).append(unit)
    questions = {s.offer.pk: len(s.open_questions) for s in page.statuses}
    observed = situation.observations(page)
    # Con el ítem de origen y su página (el enlace y la fecha del Portal), sin la página bajada.
    data = {d.offer_id: d for d in (PortalOfferData.objects.filter(offer__in=page.offers)
                                    .select_related("item__page", "item__proposal")
                                    .defer("item__page__content", "item__payload",
                                           "item__proposal__anomalies"))}
    quotes = {(q.offer_id, q.line.number): q for q in
              PortalQuote.objects.filter(offer__in=page.offers).select_related("line")}
    line_count = PortalLine.objects.filter(procedure=page.procedure).count()
    quoted = {}
    for (offer_id, _), quote in quotes.items():
        if quote.price is not None:
            quoted[offer_id] = quoted.get(offer_id, 0) + 1

    def lines_text(offer):
        return f"{quoted.get(offer.pk, 0)} de {line_count}" if line_count else "—"

    totals = []
    for row in order.totals:
        mine = by_offer.get(row.offer.pk, [])
        note = row.note if row.position is None else ""
        struck = any(u.is_whole and u.state == service.PROPOSED for u in mine)
        totals.append(TotalRow(
            position=str(row.position) if row.position is not None else "—",
            label=f"{row.offer.number} · {row.offer.bidder}", lines=lines_text(row.offer),
            total=_money(row.amount, row.currency),
            situation=_situation(mine, questions.get(row.offer.pk, 0), note,
                                 observed.get(row.offer.pk, ())), struck=struck))
    for offer in page.offers:
        whole = next((u for u in by_offer.get(offer.pk, [])
                      if u.is_whole and u.state == service.CONFIRMED), None)
        if whole is None:
            continue
        info = data.get(offer.pk)
        totals.append(TotalRow(
            position="—", label=f"{offer.number} · {offer.bidder}", lines=lines_text(offer),
            total=_money(info.total, info.currency) if info else "—",
            situation=f"Descartada. {_decided(whole.decision)}", struck=True))

    lines = []
    for line_order in order.lines:
        number = line_order.line.number
        description = _excerpt(line_order.line.description)
        label = f"Renglón {number}"
        if description and description != label:
            label += f" · {description}"
        row = LineRow(label=label,
                      quantity=(_number(line_order.line.quantity)
                                if line_order.line.quantity is not None else "—"))
        for item in line_order.rows:
            price = item.unit_price if item.unit_price is not None else item.amount
            text = (f"Of. {item.offer.number} · {_money(price, item.currency)}"
                    if price is not None else f"Of. {item.offer.number} · sin precio")
            row.cells.append((text, False))
        for offer in page.offers:
            mine = by_offer.get(offer.pk, [])
            dropped = any(u.state == service.CONFIRMED and (u.is_whole or u.line == number)
                          for u in mine)
            if not dropped:
                continue
            quote = quotes.get((offer.pk, number))
            if quote is not None and quote.price is not None:
                info = data.get(offer.pk)
                row.cells.append((f"Of. {offer.number} · "
                                  f"{_money(quote.price, info.currency if info else '')}", True))
            else:
                row.cells.append((f"Of. {offer.number} · sin precio", True))
        row.pad = range(max(0, len(page.offers) - len(row.cells)))
        lines.append(row)
    warnings = [w for w in [order.warning] + [lo.warning for lo in order.lines] if w]
    return {"totals": totals, "lines": lines, "columns": range(1, len(page.offers) + 1),
            "warnings": warnings,
            "price_sources": portal_sources.price_sources(page.offers, data)}


# --- Los descartes --------------------------------------------------------------------------------


def _rows(found, procedure, is_evaluator):
    cited, portal = basis.of_results({ground.result.pk for unit in found
                                      for ground in unit.grounds})
    rows = []
    for unit in found:
        icon, name = STATE_VIEW[unit.state]
        rows.append(DiscardRow(
            anchor=_anchor(unit), title=_title(unit), bidder=unit.offer.bidder,
            grounds=_grounds(unit, procedure, cited, portal), icon=icon, state_name=name,
            decided=_decided(unit.decision), offer_id=unit.offer.pk, line=unit.line,
            can_decide=is_evaluator and unit.state == service.PROPOSED, state=unit.state))
    return rows


AVISO = "s4-descartes-aviso"


def _back(procedure, text, ok=True):
    """Vuelve al detalle de los descartes, donde se dibuja el aviso (T-335)."""
    return base.back(procedure, text, ok, anchor=f"#{AVISO}")


def context(user, procedure, request):
    aviso = base.unpack(request.GET.get("aviso")) if request is not None else None
    page = memo.matrix_page(user, procedure.pk, channel=CHANNEL)
    evaluated = any(s.evaluated for s in page.statuses)
    is_evaluator = getattr(user, "commission_role", "") == CommissionRole.EVALUATOR
    empty = {"pid": procedure.pk, "evaluated": evaluated, "is_evaluator": is_evaluator,
             "requirements": len(page.requirements), "results": [], "rows": [],
             "to_decide": 0, "decided": 0, "totals": [], "lines": [], "columns": (),
             "warnings": [], "price_sources": [], "aviso": aviso, "aviso_id": AVISO}
    if not evaluated:
        return empty
    found = service.units(page)
    rows = _rows(found, procedure, is_evaluator)
    to_decide = sum(1 for r in rows if r.state == service.PROPOSED)
    return {**empty, "results": _results(page), "rows": rows, "to_decide": to_decide,
            "decided": len(rows) - to_decide, **_economic(page, found)}


# --- Mosaico del tablero (plan 017, T-328) ---------------------------------------------------------

SHOWN_TITLES = 3


def tiles(user, procedure, ctx):
    """El mosaico «Descartes propuestos»: los que el sistema propuso y la Comisión todavía no
    decidió, con cuáles son y cuántos ya se decidieron. Sin evaluación dice «Pendiente»; con una
    evaluación que no propone ninguno, el cero es un dato (REQ-141). Confirmar o rechazar se hace
    en el detalle, nunca desde el mosaico (P6)."""
    ctx = ctx if ctx is not None else context(user, procedure, None)
    detail = detail_id(KEY)
    if not ctx["evaluated"]:
        return [Tile(key="descartes", title="Descartes propuestos", detail=detail,
                     sub="Todavía no hay una evaluación", missing="Pendiente")]
    rows = ctx["rows"]
    waiting = [r for r in rows if r.state == service.PROPOSED]
    parts = []
    if waiting:
        shown = [r.title for r in waiting[:SHOWN_TITLES]]
        text = "; ".join(shown)
        if len(waiting) > SHOWN_TITLES:
            text += f" y {len(waiting) - SHOWN_TITLES} más"
        parts.append(text)
    for state, one, many in ((service.CONFIRMED, "confirmado", "confirmados"),
                             (service.REJECTED, "rechazado", "rechazados")):
        count = sum(1 for r in rows if r.state == state)
        if count:
            parts.append(f"{count} {one if count == 1 else many}")
    if not rows:
        parts.append("El sistema no propuso descartes")
    return [Tile(key="descartes", title="Descartes propuestos", detail=detail,
                 big=len(waiting), unit="por decidir", sub=" · ".join(parts))]


# --- Acciones -------------------------------------------------------------------------------------


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


@require_POST
def decide(request, procedure_id):
    """Confirma o rechaza un descarte con `discards.decide`; queda quién y cuándo. Sin el rol de
    evaluador, «acceso denegado» (403) con el rechazo registrado."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    post = request.POST
    offer_id = _int(post.get("offer"))
    line = _int(post.get("line")) if post.get("line", "") != "" else None
    try:
        done = service.decide(request.user, procedure.pk, offer_id, line,
                              post.get("action", ""), note=post.get("note", ""),
                              channel=CHANNEL)
    except service.DiscardRefused as error:
        return _back(procedure, str(error), ok=False)
    scope = "completa" if line is None else f"renglón {line}"
    return _back(procedure, f"{DONE[done.decision.action]} el descarte de la oferta "
                                f"{done.decision.offer.number} ({scope}). "
                                "Quedó registrado quién y cuándo.")


urlpatterns = [
    path("evaluacion/descarte/decidir/", decide, name="s4_decidir_descarte"),
]
