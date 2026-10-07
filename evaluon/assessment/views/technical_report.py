"""Subir el informe técnico del área y pedir que el sistema proponga (REQ-074; T-190).

Son POST del evaluador desde la matriz de evaluación; el rol y las reglas las comprueba la
función de negocio (`services/technical_report.py`): sin rol, "acceso denegado" (403); un pedido
inválido vuelve a la matriz con el motivo (422). La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.assessment.services import technical_report as service
from evaluon.assessment.views.matrix import _render
from evaluon.audit.models import Channel
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service
from evaluon.tenders.models import Procedure


def _offer(offer_id):
    try:
        return Offer.objects.select_related("procedure").get(pk=offer_id)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número.")


def _back(procedure_id, anchor=""):
    return redirect(reverse("assessment:matrix", args=[procedure_id]) + anchor)


def _refused(request, procedure_id, error, offer=None):
    return _render(request, procedure_id, report_error=str(error),
                   report_offer=offer.pk if offer else None, status=422)


def _file(request):
    upload = request.FILES.get("file")
    return (upload.read() if upload is not None else b"",
            upload.name if upload is not None else "")


@require_POST
def upload_for_offer(request, offer_id):
    """Sube el informe técnico del área de una oferta."""
    offer = _offer(offer_id)
    data, name = _file(request)
    try:
        service.upload_report(request.user, offer_id=offer.pk, data=data, file_name=name,
                              note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except (service.ReportRefused, offers_service.OfferRefused) as error:
        return _refused(request, offer.procedure_id, error, offer)
    return _back(offer.procedure_id, f"#oferta-{offer.number}")


@require_POST
def upload_for_procedure(request, procedure_id):
    """Sube el informe técnico del área que rige para todo el procedimiento."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    data, name = _file(request)
    try:
        service.upload_report(request.user, procedure_id=procedure.pk, data=data,
                              file_name=name, note=request.POST.get("note", ""),
                              channel=Channel.SCREEN)
    except (service.ReportRefused, offers_service.OfferRefused) as error:
        return _refused(request, procedure.pk, error)
    return _back(procedure.pk)


@require_POST
def propose(request, offer_id):
    """Pide que el sistema proponga de nuevo desde los informes ya leídos de la oferta."""
    offer = _offer(offer_id)
    try:
        service.request_proposal(request.user, offer_id, channel=Channel.SCREEN)
    except service.ReportRefused as error:
        return _refused(request, offer.procedure_id, error, offer)
    return _back(offer.procedure_id, f"#oferta-{offer.number}")
