"""Oraciones y unidad de sentido de un tramo del pliego (REQ-101; plan 015, T-234; ADR-0054,
reglas 1 a 3).

Lo comparten la matriz (`extraction`, `completeness`, `filter`, `run`) y, más adelante, la
evaluación. Todo corre en CPU, sin modelo, y trabaja sobre el texto literal de un tramo
(`Segment.text`): las posiciones que recibe y devuelve son relativas a ese texto.

**Oración.** Termina en un punto, un cierre de exclamación o de pregunta seguido de espacio,
salvo tras una abreviatura conocida (`ABBREVIATIONS`) o una inicial ("art.", "S.A.",
"J. Pérez"). El número de la cláusula, la viñeta y la letra del inciso que abren el tramo no
son parte de la primera oración.

**Unidad de sentido** (`expand_to_sentence`). El modelo señala un fragmento; el sistema lo
amplía a la oración completa (a las que toca, si cruza varias) y le suma las oraciones cortas
contiguas que siguen el mismo asunto: las que empiezan sin sujeto propio (en minúscula, o con
«y», «e», «o», «ni»), con «Deberá», «Deberán», «La misma…» o «Esto…» (`is_continuation`).
La oración que el modelo señaló puede ser la continuadora; entonces la unidad incluye la
anterior. Una unidad que pasa de `ASSESSMENT_CITATION_MAX_CHARS` caracteres no se usa: queda el
fragmento del modelo y se avisa (`Expansion.too_long`) para que la Comisión lo revise. Así una
enumeración, "cuatro patas, dos ojos y de color marrón", es una sola fila.

El texto de una tabla no tiene oraciones: sus celdas son líneas, y la cita de un tramo `tabla`
queda en el fragmento del modelo (`quotes.locate_unit(..., expand=False)`).

**Encabezado** (`heading_of`). Un tramo cuya oración sola no se entiende (un inciso o viñeta
de una lista cuyo encabezado termina en «:», o una oración que empieza en minúscula, con
«Esto», «La misma» o «Deberá») muestra el texto del tramo padre, que se toma por la clave del
tramo. Es contexto: nunca se cita.
"""

import re
from dataclasses import dataclass

from django.conf import settings

# --- Oraciones ----------------------------------------------------------------------------------

SENTENCE_END = re.compile(r"[.!?]\s+")
_WORD_BEFORE = re.compile(r"([^\W\d_]+(?:\.[^\W\d_]+)*)\.$")

# Abreviaturas que no terminan la oración aunque lleven punto y espacio detrás (en
# minúscula y sin el punto final); una inicial suelta ("S.A.", "J. Pérez") tampoco la termina.
ABBREVIATIONS = frozenset({
    "art", "arts", "inc", "incs", "dec", "decs", "res", "disp", "nro", "nros", "núm", "num",
    "cap", "apdo", "pto", "ptos", "pág", "pag", "págs", "ap", "cód", "cod", "ej", "dto",
    "lic", "dr", "dra", "ing", "sr", "sra", "ref", "vs", "s.a", "s.r.l", "s.a.s", "c.u.i.t",
    "cons", "pár", "par", "anex", "exp", "expte", "fs", "tít", "tit", "sec", "ss", "cfr",
})


def _sentence_ends(text):
    """Las posiciones donde empieza una oración nueva: tras `.`, `!` o `?` y espacio,
    salvo cuando el punto cierra una abreviatura conocida o una inicial."""
    ends = []
    for mark in SENTENCE_END.finditer(text):
        if text[mark.start()] == ".":
            word = _WORD_BEFORE.search(text[:mark.start() + 1])
            if word:
                lower = word.group(1).lower()
                if lower in ABBREVIATIONS or all(len(p) == 1 for p in lower.split(".")):
                    continue
        ends.append(mark.end())
    return ends


def sentence_range(text, span):
    """Las oraciones del texto canónico del tramo que toca `span`, como `(primera, última)`.
    Una oración termina en un punto, un cierre de exclamación o de pregunta seguido de
    espacio, salvo tras una abreviatura (`ABBREVIATIONS`) o una inicial; las posiciones son
    las del texto del tramo."""
    ends = _sentence_ends(text)
    first = sum(1 for end in ends if end <= span[0])
    last = sum(1 for end in ends if end < span[1])
    return first, last


