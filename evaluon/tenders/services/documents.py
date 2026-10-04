"""Cargar los documentos del pliego, leerlos en segundo plano y entregar el original
(REQ-023, REQ-028, REQ-031; plan 003, "Carga y lectura", "Procedimiento y documentos",
"Roles" y "Registro de auditoría"; T-072).

- `load_document`: carga un archivo del pliego final de un procedimiento con su tipo,
  su título y, si es una circular o una respuesta a consulta, su fecha (obligatoria,
  REQ-031; optativa en los demás). Lo hacen el operador y el evaluador. Guarda el
  original byte por byte con su huella, como la 001 (REQ-023), encola su lectura y deja
  el hecho `tender_load`, todo en una transacción: el `worker` nunca ve un pedido sin su
  documento. El formato se reconoce por el contenido, con la misma función de la 001
  (`detect_format`): un archivo que no es PDF ni página web guardada se rechaza al
  cargarlo. El mismo archivo (misma huella) dos veces en un procedimiento se rechaza
  con aviso. Toda carga rechazada (dato que falta, formato, archivo repetido) deja el
  hecho `tender_load` con resultado `rejected`, su motivo y lo que se intentó cargar, sin
  nada incorporado.
- `refuse_invalid_date`: registra igual el rechazo de una fecha que la pantalla no pudo
  convertir (motivo `invalid_date`), para que ningún rechazo de carga quede sin hecho.
- `run_read_document`: el manejador del pedido `read_document` (lo registra
  `jobs.HANDLERS`). Comprueba la huella del original guardado, lo lee con la lectura de
  la 001 (`read_document`: PDF con texto o escaneado, página por página, o página web),
  busca las zonas de tabla (`tables.table_zones`) y lo parte en tramos
  (`segmenting.split_tender`). Guarda la lectura (número siguiente del documento), sus
  tramos y el informe, y deja el hecho `tender_read`, en una sola transacción: una
  lectura cortada no queda a medias. No modifica una lectura ni sus tramos ya guardados.
  Si algo falla, deja el hecho `tender_read` con resultado `failed` y el motivo, y
  vuelve a lanzar el error para que la cola deje el pedido `failed`. No marca el estado
  del pedido: eso es de `jobs.run`.
- `procedure_page`: el procedimiento con su régimen y sus documentos, cada uno con el
  estado de su lectura y, si ya se leyó, sus tramos pendientes de revisión (REQ-028).
- `original_file`: el original guardado, para la vista que lo entrega (REQ-023).

El rol se comprueba fuera de toda transacción, como en la 001, para que el hecho
`rejected` no se pierda si algo después se deshace. La lectura corre en CPU y sin
conexión (P4).

El hecho `tender_read` lo deja el `worker`: lleva como usuario a quien pidió la lectura
(`job.requested_by`), el canal `command` (el `worker` corre `procesar_pedidos`) y el
número del pedido.

Los mensajes de los errores son para la persona que carga: en español llano.
"""

import hashlib
from dataclasses import asdict, dataclass, field

from django.db import IntegrityError, transaction
from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.reading import detect_format, read_document
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    DATED_DOCUMENT_KINDS,
    Document,
    DocumentFile,
    DocumentKind,
    Job,
    JobKind,
    JobStatus,
    Procedure,
    Reading,
    Segment,
)
from evaluon.tenders.segmenting import RULES_VERSION, split_tender
from evaluon.tenders.services.procedures import regime_for
from evaluon.tenders.tables import table_zones

LOAD_OPERATION = "evaluon.tenders.services.documents.load_document"
PAGE_OPERATION = "evaluon.tenders.services.documents.procedure_page"
ORIGINAL_OPERATION = "evaluon.tenders.services.documents.original_file"

# Restricción de la base que hace única la huella dentro del procedimiento.
_UNIQUE_FILE_CONSTRAINT = "tenders_document_sha256_unique_in_procedure"

