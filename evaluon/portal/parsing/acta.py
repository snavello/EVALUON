"""Lectura del acta de apertura del Portal (T-143; REQ-047; ADR-0032).

`parse_acta(bytes)` es una función pura. El acta trae una fila por oferente y por garantía:
un mismo proveedor aparece en dos filas cuando constituyó dos garantías (con montos
distintos, o con campos vacíos) y a veces con filas idénticas repetidas. Se agrupa por CUIT:
una oferta por CUIT, con la lista de sus garantías sin repetir y sin las filas vacías.
Lo que no se puede leer se informa en `issues`; no se inventa nada (P3).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from . import texto

_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_THOUSANDS = re.compile(r"\d{1,3}(\.\d{3})+")


def parse_amount(text):
    """Importe en formato argentino (`$ 1.234,50`, `195823,50`, `178376`) a `Decimal`, o
    `None` si no hay un número legible."""
    cleaned = re.sub(r"[^\d.,]", "", texto.normalize(text))
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif _THOUSANDS.fullmatch(cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_date(text):
    found = _DATE.search(text or "")
    if not found:
        return None
    day, month, year = (int(g) for g in found.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalize_cuit(text):
    """Los 11 dígitos del CUIT, o `""` si no son 11."""
    digits = re.sub(r"\D", "", text or "")
    return digits if len(digits) == 11 else ""


@dataclass
class ActaOffer:
    """Una oferta del acta, con las garantías de todas sus filas."""

    bidder: str
    cuit: str
    confirmed_on: date = None
    currency: str = ""
    total: Decimal = None
    guarantees: list = field(default_factory=list)  # [{"tipo", "forma", "monto"}]
    damaged: bool = False
    order: int = 0


@dataclass
class Acta:
    offers: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def parse_acta(data: bytes) -> Acta:
    soup = BeautifulSoup(texto.decode(data), "lxml")
    acta = Acta()
    table = soup.find("table", id=re.compile(r"gvOfertas$"))
    if table is None:
        acta.issues.append("no se encontró la tabla de ofertas del acta")
        return acta
    by_cuit = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 9:
            continue
        name = texto.clean(cells[0].get_text())
        cuit = normalize_cuit(texto.normalize(cells[1].get_text()))
        if not cuit:
            acta.issues.append(
                f"una fila del acta no trae un CUIT de 11 dígitos (oferente «{name.value}»)")
            continue
        total = parse_amount(cells[4].get_text())
        offer = by_cuit.get(cuit)
        if offer is None:
            offer = by_cuit[cuit] = ActaOffer(
                bidder=name.value, cuit=cuit, confirmed_on=parse_date(cells[2].get_text()),
                currency=texto.normalize(cells[3].get_text()), total=total,
                damaged=name.damaged, order=len(by_cuit) + 1)
            acta.offers.append(offer)
        elif total is not None and offer.total not in (None, total):
            acta.issues.append(
                f"el CUIT {cuit} figura con dos totales distintos en el acta; se toma el primero")
        guarantee = {"tipo": texto.normalize(cells[6].get_text()),
                     "forma": texto.normalize(cells[7].get_text()),
                     "monto": parse_amount(cells[8].get_text())}
        if not (guarantee["tipo"] or guarantee["forma"] or guarantee["monto"] is not None):
            continue  # fila sin garantía
        if guarantee not in offer.guarantees:  # fila repetida
            offer.guarantees.append(guarantee)
    for offer in acta.offers:
        if offer.total is None:
            acta.issues.append(f"el acta no trae un total legible para el CUIT {offer.cuit}")
        if offer.confirmed_on is None:
            acta.issues.append(
                f"el acta no trae la fecha de confirmación del CUIT {offer.cuit}")
    return acta
