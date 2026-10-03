"""Rutas de ingreso y salida (REQ-016)."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from evaluon.accounts.views import LoginView

app_name = "accounts"

urlpatterns = [
    path("ingresar/", LoginView.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
]
