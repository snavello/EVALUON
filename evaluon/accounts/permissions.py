"""Comprobación de rol y autenticación de los comandos (REQ-016, REQ-012; ADR-0005).

La comprobación de rol la usan las funciones de negocio (`services`) antes de hacer una
operación: la pantalla y los comandos solo traducen y llaman, de modo que el rol se
comprueba en un solo lugar. Ese mismo lugar registra el rechazo (T-038): antes de
rechazar deja el hecho `rejected` con el usuario, la operación intentada y el canal, así
toda función de negocio que rechaza por rol queda registrada sin hacerlo por su cuenta.

- La operación, si quien comprueba no la nombra, es la función que llamó a
  `require_role`, con su módulo (por ejemplo,
  `evaluon.norms.services.loading.load_norm`).
- El canal, si quien comprueba no lo indica, sale de cómo ingresó el usuario: `command`
  si lo devolvió `authenticate_command` (que además anota el nombre del comando) y
  `screen` en otro caso (el usuario de la sesión).

Los comandos, salvo `crear_usuario`, reciben `--usuario` y piden la clave por teclado
sin mostrarla; se verifica contra la misma tabla de usuarios que usa el ingreso por
pantalla. La clave no se pasa como argumento ni se guarda en ningún lado. Un ingreso
correcto por comando deja el hecho `login`; uno fallido deja `login_failed` por la señal
de Django que recibe `evaluon.accounts.apps`, la misma del ingreso por pantalla.
"""

import getpass
import sys

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.core.management import CommandError

from evaluon.accounts.models import Role

# El mismo mensaje único que la pantalla de ingreso (T-006).
LOGIN_FAILED_MESSAGE = "Usuario o clave incorrectos."

# Qué roles alcanzan para cada nivel exigido: lectura y escritura incluye lectura.
_ALLOWED = {
    Role.READ: {Role.READ, Role.READ_WRITE},
    Role.READ_WRITE: {Role.READ_WRITE},
}

# Atributos que `authenticate_command` deja en el usuario que devuelve: solo existen en
# ese objeto, no en la base ni en la sesión.
_CHANNEL_ATTR = "_evaluon_channel"
_COMMAND_ATTR = "_evaluon_command"

_COMMANDS_PACKAGE = ".management.commands."


class RoleRejected(PermissionDenied):
    """El usuario no tiene el rol que pide la operación."""


def _is_identified(user):
    """Usuario de la tabla, con sesión o autenticado por comando (no anónimo)."""
    return (
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "pk", None) is not None
    )


def _calling_operation(frame):
    """Nombre de la función de `frame`, con su módulo."""
    module = frame.f_globals.get("__name__", "")
    return f"{module}.{frame.f_code.co_qualname}"


def record_rejection(user, required, *, operation, channel=None):
    """Deja el hecho `rejected`: usuario (si está identificado), operación intentada,
    rol exigido, rol del usuario, canal y, por comando, el nombre del comando."""
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, EventType, Outcome

    identified = _is_identified(user)
    if channel is None:
        channel = getattr(user, _CHANNEL_ATTR, None) or Channel.SCREEN
    detail = {
        "operation": operation,
        "required_role": str(Role(required)),
        "user_role": getattr(user, "role", None) if identified else None,
    }
    command = getattr(user, _COMMAND_ATTR, None)
    if command:
        detail["command"] = command
    audit.record(
        EventType.REJECTED,
        outcome=Outcome.REJECTED,
        channel=channel,
        user=user if identified else None,
        detail=detail,
    )


def require_role(user, required, *, operation=None, channel=None):
    """Deja pasar si `user` es un usuario activo con el rol `required` o uno que lo
    incluye; si no, registra el hecho `rejected` y lanza `RoleRejected`.

    `operation` y `channel` son opcionales: sin ellos se toman de la función que llama
    y de cómo ingresó el usuario (ver el módulo)."""
    allowed = _ALLOWED[Role(required)]
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not user.is_active
        or user.role not in allowed
    ):
        if operation is None:
            operation = _calling_operation(sys._getframe(1))
        record_rejection(user, required, operation=operation, channel=channel)
        raise RoleRejected("Su usuario no tiene permiso para hacer esta operación.")


def read_password(prompt):
    """Pide la clave por teclado, sin mostrarla en la pantalla."""
    return getpass.getpass(prompt)


def add_user_argument(parser):
    """Agrega a un comando la opción `--usuario`, obligatoria."""
    parser.add_argument(
        "--usuario",
        required=True,
        help="Su nombre de usuario en EVALUON. La clave se pide después, por teclado.",
    )


def _calling_command(frame):
    """Nombre del comando de `manage.py` desde el que se llamó, o vacío."""
    module = frame.f_globals.get("__name__", "")
    if _COMMANDS_PACKAGE in module:
        return module.rsplit(".", 1)[-1]
    return ""


def authenticate_command(username):
    """Pide la clave de `username` por teclado y la verifica contra la tabla de
    usuarios. Devuelve el usuario si la clave es correcta y el usuario está activo, y
    deja el hecho `login` por comando; si no, lanza `CommandError` con el mensaje único,
    sin decir cuál de los dos falló (el hecho `login_failed` lo deja la señal de
    ingreso fallido de Django). La clave solo pasa a `authenticate`."""
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, EventType, Outcome

    user = authenticate(
        None, username=username, password=read_password("Clave de EVALUON: ")
    )
    if user is None:
        raise CommandError(LOGIN_FAILED_MESSAGE)
    command = _calling_command(sys._getframe(1))
    setattr(user, _CHANNEL_ATTR, Channel.COMMAND)
    setattr(user, _COMMAND_ATTR, command)
    audit.record(
        EventType.LOGIN,
        outcome=Outcome.OK,
        channel=Channel.COMMAND,
        user=user,
        detail={"command": command} if command else None,
    )
    return user
