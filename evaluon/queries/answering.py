"""Generación de la respuesta con esquema e inserción de citas (REQ-008, REQ-009, REQ-018,
REQ-019; plan 001, "Generación", "Cita", "Abstención" y "Forma de la respuesta";
ADR-0002). Versión mínima de T-018, completada en T-034.

`answer(pregunta, unit_ids, reference_date=fecha, passages=None)`:

1. Lee de la base las unidades seleccionadas por la recuperación (`unit_ids`) y, con
   `unit_changes(fecha)`, los cambios de cada una a la fecha de autorización del
   procedimiento y las unidades que los traen.
2. Las ordena para mostrarlas (orden fijado por el código, estable): régimen específico,
   otra normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría;
   dentro de cada categoría, en el orden recibido (el de la recuperación). Los
   considerandos van en un bloque aparte, al final, rotulado como contexto. Una unidad
   modificada lleva a continuación la que la modifica, con la fecha del cambio; esa
   unidad no se repite aparte aunque también esté entre las seleccionadas. Cada unidad
   mostrada recibe un alias en el orden en que aparece: `U1`, `U2`, …
3. Arma el pedido: las instrucciones versionadas de `prompts/` (`consulta-v3`) como
   mensaje de sistema; la fecha, la pregunta y las unidades (alias, categoría con su
   papel, norma, ruta, tipo y texto) como mensaje del usuario. El texto de cada unidad es
   `canonical_text[char_start:char_end]` de su lectura, o solo los tramos que indique
   `passages` para esa unidad (`prompt_text`).
4. Arma el esquema de la consulta (`build_schema`): solo esos alias, al menos una cita, un
   texto no vacío y la marca `regimes_differ` por afirmación, y hasta
   `GENERATION_MAX_STATEMENTS` (6) afirmaciones. El motor obliga a cumplirlo.
5. Hace un solo pedido al motor (`generation.generate`).
6. Valida la salida (plan, "Cita"):
   - no es un JSON que cumpla el esquema (por ejemplo, quedó cortada): falla técnica,
     `error` con `invalid_output`;
   - `status` `undetermined`: "no determinado" con `model_abstained`; si trajo
     afirmaciones, se descartan y queda la anomalía `statements_discarded`;
   - alguna afirmación cita un alias no mostrado o no trae citas, o la respuesta con
     fundamento no trae ninguna afirmación: "no determinado" con `invalid_citation`, y se
     descarta la respuesta entera;
   - `regimes_differ` verdadero sin una cita del régimen específico y otra del marco
     nacional (un considerando no cuenta): se apaga la marca, la afirmación queda con sus
     citas y se anota la anomalía `regimes_flag_dropped`. Su campo `statement` es la
     posición de la afirmación en la salida del modelo (`raw_output`), contando desde 0,
     no en la respuesta ordenada del paso 7: así se la encuentra en la salida guardada.
7. Traduce cada alias al `id` de su unidad, ordena las citas de cada afirmación por
   categoría con los considerandos al final, y las afirmaciones por la categoría de su
   primera cita (REQ-018). Arma la parte del resultado que le toca, con la forma de
   "Forma de la respuesta": `status`, `reason`, `statements` y `units`, con `changes` por
   unidad; `units` trae cada unidad citada y cada unidad que la modifica. El texto literal
   no viaja en el resultado: se inserta desde la base al mostrarlo (`citation_texts`).
   `query_id`, `reference_date`, `regime` y `notices` los agrega `services.py`.

Los pasos 1 a 4 los hace `build_request`, que arma el pedido sin llamar al modelo; `answer`
la usa por dentro. `services.py` (T-040) arma el pedido con ella dentro de su instantánea,
lo cuenta y genera con `answer(pregunta, request=pedido)`, que no vuelve a leer la base.

Sin fecha (`reference_date=None`; `services.py` siempre pasa la fecha desde T-040), se
conserva el camino de T-018: instrucciones `consulta-v1`, que no se
modifican, su esquema sin `regimes_differ`, las unidades en el orden recibido y sin
cambios. El orden de la respuesta se aplica igual, y la marca queda apagada. Nunca se
toma la fecha del día.

Una falla del servicio (`timeout`, `service_unavailable`, `input_too_long`) también
termina en `error` con su motivo, y el pedido armado y el error quedan en el `Answer`
para el registro (P6). Nunca es un "no determinado".

El cliente se usa por su módulo (`generation.generate`) para que el doble de las pruebas
lo reemplace.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import connection

from evaluon.ai import AIServiceError, generation
from evaluon.norms.indexing import norm_name
from evaluon.norms.models import Category, Norm, Unit, UnitType
from evaluon.queries.models import Reason, Status

# Versión de las instrucciones: nombre del archivo en `prompts/`, sin extensión. Una
# versión publicada no se modifica: un cambio es un archivo nuevo (P7).
#
# - `PROMPT_VERSION_WITH_DATE`: instrucciones completas, con fecha: `consulta-v3`
#   (T-063, remisión a una norma no cargada, ADR-0015), sobre la v2 de T-034.
# - `PROMPT_VERSION_WITHOUT_DATE`: las de T-018, para `answer` sin fecha.
# - `PROMPT_VERSION`: la que usa `answer` cuando no recibe fecha (camino de T-018). La
#   consulta (`services.ask`, T-040) siempre pasa la fecha, así que la pantalla y
#   `correr_evals` usan y registran `PROMPT_VERSION_WITH_DATE`.
PROMPT_VERSION_WITH_DATE = "consulta-v3"
PROMPT_VERSION_WITHOUT_DATE = "consulta-v1"
PROMPT_VERSION = PROMPT_VERSION_WITHOUT_DATE
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Valores de `status` en la salida del modelo.
GROUNDED = "grounded"
UNDETERMINED = "undetermined"

ALIAS_PREFIX = "U"

# Anomalía de una marca `regimes_differ` sin las dos citas que la sostienen.
REGIMES_FLAG_DROPPED = "regimes_flag_dropped"

# Rótulo del bloque de considerandos en el pedido.
CONSIDERANDOS_HEADING = ("Considerandos (contexto: explican la norma, no establecen "
                         "obligaciones):")

# Orden de las categorías fijado por el código (plan, "Reordenamiento", paso 7, y "Cita").
CATEGORY_ORDER = (
    Category.REGIMEN_ESPECIFICO,
    Category.OTRA_NORMATIVA,
    Category.MARCO_NACIONAL,
    Category.DICTAMEN_LEGAL,
    Category.RECOMENDACION_AUDITORIA,
)

# Papel de cada categoría, en las palabras de la spec y de ADR-0005.
ROLES = {
    Category.REGIMEN_ESPECIFICO: "es lo que se aplica",
    Category.OTRA_NORMATIVA: "se aplica en lo que trata",
    Category.MARCO_NACIONAL: "marco de referencia",
    Category.DICTAMEN_LEGAL: "criterio que acompaña",
    Category.RECOMENDACION_AUDITORIA: "criterio que acompaña",
}
CONSIDERANDO_ROLE = "contexto; no establece obligaciones"

# Marca que reemplaza, en el pedido, el texto omitido de una unidad mostrada por tramos.
OMITTED_MARK = "[… texto omitido …]"

_CHANGES_SQL = """
SELECT unit_id, relation_id, relation_type, target_unit_key, effective_date,
       source_norm_id, source_unit_id
