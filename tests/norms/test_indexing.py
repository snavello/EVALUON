"""Pasajes de búsqueda y sus vectores (T-015; plan 001, "Unidades base, incisos y
pasajes" y `norms_passage`).

Un pasaje por unidad base, con su encabezado de contexto (norma y ruta), su texto, su
vector y el nombre y la huella del modelo que lo calculó. La partición de unidades largas
es de T-031. Los datos son sintéticos (P4) y el vector lo da el doble de embeddings.
"""

import pytest
from django.conf import settings

from evaluon.norms import indexing
from evaluon.norms.models import Passage


def annex_norm(make_norm):
    return make_norm(norm_type="disposicion", number="247", year=2022, issuer="afip")


def test_passage_document_is_header_newline_text():
    """REQ-005: el texto que se convierte en vector es el encabezado y el texto del
    pasaje unidos por un salto de línea, la misma forma con que la recuperación puntúa
    cada pasaje. Se fija la forma exacta."""
    assert (
        indexing.passage_document("Disposición AFIP 247/2022, Anexo, Artículo 1", "Texto.")
        == "Disposición AFIP 247/2022, Anexo, Artículo 1\nTexto."
    )


@pytest.mark.django_db
def test_header_is_norm_name_and_path(make_norm, make_document, make_reading):
    """REQ-005: el encabezado de contexto de un pasaje es el nombre de la norma y la
    ruta de la unidad, con sus tramos separados por comas."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm, part="anexo"), [
        ("anexo", "ANEXO"),
        {"key": "anexo/art-50", "text": "ARTÍCULO 50.- Garantías sintéticas.",
         "path": "Anexo › Título II › Capítulo V › Artículo 50"},
        {"key": "anexo/clausula-transitoria", "text": "CLÁUSULA TRANSITORIA Texto.",
         "path": "Anexo › Cláusula transitoria"},
    ], status="pending", passages=False)
    units = reading.units_by_key

    assert indexing.norm_name(norm) == "Disposición AFIP 247/2022"
    assert indexing.passage_header(norm, units["anexo/art-50"]) == (
        "Disposición AFIP 247/2022, Anexo, Título II, Capítulo V, Artículo 50"
    )
    assert indexing.passage_header(norm, units["anexo/clausula-transitoria"]) == (
        "Disposición AFIP 247/2022, Anexo, Cláusula transitoria"
    )


@pytest.mark.django_db
def test_one_passage_per_base_unit_and_none_for_incisos(
    make_norm, make_document, make_reading
):
    """REQ-005: cada unidad base da un pasaje con todo su texto; los incisos no generan
    pasajes."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTICULO 1.- Objeto sintético: a) primero."),
        ("art-1/inc-a", "a) primero."),
        ("art-2", "ARTICULO 2.- Comuníquese."),
    ], status="pending", passages=False)
    units = reading.units_by_key

    drafts = indexing.build_passages(reading)

    assert [d.unit.key for d in drafts] == ["art-1", "art-2"]
    for draft in drafts:
        assert draft.order == 1
        assert draft.char_start == 0
        assert draft.char_end == len(draft.unit.text)
        assert draft.text == draft.unit.text
        assert draft.header == indexing.passage_header(norm, draft.unit)
    assert drafts[0].unit.pk == units["art-1"].pk


@pytest.mark.django_db
def test_annex_with_articles_contributes_only_its_own_text(
    make_norm, make_document, make_reading
):
    """REQ-005: un anexo que contiene artículos aporta como pasaje solo su texto propio
    (lo que va antes del primer artículo), para que ningún texto quede en pasajes de dos
    unidades base."""
    norm = annex_norm(make_norm)
    annex_text = "ANEXO\nDisposiciones sintéticas.\nARTÍCULO 1°.- Objeto sintético."
    article_text = "ARTÍCULO 1°.- Objeto sintético."
    start = annex_text.index(article_text)
    reading = make_reading(make_document(norm, part="anexo"), [
        {"key": "anexo", "text": annex_text, "char_start": 0, "char_end": len(annex_text)},
        {"key": "anexo/art-1", "text": article_text, "char_start": start,
         "char_end": start + len(article_text)},
    ], status="pending", passages=False)

    drafts = {d.unit.key: d for d in indexing.build_passages(reading)}

    assert drafts["anexo"].text == "ANEXO\nDisposiciones sintéticas."
    assert drafts["anexo"].char_start == 0
    assert drafts["anexo"].char_end == len("ANEXO\nDisposiciones sintéticas.")
    assert drafts["anexo/art-1"].text == article_text


@pytest.mark.django_db
def test_vectors_are_computed_on_header_and_text(
    make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-005, REQ-012: el vector de cada pasaje se calcula sobre
    `passage_document(header, text)`, con el cliente de embeddings, y el pasaje guarda
    el vector, el nombre del modelo y la huella del archivo del modelo."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTICULO 1.- Objeto sintético."),
        ("art-2", "ARTICULO 2.- Comuníquese."),
    ], status="pending", passages=False)
    drafts = indexing.build_passages(reading)
    expected_documents = [indexing.passage_document(d.header, d.text) for d in drafts]
    fake_embeddings.vectors[expected_documents[0]] = [0.5] * 1024

    vectors = indexing.embed_passages(drafts)
    indexing.save_passages(drafts, vectors)

    assert fake_embeddings.calls == [expected_documents]
    stored = list(Passage.objects.filter(unit__reading=reading).order_by("unit__order"))
    assert [p.unit.key for p in stored] == ["art-1", "art-2"]
    assert list(stored[0].embedding) == [0.5] * 1024
    assert list(stored[1].embedding) == fake_embeddings.vector_for(expected_documents[1])
    for passage, draft in zip(stored, drafts):
        assert passage.header == draft.header
        assert passage.text == draft.text
        assert passage.embedding_model == settings.EMBEDDINGS_MODEL
        assert passage.embedding_revision == settings.EMBEDDINGS_MODEL_SHA256
