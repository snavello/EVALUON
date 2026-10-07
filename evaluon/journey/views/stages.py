"""Solo el bloque de las etapas, lo que pide el sondeo (REQ-067). Devuelve el HTML del
bloque sin pasar por `base.html`: así no consume el aviso de fin de pedidos (que lo entrega
una sola vez y lo marca como visto)."""

from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.journey.views.procedure import get_journey
from evaluon.journey.window import window_for


@require_GET
def stages(request, procedure_id):
    journey = get_journey(request, procedure_id)
    response = render(request, "journey/_stages.html", {"journey": journey, "window": window_for(journey.procedure)})
    response["Cache-Control"] = "no-store"
    return response
