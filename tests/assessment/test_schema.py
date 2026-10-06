"""El esquema de la evaluación asistida y sus triggers de inmutabilidad (REQ-052, REQ-053,
REQ-054, REQ-056, REQ-057; plan 004, "Modelo de datos"; ADR-0039 y ADR-0040; T-148)."""

import pytest
from django.db import IntegrityError, connection, transaction

from evaluon.assessment import models as am
from evaluon.audit.models import EventType
from evaluon.tenders import jobs
from evaluon.tenders import models as m

pytestmark = pytest.mark.django_db

TABLES = ("assessment_request", "assessment_run", "assessment_result",
          "assessment_citation", "assessment_step", "assessment_decision",
          "assessment_question", "assessment_answer")


def _new_run(rows, number=2):
    return am.Run.objects.create(
        request=rows.request, offer=rows.run.offer, matrix_version=rows.version,
        number=number, channel=am.Channel.EVAL, documents=[], norms={}, models_used={},
        parameters={}, prompt_versions={})


@pytest.mark.parametrize("table", TABLES)
def test_every_table_is_insert_only(rows, table):
    """REQ-056 (P3, P6): ninguna de las ocho tablas admite UPDATE ni DELETE, ni por SQL."""
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET id = id")
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table}")


def test_a_result_cannot_be_overwritten_from_the_model(rows):
    """REQ-052: un resultado propuesto no se pisa: se inserta otro."""
    rows.result.outcome = am.Outcome.NO_CUMPLE
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        rows.result.save()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        am.Result.objects.filter(pk=rows.result.pk).update(explanation="otra")
    assert am.Result.objects.get(pk=rows.result.pk).outcome == am.Outcome.CUMPLE


def test_there_is_one_result_per_run_and_requirement(rows):
    """REQ-052: único por evaluación y requisito."""
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Result.objects.create(run=rows.run, offer=rows.run.offer,
                                 requirement=rows.requirement, outcome=am.Outcome.CUMPLE)


def test_a_new_run_can_hold_a_new_result_for_the_same_pair(rows):
    """REQ-060: evaluar de nuevo un par es un resultado nuevo con `previous`."""
    run = _new_run(rows)
    new = am.Result.objects.create(
        run=run, offer=run.offer, requirement=rows.requirement,
        outcome=am.Outcome.SIN_DOCUMENTO, previous=rows.result)
    assert new.previous == rows.result
    assert am.Run.objects.filter(offer=run.offer).count() == 2


def test_a_run_number_is_unique_per_offer(rows):
    with pytest.raises(IntegrityError), transaction.atomic():
        _new_run(rows, number=1)


def test_the_run_keeps_the_matrix_version_it_was_made_with(rows):
    """REQ-057: cada evaluación guarda la versión de la matriz."""
    assert am.Run.objects.get(pk=rows.run.pk).matrix_version == rows.version


@pytest.mark.parametrize("outcome,doubt", [
    (am.Outcome.NO_DETERMINADO, ""),
    (am.Outcome.CUMPLE, "duda"),
    (am.Outcome.NO_DETERMINADO, "inventado"),
    ("aprobado", ""),
])
def test_an_undetermined_result_always_says_why_and_only_it(rows, outcome, doubt):
    """REQ-052 (P3): «no determinado» lleva su motivo; los otros tres resultados, ninguno; el
    motivo es uno de los siete y el resultado, uno de los cuatro."""
    run = _new_run(rows)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Result.objects.create(run=run, offer=run.offer, requirement=rows.requirement,
                                 outcome=outcome, doubt=doubt)


def test_the_four_outcomes_and_seven_doubts_are_the_plans():
    assert set(am.Outcome.values) == {"cumple", "no_cumple", "sin_documento",
                                      "no_determinado"}
    assert set(am.Doubt.values) == {"duda", "sin_corroborar", "contradiccion",
                                    "lectura_incompleta", "externo", "sin_cita",
                                    "sin_dato"}


# --- Una restricción por clase de cita (REQ-053) ----------------------------------------------


def _citation(rows, order, **fields):
    return am.Citation.objects.create(result=rows.result, order=order, **fields)


