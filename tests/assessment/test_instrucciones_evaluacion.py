"""Las instrucciones de la evaluación: evaluación, contraste y cláusulas (REQ-104, REQ-105,
REQ-106; plan 015, "Flujo de IA · Evaluación"; ADR-0055; T-237).

Se comprueba la forma: sin las reglas que empujan al error, con las definiciones y el bloque del
Portal, ejemplos balanceados que coinciden con el esquema y con la regla que deriva el resultado, y
versiones publicadas congeladas (como `scripts/models.sha256` con los modelos). Sin modelo ni GPU:
el uso real se mide en T-239. Textos inventados (P4).

T-281 (spec 016, REQ-119; ADR-0070): las vigentes eran `evaluacion-v13` (desde T-285, la v14), `contraste-v5`,
`clausulas-v6` y `reescritura-v3`, cortas y sin ejemplos. Cada prueba de la 015 lee la versión
publicada que nombra (la que tenía los ejemplos y las frases que comprueba) y suma la comprobación
de la misma decisión sobre la vigente, con sus frases; el esqueleto de la salida de cada vigente se
compara con su esquema (`tests/tenders/test_esqueleto_salida.py`).
"""

import json
import re
from collections import Counter

import pytest
from django.conf import settings

from evaluon.assessment import combine, prompting

PROMPTS = prompting.PROMPTS_DIR

# Huellas SHA-256 (saltos de línea normalizados) de las versiones publicadas. Un archivo publicado
# no se edita: un cambio de texto es una versión nueva y se suma acá (REQ-106, P6).
FROZEN = {
    "evaluacion-v5": "7da641687e8b6163fb4447018aea094f0c0f6a591add203c6fefb55d0e402e20",
    "contraste-v2": "b01e7d6a1411efe1525d04af87723c48832ee62e8779e5d8729e08cf8eff8ac2",
    "clausulas-v2": "c791fe4d723a75053ee4716eda2adec258ca2e1729f9d7d641db996f5c82fa28",
    "evaluacion-v6": "a21614b9f64e6bd5455ed1990b0a358303420b313ab267cadcdde1bfeb363f16",
    "contraste-v3": "48533ad102f79ffe3cb3c1b872d1d42b2eba73a69b6dbd60139031068d9ca787",
    "clausulas-v3": "c352ed616e33cfc9e039625e44ddcccf58fd4dd8b95daf9636af7aeab5cf189c",
    "evaluacion-v7": "621dfb1c6c01d1e90fec301723f396881e55d0bf2c1d7a38a1507a4f6a41352c",
    "contraste-v4": "cb9b4a7aa7eb1b1d326ea8ba50c475ef548d9ba1c990b6c25d78e048c7e49fdc",
    "clausulas-v4": "96e9e2b445205ec192ecef944c167d99fc2d8157eed0255bb99a552e3562721f",
    "evaluacion-v8": "e2242a56f4e449f9fd88e02de1ffa0781817a390b604343fa469467579434951",
    "clausulas-v5": "a5d31f046c157bb4f7fc4f90be5153b5355bec316d15e9528b3faafe061d10cc",
    "evaluacion-v9": "5cff8082a2dc41fea7c45a5dccf19d9ecd16afda90a90c22e57208ab8b6d585c",
    "evaluacion-v10": "b62a708808a40465b83b3899b777aa7026939d8adcfbb2ba32314e2f5826db2f",
    "evaluacion-v11": "f4820bba8e67e515a35cbcd755759265af999ce4a40657e436954eea0d4b87a8",
    "evaluacion-v12": "99d76d7c48c05c2402cf05d68fec24367d871bccd66bd7ab1f43a08ea6a3c7ea",
    # T-281 (spec 016, REQ-119; ADR-0070): cortas, sin ejemplos.
    "evaluacion-v13": "380b4869c5bbd41e9045d7179a9dad4b2f8dbbb4a9852fe30c8f2acfacd567fd",
    "contraste-v5": "6e29204e34714e9e0e3b9925f00d7203025d7ac3b7441c223fafe0147b3bc7e2",
    "clausulas-v6": "439b2797df3c69576676ce3c338717a3b8e5a1289818e2e6704a8302de369f26",
    # T-285 (ajuste único del paso 2): hallazgos de T-283 como definiciones generales.
    "evaluacion-v14": "4480962ca24e766ba358a499dac01349c44ed47fc61708a3c74385234a7b2c9b",
}

