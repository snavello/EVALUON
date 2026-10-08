"""Rutas del recorrido de la 013, bajo `recorrido/` (plan 013, «Rutas»), y las de la aplicación por
secciones, bajo `expedientes/` (plan 014, «Rutas»).

Las pantallas del recorrido redirigen a su sección (T-219). Las
rutas de acción de cada tema las suma `temas.url_patterns()`: después de T-192 nadie vuelve a
tocar este archivo. Lo único propio de este archivo son las del alta sin procedimiento
(`nuevo/`, T-195), que no cuelgan de un procedimiento."""

from django.urls import include, path

from evaluon.journey import temas
from evaluon.journey.sections import SECTIONS
from evaluon.journey.temas import s1_pliego
from evaluon.journey.views import index, nuevo, portada, procedure, stages

app_name = "journey"

urlpatterns = [
    path("", index.index, name="index"),
    path("<int:procedure_id>/", procedure.procedure, name="procedure"),
    path("<int:procedure_id>/etapas/", stages.stages, name="stages"),
]

# Se incluye en `evaluon/urls.py` con el espacio de nombres `expedientes`.
# Se incluye en `evaluon/urls.py` con el espacio de nombres `expedientes`.
expedientes_urlpatterns = [
    path("", portada.lista, name="index"),
    path("nuevo/", nuevo.nuevo, name="nuevo"),
    # El alta subiendo el pliego (T-197): las rutas las define el tema s1_pliego.
    path("nuevo/pliego/", include(s1_pliego.draft_urlpatterns)),
    path("nuevo/<int:link_id>/", nuevo.enlace, name="nuevo_enlace"),
    path("nuevo/<int:link_id>/decidir/", nuevo.decidir, name="nuevo_decidir"),
    path("nuevo/<int:link_id>/revisar/", nuevo.revisar, name="nuevo_revisar"),
    path("nuevo/<int:link_id>/dejar-de-seguir/", nuevo.dejar, name="nuevo_dejar"),
    path("<int:procedure_id>/", portada.portada, name="portada"),
    path("<int:procedure_id>/barra/", portada.barra, name="barra"),
    path("<int:procedure_id>/ventana/", portada.ventana, name="ventana"),
    *[path(f"<int:procedure_id>/{module.SLUG}/", portada.seccion, {"key": module.KEY},
           name=module.KEY) for module in SECTIONS],
    *temas.url_patterns(),
]
