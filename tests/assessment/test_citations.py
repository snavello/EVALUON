"""Cita ubicada por el sistema en el texto canónico y su página (REQ-053; plan 004, "Cita";
ADR-0038; T-150). Textos inventados (P4)."""

import pytest
from django.conf import settings

from evaluon.assessment import citations, documents
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


@pytest.fixture
def text(procedure, operator_user, fake_ai):
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Declaro bajo juramento que me encuentro  habilitado\npara contratar.",
                  "Los precios se cotizan en pesos con impuestos incluidos."],
        "b.pdf": ["Constancia de inscripción número 000123."]})
    return documents.build_offer_text(offer)


def doc(text, name):
    return next(d for d in text.documents if d.document.file_name == name)


def test_the_citation_is_the_cut_of_the_canonical_text_not_the_models_words(text):
    """REQ-053: el texto de la cita es el recorte del texto canónico, con la página de ahí;
    el modelo cambió los espacios y el sistema guarda los del documento."""
    finder = citations.PageFinder()
    found = citations.locate_quote(
        doc(text, "a.pdf"), "me encuentro habilitado para contratar", finder)
    assert found is not None
    canonical = doc(text, "a.pdf").reading.canonical_text
    assert found.text == canonical[found.char_start:found.char_end]
    assert found.text == "me encuentro  habilitado\npara contratar"
    assert found.page == 1


def test_the_page_comes_from_the_text_not_from_the_model(text):
    """REQ-053: la página sale del lugar del recorte en el documento."""
    finder = citations.PageFinder()
    found = citations.locate_quote(
        doc(text, "a.pdf"), "pesos con impuestos incluidos", finder)
    assert found.page == 2
    assert found.document == doc(text, "a.pdf").document
    assert found.reading == doc(text, "a.pdf").reading


def test_a_quote_that_is_not_in_the_document_is_dropped_with_its_anomaly(text):
    """REQ-053: una cita que no está en el documento no se ubica; queda la anomalía."""
    anomalies = []
    found = citations.locate_quote(
        doc(text, "a.pdf"), "inscripto en el registro", citations.PageFinder(),
        anomalies=anomalies)
    assert found is None
    assert anomalies[0]["type"] == citations.ANOMALY_NOT_FOUND


def test_a_quote_from_another_document_is_not_located_in_this_one(text):
    """REQ-053: la cita se busca solo en el documento que el modelo nombró."""
    found = citations.locate_quote(doc(text, "b.pdf"), "pesos con impuestos incluidos",
                                   citations.PageFinder())
    assert found is None


def test_a_quote_longer_than_the_limit_is_dropped(text):
    """REQ-053: una cita más larga que el máximo se descarta con su anomalía."""
    anomalies = []
    long_quote = "Los " * (settings.ASSESSMENT_CITATION_MAX_CHARS // 4 + 1)
    assert citations.locate_quote(doc(text, "a.pdf"), long_quote, citations.PageFinder(),
                                  anomalies=anomalies) is None
    assert anomalies[0]["type"] == citations.ANOMALY_TOO_LONG


def test_the_same_place_is_not_cited_twice(text):
    """REQ-053: una cita que repite otra ya ubicada se descarta."""
    finder = citations.PageFinder()
    first = citations.locate_quote(doc(text, "a.pdf"), "Declaro bajo juramento", finder)
    anomalies = []
    again = citations.locate_quote(doc(text, "a.pdf"), "Declaro bajo juramento", finder,
                                   used={first.span}, anomalies=anomalies)
    assert again is None
    assert anomalies[0]["type"] == citations.ANOMALY_REPEATED


def test_the_page_is_found_with_the_lines_of_a_real_reading(db, operator_user, fake_ai):
    """REQ-053: con la lectura real (páginas, líneas), la página sale de `pages_at`."""
    from evaluon.offers import evaluation as ev
    from tests.assessment.fakes import CASO_CHICO as DATA

    expected = ev.load_expected(DATA / "evaluacion-esperada.yaml")
    import dataclasses

    only_a = dataclasses.replace(expected, offers=expected.offers[:1])
    only_a.offers[0].documents = [d for d in only_a.offers[0].documents
                                  if d["archivo"].endswith("oferta-propuesta.pdf")]
    _, offers = ev.build_case(operator_user, only_a)
    offer_text = documents.build_offer_text(offers["Oferente A Sintético"])
    entry = offer_text.documents[0]
    finder = citations.PageFinder()
    assert finder._canonical_of(entry.reading) is not None
    found = citations.locate_quote(
        entry, "Los precios se cotizan en pesos con impuestos incluidos.", finder)
    assert found.page == 2
    assert found.text == entry.reading.canonical_text[found.char_start:found.char_end]
