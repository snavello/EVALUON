"""Rutas de EVALUON. La raíz la ocupa la pantalla de consulta (T-016); los
procedimientos, pliegos y matrices van bajo `procedimientos/` (T-069) y las ofertas y sus
fichas, bajo `ofertas/` (T-130). La aplicación por secciones (feature 014) va bajo
`expedientes/`; `recorrido/` sigue con las pantallas de la 013 hasta que T-219 las redirija."""

from django.urls import include, path

from evaluon.journey.urls import expedientes_urlpatterns

urlpatterns = [
    path("", include("evaluon.accounts.urls")),
    path("normas/", include("evaluon.norms.urls")),
    path("expedientes/", include((expedientes_urlpatterns, "expedientes"))),
    path("recorrido/", include("evaluon.journey.urls")),
    path("procedimientos/", include("evaluon.tenders.urls")),
    path("ofertas/", include("evaluon.offers.urls")),
    path("evaluacion/", include("evaluon.assessment.urls")),
    path("importar/", include("evaluon.portal.urls")),
    path("", include("evaluon.queries.urls")),
]
