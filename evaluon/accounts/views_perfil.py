"""Preferencias del perfil del usuario (REQ-134; ADR-0074).

Por ahora solo el tema de la pantalla. Cambiarlo no es una acción de decisión de la Comisión ni
interviene en ninguna evaluación, así que lo puede hacer cualquier usuario con sesión, también el de
lectura, y no deja registro de auditoría (P6 pide registrar los pasos en que interviene la IA).
"""

from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from evaluon.accounts.models import Theme


@require_POST
def tema(request):
    """Guarda el tema elegido (`claro` o `negro`) y vuelve a la página de origen (`next`).

    El valor se valida contra la lista cerrada del modelo; un `next` de otro sitio (o ausente)
    se ignora y se vuelve a la entrada. La exigencia de sesión la pone el middleware de ingreso
    y la de CSRF, el de Django.
    """
    value = request.POST.get("tema", "")
    if value not in Theme.values:
        return HttpResponseBadRequest("Tema no válido: use «claro» o «negro».")
    request.user.theme = value
    request.user.save(update_fields=["theme"])
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = reverse("inicio")
    return redirect(target)
