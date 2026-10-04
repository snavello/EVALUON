"""Elegir la consecuencia de un requisito desde la página de la matriz (REQ-029; plan 003,
"Pantalla"; ADR-0005; T-081).

El formulario se envía por POST, llama a `services.consequences.choose` y vuelve a la matriz,
en el requisito tocado. Una elección rechazada (sin motivo, sin condición, «no determinada»,
sin tramo) vuelve a mostrar la matriz con el motivo, sin cambiar nada. Sin el rol de
evaluador, "acceso denegado" (403) y el rechazo queda registrado. No guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.audit.models import Channel
from evaluon.tenders.models import Requirement
from evaluon.tenders.services import consequences as service
from evaluon.tenders.services import matrix_page as pages

MATRIX_TEMPLATE = "tenders/matrix.html"


@require_POST
def choose(request, requirement_id):
    try:
        requirement = Requirement.objects.get(pk=requirement_id)
    except Requirement.DoesNotExist:
        raise Http404("No hay un requisito con ese número.")
    post = request.POST
    try:
        service.choose(
            request.user, requirement_id,
            option=post.get("option") or None,
            consequence_type=post.get("consequence_type") or None,
            note=post.get("note", ""), segment=post.get("segment") or None,
            quote=post.get("quote", ""), channel=Channel.SCREEN)
    except service.ChoiceRefused as error:
        page = pages.matrix_page(request.user, requirement.version_id,
                                 channel=Channel.SCREEN)
        return render(request, MATRIX_TEMPLATE, {
            "page": page, "review_error": str(error),
            "review_error_field": error.field, "review_error_requirement": requirement.pk,
        }, status=400)
    url = reverse("tenders:matrix", args=[requirement.version_id])
    return redirect(f"{url}#requisito-{requirement.number}")
