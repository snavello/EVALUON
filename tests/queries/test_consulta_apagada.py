"""La Consulta con su motor apagado (T-247, ADR-0057; REQ-107).

Con el Qwen3.8-27B en el motor de lotes, `generation` (el 12B de la Consulta) no se levanta: la
pantalla de la Consulta y la pestaña de Normativas tienen que decir que no está disponible por
ahora, en lugar de recorrer la recuperación y terminar en «falla técnica» con una consulta fallida
guardada. Los dobles de IA no usan la red ni la GPU; el chequeo de salud se prueba con un
`urlopen` falso. Los datos son sintéticos (P4)."""

import contextlib
import http.client
import socket
import threading
import time
import urllib.error

import pytest
from django.urls import reverse

from evaluon.ai import generation
from evaluon.queries.models import Query
from tests.conftest import REAL_IS_AVAILABLE, TEST_PASSWORD

pytestmark = pytest.mark.django_db

NOTICE = "La consulta de normativa no está disponible por ahora"
FAILURE = "No se pudo completar la consulta"


@pytest.fixture
def engine_down(monkeypatch):
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


# --- El chequeo de salud ----------------------------------------------------------------------


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_availability_asks_the_health_of_the_generation_engine(monkeypatch, settings):
    """REQ-107: `is_available` pide `/health` de `GENERATION_URL` con una espera corta; 200 es
    disponible."""
    asked = []

    def urlopen(url, timeout=None):
        asked.append((url, timeout))
        return _Response(200)

    monkeypatch.setattr(generation.urllib.request, "urlopen", urlopen)
    settings.GENERATION_URL = "http://generation:8080/"

    assert REAL_IS_AVAILABLE() is True
    # el tope del chequeo es de 2 s: la pantalla de la Consulta lo hace al mostrarse y, con el
    # motor colgado, no puede esperar más (entorno.md, «La Consulta y las propuestas de datos»)
    assert generation.HEALTH_TIMEOUT_SECONDS == 2
    assert asked == [("http://generation:8080/health", 2)]


@pytest.mark.parametrize("failure", [
    urllib.error.URLError("Name or service not known"),   # el contenedor no existe: apagado
    urllib.error.HTTPError("http://generation:8080/health", 503, "Loading model", {}, None),
    ConnectionRefusedError("rechazada"),
    TimeoutError("sin respuesta"),
    socket.timeout("sin respuesta"),
    ConnectionResetError("cortada"),
    http.client.BadStatusLine("esto no es http"),          # responde algo que no es HTTP
    http.client.IncompleteRead(b"parte"),
    http.client.LineTooLong("status line"),
    http.client.RemoteDisconnected("cerró sin responder"),
], ids=["apagado", "cargando", "rechazada", "espera", "espera-de-socket", "cortada",
        "no-es-http", "lectura-incompleta", "linea-larga", "cerro-sin-responder"])
def test_availability_is_false_when_the_engine_does_not_answer(monkeypatch, failure):
    """REQ-107: apagado, cargando, rechazando o sin contestar a tiempo es «no disponible», y
    nunca una excepción."""
    def urlopen(url, timeout=None):
        raise failure

    monkeypatch.setattr(generation.urllib.request, "urlopen", urlopen)
    assert REAL_IS_AVAILABLE() is False


