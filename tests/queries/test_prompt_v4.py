"""Instrucciones `consulta-v4`: las afirmaciones antes que el estado (T-248; REQ-106; ADR-0055,
regla 1; hallazgo de gravedad baja de la revisión de las instrucciones).

La v4 conserva de la v3 todas las reglas (régimen específico, considerandos, cambios, regímenes que
difieren, remisión, abstención) y cambia el orden de la salida: el motor genera los campos en el
orden del esquema, así que el estado (`grounded` o `undetermined`) se escribe después de las
afirmaciones que lo sostienen. Los ejemplos suman una segunda abstención y dicen qué situación
muestran. La pregunta repetida al final del mensaje, que también pedía la revisión, no se hace
acá: cambia la cuenta de tokens que comparten `services.py`, `evaluation.py` y `retrieval.py`, que
la T-255 (Consulta con el 27B) reabre, y se mide con el conjunto dorado de la 001 (P7).

Los textos son sintéticos (P4). Lo que hace el modelo con la v4 lo mide la corrida del conjunto
dorado (T-249).
"""

import json

from evaluon.queries import answering


def v4():
    return answering.load_instructions("consulta-v4")


def test_v4_keeps_every_rule_of_v3():
    """REQ-008, REQ-009, REQ-018, REQ-019: las reglas de la 1 a la 11 de la v3 están en la v4,
    palabra por palabra."""
    v3 = answering.load_instructions("consulta-v3")
    rules = v3.split("QUÉ TENÉS QUE HACER", 1)[1].split("FORMATO DE LA SALIDA", 1)[0]

    assert rules in v4()


def test_v4_asks_for_the_statements_before_the_status():
    """REQ-106: la v4 dice que primero van las afirmaciones y después el estado, y su formato lo
    describe en ese orden."""
    text = v4()
    format_part = text.split("FORMATO DE LA SALIDA", 1)[1]

    assert "primero las afirmaciones y después el estado" in text
    assert format_part.index('- "statements"') < format_part.index('- "status"')
    assert 'y después el estado que ellas sostienen' in text


def test_the_examples_of_v4_follow_the_schema_order_and_are_balanced():
    """REQ-106 (ADR-0055, regla 4): cada ejemplo trae `statements` antes que `status`, dice
    entre paréntesis la situación que muestra, y hay tres con afirmaciones y dos sin ellas."""
    examples = [json.loads(line) for line in v4().splitlines() if line.startswith("{")]

    assert len(examples) == 5
    assert all(list(example) == ["statements", "status"] for example in examples)
    assert [e["status"] for e in examples].count("grounded") == 3
    assert [e["status"] for e in examples].count("undetermined") == 2
    assert all(not e["statements"] for e in examples if e["status"] == "undetermined")
    lines = v4().splitlines()
    for number, line in enumerate(lines):
        if line.startswith("{"):
            assert lines[number - 1].startswith("(") and lines[number - 1].endswith(".)")


def test_the_schema_of_v4_puts_the_statements_first_and_v1_keeps_its_order():
    """REQ-106: el esquema de la v4 (y el de la v2 y la v3) generan `statements` antes que
    `status`; el de la `consulta-v1` conserva el orden de siempre (versión publicada)."""
    current = answering.build_schema(["U1"], version="consulta-v4")
    legacy = answering.build_schema(["U1"], version="consulta-v1")

    assert list(current["properties"]) == ["statements", "status"]
    assert current["required"] == ["statements", "status"]
    assert list(legacy["properties"]) == ["status", "statements"]
    assert legacy["required"] == ["status", "statements"]
    assert current["properties"] == answering.build_schema(["U1"], "consulta-v3")["properties"]
