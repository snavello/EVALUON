"""Etapa 3, Matriz de cumplimiento (REQ-066, REQ-068, REQ-069, REQ-072; plan 013).

La versión que cuenta es la última no descartada.

- En curso: hay un pedido `propose_matrix` en espera o en curso.
- Con error: el último pedido falló y ninguna versión posterior lo superó (con el motivo).
- Pendiente: no hay versión (el pliego no está leído o todavía no se pidió la propuesta).
- A decidir: la versión es un borrador. Cuenta los requisitos `propuesto` más los tramos
  pendientes sin resolver; si no queda ninguno, queda solo validarla.
- Lista: la versión está validada.

Las sugerencias son los requisitos `sugerido` del borrador: se muestran aparte y no frenan la
validación. `decide_url` es solo del evaluador y solo mientras haya un borrador.
"""

from django.db.models import Max
from django.urls import reverse

from evaluon.journey.progress import progress_of
from evaluon.journey.stages import base, pliego
from evaluon.tenders.models import (
    JobKind,
    JobStatus,
    MatrixVersion,
    PendingItem,
    RequirementState,
    VersionStatus,
)

KINDS = (JobKind.PROPOSE_MATRIX,)
KEY = "matriz"
LABEL = "Matriz de cumplimiento"


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def compute(user, procedure):
    common = {"key": KEY, "label": LABEL,
              "view_url": reverse("tenders:procedure", args=[procedure.pk])}

    version = (MatrixVersion.objects.filter(procedure=procedure)
               .exclude(status=VersionStatus.DISCARDED).order_by("-number").first())
    if version is not None:
        common["view_url"] = reverse("tenders:matrix", args=[version.pk])

    active = base.active_job(KINDS, procedure=procedure)
    if active is not None:
        return base.Stage(state=base.EN_CURSO, job=active, progress=progress_of(active),
                          detail="El sistema está proponiendo la matriz.", **common)

    last = base.last_job(KINDS, procedure=procedure)
    if last is not None and last.status == JobStatus.FAILED:
        newest = MatrixVersion.objects.filter(procedure=procedure).aggregate(
            at=Max("created_at"))["at"]
        if not base.superseded(last, newest):
            reason = last.error or "no se registró el motivo"
            return base.Stage(state=base.CON_ERROR, job=last, error=reason,
                              detail="La última propuesta de la matriz falló.", **common)

    if version is None:
        if pliego.compute(user, procedure).state != base.LISTA:
            detail = "Falta el pliego leído para proponer la matriz."
        else:
            detail = "Todavía no se pidió la propuesta de la matriz."
        return base.Stage(state=base.PENDIENTE, detail=detail, **common)

    if version.status == VersionStatus.VALIDATED:
        return base.Stage(state=base.LISTA,
                          detail=f"La versión {version.number} está validada.", **common)

    proposed = version.requirements.filter(state=RequirementState.PROPUESTO).count()
    unresolved = PendingItem.objects.filter(version=version, resolved_at__isnull=True).count()
    suggested = version.requirements.filter(state=RequirementState.SUGERIDO).count()
    pending = proposed + unresolved
    detail = f"Borrador de la versión {version.number}: "
    detail += (f"{_plural(proposed, 'requisito', 'requisitos')} por confirmar y "
               f"{_plural(unresolved, 'tramo', 'tramos')} por resolver."
               if pending else "no queda nada por confirmar; falta validarla.")
    decide_url = common["view_url"] if base.is_evaluator(user) else None
    return base.Stage(state=base.A_DECIDIR, pending=pending, suggestions=suggested,
                      detail=detail, decide_url=decide_url, **common)
