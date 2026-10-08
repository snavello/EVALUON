"""Rutas del recorrido de la 013, bajo `recorrido/` (plan 013, «Rutas»), y las de la aplicación por
secciones, bajo `expedientes/` (plan 014, «Rutas»).

Las pantallas del recorrido siguen funcionando hasta que T-219 las redirija a su sección. Las
rutas de acción de cada tema las suma `temas.url_patterns()`: después de T-192 nadie vuelve a
tocar este archivo."""

from django.urls import path

from evaluon.journey import temas
from evaluon.journey.sections import SECTIONS
from evaluon.journey.views import index, portada, procedure, stages

app_name = "journey"

urlpatterns = [
    path("", index.index, name="index"),
    path("<int:procedure_id>/", procedure.procedure, name="procedure"),
    path("<int:procedure_id>/etapas/", stages.stages, name="stages"),
]

# Se incluye en `evaluon/urls.py` con el espacio de nombres `expedientes`.
expedientes_urlpatterns = [
    path("", portada.lista, name="index"),
    path("<int:procedure_id>/", portada.portada, name="portada"),
    path("<int:procedure_id>/barra/", portada.barra, name="barra"),
    path("<int:procedure_id>/ventana/", portada.ventana, name="ventana"),
    *[path(f"<int:procedure_id>/{module.SLUG}/", portada.seccion, {"key": module.KEY},
           name=module.KEY) for module in SECTIONS],
    *temas.url_patterns(),
]