INVALID_DATE_MESSAGE = "La fecha del documento no es una fecha válida: no se cargó."

# Estado de la lectura de un documento, para la pantalla.
STATE_QUEUED = "en_espera"
STATE_RUNNING = "leyendo"
STATE_READ = "leido"
STATE_FAILED = "fallido"


class DocumentRefused(ValueError):
    """No se cargó el documento. `field` es el dato que lo impidió y `reason`, el
    motivo que queda en el registro."""

    reason = "invalid_data"

    def __init__(self, message, field=None, reason=None):
        super().__init__(message)
        self.field = field
        if reason is not None:
            self.reason = reason


class DuplicateFile(DocumentRefused):
    """El mismo archivo ya está cargado en el procedimiento."""

    reason = "duplicate_file"

    def __init__(self, message, loaded_document):
        super().__init__(message, field="file")
        self.loaded_document = loaded_document


class OriginalChanged(RuntimeError):
    """El original guardado ya no tiene la huella con que se cargó."""


@dataclass(frozen=True)
class Loaded:
    """Lo que devuelve `load_document`: el documento, el pedido de lectura y el hecho
    `tender_load`."""

    document: Document
    job: Job
    event: object


@dataclass
class DocumentRow:
    """Un documento de la página del procedimiento: su estado de lectura (`STATE_*`), el
    último pedido de lectura, la última lectura y sus tramos pendientes de revisión."""

    document: Document
    state: str
    job: Job | None
    reading: Reading | None
    pending: list = field(default_factory=list)


@dataclass(frozen=True)
class ProcedurePage:
    """El procedimiento, su régimen y sus documentos en el orden de carga."""

    procedure: Procedure
    regime: list
    documents: list


# --- Carga --------------------------------------------------------------------------------


def _file_detail(file_name, file_format, data, sha256):
    return {"name": file_name, "format": file_format, "size": len(data), "sha256": sha256}


def _check(kind, title, issued_on, file_name, data):
    """Comprueba los datos y devuelve el título sin los espacios de los extremos y el
    formato del archivo."""
    if not data or not (file_name or "").strip():
        raise DocumentRefused("Elija el archivo del documento.", "file", "missing_data")
    if kind not in DocumentKind.values:
        raise DocumentRefused("Elija el tipo de documento.", "kind", "missing_data")
    title = (title or "").strip()
    if not title:
        raise DocumentRefused("Escriba el título del documento.", "title", "missing_data")
    if kind in DATED_DOCUMENT_KINDS and issued_on is None:
        raise DocumentRefused(
            f"Escriba la fecha del documento: una {DocumentKind(kind).label.lower()} "
            "lleva siempre su fecha.",
            "issued_on",
            "missing_date",
        )
    file_format = detect_format(data)
    if file_format is None:
        raise DocumentRefused(
            "El archivo no es un PDF ni una página web guardada (.html): no se cargó.",
            "file",
            "unsupported_format",
        )
    return title, file_format


def _duplicate(procedure, sha256):
    loaded = procedure.documents.filter(file_sha256=sha256).order_by("id").first()
    if loaded is None:
        return None
    return DuplicateFile(
        f"Ese archivo ya está cargado en este procedimiento, como «{loaded.title}» "
        f"({loaded.file_name}). No se cargó de nuevo.",
        loaded.pk,
    )


def _violated_constraint(error):
    cause = error.__cause__
    return getattr(getattr(cause, "diag", None), "constraint_name", None) or ""


def _record_refusal(user, channel, procedure, detail, error):
    detail = {**detail, "reason": error.reason, "message": str(error)}
    if isinstance(error, DuplicateFile):
        detail["loaded_document"] = error.loaded_document
    audit.record(EventType.TENDER_LOAD, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail=detail)