FROM unit_changes(%s)
WHERE unit_id = ANY(%s)
ORDER BY unit_id, effective_date, relation_id
"""


@dataclass(frozen=True)
class Answer:
    """Resultado de la generación.

    - `result`: `status`, `reason`, `statements` (cada una con `text`, `regimes_differ` y
      `citations` por `id` de unidad, en el orden fijado por el código) y `units` (cada
      unidad citada y cada una que la modifica, una vez, por `id` como texto, con sus
      `changes`).
    - `prompt_version`: versión de las instrucciones usadas.
    - `aliases`: alias mostrado al modelo → `id` de la unidad.
    - `request`: el pedido completo enviado al motor.
    - `raw_output`: la salida del modelo sin tocar; vacía si el motor no respondió.
    - `anomalies`: fallas de formato, de cita o de marca detectadas al validar.
    - `error`: si el servicio falló, `service`, `status`, `detail` y `message` del error
      propio del cliente; si no, `None`.
    """

    result: dict
    prompt_version: str
    aliases: dict
    request: dict
    raw_output: str = ""
    anomalies: list = field(default_factory=list)
    error: dict | None = None


@dataclass(frozen=True)
class Change:
    """Una fila de `unit_changes(fecha)` para una unidad mostrada."""

    unit_id: int
    relation_id: int
    relation_type: str
    target_unit_key: str
    effective_date: object
    source_norm_id: int
    source_unit_id: int | None

    def as_record(self):
        return {"relation_type": self.relation_type, "unit": self.source_unit_id,
                "target_unit_key": self.target_unit_key,
                "effective_date": self.effective_date.isoformat()}


class InvalidOutput(ValueError):
    """La salida del modelo no es un JSON que cumpla el esquema."""


def load_instructions(version=PROMPT_VERSION_WITH_DATE):
    """Texto de las instrucciones de esa versión."""
    return (PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8")


def unit_text(unit):
    """Texto literal de una unidad: `canonical_text[char_start:char_end]` de su lectura,
    la única definición del proyecto (plan, "Cita")."""
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def _merged_spans(spans, length):
    """Tramos validados, en orden de texto, con los que se solapan o se tocan unidos."""
    merged = []
    for start, end in sorted(spans):
        if not 0 <= start < end <= length:
            raise ValueError(f"Tramo ({start}, {end}) fuera del texto de la unidad "
                             f"(largo {length}) o vacío.")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def prompt_text(unit, spans=None):
    """Texto de una unidad tal como se le muestra al modelo (plan, "Recuperación", paso
    6). Es el que va en el pedido: la recuperación (T-033) cuenta sus tokens sobre este
    mismo texto.

    - Sin tramos (`None` o lista vacía): la unidad entera, `unit_text(unit)`.
    - Con tramos `(char_start, char_end)`, relativos al texto de la unidad: solo esos
      tramos, en orden de texto, unidos cuando se solapan o se tocan, cada uno en su línea
      y separados por `OMITTED_MARK` donde se omitió texto (también al principio o al
      final si la unidad no empieza o no termina con un tramo). Un tramo vacío, invertido
      o fuera del texto es `ValueError`.

    La cita sigue siendo de la unidad entera: los tramos solo cambian lo que lee el
    modelo."""
    text = unit_text(unit)
    if not spans:
        return text
    pieces = []
    position = 0
    for start, end in _merged_spans(spans, len(text)):
        if start > position:
            pieces.append(OMITTED_MARK)
        pieces.append(text[start:end])
        position = end
    if position < len(text):
        pieces.append(OMITTED_MARK)
    return "\n".join(pieces)


def build_schema(aliases, version=PROMPT_VERSION_WITH_DATE):
    """Esquema de la salida para una consulta: solo los alias mostrados, al menos una
    cita y un texto no vacío por afirmación, y hasta `GENERATION_MAX_STATEMENTS`
    afirmaciones. Desde `consulta-v2`, cada afirmación lleva además `regimes_differ`."""
    properties = {
        "text": {"type": "string", "minLength": 1},
        "citations": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": list(aliases)},
        },
    }
    required = ["text", "citations"]
    if version != PROMPT_VERSION_WITHOUT_DATE:
        properties["regimes_differ"] = {"type": "boolean"}
        required.append("regimes_differ")
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": [GROUNDED, UNDETERMINED]},
            "statements": {
                "type": "array",
                "maxItems": settings.GENERATION_MAX_STATEMENTS,
                "items": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        },
        "required": ["status", "statements"],
        "additionalProperties": False,
    }


# --- Orden fijado por el código --------------------------------------------------------


def _category(unit):
    return unit.reading.document.norm.category


def _is_considerando(unit):
    return unit.unit_type == UnitType.CONSIDERANDO


def order_key(unit):
    """Clave de orden de una unidad: los considerandos al final; si no, por categoría
    (régimen específico, otra normativa aplicable, marco nacional, dictamen legal,
    recomendación de auditoría). Se usa con un orden estable."""
    return (_is_considerando(unit), CATEGORY_ORDER.index(_category(unit)))


def _role(unit):
    return CONSIDERANDO_ROLE if _is_considerando(unit) else ROLES[_category(unit)]


# --- Pedido ----------------------------------------------------------------------------


def unit_block(alias_line, unit, spans=None, *, with_role=True):
    """Bloque de una unidad tal como va en el pedido: `alias_line` (el alias entre
    corchetes, como `[U1]`, o la línea de un cambio), categoría, papel (si `with_role`),
    norma, ruta, tipo y el texto de `prompt_text(unit, spans)`. Es la única definición del
    formato: la usan el armado del pedido y la cuenta de tokens de la recuperación
    (T-033)."""
    norm = unit.reading.document.norm
    lines = [alias_line, f"Categoría: {Category(norm.category).label}"]
    if with_role:
        lines.append(f"Papel: {_role(unit)}")
    lines += [
        f"Norma: {norm_name(norm)}",
        f"Ruta: {unit.path}",
        f"Tipo: {UnitType(unit.unit_type).label}",
        "Texto:",
        prompt_text(unit, spans),
    ]
    return "\n".join(lines)


def _date(value):
    return value.strftime("%d/%m/%Y")


def change_block(change, unit, alias, *, target_path=None, source_alias=None,
                 source=None, source_norm=None, spans=None):
    """Texto que va en el pedido, a continuación de `unit` (mostrada como `alias`), por
    un cambio (`Change`). Es la única definición del formato: la usan el armado del
    pedido y la cuenta de tokens de la recuperación (T-033). Tres formas:

    - Sin `source_alias` (la unidad que trae el cambio no se muestra): la línea
      "Cambio: <norma de origen> modifica a [U1] desde el …. El texto que trae el cambio
      no está entre las unidades."; necesita `source_norm`.
    - Con `source_alias` y sin `source` (la unidad que lo trae ya se mostró): la línea
      "[U3] modifica a [U1] desde el …. Su texto está más arriba."
    - Con `source_alias` y `source`: el bloque de `source` (`unit_block`, con sus
      `spans`) encabezado por la línea "[U3] modifica a [U1] desde el …".

    Si el cambio alcanza una parte de la unidad, el destino es "la parte «ruta» de
    [U1]", con `target_path` o, si falta, la clave alcanzada."""
    if change.target_unit_key == unit.key:
        target = f"[{alias}]"
        verb = "modifica a" if change.relation_type == "modifica" else "deroga"
    else:
        path = target_path or change.target_unit_key
        target = f"la parte «{path}» de [{alias}]"
        verb = "modifica" if change.relation_type == "modifica" else "deroga"
    since = f"desde el {_date(change.effective_date)}"
    if source_alias is None:
        return (f"Cambio: {norm_name(source_norm)} {verb} {target} {since}. El texto "
                "que trae el cambio no está entre las unidades.")
    line = f"[{source_alias}] {verb} {target} {since}"
    if source is None:
        return f"{line}. Su texto está más arriba."
    return unit_block(line, source, spans)


