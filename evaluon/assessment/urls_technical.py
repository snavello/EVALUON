"""Rutas del ok de la Comisión al informe técnico (T-168); `urls.py` las suma a las del espacio
`assessment`."""

from django.urls import path

from evaluon.assessment.views import technical

urlpatterns = [
    path("oferta/<int:offer_id>/informe-tecnico/ok/", technical.give, name="technical_give"),
    path("oferta/<int:offer_id>/informe-tecnico/retirar/", technical.withdraw,
         name="technical_withdraw"),
]
