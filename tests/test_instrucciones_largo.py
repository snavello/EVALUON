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
unión de la matriz; T-280: el filtro, las consecuencias, las circulares, los cambios de las
circulares y el respaldo; T-281: la evaluación, el contraste, las cláusulas y la reescritura), y
T-282 agrega la prueba de que toda instrucción vigente figura en la tabla. `SIMPLIFIED_SCHEMAS` hace
lo mismo con los esquemas de salida (T-281: los de la evaluación, el contraste, las cláusulas y la
reescritura).

T-281 (H-280-4, d, de la verificación de T-280): el tope del razonamiento que dice cada instrucción
(«de hasta N caracteres») es el del esquema que se manda con el pedido, o hasta
`REASONING_MARGIN` caracteres menos (el esquema corta la salida en su tope: la instrucción pide un
poco menos para que el modelo termine la oración).

La tabla también la usan `test_instrucciones_sin_casos.py` y `test_instrucciones_revisadas.py`:
una versión que se suma acá queda sujeta a las tres pruebas.

Los textos de estas pruebas son inventados (P4).
"""

import importlib
import re
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
    # T-279: la matriz, parte 1 (el bloque común y las tres instrucciones que lo incluyen). T-285: el
    # bloque v10 y la extracción v14 (ajuste único del paso 2); la completitud v7 y la unión v2 siguen
    # y leen el bloque v10.
    "matriz-definiciones-v10": {"path": "evaluon/tenders/prompts/matriz-definiciones-v10.md"},
    "matriz-extraccion-v14": {"path": "evaluon/tenders/prompts/matriz-extraccion-v14.md",
                              "definitions": "matriz-definiciones-v10"},
    "matriz-completitud-v7": {"path": "evaluon/tenders/prompts/matriz-completitud-v7.md",
                              "definitions": "matriz-definiciones-v10"},
    "matriz-union-v2": {"path": "evaluon/tenders/prompts/matriz-union-v2.md",
                        "definitions": "matriz-definiciones-v10"},
    # T-280: la matriz, parte 2 (el filtro incluye el bloque; las otras cuatro no lo llevan). T-285:
    # el filtro v11.
    "matriz-filtro-v11": {"path": "evaluon/tenders/prompts/matriz-filtro-v11.md",
                          "definitions": "matriz-definiciones-v10"},
    "matriz-consecuencias-v3": {"path": "evaluon/tenders/prompts/matriz-consecuencias-v3.md"},
    "matriz-circulares-v8": {"path": "evaluon/tenders/prompts/matriz-circulares-v8.md"},
    "matriz-circulares-cambios-v7": {
        "path": "evaluon/tenders/prompts/matriz-circulares-cambios-v7.md"},
    "matriz-respaldo-v3": {"path": "evaluon/tenders/prompts/matriz-respaldo-v3.md"},
    # T-281: la evaluación (decisora), el contraste, las cláusulas y la reescritura.
    "evaluacion-v14": {"path": "evaluon/assessment/prompts/evaluacion-v14.md"},  # T-285
    "contraste-v5": {"path": "evaluon/assessment/prompts/contraste-v5.md"},
    "clausulas-v6": {"path": "evaluon/assessment/prompts/clausulas-v6.md"},
    "reescritura-v3": {"path": "evaluon/offers/prompts/reescritura-v3.md"},
    # T-282: las auxiliares (visión, ficha, ficha por renglón, informe técnico, nombre del oferente,
    # datos del procedimiento y consulta). Desde acá toda instrucción vigente está en la tabla
    # (`test_instrucciones_revisadas.test_every_current_instruction_is_simplified`).
    "vision-v6": {"path": "evaluon/assessment/prompts/vision-v6.md"},  # T-285
    "ficha-v4": {"path": "evaluon/offers/prompts/ficha-v4.md"},
    "ficha-renglon-v6": {"path": "evaluon/offers/prompts/ficha-renglon-v6.md"},
    "informe-tecnico-v3": {"path": "evaluon/assessment/prompts/informe-tecnico-v3.md"},
    "oferente-nombre-v3": {"path": "evaluon/offers/prompts/oferente-nombre-v3.md"},
    "procedimiento-datos-v3": {"path": "evaluon/tenders/prompts/procedimiento-datos-v3.md"},
    "consulta-v6": {"path": "evaluon/queries/prompts/consulta-v6.txt"},  # T-285
    # T-291: la instrucción propia del modelo externo de la matriz (decisora), con el bloque v10.
    # T-294: la v2 (ajuste único del paso 3) reemplaza a la v1, que sigue publicada.
    "matriz-externa-v2": {"path": "evaluon/tenders/prompts/matriz-externa-v2.md",
                          "definitions": "matriz-definiciones-v10"},
    # T-299: la instrucción propia del verificador externo de citas (no decisora: 50 y 5.000).
    "verificador-v1": {"path": "evaluon/assessment/prompts/verificador-v1.md"},
}

# Los esquemas de salida de las instrucciones simplificadas: `{nombre: "módulo:atributo"}`; el
# atributo es el esquema JSON o una función sin argumentos que lo devuelve.
SIMPLIFIED_SCHEMAS = {
    # T-281: los que se mandan con los pedidos de la evaluación (el de lectura, con un alias de cada
    # clase), del contraste, del contraste por cláusula y de la reescritura.
    "evaluacion-v14": "tests.test_instrucciones_largo:evaluation_output_schema",  # T-285
    "contraste-v5": "evaluon.assessment.prompting:CONTRAST_SCHEMA",
    "clausulas-v6": "evaluon.assessment.prompting:CLAUSES_SCHEMA",
    "reescritura-v3": "evaluon.offers.services.sheets:REWRITE_SCHEMA",
    # T-282: los de la ficha (fila común y renglón), el informe técnico, el nombre del oferente, los
    # datos del procedimiento y la consulta. La visión no tiene esquema: su salida es texto plano.
    "ficha-v4": "tests.test_instrucciones_largo:sheet_schema",
    "ficha-renglon-v6": "tests.test_instrucciones_largo:item_sheet_schema",
    "informe-tecnico-v3": "tests.test_instrucciones_largo:technical_report_schema",
    "oferente-nombre-v3": "evaluon.offers.proposal_fields:MODEL_SCHEMA",
    "procedimiento-datos-v3": "evaluon.tenders.proposal.procedure_fields:MODEL_SCHEMA",
    "consulta-v6": "tests.test_instrucciones_largo:query_schema",  # T-285
    # T-299: el del verificador externo de citas (sin largos: los valida el código).
    "verificador-v1": "evaluon.assessment.verifier:OUTPUT_SCHEMA",
}


def evaluation_output_schema():
    """El esquema de un pedido de lectura de la evaluación con un documento, un fundamento y un dato
    del Portal (`prompting.evaluation_schema`)."""
    from evaluon.assessment import prompting

    return prompting.evaluation_schema(["D1"], ["N1"], ["P1"])


def sheet_schema():
    """El esquema de un pedido de la ficha para una fila común, con un pasaje (`sheets.build_schema`)."""
    from evaluon.offers.services import sheets

    return sheets.build_schema(["P1"], False)


def item_sheet_schema():
    """El de una fila por renglón, con la cotización."""
    from evaluon.offers.services import sheets

    return sheets.build_schema(["P1"], True)


def technical_report_schema():
    """El del informe técnico, con un renglón (`technical_report._schema`)."""
    from evaluon.assessment.services import technical_report

    return technical_report._schema({1})


def query_schema():
    """El de la consulta con fecha, con una unidad (`answering.build_schema`)."""
    from evaluon.queries import answering

    return answering.build_schema(["U1"], version=answering.PROMPT_VERSION_WITH_DATE)

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
    module, attribute = reference.split(":")
    found = getattr(importlib.import_module(module), attribute)
    return found() if callable(found) else found


def all_schema_problems(table=None):
    table = SIMPLIFIED_SCHEMAS if table is None else table
    return [problem for name, reference in table.items()
            for problem in description_problems(name, load_schema(reference))]


# --- Pruebas sobre las versiones listadas ---------------------------------------------------


def test_the_limits_are_the_ones_of_the_plan():
    """REQ-119 (umbral 5): los topes son los del plan 016 y el ADR-0070."""
    assert limits_of("matriz-extraccion-v14") == (90, 9000)
    assert limits_of("matriz-filtro-v11") == (90, 9000)
    assert limits_of("evaluacion-v14") == (90, 9000)
    assert limits_of("matriz-externa-v2") == (90, 9000)
    for other in ("matriz-completitud-v7", "matriz-union-v2", "matriz-consecuencias-v3",
                  "matriz-circulares-v8", "matriz-circulares-cambios-v7", "matriz-respaldo-v3",
                  "contraste-v5", "clausulas-v6",
                  "reescritura-v3", "vision-v6", "ficha-v4", "ficha-renglon-v6",
                  "informe-tecnico-v3", "oferente-nombre-v3", "procedimiento-datos-v3",
                  "consulta-v6", "verificador-v1"):
        assert limits_of(other) == (50, 5000), other
    assert limits_of("matriz-definiciones-v10") == (None, 5000)
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


# --- T-281 (H-280-4, d): el tope del razonamiento que dice la instrucción y el del esquema --------

# Lo que la instrucción puede pedir por debajo del tope del esquema, como máximo.
REASONING_MARGIN = 100
SAID_LIMIT = re.compile(r'"razonamiento"[^\n]*?de hasta (\d+) caracteres')


def said_reasoning_limit(text):
    """El tope del razonamiento que dice la instrucción («"razonamiento"… de hasta N caracteres»), o
    `None` si no lo dice."""
    match = SAID_LIMIT.search(text)
    return int(match.group(1)) if match else None


def reasoning_problem(name, said, schema_limit):
    """Por qué el tope que dice la instrucción no es el del esquema, o `""`."""
    if said is None:
        return f"{name}: la instrucción no dice el tope del razonamiento"
    if not 0 <= schema_limit - said <= REASONING_MARGIN:
        return (f"{name}: la instrucción dice {said} caracteres y el esquema corta en {schema_limit} "
                f"(margen admitido: de 0 a {REASONING_MARGIN})")
    return ""


def _current_reasoning_limits():
    """`{nombre: (texto vigente, tope del esquema)}` de las instrucciones vigentes que piden un
    razonamiento con tope: la evaluación, el contraste, las cláusulas y las dos preguntas del
    filtro."""
    from evaluon.assessment import prompting
    from evaluon.tenders.proposal import filter as row_filter

    first, second = row_filter.load_prompts()
    item_a = row_filter.schema_a(["F1"])["properties"]["F1"]["properties"]
    item_b = row_filter.schema_b(["F1"])["properties"]["F1"]["properties"]
    return {
        "evaluacion": (prompting.load_prompt("evaluacion"),
                       evaluation_output_schema()["properties"]["razonamiento"]["maxLength"]),
        "contraste": (prompting.load_prompt("contraste"),
                      prompting.CONTRAST_SCHEMA["properties"]["razonamiento"]["maxLength"]),
        "clausulas": (prompting.load_prompt("clausulas"),
                      prompting.CLAUSES_SCHEMA["properties"]["razonamiento"]["maxLength"]),
        "filtro_a": (first, item_a["razonamiento"]["maxLength"]),
        "filtro_b": (second, item_b["razonamiento"]["maxLength"]),
    }


def test_the_reasoning_limit_of_each_instruction_is_the_one_of_its_schema():
    """REQ-119, ADR-0055 regla 2 (H-280-4, d): el tope del razonamiento que dice cada instrucción
    vigente es el del esquema que se manda con el pedido, o hasta 100 caracteres menos: el filtro
    dice 400 y corta en `filter.REASONING_MAX_CHARS`; la evaluación, el contraste y las cláusulas
    piden 600, 400 y 400 con un margen de 100."""
    from evaluon.assessment import prompting
    from evaluon.tenders.proposal import filter as row_filter

    limits = _current_reasoning_limits()
    problems = [reasoning_problem(name, said_reasoning_limit(text), limit)
                for name, (text, limit) in limits.items()]

    assert [problem for problem in problems if problem] == []
    assert limits["filtro_a"][1] == limits["filtro_b"][1] == row_filter.REASONING_MAX_CHARS
    assert limits["evaluacion"][1] == prompting.REASONING_MAX_CHARS
    assert limits["contraste"][1] == limits["clausulas"][1] == prompting.CONTRAST_REASONING_MAX_CHARS


def test_the_reasoning_check_fails_when_the_schema_or_the_instruction_changes(monkeypatch):
    """REQ-119 (H-280-4, d; la alteración F14 de la verificación de T-280): bajar el tope del esquema
    del filtro a 300 con la instrucción en 400, subir el del esquema muy por encima de lo que dice la
    instrucción o quitar el tope de la instrucción hace fallar la comprobación."""
    from evaluon.tenders.proposal import filter as row_filter

    monkeypatch.setitem(row_filter._REASONING, "maxLength", 300)
    limits = _current_reasoning_limits()
    text, limit = limits["filtro_a"]
    assert limit == 300
    assert "dice 400 caracteres y el esquema corta en 300" in reasoning_problem(
        "filtro_a", said_reasoning_limit(text), limit)

    assert reasoning_problem("prueba", 600, 900)
    assert reasoning_problem("prueba", None, 700)
    assert said_reasoning_limit('- "razonamiento": una oración, de hasta 400 caracteres, que dice') == 400
    assert reasoning_problem("prueba", 600, 700) == "" and reasoning_problem("prueba", 400, 400) == ""


# --- T-282 (H-281-3): los topes del razonamiento, fijos en una tabla de control ---------------------

# `{instrucción: (lo que dice la instrucción, lo que corta el esquema)}`. El margen de 0 a 100 de
# `reasoning_problem` deja pasar una deriva dentro del margen (bajar el esquema de la evaluación de 700
# a 600, o que la instrucción diga 700): esta tabla la ata a los valores de hoy. Cambiar un tope pide
# cambiar esta tabla en el mismo commit, a la vista.
REASONING_LIMITS = {
    "evaluacion": (600, 700),
    "contraste": (400, 500),
    "clausulas": (400, 500),
    "filtro_a": (400, 400),
    "filtro_b": (400, 400),
}


def reasoning_limit_changes(limits, expected=None):
    """Las instrucciones cuyo tope dicho o del esquema no es el de la tabla de control: lista de
    textos, vacía si todos coinciden (y si están todas las de la tabla, y solo ellas)."""
    expected = REASONING_LIMITS if expected is None else expected
    found = {name: (said_reasoning_limit(text), limit) for name, (text, limit) in limits.items()}
    problems = [f"{name}: dice {said} y el esquema corta en {limit}; la tabla dice "
                f"{expected[name][0]} y {expected[name][1]}"
                for name, (said, limit) in found.items()
                if name in expected and (said, limit) != expected[name]]
    problems += [f"{name}: no está en la tabla de control" for name in found if name not in expected]
    problems += [f"{name}: ya no se comprueba" for name in expected if name not in found]
    return problems


def test_the_reasoning_limits_are_the_ones_of_the_control_table():
    """REQ-119, ADR-0055 regla 2 (H-281-3 de la verificación de T-281): el tope que dice cada
    instrucción y el del esquema son exactamente los de `REASONING_LIMITS`, sin el margen de 100."""
    assert reasoning_limit_changes(_current_reasoning_limits()) == []


def test_the_control_table_catches_a_drift_inside_the_margin(monkeypatch):
    """REQ-119 (H-281-3; alteraciones d3, d8 y d12 de la verificación de T-281): bajar el esquema de
    la evaluación de 700 a 600, o que la instrucción de la evaluación diga 700 o la de las cláusulas
    500, pasa el margen de 100 pero no la tabla de control."""
    from evaluon.assessment import prompting

    monkeypatch.setattr(prompting, "REASONING_MAX_CHARS", 600)
    limits = _current_reasoning_limits()
    assert limits["evaluacion"][1] == 600
    assert reasoning_problem("evaluacion", said_reasoning_limit(limits["evaluacion"][0]), 600) == ""
    assert any(p.startswith("evaluacion:") for p in reasoning_limit_changes(limits))

    monkeypatch.undo()
    limits = _current_reasoning_limits()
    for name, said in (("evaluacion", 700), ("clausulas", 500)):
        text, limit = limits[name]
        altered = dict(limits)
        altered[name] = (re.sub(r'(?<="razonamiento")([^\n]*?de hasta )\d+', rf"\g<1>{said}", text,
                                count=1), limit)
        assert reasoning_problem(name, said, limit) == ""
        assert [p for p in reasoning_limit_changes(altered) if p.startswith(f"{name}:")]
