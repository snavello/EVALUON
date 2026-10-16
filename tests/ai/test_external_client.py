"""Cliente de la API externa (T-289; REQ-122; ADR-0066; plan 016, «Plataforma externa»).

Nunca se toca la red real: las pruebas del transporte usan un servidor HTTP local de prueba (el
cliente pide siempre `https://api.anthropic.com`, y la prueba redirige ese pedido al servidor
local) y las demás, el doble `FakeExternal` de `tests/conftest.py`. Todos los textos son
sintéticos (P4).

Qué comprueban:

- `ExternalPayload`: solo se construye con `from_guard`, es inmutable, arma el cuerpo del
  proveedor y su huella, y ningún otro archivo de `evaluon/` lo construye;
- apagado: sin interruptor, con la etapa en `local` o sin clave, `ExternalDisabled` antes de
  abrir un socket; la clave no está en `settings`;
- el cliente: anfitrión fijo y HTTPS, cabeceras, mensaje directo, lotes con sondeo y tope de
  espera, errores propios, reintentos acotados, redirecciones sin seguir y la clave fuera de
  todo error;
- la suite: una llamada real dentro de la suite falla y el doble funciona de punta a punta.
"""

import dataclasses
import json
import socket
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.conf import settings as django_settings

from evaluon.ai.external import client
from evaluon.ai.external.payload import ExternalPayload
from tests.conftest import RealExternalCallError, external_payload

KEY = "clave-sintetica-de-prueba-externa"
EVALUON = Path(django_settings.BASE_DIR) / "evaluon"


# --- Ayudas ---------------------------------------------------------------------------------


def enable(settings, monkeypatch, *stages):
    """Enciende el uso externo con una clave sintética (como `FakeExternal.enable`)."""
    settings.EXTERNAL_ENABLED = True
    stages = stages or tuple(settings.EXTERNAL_STAGE_NAMES)
    settings.EXTERNAL_STAGES = {**settings.EXTERNAL_STAGES,
                                **{stage: "externo" for stage in stages}}
    monkeypatch.setenv(client.KEY_ENV, KEY)


