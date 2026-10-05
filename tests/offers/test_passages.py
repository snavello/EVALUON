"""Partir la lectura de un documento de una oferta en pasajes (REQ-038, REQ-039; plan 008,
"Pasajes"; T-130). Texto inventado (P4); se arma el texto canónico con la lectura real de la
001 sobre PDF sintéticos."""

import pytest

from evaluon.norms.reading import read_document
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers.passages import build_passages
from tests.tenders.pdfs import para, tender_pdf


def passages_of(pages):
    canonical = build_canonical_text(read_document(tender_pdf(pages, header=None)))
    return canonical, build_passages(canonical)


def test_a_passage_is_the_literal_slice_of_the_canonical_text():
    """REQ-039: el texto de un pasaje es el recorte del texto canónico."""
    canonical, specs = passages_of([[para("Primer párrafo de la oferta."),
                                     para("Segundo párrafo de la oferta.")]])
    assert specs
    for spec in specs:
        assert spec.text == canonical.text[spec.char_start:spec.char_end]


def test_a_passage_never_crosses_a_page():
    """REQ-039: su página es la suya; ninguno cruza de una página a otra."""
    _, specs = passages_of([[para("Texto de la página uno.")],
                            [para("Texto de la página dos.")]])
    assert [spec.page for spec in specs] == [1, 2]
    assert [spec.key for spec in specs] == ["p1/b1", "p2/b1"]
    assert all("página dos" not in s.text for s in specs if s.page == 1)


def test_small_blocks_join_the_next_one_of_their_page(settings):
    """Un bloque de menos del mínimo se une al siguiente de su página."""
    settings.OFFERS_PASSAGE_MIN_CHARS = 200
    _, specs = passages_of([[para("Uno."), para("Dos."), para("Tres.")]])
    assert len(specs) == 1
    assert "Uno." in specs[0].text and "Tres." in specs[0].text


def test_blocks_over_the_minimum_stay_apart(settings):
    settings.OFFERS_PASSAGE_MIN_CHARS = 10
    _, specs = passages_of([[para("Primer párrafo largo de la oferta."),
                             para("Segundo párrafo largo de la oferta.")]])
    assert len(specs) == 2
    assert [spec.key for spec in specs] == ["p1/b1", "p1/b2"]


def test_a_long_block_is_split_at_sentence_boundaries(settings):
    """Un bloque de más del máximo se parte en límite de oración, sin perder texto."""
    settings.OFFERS_PASSAGE_MAX_CHARS = 120
    settings.OFFERS_PASSAGE_MIN_CHARS = 10
    sentences = [f"Esta es la oración número {n} de la oferta sintética." for n in range(1, 8)]
    canonical, specs = passages_of([[para(*sentences)]])
    assert len(specs) > 1
    assert all(len(spec.text) <= 120 for spec in specs)
    assert all(spec.text.endswith(".") for spec in specs)
    joined = " ".join(spec.text for spec in specs)
    assert joined == canonical.text


def test_a_sentence_longer_than_the_maximum_is_split_at_a_space(settings):
    settings.OFFERS_PASSAGE_MAX_CHARS = 60
    settings.OFFERS_PASSAGE_MIN_CHARS = 10
    words = " ".join(["palabra"] * 30)
    _, specs = passages_of([[para(words)]])
    assert len(specs) > 1
    assert all(len(spec.text) <= 60 for spec in specs)
    assert all(not spec.text.startswith(" ") and not spec.text.endswith(" ")
               for spec in specs)


def test_a_page_without_text_has_no_passages():
    """Una página sin texto no genera pasajes."""
    from tests.tenders.pdfs import fields_only_page

    _, specs = passages_of([[para("Texto de la página uno.")], fields_only_page()])
    assert {spec.page for spec in specs} == {1}


@pytest.mark.parametrize("pages", [1, 3])
def test_orders_are_consecutive(pages):
    _, specs = passages_of([[para(f"Texto de la página {n}.")] for n in range(1, pages + 1)])
    assert [spec.order for spec in specs] == list(range(1, len(specs) + 1))
