"""Subir la hoja de compliance de una oferta y pedir la reevaluación de sus requisitos externos
(REQ-073; T-189).

Son POST del evaluador desde la matriz de evaluación; el rol y las reglas las comprueba la
función de negocio (`services/compliance.py`): sin rol, "acceso denegado" (403); un pedido
inválido vuelve a la matriz con el motivo (422). La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.assessment.services import compliance, evaluate
from evaluon.assessment.views.matrix import _render
from evaluon.audit.models import Channel
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service


def _offer(offer_id):
    try:
        return Offer.objects.select_related("procedure").get(pk=offer_id)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número.")


def _back(offer):
    return redirect(reverse("assessment:matrix", args=[offer.procedure_id])
                    + f"#oferta-{offer.number}")


def _refused(request, offer, error):
    return _render(request, offer.procedure_id, compliance_error=str(error),
                   compliance_offer=offer.pk, status=422)


@require_POST
def upload(request, offer_id):
    """Sube la hoja de compliance de la oferta."""
    offer = _offer(offer_id)
    upload_file = request.FILES.get("file")
    try:
        compliance.upload_sheet(
            request.user, offer_id,
            data=upload_file.read() if upload_file is not None else b"",
            file_name=upload_file.name if upload_file is not None else "",
            note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except (compliance.ComplianceRefused, offers_service.OfferRefused) as error:
        return _refused(request, offer, error)
    return _back(offer)


@require_POST
def reevaluate(request, offer_id):
    """Pide evaluar de nuevo los requisitos externos de la oferta con su hoja."""
    offer = _offer(offer_id)
    try:
        compliance.reevaluate_externals(request.user, offer_id, channel=Channel.SCREEN)
    except (compliance.ComplianceRefused, evaluate.EvaluationRefused) as error:
        return _refused(request, offer, error)
    return _back(offer)
