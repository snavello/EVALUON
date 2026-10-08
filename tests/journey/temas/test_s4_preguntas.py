"""Tema «preguntas y subsanación» de la sección Evaluación y dictamen (REQ-090; plan 014, T-208).
Los resultados se guardan directo, sin el modelo (la GPU no se comparte); todo el material es
inventado (P4)."""

import datetime
import html as htmllib
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import questions
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.temas import s4_preguntas, s4_propuesta
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    evaluated,
    requirement,
    three,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.offers.conftest import DATA

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def block(client, procedure):
    """El bloque «Preguntas a la Comisión y pedidos de subsanación» de la pestaña."""
    response = client.get(tab(procedure))
    assert response.status_code == 200
    html = response.content.decode()
    start = html.index('id="s4-preguntas"')
    end = html.find('id="s4-informe"', start)
    return html[start:] if end < 0 else html[start:end]


def notice(client, response):
    assert response.status_code == 302
    assert response["Location"].startswith("/expedientes/") and "#s4-preguntas" in response[
        "Location"]
    page_ = client.get(response["Location"])
    assert page_.status_code == 200
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)" id="s4-aviso"[^>]*>(.*?)</p>',
                      page_.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


def result_of(offer, requirement_):
    return am.Result.objects.filter(offer=offer, requirement=requirement_).get()


@pytest.fixture
def asked(evaluated, procedure, evaluator_user):
    """Una pregunta abierta (oferta C, garantía) y una respondida (oferta B, declaración)."""
    _, b, c = evaluated
    guarantee = requirement(procedure, "garantía de mantenimiento")
    declaration = requirement(procedure, "declaración jurada")
    open_ = am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=c,
        result=result_of(c, guarantee), text="¿La garantía está vigente?",
        reason="No se pudo determinar")
    done = am.Question.objects.create(
        procedure=procedure, requirement=declaration, offer=b,
        result=result_of(b, declaration), text="¿La firma es del apoderado?")
    answer = questions.answer(evaluator_user, done.pk, "Sí, figura en el poder.").answer
    return open_, done, answer


def answer_url(procedure, question):
    return reverse("expedientes:s4_responder", args=[procedure.pk, question.pk])


# --- Qué se ve ---------------------------------------------------------------------------------


def test_an_open_question_is_among_the_pending_with_its_access_to_answer(
        client, asked, procedure, evaluator_user):
    """REQ-090: la pregunta abierta figura entre los pendientes de la sección con su acceso
    «Resolver», que lleva a esta pestaña, y el evaluador tiene ahí el formulario para
    responderla."""
    open_, _, _ = asked
    status = s4_propuesta.status(evaluator_user, procedure)
    items = [i for i in status.pending_items if "pregunta abierta" in i.text]
    assert len(items) == 1 and items[0].action == "Resolver"
    assert items[0].url.startswith(tab(procedure))
    assert f"requisito {open_.requirement.number}" in items[0].text
    # La cuenta de la sección la suma s4_propuesta; este tema no duplica pendientes.
    assert s4_preguntas.status(evaluator_user, procedure).pending_items == ()
    section = sections_for(evaluator_user, procedure).get("evaluacion")
    assert sum(1 for i in section.pending_items if "pregunta abierta" in i.text) == 1
    log_in(client, evaluator_user)
    html = block(client, procedure)
    assert f'id="preg-{open_.pk}"' in html
    assert answer_url(procedure, open_) in html and "Responder" in html


def test_the_block_shows_the_open_and_the_answered_with_who_and_when_in_local_time(
        client, asked, procedure, evaluator_user, operator_user):
    """REQ-090: abierta y respondida figuran con su estado; la respondida muestra el texto, quién
    y cuándo (hora local, no UTC); el operador lo ve igual pero sin botones."""
    open_, done, answer = asked
    # 01:30 UTC del 8 de octubre es el 7 a las 22:30 en Buenos Aires.
    # Las respuestas no se modifican: se agrega otra, que pasa a ser la vigente.
    later = am.Answer.objects.create(
        question=done, text="Sí, figura en el poder.", scope=answer.scope,
        answered_by=evaluator_user, event=answer.event,
        answered_at=datetime.datetime(2099, 10, 8, 1, 30, tzinfo=datetime.timezone.utc))
    assert later.pk != answer.pk
    log_in(client, operator_user)
    html = block(client, procedure)
    assert "Abierta" in html and "Respondida" in html
    assert "¿La garantía está vigente?" in html and "¿La firma es del apoderado?" in html
    assert "Sí, figura en el poder." in html
    assert f"{evaluator_user.username} · 07/10/2099 22:30" in html
    assert "<form" not in html and "Lo decide un evaluador" in html
    assert "Responder" not in html


