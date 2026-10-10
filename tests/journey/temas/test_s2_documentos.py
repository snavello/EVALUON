"""Tema «documentos del pliego» de la sección Pliego y matriz (REQ-080, REQ-097; plan 014,
T-198). Todo el material es inventado (P4); no se usa ningún modelo: la lectura de los archivos
subidos queda en espera y la de los documentos del caso chico ya está hecha."""

import datetime
import html as htmllib
import itertools
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.portal import models as p
from evaluon.tenders.models import Document, DocumentKind, Job, JobKind, Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:pliego", args=[procedure.pk])


def upload_url(procedure):
    return reverse("expedientes:s2_documentos_subir", args=[procedure.pk])


def pdf(text):
    return tender_pdf([[para(text)]])


_BYTES = {}


def pdf_file(name, text=None):
    """El mismo texto da siempre los mismos bytes (el PDF armado no es determinista)."""
    text = text or f"Documento sintético {name}"
    if text not in _BYTES:
        _BYTES[text] = pdf(text)
    return SimpleUploadedFile(name, _BYTES[text], content_type="application/pdf")


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"DOCS-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


def follow(client, response):
    assert response.status_code == 302
    return client.get(response["Location"])


def test_without_a_tender_both_accesses_and_what_is_missing_appear(client, bare, operator_user):
    """REQ-080, REQ-097: un procedimiento sin pliego muestra «Subir archivo», «Tomar del
    Portal» y lo que falta."""
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    assert "Todavía no hay pliego ni matriz" in page
    assert page.count("Subir archivo") >= 2          # el encabezado y el aviso vacío
    assert "Tomar del Portal" in page
    assert "el pliego, sus anexos y las especificaciones técnicas" in page


def test_the_header_upload_button_goes_to_the_new_upload(client, bare, operator_user):
    """REQ-097: el botón del encabezado ya no va a la pantalla vieja."""
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    header = re.search(r'<span class="barra-cargas">(.*?)</span>', page, re.S).group(1)
    assert f'href="{tab(bare)}#s2-subir"' in header
    assert f"/procedimientos/{bare.pk}/" not in header
    assert 'id="s2-subir"' in page


def test_three_files_at_once_are_loaded_each_with_its_kind(client, bare, operator_user):
    """REQ-080: tres documentos juntos quedan los tres, cada uno con su tipo y su hecho."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("pliego.pdf"), pdf_file("anexo_1.pdf"), pdf_file("espec.pdf")],
        "kind_0": "pliego", "kind_1": "anexo", "kind_2": "especificaciones",
        "title_0": "Pliego inventado", "title_1": "Anexo I inventado"})
    page = follow(client, response).content.decode()
    docs = list(bare.documents.order_by("pk"))
    assert [d.kind for d in docs] == ["pliego", "anexo", "especificaciones"]
    assert [d.title for d in docs] == ["Pliego inventado", "Anexo I inventado", "espec"]
    assert Job.objects.filter(kind=JobKind.READ_DOCUMENT, document__procedure=bare).count() == 3
    assert AuditEvent.objects.filter(event_type=EventType.TENDER_LOAD,
                                     outcome=Outcome.OK).count() == 3
    assert page.count("Cargado; queda en espera de lectura.") == 3
    assert "3 cargados" in page
    for doc in docs:
        assert f'id="doc-{doc.pk}"' in page


def test_a_repeated_file_is_refused_with_its_reason_without_stopping_the_others(
        client, bare, operator_user):
    """REQ-080: el repetido se rechaza con su motivo y los otros se cargan."""
    log_in(client, operator_user)
    client.post(upload_url(bare), {"files": [pdf_file("a.pdf", "mismo texto")],
                                   "kind": "pliego"})
    response = client.post(upload_url(bare), {
        "files": [pdf_file("b.pdf", "otro texto"), pdf_file("a-de-nuevo.pdf", "mismo texto"),
                  pdf_file("c.pdf", "un tercero")],
        "kind": "anexo"})
    page = htmllib.unescape(follow(client, response).content.decode())
    assert bare.documents.count() == 3
    assert "Ese archivo ya está cargado en este procedimiento" in page
    assert page.count("Cargado; queda en espera de lectura.") == 2
    refusal = AuditEvent.objects.get(event_type=EventType.TENDER_LOAD,
                                     outcome=Outcome.REJECTED)
    assert refusal.detail["reason"] == "duplicate_file"


def test_an_unreadable_file_is_refused_and_the_rest_go_on(client, bare, operator_user):
    """REQ-080: un archivo que no es PDF ni página guardada se rechaza con su motivo."""
    log_in(client, operator_user)
    bad = SimpleUploadedFile("nota.txt", b"texto plano", content_type="text/plain")
    response = client.post(upload_url(bare), {"files": [bad, pdf_file("ok.pdf")],
                                              "kind": "pliego"})
    page = htmllib.unescape(follow(client, response).content.decode())
    assert bare.documents.count() == 1
    assert "no es un PDF ni una página web guardada" in page


def test_an_optional_date_is_kept_and_an_invalid_one_is_refused(client, bare, operator_user):
    """REQ-080: la fecha opcional se guarda; una que no es fecha se rechaza y queda registrada."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("c2.pdf", "dos"), pdf_file("c3.pdf", "tres")],
        "kind_0": "anexo", "issued_on_0": "2026-09-10", "kind_1": "pliego",
        "issued_on_1": "31/02/2026"})
    page = htmllib.unescape(follow(client, response).content.decode())
    assert "no es una fecha válida" in page
    assert list(bare.documents.values_list("file_name", flat=True)) == ["c2.pdf"]
    assert bare.documents.get().issued_on == datetime.date(2026, 9, 10)
    reasons = set(AuditEvent.objects.filter(outcome=Outcome.REJECTED)
                  .values_list("detail__reason", flat=True))
    assert reasons == {"invalid_date"}


