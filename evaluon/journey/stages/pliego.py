"""Etapa 2, Pliego y circulares (REQ-066, REQ-068, REQ-069, REQ-072; plan 013).

- En curso: hay un pedido `read_document` en espera o en curso.
- Con error: el último pedido de algún documento falló y ninguna lectura posterior lo superó
  (con el motivo y el documento).
- Pendiente: no hay documentos del procedimiento o alguno todavía no tiene lectura.
- Lista: todos los documentos tienen lectura.

La lectura es automática: no hay decisiones (`pending` 0) ni sugerencias (`suggestions` 0).
Los documentos pueden venir del Portal o subirse a mano; ambos se leen igual.
"""

from django.urls import reverse

from evaluon.journey.progress import progress_of
from evaluon.journey.stages import base
from evaluon.tenders.models import JobKind, JobStatus

KINDS = (JobKind.READ_DOCUMENT,)
KEY = "pliego"
LABEL = "Pliego y circulares"


def compute(user, procedure):
    view_url = reverse("tenders:procedure", args=[procedure.pk])
    common = {"key": KEY, "label": LABEL, "view_url": view_url}

    active = base.active_job(KINDS, document__procedure=procedure)
    if active is not None:
        return base.Stage(state=base.EN_CURSO, job=active, progress=progress_of(active),
                          detail="El sistema está leyendo los documentos.", **common)

    documents = list(procedure.documents.order_by("loaded_at", "pk"))
    if not documents:
        return base.Stage(state=base.PENDIENTE,
                          detail="Faltan los documentos del pliego.", **common)

    unread = []
    for document in documents:
        reading = document.readings.order_by("-sequence").first()
        job = base.last_job(KINDS, document=document)
        if (job is not None and job.status == JobStatus.FAILED
                and not base.superseded(job, reading.created_at if reading else None)):
            reason = job.error or "no se registró el motivo"
            return base.Stage(
                state=base.CON_ERROR, job=job, error=reason,
                detail=f"No se pudo leer «{document.title}».", **common)
        if reading is None:
            unread.append(document)

    if unread:
        return base.Stage(
            state=base.PENDIENTE,
            detail=f"Falta leer {len(unread)} de {len(documents)} documentos.", **common)
    return base.Stage(
        state=base.LISTA,
        detail=("El documento del pliego está leído." if len(documents) == 1 else
                f"Los {len(documents)} documentos del pliego y sus circulares están leídos."),
        **common)
