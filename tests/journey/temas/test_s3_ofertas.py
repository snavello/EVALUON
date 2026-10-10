"""Tema «ofertas» de la sección Ofertas (REQ-083, REQ-084, REQ-097; plan 014, T-202).

La tabla de ofertas con el alta a la vista (desde el acta del Portal o subiendo los archivos de la
oferta, con nombre y CUIT propuestos por el sistema para que un evaluador los apruebe o corrija),
los documentos de cada oferta con subida de varios a la vez y el detalle de la oferta dentro de la
pestaña. Todo el material es inventado (P4); el modelo local es el doble de las pruebas.
"""

import hashlib
import html as htmllib
import re
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.journey.sections import sections_for
from evaluon.norms.models import ProposalState
from evaluon.offers import models as om
from evaluon.portal import models as pm
from evaluon.tenders import jobs
from evaluon.tenders import models as tm
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import two_offers  # noqa: F401  (fixture)
from tests.offers.test_offer_proposal import CUIT_A, CUIT_B, NAME_A, NAME_B, cover_offer
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure, query=""):
    return reverse("expedientes:ofertas", args=[procedure.pk]) + query


def url(name, procedure, *args):
    return reverse(f"expedientes:{name}", args=[procedure.pk, *args])


def page(client, procedure, query=""):
    response = client.get(tab(procedure, query))
    assert response.status_code == 200
    return response.content.decode()


def block(html):
    """El bloque del tema dentro de la pestaña (sin los demás temas)."""
    return html[html.index('class="s3-of"'):html.index('id="s3-of-fin"')]


