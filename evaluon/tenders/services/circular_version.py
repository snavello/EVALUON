"""Circulares y aclaraciones del procedimiento y la versión nueva de la matriz que abre una
circular modificatoria (REQ-085, REQ-097; plan 014, T-205; principios P3 y P6).

**Relevamiento (T-205).** Cómo aplica el sistema una circular, leído de `tenders/proposal/`:

- No hay una pasada que aplique una circular sobre una versión ya validada. La única puerta
  es el pedido de propuesta de la matriz (`matrix.request_matrix` → `proposal.run.propose`):
  `circulars.load` toma TODOS los documentos fechados del procedimiento (modificatorias,
  aclaratorias y respuestas a consultas) que tengan lectura, los ordena por fecha y, a igual
  fecha, por orden de carga, y `circular_units` / `circular_changes` / `Processor` resuelven
  cada tramo (por clave, por extracción del modelo o por candidatas) y devuelven las fuentes
  (`RequirementSource`, con efecto modifica, aclara o suprime) y los requisitos nuevos (origen
  `circular`). `run._save` crea una versión borrador con el número siguiente.
- Un documento fechado sin lectura no falla: queda en `counts["circulars"]["not_read"]` y la
  versión se arma sin él. Por eso el pedido solo se hace con la circular ya leída.
- Los documentos usados quedan en `run.counts["circulars"]["documents"]` (con su `document`).
  De ahí se sabe en qué versión entró cada circular.
- `validation.open_new_version` copia una versión validada con las decisiones de la Comisión,
  pero no aplica circulares; la propuesta nueva no copia decisiones (la Comisión valida de
  nuevo, como pide la spec). Un borrador abierto o un pedido en curso impiden el pedido
  (`draft_open`, `request_in_progress`).
- Lo cambiado se marca con las fuentes (`RequirementSource`): `matrix_page` arma de ahí el
  texto anterior, el vigente y la circular; el origen `circular` marca los requisitos
  agregados. La propuesta no llena `Requirement.previous`.

Por eso, acá la versión nueva se obtiene con un pedido de propuesta que incluye la circular
(`open_for_circular`). Una aclaratoria o una respuesta a consulta no abre versión: solo la
modificatoria lo hace; su efecto de aclaración, si lo hay, queda como nota junto al requisito
cuando se arma una versión.

Este módulo no decide nada: la versión nueva queda en borrador y la valida el evaluador con la
acción de siempre. El pedido deja el hecho `matrix_request` (lo escribe `request_matrix`) y un
hecho `matrix_version` con la circular que lo motivó.
"""

from dataclasses import dataclass, field

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    DATED_DOCUMENT_KINDS,
    DocumentKind,
    JobKind,
    JobStatus,
    Requirement,
    RequirementOrigin,
    RequirementSource,
    SourceEffect,
    VersionStatus,
)
from evaluon.tenders.services import document_history
from evaluon.tenders.services import documents as documents_service
from evaluon.tenders.services import matrix as matrix_service

OPEN_REASON = "circular"
OPEN_OPERATION = "evaluon.tenders.services.circular_version.open_for_circular"

# Estados de una circular modificatoria frente a la matriz.
SIN_VERSION = "sin_version"      # leída o por leer, todavía no entró a ninguna versión
EN_BORRADOR = "borrador"         # entró a un borrador: falta validarlo
VALIDADA = "validada"            # entró a una versión validada
DESCARTADA = "descartada"        # la única versión donde entró se descartó
NO_APLICA = "no_aplica"          # aclaratoria o respuesta: no abre versión


