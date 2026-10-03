"""Alta de usuarios por comando y autenticación de los comandos (T-007, REQ-016, REQ-012).

`crear_usuario` lo corre quien administra el equipo, sin rol de EVALUON, y deja el hecho
`user_created` sin usuario actuante (plan 001, "Pantalla, acceso y comandos"). Los demás
comandos reciben `--usuario` y piden la clave por teclado sin mostrarla (ADR-0005).

La clave se pide con `permissions.read_password`; las pruebas la reemplazan por una
función que devuelve claves sintéticas, como si la persona las escribiera.
"""

import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.core.management.base import CommandParser

from evaluon.accounts import permissions
from evaluon.accounts.models import Role
from evaluon.audit.models import AuditEvent
from tests.conftest import TEST_PASSWORD

NEW_PASSWORD = "otra-clave-sintetica-larga"


@pytest.fixture
def typed_passwords(monkeypatch):
    """Simula lo que la persona escribe cuando se le pide la clave. Guarda los textos
    con que se le pidió."""
    prompts = []

    def type_(*answers):
        pending = list(answers)

        def fake_read_password(prompt):
            prompts.append(prompt)
            return pending.pop(0)

        monkeypatch.setattr(permissions, "read_password", fake_read_password)
        return prompts

    return type_


def run_crear_usuario(*args, **options):
    out, err = StringIO(), StringIO()
    call_command("crear_usuario", *args, stdout=out, stderr=err, **options)
    return out.getvalue(), err.getvalue()


def everything_stored_in_audit():
    """Todo lo guardado en `audit_event`, como texto, para buscar la clave."""
    return json.dumps(
        list(AuditEvent.objects.values()), default=str, ensure_ascii=False
    )


# --- crear_usuario ---------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rol, role", [("lectura", Role.READ), ("lectura-escritura", Role.READ_WRITE)]
)
def test_crear_usuario_creates_user_with_role_and_records_event(
    typed_passwords, rol, role
):
    """REQ-016 y REQ-012: `crear_usuario` crea el usuario con su rol, la clave no queda
    legible y existe el hecho `user_created` sin usuario actuante."""
    prompts = typed_passwords(NEW_PASSWORD, NEW_PASSWORD)

    out, _ = run_crear_usuario("ana", rol=rol)

    user = get_user_model().objects.get(username="ana")
    assert user.role == role
    assert user.is_active
    assert NEW_PASSWORD not in user.password
    assert user.password.startswith("argon2$argon2id$")
    assert user.check_password(NEW_PASSWORD)
    assert len(prompts) == 2
    assert "ana" in out

    event = AuditEvent.objects.get(event_type="user_created")
    assert event.user is None
    assert event.outcome == "ok"
    assert event.channel == "command"
    assert event.detail["created_user"] == "ana"
    assert event.detail["role"] == role


@pytest.mark.django_db
def test_crear_usuario_never_stores_the_password(typed_passwords):
    """REQ-016 y REQ-012: la clave no se guarda en el hecho registrado, ni en su
    detalle ni en ningún otro campo, y no se muestra en la salida del comando."""
    typed_passwords(NEW_PASSWORD, NEW_PASSWORD)

    out, err = run_crear_usuario("ana", rol="lectura")

    assert AuditEvent.objects.count() == 1
    assert NEW_PASSWORD not in everything_stored_in_audit()
    assert NEW_PASSWORD not in out
    assert NEW_PASSWORD not in err


