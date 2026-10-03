"""Búsqueda directa por norma y artículo, y por palabras (T-035; plan 001, "Búsqueda
directa (REQ-010)" y "Unidades consultables a una fecha").

La búsqueda no usa modelos de IA y lee siempre de `consultable_units(fecha)`, con la
fecha de autorización que recibe. Los datos son sintéticos (P4): los dos regímenes de
prueba de `two_regimes` y normas armadas con las fábricas de `conftest.py`.
"""

import json
from datetime import date

import pytest

from evaluon.queries import search

pytestmark = pytest.mark.django_db


def keys(results):
    return [result.key for result in results]


def by_key(results):
    return {result.key: result for result in results}


@pytest.fixture
def worded_norm(make_norm, make_document, make_reading):
    """Una norma con tildes, plurales, una frase y una cláusula sin número, en vigencia
    desde el 2010-01-01."""
    norm = make_norm(citation="Resolución sintética 55/10")
    reading = make_reading(make_document(norm, effective_from=date(2010, 1, 1)), [
        ("art-1", "ARTÍCULO 1°.- La garantía de oferta se constituye por escrito."),
        ("art-2", "ARTÍCULO 2°.- La oferta incluye una garantía bancaria."),
        ("art-3", "ARTÍCULO 3°.- Las adjudicaciones se publican."),
        ("anexo", "ANEXO"),
        ("anexo/clausula-transitoria",
         "CLÁUSULA TRANSITORIA Registro sintético de proveedores."),
    ])
    return norm, reading.units_by_key


# --- Por norma y número de artículo -------------------------------------------------


def test_article_returns_unit_with_its_literal_text(two_regimes):
    """REQ-010: dado un número de norma y de artículo se obtiene la unidad con su texto
    literal, su ruta, su categoría y su documento."""
    results = search.by_article(two_regimes.old.pk, "2", two_regimes.before_v)

    assert keys(results) == ["art-2"]
    [result] = results
    unit = two_regimes.old_units["art-2"]
    reading = unit.reading
    assert result.unit_id == unit.pk
    assert result.text == reading.canonical_text[unit.char_start:unit.char_end]
    assert result.path == unit.path
    assert result.norm_id == two_regimes.old.pk
    assert result.norm_name == "Disposición AFIP 297/03"
    assert result.category == "regimen_especifico"
    assert result.document_id == two_regimes.old_body.pk
    assert result.document_part == "cuerpo"


def test_article_1_in_body_and_annex_of_one_file(two_regimes):
    """REQ-010: "artículo 1" de una norma con artículo 1 en el cuerpo y en el anexo del
    mismo archivo devuelve las dos unidades, cada una con su ruta."""
    results = search.by_article(two_regimes.old.pk, "1", two_regimes.before_v)

    assert keys(results) == ["art-1", "anexo-i/art-1"]
    paths = [result.path for result in results]
    assert paths == [two_regimes.old_units["art-1"].path,
                     two_regimes.old_units["anexo-i/art-1"].path]
    assert len(set(paths)) == 2
    assert {result.document_id for result in results} == {two_regimes.old_body.pk}


def test_article_1_in_body_and_annex_of_two_files(two_regimes):
    """REQ-010: "artículo 1" de una norma publicada en dos archivos (cuerpo y anexo)
    devuelve las dos unidades, cada una con su ruta y su documento."""
    results = search.by_article(two_regimes.new.pk, "1", two_regimes.after_v)

    assert keys(results) == ["art-1", "anexo/art-1"]
    assert [result.document_id for result in results] == [
        two_regimes.new_body.pk, two_regimes.new_annex.pk]
    assert [result.document_part for result in results] == ["cuerpo", "anexo"]
    assert results[1].path == two_regimes.new_units["anexo/art-1"].path


def test_article_number_is_trimmed_and_ignores_degree_sign(two_regimes):
    """REQ-010: el número escrito con espacios o con el signo de grado encuentra el
    mismo artículo."""
    plain = keys(search.by_article(two_regimes.old.pk, "1", two_regimes.before_v))

    assert keys(search.by_article(two_regimes.old.pk, " 1° ", two_regimes.before_v)) \
        == plain


