"""Cliente del Portal (T-138; plan 012, "Red y conexión"; ADR-0031).

Todo contra un transporte de mentira: un destino no permitido se rechaza antes de pedir
nada, y las redirecciones se verifican una por una.
"""

import pytest

from evaluon.portal import client as portal_client
from evaluon.portal.client import (
    DestinationNotAllowed,
    PortalHTTPError,
    ResponseTooLarge,
    TooManyRedirects,
    hidden_fields,
    validate_url,
)
from tests.portal.conftest import ALLOWED, reply

PAGE = f"https://{ALLOWED}/PLIEGO/VistaPreviaPliegoCiudadano.aspx?qs=abc"

FORM = (
    b'<form><input type="hidden" name="__VIEWSTATE" value="vs=="/>'
    b'<input type="hidden" name="__EVENTVALIDATION" value="ev"/>'
    b'<input type="text" name="visible" value="no"/>'
    b'<input type="hidden" name="__VIEWSTATEGENERATOR" value="GEN1"/></form>'
)


# --- Lista de destinos ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url, reason",
    [
        ("https://otro.ejemplo.test/x", "no está en la lista"),
        (f"http://{ALLOWED}/x", "HTTPS"),
        (f"https://{ALLOWED}:8443/x", "puerto"),
        (f"https://usuario:clave@{ALLOWED}/x", "usuario"),
        (f"https://{ALLOWED}.otro.test/x", "no está en la lista"),
        (f"https://{ALLOWED}@malo.test/x", "usuario"),
        ("ftp://portal.ejemplo.test/x", "HTTPS"),
        ("https:///x", "host"),
    ],
)
def test_rejected_destinations_never_connect(fake_portal, make_client, url, reason):
    """REQ-045: un host fuera de la lista, HTTP, otro puerto o una dirección con usuario
    se rechazan antes de conectar: el transporte no recibe ninguna solicitud."""
    client = make_client()
    with pytest.raises(DestinationNotAllowed, match=reason):
        client.get(url)
    with pytest.raises(DestinationNotAllowed):
        client.submit_form(url, FORM)
    assert fake_portal.requests == []


def test_explicit_port_443_and_uppercase_host_are_accepted(fake_portal, make_client):
    """REQ-045: el puerto 443 explícito y el host en mayúsculas son el mismo destino."""
    url = f"https://{ALLOWED.upper()}:443/x"
    fake_portal.routes[("GET", url)] = reply(url, b"ok")
    assert make_client().get(url).body == b"ok"


def test_validate_url_uses_settings_by_default(settings):
    """REQ-045: sin lista explícita se usa `PORTAL_ALLOWED_HOSTS`; sirve para validar el
    enlace que registra una persona."""
    settings.PORTAL_ALLOWED_HOSTS = ["afipcompras.afip.gob.ar"]
    assert validate_url("https://afipcompras.afip.gob.ar/PLIEGO/x.aspx?qs=1") == (
        "afipcompras.afip.gob.ar")
    with pytest.raises(DestinationNotAllowed):
        validate_url("https://www.afip.gob.ar/x")


# --- Redirecciones -------------------------------------------------------------------


def test_redirect_to_another_host_is_rejected_before_connecting(fake_portal, make_client):
    """REQ-045: una redirección a otro host se rechaza sin pedirla."""
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, status=302, location="https://malo.test/x")
    with pytest.raises(DestinationNotAllowed):
        make_client().get(PAGE)
    assert [r.url for r in fake_portal.requests] == [PAGE]


def test_redirect_to_http_is_rejected(fake_portal, make_client):
    """REQ-045: una redirección a HTTP también se rechaza."""
    fake_portal.routes[("GET", PAGE)] = reply(
        PAGE, status=301, location=f"http://{ALLOWED}/x")
    with pytest.raises(DestinationNotAllowed, match="HTTPS"):
        make_client().get(PAGE)
    assert len(fake_portal.requests) == 1


def test_redirect_inside_the_list_is_followed_by_hand(fake_portal, make_client):
    """REQ-045: una redirección relativa dentro de la lista se verifica y se sigue."""
    final = f"https://{ALLOWED}/nueva"
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, status=302, location="/nueva")
    fake_portal.routes[("GET", final)] = reply(final, b"destino")
    response = make_client().get(PAGE)
    assert response.body == b"destino"
    assert [r.url for r in fake_portal.requests] == [PAGE, final]


def test_redirect_loop_is_cut(fake_portal, make_client):
    """REQ-045: un ciclo de redirecciones se corta."""
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, status=302, location=PAGE)
    with pytest.raises(TooManyRedirects):
        make_client().get(PAGE)
    assert len(fake_portal.requests) == portal_client.MAX_REDIRECTS + 1


