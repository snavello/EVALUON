"""Entrada del recorrido (REQ-065, REQ-071; plan 013).

Una fila por procedimiento, el más reciente primero, con su etapa actual, sus pendientes y
sus sugerencias. El alta empieza por explorar el Portal (el formulario envía a `portal:links`)
y la carga a mano queda como alternativa. También lista lo que trajo el Portal.
"""

from dataclasses import dataclass

from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey.stages import Journey, stages_for
from evaluon.portal.services import links as portal_links
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.index.index"


@dataclass
class Row:
    procedure: Procedure
    journey: Journey


@require_GET
def index(request):
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.SCREEN)
    rows = [Row(procedure=p, journey=stages_for(request.user, p, channel=Channel.SCREEN))
            for p in Procedure.objects.order_by("-created_at", "-pk")]
    portal_rows = portal_links.list_links(request.user, channel=Channel.SCREEN)
    return render(request, "journey/index.html", {"rows": rows, "portal_rows": portal_rows})
