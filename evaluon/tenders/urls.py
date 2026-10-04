"""Rutas de pliegos y matriz, bajo `procedimientos/` (plan 003, "Pantalla"). La lista de
procedimientos con el formulario para registrar es la raíz (T-069); cada procedimiento
tiene su página con sus documentos y el formulario de carga, y cada documento, su
original (T-072)."""

from django.urls import path

from evaluon.tenders.views import (
    consequences,
    discarded,
    documents,
    export,
    matrix,
    procedures,
    review,
    validation,
)

app_name = "tenders"

urlpatterns = [
    path("", procedures.procedures, name="procedures"),
    path("<int:procedure_id>/", documents.procedure, name="procedure"),
    path("<int:procedure_id>/matriz/proponer/", matrix.request_proposal,
         name="request_matrix"),
    path("matrices/<int:version_id>/", matrix.matrix, name="matrix"),
    path("matrices/<int:version_id>/cobertura/", matrix.coverage, name="coverage"),
    path("matrices/<int:version_id>/imprimir/", export.print_view, name="print"),
    path("matrices/<int:version_id>/pdf/", export.pdf, name="pdf"),
    path("matrices/<int:version_id>/confirmar/", review.confirm, name="review_confirm"),
    path("matrices/<int:version_id>/agregar/", review.add, name="review_add"),
    path("matrices/<int:version_id>/agregar-tecnico/", review.add_technical,
         name="review_add_technical"),
    path("matrices/<int:version_id>/sumar-tramo/", review.join_segment,
         name="review_join_segment"),
    path("matrices/<int:version_id>/descartadas/", discarded.listing, name="discarded"),
    path("matrices/<int:version_id>/descartadas/devolver/", discarded.restore,
         name="discarded_restore"),
    path("matrices/<int:version_id>/grupo/", review.group, name="group_review"),
    path("matrices/<int:version_id>/validar/", validation.validate, name="validate"),
    path("matrices/<int:version_id>/descartar/", validation.discard, name="discard"),
    path("<int:procedure_id>/matriz/nueva-version/", validation.open_new,
         name="open_new_version"),
    path("requisitos/<int:requirement_id>/corregir/", review.correct,
         name="review_correct"),
    path("requisitos/<int:requirement_id>/quitar/", review.remove, name="review_remove"),
    path("requisitos/<int:requirement_id>/restituir/", review.restore,
         name="review_restore"),
    path("requisitos/<int:requirement_id>/historial/", review.history, name="history"),
    path("requisitos/<int:requirement_id>/consecuencia/", consequences.choose,
         name="consequence_choose"),
    path("pendientes/<int:pending_id>/resolver/", review.resolve, name="review_resolve"),
    path(
        "documentos/<int:document_id>/original/",
        documents.document_original,
        name="document_original",
    ),
]
