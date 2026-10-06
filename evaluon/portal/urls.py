"""Rutas de la importación desde el Portal, bajo `importar/` (plan 012, "Pantalla")."""

from django.urls import path

from evaluon.portal.views import imported, links, proposal

app_name = "portal"

urlpatterns = [
    path("", links.links, name="links"),
    path("<int:link_id>/", proposal.proposal, name="proposal"),
    path("<int:link_id>/decidir/", proposal.decide, name="decide"),
    path("<int:link_id>/importado/", imported.imported, name="imported"),
    path("<int:link_id>/archivo/<int:file_id>/", imported.download, name="download"),
    path("<int:link_id>/dejar-de-seguir/", links.stop_following, name="stop_following"),
    path("<int:link_id>/revisar-ahora/", links.review_now, name="review_now"),
]
