"""Cola de pedidos en segundo plano (plan 003, "Componentes"; ADR-0018, "Cómo funciona").

Un pedido (leer un documento, proponer una matriz) es una fila de `tenders_job`. El
servicio `worker` corre `procesar_pedidos`, que los atiende de a uno:

- `enqueue`: deja un pedido `queued`.
- `claim`: toma el pedido en espera más antiguo con `SELECT … FOR UPDATE SKIP LOCKED` y
  lo pasa a `running` en la misma transacción: dos tomas a la vez nunca toman el mismo.
- `run`: ejecuta el manejador de su tipo. Si vuelve sin error, `done`; si falla, `failed`
  con el motivo (no se reintenta solo: la persona lo vuelve a pedir). Lo que el manejador
  registró antes de fallar queda. Si el proceso recibe la orden de detenerse a mitad del
  pedido, el pedido queda `failed` "interrumpido" antes de salir.
- `fail_interrupted`: al arrancar, pasa a `failed` "interrumpido" los pedidos que quedaron
  `running` porque el `worker` se cayó. Nunca queda una matriz a medias marcada como lista.
- `unseen_finished` y `mark_seen`: el aviso de fin, con los pedidos de la persona que
  terminaron y todavía no vio.

Manejadores (`HANDLERS`): un tipo de pedido, una función que recibe el `Job`. Se anotan
por su ruta (`"evaluon.tenders.services.documents.run_read_document"`) para que el
servicio que encola un pedido pueda registrar su manejador aquí sin importarse en
círculo. Los registran T-072 (`read_document`) y T-073 (`propose_matrix`). Cada
manejador deja su propio registro de auditoría (`tender_read`, `matrix_proposal`, P6).
"""

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from evaluon.ai import AIServiceError
from evaluon.tenders.models import Job, JobKind, JobStatus

logger = logging.getLogger(__name__)

# Motivo de un pedido cortado a mitad de camino (ADR-0018).
INTERRUPTED = "interrumpido"

# Tipo de pedido → manejador (función o su ruta). Ver el docstring del módulo.
HANDLERS = {
    JobKind.READ_DOCUMENT: "evaluon.tenders.services.documents.run_read_document",
    JobKind.PROPOSE_MATRIX: "evaluon.tenders.services.matrix.run_propose_matrix",
}

FINISHED = (JobStatus.DONE, JobStatus.FAILED)


def enqueue(kind, *, procedure, requested_by, document=None):
    """Deja un pedido en espera y lo devuelve."""
    return Job.objects.create(
        kind=kind, procedure=procedure, document=document, requested_by=requested_by
    )


def claim():
    """Toma el pedido en espera más antiguo, lo pasa a `running` y lo devuelve; `None`
    si no hay. Un pedido que otra toma tiene bloqueado se saltea, sin esperar."""
    with transaction.atomic():
        job = (
            Job.objects.select_for_update(skip_locked=True)
            .filter(status=JobStatus.QUEUED)
            .order_by("requested_at", "id")
            .first()
        )
        if job is None:
            return None
        job.status = JobStatus.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
    return job


def finish(job):
    """Marca el pedido como terminado."""
    job.status = JobStatus.DONE
    job.finished_at = timezone.now()
    job.error = ""
    job.save(update_fields=["status", "finished_at", "error"])


def fail(job, reason):
    """Marca el pedido como fallido con su motivo."""
    job.status = JobStatus.FAILED
    job.finished_at = timezone.now()
    job.error = reason
    job.save(update_fields=["status", "finished_at", "error"])


def fail_interrupted():
    """Pasa a `failed` "interrumpido" los pedidos que quedaron `running`. Devuelve
    cuántos."""
    return Job.objects.filter(status=JobStatus.RUNNING).update(
        status=JobStatus.FAILED, error=INTERRUPTED, finished_at=timezone.now()
    )


def _handler(kind):
    handler = HANDLERS.get(kind)
    if isinstance(handler, str):
        handler = import_string(handler)
    return handler


def _reason(error):
    """Motivo que se guarda: el propio del cliente de IA si es una falla técnica del
    motor (`timeout: …`); si no, el tipo de error y su mensaje."""
    if isinstance(error, AIServiceError):
        return f"{error.reason}: {error}"
    return f"{type(error).__name__}: {error}"


def run(job):
    """Ejecuta un pedido ya tomado con el manejador de su tipo y deja su estado final."""
    handler = _handler(job.kind)
    if handler is None:
        fail(job, f"sin manejador para el tipo de pedido {job.kind}")
        return
    try:
        handler(job)
    except Exception as error:  # noqa: BLE001 - toda falla deja el pedido `failed`
        logger.exception("Pedido %s fallido", job.pk)
        fail(job, _reason(error))
    except BaseException:
        # Orden de detenerse (señal, Ctrl-C) a mitad del pedido: se cierra y se sale.
        fail(job, INTERRUPTED)
        raise
    else:
        finish(job)


def run_next():
    """Toma y ejecuta el pedido siguiente. Devuelve el pedido, o `None` si no había."""
    job = claim()
    if job is not None:
        run(job)
    return job


def unseen_finished(user):
    """Pedidos de `user` terminados (bien o mal) cuyo aviso todavía no vio, del más
    reciente al más antiguo."""
    return Job.objects.filter(
        requested_by=user, status__in=FINISHED, seen_at__isnull=True
    ).order_by("-finished_at", "-id")


def mark_seen(user, job_ids):
    """Marca como visto el aviso de los pedidos indicados que son de `user` y
    terminaron. Un aviso ya visto conserva su primera fecha. Devuelve cuántos marcó."""
    return Job.objects.filter(
        requested_by=user, status__in=FINISHED, seen_at__isnull=True, pk__in=job_ids
    ).update(seen_at=timezone.now())
