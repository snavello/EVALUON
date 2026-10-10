"""El punto completo del pliego del que sale un requisito (plan 014, T-228; REQ-089, REQ-090,
REQ-098).

Un requisito cita un fragmento de un tramo del pliego (`RequirementQuote.segment`). Mostrar solo
el fragmento lo deja en pedazos («se deberá adjuntar electrónicamente en el sistema…»): la
Comisión necesita el punto entero (el texto del tramo, con su encabezado, por ejemplo «7.1.») y
ver en él qué parte es el requisito. Este módulo arma ese punto una vez por requisito, con el
fragmento marcado y, si el punto es largo, sus primeras líneas y el texto completo aparte
(«ver todo»). Lo usan la tabla de la evaluación, el detalle del par, los pendientes y las
preguntas, con el mismo parcial (`journey/_punto_pliego.html`).

Solo lee; no decide nada (P3). Las citas de todos los requisitos de una pantalla se cargan con una
sola consulta (con el tramo y su documento), y por alcance de pedido (`memo.once`): los pendientes,
la tabla y las preguntas no la repiten.
"""

from collections import defaultdict
from dataclasses import dataclass

from evaluon.journey import memo
from evaluon.tenders.models import RequirementQuote

HEAD_LINES = 5  # líneas del punto que se ven antes de «ver todo»
HEAD_CHARS = 420  # y como máximo estos caracteres
LEAD_CHARS = 90  # si el fragmento queda más allá de las primeras líneas, cuánto texto lo antecede


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


def build(segment, quotes):
    """El `Point` de `segment` con sus `quotes` marcadas."""
    text = segment.text or ""
    ranges = _merge([found for found in (_locate(segment, q) for q in quotes) if found])
    first, last, long = _head_window(text, ranges)
    head = _slice(text, ranges, first, last)
    if first > 0:
        head = [("… ", False)] + head
    if last < len(text):
        head = head + [(" …", False)]
    return Point(label=_label(segment), where=_where(segment),
                 parts=tuple(_slice(text, ranges, 0, len(text))), head=tuple(head), long=long,
                 chars=len(text), segment_id=segment.pk)


def quotes_of(requirement_ids):
    """`{id del requisito: [citas]}` en su orden, con el tramo y su documento cargados (una sola
    consulta)."""
    found = defaultdict(list)
    for quote in (RequirementQuote.objects.filter(requirement_id__in=requirement_ids)
                  .select_related("segment__reading__document")
                  .order_by("requirement_id", "order")):
        found[quote.requirement_id].append(quote)
    return found


def quotes_of_page(page):
    """Las citas de los requisitos de `page` (la matriz de evaluación), una vez por pedido."""
    key = ("quotes", page.procedure.pk, page.version.pk if page.version else None)
    return memo.once(key, lambda: quotes_of([r.pk for r in page.requirements]))


def _points_of(quotes):
    """Los puntos de un requisito: uno por tramo del que salen sus citas (casi siempre uno), con
    todas sus citas de ese tramo marcadas."""
    by_segment, order = defaultdict(list), []
    for quote in quotes:
        if quote.segment_id not in by_segment:
            order.append(quote.segment)
        by_segment[quote.segment_id].append(quote)
    return [build(segment, by_segment[segment.pk]) for segment in order]


def points_of_page(page):
    """`{id del requisito: [Point]}` de todos los requisitos de `page`, una vez por pedido."""
    key = ("points", page.procedure.pk, page.version.pk if page.version else None)

    def compute():
        quotes = quotes_of_page(page)
        return {r.pk: _points_of(quotes.get(r.pk, [])) for r in page.requirements}

    return memo.once(key, compute)


def points_of(requirement_ids):
    """`{id del requisito: [Point]}` para requisitos sueltos (una consulta)."""
    quotes = quotes_of(list(requirement_ids))
    return {pk: _points_of(quotes.get(pk, [])) for pk in requirement_ids}
