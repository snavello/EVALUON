"""Página de recorrido de un procedimiento (REQ-066, REQ-067, REQ-068). Desde T-219 la página
es la pestaña «Procedimiento» (REQ-075); acá queda el cálculo de las etapas que usa el bloque
del sondeo (`stages.py`)."""

from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from evaluon.audit.models import Channel
from evaluon.journey.legacy import section_url
from evaluon.journey.stages import stages_for
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
    return redirect(section_url("procedimiento", procedure_id))
