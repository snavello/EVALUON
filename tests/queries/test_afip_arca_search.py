"""AFIP y ARCA en la búsqueda y en la recuperación (T-057; ADR-0010).

Una búsqueda por palabras o una pregunta que nombra a "ARCA" encuentra los textos que
dicen "AFIP", y al revés, con la sigla o con el nombre largo. La referencia a una norma
en la pregunta no depende del organismo escrito. El índice guardado (`tsv`) no cambia:
se amplía la consulta.

Con los dobles de embeddings y reranker de `tests/conftest.py`; los textos son
sintéticos (P4).
"""

from datetime import date

import pytest

from evaluon.norms.services.loading import issuer_variants
from evaluon.queries import retrieval, search

pytestmark = pytest.mark.django_db

REFERENCE_DATE = date(2024, 5, 20)


@pytest.fixture
def issuer_norm(make_norm, make_document, make_reading):
    """Una norma con un artículo que nombra a la AFIP, otro a la ARCA, otro con el nombre
    largo de cada una y otro que no nombra a ninguna."""
    norm = make_norm(citation="Resolución sintética 57/24")
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTÍCULO 1°.- La inscripción ante la AFIP es previa marca-uno."),
        ("art-2", "ARTÍCULO 2°.- La ARCA publica el llamado marca-dos."),
        ("art-3", "ARTÍCULO 3°.- La Administración Federal de Ingresos Públicos "
                  "fija el plazo marca-tres."),
        ("art-4", "ARTÍCULO 4°.- La Agencia de Recaudación y Control Aduanero "
                  "recibe las ofertas marca-cuatro."),
        ("art-5", "ARTÍCULO 5°.- Las ofertas se abren en acto público marca-cinco."),
    ])
    return reading.units_by_key


ALL_ISSUER_UNITS = ["art-1", "art-2", "art-3", "art-4"]


@pytest.mark.parametrize("text", [
    "ARCA",
    "afip",
    "Agencia de Recaudación y Control Aduanero",
    "administracion federal de ingresos publicos",
])
def test_words_search_treats_afip_and_arca_as_the_same(issuer_norm, text):
    """REQ-010: buscar por palabras "ARCA" devuelve las unidades que dicen "AFIP" y al
    revés; el nombre largo de cada una cuenta igual que la sigla."""
    results = search.by_words(text, REFERENCE_DATE)

    assert [result.key for result in results] == ALL_ISSUER_UNITS


def test_words_search_with_another_word_and_a_phrase(issuer_norm):
    """REQ-010: con otra palabra, la equivalencia se mantiene y la otra palabra se sigue
    exigiendo; entre comillas, "inscripción ante la ARCA" encuentra la frase que dice
    AFIP."""
    assert [r.key for r in search.by_words("ARCA inscripción", REFERENCE_DATE)] == [
        "art-1"]
    assert [r.key for r in search.by_words("AFIP llamado", REFERENCE_DATE)] == ["art-2"]
    assert [r.key for r in search.by_words('"inscripción ante la ARCA"',
                                           REFERENCE_DATE)] == ["art-1"]


def test_words_search_without_issuer_is_unchanged(issuer_norm):
    """REQ-010: una búsqueda que no nombra al organismo no cambia: "ofertas" trae solo
    los artículos que lo dicen."""
    assert [r.key for r in search.by_words("ofertas", REFERENCE_DATE)] == [
        "art-4", "art-5"]


@pytest.mark.parametrize("question", [
    "¿Qué hace la ARCA?",
    "¿Qué dice la AFIP?",
    "¿Qué dice la Agencia de Recaudación y Control Aduanero?",
])
def test_words_path_treats_afip_and_arca_as_the_same(issuer_norm, question,
                                                     fake_embeddings, fake_reranker):
    """REQ-008: una pregunta que nombra a la ARCA o a la AFIP, con sigla o nombre largo,
    trae por el camino por palabras las unidades que nombran a cualquiera de las dos."""
    result = retrieval.retrieve(question, REFERENCE_DATE, paths=(retrieval.WORDS,))

    units = {candidate.unit_id for candidate in result.candidates}
    assert {issuer_norm[key].pk for key in ALL_ISSUER_UNITS} <= units
    assert issuer_norm["art-5"].pk not in units


