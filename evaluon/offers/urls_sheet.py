"""Rutas de la ficha (T-130) y de su revisión (T-132)."""

from django.urls import path

from evaluon.offers.views import sheet

urlpatterns = [
    path("<int:offer_id>/ficha/armar/", sheet.build, name="build_sheet"),
    path("fichas/<int:sheet_id>/", sheet.sheet, name="sheet"),
    path("fichas/<int:sheet_id>/confirmar/", sheet.confirm, name="confirm_entries"),
    path("fichas/filas/<int:entry_id>/", sheet.entry_history, name="entry_history"),
    path("fichas/filas/<int:entry_id>/agregar/", sheet.add, name="add_fragment"),
    path("fichas/fragmentos/<int:fragment_id>/<str:action>/", sheet.fragment_action,
         name="fragment_action"),
]
