"""Pantallas de ofertas y de la ficha (REQ-037, REQ-038, REQ-039, REQ-040, REQ-043, REQ-044;
plan 008, "Pantalla"; ADR-0005; T-130). El caso es el chico, inventado; el modelo es un
guion. Se prueban con el cliente de pruebas de Django."""

import html
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import sheets
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from tests.conftest import TEST_PASSWORD
from tests.offers.conftest import DATA, make_offer, pick

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    """El texto visible de la página: sin etiquetas, con los espacios colapsados y sin
    espacio antes de los signos de puntuación."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", response.content.decode()))
    return re.sub(r"\s+(?=[.,;:])", "", " ".join(text.split()))


def test_the_offers_page_lists_the_offers_and_registers_one(client, operator_user, procedure,
                                                            offer):
    """REQ-037: la lista de ofertas del procedimiento y el alta de una oferta."""
    log_in(client, operator_user)
    url = reverse("offers:procedure_offers", args=[procedure.pk])
    page = text_of(client.get(url))
    assert "Ofertas del procedimiento CASO-CHICO-SINTETICO" in page
    assert "Oferente de prueba" in page and "Sin ficha" in page
    response = client.post(url, {"bidder": "Segundo oferente"})
    created = procedure.offers.get(bidder="Segundo oferente")
    assert response.status_code == 302
    assert response.url == reverse("offers:offer", args=[created.pk])


def test_a_repeated_bidder_is_shown_with_its_reason(client, operator_user, procedure, offer):
    """REQ-037: el oferente repetido se rechaza con aviso, sin crear otra oferta."""
    log_in(client, operator_user)
    response = client.post(reverse("offers:procedure_offers", args=[procedure.pk]),
                           {"bidder": offer.bidder})
    assert response.status_code == 200
    assert "ya tiene una oferta en este procedimiento" in text_of(response)
    assert procedure.offers.count() == 1


def test_the_offer_page_shows_documents_state_kind_and_original(client, operator_user, offer):
    """REQ-037, REQ-038: documentos con su tipo, su estado y el enlace al original."""
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:offer", args=[offer.pk])))
    assert "Oferta 1 · Oferente de prueba" in page
    assert "oferta.pdf" in page and "Leído · 2 páginas" in page
    original = reverse("offers:document_original",
                       args=[offer.documents.get(file_name="oferta.pdf").pk])
    assert original in client.get(reverse("offers:offer", args=[offer.pk])).content.decode()
    assert "Armar ficha" in page and "matriz versión 1" in page


def test_several_documents_are_loaded_at_once_and_a_repeated_one_is_refused(
        client, operator_user, procedure, fake_ai):
    """REQ-037: se cargan varios documentos a la vez; el repetido se rechaza con aviso."""
    from evaluon.offers.services import offers as service

    offer = service.register_offer(operator_user, procedure, bidder="Por pantalla")
    log_in(client, operator_user)
    url = reverse("offers:offer", args=[offer.pk])
    files = [SimpleUploadedFile(name, (DATA / name).read_bytes(), "application/pdf")
             for name in ("oferta-propuesta.pdf", "constancia-escaneada.pdf")]
    response = client.post(url, {"file": files})
    assert response.status_code == 302 and response.url.endswith("?cargados=2")
    assert offer.documents.count() == 2
    assert "Se cargaron 2 documentos" in text_of(client.get(response.url))
    repeated = SimpleUploadedFile("otra.pdf", (DATA / "oferta-propuesta.pdf").read_bytes())
    response = client.post(url, {"file": [repeated]})
    assert response.status_code == 200
    assert "ya está cargado en esta oferta" in text_of(response)
    assert offer.documents.count() == 2


def test_the_original_is_served_as_a_pdf(client, operator_user, offer):
    """REQ-037: el original se entrega para el visor del navegador."""
    log_in(client, operator_user)
    document = offer.documents.get(file_name="oferta.pdf")
    response = client.get(reverse("offers:document_original", args=[document.pk]))
    assert response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content if response.streaming else [response.content]) \
        == b"%PDF-sintetico"
    assert client.get(reverse("offers:document_original", args=[99999])).status_code == 404


def test_the_unread_pages_are_listed_in_the_offer_page(client, operator_user, procedure,
                                                       fake_ai):
    """REQ-038, escenario 3: las páginas no leídas se muestran con su documento y página."""
    offer = make_offer(procedure, operator_user, "Con hoja ilegible",
                       {"a.pdf": ["Texto.", ""]}, unread=[("a.pdf", 2)])
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:offer", args=[offer.pk])))
    assert "Páginas no leídas" in page and "a.pdf · página 2" in page


def test_a_user_without_commission_role_gets_403(client, no_commission_user, offer):
    """Sin rol de la Comisión no se ve nada de ofertas, y el rechazo queda registrado."""
    log_in(client, no_commission_user)
    assert client.get(reverse("offers:offer", args=[offer.pk])).status_code == 403
    assert client.get(reverse("offers:procedure_offers",
                              args=[offer.procedure_id])).status_code == 403
    assert client.post(reverse("offers:build_sheet", args=[offer.pk])).status_code == 403
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 3


def test_build_sheet_queues_the_request_and_shows_the_notice(client, operator_user, offer,
                                                             script):
    """REQ-039: "Armar ficha" encola el pedido; al terminar, el aviso de fin lo cuenta y
    enlaza a la oferta."""
    log_in(client, operator_user)
    response = client.post(reverse("offers:build_sheet", args=[offer.pk]))
    assert response.status_code == 302 and "?ficha=" in response.url
    page = text_of(client.get(response.url))
    assert "Se pidió la ficha" in page and "Ficha en preparación (en espera)" in page
    jobs.run_next()
    page = text_of(client.get(reverse("offers:offer", args=[offer.pk])))
    assert "La ficha de la oferta del procedimiento CASO-CHICO-SINTETICO terminó" in page
    assert "Ficha 1" in page
    assert "terminó" not in text_of(client.get(reverse("offers:offer", args=[offer.pk])))


def test_the_notice_of_a_finished_reading_links_to_the_offers(client, operator_user,
                                                              procedure, fake_ai):
    """REQ-038: el aviso de fin de la lectura de un documento de oferta."""
    from evaluon.offers.services import offers as service

    offer = service.register_offer(operator_user, procedure, bidder="Aviso")
    service.load_document(operator_user, offer, data=(DATA / "oferta-propuesta.pdf").read_bytes(),
                          file_name="oferta-propuesta.pdf")
    jobs.run_next()
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:offer", args=[offer.pk])))
    assert "La lectura de un documento de una oferta del procedimiento " \
           "CASO-CHICO-SINTETICO terminó" in page


def test_a_refused_request_is_shown_with_its_reason(client, operator_user, procedure):
    """REQ-043: sin matriz validada, "Armar ficha" muestra el motivo y no encola nada."""
    other = m.Procedure.objects.create(
        number="SIN-MATRIZ", procedure_type="x", subject="x",
        authorization_date="2026-01-01", created_by=operator_user)
    offer = make_offer(other, operator_user, "Oferente", {"a.pdf": ["texto"]})
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:offer", args=[offer.pk])))
    assert "no tiene una matriz validada" in page and "Armar ficha" not in page
    response = client.post(reverse("offers:build_sheet", args=[offer.pk]))
    assert response.status_code == 200 and "no tiene una matriz validada" in text_of(response)
    assert not m.Job.objects.filter(kind=m.JobKind.BUILD_SHEET).exists()


def build_sheet(offer, user, script):
    script.choose(pick("Declaro bajo juramento", when="declaración jurada"))
    return sheets.build_sheet(offer, user)


def test_the_sheet_page_shows_fragments_missing_rows_and_no_judgment(
        client, operator_user, offer, script):
    """REQ-039, REQ-040, REQ-041: la ficha muestra cada fragmento con su documento, página,
    texto literal y enlace al original; lo que no se encontró primero; sin juicio."""
    sheet = build_sheet(offer, operator_user, script)
    log_in(client, operator_user)
    response = client.get(reverse("offers:sheet", args=[sheet.pk]))
    page = text_of(response)
    assert "Ficha 1 de la oferta 1 · Oferente de prueba" in page
    assert "Armada con la matriz versión 1" in page
    assert "La ficha dice qué ofreció el oferente y dónde lo dice" in page
    assert page.index("Lo que no se encontró") < page.index("Requisitos")
    assert "Requisito 3" in page.split("Páginas sin leer")[0]  # la garantía, sin respuesta
    assert "No se encontró en la oferta." in page
    assert "Lo que ofrece el oferente." in page
    assert "Declaro bajo juramento que me encuentro habilitado" in page
    document = offer.documents.get(file_name="oferta.pdf")
    assert f"{reverse('offers:document_original', args=[document.pk])}#page=1" in \
        response.content.decode()
    assert sheets.judgment_words(page) == [], "la ficha muestra una palabra de juicio"
    assert "no se pudo leer" not in page  # no hay páginas sin leer


def test_the_sheet_page_shows_the_item_rows_and_technical_documentation(
        client, operator_user, offer, script):
    """REQ-044: renglones "cotizado" o "no cotizado" y la documentación técnica."""
    script.choose(pick("Renglón 1: resma", when="RESMA"))
    sheet = sheets.build_sheet(offer, operator_user)
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:sheet", args=[sheet.pk])))
    assert "Renglón: cotizado." in page and "Renglón: no cotizado." in page
    assert "La oferta trae documentación técnica." in page


def test_the_sheet_warns_when_a_newer_matrix_version_is_validated(
        client, operator_user, offer, matrix, script):
    """REQ-043: "Armada con la versión 1; la versión vigente es la 2"."""
    sheet = sheets.build_sheet(offer, operator_user)
    second = m.MatrixVersion.objects.create(procedure=matrix.procedure, number=2,
                                            created_by=operator_user)
    second.status = m.VersionStatus.VALIDATED
    second.validated_at = timezone.now()
    second.validated_by = operator_user
    second.save()
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:sheet", args=[sheet.pk])))
    assert "Armada con la versión 1; la versión vigente es la 2" in page


def test_the_sheet_lists_the_unread_pages_and_marks_unreadable_items(
        client, operator_user, procedure, fake_ai, script):
    """REQ-038, REQ-044: las páginas sin leer y el renglón "no se pudo leer"."""
    offer = make_offer(procedure, operator_user, "Con hoja ilegible",
                       {"a.pdf": ["Texto sin relación.", ""]}, unread=[("a.pdf", 2)])
    sheet = sheets.build_sheet(offer, operator_user)
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:sheet", args=[sheet.pk])))
    assert "a.pdf · página 2" in page
    assert "Renglón: no se pudo leer" in page and "Renglón: no cotizado" not in page
    assert "Hay páginas sin leer en la oferta." in page


def test_an_unknown_offer_or_sheet_is_a_404(client, operator_user):
    log_in(client, operator_user)
    assert client.get(reverse("offers:offer", args=[999])).status_code == 404
    assert client.get(reverse("offers:sheet", args=[999])).status_code == 404
    assert client.get(reverse("offers:procedure_offers", args=[999])).status_code == 404
    assert om.Sheet.objects.count() == 0 and Outcome.OK
