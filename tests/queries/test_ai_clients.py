"""Clientes de IA, sus dobles y los parámetros (T-011; plan 001, "Servicios", "Conteo de
tokens", "Reordenamiento", "Generación" y "Abstención").

Los clientes de `evaluon/ai/` se prueban contra un servidor HTTP falso que corre dentro
del test, en 127.0.0.1, y responde con las formas que devolvió `llama-server` en la
etapa 0 (`entorno.md`, T-002 y T-003): mismos campos, mismos códigos y mismos mensajes
de error. No hace falta ningún servicio de IA. Los textos son sintéticos (P4); los pares
del reranker son los de la ficha pública de `bge-reranker-v2-m3`.
"""

import json
import math
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings

from evaluon.ai import (
    AIServiceError,
    InputTooLongError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    embeddings,
    generation,
    reranker,
)

# Respuestas de error medidas en la etapa 0 (entorno.md, T-002 sección 9 y T-003 sección 5).
GENERATION_TOO_LONG = {
    "error": {
        "code": 400,
        "message": "request (17811 tokens) exceeds the available context size (16384 tokens), "
                   "try increasing it",
        "type": "exceed_context_size_error",
        "n_prompt_tokens": 17811,
        "n_ctx": 16384,
    }
}
EMBEDDINGS_TOO_LONG = {
    "error": {
        "code": 500,
        "message": "input (11257 tokens) is too large to process. increase the physical batch "
                   "size (current batch size: 8192)",
        "type": "server_error",
    }
}
RERANKER_TOO_LONG = {
    "error": {
        "code": 500,
        "message": "input (11269 tokens) is too large to process. increase the physical batch "
                   "size (current batch size: 8192)",
        "type": "server_error",
    }
}
OTHER_SERVER_ERROR = {
    "error": {"code": 500, "message": "failed to decode the batch", "type": "server_error"}
}

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["grounded", "undetermined"]},
        "statements": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "enum": ["U1", "U2"]},
                    },
                },
                "required": ["text", "citations"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["status", "statements"],
    "additionalProperties": False,
}

MESSAGES = [
    {"role": "system", "content": "Instrucciones sintéticas de prueba."},
    {"role": "user", "content": "Pregunta sintética: ¿cuál es el plazo de la garantía?"},
]


def chat_completion(content, finish_reason="stop"):
    """Respuesta de `/v1/chat/completions` con la forma de `llama-server`."""
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "index": 0,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "created": 1790000000,
        "model": "gemma-4-12b-it-qat-q4_0",
        "object": "chat.completion",
        "usage": {"completion_tokens": 25, "prompt_tokens": 324, "total_tokens": 349},
    }


class FakeServer:
    """Servidor HTTP falso. `routes[(método, ruta)] = (código, cuerpo, demora)`; guarda en
    `requests` cada pedido recibido como `(método, ruta, cuerpo JSON)`."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                body = json.loads(raw) if raw else None
                fake.requests.append(("POST", self.path, body))
                status, payload, delay = fake.routes.get(
                    ("POST", self.path), (404, {"error": {"code": 404}}, 0)
                )
                if delay:
                    time.sleep(delay)
                data = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # el cliente ya cortó por espera agotada

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.thread.start()

    def route(self, path, payload, status=200, delay=0):
        self.routes[("POST", path)] = (status, payload, delay)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    fake = FakeServer()
    with override_settings(
        GENERATION_URL=fake.url, EMBEDDINGS_URL=fake.url, RERANKER_URL=fake.url
    ):
        yield fake
    fake.close()


def closed_port_url():
    """Dirección de un puerto local donde no escucha nadie."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


# --- Generación con esquema ----------------------------------------------------------