def _attempt_detail(procedure, kind, title, issued_on, file_name, data):
    """Lo que se intentó cargar, para el hecho `tender_load`. `issued_on` va como
    texto: la fecha en ISO, o tal como se escribió si no es una fecha válida."""
    return {
        "procedure": procedure.pk,
        "kind": kind,
        "title": title,
        "issued_on": issued_on,
        "file": _file_detail(file_name, None, data, hashlib.sha256(data).hexdigest()),
    }


def refuse_invalid_date(user, procedure, *, data, file_name, kind, title, issued_on_text,
                        channel=Channel.SCREEN):
    """Rechaza una carga cuya fecha no es una fecha válida (por ejemplo, "31/02/2025"):
    la pantalla no la puede convertir y no llega a `load_document`. Comprueba el rol,
    deja el hecho `tender_load` rechazado con motivo `invalid_date` y lo intentado, y
    devuelve el `DocumentRefused` para mostrarlo; no guarda nada más."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=LOAD_OPERATION,
                            channel=channel)
    data = bytes(data or b"")
    detail = _attempt_detail(procedure, kind, title, issued_on_text, file_name, data)
    refusal = DocumentRefused(INVALID_DATE_MESSAGE, "issued_on", "invalid_date")
    _record_refusal(user, channel, procedure, detail, refusal)
    return refusal


def load_document(user, procedure, *, data, file_name, kind, title, issued_on=None,
                  channel=Channel.SCREEN):
    """Carga el archivo `data` (sus bytes, con su nombre `file_name`) como documento del
    pliego de `procedure` y encola su lectura. Ver el módulo.

    Lanza `RoleRejected` sin rol de la Comisión (con su hecho `rejected`),
    `DuplicateFile` si el archivo ya está cargado en el procedimiento y
    `DocumentRefused` con un dato que falta o un formato que no se lee. En esos casos no
    se guarda nada salvo el hecho que lo registra."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=LOAD_OPERATION,
                            channel=channel)
    data = bytes(data or b"")
    sha256 = hashlib.sha256(data).hexdigest()
    detail = _attempt_detail(procedure, kind, title,
                             issued_on.isoformat() if issued_on else None, file_name, data)
    try:
        title, file_format = _check(kind, title, issued_on, file_name, data)
        detail["title"] = title
        detail["file"]["format"] = file_format
        duplicate = _duplicate(procedure, sha256)
        if duplicate is not None:
            raise duplicate
        with transaction.atomic():
            document = Document.objects.create(
                procedure=procedure,
                kind=kind,
                title=title,
                issued_on=issued_on,
                file_name=file_name,
                file_format=file_format,
                file_size=len(data),
                file_sha256=sha256,
                loaded_by=user,
            )
            DocumentFile.objects.create(document=document, content=data)
            job = jobs.enqueue(JobKind.READ_DOCUMENT, procedure=procedure,
                               requested_by=user, document=document)
            event = audit.record(
                EventType.TENDER_LOAD, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "document": document.pk, "job": job.pk},
            )
    except IntegrityError as error:
        # Otra carga del mismo archivo se confirmó entre el control y el alta.
        if _violated_constraint(error) != _UNIQUE_FILE_CONSTRAINT:
            raise
        refusal = _duplicate(procedure, sha256)
        if refusal is None:
            raise
        _record_refusal(user, channel, procedure, detail, refusal)
        raise refusal from error
    except DocumentRefused as error:
        _record_refusal(user, channel, procedure, detail, error)
        raise
    return Loaded(document=document, job=job, event=event)


# --- Lectura en segundo plano ---------------------------------------------------------------


def _segment_fields(segment):
    values = asdict(segment)
    values.pop("review_detail")
    return values


def _read_detail(job, document):
    return {"procedure": document.procedure_id, "document": document.pk, "job": job.pk,
            "file_sha256": document.file_sha256}


