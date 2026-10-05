"""Partir la lectura de un documento de una oferta en pasajes (plan 008, "Pasajes"; ADR-0027).

Un pasaje es un bloque de texto de una sola página: nunca cruza la página, así su página es
la suya. Se arman sobre el texto canónico de la lectura (`norms/splitting/canonical.py`):

1. Los bloques son los párrafos del texto canónico, cortados en el límite de cada página.
   (El texto canónico ya separa un párrafo de otro por línea en blanco o por un salto
   vertical mayor que la mitad del alto de la línea.)
2. Un bloque de menos de `OFFERS_PASSAGE_MIN_CHARS` caracteres se une al siguiente de su
   página, hasta llegar al mínimo o quedarse sin siguiente.
3. Un bloque de más de `OFFERS_PASSAGE_MAX_CHARS` caracteres se parte en límite de
   oración (o, si una oración sola es más larga, en un espacio).
4. Una página sin texto (ilegible, en blanco) no genera pasajes.

El texto de un pasaje es siempre el recorte `canonical_text[char_start:char_end]`: lo que
se muestra es copia literal del documento (P3, REQ-039). No usa la base ni los servicios de
IA: recibe la lectura y el texto canónico y devuelve los pasajes sin vector.
"""

import re
from dataclasses import dataclass

from django.conf import settings

from evaluon.norms.reading import ORIGIN_OCR

# Fin de oración: el espacio que sigue a un punto, signo de cierre, punto y coma o dos puntos.
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")


@dataclass(frozen=True)
class PassageSpec:
    """Un pasaje todavía sin vector: su orden, su clave `p{página}/b{n}`, su página, su
    lugar en el texto canónico, su texto y el origen y la confianza del reconocimiento."""

    order: int
    key: str
    page: int
    char_start: int
    char_end: int
    text: str
    text_origin: str
    ocr_confidence_min: float | None
    ocr_confidence_avg: float | None


def _blocks(canonical):
    """Los bloques `(página, inicio, fin)` en el orden del documento: cada párrafo del
    texto canónico, cortado donde cambia la página."""
    blocks = []
    lines = [line for line in canonical.lines if line.page is not None]
    for start, end in canonical.paragraphs:
        current = None
        for line in lines:
            if line.start < start or line.end > end or line.end <= line.start:
                continue
            if current is not None and current[0] == line.page:
                current[2] = line.end
            else:
                if current is not None:
                    blocks.append(tuple(current))
                current = [line.page, line.start, line.end]
        if current is not None:
            blocks.append(tuple(current))
    return blocks


def _merge_small(blocks, text, minimum):
    """Une cada bloque de menos de `minimum` caracteres con el siguiente de su página."""
    merged = []
    index = 0
    while index < len(blocks):
        page, start, end = blocks[index]
        index += 1
        while (end - start < minimum and index < len(blocks)
               and blocks[index][0] == page):
            end = blocks[index][2]
            index += 1
        merged.append((page, start, end))
    return merged


def _sentences(text, start, end):
    """Las oraciones de `text[start:end]` como posiciones `(inicio, fin)`, sin el espacio
    que las separa."""
    spans, position = [], start
    for match in _SENTENCE_END.finditer(text, start, end):
        spans.append((position, match.start()))
        position = match.end()
    spans.append((position, end))
    return [(s, e) for s, e in spans if e > s]


def _hard_split(text, start, end, maximum):
    """Parte un tramo sin límite de oración en espacios, en tramos de hasta `maximum`."""
    if end - start <= maximum:
        return [(start, end)]
    pieces, position = [], start
    while end - position > maximum:
        cut = text.rfind(" ", position + 1, position + maximum + 1)
        if cut <= position:
            cut = position + maximum
        pieces.append((position, cut))
        position = cut
        while position < end and text[position].isspace():
            position += 1
    if position < end:
        pieces.append((position, end))
    return pieces


def _split_long(text, start, end, maximum):
    """Parte `text[start:end]` en tramos de hasta `maximum` caracteres, en límite de
    oración; una oración más larga se parte en un espacio."""
    if end - start <= maximum:
        return [(start, end)]
    pieces, current = [], None
    for sentence_start, sentence_end in _sentences(text, start, end):
        for piece_start, piece_end in _hard_split(text, sentence_start, sentence_end,
                                                  maximum):
            if current is None:
                current = [piece_start, piece_end]
            elif piece_end - current[0] <= maximum:
                current[1] = piece_end
            else:
                pieces.append(tuple(current))
                current = [piece_start, piece_end]
    if current is not None:
        pieces.append(tuple(current))
    return pieces


def _origin_and_confidence(canonical, start, end):
    lines = canonical.lines_in(start, end)
    recognized = [line.confidence for line in lines
                  if line.origin == ORIGIN_OCR and line.confidence is not None]
    if recognized:
        return ORIGIN_OCR, min(recognized), sum(recognized) / len(recognized)
    origins = [line.origin for line in lines]
    origin = ORIGIN_OCR if ORIGIN_OCR in origins else (origins[0] if origins else "pdf_text")
    return origin, None, None


def build_passages(canonical):
    """Los pasajes de un texto canónico (`CanonicalText`), en el orden del documento."""
    text = canonical.text
    minimum = settings.OFFERS_PASSAGE_MIN_CHARS
    maximum = settings.OFFERS_PASSAGE_MAX_CHARS
    blocks = _merge_small(_blocks(canonical), text, minimum)
    specs, per_page = [], {}
    for page, start, end in blocks:
        for piece_start, piece_end in _split_long(text, start, end, maximum):
            snippet = text[piece_start:piece_end]
            if not snippet.strip():
                continue
            per_page[page] = per_page.get(page, 0) + 1
            origin, low, average = _origin_and_confidence(canonical, piece_start, piece_end)
            specs.append(PassageSpec(
                order=len(specs) + 1,
                key=f"p{page}/b{per_page[page]}",
                page=page,
                char_start=piece_start,
                char_end=piece_end,
                text=snippet,
                text_origin=origin,
                ocr_confidence_min=None if low is None else round(low, 2),
                ocr_confidence_avg=None if average is None else round(average, 2),
            ))
    return specs
