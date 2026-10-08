"""Tema s2_documentos, historial de los documentos del pliego (REQ-099, REQ-097; plan 014,
T-200): Reemplazar, Retirar (con motivo), Restituir, historial dentro de la pestaña, bloque
«Retirados» y aviso de matriz armada con un documento que ya no está vigente. Todo el material
es inventado (P4); no se usa ningún modelo."""

import html as htmllib
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import document_history as history
from tests.accounts.test_session import TEST_PASSWORD
from tests.offers.conftest import expected, matrix as validated_matrix  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import load_and_read, make_procedure

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def pdf(text):
    return tender_pdf([[para(f"PLIEGO SINTÉTICO {text}"), para("1. Objeto de prueba.")]])


def tab(procedure, query=""):
    return reverse("expedientes:pliego", args=[procedure.pk]) + query


def url(name, procedure, document):
    return reverse(f"expedientes:s2_documentos_{name}", args=[procedure.pk, document.pk])


def text_of(response):
    return htmllib.unescape(response.content.decode())


def follow(client, response):
    assert response.status_code == 302
    return text_of(client.get(response["Location"]))


def new_file(name, text):
    return SimpleUploadedFile(name, pdf(text), content_type="application/pdf")


@pytest.fixture
def procedure(operator_user):
    return make_procedure(operator_user)


@pytest.fixture
def document(operator_user, procedure):
    return load_and_read(operator_user, procedure, pdf("v1"), title="Pliego particular",
                         file_name="v1.pdf")


def test_a_replaced_document_shows_the_new_version_and_its_history_the_old_one(
        client, operator_user, procedure, document):
    """REQ-099: tras reemplazar, la tabla muestra la versión nueva; el historial, las dos, con
    motivo, quién y cuándo."""
    log_in(client, operator_user)
    response = client.post(url("reemplazar", procedure, document), {
        "file": new_file("v2.pdf", "v2"), "note": "Versión corregida del pliego"})
    page = follow(client, response)
    assert "Reemplazado" in page
    new = history.current_documents(procedure).get()
    assert new.file_name == "v2.pdf" and new.pk != document.pk
    table = page.split('id="s2-documentos"')[1]
    assert "v2.pdf" in table and "v1.pdf" not in table.split("Retirados")[0]
    shown = text_of(client.get(tab(procedure, f"?historial={document.pk}")))
    assert "← Volver a Pliego y matriz" in shown
    assert "Versión 1 · reemplazado" in shown and "Versión 2 · vigente" in shown
    assert "Motivo: «Versión corregida del pliego»" in shown
    assert operator_user.username in shown
    assert re.search(r"\d\d/\d\d/\d{4} \d\d:\d\d", shown)
    assert shown.count("Ver el archivo") == 2
    # La misma historia se llega desde la versión nueva.
    again = text_of(client.get(tab(procedure, f"?historial={new.pk}")))
    assert "Versión 1 · reemplazado" in again


def test_replace_requires_the_file_and_the_reason(client, operator_user, procedure, document):
    """REQ-099: sin archivo o sin motivo no se reemplaza nada."""
    log_in(client, operator_user)
    no_reason = follow(client, client.post(url("reemplazar", procedure, document), {
        "file": new_file("v2.pdf", "v2"), "note": "  "}))
    assert "Escriba el motivo" in no_reason
    no_file = follow(client, client.post(url("reemplazar", procedure, document),
                                         {"note": "motivo"}))
    assert "Elija el archivo" in no_file
    assert m.Document.objects.filter(procedure=procedure).count() == 1
    assert not m.DocumentChange.objects.exists()


def test_a_withdrawn_document_appears_in_withdrawn_and_restoring_returns_it(
        client, operator_user, evaluator_user, procedure, document):
    """REQ-099: retirar exige motivo, saca el documento de la tabla y lo lista en «Retirados»;
    restituirlo lo devuelve."""
    log_in(client, operator_user)
    empty = follow(client, client.post(url("retirar", procedure, document), {"note": ""}))
    assert "Escriba el motivo" in empty
    assert history.state(document) == "vigente"

    page = follow(client, client.post(url("retirar", procedure, document),
                                      {"note": "Se cargó por error"}))
    assert "Retirado" in page and "Ver retirados (1)" in page
    assert list(history.withdrawn_documents(procedure)) == [document]
    table = page.split('<tbody>')[1].split('</tbody>')[0] if "<tbody>" in page else ""
    assert "v1.pdf" not in table

    retired = text_of(client.get(tab(procedure, "?historial=retirados")))
    assert "← Volver a Pliego y matriz" in retired
    assert "Pliego particular" in retired and "Se cargó por error" in retired
    assert operator_user.username in retired and "Restituir" in retired

    log_in(client, evaluator_user)
    back = follow(client, client.post(url("restituir", procedure, document),
                                      {"note": "Era el correcto"}))
    assert "Restituido" in back and "Ver retirados" not in back
    assert history.state(document) == "vigente"
    assert "v1.pdf" in back
    timeline = text_of(client.get(tab(procedure, f"?historial={document.pk}")))
    assert "Retirado" in timeline and "Restituido" in timeline
    assert "Era el correcto" in timeline and evaluator_user.username in timeline


