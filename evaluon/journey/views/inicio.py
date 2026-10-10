"""Entrada de la aplicación (T-219, REQ-075): `/` lleva a la pestaña «Procedimiento» del último
procedimiento que abrió el usuario o, si no hay ninguno, al más reciente; sin procedimientos, a
la pantalla «Nuevo procedimiento». El último se recuerda en una cookie del navegador y no en la
sesión: grabar la sesión renovaría el tope de 8 horas desde el ingreso. La cookie solo guarda un
número y se valida contra la base antes de usarse."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.tenders.models import Procedure

COOKIE = "evaluon_ultimo_{}"


def remember(response, user, procedure_id):
    """Anota en el navegador el último procedimiento abierto por `user`."""
    response.set_cookie(COOKIE.format(user.pk), str(procedure_id), samesite="Strict",
                        httponly=True)
    return response


def _last_opened(request):
    raw = request.COOKIES.get(COOKIE.format(request.user.pk), "")
    if raw.isdigit() and Procedure.objects.filter(pk=int(raw)).exists():
        return int(raw)
    return None


@require_GET
@login_required
def inicio(request):
    if not request.user.commission_role:
        return redirect("queries:screen")
    procedure_id = _last_opened(request)
    if procedure_id is None:
        latest = Procedure.objects.order_by("-created_at", "-pk").values_list("pk", flat=True)
        procedure_id = latest.first()
    if procedure_id is None:
        return redirect("expedientes:nuevo")
    return redirect(reverse("expedientes:procedimiento", args=[procedure_id]))
