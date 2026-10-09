"""Tema «circulares y aclaraciones» de la sección Ofertas (REQ-085, REQ-097; plan 014, T-205).
Todo el material es inventado (P4); el modelo es el doble con guion de `tests/tenders`, sin
modelo real ni GPU."""

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
from evaluon.tenders.models import Document, Job, JobKind, Procedure
from evaluon.tenders.services import circular_version
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import run_jobs
from tests.tenders.test_circular_version import (  # noqa: F401  (fixtures)
    RAM_CHANGE,
    script,
    validated,
)
from tests.tenders.test_circulars import circular as circular_pdf

pytestmark = pytest.mark.django_db

_n = itertools.count(1)
_BYTES = {}


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:ofertas", args=[procedure.pk])


def upload_url(procedure):
    return reverse("expedientes:s3_circulares_subir", args=[procedure.pk])


def open_url(procedure):
    return reverse("expedientes:s3_circulares_abrir", args=[procedure.pk])


def pdf_file(name, text=None):
    text = text or f"Circular sintética {name}"
    if text not in _BYTES:
        _BYTES[text] = tender_pdf([[para(text)]])
    return SimpleUploadedFile(name, _BYTES[text], content_type="application/pdf")


def text_of(response):
    return htmllib.unescape(response.content.decode())


def follow(client, response):
    assert response.status_code == 302
    return client.get(response["Location"])


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"CIRC-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2026, 3, 3), created_by=operator_user)


def test_an_empty_tab_offers_both_accesses_with_no_old_texts(client, bare, operator_user):
    """REQ-097: sin circulares se ven «Subir circular o aclaración» y «Tomar del Portal»."""
    log_in(client, operator_user)
    page = text_of(client.get(tab(bare)))
    assert "Todavía no hay circulares ni aclaraciones" in page
    assert page.count("Subir circular o aclaración") >= 2
    assert 'href="#s3-subir"' in page and 'id="s3-subir"' in page
    assert "Tomar del Portal" in page


def test_three_files_are_loaded_each_with_its_kind_and_date(client, bare, operator_user):
    """REQ-085: tres archivos juntos quedan los tres, con su tipo, su fecha y su hecho."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("c1.pdf"), pdf_file("c2.pdf"), pdf_file("r1.pdf")],
        "kind_0": "circular_modificatoria", "kind_1": "circular_aclaratoria",
        "kind_2": "respuesta_consulta", "title_0": "Circular N.º 1",
        "issued_on_0": "2026-09-10", "issued_on_1": "15/09/2026", "issued_on_2": "2026-09-16"})
    page = text_of(follow(client, response))
    docs = list(bare.documents.order_by("pk"))
    assert [d.kind for d in docs] == ["circular_modificatoria", "circular_aclaratoria",
                                      "respuesta_consulta"]
    assert [d.issued_on for d in docs] == [datetime.date(2026, 9, 10),
                                           datetime.date(2026, 9, 15),
                                           datetime.date(2026, 9, 16)]
    assert Job.objects.filter(kind=JobKind.READ_DOCUMENT, document__procedure=bare).count() == 3
    assert AuditEvent.objects.filter(event_type=EventType.TENDER_LOAD,
                                     outcome=Outcome.OK).count() == 3
    assert page.count("Cargada; queda en espera de lectura.") == 3
    assert "3 cargadas" in page
    for doc in docs:
        assert f'id="circular-{doc.pk}"' in page
    assert "10/09/2026" in page and "Circular N.º 1" in page


def test_without_scripts_one_kind_and_one_date_apply_to_every_file(client, bare, operator_user):
    """REQ-085: sin el script, el tipo y la fecha únicos valen para todos los archivos."""
    log_in(client, operator_user)
    client.post(upload_url(bare), {
        "files": [pdf_file("a.pdf"), pdf_file("b.pdf")], "kind": "circular_aclaratoria",
        "issued_on": "2026-09-20"})
    assert {(d.kind, d.issued_on) for d in bare.documents.all()} == {
        ("circular_aclaratoria", datetime.date(2026, 9, 20))}


def test_a_missing_date_refuses_that_file_and_the_others_still_load(client, bare, operator_user):
    """REQ-085: la fecha es obligatoria; el archivo sin fecha se rechaza con su motivo y los
    otros se cargan."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("sin_fecha.pdf"), pdf_file("con_fecha.pdf")],
        "kind_0": "circular_modificatoria", "kind_1": "respuesta_consulta",
        "issued_on_1": "2026-09-18"})
    page = text_of(follow(client, response))
    assert bare.documents.count() == 1
    assert "Escriba la fecha del documento" in page
    assert "Cargada; queda en espera de lectura." in page


