"""Pasajes de búsqueda y sus vectores (REQ-003, REQ-005, REQ-008, REQ-012; plan 001,
"Unidades base, incisos y pasajes", "Conteo de tokens" y `norms_passage`).

Los pasajes solo sirven para buscar: nunca se muestran ni se citan. Cada unidad base da
uno o más pasajes, cada uno con:

- su encabezado de contexto, norma y ruta ("Disposición AFIP 247/2022, Anexo, Cláusula
  transitoria"), armado por `passage_header`;
- su texto, un tramo del texto propio de la unidad base: el de toda la unidad, salvo en
  una unidad que contiene otras unidades base (un anexo con artículos), que aporta solo
  lo que va antes de la primera, para que ningún texto quede en pasajes de dos unidades;
- el tramo que cubre (`char_start`, `char_end`), relativo al texto de la unidad;
- su vector, calculado por el servicio `embeddings` sobre `passage_document(header,
  text)`, que es también lo que puntúa el reranker en la recuperación;
- el nombre y la huella del modelo que calculó el vector.

Partición (T-031). Si el encabezado más el texto propio entra en `PASSAGE_MAX_TOKENS`, la
unidad da un solo pasaje. Si no, el texto se divide en tramos: primero en los límites de
sus incisos (unidades `inciso` hijas); el tramo que solo no entra se divide en párrafos
(`\\n`), el párrafo que no entra en oraciones y la oración que no entra entre palabras.
Nunca se corta una palabra. Los tramos se acumulan, en orden, mientras el encabezado más
el texto acumulado entre en el límite. El pasaje siguiente empieza repitiendo los
últimos tramos completos del anterior (párrafos, oraciones o palabras) que sumen hasta
`PASSAGE_OVERLAP_TOKENS`, sin que el pasaje pase nunca de `PASSAGE_MAX_TOKENS`: si no
entran, se repite menos. Ningún texto queda afuera.

Los tokens se cuentan con `count_tokens` del cliente de embeddings, siempre sobre el
texto real que se va a mandar (`passage_document(header, text)`), no sumando cuentas de
tramos sueltos: así ningún pasaje supera el límite aunque el modelo cuente distinto
en las uniones. El solape se cuenta sobre su texto, sin el encabezado.

Los incisos no generan pasajes. Una unidad base sin texto propio no da pasaje (una raíz
`anexo` sin carátula, por ejemplo).

Nada de este módulo confirma una validación: `services/validation.py` arma los pasajes,
pide los vectores antes de abrir la transacción y los guarda dentro de ella.

El cliente de embeddings se usa importando el módulo (`embeddings.embed(...)`,
`embeddings.count_tokens(...)`), para que el doble de `tests/conftest.py` lo reemplace.
"""

import re
from dataclasses import dataclass

from django.conf import settings

from evaluon.ai import embeddings
from evaluon.norms.models import Passage, Unit, UnitType

# Separador de los tramos de `norms_unit.path` ("Anexo › Título II › Artículo 50").
PATH_SEPARATOR = " › "
# Separador de los tramos en el encabezado de un pasaje.
HEADER_SEPARATOR = ", "

def norm_name(norm):
    """Nombre de la norma para el encabezado: su nombre de cita, tal como lo escribió la
    persona al cargarla ("Disposición AFIP 297/03"). Sin reglas propias de tipo,
    organismo ni año (T-055)."""
    return norm.citation


def passage_header(norm, unit):
    """Encabezado de contexto de un pasaje: el nombre de la norma y la ruta de la
    unidad, con sus tramos separados por comas."""
    return HEADER_SEPARATOR.join([norm_name(norm), *unit.path.split(PATH_SEPARATOR)])


def passage_document(header, text):
    """Texto con que se calcula el vector de un pasaje y con que el reranker lo puntúa:
    encabezado y texto unidos por un salto de línea."""
    return f"{header}\n{text}"


@dataclass(frozen=True)
class PassageDraft:
    """Pasaje armado y todavía sin guardar. `char_start` y `char_end` son posiciones
    dentro del texto de la unidad."""

    unit: Unit
    order: int
    char_start: int
    char_end: int
    header: str
    text: str


def _own_text_end(unit, base_children):
    """Fin del texto propio de una unidad base, relativo a su texto: el comienzo de la
    primera unidad base que contiene, o el fin de su texto. Sin espacios al final."""
    end = len(unit.text)
    starts = [c.char_start - unit.char_start for c in base_children]
    inside = [s for s in starts if 0 <= s < end]
    if inside:
        end = min(inside)
    return len(unit.text[:end].rstrip())


# Niveles de corte de un tramo que no entra, de mayor a menor.
_INCISO, _PARAGRAPH, _SENTENCE, _WORD = range(4)
# Fin de oración: punto, punto y coma, dos puntos, cierre de pregunta o exclamación,
# seguido de espacio y de una mayúscula o un signo de apertura. Así "art. 4" o "N° 5"
# no cortan.
_SENTENCE_BREAK = re.compile(r"(?<=[.;:!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡“\"«])")
_PARAGRAPH_BREAK = re.compile(r"\n")
_WORD_BREAK = re.compile(r"\s+")


def _cuts(pattern, text, start, end):
    """Posiciones de `text[start:end]` donde empieza un tramo nuevo según `pattern`."""
    return [start + m.end() for m in pattern.finditer(text[start:end])]


def _ranges(text, start, end, cuts):
    """Tramos de `text[start:end]` cortados en `cuts`, sin espacios en los bordes; los
    tramos vacíos se descartan."""
    bounds = [start, *sorted({c for c in cuts if start < c < end}), end]
    ranges = []
    for a, b in zip(bounds, bounds[1:]):
        piece = text[a:b]
        a2 = a + len(piece) - len(piece.lstrip())
        b2 = b - (len(piece) - len(piece.rstrip()))
        if a2 < b2:
            ranges.append((a2, b2))
    return ranges


