"""Rutas de pliegos y matriz, bajo `procedimientos/` (plan 003, "Pantalla"). La lista de
procedimientos con el formulario para registrar es la raíz (T-069); cada procedimiento
tiene su página con sus documentos y el formulario de carga, y cada documento, su
original (T-072)."""

from django.urls import path

from evaluon.tenders.views import documents, procedures

app_name = "tenders"

urlpatterns = [
    path("", procedures.procedures, name="procedures"),
    path("<int:procedure_id>/", documents.procedure, name="procedure"),
    path(
        "documentos/<int:document_id>/original/",
        documents.document_original,
        name="document_original",
    ),
]