def test_article_search_does_not_return_other_norms_or_types(two_regimes, worded_norm):
    """REQ-010: solo devuelve unidades de tipo `articulo` de la norma pedida; una
    cláusula sin número no sale con un número vacío."""
    norm, _ = worded_norm

    results = search.by_article(two_regimes.new.pk, "2", two_regimes.after_v)
    assert keys(results) == ["art-2", "anexo/art-2"]
    assert {result.norm_id for result in results} == {two_regimes.new.pk}
    assert {result.unit_type for result in results} == {"articulo"}
    assert search.by_article(norm.pk, "", date(2024, 1, 1)) == []
    assert search.by_article(norm.pk, "   ", date(2024, 1, 1)) == []


def test_article_with_subsection_returns_the_subsection(two_regimes):
    """REQ-010: cuando se pide el inciso, devuelve el inciso de ese artículo con su
    ruta y su texto."""
    results = search.by_article(two_regimes.old.pk, "1", two_regimes.before_v,
                                subsection="A")

    assert keys(results) == ["anexo-i/art-1/inc-a"]
    unit = two_regimes.old_units["anexo-i/art-1/inc-a"]
    assert results[0].text == unit.text
    assert results[0].unit_type == "inciso"
    assert search.by_article(two_regimes.old.pk, "1", two_regimes.before_v,
                             subsection="z") == []


# --- Fecha de autorización (REQ-020) ------------------------------------------------


def test_repealed_unit_is_marked_with_norm_and_date(two_regimes):
    """REQ-010, REQ-020: con una fecha posterior a la derogación, las dos unidades del
    artículo 1 aparecen marcadas como derogadas, con la norma que las derogó y desde
    cuándo."""
    results = search.by_article(two_regimes.old.pk, "1", two_regimes.after_v)

    assert keys(results) == ["art-1", "anexo-i/art-1"]
    for result in results:
        assert result.repealed is True
        assert result.repealed_by.relation_id == two_regimes.repeal.pk
        assert result.repealed_by.norm_id == two_regimes.new.pk
        assert result.repealed_by.norm_name == "Disposición AFIP 247/2022"
        assert result.repealed_by.since == two_regimes.v


def test_same_unit_before_repeal_has_no_mark(two_regimes):
    """REQ-020: con una fecha anterior a la derogación, la misma unidad aparece sin la
    marca."""
    results = search.by_article(two_regimes.old.pk, "1", two_regimes.before_v)

    assert [result.repealed for result in results] == [False, False]
    assert [result.repealed_by for result in results] == [None, None]


def test_norm_not_yet_in_force_does_not_appear(two_regimes):
    """REQ-020: las unidades de una norma que todavía no regía a la fecha no aparecen,
    ni por artículo ni por palabras."""
    assert search.by_article(two_regimes.new.pk, "1", two_regimes.before_v) == []
    assert search.by_words("vigente", two_regimes.before_v) == []
    assert keys(search.by_words("vigente", two_regimes.after_v)) == ["anexo/art-1"]


def test_nothing_before_any_regime(two_regimes):
    """REQ-020: antes de la vigencia de los dos regímenes no hay resultados."""
    assert search.by_article(two_regimes.old.pk, "1", two_regimes.before_all) == []
    assert search.by_words("sintético", two_regimes.before_all) == []


def test_search_requires_the_reference_date(two_regimes):
    """REQ-020: la búsqueda no usa la fecha del día por su cuenta: sin fecha de
    autorización, no busca."""
    with pytest.raises(ValueError):
        search.by_article(two_regimes.old.pk, "1", None)
    with pytest.raises(ValueError):
        search.by_words("sintético", None)


# --- Norma sin validar (REQ-005) ----------------------------------------------------


