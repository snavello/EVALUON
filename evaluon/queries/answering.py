"""Generación de la respuesta con esquema e inserción de citas (REQ-008, REQ-009; plan
001, "Generación", "Cita", "Abstención" y "Forma de la respuesta"; ADR-0002). Versión
mínima de T-018.

`answer(pregunta, unit_ids)`:

1. Lee de la base las unidades seleccionadas por la recuperación (`unit_ids`, en ese
   orden) y le da a cada una un alias: `U1`, `U2`, …
2. Arma el pedido: las instrucciones versionadas de `prompts/` como mensaje de sistema, y
   la pregunta con cada unidad (alias, categoría, norma, ruta, tipo y texto) como mensaje
   del usuario. El texto de cada unidad es `canonical_text[char_start:char_end]` de su
   lectura.
3. Arma el esquema de la consulta (`build_schema`), que enumera solo esos alias, exige al
   menos una cita por afirmación y limita las afirmaciones a
   `GENERATION_MAX_STATEMENTS`. El motor obliga a cumplirlo.
4. Hace un solo pedido al motor (`generation.generate`).
5. Valida la salida (plan, "Cita"):
   - no es un JSON que cumpla el esquema (por ejemplo, quedó cortada): falla técnica,
     `error` con `invalid_output`;
   - `status` `undetermined`: "no determinado" con `model_abstained`; si trajo
     afirmaciones, se descartan y queda la anomalía `statements_discarded`;
   - alguna afirmación cita un alias no mostrado o no trae citas, o la respuesta con
     fundamento no trae ninguna afirmación: "no determinado" con `invalid_citation`, y se
     descarta la respuesta entera.
6. Traduce cada alias al `id` de su unidad y arma la parte del resultado que le toca, con
   la forma de "Forma de la respuesta": `status`, `reason`, `statements` y `units`. El
   texto literal no viaja en el resultado: se inserta desde la base al mostrarlo
   (`citation_texts`). `query_id`, `reference_date`, `regime` y `notices` los agrega
   `services.py` (T-019).

Una falla del servicio (`timeout`, `service_unavailable`, `input_too_long`) también
termina en `error` con su motivo, y el pedido armado y el error quedan en el `Answer`
para el registro (P6). Nunca es un "no determinado".

La fecha de autorización en el pedido, la marca `regimes_differ`, el orden de las citas
por categoría, los cambios por relación y las instrucciones completas son de T-034.

El cliente se usa por su módulo (`generation.generate`) para que el doble de las pruebas
lo reemplace.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.norms.indexing import norm_name
from evaluon.norms.models import Category, Unit, UnitType
from evaluon.queries.models import Reason, Status

# Versión de las instrucciones: nombre del archivo en `prompts/`, sin extensión. Una
# versión publicada no se modifica: un cambio es un archivo nuevo (P7).
PROMPT_VERSION = "consulta-v1"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Valores de `status` en la salida del modelo.
GROUNDED = "grounded"
UNDETERMINED = "undetermined"

ALIAS_PREFIX = "U"


@dataclass(frozen=True)
class Answer:
    """Resultado de la generación.

    - `result`: `status`, `reason`, `statements` (cada una con `text` y `citations` por
      `id` de unidad) y `units` (cada unidad citada, una vez, por `id` como texto).
    - `prompt_version`: versión de las instrucciones usadas.
    - `aliases`: alias mostrado al modelo → `id` de la unidad.
    - `request`: el pedido completo enviado al motor.
    - `raw_output`: la salida del modelo sin tocar; vacía si el motor no respondió.
    - `anomalies`: fallas de formato o de cita detectadas al validar.
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


class InvalidOutput(ValueError):
    """La salida del modelo no es un JSON que cumpla el esquema."""


def load_instructions(version=PROMPT_VERSION):
    """Texto de las instrucciones de esa versión."""
    return (PROMPTS_DIR / f"{version}.txt").read_text(encoding="utf-8")


def unit_text(unit):
    """Texto literal de una unidad: `canonical_text[char_start:char_end]` de su lectura,
    la única definición del proyecto (plan, "Cita")."""
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def build_schema(aliases):
    """Esquema de la salida para una consulta: solo los alias mostrados, al menos una
    cita por afirmación y hasta `GENERATION_MAX_STATEMENTS` afirmaciones."""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": [GROUNDED, UNDETERMINED]},
            "statements": {
                "type": "array",
                "maxItems": settings.GENERATION_MAX_STATEMENTS,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string", "enum": list(aliases)},
                        },
                    },
                    "required": ["text", "citations"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["status", "statements"],
        "additionalProperties": False,
    }