def test_the_block_has_the_approved_titles_and_none_of_the_mockup_samples_or_old_links(
        client, asked, procedure, evaluator_user):
    """REQ-090/REQ-100: títulos de la maqueta aprobada, sin textos de ejemplo ni enlaces a las
    pantallas viejas."""
    log_in(client, evaluator_user)
    html = block(client, procedure)
    for text in ("Preguntas a la Comisión y pedidos de subsanación", "Asunto",
                 "Oferta · requisito", "Respuesta registrada / acción"):
        assert text in html
    assert "por decidir" in html and "resueltos" in html
    for sample in ("pago a 15 días", "hoja de compliance según", "evaluador de muestra",
                   "[texto de ejemplo]"):
        assert sample not in html
    assert "/assessment/" not in html and "/evaluacion/pregunta" in html
    assert reverse("assessment:questions", args=[procedure.pk]) not in html


# --- Responder -----------------------------------------------------------------------------------


def test_answering_leaves_the_same_answer_and_fact_as_the_old_route(
        client, asked, evaluated, procedure, evaluator_user):
    """REQ-090: responder desde la pestaña deja la misma respuesta y el mismo hecho de auditoría
    que `assessment:answer`, vuelve a la pestaña con su aviso y la fila muestra quién y
    cuándo."""
    open_, _, _ = asked
    guarantee = requirement(procedure, "garantía de mantenimiento")
    other = am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=evaluated[0],
        result=result_of(evaluated[0], guarantee), text="Otra pregunta")
    log_in(client, evaluator_user)
    old = client.post(reverse("assessment:answer", args=[other.pk]),
                      {"text": "Vigente.", "scope": "par"})
    assert old.status_code == 302
    new = client.post(answer_url(procedure, open_), {"text": "Vigente.", "scope": "par"})
    ok, text = notice(client, new)
    assert ok and f"oferta {open_.offer.number}" in text and "quién y cuándo" in text
    first = am.Answer.objects.get(question=other)
    second = am.Answer.objects.get(question=open_)
    for field in ("text", "scope", "answered_by_id"):
        assert getattr(first, field) == getattr(second, field)
    skip = ("question", "question_text", "offer", "requirement")
    assert ({k: v for k, v in first.event.detail.items() if k not in skip}
            == {k: v for k, v in second.event.detail.items() if k not in skip})
    assert (first.event.event_type, first.event.outcome, first.event.channel) == (
        second.event.event_type, second.event.outcome, second.event.channel)
    assert second.event.event_type == EventType.EVAL_ANSWER
    html = block(client, procedure)
    assert "Vigente." in html and f"{evaluator_user.username} · " in html
    assert "Solo esa oferta y ese requisito" in html


def test_an_empty_answer_is_refused_and_says_why(client, asked, procedure, evaluator_user):
    """REQ-090: sin texto no se guarda nada y el aviso lo dice."""
    open_, _, _ = asked
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(answer_url(procedure, open_), {"text": "  "}))
    assert not ok and "Escriba la respuesta" in text
    assert not am.Answer.objects.filter(question=open_).exists()
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_ANSWER,
                                     outcome=AuditOutcome.REJECTED).exists()


def test_the_operator_cannot_answer_and_the_refusal_is_recorded(
        client, asked, procedure, operator_user):
    """P3, P6: sin el rol de evaluador responder da 403, no cambia nada y deja el hecho
    `rejected`."""
    open_, _, _ = asked
    log_in(client, operator_user)
    before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    response = client.post(answer_url(procedure, open_), {"text": "Vigente."})
    assert response.status_code == 403
    assert not am.Answer.objects.filter(question=open_).exists()
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == before + 1


def test_a_question_of_another_procedure_is_not_found(client, asked, procedure,
                                                      evaluator_user):
    """La ruta es del procedimiento: una pregunta que no es de él no existe."""
    open_, _, _ = asked
    log_in(client, evaluator_user)
    wrong = reverse("expedientes:s4_responder", args=[procedure.pk + 999, open_.pk])
    assert client.post(wrong, {"text": "x"}).status_code == 404


# --- Subsanación ---------------------------------------------------------------------------------


def missing(evaluated, procedure):
    registry = requirement(procedure, "constancia de inscripción")
    return result_of(evaluated[2], registry)  # «no se encontró el documento»


def test_a_remediable_result_is_a_remedy_to_decide_and_only_the_evaluator_has_buttons(
        client, evaluated, procedure, evaluator_user, operator_user):
    """REQ-090: el resultado «no se encontró el documento» figura como subsanación por decidir,
    con «Pedir que se subsane» para el evaluador y sin botones para el operador."""
    result = missing(evaluated, procedure)
    log_in(client, operator_user)
    html = block(client, procedure)
    assert "Subsanación: falta el documento" in html and "Por decidir" in html
    assert f'id="sub-{result.pk}"' in html and "<form" not in html
    assert "Lo decide un evaluador" in html
    client.logout()
    log_in(client, evaluator_user)
    html = block(client, procedure)
    assert "Pedir que se subsane" in html and "Motivo del pedido (obligatorio)" in html
    assert reverse("expedientes:s4_pedir_subsanacion", args=[procedure.pk, result.pk]) in html