@pytest.mark.django_db
def test_crear_usuario_rejects_password_of_7_characters(typed_passwords):
    """REQ-016: una clave de 7 caracteres se rechaza, con un mensaje que dice "clave"
    y no "contraseña", y no se crea el usuario ni el hecho."""
    short = "abcdefg"
    typed_passwords(short, short)

    with pytest.raises(CommandError) as rejected:
        run_crear_usuario("ana", rol="lectura")

    message = str(rejected.value)
    assert "clave" in message
    assert "8" in message
    assert "contraseña" not in message.lower()
    assert short not in message
    assert not get_user_model().objects.filter(username="ana").exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_crear_usuario_rejects_different_confirmation(typed_passwords):
    """REQ-016: si la confirmación no coincide con la clave, no se crea el usuario ni
    el hecho."""
    typed_passwords(NEW_PASSWORD, NEW_PASSWORD + "x")

    with pytest.raises(CommandError) as rejected:
        run_crear_usuario("ana", rol="lectura")

    assert "clave" in str(rejected.value)
    assert not get_user_model().objects.filter(username="ana").exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_crear_usuario_rejects_existing_username(typed_passwords, read_user):
    """REQ-016: un nombre de usuario que ya existe se rechaza sin tocar al usuario
    existente ni registrar un alta."""
    typed_passwords(NEW_PASSWORD, NEW_PASSWORD)
    stored_before = get_user_model().objects.get(pk=read_user.pk).password

    with pytest.raises(CommandError):
        run_crear_usuario(read_user.username, rol="lectura-escritura")

    user = get_user_model().objects.get(pk=read_user.pk)
    assert user.role == Role.READ
    assert user.password == stored_before
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_crear_usuario_requires_a_valid_role(typed_passwords):
    """REQ-016: solo hay dos roles; otro valor se rechaza sin crear el usuario."""
    typed_passwords(NEW_PASSWORD, NEW_PASSWORD)

    with pytest.raises(CommandError):
        run_crear_usuario("ana", rol="administrador")

    assert not get_user_model().objects.filter(username="ana").exists()
    assert not AuditEvent.objects.exists()


def test_crear_usuario_does_not_take_the_password_as_argument():
    """REQ-016: la clave no se pasa como argumento (quedaría en el historial de la
    terminal); el comando no tiene opción para eso ni pide `--usuario` de quien actúa."""
    from evaluon.accounts.management.commands.crear_usuario import Command

    parser = Command().create_parser("manage.py", "crear_usuario")
    options = {o for action in parser._actions for o in action.option_strings}
    assert not {"--clave", "--password", "--contraseña", "--usuario"} & options


# --- autenticación de los comandos -----------------------------------------------


def test_command_user_argument_is_usuario():
    """REQ-016: los comandos reciben `--usuario`, obligatorio, y ninguna opción para
    la clave."""
    parser = CommandParser(prog="prueba")
    permissions.add_user_argument(parser)

    assert parser.parse_args(["--usuario", "ana"]).usuario == "ana"
    with pytest.raises(CommandError):
        parser.parse_args([])


@pytest.mark.django_db
def test_command_authentication_accepts_right_password(typed_passwords, read_user):
    """REQ-016: la autenticación de comandos acepta la clave correcta y devuelve el
    usuario de la misma tabla que usa el ingreso por pantalla."""
    prompts = typed_passwords(TEST_PASSWORD)

    user = permissions.authenticate_command(read_user.username)

    assert user.pk == read_user.pk
    assert user.role == Role.READ
    assert len(prompts) == 1
    assert "clave" in prompts[0].lower()


@pytest.mark.django_db
@pytest.mark.parametrize("username", ["lectura", "no-existe"])
def test_command_authentication_rejects_wrong_password_without_storing_it(
    typed_passwords, read_user, username
):
    """REQ-016: la autenticación de comandos rechaza una clave incorrecta (o un usuario
    que no existe) con el mensaje único, y la clave no queda guardada en ningún lado:
    ni en el registro, ni en el usuario, ni en el mensaje."""
    wrong = "clave-incorrecta-sintetica"
    typed_passwords(wrong)
    stored_before = get_user_model().objects.get(pk=read_user.pk).password

    with pytest.raises(CommandError) as rejected:
        permissions.authenticate_command(username)

    assert str(rejected.value) == "Usuario o clave incorrectos."
    assert wrong not in everything_stored_in_audit()
    assert get_user_model().objects.get(pk=read_user.pk).password == stored_before


@pytest.mark.django_db
def test_command_authentication_rejects_inactive_user(typed_passwords, read_user):
    """REQ-016: un usuario dado de baja no puede correr comandos aunque la clave sea
    correcta."""
    read_user.is_active = False
    read_user.save()
    typed_passwords(TEST_PASSWORD)

    with pytest.raises(CommandError):
        permissions.authenticate_command(read_user.username)


def test_password_is_read_without_echo(monkeypatch):
    """REQ-016: la clave se pide por teclado sin mostrarla (`getpass`)."""
    calls = []
    monkeypatch.setattr(
        permissions.getpass, "getpass", lambda prompt: calls.append(prompt) or "x"
    )

    assert permissions.read_password("Clave: ") == "x"
    assert calls == ["Clave: "]
