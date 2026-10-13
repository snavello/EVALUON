"""Campos escritos a mano y visión con el modelo adoptado (REQ-104; T-259; informe del comité,
H2 y acción A4; ADR-0041; ADR-0057).

- Una página que el reconocimiento dio por legible en promedio, pero con un pasaje de
  confianza mínima menor que `ASSESSMENT_VISION_PASSAGE_CONFIDENCE` (la firma, la aclaración o
  la fecha escritas a mano en un formulario impreso), va a visión con el motivo
  `low_confidence_passage`, **solo si el ajuste está encendido**: por omisión vale 0 y está
  apagado (decisión del Coordinador del 2026-10-12: en el pagaré del caso-00 el 27B inventó el
  año, el concepto y el proceso; P3).
- El pedido de visión va al motor de lotes con el alias de su modelo (el 27B adoptado, en este
  test un alias inventado) y el registro dice qué modelo atendió el pedido según la respuesta
  del motor (P6).

Páginas y textos inventados (P4); el motor es un doble.
"""

import hashlib

import pytest
from django.test import override_settings

from evaluon.ai import generation
from evaluon.audit.models import Channel
from evaluon.norms.reading import DocumentReading, Line, Page, Word
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers import models as om
from evaluon.offers import passages as passage_rules
from evaluon.offers import vision
from evaluon.offers.services import offers as offers_service
from tests.assessment.fakes import pdf_of

pytestmark = pytest.mark.django_db

PRINTED = "DECLARACIÓN JURADA DE HABILIDAD PARA CONTRATAR CON EL ORGANISMO SINTÉTICO"
HANDWRITTEN = "Firma y aclaración: Fe J 0 , 1. , JS"
SEEN_TEXT = "Firma y aclaración: Juana Inventada · Fecha: 01/12/2099"
ALIAS = "modelo-adoptado-de-prueba"


PASSAGE_ON = 40


@pytest.fixture(autouse=True)
def whole_pages():
    with override_settings(ASSESSMENT_VISION_TILES=1):
        yield


@pytest.fixture
def new_offer(procedure, operator_user, fake_ai):
    return offers_service.register_offer(operator_user, procedure, bidder="Oferente manuscrito",
                                         channel=Channel.COMMAND)


def _ocr_line(text, confidence, top):
    words = [Word(text=word, confidence=confidence) for word in text.split()]
    return Line(text=text, x0=72.0, top=top, x1=540.0, bottom=top + 12, origin="ocr",
                confidence=confidence, words=words)


def read_form(offer, user, pages):
    """Un documento escaneado de `offer` con su primera lectura: `pages` es una lista de listas
    de `(texto, confianza)`, una por línea reconocida; todas las páginas quedan «legible»
    porque su confianza promedio es alta."""
    content = pdf_of(len(pages))
    document = om.Document.objects.create(
        offer=offer, title="formulario.pdf", file_name="formulario.pdf", file_format="pdf",
        file_size=len(content), file_sha256=hashlib.sha256(content).hexdigest(),
        loaded_by=user)
    om.DocumentFile.objects.create(document=document, content=content)
    reading_pages = []
    for number, lines in enumerate(pages, start=1):
        # Un párrafo por línea (separadas más que media línea), así cada una es su pasaje.
        built = [_ocr_line(text, confidence, 100.0 + 60 * index)
                 for index, (text, confidence) in enumerate(lines)]
        words = [word for line in built for word in line.words]
        reading_pages.append(Page(
            number=number, width=612.0, height=792.0, status="legible", lines=built,
            origin="ocr", confidence=round(sum(w.confidence for w in words) / len(words), 2),
            classification="escaneada"))
    reading = DocumentReading(file_format="pdf", pages=reading_pages,
                              tool_versions={"tesseract": "sintetico"})
    canonical = build_canonical_text(reading)
    specs = passage_rules.build_passages(canonical)
    vectors = offers_service._vectors(specs)
    saved = om.Reading.objects.create(
        document=document, sequence=1, pages=reading.as_json(),
        canonical_text=canonical.text,
        canonical_sha256=hashlib.sha256(canonical.text.encode()).hexdigest(),
        tool_versions=reading.tool_versions,
        report=offers_service.read_report(document, reading, specs))
    om.Passage.objects.bulk_create(
        om.Passage(reading=saved, order=spec.order, key=spec.key, page=spec.page,
                   char_start=spec.char_start, char_end=spec.char_end, text=spec.text,
                   text_origin=spec.text_origin, ocr_confidence_min=spec.ocr_confidence_min,
                   ocr_confidence_avg=spec.ocr_confidence_avg, embedding=vector)
        for spec, vector in zip(specs, vectors, strict=True))
    return document, saved


