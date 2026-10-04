"""Rutas de pliegos y matriz, bajo `procedimientos/` (plan 003, "Pantalla"). La lista de
procedimientos con el formulario para registrar es la raíz (T-069)."""

from django.urls import path

from evaluon.tenders.views import procedures

app_name = "tenders"

urlpatterns = [
    path("", procedures.procedures, name="procedures"),
]
