"""Cambios de una unidad a una fecha (T-009; plan 001, "Unidades consultables a una
fecha").

`unit_changes(fecha)` devuelve, para cada unidad consultable a la fecha, las relaciones
`modifica` o `deroga` vigentes a esa fecha que la alcanzan a ella o a una unidad
contenida en ella, con la unidad de la norma de origen que trae el cambio. Los datos son
sintéticos.
"""

from datetime import date

import pytest
from django.db import connection

COLUMNS = (
    "unit_id", "relation_id", "relation_type", "target_unit_key", "effective_date",
    "source_norm_id", "source_unit_key", "source_unit_id",
)


def changes(reference_date):
    """Filas de `unit_changes(fecha)`, cada una como diccionario."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {', '.join(COLUMNS)} FROM unit_changes(%s)", [reference_date]
        )
        return [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]


def changes_of(reference_date, unit):
    return [row for row in changes(reference_date) if row["unit_id"] == unit.pk]


@pytest.fixture
def modified_article(make_norm, make_document, make_reading, make_relation):
    """Una norma con `art-1` (e inciso `a`), `art-10` y `art-2`; otra norma cuyo `art-3`
    modifica el `art-1` desde el 2020-06-01."""
    target = make_norm()
    target_reading = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Texto original."),
        ("art-1/inc-a", "a) inciso original."),
        ("art-10", "ARTICULO 10.- Otro texto."),
        ("art-2", "ARTICULO 2.- Otro texto."),
    ])
    source = make_norm()
    source_reading = make_reading(make_document(source), [
        ("art-3", "ARTICULO 3.- Sustitúyese el artículo 1 por el siguiente texto."),
    ])
    relation = make_relation(source, target, "modifica", source_unit_key="art-3",
                             target_unit_key="art-1", effective_date=date(2020, 6, 1))
    return target_reading.units_by_key, source_reading.units_by_key, relation, source


@pytest.mark.django_db
def test_before_the_date_no_change_and_after_it_the_modifying_unit(modified_article):
    """REQ-007: un artículo modificado en una fecha: antes, sin cambios; desde esa
    fecha, con la unidad que lo modifica y su texto literal."""
    target, source_units, relation, source = modified_article

    assert changes_of(date(2020, 5, 31), target["art-1"]) == []

    [row] = changes_of(date(2020, 6, 1), target["art-1"])
    assert row["relation_id"] == relation.pk
    assert row["relation_type"] == "modifica"
    assert row["target_unit_key"] == "art-1"
    assert row["effective_date"] == date(2020, 6, 1)
    assert row["source_norm_id"] == source.pk
    assert row["source_unit_key"] == "art-3"
    assert row["source_unit_id"] == source_units["art-3"].pk
    assert source_units["art-3"].text.startswith("ARTICULO 3.- Sustitúyese")


@pytest.mark.django_db
def test_change_reaches_the_target_and_not_its_incisos_or_siblings(
    modified_article,
):
    """REQ-007: un cambio sobre `art-1` lo trae `art-1`; no lo traen su inciso (que está
    contenido en la unidad alcanzada, no la contiene), `art-10` ni `art-2`. El caso en
    que la clave alcanzada empieza con la de otra unidad (`art-10` frente a `art-1`) lo
    cubre `test_change_to_art_10_is_not_reported_on_art_1`."""
    target, _, _, _ = modified_article
    result = changes(date(2021, 1, 1))
    reached = {row["unit_id"] for row in result}

    assert target["art-1"].pk in reached
    for key in ("art-1/inc-a", "art-10", "art-2"):
        assert target[key].pk not in reached


@pytest.mark.django_db
def test_change_to_art_10_is_not_reported_on_art_1(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: una modificación de `art-10` aparece en `art-10` y no en `art-1`, aunque
    la clave alcanzada empiece con `art-1`: una unidad contenida se reconoce por su clave
    seguida de `/`, no por cualquier prefijo."""
    target = make_norm()
    units = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Texto."),
        ("art-10", "ARTICULO 10.- Texto."),
    ]).units_by_key
    relation = make_relation(make_norm(), target, "modifica", target_unit_key="art-10",
                             effective_date=date(2020, 1, 1))

    assert changes_of(date(2020, 1, 1), units["art-1"]) == []
    [row] = changes_of(date(2020, 1, 1), units["art-10"])
    assert row["relation_id"] == relation.pk


