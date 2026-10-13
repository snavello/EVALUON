"""Segundo motor de generación y máximo de salida por pedido (T-071; plan 003,
"Componentes" y "Pedido"; ADR-0018, parte 2).

- El cliente de generación manda el máximo de salida que se le pide y espera lo que se
  le indica; sin indicarlo, se comporta como en la 001. `generate_batch` va a
  `GENERATION_BATCH_URL` con la espera de los pedidos del `worker`.
- El doble de `tests/conftest.py` registra lo mismo.
- `docker-compose.yml`: `generation_batch` arranca igual que `generation` (misma imagen,
  `--parallel 1`, `--offline`) salvo el contexto, que es propio (32.768, plan 004,
  ADR-0037), y el modelo, el alias y el proyector de imagen (ADR-0041 y ADR-0042), en la
  red interna y sin puertos;
  `worker` corre `procesar_pedidos` con la imagen de `app`.

Se prueba con un servidor HTTP local de prueba, sin modelo ni GPU. Textos sintéticos
(P4).
"""

import json
import runpy
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.ai import ServiceTimeoutError
from evaluon.ai import generation

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
MESSAGES = [{"role": "user", "content": "Pregunta sintética."}]


class _Engine(BaseHTTPRequestHandler):
    """Servidor de prueba con la forma de `/v1/chat/completions` de `llama-server`.
    Guarda cada cuerpo recibido; con `delay` tarda en responder."""

    bodies = []
    delay = 0.0
    release = None

    def do_POST(self):  # noqa: N802 - nombre de http.server
        length = int(self.headers["Content-Length"])
        type(self).bodies.append(json.loads(self.rfile.read(length)))
        if type(self).release is not None:
            type(self).release.wait(timeout=10)
        payload = json.dumps({
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            pass  # el cliente ya cortó por espera agotada

    def log_message(self, *args):
        pass


@pytest.fixture
def engine():
    _Engine.bodies = []
    _Engine.release = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", _Engine
    if _Engine.release is not None:
        _Engine.release.set()
    server.shutdown()
    server.server_close()


def test_client_sends_the_requested_max_output(engine, settings):
    """REQ-024, REQ-030: el cliente manda el máximo de salida que se le pide (el de la
    matriz, 4.096), no el de la consulta de normativa."""
    url, server = engine
    settings.GENERATION_URL = url
    result = generation.generate(MESSAGES, SCHEMA, max_tokens=settings.MATRIX_MAX_OUTPUT_TOKENS)
    assert server.bodies[-1]["max_tokens"] == 4096
    assert result.request["max_tokens"] == 4096
    assert result.content == '{"ok": true}'


def test_client_without_max_output_keeps_the_001_default(engine, settings):
    """REQ-024: sin indicar el máximo, el pedido es el de la 001
    (`GENERATION_MAX_OUTPUT_TOKENS`), con los mismos parámetros fijos."""
    url, server = engine
    settings.GENERATION_URL = url
    generation.generate(MESSAGES, SCHEMA)
    body = server.bodies[-1]
    assert body["max_tokens"] == settings.GENERATION_MAX_OUTPUT_TOKENS == 800
    assert body["temperature"] == 0
    assert body["seed"] == settings.GENERATION_SEED
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


def test_client_uses_the_given_url_and_timeout(engine, settings):
    """REQ-024: con una dirección y una espera propias, el pedido va a esa dirección y
    se corta al agotar esa espera, aunque la de la 001 sea mayor."""
    url, server = engine
    settings.GENERATION_URL = "http://127.0.0.1:9"  # no debe usarse
    settings.AI_TIMEOUT_SECONDS = 60
    server.release = threading.Event()
    with pytest.raises(ServiceTimeoutError):
        generation.generate(MESSAGES, SCHEMA, base_url=url, timeout=0.5)
    assert len(server.bodies) == 1


def test_generate_batch_goes_to_the_second_engine_with_its_timeout(engine, settings,
                                                                    monkeypatch):
    """REQ-024, REQ-030: `generate_batch` manda el pedido a `GENERATION_BATCH_URL`, con la
    espera de los pedidos del `worker` y el máximo de salida indicado."""
    url, server = engine
    settings.GENERATION_URL = "http://127.0.0.1:9"  # no debe usarse
    settings.GENERATION_BATCH_URL = url
    settings.GENERATION_BATCH_TIMEOUT_SECONDS = 180
    seen = {}
    real_post = generation.post_json

    def spy(service, base_url, path, body, *, timeout=None):
        seen.update(service=service, base_url=base_url, timeout=timeout)
        return real_post(service, base_url, path, body, timeout=timeout)

    monkeypatch.setattr(generation, "post_json", spy)
    generation.generate_batch(MESSAGES, SCHEMA, max_tokens=2048)
    assert seen == {"service": "generation", "base_url": url, "timeout": 180}
    assert server.bodies[-1]["max_tokens"] == 2048


def test_double_records_max_output_url_and_timeout(fake_generation, settings):
    """REQ-024, REQ-030: el doble acepta lo mismo que el cliente y lo registra en
    `options`; su pedido lleva el máximo de salida pedido. `generate_batch` también pasa
    por el doble."""
    result = generation.generate(MESSAGES, SCHEMA, max_tokens=4096)
    assert result.request["max_tokens"] == 4096
    generation.generate_batch(MESSAGES, SCHEMA, max_tokens=1024)
    assert fake_generation.options == [
        {"max_tokens": 4096, "base_url": None, "timeout": None},
        {"max_tokens": 1024, "base_url": settings.GENERATION_BATCH_URL,
         "timeout": settings.GENERATION_BATCH_TIMEOUT_SECONDS},
    ]
    assert len(fake_generation.calls) == 2


# --- T-251: el modelo que atiende el pedido de lotes y el motor con que se cuentan sus tokens ------


@pytest.fixture
def two_engines(settings):
    """Un motor de lotes con otro modelo que el de `generation` (como en una comparación)."""
    settings.GENERATION_MODEL = "modelo-consulta"
    settings.GENERATION_BATCH_MODEL = "modelo-de-lotes"
    settings.GENERATION_URL = "http://generation:8080"
    settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    return settings


def test_a_batch_request_body_names_the_batch_model(two_engines):
    """REQ-107, P6: el cuerpo registrado de un pedido de lotes dice el alias del modelo del
    motor que lo atiende (`GENERATION_BATCH_MODEL`), no el de `generation`."""
    batch = generation.build_batch_request(MESSAGES, SCHEMA, 512)
    assert batch["model"] == "modelo-de-lotes" and batch["max_tokens"] == 512
    assert generation.build_request(MESSAGES, SCHEMA)["model"] == "modelo-consulta"
    assert generation.build_request(
        MESSAGES, SCHEMA, base_url=two_engines.GENERATION_BATCH_URL)["model"] == "modelo-de-lotes"


def test_a_query_request_body_keeps_the_generation_model(two_engines):
    """REQ-107: la consulta de normativa sigue registrando el modelo de `generation`."""
    for body in (generation.build_request(MESSAGES, SCHEMA, 800),
                 generation.build_request(MESSAGES, SCHEMA, 800,
                                          base_url=two_engines.GENERATION_URL)):
        assert body["model"] == "modelo-consulta"


def test_with_a_single_engine_the_model_is_the_one_of_generation(two_engines):
    """REQ-107: si `GENERATION_BATCH_URL` apunta a `GENERATION_URL` (un solo motor), el alias es
    el de ese motor."""
    two_engines.GENERATION_BATCH_URL = two_engines.GENERATION_URL
    assert generation.build_batch_request(MESSAGES, SCHEMA)["model"] == "modelo-consulta"


def test_what_goes_to_the_batch_engine_sends_the_batch_alias(engine, settings):
    """REQ-107: el pedido que de verdad va a `GENERATION_BATCH_URL` (con `generate_batch` o con
    `generate(base_url=…)`, como la evaluación) lleva el alias del lote en el cuerpo enviado, y el
    texto libre de la visión también."""
    url, server = engine
    settings.GENERATION_URL = "http://127.0.0.1:9"
    settings.GENERATION_BATCH_URL = url
    settings.GENERATION_MODEL = "modelo-consulta"
    settings.GENERATION_BATCH_MODEL = "modelo-de-lotes"
    generation.generate_batch(MESSAGES, SCHEMA, max_tokens=64)
    generation.generate(MESSAGES, SCHEMA, base_url=url, timeout=5)
    generation.generate_text(MESSAGES, max_tokens=64, repeat_penalty=1.0, base_url=url, timeout=5)
    assert [b["model"] for b in server.bodies] == ["modelo-de-lotes"] * 3


def test_the_double_records_the_model_of_the_engine_it_was_asked(fake_generation, two_engines):
    """REQ-107: el doble arma el pedido registrado con el mismo criterio que el cliente."""
    consulta = generation.generate(MESSAGES, SCHEMA, max_tokens=10)
    lote = generation.generate_batch(MESSAGES, SCHEMA, max_tokens=10)
    assert consulta.request["model"] == "modelo-consulta"
    assert lote.request["model"] == "modelo-de-lotes"


def test_count_tokens_batch_asks_the_batch_engine(engine, settings, monkeypatch):
    """REQ-107: `count_tokens_batch` pide `/tokenize` a `GENERATION_BATCH_URL`; `count_tokens`,
    a `GENERATION_URL`. Misma interfaz."""
    settings.GENERATION_URL = "http://consulta:8080"
    settings.GENERATION_BATCH_URL = "http://lotes:8080"
    seen = []

    def spy(service, base_url, path, body, *, timeout=None):
        seen.append((base_url, path, body["content"]))
        return {"tokens": [1, 2, 3, 4]}

    import evaluon.ai as ai

    monkeypatch.setattr(ai, "post_json", spy)
    assert generation.count_tokens_batch("un texto") == 4
    assert generation.count_tokens("otro texto") == 4
    assert seen == [("http://lotes:8080", "/tokenize", "un texto"),
                    ("http://consulta:8080", "/tokenize", "otro texto")]


def test_batch_callers_count_with_the_batch_engine(fake_generation, monkeypatch):
    """REQ-107: los llamadores de los lotes (matriz, circulares, respaldo, evaluación) cuentan
    con `count_tokens_batch`, no con `count_tokens`. Se comprueba sobre el código."""
    import re

    root = Path(settings.BASE_DIR) / "evaluon"
    callers = [
        "tenders/proposal/extraction.py", "tenders/proposal/completeness.py",
        "tenders/proposal/consequences.py", "tenders/proposal/circulars.py",
        "tenders/proposal/circular_changes.py", "tenders/proposal/norm_support.py",
        "assessment/documents.py", "assessment/sizing.py",
        "assessment/services/technical_report.py"]
    for name in callers:
        source = (root / name).read_text(encoding="utf-8")
        code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        assert "generation.count_tokens(" not in code and "generation.count_tokens)" not in code, name
        assert "count_tokens_batch" in code, name
        assert "build_request(" not in code.replace("build_batch_request(", ""), name


def test_every_batch_selection_of_norm_units_counts_with_the_batch_engine():
    """REQ-107 (H-244-1, T-254): todo `select_units` que arma un pedido para el motor de lotes
    (respaldo normativo y consecuencias de la matriz) pasa `count=generation.count_tokens_batch`;
    solo la Consulta (`queries/`) cuenta con el motor de la Consulta. Sin esto, la propuesta de
    la matriz falla con `generation` apagado. Se comprueba sobre el código."""
    import re

    root = Path(settings.BASE_DIR) / "evaluon"
    found = 0
    for folder in ("tenders", "assessment", "offers"):
        for path in sorted((root / folder).rglob("*.py")):
            code = re.sub(r'""".*?"""', "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
            for call in re.finditer(r"retrieval\.select_units\(", code):
                # el paréntesis de cierre de la llamada: se cuentan los que abre y cierra
                depth, at = 0, call.end() - 1
                while True:
                    depth += {"(": 1, ")": -1}.get(code[at], 0)
                    if depth == 0:
                        break
                    at += 1
                found += 1
                assert "count=generation.count_tokens_batch" in code[call.start():at], str(path)
    assert found >= 2  # el respaldo normativo y las consecuencias


def test_the_double_replaces_the_new_counter_too(fake_generation):
    """REQ-107: el doble de `tests/conftest.py` reemplaza también `count_tokens_batch`."""
    assert generation.count_tokens_batch("uno dos tres") == 3


# --- docker-compose.yml ------------------------------------------------------------------

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


# Lo propio del motor de lotes: contexto, modelo, alias y proyector de imagen.
BATCH_OWN_FLAGS = ("--ctx-size", "--model", "--alias", "--mmproj")


def _without_batch_own(command):
    """El `command` sin las banderas propias del lote y sus valores."""
    command = [str(item) for item in command]
    for flag in BATCH_OWN_FLAGS:
        if flag in command:
            position = command.index(flag)
            del command[position:position + 2]
    return command


def test_generation_batch_starts_like_generation(compose):
    """REQ-024, REQ-054: `generation_batch` es la misma imagen, compilación, modelo y
    argumentos que `generation` (`--parallel 1`, `--offline`) salvo el contexto, el modelo,
    el alias y el proyector de imagen, en la red interna, sin puertos publicados y con los
    modelos en solo lectura (ADR-0018, ADR-0037, ADR-0042)."""
    services = compose["services"]
    batch, interactive = services["generation_batch"], services["generation"]
    assert batch["image"] == interactive["image"]
    assert batch["image"].endswith(settings.GENERATION_ENGINE_BUILD)
    assert _without_batch_own(batch["command"]) == _without_batch_own(interactive["command"])
    assert "--mmproj" in [str(item) for item in batch["command"]]
    assert "--mmproj" not in [str(item) for item in interactive["command"]]
    command = [str(item) for item in batch["command"]]
    assert command[command.index("--parallel") + 1] == "1"
    assert "--offline" in command
    assert batch["networks"] == ["internal"]
    assert "ports" not in batch
    assert batch["volumes"] == ["./models:/models:ro"]
    assert batch["deploy"] == interactive["deploy"]
    assert batch["healthcheck"] == interactive["healthcheck"]


def test_the_batch_engine_has_its_own_context_and_the_interactive_one_keeps_16384(
        compose, monkeypatch):
    """REQ-054 (ADR-0037): `generation_batch` arranca con `GENERATION_BATCH_CTX_SIZE`
    (32.768 por omisión) y `generation` sigue con `GENERATION_CTX_SIZE` (16.384). Los valores por
    omisión de `settings.py`, no los del entorno: con la Consulta en el motor de lotes
    (docker-compose.consulta-27b.yml, T-255) `app` recibe `GENERATION_CTX_SIZE` de 32.768."""
    services = compose["services"]

    def context(name):
        command = [str(item) for item in services[name]["command"]]
        return command[command.index("--ctx-size") + 1]

    assert context("generation_batch") == "${GENERATION_BATCH_CTX_SIZE:-32768}"
    assert context("generation") == "${GENERATION_CTX_SIZE:-16384}"
    monkeypatch.delenv("GENERATION_BATCH_CTX_SIZE", raising=False)
    monkeypatch.delenv("GENERATION_CTX_SIZE", raising=False)
    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))
    assert fresh["GENERATION_BATCH_CONTEXT_TOKENS"] == 32768
    assert fresh["GENERATION_CONTEXT_TOKENS"] == 16384


def test_worker_runs_the_queue_with_the_app_image(compose):
    """REQ-024: `worker` usa la imagen de `app`, corre `procesar_pedidos`, solo en la red
    interna y sin puertos, y arranca con la base migrada y `generation_batch` sano."""
    services = compose["services"]
    worker = services["worker"]
    assert worker["image"] == services["app"]["image"]
    assert worker["command"][-1] == "procesar_pedidos"
    assert worker["networks"] == ["internal"]
    assert "ports" not in worker
    assert worker["depends_on"]["generation_batch"] == {"condition": "service_healthy"}
    assert worker["depends_on"]["migrate"] == {
        "condition": "service_completed_successfully"
    }


def test_app_and_worker_receive_the_batch_engine_url(compose, monkeypatch):
    """REQ-024: `app` (comando de medición) y `worker` reciben `GENERATION_BATCH_URL`
    desde `.env`, con el mismo valor por omisión que `settings.py`."""
    for name in ("app", "worker", "migrate"):
        environment = compose["services"][name]["environment"]
        assert environment["GENERATION_BATCH_URL"] == (
            "${GENERATION_BATCH_URL:-http://generation_batch:8080}"
        )
    monkeypatch.delenv("GENERATION_BATCH_URL", raising=False)
    fresh = runpy.run_path(str(Path(settings.BASE_DIR) / "evaluon" / "settings.py"))
    assert fresh["GENERATION_BATCH_URL"] == "http://generation_batch:8080"


def test_only_app_writes_the_cases_folder(compose):
    """REQ-024, REQ-030: `app` monta `corpus/casos` con escritura para guardar las
    corridas de medición (plan 003, "Medición"); el resto de `corpus` sigue en solo
    lectura y `worker` no escribe ahí."""
    services = compose["services"]
    assert "./corpus/casos:/app/corpus/casos" in services["app"]["volumes"]
    assert "./corpus:/app/corpus:ro" in services["app"]["volumes"]
    for name in ("worker", "migrate"):
        assert not any("corpus/casos" in v for v in services[name]["volumes"])


# --- Contexto registrado (plan 004, ADR-0037; P6) ----------------------------------------


def test_the_proposal_and_the_sheet_record_the_batch_engine_context(settings):
    """REQ-054 (P6): las propuestas de la 003 y las fichas de la 008 registran el contexto
    real del motor que respondió, el de `generation_batch`, y no el de `generation`."""
    from evaluon.assessment.services import evaluate
    from evaluon.offers.services import sheets
    from evaluon.tenders.proposal import run as proposal_run

    settings.GENERATION_CONTEXT_TOKENS = 16384
    settings.GENERATION_BATCH_CONTEXT_TOKENS = 32768
    for models in (proposal_run._models(), sheets._models(), evaluate._models()):
        assert models["generation_batch"]["context_tokens"] == 32768


def test_the_records_name_the_model_and_the_projector_of_the_batch_engine(settings):
    """REQ-052 (P6, ADR-0042): las propuestas de la 003, las fichas de la 008 y las
    evaluaciones de la 004 registran el alias, el archivo y la huella del modelo del motor
    de lotes y su proyector de imagen, no los de `generation`."""
    from evaluon.assessment.services import evaluate
    from evaluon.offers.services import sheets
    from evaluon.tenders.proposal import run as proposal_run

    settings.GENERATION_MODEL = "interactivo"
    settings.GENERATION_MODEL_FILE = "interactivo.gguf"
    settings.GENERATION_MODEL_SHA256 = "a" * 64
    settings.GENERATION_BATCH_MODEL = "lote"
    settings.GENERATION_BATCH_MODEL_FILE = "lote.gguf"
    settings.GENERATION_BATCH_MODEL_SHA256 = "b" * 64
    settings.GENERATION_BATCH_MMPROJ_FILE = "lote-mmproj.gguf"
    settings.GENERATION_BATCH_MMPROJ_SHA256 = "c" * 64
    for models in (proposal_run._models(), sheets._models(), evaluate._models()):
        assert models["generation_batch"]["model"] == "lote"
        assert models["generation_batch"]["file"] == "lote.gguf"
        assert models["generation_batch"]["sha256"] == "b" * 64
        assert models["generation_batch"]["mmproj_file"] == "lote-mmproj.gguf"
        assert models["generation_batch"]["mmproj_sha256"] == "c" * 64


@pytest.mark.parametrize("name", ["qwen38-27b", "qwen36-35b"])
def test_candidate_batch_engines_start_like_generation(compose, name):
    """REQ-107 (ADR-0056, punto 1: todo igual salvo el modelo): `generation_batch` de cada
    archivo de candidato arranca como `generation` salvo el contexto, el modelo, el alias y
    el proyector (lo propio del lote) y las dos banderas de la caché de prefijo."""
    candidate = yaml.safe_load(
        (Path(settings.BASE_DIR) / f"docker-compose.{name}.yml").read_text(encoding="utf-8"))
    command = candidate["services"]["generation_batch"]["command"]
    interactive = compose["services"]["generation"]["command"]
    stripped = _without_batch_own(command)
    for flag in ("--ctx-checkpoints", "--checkpoint-min-step"):
        position = stripped.index(flag)
        del stripped[position:position + 2]
    assert stripped == _without_batch_own(interactive)
    command = [str(item) for item in command]
    assert command[command.index("--ctx-size") + 1] == "${GENERATION_BATCH_CTX_SIZE:-32768}"
