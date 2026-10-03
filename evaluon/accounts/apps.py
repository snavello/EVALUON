"""Usuarios, roles, ingreso y salida (REQ-016)."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "evaluon.accounts"
    label = "accounts"
    verbose_name = "Usuarios"