# Reglas que empujaban al error (informe de revisión, 4.7 a 4.9).
FORBIDDEN = ("fragmento mínimo", "fragmento más corto", "ante la duda", "por sí sola",
             "por sí solo", "dividí", "o dudás")


# Las últimas versiones publicadas con ejemplos (T-281: las vigentes no los traen, ADR-0070).
WITH_EXAMPLES = {"evaluacion": "evaluacion-v12", "contraste": "contraste-v4",
                 "clausulas": "clausulas-v5"}


def text_of(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def current(name):
    return text_of(settings.ASSESSMENT_PROMPT_VERSIONS[name])


def examples_of(name):
    """Las líneas JSON de la sección de ejemplos de la última versión publicada de `name` que los
    trae (`WITH_EXAMPLES`)."""
    body = text_of(WITH_EXAMPLES[name])
    section = body[body.index("EJEMPLOS"):]
    return [json.loads(line) for line in section.splitlines() if line.startswith("{")]


def test_the_current_versions_are_the_new_ones_and_exist():
    """REQ-106: `ASSESSMENT_PROMPT_VERSIONS` apunta a las versiones nuevas y los archivos existen."""
    assert settings.ASSESSMENT_PROMPT_VERSIONS == {
        "evaluacion": "evaluacion-v14", "contraste": "contraste-v5", "clausulas": "clausulas-v6"}
    for name in settings.ASSESSMENT_PROMPT_VERSIONS:
        assert prompting.load_prompt(name)


@pytest.mark.parametrize("version, digest", sorted(FROZEN.items()))
def test_the_published_versions_are_frozen(version, digest):
    """REQ-106, P6: el texto de una versión publicada no cambia; la huella que cada pedido registra
    es la de este archivo."""
    assert prompting.prompt_hash(text_of(version)) == digest


def test_the_recorded_hash_is_the_one_of_the_current_file():
    """REQ-106: `prompt_record` da la versión y la huella del archivo vigente."""
    for name, version in settings.ASSESSMENT_PROMPT_VERSIONS.items():
        record = prompting.prompt_record(name)
        assert record == {"nombre": name, "version": version, "sha256": FROZEN[version]}
    assert prompting.prompt_hashes() == {
        name: FROZEN[version] for name, version in settings.ASSESSMENT_PROMPT_VERSIONS.items()}


@pytest.mark.parametrize("name", ["evaluacion", "contraste", "clausulas"])
def test_the_instructions_have_none_of_the_rules_that_push_to_error(name):
    """REQ-104, REQ-106: ni el fragmento mínimo, ni «ante la duda», ni juzgar la cita «por sí
    sola», ni dividir."""
    body = current(name).lower()
    for phrase in FORBIDDEN:
        assert phrase not in body, phrase


def test_the_instruction_states_the_limit_of_six_conditions():
    """O-237-1: la instrucción dice el tope de condiciones del esquema y qué hacer con las que
    sobran: se juntan en la última y valen con la misma regla (la v12 publicada y la vigente)."""
    body = text_of("evaluacion-v12")
    assert prompting.CONDITIONS_MAX == 6 and "hasta seis" in body
    assert "juntá las que sobran en la sexta" in body
    assert prompting.evaluation_schema(["D1"], [])["properties"]["condiciones"]["maxItems"] == 6
    body = current("evaluacion")
    assert "hasta seis" in body and "las que sobran van juntas en la sexta" in body


def test_the_evaluation_asks_for_the_whole_sentence_and_each_condition():
    """REQ-104: la cita es la oración completa; se revisa cada condición con su dato, su cita y su
    resultado; «cumple» solo si todas; la duda se declara con su razón (la v12 publicada y, con sus
    frases, la vigente)."""
    body = text_of("evaluacion-v12")
    assert "oración completa" in body and "LETRA POR LETRA" in body
    assert '"condiciones"' in body and '"dato"' in body and '"cita"' in body
    assert 'solo si TODAS las condiciones cumplen' in body
    assert '"no_cumple" si alguna no cumple' in body
    assert 'si falta el dato de alguna condición' in body
    assert "La duda no es un motivo" in body and "qué dato falta o qué texto contradice" in body
    assert "No supongas el dato de una condición" in body
    # D-237-2: cada condición cumple o no cumple con su propio dato y su propia cita
    assert "solo con su propio dato (no vacío) y su propia cita" in body
    body = current("evaluacion")
    assert "la oración completa, copiada letra por letra" in body
    assert '"condiciones"' in body and '"dato"' in body and '"cita"' in body
    assert '"cumple" si todas cumplen' in body and '"no_cumple" si alguna no cumple' in body
    assert '"no_determinado" si a alguna le falta el dato' in body
    assert "La duda no es un motivo: si falta un dato, decí cuál falta" in body
    assert "nombra el dato que falta o el texto que contradice" in body
    assert "No supongas un dato" in body
    assert "solo con su propio dato y su propia cita" in body
    # ADR-0055: el razonamiento, primero y antes de decidir
    assert '"razonamiento": de dos a cuatro oraciones, de hasta 600 caracteres, antes de decidir' in body


def test_the_evaluation_explains_the_portal_block_and_how_to_cite_it():
    """REQ-103, REQ-104: el bloque `[P…]` del Portal, qué es y cómo se cita (la v12 publicada). La
    vigente lo dice sin repetir lo que el código garantiza (que el sistema escribe la cita del
    Portal): el dato del Portal es oficial, se cita por su alias y, si no coincide con la oferta, se
    citan los dos (decisión del 2026-10-15, enmienda del ADR-0053)."""
    body = text_of("evaluacion-v12")
    assert "[P1]" in body and "Datos del Portal" in body
    assert '{"documento": "P1"' in body
    assert "el sistema escribe la cita del portal" in body.lower().replace("\n", " ")
    assert "<<<" in body and ">>>" in body    # la oración que se evalúa va marcada
    body = current("evaluacion")
    assert "[P1]" in body and "datos del Portal" in body
    assert "Son datos oficiales: valen como fundamento igual que el texto de la oferta" in body
    assert "Solo se cita de [D] y de [P]" in body
    assert ("Un dato del Portal que dice lo que la condición pide sostiene \"cumple\" o \"no_cumple\" "
            "igual que un texto de la oferta") in body
    assert ("Si la oferta y el Portal dan valores distintos para un mismo dato, citá los dos: la "
            "Comisión decide cuál rige") in body
    assert "<<<" in body and ">>>" in body


def test_the_question_is_for_the_commission_with_requirement_conclusion_and_text():
    """REQ-105: la pregunta va a la Comisión, nombra el requisito, la conclusión y el texto, y
    nunca le pide algo al oferente (la v12 publicada y, con sus frases, la vigente)."""
    body = text_of("evaluacion-v12")
    assert "es para la Comisión, nunca para el oferente" in body
    assert "nombre el requisito, tu conclusión y el texto" in body
    assert "pedirle algo al oferente es una subsanación" in body
    assert "Lo externo es la verificación en el registro o en la base" in body
    body = current("evaluacion")
    assert ("una pregunta dirigida a la Comisión que nombra el requisito, tu conclusión y el texto "
            "que leíste") in body
    assert "Nunca le pide un dato ni un documento al oferente" in body
    assert "pedirle algo es una subsanación y la decide la Comisión" in body
    assert "una consulta que hace la Comisión fuera de la oferta" in body
    assert ("Lo que la oferta presenta, como una declaración o una constancia, se evalúa como "
            "cualquier documento") in body


def test_the_schema_order_in_the_instruction_is_the_one_of_the_schema():
    """REQ-104, ADR-0055: la instrucción nombra los campos en el orden del esquema, y el cierre del
    mensaje (tres líneas) también. La v12 publicada lo dice en su línea de formato; la vigente, en su
    esqueleto, que tiene las claves del esquema en el mismo orden."""
    order = list(prompting.evaluation_schema(["D1"], [], ["P1"])["properties"])
    body = text_of("evaluacion-v12")
    format_line = next(line for line in body.splitlines() if line.startswith('{"razonamiento"'))
    first = [format_line.index(f'"{name}"') for name in order[:order.index("condiciones") + 1]]
    last = [format_line.rindex(f'"{name}"') for name in order[order.index("resultado"):]]
    assert first == sorted(first) and last == sorted(last)
    assert first[-1] < last[0]   # las condiciones antes del resultado
    assert prompting.CLOSING.count("\n") == 2   # tres líneas
    assert prompting.CLOSING.index("razonamiento") < prompting.CLOSING.index("condiciones") < (
        prompting.CLOSING.index("resultado"))
    skeleton = skeleton_of(current("evaluacion"))
    assert list(skeleton) == order
    assert list(skeleton["condiciones"][0]) == ["condicion", "dato", "cita", "resultado"]


def parse(example):
    return prompting.parse_evaluation(json.dumps(example), ["D1", "D2", "D3", "D4", "P1"], [])


def test_the_evaluation_examples_are_balanced():
    """REQ-106, ADR-0055 regla 4 (T-240, T-257): 7 «cumple» (uno con el Portal), 3 «no cumple», 3
    «no consta» y 5 «no determinado» (T-257 suma la opción que la oferta no usa, lo que solo se
    permite y el requisito negativo que nada contradice); ningún resultado pasa del 40 % del total;
    el Portal se cita en uno que cumple. T-281: los ejemplos son de la v12 publicada; la vigente no
    los trae (ADR-0070) y su esqueleto lo prueba `test_the_current_instructions_have_only_the_skeleton`."""
    examples = examples_of("evaluacion")
    counts = Counter(e["resultado"] for e in examples)
    assert counts == {"cumple": 7, "no_cumple": 3, "no_consta": 3, "no_determinado": 5}
    assert max(counts.values()) / len(examples) <= 0.4
    with_portal = [e for e in examples if any(c["documento"] == "P1" for c in e["citas"])]
    assert any(e["resultado"] == "cumple" for e in with_portal)
    # un requisito de dos condiciones que cumple y uno que no puede determinar una de ellas
    assert any(e["resultado"] == "cumple" and len(e["condiciones"]) == 2 for e in examples)
    assert any(e["resultado"] == "no_determinado"
               and {c["resultado"] for c in e["condiciones"]} >= {"cumple", "no_determinado"}
               for e in examples)


def test_the_evaluation_examples_follow_the_schema_and_the_derivation_rule():
    """REQ-104: cada ejemplo tiene los campos en el orden del esquema, se lee con el código, su
    `resultado` es el que se deriva de sus condiciones, cada cita de condición apunta a una cita
    que existe, y ninguna pregunta se dirige al oferente."""
    order = list(prompting.evaluation_schema(["D1"], [], ["P1"])["properties"])
    for example in examples_of("evaluacion"):
        assert list(example) == order
        parsed = parse(example)
        assert prompting.derive_result(parsed.conditions) == example["resultado"]
        for condition in parsed.conditions:
            assert condition.cite <= len(parsed.citations)
            if condition.result in ("cumple", "no_cumple"):
                assert condition.cite >= 1 and condition.datum
            else:
                assert condition.cite == 0 or condition.result == "no_determinado"
        assert not combine.addresses_offeror(example["pregunta"]), example["pregunta"]
        assert 2 <= len(re.findall(r"[.!?](?:\s|$)", example["razonamiento"])) <= 4
        assert len(example["razonamiento"]) <= prompting.REASONING_MAX_CHARS
        if example["resultado"] == "no_determinado":
            assert example["pregunta"]    # lo que la Comisión puede aclarar, preguntado


def test_the_contrast_examples_reason_first_and_include_a_partial_of_two_conditions():
    """REQ-104, REQ-106: el contraste razona antes de responder; hay un «parcial» de un requisito
    de dos condiciones; las respuestas están repartidas (ninguna pasa del 60 %). Los ejemplos son de
    la v4 publicada; la vigente dice el contexto, el Portal y el «parcial» de varias condiciones."""
    examples = examples_of("contraste")
    assert all(list(e) == ["razonamiento", "respuesta"] for e in examples)
    counts = Counter(e["respuesta"] for e in examples)
    assert set(counts) == {"si", "no", "parcial"} and max(counts.values()) / len(examples) <= 0.6
    assert any("dos condiciones" in e["razonamiento"] and e["respuesta"] == "parcial"
               for e in examples)
    body = text_of("contraste-v4")
    assert "Contexto en la misma página" in body and "Datos del Portal" in body
    for example in examples:
        assert prompting.parse_contrast(json.dumps(example))[0] == example["respuesta"]
    body = current("contraste")
    assert "el contexto en la misma página" in body and "datos del Portal" in body
    assert ("Si el requisito tiene varias condiciones y el texto responde solo a algunas, es "
            '"parcial" y el razonamiento dice cuál falta') in body
    assert "con las mismas palabras o con otras equivalentes, alcanza" in body


def test_the_clauses_examples_put_the_motive_before_the_state_and_ask_the_commission():
    """REQ-104, REQ-105: el contraste por cláusula razona primero, el motivo va antes del estado
    y la pregunta del ejemplo es para la Comisión, con la cláusula y lo que se leyó. Los ejemplos son
    de la v5 publicada; la vigente lo dice con sus frases."""
    examples = examples_of("clausulas")
    assert examples
    for example in examples:
        assert list(example) == ["razonamiento", "clausulas", "pregunta"]
        for clause in example["clausulas"]:
            assert list(clause) == ["clausula", "motivo", "estado", "cita"]
        assert prompting.parse_clauses(json.dumps(example))[0]
        assert not combine.addresses_offeror(example["pregunta"]), example["pregunta"]
    asked = [e["pregunta"] for e in examples if e["pregunta"]]
    assert asked and all("Comisión" in q for q in asked)
    assert all(re.search(r"Renglón \d", q) for q in asked)
    # O-237-2: el motivo nunca va vacío, ni en el texto ni en los ejemplos
    assert "Nunca va vacío" in text_of("clausulas-v5") and "(vacío si" not in text_of("clausulas-v5")
    assert all(clause["motivo"] for e in examples for clause in e["clausulas"])
    body = current("clausulas")
    assert '"motivo": una oración, nunca vacía' in body and "Va antes del estado" in body
    assert "(vacío si" not in body
    assert ("una pregunta dirigida a la Comisión que nombra el renglón, la cláusula y lo que se leyó "
            "en la oferta") in body
    assert "Nunca le pide nada al oferente" in body


def test_a_retry_message_has_no_the_old_suggestion():
    """REQ-104: el aviso del reintento ya no sugiere «no_determinado» sin más: pide la oración
    completa y nombra la cita que no se encontró."""
    text = prompting.correction_for(prompting.ANOMALY_NO_CITATION, ["Texto  que\nno está"])
    assert "«Texto que no está»" in text and "oración completa" in text
    assert "respondé \"no_determinado\"" not in text


# --- T-281: las vigentes, cortas y sin ejemplos (spec 016, REQ-119; ADR-0070) -------------------------

from tests.tenders.test_esqueleto_salida import shape_problems  # noqa: E402

# El esquema que se manda con cada pedido de las vigentes (la evaluación, con un alias de cada clase).
CURRENT_SCHEMAS = {
    "evaluacion": lambda: prompting.evaluation_schema(["D1"], ["N1"], ["P1"]),
    "contraste": lambda: prompting.CONTRAST_SCHEMA,
    "clausulas": lambda: prompting.CLAUSES_SCHEMA,
}


def skeleton_of(text):
    """El esqueleto de la salida: la única línea de la instrucción que es un objeto JSON."""
    lines = [line for line in text.splitlines() if line.startswith("{")]
    assert len(lines) == 1, f"se esperaba una línea de esqueleto y hay {len(lines)}"
    return json.loads(lines[0])


@pytest.mark.parametrize("name", sorted(CURRENT_SCHEMAS))
def test_the_current_instructions_have_only_the_skeleton(name):
    """REQ-119 (ADR-0070, regla 2; ADR-0055): la vigente no trae ejemplos, solo una línea con el
    esqueleto de la salida, y el esqueleto tiene las claves del esquema que se manda con el pedido,
    en su orden, con los valores que el esquema admite o marcadores."""
    body = current(name)
    assert "EJEMPLO" not in body.upper()
    assert shape_problems(skeleton_of(body), CURRENT_SCHEMAS[name](), name) == []


def test_the_skeleton_check_finds_a_wrong_key_order_or_value():
    """REQ-119: la comparación del esqueleto con el esquema falla si cambia el orden de las claves o
    un valor que el esquema no admite (esqueletos de prueba, inventados)."""
    schema = CURRENT_SCHEMAS["contraste"]()
    assert shape_problems({"razonamiento": "<x>", "respuesta": "si|no|parcial"}, schema) == []
    assert shape_problems({"respuesta": "si", "razonamiento": "<x>"}, schema)
    assert shape_problems({"razonamiento": "<x>", "respuesta": "tal vez"}, schema)


def test_the_evaluation_schema_keeps_the_order_of_the_reasoning():
    """REQ-104, ADR-0055 regla 1 (T-281): el esquema de la evaluación pide primero el razonamiento,
    después las citas, lo externo y lo ilegible, los datos, las condiciones y, al final, el resultado,
    la explicación y la pregunta."""
    order = list(CURRENT_SCHEMAS["evaluacion"]()["properties"])
    expected = ["razonamiento", "citas", "externo", "ilegible", "datos", "condiciones", "resultado",
                "explicacion", "pregunta"]
    positions = [order.index(name) for name in expected]
    assert positions == sorted(positions) and order[0] == "razonamiento" and order[-1] == "pregunta"


def test_the_current_evaluation_states_the_decisions_in_general_terms():
    """REQ-119, REQ-103, REQ-104 (ADR-0058 y la decisión del 2026-10-12 del IVA; spec 004, REQ-060 y
    REQ-063): la vigente dice, sin ejemplos, el cumple por ausencia con los documentos leídos, la
    exigencia de un documento dicha en negativo, el plazo de mantenimiento y su prórroga, el criterio
    del precio del Portal con los impuestos, el documento que falta («no_consta», nunca «no_cumple»), lo
    externo con la hoja de compliance, el texto vigente tras una circular y el informe técnico."""
    body = current("evaluacion")
    for phrase in (
            'el sistema lo propone "cumple" por ausencia, con los documentos leídos',
            "Una exigencia de un documento dicha en negativo pide ese documento",
            "son \"no_cumple\" solo si la oferta fija un plazo menor o limita o rechaza la prórroga",
            "El precio cotizado en el Portal es precio final, con los impuestos incluidos, salvo que "
            "la oferta diga lo contrario",
            'la condición es "no_consta", nunca "no_cumple"',
            "que consta en la hoja de compliance",
            'Con true, el resultado es "no_determinado" y la pregunta va vacía',
            "vale el texto vigente con su aclaración",
            "Una respuesta de la Comisión sola no alcanza para concluir",
            "El cumplimiento técnico lo confirma el informe técnico del área"):
        assert phrase in body, phrase


def test_the_current_evaluation_drops_the_rules_born_from_a_case_and_what_the_code_does():
    """REQ-119 (ADR-0070, regla 2): la vigente no lleva las reglas de la v12 nacidas de pares de un
    caso (requisito de referencia, declaración aceptada en el Portal, cuadro del Portal, factura o
    prima como prueba del impuesto, coherencia con el bloque del Portal) ni lo que el código
    garantiza (la cita del Portal la escribe el sistema, el tope de citas, el resultado que calcula el
    sistema, la comparación con el Portal, la forma de garantía que reconoce el sistema)."""
    body = current("evaluacion")
    for phrase in ("Requisito de referencia", "Declaraciones aceptadas en el Portal",
                   "cuadro del Portal", "la factura ni la prima", "Coherencia",
                   "El sistema escribe la cita del Portal", "Hasta cuatro citas",
                   "El sistema calcula el resultado final", "lo compara con el que informa el Portal",
                   "El sistema reconoce por su cuenta", "RECORDATORIO", "EJEMPLOS"):
        assert phrase not in body, phrase
