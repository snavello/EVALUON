"""Rutas de la importación desde el Portal, bajo `importar/` (plan 012, "Pantalla")."""

from django.urls import path

from evaluon.portal.views import links, proposal

app_name = "portal"

urlpatterns = [
    path("", links.links, name="links"),
    path("<int:link_id>/", proposal.proposal, name="proposal"),
    path("<int:link_id>/decidir/", proposal.decide, name="decide"),
    path("<int:link_id>/dejar-de-seguir/", links.stop_following, name="stop_following"),
]