def message_body(text="Respuesta sintética.", **overrides):
    body = {"id": "msg_01", "type": "message", "role": "assistant",
            "model": "claude-sonnet-5-5-20260915",
            "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 120, "output_tokens": 30,
                      "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0}}
    body.update(overrides)
    return body


class Provider:
    """Servidor HTTP local que hace de proveedor: responde lo que se le programa, en orden
    (la última respuesta de una ruta se repite) y guarda lo que le llega."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        self.urls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self):
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.requests.append({
                    "method": self.command, "path": self.path, "body": body,
                    "headers": {k.lower(): v for k, v in self.headers.items()}})
                queue = outer.routes.get((self.command, self.path))
                if not queue:
                    status, headers, payload = 404, {}, json.dumps(
                        {"type": "error", "error": {"type": "not_found_error",
                                                    "message": "no existe"}}).encode()
                else:
                    status, headers, payload = queue.pop(0) if len(queue) > 1 else queue[0]
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = _serve

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def route(self, method, path, body, status=200, headers=None):
        raw = body if isinstance(body, bytes) else (
            body.encode() if isinstance(body, str) else json.dumps(body).encode())
        self.routes.setdefault((method, path), []).append((status, headers or {}, raw))

    def sent(self, method=None, path=None):
        return [r for r in self.requests
                if (method is None or r["method"] == method)
                and (path is None or r["path"] == path)]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def provider(monkeypatch, settings):
    """Un proveedor local y el cliente apuntando a él: el cliente arma su pedido de siempre
    (HTTPS, `api.anthropic.com`) y este reemplazo de `_urlopen` solo cambia el destino, sin
    seguir redirecciones, por el servidor local. Sin esperas reales."""
    server = Provider()
    sleeps = []

    def to_local(request, timeout):
        server.urls.append(request.full_url)
        local = urllib.request.Request(
            f"http://127.0.0.1:{server.port}{urlsplit(request.full_url).path}",
            data=request.data, method=request.get_method(), headers=dict(request.header_items()))
        return client._OPENER.open(local, timeout=timeout)

    monkeypatch.setattr(client, "_urlopen", to_local)
    monkeypatch.setattr(client, "_sleep", sleeps.append)
    server.sleeps = sleeps
    enable(settings, monkeypatch)
    yield server
    server.close()


@pytest.fixture
def clock(monkeypatch):
    """Reloj virtual del cliente: `_sleep` lo adelanta y `_now` lo lee."""
    state = {"now": 0.0, "sleeps": []}

    def sleep(seconds):
        state["sleeps"].append(seconds)
        state["now"] += seconds

    monkeypatch.setattr(client, "_sleep", sleep)
    monkeypatch.setattr(client, "_now", lambda: state["now"])
    return state


def batch_payloads(count=3, **overrides):
    return [external_payload(custom_id=f"ext-{n:04d}", **overrides) for n in range(1, count + 1)]


# --- ExternalPayload --------------------------------------------------------------------------


def test_a_payload_cannot_be_built_without_the_guard():
    """REQ-122 (ADR-0066/0067): el constructor directo falla; solo `from_guard` arma un
    pedido, que es lo que el cliente acepta."""
    with pytest.raises(TypeError, match="from_guard"):
        ExternalPayload(stage="matriz_extraccion", model="m", max_tokens=1, system="",
                        messages=(("user", "x"),), custom_id="a")
    assert isinstance(external_payload(), ExternalPayload)


def test_only_the_guard_module_calls_from_guard():
    """REQ-122: ningún archivo de `evaluon/` fuera de `payload.py` y de `guard.py` (T-290)
    llama a `from_guard`: no hay otro camino para armar un pedido."""
    callers = [path.relative_to(EVALUON).as_posix() for path in sorted(EVALUON.rglob("*.py"))
               if "from_guard(" in path.read_text(encoding="utf-8")]
    assert set(callers) <= {"ai/external/payload.py", "ai/external/guard.py"}


def test_a_payload_is_immutable():
    """REQ-122: el pedido no se puede cambiar después de construido, ni el cuerpo que se
    saca de él cambia el pedido."""
    payload = external_payload()
    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.model = "otro"
    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.messages = ()
    assert isinstance(payload.messages, tuple)
    params = payload.to_params()
    params["messages"].append({"role": "user", "content": "colado"})
    params["model"] = "otro"
    assert payload.to_params()["model"] == "claude-sonnet-5-5"
    assert len(payload.to_params()["messages"]) == 1


def test_the_params_have_the_shape_of_the_providers_message():
    """REQ-122 (ADR-0066, punto 4): modelo, `max_tokens`, mensajes, `system` con la caché de
    una hora en el último bloque, `output_config` con esfuerzo y formato `json_schema`, y
    `thinking`."""
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    payload = external_payload(output_schema=schema, thinking="between_tools", effort="low")
    assert payload.to_params() == {
        "model": "claude-sonnet-5-5", "max_tokens": 1000,
        "messages": [{"role": "user", "content": "Texto público sintético."}],
        "system": [{"type": "text", "text": "Instrucción sintética de la prueba.",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        "output_config": {"effort": "low",
                          "format": {"type": "json_schema", "schema": schema}},
        "thinking": {"type": "between_tools"},
    }


def test_optional_params_are_left_out():
    """REQ-122: sin pensamiento, sin esfuerzo, sin esquema y sin caché, el cuerpo solo lleva
    lo que el pedido fija (el resto lo decide el proveedor)."""
    payload = external_payload(thinking="off", effort=None, cache_system_ttl=None)
    assert payload.to_params() == {
        "model": "claude-sonnet-5-5", "max_tokens": 1000,
        "messages": [{"role": "user", "content": "Texto público sintético."}],
        "system": "Instrucción sintética de la prueba."}
    assert "system" not in external_payload(system="").to_params()
    assert external_payload(thinking="adaptive").to_params()["thinking"] == {"type": "adaptive"}


@pytest.mark.parametrize("overrides", [
    {"thinking": "mucho"}, {"max_tokens": 0}, {"max_tokens": True}, {"max_tokens": "10"},
    {"messages": []}, {"messages": [{"role": "system", "content": "x"}]},
    {"messages": [{"role": "user", "content": "  "}]}, {"custom_id": ""},
    {"custom_id": "x" * 65}, {"model": ""}, {"stage": ""}, {"output_schema": "texto"},
    {"effort": " "}, {"system": 3},
])
def test_an_invalid_payload_is_rejected(overrides):
    """REQ-122: un dato inválido no se corrige: `from_guard` lanza `ValueError`."""
    with pytest.raises(ValueError):
        external_payload(**overrides)


def test_an_unknown_payload_field_is_rejected():
    """REQ-122: un campo que `from_guard` no conoce es un error, no se ignora."""
    with pytest.raises(TypeError, match="desconocidos"):
        external_payload(texto_extra="x")


def test_the_request_fingerprint_depends_on_the_request_and_not_on_the_ids():
    """REQ-122 (ADR-0068): la huella cambia con el texto, el modelo o los parámetros, y no con
    el `custom_id` ni con los identificadores del registro; es estable."""
    base = external_payload()
    assert base.request_sha256 == external_payload().request_sha256
    assert len(base.request_sha256) == 64
    assert base.request_sha256 == external_payload(custom_id="otro", offer_id=9,
                                                   run_id=5).request_sha256
    for change in ({"model": "claude-opus-5-5"}, {"effort": "high"}, {"system": "otra"},
                   {"messages": [{"role": "user", "content": "otro"}]},
                   {"max_tokens": 999}, {"thinking": "off"}, {"output_schema": {"type": "x"}}):
        assert external_payload(**change).request_sha256 != base.request_sha256, change


def test_the_payload_carries_the_ids_the_register_needs():
    """REQ-122 (ADR-0068): procedimiento, oferta, requisito, corrida e instrucción viajan con
    el pedido."""
    payload = external_payload(procedure_id=7, offer_id=3, requirement_id="M-004",
                               run_kind="matrix", run_id=12, instruction_name="matriz-externa",
                               instruction_version="v1", instruction_sha256="a" * 64,
                               definitions_version="v9", definitions_sha256="b" * 64)
    assert (payload.procedure_id, payload.offer_id, payload.requirement_id) == (7, 3, "M-004")
    assert (payload.run_kind, payload.run_id) == ("matrix", 12)
    assert (payload.instruction_name, payload.instruction_version) == ("matriz-externa", "v1")
    assert payload.stage_group == "matriz"
    assert external_payload(stage="verificador").stage_group == "verificador"


# --- Apagado ----------------------------------------------------------------------------------


@pytest.fixture
def no_socket(monkeypatch):
    """Cuenta los intentos de abrir una conexión: `_urlopen` y los sockets de bajo nivel."""
    attempts = []

    def count(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("se abrió un socket")

    monkeypatch.setattr(client, "_urlopen", count)
    monkeypatch.setattr(socket.socket, "connect", count)
    monkeypatch.setattr(socket, "create_connection", count)
    return attempts


def operations(payload):
    batch = client.ExternalBatch(id="msgbatch_1", stage=payload.stage, status="ended",
                                 request_counts={}, payloads=(payload,), request_body={},
                                 response_body={})
    return {
        "send_message": lambda: client.send_message(payload),
        "create_batch": lambda: client.create_batch([payload]),
        "retrieve_batch": lambda: client.retrieve_batch(batch),
        "fetch_results": lambda: client.fetch_results(batch),
        "run_batch": lambda: client.run_batch([payload]),
    }


def test_with_the_default_configuration_nothing_leaves(no_socket):
    """REQ-122, umbral 20 (parte): con los valores por omisión del equipo, toda operación
    lanza `ExternalDisabled` y no se abre ningún socket."""
    assert django_settings.EXTERNAL_ENABLED is False
    assert set(django_settings.EXTERNAL_STAGES.values()) == {"local"}
    for name, operation in operations(external_payload()).items():
        with pytest.raises(client.ExternalDisabled):
            operation()
    assert no_socket == []


@pytest.mark.parametrize("case", ["interruptor", "etapa_local", "sin_clave", "clave_vacia",
                                  "etapa_desconocida"])
def test_each_missing_condition_disables_the_client_before_any_socket(
        case, settings, monkeypatch, no_socket):
    """REQ-122 (ADR-0066, punto 5; O-288-3): la habilitación se decide con el interruptor, la
    etapa y la clave juntos; si falta uno, `ExternalDisabled` y ningún socket (ni `urlopen` ni
    `connect`)."""
    enable(settings, monkeypatch)
    payload = external_payload()
    if case == "interruptor":
        settings.EXTERNAL_ENABLED = False
    elif case == "etapa_local":
        settings.EXTERNAL_STAGES = {**settings.EXTERNAL_STAGES, "matriz": "local"}
    elif case == "sin_clave":
        monkeypatch.delenv(client.KEY_ENV)
    elif case == "clave_vacia":
        monkeypatch.setenv(client.KEY_ENV, "   ")
    else:
        payload = external_payload(stage="cualquier_cosa")
    for operation in operations(payload).values():
        with pytest.raises(client.ExternalDisabled) as raised:
            operation()
        assert raised.value.reason == "external_disabled"
        assert KEY not in str(raised.value)
    assert no_socket == []


def test_the_stage_decides_per_stage(settings, monkeypatch, no_socket):
    """REQ-122: con `matriz` en externo y `verificador` en local, un pedido del verificador no
    sale."""
    enable(settings, monkeypatch, "matriz")
    assert client.require_enabled("matriz_extraccion") == KEY
    with pytest.raises(client.ExternalDisabled):
        client.send_message(external_payload(stage="verificador"))
    assert no_socket == []


def test_the_client_only_accepts_an_external_payload(settings, monkeypatch, no_socket):
    """REQ-122 (ADR-0067): lo que no es un `ExternalPayload` (un diccionario, un texto) se
    rechaza antes de todo, aunque esté habilitado."""
    enable(settings, monkeypatch)
    for thing in ({"model": "x", "messages": []}, "texto", None):
        with pytest.raises(TypeError):
            client.send_message(thing)
        with pytest.raises(TypeError):
            client.create_batch([thing])
    assert no_socket == []


def test_the_key_is_not_in_settings(settings, monkeypatch):
    """REQ-122, P4: `settings` no expone la clave del proveedor, ni encendiendo todo."""
    enable(settings, monkeypatch)
    assert not hasattr(django_settings, "ANTHROPIC_API_KEY")
    assert KEY not in repr({name: getattr(django_settings, name)
                            for name in dir(django_settings) if name.startswith("EXTERNAL_")})


def test_a_real_call_inside_the_suite_fails(settings, monkeypatch):
    """REQ-122, ADR-0066 punto 8: con todo encendido y una clave, pero sin el doble, la
    llamada real falla (el fixture automático corta el único punto que toca la red)."""
    enable(settings, monkeypatch)
    with pytest.raises(RealExternalCallError, match="api.anthropic.com"):
        client.send_message(external_payload())
    with pytest.raises(RealExternalCallError):
        client.run_batch(batch_payloads(1))


def test_the_suite_has_no_key_in_the_environment():
    """REQ-122, P4: el fixture automático saca la clave del entorno de cada prueba."""
    import os
    assert client.KEY_ENV not in os.environ


# --- Transporte: mensaje directo --------------------------------------------------------------


def test_a_direct_message_goes_to_the_fixed_host_with_the_headers(provider):
    """REQ-122 (ADR-0066): `POST https://api.anthropic.com/v1/messages` con `x-api-key`,
    `anthropic-version` y `content-type`, y el cuerpo es el del pedido, sin la clave."""
    provider.route("POST", "/v1/messages", message_body())
    payload = external_payload()
    client.send_message(payload)
    assert provider.urls == ["https://api.anthropic.com/v1/messages"]
    request = provider.sent("POST", "/v1/messages")[0]
    assert request["headers"]["x-api-key"] == KEY
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["headers"]["content-type"] == "application/json"
    assert json.loads(request["body"]) == payload.to_params()
    assert KEY.encode() not in request["body"]


def test_a_direct_message_returns_everything_the_register_needs(provider):
    """REQ-122 (ADR-0068): texto, modelo devuelto, `stop_reason`, uso de tokens (entrada,
    salida, escritura y lectura de caché), identificadores, huella y el cuerpo completo del
    pedido y de la respuesta."""
    body = message_body("Texto de la respuesta.", usage={
        "input_tokens": 120, "output_tokens": 30, "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 7})
    provider.route("POST", "/v1/messages", body)
    payload = external_payload()
    result = client.send_message(payload)
    assert (result.ok, result.outcome, result.mode) == (True, "ok", "directo")
    assert result.text == "Texto de la respuesta."
    assert result.model == "claude-sonnet-5-5-20260915"
    assert result.stop_reason == "end_turn"
    assert result.usage == client.ExternalUsage(120, 30, 100, 7)
    assert (result.message_id, result.batch_id, result.custom_id) == ("msg_01", None, "ext-0001")
    assert result.request_body == payload.to_params()
    assert result.response_body == body
    assert result.request_sha256 == payload.request_sha256
    assert result.payload is payload
    assert result.duration_s >= 0
    assert result.raise_for_outcome() is result


def test_only_text_blocks_make_the_text(provider):
    """REQ-122: el texto es el de los bloques `text`; los de pensamiento no cuentan."""
    provider.route("POST", "/v1/messages", message_body(content=[
        {"type": "thinking", "thinking": "razono", "signature": "x"},
        {"type": "text", "text": "Parte 1. "}, {"type": "text", "text": "Parte 2."}]))
    assert client.send_message(external_payload()).text == "Parte 1. Parte 2."


def test_a_cut_or_refused_answer_is_returned_with_its_stop_reason(provider):
    """REQ-122: `max_tokens` o `refusal` no son errores del cliente: se devuelven con su
    `stop_reason` para que quien lo usa decida."""
    for reason in ("max_tokens", "refusal"):
        provider.routes.clear()
        provider.route("POST", "/v1/messages", message_body("", stop_reason=reason, content=[]))
        assert client.send_message(external_payload()).stop_reason == reason


def test_missing_cache_usage_counts_as_zero(provider):
    """REQ-122: si el proveedor no informa la caché, cuenta cero."""
    provider.route("POST", "/v1/messages",
                   message_body(usage={"input_tokens": 5, "output_tokens": 2}))
    assert client.send_message(external_payload()).usage == client.ExternalUsage(5, 2, 0, 0)


@pytest.mark.parametrize("status,message", [
    (400, "prompt is too long: 250000 tokens > 200000 maximum"),
    (413, "Request exceeds the maximum allowed number of bytes."),
])
def test_a_too_long_request_is_its_own_error(provider, status, message):
    """REQ-122: el rechazo por tamaño es `ExternalInputTooLongError` (`input_too_long`); no se
    recorta ni se reintenta."""
    provider.route("POST", "/v1/messages", {"type": "error", "error": {
        "type": "invalid_request_error", "message": message}}, status=status)
    with pytest.raises(client.ExternalInputTooLongError) as raised:
        client.send_message(external_payload())
    assert raised.value.reason == "input_too_long" and raised.value.status == status
    assert len(provider.sent("POST", "/v1/messages")) == 1


def test_other_http_errors_are_service_unavailable_without_the_key(provider):
    """REQ-122: 401, 500 y similares son `ExternalUnavailableError` con el estado; un pedido
    que pudo haber trabajado no se reintenta, y la clave no aparece en el error."""
    for status in (401, 500, 503):
        provider.requests.clear()
        provider.routes.clear()
        provider.route("POST", "/v1/messages", {"type": "error", "error": {
            "type": "api_error", "message": "falla"}}, status=status)
        with pytest.raises(client.ExternalUnavailableError) as raised:
            client.send_message(external_payload())
        assert raised.value.status == status and raised.value.reason == "service_unavailable"
        assert KEY not in str(raised.value) and KEY not in repr(raised.value.detail)
        assert len(provider.sent("POST", "/v1/messages")) == 1, status


def test_rate_limit_and_overload_are_retried_a_few_times(provider):
    """REQ-122: 429 y 529 (el proveedor rechazó antes de procesar) se reintentan, esperando
    lo que dice `retry-after` o un tiempo creciente, hasta `MAX_RETRIES`."""
    error = {"type": "error", "error": {"type": "overloaded_error", "message": "ocupado"}}
    provider.route("POST", "/v1/messages", error, status=429, headers={"retry-after": "3"})
    provider.route("POST", "/v1/messages", error, status=529)
    provider.route("POST", "/v1/messages", message_body())
    assert client.send_message(external_payload()).ok
    assert len(provider.sent("POST", "/v1/messages")) == 3
    assert provider.sleeps == [3.0, client.RETRY_SECONDS * 2]


def test_retries_are_bounded(provider):
    """REQ-122: si el proveedor sigue rechazando, tras `MAX_RETRIES` reintentos se da por no
    disponible."""
    provider.route("POST", "/v1/messages", {"type": "error", "error": {
        "type": "overloaded_error", "message": "ocupado"}}, status=529)
    with pytest.raises(client.ExternalUnavailableError) as raised:
        client.send_message(external_payload())
    assert raised.value.status == 529
    assert len(provider.sent("POST", "/v1/messages")) == client.MAX_RETRIES + 1


@pytest.mark.parametrize("failure", [
    socket.timeout("timed out"), urllib.error.URLError(socket.timeout("timed out"))])
def test_a_timeout_is_its_own_error_and_is_not_retried(provider, monkeypatch, failure):
    """REQ-122: la espera agotada es `ExternalTimeoutError` (`timeout`); no se reintenta, porque
    el pedido pudo haberse procesado (y cobrado)."""
    calls = []

    def slow(request, timeout):
        calls.append(timeout)
        raise failure

    monkeypatch.setattr(client, "_urlopen", slow)
    with pytest.raises(client.ExternalTimeoutError) as raised:
        client.send_message(external_payload())
    assert raised.value.reason == "timeout"
    assert calls == [client.MESSAGE_TIMEOUT_SECONDS]


def test_a_connection_failure_on_a_post_is_not_retried(provider, monkeypatch):
    """REQ-122: si la conexión se cae durante un pedido que cuesta, se informa sin reintentar
    (podría duplicar el gasto)."""
    calls = []

    def down(request, timeout):
        calls.append(1)
        raise urllib.error.URLError(ConnectionRefusedError("rechazada"))

    monkeypatch.setattr(client, "_urlopen", down)
    with pytest.raises(client.ExternalUnavailableError):
        client.send_message(external_payload())
    assert calls == [1]


@pytest.mark.parametrize("body,error_class", [
    (b"no es json", client.ExternalInvalidResponse),
    (b"[1, 2]", client.ExternalInvalidResponse),
    (json.dumps({"id": "m", "usage": {}}).encode(), client.ExternalInvalidResponse),
    (json.dumps(message_body(content="texto")).encode(), client.ExternalInvalidResponse),
    (json.dumps({k: v for k, v in message_body().items() if k != "usage"}).encode(),
     client.ExternalInvalidResponse),
    (json.dumps(message_body(usage={"input_tokens": "muchos", "output_tokens": 1})).encode(),
     client.ExternalInvalidResponse),
    (json.dumps({"type": "error", "error": {"type": "api_error", "message": "x"}}).encode(),
     client.ExternalUnavailableError),
])
def test_a_malformed_answer_is_not_accepted(provider, body, error_class):
    """REQ-122: una respuesta que no es JSON, no es un objeto, no trae `content` como lista ni
    `usage` válido es `ExternalInvalidResponse`; un error con estado 200 es el error del
    proveedor."""
    provider.route("POST", "/v1/messages", body)
    with pytest.raises(error_class) as raised:
        client.send_message(external_payload())
    assert type(raised.value) is error_class


def test_redirects_are_not_followed(provider):
    """REQ-122, P4: una redirección no se sigue (la clave no viaja a otro destino): es un
    error y el servidor al que apuntaba no recibe nada."""
    provider.route("POST", "/v1/messages", b"", status=302,
                   headers={"location": "http://127.0.0.1:9/robar"})
    with pytest.raises(client.ExternalUnavailableError) as raised:
        client.send_message(external_payload())
    assert raised.value.status == 302
    assert len(provider.requests) == 1


def test_the_host_is_fixed_and_https():
    """REQ-122 (ADR-0066): el anfitrión está escrito en el código, es HTTPS y no sale de
    `settings` ni del entorno."""
    assert client.HOST == "api.anthropic.com"
    assert client.BASE_URL == "https://api.anthropic.com"
    source = Path(client.__file__).read_text(encoding="utf-8")
    assert 'BASE_URL = "https://" + HOST' in source
    assert "settings.EXTERNAL_HOST" not in source and "settings.EXTERNAL_URL" not in source


# --- Transporte: lotes ------------------------------------------------------------------------


def batch_created(batch_id="msgbatch_01", status="in_progress"):
    return {"id": batch_id, "type": "message_batch", "processing_status": status,
            "request_counts": {"processing": 3, "succeeded": 0, "errored": 0, "canceled": 0,
                               "expired": 0}}


def results_lines(*entries):
    return "\n".join(json.dumps({"custom_id": cid, "result": result})
                     for cid, result in entries).encode()


def test_create_batch_posts_every_request_with_its_params(provider):
    """REQ-122 (ADR-0066): `POST /v1/messages/batches` con `requests` de `custom_id` y
    `params` (los mismos campos del mensaje); devuelve el lote con su identificador y su
    estado."""
    provider.route("POST", "/v1/messages/batches", batch_created())
    payloads = batch_payloads(3)
    batch = client.create_batch(payloads)
    assert provider.urls == ["https://api.anthropic.com/v1/messages/batches"]
    sent = json.loads(provider.sent("POST", "/v1/messages/batches")[0]["body"])
    assert sent == {"requests": [{"custom_id": p.custom_id, "params": p.to_params()}
                                 for p in payloads]}
    assert sent == batch.request_body
    assert (batch.id, batch.status, batch.stage) == ("msgbatch_01", "in_progress",
                                                     "matriz_extraccion")
    assert batch.request_counts["processing"] == 3
    assert provider.sent()[0]["headers"]["x-api-key"] == KEY


def test_a_batch_is_checked_before_sending(provider):
    """REQ-122: un lote vacío, con `custom_id` repetidos o con etapas distintas no sale."""
    for payloads in ([], [external_payload(), external_payload()],
                     [external_payload(custom_id="a"),
                      external_payload(custom_id="b", stage="verificador")]):
        with pytest.raises(ValueError):
            client.create_batch(payloads)
    assert provider.requests == []


@pytest.mark.parametrize("bad_id", ["../etc/passwd", "a b", "", None, 5])
def test_a_batch_id_that_is_not_an_identifier_is_rejected(provider, bad_id):
    """REQ-122: el identificador del lote entra en la ruta de las consultas; uno que no es un
    identificador simple es una respuesta inválida."""
    provider.route("POST", "/v1/messages/batches", {**batch_created(), "id": bad_id})
    with pytest.raises(client.ExternalInvalidResponse):
        client.create_batch(batch_payloads(1))


def test_run_batch_polls_until_it_ends_and_returns_each_result(provider, clock, settings):
    """REQ-122 (ADR-0066): crea el lote, lo consulta cada `EXTERNAL_BATCH_POLL_SECONDS` hasta
    que termina y baja los resultados: aciertos, errores, vencidos y cancelados, cada uno en su
    `custom_id` y en el orden de los pedidos."""
    settings.EXTERNAL_BATCH_POLL_SECONDS = 30
    payloads = batch_payloads(4)
    provider.route("POST", "/v1/messages/batches", batch_created())
    path = "/v1/messages/batches/msgbatch_01"
    provider.route("GET", path, batch_created())
    provider.route("GET", path, batch_created())
    provider.route("GET", path, batch_created(status="ended"))
    error = {"type": "error", "error": {"type": "api_error", "message": "falla del lote"}}
    provider.route("GET", path + "/results", results_lines(
        ("ext-0004", {"type": "canceled"}),
        ("ext-0002", {"type": "errored", "error": error}),
        ("ext-0001", {"type": "succeeded", "message": message_body("uno")}),
        ("ext-0003", {"type": "expired"})))
    seen = []
    run = client.run_batch(payloads, on_created=seen.append)
    assert [b.id for b in seen] == ["msgbatch_01"]
    assert run.polls == 3 and run.batch.status == "ended"
    assert clock["sleeps"] == [30, 30, 30]
    assert list(run.results) == ["ext-0001", "ext-0002", "ext-0003", "ext-0004"]
    one, two, three, four = run.results.values()
    assert (one.outcome, one.text, one.batch_id, one.mode) == ("ok", "uno", "msgbatch_01",
                                                             "lotes")
    assert one.usage == client.ExternalUsage(120, 30, 100, 0) and one.duration_s is None
    assert one.request_body == payloads[0].to_params()
    assert (two.outcome, two.text, two.reason) == ("error", "", "service_unavailable")
    assert two.error == error["error"]
    assert (three.outcome, three.reason) == ("expired", "expired")
    assert (four.outcome, four.reason) == ("canceled", "service_unavailable")
    assert run.duration_s == 90
    assert provider.urls[-1] == "https://api.anthropic.com/v1/messages/batches/msgbatch_01/results"


def test_run_batch_gives_up_after_the_maximum_wait(provider, clock, settings):
    """REQ-122: si el lote no termina en `EXTERNAL_BATCH_MAX_WAIT_SECONDS`, `ExternalTimeoutError`
    con el identificador del lote (sigue en el proveedor); la última espera no pasa del tope."""
    settings.EXTERNAL_BATCH_POLL_SECONDS = 30
    settings.EXTERNAL_BATCH_MAX_WAIT_SECONDS = 100
    provider.route("POST", "/v1/messages/batches", batch_created())
    provider.route("GET", "/v1/messages/batches/msgbatch_01", batch_created())
    with pytest.raises(client.ExternalTimeoutError) as raised:
        client.run_batch(batch_payloads(2))
    assert raised.value.batch_id == "msgbatch_01" and raised.value.reason == "timeout"
    assert clock["sleeps"] == [30, 30, 30, 10]
    assert provider.sent("GET", "/v1/messages/batches/msgbatch_01/results") == []


def test_an_expired_or_failed_result_raises_the_matching_error(provider, clock):
    """REQ-122: `raise_for_outcome` convierte un pedido vencido en `ExternalExpired`, uno
    rechazado por largo en `ExternalInputTooLongError` y otro con error en
    `ExternalUnavailableError`."""
    provider.route("POST", "/v1/messages/batches", batch_created(status="ended"))
    too_long = {"type": "error", "error": {"type": "invalid_request_error",
                                           "message": "prompt is too long: 9 > 8"}}
    other = {"type": "error", "error": {"type": "api_error", "message": "falla"}}
    provider.route("GET", "/v1/messages/batches/msgbatch_01/results", results_lines(
        ("ext-0001", {"type": "expired"}), ("ext-0002", {"type": "errored", "error": too_long}),
        ("ext-0003", {"type": "errored", "error": other})))
    run = client.run_batch(batch_payloads(3))
    expected = [client.ExternalExpired, client.ExternalInputTooLongError,
                client.ExternalUnavailableError]
    for result, error_class in zip(run.results.values(), expected):
        with pytest.raises(error_class) as raised:
            result.raise_for_outcome()
        assert raised.value.batch_id == "msgbatch_01"


@pytest.mark.parametrize("lines", [
    [("ext-0001", {"type": "succeeded", "message": message_body()})],                     # faltan
    [("ext-0001", {"type": "expired"}), ("ext-0001", {"type": "expired"}),
     ("ext-0002", {"type": "expired"})],                                                  # repetido
    [("ext-0001", {"type": "expired"}), ("ext-0002", {"type": "expired"}),
     ("ext-9999", {"type": "expired"})],                                                  # ajeno
    [("ext-0001", {"type": "otro"}), ("ext-0002", {"type": "expired"})],                  # tipo
    [("ext-0001", {"type": "succeeded", "message": {"id": "x"}}),
     ("ext-0002", {"type": "expired"})],                                                  # sin content
])
def test_inconsistent_batch_results_are_an_invalid_response(provider, clock, lines):
    """REQ-122: resultados que faltan, se repiten, no se pidieron, de tipo desconocido o sin
    forma de mensaje no se aceptan a medias."""
    provider.route("POST", "/v1/messages/batches", batch_created(status="ended"))
    provider.route("GET", "/v1/messages/batches/msgbatch_01/results", results_lines(*lines))
    with pytest.raises(client.ExternalInvalidResponse) as raised:
        client.run_batch(batch_payloads(2))
    assert raised.value.batch_id == "msgbatch_01"


def test_a_status_of_an_unknown_kind_is_an_invalid_response(provider, clock):
    """REQ-122: un estado de lote que el cliente no conoce detiene la espera."""
    provider.route("POST", "/v1/messages/batches", batch_created())
    provider.route("GET", "/v1/messages/batches/msgbatch_01", batch_created(status="raro"))
    with pytest.raises(client.ExternalInvalidResponse):
        client.run_batch(batch_payloads(1))


def test_polling_survives_a_server_error_but_creation_does_not_repeat(provider, clock):
    """REQ-122: una consulta de estado que falla con 500 se reintenta (no cambia nada); crear
    el lote con 500 no se reintenta (podría crear dos y cobrar dos)."""
    provider.route("POST", "/v1/messages/batches", batch_created())
    path = "/v1/messages/batches/msgbatch_01"
    provider.route("GET", path, {"type": "error", "error": {"type": "api_error",
                                                            "message": "falla"}}, status=500)
    provider.route("GET", path, batch_created(status="ended"))
    provider.route("GET", path + "/results", results_lines(
        ("ext-0001", {"type": "expired"})))
    assert client.run_batch(batch_payloads(1)).polls == 1
    assert len(provider.sent("GET", path)) == 2

    provider.requests.clear()
    provider.routes.clear()
    provider.route("POST", "/v1/messages/batches", {"type": "error", "error": {
        "type": "api_error", "message": "falla"}}, status=500)
    with pytest.raises(client.ExternalUnavailableError):
        client.create_batch(batch_payloads(1))
    assert len(provider.sent("POST", "/v1/messages/batches")) == 1


def test_fetching_results_of_a_running_batch_is_a_mistake(provider):
    """REQ-122: bajar los resultados de un lote que no terminó es un error de quien llama; no
    se pide nada."""
    batch = client.ExternalBatch(id="msgbatch_01", stage="matriz_extraccion",
                                 status="in_progress", request_counts={}, payloads=(),
                                 request_body={}, response_body={})
    with pytest.raises(ValueError):
        client.fetch_results(batch)
    assert provider.requests == []


# --- El doble ---------------------------------------------------------------------------------


def test_the_double_is_off_by_default_like_the_configuration(fake_external):
    """REQ-122: `fake_external` arranca apagado: sin `enable()`, `ExternalDisabled`."""
    with pytest.raises(client.ExternalDisabled):
        client.send_message(external_payload())
    with pytest.raises(client.ExternalDisabled):
        client.run_batch(batch_payloads(1))
    assert fake_external.messages == [] and fake_external.batches == []


def test_the_double_answers_by_custom_id(fake_external):
    """REQ-122: las respuestas se guían por `custom_id`; el modo directo y el de lotes dan el
    mismo resultado, con la forma del cliente real."""
    fake_external.enable()
    fake_external.respond("por omisión")
    fake_external.respond("la del dos", "ext-0002", model="claude-opus-5-5",
                          usage={"cache_read_input_tokens": 50})
    run = client.run_batch(batch_payloads(3))
    assert [r.text for r in run.results.values()] == ["por omisión", "la del dos",
                                                      "por omisión"]
    assert run.results["ext-0002"].model == "claude-opus-5-5"
    assert run.results["ext-0002"].usage.cache_read_input_tokens == 50
    direct = client.send_message(external_payload(custom_id="ext-0002"))
    assert direct.text == "la del dos" and direct.mode == "directo"
    assert fake_external.messages[0].custom_id == "ext-0002"
    assert [len(batch) for batch in fake_external.batches] == [3]


def test_the_double_simulates_polls_failures_and_expiry(fake_external, settings):
    """REQ-122: lotes que terminan tras N consultas, pedidos con error, vencidos y cancelados,
    errores de la llamada entera y un lote que nunca termina, sin esperar de verdad."""
    fake_external.enable()
    settings.EXTERNAL_BATCH_POLL_SECONDS = 30
    fake_external.polls_before_end(3)
    run = client.run_batch(batch_payloads(1))
    assert run.polls == 4 and fake_external.sleeps == [30, 30, 30, 30]

    fake_external.fail("ext-0001")
    fake_external.expire("ext-0002")
    fake_external.cancel("ext-0003")
    results = client.run_batch(batch_payloads(3)).results
    assert [r.outcome for r in results.values()] == ["error", "expired", "canceled"]
    with pytest.raises(client.ExternalUnavailableError):
        client.send_message(external_payload(custom_id="ext-0001"))
    with pytest.raises(client.ExternalExpired):
        client.send_message(external_payload(custom_id="ext-0002"))

    for method, error_class in (("timeout", client.ExternalTimeoutError),
                                ("unavailable", client.ExternalUnavailableError),
                                ("input_too_long", client.ExternalInputTooLongError)):
        getattr(fake_external, method)()
        with pytest.raises(error_class):
            client.send_message(external_payload())
        with pytest.raises(error_class):
            client.create_batch(batch_payloads(1))
    fake_external.working()

    settings.EXTERNAL_BATCH_MAX_WAIT_SECONDS = 100
    fake_external.never_ends()
    with pytest.raises(client.ExternalTimeoutError) as raised:
        client.run_batch(batch_payloads(1))
    assert raised.value.batch_id.startswith("msgbatch_fake_")
    assert fake_external.clock >= 100


def test_the_double_does_not_unblock_the_real_network(fake_external):
    """REQ-122: con el doble puesto, el transporte real sigue cortado: nada del cliente que el
    doble no reemplace puede salir."""
    fake_external.enable()
    with pytest.raises(RealExternalCallError):
        client._call(KEY, "GET", "/v1/messages/batches/x", timeout=1)
