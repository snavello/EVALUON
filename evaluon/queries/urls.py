"""Rutas de la consulta: la pantalla, en `consulta/` (la raíz lleva al último procedimiento, T-219), y la página de una consulta
guardada (T-016). La pregunta se envía a la pantalla, que consulta y redirige a la página
de la consulta guardada (T-019). La búsqueda directa se envía a `buscar/`, que busca y
muestra la pantalla con los resultados (T-041)."""

from django.urls import path

from evaluon.queries import views

app_name = "queries"

urlpatterns = [
    path("consulta/", views.screen, name="screen"),
    path("consultas/<int:pk>/", views.query_detail, name="query"),
    path("buscar/", views.search, name="search"),
]
