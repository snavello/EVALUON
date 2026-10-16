"""El esqueleto de la salida de cada instrucción de la matriz coincide con su esquema (T-280; REQ-119;
H-279-5 de la verificación de T-279; ADR-0070, regla 2; ADR-0055).

Las instrucciones cortas de la 016 no llevan ejemplos: le muestran al modelo solo el esqueleto de la
salida, con marcadores (`"<oración del tramo>"`) y los valores posibles separados por `|`. El esquema
que se manda con el pedido (`build_schema`, `schema_a`, `schema_b`) es el que manda; si el esqueleto
nombra otra clave, otro orden u otro valor, el modelo recibe dos órdenes distintas. Esta prueba lee el
esqueleto de cada instrucción vigente y lo compara con su esquema:

- las mismas claves, en el mismo orden (el modelo escribe en el orden del esquema, ADR-0055);
- donde el esqueleto da los valores (`"formal|economico"`), los mismos que la enumeración del esquema;
- donde da un valor suelto, uno que el esquema admite, o un marcador entre `<` y `>`.

Además, las listas de valores que la instrucción explica una por una (motivos de descarte, opciones,
tipos de consecuencia, tipos y objetivos de un cambio de circular) son las del código.

Los textos de prueba son inventados (P4).
"""

import json
import re

import pytest
from django.conf import settings

from evaluon.tenders.models import DiscardReason
from evaluon.tenders.proposal import (
    circular_changes,
    circulars,
    completeness,
    consequences,
    extraction,
    joining,
    norm_support,
)
from evaluon.tenders.proposal import filter as row_filter

# `{nombre: (texto de la instrucción vigente, función que arma el esquema con los alias del esqueleto)}`.
# El filtro tiene dos pedidos con su parte de la instrucción cada uno.
SCHEMAS = {
    "extraccion": lambda aliases: extraction.build_schema(aliases, [1, 2]),
    "completitud": completeness.build_schema,
    "union": joining.build_schema,
    "filtro_a": row_filter.schema_a,
    "filtro_b": row_filter.schema_b,
    "consecuencias": lambda aliases: consequences.build_schema(aliases, ["P1", "N1"]),
    "circulares": lambda aliases: circulars.build_schema(["Q1"]),
    "circulares_cambios": lambda aliases: circular_changes.build_schema(),
    "respaldo": norm_support.build_schema,
}
# Las que devuelven un objeto por alias: el esqueleto trae un alias de muestra.
BY_ALIAS = {"extraccion", "completitud", "union", "filtro_a", "filtro_b", "consecuencias",
            "respaldo"}


def instruction_text(name):
    """El texto vigente que recibe el modelo: el de la parte A o B en el filtro."""
    if name in ("filtro_a", "filtro_b"):
        first, second = row_filter.load_prompts()
        return first if name == "filtro_a" else second
    return extraction.load_prompt(name)


def skeleton_of(text):
    """El esqueleto de la salida: la única línea de la instrucción que es un objeto JSON."""
    lines = [line for line in text.splitlines() if line.startswith("{")]
    assert len(lines) == 1, f"se esperaba una línea de esqueleto y hay {len(lines)}"
    return json.loads(lines[0])


def _is_marker(value):
    return value.startswith("<") and value.endswith(">")


