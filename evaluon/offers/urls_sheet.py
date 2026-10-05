"""Rutas de la ficha (T-130). T-132 suma las de revisión."""

from django.urls import path

from evaluon.offers.views import sheet

urlpatterns = [
    path("<int:offer_id>/ficha/armar/", sheet.build, name="build_sheet"),
    path("fichas/<int:sheet_id>/", sheet.sheet, name="sheet"),
]
