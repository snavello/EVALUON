"""Registro de auditoría (REQ-012, principio P6)."""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "evaluon.audit"
    label = "audit"
    verbose_name = "Registro de auditoría"
