"""Página de un par: el resultado vigente de una oferta para un requisito, en solo lectura
(REQ-052, REQ-053, REQ-055; plan 004, "Revisión y decisión"; ADR-0005; T-150).

Muestra el texto del requisito, las citas de la oferta con su documento, página y texto
literal (con el enlace al original en esa página), la norma o la respuesta de la Comisión
rotuladas como tales, la explicación del sistema (rotulada, nunca como cita), el motivo de un
"no determinado" y la pregunta abierta. Todo es una propuesta: la decisión es de la Comisión
(P3). Las acciones de decisión las suma T-153.

La función de negocio comprueba el rol de la Comisión: sin él, "acceso denegado" (403). La vista
no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.assessment.models import Result
from evaluon.assessment.services import evaluate
from evaluon.audit.models import Channel

RESULT_TEMPLATE = "assessment/result.html"


@require_GET
def pair(request, offer_id, requirement_id):
    """El resultado vigente del par."""
    try:
        page = evaluate.pair_page(request.user, offer_id, requirement_id,
                                  channel=Channel.SCREEN)
    except Result.DoesNotExist:
        raise Http404("Ese requisito todavía no se evaluó para esa oferta.")
    return render(request, RESULT_TEMPLATE, {"page": page})
