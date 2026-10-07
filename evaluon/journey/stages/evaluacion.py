"""Etapa 5, Evaluación (REQ-066, REQ-067; plan 013).

- En curso: hay un pedido `evaluate_offers` en espera o en curso (con su avance).
- Con error: el último pedido falló y ninguna evaluación posterior lo superó (con el motivo).
- Pendiente: falta una matriz validada, ofertas con documentos o evaluar alguna oferta con la
  versión validada vigente.
- Lista: cada oferta con documentos tiene una evaluación de la versión validada vigente.

La evaluación solo propone: no tiene decisiones propias que contar (`pending` es 0). La ficha
de la oferta no es condición para evaluar (decisión del responsable, 2026-10-07).
"""

from django.db.models import Max
from django.urls import reverse

from evaluon.assessment.models import Run
from evaluon.journey.progress import progress_of
from evaluon.journey.stages import base
from evaluon.tenders.models import JobKind, JobStatus
from evaluon.tenders.services.validation import latest_validated

KINDS = (JobKind.EVALUATE_OFFERS,)
KEY = "evaluacion"
LABEL = "Evaluación"


def _latest_result_at(procedure):
    return Run.objects.filter(request__procedure=procedure).aggregate(
        at=Max("built_at"))["at"]


def compute(user, procedure):
    view_url = reverse("assessment:matrix", args=[procedure.pk])
    decide_url = view_url if base.is_evaluator(user) else None
    common = {"key": KEY, "label": LABEL, "view_url": view_url, "decide_url": decide_url}

    active = base.active_job(KINDS, procedure=procedure)
    if active is not None:
        return base.Stage(state=base.EN_CURSO, job=active, progress=progress_of(active),
                          detail="El sistema está evaluando las ofertas.", **common)

    last = base.last_job(KINDS, procedure=procedure)
    if (last is not None and last.status == JobStatus.FAILED
            and not base.superseded(last, _latest_result_at(procedure))):
        reason = last.error or "no se registró el motivo"
        return base.Stage(state=base.CON_ERROR, job=last, error=reason,
                          detail="La última evaluación falló.", **common)

    version = latest_validated(procedure)
    if version is None:
        return base.Stage(state=base.PENDIENTE, detail="Falta una matriz validada.", **common)
    offers = [o for o in procedure.offers.order_by("number") if o.documents.exists()]
    if not offers:
        return base.Stage(state=base.PENDIENTE,
                          detail="Faltan ofertas con documentos cargados.", **common)
    evaluated = [o for o in offers
                 if Run.objects.filter(offer=o, matrix_version=version).exists()]
    if len(evaluated) < len(offers):
        detail = ("Todavía no se evaluó ninguna oferta." if not evaluated else
                  f"Se evaluaron {len(evaluated)} de {len(offers)} ofertas con la matriz vigente.")
        return base.Stage(state=base.PENDIENTE, detail=detail, **common)
    return base.Stage(state=base.LISTA,
                      detail=f"Las {len(offers)} ofertas están evaluadas con la matriz vigente.",
                      **common)
