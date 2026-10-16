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
contiguas que son una continuación explícita (`is_continuation`): las que empiezan con una
anáfora («La misma», «Los mismos», «Las mismas», «Dicho», «Dicha», «Este», «Esto», «Ello») o en
minúscula sin ser la letra de un inciso («b)», «c.», «ii)»). Una oración que empieza con
«Deberá…» sin anáfora ya no se une por código (decisión del Coordinador, verificación de
T-234): puede abrir otro asunto, y la instrucción de extracción le pide al modelo citar juntas
las del mismo asunto. La oración que el modelo señaló puede ser la continuadora; entonces la
unidad incluye la anterior. Una unidad que pasa de `ASSESSMENT_CITATION_MAX_CHARS` caracteres no se usa: queda el
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

# Anáforas: la oración remite de manera explícita a la anterior.
_ANAPHORA = re.compile(
    r"(?:la\s+misma|los\s+mismos|las\s+mismas|dich[oa]s?|este|esto|ello"
    # T-240 (H-6): «Tal manifestación…», «Tales documentos…»; no «Tal como…», «Tal vez…».
    r"|tal(?:es)?\b(?!\s+(?:como|cual|vez|que)\b))\b", re.IGNORECASE)
# T-240 (H-6): «dicho», «dicha», «dichos» o «dichas» en las primeras palabras («El porcentaje de
# dicha cotización…») remiten a la oración anterior aunque no abran la oración.
_EARLY_DICHO = re.compile(r"^(?:\S+\s+){0,5}?dich[oa]s?\b", re.IGNORECASE)
# La letra de un inciso en línea («b)», «c.», «ii)») no es una oración que continúa.
_INLINE_LABEL = re.compile(r"(?:[a-zñ]|[ivxlcdm]{2,4})[).](?=\s|$)")
# Una oración que empieza con un verbo de obligación no tiene sujeto propio, pero no se une
# sola: puede abrir otro asunto.
_VERB_FIRST = re.compile(r"deb(?:e|en|er[aá]|er[aá]n)\b", re.IGNORECASE)


def is_continuation(sentence):
    """Si la oración es una continuación explícita de la anterior: empieza con una anáfora
    («La misma», «Los mismos», «Las mismas», «Dicho», «Dicha», «Este», «Esto», «Ello») o en
    minúscula sin ser la letra de un inciso («b)», «c.», «ii)»). «Deberá…» sin anáfora no lo
    es (`lacks_subject`)."""
    sentence = sentence.lstrip()
    if not sentence or _INLINE_LABEL.match(sentence):
        return False
    first = sentence[0]
    if first.isalpha() and first.islower():
        return True
    return bool(_ANAPHORA.match(sentence) or _EARLY_DICHO.match(sentence))


def lacks_subject(sentence):
    """Si la oración empieza sin sujeto propio: una continuación explícita
    (`is_continuation`) o un verbo de obligación («Deberá…»), que no se une por código pero
    tampoco se entiende sola. Lo usan el encabezado del punto y la medida de pedazos."""
    return is_continuation(sentence) or bool(_VERB_FIRST.match(sentence.lstrip()))


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
    """Si la primera oración del texto empieza sin sujeto propio (`lacks_subject`)."""
    spans = sentence_spans(text)
    return bool(spans) and lacks_subject(text[spans[0][0]:spans[0][1]])


def may_need_heading(segment):
    """Si el tramo podría necesitar el encabezado de su punto, sin mirar a su padre: tiene
    padre y es una viñeta o un inciso, o su primera oración empieza sin sujeto propio
    (`lacks_subject`)."""
    return bool(parent_key(segment.key)) and (
        segment.segment_type == "vineta" or _starts_without_subject(segment.text))


def needs_heading(segment, parent_text):
    """Si la oración del tramo sola no se entiende: es un inciso o una viñeta de una lista
    cuyo encabezado (`parent_text`) termina en «:», o su primera oración empieza sin sujeto
    propio (`lacks_subject`)."""
    if segment.segment_type == "vineta" and parent_text.rstrip().endswith(":"):
        return True
    return _starts_without_subject(segment.text)


# T-240: la letra de un inciso que abre un párrafo («b) …»), y el número de un párrafo hermano.
_INCISO_PARAGRAPH = re.compile(r"\s*[a-zñ]\)(?=\s)")
_PARAGRAPH_KEY = re.compile(r"^(.*/p-)(\d+)$")
# Cuántos párrafos hacia atrás se busca el que introduce una lista de incisos.
INTRO_LOOKBACK = 40


def _sibling_intro(segment, lookup):
    """El párrafo que introduce la lista de incisos a la que pertenece `segment` (T-240): el
    primero hacia atrás, entre sus hermanos (`…/p-N`), que no es otro inciso. Es lo que pasa en los
    formularios y anexos, donde la oración que introduce la lista («No podrán contratar:») es un
    párrafo hermano y no el tramo padre. `None` si el tramo no es un inciso o no hay."""
    if not _INCISO_PARAGRAPH.match(segment.text):
        return None
    mark = _PARAGRAPH_KEY.match(segment.key)
    if not mark:
        return None
    prefix, number = mark.group(1), int(mark.group(2))
    for previous in range(number - 1, max(number - INTRO_LOOKBACK, 0), -1):
        sibling = lookup(f"{prefix}{previous}")
        if sibling is None:
            return None
        if not _INCISO_PARAGRAPH.match(sibling.text):
            return sibling if sibling.text.strip() else None
    return None


