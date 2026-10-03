"""Rutas de la consulta: la pantalla, en la raíz del sitio, y la página de una consulta
guardada (T-016). La pregunta se envía a la pantalla, que consulta y redirige a la página
de la consulta guardada (T-019)."""

from django.urls import path

from evaluon.queries import views

app_name = "queries"

urlpatterns = [
    path("", views.screen, name="screen"),
    path("consultas/<int:pk>/", views.query_detail, name="query"),
]
