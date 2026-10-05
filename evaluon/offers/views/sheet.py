"""Páginas de la ficha: pedirla y verla en solo lectura (REQ-039 a REQ-041, REQ-043, REQ-044;
plan 008, "Pantalla"; ADR-0005; T-130).

- `build`: el botón "Armar ficha" de la página de la oferta. Llama a
  `services.sheets.request_sheet`. Un pedido correcto redirige a la página de la oferta; uno
  rechazado (sin matriz validada, documentos sin leer, pedido en curso) la vuelve a mostrar con
  el motivo.
- `sheet`: la ficha: "Lo que no se encontró" y "Páginas sin leer" primero, una fila por
  requisito con su síntesis y sus fragmentos (documento, página, texto literal y enlace al
  original en esa página), y las filas técnicas con su cotización. Sin juicio de cumplimiento.

Las funciones de negocio comprueban el rol de la Comisión. La vista no guarda nada en la
sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.offers.models import Offer, Sheet
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets as services
from evaluon.offers.views.documents import OFFER_TEMPLATE, REQUESTED_PARAM

SHEET_TEMPLATE = "offers/sheet.html"


@require_POST
def build(request, offer_id):
    """Pide la ficha de la oferta."""
    try:
        page = offers_service.offer_page(request.user, offer_id, channel=Channel.SCREEN)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número.")
    try:
        requested = services.request_sheet(request.user, page.offer, channel=Channel.SCREEN)
    except services.SheetRefused as error:
        return render(request, OFFER_TEMPLATE, {"page": page, "errors": [],
                                                "loaded": None, "requested": None,
                                                "sheet_error": str(error)})
    return redirect(reverse("offers:offer", args=[page.offer.pk])
                    + f"?{REQUESTED_PARAM}={requested.job.pk}")


@require_GET
def sheet(request, sheet_id):
    """La ficha en solo lectura."""
    try:
        page = services.sheet_page(request.user, sheet_id, channel=Channel.SCREEN)
    except Sheet.DoesNotExist:
        raise Http404("No hay una ficha con ese número.")
    return render(request, SHEET_TEMPLATE, {"page": page})
