"""Dar y retirar el ok de la Comisión al informe técnico de una oferta (REQ-061; plan 004, "Ok
del informe técnico"; T-168).

Son POST del evaluador desde la matriz; el rol y las reglas las comprueba la función de negocio
(`services/technical.py`): sin rol, "acceso denegado" (403); un ok inválido vuelve a la matriz con
el motivo (422). La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.assessment.services import technical
from evaluon.assessment.views.matrix import _render
from evaluon.audit.models import Channel
from evaluon.offers.models import Offer


def _offer(offer_id):
    try:
        return Offer.objects.select_related("procedure").get(pk=offer_id)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número.")


def _items(post):
    """`None` si se marcó "todo el informe"; si no, los renglones marcados."""
    if post.get("all"):
        return None
    return post.getlist("item")


def _back(offer):
    return redirect(reverse("assessment:matrix", args=[offer.procedure_id])
                    + f"#oferta-{offer.number}")


@require_POST
def give(request, offer_id):
    """Da el ok del informe técnico."""
    offer = _offer(offer_id)
    items = _items(request.POST)
    scope = items if items is not None else [
        str(i) for i in technical.item_rows(offer)]
    verdicts = {i: request.POST.get(f"verdict_{i}", "") for i in scope}
    try:
        technical.give_ok(request.user, offer, items=items, verdicts=verdicts,
                          note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except technical.TechnicalRefused as error:
        return _render(request, offer.procedure_id, technical_error=str(error),
                       technical_offer=offer.pk, status=422)
    return _back(offer)


@require_POST
def withdraw(request, offer_id):
    """Retira el ok del informe técnico."""
    offer = _offer(offer_id)
    try:
        technical.withdraw_ok(request.user, offer, items=_items(request.POST),
                              note=request.POST.get("note", ""), channel=Channel.SCREEN)
    except technical.TechnicalRefused as error:
        return _render(request, offer.procedure_id, technical_error=str(error),
                       technical_offer=offer.pk, status=422)
    return _back(offer)
