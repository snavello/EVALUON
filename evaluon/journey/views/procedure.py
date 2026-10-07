"""Página de recorrido de un procedimiento (REQ-066, REQ-067, REQ-068)."""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.audit.models import Channel
from evaluon.journey.stages import stages_for
from evaluon.journey.window import window_for
from evaluon.tenders.models import Procedure


def get_journey(request, procedure_id):
    """Las etapas del procedimiento. 404 si no existe; `RoleRejected` (403) sin rol."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    return stages_for(request.user, procedure, channel=Channel.SCREEN)


@require_GET
def procedure(request, procedure_id):
    journey = get_journey(request, procedure_id)
    return render(request, "journey/procedure.html", {
        "journey": journey,
        "window": window_for(journey.procedure),
        "stages_url": reverse("journey:stages", args=[procedure_id]),
        "login_url": reverse("accounts:login"),
    })