def request_head(question, reference_date):
    """Comienzo del mensaje del usuario con fecha (`consulta-v2` y `consulta-v3`), antes
    de las unidades: la fecha, la pregunta y el rótulo "Unidades:", separados por una línea en blanco. Quien
    llama a la recuperación (T-040) cuenta sus tokens junto con las instrucciones."""
    return "\n\n".join([
        f"Fecha de autorización del procedimiento: {_date(reference_date)}",
        f"Pregunta: {question}",
        "Unidades:",
    ])


def _messages_without_date(question, units_by_alias, passages):
    """Pedido de `consulta-v1` (T-018): pregunta y unidades en el orden recibido."""
    blocks = [unit_block(f"[{alias}]", unit, passages.get(unit.pk), with_role=False)
              for alias, unit in units_by_alias.items()]
    content = f"Pregunta: {question}\n\nUnidades:\n\n" + "\n\n".join(blocks)
    return [
        {"role": "system", "content": load_instructions(PROMPT_VERSION_WITHOUT_DATE)},
        {"role": "user", "content": content},
    ]


class _Layout:
    """Unidades a mostrar con su alias, en el orden fijado por el código, y los bloques de
    texto del pedido (articulado y considerandos)."""

    def __init__(self, units, changes, modifiers, target_paths, source_norms, passages):
        self.units_by_alias = {}
        self._passages = passages
        self._alias_of = {}
        self._changes = changes
        self._modifiers = modifiers
        self._target_paths = target_paths
        self._source_norms = source_norms
        self.articulado = []
        self.considerandos = []

        nested = {c.source_unit_id for unit in units for c in changes.get(unit.pk, ())
                  if c.source_unit_id and c.source_unit_id != unit.pk}
        ordered = sorted(units, key=order_key)
        top = [unit for unit in ordered if unit.pk not in nested]
        for unit in top:
            self._show(unit)
        # Una unidad seleccionada que modifica a otra que también modifica (cadena) no
        # quedó a continuación de nadie: se muestra aparte.
        for unit in ordered:
            if unit.pk not in self._alias_of:
                self._show(unit)

    def _assign(self, unit):
        alias = f"{ALIAS_PREFIX}{len(self.units_by_alias) + 1}"
        self.units_by_alias[alias] = unit
        self._alias_of[unit.pk] = alias
        return alias

    def _show(self, unit):
        blocks = self.considerandos if _is_considerando(unit) else self.articulado
        alias = self._assign(unit)
        blocks.append(unit_block(f"[{alias}]", unit, self._passages.get(unit.pk)))
        for change in self._changes.get(unit.pk, ()):
            blocks.append(self._change_block(change, alias, unit))

    def _change_block(self, change, alias, unit):
        target_path = self._target_paths.get((unit.reading_id, change.target_unit_key))
        source = self._modifiers.get(change.source_unit_id)
        if source is None:
            return change_block(change, unit, alias, target_path=target_path,
                                source_norm=self._source_norms[change.source_norm_id])
        if source.pk in self._alias_of:
            return change_block(change, unit, alias, target_path=target_path,
                                source_alias=self._alias_of[source.pk])
        source_alias = self._assign(source)
        return change_block(change, unit, alias, target_path=target_path,
                            source_alias=source_alias, source=source,
                            spans=self._passages.get(source.pk))