@pytest.mark.parametrize("question, norms", [
    ("Disposición ARCA 297/03", {("297", 3, 2)}),
    ("Disposición AFIP 297/03", {("297", 3, 2)}),
    ("Disposición ARCA 247/2022", {("247", 2022, 4)}),
    ("Disposición de la Agencia de Recaudación y Control Aduanero 247/2022",
     {("247", 2022, 4)}),
])
def test_norm_reference_does_not_depend_on_the_issuer(question, norms):
    """REQ-008, REQ-020: "Disposición ARCA 297/03" y "Disposición ARCA 247/2022" se
    reconocen como referencia a la 297/03 y a la 247/2022, igual que con AFIP."""
    found = {(ref.number, ref.year, ref.year_digits)
             for ref in retrieval.find_references(question).norms}
    assert found == norms


def test_reference_to_arca_norm_brings_the_afip_norm(make_norm, make_document,
                                                     make_reading, fake_embeddings,
                                                     fake_reranker):
    """REQ-008: "artículo 5 de la Disposición ARCA 297/03" trae el artículo 5 de la
    norma cargada como AFIP 297/2003, y no el de otra norma; la norma conserva su
    nombre de cita."""
    old = make_norm(citation="Disposición AFIP 297/03", number="297", year=2003,
                    issuer="afip")
    old_units = make_reading(make_document(old), [
        ("art-5", "ARTICULO 5.- Texto sintético de la 297 marca-vieja."),
    ]).units_by_key
    other = make_norm(number="555", year=2010)
    make_reading(make_document(other), [("art-5", "ARTICULO 5.- Otra norma.")])

    result = retrieval.retrieve("¿Qué dice el artículo 5 de la Disposición ARCA 297/03?",
                                REFERENCE_DATE, paths=(retrieval.REFERENCE,))

    assert {c.unit_id for c in result.candidates} == {old_units["art-5"].pk}
    old.refresh_from_db()
    assert old.citation == "Disposición AFIP 297/03"


@pytest.fixture
def lookalike_norm(make_norm, make_document, make_reading):
    """Una norma con palabras que contienen "arca" o "afip" sin serlo, y otra con AFIP."""
    norm = make_norm(citation="Resolución sintética 58/24")
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTÍCULO 1°.- La AFIP recibe el pedido marca-uno."),
        ("art-2", "ARTÍCULO 2°.- Arcadia es un nombre sintético marca-dos."),
        ("art-3", "ARTÍCULO 3°.- Las arcas del Estado reciben el pago marca-tres."),
        ("art-4", "ARTÍCULO 4°.- Comarca sintética marca-cuatro."),
    ])
    return reading.units_by_key


@pytest.mark.parametrize("text, expected", [
    ("Arcadia", ["art-2"]),
    ("comarca", ["art-4"]),
    ("arcas", ["art-3"]),
])
def test_words_search_does_not_widen_words_that_contain_arca(lookalike_norm, text,
                                                              expected):
    """REQ-010: "Arcadia", "comarca" o "arcas" no son ARCA: la búsqueda no se amplía y
    no trae el texto que dice AFIP. Se comprueba también que el texto no da variantes:
    sin los límites de palabra, la variante ("AFIPdia") no coincidiría con nada y el
    resultado solo no lo mostraría."""
    assert issuer_variants(text) == [text]
    assert [r.key for r in search.by_words(text, REFERENCE_DATE)] == expected


@pytest.mark.parametrize("question", [
    "¿Qué es Arcadia?",
    "¿Qué hay en la comarca?",
    "¿Qué entra en las arcas?",
])
def test_words_path_does_not_widen_words_that_contain_arca(lookalike_norm, question,
                                                           fake_embeddings,
                                                           fake_reranker):
    """REQ-008: una pregunta con "Arcadia", "comarca" o "arcas" no suma los nombres del
    organismo al camino por palabras: no trae el texto que dice AFIP."""
    result = retrieval.retrieve(question, REFERENCE_DATE, paths=(retrieval.WORDS,))

    units = {candidate.unit_id for candidate in result.candidates}
    assert lookalike_norm["art-1"].pk not in units
    assert units
