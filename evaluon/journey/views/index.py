"""Entrada mínima del recorrido (REQ-065, REQ-071; T-183 la completa): los procedimientos con
el enlace a su recorrido y, primero, la exploración del Portal."""

from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.index.index"


@require_GET
def index(request):
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.SCREEN)
    procedures = Procedure.objects.order_by("-created_at", "-pk")
    return render(request, "journey/index.html", {"procedures": procedures})
