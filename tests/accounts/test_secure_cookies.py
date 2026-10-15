"""La aplicación detrás del intermediario cifrado (T-269, REQ-110).

Caddy, en el mismo equipo, recibe la conexión cifrada y reenvía el pedido a `127.0.0.1` con
`X-Forwarded-Proto: https` (plan 007, «Encabezados que pone Caddy»). Django lo toma como un pedido
cifrado (`SECURE_PROXY_SSL_HEADER`) y `accounts/secure_cookies.py` marca `Secure` las cookies de
sesión y de CSRF, para que el navegador no las mande nunca sin cifrar. Un pedido sin ese encabezado
es el uso local por `http://127.0.0.1:8000`, que sigue como siempre.

La dirección es de documentación (192.0.2.0/24, RFC 5737); el usuario y su clave son los
sintéticos de `tests/conftest.py`.
"""

import pytest
from django.conf import settings
from django.shortcuts import resolve_url
from django.test import Client

from tests.conftest import TEST_PASSWORD

ADDRESS = "192.0.2.10"
FROM_CADDY = {"HTTP_HOST": ADDRESS, "HTTP_X_FORWARDED_PROTO": "https"}

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def network_address(settings):
    """La dirección de EVALUON en DJANGO_ALLOWED_HOSTS, como pide entorno.md."""
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, ADDRESS]


def login_url():
    return resolve_url(settings.LOGIN_URL)


def credentials(**extra):
    return {"username": "lectura", "password": TEST_PASSWORD, **extra}


def test_cookies_are_secure_when_the_request_came_encrypted(client, read_user):
    """REQ-110: con `X-Forwarded-Proto: https`, la cookie de CSRF de la pantalla de ingreso y las
    de sesión y CSRF del ingreso salen `Secure`; siguen HttpOnly y SameSite estricto (REQ-016)."""
    page = client.get(login_url(), **FROM_CADDY)
    assert page.status_code == 200
    assert page.cookies[settings.CSRF_COOKIE_NAME]["secure"] is True

    response = client.post(login_url(), credentials(), **FROM_CADDY)

    assert response.status_code == 302
    session = response.cookies[settings.SESSION_COOKIE_NAME]
    assert session["secure"] is True
    assert session["httponly"] is True
    assert session["samesite"] == "Strict"
    assert response.cookies[settings.CSRF_COOKIE_NAME]["secure"] is True


def test_cookies_are_not_secure_on_local_plain_http(client, read_user):
    """REQ-110: sin el encabezado (el uso local por http://127.0.0.1:8000), las cookies salen como
    siempre: una cookie `Secure` no volvería por http y la sesión local no andaría."""
    page = client.get(login_url())
    assert not page.cookies[settings.CSRF_COOKIE_NAME]["secure"]

    response = client.post(login_url(), credentials())

    assert response.status_code == 302
    assert not response.cookies[settings.SESSION_COOKIE_NAME]["secure"]
    assert not response.cookies[settings.CSRF_COOKIE_NAME]["secure"]


def test_a_post_from_the_encrypted_address_passes_the_csrf_check(read_user):
    """REQ-110: un formulario enviado desde `https://<dirección>` (el navegador manda
    `Origin: https://<dirección>`) pasa el control de CSRF: Django sabe que el pedido llegó
    cifrado. Sin `X-Forwarded-Proto`, el mismo envío se rechaza, que es lo que pasaría sin
    `SECURE_PROXY_SSL_HEADER`."""
    origin = {"HTTP_ORIGIN": f"https://{ADDRESS}"}

    behind_caddy = Client(enforce_csrf_checks=True)
    token = behind_caddy.get(login_url(), **FROM_CADDY).cookies[settings.CSRF_COOKIE_NAME].value
    accepted = behind_caddy.post(login_url(), credentials(csrfmiddlewaretoken=token),
                                 **FROM_CADDY, **origin)
    assert accepted.status_code == 302

    without_header = Client(enforce_csrf_checks=True)
    token = without_header.get(login_url(), HTTP_HOST=ADDRESS).cookies[
        settings.CSRF_COOKIE_NAME].value
    rejected = without_header.post(login_url(), credentials(csrfmiddlewaretoken=token),
                                   HTTP_HOST=ADDRESS, **origin)
    assert rejected.status_code == 403