def _level_cuts(level, text, start, end, inciso_starts):
    if level == _INCISO:
        return inciso_starts
    if level == _PARAGRAPH:
        return _cuts(_PARAGRAPH_BREAK, text, start, end)
    if level == _SENTENCE:
        return _cuts(_SENTENCE_BREAK, text, start, end)
    return _cuts(_WORD_BREAK, text, start, end)


def _atoms(text, start, end, level, fits, inciso_starts):
    """Tramos mínimos de `text[start:end]`: cada uno entra solo en el límite o es una
    palabra. Un tramo que no entra se divide en el nivel siguiente."""
    ranges = _ranges(text, start, end, _level_cuts(level, text, start, end, inciso_starts))
    if level == _WORD:
        return ranges
    if len(ranges) == 1:  # este nivel no corta: se pasa al siguiente sin contar de nuevo
        return _atoms(text, *ranges[0], level + 1, fits, inciso_starts)
    atoms = []
    for a, b in ranges:
        if fits(a, b):
            atoms.append((a, b))
        else:
            atoms.extend(_atoms(text, a, b, level + 1, fits, inciso_starts))
    return atoms


def _overlap_starts(text, start, end, atoms, passage_start):
    """Comienzos posibles del pasaje siguiente dentro del tramo `[start, end)` de un
    pasaje: los de sus últimos tramos completos (párrafos, oraciones o palabras) que
    suman hasta `PASSAGE_OVERLAP_TOKENS`, del solape mayor al menor."""
    limit = settings.PASSAGE_OVERLAP_TOKENS
    if limit <= 0:
        return []
    cuts = [a for a, _ in atoms]
    cuts += _cuts(_PARAGRAPH_BREAK, text, start, end)
    cuts += _cuts(_SENTENCE_BREAK, text, start, end)
    starts = []
    for a, _ in reversed(_ranges(text, start, end, cuts)):
        if a <= passage_start or embeddings.count_tokens(text[a:end]) > limit:
            break
        starts.append(a)
    return list(reversed(starts))


def _split(text, header, inciso_starts):
    """Tramos `(char_start, char_end)` de los pasajes de `text`, relativos a `text`."""
    limit = settings.PASSAGE_MAX_TOKENS

    def fits(a, b):
        return embeddings.count_tokens(passage_document(header, text[a:b])) <= limit

    if fits(0, len(text)):
        return [(0, len(text))]
    atoms = _atoms(text, 0, len(text), _INCISO, fits, inciso_starts)
    spans = []
    overlap = []
    i = 0
    while i < len(atoms):
        first_start, first_end = atoms[i]
        start = next((s for s in overlap if fits(s, first_end)), first_start)
        end = first_end
        j = i + 1
        while j < len(atoms) and fits(start, atoms[j][1]):
            end = atoms[j][1]
            j += 1
        spans.append((start, end))
        if j < len(atoms):
            overlap = _overlap_starts(text, first_start, end, atoms[i:j], start)
        i = j
    return spans


def build_passages(reading):
    """Pasajes de las unidades base de `reading`, en el orden del documento. Una unidad
    base sin texto propio no da pasaje; una larga da varios (ver la partición arriba).
    Cuenta tokens con el servicio `embeddings` y propaga sus errores (`evaluon.ai`)."""
    norm = reading.document.norm
    units = list(reading.units.order_by("order"))
    base_units = [u for u in units if u.unit_type != UnitType.INCISO]
    children = {}
    incisos = {}
    for unit in units:
        if unit.parent_id is None:
            continue
        target = incisos if unit.unit_type == UnitType.INCISO else children
        target.setdefault(unit.parent_id, []).append(unit)

    drafts = []
    for unit in base_units:
        end = _own_text_end(unit, children.get(unit.pk, []))
        if end == 0:
            continue
        text = unit.text[:end]
        header = passage_header(norm, unit)
        inciso_starts = [
            c.char_start - unit.char_start for c in incisos.get(unit.pk, [])
            if 0 < c.char_start - unit.char_start < end
        ]
        for order, (start, stop) in enumerate(_split(text, header, inciso_starts), start=1):
            drafts.append(PassageDraft(
                unit=unit,
                order=order,
                char_start=start,
                char_end=stop,
                header=header,
                text=text[start:stop],
            ))
    return drafts


def embed_passages(drafts):
    """Vectores de los pasajes, uno por pasaje y en el mismo orden, en un solo pedido al
    servicio `embeddings`. Propaga los errores propios del cliente (`evaluon.ai`)."""
    return embeddings.embed([passage_document(d.header, d.text) for d in drafts])


def embedding_model():
    """Nombre y huella del archivo del modelo que calcula los vectores."""
    return settings.EMBEDDINGS_MODEL, settings.EMBEDDINGS_MODEL_SHA256


def save_passages(drafts, vectors):
    """Guarda los pasajes con su vector y el modelo que lo calculó. La base calcula la
    columna `tsv`."""
    if len(vectors) != len(drafts):
        raise ValueError("La cantidad de vectores no coincide con la de pasajes.")
    model, revision = embedding_model()
    return Passage.objects.bulk_create([
        Passage(
            unit=draft.unit,
            order=draft.order,
            char_start=draft.char_start,
            char_end=draft.char_end,
            header=draft.header,
            text=draft.text,
            embedding=vector,
            embedding_model=model,
            embedding_revision=revision,
        )
        for draft, vector in zip(drafts, vectors)
    ])
