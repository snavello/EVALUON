"""Tipo `Stage`, estados y ayudantes de pedidos de las etapas del recorrido (plan 013,
"Las etapas y cómo se calcula cada estado").

Cada etapa es una función de solo lectura `compute(user, procedure) -> Stage`. Reglas comunes,
en este orden: pedido activo, en curso; último pedido fallido sin un resultado posterior, con
error; sin lo necesario, pendiente; con decisiones que esperan, a decidir; si no, lista.
"""

from dataclasses import dataclass

from evaluon.accounts.models import CommissionRole
from evaluon.tenders.models import Job, JobStatus

PENDIENTE = "pendiente"
EN_CURSO = "en_curso"
A_DECIDIR = "a_decidir"
LISTA = "lista"
CON_ERROR = "con_error"

LABELS = {
    PENDIENTE: "Pendiente",
    EN_CURSO: "En curso",
    A_DECIDIR: "A decidir",
    LISTA: "Lista",
    CON_ERROR: "Con error",
}

ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


@dataclass(frozen=True)
class Stage:
    """Una etapa del recorrido. `decide_url` es `None` para quien no es evaluador (REQ-069).
    `pending` cuenta las decisiones que esperan a la Comisión y `suggestions`, aparte, las
    sugerencias del sistema (REQ-072)."""

    key: str
    label: str
    state: str
    pending: int = 0
    suggestions: int = 0
    detail: str = ""
    view_url: str | None = None
    decide_url: str | None = None
    job: Job | None = None
    progress: dict | None = None
    error: str = ""
    optional: bool = False

    @property
    def state_label(self):
        return LABELS[self.state]


def is_evaluator(user):
    """Solo el evaluador recibe enlaces de decisión (REQ-069)."""
    return getattr(user, "commission_role", "") == CommissionRole.EVALUATOR


def active_job(kinds, **filters):
    """El pedido más reciente en espera o en curso de esos tipos, o `None`."""
    return (Job.objects.filter(kind__in=kinds, status__in=ACTIVE_STATUSES, **filters)
            .order_by("-requested_at", "-pk").first())


def last_job(kinds, **filters):
    """El pedido más reciente de esos tipos, en el estado que sea, o `None`."""
    return (Job.objects.filter(kind__in=kinds, **filters)
            .order_by("-requested_at", "-pk").first())


def superseded(job, latest_result_at):
    """Si un resultado posterior al fin del pedido lo superó (la falla ya no cuenta)."""
    return (job.finished_at is not None and latest_result_at is not None
            and latest_result_at > job.finished_at)


def placeholder(key, label, *, optional=False):
    """La etapa reservada: todavía no se calcula (la reemplazan T-180, T-181 y T-182)."""
    return Stage(key=key, label=label, state=PENDIENTE, detail="Todavía no calculada.",
                 optional=optional)
