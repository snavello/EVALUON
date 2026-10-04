"""Filas técnicas por renglón y sus controles (REQ-024, REQ-025, REQ-028; plan 003, "Filas
técnicas por renglón" y "Qué es un requisito y su clase"; ADR-0019, decisión 3 bis).

Los requisitos técnicos van en una fila por renglón del pliego, con una cita por tramo
(el tramo entero) de sus especificaciones técnicas:

- `propia`: un tramo del renglón (su encabezado y lo que cuelga de él), o un tramo que el
  modelo marcó como técnico para ese renglón.
- `general`: un tramo técnico común a todos los renglones (por ejemplo, una sección de
  especificaciones técnicas generales, o un tramo marcado `todos`). Se cita en la fila de
  cada renglón.

La arma una regla, no el modelo:

1. Los renglones son los de `items` de las lecturas de los documentos base. Si no hay
   ninguno, el pliego tiene una sola fila técnica, sin renglón, con todos los tramos
   técnicos como citas `propia`.
2. Un tramo que cuelga de un renglón (`segment.items`) entra en la fila de sus renglones,
   sin importar los números que haya dicho el modelo.
3. Un tramo marcado por el modelo para algunos renglones va como `propia` en la fila de
   cada uno; un número que no es de ningún renglón del pliego se anota como anomalía y, si
   no queda ninguno válido, el tramo va como `general` (ante la duda, de más).
4. Un renglón sin ningún tramo `propia` más allá de su encabezado conserva su fila (con las
   citas generales) y queda con un pendiente `renglon_sin_especificaciones` en el tramo de
   su encabezado.

Este módulo no toca la base: recibe los tramos que aportan y devuelve las filas.
"""

from dataclasses import dataclass, field

from evaluon.tenders.models import QuoteScope

ALL_ITEMS = "todos"

ANOMALY_UNKNOWN_ITEM = "tecnico_renglon_desconocido"
ANOMALY_NO_HEADER = "renglon_sin_encabezado"


@dataclass(frozen=True)
class Contribution:
    """Un tramo que aporta a las filas técnicas: la unidad (`extraction.Unit`) y las
    marcas del modelo (`todos` o números de renglón; vacía si lo dispuso una regla)."""

    unit: object
    marks: tuple = ()


@dataclass
class RowQuote:
    """Una cita de una fila técnica: el tramo entero y su alcance."""

    segment: object
    scope: str


@dataclass
class Row:
    """Una fila técnica. `number` es el renglón (`None` si el pliego no tiene renglones);
    `pending` es el tramo del encabezado si el renglón quedó sin especificaciones."""

    number: int | None
    quotes: list = field(default_factory=list)
    pending: object = None


def reading_items(readings):
    """Los renglones del pliego: para cada número, el tramo de su encabezado. `readings`
    es una lista de `(lectura, {clave: tramo})`. Devuelve `[(número, tramo o None)]`
    ordenado por número; si un número está en dos lecturas, vale el de la primera."""
    result = {}
    for reading, by_key in readings:
        for item in reading.items:
            number = item["number"]
            if number not in result:
                result[number] = by_key.get(item["key"])
    return sorted(result.items())


def build_rows(items, contributions, anomalies):
    """Arma las filas técnicas.

    - `items`: `[(número, tramo del encabezado o None)]` (`reading_items`).
    - `contributions`: los `Contribution` de los tramos que aportan, en cualquier orden.
    - `anomalies`: lista donde se anotan las anomalías.

    Devuelve las filas ordenadas por renglón, con las citas en el orden del pliego."""
    contributions = sorted(contributions, key=lambda c: c.unit.position)
    if not items:
        if not contributions:
            return []
        row = Row(number=None)
        row.quotes = [RowQuote(c.unit.segment, QuoteScope.PROPIA.value)
                      for c in contributions]
        return [row]

    numbers = {number for number, _ in items}
    own = {number: [] for number in numbers}
    general = []
    for contribution in contributions:
        segment = contribution.unit.segment
        if segment.items:
            targets = [n for n in segment.items if n in numbers]
            for unknown in sorted(set(segment.items) - numbers):
                anomalies.append({"type": ANOMALY_UNKNOWN_ITEM, "segment": segment.pk,
                                  "key": segment.key, "renglon": unknown})
        else:
            targets = _targets_from_marks(contribution, numbers, anomalies)
        if targets:
            for number in targets:
                own[number].append(contribution)
        else:
            general.append(contribution)

    headers = {segment.pk for _, segment in items if segment is not None}
    rows = []
    for number, header in items:
        quotes = [(c.unit.position, c.unit.segment, QuoteScope.PROPIA.value)
                  for c in own[number]]
        quotes += [(c.unit.position, c.unit.segment, QuoteScope.GENERAL.value)
                   for c in general]
        quotes.sort(key=lambda quote: quote[0])
        row = Row(number=number,
                  quotes=[RowQuote(segment, scope) for _, segment, scope in quotes])
        if not any(c.unit.segment.pk not in headers for c in own[number]):
            if header is None:
                anomalies.append({"type": ANOMALY_NO_HEADER, "renglon": number})
            else:
                row.pending = header
        rows.append(row)
    return rows


def _targets_from_marks(contribution, numbers, anomalies):
    """Los renglones (`propia`) de un tramo que no cuelga de ninguno, según las marcas
    del modelo; vacío si va como `general`."""
    marks = [mark for mark in contribution.marks]
    if not marks or ALL_ITEMS in marks:
        return []
    segment = contribution.unit.segment
    valid = [mark for mark in marks if mark in numbers]
    for unknown in sorted(set(marks) - numbers):
        anomalies.append({"type": ANOMALY_UNKNOWN_ITEM, "segment": segment.pk,
                          "key": segment.key, "renglon": unknown})
    return valid
