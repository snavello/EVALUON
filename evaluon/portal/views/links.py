"""Página "Importar desde el Portal": los enlaces y el alta de uno (REQ-045; plan 012,
"Pantalla"; ADR-0005; T-141).

Las funciones de negocio comprueban el rol de la Comisión: sin él, "acceso denegado" (403).
Un alta correcta redirige a la lista para que recargar no repita el pedido; uno rechazado
vuelve a mostrarla con el motivo. La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from evaluon.audit.models import Channel
from evaluon.portal.models import PortalLink
from evaluon.portal.services import links as services

TEMPLATE = "portal/links.html"


@require_http_methods(["GET", "POST"])
def links(request):
    error = ""
    if request.method == "POST":
        try:
            link = services.register_link(request.user, request.POST.get("url", ""),
                                          channel=Channel.SCREEN)
        except services.LinkRefused as refused:
            error = str(refused)
        else:
            return redirect(reverse("portal:proposal", args=[link.pk]))
    rows = services.list_links(request.user, channel=Channel.SCREEN)
    return render(request, TEMPLATE, {
        "rows": rows, "error": error,
        "url": request.POST.get("url", "") if error else ""})


@require_POST
def stop_following(request, link_id):
    try:
        services.stop_following(request.user, link_id, channel=Channel.SCREEN)
    except PortalLink.DoesNotExist:
        raise Http404("No hay un enlace con ese número.")
    return redirect(reverse("portal:links"))