def test_a_legible_page_with_a_handwritten_field_goes_to_vision(new_offer, operator_user):
    """REQ-104 (T-259, H2): la página 1 salió legible en promedio pero trae un pasaje de
    confianza 19 (un campo escrito a mano): va a visión con el motivo
    `low_confidence_passage` y esa confianza. La página 2, legible y sin pasajes de confianza
    baja, no va."""
    document, reading = read_form(new_offer, operator_user, [
        [(PRINTED, 96.0), (PRINTED, 95.0), (PRINTED, 97.0), (PRINTED, 96.0),
         (HANDWRITTEN, 19.0)],
        [(PRINTED, 95.0), (PRINTED, 93.0)],
    ])
    assert reading.report["low_confidence"] == [] and reading.report["unread"] == []

    with override_settings(ASSESSMENT_VISION_PASSAGE_CONFIDENCE=PASSAGE_ON):
        found = vision.candidate_pages(document, reading)

    assert [(c["page"], c["reason"]) for c in found] == [(1, "low_confidence_passage")]
    assert found[0]["status"] == "legible" and found[0]["passage_confidence"] == 19.0


def test_a_passage_at_the_threshold_does_not_send_its_page(new_offer, operator_user):
    """REQ-104 (T-259): el umbral es «menor que» el ajuste: un pasaje con confianza igual al
    umbral no manda su página a visión."""
    document, reading = read_form(new_offer, operator_user, [
        [(PRINTED, 96.0), (PRINTED, 95.0), (HANDWRITTEN, float(PASSAGE_ON))],
    ])
    with override_settings(ASSESSMENT_VISION_PASSAGE_CONFIDENCE=PASSAGE_ON):
        assert vision.candidate_pages(document, reading) == []


def test_by_default_the_vision_by_passage_is_off(new_offer, operator_user):
    """REQ-104 (T-259; decisión del Coordinador del 2026-10-12; P3): por omisión el ajuste vale
    0 y una página legible con un pasaje de confianza 19 no va a visión: la transcripción
    inventaba datos."""
    from django.conf import settings

    assert settings.ASSESSMENT_VISION_PASSAGE_CONFIDENCE == 0
    document, reading = read_form(new_offer, operator_user, [
        [(PRINTED, 96.0), (PRINTED, 95.0), (PRINTED, 97.0), (HANDWRITTEN, 19.0)],
    ])
    assert vision.candidate_pages(document, reading) == []


def test_the_handwritten_page_is_transcribed_by_the_batch_engine_and_the_record_says_which(
        new_offer, operator_user, monkeypatch):
    """REQ-104 (T-259, H2; ADR-0057; P6): la página va al motor de lotes, el pedido lleva el
    alias de su modelo y el registro de la lectura nueva guarda el modelo configurado y el que
    dijo la respuesta del motor (`served_model`), con el motivo y la confianza del pasaje."""
    document, _ = read_form(new_offer, operator_user, [
        [(PRINTED, 96.0), (PRINTED, 95.0), (PRINTED, 97.0), (HANDWRITTEN, 19.0)],
    ])
    asked = []

    def generate_text(messages, *, max_tokens, repeat_penalty, base_url=None, timeout=None):
        body = generation.build_text_request(messages, max_tokens, repeat_penalty, base_url)
        asked.append((base_url, body))
        content = f"{SEEN_TEXT}\n<<FIN>>"
        response = {"model": body["model"], "choices": [
            {"index": 0, "finish_reason": "stop",
             "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 20}}
        return generation.GenerationResult(
            content=content, finish_reason="stop", prompt_tokens=300, completion_tokens=20,
            request=body, response=response)

    monkeypatch.setattr(vision.generation, "generate_text", generate_text)
    with override_settings(GENERATION_BATCH_MODEL=ALIAS,
                           GENERATION_BATCH_URL="http://generation_batch:8080",
                           GENERATION_URL="http://generation:8080",
                           ASSESSMENT_VISION_PASSAGE_CONFIDENCE=PASSAGE_ON):
        summary = vision.read_offer(new_offer, user=operator_user, channel=Channel.COMMAND)

    assert summary.read == 1 and not summary.errors
    [(base_url, body)] = asked
    assert base_url == "http://generation_batch:8080" and body["model"] == ALIAS
    reading = document.readings.order_by("-sequence").first()
    record = reading.report["vision"]
    assert record["models"]["model"] == ALIAS
    entry = record["pages"][0]
    assert entry["reason"] == "low_confidence_passage" and entry["passage_confidence"] == 19.0
    assert entry["parts"][0]["served_model"] == ALIAS
    assert SEEN_TEXT in reading.canonical_text