def test_no_file_chosen_says_so(client, bare, operator_user):
    log_in(client, operator_user)
    page = follow(client, client.post(upload_url(bare), {"kind": "pliego"})).content.decode()
    assert "Elija al menos un archivo para subir." in page
    assert not bare.documents.exists()


def test_a_user_without_commission_role_cannot_upload(client, bare, no_commission_user):
    """P7: sin rol de la Comisión no se sube; el rechazo queda registrado."""
    log_in(client, no_commission_user)
    response = client.post(upload_url(bare), {"files": [pdf_file("x.pdf")], "kind": "pliego"})
    assert response.status_code == 403
    assert not bare.documents.exists()


def test_the_list_shows_origin_with_local_date_and_reading_state(client, procedure,
                                                                  operator_user):
    """REQ-080: cada documento con su origen (archivo o Portal, con fecha local) y su lectura."""
    when = datetime.datetime(2026, 8, 21, 1, 30, tzinfo=datetime.timezone.utc)  # 20/08 22:30 local
    first = procedure.documents.order_by("pk").first()
    Document.objects.filter(pk=first.pk).update(loaded_at=when, kind="pliego")
    other = procedure.documents.exclude(pk=first.pk).first()
    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/x?qs=1",
                                       procedure=procedure, created_by=operator_user)
    if other is not None:
        Document.objects.filter(pk=other.pk).update(kind="anexo")
        proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                                   origin=p.Origin.IMPORTACION)
        page_row = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                               url=link.url, sha256="a" * 64, content=b"x")
        item = p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.DOCUMENTO,
                                           key="anexo-1", payload={"nombre": "Anexo", "clase": "anexo"},
                                           content_sha256="b" * 64, page=page_row)
        p.PortalItem.objects.filter(pk=item.pk).update(
            state=p.ItemState.CARGADO, decided_by=operator_user, decided_at=timezone.now(),
            loaded_model=p.LoadedModel.DOCUMENT, loaded_id=other.pk)
    log_in(client, operator_user)
    page = client.get(tab(procedure)).content.decode()
    row = re.search(rf'<tr id="doc-{first.pk}">(.*?)</tr>', page, re.S).group(1)
    assert "<b>Archivo</b> · 20/08/2026" in row
    assert "Leído" in row
    if other is not None:
        row = re.search(rf'<tr id="doc-{other.pk}">(.*?)</tr>', page, re.S).group(1)
        assert "<b>Portal</b>" in row


def test_circulars_do_not_appear_here(client, bare, operator_user):
    """REQ-085: las circulares y aclaraciones van en Ofertas, no en esta lista."""
    for kind, title in (("pliego", "El pliego"), ("circular_modificatoria", "Una circular"),
                        ("respuesta_consulta", "Una respuesta")):
        Document.objects.create(
            procedure=bare, kind=kind, title=title, file_name=f"{next(_n)}.pdf",
            file_format="pdf", file_size=1, file_sha256=f"{next(_n):064x}",
            issued_on=None if kind == "pliego" else datetime.date(2026, 9, 1),
            loaded_by=operator_user)
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    assert "El pliego" in page
    assert "Una circular" not in page and "Una respuesta" not in page
    assert "1 cargado" in page


