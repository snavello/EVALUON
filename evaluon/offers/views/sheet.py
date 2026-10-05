"""Páginas de la ficha: pedirla, verla y corregirla (REQ-039 a REQ-044; plan 008, "Pantalla";
ADR-0005; T-130 y T-132).

- `build`: el botón "Armar ficha" de la página de la oferta. Llama a
  `services.sheets.request_sheet`. Un pedido correcto redirige a la página de la oferta; uno
  rechazado (sin matriz validada, documentos sin leer, pedido en curso) la vuelve a mostrar con
  el motivo.
- `sheet`: la ficha: "Lo que no se encontró" y "Páginas sin leer" primero, una fila por
  requisito con su síntesis y sus fragmentos (documento, página, texto literal y enlace al
  original en esa página), y las filas técnicas con su cotización. Sin juicio de cumplimiento.
  Con las acciones de revisión y el aviso de versión de la matriz.
- `confirm`, `fragment_action` (corregir, quitar, restituir) y `add`: la revisión de la ficha
  (REQ-042). Un cambio rechazado vuelve a mostrar la página con el motivo.
- `entry_history`: una fila con su historial y los formularios de corregir y agregar.

Las funciones de negocio comprueban el rol de la Comisión. La vista no guarda nada en la
sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.offers.models import Fragment, Offer, Sheet, SheetEntry
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import review
from evaluon.offers.services import sheets as services
from evaluon.offers.views.documents import OFFER_TEMPLATE, REQUESTED_PARAM

SHEET_TEMPLATE = "offers/sheet.html"
HISTORY_TEMPLATE = "offers/sheet_history.html"
BACK_TO_ENTRY = "fila"


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


def _sheet_response(request, sheet_id, error=None, status=200):
    try:
        reviewed = review.review_page(request.user, sheet_id, channel=Channel.SCREEN)
    except Sheet.DoesNotExist:
        raise Http404("No hay una ficha con ese número.")
    return render(request, SHEET_TEMPLATE, {"page": reviewed.page, "review": reviewed,
                                            "error": error}, status=status)


def _history_response(request, entry_id, error=None, status=200):
    try:
        page = review.history(request.user, entry_id, channel=Channel.SCREEN)
    except SheetEntry.DoesNotExist:
        raise Http404("No hay una fila de la ficha con ese número.")
    return render(request, HISTORY_TEMPLATE, {"history": page, "error": error},
                  status=status)


def _after(request, entry):
    """A dónde vuelve la persona tras un cambio: a la ficha, o a la fila si vino de ella."""
    if request.POST.get("volver") == BACK_TO_ENTRY:
        return redirect(reverse("offers:entry_history", args=[entry.pk]))
    return redirect(reverse("offers:sheet", args=[entry.sheet_id]) + f"#fila-{entry.pk}")


def _refused(request, error, entry):
    if request.POST.get("volver") == BACK_TO_ENTRY:
        return _history_response(request, entry.pk, str(error), status=422)
    return _sheet_response(request, entry.sheet_id, str(error), status=422)


@require_GET
def sheet(request, sheet_id):
    """La ficha, con las acciones de revisión."""
    return _sheet_response(request, sheet_id)


@require_GET
def entry_history(request, entry_id):
    """Una fila de la ficha con su historial."""
    return _history_response(request, entry_id)


@require_POST
def confirm(request, sheet_id):
    """Confirma las filas marcadas (solo el evaluador)."""
    if not Sheet.objects.filter(pk=sheet_id).exists():
        raise Http404("No hay una ficha con ese número.")
    try:
        review.confirm(request.user, request.POST.getlist("entry"), channel=Channel.SCREEN)
    except review.ReviewRefused as error:
        return _sheet_response(request, sheet_id, str(error), status=422)
    return redirect(reverse("offers:sheet", args=[sheet_id]))


@require_POST
def fragment_action(request, fragment_id, action):
    """Corrige, quita o restituye un fragmento."""
    if action not in ("corregir", "quitar", "restituir"):
        raise Http404("Acción desconocida.")
    try:
        entry = Fragment.objects.select_related("entry").get(pk=fragment_id).entry
    except Fragment.DoesNotExist:
        raise Http404("No hay un fragmento con ese número.")
    try:
        if action == "corregir":
            review.correct(request.user, fragment_id,
                           passage_id=request.POST.get("passage") or None,
                           text=request.POST.get("text", ""), channel=Channel.SCREEN)
        elif action == "quitar":
            review.remove(request.user, fragment_id, channel=Channel.SCREEN)
        else:
            review.restore(request.user, fragment_id, channel=Channel.SCREEN)
    except review.ReviewRefused as error:
        return _refused(request, error, entry)
    return _after(request, entry)


@require_POST
def add(request, entry_id):
    """Agrega un fragmento a la fila."""
    try:
        entry = SheetEntry.objects.get(pk=entry_id)
    except SheetEntry.DoesNotExist:
        raise Http404("No hay una fila de la ficha con ese número.")
    try:
        review.add(request.user, entry.pk, passage_id=request.POST.get("passage"),
                   text=request.POST.get("text", ""), channel=Channel.SCREEN)
    except review.ReviewRefused as error:
        return _refused(request, error, entry)
    return _after(request, entry)
