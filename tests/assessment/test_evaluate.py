"""Evaluar una oferta de punta a punta con un modelo simulado (REQ-052 a REQ-055, REQ-059,
REQ-060; plan 004, "Flujo de IA"; ADR-0037 a ADR-0039; T-150). Caso chico y textos inventados
(P4); el modelo es un guion (`fakes.py`)."""

import sys

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.core.management.base import CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import ServiceTimeoutError
from evaluon.assessment import models as am
from evaluon.assessment.models import Channel as RunChannel
from evaluon.assessment.services import evaluate
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.offers import models as om
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

DECLARATION = "Declaro bajo juramento que me encuentro habilitado para contratar"


def number_of(procedure, needle):
    """El número del requisito de la matriz cuyo texto contiene `needle`."""
    version = procedure.matrix_versions.get(number=1)
    for requirement in version.requirements.all():
        if any(needle in q.text for q in requirement.quotes.all()):
            return requirement.number
    raise AssertionError(needle)


def requirement_of(procedure, needle):
    version = procedure.matrix_versions.get(number=1)
    return version.requirements.get(number=number_of(procedure, needle))


def open_matrix():
    """Deja sumar filas a la matriz validada (una consecuencia, una circular): apaga los
    disparadores que solo admiten filas en un borrador. Vale solo dentro de esta prueba: la
    transacción de la prueba se deshace al terminar y con ella el cambio."""
    with connection.cursor() as cursor:
        for table in ("tenders_consequence", "tenders_requirement_source"):
            cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")


def run_all(user, procedure, **kwargs):
    """Pide y corre la evaluación; devuelve `(pedido, evaluaciones)`."""
    requested = evaluate.request_evaluation(user, procedure, **kwargs)
    try:
        runs = evaluate.execute(requested.request, user, channel=RunChannel.EVAL,
                                audit_channel=Channel.EVAL, job=requested.job)
    finally:
        jobs.finish(requested.job)
    return requested.request, runs


def results_of(run):
    return {r.requirement.number: r for r in run.results.select_related("requirement")}


def offer_cites(result):
    return list(result.citations.filter(kind="oferta").order_by("order"))


def cumple_declaration(call):
    """Un guion: la declaración jurada cumple; el resto, "no consta"."""
    if "declaración jurada" in call.requirement:
        return says("cumple", call.quote(DECLARATION), exigence="condicion")
    return None


# --- Pedido ------------------------------------------------------------------------------------


def test_the_request_queues_one_job_and_records_the_fact(offer, operator_user, procedure):
    """REQ-052, P6: un pedido de evaluación encola un solo pedido `evaluate_offers` que nombra
    el pedido, y deja el hecho `eval_request` con la versión de la matriz."""
    requested = evaluate.request_evaluation(operator_user, procedure)
    job = requested.job
    assert job.kind == m.JobKind.EVALUATE_OFFERS and job.status == m.JobStatus.QUEUED
    assert job.target_id == requested.request.pk
    assert requested.request.job_id == job.pk
    assert requested.request.offers == [offer.pk] and requested.request.requirements is None
    assert requested.request.cause == "matriz"
    event = AuditEvent.objects.get(event_type=EventType.EVAL_REQUEST)
    assert event.outcome == "ok" and event.user == operator_user
    assert event.detail["matrix_version_number"] == 1
    assert event.detail["request"] == requested.request.pk and event.detail["job"] == job.pk


def test_an_evaluator_can_request_a_single_requirement_of_a_single_offer(
        offer, evaluator_user, procedure):
    """REQ-059: se puede pedir un requisito de una oferta (volver a evaluar)."""
    requirement = requirement_of(procedure, "declaración jurada")
    requested = evaluate.request_evaluation(
        evaluator_user, procedure, offers=[offer], requirements=[requirement],
        cause=am.Cause.MANUAL)
    assert requested.request.requirements == [requirement.pk]
    assert requested.request.cause == "manual"


def test_a_user_without_a_commission_role_is_rejected_and_nothing_is_queued(
        offer, no_commission_user, procedure):
    """Roles: sin rol de la Comisión, no se pide; el rechazo queda registrado."""
    with pytest.raises(RoleRejected):
        evaluate.request_evaluation(no_commission_user, procedure)
    assert not m.Job.objects.filter(kind=m.JobKind.EVALUATE_OFFERS).exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def refused(user, procedure, reason, **kwargs):
    with pytest.raises(evaluate.EvaluationRefused) as error:
        evaluate.request_evaluation(user, procedure, **kwargs)
    assert error.value.reason == reason
    event = AuditEvent.objects.filter(event_type=EventType.EVAL_REQUEST).latest("pk")
    assert event.outcome == "rejected" and event.detail["reason"] == reason
    return error.value


def test_a_procedure_without_a_validated_matrix_is_refused(operator_user, db):
    """REQ-057: sin matriz validada no se evalúa."""
    bare = m.Procedure.objects.create(
        number="SIN-MATRIZ", procedure_type="x", subject="x",
        authorization_date="2026-01-15", created_by=operator_user)
    refused(operator_user, bare, "no_matrix")
    assert not m.Job.objects.exists()


def test_a_procedure_without_offers_is_refused(matrix, operator_user):
    refused(operator_user, matrix.procedure, "no_offers")


def test_an_offer_without_documents_is_refused(matrix, operator_user):
    from evaluon.audit.models import Channel as AuditChannel
    from evaluon.offers.services import offers as offers_service

    offers_service.register_offer(operator_user, matrix.procedure, bidder="Sin documentos",
                                  channel=AuditChannel.COMMAND)
    refused(operator_user, matrix.procedure, "no_documents")


def test_a_document_still_being_read_or_failed_is_refused(offer, operator_user, procedure):
    """El pedido espera a que termine la lectura de todos los documentos y no sigue con uno
    cuya lectura falló."""
    document = om.Document.objects.create(
        offer=offer, title="nuevo", file_name="nuevo.pdf", file_format="pdf", file_size=1,
        file_sha256="b" * 64, loaded_by=operator_user)
    refused(operator_user, procedure, "reading_in_progress")
    m.Job.objects.create(kind=m.JobKind.READ_OFFER_DOCUMENT, procedure=procedure,
                         target_id=document.pk, status=m.JobStatus.FAILED,
                         requested_by=operator_user, error="falla")
    refused(operator_user, procedure, "reading_failed")


def test_only_one_request_in_progress_per_procedure(offer, operator_user, procedure):
    evaluate.request_evaluation(operator_user, procedure)
    refused(operator_user, procedure, "request_in_progress")


