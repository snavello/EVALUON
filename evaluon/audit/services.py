"""Función de registro de auditoría (REQ-012, P6; plan 001, "Registro de auditoría").

Solo inserta filas en `audit_event`: un trigger de la base rechaza cualquier UPDATE o
DELETE (T-007). Quien llama arma el detalle propio de cada hecho y nunca pone en él
claves ni identificadores de sesión; `record` rechaza un detalle con un dato de esos
nombres (`FORBIDDEN_DETAIL_KEYS`, T-038).

Versión de la normativa (P8; plan 001, `norms_corpus_version`). Todo hecho lleva en
`corpus_version` el número de la versión vigente al registrarlo: la última de
`norms_corpus_version`, o vacío si todavía no hay ninguna.

Los hechos que cambian lo que se puede consultar o lo que se avisa (validar una lectura,
registrar una relación, registrar una versión de una norma, anotar modificatorias sin
cargar) crean una versión nueva con `creates_corpus_version=True`. Como el hecho no se
puede modificar después de insertado, el orden es:

1. Se bloquea `norms_corpus_version` contra otras creaciones de versión (modo
   SHARE ROW EXCLUSIVE, que no impide leerla). Así los números se confirman en el mismo
   orden en que se reservan y nadie ve vigente un número cuyo cambio todavía no se
   confirmó.
2. Se reserva el número con `nextval` de la secuencia de `norms_corpus_version.id`.
3. Se inserta el hecho con ese número en `corpus_version` y en su detalle
   (`new_corpus_version`).
4. Se inserta la versión con ese número, apuntando al hecho.

Todo dentro de la transacción de quien llama: el cambio que origina la versión (por
ejemplo, pasar una lectura a `validated`) va en el mismo `transaction.atomic()`, de modo
que el cambio, el hecho y la versión se confirman o se deshacen juntos.
"""

from django.db import connection, transaction

from evaluon.audit.models import AuditEvent, Outcome
from evaluon.norms.models import CorpusVersion

CORPUS_VERSION_TABLE = CorpusVersion._meta.db_table


def current_corpus_version():
    """Número de la versión de la normativa vigente, o `None` si no hay ninguna."""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT max(id) FROM {CORPUS_VERSION_TABLE}")
        return cursor.fetchone()[0]


def _reserve_corpus_version():
    """Bloquea la creación de otras versiones hasta el fin de la transacción y reserva
    el número de la versión nueva."""
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {CORPUS_VERSION_TABLE} IN SHARE ROW EXCLUSIVE MODE")
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [CORPUS_VERSION_TABLE]
        )
        return cursor.fetchone()[0]


# Nombres de dato que el detalle de un hecho nunca lleva: claves e identificadores de
# sesión (plan 001, "Registro de auditoría"; T-038). Se comparan en minúsculas.
FORBIDDEN_DETAIL_KEYS = frozenset({
    "password", "passwd", "clave", "contraseña",
    "sessionid", "session_id", "session_key", "csrfmiddlewaretoken",
})


def _refuse_secrets(value):
    """Lanza `ValueError` si `value` tiene, en cualquier nivel, un dato con nombre de
    clave o de identificador de sesión."""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_DETAIL_KEYS:
                raise ValueError(
                    f"El detalle de un hecho no puede llevar el dato {key!r}: el "
                    "registro no guarda claves ni identificadores de sesión."
                )
            _refuse_secrets(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _refuse_secrets(item)


def record(
    event_type,
    *,
    outcome,
    channel,
    user=None,
    username="",
    detail=None,
    creates_corpus_version=False,
):
    """Registra un hecho y lo devuelve.

    - `event_type`, `outcome` y `channel`: valores de `EventType`, `Outcome` y `Channel`.
    - `user`: usuario que actuó, o `None` (ingreso fallido, alta por quien administra
      el equipo).
    - `username`: nombre tal como se escribió; si falta y hay usuario, se usa el suyo.
    - `detail`: datos propios del hecho, que se guardan como JSON.
    - `creates_corpus_version`: el hecho crea una versión nueva de la normativa. Solo
      con resultado `ok`. El hecho lleva el número nuevo en `corpus_version` y en
      `detail["new_corpus_version"]`, y la versión apunta al hecho. Quien llama hace su
      cambio y este registro dentro del mismo `transaction.atomic()`.

    Sin `creates_corpus_version`, el hecho lleva la versión vigente.
    """
    if user is not None and not username:
        username = user.get_username()
    detail = dict(detail) if detail is not None else {}
    _refuse_secrets(detail)

    if not creates_corpus_version:
        return AuditEvent.objects.create(
            event_type=event_type,
            outcome=outcome,
            channel=channel,
            user=user,
            username=username,
            corpus_version=current_corpus_version(),
            detail=detail,
        )

    if outcome != Outcome.OK:
        raise ValueError(
            "Solo un hecho con resultado 'ok' crea una versión de la normativa."
        )
    with transaction.atomic():
        number = _reserve_corpus_version()
        detail["new_corpus_version"] = number
        event = AuditEvent.objects.create(
            event_type=event_type,
            outcome=outcome,
            channel=channel,
            user=user,
            username=username,
            corpus_version=number,
            detail=detail,
        )
        CorpusVersion.objects.create(
            id=number, created_at=event.occurred_at, event=event
        )
    return event