def test_an_offer_citation_needs_document_reading_page_range_and_text(rows):
    """REQ-053: la cita de la oferta lleva documento, lectura, página, posiciones y texto."""
    base = dict(kind=am.CitationKind.OFERTA, document=rows.document, reading=rows.reading,
                page=1, char_start=0, char_end=5, text="Decla")
    _citation(rows, 2, **base)
    for index, missing in enumerate(("document", "reading", "page", "char_start", "char_end")):
        with pytest.raises(IntegrityError), transaction.atomic():
            _citation(rows, 3 + index, **{**base, missing: None})
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 20, **{**base, "text": ""})
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 21, **{**base, "char_start": 9, "char_end": 5})
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 22, **{**base, "requirement_quote": rows.quote})


def test_a_requirement_citation_needs_the_quote_and_its_text(rows):
    """REQ-053: la cita del pliego lleva la cita del requisito y el texto vigente, y no los
    campos de la oferta; el original es opcional."""
    _citation(rows, 2, kind=am.CitationKind.PLIEGO, requirement_quote=rows.quote,
              text="texto vigente", original_text="texto original")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 3, kind=am.CitationKind.PLIEGO, text="sin cita del requisito")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 4, kind=am.CitationKind.PLIEGO, requirement_quote=rows.quote)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 5, kind=am.CitationKind.PLIEGO, requirement_quote=rows.quote,
                  text="x", document=rows.document)


def test_a_norm_citation_needs_the_unit_label_and_text(rows, make_norm, make_document,
                                                       make_reading):
    """REQ-053: la cita de norma lleva la unidad, su rótulo (norma y artículo) y el texto."""
    reading = make_reading(make_document(make_norm()), [("art-1", "Artículo 1. Texto.")])
    unit = reading.units_by_key["art-1"]
    _citation(rows, 2, kind=am.CitationKind.NORMA, norm_unit=unit, label="Norma, art. 1",
              text="Artículo 1. Texto.")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 3, kind=am.CitationKind.NORMA, label="Norma, art. 1", text="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 4, kind=am.CitationKind.NORMA, norm_unit=unit, text="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 5, kind=am.CitationKind.NORMA, norm_unit=unit, label="a")


def test_an_answer_citation_needs_the_answer(rows):
    """REQ-053, REQ-056: la cita de una respuesta de la Comisión lleva la respuesta."""
    _citation(rows, 2, kind=am.CitationKind.RESPUESTA, answer=rows.answer)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 3, kind=am.CitationKind.RESPUESTA)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 4, kind=am.CitationKind.RESPUESTA, answer=rows.answer,
                  requirement_quote=rows.quote)


def test_a_citation_order_is_unique_in_its_result(rows):
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 1, kind=am.CitationKind.RESPUESTA, answer=rows.answer)


def test_an_unknown_citation_kind_is_refused(rows):
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 2, kind="otra", answer=rows.answer)


# --- Decisiones (REQ-056) ------------------------------------------------------------------


@pytest.mark.parametrize("action", [am.Action.CORREGIR, am.Action.RECHAZAR,
                                    am.Action.PEDIR_SUBSANACION])
def test_a_decision_that_changes_or_asks_needs_a_note(rows, evaluator_user, action):
    """REQ-056: `corregir`, `rechazar` y `pedir_subsanacion` exigen la nota."""
    after = am.Outcome.NO_CUMPLE if action == am.Action.CORREGIR else ""
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=action, outcome_after=after,
                                   user=evaluator_user, event=rows.event)
    am.Decision.objects.create(result=rows.result, action=action, outcome_after=after,
                               note="Motivo.", user=evaluator_user, event=rows.event)


def test_a_correction_names_the_new_outcome_and_only_it(rows, evaluator_user):
    """REQ-056: `corregir` lleva uno de los cuatro resultados; las demás acciones no."""
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=am.Action.CORREGIR,
                                   note="x", user=evaluator_user, event=rows.event)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=am.Action.CORREGIR,
                                   outcome_after="aprobado", note="x", user=evaluator_user,
                                   event=rows.event)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=am.Action.RECHAZAR,
                                   outcome_after=am.Outcome.CUMPLE, note="x",
                                   user=evaluator_user, event=rows.event)