def test_asking_the_remedy_leaves_the_same_decision_and_fact_as_the_old_route(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: pedir la subsanación desde la pestaña deja la misma decisión y el mismo hecho
    que `assessment:request_remedy`; sin motivo no cambia nada; la fila muestra quién y
    cuándo."""
    result = missing(evaluated, procedure)
    url = reverse("expedientes:s4_pedir_subsanacion", args=[procedure.pk, result.pk])
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(url, {"note": "  "}))
    assert not ok and "motivo" in text.lower()
    assert not am.Decision.objects.filter(result=result).exists()
    old = client.post(reverse("assessment:request_remedy", args=[result.pk]),
                      {"note": "Se pide la constancia."})
    assert old.status_code == 302
    ok, text = notice(client, client.post(url, {"note": "Se pide la constancia."}))
    assert ok and "Se pidió la subsanación" in text
    first, second = am.Decision.objects.filter(
        result=result, action=am.Action.PEDIR_SUBSANACION).order_by("pk")
    for field in ("action", "note", "user_id", "outcome_after"):
        assert getattr(first, field) == getattr(second, field)
    assert first.event.detail == second.event.detail
    assert (first.event.event_type, first.event.outcome, first.event.channel) == (
        second.event.event_type, second.event.outcome, second.event.channel)
    html = block(client, procedure)
    assert "Pedida, falta el documento" in html
    assert f"Pedida por {evaluator_user.username} el " in html
    assert "motivo: Se pide la constancia." in html
    assert "Agregar el documento" in html and "Pedir que se subsane" not in html


def test_the_operator_cannot_ask_the_remedy_and_the_refusal_is_recorded(
        client, evaluated, procedure, operator_user):
    """P3, P6: pedir la subsanación sin ser evaluador da 403, no deja decisión y registra el
    rechazo."""
    result = missing(evaluated, procedure)
    log_in(client, operator_user)
    before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    response = client.post(
        reverse("expedientes:s4_pedir_subsanacion", args=[procedure.pk, result.pk]),
        {"note": "Se pide."})
    assert response.status_code == 403
    assert not am.Decision.objects.exists()
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == before + 1


def test_adding_the_document_shows_it_and_waits_for_the_reading_to_evaluate_again(
        client, evaluated, procedure, evaluator_user, operator_user):
    """REQ-090: agregar el documento de la subsanación lo deja vinculado (quién y cuándo), lo
    muestra en la fila y «evaluar de nuevo» espera a que se lea; sin archivo, no cambia nada."""
    result = missing(evaluated, procedure)
    ask = reverse("expedientes:s4_pedir_subsanacion", args=[procedure.pk, result.pk])
    add = reverse("expedientes:s4_agregar_documento", args=[procedure.pk, result.pk])
    log_in(client, evaluator_user)
    client.post(ask, {"note": "Se pide la constancia."})
    ok, text = notice(client, client.post(add, {"note": "sin archivo"}))
    assert not ok
    assert not am.Decision.objects.filter(action=am.Action.SUBSANAR).exists()
    upload = SimpleUploadedFile("constancia.pdf", (DATA / "poliza-caucion.pdf").read_bytes(),
                                content_type="application/pdf")
    ok, text = notice(client, client.post(add, {"file": upload, "note": "Llegó el 4/10."}))
    assert ok and "Se agregó el documento" in text
    added = am.Decision.objects.get(result=result, action=am.Action.SUBSANAR)
    assert added.user == evaluator_user and added.document.offer_id == result.offer_id
    html = block(client, procedure)
    assert "Documento agregado: «" in html and f"por {evaluator_user.username} el " in html
    reevaluate = reverse("expedientes:s4_evaluar_subsanacion", args=[procedure.pk, result.pk])
    assert reevaluate in html and "Se puede cuando termine de leerse" in html
    assert re.search(r'<button class="btn primario chico" type="submit" disabled>Evaluar de nuevo',
                     html)
    # Mientras se lee, evaluar de nuevo se rechaza con el motivo y no cambia nada.
    runs = am.Run.objects.count()
    ok, text = notice(client, client.post(reevaluate))
    assert not ok and am.Run.objects.count() == runs
    client.logout()
    log_in(client, operator_user)
    html = block(client, procedure)
    assert "Documento agregado: «" in html and reevaluate not in html


def test_a_result_that_was_evaluated_again_stays_as_a_resolved_remedy(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: la subsanación de un resultado que ya no rige queda a la vista como resuelta,
    con lo pedido y quién y cuándo."""
    result = missing(evaluated, procedure)
    log_in(client, evaluator_user)
    client.post(reverse("expedientes:s4_pedir_subsanacion", args=[procedure.pk, result.pk]),
                {"note": "Se pide la constancia."})
    registry = result.requirement
    newer = am.Run.objects.create(
        request=result.run.request, offer=result.offer, matrix_version=result.run.matrix_version,
        number=result.run.number + 1, channel=am.Channel.SCREEN, documents=[], norms={},
        models_used={}, parameters={}, prompt_versions={})
    am.Result.objects.create(run=newer, offer=result.offer, requirement=registry,
                             outcome="cumple", exigence=am.Exigence.CONDICION,
                             explanation="Ahora está.", previous=result)
    html = block(client, procedure)
    assert "Subsanación: ya se evaluó de nuevo" in html and "Subsanada" in html
    assert "motivo: Se pide la constancia." in html
    assert "Pedir que se subsane" not in html