class CircularRefused(ValueError):
    """No se pidió la versión nueva. `reason` queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


@dataclass
class Effect:
    """Lo que una circular hizo en una versión de la matriz, por número de requisito."""

    changed: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    clarified: list = field(default_factory=list)
    added: list = field(default_factory=list)

    @property
    def empty(self):
        return not (self.changed or self.removed or self.clarified or self.added)


@dataclass
class CircularState:
    document: object
    state: str
    version: object = None
    effect: Effect = field(default_factory=Effect)
    reading: str = ""      # estado de la lectura (`documents.STATE_*`)
    building: bool = False  # hay un pedido de propuesta en espera o en curso
    failed: str = ""       # el último pedido de propuesta falló: el motivo


def circulars_of(procedure):
    """Las circulares, aclaraciones y respuestas vigentes, por fecha y orden de carga."""
    return list(document_history.current_documents(procedure)
                .filter(kind__in=[k.value for k in DATED_DOCUMENT_KINDS])
                .select_related("loaded_by").order_by("issued_on", "loaded_at", "pk"))


def _used_documents(version):
    """Los números de documento que usó la propuesta de la que sale la versión."""
    seen = set()
    while version is not None and version.pk not in seen:
        seen.add(version.pk)
        if version.run_id is not None:
            counts = version.run.counts if isinstance(version.run.counts, dict) else {}
            used = (counts.get("circulars") or {}).get("documents") or []
            return {entry.get("document") for entry in used if isinstance(entry, dict)}
        version = version.based_on
    return set()


def _versions(procedure):
    return list(procedure.matrix_versions.select_related("run", "based_on")
                .order_by("number"))


def _reading_state(document):
    job = (document.jobs.filter(kind=JobKind.READ_DOCUMENT)
           .order_by("-requested_at", "-id").first())
    reading = document.readings.order_by("-sequence").first()
    return documents_service._state(job, reading)


def effect_in(document, version):
    """Qué hizo `document` en `version`: requisitos cambiados, sin efecto, aclarados y
    agregados."""
    effect = Effect()
    sources = (RequirementSource.objects
               .filter(requirement__version=version, segment__reading__document=document)
               .select_related("requirement").order_by("requirement__number", "pk"))
    for source in sources:
        target = {SourceEffect.MODIFICA: effect.changed,
                  SourceEffect.SUPRIME: effect.removed,
                  SourceEffect.ACLARA: effect.clarified}.get(source.effect)
        if target is not None and source.requirement.number not in target:
            target.append(source.requirement.number)
    added = (Requirement.objects
             .filter(version=version, origin=RequirementOrigin.CIRCULAR,
                     quotes__segment__reading__document=document)
             .order_by("number").distinct())
    effect.added = [requirement.number for requirement in added]
    return effect


def states(procedure):
    """El estado de cada circular, aclaración y respuesta del procedimiento."""
    versions = _versions(procedure)
    used = [(version, _used_documents(version)) for version in versions]
    propose = procedure.jobs.filter(kind=JobKind.PROPOSE_MATRIX)
    building = propose.filter(status__in=(JobStatus.QUEUED, JobStatus.RUNNING)).exists()
    last = propose.order_by("-requested_at", "-id").first()
    rows = []
    for document in circulars_of(procedure):
        row = CircularState(document=document, state=NO_APLICA,
                            reading=_reading_state(document))
        if document.kind == DocumentKind.CIRCULAR_MODIFICATORIA:
            row.state = SIN_VERSION
            containing = [version for version, docs in used if document.pk in docs]
            validated = [v for v in containing if v.status == VersionStatus.VALIDATED]
            drafts = [v for v in containing if v.status == VersionStatus.DRAFT]
            if validated:
                row.state, row.version = VALIDADA, validated[0]
            elif drafts:
                row.state, row.version = EN_BORRADOR, drafts[0]
            elif containing:
                row.state, row.version = DESCARTADA, containing[0]
            if row.version is not None:
                row.effect = effect_in(document, row.version)
            else:
                row.building = building
                if (not building and last is not None and last.status == JobStatus.FAILED
                        and last.requested_at >= document.loaded_at):
                    row.failed = last.error or "el pedido falló"
        rows.append(row)
    return rows


def pending(procedure):
    """Las modificatorias sin una matriz nueva validada. Si el procedimiento todavía no tiene
    ninguna versión de la matriz, no hay nada que rehacer: la primera propuesta las incluye."""
    if not procedure.matrix_versions.exclude(status=VersionStatus.DISCARDED).exists():
        return []
    return [row for row in states(procedure)
            if row.state in (SIN_VERSION, EN_BORRADOR, DESCARTADA)]


def open_for_circular(user, procedure, document, *, channel=Channel.SCREEN):
    """Pide la versión nueva de la matriz que incorpora la circular `document` (y las demás
    fechadas ya leídas). Devuelve `matrix.Requested`; la propuesta la arma el trabajador en
    segundo plano y queda en borrador. Lanza `CircularRefused` o los rechazos de
    `matrix.request_matrix` (rol incluido)."""
    # El rol se comprueba antes de todo, fuera de toda transacción (deja el hecho `rejected`).
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPEN_OPERATION,
                            channel=channel)
    detail = {"procedure": procedure.pk, "document": document.pk, "action": OPEN_REASON}

    def refuse(message, reason):
        audit.record(EventType.MATRIX_VERSION, outcome=Outcome.REJECTED, channel=channel,
                     user=user, detail={**detail, "reason": reason, "message": message})
        raise CircularRefused(message, reason)

    if document.procedure_id != procedure.pk:
        refuse("Ese documento no es de este procedimiento.", "document_not_found")
    if document.kind != DocumentKind.CIRCULAR_MODIFICATORIA:
        refuse("Solo una circular modificatoria abre una versión nueva de la matriz: una "
               "aclaratoria o una respuesta a una consulta no la cambia.", "not_modifying")
    row = next((r for r in states(procedure) if r.document.pk == document.pk), None)
    if row is None:
        refuse("La circular no está vigente en el expediente (se retiró o se reemplazó).",
               "not_current")
    if row.reading != documents_service.STATE_READ:
        refuse("La circular todavía no se terminó de leer o no se pudo leer: la versión "
               "nueva se abre cuando esté leída.", "not_read")
    if row.state in (EN_BORRADOR, VALIDADA):
        refuse(f"La circular ya está en la versión {row.version.number} de la matriz.",
               "already_applied")
    if row.building:
        refuse("Ya hay una propuesta de la matriz en espera o en curso: espere a que "
               "termine.", "request_in_progress")
    versions = _versions(procedure)
    if not any(v.status == VersionStatus.VALIDATED for v in versions):
        refuse("La matriz todavía no tiene una versión validada: cuando se proponga la "
               "matriz ya incluirá esta circular.", "no_validated_version")
    try:
        requested = matrix_service.request_matrix(user, procedure, channel=channel)
    except matrix_service.MatrixRefused as error:
        raise CircularRefused(str(error), error.reason) from error
    audit.record(EventType.MATRIX_VERSION, outcome=Outcome.OK, channel=channel, user=user,
                 detail={**detail, "run": requested.run.pk, "job": requested.job.pk,
                         "based_on": next(v.pk for v in reversed(versions)
                                          if v.status == VersionStatus.VALIDATED)})
    return requested