def test_unvalidated_norm_does_not_appear(make_norm, make_document, make_reading):
    """REQ-005: una norma cargada y todavía sin validar no aparece en la búsqueda
    directa, ni por artículo ni por palabras."""
    norm = make_norm()
    make_reading(make_document(norm), [
        ("art-1", "ARTICULO 1.- Texto pendiente de validación sintético."),
    ], status="pending")

    assert search.by_article(norm.pk, "1", date(2024, 1, 1)) == []
    assert search.by_words("pendiente", date(2024, 1, 1)) == []


# --- Por palabras -------------------------------------------------------------------


def test_words_without_accents_find_text_with_accents(two_regimes, worded_norm):
    """REQ-010: una búsqueda sin tildes encuentra el texto con tildes, y el singular
    encuentra el plural."""
    norm, units = worded_norm
    when = date(2024, 1, 1)

    assert keys(search.by_words("garantia", when, norm_id=norm.pk)) == ["art-1", "art-2"]
    assert keys(search.by_words("GARANTIA", two_regimes.after_v,
                                norm_id=two_regimes.new.pk)) == ["anexo/art-2"]
    assert keys(search.by_words("adjudicacion", when)) == ["art-3"]
    result = search.by_words("adjudicacion", when)[0]
    assert result.unit_id == units["art-3"].pk
    assert result.text == units["art-3"].text


def test_quotes_search_exact_phrase(worded_norm):
    """REQ-010: con comillas se busca la frase exacta; sin comillas, todas las
    palabras en cualquier orden."""
    norm, _ = worded_norm
    when = date(2024, 1, 1)

    assert keys(search.by_words('"garantia de oferta"', when)) == ["art-1"]
    assert keys(search.by_words("garantia oferta", when)) == ["art-1", "art-2"]


def test_words_find_clause_without_number(worded_norm):
    """REQ-010: una unidad sin número de artículo se encuentra por palabras."""
    norm, units = worded_norm

    results = search.by_words("proveedores", date(2024, 1, 1))

    assert keys(results) == ["anexo/clausula-transitoria"]
    assert results[0].number == ""


def test_words_are_grouped_by_base_unit(worded_norm, make_passage):
    """REQ-010: los resultados se agrupan por unidad base: una unidad con dos pasajes
    que coinciden aparece una sola vez."""
    norm, units = worded_norm
    unit = units["art-1"]
    make_passage(unit, char_start=0, char_end=10, text=unit.text)

    results = search.by_words("garantia", date(2024, 1, 1), norm_id=norm.pk)

    assert keys(results) == ["art-1", "art-2"]


def test_words_filter_by_norm(two_regimes):
    """REQ-010: la norma se filtra por su campo, no por las palabras: el número de la
    norma no está en el texto."""
    when = two_regimes.after_v

    all_norms = {result.norm_id for result in search.by_words("sintético", when)}
    assert all_norms == {two_regimes.old.pk, two_regimes.new.pk}
    only_new = search.by_words("sintético", when, norm_id=two_regimes.new.pk)
    assert only_new
    assert {result.norm_id for result in only_new} == {two_regimes.new.pk}


def test_words_mark_repealed_units(two_regimes):
    """REQ-010, REQ-020: por palabras, una unidad derogada a la fecha aparece marcada;
    con una fecha anterior, sin la marca."""
    after = by_key(search.by_words("licitaciones", two_regimes.after_v))
    before = by_key(search.by_words("licitaciones", two_regimes.before_v))

    assert after["art-1"].repealed is True
    assert after["art-1"].repealed_by.norm_id == two_regimes.new.pk
    assert before["art-1"].repealed is False


def test_blank_words_return_nothing(two_regimes):
    """REQ-010: una búsqueda sin palabras no devuelve resultados."""
    assert search.by_words("", two_regimes.after_v) == []
    assert search.by_words("   ", two_regimes.after_v) == []


# --- Cambios y vínculos (REQ-006) ---------------------------------------------------


