"""Zonas de tabla de cada página de un PDF del pliego, con sus celdas (plan 003, "Carga y
lectura" y "Tramos"; ADR-0019; T-070; T-259).

La lectura de la 001 (`evaluon/norms/reading/`) entrega líneas de texto, sin saber si
una línea está dentro de una tabla. Una tabla leída línea por línea mezcla las
condiciones de sus celdas (el detalle de renglones y cantidades, las multas), así que la
partición en tramos (`segmenting.py`) junta las líneas que caen dentro de una zona de
tabla en un tramo `tabla`, pendiente de revisión (REQ-028).

Las zonas se buscan con pdfplumber, con su estrategia por omisión (bordes dibujados), sin
tocar la lectura de la 001. Cada zona es un rectángulo en las unidades de la página, con
el origen arriba a la izquierda, como las posiciones de las líneas de la lectura:

    {"page": 5, "x0": 112.0, "top": 385.0, "x1": 519.0, "bottom": 705.0}

**Celdas (T-259).** `read_tables` suma a cada zona sus filas con el texto de cada celda
(`rows`, `None` en la celda que cubre otra unida), como las arma pdfplumber: la tabla queda
guardada con sus celdas. `with_cells` escribe en la lectura cada tabla de dos filas o más como
**una sola línea**: sus filas separadas por un salto de línea y sus celdas por una tabulación
(texto separado por tabulaciones). Así la marca de una celda queda con su fila: la cláusula
17.1 del caso-00, que se leía «Total Por Renglón X Por grupo de Renglones», queda «Total»,
«Por Renglón<TAB>X» y «Por grupo de Renglones», una por renglón (con la tabulación de la
celda vacía al final). Se eligió la tabulación y no « | » porque es un espacio en blanco: la
cita que el modelo copia con un espacio entre dos celdas se sigue ubicando en el tramo
(`quotes.locate` cuenta toda secuencia de espacios en blanco por uno), y la pantalla la
muestra como un espacio. La línea reemplaza a las que la partición ponía en la zona (la misma
regla que `segmenting._zone_of`); su posición horizontal es la que las abarca y la vertical, la
de su primera fila, para que el texto canónico decida el párrafo de la tabla como lo decidía
con su primera línea (con el alto de toda la tabla, la tabla se pegaba al párrafo anterior). El
tramo `tabla` sale igual que antes, con las celdas.

Una tabla no se escribe, y sus líneas quedan como estaban, si:

- la página no se leyó de la capa de texto (un escaneo o un texto inservible leído por
  reconocimiento: las celdas de pdfplumber traerían el texto que no sirve);
- tiene una sola fila (un recuadro de un renglón, como el lema del año);
- alguna de sus líneas sale de la zona por los costados (una línea que la cruza), o
- sus celdas no traen exactamente los mismos caracteres que esas líneas, sin contar los
  espacios: ni se pierde ni se agrega texto.

Cada zona dice si se escribió (`cells`) y la lectura guarda `CELLS_VERSION` (P6).

Se guardan en `tenders_reading.tables`. Una página web no tiene zonas. Todo corre en
CPU y sin conexión (P4).
"""

import io
from collections import Counter
from dataclasses import replace

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_PDF_TEXT,
    PAGE_KIND_TEXT,
    Line,
    UnsupportedFormatError,
    detect_format,
)

# Versión de la forma en que se escriben las celdas de una tabla en la lectura (P6).
CELLS_VERSION = "celdas-1"
CELL_SEPARATOR = "\t"
ROW_SEPARATOR = "\n"
# Claves de la posición de una zona (lo que trae `table_zones`).
ZONE_KEYS = ("page", "x0", "top", "x1", "bottom")
# Filas que tiene que tener una tabla para escribirla celda por celda.
MIN_ROWS = 2
# Tolerancia, en puntos, para que una línea quede dentro de la zona por los costados.
SIDE_TOLERANCE = 1.0

# Decimales de las medidas, como en la lectura de la 001.
_DECIMALS = 2

_DAMAGED_MESSAGE = "El PDF está dañado o incompleto: no se pueden buscar sus tablas."


