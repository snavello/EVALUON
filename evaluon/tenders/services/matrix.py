"""Pedir una propuesta de la matriz de cumplimiento (REQ-024, REQ-030; plan 003,
"Propuesta de la matriz", "Roles" y "Registro de auditoría"; T-073).

- `request_matrix`: pide la propuesta de la matriz de un procedimiento. Hay un solo proceso
  (`MATRIX_PROCESS`, el más completo; REQ-030 enmendado): no se elige nivel. Lo hacen el
  operador y el evaluador. Encola el pedido `propose_matrix`, deja la propuesta
  (`tenders_matrix_run`) con su proceso, su canal y los documentos base con su lectura, y el
  hecho `matrix_request`, todo en una transacción. Se rechaza, sin encolar nada y con el
  hecho `matrix_request` en resultado `rejected` y su motivo:
  - sin ningún documento base (pliego, anexo o especificaciones) (`no_documents`);
  - si algún documento base está en lectura, o en espera de ella (`reading_in_progress`);
  - si la lectura de algún documento base falló (`reading_failed`): no se propone sin ese
    documento;
  - si el procedimiento ya tiene un borrador abierto (`draft_open`);
  - si ya hay un pedido de propuesta en espera o en curso (`request_in_progress`).
- `run_propose_matrix`: el manejador del pedido `propose_matrix` (lo registra
  `jobs.HANDLERS`). Corre `proposal.run.propose` con la propuesta del pedido. No marca el
  estado del pedido: eso es de `jobs.run`.

Los documentos que no son base (circulares y respuestas a consultas) no bloquean el pedido
y todavía no se usan (T-083).

El rol se comprueba fuera de toda transacción, como en la 001, para que el hecho
`rejected` no se pierda si algo después se deshace. Los mensajes de los rechazos son para
la persona que pide: en español llano.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    DocumentKind,
    Job,
    JobKind,
    JobStatus,
    MatrixRun,
    MatrixVersion,
    Procedure,
    RunChannel,
    VersionStatus,
)
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.services import document_history
from evaluon.tenders.services import documents as documents_service

REQUEST_OPERATION = "evaluon.tenders.services.matrix.request_matrix"

# Documentos que son el pliego: se leen para proponer la matriz.
BASE_KINDS = (DocumentKind.PLIEGO, DocumentKind.ANEXO, DocumentKind.ESPECIFICACIONES)


class MatrixRefused(ValueError):
    """No se pidió la propuesta. `reason` es el motivo que queda en el registro y
    `field`, el dato que lo impidió, si hay uno."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass(frozen=True)
class Requested:
    """Lo que devuelve `request_matrix`: el pedido, la propuesta y el hecho
    `matrix_request`."""

    job: Job
    run: MatrixRun
    event: object


def base_documents(procedure):
    """Los documentos base vigentes del procedimiento, en el orden de carga: los retirados o
    reemplazados no entran a la propuesta (REQ-099, ADR-0048)."""
    return document_history.current_documents(procedure).filter(kind__in=BASE_KINDS)


def _documents_snapshot(procedure):
    """Los documentos base con su lectura vigente. Lanza `MatrixRefused` si no hay
    ninguno o si alguno no está leído."""
    rows = [documents_service._document_row(document)
            for document in base_documents(procedure)]
    if not rows:
        raise MatrixRefused(
            "El procedimiento no tiene ningún documento del pliego cargado: cargue el "
            "pliego antes de pedir la matriz.",
            "no_documents",
        )
    waiting = [row.document.title for row in rows
               if row.state in (documents_service.STATE_QUEUED,
                                documents_service.STATE_RUNNING)]
    if waiting:
        raise MatrixRefused(
            "Hay documentos del pliego que todavía se están leyendo: "
            + ", ".join(f"«{title}»" for title in waiting)
            + ". Espere a que terminen para pedir la matriz.",
            "reading_in_progress",
        )
    failed = [row.document.title for row in rows
              if row.state == documents_service.STATE_FAILED or row.reading is None]
    if failed:
        raise MatrixRefused(
            "No se pudo leer: " + ", ".join(f"«{title}»" for title in failed)
            + ". La matriz no se propone sin ese documento.",
            "reading_failed",
        )
    return [
        {
            "document": row.document.pk,
            "title": row.document.title,
            "kind": row.document.kind,
            "file_sha256": row.document.file_sha256,
            "reading": row.reading.pk,
            "sequence": row.reading.sequence,
            "canonical_sha256": row.reading.canonical_sha256,
        }
        for row in rows
    ]


def _check_open_work(procedure):
    if procedure.matrix_versions.filter(status=VersionStatus.DRAFT).exists():
        raise MatrixRefused(
            "El procedimiento ya tiene un borrador de la matriz abierto: revíselo o "
            "descártelo antes de pedir otra propuesta.",
            "draft_open",
        )
    if procedure.jobs.filter(
        kind=JobKind.PROPOSE_MATRIX, status__in=(JobStatus.QUEUED, JobStatus.RUNNING)
    ).exists():
        raise MatrixRefused(
            "Ya hay una propuesta de la matriz en espera o en curso para este "
            "procedimiento.",
            "request_in_progress",
        )


def request_matrix(user, procedure, *, run_channel=RunChannel.SCREEN,
                   channel=Channel.SCREEN):
    """Pide la propuesta de la matriz de `procedure` y devuelve `Requested`. Ver el
    módulo.

    Lanza `RoleRejected` sin rol de la Comisión (con su hecho `rejected`) y
    `MatrixRefused` en los casos del módulo (con su hecho `matrix_request` rechazado)."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REQUEST_OPERATION,
                            channel=channel)
    detail = {"procedure": procedure.pk, "process": settings.MATRIX_PROCESS}
    try:
        with transaction.atomic():
            # El procedimiento bloqueado ordena dos pedidos a la vez.
            Procedure.objects.select_for_update().get(pk=procedure.pk)
            documents = _documents_snapshot(procedure)
            _check_open_work(procedure)
            job = jobs.enqueue(JobKind.PROPOSE_MATRIX, procedure=procedure,
                               requested_by=user)
            run = MatrixRun.objects.create(
                procedure=procedure,
                job=job,
                process=settings.MATRIX_PROCESS,
                channel=run_channel,
                documents=documents,
                authorization_date=procedure.authorization_date,
            )
            event = audit.record(
                EventType.MATRIX_REQUEST, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail,
                        "run": run.pk, "job": job.pk, "documents": documents},
            )
    except MatrixRefused as error:
        audit.record(
            EventType.MATRIX_REQUEST, outcome=Outcome.REJECTED, channel=channel,
            user=user,
            detail={**detail, "reason": error.reason, "message": str(error)},
        )
        raise
    return Requested(job=job, run=run, event=event)


def run_propose_matrix(job):
    """Manejador del pedido `propose_matrix`: propone la matriz de la propuesta del
    pedido. Ver `proposal.run.propose`."""
    run = job.matrix_runs.order_by("-id").first()
    if run is None:
        raise RuntimeError("El pedido no tiene una propuesta de matriz registrada.")
    return proposal.propose(run, user=job.requested_by, channel=Channel.COMMAND)
