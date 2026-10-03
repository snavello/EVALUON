"""Función de registro de auditoría (REQ-012, P6; plan 001, "Registro de auditoría").

Solo inserta filas en `audit_event`. Quien llama arma el detalle propio de cada hecho y
nunca pone en él claves ni identificadores de sesión. La versión vigente de la
normativa (`corpus_version`) la completa T-008; hasta entonces queda vacía.
"""

from evaluon.audit.models import AuditEvent


def record(event_type, *, outcome, channel, user=None, username="", detail=None):
    """Registra un hecho y lo devuelve.

    - `event_type`, `outcome` y `channel`: valores de `EventType`, `Outcome` y `Channel`.
    - `user`: usuario que actuó, o `None` (ingreso fallido, alta por quien administra
      el equipo).
    - `username`: nombre tal como se escribió; si falta y hay usuario, se usa el suyo.
    - `detail`: datos propios del hecho, que se guardan como JSON.
    """
    if user is not None and not username:
        username = user.get_username()
    return AuditEvent.objects.create(
        event_type=event_type,
        outcome=outcome,
        channel=channel,
        user=user,
        username=username,
        corpus_version=None,
        detail=detail if detail is not None else {},
    )
