"""Ubicar un fragmento literal dentro de un tramo (REQ-025; plan 003, "Extracción: qué
recibe y qué devuelve el modelo" y "Cita"; ADR-0019, decisión 3).

El modelo no redacta el requisito: copia un fragmento del tramo. El sistema lo busca dentro
del texto del tramo y, si lo encuentra, guarda sus posiciones; desde ahí se muestra el texto
del pliego, nunca el del modelo.

La búsqueda tolera una sola diferencia: los espacios y los saltos de línea. El modelo suele
juntar o separar líneas, así que el tramo y la cita se comparan con toda secuencia de
espacios en blanco colapsada a un espacio, y la posición encontrada se lleva de vuelta al
texto del tramo. Las letras, las tildes, las mayúsculas y la puntuación se comparan tal
cual. Lo que se guarda como cita es siempre el recorte exacto del texto canónico, así que
sigue siendo literal.

Las posiciones que devuelve `locate` son relativas al texto del tramo; `absolute`
las lleva al texto canónico de la lectura, donde `text[start:end]` es el texto de la cita.

`locate_unit` ubica el fragmento y lo amplía a su unidad de sentido (T-234, REQ-101; ADR-0054,
reglas 1 y 3): la oración completa y las oraciones cortas contiguas del mismo asunto
(`sentences.expand_to_sentence`). Sigue siendo un recorte contiguo del texto del tramo, así que
la cita guardada es literal.
"""

from evaluon.tenders.proposal import sentences

WIDE = "cita_amplia"


def _collapse(text):
    """El texto con cada secuencia de espacios en blanco reducida a un espacio, y para cada
    carácter del resultado su posición en el texto original."""
    chars, positions = [], []
    previous_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if previous_space:
                continue
            chars.append(" ")
            previous_space = True
        else:
            chars.append(char)
            previous_space = False
        positions.append(index)
    return "".join(chars), positions


def locate(text, quote, used=()):
    """Posiciones `(inicio, fin)` de `quote` dentro de `text`, o `None` si no está o está
    vacío. Los espacios de los extremos de `quote` no cuentan y toda secuencia de espacios
    en blanco, dentro de `quote` o de `text`, vale por un espacio. Si aparece más de una
    vez, la primera aparición cuyas posiciones no estén en `used`."""
    needle = " ".join((quote or "").split())
    if not needle:
        return None
    haystack, positions = _collapse(text)
    start = haystack.find(needle)
    while start != -1:
        span = (positions[start], positions[start + len(needle) - 1] + 1)
        if span not in used:
            return span
        start = haystack.find(needle, start + 1)
    return None


def locate_unit(text, quote, used=(), expand=True):
    """Ubica `quote` como `locate` y la amplía a su unidad de sentido. Devuelve
    `(fragmento, Expansion)`, con las posiciones del fragmento que señaló el modelo y la
    ampliación (`sentences.Expansion`), o `None` si `quote` no está en `text`. Con
    `expand` falso (el texto de una tabla, que no tiene oraciones) la cita queda en el
    fragmento y la ampliación no trae unidad."""
    span = locate(text, quote, used)
    if span is None:
        return None
    if not expand:
        return span, sentences.Expansion(span, None)
    return span, sentences.expand_to_sentence(text, span)


def absolute(segment, span):
    """Lleva las posiciones `span` (relativas al tramo) al texto canónico de la lectura."""
    return (segment.char_start + span[0], segment.char_start + span[1])


def whole(segment):
    """Posiciones del tramo entero en el texto canónico: la cita amplia."""
    return (segment.char_start, segment.char_end)
