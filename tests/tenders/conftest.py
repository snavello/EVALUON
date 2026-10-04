"""Fixtures de la feature 003 (pliego y matriz).

- Usuarios de prueba de la Comisión (T-068; plan 003, "Roles"): `operator_user` y
  `evaluator_user`, con rol de lectura de la normativa, y `no_commission_user`, con rol
  de lectura y escritura de la normativa pero sin rol de la Comisión. Las claves son
  sintéticas y solo existen en la base de pruebas que pytest-django crea y borra (P4).
"""

import pytest

from tests.conftest import TEST_PASSWORD


def _make_user(username, commission_role, role):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username=username,
        password=TEST_PASSWORD,
        role=role,
        commission_role=commission_role,
    )


@pytest.fixture
def operator_user(db):
    """Operador de la Comisión: registra procedimientos, carga pliegos y propone
    correcciones a la matriz."""
    from evaluon.accounts.models import CommissionRole, Role

    return _make_user("operador", CommissionRole.OPERATOR, Role.READ)


@pytest.fixture
def evaluator_user(db):
    """Evaluador de la Comisión: todo lo del operador y, además, confirma, elige la
    consecuencia y valida."""
    from evaluon.accounts.models import CommissionRole, Role

    return _make_user("evaluador", CommissionRole.EVALUATOR, Role.READ)


@pytest.fixture
def no_commission_user(db):
    """Usuario sin rol de la Comisión, aunque escriba en la normativa."""
    from evaluon.accounts.models import CommissionRole, Role

    return _make_user("sin-comision", CommissionRole.NONE, Role.READ_WRITE)
