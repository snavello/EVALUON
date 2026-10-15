"""Largo máximo de las instrucciones simplificadas (T-278; REQ-119; plan 016, umbral 5; ADR-0070).

Cada instrucción al modelo local que reemplaza a las de la 015 tiene un tope de largo, con el
bloque común de definiciones **ya incluido** (el modelo lo lee entero):

- decisoras (extracción, filtro, evaluación y matriz externa): 90 líneas y 9.000 caracteres;
- las demás: 50 líneas y 5.000 caracteres;
- el bloque de definiciones (`matriz-definiciones-vN`): 5.000 caracteres;
- la descripción de cada campo de un esquema de salida: 80 caracteres (para que no se mueva
  texto de la instrucción al esquema).

El tope se aplica a las versiones listadas en `SIMPLIFIED`. Cada tarea de instrucciones (T-279 a
T-282, T-291) suma las suyas (T-279: el bloque de definiciones, la extracción, la completitud y la
unión de la matriz), y T-282 agrega la prueba de que toda
instrucción vigente figura en la tabla. `SIMPLIFIED_SCHEMAS` hace lo mismo con los esquemas de
salida (T-281).

La tabla también la usan `test_instrucciones_sin_casos.py` y `test_instrucciones_revisadas.py`:
una versión que se suma acá queda sujeta a las tres pruebas.

Los textos de estas pruebas son inventados (P4).
"""

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Misma marca que `extraction.DEFINITIONS_MARK` (el bloque común va donde la instrucción la trae).
DEFINITIONS_MARK = "{{DEFINICIONES}}"

# Las versiones simplificadas: `{nombre de versión: {"path": ruta desde la raíz del repositorio,
# "definitions": versión del bloque común que el código incluye (si la instrucción tiene la
# marca)}}`. Ejemplo:
#     "matriz-extraccion-v13": {"path": "evaluon/tenders/prompts/matriz-extraccion-v13.md",
#                               "definitions": "matriz-definiciones-v9"},
SIMPLIFIED = {
    # T-279: la matriz, parte 1 (el bloque común y las tres instrucciones que lo incluyen).
    "matriz-definiciones-v9": {"path": "evaluon/tenders/prompts/matriz-definiciones-v9.md"},
    "matriz-extraccion-v13": {"path": "evaluon/tenders/prompts/matriz-extraccion-v13.md",
                              "definitions": "matriz-definiciones-v9"},
    "matriz-completitud-v7": {"path": "evaluon/tenders/prompts/matriz-completitud-v7.md",
                              "definitions": "matriz-definiciones-v9"},
    "matriz-union-v2": {"path": "evaluon/tenders/prompts/matriz-union-v2.md",
                        "definitions": "matriz-definiciones-v9"},
}

# Los esquemas de salida de las instrucciones simplificadas: `{nombre: "módulo:función"}`; la
# función no recibe argumentos y devuelve el esquema JSON.
SIMPLIFIED_SCHEMAS = {}

# Instrucciones decisoras: por prefijo del nombre de versión (plan 016, «Largo máximo»).
DECISIVE_PREFIXES = ("matriz-extraccion-", "matriz-filtro-", "evaluacion-", "matriz-externa-")
DEFINITIONS_PREFIX = "matriz-definiciones-"

DECISIVE_LINES, DECISIVE_CHARS = 90, 9000
OTHER_LINES, OTHER_CHARS = 50, 5000
DEFINITIONS_CHARS = 5000
DESCRIPTION_CHARS = 80


def kind_of(version):
    """`decisora`, `definiciones` u `otra`, según el nombre de la versión."""
    if version.startswith(DEFINITIONS_PREFIX):
        return "definiciones"
    if version.startswith(DECISIVE_PREFIXES):
        return "decisora"
    return "otra"


def limits_of(version):
    """`(líneas, caracteres)` máximos de la versión; `None` donde no hay tope (las líneas del
    bloque de definiciones: lo acota el tope de cada instrucción que lo incluye)."""
    return {"decisora": (DECISIVE_LINES, DECISIVE_CHARS),
            "definiciones": (None, DEFINITIONS_CHARS),
            "otra": (OTHER_LINES, OTHER_CHARS)}[kind_of(version)]


def _read(path):
    return Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")


def effective_text(version, entry):
    """El texto que lee el modelo: el archivo de la instrucción con el bloque común de
    definiciones puesto donde tiene la marca, como lo arma `extraction.load_instruction`."""
    path = ROOT / entry["path"]
    raw = _read(path)
    if DEFINITIONS_MARK not in raw:
        return raw
    block_version = entry.get("definitions")
    if not block_version:
        raise ValueError(f"{version}: la instrucción trae la marca {DEFINITIONS_MARK} y la tabla "
                         "no dice qué versión del bloque de definiciones incluye")
    block = _read(path.parent / f"{block_version}.md")
    return raw.replace(DEFINITIONS_MARK, block.strip())


