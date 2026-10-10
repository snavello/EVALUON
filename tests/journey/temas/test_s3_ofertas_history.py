"""Tema «ofertas», historial de los documentos de la oferta (REQ-099; plan 014, T-206):
Reemplazar, Retirar (con motivo) y Restituir por documento, historial dentro de la pestaña,
bloque «Retirados» y aviso de evaluación hecha con un documento retirado. Todo el material es
inventado (P4); no se usa ningún modelo real."""

import html as htmllib
import re
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers.services import document_history as history
from evaluon.tenders.models import Job, JobKind
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure, query=""):
    return reverse("expedientes:ofertas", args=[procedure.pk]) + query


def url(name, procedure, document):
    return reverse(f"expedientes:s3_ofertas_{name}", args=[procedure.pk, document.pk])


def text(client, address):
    response = client.get(address)
    assert response.status_code == 200
    return htmllib.unescape(response.content.decode())


def follow(client, response):
    assert response.status_code == 302
    return text(client, response["Location"])


def new_file(name, body):
    return SimpleUploadedFile(name, tender_pdf([[para(body)]], header=None),
                              content_type="application/pdf")


def first_document(offer):
    return offer.documents.order_by("pk").first()


def detail(procedure, offer, extra=""):
    return tab(procedure, f"?oferta={offer.pk}{extra}")


def test_a_replaced_document_shows_both_versions_in_its_history(
        client, offer, procedure, operator_user, fake_ai):
    """REQ-099: dado un documento reemplazado, su historial muestra la versión anterior y la
    nueva, con quién, cuándo (hora local) y el motivo; en la oferta queda solo la nueva."""
    document = first_document(offer)
    log_in(client, operator_user)
    html = follow(client, client.post(url("reemplazar", procedure, document), {
        "file": new_file("nueva.pdf", "Versión corregida sintética"),
        "note": "El oferente mandó la versión firmada"}))
    assert "Reemplazado" in html
    new = offer.documents.get(file_name="nueva.pdf")
    assert history.state(document) == "reemplazado" and history.state(new) == "vigente"
    shown = text(client, detail(procedure, offer))
    table = shown[shown.index('id="s3-documentos"'):shown.index('id="s3-retirados"')]
    assert f'id="doc-{new.pk}"' in table and "nueva.pdf" in table
    assert f'id="doc-{document.pk}"' not in table
    timeline = text(client, detail(procedure, offer, f"&historial={new.pk}"))
    assert "Versión 1 · reemplazado" in timeline and "Versión 2 · vigente" in timeline
    assert document.file_name in timeline and "nueva.pdf" in timeline
    assert "El oferente mandó la versión firmada" in timeline
    change = history.history(new)[-1]
    assert f"{timezone.localtime(change.at):%d/%m/%Y %H:%M}" in timeline
    assert operator_user.username in timeline


def test_a_withdrawn_document_is_in_withdrawn_and_restoring_returns_it(
        client, offer, procedure, operator_user):
    """REQ-099: un documento retirado sale de la tabla y aparece en «Retirados» con su motivo;
    restituirlo lo devuelve. Nada se borra."""
    document = first_document(offer)
    log_in(client, operator_user)
    follow(client, client.post(url("retirar", procedure, document),
                               {"note": "Se cargó por error"}))
    html = text(client, detail(procedure, offer))
    withdrawn = html[html.index('id="s3-retirados"'):]
    assert document.title in withdrawn and "Se cargó por error" in withdrawn
    table = html[html.index('id="s3-documentos"'):html.index('id="s3-retirados"')]
    assert f'id="doc-{document.pk}"' not in table
    follow(client, client.post(url("restituir", procedure, document),
                               {"note": "Era el correcto"}))
    assert history.state(document) == "vigente"
    html = text(client, detail(procedure, offer))
    table = html[html.index('id="s3-documentos"'):html.index('id="s3-retirados"')]
    assert f'id="doc-{document.pk}"' in table
    assert offer.documents.filter(pk=document.pk).exists()


