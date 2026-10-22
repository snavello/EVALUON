"""Rutas de ingreso y salida (REQ-016)."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from evaluon.accounts import views_fotos, views_perfil
from evaluon.accounts.views import LoginView

app_name = "accounts"

urlpatterns = [
    path("ingresar/", LoginView.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("perfil/tema/", views_perfil.tema, name="tema"),  # REQ-134, ADR-0074
    # Mis fotos (REQ-136, ADR-0073). `photos.Picked.url` usa el nombre `accounts:foto`.
    path("perfil/fotos/", views_fotos.fotos, name="fotos"),
    path("perfil/fotos/<int:pk>/", views_fotos.foto, name="foto"),
    path("perfil/fotos/<int:pk>/quitar/", views_fotos.foto_quitar, name="foto_quitar"),
]
