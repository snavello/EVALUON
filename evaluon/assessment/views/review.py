"""Decidir sobre la propuesta de un par y ver su historial (REQ-056; plan 004, "Revisión y
decisión"; T-153).

La decisión es un POST del evaluador; el rol y las reglas las comprueba la función de negocio
(`services/review.py`): sin rol, "acceso denegado" (403); una decisión inválida vuelve a la
página del par con el motivo (422). La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.assessment.models import Result
from evaluon.assessment.services import review
from evaluon.assessment.views.results import render_pair
from evaluon.audit.models import Channel

HISTORY_TEMPLATE = "assessment/history.html"


@require_POST
def decide(request, result_id):
    """Confirma, corrige o rechaza la propuesta `result_id`."""
    try:
        result = Result.objects.get(pk=result_id)
    except Result.DoesNotExist:
        raise Http404("No hay un resultado con ese número.")
    try:
        review.decide(request.user, result_id, request.POST.get("action", ""),
                      outcome_after=request.POST.get("outcome_after", ""),
                      note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except review.ReviewRefused as error:
        return render_pair(request, result.offer_id, result.requirement_id,
                           error=str(error), status=422)
    return redirect(reverse("assessment:pair", args=[result.offer_id, result.requirement_id]))


@require_GET
def history(request, offer_id, requirement_id):
    """Todo el recorrido del par."""
    try:
        stages = review.history(request.user, offer_id, requirement_id,
                                channel=Channel.SCREEN)
    except Result.DoesNotExist:
        raise Http404("Ese requisito todavía no se evaluó para esa oferta.")
    first = stages[0].result
    return render(request, HISTORY_TEMPLATE, {
        "offer": first.offer, "requirement": first.requirement, "stages": stages})
