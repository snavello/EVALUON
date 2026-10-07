"""Avance de un pedido en segundo plano (REQ-067; plan 013, "Avance en vivo"; ADR-0045, 3.A).

`progress_of(job)` usa la columna `tenders_job.progress` (T-184, ADR-0045 3.B) cuando tiene
datos y, si está vacía, lo que la cola y cada servicio ya registran (el cálculo del corte):

- `evaluate_offers`: "N de M ofertas evaluadas" (evaluaciones del pedido sobre las ofertas pedidas).
- `propose_matrix`: la última pasada de la propuesta y la cuenta de pedidos al modelo hechos.
- Los demás: la tarea y el tiempo transcurrido.

Con la columna, el resultado suma `detail_done` y `detail_total` (por ejemplo, requisito x de y
de la oferta en curso) y `recent`: los últimos pasos (`RECENT_LIMIT` como máximo), del más
antiguo al más nuevo, cada uno `{"at", "text", "scope"}` en lenguaje llano. La ventana del proceso
(T-187) los muestra tal cual. `done`, `total` y `percent` siguen siendo la cuenta gruesa (ofertas).
"""

from django.utils import timezone

from evaluon.assessment.models import Request, Run
from evaluon.tenders.models import (
    JobKind,
    JobStatus,
    MatrixRun,
    PassName,
    RunStep,
)

TASKS = {
    JobKind.EVALUATE_OFFERS: "Evaluando las ofertas",
    JobKind.PROPOSE_MATRIX: "Proponiendo la matriz",
    JobKind.READ_DOCUMENT: "Leyendo un documento del pliego",
    JobKind.READ_OFFER_DOCUMENT: "Leyendo un documento de una oferta",
    JobKind.BUILD_SHEET: "Armando la ficha de una oferta",
    JobKind.PORTAL_EXPLORE: "Explorando el proceso en el Portal",
    JobKind.PORTAL_REVIEW: "Revisando el proceso en el Portal",
}


def format_elapsed(seconds):
    """`125` -> "2 min 5 s"; `45` -> "45 s"."""
    seconds = max(0, int(seconds))
    minutes, rest = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {rest} s"
    return f"{rest} s"


def _evaluation(job):
    request = Request.objects.filter(pk=job.target_id).first()
    if request is None:
        return None, None, ""
    total = len(request.offers)
    done = Run.objects.filter(request=request).count()
    return done, total, f"{done} de {total} ofertas evaluadas"


def _matrix(job):
    run = MatrixRun.objects.filter(job=job).order_by("-pk").first()
    if run is None:
        return None, None, ""
    steps = RunStep.objects.filter(run=run)
    last = steps.order_by("-pk").first()
    if last is None:
        return 0, None, "Preparando la propuesta"
    name = PassName(last.pass_name).label
    return steps.count(), None, f"Pasada: {name} ({steps.count()} pedidos al modelo)"


# Cuántos de los últimos pasos devuelve `progress_of`.
RECENT_LIMIT = 8


def _fine(job):
    """Lo anotado por `jobs.report`: `(paso, hecho, total, contexto, últimos)` o `None`."""
    data = job.progress if isinstance(job.progress, dict) else {}
    if not data.get("step"):
        return None
    recent = [r for r in (data.get("recent") or []) if isinstance(r, dict) and r.get("text")]
    return (data["step"], data.get("done"), data.get("total"), data.get("scope") or "",
            recent[-RECENT_LIMIT:])


def progress_of(job, now=None):
    """`{task, step, done, total, percent, waiting, elapsed_seconds, elapsed_text}` del pedido."""
    now = now or timezone.now()
    waiting = job.status == JobStatus.QUEUED
    start = job.requested_at if waiting else (job.started_at or job.requested_at)
    elapsed = int((now - start).total_seconds()) if start else 0
    done = total = None
    step = "En espera" if waiting else "En curso"
    if job.kind == JobKind.EVALUATE_OFFERS:
        done, total, text = _evaluation(job)
    elif job.kind == JobKind.PROPOSE_MATRIX:
        done, total, text = _matrix(job)
    else:
        text = ""
    fine = _fine(job)
    detail_done = detail_total = None
    recent = []
    if fine and not waiting:
        note, detail_done, detail_total, scope, recent = fine
        text = f"{scope}: {note}" if scope else note
        if done is None:
            done, total = detail_done, detail_total
            detail_done = detail_total = None
    if text and not waiting:
        step = text
    percent = round(100 * done / total) if total and done is not None else None
    return {
        "task": TASKS.get(job.kind) or JobKind(job.kind).label,
        "step": step, "done": done, "total": total, "percent": percent,
        "detail_done": detail_done, "detail_total": detail_total, "recent": recent,
        "waiting": waiting, "elapsed_seconds": max(0, elapsed),
        "elapsed_text": format_elapsed(elapsed),
    }