def test_generation_request_carries_schema_and_fixed_parameters(server):
    """REQ-008: el pedido de generación va a `/v1/chat/completions` con el esquema de la
    consulta y los parámetros fijos del plan: sin transmisión parcial, temperatura 0,
    semilla fija, pensamiento apagado y máximo de salida, con el modelo configurado."""
    content = '{"status": "grounded", "statements": [{"text": "x", "citations": ["U1"]}]}'
    server.route("/v1/chat/completions", chat_completion(content))

    result = generation.generate(MESSAGES, SCHEMA)

    [(method, path, body)] = server.requests
    assert (method, path) == ("POST", "/v1/chat/completions")
    assert body["model"] == settings.GENERATION_MODEL
    assert body["messages"] == MESSAGES
    assert body["stream"] is False
    assert body["temperature"] == 0
    assert body["seed"] == settings.GENERATION_SEED
    assert body["max_tokens"] == settings.GENERATION_MAX_OUTPUT_TOKENS
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "response", "strict": True, "schema": SCHEMA},
    }
    # El pedido que se registra es el mismo que se envió.
    assert result.request == body


def test_generation_returns_raw_output_untouched(server):
    """REQ-008, REQ-009: el cliente devuelve la salida del modelo sin tocar, con el motivo
    de fin y las cuentas de tokens; no la interpreta. Una salida cortada (que no cumple el
    esquema) llega igual, para que la validación la trate como falla técnica y no como
    "no determinado"."""
    cut = '{"status": "grounded", "statements": [{"text": "La garantía se integ'
    server.route("/v1/chat/completions", chat_completion(cut, finish_reason="length"))

    result = generation.generate(MESSAGES, SCHEMA)

    assert result.content == cut
    assert result.finish_reason == "length"
    assert result.prompt_tokens == 324
    assert result.completion_tokens == 25
    assert result.response["choices"][0]["message"]["content"] == cut


# --- Vectores ------------------------------------------------------------------------


