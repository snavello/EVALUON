"""Sesiones (T-006, REQ-016).

Sesiones en la base; 8 horas desde el ingreso y hasta cerrar el navegador; cookie
HttpOnly y SameSite estricto; identificador nuevo al ingresar; la salida anula la
sesión en la base.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.urls import path, reverse
from django.utils import timezone

from evaluon import urls as project_urls
from tests.conftest import TEST_PASSWORD


def protected_page(request):
    return HttpResponse("página protegida")


urlpatterns = project_urls.urlpatterns + [path("protegida/", protected_page)]

pytestmark = [pytest.mark.urls("tests.accounts.test_session"), pytest.mark.django_db]


def log_in(client):
    response = client.post(
        resolve_url(settings.LOGIN_URL),
        {"username": "lectura", "password": TEST_PASSWORD},
    )
    assert response.status_code == 302
    return response


def shift_clock(monkeypatch, start, delta):
    """Pone el reloj de Django en `start + delta`. `start` se toma una sola vez, antes
    de adelantar, para que cada salto se mida desde el mismo instante."""
    monkeypatch.setattr(timezone, "now", lambda: start + delta)


def assert_redirects_to_login(response):
    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))


def test_session_is_stored_in_db_with_strict_cookie(client, read_user):
    """REQ-016: la sesión se guarda en la base; la cookie lleva solo el identificador,
    es HttpOnly y SameSite estricto, y vence al cerrar el navegador (sin fecha)."""
    before = timezone.now()
    response = log_in(client)

    cookie = response.cookies[settings.SESSION_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert cookie["expires"] == ""
    assert cookie["max-age"] == ""

    session = Session.objects.get(session_key=cookie.value)
    expected = before + timedelta(hours=8)
    assert expected <= session.expire_date <= expected + timedelta(minutes=1)
    assert session.get_decoded()["_auth_user_id"] == str(read_user.pk)


def test_login_issues_a_new_session_id(client, read_user):
    """REQ-016: al ingresar se entrega un identificador de sesión nuevo y el anterior
    deja de existir en la base."""
    session = client.session
    session["previo"] = True
    session.save()
    old_key = session.session_key
    assert Session.objects.filter(session_key=old_key).exists()

    log_in(client)

    new_key = client.cookies[settings.SESSION_COOKIE_NAME].value
    assert new_key != old_key
    assert not Session.objects.filter(session_key=old_key).exists()
    assert Session.objects.filter(session_key=new_key).exists()


def test_session_expires_eight_hours_after_login(client, read_user, monkeypatch):
    """REQ-016: con el reloj adelantado más de 8 horas desde el ingreso, la sesión
    venció y se vuelve a pedir usuario y clave. Usarla antes no la extiende."""
    log_in(client)
    login_time = timezone.now()
    assert client.get("/protegida/").status_code == 200

    shift_clock(monkeypatch, login_time, timedelta(hours=7, minutes=59))
    assert client.get("/protegida/").status_code == 200

    shift_clock(monkeypatch, login_time, timedelta(hours=8, minutes=1))
    assert_redirects_to_login(client.get("/protegida/"))


def test_logout_deletes_session_in_db(client, read_user):
    """REQ-016: la salida anula la sesión en la base; el identificador anterior ya no
    sirve aunque se vuelva a presentar."""
    log_in(client)
    key = client.cookies[settings.SESSION_COOKIE_NAME].value
    assert Session.objects.filter(session_key=key).exists()

    response = client.post(reverse("accounts:logout"))

    assert_redirects_to_login(response)
    assert not Session.objects.filter(session_key=key).exists()

    client.cookies[settings.SESSION_COOKIE_NAME] = key
    assert_redirects_to_login(client.get("/protegida/"))


def test_logout_requires_post(client, read_user):
    """REQ-016: la salida es un formulario; un enlace (GET) no cierra la sesión."""
    log_in(client)
    key = client.cookies[settings.SESSION_COOKIE_NAME].value

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405
    assert Session.objects.filter(session_key=key).exists()
