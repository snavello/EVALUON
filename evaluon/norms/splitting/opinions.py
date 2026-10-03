"""Partición de dictámenes legales y recomendaciones de auditoría (ADR-0004, "Cómo se
parte", fila "Dictamen o recomendación"; plan 001, "Identificación de unidades"; T-024).

Trabaja sobre los mismos párrafos del texto canónico que las reglas de normas
(`canonical.py` y `partition.classify`), y deja cada párrafo en una unidad, en la lista
de descartados o en la de no ubicados, igual que ellas (control de cobertura).

| Encabezado de punto | Formas | Número y clave |
|---|---|---|
| Romano | `I.`, `IV.`, `XII.` (del I al XXXIX), seguido de espacio o del fin del párrafo | `I`, `punto-i` |
| Arábigo | `1.`, `12.` | `1`, `punto-1` |
| Decimal | `1.1.`, `2.3`, `1.2.4.`: con o sin punto final; cada parte de una o dos cifras | `2.3`, `punto-2.3` |
| No es punto | `1.000` (monto), `12.5%`, `2 de mayo`, `1)`, `a)`, `V.E.`, `IIII.`, un número de punto en medio de un párrafo | — |

Reglas:

- **Puntos.** Un encabezado de punto solo se reconoce al comienzo de un párrafo. El punto
  va desde su encabezado hasta el párrafo anterior al siguiente punto aceptado o a la
  firma. Lo que está antes del primer punto (por ejemplo, el encabezado del dictamen y la
  referencia) queda como no ubicado, a la vista en el informe; la carátula GDE se
  descarta como en las normas; la firma y lo que la sigue quedan como no ubicados.
- **Puntos romanos.** Son el primer nivel. Los puntos arábigos que les siguen cuelgan de
  ellos: clave `punto-ii/punto-3`, ruta "Punto II › Punto 3". Su texto propio es su
  encabezado y lo que haya antes del primer punto arábigo, como el de un anexo.
- **Puntos arábigos y decimales.** No se anidan entre sí: `2.3` no es una unidad hija de
  `2.`, porque su número ya dice dónde está. Así cada carácter está en un solo punto.
- **Secuencia.** Como en los artículos (`partition.SEQUENCE_MARGIN`): un romano se
  acepta si continúa la numeración o salta hacia adelante dentro del margen. Un arábigo
  o decimal se acepta si es el primero (todas sus partes valen 1: `1.`, `1.1.`), si baja
  un nivel desde el anterior (`2.` → `2.1`), o si es el siguiente del anterior o de uno
  de sus niveles superiores, dentro del margen (`2.1` → `2.2`, `1.2` → `2.1`, `3.1` →
  `4.`). Después de cada romano la numeración arábiga puede volver a empezar. Los saltos
  se informan; un encabezado que no se acepta (por ejemplo, una enumeración propia
  dentro de un punto) queda dentro del punto abierto y se informa.
- **Párrafos.** Si el documento no tiene al menos `MIN_POINTS` puntos aceptados, no está
  numerado: cada párrafo es una unidad `parrafo`, numerada por orden (`parrafo-12`,
  "Párrafo 12"). La firma y lo que la sigue quedan como no ubicados.
"""

import re
from dataclasses import dataclass

from evaluon.norms.splitting.headings import SIGNATURE, _article_label
from evaluon.norms.splitting.partition import (
    DISCARDED,
    PATH_SEPARATOR,
    SEQUENCE_MARGIN,
    UNLOCATED,
    Block,
    Container,
    Partition,
    Span,
    _cover_end,
)

# Cuántos puntos aceptados hacen falta para tomar el documento como numerado. Con uno
# solo, un párrafo que empieza con "1." no alcanza para dejar el resto sin ubicar.
MIN_POINTS = 2

POINTS_NAME = "Puntos"

POINT_HEADING = re.compile(
    r"(?:(?P<roman>[IVX]+)\.|(?P<decimal>\d{1,2}(?:\.\d{1,2})+)\.?|(?P<single>\d{1,2})\.)"
    r"(?=\s|$)"
)
# Números romanos del I al XXXIX, bien escritos.
_ROMAN = re.compile(r"X{0,3}(?:IX|IV|V?I{0,3})")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10}

ROMAN = "roman"
ARABIC = "arabic"


@dataclass(frozen=True)
class PointHeading:
    """Encabezado de punto: `style` romano o arábigo; `value`, el número romano como
    entero o las partes del arábigo (`(2, 3)`); `number`, el número normalizado
    (`II`, `2.3`); `label`, el encabezado con su epígrafe en mayúsculas, si lo tiene."""

    style: str
    value: object
    number: str
    label: str


def point_heading(text):
    """El encabezado de punto con que empieza un párrafo, o vacío."""
    match = POINT_HEADING.match(text)
    if not match:
        return None
    label = _article_label(text, match.end())
    roman = match.group("roman")
    if roman is not None:
        if not _ROMAN.fullmatch(roman):
            return None
        return PointHeading(ROMAN, _roman_value(roman), roman, label)
    parts = tuple(int(part) for part in (match.group("decimal") or match.group("single")).split("."))
    return PointHeading(ARABIC, parts, ".".join(str(part) for part in parts), label)


def partition(paragraphs):
    """Asigna cada párrafo a un punto o a un tramo; si el documento no está numerado,
    a un párrafo."""
    return _Points(paragraphs).run() or _paragraphs(paragraphs)


