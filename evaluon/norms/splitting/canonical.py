"""Texto canónico de una lectura (ADR-0004, "Texto literal"; plan 001, "Cita"; T-013).

El texto de cada unidad es un recorte del texto canónico, que se obtiene de la lectura
con cinco operaciones fijas y ninguna más:

1. Normalización Unicode NFC (no NFKC, que convertiría `º` en `o`).
2. Las ligaduras tipográficas se separan en sus letras, los espacios duros pasan a
   espacio común y los guiones opcionales invisibles se quitan.
3. Los saltos de línea dentro de un párrafo se reemplazan por un espacio.
4. Una palabra cortada por guion al final de la línea se une (`contra-` + `tación` →
   `contratación`) solo si la línea siguiente empieza en minúscula. Cada unión se cuenta
   y se lista en el informe.
5. Los espacios repetidos se reducen a uno.

No se corrige ortografía, no se agregan ni quitan tildes, no se cambian mayúsculas.

Qué es un párrafo, para la operación 3. Los párrafos quedan separados por un salto de
línea (`\\n`) y las líneas de un mismo párrafo se unen. Dentro de una página, una línea
empieza un párrafo si la separa de la anterior un espacio vertical mayor que la mitad del
alto de la línea (en el anexo de la Disp. 247/2022: 1,5 puntos entre líneas de un
párrafo y 13,5 entre párrafos, con líneas de 12 puntos), o si empieza con un encabezado
de artículo. Entre páginas, el párrafo sigue solo si la última línea de la página llega
al margen derecho y no termina en punto, dos puntos o punto y coma; ante la duda empieza
otro párrafo, porque un salto de más no cambia ninguna palabra y una unión de más podría
esconder un encabezado. Una línea sin posición (página web) es un párrafo propio.

Las líneas que la lectura marcó como descartadas (`Line.discarded`) no entran en el
texto canónico: se cuentan para el informe.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from evaluon.norms.splitting.articles import ARTICLE_HEADING

# Operación 2. Ligaduras del bloque de formas de presentación alfabéticas (U+FB00 a
# U+FB06), espacios duros y guion opcional.
LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}
HARD_SPACES = ("\u00a0", "\u2007", "\u202f")
SOFT_HYPHEN = "\u00ad"

# Operación 4. Guion al final de una línea, pegado a una letra.
_HYPHENATED_END = re.compile(r"([^\W\d_]+)[-\u2010]$")
_LOWERCASE_START = re.compile(r"[a-záéíóúüñ]")
_FIRST_WORD = re.compile(r"\w+")

# Operación 5.
_REPEATED_SPACES = re.compile(r" {2,}")

# Un renglón que empieza con un encabezado de artículo empieza un párrafo. Es la misma
# forma que reconoce la partición.
_ARTICLE_HEADING_START = ARTICLE_HEADING

# Separación vertical entre líneas, en proporción al alto de la línea, a partir de la
# cual empieza otro párrafo.
PARAGRAPH_GAP_RATIO = 0.5
# Distancia al margen derecho de la página, en proporción a su ancho, dentro de la cual
# una línea se considera llena (llega al margen).
FULL_LINE_RATIO = 0.04
# Una línea llena que termina con uno de estos signos cierra su párrafo al cambiar de
# página.
_PARAGRAPH_END = (".", ":", ";")


@dataclass
class CanonicalLine:
    """Una línea leída y su lugar en el texto canónico: `text[start:end]`."""

    page: int | None
    start: int
    end: int
    origin: str
    confidence: float | None = None


@dataclass
class HyphenJoin:
    """Una palabra cortada por guion que se unió (operación 4)."""

    page: int | None
    word: str
    position: int


@dataclass
class CanonicalText:
    """El texto canónico de una lectura y cómo se armó."""

    text: str
    lines: list[CanonicalLine] = field(default_factory=list)
    paragraphs: list[tuple[int, int]] = field(default_factory=list)
    hyphen_joins: list[HyphenJoin] = field(default_factory=list)
    discarded_lines: int = 0

    def lines_in(self, start, end):
        """Las líneas que tienen texto dentro de `text[start:end]`."""
        return [line for line in self.lines if line.start < end and line.end > start]

    def pages_at(self, start, end):
        """Primera y última página del tramo `text[start:end]`; vacías en páginas web."""
        pages = [line.page for line in self.lines_in(start, end) if line.page is not None]
        if not pages:
            return (None, None)
        return (min(pages), max(pages))


def normalize_line(text):
    """Operaciones 1 y 2, y la 5 dentro de la línea."""
    text = unicodedata.normalize("NFC", text)
    for ligature, letters in LIGATURES.items():
        text = text.replace(ligature, letters)
    for space in HARD_SPACES:
        text = text.replace(space, " ")
    text = text.replace(SOFT_HYPHEN, "")
    return _REPEATED_SPACES.sub(" ", text)


def build_canonical_text(reading):
    """Arma el texto canónico de una lectura (`evaluon.norms.reading.DocumentReading`)."""
    builder = _Builder()
    previous = None  # (página, línea) de la última línea agregada
    for page in reading.pages:
        for line in page.lines:
            if line.discarded:
                builder.discarded_lines += 1
                continue
            text = normalize_line(line.text)
            if not text.strip():
                continue
            if previous is None or _starts_paragraph(previous, page, line, text):
                builder.new_paragraph()
            builder.add_line(page.number, line, text)
            previous = (page, line)
    return builder.result()


def _starts_paragraph(previous, page, line, text):
    previous_page, previous_line = previous
    if _ARTICLE_HEADING_START.match(text.lstrip()):
        return True
    if None in (line.top, line.bottom, previous_line.top, previous_line.bottom):
        return True
    if previous_page is page:
        height = max(line.bottom - line.top, previous_line.bottom - previous_line.top)
        return line.top - previous_line.bottom > height * PARAGRAPH_GAP_RATIO
    return not _continues_on_next_page(previous_page, previous_line)


def _continues_on_next_page(page, line):
    right_edge = max(other.x1 for other in page.lines if other.x1 is not None)
    margin = (page.width or 0) * FULL_LINE_RATIO
    full = line.x1 is not None and line.x1 >= right_edge - margin
    return full and not normalize_line(line.text).rstrip().endswith(_PARAGRAPH_END)


class _Builder:
    def __init__(self):
        self.parts = []
        self.length = 0
        self.lines = []
        self.paragraphs = []
        self.hyphen_joins = []
        self.discarded_lines = 0
        self.paragraph_start = None

    def _append(self, text):
        self.parts.append(text)
        self.length += len(text)

    def _last_char(self):
        return self.parts[-1][-1] if self.parts and self.parts[-1] else ""

    def new_paragraph(self):
        self._close_paragraph()
        if self.paragraphs:
            self._append("\n")
        self.paragraph_start = self.length

    def _close_paragraph(self):
        if self.paragraph_start is not None:
            self.paragraphs.append((self.paragraph_start, self.length))
            self.paragraph_start = None

    def add_line(self, page_number, line, text):
        if self.length > self.paragraph_start:
            previous = self.lines[-1]
            hyphenated = _HYPHENATED_END.search(self.parts[-1])
            if hyphenated and _LOWERCASE_START.match(text):
                # Operación 4: se quita el guion y no se agrega espacio.
                fragment = hyphenated.group(1)
                self.parts[-1] = self.parts[-1][:-1]
                self.length -= 1
                previous.end -= 1
                rest = _FIRST_WORD.match(text)
                self.hyphen_joins.append(
                    HyphenJoin(
                        page=page_number,
                        word=fragment + (rest.group(0) if rest else ""),
                        position=self.length - len(fragment),
                    )
                )
            else:
                # Operación 3, con la 5 en la unión: un solo espacio.
                if self._last_char() == " ":
                    text = text.lstrip(" ")
                else:
                    self._append(" ")
                    text = text.lstrip(" ")
        start = self.length
        self._append(text)
        self.lines.append(
            CanonicalLine(
                page=page_number,
                start=start,
                end=self.length,
                origin=line.origin,
                confidence=line.confidence,
            )
        )

    def result(self):
        self._close_paragraph()
        return CanonicalText(
            text="".join(self.parts),
            lines=self.lines,
            paragraphs=self.paragraphs,
            hyphen_joins=self.hyphen_joins,
            discarded_lines=self.discarded_lines,
        )