def _unit_block(alias, unit):
    norm = unit.reading.document.norm
    return "\n".join([
        f"[{alias}]",
        f"Categoría: {Category(norm.category).label}",
        f"Norma: {norm_name(norm)}",
        f"Ruta: {unit.path}",
        f"Tipo: {UnitType(unit.unit_type).label}",
        "Texto:",
        unit_text(unit),
    ])


def build_messages(question, units_by_alias, version=PROMPT_VERSION):
    """Mensajes del pedido: instrucciones como sistema; pregunta y unidades como
    usuario."""
    blocks = [_unit_block(alias, unit) for alias, unit in units_by_alias.items()]
    content = f"Pregunta: {question}\n\nUnidades:\n\n" + "\n\n".join(blocks)
    return [
        {"role": "system", "content": load_instructions(version)},
        {"role": "user", "content": content},
    ]


def _load_units(unit_ids):
    unit_ids = list(unit_ids)
    found = Unit.objects.select_related("reading__document__norm").in_bulk(unit_ids)
    missing = [unit_id for unit_id in unit_ids if unit_id not in found]
    if missing:
        raise ValueError(f"No existen las unidades {missing}.")
    return [found[unit_id] for unit_id in unit_ids]


def _parse(content):
    """Comprueba que la salida cumpla la forma del esquema. La lista cerrada de alias y
    el mínimo de una cita no se comprueban acá: su falta es `invalid_citation`."""
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
        if not isinstance(statement, dict) or set(statement) != {"text", "citations"}:
            raise InvalidOutput(f"afirmación {position}: no es un objeto con text y "
                                "citations")
        if not isinstance(statement["text"], str):
            raise InvalidOutput(f"afirmación {position}: text no es texto")
        citations = statement["citations"]
        if not isinstance(citations, list) or not all(isinstance(c, str)
                                                      for c in citations):
            raise InvalidOutput(f"afirmación {position}: citations no es una lista de "
                                "alias")
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


def _empty_result(status, reason):
    return {"status": status, "reason": reason, "statements": [], "units": {}}


def _unit_record(unit):
    norm = unit.reading.document.norm
    return {
        "norm": norm_name(norm),
        "category": norm.category,
        "unit_type": unit.unit_type,
        "path": unit.path,
        "text_origin": unit.text_origin,
        "document": unit.reading.document_id,
        "page_start": unit.page_start,
    }


def _grounded_result(statements, units_by_alias):
    result_statements = []
    cited = {}
    for statement in statements:
        unit_ids = []
        for alias in statement["citations"]:
            unit = units_by_alias[alias]
            if unit.pk not in unit_ids:
                unit_ids.append(unit.pk)
            cited.setdefault(unit.pk, unit)
        result_statements.append({"text": statement["text"], "citations": unit_ids})
    return {
        "status": Status.GROUNDED.value,
        "reason": None,
        "statements": result_statements,
        "units": {str(pk): _unit_record(unit) for pk, unit in cited.items()},
    }


def answer(question, unit_ids):
    """Genera la respuesta a `question` con las unidades `unit_ids` (las seleccionadas
    por la recuperación, en su orden). Ver el módulo. Sin unidades no llama al modelo:
    esa abstención (`below_threshold`) la resuelve quien llama."""
    units = _load_units(unit_ids)
    if not units:
        raise ValueError("La generación necesita al menos una unidad seleccionada.")
    units_by_alias = {f"{ALIAS_PREFIX}{n}": unit for n, unit in enumerate(units, start=1)}
    aliases = {alias: unit.pk for alias, unit in units_by_alias.items()}
    messages = build_messages(question, units_by_alias)
    schema = build_schema(list(units_by_alias))
    common = {"prompt_version": PROMPT_VERSION, "aliases": aliases}

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
        status, statements = _parse(output.content)
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

    return Answer(result=_grounded_result(statements, units_by_alias), **common)


def citation_texts(result):
    """Texto literal de cada unidad citada en un resultado, leído de la base por `id`:
    `{id: canonical_text[char_start:char_end]}`. Así se inserta el texto de las citas;
    nunca sale de la salida del modelo."""
    unit_ids = [int(unit_id) for unit_id in result.get("units") or {}]
    units = Unit.objects.select_related("reading").in_bulk(unit_ids)
    return {unit_id: unit_text(units[unit_id]) for unit_id in unit_ids}
