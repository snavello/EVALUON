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
- Dos consumidores (ADR-0031): `worker` atiende todo menos los pedidos del Portal
  (`exclude=PORTAL_JOB_KINDS`) y `portal_worker` solo esos
  (`kinds=PORTAL_JOB_KINDS`). `claim`, `run_next` y `fail_interrupted` reciben `kinds` (solo
  esos) o `exclude` (todos menos esos); sin ninguno, atienden todos los tipos. Así uno no
  toma ni corta los pedidos del otro.
- `report`: el avance fino de un pedido en curso (REQ-067, ADR-0045 3.B), en la columna
  `progress`: `{step, done, total, scope, recent}`, con `recent` la lista corta de los últimos
  pasos. Se escribe aparte, fuera de la transacción del manejador, y nunca hace fallar al pedido.
- `unseen_finished` y `mark_seen`: el aviso de fin, con los pedidos de la persona que
  terminaron y todavía no vio.

Manejadores (`HANDLERS`): un tipo de pedido, una función que recibe el `Job`. Se anotan
por su ruta (`"evaluon.tenders.services.documents.run_read_document"`) para que el
servicio que encola un pedido pueda registrar su manejador aquí sin importarse en
círculo. Los registran T-072 (`read_document`), T-073 (`propose_matrix`) y T-130
(`read_offer_document`, `build_sheet`). Cada manejador deja su propio registro de
auditoría (`tender_read`, `matrix_proposal`, `offer_read`, `sheet_build`, P6).
"""

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from evaluon.ai import AIServiceError
from evaluon.tenders.models import PORTAL_JOB_KINDS, Job, JobKind, JobStatus

logger = logging.getLogger(__name__)

# Motivo de un pedido cortado a mitad de camino (ADR-0018).
INTERRUPTED = "interrumpido"

# Tipo de pedido → manejador (función o su ruta). Ver el docstring del módulo.
HANDLERS = {
    JobKind.READ_DOCUMENT: "evaluon.tenders.services.documents.run_read_document",
    JobKind.PROPOSE_MATRIX: "evaluon.tenders.services.matrix.run_propose_matrix",
    # Feature 008 (ADR-0026): los dos pedidos de ofertas comparten esta cola.
    JobKind.READ_OFFER_DOCUMENT: "evaluon.offers.services.offers.run_read_document",
    JobKind.BUILD_SHEET: "evaluon.offers.services.sheets.run_build_sheet",
    # Feature 012 (ADR-0031): los manejadores los crea T-141 en
    # `evaluon.portal.services.explore`; hasta entonces el pedido falla con un motivo.
    JobKind.PORTAL_EXPLORE: "evaluon.portal.services.explore.run_explore",
    JobKind.PORTAL_REVIEW: "evaluon.portal.services.explore.run_review",
    # Feature 004 (ADR-0039): el manejador lo crea T-150 en
    # `evaluon.assessment.services.evaluate`; hasta entonces el pedido falla con un motivo.
    JobKind.EVALUATE_OFFERS: "evaluon.assessment.services.evaluate.run_evaluate_offers",
}

FINISHED = (JobStatus.DONE, JobStatus.FAILED)

# Cuántos pasos recientes conserva `progress["recent"]` y cuánto texto cada uno.
RECENT_STEPS = 8
STEP_MAX_CHARS = 140


def report(job, step, done=None, total=None, scope=""):
    """Anota el avance de `job`: el paso actual `step` (lenguaje llano, sin datos personales),
    cuántos van de cuántos y el contexto `scope` (por ejemplo "Oferta 2 de 5"). El paso se suma
    a la lista corta de los últimos. Escribe con una consulta aparte y devuelve `True` si
    pudo; ninguna falla al escribir sale de aquí (el avance es descartable)."""
    try:
        step = str(step)[:STEP_MAX_CHARS]
        current = job.progress if isinstance(job.progress, dict) else {}
        recent = list(current.get("recent") or [])
        if not recent or recent[-1].get("text") != step or recent[-1].get("scope") != scope:
            recent.append({"at": timezone.now().isoformat(timespec="seconds"),
                           "text": step, "scope": str(scope)[:STEP_MAX_CHARS]})
        data = {"step": step, "done": done, "total": total, "scope": str(scope)[:STEP_MAX_CHARS],
                "recent": recent[-RECENT_STEPS:]}
        with transaction.atomic():
            Job.objects.filter(pk=job.pk).update(progress=data)
        job.progress = data
        return True
    except Exception:  # noqa: BLE001 - el avance nunca hace fallar al pedido
        logger.warning("No se pudo anotar el avance del pedido %s", getattr(job, "pk", None),
                       exc_info=True)
        return False


def enqueue(kind, *, procedure, requested_by, document=None, target_id=None):
    """Deja un pedido en espera y lo devuelve. `target_id` es el objeto de un pedido de
    ofertas (ADR-0026): el documento de la oferta o la oferta."""
    return Job.objects.create(
        kind=kind, procedure=procedure, document=document, requested_by=requested_by,
        target_id=target_id,
    )


def _of_kinds(queryset, kinds=None, exclude=None):
    """Limita el conjunto a los tipos `kinds` o, si no, a todos menos `exclude`."""
    if kinds is not None:
        queryset = queryset.filter(kind__in=kinds)
    if exclude is not None:
        queryset = queryset.exclude(kind__in=exclude)
    return queryset


def claim(kinds=None, exclude=None):
    """Toma el pedido en espera más antiguo (solo de los tipos `kinds`, o de todos menos
    `exclude`), lo pasa a `running` y lo devuelve; `None` si no hay. Un pedido que otra
    toma tiene bloqueado se saltea, sin esperar."""
    with transaction.atomic():
        job = (
            _of_kinds(
                Job.objects.select_for_update(skip_locked=True), kinds, exclude
            )
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


def fail_interrupted(kinds=None, exclude=None):
    """Pasa a `failed` "interrumpido" los pedidos que quedaron `running` (solo de los
    tipos `kinds`, o de todos menos `exclude`). Devuelve cuántos."""
    return _of_kinds(Job.objects.filter(status=JobStatus.RUNNING), kinds, exclude).update(
        status=JobStatus.FAILED, error=INTERRUPTED, finished_at=timezone.now()
    )


def _handler(kind):
    handler = HANDLERS.get(kind)
    if isinstance(handler, str):
        path = handler
        try:
            handler = import_string(path)
        except ModuleNotFoundError as error:
            # Un manejador que todavía no existe (su módulo o un paquete de su ruta): el
            # pedido falla con un motivo, no tira al `worker`. Un módulo que falta *dentro*
            # del manejador es un defecto: sube con su causa.
            module = path.rsplit(".", 1)[0]
            if error.name and (module == error.name or module.startswith(error.name + ".")):
                return None
            raise
    return handler


def _reason(error):
    """Motivo que se guarda: el propio del cliente de IA si es una falla técnica del
    motor (`timeout: …`); si no, el tipo de error y su mensaje."""
    if isinstance(error, AIServiceError):
        return f"{error.reason}: {error}"
    return f"{type(error).__name__}: {error}"


def run(job):
    """Ejecuta un pedido ya tomado con el manejador de su tipo y deja su estado final."""
    try:
        handler = _handler(job.kind)
    except ImportError as error:
        # El módulo del manejador existe pero no se puede importar: queda la causa.
        logger.exception("Manejador roto para el pedido %s", job.pk)
        fail(job, f"manejador roto para el tipo de pedido {job.kind}: {_reason(error)}")
        return
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


def run_next(kinds=None, exclude=None):
    """Toma y ejecuta el pedido siguiente de los tipos que se atienden. Devuelve el
    pedido, o `None` si no había."""
    job = claim(kinds, exclude)
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
