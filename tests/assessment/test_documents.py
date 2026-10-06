"""Documentos de la oferta como texto por página, copias, grupos y ventanas (REQ-054; plan 004,
"Qué se lee y cómo se agrupa"; ADR-0037; T-150). Textos inventados (P4). El contador de tokens
es el del doble de pruebas (una palabra, un token)."""

import pytest

from evaluon.assessment import documents
from evaluon.offers import models as om
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


def words(n, prefix="palabra"):
    return " ".join(f"{prefix}{i}" for i in range(n))


@pytest.fixture(autouse=True)
def _ai(fake_ai):
    return fake_ai


def build(offer, budget=20000):
    return documents.build_offer_text(offer, budget=budget)


def test_a_small_offer_is_one_group_in_load_order(procedure, operator_user):
    """REQ-054: si toda la oferta entra, es un solo grupo y no se ordena nada: los documentos
    enteros, en el orden de carga."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Texto de la primera.", "Texto de la segunda."], "b.pdf": ["Otro."]})
    text = build(offer)
    assert text.fits and not text.has_unread
    plan = documents.plan_groups(text)
    assert plan.unread_groups == 0
    assert [[p.doc.document.file_name for p in group] for group in plan.groups] == [
        ["a.pdf", "b.pdf"]]
    assert text.pieces[0].render().splitlines()[2] == "--- página 1 ---"


def test_a_page_that_could_not_be_read_is_marked_and_listed(procedure, operator_user):
    """REQ-054: una página ilegible figura "no se pudo leer" en el texto y en la lista de lo
    que el modelo no vio."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Uno.", "Dos."]}, unread=[("a.pdf", 2)])
    text = build(offer)
    assert "--- página 2: no se pudo leer ---" in text.pieces[0].render()
    assert text.has_unread
    assert [(u["title"], u["page"]) for u in text.unread] == [("a.pdf", 2)]


def test_documents_with_identical_text_are_counted_once(procedure, operator_user):
    """REQ-054: el documento de texto canónico idéntico figura como copia del primero; no
    suma tokens ni páginas ni grupos."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "poliza.pdf": ["Póliza de caución por veinte mil pesos."],
        "poliza-copia.pdf": ["Póliza de caución por veinte mil pesos."],
        "otro.pdf": ["Texto distinto."]})
    text = build(offer)
    by_name = {d.document.file_name: d for d in text.documents}
    assert by_name["poliza-copia.pdf"].copy_of == by_name["poliza.pdf"].document.pk
    assert by_name["poliza.pdf"].copy_of is None
    assert [p.doc.document.file_name for p in text.pieces] == ["poliza.pdf", "otro.pdf"]
    record = {r["file"]: r for r in text.record()}
    assert record["poliza-copia.pdf"]["copy_of"] == by_name["poliza.pdf"].document.pk


def test_tokens_are_counted_once_per_document_and_page(procedure, operator_user, fake_ai,
                                                       monkeypatch):
    """REQ-054: los tokens se cuentan por documento y por página, una vez, no por requisito."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Uno dos tres.", "Cuatro cinco."]})
    seen = []
    monkeypatch.setattr(documents.generation, "count_tokens",
                        lambda text: seen.append(text) or len(text.split()))
    text = build(offer)
    assert len(seen) == 3  # el encabezado y las dos páginas
    document = text.documents[0]
    assert document.page_tokens == [7, 6]  # cada página lleva su encabezado "--- página k ---"
    assert document.tokens == document.header_tokens + 13


def test_a_big_offer_is_packed_in_several_groups_by_relevance(procedure, operator_user):
    """REQ-054: si no entra, los documentos se ordenan por relevancia y se empaquetan enteros;
    la relevancia ordena y no descarta."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": [words(50, "a")], "b.pdf": [words(50, "b")], "c.pdf": [words(50, "c")]})
    text = build(offer, budget=130)
    assert not text.fits
    by_name = {d.document.file_name: d.document.pk for d in text.documents}
    scores = {by_name["c.pdf"]: 0.9, by_name["a.pdf"]: 0.2}
    plan = documents.plan_groups(text, scores)
    names = [[p.doc.document.file_name for p in group] for group in plan.groups]
    assert names == [["c.pdf", "a.pdf"], ["b.pdf"]]
    assert plan.unread_groups == 0
    # sin puntajes, el orden de carga
    plain = documents.plan_groups(text)
    assert [[p.doc.document.file_name for p in g] for g in plain.groups] == [
        ["a.pdf", "b.pdf"], ["c.pdf"]]


def test_a_document_bigger_than_the_budget_is_split_in_windows(procedure, operator_user):
    """REQ-054: un documento mayor que el presupuesto se parte por páginas, con una página de
    solape; cada ventana dice qué páginas trae."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "largo.pdf": [words(40), words(40), words(40), words(40)]})
    text = build(offer, budget=100)
    windows = [(p.first_page, p.last_page) for p in text.pieces]
    assert windows == [(1, 2), (2, 3), (3, 4)]
    assert "Páginas 2 a 3" in text.pieces[1].render()
    assert "--- página 1 ---" not in text.pieces[1].render()
    assert text.record()[0]["windows"] == [[1, 2], [2, 3], [3, 4]]


def test_groups_past_the_limit_are_not_read_and_are_counted(procedure, operator_user,
                                                            settings):
    """REQ-054: se pregunta por todos los grupos hasta el tope; los que pasan quedan contados
    y sin leer."""
    settings.ASSESSMENT_MAX_GROUPS = 2
    offer = make_offer(procedure, operator_user, "Oferente A", {
        f"{n}.pdf": [words(60, n)] for n in "abcd"})
    text = build(offer, budget=70)
    plan = documents.plan_groups(text)
    assert len(plan.groups) == 2
    assert plan.unread_groups == 2
    assert {p.doc.document.file_name for p in plan.skipped} == {"c.pdf", "d.pdf"}


def test_a_document_without_reading_is_listed_as_unread(procedure, operator_user):
    """REQ-054: un documento sin lectura no se inventa: queda listado como sin leer."""
    offer = make_offer(procedure, operator_user, "Oferente A", {"a.pdf": ["Texto."]})


    document = om.Document.objects.create(
        offer=offer, title="sin lectura", file_name="x.pdf", file_format="pdf", file_size=1,
        file_sha256="a" * 64, loaded_by=operator_user)
    text = build(offer)
    assert text.without_reading == [document.pk]
    assert text.has_unread


def test_relevance_is_the_best_reranker_score_of_each_document(procedure, operator_user,
                                                               fake_ai):
    """REQ-054: la relevancia de un documento es el mayor puntaje del reranker entre sus
    pasajes recuperados."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Garantía de mantenimiento de la oferta por pesos."],
        "b.pdf": ["Constancia de inscripción en el registro."]})
    fake_ai.reranker.scores = {"Garantía": 0.8, "Constancia": 0.3}
    text = build(offer)
    scores, found = documents.relevance(text, "garantía de mantenimiento")
    by_name = {d.document.file_name: d.document.pk for d in text.documents}
    assert scores[by_name["a.pdf"]] == pytest.approx(0.8)
    assert scores[by_name["b.pdf"]] == pytest.approx(0.3)
    assert found.query == "garantía de mantenimiento"
