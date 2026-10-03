"""Espera de una consulta larga detrás de Gunicorn (T-020; plan 001, "Sin verificar":
"Tiempo de espera de Gunicorn con hilos"; ADR-0005).

Una consulta puede tardar hasta 30 segundos (spec, "Tiempo de respuesta"), que es
justo la espera por omisión de Gunicorn. El servicio `app` arranca Gunicorn con una
espera mayor. Esta prueba levanta Gunicorn con el mismo `command` de `app` en
`docker-compose.yml` (solo cambia la dirección, a un puerto libre de 127.0.0.1), sobre la
base de pruebas, y envía una pregunta desde la pantalla, como el navegador. Los tres
servicios de IA son servidores HTTP falsos dentro del test, con la forma de respuesta
de `llama-server`; el del motor tarda de verdad más de 30 segundos en responder. El
doble `fake_generation` de `tests/conftest.py` no sirve aquí: su demora lanza la espera
agotada sin esperar, y además Gunicorn corre en otro proceso, donde los dobles no
llegan.

La consulta tiene que terminar con su respuesta y su registro, sin que Gunicorn corte
el pedido. Los textos son sintéticos (P4).
"""

import http.cookiejar
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.db import connection

from evaluon.queries.models import Query, Status
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db(transaction=True)

COMPOSE_FILE = Path(settings.BASE_DIR) / "docker-compose.yml"

# Espera por omisión de Gunicorn y máximo de una consulta (spec, "Tiempo de respuesta").
GUNICORN_DEFAULT_TIMEOUT = 30

# Lo que tarda el motor falso: más que la espera por omisión de Gunicorn.
GENERATION_DELAY = GUNICORN_DEFAULT_TIMEOUT + 5

QUESTION = "¿Qué garantías sintéticas se exigen?"


def app_command():
    """El `command` del servicio `app` en `docker-compose.yml`."""
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    return [str(part) for part in compose["services"]["app"]["command"]]


def option(command, name):
    """Valor de la opción `name` de una línea de comandos en forma de lista."""
    return command[command.index(name) + 1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeService:
    """Servidor HTTP falso de un servicio de IA. `handlers[ruta](cuerpo)` devuelve el
    cuerpo de la respuesta; `delays[ruta]` son los segundos que tarda en responder.
    Guarda en `requests` cada `(ruta, cuerpo, momento)` recibido."""

    def __init__(self, handlers, delays=None):
        self.handlers = handlers
        self.delays = delays or {}
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"null")
                fake.requests.append((self.path, body, time.monotonic()))
                handler = fake.handlers.get(self.path)
                if handler is None:
                    status, payload = 404, {"error": {"code": 404}}
                else:
                    time.sleep(fake.delays.get(self.path, 0))
                    status, payload = 200, handler(body)
                data = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass  # el cliente ya cortó

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def tokenize(body):
    """`/tokenize` de `llama-server`: un token por palabra."""
    return {"tokens": list(range(len(str(body["content"]).split())))}


def embed(body):
    """`/v1/embeddings`: el mismo vector para todo texto; la búsqueda exacta igual
    devuelve los pasajes ordenados."""
    vector = [0.0] * settings.EMBEDDINGS_DIMENSIONS
    vector[0] = 1.0
    return {
        "model": body["model"], "object": "list",
        "usage": {"prompt_tokens": 8, "total_tokens": 8},
        "data": [{"index": i, "object": "embedding", "embedding": vector}
                 for i, _ in enumerate(body["input"])],
    }


def rerank(body):
    """`/v1/rerank`: valor sin escala alto para todo texto (0,993 con sigmoide), así
    todos pasan el umbral."""
    return {
        "model": body["model"], "object": "list",
        "usage": {"prompt_tokens": 14, "total_tokens": 14},
        "results": [{"index": i, "relevance_score": 5.0}
                    for i, _ in enumerate(body["documents"])],
    }


def chat_completion(body):
    """`/v1/chat/completions`: una afirmación que cita el primer alias del esquema, con
    la marca `regimes_differ` apagada si el esquema la pide (`consulta-v2`, T-040)."""
    schema = body["response_format"]["json_schema"]["schema"]
    statement = schema["properties"]["statements"]["items"]["properties"]
    alias = statement["citations"]["items"]["enum"][0]
    answer = {"text": "Se exigen garantías sintéticas.", "citations": [alias]}
    if "regimes_differ" in statement:
        answer["regimes_differ"] = False
    content = json.dumps({"status": "grounded", "statements": [answer]},
                         ensure_ascii=False)
    return {
        "choices": [{"finish_reason": "stop", "index": 0,
                     "message": {"role": "assistant", "content": content}}],
        "model": body["model"], "object": "chat.completion",
        "usage": {"completion_tokens": 20, "prompt_tokens": 300, "total_tokens": 320},
    }


