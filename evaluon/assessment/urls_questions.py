"""Rutas de las preguntas a la Comisión y de la subsanación (T-154); `urls.py` las suma."""

from django.urls import path

from evaluon.assessment.views import questions, remedy

urlpatterns = [
    path("procedimiento/<int:procedure_id>/preguntas/", questions.question_list,
         name="questions"),
    path("pregunta/<int:question_id>/responder/", questions.answer, name="answer"),
    path("respuesta/<int:answer_id>/evaluar-de-nuevo/", questions.reevaluate,
         name="reevaluate_answer"),
    path("resultado/<int:result_id>/subsanacion/pedir/", remedy.request_remedy,
         name="request_remedy"),
    path("resultado/<int:result_id>/subsanacion/documento/", remedy.add_document,
         name="add_remedy_document"),
    path("resultado/<int:result_id>/subsanacion/evaluar/", remedy.reevaluate,
         name="reevaluate_remedy"),
]
