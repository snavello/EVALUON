"""Registro de ingresos e ingresos fallidos, por pantalla y por comando (T-038, REQ-012,
REQ-016; plan 001, "Registro de auditoría").

Un ingreso deja el hecho `login` con el usuario y el canal; un ingreso fallido deja
`login_failed` con el nombre intentado y el canal, sin usuario y nunca con la clave. El
registro no guarda claves ni identificadores de sesión.

Las claves de estas pruebas son sintéticas (P4).
"""

import json
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.shortcuts import resolve_url

from evaluon.accounts import permissions
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent
from tests.conftest import TEST_PASSWORD

WRONG_PASSWORD = "clave-incorrecta-sintetica-t038"


def everything_stored_in_audit():
    """Todo lo guardado en `audit_event`, como texto, para buscar claves y sesiones."""
    return json.dumps(
        list(AuditEvent.objects.values()), default=str, ensure_ascii=False
    )


def events(event_type):
    return list(AuditEvent.objects.filter(event_type=event_type).order_by("pk"))


@pytest.fixture
def typed_password(monkeypatch):
    """Simula la clave escrita por teclado en un comando."""

    def type_(password):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: password)

    return type_


def run_listar_normas(username):
    call_command(
        "listar_normas", usuario=username, stdout=StringIO(), stderr=StringIO()
    )


# --- Pantalla ------------------------------------------------------------------------


@pytest.mark.django_db
def test_screen_login_records_login_with_user_and_channel(client, read_user):
    """REQ-012, REQ-016: un ingreso correcto por pantalla deja el hecho `login` con el
    usuario y el canal `screen`, sin la clave ni el identificador de sesión."""
    response = client.post(
        resolve_url(settings.LOGIN_URL),
        {"username": read_user.username, "password": TEST_PASSWORD},
    )

    assert response.status_code == 302
    [event] = events("login")
    assert event.outcome == "ok"
    assert event.channel == "screen"
    assert event.user_id == read_user.pk
    assert event.username == read_user.username
    assert not events("login_failed")
    stored = everything_stored_in_audit()
    assert TEST_PASSWORD not in stored
    session_key = client.session.session_key
    assert session_key and session_key not in stored


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["clave-incorrecta", "usuario-inexistente", "de-baja"])
def test_screen_failed_login_records_attempted_name_without_password(
    client, read_user, case
):
    """REQ-012, REQ-016: una clave incorrecta, un usuario que no existe o un usuario
    dado de baja en la pantalla de ingreso dejan `login_failed` con el nombre tal como
    se escribió y el canal `screen`, sin usuario y sin la clave."""
    username, password = read_user.username, WRONG_PASSWORD
    if case == "usuario-inexistente":
        username = "nadie-sintetico"
    elif case == "de-baja":
        read_user.is_active = False
        read_user.save()
        password = TEST_PASSWORD

    response = client.post(
        resolve_url(settings.LOGIN_URL), {"username": username, "password": password}
    )

    assert response.status_code == 200
    [event] = events("login_failed")
    assert event.outcome == "failed"
    assert event.channel == "screen"
    assert event.user_id is None
    assert event.username == username
    assert not events("login")
    assert password not in everything_stored_in_audit()


# --- Comandos ------------------------------------------------------------------------


@pytest.mark.django_db
def test_command_login_records_login_with_user_and_channel(typed_password, read_user):
    """REQ-012, REQ-016: un comando con la clave correcta deja el hecho `login` con el
    usuario y el canal `command`, sin la clave."""
    typed_password(TEST_PASSWORD)

    run_listar_normas(read_user.username)

    [event] = events("login")
    assert event.outcome == "ok"
    assert event.channel == "command"
    assert event.user_id == read_user.pk
    assert event.username == read_user.username
    assert not events("login_failed")
    assert TEST_PASSWORD not in everything_stored_in_audit()


@pytest.mark.django_db
@pytest.mark.parametrize("case", ["clave-incorrecta", "usuario-inexistente", "de-baja"])
def test_command_failed_login_records_attempted_name_without_password(
    typed_password, read_user, case
):
    """REQ-012, REQ-016: un comando con clave incorrecta, con un usuario que no existe o
    con un usuario dado de baja se rechaza con el mensaje único y deja `login_failed`
    con el nombre intentado y el canal `command`, sin usuario y sin la clave."""
    username, password = read_user.username, WRONG_PASSWORD
    if case == "usuario-inexistente":
        username = "nadie-sintetico"
    elif case == "de-baja":
        read_user.is_active = False
        read_user.save()
        password = TEST_PASSWORD
    typed_password(password)

    with pytest.raises(CommandError, match="Usuario o clave incorrectos"):
        run_listar_normas(username)

    [event] = events("login_failed")
    assert event.outcome == "failed"
    assert event.channel == "command"
    assert event.user_id is None
    assert event.username == username
    assert not events("login")
    assert password not in everything_stored_in_audit()


@pytest.mark.django_db
def test_command_failed_login_with_very_long_name_is_recorded_cut(typed_password, db):
    """REQ-012: un nombre intentado más largo que el campo se registra recortado; el
    registro no hace fallar el rechazo."""
    username = "x" * 400
    typed_password(WRONG_PASSWORD)

    with pytest.raises(CommandError, match="Usuario o clave incorrectos"):
        permissions.authenticate_command(username)

    [event] = events("login_failed")
    assert event.username == "x" * 150


@pytest.mark.django_db
def test_stored_password_hash_is_not_in_audit(client, typed_password, read_user):
    """REQ-012, REQ-016: después de ingresos correctos y fallidos por los dos canales,
    el registro no contiene ni la clave ni su forma guardada."""
    client.post(
        resolve_url(settings.LOGIN_URL),
        {"username": read_user.username, "password": WRONG_PASSWORD},
    )
    client.post(
        resolve_url(settings.LOGIN_URL),
        {"username": read_user.username, "password": TEST_PASSWORD},
    )
    typed_password(WRONG_PASSWORD)
    with pytest.raises(CommandError):
        run_listar_normas(read_user.username)
    typed_password(TEST_PASSWORD)
    run_listar_normas(read_user.username)

    assert len(events("login")) == 2
    assert len(events("login_failed")) == 2
    stored = everything_stored_in_audit()
    hashed = get_user_model().objects.get(pk=read_user.pk).password
    for secret in (TEST_PASSWORD, WRONG_PASSWORD, hashed):
        assert secret not in stored


# --- Función de registro -------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "detail",
    [
        {"password": "algo"},
        {"datos": {"clave": "algo"}},
        {"lista": [{"sessionid": "abc"}]},
        {"session_key": "abc"},
    ],
)
def test_record_refuses_password_or_session_in_detail(detail, read_user):
    """REQ-012: la función de registro no acepta un detalle con claves ni
    identificadores de sesión, en ningún nivel; no se inserta nada."""
    with pytest.raises(ValueError):
        audit.record(
            "login", outcome="ok", channel="screen", user=read_user, detail=detail
        )

    assert not AuditEvent.objects.exists()
