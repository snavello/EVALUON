"""Rutas de ofertas y documentos (T-130). T-131 completa esta pantalla."""

from django.urls import path

from evaluon.offers.views import documents

urlpatterns = [
    path("procedimiento/<int:procedure_id>/", documents.procedure_offers,
         name="procedure_offers"),
    path("<int:offer_id>/", documents.offer, name="offer"),
    path("documentos/<int:document_id>/original/", documents.document_original,
         name="document_original"),
]