def test_a_remedy_names_the_added_document(rows, evaluator_user):
    """REQ-060: `subsanar` lleva el documento agregado; las demás acciones no."""
    am.Decision.objects.create(result=rows.result, action=am.Action.SUBSANAR,
                               document=rows.document, user=evaluator_user, event=rows.event)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=am.Action.SUBSANAR,
                                   user=evaluator_user, event=rows.event)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Decision.objects.create(result=rows.result, action=am.Action.CONFIRMAR,
                                   document=rows.document, user=evaluator_user,
                                   event=rows.event)


# --- Preguntas y respuestas (ADR-0040) --------------------------------------------------------


def test_an_answer_has_a_valid_scope_and_text(rows, evaluator_user):
    """REQ-055, REQ-056: el alcance es par, requisito o procedimiento (por omisión,
    requisito) y la respuesta no está vacía."""
    assert rows.answer.scope == am.AnswerScope.REQUISITO
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Answer.objects.create(question=rows.question, text="x", scope="todo",
                                 answered_by=evaluator_user, event=rows.event)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Answer.objects.create(question=rows.question, text="", answered_by=evaluator_user,
                                 event=rows.event)


def test_a_question_has_text(rows, matrix, offer):
    """REQ-055: una pregunta no puede estar vacía."""
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Question.objects.create(procedure=matrix.procedure, requirement=rows.requirement,
                                   offer=offer, result=rows.result, text="")


# --- Cola y auditoría ------------------------------------------------------------------------


def test_the_evaluate_offers_job_kind_is_valid(procedure, operator_user):
    """REQ-052: el pedido de evaluación entra a la cola compartida (ADR-0039)."""
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user)
    assert m.Job.objects.get(pk=job.pk).kind == "evaluate_offers"


def test_a_job_can_name_its_request_after_the_request_is_inserted(rows, procedure,
                                                                   operator_user):
    """ADR-0039: las tablas de la evaluación no se actualizan; el pedido de la cola sí, y
    lleva el id del pedido de evaluación en `target_id`."""
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=rows.version, offers=[], cause=am.Cause.MANUAL,
        requested_by=operator_user, job=job)
    job.target_id = request.pk
    job.save(update_fields=["target_id"])
    assert m.Job.objects.get(pk=job.pk).target_id == request.pk


def test_an_evaluate_offers_job_without_handler_fails_with_a_reason(procedure, operator_user,
                                                                    monkeypatch):
    """REQ-052: un pedido cuyo manejador no existe falla con un motivo y no tira al `worker`.
    Desde T-150 el manejador existe: se prueba con un módulo que falta."""
    monkeypatch.setitem(jobs.HANDLERS, m.JobKind.EVALUATE_OFFERS,
                        "evaluon.assessment.services.no_existe.run_evaluate_offers")
    job = jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                       requested_by=operator_user, target_id=1)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert "sin manejador" in job.error
    assert m.JobKind.EVALUATE_OFFERS in job.error


def test_the_handler_points_to_the_evaluation_service():
    """REQ-052: el manejador es el de T-150."""
    assert jobs.HANDLERS[m.JobKind.EVALUATE_OFFERS] == (
        "evaluon.assessment.services.evaluate.run_evaluate_offers")


def test_the_four_audit_event_types_of_the_feature_exist():
    """P6: los cuatro tipos de hecho de la 004, de hasta 20 caracteres."""
    for name in ("eval_request", "eval_build", "eval_decision", "eval_answer"):
        assert name in EventType.values
        assert len(name) <= 20


def test_the_audit_table_accepts_the_new_event_types(operator_user):
    """P6: la restricción de la base admite los cuatro tipos nuevos."""
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, Outcome

    for event_type in (EventType.EVAL_REQUEST, EventType.EVAL_BUILD,
                       EventType.EVAL_DECISION, EventType.EVAL_ANSWER):
        event = audit.record(event_type, outcome=Outcome.OK, channel=Channel.EVAL,
                             user=operator_user)
        assert event.event_type == event_type
