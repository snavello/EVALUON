"""Evaluación asistida de ofertas (feature 004; ADR-0039)."""

from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    name = "evaluon.assessment"
    label = "assessment"
    verbose_name = "Evaluación de ofertas"
