"""Indicador de avance del encabezado (REQ-140; plan 017, T-312 y T-330).

Devuelve el fragmento `_avance_encabezado.html`: un anillo con el porcentaje global del pedido en
curso (`window_for(...)["overall_percent"]`: ofertas hechas más el avance de la oferta en curso),
enlazado al primer panel. En espera, o sin un total conocido (matriz, lectura, Portal), el anillo
gira sin porcentaje. Sin pedido activo no dibuja nada. Solo lee (P3)."""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.stages import is_viewer
from evaluon.journey.views.portada import reading
from evaluon.journey.window import window_for
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.avance.avance"


def avance_of(procedure):
    """Lo que dibuja el indicador, o `None` si no hay un pedido en espera ni en curso.
    `percent` es `None` mientras no se sabe (en espera, o un pedido sin total): no se inventa
    (REQ-141); el anillo gira en ese caso."""
    # Una vez por pedido: el primer panel pide la misma ventana (T-336).
    window = memo.once(("window", procedure.pk), lambda: window_for(procedure))
    if not window or not window.get("active"):
        return None
    percent = window["overall_percent"] if window["state"] == "running" else None
    return {"state": window["state"], "state_label": window["state_label"],
            "task": window["task"], "percent": percent,
            "url": reverse("expedientes:procedimiento", args=[procedure.pk])}


@require_GET
@memo.scoped
@reading
def avance(request, procedure_id):
    """Solo el indicador, para el sondeo del encabezado. Sin `base.html`."""
    if not is_viewer(request.user):
        require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                                channel=Channel.SCREEN)
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    response = render(request, "journey/_avance_encabezado.html",
                      {"avance_pedido": avance_of(procedure)})
    response["Cache-Control"] = "no-store"
    return response
