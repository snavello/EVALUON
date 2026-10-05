"""Importación desde el Portal de Compras (feature 012; ADR-0030)."""

from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "evaluon.portal"
    label = "portal"
    verbose_name = "Importación desde el Portal de Compras"
