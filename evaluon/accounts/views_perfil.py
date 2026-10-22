"""Preferencias del perfil del usuario (REQ-134; ADR-0074).

Por ahora solo el tema de la pantalla. Cambiarlo no es una acción de decisión de la Comisión ni
interviene en ninguna evaluación, así que lo puede hacer cualquier usuario con sesión, también el de
lectura, y no deja registro de auditoría (P6 pide registrar los pasos en que interviene la IA).
"""

from urllib.parse import urlsplit

from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from evaluon.accounts.models import Theme


def _same_site(request, url):
    return bool(url) and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure())


def _back(request):
    """A dónde volver. `next` (del formulario o de la dirección del formulario) solo vale si es
    del mismo sitio; si no, o si falta, la entrada. Si el Referer es del mismo sitio y de la misma
    ruta que `next`, se vuelve a él para conservar la consulta (`?oferta=…`, `?tipo=…`)."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if not _same_site(request, target):
        return reverse("inicio")
    referer = request.headers.get("Referer", "")
    if _same_site(request, referer):
        seen, wanted = urlsplit(referer), urlsplit(target)
        kept = seen.path + (f"?{seen.query}" if seen.query else "")
        if seen.path == wanted.path and _same_site(request, kept):  # `//otro.sitio` no pasa
            return kept
    return target


@require_POST
def tema(request):
    """Guarda el tema elegido (`claro` o `negro`) y vuelve a la página de origen.

    El valor se valida contra la lista cerrada del modelo. La exigencia de sesión la pone el
    middleware de ingreso y la de CSRF, el de Django.
    """
    value = request.POST.get("tema", "")
    if value not in Theme.values:
        return HttpResponseBadRequest("Tema no válido: use «claro» o «negro».")
    request.user.theme = value
    request.user.save(update_fields=["theme"])
    return redirect(_back(request))