def test_embeddings_returns_vectors_in_input_order(server):
    """REQ-008: `/v1/embeddings` recibe los textos en un solo pedido y el cliente devuelve
    un vector por texto, en el orden de entrada aunque el servidor los devuelva en otro."""
    server.route("/v1/embeddings", {
        "model": "bge-m3",
        "object": "list",
        "usage": {"prompt_tokens": 12, "total_tokens": 12},
        "data": [
            {"index": 1, "object": "embedding", "embedding": [0.0, 1.0]},
            {"index": 0, "object": "embedding", "embedding": [1.0, 0.0]},
        ],
    })

    vectors = embeddings.embed(["primer texto sintético", "segundo texto sintético"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    [(_, path, body)] = server.requests
    assert path == "/v1/embeddings"
    assert body["model"] == settings.EMBEDDINGS_MODEL
    assert body["input"] == ["primer texto sintético", "segundo texto sintético"]


def test_embeddings_and_rerank_with_no_texts_do_not_call_the_server(server):
    """REQ-008: sin textos no hay pedido; el resultado es una lista vacía."""
    assert embeddings.embed([]) == []
    assert reranker.rerank("pregunta", []) == []
    assert server.requests == []


# --- Reordenamiento con sigmoide -----------------------------------------------------


def test_rerank_applies_sigmoid_and_keeps_input_order(server):
    """REQ-009: el reranker devuelve un valor sin escala; el cliente lo lleva a un número
    entre 0 y 1 con la sigmoide: −8,19 queda en 0,0003 y 5,26 en 0,995 (pares de la ficha
    de `bge-reranker-v2-m3`). Los puntajes vuelven en el orden de los textos enviados,
    aunque el servidor los ordene de mayor a menor."""
    server.route("/v1/rerank", {
        "model": "bge-reranker-v2-m3",
        "object": "list",
        "usage": {"prompt_tokens": 53, "total_tokens": 53},
        "results": [
            {"index": 1, "relevance_score": 5.26},
            {"index": 0, "relevance_score": -8.19},
        ],
    })
    documents = [
        "hi",
        "The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear or simply "
        "panda, is a bear species endemic to China.",
    ]

    scores = reranker.rerank("what is panda?", documents)

    assert round(scores[0], 4) == 0.0003
    assert round(scores[1], 3) == 0.995
    assert all(0 <= s <= 1 for s in scores)
    [(_, path, body)] = server.requests
    assert path == "/v1/rerank"
    assert body["model"] == settings.RERANKER_MODEL
    assert body["query"] == "what is panda?"
    assert body["documents"] == documents
    assert body["top_n"] == 2


def test_sigmoid_does_not_overflow():
    """REQ-009: valores extremos del reranker quedan dentro de 0 y 1, sin error."""
    assert reranker.sigmoid(-1000.0) == 0.0
    assert reranker.sigmoid(1000.0) == 1.0
    assert reranker.sigmoid(0.0) == 0.5
    assert math.isclose(reranker.sigmoid(-8.19), 1 / (1 + math.exp(8.19)))


def test_rerank_with_missing_scores_is_a_service_error(server):
    """REQ-009: si el servidor no devuelve un puntaje por texto, el cliente no inventa los
    que faltan: es una falla del servicio."""
    server.route("/v1/rerank", {"results": [{"index": 0, "relevance_score": 1.0}]})

    with pytest.raises(ServiceUnavailableError):
        reranker.rerank("pregunta", ["uno", "dos"])


# --- Conteo de tokens ----------------------------------------------------------------


@pytest.mark.parametrize("client", [generation, embeddings], ids=["generation", "embeddings"])
def test_count_tokens_returns_the_server_count(server, client):
    """REQ-008: `count_tokens` pide `/tokenize` al servidor del modelo y devuelve el largo
    de la lista de tokens que informa, sin tokens especiales."""
    server.route("/tokenize", {"tokens": [57161, 11808, 441, 142666, 5035, 9, 164837]})

    assert client.count_tokens("ARTÍCULO 1°.- Texto sintético.") == 7

    [(_, path, body)] = server.requests
    assert path == "/tokenize"
    assert body == {"content": "ARTÍCULO 1°.- Texto sintético.", "add_special": False}


def test_each_client_counts_with_its_own_server():
    """REQ-008: el cliente de generación cuenta con el servidor de generación y el de
    embeddings con el suyo (cada modelo corta el texto a su manera)."""
    gen_server, emb_server = FakeServer(), FakeServer()
    try:
        gen_server.route("/tokenize", {"tokens": [1, 2, 3]})
        emb_server.route("/tokenize", {"tokens": [1, 2, 3, 4, 5]})
        with override_settings(GENERATION_URL=gen_server.url, EMBEDDINGS_URL=emb_server.url):
            assert generation.count_tokens("texto") == 3
            assert embeddings.count_tokens("texto") == 5
    finally:
        gen_server.close()
        emb_server.close()


# --- Errores propios -----------------------------------------------------------------


@pytest.mark.parametrize(
    "path, status, payload, call",
    [
        ("/v1/chat/completions", 400, GENERATION_TOO_LONG,
         lambda: generation.generate(MESSAGES, SCHEMA)),
        ("/v1/embeddings", 500, EMBEDDINGS_TOO_LONG,
         lambda: embeddings.embed(["texto sintético muy largo"])),
        ("/v1/rerank", 500, RERANKER_TOO_LONG,
         lambda: reranker.rerank("pregunta", ["pasaje sintético muy largo", "hola"])),
    ],
    ids=["generation-400", "embeddings-500", "reranker-500"],
)
def test_input_rejected_as_too_long_is_its_own_error(server, path, status, payload, call):
    """REQ-008, REQ-009: el rechazo de una entrada demasiado larga se propaga como el error
    propio de entrada demasiado larga, nunca como servicio caído ni se recorta: en
    `generation` llega como HTTP 400 `exceed_context_size_error`; en `embeddings` y
    `reranker`, como HTTP 500 con el mensaje `is too large to process`."""
    server.route(path, payload, status=status)

    with pytest.raises(InputTooLongError) as caught:
        call()

    assert caught.value.reason == "input_too_long"
    assert not isinstance(caught.value, ServiceUnavailableError)
    # Un solo pedido: el cliente no reintenta con la entrada recortada.
    assert len(server.requests) == 1


def test_other_server_error_is_not_input_too_long(server):
    """REQ-009: un HTTP 500 por otro motivo es una falla del servicio, no una entrada
    demasiado larga."""
    server.route("/v1/embeddings", OTHER_SERVER_ERROR, status=500)

    with pytest.raises(ServiceUnavailableError) as caught:
        embeddings.embed(["texto"])

    assert caught.value.reason == "service_unavailable"


@pytest.mark.parametrize(
    "path, call",
    [
        ("/v1/chat/completions", lambda: generation.generate(MESSAGES, SCHEMA)),
        ("/v1/embeddings", lambda: embeddings.embed(["texto"])),
        ("/v1/rerank", lambda: reranker.rerank("pregunta", ["pasaje"])),
        ("/tokenize", lambda: generation.count_tokens("texto")),
    ],
    ids=["generation", "embeddings", "reranker", "tokenize"],
)
def test_timeout_and_service_down_are_distinct_errors(server, path, call):
    """REQ-009: una espera agotada y un servicio que no responde dan errores propios y
    distintos entre sí, con su motivo (`timeout` y `service_unavailable`); ninguno es un
    "no determinado"."""
    server.route(path, {"tokens": [], "results": [], "data": []}, delay=1.0)
    with override_settings(AI_TIMEOUT_SECONDS=0.2):
        with pytest.raises(ServiceTimeoutError) as timed_out:
            call()

    down = closed_port_url()
    with override_settings(GENERATION_URL=down, EMBEDDINGS_URL=down, RERANKER_URL=down):
        with pytest.raises(ServiceUnavailableError) as unavailable:
            call()

    assert timed_out.value.reason == "timeout"
    assert unavailable.value.reason == "service_unavailable"
    assert not isinstance(timed_out.value, ServiceUnavailableError)
    assert not isinstance(unavailable.value, ServiceTimeoutError)
    assert isinstance(timed_out.value, AIServiceError)
    assert isinstance(unavailable.value, AIServiceError)


@pytest.mark.parametrize(
    "call",
    [
        lambda: generation.generate(MESSAGES, SCHEMA),
        lambda: embeddings.embed(["texto"]),
        lambda: reranker.rerank("pregunta", ["pasaje"]),
        lambda: embeddings.count_tokens("texto"),
    ],
    ids=["generation", "embeddings", "reranker", "tokenize"],
)
def test_timeout_while_connecting_is_a_timeout(monkeypatch, call):
    """REQ-008, REQ-009: si la conexión con el servicio no se establece dentro de la
    espera máxima (el servidor no contesta ni rechaza), el cliente da el error de espera
    agotada, con motivo `timeout`, y no el de servicio caído. La conexión se pide con la
    espera de `AI_TIMEOUT_SECONDS`.

    El servidor que no contesta se simula en `socket.create_connection`, que es donde
    `http.client` abre la conexión: espera la mitad del plazo y lanza el mismo error que
    lanza el sistema cuando se agota (`TimeoutError: timed out`)."""
    attempts = []

    def silent_server(address, timeout=None, *args, **kwargs):
        attempts.append((address, timeout))
        time.sleep(timeout / 2)
        raise TimeoutError("timed out")

    monkeypatch.setattr(socket, "create_connection", silent_server)
    with override_settings(
        AI_TIMEOUT_SECONDS=0.2,
        GENERATION_URL="http://generation:8080",
        EMBEDDINGS_URL="http://embeddings:8080",
        RERANKER_URL="http://reranker:8080",
    ):
        with pytest.raises(ServiceTimeoutError) as caught:
            call()

    assert caught.value.reason == "timeout"
    assert not isinstance(caught.value, ServiceUnavailableError)
    [(address, timeout)] = attempts
    assert address[1] == 8080
    assert timeout == 0.2


def test_unexpected_response_is_a_service_error(server):
    """REQ-009: una respuesta que no tiene la forma esperada es una falla del servicio."""
    server.route("/v1/chat/completions", {"sin": "choices"})

    with pytest.raises(ServiceUnavailableError):
        generation.generate(MESSAGES, SCHEMA)


# --- Parámetros ----------------------------------------------------------------------


def test_parameters_have_the_plan_initial_values():
    """REQ-008, REQ-009: los parámetros de búsqueda y generación están en `settings.py`
    con los valores iniciales del plan, y la espera máxima es de 60 segundos."""
    assert settings.AI_TIMEOUT_SECONDS == 60
    assert settings.RETRIEVAL_CANDIDATES_PER_PATH == 30
    assert 0 < settings.RERANK_THRESHOLD < 1
    assert settings.SELECTION_UNITS_PER_CATEGORY == 3
    assert settings.SELECTION_CONSIDERANDOS == 2
    assert settings.PASSAGE_MAX_TOKENS == 800
    assert settings.UNIT_BY_PASSAGES_FROM_TOKENS == 1500
    assert settings.GENERATION_CONTEXT_TOKENS == 16384
    assert settings.PROMPT_TEMPLATE_MARGIN_TOKENS == 512
    assert settings.GENERATION_MAX_STATEMENTS == 6
    assert settings.GENERATION_MAX_OUTPUT_TOKENS == 800
    assert settings.GENERATION_TEMPERATURE == 0
    assert isinstance(settings.GENERATION_SEED, int)
    assert settings.GENERATION_THINKING is False
    assert settings.EMBEDDINGS_DIMENSIONS == 1024
    # Direcciones de los servicios de la red interna (docker-compose.yml), por omisión.
    assert settings.GENERATION_URL.startswith("http")
    assert settings.EMBEDDINGS_URL.startswith("http")
    assert settings.RERANKER_URL.startswith("http")


def test_model_hashes_match_the_downloaded_files():
    """REQ-008: el nombre de archivo y la huella de cada modelo en `settings.py` son los
    que baja y verifica `scripts/fetch_models.sh` (`scripts/models.sha256`), para que el
    registro de cada consulta nombre el archivo que realmente se usó."""
    listed = {}
    for line in (Path(settings.BASE_DIR) / "scripts" / "models.sha256").read_text().splitlines():
        if line.strip():
            sha256, name = line.split()
            listed[name] = sha256

    assert listed[settings.GENERATION_MODEL_FILE] == settings.GENERATION_MODEL_SHA256
    assert listed[settings.EMBEDDINGS_MODEL_FILE] == settings.EMBEDDINGS_MODEL_SHA256
    assert listed[settings.RERANKER_MODEL_FILE] == settings.RERANKER_MODEL_SHA256
    assert settings.GENERATION_ENGINE_BUILD == "b11347"


def test_embedding_dimension_has_a_single_source():
    """REQ-008: la dimensión del vector de `bge-m3` se define una sola vez, en
    `settings.EMBEDDINGS_DIMENSIONS`: la columna `embedding` de `norms_passage`, la
    constante de `norms.models` y la de los dobles de prueba la toman de ahí (son el mismo
    objeto, no un número repetido)."""
    import tests.conftest as test_fixtures
    from evaluon.norms import models as norms_models

    assert norms_models.EMBEDDING_DIMENSIONS is settings.EMBEDDINGS_DIMENSIONS
    assert test_fixtures.EMBEDDING_DIMENSIONS is settings.EMBEDDINGS_DIMENSIONS
    field = norms_models.Passage._meta.get_field("embedding")
    assert field.dimensions == settings.EMBEDDINGS_DIMENSIONS


# --- Dobles de conftest.py -----------------------------------------------------------


def test_generation_double_answers_with_citations(fake_generation):
    """REQ-008: el doble de generación responde, por omisión, una afirmación que cita el
    primer alias que permite el esquema, con la misma forma de resultado que el cliente."""
    result = generation.generate(MESSAGES, SCHEMA)

    output = json.loads(result.content)
    assert output["status"] == "grounded"
    assert output["statements"][0]["citations"] == ["U1"]
    assert result.request == generation.build_request(MESSAGES, SCHEMA)
    assert fake_generation.calls == [(MESSAGES, SCHEMA)]


def test_generation_double_modes(fake_generation):
    """REQ-008, REQ-009: el doble de generación da a pedido una respuesta con las citas
    indicadas, un "no determinado", una salida inválida, una demora agotada, un rechazo por
    entrada demasiado larga o un servicio caído."""
    fake_generation.answer([{"text": "Afirmación sintética.", "citations": ["U2"]}])
    output = json.loads(generation.generate(MESSAGES, SCHEMA).content)
    assert output["statements"] == [{"text": "Afirmación sintética.", "citations": ["U2"]}]

    fake_generation.abstain()
    assert json.loads(generation.generate(MESSAGES, SCHEMA).content) == {
        "status": "undetermined", "statements": []
    }

    fake_generation.invalid_output()
    result = generation.generate(MESSAGES, SCHEMA)
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.content)
    assert result.finish_reason == "length"

    for mode, error in [
        (fake_generation.timeout, ServiceTimeoutError),
        (fake_generation.input_too_long, InputTooLongError),
        (fake_generation.unavailable, ServiceUnavailableError),
    ]:
        mode()
        with pytest.raises(error):
            generation.generate(MESSAGES, SCHEMA)


def test_generation_and_embeddings_doubles_count_words(fake_generation, fake_embeddings):
    """REQ-008: los dobles de generación y de embeddings cuentan tokens de forma fija, por
    palabras, para que las pruebas no dependan del modelo."""
    text = "Artículo 1. Texto   sintético\nde cinco"
    assert generation.count_tokens(text) == 6
    assert embeddings.count_tokens(text) == 6


def test_embeddings_double_gives_fixed_vectors(fake_embeddings):
    """REQ-008: el doble de embeddings da vectores fijos: el mismo texto da siempre el
    mismo vector de 1024 dimensiones, y se puede fijar el vector de un texto."""
    first = embeddings.embed(["uno", "dos"])
    again = embeddings.embed(["uno", "dos"])
    assert first == again
    assert all(len(v) == settings.EMBEDDINGS_DIMENSIONS for v in first)

    chosen = [0.0] * settings.EMBEDDINGS_DIMENSIONS
    chosen[7] = 1.0
    fake_embeddings.vectors["pregunta sintética"] = chosen
    assert embeddings.embed(["pregunta sintética"]) == [chosen]
    assert fake_embeddings.calls[-1] == ["pregunta sintética"]

    fake_embeddings.unavailable()
    with pytest.raises(ServiceUnavailableError):
        embeddings.embed(["uno"])


def test_reranker_double_gives_configurable_scores(fake_reranker):
    """REQ-009: el doble del reranker da puntajes configurables entre 0 y 1: por un texto
    que contiene una marca, o el valor por omisión."""
    fake_reranker.scores["garantía"] = 0.92
    fake_reranker.default = 0.05

    scores = reranker.rerank("pregunta", ["Encabezado. Plazo de la garantía.", "Otro tema."])

    assert scores == [0.92, 0.05]
    assert fake_reranker.calls == [("pregunta", ["Encabezado. Plazo de la garantía.",
                                                 "Otro tema."])]
    fake_reranker.timeout()
    with pytest.raises(ServiceTimeoutError):
        reranker.rerank("pregunta", ["uno"])
