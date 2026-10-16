"""Instrucciones `consulta-v6`: la consulta corta que responde cuando una unidad trata el punto (T-285;
REQ-119 de la 016; REQ-008, REQ-009 de la 001; ADR-0002, ADR-0015, ADR-0070).

La medición T-283 (D-283-8) mostró que con la `consulta-v5` el modelo se abstenía donde con la v4
contestaba (y por eso faltaban dos avisos de modificatorias, REQ-021, que solo acompañan una
respuesta). La v5 decía «Si ninguna unidad trata el punto…, no respondas»; la v4 decía que la
abstención es **solo** para cuando ninguna unidad trata el punto, y que si alguna lo trata la lista de
afirmaciones lleva al menos una. La v6 conserva el largo de la v5 y vuelve a decir eso, con la enmienda
de REQ-009 (ADR-0015): «"No determinado" queda para los temas que ninguna norma cargada trata». Sin
ejemplos. Lo que hace el modelo con la v6 lo mide T-286 (P7).

Con los dobles de `tests/conftest.py`; los textos son sintéticos (P4).
"""

import json
import re

import pytest

from evaluon.queries import answering

# Las reglas que la v5 traía de ADR-0002 y de la 001 (`test_prompt_v5.py`), que la v6 conserva.
V5_RULES = ("No copies el texto de la norma",
            "el sistema muestra el texto literal de cada unidad citada",
            "No agregues nada que no esté en las unidades",
            "Régimen específico: es lo que se aplica",
            "Marco nacional: marco de referencia",
            "criterio que acompaña",
            "Considerando: contexto",
            "con el cambio aplicado, y citá también la unidad que la modifica",
            '"regimes_differ" en true',
            "remite su contenido a otra norma",
            "No des el contenido de la norma remitida",
            'esa respuesta es "grounded"',
            "ni siquiera para remitirlo a otra norma",
            "es preferible no responder a responder sin sustento")


def v6():
    return answering.load_instructions("consulta-v6")


def test_v6_is_the_active_version_with_date():
    """REQ-119, REQ-008: con fecha, la versión activa es `consulta-v6`; la v5 y la v4 siguen
    publicadas y el camino sin fecha sigue con la `consulta-v1`."""
    assert answering.PROMPT_VERSION_WITH_DATE == "consulta-v6"
    assert answering.PROMPT_VERSION_WITHOUT_DATE == "consulta-v1"
    assert answering.load_instructions() == v6()
    assert answering.load_instructions("consulta-v5") and answering.load_instructions("consulta-v4")


def test_v6_answers_whenever_a_unit_treats_the_point_and_abstains_only_otherwise():
    """REQ-009 (enmienda del 2026-10-03, ADR-0015: «"No determinado" queda para los temas que ninguna
    norma cargada trata»; D-47): si alguna unidad trata el punto, aunque sea en parte o para remitirlo,
    se responde con al menos una afirmación; «undetermined» es solo cuando ninguna lo trata. La v5 no lo
    decía así (D-283-8)."""
    text = v6()

    assert ("Si alguna unidad trata el punto de la pregunta, aunque sea en parte o solo para "
            "remitirlo a otra norma, respondé con lo que dice: \"statements\" lleva al menos una "
            "afirmación.") in text
    assert ("Devolvé \"undetermined\", con \"statements\" vacía, solo si ninguna unidad trata el "
            "punto de la pregunta") in text
    assert "vacía solo si ninguna unidad trata el punto" in text
    assert "no respondas:" not in text and "no respondas:" in answering.load_instructions(
        "consulta-v5")


def test_v6_keeps_the_rules_of_v5_and_its_length():
    """REQ-119 (ADR-0070), REQ-008, REQ-018 a REQ-020: la v6 conserva cada regla que la v5 traía de
    ADR-0002 y la 001, sin ejemplos, con el esqueleto en el orden del esquema, y sigue corta (no
    vuelve al largo de la v4)."""
    text = v6()
    for phrase in V5_RULES:
        assert phrase in text, phrase
    assert not re.search(r"(?im)^[\s#>*\-\d.)]*ejemplos?\b", text)
    [skeleton] = [line for line in text.splitlines() if line.startswith("{")]
    assert list(json.loads(skeleton.replace("grounded|undetermined", "grounded"))) == [
        "statements", "status"]
    v4, v5 = (answering.load_instructions(f"consulta-v{n}") for n in (4, 5))
    assert len(text) < len(v4) and len(text) <= len(v5) + 300
    assert len(text.splitlines()) <= len(v5.splitlines()) + 2


# --- H-282-2: cada una de las dos líneas que registran la instrucción, por separado ---------------

QUESTION = "¿Cuál es el plazo sintético para presentar la muestra?"
MARK = "[articulo-v6]"
UNIT_TEXT = f"ARTICULO 4.- {MARK} La muestra sintética se presenta dentro de los cinco días."


@pytest.mark.django_db
def test_h282_2_a_query_stopped_after_the_selection_records_its_instruction(
        read_user, make_norm, make_document, make_reading, fake_ai, settings):
    """REQ-119, P6 (H-282-2): una consulta que se detiene después de elegir las unidades y antes de
    llamar al modelo (ninguna entra en el contexto) deja el nombre, la versión y la huella de la
    instrucción que se iba a usar: lo registra `_prepare`, sin `_generate`."""
    from datetime import date

    from evaluon.queries import services

    norm = make_norm(category="regimen_especifico", general_regime=True)
    make_reading(make_document(norm), [("art-4", UNIT_TEXT)])
    settings.RERANK_THRESHOLD = 0.219
    settings.GENERATION_CONTEXT_TOKENS = 10
    fake_ai.reranker.scores = {MARK: 0.9}

    query = services.ask(read_user, QUESTION, date(2024, 5, 20))

    assert (query.status, query.reason) == ("error", "input_too_long")
    assert fake_ai.generation.calls == []
    assert query.parameters["instruccion"] == answering.prompt_record(
        answering.PROMPT_VERSION_WITH_DATE)


@pytest.mark.django_db
def test_h282_2_the_query_records_the_instruction_of_the_request_it_sent(
        read_user, make_norm, make_document, make_reading, fake_ai, settings, monkeypatch):
    """REQ-119, P6 (H-282-2): la instrucción registrada es la del pedido que se envió
    (`generated.prompt_version`, que escribe `_generate`), aunque difiera de la que eligió
    `_prepare`."""
    import dataclasses
    from datetime import date

    from evaluon.queries import services

    real = answering.answer

    def answered(*args, **kwargs):
        return dataclasses.replace(real(*args, **kwargs), prompt_version="consulta-v4")

    monkeypatch.setattr(answering, "answer", answered)
    norm = make_norm(category="regimen_especifico", general_regime=True)
    make_reading(make_document(norm), [("art-4", UNIT_TEXT)])
    settings.RERANK_THRESHOLD = 0.219
    fake_ai.reranker.scores = {MARK: 0.9}

    query = services.ask(read_user, QUESTION, date(2024, 5, 20))

    assert query.prompt_version == "consulta-v4"
    assert query.parameters["instruccion"] == answering.prompt_record("consulta-v4")
