"""Régimen aplicado a una fecha (T-009; plan 001, "Unidades consultables a una fecha" y
"Fecha de autorización y régimen aplicado").

`applicable_regimes(fecha)` devuelve las normas con `general_regime` verdadero que tienen
al menos una unidad consultable y no derogada a esa fecha. Los datos son sintéticos.
"""

from datetime import date

import pytest
from django.db import connection


def regimes(reference_date):
    with connection.cursor() as cursor:
        cursor.execute("SELECT norm_id FROM applicable_regimes(%s)", [reference_date])
        rows = [row[0] for row in cursor.fetchall()]
    assert len(rows) == len(set(rows)), "una norma aparece más de una vez"
    return set(rows)


@pytest.mark.django_db
def test_two_regimes_before_v_the_first(two_regimes):
    """REQ-020: con una fecha anterior a V, el régimen aplicado es el primero."""
    assert regimes(two_regimes.before_v) == {two_regimes.old.pk}


@pytest.mark.django_db
@pytest.mark.parametrize("when", ["v", "after_v"])
def test_two_regimes_from_v_the_second(two_regimes, when):
    """REQ-020: con V o una fecha posterior, el régimen aplicado es el segundo."""
    assert regimes(getattr(two_regimes, when)) == {two_regimes.new.pk}


@pytest.mark.django_db
def test_two_regimes_before_both_none(two_regimes):
    """REQ-020: con una fecha anterior a los dos regímenes no hay régimen aplicado."""
    assert regimes(two_regimes.before_all) == set()


@pytest.mark.django_db
def test_only_general_regimes_with_validated_units_count(
    make_norm, make_document, make_reading
):
    """REQ-020, REQ-005: una norma sin la marca de régimen general no es un régimen
    aplicado aunque sea consultable; un régimen general cuya lectura no está validada
    tampoco."""
    plain = make_norm()
    make_reading(make_document(plain), [("art-1", "Norma común.")])
    unvalidated = make_norm(general_regime=True)
    make_reading(make_document(unvalidated), [("art-1", "Régimen sin validar.")],
                 status="pending")
    validated = make_norm(general_regime=True)
    make_reading(make_document(validated), [("art-1", "Régimen validado.")])

    assert regimes(date(2024, 1, 1)) == {validated.pk}


@pytest.mark.django_db
def test_partly_repealed_regime_still_applies(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-020: un régimen con una parte derogada sigue aplicando mientras tenga alguna
    unidad sin derogar; derogado entero, deja de aplicar."""
    regime = make_norm(general_regime=True)
    make_reading(make_document(regime), [("art-1", "Uno."), ("art-2", "Dos.")])
    make_relation(make_norm(), regime, "deroga", target_unit_key="art-1",
                  effective_date=date(2020, 1, 1))
    make_relation(make_norm(), regime, "deroga", effective_date=date(2022, 1, 1))

    assert regimes(date(2021, 1, 1)) == {regime.pk}
    assert regimes(date(2022, 1, 1)) == set()


@pytest.mark.django_db
def test_two_regimes_day_before_v_the_first(two_regimes):
    """REQ-020: el día anterior a V (2022-12-31) el régimen aplicado es el primero."""
    assert two_regimes.v == date(2023, 1, 1)
    assert regimes(date(2022, 12, 31)) == {two_regimes.old.pk}
