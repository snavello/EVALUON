"""Normativa: normas, documentos, lecturas, unidades, pasajes, relaciones, versiones y
modificatorias sin cargar (plan 001, "Modelo de datos")."""

from django.apps import AppConfig


class NormsConfig(AppConfig):
    name = "evaluon.norms"
    label = "norms"
    verbose_name = "Normativa"
