"""Partición en artículos (ADR-0004, "Cómo se parte"; plan 001, "Identificación de
unidades" y "Una norma en más de un archivo"; T-013).

Las reglas trabajan sobre los párrafos del texto canónico: un encabezado solo se
reconoce al comienzo de un párrafo. En esta etapa se reconocen solo artículos, con las
formas del anexo de la Disp. AFIP 247/2022; incisos, considerandos, anexos dentro del
documento, títulos en la ruta, cláusulas y cierre son de T-023 a T-025, y las formas de
la Disp. 297/03, de T-050.

Cada párrafo termina en uno de tres lugares, y la suma da el total (control de
cobertura):

- **Una unidad.** Un artículo va desde su encabezado hasta el párrafo anterior al
  siguiente encabezado aceptado, o hasta un encabezado en mayúsculas que no es un
  artículo (un título, un capítulo, una cláusula transitoria): ese texto no es del
  artículo. Con una parte que es un anexo, la unidad raíz `anexo` tiene como texto propio
  lo que está antes del índice, del primer título o del primer artículo.
- **Descartado.** El índice: una serie de dos o más encabezados de artículo seguidos sin
  texto entre ellos, con los títulos y capítulos intercalados y la palabra "ÍNDICE" que
  los encabeza.
- **No ubicado.** Todo lo demás.

Control de secuencia: dentro del contenedor, un encabezado de artículo se acepta solo si
continúa la numeración (el primero, si es el 1). Un encabezado fuera de secuencia (un
artículo transcripto, una repetición) queda dentro del artículo abierto.
"""

import re
from dataclasses import dataclass

# Encabezado de artículo del anexo de la 247/2022: `ARTÍCULO 1°.-` (grado), `ARTÍCULO
# 1º.-` (ordinal, en el índice y en el artículo 9) y `ARTÍCULO 10.-` (sin signo). Con o
# sin tilde. Solo en mayúsculas, para no tomar "Artículo 2° de la Ley ...".
ARTICLE_HEADING = re.compile(r"ART[IÍ]CULO (?P<number>\d+)[°º]?\.-")

# Título, capítulo o sección en un párrafo propio: `TÍTULO II - ...`, `CAPÍTULO I - ...`.
TITLE_HEADING = re.compile(r"(?:T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N) [IVXLCDM\d]+\b")

# La palabra que encabeza el índice.
INDEX_MARKER = re.compile(r"[IÍ]NDICE:?")

# Encabezado "ANEXO" de la carátula: da la etiqueta de la unidad raíz.
ANNEX_HEADING = re.compile(r"ANEXO\b")

# Epígrafe de un artículo: lo que sigue al encabezado, en mayúsculas, hasta el punto.
_EPIGRAPH = re.compile(r"\s*(?P<epigraph>[^.]*?)\.(?=\s|$)")

_LOWERCASE = re.compile(r"[a-záéíóúüñç]")
_LETTER = re.compile(r"[^\W\d_]")

# Cuántos encabezados de artículo sin texto, seguidos, hacen un índice.
INDEX_MIN_HEADINGS = 2

# Clases de párrafo.
ARTICLE = "article"
TITLE = "title"
INDEX = "index"
UPPER = "upper"
TEXT = "text"


@dataclass
class Paragraph:
    index: int
    start: int
    end: int
    text: str
    kind: str
    number: int | None = None
    heading_only: bool = False


@dataclass
class Segment:
    """Un tramo de párrafos seguidos con el mismo destino."""

    kind: str  # "root", "article", "discarded" o "unlocated"
    first: int
    last: int
    number: int | None = None
    reason: str = ""


def classify(text, start, end, index):
    """Clase de un párrafo del texto canónico."""
    heading = ARTICLE_HEADING.match(text)
    if heading:
        rest = text[heading.end() :]
        return Paragraph(
            index,
            start,
            end,
            text,
            ARTICLE,
            number=int(heading.group("number")),
            heading_only=not _LOWERCASE.search(rest),
        )
    uppercase = not _LOWERCASE.search(text)
    if INDEX_MARKER.fullmatch(text):
        return Paragraph(index, start, end, text, INDEX)
    if uppercase and TITLE_HEADING.match(text):
        return Paragraph(index, start, end, text, TITLE)
    if uppercase and _LETTER.match(text) and len(_LETTER.findall(text)) >= 3:
        return Paragraph(index, start, end, text, UPPER)
    return Paragraph(index, start, end, text, TEXT)


def article_label(text):
    """Etiqueta como figura en el documento: el encabezado y su epígrafe, sin el punto
    que cierra el epígrafe ni el texto que sigue. `ARTÍCULO 1°.- OBJETO`."""
    heading = ARTICLE_HEADING.match(text)
    end = heading.end()
    epigraph = _EPIGRAPH.match(text, end)
    if epigraph:
        words = epigraph.group("epigraph")
        if words.strip() and _LETTER.search(words) and not _LOWERCASE.search(words):
            end = epigraph.end("epigraph")
    return text[:end].rstrip()


def find_index_blocks(paragraphs):
    """Índices: series de párrafos que son la palabra "ÍNDICE", títulos o encabezados de
    artículo sin texto, con al menos `INDEX_MIN_HEADINGS` encabezados de artículo. La
    serie termina en su último encabezado de artículo. Devuelve pares (primero, último)."""
    blocks = []
    i = 0
    while i < len(paragraphs):
        j = i
        while j < len(paragraphs) and _index_member(paragraphs[j]):
            j += 1
        headings = [p.index for p in paragraphs[i:j] if p.kind == ARTICLE]
        if len(headings) >= INDEX_MIN_HEADINGS:
            blocks.append((i, headings[-1]))
            i = headings[-1] + 1
        else:
            i = max(j, i + 1)
    return blocks


def _index_member(paragraph):
    if paragraph.kind == ARTICLE:
        return paragraph.heading_only
    return paragraph.kind in (INDEX, TITLE)


def partition(paragraphs, with_root):
    """Asigna cada párrafo a un tramo. Devuelve los tramos en orden."""
    in_index = {}
    for first, last in find_index_blocks(paragraphs):
        for k in range(first, last + 1):
            in_index[k] = first

    segments = []
    position = 0
    if with_root:
        while position < len(paragraphs) and not _ends_root(paragraphs[position], in_index):
            position += 1
        segments.append(Segment("root", 0, position - 1))

    expected = 1
    current = None  # tramo del artículo abierto
    for paragraph in paragraphs[position:]:
        k = paragraph.index
        if k in in_index:
            current = None
            _extend(segments, "discarded", k, reason="indice", block=in_index[k])
        elif paragraph.kind == ARTICLE and paragraph.number == expected:
            current = Segment("article", k, k, number=paragraph.number)
            segments.append(current)
            expected += 1
        elif current is not None and paragraph.kind in (TITLE, UPPER, INDEX):
            current = None
            _extend(segments, "unlocated", k)
        elif current is not None:
            current.last = k
        else:
            _extend(segments, "unlocated", k)
    return segments


def _ends_root(paragraph, in_index):
    return paragraph.index in in_index or paragraph.kind in (ARTICLE, TITLE)


def _extend(segments, kind, k, reason="", block=None):
    """Suma el párrafo `k` al último tramo si es del mismo destino y le sigue; si no,
    abre un tramo nuevo. Dos índices distintos son dos tramos."""
    last = segments[-1] if segments else None
    same_block = kind != "discarded" or (last is not None and last.number == block)
    if last is not None and last.kind == kind and last.last == k - 1 and same_block:
        last.last = k
        return
    segments.append(Segment(kind, k, k, number=block, reason=reason))
