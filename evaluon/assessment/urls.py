"""Rutas de la evaluación asistida, bajo `evaluacion/` (plan 004, "Pantalla"; T-150). Las
pantallas de la matriz, la revisión y las preguntas suman sus rutas en archivos aparte
(`urls_matrix.py`, `urls_review.py`, `urls_questions.py`)."""

from django.urls import include, path

from evaluon.assessment import urls_matrix, urls_technical
from evaluon.assessment.views import results

app_name = "assessment"

urlpatterns = [
    path("", include("evaluon.assessment.urls_review")),
    path("", include("evaluon.assessment.urls_questions")),
    path("par/<int:offer_id>/<int:requirement_id>/", results.pair, name="pair"),
    path("par/<int:offer_id>/<int:requirement_id>/pagina/<int:document_id>/<int:page>/",
         results.vision_page, name="vision_page"),
    *urls_matrix.urlpatterns,
    *urls_technical.urlpatterns,
]
