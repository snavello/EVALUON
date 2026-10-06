"""Medida de tamaños de las ofertas y su comando (REQ-054; plan 004, "Qué se lee y cómo se
agrupa"; ADR-0037; T-148). El contador de tokens es el del doble de pruebas (una palabra, un
token). Textos inventados (P4)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluon.accounts import permissions
from evaluon.assessment import sizing
from tests.conftest import count_words
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


def words(n, prefix="palabra"):
    return " ".join(f"{prefix}{i}" for i in range(n))


# --- Armado de páginas ---------------------------------------------------------------------


def test_a_reading_is_split_by_page_with_unreadable_pages_marked(procedure, operator_user):
    """REQ-054: el texto de una página son sus pasajes; una página que el informe lista como
    sin leer se marca como ilegible."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": ["Texto de la primera.", "Texto de la segunda.", "Texto de la tercera."]},
        unread=[("a.pdf", 2)])
    reading = offer.documents.get().readings.get()
    pages = sizing.document_pages(reading)
    assert [(p["page"], p["readable"]) for p in pages] == [(1, True), (2, False), (3, True)]
    assert sizing.render_page(pages[0]) == "--- página 1 ---\nTexto de la primera."
    assert sizing.render_page(pages[1]) == "--- página 2: no se pudo leer ---"


def test_the_pages_of_the_report_without_passages_are_listed_too(procedure, operator_user):
    """REQ-054: una página del informe sin pasajes figura con texto vacío; una listada como
    sin leer, ilegible."""
    offer = make_offer(procedure, operator_user, "Oferente A", {"a.pdf": ["Uno.", "Dos."]})
    reading = offer.documents.get().readings.get()
    reading.report = {"pages": 4, "unread": [{"page": 4}]}
    pages = sizing.document_pages(reading)
    assert [(p["page"], p["text"], p["readable"]) for p in pages] == [
        (1, "Uno.", True), (2, "Dos.", True), (3, "", True), (4, "", False)]


# --- Empaquetado y ventanas ----------------------------------------------------------------


def test_pack_fills_groups_in_order_up_to_the_budget():
    """REQ-054: documentos enteros, en el orden dado, hasta el presupuesto."""
    items = [{"id": n, "tokens": t} for n, t in enumerate([6, 6, 6, 6, 3], start=1)]
    groups = sizing.pack(items, 14)
    assert [[i["id"] for i in group] for group in groups] == [[1, 2], [3, 4], [5]]


def test_pack_puts_an_oversized_item_alone_and_keeps_the_order():
    items = [{"id": 1, "tokens": 2}, {"id": 2, "tokens": 50}, {"id": 3, "tokens": 2}]
    groups = sizing.pack(items, 10)
    assert [[i["id"] for i in group] for group in groups] == [[1], [2], [3]]


def test_pack_of_nothing_is_no_group():
    assert sizing.pack([], 10) == []


def test_windows_split_by_pages_with_one_page_of_overlap():
    """REQ-054: un documento mayor que el presupuesto se parte por páginas, con una página
    de solape."""
    assert sizing.windows([4, 4, 4, 4, 4], 10) == [[0, 1], [1, 2], [2, 3], [3, 4]]
    assert sizing.windows([4, 4, 4], 100) == [[0, 1, 2]]


def test_a_single_page_over_the_budget_gets_its_own_window():
    assert sizing.windows([3, 50, 3], 10) == [[0], [1], [2]]


# --- Medida de una oferta ------------------------------------------------------------------


def test_a_small_offer_is_one_group_and_counts_tokens_per_document_and_page(
        procedure, operator_user, fake_ai):
    """REQ-054: la oferta chica entra en un grupo; los tokens salen por página y por
    documento."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": [words(10), words(20)], "b.pdf": [words(5)]})
    measure = sizing.measure_offer(offer, budget=1000)
    assert measure["pages"] == 3 and measure["documents_count"] == 2
    first, second = measure["documents"]
    assert first["page_tokens"] == [count_words(f"--- página 1 ---\n{words(10)}"),
                                    count_words(f"--- página 2 ---\n{words(20)}")]
    assert first["tokens"] == sum(first["page_tokens"]) + count_words(
        "Documento: a.pdf\nArchivo: a.pdf")
    assert measure["tokens"] == first["tokens"] + second["tokens"]
    assert measure["groups"] == 1
    assert measure["group_tokens"] == [measure["tokens"]]


def test_a_bigger_offer_is_packed_in_load_order(procedure, operator_user, fake_ai):
    """REQ-054: se arman grupos de documentos enteros hasta el presupuesto, en el orden de
    carga."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": [words(40, "a")], "b.pdf": [words(40, "b")], "c.pdf": [words(40, "c")]})
    one = sizing.measure_offer(offer, budget=10_000)["documents"][0]["tokens"]
    measure = sizing.measure_offer(offer, budget=one * 2)
    assert measure["groups"] == 2
    assert measure["group_tokens"] == [one * 2, one]