def notice(client, response):
    """La pestaña a la que vuelve la acción y los mensajes que muestra."""
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("expedientes:ofertas",
                                                   args=[_pid(response)]))
    shown = client.get(response["Location"])
    assert shown.status_code == 200
    found = re.search(r'<div class="aviso" id="s3-aviso-ofertas"[^>]*>(.*?)</div>',
                      shown.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    items = re.findall(r'<li class="(ok|rechazado)">(.*?)</li>', found.group(1), re.S)
    return [(cls == "ok", htmllib.unescape(re.sub(r"<[^>]+>", "", text))) for cls, text in items]


def _pid(response):
    return int(re.search(r"/expedientes/(\d+)/", response["Location"]).group(1))


def as_upload(files):
    return [SimpleUploadedFile(name, data) for name, data in files]


def pdf_file(name, text):
    return SimpleUploadedFile(name, tender_pdf([[para(text)]], header=None))


def read_proposals():
    while jobs.run_next(kinds=[tm.JobKind.PROPOSE_OFFER]) is not None:
        pass


# --- El alta a la vista (REQ-083) ----------------------------------------------------------------


def test_both_ways_to_add_an_offer_are_visible_without_opening_anything(
        client, procedure, operator_user):
    """REQ-083: con la pestaña recién abierta, «Agregar oferta desde el Portal» y «Subir los
    archivos de una oferta» están a la vista, como botones del bloque «Ofertas presentadas»."""
    log_in(client, operator_user)
    html = block(page(client, procedure))
    head = html[html.index('id="s3-ofertas"'):html.index("</table>") if "</table>" in html
                else len(html)]
    assert "Ofertas presentadas" in head
    assert re.search(r'<a class="btn primario[^"]*" href="[^"]*#s3-alta-portal">'
                     r"Agregar oferta desde el Portal</a>", html)
    assert re.search(r'<a class="btn secundario[^"]*" href="[^"]*#s3-alta-archivos">'
                     r"Subir los archivos de una oferta</a>", html)
    assert 'id="s3-alta-archivos"' in html and 'id="s3-alta-portal"' in html


def test_an_empty_tab_says_there_are_no_offers_and_what_to_do(client, operator_user):
    """REQ-097: sin ofertas, la pestaña dice qué falta con su acción directa."""
    bare = tm.Procedure.objects.create(number="SINT-T202-VACIO", procedure_type="Licitación",
                                       subject="Objeto sintético", created_by=operator_user,
                                       authorization_date=date(2025, 11, 14))
    log_in(client, operator_user)
    html = block(page(client, bare))
    assert "Todavía no hay ofertas" in html
    section = sections_for(operator_user, bare).get("ofertas")
    assert any(m.text.startswith("Todavía no hay ofertas") and m.url for m in section.tema_missing)
    assert section.upload_url == tab(bare) + "?alta=archivos#s3-alta-archivos"


def test_the_section_no_longer_points_to_the_old_offers_screen(procedure, operator_user):
    """REQ-097: «Subir archivo» de la sección lleva al alta de la pestaña, no a la pantalla
    vieja de ofertas."""
    section = sections_for(operator_user, procedure).get("ofertas")
    assert "/ofertas/procedimiento/" not in (section.upload_url or "")
    assert section.legacy_links == ()


# --- La tabla de ofertas -------------------------------------------------------------------------


def test_the_table_shows_each_offer_with_its_documents_annexes_sheet_and_card(
        client, two_offers, procedure, operator_user):
    """REQ-083, REQ-084: cada oferta es una fila con su total, sus documentos (y «Subir
    documentos»), sus anexos técnicos y su hoja de compliance (el bloque de T-204) y el enlace a
    su ficha dentro de la pestaña. La lista provisoria de la ficha ya no está."""
    a, b = two_offers
    log_in(client, operator_user)
    html = page(client, procedure)
    mine = block(html)
    for offer in (a, b):
        row = mine[mine.index(f'id="s3-anexos-oferta-{offer.number}"'):]
        row = row[:row.index("</tr>")]
        assert offer.bidder in row
        assert f'href="{tab(procedure, f"?ficha={offer.pk}")}#s3-ficha"' in row
        assert f'href="{tab(procedure, f"?oferta={offer.pk}")}#s3-oferta"' in row
        assert "Subir documentos" in row and "Subir anexo técnico" in row
        assert f'id="s3-anexos-anexos-{offer.number}"' in row
        assert f'id="s3-anexos-hoja-{offer.number}"' in row
    assert "Lo que presentó cada oferta" not in html
    assert 'id="s3-fichas"' not in html


def test_three_files_uploaded_together_stay_in_the_offer(client, offer, procedure,
                                                         operator_user, fake_ai):
    """REQ-084: dada una oferta, cuando se suben tres archivos juntos, quedan los tres en la
    oferta, cada uno con su hecho `offer_load`, y la pestaña dice el resultado de cada uno."""
    before = offer.documents.count()
    log_in(client, operator_user)
    files = [pdf_file(f"doc-{n}.pdf", f"Documento sintético número {n} de la oferta")
             for n in (1, 2, 3)]
    response = client.post(url("s3_ofertas_documentos", procedure, offer.pk), {"files": files})
    results = notice(client, response)
    assert len(results) == 3 and all(ok for ok, _ in results)
    assert offer.documents.count() == before + 3
    for n in (1, 2, 3):
        document = offer.documents.get(file_name=f"doc-{n}.pdf")
        assert AuditEvent.objects.filter(event_type=EventType.OFFER_LOAD, outcome=Outcome.OK,
                                         detail__document=document.pk).exists()


def test_a_repeated_file_is_refused_with_its_reason_and_the_others_load(
        client, offer, procedure, operator_user, fake_ai):
    """REQ-084: si uno se rechaza (repetido), los demás igual se cargan."""
    log_in(client, operator_user)
    content = tender_pdf([[para("Texto sintético uno")]], header=None)
    first = SimpleUploadedFile("uno.pdf", content)
    client.post(url("s3_ofertas_documentos", procedure, offer.pk), {"files": [first]})
    again = SimpleUploadedFile("uno-otra-vez.pdf", content)
    other = pdf_file("dos.pdf", "Texto sintético dos")
    results = notice(client, client.post(url("s3_ofertas_documentos", procedure, offer.pk),
                                         {"files": [again, other]}))
    assert [ok for ok, _ in results] == [False, True]
    assert "ya está cargado" in results[0][1]
    assert offer.documents.filter(file_name="dos.pdf").exists()


def test_without_role_the_upload_is_refused_and_recorded(client, offer, procedure,
                                                         no_commission_user):
    """REQ-084: sin rol de la Comisión, la carga da 403 y queda el rechazo registrado."""
    log_in(client, no_commission_user)
    response = client.post(url("s3_ofertas_documentos", procedure, offer.pk),
                           {"files": [pdf_file("x.pdf", "Texto")]})
    assert response.status_code == 403
    assert not offer.documents.filter(file_name="x.pdf").exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def test_the_offer_detail_opens_inside_the_tab(client, offer, procedure, operator_user):
    """REQ-084: el detalle de la oferta se abre dentro de la pestaña, con sus documentos, su
    origen en hora local, la subida múltiple y «Volver a Ofertas»."""
    log_in(client, operator_user)
    html = block(page(client, procedure, f"?oferta={offer.pk}"))
    assert f"Oferta {offer.number} · {offer.bidder}" in html
    assert "← Volver a Ofertas" in html and 'id="s3-oferta-abierta"' in html
    document = offer.documents.order_by("pk").first()
    assert document.title in html
    assert f"{timezone.localtime(document.loaded_at):%d/%m/%Y}" in html
    assert 'name="files"' in html and "multiple" in html
    assert "Ofertas presentadas" not in html


# --- Alta desde el Portal (REQ-083) --------------------------------------------------------------


@pytest.fixture
def portal_offer(procedure, operator_user):
    """Un ítem de oferta del acta de apertura, sin aprobar, con un renglón ya propuesto."""
    link = pm.PortalLink.objects.create(url="https://afipcompras.afip.gob.ar/sintetico?qs=t202",
                                        procedure=procedure, created_by=operator_user)
    page_ = pm.PortalPage.objects.create(link=link, exploration=1, kind=pm.PageKind.ACTA,
                                         url=link.url, sha256="a" * 64, content=b"acta")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1,
                                                origin=pm.Origin.IMPORTACION)
    lines = pm.PortalItem.objects.create(proposal=proposal, kind=pm.ItemKind.RENGLONES,
                                         key="renglones", payload={"renglones": []},
                                         content_sha256="b" * 64, page=page_)
    pm.PortalLine.objects.create(procedure=procedure, number=1, description="Renglón sintético",
                                 quantity=Decimal("10"), item=lines)
    payload = {"oferente": "Proveedora Inventada S.A.", "cuit": CUIT_B, "confirmada": None,
               "moneda": "Peso Argentino", "total": "16054000.00", "total_cuadro": None,
               "garantias": [{"tipo": "Mantenimiento de oferta", "forma": "Póliza",
                              "monto": "802700.00"}],
               "cotizaciones": [{"renglon": 1, "alternativa": 0, "precio": "1605400.00",
                                 "cantidad": "10", "total_renglon": "16054000.00"}],
               "fuentes": ["acta"], "anomalias": []}
    return pm.PortalItem.objects.create(
        proposal=proposal, kind=pm.ItemKind.OFERTA, key=f"oferta:{CUIT_B}", payload=payload,
        content_sha256=hashlib.sha256(b"oferta-t202").hexdigest(), page=page_)


