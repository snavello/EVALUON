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

**Caracteres de área privada** (T-258, H5 del comité): la extracción del PDF deja viñetas como
caracteres de área privada de Unicode (U+F000 a U+F8FF), que el modelo no reproduce. En la propuesta
de la matriz no se le muestran al modelo (`visible`) y no cuentan al ubicar sus citas (`locate_unit`,
que llama a `locate` con `ignore_private`): la cita guardada sigue siendo el recorte del texto
canónico, con la viñeta adentro si cae en el medio. Los demás usos de `locate` (la evaluación, la
medición) comparan como antes.
"""

import re

from evaluon.tenders.proposal import sentences

WIDE = "cita_amplia"

# Caracteres de área privada de Unicode que deja la extracción del PDF (viñetas): ni se muestran al
# modelo ni cuentan al comparar (T-258).
PRIVATE_USE = re.compile("[\uf000-\uf8ff]")


def is_private_use(char):
    """Si `char` es un carácter de área privada (U+F000 a U+F8FF)."""
    return "\uf000" <= char <= "\uf8ff"


def visible(text):
    """El texto tal como lo ve el modelo: sin los caracteres de área privada (T-258)."""
    return PRIVATE_USE.sub("", text)


def _collapse(text, ignore_private=False):
    """El texto con cada secuencia de espacios en blanco reducida a un espacio (y, con
    `ignore_private`, sin los caracteres de área privada, T-258), y para cada carácter del resultado
    su posición en el texto original."""
    chars, positions = [], []
    previous_space = False
    for index, char in enumerate(text):
        if ignore_private and is_private_use(char):
            continue
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


def locate(text, quote, used=(), ignore_private=False):
    """Posiciones `(inicio, fin)` de `quote` dentro de `text`, o `None` si no está o está
    vacío. Los espacios de los extremos de `quote` no cuentan y toda secuencia de espacios
    en blanco, dentro de `quote` o de `text`, vale por un espacio. Si aparece más de una
    vez, la primera aparición cuyas posiciones no estén en `used`. Con `ignore_private`, los
    caracteres de área privada no cuentan, ni en `quote` ni en `text` (T-258)."""
    quote = visible(quote or "") if ignore_private else (quote or "")
    needle = " ".join(quote.split())
    if not needle:
        return None
    haystack, positions = _collapse(text, ignore_private)
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
    fragmento y la ampliación no trae unidad. Los caracteres de área privada no cuentan (T-258)."""
    span = locate(text, quote, used, ignore_private=True)
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
