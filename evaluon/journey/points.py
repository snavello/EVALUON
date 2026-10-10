"""El punto completo del pliego del que sale un requisito (plan 014, T-228; REQ-089, REQ-090,
REQ-098).

Un requisito cita un fragmento de un tramo del pliego (`RequirementQuote.segment`). Mostrar solo
el fragmento lo deja en pedazos («se deberá adjuntar electrónicamente en el sistema…»): la
Comisión necesita el punto entero (el texto del tramo, con su encabezado, por ejemplo «7.1.») y
ver en él qué parte es el requisito. Este módulo arma ese punto una vez por requisito, con el
fragmento marcado y, si el punto es largo, sus primeras líneas y el texto completo aparte
(«ver todo»). Lo usan la tabla de la evaluación, el detalle del par, los pendientes y las
preguntas, con el mismo parcial (`journey/_punto_pliego.html`).

El punto muestra el texto vigente, el mismo que lee la evaluación (`grounds.requirement_text`): si
una circular modificó el requisito, el texto nuevo va en el lugar del fragmento, marcado, con una
línea «Modificado por la circular N» y el original plegado; si la circular lo suprimió, lo dice y
deja el fragmento original.

Solo lee; no decide nada (P3). Las citas y las circulares de todos los requisitos de una pantalla
se cargan con una consulta cada una (con el tramo y su documento), y por alcance de pedido
(`memo.once`): los pendientes, la tabla y las preguntas no las repiten.
"""

import re
from collections import defaultdict
from dataclasses import dataclass

from evaluon.assessment import grounds
from evaluon.journey import memo
from evaluon.tenders.models import RequirementQuote, RequirementSource

HEAD_LINES = 5  # líneas del punto que se ven antes de «ver todo»
HEAD_CHARS = 420  # y como máximo estos caracteres
LEAD_CHARS = 90  # si el fragmento queda más allá de las primeras líneas, cuánto texto lo antecede


@dataclass(frozen=True)
class Change:
    """Lo que una circular hizo a una cita: `note` dice cuál («Modificado por la circular 3
    (01/02/2026)») y `original` es el texto que reemplazó, plegado en la pantalla (vacío si la
    circular suprimió la cita: el fragmento sigue a la vista)."""

    note: str
    original: str = ""


@dataclass(frozen=True)
class Point:
    """Un punto del pliego listo para mostrar. `parts` y `head` son listas de
    `(texto, marcado)`: el punto entero y lo que se ve antes de «ver todo»."""

    label: str
    where: str
    parts: tuple
    head: tuple
    long: bool
    chars: int
    segment_id: int
    changes: tuple = ()

    @property
    def text(self):
        return "".join(text for text, _ in self.parts)


def _label(segment):
    """El encabezado del punto («7.1.»); sin encabezado, el último título de su ruta."""
    label = (segment.label or "").strip()
    if label:
        return label
    path = [p.strip() for p in (segment.path or "").replace("›", ">").split(">") if p.strip()]
    return path[-1] if path else ""


def _where(segment):
    document = segment.reading.document.title
    return f"{document} › {segment.path}" if segment.path else document


def _squash(text):
    return " ".join((text or "").split())


def _locate(segment, quote):
    """`(inicio, fin)` del fragmento dentro del texto del tramo, o `None` si no se encuentra. Primero
    por las posiciones guardadas (relativas al tramo); si el recorte no coincide, buscando el texto
    de la cita; si tampoco, sin marca (no se inventa una)."""
    text = segment.text or ""
    start, end = quote.char_start - segment.char_start, quote.char_end - segment.char_start
    if 0 <= start < end <= len(text) and _squash(text[start:end]) == _squash(quote.text):
        return start, end
    found = text.find(quote.text) if quote.text else -1
    if found >= 0:
        return found, found + len(quote.text)
    return None