@pytest.fixture
def amended_old(two_regimes, make_norm, make_document, make_reading, make_relation):
    """Una norma que modifica el inciso a del artículo 1 del Anexo I de `old` desde el
    2010-05-01 y que complementa a `old` entera desde la misma fecha."""
    amending = make_norm(citation="Disposición sintética 10/10")
    amending_units = make_reading(
        make_document(amending, effective_from=date(2010, 5, 1)),
        [("art-3", "ARTICULO 3.- Sustitúyese el inciso a por el texto sintético.")],
    ).units_by_key
    change = make_relation(amending, two_regimes.old, "modifica",
                           source_unit_key="art-3",
                           target_unit_key="anexo-i/art-1/inc-a",
                           effective_date=date(2010, 5, 1))
    complement = make_relation(amending, two_regimes.old, "complementa",
                               effective_date=date(2010, 5, 1))
    return amending, amending_units, change, complement


def test_changes_in_force_come_with_the_result(two_regimes, amended_old):
    """REQ-006, REQ-020: el resultado trae los cambios vigentes a la fecha, con la
    unidad de la norma que lo modifica y su texto; antes del cambio, no los trae."""
    amending, amending_units, change, complement = amended_old

    after = by_key(search.by_article(two_regimes.old.pk, "1", date(2015, 1, 1)))
    [item] = after["anexo-i/art-1"].changes
    assert item.relation_id == change.pk
    assert item.relation_type == "modifica"
    assert item.target_unit_key == "anexo-i/art-1/inc-a"
    assert item.effective_date == date(2010, 5, 1)
    assert item.source_norm_id == amending.pk
    assert item.source_norm_name == "Disposición sintética 10/10"
    assert item.source_unit_id == amending_units["art-3"].pk
    assert item.source_unit_text == amending_units["art-3"].text
    assert item.source_unit_path == amending_units["art-3"].path
    # La relación sobre la norma entera no es un cambio de la unidad.
    assert after["art-1"].changes == ()

    before = by_key(search.by_article(two_regimes.old.pk, "1", date(2008, 1, 1)))
    assert before["anexo-i/art-1"].changes == ()


def test_links_of_the_norm_in_both_directions(two_regimes, amended_old):
    """REQ-006: el resultado trae los vínculos de su norma con otras en los dos
    sentidos, vigentes a la fecha."""
    amending, _, change, complement = amended_old

    [old_result, _] = search.by_article(two_regimes.old.pk, "1", two_regimes.after_v)
    links = {link.relation_id: link for link in old_result.links}
    assert set(links) == {two_regimes.repeal.pk, change.pk, complement.pk}
    repeal = links[two_regimes.repeal.pk]
    assert repeal.direction == "incoming"
    assert repeal.relation_type == "deroga"
    assert repeal.other_norm_id == two_regimes.new.pk
    assert repeal.other_norm_name == "Disposición AFIP 247/2022"
    assert repeal.source_unit_key == "art-2"
    assert repeal.target_unit_key == ""
    assert repeal.effective_date == two_regimes.v

    [new_result, _] = search.by_article(two_regimes.new.pk, "1", two_regimes.after_v)
    [new_link] = new_result.links
    assert new_link.relation_id == two_regimes.repeal.pk
    assert new_link.direction == "outgoing"
    assert new_link.other_norm_id == two_regimes.old.pk
    assert new_link.other_norm_name == "Disposición AFIP 297/03"

    # Antes de la derogación, el vínculo todavía no regía.
    [before, _] = search.by_article(two_regimes.old.pk, "1", two_regimes.before_v)
    assert {link.relation_id for link in before.links} == {change.pk, complement.pk}


def test_result_as_record_is_json(two_regimes, amended_old):
    """REQ-010: cada resultado se puede guardar tal cual en el registro de la búsqueda,
    con su marca de derogada."""
    results = search.by_article(two_regimes.old.pk, "1", two_regimes.after_v)

    record = json.loads(json.dumps([result.as_record() for result in results]))

    assert record[0]["unit_id"] == two_regimes.old_units["art-1"].pk
    assert record[0]["repealed"] is True
    assert record[0]["repealed_by"]["since"] == "2023-01-01"
    assert record[1]["changes"][0]["effective_date"] == "2010-05-01"