def test_requirements_that_are_not_of_the_matrix_are_refused(offer, operator_user,
                                                             procedure):
    refused(operator_user, procedure, "invalid_request", requirements=[999999])


# --- Un resultado con cita ---------------------------------------------------------------------


def test_a_cumple_has_a_literal_citation_located_by_the_system(offer, operator_user, procedure,
                                                               model):
    """REQ-052, REQ-053: "cumple" con el texto de la oferta, ubicado en el texto canónico: la
    cita es el recorte del canónico, con su documento y su página, y el requisito del pliego
    va como fundamento."""
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "declaración jurada")
    result = results_of(runs[0])[number]
    assert result.outcome == "cumple" and result.doubt == ""
    cite = offer_cites(result)[0]
    assert cite.text == cite.reading.canonical_text[cite.char_start:cite.char_end]
    assert cite.text.startswith(DECLARATION) and cite.page == 1
    assert cite.document.file_name == "oferta.pdf"
    pliego = result.citations.get(kind="pliego")
    assert "declaración jurada" in pliego.text and pliego.requirement_quote is not None
    assert pliego.original_text == ""
    assert len(model.contrast_calls) == 1  # solo el "cumple" se contrasta


def test_the_page_and_the_text_are_the_systems_not_the_models(offer, operator_user, procedure,
                                                              model):
    """REQ-053: el modelo cita con otros espacios y el texto guardado es el del documento."""
    def function(call):
        if "declaración jurada" in call.requirement:
            alias = call.alias_with(DECLARATION)
            return says("cumple", (alias, "Declaro   bajo juramento que me encuentro\n"
                                          "habilitado para contratar"))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert offer_cites(result)[0].text == DECLARATION


def test_a_citation_that_cannot_be_located_lowers_the_cumple_to_undetermined(
        offer, operator_user, procedure, model):
    """REQ-053, P3: un "cumple" cuya cita no está en el documento se reintenta una vez y, si
    sigue igual, queda "no determinado" `sin_cita`, sin cita de la oferta."""
    def function(call):
        if "declaración jurada" in call.requirement:
            return says("cumple", (call.alias_with(DECLARATION), "Texto que no está"))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "declaración jurada")
    result = results_of(runs[0])[number]
    assert result.outcome == "no_determinado" and result.doubt == "sin_cita"
    assert offer_cites(result) == []
    asked = [c for c in model.calls if "declaración jurada" in c.requirement]
    assert len(asked) == 2  # el pedido y su reintento
    assert "letra por letra" in asked[1].messages[-1]["content"]
    steps = am.Step.objects.filter(run=runs[0], requirement__number=number)
    assert steps.count() == 2 and steps.exclude(retry_of=None).count() == 1
    assert any(a["type"] == "cita_no_ubicada" for a in runs[0].anomalies)
    assert not model.contrast_calls


def test_a_citation_with_the_wrong_alias_is_located_in_the_document_that_has_it(
        offer, operator_user, procedure, model):
    """REQ-053, T-157: el modelo copió bien el texto pero nombró otro documento del grupo; el
    sistema lo ubica en el documento que de verdad lo tiene y lo anota como anomalía."""
    def function(call):
        if "declaración jurada" in call.requirement:
            right = call.alias_with(DECLARATION)
            wrong = next(a for a in call.documents if a != right)
            return says("cumple", (wrong, DECLARATION))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "cumple"
    cite = offer_cites(result)[0]
    assert cite.document.file_name == "oferta.pdf" and cite.text == DECLARATION
    assert any(a["type"] == "cita_en_otro_documento" for a in runs[0].anomalies)


def test_the_retry_can_rescue_a_citation(offer, operator_user, procedure, model):
    """REQ-053: el reintento con el aviso puede dar una cita ubicada."""
    def function(call):
        if "declaración jurada" in call.requirement:
            retried = "letra por letra" in call.messages[-1]["content"]
            text = DECLARATION if retried else "Texto que no está"
            return says("cumple", (call.alias_with(DECLARATION), text))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "cumple"
    assert len([c for c in model.calls if "declaración jurada" in c.requirement]) == 2


def test_a_contrast_that_does_not_corroborate_lowers_the_cumple(offer, operator_user,
                                                                procedure, model):
    """ADR-0038: el contraste que no contesta `si` baja el "cumple" a "no determinado" con
    las mismas citas; el pedido del contraste queda registrado."""
    model.evaluates(cumple_declaration)
    model.contrasts(lambda call: {"respuesta": "parcial", "motivo": "solo lo anuncia"})
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "declaración jurada")
    result = results_of(runs[0])[number]
    assert result.outcome == "no_determinado" and result.doubt == "sin_corroborar"
    assert len(offer_cites(result)) == 1
    assert "solo lo anuncia" in result.explanation
    contrast = am.Step.objects.get(run=runs[0], purpose="contraste")
    assert contrast.requirement.number == number and contrast.parsed["respuesta"] == "parcial"
    # el contraste recibe solo el requisito, el texto citado y los fundamentos
    assert DECLARATION in model.contrast_calls[0].user
    assert "Texto de la oferta" not in model.contrast_calls[0].user


def test_the_contrasts_are_asked_after_all_the_readings(offer, operator_user, procedure,
                                                        model):
    """Plan, "Orden de los pedidos": los contrastes van todos juntos al final, para no
    desalojar el prefijo de los documentos."""
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION))
                    if "declaración jurada" in call.requirement or "Renglón 1" in
                    call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    purposes = list(am.Step.objects.filter(run=runs[0]).order_by("pk")
                    .values_list("purpose", flat=True))
    first_contrast = purposes.index("contraste")
    assert set(purposes[:first_contrast]) == {"grupo"}
    assert set(purposes[first_contrast:]) == {"contraste"}


def test_a_no_cumple_needs_a_citation_and_a_contrast_too(offer, operator_user, procedure,
                                                         model):
    """REQ-052: un "no cumple" con cita y contraste `si` queda "no cumple"."""
    model.evaluates(lambda call: says("no_cumple", call.quote("sesenta días corridos"))
                    if "sesenta días" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "sesenta días")]
    assert result.outcome == "no_cumple" and offer_cites(result)


# --- Los otros dos resultados ------------------------------------------------------------------


def test_a_missing_document_is_not_found_and_is_not_a_no_cumple(offer, operator_user,
                                                                procedure, model):
    """REQ-060: el pliego exige un documento que ninguno de la oferta es: "no se encontró el
    documento", con la cita del pliego, sin cita de la oferta y sin pregunta."""
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "libre deuda")]
    assert result.outcome == "sin_documento" and result.exigence == "documento"
    assert offer_cites(result) == []
    assert "libre deuda" in result.citations.get(kind="pliego").text
    assert not am.Question.objects.filter(requirement__number=result.requirement.number)
    assert not runs[0].results.filter(outcome="no_cumple").exists()