@pytest.mark.django_db
def test_source_unit_is_taken_from_the_source_norm(two_regimes, make_relation):
    """REQ-007, REQ-020: la unidad de origen es la de la norma de origen con esa clave,
    no la de otra norma con la misma clave: un cambio desde `art-2` de la norma nueva
    sobre `art-1` de la anterior trae el `art-2` de la nueva, no el de la anterior."""
    relation = make_relation(
        two_regimes.new, two_regimes.old, "modifica", source_unit_key="art-2",
        target_unit_key="art-1", effective_date=two_regimes.v,
    )

    [row] = changes_of(two_regimes.after_v, two_regimes.old_units["art-1"])
    assert row["relation_id"] == relation.pk
    assert row["source_norm_id"] == two_regimes.new.pk
    assert row["source_unit_id"] == two_regimes.new_units["art-2"].pk
    assert row["source_unit_id"] != two_regimes.old_units["art-2"].pk


@pytest.mark.django_db
def test_a_change_to_an_inciso_is_reported_on_its_article(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: una modificación de un inciso aparece en el inciso y en el artículo que
    lo contiene, con la clave del inciso alcanzado."""
    target = make_norm()
    units = make_reading(make_document(target), [
        ("art-14", "ARTICULO 14.- Texto."),
        ("art-14/inc-b", "b) inciso."),
    ]).units_by_key
    make_relation(make_norm(), target, "modifica", target_unit_key="art-14/inc-b",
                  effective_date=date(2020, 1, 1))

    [on_article] = changes_of(date(2020, 1, 1), units["art-14"])
    [on_inciso] = changes_of(date(2020, 1, 1), units["art-14/inc-b"])
    assert on_article["target_unit_key"] == on_inciso["target_unit_key"] == "art-14/inc-b"


@pytest.mark.django_db
def test_only_modifica_and_deroga_count(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: las relaciones `complementa` y `reglamenta` no son cambios del texto;
    `modifica` y `deroga` sí."""
    target = make_norm()
    unit = make_reading(make_document(target), [("art-1", "Texto.")]).units_by_key["art-1"]
    for relation_type in ("modifica", "complementa", "reglamenta", "deroga"):
        make_relation(make_norm(), target, relation_type, target_unit_key="art-1",
                      effective_date=date(2020, 1, 1))

    types = sorted(row["relation_type"] for row in changes_of(date(2020, 1, 1), unit))
    assert types == ["deroga", "modifica"]


@pytest.mark.django_db
def test_relation_between_whole_norms_has_no_source_unit(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: si la relación viene de la norma de origen entera, la fila no trae
    unidad de origen; tampoco la trae si la unidad de origen no es consultable a la
    fecha (su norma todavía no rige)."""
    target = make_norm()
    unit = make_reading(make_document(target), [
        ("art-1", "Texto."), ("art-2", "Texto."),
    ]).units_by_key
    whole = make_relation(make_norm(), target, "modifica", target_unit_key="art-1",
                          effective_date=date(2020, 1, 1))
    late_source = make_norm()
    make_reading(make_document(late_source, effective_from=date(2030, 1, 1)),
                 [("art-9", "Texto que rige después.")])
    make_relation(late_source, target, "modifica", source_unit_key="art-9",
                  target_unit_key="art-2", effective_date=date(2020, 1, 1))

    [row1] = changes_of(date(2021, 1, 1), unit["art-1"])
    [row2] = changes_of(date(2021, 1, 1), unit["art-2"])
    assert row1["relation_id"] == whole.pk
    assert row1["source_unit_key"] == "" and row1["source_unit_id"] is None
    assert row2["source_unit_key"] == "art-9" and row2["source_unit_id"] is None


@pytest.mark.django_db
def test_each_version_reports_the_changes_on_its_own_unit(
    make_norm, make_document, make_reading, make_relation
):
    """REQ-007: los cambios se informan sobre la unidad consultable a la fecha: con dos
    versiones de la norma, cada fecha da la unidad de su versión."""
    target = make_norm()
    v1 = make_reading(
        make_document(target, version_number=1, effective_to=date(2019, 1, 1)),
        [("art-1", "Versión 1.")],
    ).units_by_key["art-1"]
    v2 = make_reading(
        make_document(target, version_number=2, effective_from=date(2019, 1, 1)),
        [("art-1", "Versión 2.")],
    ).units_by_key["art-1"]
    make_relation(make_norm(), target, "modifica", target_unit_key="art-1",
                  effective_date=date(2010, 1, 1))

    assert {r["unit_id"] for r in changes(date(2015, 1, 1))} == {v1.pk}
    assert {r["unit_id"] for r in changes(date(2020, 1, 1))} == {v2.pk}


@pytest.mark.django_db
def test_two_regimes_repeal_is_not_a_unit_change(two_regimes):
    """REQ-020: la derogación del primer régimen entero se informa como marca
    `repealed` de `consultable_units`, no como cambio de cada unidad."""
    assert changes(two_regimes.after_v) == []
