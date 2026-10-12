"""Razonamiento propio del modelo en la evaluación y el contraste (T-253; REQ-107; ADR-0056,
enmienda del 2026-10-11; P6). Caso chico y textos inventados (P4); el modelo es un guion
(`fakes.py`).

Con el paso encendido, el pedido de lectura (evaluación) y el del contraste piden pensar con su
nivel y su tope, y el texto del razonamiento con sus tokens queda en el `parsed` del pedido; la
corrida registra qué pasos lo tenían encendido. Apagado, nada cambia.
"""

import pytest

from evaluon.assessment import models as am
from tests.assessment.fakes import ILEGIBLE_NEEDLE, model, model_view, says  # noqa: F401
from tests.assessment.test_evaluate import (
    cumple_declaration,
    number_of,
    results_of,
    run_all,
)

pytestmark = pytest.mark.django_db

STEPS = ("extraction", "completeness", "filter", "evaluation", "contrast")
OFF = {step: "off" for step in STEPS}


def test_evaluation_and_contrast_with_reasoning_on_record_it(offer, operator_user, procedure,
                                                              model, settings):
    """REQ-107, P6: con evaluación en `medium` y contraste en `low`, cada pedido de lectura y de
    contraste pide pensar con su nivel y su tope, y su `parsed` lleva el razonamiento del modelo
    (texto y tokens) con el nivel; la reescritura de la búsqueda, que no es uno de los cinco
    pasos, no piensa; la corrida registra los pasos encendidos."""
    settings.GENERATION_BATCH_REASONING = {**OFF, "evaluation": "medium", "contrast": "low"}
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure)
    run = runs[0]
    budgets = settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS
    expected = {"grupo": "medium", "contraste": "low"}
    steps = list(am.Step.objects.filter(run=run))
    assert {s.purpose for s in steps} >= {"grupo", "contraste"}
    for step in steps:
        level = expected.get(step.purpose)
        if level is None:
            assert step.request["chat_template_kwargs"] == {"enable_thinking": False}
            assert "razonamiento_propio" not in (step.parsed or {})
            continue
        assert step.request["chat_template_kwargs"]["enable_thinking"] is True
        assert step.request["reasoning_effort"] == level
        assert step.request["thinking_budget_tokens"] == budgets[level]
        record = step.parsed["razonamiento_propio"]
        assert record["nivel"] == level and record["texto"]
        assert record["tokens"] == len(record["texto"].split())
    assert run.parameters["reasoning"] == {**OFF, "evaluation": "medium", "contrast": "low"}
    assert run.parameters["reasoning_budget_tokens"] == budgets
    result = results_of(run)[number_of(procedure, "declaración jurada")]
    assert result.outcome == "cumple"  # el pedir razonar no cambia lo que se hace con la salida


def test_the_requests_wait_longer_when_the_step_thinks(offer, operator_user, procedure, model,
                                                        settings):
    """REQ-107: el pedido de lectura de un paso que piensa espera `ASSESSMENT_REQUEST_TIMEOUT_SECONDS`
    más el tiempo extra del razonamiento."""
    settings.GENERATION_BATCH_REASONING = {**OFF, "evaluation": "low"}
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    waits = {(c.kwargs.get("reasoning"), c.kwargs["timeout"]) for c in model.calls}
    assert waits == {("low", settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS
                      + settings.GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS)}


def test_with_everything_off_the_evaluation_asks_what_it_asked_before(
        offer, operator_user, procedure, model, settings):
    """REQ-107: apagado, los pedidos de la evaluación y el contraste no llevan nada de
    razonamiento propio, ni en el pedido ni en el `parsed`, y la espera es la de hoy; la corrida
    registra los cinco pasos apagados."""
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure)
    for step in am.Step.objects.filter(run=runs[0]):
        assert step.request["chat_template_kwargs"] == {"enable_thinking": False}
        assert "reasoning_effort" not in step.request
        assert "thinking_budget_tokens" not in step.request
        assert "razonamiento_propio" not in (step.parsed or {})
    for call in model.calls:
        assert "reasoning" not in call.kwargs
        assert call.kwargs["timeout"] == settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS
    assert runs[0].parameters["reasoning"] == OFF