@contextlib.contextmanager
def tcp_engine(reply):
    """Un servidor TCP local de prueba (solo 127.0.0.1): lee el pedido y contesta `reply` (bytes) y
    cierra, o, con `reply=None`, no contesta nunca. Entrega su dirección."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    server.settimeout(0.1)
    stop, held = threading.Event(), []

    def serve():
        while not stop.is_set():
            try:
                connection, _ = server.accept()
            except OSError:  # la espera de 0,1 s sin nadie, o el servidor cerrado
                continue
            held.append(connection)
            try:
                connection.settimeout(1)
                connection.recv(4096)
                if reply is not None:
                    connection.sendall(reply)
                    connection.close()
            except OSError:
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}"
    finally:
        stop.set()
        thread.join(2)
        for connection in held:
            connection.close()
        server.close()


def test_availability_is_false_when_the_engine_answers_something_that_is_not_http(settings):
    """REQ-107 (H-247-1): un servidor que contesta basura levanta `http.client.BadStatusLine`, que
    no es `OSError`; `is_available` no lanza, devuelve falso."""
    with tcp_engine(b"esto no es http\r\n\r\n") as url:
        settings.GENERATION_URL = url
        assert REAL_IS_AVAILABLE() is False


def test_availability_gives_up_at_the_timeout_when_the_engine_never_answers(settings):
    """REQ-107: un motor colgado (acepta y no contesta) es «no disponible» al vencer la espera, no
    antes ni mucho después."""
    with tcp_engine(None) as url:
        settings.GENERATION_URL = url
        started = time.monotonic()
        assert REAL_IS_AVAILABLE(timeout=0.3) is False
        elapsed = time.monotonic() - started
    assert 0.25 <= elapsed < 2


def test_availability_is_true_for_a_real_200(settings):
    """REQ-107: con un servidor que contesta `200` a `/health`, `is_available` es verdadero."""
    with tcp_engine(b"HTTP/1.1 200 OK\r\nContent-Length: 15\r\nConnection: close\r\n\r\n"
                    b'{"status":"ok"}') as url:
        settings.GENERATION_URL = url
        assert REAL_IS_AVAILABLE() is True


def test_availability_is_false_for_an_answer_that_is_not_200(monkeypatch):
    """REQ-107: una respuesta que no es 200 (sin excepción) tampoco es «disponible»."""
    monkeypatch.setattr(generation.urllib.request, "urlopen",
                        lambda url, timeout=None: _Response(503))
    assert REAL_IS_AVAILABLE() is False


# --- La pantalla de la Consulta ------------------------------------------------------------------


def test_the_screen_says_the_consultation_is_off_instead_of_failing(client, read_user,
                                                                    engine_down):
    """REQ-107: con el motor apagado la pantalla trae el aviso y el botón desactivado; no hay
    bloque de falla técnica."""
    log_in(client, read_user)
    html = client.get(reverse("queries:screen")).content.decode()
    assert NOTICE in html and 'id="query-unavailable"' in html
    assert 'id="query-submit" disabled' in html
    assert FAILURE not in html


def test_the_screen_gives_the_notice_and_not_an_error_page_when_the_engine_is_not_http(
        client, read_user, settings, monkeypatch):
    """REQ-107 (H-247-1): con el chequeo real y un motor que contesta algo que no es HTTP,
    `/consulta/` da el aviso con el botón desactivado, no un error 500."""
    monkeypatch.setattr(generation, "is_available", REAL_IS_AVAILABLE)
    log_in(client, read_user)
    with tcp_engine(b"esto no es http\r\n\r\n") as url:
        settings.GENERATION_URL = url
        response = client.get(reverse("queries:screen"))
    assert response.status_code == 200
    html = response.content.decode()
    assert NOTICE in html and 'id="query-submit" disabled' in html


def test_the_screen_has_no_notice_with_the_engine_up(client, read_user):
    """REQ-107: con el motor encendido la pantalla es la de siempre."""
    log_in(client, read_user)
    html = client.get(reverse("queries:screen")).content.decode()
    assert NOTICE not in html
    assert 'id="query-submit" disabled' not in html and 'id="query-submit"' in html


def test_a_question_sent_with_the_engine_off_is_not_run_nor_saved(client, read_user, fake_ai,
                                                                 engine_down):
    """REQ-107: la pregunta no recorre la recuperación ni deja una consulta fallida guardada; la
    pantalla dice que no está disponible y conserva lo escrito."""
    log_in(client, read_user)
    response = client.post(reverse("queries:screen"),
                           {"question": "¿Qué garantía se exige al ofertar?", "reference_date": ""})
    assert response.status_code == 200
    html = response.content.decode()
    assert NOTICE in html and FAILURE not in html
    assert "¿Qué garantía se exige al ofertar?" in html
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.reranker.calls == []
    assert fake_ai.generation.calls == []


def test_the_page_of_a_saved_query_also_says_it(client, read_user, engine_down):
    """REQ-107: la página de una consulta ya guardada también trae el aviso (el formulario de
    arriba está desactivado)."""
    from tests.queries.test_screen import save_query

    query = save_query(read_user, {"status": "undetermined", "reason": "below_threshold",
                                   "reference_date": "2024-05-20", "regime": [], "notices": [],
                                   "statements": [], "units": {}, "query_id": None})
    log_in(client, read_user)
    html = client.get(reverse("queries:query", args=[query.pk])).content.decode()
    assert NOTICE in html
