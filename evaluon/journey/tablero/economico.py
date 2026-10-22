"""Orden económico del tablero (REQ-130, REQ-141; plan 017, «Orden económico»; ADR-0077, D;
T-314).

Muestra las ofertas de menor a mayor total, con la más baja y la más alta como indicadores y
cuánto se aparta cada una de la más baja. **No hay monto estimado** (decisión del responsable
del 2026-10-21): el Portal no lo publica y el sistema no lo tiene.

- El orden sale de `assessment.ordering.economic_order` sobre `PortalOfferData.total`: las
  empatadas comparten posición y con monedas distintas no se ordena (se avisa).
- Todo lo que el sistema no tiene se dice, nunca se inventa (REQ-141, P3): sin ofertas, el día
  de la apertura (del cronograma, si lo hay) y «Pendiente», sin una cifra; con ofertas pero sin
  ningún total, solo la cantidad y «Falta el total»; una oferta sin total, en un orden con
  otras, va al final sin posición y con «Falta el total».
- La diferencia se calcula con el total de la más baja; si esa es cero no existe y se deja
  vacía.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property

from evaluon.assessment import ordering
from evaluon.journey.tablero import charts
from evaluon.journey.temas import s1_datos

STATE_ORDERED = "ordered"
STATE_PENDING = "pending"
STATE_NO_TOTAL = "no_total"

PENDING_TEXT = "Pendiente"
NO_TOTAL_TEXT = "Falta el total"
LOW_TEXT = "La más baja"
HIGH_TEXT = "La más alta"

_PESOS = ("", "ARS", "$")
_TENTH = Decimal("0.1")


@dataclass
class EconomicRow:
    """Una oferta del orden. `position`, `diff_pct` y `amount` son `None` si no existen."""

    offer: object
    number: int
    name: str
    amount: Decimal | None
    currency: str
    amount_text: str
    position: int | None
    is_low: bool = False
    is_high: bool = False
    diff_pct: Decimal | None = None
    diff_text: str = ""
    note: str = ""


@dataclass
class EconomicView:
    """Lo que el tablero y el primer panel muestran del orden económico."""

    state: str
    rows: list = field(default_factory=list)
    count: int = 0
    opening_day: str | None = None
    missing: str = ""
    warning: str = ""
    low: EconomicRow | None = None
    high: EconomicRow | None = None

    @cached_property
    def chart(self):
        """El gráfico del orden: solo las ofertas con total y, con monedas distintas, ninguna
        (no se comparan)."""
        rows = [] if self.warning else [
            charts.LollipopRow(r.name, r.amount, r.amount_text, _chart_note(r),
                               low=r.is_low, high=r.is_high)
            for r in self.rows if r.amount is not None]
        return charts.Lollipop(uid="orden", title="Orden económico de las ofertas", rows=rows)


def _number(value):
    """Miles con punto y centavos con coma."""
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _money(value, currency=""):
    """«$ 1.234,50», o «USD 10,00» si la moneda no es el peso."""
    symbol = "$" if (currency or "").strip().upper() in _PESOS else currency.strip()
    return f"{symbol} {_number(value)}"


def _percent(value):
    return f"+{value:.1f}".replace(".", ",") + " %"


def _chart_note(row):
    if row.is_low:
        return LOW_TEXT
    sobre = f"{row.diff_text} sobre la más baja" if row.diff_text else ""
    if row.is_high:
        return f"{HIGH_TEXT} · {sobre}" if sobre else HIGH_TEXT
    return sobre


def opening_day(procedure):
    """El día de la apertura de ofertas (`dd/mm/aaaa`) según el cronograma del Portal, o `None`
    si el procedimiento no lo tiene."""
    opening = s1_datos._opening(s1_datos._schedule(s1_datos._portal_data(procedure)))
    if opening is None:
        return None
    moment, _ = s1_datos._stamp(opening[1])
    return f"{moment:%d/%m/%Y}" if moment else None


def economic_view(procedure, offers=None, discards=None):
    """El orden económico de `procedure`. `offers` son las ofertas a ordenar (por omisión todas
    las del procedimiento) y `discards` lo que devuelve `ordering.propose_discards` (por omisión
    ninguna se descarta)."""
    if offers is None:
        offers = list(procedure.offers.order_by("number"))
    order = ordering.economic_order(procedure, list(offers), discards or {}) if offers else None
    if order is None or not order.totals:
        return EconomicView(state=STATE_PENDING, opening_day=opening_day(procedure),
                            missing=PENDING_TEXT)
    count = len(order.totals)
    if all(r.amount is None for r in order.totals):
        return EconomicView(state=STATE_NO_TOTAL, count=count, missing=NO_TOTAL_TEXT)

    priced = [r.amount for r in order.totals if r.amount is not None]
    comparable = not order.warning
    lowest, highest = min(priced), max(priced)
    rows = []
    for r in order.totals:
        has_total = r.amount is not None
        row = EconomicRow(
            offer=r.offer, number=r.offer.number, name=f"Oferta {r.offer.number}",
            amount=r.amount, currency=r.currency,
            amount_text=_money(r.amount, r.currency) if has_total else "",
            position=r.position, note=r.note if has_total else NO_TOTAL_TEXT)
        if has_total and comparable:
            row.is_low = r.amount == lowest
            row.is_high = r.amount == highest and highest != lowest
            if lowest > 0:
                row.diff_pct = ((r.amount - lowest) / lowest * 100).quantize(
                    _TENTH, rounding=ROUND_HALF_UP)
            elif r.amount == lowest:
                row.diff_pct = Decimal("0.0")
            if row.diff_pct and not row.is_low:
                row.diff_text = _percent(row.diff_pct)
        rows.append(row)
    return EconomicView(
        state=STATE_ORDERED, rows=rows, count=count, warning=order.warning,
        low=next((r for r in rows if r.is_low), None),
        high=next((r for r in rows if r.is_high), None))
