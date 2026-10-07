"""Rutas de la hoja de compliance por oferta (T-189); `urls.py` las suma a las del espacio
`assessment`."""

from django.urls import path

from evaluon.assessment.views import compliance

urlpatterns = [
    path("oferta/<int:offer_id>/hoja-de-compliance/", compliance.upload,
         name="compliance_upload"),
    path("oferta/<int:offer_id>/hoja-de-compliance/evaluar/", compliance.reevaluate,
         name="compliance_reevaluate"),
]
