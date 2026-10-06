"""Lectura del cuadro comparativo del Portal (T-143; REQ-047; ADR-0032).

`parse_cuadro(bytes)` es una función pura. Devuelve los oferentes con su total y, por
renglón, el precio unitario y la cantidad ofertada de cada oferente. Los oferentes se
identifican por CUIT (el nombre del cuadro es «Nombre - CUIT»). Un renglón con más de una
alternativa se lee por alternativa; si un oferente repite renglón y alternativa se informa.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from bs4 import BeautifulSoup

from . import texto
from .acta import normalize_cuit, parse_amount

_NAME = re.compile(r"^(.*?)\s*-\s*(\d[\d-]*)\s*$")


@dataclass
class CuadroBidder:
    bidder: str
    cuit: str
    total: Decimal = None
    damaged: bool = False
    order: int = 0


@dataclass
class Cuadro:
    bidders: list = field(default_factory=list)
    # [{"renglon": int, "alternativa": int, "cuit": str, "precio": Decimal,
    #   "cantidad": Decimal, "total": Decimal}]
    quotes: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def _split_name(text):
    cleaned = texto.clean(text)
    found = _NAME.match(cleaned.value)
    if not found:
        return cleaned.value, "", cleaned.damaged
    return found.group(1).strip(), normalize_cuit(found.group(2)), cleaned.damaged


def _text(soup, element_id):
    span = soup.find("span", id=element_id)
    return texto.normalize(span.get_text()) if span is not None else ""


def parse_cuadro(data: bytes) -> Cuadro:
    soup = BeautifulSoup(texto.decode(data), "lxml")
    cuadro = Cuadro()
    for span in soup.find_all("span", id=re.compile(r"rptProveedores_ctl\d+_lblNombreProveedor$")):
        name, cuit, damaged = _split_name(span.get_text())
        if not cuit:
            cuadro.issues.append(f"un oferente del cuadro no trae un CUIT de 11 dígitos: «{name}»")
            continue
        total = parse_amount(_text(soup, span["id"].replace("lblNombreProveedor", "lblTotal"))
                             .replace("Total:", ""))
        cuadro.bidders.append(CuadroBidder(name, cuit, total, damaged, len(cuadro.bidders) + 1))
    if not cuadro.bidders:
        cuadro.issues.append("no se encontraron oferentes en el cuadro comparativo")
    seen = set()
    for number_span in soup.find_all("span", id=re.compile(r"rptLineas_ctl\d+_lblRenglon$")):
        prefix = number_span["id"][: -len("lblRenglon")]
        raw = texto.normalize(number_span.get_text())
        if not raw.isdigit():
            cuadro.issues.append(f"un renglón del cuadro no trae un número legible: «{raw}»")
            continue
        number = int(raw)
        option = _text(soup, prefix + "lblOpcion")
        alternative = int(option) if option.isdigit() else 1
        for name_span in soup.find_all(
                "span", id=re.compile(re.escape(prefix) + r"rptLineasOfertas_ctl\d+_lblNombre$")):
            _, cuit, _ = _split_name(name_span.get_text())
            base = name_span["id"][: -len("lblNombre")]
            price = parse_amount(_text(soup, base + "txtPrecioUnitario"))
            quantity = parse_amount(_text(soup, base + "lblCantidadOfertada"))
            line_total = parse_amount(_text(soup, base + "txtTotalPorRenglon"))
            where = f"renglón {number}, CUIT {cuit or '?'}"
            if not cuit:
                cuadro.issues.append(f"{where}: el oferente no trae CUIT")
                continue
            if price is None or quantity is None:
                cuadro.issues.append(f"{where}: no se pudo leer el precio o la cantidad")
                continue
            if (number, alternative, cuit) in seen:
                cuadro.issues.append(f"{where}: figura dos veces; se toma la primera")
                continue
            seen.add((number, alternative, cuit))
            cuadro.quotes.append({"renglon": number, "alternativa": alternative, "cuit": cuit,
                                  "precio": price, "cantidad": quantity, "total": line_total})
    return cuadro
