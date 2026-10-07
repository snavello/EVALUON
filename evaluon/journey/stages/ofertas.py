"""Etapa 4, Ofertas (REQ-066, REQ-068, REQ-069, REQ-072; plan 013).

Reglas, en este orden (plan, "Las etapas y cómo se calcula cada estado"):

- En curso: hay un pedido `read_offer_document` o `build_sheet` del procedimiento en espera o
  en curso.
- Con error: el último pedido de lectura de algún documento, o de ficha de alguna oferta,
  falló y ningún resultado posterior (lectura o ficha) lo superó; se muestra el motivo.
- Pendiente: no hay ofertas con documentos, o algún documento todavía no tiene lectura.
- A decidir: la última ficha de pantalla de alguna oferta tiene filas en estado `propuesto`;
  la cuenta es la suma de esas filas.
- Lista: todos los documentos leídos y ninguna fila propuesta.

La ficha no es obligatoria para evaluar (decisión del responsable, 2026-10-07): que una oferta
no tenga ficha no frena la etapa. Es una sugerencia, que se cuenta aparte de las decisiones
pendientes (REQ-072): una por cada oferta con todos sus documentos leídos y sin ficha, mientras
haya una matriz validada con la cual armarla. Las filas pendientes de una ficha, en cambio, son
decisiones de la Comisión. El recorrido solo lee: no arma fichas ni confirma filas.
"""

from django.db.models import Count, Max, Q
from django.urls import reverse

from evaluon.journey.progress import progress_of
from evaluon.journey.stages import base
from evaluon.offers.models import Document, EntryState, Sheet, SheetChannel
from evaluon.tenders.models import JobKind, JobStatus
from evaluon.tenders.services.validation import latest_validated

KINDS = (JobKind.READ_OFFER_DOCUMENT, JobKind.BUILD_SHEET)
KEY = "ofertas"
LABEL = "Ofertas"


def _failed_job(procedure):
    """El pedido fallido más reciente cuyo objeto (documento u oferta) no tiene después un
    resultado que lo supere, o `None`. Devuelve `(pedido, nombre del objeto)`."""
    failed = []
    for document in Document.objects.filter(offer__procedure=procedure).select_related("offer"):
        job = base.last_job((JobKind.READ_OFFER_DOCUMENT,), target_id=document.pk,
                            procedure=procedure)
        if job is None or job.status != JobStatus.FAILED:
            continue
        latest = document.readings.aggregate(at=Max("created_at"))["at"]
        if not base.superseded(job, latest):
            failed.append((job, f"el documento «{document.title}» de la oferta "
                                f"{document.offer.number}"))
    for offer in procedure.offers.all():
        job = base.last_job((JobKind.BUILD_SHEET,), target_id=offer.pk, procedure=procedure)
        if job is None or job.status != JobStatus.FAILED:
            continue
        latest = offer.sheets.aggregate(at=Max("built_at"))["at"]
        if not base.superseded(job, latest):
            failed.append((job, f"la ficha de la oferta {offer.number}"))
    if not failed:
        return None
    return max(failed, key=lambda item: (item[0].requested_at, item[0].pk))


def _pending_sheets(offers):
    """Por oferta, la última ficha de pantalla con filas `propuesto`: `[(oferta, ficha,
    filas)]`, en el orden de las ofertas."""
    rows = []
    for offer in offers:
        sheet = (Sheet.objects.filter(offer=offer, channel=SheetChannel.SCREEN)
                 .order_by("-number").annotate(
                     proposed=Count("entries", filter=Q(entries__state=EntryState.PROPUESTO)))
                 .first())
        if sheet is not None and sheet.proposed:
            rows.append((offer, sheet, sheet.proposed))
    return rows


def compute(user, procedure):
    view_url = reverse("offers:procedure_offers", args=[procedure.pk])
    common = {"key": KEY, "label": LABEL, "view_url": view_url}

    offers = list(procedure.offers.order_by("number"))
    with_documents = [o for o in offers if o.documents.exists()]
    documents = list(Document.objects.filter(offer__in=with_documents))
    unread = [d for d in documents if not d.readings.exists()]
    all_read = bool(with_documents) and not unread

    pending_sheets = _pending_sheets(with_documents)
    pending = sum(count for _, _, count in pending_sheets)
    suggestions = 0
    if all_read and latest_validated(procedure) is not None:
        suggestions = sum(1 for o in with_documents if not o.sheets.exists())
    counts = {"pending": pending, "suggestions": suggestions}

    decide_url = None
    if pending_sheets and base.is_evaluator(user):
        decide_url = reverse("offers:sheet", args=[pending_sheets[0][1].pk])
    common_all = {**common, **counts, "decide_url": decide_url}

    active = base.active_job(KINDS, procedure=procedure)
    if active is not None:
        what = ("leyendo documentos de las ofertas"
                if active.kind == JobKind.READ_OFFER_DOCUMENT else "armando una ficha")
        return base.Stage(state=base.EN_CURSO, job=active, progress=progress_of(active),
                          detail=f"El sistema está {what}.", **common_all)

    failed = _failed_job(procedure)
    if failed is not None:
        job, what = failed
        reason = job.error or "no se registró el motivo"
        return base.Stage(state=base.CON_ERROR, job=job, error=reason,
                          detail=f"Falló {what}.", **common_all)

    if not offers:
        return base.Stage(state=base.PENDIENTE, detail="Todavía no hay ofertas cargadas.",
                          **common_all)
    if not with_documents:
        return base.Stage(state=base.PENDIENTE,
                          detail="Las ofertas todavía no tienen documentos cargados.",
                          **common_all)
    if unread:
        return base.Stage(
            state=base.PENDIENTE,
            detail=f"Faltan leer {len(unread)} de {len(documents)} documentos de las ofertas.",
            **common_all)
    if pending_sheets:
        parts = [f"oferta {offer.number} ({offer.bidder}): {count} "
                 f"{'fila' if count == 1 else 'filas'} de la ficha por confirmar"
                 for offer, _, count in pending_sheets]
        return base.Stage(state=base.A_DECIDIR, detail="; ".join(parts) + ".", **common_all)
    detail = f"Los {len(documents)} documentos de las ofertas están leídos."
    if suggestions:
        detail += (f" Se puede armar la ficha de {suggestions} "
                   f"{'oferta' if suggestions == 1 else 'ofertas'} (no es obligatoria).")
    return base.Stage(state=base.LISTA, detail=detail, **common_all)

