"""Lectura con visión de las páginas de lectura dudosa de una oferta (REQ-052, REQ-053, REQ-054;
plan 004, enmienda 2026-10-06; ADR-0041; T-160). Páginas y fotos inventadas (P4); el motor de
lotes es un guion (`tests/assessment/fakes.py`)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import override_settings

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import ServiceUnavailableError
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.offers import models as om
from evaluon.offers import vision
from evaluon.offers.services import offers as offers_service
from tests.assessment.fakes import (  # noqa: F401 - `model` es una fixture
    VISION_DATA,
    make_read_document,
    model,
)

pytestmark = pytest.mark.django_db

PAGE_TEXT = "Papelera Ficticia S.A. mantiene su oferta por sesenta días corridos."
SEEN_TEXT = "Papelera Ficticia S.A. declara que entregará los bienes en cinco días hábiles."


@pytest.fixture
def new_offer(procedure, operator_user, fake_ai):
    return offers_service.register_offer(operator_user, procedure, bidder="Oferente de visión",
                                         channel=Channel.COMMAND)


def pages_of(reading):
    return {p["number"]: p for p in reading.pages["pages"]}


def latest(document):
    return document.readings.order_by("-sequence").first()


def test_the_criterion_sends_doubtful_unread_and_unlisted_pages_but_not_legible_or_blank(
        new_offer, operator_user):
    """REQ-052: el criterio es el del informe de la lectura: dudosas, ilegibles y páginas sin
    pasajes que no están en blanco; una página legible o en blanco nunca va a visión."""
    document = make_read_document(new_offer, operator_user, "mixto.pdf", [
        ("legible", PAGE_TEXT), ("dudosa", "Texto dudoso del reconocimiento"),
        ("ilegible", ""), ("en_blanco", ""), ("legible", ""), ("legible", PAGE_TEXT)])
    found = vision.candidate_pages(document, latest(document))
    assert [(c["page"], c["reason"]) for c in found] == [
        (2, "low_confidence"), (3, "unread"), (5, "without_text_unlisted")]
    assert found[0]["status"] == "dudosa" and found[0]["confidence"] == 65.0


def test_every_page_of_an_image_document_is_a_candidate(new_offer, operator_user):
    """ADR-0041: toda página de un documento en formato imagen va a visión, aunque el
    reconocimiento la haya dado por legible."""
    content = (VISION_DATA / "foto-tabla.png").read_bytes()
    document = make_read_document(new_offer, operator_user, "foto.png",
                                  [("legible", "Cuadro de precios")], file_format="png",
                                  content=content)
    found = vision.candidate_pages(document, latest(document))
    assert [(c["page"], c["reason"]) for c in found] == [(1, "image_format")]


def test_the_cap_is_respected_and_the_rest_is_counted(new_offer, operator_user, model):
    """REQ-052: hasta `ASSESSMENT_VISION_MAX_PAGES` páginas por oferta; las demás siguen como
    están y quedan contadas."""
    make_read_document(new_offer, operator_user, "tres.pdf",
                       [("ilegible", ""), ("ilegible", ""), ("ilegible", "")])
    model.sees(lambda seen: SEEN_TEXT)
    with override_settings(ASSESSMENT_VISION_MAX_PAGES=2):
        summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert len(model.vision_calls) == 2
    assert summary.candidates == 3 and summary.attempted == 2 and summary.over_limit == 1
    document = new_offer.documents.get()
    assert vision.vision_pages(latest(document)) == {1, 2}
    assert [e["page"] for e in latest(document).report["unread"]] == [3]
    # El tope cuenta las ya intentadas: otra pasada no manda más páginas.
    with override_settings(ASSESSMENT_VISION_MAX_PAGES=2):
        again = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert len(model.vision_calls) == 2 and again.over_limit == 1


@pytest.mark.parametrize("settings_change", [
    {"ASSESSMENT_VISION_MAX_PAGES": 0}, {"GENERATION_BATCH_MMPROJ_FILE": ""}])
def test_without_the_projector_or_with_a_zero_cap_nothing_changes(
        new_offer, operator_user, model, settings_change):
    """REQ-052: con el tope en 0 o sin `--mmproj` no se pide ninguna página y no se guarda
    ninguna lectura: el flujo sigue igual."""
    document = make_read_document(new_offer, operator_user, "uno.pdf", [("ilegible", "")])
    model.sees(lambda seen: SEEN_TEXT)
    with override_settings(**settings_change):
        summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert summary.disabled and not model.vision_calls
    assert document.readings.count() == 1


def test_a_transcription_with_too_much_illegible_leaves_the_page_unread(
        new_offer, operator_user, model):
    """REQ-052: una transcripción vacía o con más de 30 % de `[ilegible]` no cuenta como
    lectura: la página sigue "no se pudo leer"; no se vuelve a pedir."""
    document = make_read_document(new_offer, operator_user, "ruido.pdf", [
        ("ilegible", ""), ("ilegible", ""), ("ilegible", ""), ("legible", PAGE_TEXT)])
    answers = {
        1: "",
        2: "[ilegible] [ilegible] palabra [ilegible] otra",  # 3 de 5: 60 %
        3: "uno dos tres cuatro cinco seis siete [ilegible] [ilegible]",  # 2 de 9: 22 %
    }
    model.sees(lambda seen: answers[seen.number])
    summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    reading = latest(document)
    outcomes = {e["page"]: e["outcome"] for e in reading.report["vision"]["pages"]}
    assert outcomes == {1: "empty", 2: "too_illegible", 3: "read"}
    assert vision.vision_pages(reading) == {3}
    assert [e["page"] for e in reading.report["unread"]] == [1, 2]
    assert summary.read == 1 and summary.discarded == 2
    # Lo ya intentado, leído o descartado, no se repite.
    model.vision_calls.clear()
    vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert not model.vision_calls and document.readings.count() == 2


def test_the_share_of_illegible_marks_counts_marks_against_words():
    """REQ-052: la proporción es de marcas `[ilegible]` sobre marcas más palabras."""
    assert vision.illegible_share("uno dos tres") == 0
    assert vision.illegible_share("[ilegible] uno [ilegible] dos") == 0.5
    assert vision.illegible_share("[ilegible]") == 1.0


def test_an_output_that_is_not_the_requested_json_leaves_the_page_as_it_was(
        new_offer, operator_user, model):
    """REQ-052: una salida con otra forma no es una lectura; queda registrada y la página
    sigue sin leer."""
    document = make_read_document(new_offer, operator_user, "raro.pdf", [("ilegible", "")])
    model.sees(lambda seen: '{"otra": 1}')
    vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    entry = latest(document).report["vision"]["pages"][0]
    assert entry["outcome"] == "invalid_output" and entry["raw_output"] == '{"otra": 1}'
    assert vision.vision_pages(latest(document)) == set()


def test_the_new_reading_keeps_the_legible_pages_and_does_not_touch_the_previous_one(
        new_offer, operator_user, model):
    """REQ-054: lectura nueva (`sequence` siguiente) con las páginas legibles de la anterior
    tal cual y las de visión con origen `vision`; la anterior no se toca."""
    document = make_read_document(new_offer, operator_user, "pagare.pdf", [
        ("legible", PAGE_TEXT), ("ilegible", ""), ("legible", "Tercera página legible.")])
    before = latest(document)
    before_state = (before.pk, before.canonical_text, before.canonical_sha256, before.pages,
                    before.report, list(before.passages.values_list("pk", "text")))
    model.sees(lambda seen: SEEN_TEXT + "\nOtra línea de la página.")
    summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)

    after = latest(document)
    assert after.sequence == 2 and after.pk != before.pk and summary.readings == [after]
    previous = document.readings.get(sequence=1)
    assert (previous.pk, previous.canonical_text, previous.canonical_sha256, previous.pages,
            previous.report, list(previous.passages.values_list("pk", "text"))) == before_state
    by_page = {}
    for passage in after.passages.order_by("order"):
        by_page.setdefault(passage.page, []).append(passage)
    assert [p.text for p in by_page[1]] == [PAGE_TEXT] and by_page[1][0].text_origin == "pdf_text"
    assert [p.text for p in by_page[3]] == ["Tercera página legible."]
    assert {p.text_origin for p in by_page[2]} == {"vision"}
    assert SEEN_TEXT in after.canonical_text and "Otra línea de la página." in after.canonical_text
    for passage in after.passages.all():
        assert passage.text == after.canonical_text[passage.char_start:passage.char_end]
    assert pages_of(after)[2]["status"] == "legible" and pages_of(after)[2]["origin"] == "vision"
    assert after.report["unread"] == [] and after.report["vision"]["from_reading"] == before.pk
    assert vision.vision_pages(after) == {2}


def test_the_image_document_page_is_replaced_by_the_transcription_of_the_photo(
        new_offer, operator_user, model):
    """REQ-054: la foto de una tabla se transcribe con las celdas separadas por ` | ` y su
    texto reemplaza al del reconocimiento."""
    content = (VISION_DATA / "foto-tabla.png").read_bytes()
    document = make_read_document(new_offer, operator_user, "cuadro.png",
                                  [("legible", "Renglon 1 resma 3150")], file_format="png",
                                  content=content)
    table = ("CUADRO DE PRECIOS INVENTADO\nRenglón | Descripción | Cantidad | Precio unitario\n"
             "1 | Resma de papel A4 75 g | 100 | $ 3.150,00\n"
             "2 | Carpeta oficio con solapas | 40 | $ 820,50")
    model.sees(lambda seen: table)
    vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    reading = latest(document)
    assert "1 | Resma de papel A4 75 g | 100 | $ 3.150,00" in reading.canonical_text
    assert "Renglon 1 resma 3150" not in reading.canonical_text
    assert vision.vision_pages(reading) == {1}
    assert {p.text_origin for p in reading.passages.all()} == {"vision"}
    # La foto se dibuja a la resolución con que se la convirtió a PDF: con los píxeles de la foto.
    entry = reading.report["vision"]["pages"][0]
    width, height = entry["image_size"]
    assert entry["dpi"] == 300 and abs(width - 1500) <= 1 and abs(height - 900) <= 1


def test_the_request_carries_the_page_image_and_the_registered_instructions(
        new_offer, operator_user, model):
    """REQ-052: una página por pedido, con la imagen dibujada de la página y las instrucciones
    `vision-v1`, al motor de lotes."""
    from django.conf import settings

    make_read_document(new_offer, operator_user, "dos.pdf", [("ilegible", ""), ("dudosa", "x y")])
    model.sees(lambda seen: SEEN_TEXT)
    vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert len(model.vision_calls) == 2
    first = model.vision_calls[0]
    assert first.image.startswith(b"\x89PNG") and max(first.size) <= settings.ASSESSMENT_VISION_MAX_SIDE
    assert first.messages[0] == {"role": "system", "content": vision.load_prompt()}
    assert "[ilegible]" in vision.load_prompt() and "Transcrib" in vision.load_prompt()
    assert first.kwargs["max_tokens"] == settings.ASSESSMENT_VISION_MAX_OUTPUT_TOKENS
    assert first.kwargs["base_url"] == settings.GENERATION_BATCH_URL
    assert first.schema["required"] == ["transcripcion"]
    assert model.vision_calls[0].sha256 != model.vision_calls[1].sha256


def test_the_report_records_what_P6_asks_for(new_offer, operator_user, model):
    """REQ-052 (P6): modelo, huellas, compilación, parámetros, versión de las instrucciones y,
    por página, motivo, huella de la imagen, pedido sin los bytes, salida cruda, tokens y
    tiempos; y el hecho `offer_read` con la acción `vision`."""
    from django.conf import settings

    document = make_read_document(new_offer, operator_user, "p6.pdf", [("ilegible", "")])
    model.sees(lambda seen: SEEN_TEXT)
    ticks = iter(range(0, 100, 3))
    vision.read_offer(new_offer, user=operator_user, channel=Channel.COMMAND,
                      clock=lambda: next(ticks))
    reading = latest(document)
    report = reading.report["vision"]
    assert report["models"]["sha256"] == settings.GENERATION_BATCH_MODEL_SHA256
    assert report["models"]["mmproj_sha256"] == settings.GENERATION_BATCH_MMPROJ_SHA256
    assert report["models"]["mmproj_file"] and report["models"]["engine_build"] == "b11347"
    assert report["parameters"]["dpi"] == settings.ASSESSMENT_VISION_DPI
    assert report["parameters"]["image_tokens"] == settings.ASSESSMENT_VISION_IMAGE_TOKENS
    assert report["parameters"]["temperature"] == 0 and report["parameters"]["seed"] == 42
    assert report["prompt_version"] == "vision-v2"
    entry = report["pages"][0]
    assert entry["page"] == 1 and entry["reason"] == "unread" and entry["status"] == "ilegible"
    assert entry["confidence"] == 20.0 and entry["outcome"] == "read"
    seen = model.vision_calls[0]
    assert entry["image_sha256"] == seen.sha256 and entry["image_size"] == list(seen.size)
    assert entry["raw_output"] == json.dumps({"transcripcion": SEEN_TEXT}, ensure_ascii=False)
    assert "data:image" not in json.dumps(entry["request"])
    assert entry["request"]["messages"][1]["content"][1]["image_url"]["url"] == \
        f"[imagen png sha256:{seen.sha256}]"
    assert entry["prompt_tokens"] and entry["completion_tokens"] and entry["seconds"] == 3
    assert reading.tool_versions["vision"]["mmproj_sha256"]
    event = AuditEvent.objects.get(event_type=EventType.OFFER_READ,
                                   detail__action="vision")
    assert event.outcome == "ok" and event.user == operator_user
    assert event.detail["reading"] == reading.pk and event.detail["pages_read"] == [1]
    assert event.detail["vision"]["pages"][0]["image_sha256"] == seen.sha256
    assert "raw_output" not in event.detail["vision"]["pages"][0]


def test_an_engine_error_leaves_everything_as_it_was_and_stops_asking(
        new_offer, operator_user, model):
    """REQ-052: sin proyector o con el motor caído, el error queda en el resumen, no se
    guarda ninguna lectura y no se siguen pidiendo páginas."""
    document = make_read_document(new_offer, operator_user, "caido.pdf",
                                  [("ilegible", ""), ("ilegible", "")])

    def down(seen):
        raise ServiceUnavailableError("generation_batch: sin proyector", service="generation")

    model.sees(down)
    summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert len(model.vision_calls) == 1
    assert summary.read == 0 and "ServiceUnavailableError" in summary.errors[0]
    assert document.readings.count() == 1
    # Un error técnico no cuenta como intento: la próxima vez se vuelve a pedir.
    assert [c["page"] for c in vision.candidate_pages(document, latest(document))] == [1, 2]


def test_the_original_must_match_its_fingerprint(new_offer, operator_user, model):
    """REQ-052: si el original guardado no coincide con la huella, no se dibuja nada."""
    document = make_read_document(new_offer, operator_user, "cambiado.pdf", [("ilegible", "")])
    om.DocumentFile.objects.filter(document=document).update(content=b"%PDF-otro")
    summary = vision.read_offer(new_offer, user=None, channel=Channel.COMMAND)
    assert not model.vision_calls and "OriginalChanged" in summary.errors[0]


def test_a_passage_may_have_the_vision_origin_and_no_other_new_one(new_offer, operator_user):
    """REQ-054: el único cambio de esquema es el valor `vision` del origen del pasaje."""
    document = make_read_document(new_offer, operator_user, "origen.pdf", [("legible", PAGE_TEXT)])
    passage = latest(document).passages.get()
    om.Passage.objects.filter(pk=passage.pk)  # sigue existiendo
    assert "vision" in om.PassageOrigin.values
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                       "WHERE conname = 'offers_passage_text_origin_valid'")
        definition = cursor.fetchone()[0]
    assert "vision" in definition
    with pytest.raises(IntegrityError), transaction.atomic():
        om.Passage.objects.create(
            reading=latest(document), order=99, key="p9/b9", page=9, char_start=0, char_end=1,
            text="x", text_origin="inventado", embedding=[0.0] * 1024)


def test_only_a_commission_role_may_ask_for_the_reading_by_hand(new_offer, no_commission_user):
    """REQ-052: el comando lo hacen el operador y el evaluador."""
    with pytest.raises(RoleRejected):
        vision.read_offer_for(no_commission_user, new_offer)


def test_the_command_reads_an_offer_with_vision(new_offer, operator_user, model, monkeypatch,
                                                procedure):
    """REQ-052: `leer_con_vision` corre la lectura sobre una oferta y cuenta lo que hizo."""
    from tests.conftest import TEST_PASSWORD

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    make_read_document(new_offer, operator_user, "cmd.pdf", [("ilegible", "")])
    model.sees(lambda seen: SEEN_TEXT)
    out = StringIO()
    call_command("leer_con_vision", "--usuario", operator_user.username,
                 "--procedimiento", procedure.number, "--oferta", str(new_offer.number),
                 stdout=out)
    assert "lectura 2 con 1 páginas leídas por visión" in out.getvalue()
    assert "1 páginas dudosas, 1 pedidas, 1 leídas" in out.getvalue()
    with pytest.raises(CommandError):
        call_command("leer_con_vision", "--usuario", operator_user.username,
                     "--procedimiento", procedure.number, "--oferta", "999", stdout=out)