class _Points:
    def __init__(self, paragraphs):
        self.paragraphs = paragraphs
        self.result = Partition()
        self.container = Container(name=POINTS_NAME, key="", path="")
        self.result.containers.append(self.container)
        self.open = None
        self.accepted = 0
        self.roman = None  # bloque del punto romano en curso
        self.expected_roman = 1
        self.last = None  # partes del último punto arábigo aceptado
        self.restart = True  # la numeración arábiga puede volver a empezar

    def run(self):
        start = _cover_start(self.result.items, self.paragraphs)
        for p in self.paragraphs[start:]:
            self.step(p)
        self.close()
        return self.result if self.accepted >= MIN_POINTS else None

    def step(self, p):
        if p.heading.kind == SIGNATURE:
            self.close()
            _span(self.result.items, UNLOCATED, p.index)
            return
        heading = point_heading(p.text)
        if heading is not None:
            accept = self.accept_roman if heading.style == ROMAN else self.accept_arabic
            if accept(heading):
                self.close()
                self.open_point(p, heading)
                return
            self.container.not_accepted.append(
                {"number": heading.number, "page": p.page, "inside": self.open.key if self.open else ""}
            )
        if self.open is not None:
            self.open.last = p.index
        else:
            _span(self.result.items, UNLOCATED, p.index)

    def close(self):
        if self.open is not None:
            self.result.items.append(self.open)
            self.open = None

    def accept_roman(self, heading):
        n = heading.value
        if not self.expected_roman <= n <= self.expected_roman + SEQUENCE_MARGIN:
            return False
        self.container.gaps.extend(_to_roman(m) for m in range(self.expected_roman, n))
        self.expected_roman = n + 1
        self.restart = True
        return True

    def accept_arabic(self, heading):
        parts = heading.value
        gaps = _continues(self.last, parts) if self.last is not None else None
        if gaps is None:
            if not (self.restart and all(part == 1 for part in parts)):
                return False
            gaps = []
        self.container.gaps.extend(".".join(str(part) for part in gap) for gap in gaps)
        self.last = parts
        self.restart = False
        return True

    def open_point(self, p, heading):
        self.accepted += 1
        slug = "punto-" + heading.number.lower()
        name = f"Punto {heading.number}"
        if heading.style == ROMAN:
            self.open = Block("punto", heading.number, heading.label, slug, name, None,
                              p.index, p.index)
            self.roman = self.open
            return
        parent = self.roman
        key = f"{parent.key}/{slug}" if parent else slug
        path = f"{parent.path}{PATH_SEPARATOR}{name}" if parent else name
        self.open = Block("punto", heading.number, heading.label, key, path,
                          parent.key if parent else None, p.index, p.index)


def _continues(last, parts):
    """Si el punto `parts` sigue al `last`: los números que faltan en el medio (vacío si
    no falta ninguno), o `None` si no lo sigue. Lo sigue si baja un nivel (`2` → `2.1`)
    o si es el siguiente de alguno de sus niveles, dentro del margen, con los niveles
    inferiores en 1 (`2.1` → `2.2`, `1.2` → `2.1`)."""
    depth = len(last)
    if len(parts) > depth and parts[:depth] == last and all(part == 1 for part in parts[depth:]):
        return []
    for level in range(depth, 0, -1):
        prefix = last[: level - 1]
        if len(parts) < level or parts[: level - 1] != prefix:
            continue
        if not all(part == 1 for part in parts[level:]):
            continue
        step = parts[level - 1] - last[level - 1]
        if 1 <= step <= 1 + SEQUENCE_MARGIN:
            return [prefix + (missing,) for missing in range(last[level - 1] + 1, parts[level - 1])]
    return None


def _paragraphs(paragraphs):
    """Documento sin numeración: cada párrafo es una unidad `parrafo`, numerada por
    orden. La firma y lo que la sigue quedan como no ubicados."""
    result = Partition()
    start = _cover_start(result.items, paragraphs)
    count, signed = 0, False
    for p in paragraphs[start:]:
        if signed or p.heading.kind == SIGNATURE:
            signed = True
            _span(result.items, UNLOCATED, p.index)
            continue
        count += 1
        name = f"Párrafo {count}"
        result.items.append(
            Block("parrafo", str(count), name, f"parrafo-{count}", name, None, p.index, p.index)
        )
    return result


def _cover_start(items, paragraphs):
    """Descarta la carátula GDE, como en las normas, y devuelve el primer párrafo que
    sigue."""
    start = _cover_end(paragraphs) + 1
    if start > 0:
        items.append(Span(DISCARDED, 0, start - 1, reason="caratula"))
    return start


def _span(items, kind, k):
    """Suma el párrafo `k` al último tramo si es del mismo destino y le sigue; si no,
    abre un tramo nuevo."""
    last = items[-1] if items else None
    if isinstance(last, Span) and last.kind == kind and not last.reason and last.last == k - 1:
        last.last = k
        return
    items.append(Span(kind, k, k))


def _roman_value(roman):
    total = 0
    for position, char in enumerate(roman):
        value = _ROMAN_VALUES[char]
        following = _ROMAN_VALUES[roman[position + 1]] if position + 1 < len(roman) else 0
        total += -value if value < following else value
    return total


def _to_roman(number):
    tens, units = divmod(number, 10)
    return "X" * tens + ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"][units]