def sentence_bounds(text, position):
    """`(inicio, fin)` de la oración del tramo que contiene `position`, sin los espacios de
    los bordes."""
    ends = _sentence_ends(text)
    start = max([end for end in ends if end <= position], default=0)
    stop = min([end for end in ends if end > position], default=len(text))
    chunk = text[start:stop]
    start += len(chunk) - len(chunk.lstrip())
    stop -= len(chunk) - len(chunk.rstrip())
    return start, stop


# --- Oraciones de un tramo, sin su rótulo ---------------------------------------------------------

# Lo que abre un tramo antes de su primera palabra: el número de la cláusula ("1.1.",
# "10.2.1.Una vez"), la viñeta ("•", "−", "–", "-") o la letra del inciso ("a)").
_LABEL = re.compile(
    r"\s*(?:\d{1,3}(?:\.\d{1,3}){0,3}\.(?=\s|[A-ZÁÉÍÓÚÑ“\"(]|$)|[•−–\-](?=\s)|[a-zñ]\)(?=\s))"
    r"\s*")


def label_end(text):
    """Dónde termina el rótulo con que abre el tramo (número de cláusula, viñeta o letra de
    inciso), o 0 si no tiene."""
    mark = _LABEL.match(text)
    return mark.end() if mark else 0


def sentence_spans(text):
    """Las oraciones del texto como `[(inicio, fin)]`, sin los espacios de los bordes. La
    primera empieza después del rótulo del tramo (`label_end`)."""
    ends = _sentence_ends(text)
    starts = [0, *ends]
    stops = [*ends, len(text)]
    skip = label_end(text)
    spans = []
    for start, stop in zip(starts, stops):
        chunk = text[start:stop]
        begin = start + len(chunk) - len(chunk.lstrip())
        finish = stop - (len(chunk) - len(chunk.rstrip()))
        begin = max(begin, skip)
        if begin < finish:
            spans.append((begin, finish))
    return spans


# --- Oraciones que siguen el mismo asunto ----------------------------------------------------------

# Una oración corta que sigue el asunto de la anterior: el largo máximo de la continuadora.
SHORT_SENTENCE_CHARS = 300

_CONTINUES = re.compile(
    r"(?:(?:y|e|o|u|ni)\b"                          # conjunción: sin sujeto propio
    r"|deb(?:e|en|er[aá]|er[aá]n)\b"               # «Deberán…»: el sujeto es el de antes
    r"|(?:la|las|el|los)\s+mism[oa]s?\b"            # «La misma…»
    r"|lo\s+mismo\b|(?:esto|ello)\b)",              # «Esto…»
    re.IGNORECASE)


def is_continuation(sentence):
    """Si la oración empieza sin sujeto propio y sigue el asunto de la anterior: en
    minúscula, con «y», «e», «o», «u», «ni», con «Deberá» o «Deberán», con «La misma…» o con
    «Esto…»."""
    sentence = sentence.lstrip()
    if not sentence:
        return False
    first = sentence[0]
    if first.isalpha() and first.islower():
        return True
    return bool(_CONTINUES.match(sentence))


def _is_short_continuation(text, span):
    return span[1] - span[0] <= SHORT_SENTENCE_CHARS and is_continuation(text[span[0]:span[1]])


@dataclass(frozen=True)
class Expansion:
    """La unidad de sentido de un fragmento: `span` es la que se guarda como cita (la
    unidad, o el fragmento mismo si no se pudo ampliar); `unit` es la unidad que calculó el
    sistema, también cuando no se usó; `too_long` es verdadero si la unidad pasa del largo
    máximo de una cita y queda el fragmento del modelo, a revisar."""

    span: tuple
    unit: tuple | None
    too_long: bool = False