def _messages(question, reference_date, layout):
    """Pedido con fecha (`consulta-v3`; el mismo armado que la v2): fecha, pregunta,
    articulado y considerandos aparte."""
    parts = [request_head(question, reference_date), *layout.articulado]
    if layout.considerandos:
        parts += [CONSIDERANDOS_HEADING, *layout.considerandos]
    return [
        {"role": "system", "content": load_instructions(PROMPT_VERSION_WITH_DATE)},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


# --- Lectura de la base ------------------------------------------------------------------


def _load_units(unit_ids):
    unit_ids = list(dict.fromkeys(unit_ids))
    found = Unit.objects.select_related("reading__document__norm").in_bulk(unit_ids)
    missing = [unit_id for unit_id in unit_ids if unit_id not in found]
    if missing:
        raise ValueError(f"No existen las unidades {missing}.")
    return [found[unit_id] for unit_id in unit_ids]


def _changes(reference_date, unit_ids):
    """Cambios a la fecha de cada unidad (`unit_changes`), por `id` de unidad."""
    with connection.cursor() as cursor:
        cursor.execute(_CHANGES_SQL, [reference_date, list(unit_ids)])
        rows = [Change(*row) for row in cursor.fetchall()]
    by_unit = {}
    for change in rows:
        by_unit.setdefault(change.unit_id, []).append(change)
    return by_unit


def load_changes(reference_date, units):
    """Cambios a la fecha de `units` y lo necesario para mostrarlos: `(changes,
    modifiers, target_paths, source_norms)`, con los cambios por `id` de unidad (también
    los de las unidades que modifican, para el resultado), las unidades que los traen por
    `id`, la ruta de cada parte alcanzada por `(lectura, clave)` y las normas de origen
    por `id`. La usan `answer` y la cuenta de tokens de la recuperación (T-033)."""
    changes = _changes(reference_date, [unit.pk for unit in units])
    source_ids = {c.source_unit_id for rows in changes.values() for c in rows
                  if c.source_unit_id}
    by_id = {unit.pk: unit for unit in units}
    missing = [pk for pk in source_ids if pk not in by_id]
    modifiers = {**{pk: by_id[pk] for pk in source_ids if pk in by_id},
                 **{unit.pk: unit for unit in _load_units(missing)}}
    # Los cambios de las unidades que modifican van en el resultado (`changes`).
    changes.update(_changes(reference_date, list(missing)) if missing else {})

    units_by_reading = {unit.pk: unit.reading_id for unit in units}
    wanted = {(units_by_reading[c.unit_id], c.target_unit_key)
              for rows in changes.values() for c in rows
              if c.unit_id in units_by_reading}
    target_paths = {}
    for reading_id, key in wanted:
        path = Unit.objects.filter(reading_id=reading_id, key=key).values_list(
            "path", flat=True).first()
        if path is not None:
            target_paths[(reading_id, key)] = path
    norm_ids = {c.source_norm_id for rows in changes.values() for c in rows}
    source_norms = Norm.objects.in_bulk(norm_ids)
    return changes, modifiers, target_paths, source_norms


# --- Validación de la salida -------------------------------------------------------------


def _parse(content, version):
    """Comprueba que la salida cumpla la forma del esquema. La lista cerrada de alias y
    el mínimo de una cita no se comprueban acá: su falta es `invalid_citation`."""
    keys = {"text", "citations"}
    if version != PROMPT_VERSION_WITHOUT_DATE:
        keys.add("regimes_differ")
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidOutput(f"no es JSON: {error}") from error
    if not isinstance(data, dict) or set(data) != {"status", "statements"}:
        raise InvalidOutput("no es un objeto con status y statements")
    if data["status"] not in (GROUNDED, UNDETERMINED):
        raise InvalidOutput(f"status desconocido: {data['status']!r}")
    statements = data["statements"]
    if not isinstance(statements, list):
        raise InvalidOutput("statements no es una lista")
    if len(statements) > settings.GENERATION_MAX_STATEMENTS:
        raise InvalidOutput(f"{len(statements)} afirmaciones, más que el máximo")
    for position, statement in enumerate(statements):
        if not isinstance(statement, dict) or set(statement) != keys:
            raise InvalidOutput(f"afirmación {position}: no es un objeto con "
                                f"{', '.join(sorted(keys))}")
        if not isinstance(statement["text"], str) or not statement["text"]:
            raise InvalidOutput(f"afirmación {position}: text no es texto o está vacío")
        citations = statement["citations"]
        if not isinstance(citations, list) or not all(isinstance(c, str)
                                                      for c in citations):
            raise InvalidOutput(f"afirmación {position}: citations no es una lista de "
                                "alias")
        if "regimes_differ" in keys and not isinstance(statement["regimes_differ"], bool):
            raise InvalidOutput(f"afirmación {position}: regimes_differ no es booleano")
    return data["status"], statements


def _citation_anomalies(statements, aliases):
    anomalies = []
    if not statements:
        anomalies.append({"type": Reason.INVALID_CITATION.value, "statement": None,
                          "detail": "respuesta con fundamento sin afirmaciones"})
    for position, statement in enumerate(statements):
        unknown = [c for c in statement["citations"] if c not in aliases]
        if not statement["citations"]:
            anomalies.append({"type": Reason.INVALID_CITATION.value,
                              "statement": position, "detail": "sin citas"})
        elif unknown:
            anomalies.append({"type": Reason.INVALID_CITATION.value,
                              "statement": position, "detail": "alias no mostrado",
                              "aliases": unknown})
    return anomalies


def _regimes_cited(units):
    """Si entre las unidades hay una del régimen específico y otra del marco nacional,
    sin contar considerandos (REQ-019)."""
    categories = {_category(unit) for unit in units if not _is_considerando(unit)}
    return {Category.REGIMEN_ESPECIFICO, Category.MARCO_NACIONAL} <= categories


# --- Resultado ---------------------------------------------------------------------------


def _empty_result(status, reason):
    return {"status": status, "reason": reason, "statements": [], "units": {}}


def _unit_record(unit, changes):
    norm = unit.reading.document.norm
    record = {
        "norm": norm_name(norm),
        "category": norm.category,
        "unit_type": unit.unit_type,
        "path": unit.path,
        "text_origin": unit.text_origin,
        "document": unit.reading.document_id,
        "page_start": unit.page_start,
    }
    if changes is not None:
        record["changes"] = [c.as_record() for c in changes.get(unit.pk, ())]
    return record


def _grounded_result(statements, units_by_alias, changes, modifiers):
    """Resultado con fundamento, en el orden fijado por el código, y las anomalías de la
    marca de regímenes. `changes` es `None` en el camino sin fecha.

    Cada anomalía `regimes_flag_dropped` lleva en `statement` la posición de la
    afirmación en la salida del modelo (contando desde 0), no la que ocupa en
    `result["statements"]` después de ordenar."""
    anomalies = []
    ordered = []
    cited = {}
    for position, statement in enumerate(statements):
        units = []
        for alias in statement["citations"]:
            unit = units_by_alias[alias]
            if unit not in units:
                units.append(unit)
        units.sort(key=order_key)
        differ = statement.get("regimes_differ", False)
        # `statement` en la anomalía es `position`: la posición de la afirmación en la
        # salida del modelo (`raw_output`), no en la respuesta ordenada por el código.
        if differ and not _regimes_cited(units):
            differ = False
            anomalies.append({"type": REGIMES_FLAG_DROPPED, "statement": position,
                              "detail": "regimes_differ sin una cita del régimen "
                                        "específico y otra del marco nacional"})
        for unit in units:
            cited.setdefault(unit.pk, unit)
        ordered.append((order_key(units[0]), {
            "text": statement["text"],
            "regimes_differ": differ,
            "citations": [unit.pk for unit in units],
        }))
    ordered.sort(key=lambda item: item[0])

    shown = dict(cited)
    for unit_id in list(cited):
        for change in (changes or {}).get(unit_id, ()):
            if change.source_unit_id in modifiers:
                shown.setdefault(change.source_unit_id, modifiers[change.source_unit_id])
    result = {
        "status": Status.GROUNDED.value,
        "reason": None,
        "statements": [statement for _, statement in ordered],
        "units": {str(pk): _unit_record(unit, changes) for pk, unit in shown.items()},
    }
    return result, anomalies


@dataclass(frozen=True)
class Request:
    """Pedido armado para el motor, sin enviar (`build_request`).

    - `prompt_version`: versión de las instrucciones.
    - `messages`: los mensajes tal como se envían (sistema y usuario).
    - `schema`: el esquema de la salida, con los alias mostrados.
    - `units_by_alias`: alias → unidad (`Unit`), en el orden en que se muestran.
    - `aliases`: alias → `id` de la unidad.
    - `shown`: `id` de todas las unidades mostradas: las recibidas y las que entran por
      relación.
    - `changes` y `modifiers`: los cambios a la fecha por `id` de unidad y las unidades
      que los traen (`load_changes`); `None` y vacío en el camino sin fecha.
    """

    prompt_version: str
    messages: list
    schema: dict
    units_by_alias: dict
    aliases: dict
    shown: frozenset
    changes: dict | None = None
    modifiers: dict = field(default_factory=dict)


def build_request(question, unit_ids, reference_date=None, passages=None):
    """Arma el pedido para `question` con las unidades `unit_ids` y la fecha de
    autorización `reference_date`, sin llamar al modelo (pasos 1 a 4 del módulo).
    Devuelve un `Request`. Es el único camino del armado: lo usan `answer` y el control
    del pedido completo de `services.py` (T-040), que cuenta sus mensajes.

    Sin unidades, con unidades inexistentes, con tramos para una unidad que no se
    muestra o fuera de su texto, lanza `ValueError`. Ver `answer` para `passages`."""
    passages = passages or {}
    units = _load_units(unit_ids)
    if not units:
        raise ValueError("La generación necesita al menos una unidad seleccionada.")

    if reference_date is None:
        version = PROMPT_VERSION_WITHOUT_DATE
        units_by_alias = {f"{ALIAS_PREFIX}{n}": unit
                          for n, unit in enumerate(units, start=1)}
        messages = _messages_without_date(question, units_by_alias, passages)
        changes, modifiers = None, {}
    else:
        version = PROMPT_VERSION_WITH_DATE
        changes, modifiers, target_paths, source_norms = load_changes(reference_date,
                                                                      units)
        layout = _Layout(units, changes, modifiers, target_paths, source_norms, passages)
        units_by_alias = layout.units_by_alias
        messages = _messages(question, reference_date, layout)

    aliases = {alias: unit.pk for alias, unit in units_by_alias.items()}
    not_shown = sorted(set(passages) - set(aliases.values()))
    if not_shown:
        raise ValueError(f"Hay tramos para unidades que no se muestran: {not_shown}.")
    return Request(
        prompt_version=version,
        messages=messages,
        schema=build_schema(list(units_by_alias), version=version),
        units_by_alias=units_by_alias,
        aliases=aliases,
        shown=frozenset(aliases.values()),
        changes=changes,
        modifiers=modifiers,
    )


def answer(question, unit_ids=None, reference_date=None, passages=None, *,
           request=None):
    """Genera la respuesta a `question` con las unidades `unit_ids` (las seleccionadas
    por la recuperación) para la fecha de autorización `reference_date`. Ver el módulo.
    Sin unidades no llama al modelo: esa abstención (`below_threshold`) la resuelve quien
    llama. El pedido lo arma `build_request`.

    `passages` (opcional): `{id de unidad: [(char_start, char_end), …]}`, tramos relativos
    al texto de la unidad. De una unidad con tramos el pedido muestra solo esos tramos
    (`prompt_text`); de las demás, la unidad entera. Es lo que decide la recuperación para
    una unidad de más de 1.500 tokens (plan, "Recuperación", paso 6). Las citas, `units`,
    `aliases` y el texto que se inserta siguen siendo de la unidad entera. Tramos para una
    unidad que no se muestra, o fuera de su texto, son `ValueError` y no se llama al
    modelo.

    `request` (opcional): un `Request` ya armado con `build_request`. Se envía tal cual,
    y la salida se valida y el resultado se arma con lo que trae (alias, unidades,
    cambios y unidades que los traen), sin volver a leer la base. Así la consulta
    (`services.py`, T-040) genera con el mismo pedido que armó y controló dentro de su
    instantánea. Con `request` no se pasan `unit_ids`, `reference_date` ni `passages`
    (`ValueError`): ya están en el pedido."""
    if request is None:
        built = build_request(question, unit_ids, reference_date, passages)
    elif unit_ids is not None or reference_date is not None or passages is not None:
        raise ValueError("Con un pedido ya armado no se pasan unidades, fecha ni tramos: "
                         "ya están en el pedido.")
    else:
        built = request
    version = built.prompt_version
    messages, schema = built.messages, built.schema
    units_by_alias, aliases = built.units_by_alias, built.aliases
    changes, modifiers = built.changes, built.modifiers
    common = {"prompt_version": version, "aliases": aliases}

    try:
        output = generation.generate(messages, schema)
    except AIServiceError as error:
        return Answer(
            result=_empty_result(Status.ERROR.value, error.reason),
            request=generation.build_request(messages, schema),
            error={"service": error.service, "status": error.status,
                   "detail": error.detail, "message": str(error)},
            **common,
        )

    common.update(request=output.request, raw_output=output.content)
    try:
        status, statements = _parse(output.content, version)
    except InvalidOutput as error:
        return Answer(
            result=_empty_result(Status.ERROR.value, Reason.INVALID_OUTPUT.value),
            anomalies=[{"type": Reason.INVALID_OUTPUT.value, "detail": str(error),
                        "finish_reason": output.finish_reason}],
            **common,
        )

    if status == UNDETERMINED:
        anomalies = ([{"type": "statements_discarded", "count": len(statements)}]
                     if statements else [])
        return Answer(
            result=_empty_result(Status.UNDETERMINED.value,
                                 Reason.MODEL_ABSTAINED.value),
            anomalies=anomalies,
            **common,
        )

    anomalies = _citation_anomalies(statements, aliases)
    if anomalies:
        return Answer(
            result=_empty_result(Status.UNDETERMINED.value,
                                 Reason.INVALID_CITATION.value),
            anomalies=anomalies,
            **common,
        )

    result, anomalies = _grounded_result(statements, units_by_alias, changes, modifiers)
    return Answer(result=result, anomalies=anomalies, **common)


def citation_texts(result):
    """Texto literal de cada unidad de un resultado, leído de la base por `id`:
    `{id: canonical_text[char_start:char_end]}`. Así se inserta el texto de las citas;
    nunca sale de la salida del modelo."""
    unit_ids = [int(unit_id) for unit_id in result.get("units") or {}]
    units = Unit.objects.select_related("reading").in_bulk(unit_ids)
    return {unit_id: unit_text(units[unit_id]) for unit_id in unit_ids}