def table_zones(data: bytes) -> list[dict]:
    """Las zonas de tabla de un documento, página por página, en el orden del archivo.
    Un documento que no es PDF no tiene zonas; un PDF dañado levanta
    `UnsupportedFormatError`."""
    return [{key: zone[key] for key in ZONE_KEYS} for zone in read_tables(data)]


def read_tables(data: bytes) -> list[dict]:
    """Las zonas de `table_zones` con sus filas (`rows`): por fila, el texto de cada celda
    con los espacios reducidos a uno, o `None` si la celda la cubre otra unida."""
    if detect_format(data) != FORMAT_PDF:
        return []

    import pdfplumber
    from pdfminer.psparser import PSException
    from pdfplumber.utils.exceptions import PdfminerException

    zones = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                for table in page.find_tables():
                    # Un recuadro de una sola columna es texto con borde, no una tabla
                    # (T-178): sus cláusulas se parten como cualquier otra.
                    if max((len(row.cells) for row in table.rows), default=0) < 2:
                        continue
                    x0, top, x1, bottom = table.bbox
                    zones.append(
                        {
                            "page": number,
                            "x0": round(float(x0), _DECIMALS),
                            "top": round(float(top), _DECIMALS),
                            "x1": round(float(x1), _DECIMALS),
                            "bottom": round(float(bottom), _DECIMALS),
                            "rows": [[_cell(text) for text in row]
                                     for row in table.extract()],
                        }
                    )
    except (PdfminerException, PSException) as error:
        raise UnsupportedFormatError(_DAMAGED_MESSAGE) from error
    return zones


def _cell(text):
    return None if text is None else " ".join(text.split())


def render_rows(rows) -> str:
    """El texto de una tabla: una fila por renglón y una tabulación entre sus celdas. Una
    celda vacía queda vacía entre sus separadores; la que cubre otra unida no se escribe."""
    return ROW_SEPARATOR.join(
        CELL_SEPARATOR.join(cell for cell in row if cell is not None) for row in rows)


def with_cells(reading, zones):
    """`(lectura, zonas)`: la lectura con cada tabla escrita celda por celda (ver el módulo)
    y las zonas con `cells` (si se escribió). No cambia la lectura que recibe."""
    marked = [{**zone, "cells": False} for zone in zones]
    pages = []
    for page in reading.pages:
        lines = list(page.lines)
        if page.classification == PAGE_KIND_TEXT and lines:
            for zone in marked:
                if zone["page"] == page.number:
                    lines = _write_table(lines, zone)
        pages.append(replace(page, lines=lines))
    return replace(reading, pages=pages), marked


def _write_table(lines, zone):
    rows = zone.get("rows") or []
    if len(rows) < MIN_ROWS:
        return lines
    inside = [index for index, line in enumerate(lines) if _in_zone(line, zone)]
    if not inside:
        return lines
    chosen = [lines[index] for index in inside]
    if any(line.origin != ORIGIN_PDF_TEXT for line in chosen):
        return lines
    if any(line.x0 < zone["x0"] - SIDE_TOLERANCE or line.x1 > zone["x1"] + SIDE_TOLERANCE
           for line in chosen):
        return lines
    cells = "".join(cell for row in rows for cell in row if cell)
    if _letters(cells) != _letters("".join(line.text for line in chosen)):
        return lines
    table_line = Line(
        text=render_rows(rows),
        x0=min(line.x0 for line in chosen),
        top=chosen[0].top,
        x1=max(line.x1 for line in chosen),
        bottom=chosen[0].bottom,
        origin=ORIGIN_PDF_TEXT,
    )
    zone["cells"] = True
    taken = set(inside)
    first = inside[0]
    before = [line for index, line in enumerate(lines) if index < first]
    after = [line for index, line in enumerate(lines) if index > first and index not in taken]
    return before + [table_line] + after


def _in_zone(line, zone):
    """La misma regla que `segmenting._zone_of`: el centro vertical de la línea dentro de la
    zona y algo de superposición horizontal."""
    if None in (line.top, line.bottom, line.x0, line.x1):
        return False
    middle = (line.top + line.bottom) / 2
    return (zone["top"] <= middle <= zone["bottom"]
            and line.x0 < zone["x1"] and line.x1 > zone["x0"])


def _letters(text):
    return Counter(char for char in text if not char.isspace())