def shape_problems(skeleton, schema, path="$"):
    """Lo que el esqueleto dice distinto del esquema: lista de textos (vacía si coinciden)."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(skeleton, dict):
            return [f"{path}: el esquema pide un objeto"]
        keys, expected = list(skeleton), list(schema["properties"])
        if keys != expected:
            return [f"{path}: claves {keys}, el esquema pide {expected}"]
        return [problem for key in keys
                for problem in shape_problems(skeleton[key], schema["properties"][key],
                                              f"{path}.{key}")]
    if kind == "array":
        if not isinstance(skeleton, list):
            return [f"{path}: el esquema pide una lista"]
        return [problem for item in skeleton[:1]
                for problem in shape_problems(item, schema["items"], f"{path}[0]")]
    if kind == "string":
        if not isinstance(skeleton, str):
            return [f"{path}: el esquema pide un texto"]
        enum = schema.get("enum")
        if enum is None or _is_marker(skeleton):
            return []
        if "|" in skeleton:
            shown = set(skeleton.split("|"))
            return [] if shown == set(enum) - {""} else [
                f"{path}: valores {sorted(shown)}, el esquema admite {sorted(set(enum) - {''})}"]
        return [] if skeleton in enum else [f"{path}: «{skeleton}» no está en el esquema"]
    return []


def skeleton_problems(name, text=None):
    text = instruction_text(name) if text is None else text
    skeleton = skeleton_of(text)
    aliases = list(skeleton) if name in BY_ALIAS else []
    schema = SCHEMAS[name](aliases)
    if name in BY_ALIAS:
        if len(aliases) != 1:
            return [f"{name}: el esqueleto trae {len(aliases)} alias"]
        return shape_problems(skeleton[aliases[0]], schema["properties"][aliases[0]],
                              f"{name}.{aliases[0]}")
    return shape_problems(skeleton, schema, name)


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_the_skeleton_of_each_current_instruction_matches_its_schema(name):
    """REQ-119 (H-279-5): el esqueleto de la salida de cada instrucción vigente de la matriz tiene las
    claves, el orden y los valores del esquema que se manda con el pedido."""
    assert skeleton_problems(name) == []


def test_every_current_matrix_instruction_with_a_model_output_is_checked():
    """REQ-119: la prueba cubre cada instrucción vigente de la matriz que pide una salida al modelo
    (todas menos el bloque de definiciones y la unificación, que es de código)."""
    names = set(settings.MATRIX_PROMPT_VERSIONS) - {"definiciones", "unificacion", "filtro"}
    assert names | {"filtro_a", "filtro_b"} == set(SCHEMAS)


# --- Las listas que la instrucción explica una por una -------------------------------------------


def _bullets(text, quoted):
    pattern = r'^ *- "([a-z_]+)": ' if quoted else r"^- ([a-z_]+): "
    return set(re.findall(pattern, text, re.MULTILINE))


def test_the_extraction_names_the_discard_reasons_and_options_of_the_code():
    """REQ-119 (H-279-5, alteración D4): los motivos de descarte y las opciones que nombra la
    extracción vigente son los de `DiscardReason` y `extraction.OPTIONS`."""
    text = extraction.load_prompt("extraccion")
    assert _bullets(text, quoted=False) == set(DiscardReason.values)
    line = next(line for line in text.splitlines() if line.startswith('- "opcion":'))
    named = set(re.findall(r'"([a-z_]+)"', line.split("el nombre de esa opción:")[1]))
    assert named == set(extraction.OPTIONS)


def test_the_filter_names_the_motives_of_the_settings():
    """REQ-119: los motivos que nombra la pregunta A del filtro son los de `FILTER_MOTIVES`."""
    first, _ = row_filter.load_prompts()
    assert _bullets(first, quoted=True) - {"decision", "motivo", "indicio"} == set(
        settings.FILTER_MOTIVES)


def test_the_consequences_name_the_types_the_system_suggests():
    """REQ-119, REQ-029: los tipos que explica la instrucción de consecuencias son los que el sistema
    puede sugerir (`SYSTEM_TYPES`)."""
    text = extraction.load_prompt("consecuencias")
    assert _bullets(text, quoted=True) - {"fundamentos", "tipo"} == set(consequences.SYSTEM_TYPES)


def test_the_circulars_name_the_discard_reasons_of_the_code():
    """REQ-119: los motivos de «sin_efecto» que nombra la instrucción de circulares son los de
    `DiscardReason`."""
    text = extraction.load_prompt("circulares")
    line = next(line for line in text.splitlines() if line.startswith('- "sin_efecto":'))
    listed = line.split("el motivo:")[1].split("; si no")[0]
    listed = re.sub(r"\([^)]*\)", "", listed)
    named = {word.strip() for word in re.split(r",| o ", listed) if word.strip()}
    assert named == set(DiscardReason.values)


def test_the_circular_changes_name_the_types_and_targets_of_the_code():
    """REQ-119: los tipos y los objetivos que explica la instrucción de cambios de circulares son los
    de `circular_changes.TYPES` y `circular_changes.TARGETS`."""
    text = extraction.load_prompt("circulares_cambios")
    lines = text.splitlines()
    kinds = next(line for line in lines if line.startswith('- "tipo":'))
    targets = next(line for line in lines if line.startswith('- "objetivo":'))
    assert set(re.findall(r'"([a-z_]+)" si', kinds)) == set(circular_changes.TYPES)
    assert set(re.findall(r'"([a-z_]+)"', targets.split(":", 1)[1])) == set(
        circular_changes.TARGETS)


# --- La prueba detecta lo que dice detectar (esqueletos de prueba, inventados) -------------------


GOOD = 'Salida:\n{"T1": {"requisitos": [{"cita": "<oración>", "clase": "formal|economico", ' \
       '"opcion": ""}], "tecnico": [], "descarte": ""}}\n'


@pytest.mark.parametrize("changed, expected", [
    # Una clave cambiada (alteración D1 de la verificación de T-279).
    (GOOD.replace('"descarte"', '"descartes"'), "claves"),
    # Dos claves en otro orden.
    (GOOD.replace('"clase": "formal|economico", "opcion": ""', '"opcion": "", "clase": "formal|economico"'),
     "claves"),
    # Un valor que el esquema no tiene.
    (GOOD.replace("formal|economico", "formal|tecnico"), "valores"),
    # Un valor suelto que el esquema no admite.
    (GOOD.replace('"opcion": ""', '"opcion": "cotizacion"'), "no está en el esquema"),
])
def test_a_changed_skeleton_fails(changed, expected):
    """REQ-119 (H-279-5): con un esqueleto de prueba igual al esquema de la extracción no hay
    problemas; con una clave cambiada, otro orden o un valor que el esquema no tiene, sí."""
    assert skeleton_problems("extraccion", GOOD) == []
    problems = skeleton_problems("extraccion", changed)
    assert problems and expected in problems[0]


def test_a_changed_skeleton_of_the_union_or_the_circular_changes_fails():
    """REQ-119 (H-279-5, alteraciones D2 y D3): `una|dos` → `uno|dos` en la unión y una clave cambiada
    en los cambios de circulares fallan."""
    union = '{"P1": {"razonamiento": "<por qué>", "filas": "uno|dos"}}'
    assert skeleton_problems("union", union) != []
    changes = ('{"cambios": [{"tipo": "reemplaza", "objetivo": "ninguno", "referencia": "", '
               '"texto_viejo": "", "texto_nuevo": ""}]}')
    assert skeleton_problems("circulares_cambios", changes) != []
