"""Registrar y listar procedimientos (REQ-022; plan 003, "Procedimiento y documentos",
"Roles" y "Registro de auditoría"; T-069).

- `register_procedure`: registra un procedimiento con su número, tipo, objeto y fecha
  de autorización. Lo hacen el operador y el evaluador. Rechaza, sin guardar nada ni
  dejar el hecho `procedure`, un dato obligatorio vacío o demasiado largo, una fecha
  posterior al día (en hora de Buenos Aires, como en la 001) y un número que ya está
  registrado. El número se compara tal como se escribió, sin los espacios de los
  extremos.
- `list_procedures`: los procedimientos, el más reciente primero, cada uno con su
  régimen y el estado de su última versión de la matriz. Lo ven el operador y el
  evaluador.

El régimen no se guarda en el procedimiento: se calcula con `applicable_regimes(fecha)`
de la 001 cada vez que se muestra (`regime_for`). Al registrar, el régimen y la versión
de la normativa se leen en una misma instantánea y quedan fijados en el hecho
`procedure` (P6, P8), con número, tipo, objeto y fecha.

El rol se comprueba fuera de toda transacción, como en la 001, para que el hecho
`rejected` no se pierda si algo después se deshace. Cada función nombra su operación en
el rechazo (`REGISTER_OPERATION`, `LIST_OPERATION`).

Los mensajes de los errores son para la persona que registra: en español llano.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.queries.services import applicable_regimes
from evaluon.tenders.models import MatrixVersion, Procedure

REGISTER_OPERATION = "evaluon.tenders.services.procedures.register_procedure"
LIST_OPERATION = "evaluon.tenders.services.procedures.list_procedures"

FUTURE_DATE_MESSAGE = "La fecha de autorización no puede ser posterior a hoy"
DUPLICATE_NUMBER_MESSAGE = "Ya hay un procedimiento registrado con ese número."

# Nombre de cada dato en los mensajes.
_FIELD_NAMES = {
    "number": "el número",
    "procedure_type": "el tipo",
    "subject": "el objeto",
}


class ProcedureRefused(ValueError):
    """No se registró el procedimiento. `field` es el dato que lo impidió."""

    field = None

    def __init__(self, message, field=None):
        super().__init__(message)
        if field is not None:
            self.field = field


class FutureDate(ProcedureRefused):
    field = "authorization_date"


class DuplicateNumber(ProcedureRefused):
    field = "number"


@dataclass(frozen=True)
class Registration:
    """Lo que devuelve `register_procedure`: el procedimiento, el régimen mostrado, la
    versión de la normativa y el hecho `procedure`."""

    procedure: Procedure
    regime: list
    corpus_version: int | None
    event: object


@dataclass(frozen=True)
class ProcedureRow:
    """Un procedimiento de la lista con su régimen y su última versión de la matriz
    (`None` si todavía no tiene)."""

    procedure: Procedure
    regime: list
    matrix: MatrixVersion | None


def today():
    """Fecha del día en hora de Buenos Aires (`TIME_ZONE`)."""
    return timezone.localdate()


def regime_for(authorization_date):
    """Régimen aplicable a la fecha, como lo devuelve `applicable_regimes` de la 001:
    una entrada `{"norm", "name"}` por norma."""
    return applicable_regimes(authorization_date)


@contextmanager
def _snapshot():
    """Transacción `REPEATABLE READ`: el régimen y la versión de la normativa se leen
    en el mismo momento. Si ya hay una transacción abierta (por ejemplo, la de una
    prueba), se usa un punto de guardado dentro de ella."""
    if connection.in_atomic_block:
        with transaction.atomic():
            yield
        return
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        yield


def _clean_text(field, value):
    value = (value or "").strip()
    if not value:
        raise ProcedureRefused(f"Escriba {_FIELD_NAMES[field]} del procedimiento.", field)
    max_length = Procedure._meta.get_field(field).max_length
    if max_length is not None and len(value) > max_length:
        raise ProcedureRefused(
            f"{_FIELD_NAMES[field].capitalize()} del procedimiento no puede tener más "
            f"de {max_length} caracteres.",
            field,
        )
    return value


def register_procedure(user, *, number, procedure_type, subject, authorization_date,
                       channel=Channel.SCREEN):
    """Registra un procedimiento y deja el hecho `procedure`. Ver el módulo.

    Lanza `RoleRejected` sin rol de la Comisión (con su hecho `rejected`),
    `FutureDate` con una fecha posterior al día, `DuplicateNumber` con un número ya
    registrado y `ProcedureRefused` con un dato vacío o demasiado largo."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=REGISTER_OPERATION, channel=channel)
    number = _clean_text("number", number)
    procedure_type = _clean_text("procedure_type", procedure_type)
    subject = _clean_text("subject", subject)
    if authorization_date is None:
        raise ProcedureRefused("Escriba la fecha de autorización del procedimiento.",
                               "authorization_date")
    if authorization_date > today():
        raise FutureDate(FUTURE_DATE_MESSAGE)
    if Procedure.objects.filter(number=number).exists():
        raise DuplicateNumber(DUPLICATE_NUMBER_MESSAGE)

    try:
        with _snapshot():
            corpus_version = audit.current_corpus_version()
            regime = regime_for(authorization_date)
            procedure = Procedure.objects.create(
                number=number,
                procedure_type=procedure_type,
                subject=subject,
                authorization_date=authorization_date,
                created_by=user,
            )
            event = audit.record(
                EventType.PROCEDURE,
                outcome=Outcome.OK,
                channel=channel,
                user=user,
                corpus_version=corpus_version,
                detail={
                    "procedure": procedure.pk,
                    "number": number,
                    "procedure_type": procedure_type,
                    "subject": subject,
                    "authorization_date": authorization_date.isoformat(),
                    "regime": regime,
                    "corpus_version": corpus_version,
                },
            )
    except IntegrityError:
        # Otro registro con el mismo número se confirmó entre el control y el alta.
        if Procedure.objects.filter(number=number).exists():
            raise DuplicateNumber(DUPLICATE_NUMBER_MESSAGE) from None
        raise
    return Registration(procedure=procedure, regime=regime,
                        corpus_version=corpus_version, event=event)


def list_procedures(user, *, channel=Channel.SCREEN):
    """Los procedimientos, el más reciente primero, con su régimen y su última versión
    de la matriz. Lanza `RoleRejected` sin rol de la Comisión."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=LIST_OPERATION, channel=channel)
    rows = []
    for procedure in Procedure.objects.order_by("-created_at", "-id"):
        matrix = procedure.matrix_versions.order_by("-number").first()
        rows.append(ProcedureRow(procedure=procedure,
                                 regime=regime_for(procedure.authorization_date),
                                 matrix=matrix))
    return rows
