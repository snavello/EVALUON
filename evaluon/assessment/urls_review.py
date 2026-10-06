"""Rutas de la revisión de cada propuesta (T-153); `urls.py` las suma."""

from django.urls import path

from evaluon.assessment.views import review

urlpatterns = [
    path("resultado/<int:result_id>/decidir/", review.decide, name="decide"),
    path("par/<int:offer_id>/<int:requirement_id>/historial/", review.history,
         name="history"),
]
