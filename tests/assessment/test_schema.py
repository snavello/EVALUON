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


def test_the_four_outcomes_and_eleven_doubts_are_the_plans():
    assert set(am.Outcome.values) == {"cumple", "no_cumple", "sin_documento",
                                      "no_determinado"}
    assert set(am.Doubt.values) == {"duda", "sin_corroborar", "contradiccion",
                                    "lectura_incompleta", "externo", "sin_cita",
                                    "sin_dato", "pendiente_informe_tecnico",
                                    "no_se_pudo_leer", "en_portal", "falta_coincidencia"}


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


# --- Enmienda de decisiones literales (T-165; ADR-0043; REQ-061 a REQ-064) --------------------

NEW_DOUBTS = ("pendiente_informe_tecnico", "no_se_pudo_leer", "en_portal",
              "falta_coincidencia")


@pytest.fixture
def portal_item(procedure, operator_user):
    from evaluon.portal import models as pm

    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=operator_user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1,
                                                origin="importacion")
    return pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o",
                                        payload={}, content_sha256="b" * 64, page=page)


@pytest.mark.decision_literal
@pytest.mark.parametrize("doubt", NEW_DOUBTS)
def test_each_new_doubt_is_valid_only_in_an_undetermined_result(rows, doubt):
    """REQ-061, REQ-062, REQ-063, REQ-064: los motivos nuevos valen solo en un «no
    determinado»; en cualquier otro resultado, la base los rechaza."""
    run = _new_run(rows)
    result = am.Result.objects.create(
        run=run, offer=run.offer, requirement=rows.requirement,
        outcome=am.Outcome.NO_DETERMINADO, doubt=doubt)
    assert am.Result.objects.get(pk=result.pk).doubt == doubt
    run = _new_run(rows, number=3)
    for outcome in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE, am.Outcome.SIN_DOCUMENTO):
        with pytest.raises(IntegrityError), transaction.atomic():
            am.Result.objects.create(run=run, offer=run.offer,
                                     requirement=rows.requirement, outcome=outcome,
                                     doubt=doubt)


def test_the_external_doubt_reads_as_missing_compliance_sheet():
    """REQ-063: el rótulo de `externo` pasa a «Falta la hoja de compliance»."""
    assert am.Doubt.EXTERNO.label == "Falta la hoja de compliance"
    assert am.Doubt.EXTERNO.value == "externo"


def test_the_four_outcomes_and_decision_outcomes_do_not_change():
    """REQ-052: los cuatro resultados y los de `Decision.outcome_after` siguen iguales."""
    assert [c[0] for c in am.Decision._meta.get_field("outcome_after").choices] == [
        "cumple", "no_cumple", "sin_documento", "no_determinado"]


@pytest.mark.decision_literal
def test_a_result_opinion_and_facts_are_optional_and_validated(rows):
    """REQ-061: `opinion` es cumple, no_cumple, no_determinado o vacío; `facts` es `{}`."""
    assert rows.result.opinion == ""
    assert am.Result.objects.get(pk=rows.result.pk).facts == {}
    run = _new_run(rows)
    result = am.Result.objects.create(
        run=run, offer=run.offer, requirement=rows.requirement,
        outcome=am.Outcome.NO_DETERMINADO, doubt="pendiente_informe_tecnico",
        opinion=am.Opinion.NO_CUMPLE,
        facts={"regla": "tecnica_categoria", "version_reglas": "reglas-v2"})
    assert am.Result.objects.get(pk=result.pk).facts["regla"] == "tecnica_categoria"
    run = _new_run(rows, number=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        am.Result.objects.create(run=run, offer=run.offer, requirement=rows.requirement,
                                 outcome=am.Outcome.CUMPLE, opinion="aprobado")


def _portal_citation(rows, order, portal_item, **fields):
    base = dict(kind=am.CitationKind.PORTAL, portal_item=portal_item,
                portal_kind=am.PortalKind.COTIZACION, text="Precio: 1000",
                label="Portal: cuadro comparativo")
    return am.Citation.objects.create(result=rows.result, order=order, **{**base, **fields})


@pytest.mark.decision_literal
def test_a_portal_citation_needs_item_kind_and_text(rows, portal_item):
    """REQ-062, REQ-053: la cita del Portal lleva el ítem, la clase de dato y el texto, y
    deja vacíos los campos de las demás clases."""
    _portal_citation(rows, 2, portal_item)
    for index, kind in enumerate(am.PortalKind.values):
        _portal_citation(rows, 10 + index, portal_item, portal_kind=kind)
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 3, None)
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 4, portal_item, portal_kind="")
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 5, portal_item, portal_kind="otro")
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 6, portal_item, text="")
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 7, portal_item, document=rows.document)
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 8, portal_item, requirement_quote=rows.quote)
    with pytest.raises(IntegrityError), transaction.atomic():
        _portal_citation(rows, 9, portal_item, answer=rows.answer)