def may_need_sibling_intro(segment):
    """Si el tramo es un inciso en un párrafo hermano de la lista (T-240, `_sibling_intro`)."""
    return bool(_INCISO_PARAGRAPH.match(segment.text) and _PARAGRAPH_KEY.match(segment.key))


# T-258 (H5 del comité): un párrafo de ítems de una lista, como los de un anexo cuyo primer párrafo
# dice quién entrega qué y termina en «:» y los siguientes son las viñetas. Abre, en sus primeros
# caracteres, con una viñeta (un carácter de área privada que deja la extracción del PDF, o un
# punto, un cuadradito o un círculo de viñeta), o con el número de un ítem («1.», «2)»).
_LIST_BULLET = re.compile("[\uf000-\uf8ff\u2022\u25aa\u25e6]")
_NUMBERED_ITEM = re.compile(r"\s*\d{1,2}[.)]\s+\S")
# Hasta dónde se busca la viñeta: puede venir después de un rótulo corto («Documentación del
# personal: …», y después la viñeta).
LIST_BULLET_WITHIN = 80


def is_list_paragraph(text):
    """Si el párrafo es de ítems de una lista: una viñeta en sus primeros `LIST_BULLET_WITHIN`
    caracteres, o el número de un ítem al principio."""
    return bool(_LIST_BULLET.search(text[:LIST_BULLET_WITHIN]) or _NUMBERED_ITEM.match(text))


def _list_intro(segment, lookup):
    """El párrafo que introduce la lista de ítems a la que pertenece `segment` (T-258, H5): hacia
    atrás entre sus hermanos (`…/p-N`), saltando los otros párrafos de ítems, el primero que no es
    de ítems, si termina en «:». Así los ítems de un anexo viajan con el párrafo que dice quién los
    entrega y cuándo. `None` si el tramo no es de ítems o si el párrafo que abre la serie no
    termina en «:»."""
    if not is_list_paragraph(segment.text):
        return None
    mark = _PARAGRAPH_KEY.match(segment.key)
    if not mark:
        return None
    prefix, number = mark.group(1), int(mark.group(2))
    for previous in range(number - 1, max(number - INTRO_LOOKBACK, 0), -1):
        sibling = lookup(f"{prefix}{previous}")
        if sibling is None:
            return None
        if is_list_paragraph(sibling.text):
            continue
        return sibling if sibling.text.rstrip().endswith(":") else None
    return None


def heading_of(segment, lookup):
    """El encabezado del punto de `segment` (el texto de su tramo padre, sin el número de
    la cláusula y en una línea) si la oración sola no se entiende, o "". `lookup(clave)`
    devuelve el tramo de esa clave en la misma lectura o `None`; solo se llama si el tramo
    podría necesitar el encabezado (`may_need_heading`). Un inciso («b) …») cuyo padre no lo
    introduce toma el párrafo hermano que abre la lista (T-240); un párrafo de ítems de una lista
    de un anexo, el párrafo que la introduce si termina en «:» (T-258, `_list_intro`). No se cita:
    es contexto."""
    if may_need_heading(segment):
        parent = lookup(parent_key(segment.key))
        if parent is not None and parent.text.strip() and needs_heading(segment, parent.text):
            return _shortened(parent.text[label_end(parent.text):])
    intro = _sibling_intro(segment, lookup) or _list_intro(segment, lookup)
    if intro is None:
        return ""
    return _shortened(intro.text[label_end(intro.text):])


def piece_problem(text, start, end):
    """Si la cita `[start, end)` del `text` de su tramo es un pedazo (REQ-101, T-238).

    Comprobación mecánica con la unidad de sentido de T-234 (`proposal.sentences`): una cita
    completa empieza donde empieza una oración (o al comienzo del tramo, con su número de
    cláusula), termina donde termina una oración y es la unidad que calcula el sistema: ni
    arranca con una oración sin sujeto propio que tiene la anterior en el tramo («Deberán…»,
    «La misma…», una minúscula) ni deja afuera la oración corta que la continúa de manera
    explícita («La misma…», «Esto…»). Devuelve `None` si es completa o el problema:
    `"empieza_en_medio"`, `"termina_en_medio"`, `"sin_sujeto"` (empieza con una oración sin
    sujeto propio), `"separa_condiciones"` (deja afuera la oración corta que la continúa) o
    `"vacia"`. Un texto sin oraciones (una tabla) no tiene límites que comprobar."""
    chunk = text[start:end]
    if not chunk.strip():
        return "vacia"
    first = start + len(chunk) - len(chunk.lstrip())
    last = end - (len(chunk) - len(chunk.rstrip()))
    spans = sentence_spans(text)
    if not spans:
        return None
    if first != 0 and first not in {begin for begin, _ in spans}:
        return "empieza_en_medio"
    if last not in {finish for _, finish in spans}:
        return "termina_en_medio"
    opening = next((span for span in spans if span[0] == first), None)
    if opening is not None and opening != spans[0] and lacks_subject(text[opening[0]:opening[1]]):
        return "sin_sujeto"
    unit = expand_to_sentence(text, (first, last), max_chars=len(text)).unit
    if unit is None:
        return None
    if unit[0] < first:
        return "sin_sujeto"
    if unit[1] > last:
        return "separa_condiciones"
    return None