def test_the_portal_offers_are_listed_and_the_evaluator_adds_one(
        client, procedure, portal_offer, evaluator_user):
    """REQ-083: la oferta del acta de apertura figura con oferente, CUIT, total y garantía; el
    evaluador la agrega y queda en la tabla con su origen «Portal · acta de apertura»; deja el
    hecho `portal_decision`."""
    log_in(client, evaluator_user)
    html = block(page(client, procedure))
    alta = html[html.index('id="s3-alta-portal"'):]
    assert "Proveedora Inventada S.A." in alta and CUIT_B in alta
    assert "$ 16.054.000,00" in alta and "Póliza" in alta
    results = notice(client, client.post(url("s3_ofertas_portal", procedure, portal_offer.pk)))
    assert results[0][0], results
    offer = procedure.offers.get(bidder="Proveedora Inventada S.A.")
    assert offer.portal_data.cuit == CUIT_B and offer.portal_data.item_id == portal_offer.pk
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION,
                                     detail__item=portal_offer.pk).exists()
    html = block(page(client, procedure))
    row = html[html.index(f'id="s3-anexos-oferta-{offer.number}"'):]
    row = row[:row.index("</tr>")]
    assert "Portal" in row and "acta de apertura" in row and "$ 16.054.000,00" in row


