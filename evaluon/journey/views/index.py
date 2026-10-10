"""Entrada del recorrido de la 013 (REQ-065, REQ-071). Desde T-219 ya no es una pantalla: la
lista de procedimientos y el alta viven en el desplegable del encabezado y en «Nuevo
procedimiento», y esta dirección lleva a la entrada de la aplicación."""

from django.shortcuts import redirect
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    return redirect("inicio")