@pytest.fixture
def ai_services():
    services = {
        "generation": FakeService(
            {"/v1/chat/completions": chat_completion, "/tokenize": tokenize},
            delays={"/v1/chat/completions": GENERATION_DELAY},
        ),
        "embeddings": FakeService({"/v1/embeddings": embed, "/tokenize": tokenize}),
        "reranker": FakeService({"/v1/rerank": rerank}),
    }
    yield services
    for service in services.values():
        service.close()


@pytest.fixture
def gunicorn(ai_services, tmp_path):
    """Gunicorn con el `command` de `app`, sobre la base de pruebas y los servicios
    falsos. Devuelve `(dirección, comando)`."""
    command = app_command()
    port = free_port()
    command[command.index("--bind") + 1] = f"127.0.0.1:{port}"
    env = {
        **os.environ,
        "POSTGRES_DB": connection.settings_dict["NAME"],
        "GENERATION_URL": ai_services["generation"].url,
        "EMBEDDINGS_URL": ai_services["embeddings"].url,
        "RERANKER_URL": ai_services["reranker"].url,
    }
    log = (tmp_path / "gunicorn.log").open("w")
    process = subprocess.Popen(command, cwd=settings.BASE_DIR, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(base + "/ingresar/", timeout=2).close()
                break
            except (urllib.error.URLError, ConnectionError):
                if process.poll() is not None or time.monotonic() > deadline:
                    log.flush()
                    pytest.fail("Gunicorn no arrancó:\n"
                                + (tmp_path / "gunicorn.log").read_text())
                time.sleep(0.2)
        yield base, command
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()


class Browser:
    """Navegador mínimo: guarda las cookies, manda el token CSRF de cada formulario y
    no sigue las redirecciones, para ver la respuesta del envío."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            self._NoRedirect,
        )

    def get(self, path):
        with self.opener.open(self.base + path, timeout=10) as response:
            return response.read().decode()

    def submit(self, path, fields, timeout):
        page = self.get(path)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page).group(1)
        data = urllib.parse.urlencode({"csrfmiddlewaretoken": token, **fields}).encode()
        request = urllib.request.Request(self.base + path, data=data,
                                         headers={"Referer": self.base + path})
        try:
            response = self.opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as redirect:
            # Sin seguir la redirección, urllib la entrega como HTTPError.
            return redirect.code, redirect.headers.get("Location")
        with response:
            return response.status, response.read().decode()


def test_gunicorn_waits_longer_than_a_query_can_take():
    """REQ-013: la configuración de `app` no corta antes de que termine una consulta:
    la espera de Gunicorn supera el máximo de 30 s de una consulta y la espera de los
    clientes de IA, y cada pedido corre en un hilo."""
    command = app_command()
    assert command[0] == "gunicorn"
    timeout = int(option(command, "--timeout"))
    assert timeout > GUNICORN_DEFAULT_TIMEOUT
    assert timeout > settings.AI_TIMEOUT_SECONDS
    assert int(option(command, "--threads")) > 1


def test_query_longer_than_30_seconds_is_not_cut(gunicorn, ai_services, read_user,
                                                  two_regimes):
    """REQ-008, REQ-012, REQ-013: con Gunicorn como lo arranca `app` y un motor que
    tarda más de 30 s, la pregunta enviada desde la pantalla termina con su respuesta
    citada y su registro, y la página redirige a la consulta guardada."""
    base, command = gunicorn
    assert GENERATION_DELAY > GUNICORN_DEFAULT_TIMEOUT
    assert GENERATION_DELAY < settings.AI_TIMEOUT_SECONDS
    assert GENERATION_DELAY < int(option(command, "--timeout"))

    browser = Browser(base)
    status, location = browser.submit(
        "/ingresar/", {"username": read_user.username, "password": TEST_PASSWORD},
        timeout=10,
    )
    assert status == 302, location

    started = time.monotonic()
    status, location = browser.submit(
        "/", {"question": QUESTION, "reference_date": ""},
        timeout=int(option(command, "--timeout")) + 30,
    )
    elapsed = time.monotonic() - started

    assert status == 302, location
    query = Query.objects.get()
    assert location == f"/consultas/{query.pk}/"
    assert elapsed >= GENERATION_DELAY
    assert query.user == read_user
    assert query.question == QUESTION
    assert query.status == Status.GROUNDED
    assert query.result["regime"] == [
        {"norm": two_regimes.new.pk, "name": two_regimes.new.citation}
    ]
    assert query.timings["generation"] >= GENERATION_DELAY
    assert query.timings["total"] >= GENERATION_DELAY

    # El motor recibió un solo pedido de generación, el de la consulta.
    chats = [r for r in ai_services["generation"].requests
             if r[0] == "/v1/chat/completions"]
    assert len(chats) == 1

    page = browser.get(location)
    assert "Se exigen garantías sintéticas." in page
    assert two_regimes.new.citation in page