def test_no_consta_in_a_condition_is_undetermined_with_a_question(offer, operator_user,
                                                                  procedure, model):
    """REQ-055: un dato que no está en la oferta ni en la normativa: "no determinado" con una
    pregunta concreta a la Comisión; sin respuesta no es fundamento."""
    def function(call):
        if "sesenta días" in call.requirement:
            return says("no_consta", exigence="condicion",
                        question="¿Desde cuándo corre el plazo de sesenta días?")

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "sesenta días")
    result = results_of(runs[0])[number]
    assert result.outcome == "no_determinado" and result.doubt == "sin_dato"
    question = am.Question.objects.get(requirement__number=number)
    assert question.text == "¿Desde cuándo corre el plazo de sesenta días?"
    assert question.result == result and question.offer == offer
    assert not am.Answer.objects.exists()


def test_an_external_requirement_is_a_missing_compliance_sheet_without_a_question(
        offer, operator_user, procedure, model):
    """P9, REQ-063: lo que se verifica fuera de la oferta queda "no determinado" `externo`
    (falta la hoja de compliance) y sin pregunta (se sube la hoja), aunque la oferta lo
    declare."""
    def function(call):
        if "libre deuda" in call.requirement:
            return says("cumple", call.quote(DECLARATION), external=True)

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "libre deuda")
    result = results_of(runs[0])[number]
    assert result.outcome == "no_determinado" and result.doubt == "externo"
    assert not am.Question.objects.filter(requirement__number=number).exists()
    assert result.facts["regla"] == "externo_modelo"
    assert not model.contrast_calls


def test_an_open_question_is_reused_by_a_new_evaluation_of_the_pair(offer, operator_user,
                                                                    procedure, model):
    """ADR-0040: una pregunta por oferta y requisito mientras esté abierta."""
    model.evaluates(lambda call: says("no_consta", exigence="condicion", question="¿Cuál?")
                    if "sesenta días" in call.requirement else None)
    run_all(operator_user, procedure)
    run_all(operator_user, procedure)
    number = number_of(procedure, "sesenta días")
    assert am.Question.objects.filter(requirement__number=number).count() == 1


def test_no_consta_with_unread_pages_is_not_a_missing_document(
        procedure, operator_user, model):
    """ADR-0038: con páginas sin leer en la oferta, "no consta" no es "no se encontró el
    documento": "no determinado" por lectura incompleta, con pregunta y aviso."""
    unread = make_offer(procedure, operator_user, "Con una página ilegible", {
        "firmado.pdf": ["Se adjunta la copia del documento de identidad.", ""]},
        unread=[("firmado.pdf", 2)])
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure, offers=[unread])
    result = results_of(runs[0])[number_of(procedure, "libre deuda")]
    assert result.outcome == "no_determinado" and result.doubt == "lectura_incompleta"
    assert result.unread_pages_warning
    assert "firmado.pdf, página 2" in am.Question.objects.get(
        requirement__number=result.requirement.number).text
    assert "--- página 2: no se pudo leer ---" in model.calls[0].documents["D1"]


# --- Grupos ------------------------------------------------------------------------------------


def words(n, prefix):
    return " ".join(f"{prefix}{i}" for i in range(n))


@pytest.fixture
def big_offer(procedure, operator_user, settings):
    """Una oferta que no entra en un grupo: tres documentos de unas 60 palabras, uno por grupo."""
    settings.ASSESSMENT_GROUP_TOKENS = 100
    return make_offer(procedure, operator_user, "Oferta grande", {
        "uno.pdf": [f"Primera. {DECLARATION}. {words(50, 'u')}"],
        "dos.pdf": [f"Segunda. El plazo es de sesenta días. {words(50, 'd')}"],
        "tres.pdf": [f"Tercera. {words(50, 't')}"]})


def test_a_big_offer_is_read_in_several_groups_and_every_group_is_asked(
        big_offer, operator_user, procedure, model, fake_ai):
    """REQ-054: si la oferta no entra, se pregunta por todos los grupos; la reescritura del
    requisito se calcula una vez por requisito."""
    fake_ai.reranker.scores = {"Segunda": 0.9, "Primera": 0.2}
    _, runs = run_all(operator_user, procedure)
    requirements = len(sheets_firm(procedure))
    assert len(model.calls) == 3 * requirements
    assert len(model.rewrite_calls) == len([r for r in sheets_firm(procedure)
                                            if r.category != "tecnico"])
    first = [c for c in model.calls if "declaración jurada" in c.requirement]
    # el más relevante primero: lo que dice `Segunda` va en el primer grupo
    assert "Segunda" in first[0].documents["D1"]
    assert [len(c.documents) for c in first] == [1, 1, 1]
    assert runs[0].counts["model_requests"] == len(model.calls) + len(model.rewrite_calls)
    assert am.Step.objects.filter(run=runs[0], purpose="reescritura",
                                  requirement=None).count() == len(model.rewrite_calls)


def sheets_firm(procedure):
    from evaluon.offers.services import sheets

    return sheets.firm_requirements(procedure.matrix_versions.get(number=1))


def test_cumple_and_no_cumple_in_different_groups_is_a_contradiction(
        big_offer, operator_user, procedure, model):
    """ADR-0038: "cumple" en un grupo y "no cumple" en otro: "no determinado" por
    contradicción, con las citas de ambos y sin contraste."""
    def function(call):
        if "declaración jurada" not in call.requirement:
            return None
        if "Primera" in "".join(call.documents.values()):
            return says("cumple", call.quote(DECLARATION))
        if "Segunda" in "".join(call.documents.values()):
            return says("no_cumple", call.quote("El plazo es de sesenta días"))
        return None

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "no_determinado" and result.doubt == "contradiccion"
    assert len(offer_cites(result)) == 2
    assert not model.contrast_calls


def test_no_consta_in_every_group_without_unread_pages_is_not_found(
        big_offer, operator_user, procedure, model):
    """ADR-0038: "no consta" en todos los grupos, la exigencia es un documento y todo se
    leyó: "no se encontró el documento"."""
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure)
    assert len(model.calls) > len(sheets_firm(procedure))
    result = results_of(runs[0])[number_of(procedure, "libre deuda")]
    assert result.outcome == "sin_documento"


