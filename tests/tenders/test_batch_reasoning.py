"""Razonamiento propio del modelo, por paso, en el motor de lotes (T-253; REQ-107; ADR-0056,
enmienda del 2026-10-11; P6).

- `settings.GENERATION_BATCH_REASONING` dice, por paso (extracción, completitud, filtro,
  evaluación y contraste), si el razonamiento propio del modelo está encendido y con qué nivel
  (`low`, `medium` o `high`); por omisión todo apagado y el pedido es el de hoy.
- Encendido, el pedido pide pensar (`chat_template_kwargs.enable_thinking`), el nivel
  (`reasoning_effort`) y un tope de tokens de razonamiento (`thinking_budget_tokens`, que
  admite `llama-server` b11347 por pedido), suma ese tope al máximo de salida y suma tiempo de
  espera; la salida sigue obligada por el esquema (la gramática vale para el contenido, no para
  el razonamiento).
- El texto del razonamiento y su cantidad de tokens quedan en el `parsed` de cada pedido y la
  corrida registra qué pasos lo tenían encendido.

El motor es un servidor HTTP local de prueba con la forma de `llama-server`; el resto, los
dobles de `tests/conftest.py`. Textos sintéticos (P4).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.core.exceptions import ImproperlyConfigured

from evaluon import settings as project_settings
from evaluon.ai import generation
from evaluon.tenders import models as m
from tests.tenders.test_filter import (  # noqa: F401 - fixtures y ayudas del filtro
    CLAUSE,
    FilterScript,
    one_row,
    pliego,
    run_with,
)
from tests.tenders.test_circulars import CircularScript

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
MESSAGES = [{"role": "user", "content": "Pregunta sintética."}]
STEPS = ("extraction", "completeness", "filter", "evaluation", "contrast")
OFF = {step: "off" for step in STEPS}
# Los pedidos de la matriz que son de los pasos con razonamiento propio (extracción, completitud, filtro).
MATRIX_PASSES = ("extraccion", "extraccion_2", "completitud", "filtro", "filtro_2")
THOUGHT = "Primero miro el requisito, después el texto de la oferta."


class _Engine(BaseHTTPRequestHandler):
    """Servidor con la forma de `llama-server`: guarda cada cuerpo recibido; si el pedido pide
    pensar, responde también `reasoning_content`; `/tokenize` cuenta palabras."""

    bodies = []

    def _send(self, payload):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):  # noqa: N802 - nombre de http.server
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/tokenize":
            self._send({"tokens": list(range(len(body["content"].split())))})
            return
        type(self).bodies.append(body)
        message = {"role": "assistant", "content": '{"ok": true}'}
        if body.get("chat_template_kwargs", {}).get("enable_thinking"):
            message["reasoning_content"] = THOUGHT
        self._send({"choices": [{"index": 0, "finish_reason": "stop", "message": message}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 40}})

    def log_message(self, *args):
        pass


@pytest.fixture
def engine(settings):
    _Engine.bodies = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Engine)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    settings.GENERATION_URL = "http://127.0.0.1:9"  # la consulta de normativa: no se usa
    settings.GENERATION_BATCH_URL = url
    yield _Engine
    server.shutdown()
    server.server_close()


def reasoning_on(settings, **levels):
    settings.GENERATION_BATCH_REASONING = {**OFF, **levels}


# --- Apagado por omisión: el pedido es el de hoy -----------------------------------------------


def test_the_five_steps_are_off_by_default(settings):
    """REQ-107: por omisión el razonamiento propio está apagado en los cinco pasos."""
    assert settings.GENERATION_BATCH_REASONING == OFF
    assert settings.GENERATION_BATCH_REASONING_STEPS == STEPS


def test_with_everything_off_the_request_is_the_one_of_today(engine, settings, monkeypatch):
    """REQ-107: apagado, el pedido de cada paso no cambia: pensamiento apagado, sin nivel ni tope
    de razonamiento, mismo máximo de salida y misma espera que `generate_batch` sin paso."""
    seen = []
    real_post = generation.post_json

    def spy(service, base_url, path, body, *, timeout=None):
        seen.append(timeout)
        return real_post(service, base_url, path, body, timeout=timeout)

    monkeypatch.setattr(generation, "post_json", spy)
    for step in STEPS:
        result = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=700, step=step)
        assert result.reasoning_record() is None
    plain = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=700)
    for body in engine.bodies[:-1]:
        assert body == engine.bodies[-1]
    body = engine.bodies[-1]
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["max_tokens"] == 700
    assert "reasoning_effort" not in body and "thinking_budget_tokens" not in body
    assert plain.request == body
    assert set(seen) == {settings.GENERATION_BATCH_TIMEOUT_SECONDS}


# --- Encendido: el pedido -------------------------------------------------------------------------


@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_a_step_with_reasoning_on_asks_to_think(engine, settings, monkeypatch, level):
    """REQ-107: encendido en un paso, el pedido pide pensar con el nivel, pide el tope de
    razonamiento de ese nivel, suma ese tope al máximo de salida y suma la espera extra."""
    reasoning_on(settings, filter=level)
    seen = []
    real_post = generation.post_json

    def spy(service, base_url, path, body, *, timeout=None):
        seen.append(timeout)
        return real_post(service, base_url, path, body, timeout=timeout)

    monkeypatch.setattr(generation, "post_json", spy)
    budget = settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS[level]

    result = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=700, step="filter")

    body = engine.bodies[-1]
    assert body["chat_template_kwargs"]["enable_thinking"] is True
    assert body["reasoning_effort"] == level
    assert body["thinking_budget_tokens"] == budget
    assert body["max_tokens"] == 700 + budget
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["temperature"] == 0 and body["seed"] == settings.GENERATION_SEED
    assert seen == [settings.GENERATION_BATCH_TIMEOUT_SECONDS
                    + settings.GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS]
    assert result.request == body
    assert json.loads(result.content) == {"ok": True}


def test_the_budgets_grow_with_the_level_and_are_configurable(settings):
    """REQ-107: el tope de razonamiento crece con el nivel y se configura en `settings.py`."""
    budgets = settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS
    assert set(budgets) == {"low", "medium", "high"}
    assert 0 < budgets["low"] < budgets["medium"] < budgets["high"]
    assert settings.GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS > 0


def test_only_the_step_that_is_on_thinks(engine, settings):
    """REQ-107: con un solo paso encendido, los demás pasos piden lo de hoy."""
    reasoning_on(settings, evaluation="medium")
    for step in STEPS:
        generation.generate_batch(MESSAGES, SCHEMA, max_tokens=500, step=step)
    thinking = {step: body["chat_template_kwargs"]["enable_thinking"]
                for step, body in zip(STEPS, engine.bodies)}
    assert thinking == {step: step == "evaluation" for step in STEPS}


def test_a_batch_request_without_a_step_never_thinks(engine, settings):
    """REQ-107: los pedidos de lotes que no son de los cinco pasos (circulares, consecuencias,
    respaldo normativo, ficha) no piensan aunque haya pasos encendidos."""
    reasoning_on(settings, **{step: "high" for step in STEPS})
    generation.generate_batch(MESSAGES, SCHEMA, max_tokens=500)
    assert engine.bodies[-1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert engine.bodies[-1]["max_tokens"] == 500


def test_the_query_engine_never_thinks(engine, settings):
    """REQ-107: la opción es solo del motor de lotes: `generate` hacia `generation` (la consulta de
    normativa) no pide pensar aunque todos los pasos estén encendidos."""
    reasoning_on(settings, **{step: "high" for step in STEPS})
    settings.GENERATION_URL = settings.GENERATION_BATCH_URL
    generation.generate(MESSAGES, SCHEMA, base_url=settings.GENERATION_URL)
    assert engine.bodies[-1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "thinking_budget_tokens" not in engine.bodies[-1]


def test_the_unsent_request_of_a_failure_is_registered_as_it_would_have_gone(engine, settings):
    """REQ-107, P6: el pedido que no llegó a salir (`build_batch_request`) lleva lo mismo que el
    que sale: pensamiento, nivel, tope y máximo de salida."""
    reasoning_on(settings, extraction="low")
    sent = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=900, step="extraction").request
    assert generation.build_batch_request(MESSAGES, SCHEMA, 900, step="extraction") == sent
    assert generation.build_batch_request(MESSAGES, SCHEMA, 900) != sent


# --- Encendido: el registro -----------------------------------------------------------------------


def test_the_result_keeps_the_text_and_the_tokens_of_the_reasoning(engine, settings):
    """REQ-107, P6: el texto del razonamiento y su cantidad de tokens (la cuenta del servidor
    del lote) quedan en el resultado, con el nivel."""
    reasoning_on(settings, contrast="medium")
    result = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=500, step="contrast")
    assert result.reasoning == THOUGHT
    assert result.reasoning_record() == {
        "nivel": "medium", "texto": THOUGHT, "tokens": len(THOUGHT.split())}


def test_a_failed_token_count_does_not_lose_the_reasoning(engine, settings, monkeypatch):
    """REQ-107: si el servidor no puede contar los tokens del razonamiento, el texto queda y la
    cantidad queda sin dato; la respuesta ya generada no se pierde."""
    from evaluon.ai import ServiceUnavailableError

    def broken(*args, **kwargs):
        raise ServiceUnavailableError("generation: falla simulada", service="generation")

    reasoning_on(settings, contrast="low")
    monkeypatch.setattr(generation, "count_tokens_with", broken)
    result = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=500, step="contrast")
    assert result.reasoning_record() == {"nivel": "low", "texto": THOUGHT, "tokens": None}


def test_a_model_that_returns_no_reasoning_is_recorded_as_empty(engine, settings):
    """REQ-107: con el paso encendido y un modelo que no devuelve razonamiento, el registro lo
    dice (texto vacío, 0 tokens): no se confunde con un paso apagado."""
    reasoning_on(settings, filter="low")

    class Quiet(_Engine):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self._send({"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": '{"ok": true}'}}], "usage": {}})
            type(self).bodies.append(body)

    quiet = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=quiet.serve_forever, daemon=True).start()
    try:
        settings.GENERATION_BATCH_URL = f"http://127.0.0.1:{quiet.server_address[1]}"
        result = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=500, step="filter")
    finally:
        quiet.shutdown()
        quiet.server_close()
    assert result.reasoning_record() == {"nivel": "low", "texto": "", "tokens": 0}


# --- Variables de entorno -------------------------------------------------------------------------


def test_the_environment_turns_each_step_on_with_a_level():
    """REQ-107: una variable de entorno por paso (`GENERATION_BATCH_REASONING_<PASO>`) enciende
    el paso con su nivel; sin la variable, o con `off`, queda apagado."""
    levels = project_settings.reasoning_levels({
        "GENERATION_BATCH_REASONING_EXTRACTION": "low",
        "GENERATION_BATCH_REASONING_FILTER": "MEDIUM",
        "GENERATION_BATCH_REASONING_CONTRAST": "off",
        "GENERATION_BATCH_REASONING_EVALUATION": "",
    })
    assert levels == {"extraction": "low", "completeness": "off", "filter": "medium",
                      "evaluation": "off", "contrast": "off"}


def test_an_unknown_level_is_a_configuration_error():
    """REQ-107: un nivel que no es `off`, `low`, `medium` ni `high` frena el arranque."""
    with pytest.raises(ImproperlyConfigured):
        project_settings.reasoning_levels({"GENERATION_BATCH_REASONING_FILTER": "mucho"})


# --- Los pasos de la matriz ------------------------------------------------------------------------


@pytest.fixture
def script(fake_generation, monkeypatch):
    return CircularScript(fake_generation, monkeypatch)


@pytest.fixture
def filt(script, monkeypatch):
    return FilterScript(script, monkeypatch)


def test_the_matrix_steps_with_reasoning_on_record_it_in_each_request(
        operator_user, script, filt, settings):
    """REQ-107, P6: con extracción, completitud y filtro encendidos, el `parsed` de cada pedido de
    esos pasos lleva el texto y los tokens del razonamiento con su nivel, el pedido registrado
    pide pensar, y la corrida registra qué pasos estaban encendidos."""
    reasoning_on(settings, extraction="low", completeness="medium", filter="high")
    one_row(script)

    run = run_with(operator_user, pliego(CLAUSE))

    steps = list(m.RunStep.objects.filter(run=run))
    by_pass = {}
    for step in steps:
        by_pass.setdefault(step.pass_name, []).append(step)
    levels = {"extraccion": "low", "completitud": "medium", "filtro": "high",
              "filtro_2": "high"}
    seen = set()
    for name, level in levels.items():
        for step in by_pass.get(name, []):
            seen.add(name)
            assert step.request["chat_template_kwargs"]["enable_thinking"] is True, name
            assert step.request["thinking_budget_tokens"] == (
                settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS[level])
            record = step.parsed["razonamiento_propio"]
            assert record["nivel"] == level and record["texto"]
            assert record["tokens"] == len(record["texto"].split()) > 0
    assert {"extraccion", "filtro", "filtro_2"} <= seen
    assert run.parameters["reasoning"] == {**OFF, "extraction": "low", "completeness": "medium",
                                           "filter": "high"}
    assert run.parameters["reasoning_budget_tokens"] == (
        settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS)
    assert run.parameters["reasoning_extra_timeout_seconds"] == (
        settings.GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS)


def test_the_matrix_steps_with_reasoning_off_record_nothing_new(operator_user, script, filt,
                                                                 settings):
    """REQ-107: apagado, ningún pedido de la matriz lleva `razonamiento_propio` ni pide pensar, y
    la corrida registra los cinco pasos apagados."""
    one_row(script)
    run = run_with(operator_user, pliego(CLAUSE))
    steps = list(m.RunStep.objects.filter(run=run, pass_name__in=MATRIX_PASSES))
    assert {s.pass_name for s in steps} >= {"extraccion", "filtro", "filtro_2"}
    for step in steps:
        assert "razonamiento_propio" not in (step.parsed or {})
        assert step.request["chat_template_kwargs"] == {"enable_thinking": False}
        assert "thinking_budget_tokens" not in step.request
    assert run.parameters["reasoning"] == OFF


def test_a_matrix_step_only_asks_for_what_is_on(operator_user, script, filt, settings):
    """REQ-107: con solo el filtro encendido, la extracción no piensa."""
    reasoning_on(settings, filter="low")
    one_row(script)
    run = run_with(operator_user, pliego(CLAUSE))
    for step in m.RunStep.objects.filter(run=run, pass_name__in=MATRIX_PASSES):
        thinks = step.pass_name in ("filtro", "filtro_2")
        assert step.request["chat_template_kwargs"]["enable_thinking"] is thinks, step.pass_name
        assert ("razonamiento_propio" in step.parsed) is thinks, step.pass_name
