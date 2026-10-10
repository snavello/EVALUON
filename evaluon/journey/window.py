"""Ventana del proceso (REQ-070; plan 013, "Enmienda 2026-10-07"; T-187).

Arma, para un procedimiento, lo que muestra el panel: el pedido en curso (o, si no hay, el
último que terminó, con su resumen), el paso actual, lo hecho y lo que falta, y los últimos
pasos con su hora. Solo lee: `progress_of` (T-184) ya trae los pasos en lenguaje llano y sin
datos personales; aquí no se decide nada (P3)."""

from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from evaluon.journey.progress import format_elapsed, progress_of
from evaluon.tenders.models import Job, JobStatus

ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)

# Estado del panel -> (nombre que aparece al pasar el mouse, símbolo del ícono).
STATES = {
    "waiting": "En espera",
    "running": "En curso",
    "done": "Terminado",
    "failed": "Falló",
}


# Un pedido terminado o fallido se muestra completo este tiempo; después, una sola línea.
FULL_FOR = timedelta(hours=24)

# Inicio del motivo técnico guardado en el pedido -> motivo en lenguaje llano. El texto técnico
# (tipo de error, direcciones internas) queda solo en el registro del pedido.
REASONS = (
    ("timeout", "el motor de IA no respondió a tiempo"),
    ("service_unavailable", "el motor de IA no está disponible"),
    ("input_too_long", "el texto a analizar es demasiado largo para el motor de IA"),
    ("AIServiceError", "el motor de IA no está disponible"),
    ("UnreadableFile", "no se pudo leer el documento"),
    ("UnsupportedFormatError", "no se pudo leer el documento"),
    ("InvalidOutput", "el motor de IA devolvió una respuesta que no se pudo usar"),
    ("interrumpido", "el pedido se interrumpió"),
)
DEFAULT_REASON = "ocurrió un problema al procesar el pedido"


def plain_reason(error):
    """El motivo de una falla en lenguaje llano; nunca el texto técnico."""
    if not error:
        return "no se registró el motivo"
    for prefix, text in REASONS:
        if error.startswith(prefix):
            return text
    # Un error de conexión que nombra el tiempo de espera (T-227, D-1) es el mismo motivo.
    if "timeout" in error.lower():
        return REASONS[0][1]
    return DEFAULT_REASON


def _job_of(procedure):
    """El pedido más reciente en espera o en curso; si no hay, el último, en el estado que sea."""
    jobs = Job.objects.filter(procedure=procedure).order_by("-requested_at", "-pk")
    return jobs.filter(status__in=ACTIVE).first() or jobs.first()


def _steps(recent, now=None):
    """Los últimos pasos, del más nuevo al más viejo, con la hora local (HH:MM:SS); si no son
    de hoy, también la fecha (D/M)."""
    today = timezone.localtime(now or timezone.now()).date()
    out = []
    for item in reversed(recent):
        moment = parse_datetime(str(item.get("at") or ""))
        if moment is not None and timezone.is_aware(moment):
            moment = timezone.localtime(moment)
        text = ""
        if moment:
            text = moment.strftime("%H:%M:%S")
            if moment.date() != today:
                text = f"{moment.day}/{moment.month} {text}"
        out.append({"time": text,
                    "text": item["text"], "scope": item.get("scope") or ""})
    return out


def _count(label_done, label_total, done, total):
    """`{"done", "total", "left", "text"}` de una cuenta, o `None` si no hay total."""
    if done is None or not total:
        return None
    left = max(0, total - done)
    return {"done": done, "total": total, "left": left, "percent": round(100 * done / total),
            "text": f"{label_done} {done} de {total}", "left_text": f"{label_total}: {left}"}


def window_for(procedure, now=None):
    """Los datos del panel o `None` si el procedimiento nunca tuvo un pedido."""
    job = _job_of(procedure)
    if job is None:
        return None
    now = now or timezone.now()
    if job.status in (JobStatus.DONE, JobStatus.FAILED):
        ended = timezone.localtime(job.finished_at or job.requested_at)
        if now - (job.finished_at or job.requested_at) > FULL_FOR:
            return {"state": "old", "job_id": job.pk, "active": False,
                    "last_line": (f"Último pedido: terminó el {ended.day}/{ended.month} "
                                  f"a las {ended:%H:%M}")}
    data = progress_of(job, now=now)
    if job.status == JobStatus.QUEUED:
        state = "waiting"
    elif job.status == JobStatus.RUNNING:
        state = "running"
    elif job.status == JobStatus.DONE:
        state = "done"
    else:
        state = "failed"

    elapsed = data["elapsed_text"]
    if state in ("done", "failed") and job.finished_at:
        began = job.started_at or job.requested_at
        elapsed = format_elapsed((job.finished_at - began).total_seconds())

    # Lo hecho y lo que falta: ofertas (cuenta gruesa) y, dentro de la oferta en curso,
    # requisitos (cuenta fina). Sin cuenta fina, la gruesa puede ser de otra cosa (pasos).
    detail = _count("Requisito", "Requisitos por evaluar",
                    data["detail_done"], data["detail_total"])
    main = _count("Oferta" if data["detail_total"] else "Hecho",
                  "Ofertas por evaluar" if data["detail_total"] else "Falta",
                  data["done"], data["total"])
    if main and not data["detail_total"]:
        main["text"] = f"{data['done']} de {data['total']}"
        main["left_text"] = f"Falta: {main['left']}"

    if state == "done":
        summary = f"Terminó en {elapsed}."
        if main:
            summary += f" Se completaron {main['done']} de {main['total']}."
    elif state == "failed":
        summary = f"Falló a los {elapsed}: {plain_reason(job.error)}."
    else:
        summary = ""

    return {
        "state": state, "state_label": STATES[state], "task": data["task"],
        "step": data["step"], "elapsed": elapsed, "main": main, "detail": detail,
        "steps": _steps(data["recent"], now), "summary": summary,
        "job_id": job.pk, "active": state in ("waiting", "running"),
    }
