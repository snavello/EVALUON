"""Guardado de claves (T-006, REQ-016 y requisito no funcional "Claves").

La clave se guarda con Argon2id y parámetros iguales o superiores al mínimo de OWASP
(19 MiB de memoria, 2 iteraciones, 1 hilo). Mínimo de 15 caracteres, sin reglas de
composición.
"""

import argon2
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from tests.conftest import TEST_PASSWORD

OWASP_MIN_MEMORY_KIB = 19 * 1024
OWASP_MIN_TIME_COST = 2
OWASP_MIN_PARALLELISM = 1


def test_argon2_is_the_first_hasher():
    """REQ-016: Argon2 es el primer algoritmo; con él se guardan las claves nuevas."""
    assert settings.PASSWORD_HASHERS[0] == (
        "django.contrib.auth.hashers.Argon2PasswordHasher"
    )


@pytest.mark.django_db
def test_stored_password_is_argon2id_and_not_readable(read_user):
    """REQ-016: la clave guardada no es legible, lleva el identificador de Argon2id y
    sus parámetros igualan o superan el mínimo de OWASP."""
    stored = get_user_model().objects.get(pk=read_user.pk).password

    assert TEST_PASSWORD not in stored
    assert stored.startswith("argon2$argon2id$")

    params = argon2.extract_parameters(stored.removeprefix("argon2"))
    assert params.type is argon2.Type.ID
    assert params.memory_cost >= OWASP_MIN_MEMORY_KIB
    assert params.time_cost >= OWASP_MIN_TIME_COST
    assert params.parallelism >= OWASP_MIN_PARALLELISM

    user = get_user_model().objects.get(pk=read_user.pk)
    assert user.check_password(TEST_PASSWORD)
    assert not user.check_password(TEST_PASSWORD + "x")


def test_password_of_14_characters_is_rejected():
    """REQ-016: una clave de 14 caracteres se rechaza (mínimo de 15)."""
    with pytest.raises(ValidationError):
        validate_password("abcdefghijklmn")


@pytest.mark.parametrize(
    "password", ["abcdefghijklmno", "aaaaaaaaaaaaaaa", "123456789012345"]
)
def test_password_of_15_characters_is_accepted_without_composition_rules(password):
    """REQ-016: 15 caracteres alcanzan; no se exigen mayúsculas, números ni símbolos,
    ni se rechazan claves solo numéricas."""
    validate_password(password)
