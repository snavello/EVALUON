"""Comprobación de rol y autenticación de los comandos (REQ-016; ADR-0005).

La comprobación de rol la usan las funciones de negocio (`services`) antes de hacer una
operación: la pantalla y los comandos solo traducen y llaman, de modo que el rol se
comprueba en un solo lugar. El registro del rechazo en la auditoría lo suma T-038.

Los comandos, salvo `crear_usuario`, reciben `--usuario` y piden la clave por teclado
sin mostrarla; se verifica contra la misma tabla de usuarios que usa el ingreso por
pantalla. La clave no se pasa como argumento ni se guarda en ningún lado.
"""

import getpass

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


class RoleRejected(PermissionDenied):
    """El usuario no tiene el rol que pide la operación."""


def require_role(user, required):
    """Deja pasar si `user` es un usuario activo con el rol `required` o uno que lo
    incluye; si no, lanza `RoleRejected`."""
    allowed = _ALLOWED[Role(required)]
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not user.is_active
        or user.role not in allowed
    ):
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


def authenticate_command(username):
    """Pide la clave de `username` por teclado y la verifica contra la tabla de
    usuarios. Devuelve el usuario si la clave es correcta y el usuario está activo; si
    no, lanza `CommandError` con el mensaje único, sin decir cuál de los dos falló."""
    user = authenticate(
        None, username=username, password=read_password("Clave de EVALUON: ")
    )
    if user is None:
        raise CommandError(LOGIN_FAILED_MESSAGE)
    return user
