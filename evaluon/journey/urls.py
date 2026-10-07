"""Rutas del recorrido, bajo `recorrido/` (plan 013, "Rutas")."""

from django.urls import path

from evaluon.journey.views import index, procedure, stages

app_name = "journey"

urlpatterns = [
    path("", index.index, name="index"),
    path("<int:procedure_id>/", procedure.procedure, name="procedure"),
    path("<int:procedure_id>/etapas/", stages.stages, name="stages"),
]
