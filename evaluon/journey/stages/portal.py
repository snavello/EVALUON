"""Etapa 1, Datos del Portal (REQ-066, REQ-068, REQ-069, REQ-071, REQ-072; plan 013).

El Portal es la primera fuente de un procedimiento y lo subido a mano es su complemento:
la etapa muestra, en dos frases separadas, lo que trajo el Portal y lo que se cargó a mano.

- En curso: hay un pedido `portal_explore` o `portal_review` de un enlace del procedimiento.
- Con error: el último pedido falló y ninguna propuesta posterior lo superó (con el motivo).
- Pendiente: el procedimiento no tiene enlace del Portal o todavía no se exploró. La etapa es
  opcional: un procedimiento cargado a mano nunca tiene datos del Portal.
- A decidir: ítems `propuesto` de la última propuesta de cada enlace (la cuenta).
- Lista: ya se exploró y no queda nada propuesto sin decidir.

El Portal no trae sugerencias propias: `suggestions` es 0. `decide_url` es solo del evaluador
aunque el operador pueda aprobar documentos en la pantalla del Portal (REQ-069).
"""

from django.db.models import Max
from django.urls import reverse

from evaluon.journey.progress import progress_of
from evaluon.journey.stages import base
from evaluon.portal.models import ItemKind, ItemState, LoadedModel, PortalItem, PortalProposal
from evaluon.tenders.models import JobKind, JobStatus

KINDS = (JobKind.PORTAL_EXPLORE, JobKind.PORTAL_REVIEW)
KEY = "portal"
LABEL = "Datos del Portal"


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _latest_proposal(link):
    return link.proposals.order_by("-exploration", "-pk").first()


def _loaded_ids(links, model):
    """Los ids de los objetos que el Portal cargó (ítems aprobados y cargados)."""
    return set(PortalItem.objects.filter(
        proposal__link__in=links, state=ItemState.CARGADO, loaded_model=model,
    ).values_list("loaded_id", flat=True))


def _origin_text(procedure, links):
    """Lo que trajo el Portal y, aparte, lo subido a mano (REQ-071)."""
    portal_docs = _loaded_ids(links, LoadedModel.DOCUMENT)
    portal_offers = _loaded_ids(links, LoadedModel.OFFER)
    doc_ids = set(procedure.documents.values_list("pk", flat=True))
    offer_ids = set(procedure.offers.values_list("pk", flat=True))
    brought = []
    if PortalItem.objects.filter(
            proposal__link__in=links, state=ItemState.CARGADO,
            kind=ItemKind.PROCEDIMIENTO).exists():
        brought.append("los datos del procedimiento")
    if doc_ids & portal_docs:
        brought.append(_plural(len(doc_ids & portal_docs), "documento", "documentos"))
    if offer_ids & portal_offers:
        brought.append(_plural(len(offer_ids & portal_offers), "oferta", "ofertas"))
    by_hand = []
    if doc_ids - portal_docs:
        by_hand.append(_plural(len(doc_ids - portal_docs), "documento", "documentos"))
    if offer_ids - portal_offers:
        by_hand.append(_plural(len(offer_ids - portal_offers), "oferta", "ofertas"))
    return (f"Trajo el Portal: {', '.join(brought) if brought else 'nada todavía'}. "
            f"Subido a mano: {', '.join(by_hand) if by_hand else 'nada'}.")


def compute(user, procedure):
    links = list(procedure.portal_links.order_by("created_at", "pk"))
    origin = _origin_text(procedure, links)
    common = {"key": KEY, "label": LABEL, "optional": True}
    if not links:
        return base.Stage(
            state=base.PENDIENTE, view_url=reverse("portal:links"),
            detail=f"Sin enlace del Portal. {origin}", **common)

    ids = [link.pk for link in links]
    active = base.active_job(KINDS, target_id__in=ids)
    last = base.last_job(KINDS, target_id__in=ids)
    latest = {link.pk: _latest_proposal(link) for link in links}
    open_by_link = {
        link.pk: (PortalItem.objects.filter(
            proposal=latest[link.pk], state=ItemState.PROPUESTO).count()
            if latest[link.pk] else 0)
        for link in links}
    pending = sum(open_by_link.values())
    # Para ver y decidir: el enlace con propuestas sin decidir; si no, el último.
    target = next((link for link in links if open_by_link[link.pk]), links[-1])
    if pending or latest[target.pk] is None:
        view_url = reverse("portal:proposal", args=[target.pk])
    else:
        view_url = reverse("portal:imported", args=[target.pk])
    decide_url = view_url if pending and base.is_evaluator(user) else None
    common.update(pending=pending, view_url=view_url, decide_url=decide_url)

    if active is not None:
        return base.Stage(state=base.EN_CURSO, job=active, progress=progress_of(active),
                          detail=f"El sistema está explorando el Portal. {origin}", **common)

    result_at = PortalProposal.objects.filter(link__in=links).aggregate(
        at=Max("created_at"))["at"]
    if (last is not None and last.status == JobStatus.FAILED
            and not base.superseded(last, result_at)):
        reason = last.error or "no se registró el motivo"
        return base.Stage(state=base.CON_ERROR, job=last, error=reason,
                          detail=f"La última exploración del Portal falló. {origin}", **common)

    if all(proposal is None for proposal in latest.values()):
        return base.Stage(state=base.PENDIENTE,
                          detail=f"Todavía no se exploró el Portal. {origin}", **common)
    if pending:
        return base.Stage(
            state=base.A_DECIDIR,
            detail=f"{_plural(pending, 'dato espera', 'datos esperan')} la decisión de la "
                   f"Comisión. {origin}", **common)
    return base.Stage(state=base.LISTA, detail=origin, **common)