def test_no_consta_in_every_group_with_a_group_not_read_is_incomplete(
        big_offer, operator_user, procedure, model, settings):
    """ADR-0038: si hay grupos sin leer por el tope, no se supone que el documento falta."""
    settings.ASSESSMENT_MAX_GROUPS = 1
    model.evaluates(lambda call: says("no_consta", exigence="documento"))
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "libre deuda")]
    assert result.outcome == "no_determinado" and result.doubt == "lectura_incompleta"
    assert any(a["type"] == "grupos_sin_leer" for a in runs[0].anomalies)


def test_a_document_bigger_than_the_budget_is_read_in_windows(
        procedure, operator_user, settings, model):
    """REQ-054: un documento mayor que el presupuesto se lee en ventanas; la cita se ubica en
    el documento entero y trae su página."""
    settings.ASSESSMENT_GROUP_TOKENS = 100
    offer = make_offer(procedure, operator_user, "Oferta con un documento largo", {
        "largo.pdf": [words(40, "a"), f"{DECLARATION}. {words(40, 'b')}", words(40, "c"),
                      words(40, "d")]})
    model.evaluates(lambda call: says("cumple", call.quote(DECLARATION))
                    if "declaración jurada" in call.requirement and
                    call.alias_with(DECLARATION) else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert runs[0].documents[0]["windows"] == [[1, 2], [2, 3], [3, 4]]
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "cumple" and offer_cites(result)[0].page == 2


# --- Fundamentos: respuestas de la Comisión y normas -------------------------------------------


def make_answer(procedure, offer, requirement, user, text, scope, *, number=None):
    from evaluon.audit import services as audit

    question = am.Question.objects.create(
        procedure=procedure, requirement=requirement, offer=offer,
        result=_any_result(offer, requirement, user), text="¿Qué pasa?", reason="externo")
    event = audit.record(EventType.EVAL_ANSWER, outcome="ok", channel=Channel.SCREEN, user=user)
    return am.Answer.objects.create(question=question, text=text, scope=scope,
                                    answered_by=user, event=event)


def _any_result(offer, requirement, user):
    run = am.Run.objects.filter(offer=offer).first()
    if run is None:
        request = am.Request.objects.create(
            procedure=offer.procedure, matrix_version=requirement.version,
            offers=[offer.pk], cause="matriz", requested_by=user)
        run = am.Run.objects.create(
            request=request, offer=offer, matrix_version=requirement.version, number=1,
            channel="screen", documents=[], norms={}, models_used={}, parameters={},
            prompt_versions={})
    result = am.Result.objects.filter(run=run, requirement=requirement).first()
    return result or am.Result.objects.create(
        run=run, offer=offer, requirement=requirement, outcome="no_determinado",
        doubt="externo")


def test_the_answer_that_applies_goes_to_the_model_and_the_one_that_does_not_does_not(
        offer, operator_user, evaluator_user, procedure, model):
    """REQ-056, ADR-0040: la respuesta vigente que aplica (alcance requisito, o par de esta
    oferta) se le da al modelo con quién y cuándo; la de otro requisito, la de un par de
    otra oferta y una pregunta sin responder, no."""
    target = requirement_of(procedure, "sesenta días")
    other = requirement_of(procedure, "declaración jurada")
    other_offer = make_offer(procedure, operator_user, "Otra oferta", {"x.pdf": ["Texto."]})
    applies = make_answer(procedure, offer, target, evaluator_user,
                          "El plazo corre desde la apertura.", "requisito")
    make_answer(procedure, offer, other, evaluator_user, "Otro requisito.", "requisito")
    make_answer(procedure, other_offer, target, evaluator_user, "Solo otra oferta.", "par")
    am.Question.objects.create(procedure=procedure, requirement=target, offer=offer,
                               result=applies.question.result, text="¿Sin responder?")

    model.evaluates(lambda call: None)
    run_all(operator_user, procedure, offers=[offer])
    mine = [c for c in model.calls if "sesenta días" in c.requirement]
    assert [t.split("Respuesta: ")[-1] for _, t in mine[0].answers.values()] == [
        "El plazo corre desde la apertura."]
    assert next(iter(mine[0].answers.values()))[0] == evaluator_user.username
    asked_other = [c for c in model.calls if "declaración jurada" in c.requirement]
    assert [t.split("Respuesta: ")[-1] for _, t in asked_other[0].answers.values()] == [
        "Otro requisito."]
    assert "Sin responder" not in mine[0].messages[-1]["content"]
    assert "Solo otra oferta" not in mine[0].messages[-1]["content"]


def test_the_latest_answer_replaces_the_previous_one(offer, evaluator_user, procedure):
    """ADR-0040: la vigente de una pregunta es la última; la anterior queda."""
    from evaluon.assessment import grounds

    requirement = requirement_of(procedure, "sesenta días")
    first = make_answer(procedure, offer, requirement, evaluator_user, "Primera.",
                        "procedimiento")
    am.Answer.objects.create(question=first.question, text="Segunda.", scope="procedimiento",
                             answered_by=evaluator_user, event=first.event)
    found = grounds.applicable_answers(requirement, offer)
    assert [a.text for a in found] == ["Segunda."]
    assert am.Answer.objects.filter(question=first.question).count() == 2


def test_an_answer_alone_does_not_make_a_cumple(offer, operator_user, evaluator_user,
                                                procedure, model):
    """ADR-0038, P3: una respuesta de la Comisión como único apoyo: sin cita de la oferta, el
    resultado queda "no determinado"; la respuesta se muestra como fundamento cuando el modelo
    la usó."""
    requirement = requirement_of(procedure, "sesenta días")
    make_answer(procedure, offer, requirement, evaluator_user, "Cumple con lo pedido.",
                "requisito")

    def function(call):
        if "sesenta días" in call.requirement:
            return says("cumple", supports=list(call.answers))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[requirement.number]
    assert result.outcome == "no_determinado" and result.doubt == "sin_cita"
    assert offer_cites(result) == []


def test_a_used_answer_is_shown_as_a_commission_answer_with_who_and_when(
        offer, operator_user, evaluator_user, procedure, model):
    """REQ-053: la respuesta que el modelo usó queda como fundamento `respuesta`."""
    requirement = requirement_of(procedure, "sesenta días")
    answer = make_answer(procedure, offer, requirement, evaluator_user, "Desde la apertura.",
                         "requisito")
    model.evaluates(lambda call: says("cumple", call.quote("sesenta días corridos"),
                                      supports=list(call.answers))
                    if "sesenta días" in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[requirement.number]
    assert result.outcome == "cumple"
    cite = result.citations.get(kind="respuesta")
    assert cite.answer == answer and cite.answer.answered_by == evaluator_user


def test_the_norms_the_matrix_associates_to_the_requirement_go_to_the_model(
        offer, operator_user, procedure, model, make_norm, make_document, make_reading):
    """REQ-053: las unidades de norma que la matriz asocia (fundamentos de la consecuencia) se
    le dan al modelo con la norma y el artículo; la que usa queda como cita `norma`."""
    norm = make_norm(citation="Norma sintética de prueba 1/2099")
    reading = make_reading(make_document(norm), [
        ("art-5", "Artículo 5. La oferta debe mantenerse durante el plazo fijado.")])
    unit = reading.units_by_key["art-5"]
    requirement = requirement_of(procedure, "sesenta días")
    open_matrix()
    m.Consequence.objects.create(
        requirement=requirement, consequence_type="desestimacion",
        grounds=[{"source": "norma", "unit": unit.pk}], origin="sistema")
    model.evaluates(lambda call: says("cumple", call.quote("sesenta días corridos"),
                                      supports=list(call.norms))
                    if "sesenta días" in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    call = next(c for c in model.calls if "sesenta días" in c.requirement)
    assert "Norma sintética de prueba 1/2099" in call.norms["N1"]
    assert "mantenerse durante el plazo" in call.norms["N1"]
    cite = results_of(runs[0])[requirement.number].citations.get(kind="norma")
    assert cite.norm_unit == unit and "Norma sintética de prueba" in cite.label


def test_a_requirement_changed_by_a_circular_goes_with_its_current_text(
        offer, operator_user, procedure, model):
    """REQ-053: el texto vigente del requisito es el de la circular, con el original al lado;
    el resultado guarda los dos."""
    requirement = requirement_of(procedure, "sesenta días")
    quote = requirement.quotes.get()
    open_matrix()
    m.RequirementSource.objects.create(
        requirement=requirement, quote=quote, effect="modifica", segment=quote.segment,
        char_start=quote.char_start, char_end=quote.char_end,
        text="Mantener la validez de la oferta por noventa días corridos.",
        issued_on="2026-02-01")
    model.evaluates(lambda call: None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    call = next(c for c in model.calls if "noventa días" in c.requirement)
    assert "Texto original, antes de la circular" in call.requirement
    cite = results_of(runs[0])[requirement.number].citations.get(kind="pliego")
    assert "noventa días" in cite.text and "sesenta días" in cite.original_text


def test_a_technical_row_is_evaluated_per_renglon_with_the_quotes_of_the_pliego(
        offer, operator_user, procedure, model):
    """Punto 2 del plan: la fila técnica por renglón opina con la cita de la especificación
    del pliego y el texto de la oferta."""
    row = next(r for r in sheets_firm(procedure) if r.category == "tecnico"
               and r.items == [1])
    model.evaluates(lambda call: says("cumple", call.quote("Renglón 1: resma de papel A4"))
                    if call.requirement.startswith("Renglón 1 del pliego") else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    call = next(c for c in model.calls if c.requirement.startswith("Renglón 1 del pliego"))
    assert "renglón 1" in call.requirement
    result = results_of(runs[0])[row.number]
    # T-167: lo que el modelo concluye es la opinión; el resultado espera el informe técnico.
    assert result.opinion == "cumple" and result.doubt == "pendiente_informe_tecnico"
    assert offer_cites(result)[0].text == "Renglón 1: resma de papel A4"
    assert result.citations.filter(kind="pliego").count() == row.quotes.count()


def test_a_technical_no_cumple_needs_a_cited_clause_that_contradicts_it(
        offer, operator_user, procedure, model):
    """REQ-052, T-156: un "no cumple" de un renglón sin una cláusula del pliego (copiada letra
    por letra del requisito) es "no determinado" sin dato, con pregunta; con la cláusula
    citada, queda "no cumple"."""
    row = next(r for r in sheets_firm(procedure) if r.category == "tecnico"
               and r.items == [1])
    cited = {"clause": ""}

    def function(call):
        if not call.requirement.startswith("Renglón 1 del pliego"):
            return None
        return {**says("no_cumple", call.quote("Renglón 1: resma de papel A4")),
                "clausula": cited["clause"]}

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    # T-167: lo que se juzga es la opinión; el resultado es siempre "pendiente del informe".
    assert result.opinion == "no_determinado" and result.doubt == "pendiente_informe_tecnico"
    cited["clause"] = "una cláusula inventada que el pliego no tiene"
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert results_of(runs[0])[row.number].opinion == "no_determinado"
    cited["clause"] = row.quotes.order_by("order").first().text
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    assert result.opinion == "no_cumple" and result.outcome == "no_determinado"


# --- Registro y no pisar nada ------------------------------------------------------------------


def test_everything_the_model_was_asked_is_recorded(offer, operator_user, procedure, model):
    """P6: cada pedido al modelo queda en `assessment_step` con el pedido completo, la salida
    cruda y lo interpretado; la evaluación guarda documentos, modelos con el contexto real,
    instrucciones, parámetros y normativa; el hecho `eval_build` los resume."""
    model.evaluates(cumple_declaration)
    request, runs = run_all(operator_user, procedure)
    run = runs[0]
    asked = len(model.calls) + len(model.contrast_calls) + len(model.rewrite_calls)
    steps = list(am.Step.objects.filter(run=run))
    assert len(steps) == asked == run.counts["model_requests"]
    step = next(s for s in steps if s.purpose == "grupo"
                and "declaración jurada" in s.request["messages"][-1]["content"])
    assert step.raw_output and step.parsed["resultado"] == "cumple"
    assert step.documents[0]["tokens"] > 0 and step.prompt_tokens is not None
    assert step.request["response_format"]["type"] == "json_schema"
    assert run.models_used["generation_batch"]["context_tokens"] == 32768
    assert run.prompt_versions == {
        "evaluacion": "evaluacion-v4", "contraste": "contraste-v2", "clausulas": "clausulas-v2",
        "reglas": "reglas-v1"}
    assert run.parameters["rules_version"] == "reglas-v1"
    assert run.parameters["group_tokens"] == 20000
    assert run.norms["matrix_version"] == 1 and run.norms["authorization_date"]
    assert run.matrix_version == request.matrix_version and run.channel == "eval"
    assert {d["file"] for d in run.documents} == {"oferta.pdf", "constancia.pdf"}
    assert all(d["sha256"] and d["tokens"] for d in run.documents)
    event = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD)
    assert event.outcome == "ok" and event.detail["run"] == run.pk
    assert event.detail["counts"]["pairs"] == len(sheets_firm(procedure))
    assert event.detail["models"] == run.models_used and event.detail["documents"]


def test_a_new_evaluation_does_not_overwrite_the_previous_one(offer, operator_user, procedure,
                                                              model):
    """ADR-0039: evaluar de nuevo un par crea un resultado nuevo que apunta al anterior; el
    anterior queda y el vigente es el más reciente."""
    model.evaluates(cumple_declaration)
    requirement = requirement_of(procedure, "declaración jurada")
    _, first = run_all(operator_user, procedure)
    before = results_of(first[0])[requirement.number]
    model.evaluates(lambda call: None)
    _, second = run_all(operator_user, procedure, requirements=[requirement])
    after = results_of(second[0])[requirement.number]
    assert second[0].number == 2 and second[0].results.count() == 1
    assert after.previous == before and after.outcome == "sin_documento"
    assert evaluate.current_result(offer, requirement) == after
    before.refresh_from_db()
    assert before.outcome == "cumple" and before.citations.filter(kind="oferta").exists()
    assert am.Result.objects.filter(offer=offer, requirement=requirement).count() == 2


def test_a_failed_offer_leaves_the_other_ones_saved_and_the_fact_failed(
        offer, operator_user, procedure, model):
    """Un pedido cortado conserva las ofertas ya evaluadas y no deja una a medias; la que
    falla deja el hecho `eval_build` fallido."""
    broken = make_offer(procedure, operator_user, "Oferta que falla", {
        "x.pdf": ["BOOM del servicio."]})

    def function(call):
        if "BOOM" in "".join(call.documents.values()):
            raise ServiceTimeoutError("generation: demora", service="generation")

    model.evaluates(function)
    requested = evaluate.request_evaluation(operator_user, procedure)
    with pytest.raises(evaluate.EvaluationFailed, match=f"oferta {broken.number}"):
        evaluate.execute(requested.request, operator_user, channel=RunChannel.SCREEN,
                         audit_channel=Channel.SCREEN, job=requested.job)
    assert am.Run.objects.filter(offer=offer).count() == 1
    assert not am.Run.objects.filter(offer=broken).exists()
    assert not am.Result.objects.filter(offer=broken).exists()
    failed = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD, outcome="failed")
    assert failed.detail["offer"] == broken.pk and "ServiceTimeoutError" in failed.detail["error"]


def test_invalid_output_is_retried_once_and_then_undetermined(offer, operator_user, procedure,
                                                             model):
    """REQ-052: una salida que no es el objeto pedido se reintenta; si sigue mal, "no
    determinado", con las anomalías en el registro."""
    model.evaluates(lambda call: "esto no es JSON"
                    if "sesenta días" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    number = number_of(procedure, "sesenta días")
    result = results_of(runs[0])[number]
    assert result.outcome == "no_determinado" and result.doubt == "duda"
    assert len([c for c in model.calls if "sesenta días" in c.requirement]) == 2
    assert any(a["type"] == "salida_invalida" for a in runs[0].anomalies)


# --- Manejador del pedido y comando -------------------------------------------------------------


def test_the_worker_handler_evaluates_the_request_of_the_job(offer, operator_user, procedure,
                                                             model):
    """El pedido de la cola evalúa lo que nombra su `target_id`; al terminar queda hecho."""
    model.evaluates(cumple_declaration)
    requested = evaluate.request_evaluation(operator_user, procedure)
    job = jobs.run_next()
    job.refresh_from_db()
    assert job.pk == requested.job.pk and job.status == m.JobStatus.DONE
    run = am.Run.objects.get(offer=offer)
    assert run.request == requested.request and run.channel == "screen"


def test_a_job_whose_request_does_not_exist_fails_with_a_reason(procedure, operator_user):
    """Ya con el manejador, un pedido que nombra un pedido inexistente falla con su causa
    (no con "sin manejador")."""
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user, target_id=987654)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert "DoesNotExist" in job.error and "sin manejador" not in job.error


def test_a_missing_handler_module_still_fails_with_a_reason(procedure, operator_user,
                                                            monkeypatch):
    """T-148: un manejador cuyo módulo no existe falla con "sin manejador"."""
    monkeypatch.setitem(jobs.HANDLERS, m.JobKind.EVALUATE_OFFERS,
                        "evaluon.assessment.services.no_existe.run")
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user, target_id=1)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED and "sin manejador" in job.error


def test_a_broken_handler_reports_its_cause_and_is_not_a_missing_handler(
        procedure, operator_user, monkeypatch, tmp_path):
    """T-148 (aviso): un manejador que existe pero cuyo import interno falla informa la causa,
    no "sin manejador"."""
    (tmp_path / "manejador_roto.py").write_text(
        "import modulo_que_no_existe_en_ningun_lado\n\ndef run(job):\n    pass\n",
        encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(jobs.HANDLERS, m.JobKind.EVALUATE_OFFERS, "manejador_roto.run")
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user, target_id=1)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert "modulo_que_no_existe_en_ningun_lado" in job.error
    assert "sin manejador" not in job.error
    sys.modules.pop("manejador_roto", None)


@pytest.fixture
def logged_in(monkeypatch, operator_user):
    from tests.conftest import TEST_PASSWORD

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    return operator_user


def run_command(*args):
    out = StringIO()
    call_command("evaluar_ofertas", *args, stdout=out)
    return out.getvalue()


def test_the_command_requests_and_runs_the_evaluation_in_the_eval_channel(
        logged_in, offer, procedure, model):
    """REQ-052: el comando pide la evaluación (con su hecho) y la corre en el canal `eval`;
    con `--requisito` evalúa solo ese."""
    model.evaluates(cumple_declaration)
    number = number_of(procedure, "declaración jurada")
    output = run_command("--usuario", logged_in.username, "--procedimiento", procedure.number,
                         "--oferta", str(offer.number), "--requisito", str(number))
    assert f"Oferta {offer.number} · requisito {number}: Cumple" in output
    run = am.Run.objects.get(offer=offer)
    assert run.channel == "eval" and run.results.count() == 1
    assert AuditEvent.objects.get(event_type=EventType.EVAL_REQUEST).channel == "eval"
    job = m.Job.objects.get(kind=m.JobKind.EVALUATE_OFFERS)
    assert job.status == m.JobStatus.DONE


def test_the_command_refuses_a_user_without_a_commission_role(
        no_commission_user, offer, procedure, monkeypatch):
    from tests.conftest import TEST_PASSWORD

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    with pytest.raises(CommandError):
        run_command("--usuario", no_commission_user.username, "--procedimiento",
                    procedure.number)
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()
    assert not m.Job.objects.filter(kind=m.JobKind.EVALUATE_OFFERS).exists()


def test_the_command_reports_a_refused_request_and_a_failed_run(logged_in, offer, procedure,
                                                                model):
    with pytest.raises(CommandError, match="No hay oferta con el número 99"):
        run_command("--usuario", logged_in.username, "--procedimiento", procedure.number,
                    "--oferta", "99")
    model.evaluates(lambda call: (_ for _ in ()).throw(
        ServiceTimeoutError("generation: demora", service="generation")))
    with pytest.raises(CommandError, match="no terminó"):
        run_command("--usuario", logged_in.username, "--procedimiento", procedure.number)
    assert m.Job.objects.get(kind=m.JobKind.EVALUATE_OFFERS).status == m.JobStatus.FAILED


# --- El caso chico completo, con un modelo que sigue la lista esperada ---------------------------


def test_the_whole_small_case_with_a_model_that_follows_the_expected_list(
        db, operator_user, fake_ai, model):
    """REQ-052 a REQ-055, REQ-059, REQ-060: tres ofertas leídas de verdad (con un escaneo y una
    página ilegible), una matriz validada y un modelo simulado que contesta lo que la lista
    esperada del caso chico (T-149) dice. El sistema llega a los resultados esperados, con
    citas literales y preguntas. Con la lista corregida por T-151 (ADR-0038, regla 3), la oferta con una
    página sin leer queda en "lectura incompleta" y la que se lee completa, en "no se encontró el documento"."""
    import re

    import yaml

    from evaluon.assessment import evaluation as ev
    from tests.assessment.fakes import CASO_CHICO

    expected = ev.load_expected(CASO_CHICO / "evaluacion-esperada.yaml")
    procedure, offers = ev.build_case(operator_user, expected)
    raw = yaml.safe_load((CASO_CHICO / "evaluacion-esperada.yaml").read_text(encoding="utf-8"))
    ids = [r["id"] for r in raw["matriz"]["requisitos"]]
    by_bidder = {o["oferente"]: {ids.index(e["requisito"]) + 1: e for e in o["requisitos"]}
                 for o in raw["ofertas"]}

    missing = []

    def shorter_quote(call, anchor):
        """La ancla; si el reconocimiento de un escaneo la cambió, su comienzo más largo que
        figura en el texto leído."""
        words = anchor.split()
        for size in range(len(words), 2, -1):
            found = call.quote(" ".join(words[:size]))
            if found is not None:
                return found
        return None

    def oracle(call):
        bidder = next(b for b in by_bidder if b in "".join(call.documents.values()))
        number = int(re.search(r"requisito (\d+)", call.requirement).group(1))
        entry = by_bidder[bidder][number]
        result = entry["resultado"]
        if result in ("cumple", "no_cumple"):
            quotes = [shorter_quote(call, c["ancla"]) for c in entry["citas"]]
            missing.extend((bidder, entry["requisito"]) for q in quotes if q is None)
            answer = says(result, *[q for q in quotes if q is not None])
            if result == "no_cumple" and call.requirement.startswith("Renglón"):
                answer["clausula"] = re.findall(r"«(.*?)»", call.requirement)[-1]
            return answer
        if entry.get("motivo") == "falta_hoja_compliance":
            return says("no_determinado", external=True)
        return says("no_consta", exigence="documento")

    model.evaluates(oracle)
    _, runs = run_all(operator_user, procedure)
    assert len(runs) == 3
    assert missing == [], "anclas de la lista que no están en el texto leído"
    wanted = {"cumple": "cumple", "no_cumple": "no_cumple",
              "no_se_encontro_documento": "sin_documento", "no_determinado": "no_determinado"}
    differences, questions = [], 0
    for run in runs:
        got = results_of(run)
        for number, entry in by_bidder[run.offer.bidder].items():
            result = got[number]
            if result.requirement.category == "tecnico" and result.outcome != "sin_documento":
                # T-167: una fila técnica espera el informe del área; lo que la lista dice que
                # el sistema concluye es su opinión (informativa).
                got_value, got_doubt = result.opinion, result.doubt
                ok = (result.outcome == "no_determinado"
                      and result.doubt == "pendiente_informe_tecnico"
                      and result.opinion == wanted[entry["resultado"]]
                      or entry["resultado"] == "no_se_encontro_documento")
                if not ok:
                    differences.append((run.offer.bidder, entry["requisito"], got_value,
                                        got_doubt))
                continue
            if result.outcome != wanted[entry["resultado"]]:
                differences.append((run.offer.bidder, entry["requisito"], result.outcome,
                                    result.doubt))
            if result.outcome in ("cumple", "no_cumple"):
                cites = offer_cites(result)
                assert cites, (run.offer.bidder, entry["requisito"])
                assert all(c.text == c.reading.canonical_text[c.char_start:c.char_end]
                           for c in cites)
            if entry["resultado"] == "no_determinado":
                assert result.doubt == {"falta_hoja_compliance": "externo",
                                        "pagina_ilegible": "lectura_incompleta",
                                        "lectura_incompleta": "lectura_incompleta"}[entry["motivo"]]
        questions += run.counts["questions"]
    assert differences == []
    assert questions == raw["resumen"]["preguntas_esperadas"]
    assert not any(r.outcome == "no_cumple" and not offer_cites(r)
                   for run in runs for r in run.results.all())


def test_a_downgraded_cumple_leaves_the_question_open_for_the_commission(
        offer, operator_user, procedure, model):
    """REQ-055 (T-153): el "cumple" que el contraste baja a "sin corroborar" queda con una
    pregunta abierta a la Comisión."""
    model.evaluates(cumple_declaration)
    model.contrasts(lambda call: {"respuesta": "no", "motivo": "no lo prueba"})
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.doubt == "sin_corroborar"
    assert am.Question.objects.filter(result=result, answers__isnull=True).count() == 1
    assert runs[0].counts["questions"] >= 1


# --- Contraste por cláusula (T-158) ------------------------------------------------------------


def row_one(procedure, model):
    """El renglón 1 evaluado como "cumple"; devuelve su fila de la matriz."""
    row = next(r for r in sheets_firm(procedure) if r.category == "tecnico" and r.items == [1])
    model.evaluates(lambda call: says("cumple", call.quote("Renglón 1: resma de papel A4"))
                    if call.requirement.startswith("Renglón 1 del pliego") else None)
    return row


def test_a_technical_cumple_is_checked_clause_by_clause(offer, operator_user, procedure, model):
    """REQ-052, T-158: un "cumple" de un renglón pasa por el contraste por cláusula: el pedido
    lleva el requisito y la oferta, y queda registrado como paso de contraste."""
    row = row_one(procedure, model)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert len(model.clause_calls) == 1
    assert "Renglón 1 del pliego" in model.clause_calls[0].user
    assert "Renglón 1: resma de papel A4" in model.clause_calls[0].user
    step = am.Step.objects.filter(run=runs[0], purpose="contraste", requirement=row).first()
    assert step.parsed["clausulas"][0]["estado"] == "coincide"
    assert results_of(runs[0])[row.number].opinion == "cumple"


def test_a_contradicted_clause_turns_the_technical_cumple_into_no_cumple(
        offer, operator_user, procedure, model):
    """REQ-052, REQ-053, T-164: la oferta trae otra presentación que la que el pliego pide, y el
    modelo cita el tramo de la oferta que lo muestra: "no cumple", con la cláusula y esa cita
    ubicada por el sistema."""
    row = row_one(procedure, model)
    clause = row.quotes.order_by("order").first().text
    model.clauses(lambda call: {"clausulas": [
        {"clausula": clause, "estado": "contradice", "motivo": "Ofrece otra presentación.",
         "cita": "resma de papel A4, 100 unidades"}], "pregunta": ""})
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    cites = offer_cites(result)
    assert result.opinion == "no_cumple"
    assert cites[0].text == "resma de papel A4, 100 unidades"
    assert cites[0].text == cites[0].reading.canonical_text[cites[0].char_start:cites[0].char_end]
    assert "Ofrece otra presentación" in result.explanation


def test_a_contradiction_without_a_quote_that_the_system_can_locate_is_undetermined(
        offer, operator_user, procedure, model):
    """REQ-052, REQ-053, T-164 (F-1): sin cita, o con una cita que no está en el texto de la
    oferta, "contradice" no hace un "no cumple": no determinado con pregunta."""
    row = row_one(procedure, model)
    clause = row.quotes.order_by("order").first().text
    for quote in ("", "una frase que la oferta no dice"):
        model.clauses(lambda call: {"clausulas": [
            {"clausula": clause, "estado": "contradice", "motivo": "Otra presentación.",
             "cita": quote}], "pregunta": ""})
        _, runs = run_all(operator_user, procedure, offers=[offer])
        result = results_of(runs[0])[row.number]
        assert result.opinion == "no_determinado", quote


def test_a_contradiction_that_blames_the_reading_is_undetermined(
        offer, operator_user, procedure, model):
    """REQ-052, T-164 (F-1): aunque traiga una cita ubicada, un motivo de calidad de lectura
    (escaneo, transcripción) no es una contradicción: no determinado con pregunta."""
    row = row_one(procedure, model)
    clause = row.quotes.order_by("order").first().text
    model.clauses(lambda call: {"clausulas": [
        {"clausula": clause, "estado": "contradice",
         "motivo": "Errores de transcripción del escaneo.",
         "cita": "resma de papel A4, 100 unidades"}], "pregunta": ""})
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    assert result.opinion == "no_determinado" and result.outcome == "no_determinado"


def test_the_clause_check_sees_the_document_that_backs_the_citation(
        offer, operator_user, procedure, model):
    """REQ-052, T-164: el pedido trae el documento de la oferta donde está la cita (no solo la
    cita), para una cláusula que está en el documento y no en el tramo citado."""
    row_one(procedure, model)
    run_all(operator_user, procedure, offers=[offer])
    user = model.clause_calls[0].user
    assert "Documento de la oferta donde está el texto citado" in user
    assert "validez por sesenta días" in user          # otra página del mismo documento
    assert "Constancia de inscripción" not in user     # un documento que no respalda la cita


def test_the_clauses_go_in_bounded_requests(offer, operator_user, procedure, model, settings):
    """REQ-052, T-164 (F-2): las cláusulas van en pedidos con tope por cantidad; el resultado
    junta las filas de todos."""
    row = row_one(procedure, model)
    settings.ASSESSMENT_CLAUSES_PER_REQUEST = 1
    quotes = row.quotes.count()
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert len(model.clause_calls) == quotes
    assert results_of(runs[0])[row.number].opinion == "cumple"


def test_a_cut_output_is_retried_in_parts_before_giving_up(
        offer, operator_user, procedure, model, settings):
    """REQ-052, T-164 (F-2): una salida cortada se reintenta en dos partes; con las partes
    bien, el "cumple" sigue (no baja a "sin corroborar")."""
    row = row_one(procedure, model)
    assert row.quotes.count() >= 2
    settings.ASSESSMENT_CLAUSES_PER_REQUEST = 50
    settings.ASSESSMENT_CLAUSES_REQUEST_CHARS = 10 ** 6
    model.clauses(lambda call: '{"clausulas": [{"clausula": "5.1 Alim' if call.number == 1 else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert len(model.clause_calls) == 3
    assert results_of(runs[0])[row.number].opinion == "cumple"
    steps = list(am.Step.objects.filter(run=runs[0], purpose="contraste", requirement=row)
                 .order_by("pk"))
    assert steps[1].retry_of is not None and steps[0].anomalies


def test_a_clause_missing_from_the_offer_makes_the_technical_cumple_undetermined(
        offer, operator_user, procedure, model):
    """REQ-052, REQ-055, T-158: una cláusula sin dato en la oferta: "no determinado" con
    pregunta."""
    row = row_one(procedure, model)
    model.clauses(lambda call: {"clausulas": [
        {"clausula": "x", "estado": "no_aparece", "motivo": ""}],
        "pregunta": "¿Qué presentación ofrece?"})
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    assert result.opinion == "no_determinado" and result.doubt == "pendiente_informe_tecnico"
    assert not result.questions.exists()  # el informe del área, no una pregunta (T-167)


def test_a_non_technical_cumple_skips_the_clause_check(offer, operator_user, procedure, model):
    """REQ-052, T-158: el contraste por cláusula es solo de las filas técnicas."""
    model.evaluates(cumple_declaration)
    run_all(operator_user, procedure)
    assert model.clause_calls == []


def test_an_invalid_clause_output_leaves_the_cumple_uncorroborated(
        offer, operator_user, procedure, model):
    """REQ-052, T-158, T-164: las salidas sin la forma pedida (el pedido entero, la primera
    parte y su repetición): "no determinado" sin corroborar."""
    row = row_one(procedure, model)
    model.clauses(lambda call: "no es JSON")
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[row.number]
    assert result.opinion == "no_determinado" and result.doubt == "pendiente_informe_tecnico"
    assert len(model.clause_calls) == 3
