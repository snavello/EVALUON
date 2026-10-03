"""Formato único del pedido (T-033, ajuste B1; plan 001, "Generación" y "Conteo de
tokens").

`answering` arma el bloque de cada unidad (`unit_block`) y el texto de cada cambio
(`change_block`) con funciones públicas, para que la recuperación cuente los tokens sobre
el mismo texto que va en el pedido. Sacar esas funciones no puede cambiar el pedido: el
de un caso fijo se compara byte por byte con el que armaba el código anterior, guardado
en `tests/fixtures/t033-pedido-esperado.json`.

Con el doble del motor de `tests/conftest.py`; los textos son sintéticos (P4).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from evaluon.queries import answering

EXPECTED = Path(__file__).resolve().parents[1] / "fixtures" / "t033-pedido-esperado.json"

QUESTION = "¿Qué garantía sintética corresponde a la oferta?"
DATE = date(2024, 5, 20)
CHANGE_DATE = date(2023, 1, 1)

LONG = ("ARTICULO 1.- Primera parte sintética. Segunda parte sintética. Tercera parte "
        "sintética.")


@pytest.fixture
def fixed_case(make_norm, make_document, make_reading, make_relation):
    """Caso fijo con todas las formas del pedido: cuatro categorías, un considerando,
    una unidad mostrada por tramos, una unidad modificada con la que la modifica a
    continuación, una derogación de un inciso (parte alcanzada), un cambio traído por
    una norma entera y una unidad que modifica a dos (la segunda vez, "más arriba").
    Nombres de cita y números fijos, para que el pedido no dependa del orden de las
    pruebas. Devuelve `(unit_ids, passages)` para `answer`."""

    def norm(category, number, citation):
        made = make_norm(category=category, number=number, year=2020, citation=citation)
        return made, make_document(made)

    specific, specific_doc = norm("regimen_especifico", "1",
                                  "Régimen sintético 1/2020")
    framework, framework_doc = norm("marco_nacional", "2", "Marco sintético 2/2020")
    opinion, opinion_doc = norm("dictamen_legal", "3", "Dictamen sintético 3/2020")
    amending, amending_doc = norm("otra_normativa", "4",
                                  "Modificatoria sintética 4/2020")

    r = make_reading(specific_doc, [
        ("considerando-1", "Que la garantía sintética tiene fundamento."),
        ("art-1", LONG),
        ("art-2", "ARTICULO 2.- Garantía sintética: a) del cinco por ciento."),
        ("art-2/inc-a", "a) del cinco por ciento."),
    ]).units_by_key
    m = make_reading(framework_doc, [
        ("art-5", "ARTICULO 5.- Marco sintético de garantías."),
    ]).units_by_key
    d = make_reading(opinion_doc, [
        ("punto-1", "1. Criterio sintético sobre garantías."),
    ]).units_by_key
    make_reading(amending_doc, [
        ("art-1", "ARTICULO 1.- Sustitúyese el artículo 2 sintético."),
        ("art-2", "ARTICULO 2.- Derógase el inciso a sintético."),
    ])

    make_relation(amending, specific, "modifica", effective_date=CHANGE_DATE,
                  source_unit_key="art-1", target_unit_key="art-2")
    make_relation(amending, specific, "deroga", effective_date=CHANGE_DATE,
                  source_unit_key="art-2", target_unit_key="art-2/inc-a")
    make_relation(amending, framework, "modifica", effective_date=CHANGE_DATE,
                  target_unit_key="art-5")
    make_relation(amending, opinion, "modifica", effective_date=CHANGE_DATE,
                  source_unit_key="art-1", target_unit_key="punto-1")

    unit_ids = [r["art-1"].pk, r["art-2"].pk, m["art-5"].pk, d["punto-1"].pk,
                r["considerando-1"].pk]
    passages = {r["art-1"].pk: [(0, LONG.index(" Segunda"))]}
    return unit_ids, passages


def request_messages(fake_generation, unit_ids, passages):
    answering.answer(QUESTION, unit_ids, DATE, passages=passages)
    return fake_generation.calls[-1][0]


@pytest.mark.django_db
def test_request_is_byte_identical_to_the_previous_format(fixed_case, fake_generation):
    """REQ-007, REQ-018, REQ-019: con el bloque de unidad y el de cambio como funciones
    públicas, el pedido de un caso fijo es igual, byte por byte, al que armaba el código
    anterior (guardado en `tests/fixtures/t033-pedido-esperado.json`).

    El pedido guardado se armó con `consulta-v2`. Desde T-063 el mensaje de sistema es la
    versión activa (`consulta-v3`): ese mensaje se compara con sus instrucciones, y el
    del usuario, que es el formato que esta prueba fija, sigue igual byte por byte."""
    unit_ids, passages = fixed_case

    messages = request_messages(fake_generation, unit_ids, passages)

    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert [m["role"] for m in messages] == [m["role"] for m in expected]
    assert expected[0]["content"] == answering.load_instructions("consulta-v2")
    expected[0]["content"] = answering.load_instructions(
        answering.PROMPT_VERSION_WITH_DATE)
    for got, want in zip(messages, expected):
        assert got["content"].encode("utf-8") == want["content"].encode("utf-8")