def test_the_operator_sees_the_portal_offer_but_does_not_add_it(
        client, procedure, portal_offer, operator_user):
    """REQ-083: la oferta del Portal la aprueba un evaluador; el operador la ve sin el botón y
    si manda el formulario recibe 403 con el rechazo registrado."""
    log_in(client, operator_user)
    html = block(page(client, procedure))
    alta = html[html.index('id="s3-alta-portal"'):]
    assert "Proveedora Inventada S.A." in alta and "Lo aprueba un evaluador" in alta
    assert url("s3_ofertas_portal", procedure, portal_offer.pk) not in html
    response = client.post(url("s3_ofertas_portal", procedure, portal_offer.pk))
    assert response.status_code == 403
    assert not procedure.offers.filter(bidder="Proveedora Inventada S.A.").exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def test_a_pending_portal_offer_is_missing_with_its_action(procedure, portal_offer,
                                                            operator_user):
    """REQ-097: una oferta del acta sin agregar figura como faltante con su acción directa."""
    section = sections_for(operator_user, procedure).get("ofertas")
    item = next(m for m in section.tema_missing if "acta de apertura" in m.text)
    assert item.url.endswith("#s3-alta-portal") and item.action == "Agregar oferta desde el Portal"


# --- Alta subiendo los archivos (REQ-083) --------------------------------------------------------


def upload_files(client, procedure, files):
    return client.post(url("s3_ofertas_alta", procedure), {"files": as_upload(files)})


def draft_page(client, procedure, draft):
    return block(page(client, procedure, f"?borrador={draft.pk}"))


def test_uploading_the_files_shows_the_progress_and_then_name_and_cuit_with_their_quote(
        client, procedure, operator_user, fake_generation):
    """REQ-083: subir los archivos de una oferta vuelve a la pestaña con el avance de la
    lectura; al terminar se ven el nombre y el CUIT propuestos con su cita (documento, página y
    texto). El operador sube y ve, sin botones de aprobar ni corregir."""
    log_in(client, operator_user)
    response = upload_files(client, procedure, cover_offer(NAME_A, CUIT_A))
    draft = om.OfferDraft.objects.get(procedure=procedure)
    assert response.status_code == 302 and f"borrador={draft.pk}" in response["Location"]
    html = draft_page(client, procedure, draft)
    assert "El sistema está leyendo los archivos" in html and "data-recargar" in html
    read_proposals()
    html = draft_page(client, procedure, draft)
    assert NAME_A in html and CUIT_A in html
    citation = om.OfferDraft.objects.get(pk=draft.pk).proposal["fields"]["cuit"]["citation"]
    assert f"{citation['document']}, pág. {citation['page']}" in html
    assert "Corregir" not in html and "Aprobar" not in html.replace("Lo aprueba", "")
    assert "Lo aprueba un evaluador" in html
    main = block(page(client, procedure))
    assert NAME_A in main[main.index('id="s3-borradores"'):]


def test_the_operator_cannot_correct_or_approve_and_the_refusal_is_recorded(
        client, procedure, operator_user, fake_generation):
    """REQ-083: solo el evaluador aprueba o corrige; un POST del operador da 403 auditado."""
    log_in(client, operator_user)
    upload_files(client, procedure, cover_offer(NAME_A, CUIT_A))
    read_proposals()
    draft = om.OfferDraft.objects.get(procedure=procedure)
    for name, data in (("s3_ofertas_corregir", {"field": "bidder", "value": "Otro",
                                                "reason": "porque sí"}),
                       ("s3_ofertas_aprobar", {})):
        assert client.post(url(name, procedure, draft.pk), data).status_code == 403
    assert not procedure.offers.exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() >= 2


