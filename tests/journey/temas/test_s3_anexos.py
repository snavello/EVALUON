"""Tema «anexos técnicos y hoja de compliance» de la sección Ofertas (REQ-087, REQ-088, REQ-097;
plan 014, T-204). Cada acción vuelve a la pestaña con el mismo cambio y el mismo hecho de
auditoría que la pantalla vieja. Todo el material es inventado (P4)."""

import html as htmllib
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment.services import compliance
from evaluon.audit.models import AuditEvent, EventType
from evaluon.journey.sections import sections_for
from evaluon.offers import models as om
from evaluon.tenders import jobs
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import two_offers  # noqa: F401  (fixture)
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:ofertas", args=[procedure.pk])


def url(name, procedure, offer):
    return reverse(f"expedientes:{name}", args=[procedure.pk, offer.pk])


_CACHE = {}


def pdf(*lines, name="ficha.pdf"):
    """El mismo PDF cada vez para las mismas líneas (el armado cambia de una vez a otra)."""
    if lines not in _CACHE:
        _CACHE[lines] = tender_pdf([[para(*lines)]], header=None)
    return SimpleUploadedFile(name, _CACHE[lines])


def sheet_pdf(name="hoja.pdf"):
    return pdf("HOJA DE COMPLIANCE", "Registro de Proveedores: el oferente figura inscripto.",
               name=name)


def page(client, procedure):
    response = client.get(tab(procedure))
    assert response.status_code == 200
    return response.content.decode()


def block(html):
    return html[html.index('class="s3-anx"'):]


