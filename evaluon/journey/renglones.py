"""El renglón técnico por su bien (REQ-082, plan 017, T-338 y T-339): la tabla de renglones del
pliego, la fila de cada renglón y su título («Renglón 1 · Alimento … · 2700 kilos»). Lo usan la
matriz del Pliego (`s2_matriz`) y la propuesta de la Evaluación (`s4_propuesta`), para que un
renglón se llame igual en las dos. Solo lee; no decide nada (P3)."""

import re

from evaluon.journey import memo
from evaluon.portal.models import PortalLine

_TABLE_HEADER = re.compile(r"r[eé]ngl|[ií]tem", re.IGNORECASE)
_TABLE_ROW = re.compile(r"^\s*(\d+)\s+(\S.*?)\s*$")
_ROW_QUANTITY = re.compile(
    r"^(?P<what>.*?)[\s.]+(?P<qty>\d[\d.,]*)\s+(?P<unit>[^\W\d_][\w.]*)\.?$")


def table_rows(text):
    """`{número de renglón: su fila}` de una cita que es la tabla de renglones del pliego: un
    encabezado que nombra el renglón o el ítem y, debajo, una fila por renglón que empieza con su
    número. Una cita que no es una tabla de al menos dos renglones da `{}`."""
    lines = text.split("\n")
    if len(lines) < 3 or not _TABLE_HEADER.search(lines[0]):
        return {}
    rows = {}
    for line in lines[1:]:
        found = _TABLE_ROW.match(line)
        if found:
            rows.setdefault(int(found.group(1)), line.strip())
    return rows if len(rows) >= 2 else {}


def _readable(text):
    """El bien como se lee: lo que el pliego escribe todo en mayúsculas, en minúsculas, con el
    nombre y la marca después de un guion largo («Alimento para perros — Royal Canin»)."""
    text = text.strip().rstrip(".").strip()
    if not text.isupper():
        return text
    head, *rest = re.split(r"\s+-\s+", text)
    rest = [re.sub(r"^MARCA\s+", "", part).title() for part in rest]
    words = [w if any(c.isdigit() for c in w) else w.lower() for w in head.split()]
    head = " ".join(words)
    head = head[:1].upper() + head[1:]
    return f"{head} — {' '.join(rest)}" if rest else head


def _row_parts(line):
    """`(bien, cantidad y unidad)` de la fila de la tabla: las celdas, si vienen separadas con
    tabulaciones (`tenders/tables.py`), o lo que sigue al número."""
    if "\t" in line:
        cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
        return (cells[1] if len(cells) > 1 else ""), " ".join(cells[2:])
    rest = _TABLE_ROW.match(line).group(2)
    found = _ROW_QUANTITY.match(rest)
    if found:
        return found.group("what"), f"{found.group('qty')} {found.group('unit')}"
    return rest, ""


def _quantity_of(line):
    """La cantidad y la unidad de un renglón del procedimiento."""
    if line.quantity is None:
        return ""
    value = line.quantity
    shown = (f"{int(value)}" if value == value.to_integral_value()
             else f"{value.normalize():f}".replace(".", ","))
    return f"{shown} {line.unit}".strip()


def _is_label(what, number):
    """La descripción que es solo «Renglón N» (el Portal no dio el bien): no dice qué se compra y
    repetirla daría «Renglón 1 · Renglón 1»."""
    return re.fullmatch(rf"r[eé]ngl[oó]n\s*(n[.°º]*\s*)?{number}\.?", what.strip(),
                        re.IGNORECASE) is not None


def lines_of(procedure_id):
    """`{número: PortalLine}` de los renglones del procedimiento: una consulta por pedido (T-338)."""
    return memo.once(("renglones", procedure_id), lambda: {
        line.number: line for line in PortalLine.objects.filter(procedure_id=procedure_id)})


def renglon_text(number, tables, lines, fallback):
    """El renglón por su bien: «Renglón 1 · Alimento … · 2700 kilos». Sale de su fila en la tabla de
    renglones citada (`tables`: los textos de las citas) y, si no está, del renglón del
    procedimiento (`lines`: `{número: PortalLine}`). Si no se sabe, `fallback`: el texto de
    siempre (no se inventa); con `fallback` en `None`, la falta se informa con `None`."""
    what, quantity = "", ""
    for text in tables:
        row = table_rows(text).get(number)
        if row is not None:
            what, quantity = _row_parts(row)
            if what:
                break
    if not what:
        line = lines.get(number)
        what, quantity = (line.description, _quantity_of(line)) if line is not None else ("", "")
    if not what.strip() or _is_label(what, number):
        return None if fallback is None else f"Renglón {number} · {fallback}"
    quantity = quantity.lower() if quantity.isupper() else quantity
    text = f"Renglón {number} · {_readable(what)}"
    return f"{text} · {quantity}" if quantity else text