def test_what_the_portal_lists_and_was_not_taken_shows_as_missing(client, bare, operator_user):
    """REQ-097: una fila «Falta» con «Tomar del Portal» hacia los documentos del Portal."""
    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/y?qs=2",
                                       procedure=bare, created_by=operator_user)
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    page_row = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                           url=link.url, sha256="c" * 64, content=b"x")
    for key, name, clase in (("a3", "Anexo III inventado", "anexo"),
                             ("c1", "Circular inventada", "circular")):
        p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.DOCUMENTO, key=key,
                                    payload={"nombre": name, "clase": clase},
                                    content_sha256="d" * 64, page=page_row)
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    assert "Anexo III inventado" in page
    assert "Circular inventada" not in page
    assert "1 falta" in page
    assert f'{reverse("expedientes:procedimiento", args=[bare.pk])}#s1-portal' in page
    assert "#group-documento" not in page
    assert "El Portal lista 1 documento del pliego que no se tomaron" in page



def test_without_a_tender_there_is_one_summary_line_and_no_link_to_old_screens(
        client, bare, operator_user):
    """REQ-080: una sola línea de resumen, sin «Falta: … Ir» ni enlaces a la pantalla vieja."""
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    assert "Todavía no hay pliego: súbalo o tómelo del Portal" in page
    assert "<b>Falta:</b>" not in page
    assert "Faltan los documentos del pliego" not in page
    assert f"/procedimientos/{bare.pk}/" not in page


def test_empty_matrix_offers_upload_without_tender_and_proposal_with_a_read_one(
        client, bare, operator_user):
    """REQ-080: sin pliego, «Subir archivo»; con pliego leído, «Pedir la propuesta»."""
    log_in(client, operator_user)
    page = client.get(tab(bare)).content.decode()
    assert "Pedir la propuesta de la matriz" not in page
    doc = Document.objects.create(
        procedure=bare, kind="pliego", title="Pliego leído", file_name="p.pdf",
        file_format="pdf", file_size=1, file_sha256="e" * 64, loaded_by=operator_user)
    from evaluon.tenders.models import Reading
    Reading.objects.create(document=doc, sequence=1, pages={"pages": []}, tables=[],
                           canonical_text="x", canonical_sha256="f" * 64, items=[],
                           tool_versions={}, report={})
    page = client.get(tab(bare)).content.decode()
    assert "Pedir la propuesta de la matriz" in page
    assert f"/procedimientos/{bare.pk}/" not in page
    response = client.post(reverse("expedientes:s2_proponer", args=[bare.pk]))
    assert response.status_code == 302 and response["Location"].startswith(tab(bare))
    assert Job.objects.filter(kind=JobKind.PROPOSE_MATRIX, procedure=bare).exists()


@pytest.mark.parametrize("key", ["ofertas", "evaluacion"])
def test_what_is_missing_shows_in_every_tab_as_text_without_old_links(
        client, bare, operator_user, key):
    """REQ-097: Ofertas y Evaluación sin ofertas siguen mostrando qué falta, sin «Ir» viejos."""
    log_in(client, operator_user)
    page = client.get(reverse(f"expedientes:{key}", args=[bare.pk])).content.decode()
    line = re.search(r'<p class="falta">(.*?)</p>', page, re.S)
    # lo que falta puede llevar su acción directa, pero nunca a una pantalla vieja
    for href in re.findall(r'href="([^"]*)"', line.group(1) if line else ""):
        assert href.startswith(f"/expedientes/{bare.pk}/")
    summary = re.search(r'id="seccion-resumen">(.*?)</p>', page, re.S).group(1).strip()
    assert summary
    for sentence in re.findall(r"[^.]+\.", summary):
        assert page.count(sentence.strip()) == 1
    assert f"/procedimientos/{bare.pk}/" not in page


def test_a_crafted_kind_outside_this_tab_is_refused_with_its_reason(client, bare,
                                                                     operator_user):
    """REQ-080: solo pliego, anexo y especificaciones; una circular armada a mano se rechaza."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("c.pdf", "circular"), pdf_file("ok.pdf", "bueno")],
        "kind_0": "circular_modificatoria", "issued_on_0": "2026-09-10", "kind_1": "anexo"})
    page = htmllib.unescape(follow(client, response).content.decode())
    assert "no corresponde a esta pestaña" in page
    assert list(bare.documents.values_list("kind", flat=True)) == ["anexo"]
