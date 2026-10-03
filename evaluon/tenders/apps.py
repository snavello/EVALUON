"""Procedimientos, pliegos y matriz de cumplimiento (plan 003, "Modelo de datos")."""

from django.apps import AppConfig


class TendersConfig(AppConfig):
    name = "evaluon.tenders"
    label = "tenders"
    verbose_name = "Pliegos y matriz de cumplimiento"
