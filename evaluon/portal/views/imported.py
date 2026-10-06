"""Pantalla "Lo importado" de un proceso: los documentos que vinieron del Portal, con su
origen (página y fecha de consulta) y su huella, y los que se cargaron a mano en el mismo
procedimiento, que figuran como "carga manual" (REQ-049, REQ-051; plan 012, "Pantalla";
T-142).

Los documentos que no son del pliego (actos, acta, dictamen) quedan como archivo del Portal y
se descargan desde acá, tal como se bajaron.
"""

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    LoadedModel,
    PortalFile,
    PortalItem,
    PortalLink,
)
from evaluon.tenders.models import Document

TEMPLATE = "portal/imported.html"
PAGE_OPERATION = "evaluon.portal.views.imported.imported"
DOWNLOAD_OPERATION = "evaluon.portal.views.imported.download"
CONTENT_TYPES = {"pdf": "application/pdf", "html": "text/html; charset=utf-8"}


def imported_documents(link):
    """`(importados, manuales)`: ítems de documento decididos con éxito y documentos del
    procedimiento que no vienen de ningún ítem del Portal."""
    items = list(PortalItem.objects.filter(
        proposal__link=link, kind=ItemKind.DOCUMENTO,
        state__in=(ItemState.CARGADO, ItemState.APROBADO),
    ).select_related("page", "file", "decided_by").order_by("id"))
    manual = []
    if link.procedure_id:
        from_portal = {item.loaded_id for item in items
                       if item.loaded_model == LoadedModel.DOCUMENT}
        manual = list(Document.objects.filter(procedure_id=link.procedure_id)
                      .exclude(pk__in=from_portal).select_related("loaded_by").order_by("id"))
    return items, manual


@require_GET
def imported(request, link_id):
    require_commission_role(request.user, CommissionRole.OPERATOR,
                            operation=PAGE_OPERATION, channel=Channel.SCREEN)
    try:
        link = PortalLink.objects.select_related("procedure").get(pk=link_id)
    except PortalLink.DoesNotExist:
        raise Http404("No hay un enlace con ese número.")
    items, manual = imported_documents(link)
    return render(request, TEMPLATE, {"link": link, "items": items, "manual": manual})


@require_GET
def download(request, link_id, file_id):
    """El archivo tal como se bajó del Portal, solo si pertenece al enlace."""
    require_commission_role(request.user, CommissionRole.OPERATOR,
                            operation=DOWNLOAD_OPERATION, channel=Channel.SCREEN)
    try:
        stored = PortalFile.objects.get(pk=file_id, link_id=link_id)
    except PortalFile.DoesNotExist:
        raise Http404("No hay un archivo con ese número.")
    response = HttpResponse(bytes(stored.content),
                            content_type=CONTENT_TYPES.get(stored.file_format,
                                                           "application/octet-stream"))
    safe_name = stored.file_name.replace('"', "").encode("ascii", "replace").decode()
    response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
