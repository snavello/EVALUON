"""Reemplazar, retirar y restituir el dictamen subido, sin borrar nada (REQ-099, REQ-092; T-225).
Todo el material es inventado (P4)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.tenders import models as tm
from evaluon.tenders.services import document_history
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_dictamen import dictamen_block, post_upload
from tests.journey.temas.test_s4_propuesta import log_in, notice, page
from tests.tenders.pdfs import synthetic_tender_pdf as other_pdf

pytestmark = pytest.mark.django_db


def act(name, procedure, document):
    return reverse(f"expedientes:s4_dictamen_{name}", args=[procedure.pk, document.pk])


def uploaded(client, procedure):
    notice(client, post_upload(client, procedure, title="Dictamen CD 99"))
    return tm.Document.objects.get(procedure=procedure, kind=tm.DocumentKind.DICTAMEN)


def test_the_uploaded_dictamen_offers_history_replace_and_withdraw(
        client, procedure, operator_user):
    """REQ-099: el dictamen subido muestra «Historial», «Reemplazar» y «Retirar», cada uno con su
    motivo obligatorio."""
    log_in(client, operator_user)
    document = uploaded(client, procedure)
    block = dictamen_block(page(client, procedure))
    assert "Historial" in block and "Reemplazar" in block and "Retirar" in block
    assert act("reemplazar", procedure, document) in block
    assert act("retirar", procedure, document) in block
    assert block.count("Motivo (obligatorio)") >= 2


def test_replacing_keeps_the_previous_version_in_the_history(
        client, procedure, operator_user):
    """REQ-099: reemplazar carga el archivo nuevo, deja el anterior en el historial (las dos
    versiones se ven) y deja el hecho `document_change`; sin motivo no cambia nada."""
    log_in(client, operator_user)
    document = uploaded(client, procedure)
    ok, text = notice(client, client.post(act("reemplazar", procedure, document), {
        "file": SimpleUploadedFile("dictamen-v2.pdf", other_pdf()), "note": " "}))
    assert not ok and "motivo" in text
    assert document_history.state(document) == "vigente"
    ok, text = notice(client, client.post(act("reemplazar", procedure, document), {
        "file": SimpleUploadedFile("dictamen-v2.pdf", other_pdf()),
        "note": "Se firmó la versión final."}))
    assert ok and "historial" in text
    assert document_history.state(document) == "reemplazado"
    new = document_history.current_documents(procedure).get(kind=tm.DocumentKind.DICTAMEN)
    assert new.pk != document.pk and new.title == document.title
    block = dictamen_block(page(client, procedure))
    assert "Versión 1 · reemplazado" in block and "Versión 2 · vigente" in block
    assert "dictamen-v2.pdf" in block and "Se firmó la versión final." in block
    assert reverse("tenders:document_original", args=[document.pk]) in block
    assert AuditEvent.objects.filter(event_type=EventType.DOCUMENT_CHANGE,
                                     outcome=AuditOutcome.OK,
                                     detail__action="reemplazar").count() == 1


def test_withdrawing_moves_it_to_withdrawn_and_restoring_brings_it_back(
        client, procedure, operator_user):
    """REQ-099: retirar no borra: el dictamen aparece en «Retirados» con el motivo, deja de
    contar como cargado y se puede restituir."""
    log_in(client, operator_user)
    document = uploaded(client, procedure)
    ok, _ = notice(client, client.post(act("retirar", procedure, document),
                                       {"note": "Se subió el de otro procedimiento."}))
    assert ok and document_history.state(document) == "retirado"
    assert tm.Document.objects.filter(pk=document.pk).exists()
    block = dictamen_block(page(client, procedure))
    assert "Retirados" in block and "Se subió el de otro procedimiento." in block
    assert act("restituir", procedure, document) in block
    assert '<span class="cta">no cargado' in block
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert any("Dictamen: no se cargó" in m.text for m in section.tema_missing)
    ok, _ = notice(client, client.post(act("restituir", procedure, document),
                                       {"note": "Era el correcto."}))
    assert ok and document_history.state(document) == "vigente"
    block = dictamen_block(page(client, procedure))
    assert '<span class="cta">cargado' in block and "Restituido" in block


def test_only_a_dictamen_of_this_procedure_and_a_commission_role(
        client, procedure, operator_user, no_commission_user):
    """P3, P6: sin rol de la Comisión da 403 y queda el rechazo; un documento que no es dictamen
    no se toca desde acá."""
    log_in(client, operator_user)
    document = uploaded(client, procedure)
    client.logout()
    log_in(client, no_commission_user)
    before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    response = client.post(act("retirar", procedure, document), {"note": "x"})
    assert response.status_code == 403
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == before + 1
    assert document_history.state(document) == "vigente"
    wrong = reverse("expedientes:s4_dictamen_retirar", args=[procedure.pk + 999, document.pk])
    client.logout()
    log_in(client, operator_user)
    assert client.post(wrong, {"note": "x"}).status_code == 404