@pytest.mark.decision_literal
def test_the_other_citation_kinds_refuse_the_portal_fields(rows, portal_item):
    """REQ-053: las citas de la oferta, del pliego y de una respuesta no llevan datos del
    Portal."""
    offer_fields = dict(kind=am.CitationKind.OFERTA, document=rows.document,
                        reading=rows.reading, page=1, char_start=0, char_end=5,
                        text="Decla")
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 2, portal_item=portal_item, **offer_fields)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 3, portal_kind="total", **offer_fields)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 4, kind=am.CitationKind.PLIEGO, requirement_quote=rows.quote,
                  text="x", portal_item=portal_item)
    with pytest.raises(IntegrityError), transaction.atomic():
        _citation(rows, 5, kind=am.CitationKind.RESPUESTA, answer=rows.answer,
                  portal_kind="cuit")


def _technical_ok(rows, offer, evaluator_user, **fields):
    base = dict(offer=offer, action=am.TechnicalAction.DAR_OK, user=evaluator_user,
                event=rows.event, items=[1, 2], verdicts={"1": "apto", "2": "no_apto"})
    return am.TechnicalOk.objects.create(**{**base, **fields})


@pytest.mark.decision_literal
def test_a_technical_ok_holds_items_and_verdicts(rows, offer, evaluator_user):
    """REQ-061: el ok guarda la oferta, los renglones (o nulo: todo el informe) y el dictamen
    de cada renglón según el informe aprobado."""
    ok = _technical_ok(rows, offer, evaluator_user)
    whole = _technical_ok(rows, offer, evaluator_user, items=None, verdicts={})
    assert am.TechnicalOk.objects.get(pk=ok.pk).verdicts == {"1": "apto", "2": "no_apto"}
    assert am.TechnicalOk.objects.get(pk=whole.pk).items is None


@pytest.mark.decision_literal
def test_withdrawing_a_technical_ok_needs_a_note(rows, offer, evaluator_user):
    """REQ-061 (P3): retirar el ok exige nota; darlo no."""
    with pytest.raises(IntegrityError), transaction.atomic():
        _technical_ok(rows, offer, evaluator_user, action=am.TechnicalAction.RETIRAR_OK)
    _technical_ok(rows, offer, evaluator_user, action=am.TechnicalAction.RETIRAR_OK,
                  note="El informe se reabrió.")
    with pytest.raises(IntegrityError), transaction.atomic():
        _technical_ok(rows, offer, evaluator_user, action="borrar", note="x")


@pytest.mark.decision_literal
def test_the_technical_ok_table_is_insert_only(rows, offer, evaluator_user):
    """REQ-061 (P6): `assessment_technical_ok` rechaza UPDATE y DELETE, también por SQL y
    desde el modelo."""
    ok = _technical_ok(rows, offer, evaluator_user)
    for sql in ("UPDATE assessment_technical_ok SET note = 'x'",
                "DELETE FROM assessment_technical_ok"):
        with pytest.raises(Exception, match="solo admite agregar filas"):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(sql)
    ok.note = "otra"
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        ok.save()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        ok.delete()


def test_the_rules_version_is_set():
    """REQ-063: la versión de las reglas existe para copiarla al registro de la evaluación."""
    from django.conf import settings

    assert settings.ASSESSMENT_RULES_VERSION == "reglas-v2"


def test_the_decision_literal_marker_is_registered(pytestconfig):
    """El marcador está registrado (con `--strict-markers`)."""
    assert any(line.startswith("decision_literal") for line in
               pytestconfig.getini("markers"))


@pytest.mark.django_db(transaction=True)
def test_the_migration_applies_over_existing_results_and_is_reversible(rows):
    """REQ-052: las migraciones 0003 y 0004 se revierten y se vuelven a aplicar con
    resultados y citas guardados, que siguen siendo válidos (sin opinión ni hechos)."""
    from django.db.migrations.executor import MigrationExecutor

    def migrate(target):
        MigrationExecutor(connection).migrate([("assessment", target)])

    result_id, citation_id = rows.result.pk, rows.citation.pk
    migrate("0002_triggers")
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('assessment_technical_ok')")
        assert cursor.fetchone()[0] is None
        cursor.execute("SELECT count(*) FROM assessment_result WHERE id = %s", [result_id])
        assert cursor.fetchone()[0] == 1
    migrate("0004_triggers")
    result = am.Result.objects.get(pk=result_id)
    assert (result.outcome, result.doubt, result.opinion, result.facts) == (
        am.Outcome.CUMPLE, "", "", {})
    citation = am.Citation.objects.get(pk=citation_id)
    assert (citation.kind, citation.portal_item_id, citation.portal_kind) == (
        am.CitationKind.OFERTA, None, "")
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_trigger "
                       "WHERE tgname = 'assessment_technical_ok_append_only'")
        assert cursor.fetchone()[0] == 1
