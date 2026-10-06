"""Página de un par: el resultado vigente de una oferta para un requisito (REQ-052, REQ-053,
REQ-055, REQ-056; plan 004, "Revisión y decisión"; ADR-0005; T-150, T-153).

Muestra el texto del requisito, las citas de la oferta con su documento, página y texto
literal (con el enlace al original en esa página), la norma o la respuesta de la Comisión
rotuladas como tales, la explicación del sistema (rotulada, nunca como cita), el motivo de un
"no determinado" y la pregunta abierta. Todo es una propuesta: la decisión es de la Comisión
(P3); el evaluador la toma desde esta página (T-153, `views/review.py`).

La función de negocio comprueba el rol de la Comisión: sin él, "acceso denegado" (403). La vista
no guarda nada en la sesión.
"""

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.assessment.models import Result
from evaluon.assessment.services import evaluate, remedy, review
from evaluon.audit.models import Channel
from evaluon.offers import vision

RESULT_TEMPLATE = "assessment/result.html"


def render_pair(request, offer_id, requirement_id, *, error="", status=200):
    """La página del par, con un mensaje de error si la decisión se rechazó."""
    try:
        page = evaluate.pair_page(request.user, offer_id, requirement_id,
                                  channel=Channel.SCREEN)
    except Result.DoesNotExist:
        raise Http404("Ese requisito todavía no se evaluó para esa oferta.")
    return render(request, RESULT_TEMPLATE, {
        "page": page, "review": review.pair_review(request.user, page), "error": error,
        "remedy": remedy.state(page.result)},
        status=status)


@require_GET
def pair(request, offer_id, requirement_id):
    """El resultado vigente del par."""
    return render_pair(request, offer_id, requirement_id)


@require_GET
def vision_page(request, offer_id, requirement_id, document_id, page):
    """La imagen de una página leída por visión que cita el resultado vigente del par, dibujada
    del original (ADR-0041): la Comisión la compara con la transcripción antes de confirmar
    (P3). Solo de las páginas que el resultado cita por visión."""
    try:
        pair_page = evaluate.pair_page(request.user, offer_id, requirement_id,
                                       channel=Channel.SCREEN)
    except Result.DoesNotExist:
        raise Http404("Ese requisito todavía no se evaluó para esa oferta.")
    cited = next((c for c in pair_page.offer_citations
                  if c.by_vision and c.document_id == document_id and c.page == page), None)
    image = vision.page_image(cited.document, page) if cited is not None else None
    if image is None:
        raise Http404("No hay imagen de esa página para este resultado.")
    return HttpResponse(image, content_type="image/jpeg")
