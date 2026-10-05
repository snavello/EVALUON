"""Páginas de ofertas: la lista de un procedimiento, la página de una oferta y el original de
sus documentos (REQ-037, REQ-038; plan 008, "Pantalla"; ADR-0005; T-130).

- `procedure_offers`: las ofertas del procedimiento con el estado de lectura y de ficha, y
  el formulario para registrar una oferta (oferente).
- `offer`: los documentos de la oferta con su tipo (si el sistema lo clasificó), su estado y
  el enlace al original; las páginas no leídas y de baja confianza; el formulario de carga y
  "Armar ficha".
- `document_original`: el original byte por byte (el PDF y las fotos van para el visor del
  navegador; con `?descargar` se baja como archivo).

Las funciones de negocio comprueban el rol de la Comisión: sin él, "acceso denegado" (403).
Una operación correcta redirige a la misma página, para que recargar no repita el pedido; una
rechazada (oferente repetido, archivo repetido, formato que no se lee) la vuelve a mostrar con
el motivo. La vista no guarda nada en la sesión.
"""

from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_http_methods

from evaluon.audit.models import Channel
from evaluon.offers.models import DocumentFile, Offer
from evaluon.offers.services import offers as services
from evaluon.tenders.models import Procedure

OFFERS_TEMPLATE = "offers/offers.html"
OFFER_TEMPLATE = "offers/offer.html"

CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}

# Parámetros con que las redirecciones nombran lo que se acaba de hacer.
LOADED_PARAM = "cargados"
REQUESTED_PARAM = "ficha"


@require_http_methods(["GET", "POST"])
def procedure_offers(request, procedure_id):
    """Lista de ofertas de un procedimiento y alta de una oferta."""
    try:
        procedure, rows = services.offers_page(request.user, procedure_id,
                                               channel=Channel.SCREEN)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    error = ""
    if request.method == "POST":
        try:
            offer = services.register_offer(request.user, procedure,
                                            bidder=request.POST.get("bidder", ""),
                                            channel=Channel.SCREEN)
        except services.OfferRefused as refused:
            error = str(refused)
        else:
            return redirect(reverse("offers:offer", args=[offer.pk]))
    return render(request, OFFERS_TEMPLATE, {
        "procedure": procedure, "rows": rows, "error": error,
        "bidder": request.POST.get("bidder", "") if error else ""})


@require_http_methods(["GET", "POST"])
def offer(request, offer_id):
    """Página de una oferta y carga de documentos (uno o varios a la vez)."""
    errors = []
    try:
        page = services.offer_page(request.user, offer_id, channel=Channel.SCREEN)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número.")
    if request.method == "POST":
        uploads = request.FILES.getlist("file") or [None]
        loaded = 0
        for upload in uploads:
            content = upload.read() if upload is not None else b""
            name = upload.name if upload is not None else ""
            try:
                services.load_document(request.user, page.offer, data=content,
                                       file_name=name, channel=Channel.SCREEN)
            except services.OfferRefused as refused:
                errors.append(f"{name or 'Sin archivo'}: {refused}")
            else:
                loaded += 1
        if not errors:
            return redirect(reverse("offers:offer", args=[page.offer.pk])
                            + f"?{LOADED_PARAM}={loaded}")
        page = services.offer_page(request.user, offer_id, channel=Channel.SCREEN)
    return render(request, OFFER_TEMPLATE, {
        "page": page, "errors": errors,
        "loaded": request.GET.get(LOADED_PARAM) if request.method == "GET" else None,
        "requested": request.GET.get(REQUESTED_PARAM) if request.method == "GET" else None,
        "sheet_error": ""})


@require_GET
def document_original(request, document_id):
    """Entrega byte por byte el original de un documento de la oferta."""
    try:
        stored = services.original_file(request.user, document_id, channel=Channel.SCREEN)
    except DocumentFile.DoesNotExist:
        raise Http404("No hay un documento original con ese número.")
    document = stored.document
    response = HttpResponse(bytes(stored.content),
                            content_type=CONTENT_TYPES[document.file_format])
    response["Content-Disposition"] = content_disposition_header(
        as_attachment="descargar" in request.GET, filename=document.file_name)
    return response
