"""Unidades consultables a una fecha (T-009; plan 001, "Unidades consultables a una
fecha").

`consultable_units(fecha)` devuelve las unidades de lecturas validadas, de documentos en
uso vigentes a la fecha, con la marca `repealed` resuelta a esa fecha. Los datos son
sintéticos y se arman con las fábricas de `tests/conftest.py`.
"""

from datetime import date

import pytest
from django.db import connection

COLUMNS = (
    "unit_id", "reading_id", "document_id", "norm_id",
    "repealed", "repealed_by_relation_id", "repealed_by_norm_id", "repealed_since",
)


def consultable(reference_date):
    """Filas de `consultable_units(fecha)` por `unit_id`, cada una como diccionario."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {', '.join(COLUMNS)} FROM consultable_units(%s)", [reference_date]
        )
        rows = [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]
    by_unit = {row["unit_id"]: row for row in rows}
    assert len(by_unit) == len(rows), "una unidad aparece más de una vez"
    return by_unit


def ids(units):
    return {u.pk for u in units}


# --- Lectura validada y documento en uso (REQ-005) -----------------------------------


@pytest.mark.django_db
def test_a_reading_not_validated_returns_no_units(make_norm, make_document, make_reading):
    """REQ-005: las unidades de una lectura `pending` no son consultables; las de una
    lectura `validated`, sí; las de una lectura `superseded`, no."""
    norm = make_norm()
    pending = make_reading(make_document(norm), [("art-1", "Texto pendiente.")],
                           status="pending")
    validated = make_reading(make_document(make_norm()), [("art-1", "Texto validado.")])
    superseded = make_reading(make_document(make_norm()), [("art-1", "Texto viejo.")],
                              status="superseded")

    result = consultable(date(2024, 1, 1))

    assert ids(pending.units_by_key.values()).isdisjoint(result)
    assert ids(superseded.units_by_key.values()).isdisjoint(result)
    assert ids(validated.units_by_key.values()) <= set(result)


@pytest.mark.django_db
def test_a_document_not_in_use_returns_no_units(make_norm, make_document, make_reading):
    """REQ-005, REQ-007: un documento validado que no está en uso (otro archivo de la
    misma parte, todavía sin registrar como versión) no aporta unidades."""
    norm = make_norm()
    in_use = make_reading(make_document(norm), [("art-1", "Archivo en uso.")])
    other = make_reading(
        make_document(norm, in_use=False, version_number=None),
        [("art-1", "Otro archivo de la misma parte.")],
    )

    result = consultable(date(2024, 1, 1))

    assert ids(in_use.units_by_key.values()) <= set(result)
    assert ids(other.units_by_key.values()).isdisjoint(result)


@pytest.mark.django_db
def test_all_parts_in_use_of_a_norm_are_consultable(make_norm, make_document, make_reading):
    """REQ-020: el cuerpo y el anexo de una misma norma, los dos en uso, aportan sus
    unidades; cada fila dice su documento y su norma."""
    norm = make_norm()
    body_doc = make_document(norm, part="cuerpo")
    annex_doc = make_document(norm, part="anexo")
    body = make_reading(body_doc, [("art-1", "Cuerpo.")])
    annex = make_reading(annex_doc, [("anexo", "ANEXO"), ("anexo/art-1", "Anexo.")])

    result = consultable(date(2024, 1, 1))

    body_unit = body.units_by_key["art-1"]
    annex_unit = annex.units_by_key["anexo/art-1"]
    assert result[body_unit.pk]["document_id"] == body_doc.pk
    assert result[annex_unit.pk]["document_id"] == annex_doc.pk
    assert result[body_unit.pk]["norm_id"] == result[annex_unit.pk]["norm_id"] == norm.pk
    assert result[annex_unit.pk]["reading_id"] == annex.pk


# --- Vigencia y versiones (REQ-007) --------------------------------------------------


@pytest.mark.django_db
def test_validity_bounds_are_from_inclusive_and_to_exclusive(
    make_norm, make_document, make_reading
):
    """REQ-007: un documento es consultable desde `effective_from` inclusive y hasta el
    día anterior a `effective_to` (vigente si `effective_to` es posterior a la fecha)."""
    reading = make_reading(
        make_document(make_norm(), effective_from=date(2010, 5, 1),
                      effective_to=date(2015, 5, 1)),
        [("art-1", "Texto con vigencia acotada.")],
    )
    unit = reading.units_by_key["art-1"].pk

    assert unit not in consultable(date(2010, 4, 30))
    assert unit in consultable(date(2010, 5, 1))
    assert unit in consultable(date(2015, 4, 30))
    assert unit not in consultable(date(2015, 5, 1))


@pytest.mark.django_db
def test_two_versions_of_a_norm_each_date_returns_its_own(
    make_norm, make_document, make_reading
):
    """REQ-007: con dos versiones de una norma, cada fecha devuelve las unidades de la
    suya."""
    norm = make_norm()
    first = make_reading(
        make_document(norm, version_number=1, effective_from=date(2010, 1, 1),
                      effective_to=date(2018, 7, 1)),
        [("art-1", "Texto de la versión 1.")],
    )
    second = make_reading(
        make_document(norm, version_number=2, effective_from=date(2018, 7, 1)),
        [("art-1", "Texto de la versión 2.")],
    )
    v1 = first.units_by_key["art-1"].pk
    v2 = second.units_by_key["art-1"].pk

    early = consultable(date(2015, 1, 1))
    late = consultable(date(2018, 7, 1))
    assert v1 in early and v2 not in early
    assert v2 in late and v1 not in late
    assert v1 not in consultable(date(2009, 12, 31))


# --- Derogación a la fecha (REQ-007, REQ-020) ----------------------------------------


@pytest.mark.django_db
def test_repeal_of_a_unit_marks_it_and_the_units_it_contains(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: una derogación de una unidad marca `repealed` en esa unidad y en las que
    contiene (prefijo de clave), no en las demás, ni en `art-10` por empezar con `art-1`,
    y solo desde su fecha. Trae la relación, la norma que derogó y desde cuándo."""
    target = make_norm()
    reading = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Texto."),
        ("art-1/inc-a", "a) inciso."),
        ("art-1/inc-a/inc-1", "1) subinciso."),
        ("art-10", "ARTICULO 10.- Texto."),
        ("art-2", "ARTICULO 2.- Texto."),
    ])
    source = make_norm()
    make_reading(make_document(source), [("art-5", "Derógase el artículo 1.")])
    repeal = make_relation(source, target, "deroga", source_unit_key="art-5",
                           target_unit_key="art-1", effective_date=date(2020, 3, 1))
    units = reading.units_by_key

    before = consultable(date(2020, 2, 29))
    after = consultable(date(2020, 3, 1))

    for key in units:
        assert before[units[key].pk]["repealed"] is False
        assert before[units[key].pk]["repealed_by_relation_id"] is None
    for key in ("art-1", "art-1/inc-a", "art-1/inc-a/inc-1"):
        row = after[units[key].pk]
        assert row["repealed"] is True
        assert row["repealed_by_relation_id"] == repeal.pk
        assert row["repealed_by_norm_id"] == source.pk
        assert row["repealed_since"] == date(2020, 3, 1)
    for key in ("art-10", "art-2"):
        assert after[units[key].pk]["repealed"] is False


