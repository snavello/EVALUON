"""Rutas de EVALUON. La raíz la ocupa la pantalla de consulta (T-016)."""

from django.urls import include, path

urlpatterns = [
    path("", include("evaluon.accounts.urls")),
]
