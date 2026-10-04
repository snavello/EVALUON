"""Ubicar un fragmento literal dentro de un tramo (REQ-025; plan 003, "Extracción: qué
recibe y qué devuelve el modelo" y "Cita"; ADR-0019, decisión 3).

El modelo no redacta el requisito: copia un fragmento del tramo. El sistema lo busca
exacto dentro del texto del tramo y, si lo encuentra, guarda sus posiciones; desde ahí se
muestra el texto del pliego, nunca el del modelo. Los espacios de los extremos del
fragmento no cuentan; el interior se compara tal cual (mayúsculas, signos, espacios y
saltos de línea).

Las posiciones que devuelve `locate` son relativas al texto del tramo; `absolute`
las lleva al texto canónico de la lectura, donde `text[start:end]` es el texto de la cita.
"""

WIDE = "cita_amplia"


def locate(text, quote, used=()):
    """Posiciones `(inicio, fin)` de `quote` dentro de `text`, o `None` si no está o está
    vacío. Si aparece más de una vez, la primera aparición cuyas posiciones no estén en
    `used`."""
    quote = (quote or "").strip()
    if not quote:
        return None
    start = text.find(quote)
    while start != -1:
        span = (start, start + len(quote))
        if span not in used:
            return span
        start = text.find(quote, start + 1)
    return None


def absolute(segment, span):
    """Lleva las posiciones `span` (relativas al tramo) al texto canónico de la lectura."""
    return (segment.char_start + span[0], segment.char_start + span[1])


def whole(segment):
    """Posiciones del tramo entero en el texto canónico: la cita amplia."""
    return (segment.char_start, segment.char_end)
