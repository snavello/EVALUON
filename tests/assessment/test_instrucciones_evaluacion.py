"""Las instrucciones de la evaluación: evaluación, contraste y cláusulas (REQ-104, REQ-105,
REQ-106; plan 015, "Flujo de IA · Evaluación"; ADR-0055; T-237).

Se comprueba la forma: sin las reglas que empujan al error, con las definiciones y el bloque del
Portal, ejemplos balanceados que coinciden con el esquema y con la regla que deriva el resultado, y
versiones publicadas congeladas (como `scripts/models.sha256` con los modelos). Sin modelo ni GPU:
el uso real se mide en T-239. Textos inventados (P4).
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
}

# Reglas que empujaban al error (informe de revisión, 4.7 a 4.9).
FORBIDDEN = ("fragmento mínimo", "fragmento más corto", "ante la duda", "por sí sola",
             "por sí solo", "dividí", "o dudás")


def text_of(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def current(name):
    return text_of(settings.ASSESSMENT_PROMPT_VERSIONS[name])


def examples_of(name):
    """Las líneas JSON de la sección de ejemplos de la instrucción `name`."""
    body = current(name)
    section = body[body.index("EJEMPLOS"):]
    return [json.loads(line) for line in section.splitlines() if line.startswith("{")]


def test_the_current_versions_are_the_new_ones_and_exist():
    """REQ-106: `ASSESSMENT_PROMPT_VERSIONS` apunta a las versiones nuevas y los archivos existen."""
    assert settings.ASSESSMENT_PROMPT_VERSIONS == {
        "evaluacion": "evaluacion-v6", "contraste": "contraste-v3", "clausulas": "clausulas-v3"}
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


def test_the_evaluation_asks_for_the_whole_sentence_and_each_condition():
    """REQ-104: la cita es la oración completa; se revisa cada condición con su dato, su cita y su
    resultado; «cumple» solo si todas; la duda se declara con su razón."""
    body = current("evaluacion")
    assert "oración completa" in body and "LETRA POR LETRA" in body
    assert '"condiciones"' in body and '"dato"' in body and '"cita"' in body
    assert 'solo si TODAS las condiciones cumplen' in body
    assert '"no_cumple" si alguna no cumple' in body
    assert 'si falta el dato de alguna condición' in body
    assert "La duda no es un motivo" in body and "qué dato falta o qué texto contradice" in body
    assert "No supongas el dato de una condición" in body


def test_the_evaluation_explains_the_portal_block_and_how_to_cite_it():
    """REQ-103, REQ-104: el bloque `[P…]` del Portal, qué es y cómo se cita."""
    body = current("evaluacion")
    assert "[P1]" in body and "Datos del Portal" in body
    assert '{"documento": "P1"' in body
    assert "el sistema escribe la cita del portal" in body.lower().replace("\n", " ")
    assert "<<<" in body and ">>>" in body    # la oración que se evalúa va marcada


def test_the_question_is_for_the_commission_with_requirement_conclusion_and_text():
    """REQ-105: la pregunta va a la Comisión, nombra el requisito, la conclusión y el texto, y
    nunca le pide algo al oferente."""
    body = current("evaluacion")
    assert "es para la Comisión, nunca para el oferente" in body
    assert "nombre el requisito, tu conclusión y el texto" in body
    assert "pedirle algo al oferente es una subsanación" in body
    assert "Lo externo es la verificación en el registro o en la base" in body


def test_the_schema_order_in_the_instruction_is_the_one_of_the_schema():
    """REQ-104, ADR-0055: la instrucción nombra los campos en el orden del esquema, y el cierre del
    mensaje (tres líneas) también."""
    order = list(prompting.evaluation_schema(["D1"], [], ["P1"])["properties"])
    body = current("evaluacion")
    format_line = next(line for line in body.splitlines() if line.startswith('{"razonamiento"'))
    first = [format_line.index(f'"{name}"') for name in order[:order.index("condiciones") + 1]]
    last = [format_line.rindex(f'"{name}"') for name in order[order.index("resultado"):]]
    assert first == sorted(first) and last == sorted(last)
    assert first[-1] < last[0]   # las condiciones antes del resultado
    assert prompting.CLOSING.count("\n") == 2   # tres líneas
    assert prompting.CLOSING.index("razonamiento") < prompting.CLOSING.index("condiciones") < (
        prompting.CLOSING.index("resultado"))


def parse(example):
    return prompting.parse_evaluation(json.dumps(example), ["D1", "D2", "D3", "D4", "P1"], [])


def test_the_evaluation_examples_are_balanced():
    """REQ-106, ADR-0055 regla 4: 3 «cumple» (uno con el Portal), 2 «no cumple», 2 «no consta» y 3
    «no determinado»; ningún resultado pasa del 40 % del total; el Portal se cita en uno que
    cumple."""
    examples = examples_of("evaluacion")
    counts = Counter(e["resultado"] for e in examples)
    assert counts == {"cumple": 3, "no_cumple": 2, "no_consta": 2, "no_determinado": 3}
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
    de dos condiciones; las respuestas están repartidas (ninguna pasa del 60 %)."""
    examples = examples_of("contraste")
    assert all(list(e) == ["razonamiento", "respuesta"] for e in examples)
    counts = Counter(e["respuesta"] for e in examples)
    assert set(counts) == {"si", "no", "parcial"} and max(counts.values()) / len(examples) <= 0.6
    assert any("dos condiciones" in e["razonamiento"] and e["respuesta"] == "parcial"
               for e in examples)
    body = current("contraste")
    assert "Contexto en la misma página" in body and "Datos del Portal" in body
    for example in examples:
        assert prompting.parse_contrast(json.dumps(example))[0] == example["respuesta"]


def test_the_clauses_examples_put_the_motive_before_the_state_and_ask_the_commission():
    """REQ-104, REQ-105: el contraste por cláusula razona primero, el motivo va antes del estado
    y la pregunta del ejemplo es para la Comisión, con la cláusula y lo que se leyó."""
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


def test_a_retry_message_has_no_the_old_suggestion():
    """REQ-104: el aviso del reintento ya no sugiere «no_determinado» sin más: pide la oración
    completa y nombra la cita que no se encontró."""
    text = prompting.correction_for(prompting.ANOMALY_NO_CITATION, ["Texto  que\nno está"])
    assert "«Texto que no está»" in text and "oración completa" in text
    assert "respondé \"no_determinado\"" not in text
