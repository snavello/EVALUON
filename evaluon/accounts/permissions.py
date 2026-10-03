"""Comprobación de rol (REQ-016; ADR-0005).

La usan las funciones de negocio (`services`) antes de hacer una operación: la pantalla y
los comandos solo traducen y llaman, de modo que el rol se comprueba en un solo lugar.
El registro del rechazo en la auditoría lo suma T-038.
"""

from django.core.exceptions import PermissionDenied

from evaluon.accounts.models import Role

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