def test_copies_of_identical_text_are_counted_once(procedure, operator_user, fake_ai):
    """REQ-054: los documentos de texto idéntico se cuentan una vez; el resto figura como
    copia de aquel que quedó."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": [words(30)], "a (1).pdf": [words(30)], "b.pdf": [words(7)]})
    measure = sizing.measure_offer(offer, budget=10_000)
    original, copy, other = measure["documents"]
    assert copy["copy_of"] == original["document"] and original["copy_of"] is None
    assert measure["copies"] == 1
    assert measure["tokens"] == original["tokens"] + other["tokens"]
    assert measure["tokens_with_copies"] == measure["tokens"] + copy["tokens"]
    assert measure["pages"] == 2


def test_a_document_over_the_budget_is_split_in_windows(procedure, operator_user, fake_ai):
    """REQ-054: un documento mayor que el presupuesto se parte en ventanas por páginas y
    cada ventana cuenta como un item del empaquetado."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "grande.pdf": [words(30, f"g{n}_") for n in range(4)], "chico.pdf": [words(3)]})
    page = sizing.measure_offer(offer, budget=10_000)["documents"][0]["page_tokens"][0]
    measure = sizing.measure_offer(offer, budget=page * 2)
    assert measure["windowed"] == [{"document": measure["documents"][0]["document"],
                                    "windows": 3}]
    assert measure["groups"] == 4
    assert measure["largest_document_tokens"] > page * 2


def test_unread_pages_are_counted(procedure, operator_user, fake_ai):
    """REQ-054: las páginas ilegibles figuran como tales y se cuentan aparte."""
    offer = make_offer(procedure, operator_user, "Oferente A", {
        "a.pdf": [words(5), "", words(5)]}, unread=[("a.pdf", 2)])
    measure = sizing.measure_offer(offer, budget=1000)
    assert measure["unread_pages"] == 1
    assert measure["pages"] == 3


def test_a_document_without_reading_is_listed_and_not_counted(procedure, operator_user,
                                                              fake_ai):
    offer = make_offer(procedure, operator_user, "Oferente A", {"a.pdf": [words(5)]})
    from evaluon.offers import models as om
    om.Document.objects.create(offer=offer, title="x.pdf", file_name="x.pdf",
                               file_format="pdf", file_size=1, file_sha256="f" * 64,
                               loaded_by=operator_user)
    measure = sizing.measure_offer(offer, budget=1000)
    assert measure["without_reading"] == 1
    assert measure["documents"][1]["reading"] is None
    assert measure["groups"] == 1


# --- Comando -------------------------------------------------------------------------------


@pytest.fixture
def logged_in(monkeypatch, operator_user):
    from tests.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    return operator_user


def run_command(*args):
    out = StringIO()
    call_command("medir_tamanos", *args, stdout=out)
    return out.getvalue()


def test_the_command_reports_counts_per_offer_and_saves_the_detail_apart(
        logged_in, procedure, fake_ai, tmp_path, monkeypatch):
    """REQ-054: el comando informa las cuentas por oferta y guarda el detalle por documento
    en la carpeta indicada, fuera del repositorio; lo que sale en pantalla no nombra
    documentos."""
    make_offer(procedure, logged_in, "Oferente A", {"secreto.pdf": [words(10)]})
    make_offer(procedure, logged_in, "Oferente B", {"x.pdf": [words(4)], "y.pdf": [words(4)]})
    output = run_command("--usuario", logged_in.username, "--procedimiento",
                         procedure.number, "--corridas", str(tmp_path))
    assert "Oferta 1" in output and "Oferta 2" in output
    assert "configurado del motor de lotes: 32768" in output
    assert "secreto.pdf" not in output and "Oferente" not in output
    detail = json.loads(next(tmp_path.glob("*/tamanos.json")).read_text(encoding="utf-8"))
    assert detail["offers"][0]["documents"][0]["file"] == "secreto.pdf"
    assert detail["engine"]["context_configured"] == 32768
    assert len(detail["offers"][1]["documents"]) == 2


def test_the_command_refuses_a_user_without_a_commission_role(
        no_commission_user, procedure, monkeypatch):
    """REQ-054: un usuario sin rol de la Comisión no mide; el rechazo queda registrado."""
    from evaluon.audit.models import AuditEvent, EventType
    from tests.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    with pytest.raises(CommandError):
        run_command("--usuario", no_commission_user.username, "--procedimiento",
                    procedure.number)
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def test_the_command_needs_offers(logged_in, procedure, fake_ai):
    with pytest.raises(CommandError, match="no tiene ofertas"):
        run_command("--usuario", logged_in.username, "--procedimiento", procedure.number)


def test_the_command_needs_an_existing_procedure(logged_in, fake_ai):
    with pytest.raises(CommandError, match="No hay un procedimiento"):
        run_command("--usuario", logged_in.username, "--procedimiento", "NO-EXISTE")