def test_a_bad_date_text_is_refused_and_recorded(client, bare, operator_user):
    """REQ-085: una fecha ilegible se rechaza y queda el hecho."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("x.pdf")], "kind_0": "circular_aclaratoria",
        "issued_on_0": "pasado mañana"})
    follow(client, response)
    assert bare.documents.count() == 0
    assert AuditEvent.objects.filter(event_type=EventType.TENDER_LOAD,
                                     outcome=Outcome.REJECTED).exists()


def test_circulars_load_only_here_and_the_pliego_types_do_not(client, bare, operator_user):
    """REQ-085: los tipos de circular se suben solo en Ofertas, y los del pliego no."""
    log_in(client, operator_user)
    response = client.post(upload_url(bare), {"files": [pdf_file("p.pdf")], "kind_0": "pliego",
                                              "issued_on_0": "2026-09-20"})
    assert "no corresponde a esta pestaña" in text_of(follow(client, response))
    assert bare.documents.count() == 0
    other = client.post(reverse("expedientes:s2_documentos_subir", args=[bare.pk]),
                        {"files": [pdf_file("q.pdf")], "kind_0": "circular_modificatoria"})
    assert "no corresponde a esta pestaña" in text_of(follow(client, other))
    assert bare.documents.count() == 0


def test_a_user_without_a_commission_role_cannot_load_or_open(
        client, bare, operator_user, no_commission_user):
    """P3: sin rol de la Comisión no se sube ni se abre una versión (403); queda el rechazo y
    la pestaña no muestra los botones."""
    log_in(client, no_commission_user)
    response = client.post(upload_url(bare), {
        "files": [pdf_file("n.pdf")], "kind_0": "circular_aclaratoria",
        "issued_on_0": "2026-09-20"})
    assert response.status_code == 403 and bare.documents.count() == 0
    log_in(client, operator_user)
    client.post(upload_url(bare), {"files": [pdf_file("m.pdf")],
                                   "kind_0": "circular_modificatoria",
                                   "issued_on_0": "2026-09-21"})
    document = bare.documents.get()
    log_in(client, no_commission_user)
    assert client.post(open_url(bare), {"document": document.pk}).status_code == 403
    assert "Subir circular o aclaración" not in text_of(client.get(tab(bare)))
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() >= 2


def test_a_modifying_circular_opens_a_new_draft_version_marked_in_both_tabs(
        client, operator_user, validated, script):  # noqa: F811
    """REQ-085: la modificatoria subida, leída y abierta produce la versión 2 en borrador con
    el requisito cambiado marcado en la matriz; la pestaña lo cuenta como pendiente hasta
    validarla."""
    procedure = validated.procedure
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])
    log_in(client, operator_user)
    client.post(upload_url(procedure), {
        "files": [SimpleUploadedFile("c1.pdf", circular_pdf(RAM_CHANGE))],
        "kind_0": "circular_modificatoria", "title_0": "Circular N.º 1",
        "issued_on_0": "2026-12-01"})
    document = procedure.documents.get(title="Circular N.º 1")
    page = text_of(client.get(tab(procedure)))
    assert "Se está leyendo; cuando termine" in page or "En espera de lectura" in page

    run_jobs()
    page = text_of(client.get(tab(procedure)))
    assert "Todavía no abrió una versión nueva de la matriz." in page
    assert "falta abrir la versión nueva de la matriz" in page      # pendiente de la sección
    assert "Abrir la versión nueva de la matriz" in page

    response = client.post(open_url(procedure), {"document": document.pk})
    assert "Se pidió la versión nueva de la matriz" in text_of(follow(client, response))
    run_jobs()

    new = procedure.matrix_versions.get(number=2)
    assert new.status == "draft" and new.validated_at is None
    page = text_of(client.get(tab(procedure)))
    row = re.search(rf'<tr id="circular-{document.pk}">(.*?)</tr>', page, re.S).group(1)
    assert "Entró en la versión 2 (en revisión): cambió el requisito" in row
    assert "Falta validarla." in row
    assert "Abrir la versión nueva de la matriz" not in row
    assert "falta validarla" in page                              # sigue como pendiente

    matrix_page = text_of(client.get(reverse("expedientes:pliego", args=[procedure.pk])))
    assert "Cambiado por Circular N.º 1 (versión 2)" in matrix_page
    assert "32 GB de RAM" in matrix_page


def test_a_clarifying_circular_does_not_offer_a_version(client, operator_user, validated):
    """REQ-085: una aclaratoria no abre versión: dice que no cambia la matriz y no cuenta."""
    procedure = validated.procedure
    log_in(client, operator_user)
    client.post(upload_url(procedure), {
        "files": [pdf_file("a1.pdf", "1. El Renglón N° 1 se entrega en caja.")],
        "kind_0": "circular_aclaratoria", "title_0": "Aclaración 1",
        "issued_on_0": "2026-12-02"})
    run_jobs()
    page = text_of(client.get(tab(procedure)))
    assert "No cambia la matriz." in page
    assert 'name="document"' not in page
    assert circular_version.pending(procedure) == []
    document = procedure.documents.get(title="Aclaración 1")
    response = client.post(open_url(procedure), {"document": document.pk})
    assert "no la cambia" in text_of(follow(client, response))
    assert procedure.matrix_versions.count() == 1


def test_loaded_day_is_shown_in_local_time(client, bare, operator_user):
    """REQ-097: «de dónde vino» muestra la fecha de carga en hora local, no la de la base."""
    log_in(client, operator_user)
    client.post(upload_url(bare), {"files": [pdf_file("h.pdf")],
                                   "kind_0": "circular_aclaratoria",
                                   "issued_on_0": "2026-09-20"})
    document = bare.documents.get()
    when = datetime.datetime(2026, 10, 8, 1, 30, tzinfo=datetime.timezone.utc)
    Document.objects.filter(pk=document.pk).update(loaded_at=when)
    page = text_of(client.get(tab(bare)))
    assert "<b>Archivo</b> · 07/10/2026" in page
    assert timezone.localtime(when).day == 7


def test_what_the_portal_lists_and_was_not_taken_shows_as_missing(client, bare, operator_user):
    """REQ-097: lo que el Portal lista como circular y no se tomó figura con «Tomar del
    Portal»."""
    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/z?qs=3",
                                       procedure=bare, created_by=operator_user)
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    page_row = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                           url=link.url, sha256="e" * 64, content=b"x")
    p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.DOCUMENTO, key="c9",
                                payload={"nombre": "Circular Portal inventada",
                                         "clase": "circular"},
                                content_sha256="f" * 64, page=page_row)
    log_in(client, operator_user)
    page = text_of(client.get(tab(bare)))
    assert "Circular Portal inventada" in page
    assert "1 detectada en el Portal" in page
    assert "El Portal lista 1 circular o aclaración que no se tomaron" in page
    assert f'{reverse("portal:proposal", args=[link.pk])}#group-documento' in page
