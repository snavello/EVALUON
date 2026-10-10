"""Descarte propuesto y orden económico de la matriz de evaluación (REQ-059; plan 004,
"Decisiones del responsable", puntos 2 y 3; T-152).

Todo lo que sale de acá es una **propuesta**: la decisión es de la Comisión (P3). Nada se guarda.

- **Descarte propuesto** (`propose_discards`): una oferta se propone descartada cuando algún
  requisito de una clase de `DISCARD_CATEGORIES` tiene como resultado efectivo "no cumple". El
  resultado efectivo es el de la propuesta del sistema, o el que la persona corrigió; un
  resultado rechazado no cuenta. "No se encontró el documento" y "no determinado" **no**
  descartan: el primero es un documento por pedir y el segundo, una duda. Un "no cumple" de una
  fila técnica de un renglón descarta **solo ese renglón** (el dictamen del caso-00 desestima
  los renglones 5 y 6 de una oferta); cualquier otro "no cumple" descarta la oferta entera.
  Cada motivo lleva el requisito, su fundamento (la cita vigente del pliego y el texto de la
  oferta citado) y la consecuencia prevista en la matriz.
- **Orden económico** (`economic_order`) de lo no descartado: por precio total y, por cada
  renglón, por el total del renglón (precio por cantidad), con los datos del Portal
  (`portal_offer_data` y `portal_quote`, de la 012). Una oferta sin datos del Portal va al final
  y sin posición; con monedas distintas no se ordena y se avisa. Empatados comparten posición.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from evaluon.assessment.models import Citation, CitationKind, Outcome
from evaluon.offers.services import sheets
from evaluon.portal.models import PortalLine, PortalOfferData, PortalQuote
from evaluon.tenders.models import Consequence, RequirementClass, RequirementQuote

# El alcance del descarte propuesto: las clases de requisito cuyo "no cumple" descarta. El
# responsable decidió que también lo hace uno económico (por ejemplo, la garantía que el pliego
# manda desestimar si falta); para dejarlo afuera, quitar `ECONOMICO` de acá.
DISCARD_CATEGORIES = (
    RequirementClass.FORMAL,
    RequirementClass.TECNICO,
    RequirementClass.ECONOMICO,
)


# --- Descarte ----------------------------------------------------------------------------------


@dataclass
class Ground:
    """Un motivo de descarte: un requisito con "no cumple" y su fundamento."""

    requirement: object
    result: object
    outcome: str
    item: int | None
    requirement_text: str
    offer_quotes: list
    consequences: list


@dataclass
class Discard:
    """Lo que se propone descartar de una oferta: toda la oferta (`whole`) o renglones sueltos
    (`by_item`, número de renglón y sus motivos)."""

    offer: object
    whole: list = field(default_factory=list)
    by_item: dict = field(default_factory=dict)

    @property
    def is_whole(self):
        return bool(self.whole)

    @property
    def is_partial(self):
        return not self.whole and bool(self.by_item)

    @property
    def any(self):
        return bool(self.whole or self.by_item)

    @property
    def items(self):
        return sorted(self.by_item)


def _item_of(requirement):
    """El renglón de una fila técnica por renglón, o `None`."""
    if sheets.is_item_row(requirement):
        try:
            return int(requirement.items[0])
        except (TypeError, ValueError):
            return None
    return None


def _consequence_labels(rows):
    """La consecuencia prevista en la matriz: las elegidas, o todas las propuestas si todavía no
    se eligió ninguna (entonces se aclara). `rows` son las del requisito, por `pk`."""
    chosen = [c for c in rows if c.chosen]
    if chosen:
        return [c.get_consequence_type_display() for c in chosen]
    return [f"{c.get_consequence_type_display()} (sin elegir)" for c in rows]


@dataclass
class _Loaded:
    """Lo que los fundamentos de varias celdas piden a la base, cargado de una vez (T-223)."""

    citations: dict
    quotes: dict
    consequences: dict


def _load(cells):
    results = [c.result.pk for c in cells]
    requirements = {c.requirement.pk for c in cells}
    citations, quotes, consequences = {}, {}, {}
    for citation in Citation.objects.filter(result__in=results).order_by("order", "pk"):
        citations.setdefault(citation.result_id, []).append(citation)
    for quote in RequirementQuote.objects.filter(requirement__in=requirements).order_by("order"):
        quotes.setdefault(quote.requirement_id, []).append(quote)
    for row in Consequence.objects.filter(requirement__in=requirements).order_by("pk"):
        consequences.setdefault(row.requirement_id, []).append(row)
    return _Loaded(citations, quotes, consequences)


def _ground(cell, loaded):
    citations = loaded.citations.get(cell.result.pk, [])
    pliego = [c for c in citations if c.kind == CitationKind.PLIEGO]
    return Ground(
        requirement=cell.requirement, result=cell.result, outcome=cell.effective_outcome,
        item=_item_of(cell.requirement),
        requirement_text=(pliego[0].text if pliego else sheets.requirement_text(
            cell.requirement, loaded.quotes.get(cell.requirement.pk, []))),
        offer_quotes=[c for c in citations if c.kind == CitationKind.OFERTA],
        consequences=_consequence_labels(loaded.consequences.get(cell.requirement.pk, [])))


def _discarding(offers, requirements, cells):
    """Las celdas que son motivo de descarte, por oferta."""
    return {offer.pk: [cells[(offer.pk, requirement.pk)] for requirement in requirements
                       if (cells.get((offer.pk, requirement.pk)) is not None
                           and cells[(offer.pk, requirement.pk)].result is not None
                           and cells[(offer.pk, requirement.pk)].effective_outcome
                           == Outcome.NO_CUMPLE
                           and requirement.category in DISCARD_CATEGORIES)]
            for offer in offers}


def propose_discards(offers, requirements, cells):
    """`{id de la oferta: Discard}` para las ofertas con algún motivo de descarte. `cells` es
    `{(id de la oferta, id del requisito): celda}`; una celda trae `requirement`, `result` y
    `effective_outcome`."""
    found = {}
    mine = _discarding(offers, requirements, cells)
    every = [cell for group in mine.values() for cell in group]
    loaded = _load(every) if every else _Loaded({}, {}, {})
    for offer in offers:
        discard = Discard(offer=offer)
        for cell in mine[offer.pk]:
            ground = _ground(cell, loaded)
            if ground.item is None:
                discard.whole.append(ground)
            else:
                discard.by_item.setdefault(ground.item, []).append(ground)
        if discard.any:
            found[offer.pk] = discard
    return found


# --- Orden económico ---------------------------------------------------------------------------

NO_PORTAL_DATA = "sin datos del Portal"
NO_PRICE = "sin precio del Portal"


@dataclass
class OrderRow:
    """Una oferta en un orden. `position` es `None` si no se ordenó (con el motivo en `note`)."""

    offer: object
    amount: Decimal | None
    currency: str
    position: int | None
    note: str = ""
    quantity: Decimal | None = None
    unit_price: Decimal | None = None


@dataclass
class LineOrder:
    line: PortalLine
    rows: list
    warning: str = ""


@dataclass
class EconomicOrder:
    totals: list
    lines: list
    warning: str = ""


def _currency(value):
    return (value or "").strip().upper()


def _rank(rows):
    """Ordena `rows` (con `amount`) de menor a mayor y numera: iguales, misma posición."""
    rows.sort(key=lambda r: (r.amount, r.offer.number))
    position, previous = 0, None
    for index, row in enumerate(rows, start=1):
        if row.amount != previous:
            position, previous = index, row.amount
        row.position = position
    return rows


def _order(candidates, missing_note):
    """`candidates`: filas con `amount` o `None`. Devuelve `(filas, aviso)`: primero las
    ordenadas, al final las sin dato; si las monedas difieren, ninguna se ordena."""
    priced = [r for r in candidates if r.amount is not None]
    unpriced = [r for r in candidates if r.amount is None]
    for row in unpriced:
        row.note = row.note or missing_note
    currencies = {_currency(r.currency) for r in priced}
    warning = ""
    if len(currencies) > 1:
        warning = ("Las ofertas cotizan en monedas distintas ("
                   + ", ".join(sorted(c or "sin moneda" for c in currencies))
                   + "): no se ordenan.")
        for row in priced:
            row.note = "moneda distinta: sin orden"
        return priced + sorted(unpriced, key=lambda r: r.offer.number), warning
    return _rank(priced) + sorted(unpriced, key=lambda r: r.offer.number), warning


def economic_order(procedure, offers, discards):
    """El orden económico de las ofertas no descartadas del procedimiento. `discards` es lo que
    devuelve `propose_discards`."""
    standing = [o for o in offers if not (o.pk in discards and discards[o.pk].is_whole)]
    data = {d.offer_id: d for d in PortalOfferData.objects.filter(offer__in=standing)}
    total_rows = [OrderRow(offer=o, amount=data[o.pk].total if o.pk in data else None,
                           currency=data[o.pk].currency if o.pk in data else "", position=None,
                           note="" if o.pk in data and data[o.pk].total is not None
                           else NO_PORTAL_DATA)
                  for o in standing]
    totals, warning = _order(total_rows, NO_PORTAL_DATA)
    for row in totals:
        discard = discards.get(row.offer.pk)
        if discard is not None and discard.is_partial and not row.note:
            row.note = "con renglones descartados: " + ", ".join(str(i) for i in discard.items)

    quotes = {}
    for quote in PortalQuote.objects.filter(offer__in=standing).select_related("line"):
        quotes[(quote.offer_id, quote.line.number)] = quote
    lines = []
    for line in PortalLine.objects.filter(procedure=procedure).order_by("number"):
        rows = []
        for offer in standing:
            if offer.pk in discards and line.number in discards[offer.pk].by_item:
                continue
            quote = quotes.get((offer.pk, line.number))
            info = data.get(offer.pk)
            amount = None
            if quote is not None and quote.price is not None:
                amount = quote.price * (quote.quantity if quote.quantity is not None else 1)
            rows.append(OrderRow(
                offer=offer, amount=amount, currency=info.currency if info else "",
                position=None, quantity=quote.quantity if quote else None,
                unit_price=quote.price if quote else None))
        ordered, line_warning = _order(rows, NO_PRICE)
        lines.append(LineOrder(line=line, rows=ordered, warning=line_warning))
    return EconomicOrder(totals=totals, lines=lines, warning=warning)
