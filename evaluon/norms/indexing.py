"""Pasajes de búsqueda y sus vectores (REQ-005, REQ-012; plan 001, "Unidades base,
incisos y pasajes" y `norms_passage`).

Los pasajes solo sirven para buscar: nunca se muestran ni se citan. En esta versión hay
un pasaje por unidad base, con:

- su encabezado de contexto, norma y ruta ("Disposición AFIP 247/2022, Anexo, Cláusula
  transitoria"), armado por `passage_header`;
- su texto, que es el texto propio de la unidad base: el de toda la unidad, salvo en una
  unidad que contiene otras unidades base (un anexo con artículos), que aporta solo lo
  que va antes de la primera, para que ningún texto quede en pasajes de dos unidades;
- su vector, calculado por el servicio `embeddings` sobre `passage_document(header,
  text)`, que es también lo que puntúa el reranker en la recuperación;
- el nombre y la huella del modelo que calculó el vector.

Los incisos no generan pasajes. La partición de las unidades largas en varios pasajes
de hasta `PASSAGE_MAX_TOKENS` es de T-031.

Nada de este módulo confirma una validación: `services/validation.py` arma los pasajes,
pide los vectores antes de abrir la transacción y los guarda dentro de ella.

El cliente de embeddings se usa importando el módulo (`embeddings.embed(...)`), para que
el doble de `tests/conftest.py` lo reemplace.
"""

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


def build_passages(reading):
    """Pasajes de las unidades base de `reading`, en el orden del documento. Una unidad
    base sin texto propio no da pasaje."""
    norm = reading.document.norm
    units = list(reading.units.order_by("order"))
    base_units = [u for u in units if u.unit_type != UnitType.INCISO]
    children = {}
    for unit in base_units:
        if unit.parent_id is not None:
            children.setdefault(unit.parent_id, []).append(unit)

    drafts = []
    for unit in base_units:
        end = _own_text_end(unit, children.get(unit.pk, []))
        if end == 0:
            continue
        drafts.append(PassageDraft(
            unit=unit,
            order=1,
            char_start=0,
            char_end=end,
            header=passage_header(norm, unit),
            text=unit.text[:end],
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
