"""Fixtures comunes de la suite de EVALUON.

Usuarios de prueba de los dos roles (T-006, REQ-016). Las claves son sintéticas y solo
existen en la base de pruebas que pytest-django crea y borra.
"""

import pytest

# Clave sintética de 15 caracteres o más, el mínimo de la feature (plan 001, ADR-0005).
TEST_PASSWORD = "clave-sintetica-de-prueba"


@pytest.fixture
def read_user(db):
    """Usuario con rol de lectura: consulta y busca."""
    from django.contrib.auth import get_user_model

    from evaluon.accounts.models import Role

    return get_user_model().objects.create_user(
        username="lectura", password=TEST_PASSWORD, role=Role.READ
    )


@pytest.fixture
def read_write_user(db):
    """Usuario con rol de lectura y escritura: además carga y valida normas."""
    from django.contrib.auth import get_user_model

    from evaluon.accounts.models import Role

    return get_user_model().objects.create_user(
        username="escritura", password=TEST_PASSWORD, role=Role.READ_WRITE
    )