def test_the_evaluator_corrects_writing_value_and_reason_and_approves(
        client, procedure, operator_user, evaluator_user, fake_generation):
    """REQ-083 («Escribe el valor y motivo»): la corrección sin motivo se rechaza; con motivo
    queda lo propuesto y lo corregido, quién y cuándo. Al aprobar, la oferta queda en la tabla
    con sus archivos y su origen."""
    log_in(client, operator_user)
    files = cover_offer(NAME_A, CUIT_A)
    upload_files(client, procedure, files)
    read_proposals()
    draft = om.OfferDraft.objects.get(procedure=procedure)
    client.logout()
    log_in(client, evaluator_user)
    html = draft_page(client, procedure, draft)
    assert "Corregir" in html and "Aprobar" in html
    assert 'name="value"' in html and 'name="reason"' in html
    results = notice(client, client.post(url("s3_ofertas_corregir", procedure, draft.pk),
                                         {"field": "bidder", "value": NAME_B, "reason": ""}))
    assert not results[0][0] and "motivo" in results[0][1]
    results = notice(client, client.post(url("s3_ofertas_corregir", procedure, draft.pk),
                                         {"field": "bidder", "value": NAME_B,
                                          "reason": "Así figura en el acta firmada"}))
    assert results[0][0]
    html = draft_page(client, procedure, draft)
    assert f"«{NAME_A}»" in html and f"«{NAME_B}»" in html
    assert "Así figura en el acta firmada" in html and evaluator_user.username in html
    results = notice(client, client.post(url("s3_ofertas_aprobar", procedure, draft.pk)))
    assert results[0][0], results
    offer = procedure.offers.get(bidder=NAME_B)
    assert offer.documents.count() == len(files)
    assert offer.portal_data.cuit == CUIT_A and offer.portal_data.document_id
    html = block(page(client, procedure))
    row = html[html.index(f'id="s3-anexos-oferta-{offer.number}"'):]
    row = row[:row.index("</tr>")]
    assert NAME_B in row and "Archivos de la oferta" in row
    assert 'id="s3-borradores"' not in html


def test_the_evaluator_discards_a_badly_read_proposal_with_a_reason(
        client, procedure, operator_user, evaluator_user, fake_generation):
    """REQ-083: descartar la propuesta pide el motivo y no crea la oferta."""
    log_in(client, operator_user)
    upload_files(client, procedure, cover_offer(NAME_A, CUIT_A))
    read_proposals()
    draft = om.OfferDraft.objects.get(procedure=procedure)
    client.logout()
    log_in(client, evaluator_user)
    results = notice(client, client.post(url("s3_ofertas_rechazar", procedure, draft.pk),
                                         {"reason": "Se subió la oferta equivocada"}))
    assert results[0][0]
    assert om.OfferDraft.objects.get(pk=draft.pk).state == ProposalState.RECHAZADO
    assert not procedure.offers.exists()


def test_a_proposal_waiting_for_approval_counts_as_pending(
        client, procedure, operator_user, fake_generation):
    """REQ-097: la propuesta lista para aprobar suma a lo pendiente de la sección, con su
    enlace dentro de la pestaña."""
    log_in(client, operator_user)
    upload_files(client, procedure, cover_offer(NAME_A, CUIT_A))
    read_proposals()
    draft = om.OfferDraft.objects.get(procedure=procedure)
    section = sections_for(operator_user, procedure).get("ofertas")
    item = next(i for i in section.pending_items if "nombre y CUIT" in i.text)
    assert item.url == tab(procedure, f"?borrador={draft.pk}") + "#s3-borrador"


def test_a_refused_upload_comes_back_with_the_reason(client, procedure, operator_user):
    """REQ-083: sin archivos, o con un archivo que no se lee, vuelve con el motivo."""
    log_in(client, operator_user)
    results = notice(client, client.post(url("s3_ofertas_alta", procedure), {}))
    assert not results[0][0] and "archivos" in results[0][1]
    assert not om.OfferDraft.objects.filter(procedure=procedure).exists()


# --- Lo que no debe haber -------------------------------------------------------------------------


def test_the_block_has_no_sample_text_and_no_links_to_old_screens(
        client, two_offers, procedure, evaluator_user):
    """REQ-097: ni textos de maqueta ni enlaces a las pantallas viejas de ofertas."""
    log_in(client, evaluator_user)
    for query in ("", f"?oferta={two_offers[0].pk}"):
        html = block(page(client, procedure, query))
        assert "[texto de ejemplo]" not in html
        links = re.findall(r'href="([^"]+)"', html)
        old = [link for link in links if link.startswith(("/ofertas/", "/procedimientos/"))
               and "/original/" not in link]
        assert old == []
