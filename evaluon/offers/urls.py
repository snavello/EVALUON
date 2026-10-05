"""Rutas de ofertas y fichas, bajo `ofertas/` (plan 008, "Pantalla"). Dos archivos de rutas
separados, uno por pantalla, para que T-131 y T-132 no se pisen."""

from evaluon.offers.urls_documents import urlpatterns as documents_urlpatterns
from evaluon.offers.urls_sheet import urlpatterns as sheet_urlpatterns

app_name = "offers"

urlpatterns = [*documents_urlpatterns, *sheet_urlpatterns]