@pytest.mark.django_db
def test_repeal_of_an_inciso_does_not_mark_the_article_that_contains_it(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: derogar un inciso marca el inciso, no el artículo que lo contiene."""
    target = make_norm()
    reading = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Texto."),
        ("art-1/inc-a", "a) inciso."),
    ])
    make_relation(make_norm(), target, "deroga", target_unit_key="art-1/inc-a",
                  effective_date=date(2020, 1, 1))

    result = consultable(date(2021, 1, 1))

    assert result[reading.units_by_key["art-1/inc-a"].pk]["repealed"] is True
    assert result[reading.units_by_key["art-1"].pk]["repealed"] is False


@pytest.mark.django_db
def test_repeal_of_the_whole_norm_marks_every_part_and_other_relations_do_not(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007, REQ-020: una derogación de la norma entera marca todas sus unidades, de
    todas sus partes; una relación `modifica` no marca nada; una derogación de otra
    norma no alcanza a esta. Con dos derogaciones vigentes se informa la más antigua."""
    target = make_norm()
    body = make_reading(make_document(target, part="cuerpo"), [("art-1", "Cuerpo.")])
    annex = make_reading(make_document(target, part="anexo"),
                         [("anexo", "ANEXO"), ("anexo/art-1", "Anexo.")])
    other = make_reading(make_document(make_norm()), [("art-1", "Otra norma.")])
    make_relation(make_norm(), target, "modifica", target_unit_key="art-1",
                  effective_date=date(2015, 1, 1))
    make_relation(make_norm(), target, "deroga", effective_date=date(2019, 1, 1))
    first = make_relation(make_norm(), target, "deroga", effective_date=date(2018, 1, 1))

    assert all(not row["repealed"] for row in consultable(date(2017, 1, 1)).values())

    result = consultable(date(2020, 1, 1))
    target_units = list(body.units_by_key.values()) + list(annex.units_by_key.values())
    for unit in target_units:
        assert result[unit.pk]["repealed"] is True
        assert result[unit.pk]["repealed_by_relation_id"] == first.pk
        assert result[unit.pk]["repealed_since"] == date(2018, 1, 1)
    assert result[other.units_by_key["art-1"].pk]["repealed"] is False


@pytest.mark.django_db
def test_repeal_of_an_annex_root_marks_the_annex_units(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: derogar la unidad raíz de un anexo (`anexo-i`) marca sus artículos,
    pero no el artículo del cuerpo con el mismo número."""
    target = make_norm()
    reading = make_reading(make_document(target), [
        ("art-1", "Cuerpo."),
        ("anexo-i", "ANEXO I"),
        ("anexo-i/art-1", "Anexo I, artículo 1."),
    ])
    make_relation(make_norm(), target, "deroga", target_unit_key="anexo-i",
                  effective_date=date(2020, 1, 1))

    result = consultable(date(2020, 1, 1))
    units = reading.units_by_key
    assert result[units["anexo-i"].pk]["repealed"] is True
    assert result[units["anexo-i/art-1"].pk]["repealed"] is True
    assert result[units["art-1"].pk]["repealed"] is False


# --- Dos regímenes (REQ-020) ---------------------------------------------------------


def _keys(result, units):
    """Claves de `units` presentes en el resultado, con su marca `repealed`."""
    return {key: result[u.pk]["repealed"] for key, u in units.items() if u.pk in result}


@pytest.mark.django_db
def test_two_regimes_before_v_only_the_first_without_mark(two_regimes):
    """REQ-020: con una fecha anterior a V, devuelve las unidades del primer régimen sin
    marca y ninguna del segundo."""
    result = consultable(two_regimes.before_v)

    old = _keys(result, two_regimes.old_units)
    assert set(old) == set(two_regimes.old_units)
    assert not any(old.values())
    assert _keys(result, two_regimes.new_units) == {}


@pytest.mark.django_db
@pytest.mark.parametrize("when", ["v", "after_v"])
def test_two_regimes_from_v_the_second_in_both_parts_and_the_first_repealed(
    two_regimes, when
):
    """REQ-020: con V o una fecha posterior, devuelve las unidades del segundo régimen,
    de sus dos partes, sin marca, y las del primero con `repealed` verdadero, derogadas
    por el segundo desde V."""
    result = consultable(getattr(two_regimes, when))

    new = _keys(result, two_regimes.new_units)
    assert set(new) == set(two_regimes.new_units)
    assert {"art-1", "anexo/art-1"} <= set(new)
    assert not any(new.values())

    old = _keys(result, two_regimes.old_units)
    assert set(old) == set(two_regimes.old_units)
    assert all(old.values())
    row = result[two_regimes.old_units["anexo-i/art-1"].pk]
    assert row["repealed_by_norm_id"] == two_regimes.new.pk
    assert row["repealed_since"] == two_regimes.v


@pytest.mark.django_db
def test_two_regimes_before_both_returns_none(two_regimes):
    """REQ-020: con una fecha anterior a los dos regímenes no devuelve ninguno."""
    result = consultable(two_regimes.before_all)

    assert _keys(result, two_regimes.old_units) == {}
    assert _keys(result, two_regimes.new_units) == {}