def test_post_redirected_becomes_a_get(fake_portal, make_client):
    """REQ-045: tras un 302 a un envío de formulario, la siguiente solicitud es GET sin
    cuerpo."""
    final = f"https://{ALLOWED}/ver"
    fake_portal.routes[("POST", PAGE)] = reply(PAGE, status=302, location=final)
    fake_portal.routes[("GET", final)] = reply(final, b"listo")
    make_client().submit_form(PAGE, FORM)
    assert fake_portal.requests[1].method == "GET"
    assert fake_portal.requests[1].body == b""


# --- Formularios de ASP.NET ----------------------------------------------------------


def test_hidden_fields_are_read_in_order():
    """REQ-045: de la página salen solo los campos ocultos."""
    assert hidden_fields(FORM) == {
        "__VIEWSTATE": "vs==", "__EVENTVALIDATION": "ev", "__VIEWSTATEGENERATOR": "GEN1",
    }


def test_form_submit_carries_hidden_fields_and_overrides(fake_portal, make_client):
    """REQ-045: el envío lleva los campos ocultos de la página más los que se piden, y
    estos pisan a los ocultos del mismo nombre."""
    fake_portal.routes[("POST", PAGE)] = reply(PAGE, b"archivo")
    make_client().submit_form(
        PAGE, FORM, {"__EVENTTARGET": "ctl00$ver", "__EVENTVALIDATION": "otro"})
    request = fake_portal.requests[0]
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert request.headers["Content-Length"] == str(len(request.body))
    body = request.body.decode()
    assert "__VIEWSTATE=vs%3D%3D" in body
    assert "__VIEWSTATEGENERATOR=GEN1" in body
    assert "__EVENTTARGET=ctl00%24ver" in body
    assert "__EVENTVALIDATION=otro" in body and "__EVENTVALIDATION=ev" not in body
    assert "visible" not in body


def test_cookies_are_kept_between_requests(fake_portal, make_client):
    """REQ-045: el cliente es una sesión: la cookie de una respuesta viaja en la
    siguiente, también en el envío de un formulario."""
    other = f"https://{ALLOWED}/otra"
    fake_portal.routes[("GET", PAGE)] = reply(
        PAGE, b"x", set_cookie="ASP.NET_SessionId=abc123; path=/; HttpOnly")
    fake_portal.routes[("POST", other)] = reply(other, b"y")
    client = make_client()
    client.get(PAGE)
    client.submit_form(other, FORM)
    assert "Cookie" not in fake_portal.requests[0].headers
    assert fake_portal.requests[1].headers["Cookie"] == "ASP.NET_SessionId=abc123"


def test_user_agent_is_identified(fake_portal, make_client):
    """Cada solicitud declara quién es (riesgo "Exceso de pedidos")."""
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, b"x")
    make_client().get(PAGE)
    assert fake_portal.requests[0].headers["User-Agent"].startswith("EVALUON/")


# --- Límites -------------------------------------------------------------------------


def test_response_over_the_size_cap_is_rejected(fake_portal, make_client):
    """REQ-045: una respuesta más grande que el tope se rechaza."""
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, b"x" * 1001)
    with pytest.raises(ResponseTooLarge):
        make_client().get(PAGE)
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, b"x" * 1000)
    assert len(make_client().get(PAGE).body) == 1000


def test_http_error_is_reported(fake_portal, make_client):
    """Un error del Portal no pasa por respuesta buena."""
    with pytest.raises(PortalHTTPError) as caught:
        make_client().get(f"https://{ALLOWED}/no-hay")
    assert caught.value.status == 404


def test_pause_between_requests(fake_portal, make_client):
    """REQ-045: entre una solicitud y la siguiente el cliente espera la pausa; la primera
    sale sin esperar."""
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, b"x")
    now = [100.0]
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    client = make_client(pause=2.0, sleep=sleep, clock=lambda: now[0])
    client.get(PAGE)
    client.get(PAGE)
    now[0] += 5  # pasó más que la pausa: no espera
    client.get(PAGE)
    assert waits == [2.0]


def test_default_transport_gets_timeout_and_cap(monkeypatch):
    """REQ-045: sin transporte propio, el cliente usa el real con la espera y el tope
    configurados (no se conecta: se reemplaza `https_transport`)."""
    seen = {}

    def fake_https(request, *, timeout, max_bytes):
        seen.update(timeout=timeout, max_bytes=max_bytes)
        return reply(request.url, b"ok")

    monkeypatch.setattr(portal_client, "https_transport", fake_https)
    client = portal_client.PortalClient(
        allowed_hosts=[ALLOWED], pause=0, timeout=7, max_bytes=123)
    client.get(PAGE)
    assert seen == {"timeout": 7, "max_bytes": 123}


def test_tests_never_open_a_real_connection(monkeypatch, fake_portal, make_client):
    """P4: ningún test abre una conexión; si el cliente intentara una, la prueba falla."""
    import http.client

    def boom(*args, **kwargs):
        raise AssertionError("se intentó abrir una conexión real")

    monkeypatch.setattr(http.client.HTTPSConnection, "__init__", boom)
    fake_portal.routes[("GET", PAGE)] = reply(PAGE, b"x")
    make_client().get(PAGE)