def test_withdraw_uses_the_accent_button(client, operator_user, procedure, document):
    """REQ-099, guía visual: Retirar es acción de efecto fuerte y usa el botón de acento."""
    log_in(client, operator_user)
    page = text_of(client.get(tab(procedure)))
    assert re.search(r'class="btn acento chico"[^>]*>Retirar<', page)
    assert re.search(r'<summary class="btn secundario chico">Reemplazar<', page)
    assert "Historial</a>" in page


def test_a_refused_change_says_why_and_changes_nothing(
        client, operator_user, procedure, document):
    """REQ-099: retirar un documento ya retirado se rechaza con motivo."""
    log_in(client, operator_user)
    history.withdraw(operator_user, document, "ya retirado")
    page = follow(client, client.post(url("retirar", procedure, document), {"note": "otra vez"}))
    assert "Solo se retira un documento vigente" in page
    assert m.DocumentChange.objects.count() == 1


def test_operator_and_evaluator_can_but_a_reader_cannot(
        client, operator_user, evaluator_user, read_user, procedure, document):
    """REQ-099: operador y evaluador cambian; el pedido de lectura se rechaza y queda registrado."""
    log_in(client, read_user)
    before = AuditEvent.objects.filter(outcome=Outcome.REJECTED).count()
    assert client.post(url("retirar", procedure, document), {"note": "x"}).status_code == 403
    assert client.post(url("restituir", procedure, document), {"note": "x"}).status_code == 403
    assert client.post(url("reemplazar", procedure, document), {
        "file": new_file("v2.pdf", "v2"), "note": "x"}).status_code == 403
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() == before + 3
    assert not m.DocumentChange.objects.exists()
    log_in(client, evaluator_user)
    assert client.post(url("retirar", procedure, document), {"note": "x"}).status_code == 302
    assert history.state(document) == "retirado"


def test_every_change_leaves_its_audit_event(client, operator_user, procedure, document):
    """P6: reemplazar, retirar y restituir dejan su hecho `document_change`."""
    log_in(client, operator_user)
    client.post(url("reemplazar", procedure, document), {
        "file": new_file("v2.pdf", "v2"), "note": "uno"})
    new = history.current_documents(procedure).get()
    client.post(url("retirar", procedure, new), {"note": "dos"})
    client.post(url("restituir", procedure, new), {"note": "tres"})
    notes = [e.detail["note"] for e in AuditEvent.objects.filter(
        event_type=EventType.DOCUMENT_CHANGE, outcome=Outcome.OK).order_by("id")]
    assert notes == ["uno", "dos", "tres"]


def test_dates_are_shown_in_local_time(client, operator_user, procedure, document):
    """REQ-099: el retiro se ve en hora local, no en la de la base (UTC)."""
    from django.utils import timezone
    log_in(client, operator_user)
    client.post(url("retirar", procedure, document), {"note": "m"})
    change = m.DocumentChange.objects.get()
    local = f"{timezone.localtime(change.at):%d/%m/%Y %H:%M}"
    page = text_of(client.get(tab(procedure, "?historial=retirados")))
    assert local in page


def test_a_matrix_built_with_a_withdrawn_document_is_flagged(
        client, operator_user, validated_matrix):
    """REQ-099: la matriz armada con un documento que se retiró lleva un aviso, restituirlo lo
    quita, y la versión validada no cambia."""
    from django.utils import timezone
    from evaluon.tenders.services import matrix
    procedure = validated_matrix.procedure
    run = m.MatrixRun.objects.create(
        procedure=procedure, channel=m.RunChannel.EVAL,
        documents=matrix._documents_snapshot(procedure),
        authorization_date=procedure.authorization_date)
    version = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, status=m.VersionStatus.VALIDATED, run=run,
        created_by=operator_user, validated_at=timezone.now(), validated_by=operator_user)
    log_in(client, operator_user)
    assert "se armó con" not in text_of(client.get(tab(procedure)))
    used = m.Document.objects.get(pk=run.documents[0]["document"])
    history.withdraw(operator_user, used, "retirado para la prueba")
    page = text_of(client.get(tab(procedure)))
    assert f"La versión {version.number} de la matriz se armó con" in page
    assert f"«{used.title}» (retirado)" in page
    version.refresh_from_db()
    assert version.status == m.VersionStatus.VALIDATED
    history.restore(operator_user, used)
    assert "se armó con" not in text_of(client.get(tab(procedure)))


def test_the_history_screen_hides_the_other_blocks_and_has_no_old_links(
        client, operator_user, procedure, document):
    """REQ-097: el historial se abre dentro de la pestaña, sin enlaces a pantallas viejas."""
    log_in(client, operator_user)
    page = text_of(client.get(tab(procedure, f"?historial={document.pk}")))
    assert "s2-historial-abierto" in page
    assert "Historial · Pliego particular" in page
    assert "maqueta" not in page.lower()
    # Un historial de otro procedimiento o inexistente vuelve a la pestaña normal.
    normal = text_of(client.get(tab(procedure, "?historial=999999")))
    assert "Pliego, anexos y especificaciones técnicas" in normal