def _merge(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _slice(text, ranges, first, last):
    """El tramo `text[first:last]` como `(texto, marcado)`, con las marcas que caen adentro."""
    parts, cursor = [], first
    for start, end in ranges:
        start, end = max(start, first), min(end, last)
        if start >= end:
            continue
        if start > cursor:
            parts.append((text[cursor:start], False))
        parts.append((text[start:end], True))
        cursor = end
    if cursor < last:
        parts.append((text[cursor:last], False))
    return parts


def _head_window(text, ranges):
    """`(desde, hasta, corta)`: las primeras líneas del punto; si el fragmento queda más allá, la
    ventana que lo contiene (con un poco del texto que lo antecede)."""
    lines = text.split("\n")
    head = "\n".join(lines[:HEAD_LINES])
    if len(head) > HEAD_CHARS:
        cut = head.rfind(" ", 0, HEAD_CHARS)
        head = head[:cut if cut > HEAD_CHARS // 2 else HEAD_CHARS]
    last = len(head)
    first = 0
    if ranges and ranges[0][0] >= last:
        first = max(0, ranges[0][0] - LEAD_CHARS)
        space = text.find(" ", first, ranges[0][0])
        first = space + 1 if 0 <= space < ranges[0][0] else first
        last = min(len(text), first + HEAD_CHARS)
    return first, last, (first > 0 or last < len(text))


def _circular(source):
    """«la circular 3 (01/02/2026)»: el documento de la circular sin el prefijo «Circular», y su
    fecha."""
    title = (source.segment.reading.document.title or "").strip()
    name = re.sub(r"^circular\s*", "", title, flags=re.IGNORECASE) or title
    day = f" ({source.issued_on:%d/%m/%Y})" if source.issued_on else ""
    return f"la circular {name}{day}"


def _change(quote_text):
    """El `Change` de una cita que una circular modificó o suprimió, o `None`."""
    if quote_text.source is None:
        return None
    if quote_text.suppressed:
        return Change(f"Suprimido por {_circular(quote_text.source)}: el texto marcado ya no rige.")
    return Change(f"Modificado por {_circular(quote_text.source)}", quote_text.original)


def _current(text, located):
    """`(texto vigente del tramo, rangos marcados)`: el texto vigente de cada cita va en el lugar
    del fragmento original. `located` son `(inicio, fin, texto vigente)`."""
    pieces, ranges, cursor, size = [], [], 0, 0
    for start, end, now in sorted(located):
        if start < cursor:
            continue  # dos citas que se pisan: la segunda se deja como estaba
        pieces.append(text[cursor:start])
        size += start - cursor
        pieces.append(now)
        ranges.append((size, size + len(now)))
        size += len(now)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), _merge(ranges)


def build(segment, quote_texts):
    """El `Point` de `segment` con sus citas (`grounds.QuoteText`, con el texto vigente) marcadas."""
    original = segment.text or ""
    located, changes = [], []
    for quote_text in quote_texts:
        found = _locate(segment, quote_text.quote)
        if found:
            now = original[found[0]:found[1]] if quote_text.suppressed else quote_text.text
            located.append((found[0], found[1], now))
        change = _change(quote_text)
        if change:
            changes.append(change)
    text, ranges = _current(original, located)
    first, last, long = _head_window(text, ranges)
    head = _slice(text, ranges, first, last)
    if first > 0:
        head = [("… ", False)] + head
    if last < len(text):
        head = head + [(" …", False)]
    return Point(label=_label(segment), where=_where(segment),
                 parts=tuple(_slice(text, ranges, 0, len(text))), head=tuple(head), long=long,
                 chars=len(text), segment_id=segment.pk, changes=tuple(changes))


# T-231 (E-11): la lectura del documento trae el texto canónico y las páginas enteras del pliego
# (cientos de miles de caracteres de JSON); cada cita las traería de nuevo. Se necesita el tramo y
# el título del documento, nada de eso.
HEAVY_READING = tuple(f"segment__reading__{name}" for name in (
    "pages", "tables", "canonical_text", "items", "tool_versions", "report"))


def quotes_of(requirement_ids):
    """`{id del requisito: [citas]}` en su orden, con el tramo y su documento cargados (una sola
    consulta, sin el texto completo de la lectura)."""
    found = defaultdict(list)
    for quote in (RequirementQuote.objects.filter(requirement_id__in=requirement_ids)
                  .select_related("segment__reading__document").defer(*HEAVY_READING)
                  .order_by("requirement_id", "order")):
        found[quote.requirement_id].append(quote)
    return found


def quotes_of_page(page):
    """Las citas de los requisitos de `page` (la matriz de evaluación), una vez por pedido."""
    key = ("quotes", page.procedure.pk, page.version.pk if page.version else None)
    return memo.once(key, lambda: quotes_of([r.pk for r in page.requirements]))


def sources_of(requirement_ids):
    """`{id del requisito: [circulares que tocan sus citas]}` en el orden de la evaluación (por
    fecha), con el documento de la circular cargado (una sola consulta)."""
    found = defaultdict(list)
    for source in (RequirementSource.objects.filter(requirement_id__in=requirement_ids)
                   .exclude(quote=None).select_related("segment__reading__document")
                   .defer(*HEAVY_READING).order_by("issued_on", "pk")):
        found[source.requirement_id].append(source)
    return found


def texts_of(requirements, quotes=None):
    """`{id del requisito: RequirementText}` con el texto vigente de cada cita, el que lee la
    evaluación (`grounds.requirement_text`), armado con una consulta de citas y una de circulares
    para todos los requisitos."""
    requirements = list(requirements)
    ids = [r.pk for r in requirements]
    quotes = quotes if quotes is not None else quotes_of(ids)
    sources = sources_of(ids)
    return {r.pk: grounds.requirement_text(r, quotes.get(r.pk, []), sources.get(r.pk, []))
            for r in requirements}


def texts_of_page(page):
    """`texts_of` para los requisitos de `page`, una vez por pedido."""
    key = ("texts", page.procedure.pk, page.version.pk if page.version else None)
    return memo.once(key, lambda: texts_of(page.requirements, quotes_of_page(page)))


def _points_of(text):
    """Los puntos de un requisito: uno por tramo del que salen sus citas (casi siempre uno), con
    todas sus citas de ese tramo marcadas."""
    by_segment, order = defaultdict(list), []
    for quote_text in text.quotes:
        segment = quote_text.quote.segment
        if segment.pk not in by_segment:
            order.append(segment)
        by_segment[segment.pk].append(quote_text)
    return [build(segment, by_segment[segment.pk]) for segment in order]


def points_of_page(page):
    """`{id del requisito: [Point]}` de todos los requisitos de `page`, una vez por pedido."""
    key = ("points", page.procedure.pk, page.version.pk if page.version else None)
    return memo.once(key, lambda: {pk: _points_of(text)
                                   for pk, text in texts_of_page(page).items()})


def points_of(requirements):
    """`{id del requisito: [Point]}` para requisitos sueltos (dos consultas)."""
    return {pk: _points_of(text) for pk, text in texts_of(requirements).items()}