def expand_to_sentence(text, span, max_chars=None):
    """Amplía `span` (el fragmento que señaló el modelo, relativo a `text`) a la unidad de
    sentido que lo contiene: sus oraciones completas y las oraciones cortas contiguas que
    siguen el mismo asunto. Devuelve una `Expansion`. Ver el módulo."""
    limit = settings.ASSESSMENT_CITATION_MAX_CHARS if max_chars is None else max_chars
    span = (span[0], span[1])
    sentences = sentence_spans(text)
    touched = [i for i, (start, stop) in enumerate(sentences)
               if start < span[1] and stop > span[0]]
    if not touched or span[1] <= span[0]:
        return Expansion(span, None)

    def bounds(first, last):
        return (min(sentences[first][0], span[0]), max(sentences[last][1], span[1]))

    first, last = touched[0], touched[-1]
    alone = bounds(first, last)
    # La oración que el modelo señaló puede ser la que continúa a la anterior, y la que sigue
    # puede continuarla a ella: se juntan las contiguas, una por una.
    while first > 0 and _is_short_continuation(text, sentences[first]):
        first -= 1
    while last + 1 < len(sentences) and _is_short_continuation(text, sentences[last + 1]):
        last += 1
    unit = bounds(first, last)
    for candidate in (unit, alone):
        if candidate[1] - candidate[0] <= limit:
            return Expansion(candidate, unit)
    return Expansion(span, unit, too_long=True)


# --- Encabezado del punto -----------------------------------------------------------------------

# Largo máximo del encabezado que viaja con el tramo, en caracteres.
HEADING_MAX_CHARS = 400

_PART = re.compile(r"#\d+$")


def parent_key(key):
    """La clave del tramo que contiene al de clave `key` (la cláusula de una viñeta o de un
    inciso, la sección de una cláusula), o "" si no tiene. Una parte de un tramo largo
    (`sec-iii/1.1#2`) cuelga de la primera (`sec-iii/1.1`)."""
    whole = _PART.sub("", key)
    if whole != key:
        return whole
    head, slash, _ = key.rpartition("/")
    return head if slash else ""


def _shortened(text):
    """El texto en una línea y, si pasa de `HEADING_MAX_CHARS`, solo sus últimas oraciones
    (las que desembocan en la lista): si ni la última cabe, su final con puntos suspensivos."""
    text = " ".join(text.split())
    if len(text) <= HEADING_MAX_CHARS:
        return text
    kept = ""
    for start, stop in reversed(sentence_spans(text)):
        sentence = text[start:stop]
        if len(kept) + len(sentence) + 1 > HEADING_MAX_CHARS:
            break
        kept = f"{sentence} {kept}".strip()
    return kept or "…" + text[-(HEADING_MAX_CHARS - 1):]


def _starts_without_subject(text):
    """Si la primera oración del texto empieza sin sujeto propio (`is_continuation`)."""
    spans = sentence_spans(text)
    return bool(spans) and is_continuation(text[spans[0][0]:spans[0][1]])


def may_need_heading(segment):
    """Si el tramo podría necesitar el encabezado de su punto, sin mirar a su padre: tiene
    padre y es una viñeta o un inciso, o su primera oración empieza sin sujeto propio."""
    return bool(parent_key(segment.key)) and (
        segment.segment_type == "vineta" or _starts_without_subject(segment.text))


def needs_heading(segment, parent_text):
    """Si la oración del tramo sola no se entiende: es un inciso o una viñeta de una lista
    cuyo encabezado (`parent_text`) termina en «:», o su primera oración empieza sin sujeto
    propio (`is_continuation`)."""
    if segment.segment_type == "vineta" and parent_text.rstrip().endswith(":"):
        return True
    return _starts_without_subject(segment.text)


def heading_of(segment, lookup):
    """El encabezado del punto de `segment` (el texto de su tramo padre, sin el número de
    la cláusula y en una línea) si la oración sola no se entiende, o "". `lookup(clave)`
    devuelve el tramo de esa clave en la misma lectura o `None`; solo se llama si el tramo
    podría necesitar el encabezado (`may_need_heading`). No se cita: es contexto."""
    if not may_need_heading(segment):
        return ""
    parent = lookup(parent_key(segment.key))
    if parent is None or not parent.text.strip():
        return ""
    if not needs_heading(segment, parent.text):
        return ""
    return _shortened(parent.text[label_end(parent.text):])
