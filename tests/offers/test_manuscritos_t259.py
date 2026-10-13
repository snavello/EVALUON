"""Pasajes escritos a mano que el reconocimiento no lee (REQ-104; T-259; decisión del Coordinador
del 2026-10-12; P3, P6).

Una línea reconocida con confianza menor que `OFFERS_HANDWRITTEN_CONFIDENCE` (una firma, una
fecha o un número de proceso escritos a mano) no entra en el texto de la oferta: la lectura la
reemplaza por «no se pudo leer · manuscrito: revisar el original» y guarda la línea original
descartada con ese motivo. La evaluación trata su página como «no se pudo leer» para ese dato: el
sistema avala el «no se pudo leer» con esa página del original y la transcripción nunca llega al
modelo ni a una cita.

La marca queda **apagada por omisión** (`OFFERS_HANDWRITTEN_CONFIDENCE` en 0, decisión del
Coordinador del 2026-10-12: la confianza baja no distingue un manuscrito de una línea impresa mal
escaneada); estos tests la encienden adentro.

Páginas y textos inventados (P4).
"""

import pytest
from django.test import override_settings

from evaluon.assessment import documents as assessment_documents
from evaluon.assessment import sizing, unreadable
from evaluon.audit.models import Channel
from evaluon.norms.reading import DocumentReading, Line, Page, Word
from evaluon.offers import reading as reading_tools
from evaluon.offers.services import offers as offers_service
from evaluon.tenders import jobs
from tests.assessment.fakes import pdf_of

pytestmark = pytest.mark.django_db

PRINTED = "DECLARACIÓN JURADA DE HABILIDAD PARA CONTRATAR CON EL ORGANISMO SINTÉTICO"
GARBAGE = "Firma y aclaración: Fe J 0 , 1. , JS"


def _line(text, confidence, top):
    return Line(text=text, x0=72.0, top=top, x1=540.0, bottom=top + 12, origin="ocr",
                confidence=confidence,
                words=[Word(text=word, confidence=confidence) for word in text.split()])


def scanned_form():
    """Una página escaneada «legible» en promedio con un campo escrito a mano de confianza 7."""
    lines = [_line(PRINTED, 96.0, 100.0), _line(PRINTED, 95.0, 160.0),
             _line(GARBAGE, 7.0, 220.0)]
    return DocumentReading(file_format="pdf", tool_versions={"tesseract": "sintetico"}, pages=[
        Page(number=1, width=612.0, height=792.0, status="legible", lines=lines, origin="ocr",
             confidence=66.0, classification="escaneada")])


def test_the_handwritten_line_is_replaced_by_the_mark_and_kept_as_discarded():
    """REQ-104 (T-259; P6): la línea de confianza 7 queda en la lectura, descartada con el motivo
    «manuscrito: revisar el original», y en su lugar va la marca; las demás no cambian."""
    marked = reading_tools.mark_handwritten(scanned_form(), threshold=40)
    lines = marked.pages[0].lines
    assert [line.text for line in lines if not line.discarded] == [
        PRINTED, PRINTED, reading_tools.HANDWRITTEN_MARK]
    [kept] = [line for line in lines if line.discarded]
    assert kept.text == GARBAGE and kept.discarded == "manuscrito: revisar el original"
    assert reading_tools.handwritten_lines(marked) == [(1, 7.0)]
    assert reading_tools.mark_handwritten(scanned_form(), threshold=0) == scanned_form()


def test_by_default_nothing_is_marked_as_handwritten(
        procedure, operator_user, fake_ai, monkeypatch):
    """REQ-104 (T-259; decisión del Coordinador del 2026-10-12): por omisión el ajuste vale 0 y
    la lectura no marca nada: la línea de confianza baja queda en el texto como la leyó el
    reconocimiento y el informe no lista manuscritos."""
    from django.conf import settings

    assert settings.OFFERS_HANDWRITTEN_CONFIDENCE == 0
    assert reading_tools.mark_handwritten(scanned_form()) == scanned_form()
    offer = offers_service.register_offer(operator_user, procedure, bidder="Impreso S.A.",
                                          channel=Channel.COMMAND)
    _, reading = read_job(monkeypatch, offer, operator_user)
    assert GARBAGE in reading.canonical_text
    assert reading.report["handwritten"] == []


def read_job(monkeypatch, offer, user):
    """Lee un documento de `offer` con el pedido real; el reconocimiento devuelve el formulario
    inventado (así la confianza baja es la del test, no la de Tesseract)."""
    monkeypatch.setattr(reading_tools, "read_with_second_attempt",
                        lambda pdf: (scanned_form(), []))
    loaded = offers_service.load_document(user, offer, data=pdf_of(1), file_name="dj.pdf")
    while jobs.run_next() is not None:
        pass
    return loaded.document, loaded.document.readings.order_by("-sequence").first()


def test_the_transcription_never_reaches_the_text_the_passages_or_the_model(
        procedure, operator_user, fake_ai, monkeypatch):
    """REQ-104 (T-259; P3): leída la oferta, el texto canónico y los pasajes traen la marca y no
    la transcripción; el informe lista la página con su motivo; la página que ve el modelo trae
    la marca."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Manuscrito S.A.",
                                          channel=Channel.COMMAND)
    with override_settings(OFFERS_HANDWRITTEN_CONFIDENCE=40):
        document, reading = read_job(monkeypatch, offer, operator_user)

    assert GARBAGE not in reading.canonical_text
    assert reading_tools.HANDWRITTEN_MARK in reading.canonical_text
    assert not any(GARBAGE in p.text for p in reading.passages.all())
    [entry] = reading.report["handwritten"]
    assert entry["page"] == 1 and entry["reason"] == "manuscrito: revisar el original"
    [page] = sizing.document_pages(reading)
    assert page["handwritten"] and page["readable"]
    assert reading_tools.HANDWRITTEN_MARK in sizing.render_page(page)
    assert GARBAGE not in sizing.render_page(page)


def test_the_evaluation_backs_no_se_pudo_leer_with_that_page_of_the_original(
        procedure, operator_user, fake_ai, monkeypatch):
    """REQ-104 (T-259): para la evaluación la página con el manuscrito cuenta como no leída: la
    oferta la lista entre sus páginas sin leer y el «no se pudo leer» que pida el modelo para ese
    documento queda avalado con esa página («no determinado», con la página del original)."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Manuscrito S.A.",
                                          channel=Channel.COMMAND)
    with override_settings(OFFERS_HANDWRITTEN_CONFIDENCE=40):
        document, _ = read_job(monkeypatch, offer, operator_user)

    offer_text = assessment_documents.build_offer_text(offer, count=lambda text: len(text))
    assert {"document": document.pk, "title": document.title, "page": 1} in offer_text.unread
    [piece] = [p for p in offer_text.pieces if p.doc.document.pk == document.pk]
    backed = unreadable.resolve(piece, offer_text.unread)
    assert backed["documento_id"] == document.pk and backed["pagina"] == 1
