"""Rutas de la matriz de evaluación (T-152); `urls.py` las suma a las del espacio
`assessment`."""

from django.urls import path

from evaluon.assessment.views import matrix

urlpatterns = [
    path("procedimiento/<int:procedure_id>/", matrix.matrix, name="matrix"),
    path("procedimiento/<int:procedure_id>/evaluar/", matrix.evaluate_all,
         name="evaluate_all"),
]
