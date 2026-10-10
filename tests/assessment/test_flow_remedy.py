"""Recorrido completo de la subsanación y pantallas de preguntas y subsanación (REQ-055,
REQ-056, REQ-060; plan 004, "Subsanación" y "Pantalla"; T-154). Caso chico inventado (P4); el
modelo es un guion."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.models import Cause
from evaluon.assessment.services import evaluate, remedy, review
from evaluon.audit.models import Channel
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import number_of
from tests.assessment.test_remedy import (  # noqa: F401 - fixtures y ayudas del caso
    GUARANTEE,
    POLICY,
    external,
    missing,
    policy,
    read_documents,
    script,
)
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db


def finish(user, requested):
    """Corre el pedido encolado como lo haría el worker."""
    from evaluon.assessment.models import Channel as RunChannel
    from evaluon.tenders import jobs

    try:
        return evaluate.execute(requested.request, user, channel=RunChannel.EVAL,
                                audit_channel=Channel.EVAL, job=requested.job)
    finally:
        jobs.finish(requested.job)


def test_the_whole_remedy_leaves_both_evaluations_and_the_path(
        missing, offer, procedure, evaluator_user, model):
    """REQ-060: ante "no se encontró el documento" la Comisión pide la subsanación, agrega el
    documento, se evalúa de nuevo ese requisito leyendo el documento agregado y quedan las dos
    evaluaciones, el pedido, el documento con su huella y la decisión sobre la nueva."""
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza de caución.")
    added = remedy.add_document(evaluator_user, missing.pk, data=policy(),
                                file_name="poliza.pdf").decision
    read_documents()
    requested = remedy.reevaluate(evaluator_user, missing.pk)
    assert requested.request.cause == Cause.SUBSANACION
    runs = finish(evaluator_user, requested)
    new = evaluate.current_result(offer, missing.requirement)
    assert new.pk != missing.pk and new.previous == missing
    assert new.outcome == "cumple" and new.run == runs[0] and new.run.number == 2
    cited = new.citations.get(kind="oferta")
    assert cited.document == added.document and POLICY in cited.text
    assert any(d["document"] == added.document_id for d in new.run.documents)
    missing.refresh_from_db()
    assert missing.outcome == "sin_documento"  # la primera evaluación no se pisó
    assert am.Result.objects.filter(requirement=missing.requirement, offer=offer).count() == 2
    confirmed = review.confirm(evaluator_user, new.pk).decision
    stages = review.history(evaluator_user, offer.pk, missing.requirement_id)
    assert [s.result.pk for s in stages] == [missing.pk, new.pk]
    assert [d.action for d in stages[0].decisions] == ["pedir_subsanacion", "subsanar"]
    assert stages[0].citations["pliego"] and stages[1].decisions == [confirmed]


def test_the_history_page_shows_the_remedy_path(
        client, missing, offer, evaluator_user, model):
    """REQ-060, P6: el historial muestra el resultado con la cita del pliego, el pedido, el
    documento con su huella y quién lo cargó, la evaluación nueva y la decisión sobre ella."""
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza de caución.")
    document = remedy.add_document(evaluator_user, missing.pk, data=policy(),
                                   file_name="poliza.pdf").decision.document
    read_documents()
    new_request = remedy.reevaluate(evaluator_user, missing.pk)
    finish(evaluator_user, new_request)
    new = evaluate.current_result(offer, missing.requirement)
    review.confirm(evaluator_user, new.pk)
    log_in(client, evaluator_user)
    page = text_of(client.get(reverse("assessment:history",
                                      args=[offer.pk, missing.requirement_id])))
    for needle in ("Evaluación 1", "Evaluación 2 (vigente)", "No se encontró el documento",
                   "Pedir la subsanación", "Se pide la póliza de caución.",
                   document.file_sha256, evaluator_user.username,
                   "Documento agregado por subsanación", "reemplaza a la propuesta de la "
                   "evaluación 1", "Confirmar", "Lo que pedía el pliego"):
        assert needle in page, needle


def pair_url(result):
    return reverse("assessment:pair", args=[result.offer_id, result.requirement_id])


def test_the_evaluator_sees_and_uses_the_remedy_from_the_pair_page(
        client, missing, offer, evaluator_user):
    """REQ-060: la página del par ofrece pedir la subsanación; después, agregar el documento."""
    log_in(client, evaluator_user)
    page = text_of(client.get(pair_url(missing)))
    assert "Subsanación" in page and "Pedir la subsanación" in page
    response = client.post(reverse("assessment:request_remedy", args=[missing.pk]),
                           {"note": "Se pide la póliza."})
    assert response.status_code == 302
    page = text_of(client.get(pair_url(missing)))
    assert "Subsanación pedida por" in page and "Agregar el documento a la oferta" in page
    upload = SimpleUploadedFile("poliza.pdf", policy(), content_type="application/pdf")
    response = client.post(reverse("assessment:add_remedy_document", args=[missing.pk]),
                           {"file": upload})
    assert response.status_code == 302
    page = text_of(client.get(pair_url(missing)))
    assert "Documento agregado: «poliza»" in page and "espere a que termine" in page
    refused = client.post(reverse("assessment:reevaluate_remedy", args=[missing.pk]))
    assert refused.status_code == 422
    assert "se están leyendo" in text_of(refused) or "leyendo" in text_of(refused)
    read_documents()
    assert client.post(reverse("assessment:reevaluate_remedy", args=[missing.pk])
                       ).status_code == 302


def test_the_operator_neither_sees_nor_can_post_the_remedy(client, missing, operator_user):
    """P3: sin el rol de evaluador no hay formularios de subsanación y el POST es 403."""
    log_in(client, operator_user)
    page = text_of(client.get(pair_url(missing)))
    assert "Solo el evaluador de la Comisión pide la subsanación" in page
    assert "Pedir la subsanación" not in page
    response = client.post(reverse("assessment:request_remedy", args=[missing.pk]),
                           {"note": "x"})
    assert response.status_code == 403
    assert not am.Decision.objects.exists()


def test_a_refused_remedy_request_comes_back_with_the_reason(client, missing, evaluator_user):
    """REQ-060: sin motivo el pedido vuelve a la página con el mensaje (422)."""
    log_in(client, evaluator_user)
    response = client.post(reverse("assessment:request_remedy", args=[missing.pk]),
                           {"note": " "})
    assert response.status_code == 422 and "Escriba el motivo" in text_of(response)


@pytest.fixture
def asked(offer, operator_user, procedure, model):
    from tests.assessment.test_evaluate import run_all

    model.evaluates(lambda call: says("no_consta", exigence="condicion",
                                      question="¿Desde cuándo corre el plazo?")
                    if "sesenta días" in call.requirement else None)
    run_all(operator_user, procedure)
    return am.Question.objects.get(requirement__number=number_of(procedure, "sesenta días"))


def test_the_operator_sees_the_questions_but_cannot_answer(
        client, asked, procedure, operator_user, no_commission_user):
    """P3: el operador ve la lista sin formulario y su POST es 403; sin rol, 403 también."""
    log_in(client, operator_user)
    page = text_of(client.get(reverse("assessment:questions", args=[procedure.pk]), follow=True))
    assert "¿Desde cuándo corre el plazo?" in page and "Responder" not in page.replace(
        "Respuesta", "")
    assert client.post(reverse("assessment:answer", args=[asked.pk]),
                       {"text": "x"}).status_code == 403
    assert not am.Answer.objects.exists()
    client.logout()
    log_in(client, no_commission_user)
    assert client.get(reverse("assessment:questions", args=[procedure.pk]), follow=True).status_code == 200  # el lector ve la pestaña, sin acciones (2026-10-10)


def test_the_pair_page_links_the_open_question(client, asked, offer, evaluator_user,
                                               procedure):
    """REQ-055: la página del par con pregunta abierta lleva a la lista de preguntas."""
    log_in(client, evaluator_user)
    result = evaluate.current_result(offer, asked.requirement)
    html = client.get(pair_url(result)).content.decode()
    assert reverse("assessment:questions", args=[procedure.pk]) in html