def length_problems(version, entry):
    """Los topes que la instrucción `version` no cumple: lista de textos (vacía si cumple)."""
    try:
        text = effective_text(version, entry)
    except (OSError, ValueError) as error:
        return [f"{version}: no se pudo leer ({error})"]
    max_lines, max_chars = limits_of(version)
    problems = []
    lines = len(text.splitlines())
    if max_lines is not None and lines > max_lines:
        problems.append(f"{version}: {lines} líneas, el tope es {max_lines}")
    if len(text) > max_chars:
        problems.append(f"{version}: {len(text)} caracteres, el tope es {max_chars}")
    return problems


def all_length_problems(table=None):
    table = SIMPLIFIED if table is None else table
    return [problem for version, entry in table.items()
            for problem in length_problems(version, entry)]


def descriptions_of(schema, path="$"):
    """`[(ruta, descripción)]` de cada `description` de un esquema JSON, a cualquier profundidad."""
    found = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "description" and isinstance(value, str):
                found.append((path, value))
            else:
                found.extend(descriptions_of(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for number, value in enumerate(schema):
            found.extend(descriptions_of(value, f"{path}[{number}]"))
    return found


def description_problems(name, schema):
    return [f"{name} {path}: descripción de {len(text)} caracteres, el tope es {DESCRIPTION_CHARS}"
            for path, text in descriptions_of(schema) if len(text) > DESCRIPTION_CHARS]


def load_schema(reference):
    module, function = reference.split(":")
    return getattr(importlib.import_module(module), function)()


def all_schema_problems(table=None):
    table = SIMPLIFIED_SCHEMAS if table is None else table
    return [problem for name, reference in table.items()
            for problem in description_problems(name, load_schema(reference))]


# --- Pruebas sobre las versiones listadas ---------------------------------------------------


def test_the_limits_are_the_ones_of_the_plan():
    """REQ-119 (umbral 5): los topes son los del plan 016 y el ADR-0070."""
    assert limits_of("matriz-extraccion-v13") == (90, 9000)
    assert limits_of("matriz-filtro-v10") == (90, 9000)
    assert limits_of("evaluacion-v13") == (90, 9000)
    assert limits_of("matriz-externa-v1") == (90, 9000)
    for other in ("matriz-completitud-v7", "matriz-union-v2", "matriz-consecuencias-v3",
                  "matriz-circulares-v8", "matriz-respaldo-v3", "contraste-v5", "clausulas-v6",
                  "reescritura-v3", "vision-v5", "ficha-v4", "ficha-renglon-v6",
                  "informe-tecnico-v3", "oferente-nombre-v3", "procedimiento-datos-v3",
                  "consulta-v5"):
        assert limits_of(other) == (50, 5000), other
    assert limits_of("matriz-definiciones-v9") == (None, 5000)
    assert DESCRIPTION_CHARS == 80


def test_every_listed_version_has_its_file():
    """REQ-119: cada versión de `SIMPLIFIED` es un archivo que existe y se llama como su clave."""
    for version, entry in SIMPLIFIED.items():
        path = ROOT / entry["path"]
        assert path.is_file(), f"{version}: no existe {entry['path']}"
        assert path.stem == version, f"{version}: el archivo es {path.name}"


def test_every_simplified_instruction_is_within_its_limit():
    """REQ-119 (umbral 5): ninguna instrucción de `SIMPLIFIED` pasa su tope de líneas ni de
    caracteres, con el bloque de definiciones incluido."""
    assert all_length_problems() == []


def test_every_simplified_schema_has_short_descriptions():
    """REQ-119 (umbral 5): cada descripción de campo de un esquema de `SIMPLIFIED_SCHEMAS` tiene
    80 caracteres o menos."""
    assert all_schema_problems() == []


# --- Las pruebas de verdad detectan lo que dicen detectar (versiones de prueba, inventadas) ----


def _instruction(tmp_path, name, lines, width=20):
    path = tmp_path / f"{name}.md"
    path.write_text("\n".join(("palabra " * (width // 8)).strip() for _ in range(lines)) + "\n",
                    encoding="utf-8")
    return {"path": path}


def test_a_compliant_test_version_passes(tmp_path):
    """REQ-119: una versión de prueba que cumple (decisora de 90 líneas, otra de 50) pasa."""
    table = {"matriz-filtro-v99": _instruction(tmp_path, "matriz-filtro-v99", 90),
             "matriz-union-v99": _instruction(tmp_path, "matriz-union-v99", 50)}

    assert all_length_problems(table) == []


def test_a_100_line_instruction_fails(tmp_path):
    """REQ-119 (umbral 5): una instrucción de prueba de 100 líneas falla, decisora o no, y la
    tabla que la lista hace fallar la prueba de las versiones listadas."""
    decisive = _instruction(tmp_path, "matriz-extraccion-v99", 100)
    other = _instruction(tmp_path, "matriz-completitud-v99", 51)

    assert length_problems("matriz-extraccion-v99", decisive) == [
        "matriz-extraccion-v99: 100 líneas, el tope es 90"]
    assert length_problems("matriz-completitud-v99", other) == [
        "matriz-completitud-v99: 51 líneas, el tope es 50"]


def test_the_listed_versions_test_fails_with_a_100_line_instruction(tmp_path, monkeypatch):
    """REQ-119 (umbral 5): con una instrucción de 100 líneas en `SIMPLIFIED`, la comprobación de
    las versiones listadas devuelve el fallo."""
    monkeypatch.setitem(SIMPLIFIED, "matriz-extraccion-v99",
                        _instruction(tmp_path, "matriz-extraccion-v99", 100))

    assert all_length_problems() != []


def test_the_character_limits_fail(tmp_path):
    """REQ-119 (umbral 5): 9.001 caracteres en una decisora, 5.001 en otra y 5.001 en el bloque
    de definiciones fallan; el tope exacto pasa."""
    path = tmp_path / "matriz-filtro-v99.md"
    path.write_text("a" * 9001, encoding="utf-8")
    assert length_problems("matriz-filtro-v99", {"path": path}) == [
        "matriz-filtro-v99: 9001 caracteres, el tope es 9000"]
    path.write_text("a" * 9000, encoding="utf-8")
    assert length_problems("matriz-filtro-v99", {"path": path}) == []

    path = tmp_path / "ficha-v99.md"
    path.write_text("a" * 5001, encoding="utf-8")
    assert length_problems("ficha-v99", {"path": path}) == [
        "ficha-v99: 5001 caracteres, el tope es 5000"]

    path = tmp_path / "matriz-definiciones-v99.md"
    path.write_text("a" * 5001, encoding="utf-8")
    assert length_problems("matriz-definiciones-v99", {"path": path}) == [
        "matriz-definiciones-v99: 5001 caracteres, el tope es 5000"]
    path.write_text("\n".join("a" for _ in range(200)), encoding="utf-8")
    assert length_problems("matriz-definiciones-v99", {"path": path}) == []


def test_the_definitions_block_counts_toward_the_limit(tmp_path):
    """REQ-119 (umbral 5): el bloque común de definiciones cuenta: una decisora de 60 líneas con
    un bloque de 40 pasa a 100 líneas y falla; si el bloque no está declarado, falla."""
    (tmp_path / "matriz-definiciones-v99.md").write_text(
        "\n".join(f"definición {n}" for n in range(40)) + "\n", encoding="utf-8")
    body = tmp_path / "matriz-extraccion-v99.md"
    body.write_text("\n".join(["regla"] * 59) + f"\n{DEFINITIONS_MARK}\n", encoding="utf-8")

    problems = length_problems("matriz-extraccion-v99",
                               {"path": body, "definitions": "matriz-definiciones-v99"})
    assert problems == ["matriz-extraccion-v99: 99 líneas, el tope es 90"]
    assert "no se pudo leer" in length_problems("matriz-extraccion-v99", {"path": body})[0]


def test_a_long_schema_description_fails():
    """REQ-119 (umbral 5): una descripción de campo de 81 caracteres falla, la de 80 pasa, a
    cualquier profundidad del esquema."""
    schema = {"type": "object", "properties": {
        "razonamiento": {"type": "string", "description": "x" * 80},
        "items": {"type": "array", "items": {"type": "object", "properties": {
            "cita": {"type": "string", "description": "y" * 81}}}}}}

    problems = description_problems("esquema-de-prueba", schema)

    assert len(problems) == 1
    assert "81 caracteres" in problems[0] and "cita" in problems[0]
    assert description_problems("esquema-de-prueba", {"description": "z" * 80}) == []


def test_the_real_schemas_are_loaded_by_reference(tmp_path, monkeypatch):
    """REQ-119: `SIMPLIFIED_SCHEMAS` carga el esquema por «módulo:función» y comprueba sus
    descripciones; un esquema con una descripción larga hace fallar la comprobación."""
    module = tmp_path / "esquema_de_prueba_t278.py"
    module.write_text("def schema():\n    return {'description': '" + "w" * 90 + "'}\n",
                      encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(SIMPLIFIED_SCHEMAS, "prueba", "esquema_de_prueba_t278:schema")

    assert len(all_schema_problems()) == 1


def test_the_listed_block_is_the_one_the_code_includes(settings):
    """REQ-119 (O-278-5 de la verificación de T-278): en las instrucciones vigentes de la matriz, la
    versión del bloque de definiciones que declara `SIMPLIFIED` es la que incluye el código
    (`MATRIX_PROMPT_VERSIONS["definiciones"]`): el largo se mide sobre lo que lee el modelo."""
    active = set(settings.MATRIX_PROMPT_VERSIONS.values())
    block = settings.MATRIX_PROMPT_VERSIONS["definiciones"]

    listed = {version: entry["definitions"] for version, entry in SIMPLIFIED.items()
              if version in active and entry.get("definitions")}

    assert listed and all(value == block for value in listed.values()), listed
