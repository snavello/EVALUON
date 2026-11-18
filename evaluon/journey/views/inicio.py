"""Entrada de la aplicación (REQ-075, REQ-150): `/` muestra la misma lista de procedimientos
abiertos que `expedientes/` (T-357, plan 018). Ya no hay "último procedimiento visto" ni cookie.
Sin rol de la Comisión, `/` sigue llevando a la consulta; sin ningún procedimiento, a la
pantalla «Nuevo procedimiento»."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from evaluon.journey.views import portada
from evaluon.tenders.models import Procedure


@require_GET
@login_required
def inicio(request):
    if not request.user.commission_role:
        return redirect("queries:screen")
    if not Procedure.objects.exists():
        return redirect("expedientes:nuevo")
    return portada.lista(request)