def test_every_change_needs_a_reason_and_leaves_its_audit_event(
        client, offer, procedure, operator_user):
    """REQ-099, P6: sin motivo no se cambia nada; con motivo, cada cambio deja `document_change`
    con quién y por qué."""
    document = first_document(offer)
    log_in(client, operator_user)
    html = follow(client, client.post(url("retirar", procedure, document), {"note": " "}))
    assert "Escriba el motivo" in html and history.state(document) == "vigente"
    follow(client, client.post(url("retirar", procedure, document), {"note": "Duplicado"}))
    event = AuditEvent.objects.filter(event_type=EventType.DOCUMENT_CHANGE,
                                      outcome=Outcome.OK).latest("pk")
    assert event.user == operator_user and event.detail["note"] == "Duplicado"
    assert event.detail["offer"] == offer.pk and event.channel == "screen"


def test_operator_and_evaluator_can_but_a_user_without_role_cannot(
        client, offer, procedure, evaluator_user, no_commission_user):
    """REQ-099: el operador y el evaluador cambian; sin rol, 403 con el rechazo registrado."""
    document = first_document(offer)
    log_in(client, no_commission_user)
    response = client.post(url("retirar", procedure, document), {"note": "x"})
    assert response.status_code == 403 and history.state(document) == "vigente"
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()
    client.logout()
    log_in(client, evaluator_user)
    follow(client, client.post(url("retirar", procedure, document), {"note": "Sobra"}))
    assert history.state(document) == "retirado"


def test_a_document_of_another_procedure_is_not_found(client, offer, procedure,
                                                     operator_user):
    """REQ-099: la acción solo toca documentos de ofertas de este procedimiento."""
    from evaluon.tenders.models import Procedure

    other = Procedure.objects.create(number="SINT-T206-OTRO", procedure_type="Licitación",
                                     subject="Otro objeto", created_by=operator_user,
                                     authorization_date=date(2025, 11, 14))
    log_in(client, operator_user)
    response = client.post(url("retirar", other, first_document(offer)), {"note": "x"})
    assert response.status_code == 404


def test_an_evaluation_made_with_a_withdrawn_document_is_flagged(
        client, offer, procedure, matrix, operator_user, evaluator_user):
    """REQ-099: si una evaluación usó un documento que después se retiró, la oferta lo avisa y
    pide evaluar de nuevo (no se recalcula sola)."""
    document = first_document(offer)
    job = Job.objects.create(kind=JobKind.EVALUATE_OFFERS, procedure=procedure,
                             requested_by=evaluator_user)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=matrix.version, offers=[offer.pk],
        requirements=None, cause=am.Cause.MATRIZ, requested_by=evaluator_user, job=job)
    am.Run.objects.create(request=request, offer=offer, matrix_version=matrix.version, number=1,
                          channel=am.Channel.SCREEN, documents=[{"document": document.pk}],
                          norms={}, models_used={}, parameters={}, prompt_versions={})
    log_in(client, operator_user)
    follow(client, client.post(url("retirar", procedure, document), {"note": "No va"}))
    html = text(client, detail(procedure, offer))
    warning = re.search(r'<p class="aviso aviso-error" role="alert">([^<]*(?:<[^p][^<]*)*)</p>',
                        html)
    assert warning and document.title in warning.group(1)
    assert "evaluar de nuevo" in warning.group(1)
    assert reverse("expedientes:evaluacion", args=[procedure.pk]) in html
    main = text(client, tab(procedure))
    assert "evaluada con un documento retirado" in main


def test_the_history_view_has_no_old_links(client, offer, procedure, operator_user):
    """REQ-099: el historial se abre dentro de la pestaña, sin enlaces a pantallas viejas."""
    document = first_document(offer)
    log_in(client, operator_user)
    html = text(client, detail(procedure, offer, f"&historial={document.pk}"))
    assert f"Historial · {document.title}" in html and "← Volver a la oferta" in html
    links = re.findall(r'href="([^"]+)"',
                       html[html.index('class="s3-of"'):html.index('id="s3-of-fin"')])
    assert not [link for link in links
                if link.startswith(("/ofertas/", "/procedimientos/")) and "/original/" not in link]
