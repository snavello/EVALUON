"""Ofertas y ficha por oferta (feature 008; ADR-0026)."""

from django.apps import AppConfig


class OffersConfig(AppConfig):
    name = "evaluon.offers"
    label = "offers"
    verbose_name = "Ofertas y fichas"