def notice(client, response):
    """La pestaña a la que vuelve la acción y el mensaje que muestra."""
    assert response.status_code == 302
    page_ = client.get(response["Location"])
    assert page_.status_code == 200
    found = re.search(
        r'<p class="aviso (aviso-ok|aviso-error)" id="s3-aviso-anexos"[^>]*>(.*?)</p>',
        page_.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


def read_all():
    while jobs.run_next() is not None:
        pass


# --- Anexos técnicos (REQ-087) ---------------------------------------------------------------------


def test_a_technical_sheet_uploaded_from_the_tab_is_an_annex_of_that_offer(
        client, two_offers, procedure, operator_user, fake_ai):
    """REQ-087: la ficha técnica subida dentro de la oferta figura como anexo técnico de esa
    oferta (y no de la otra); la pestaña lo muestra y la lectura no cambia su tipo."""
    a, b = two_offers
    log_in(client, operator_user)
    response = client.post(url("s3_anexos_anexo", procedure, a),
                           {"file": pdf("FICHA TECNICA del producto ofrecido")})
    ok, text = notice(client, response)
    assert ok and f"anexo técnico de la oferta {a.number}" in text
    document = a.documents.get(file_name="ficha.pdf")
    assert document.kind == om.DocumentKind.ANEXO_TECNICO
    assert not b.documents.filter(kind=om.DocumentKind.ANEXO_TECNICO).exists()
    read_all()
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.ANEXO_TECNICO
    html = block(page(client, procedure))
    mine = html[html.index(f'id="s3-anexos-anexos-{a.number}"'):]
    mine = mine.split(f'id="s3-anexos-hoja-{a.number}"')[0]
    assert "ficha" in mine and "Leído" in mine


def test_the_annex_upload_leaves_the_same_audit_fact_as_the_service(
        client, offer, procedure, operator_user, fake_ai):
    """REQ-087, P6: la carga deja el hecho `offer_load` con el tipo, quién y el canal."""
    log_in(client, operator_user)
    client.post(url("s3_anexos_anexo", procedure, offer), {"file": pdf("Folleto", "Datos")})
    document = offer.documents.get(kind=om.DocumentKind.ANEXO_TECNICO)
    event = AuditEvent.objects.get(event_type=EventType.OFFER_LOAD,
                                   detail__document=document.pk)
    assert event.user == operator_user and event.detail["kind"] == "anexo_tecnico"
    assert event.outcome == "ok" and event.channel == "screen"


def test_a_repeated_or_empty_annex_comes_back_with_the_reason(
        client, offer, procedure, operator_user, fake_ai):
    """REQ-087: el mismo archivo dos veces, o sin archivo, vuelve a la pestaña con el motivo y
    no deja un segundo documento."""
    log_in(client, operator_user)
    client.post(url("s3_anexos_anexo", procedure, offer), {"file": pdf("Folleto", "Datos")})
    ok, text = notice(client, client.post(url("s3_anexos_anexo", procedure, offer),
                                          {"file": pdf("Folleto", "Datos")}))
    assert not ok and text
    ok, text = notice(client, client.post(url("s3_anexos_anexo", procedure, offer), {}))
    assert not ok and text
    assert offer.documents.filter(kind=om.DocumentKind.ANEXO_TECNICO).count() == 1


def test_a_user_without_commission_role_cannot_upload_an_annex(
        client, offer, procedure, no_commission_user, fake_ai):
    """REQ-087: sin rol de la Comisión, 403 con el rechazo registrado; no se guarda nada."""
    log_in(client, no_commission_user)
    response = client.post(url("s3_anexos_anexo", procedure, offer), {"file": pdf("X", "Y")})
    assert response.status_code == 403
    assert not offer.documents.filter(kind=om.DocumentKind.ANEXO_TECNICO).exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


# --- Hoja de compliance (REQ-088) ------------------------------------------------------------------


def test_an_offer_without_a_sheet_is_missing_with_its_button_and_the_upload_clears_it(
        client, two_offers, procedure, evaluator_user, operator_user, fake_ai):
    """REQ-088: la oferta sin hoja figura como faltante de la sección (con su botón) y de la
    portada; al subirla desde el botón deja de faltar."""
    a, b = two_offers
    section = sections_for(operator_user, procedure).get("ofertas")
    texts = [m.text for m in section.tema_missing]
    assert f"Oferta {a.number} ({a.bidder}): falta la hoja de compliance" in texts
    assert f"Oferta {b.number} ({b.bidder}): falta la hoja de compliance" in texts
    item = next(m for m in section.tema_missing if f"Oferta {a.number} " in m.text)
    assert item.url == tab(procedure) + f"#s3-anexos-oferta-{a.number}"
    assert item.action == "Subir hoja de compliance"
    log_in(client, evaluator_user)
    html = block(page(client, procedure))
    assert html.count("Falta la hoja de compliance") >= 2
    assert url("s3_anexos_hoja", procedure, a) in html
    portada = client.get(reverse("expedientes:portada", args=[procedure.pk])).content.decode()
    assert f"Oferta {a.number} ({a.bidder}): falta la hoja de compliance" in portada
    ok, text = notice(client, client.post(url("s3_anexos_hoja", procedure, a),
                                          {"file": sheet_pdf()}))
    assert ok and f"hoja de compliance de la oferta {a.number}" in text
    section = sections_for(operator_user, procedure).get("ofertas")
    texts = [m.text for m in section.tema_missing]
    assert f"Oferta {a.number} ({a.bidder}): falta la hoja de compliance" not in texts
    assert f"Oferta {b.number} ({b.bidder}): falta la hoja de compliance" in texts


def test_the_sheet_upload_does_the_same_as_the_old_route(
        client, two_offers, procedure, evaluator_user, fake_ai):
    """REQ-088, P6: el mismo cambio (documento de tipo compliance, una sola hoja) y el mismo
    hecho de auditoría (`eval_decision`, `hoja_compliance`) que la ruta vieja."""
    a, b = two_offers
    log_in(client, evaluator_user)
    client.post(url("s3_anexos_hoja", procedure, a), {"file": sheet_pdf("nueva.pdf")})
    client.post(reverse("assessment:compliance_upload", args=[b.pk]),
                {"file": sheet_pdf("vieja.pdf")})
    new, old = compliance.sheets_of(a), compliance.sheets_of(b)
    assert len(new) == len(old) == 1
    assert new[0].kind == old[0].kind == om.DocumentKind.COMPLIANCE
    facts = []
    for offer, document in ((a, new[0]), (b, old[0])):
        event = AuditEvent.objects.get(event_type=EventType.EVAL_DECISION,
                                       detail__document=document.pk)
        facts.append((event.outcome, event.channel, event.user_id, event.detail["action"],
                      event.detail["offer"] == offer.pk))
    assert facts[0] == facts[1]


def test_the_sheet_is_shown_with_its_local_date_and_state(
        client, offer, procedure, evaluator_user, fake_ai):
    """REQ-088: con hoja, la pestaña muestra cuándo se cargó (hora local) y su lectura; la
    oferta ya no figura como faltante."""
    log_in(client, evaluator_user)
    client.post(url("s3_anexos_hoja", procedure, offer), {"file": sheet_pdf()})
    document = compliance.sheets_of(offer)[0]
    html = block(page(client, procedure))
    assert f"Cargada el {timezone.localtime(document.loaded_at):%d/%m/%Y %H:%M}" in html
    assert "En espera de lectura" in html
    assert "Falta la hoja de compliance" not in html
    read_all()
    assert "Leído" in block(page(client, procedure))


def test_an_operator_sees_the_state_and_not_the_sheet_button_and_is_refused_by_the_service(
        client, offer, procedure, operator_user, fake_ai):
    """REQ-088: la hoja la sube un evaluador (rol del servicio): el operador ve el estado, no el
    botón, y si manda el formulario, 403 con el rechazo registrado."""
    log_in(client, operator_user)
    html = block(page(client, procedure))
    assert "Falta la hoja de compliance" in html
    assert "Subir hoja de compliance" not in html and "Subir anexo técnico" in html
    response = client.post(url("s3_anexos_hoja", procedure, offer), {"file": sheet_pdf()})
    assert response.status_code == 403
    assert not compliance.sheets_of(offer)
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def test_a_sheet_that_cannot_be_loaded_comes_back_with_the_reason(
        client, offer, procedure, evaluator_user, fake_ai):
    """REQ-088: sin archivo, vuelve a la pestaña con el motivo y la oferta sigue faltando."""
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(url("s3_anexos_hoja", procedure, offer), {}))
    assert not ok and text
    assert not compliance.sheets_of(offer)


def test_the_block_has_no_sample_text_and_no_old_links(
        client, offer, procedure, evaluator_user, fake_ai):
    """REQ-097: el bloque no trae textos de maqueta ni enlaces a pantallas viejas."""
    log_in(client, evaluator_user)
    html = block(page(client, procedure))
    html = html.split('id="s3-anexos"', 1)[1]
    assert "/assessment/" not in html and "[texto de ejemplo]" not in html
    assert not re.search(r'href="/ofertas/', html)