def run_read_document(job):
    """Lee el documento del pedido `job` y guarda su lectura, sus tramos y su informe.
    Ver el módulo. Cualquier falla deja el hecho `tender_read` fallido y se vuelve a
    lanzar."""
    document = job.document
    detail = _read_detail(job, document)
    try:
        data = bytes(DocumentFile.objects.get(document=document).content)
        if hashlib.sha256(data).hexdigest() != document.file_sha256:
            raise OriginalChanged(
                "El original guardado no coincide con la huella con que se cargó: no se "
                "leyó."
            )
        reading = read_document(data)
        zones = table_zones(data)
        split = split_tender(reading, zones)
        canonical_text = split.canonical.text
        canonical_sha256 = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
        tool_versions = {**reading.tool_versions, "rules_version": RULES_VERSION}
        report = split.report

        with transaction.atomic():
            # El documento bloqueado ordena dos lecturas del mismo documento.
            Document.objects.select_for_update().get(pk=document.pk)
            last = document.readings.aggregate(last=Max("sequence"))["last"] or 0
            saved = Reading.objects.create(
                document=document,
                sequence=last + 1,
                pages=reading.as_json(),
                tables=zones,
                canonical_text=canonical_text,
                canonical_sha256=canonical_sha256,
                items=split.items,
                tool_versions=tool_versions,
                report=report,
                job=job,
            )
            Segment.objects.bulk_create(
                Segment(reading=saved, **_segment_fields(segment))
                for segment in split.segments
            )
            audit.record(
                EventType.TENDER_READ, outcome=Outcome.OK, channel=Channel.COMMAND,
                user=job.requested_by,
                detail={
                    **detail,
                    "reading": saved.pk,
                    "sequence": saved.sequence,
                    "canonical_sha256": canonical_sha256,
                    "tool_versions": tool_versions,
                    "pages_by_status": report["pages_by_status"],
                    "segments_by_type": report["segments_by_type"],
                    "segments": report["segments"],
                    "items": split.items,
                    "coverage": report["coverage"],
                    "pending": report["pending"],
                    "tables": len(zones),
                },
            )
    except Exception as error:
        audit.record(
            EventType.TENDER_READ, outcome=Outcome.FAILED, channel=Channel.COMMAND,
            user=job.requested_by,
            detail={**detail, "error": f"{type(error).__name__}: {error}"},
        )
        raise
    return saved


# --- Página del procedimiento y original ---------------------------------------------------


def _state(job, reading):
    if job is None or job.status == JobStatus.DONE:
        return STATE_READ if reading is not None else STATE_QUEUED
    return {
        JobStatus.QUEUED: STATE_QUEUED,
        JobStatus.RUNNING: STATE_RUNNING,
        JobStatus.FAILED: STATE_FAILED,
    }[job.status]


def _document_row(document):
    job = document.jobs.filter(kind=JobKind.READ_DOCUMENT).order_by("-requested_at",
                                                                     "-id").first()
    reading = document.readings.order_by("-sequence").first()
    pending = []
    if reading is not None:
        pending = list(reading.segments.exclude(review_reason="").order_by("order"))
    return DocumentRow(document=document, state=_state(job, reading), job=job,
                       reading=reading, pending=pending)


def procedure_page(user, procedure_id, *, channel=Channel.SCREEN):
    """El procedimiento con su régimen y sus documentos. Lanza `RoleRejected` sin rol de
    la Comisión y `Procedure.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    procedure = Procedure.objects.get(pk=procedure_id)
    rows = [_document_row(document)
            for document in procedure.documents.order_by("loaded_at", "id")]
    return ProcedurePage(procedure=procedure,
                         regime=regime_for(procedure.authorization_date),
                         documents=rows)


def original_file(user, document_id, *, channel=Channel.SCREEN):
    """El original guardado de un documento (`DocumentFile`, con su documento). Lanza
    `RoleRejected` sin rol de la Comisión y `DocumentFile.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=ORIGINAL_OPERATION,
                            channel=channel)
    return DocumentFile.objects.select_related("document").get(document_id=document_id)
