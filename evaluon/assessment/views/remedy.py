"""Subsanación desde la página del par: pedirla, agregar el documento y evaluar de nuevo
(REQ-060; plan 004, "Subsanación"; T-154).

Son POST del evaluador; el rol y las reglas las comprueba la función de negocio
(`services/remedy.py`): sin rol, "acceso denegado" (403); un pedido inválido vuelve a la página
del par con el motivo (422).
"""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.assessment.models import Result
from evaluon.assessment.services import evaluate, remedy
from evaluon.assessment.views.results import render_pair
from evaluon.audit.models import Channel
from evaluon.offers.services import offers as offers_service


def _result(result_id):
    try:
        return Result.objects.select_related("offer", "requirement").get(pk=result_id)
    except Result.DoesNotExist:
        raise Http404("No hay un resultado con ese número.")


def _back(result):
    return redirect(reverse("assessment:pair", args=[result.offer_id, result.requirement_id]))


def _refused(request, result, error):
    return render_pair(request, result.offer_id, result.requirement_id, error=str(error),
                       status=422)


@require_POST
def request_remedy(request, result_id):
    """Pide la subsanación del resultado."""
    result = _result(result_id)
    try:
        remedy.request_remedy(request.user, result_id, request.POST.get("note", ""),
                              channel=Channel.SCREEN)
    except remedy.RemedyRefused as error:
        return _refused(request, result, error)
    return _back(result)


@require_POST
def add_document(request, result_id):
    """Agrega a la oferta el documento (o la hoja de compliance) de la subsanación."""
    result = _result(result_id)
    upload = request.FILES.get("file")
    try:
        remedy.add_document(
            request.user, result_id, data=upload.read() if upload is not None else b"",
            file_name=upload.name if upload is not None else "",
            note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except (remedy.RemedyRefused, offers_service.OfferRefused) as error:
        return _refused(request, result, error)
    return _back(result)


@require_POST
def reevaluate(request, result_id):
    """Pide evaluar de nuevo el requisito con el documento agregado."""
    result = _result(result_id)
    try:
        remedy.reevaluate(request.user, result_id, channel=Channel.SCREEN)
    except (remedy.RemedyRefused, evaluate.EvaluationRefused) as error:
        return _refused(request, result, error)
    return _back(result)
