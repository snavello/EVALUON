"""Pedir la propuesta de la matriz: proceso único, rechazos, registro y manejador (REQ-024, REQ-030;
plan 003, "Propuesta de la matriz", "Roles" y "Registro de auditoría"; T-073).

Pliegos sintéticos y el doble del modelo con guion (`tests/tenders/scripted.py`); sin datos
de personas (P4). La propuesta corre con `jobs.run_next()` sobre la base de pruebas, como la
haría el `worker`.
"""

from datetime import date

import pytest
from django.core.management import call_command

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.services import matrix
from tests.tenders.pdfs import para, synthetic_tender_pdf, tender_pdf
from tests.tenders.scripted import (
    ENTREGA,
    GARANTIA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    run_jobs,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db




@pytest.fixture
def read_case(operator_user, script):
    """Un procedimiento con el pliego de tres renglones ya leído y un modelo que acierta."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(ENTREGA, item(technical=["todos"]))
    return procedure


def request_events(outcome=None):
    events = AuditEvent.objects.filter(event_type=EventType.MATRIX_REQUEST)
    if outcome is not None:
        events = events.filter(outcome=outcome)
    return events.order_by("id")


def proposal_events():
    return AuditEvent.objects.filter(event_type=EventType.MATRIX_PROPOSAL).order_by("id")


def nothing_was_queued():
    return not m.Job.objects.filter(kind="propose_matrix").exists() and \
        not m.MatrixRun.objects.exists()


def signature(version):
    """Lo que la comisión ve de una versión: clase, renglones y citas de cada requisito."""
    return [
        (r.category, r.items, [(q.text, q.scope, q.quote_flag)
                               for q in r.quotes.order_by("order")])
        for r in m.Requirement.objects.filter(version=version).order_by("number")
    ]


# --- Proceso único (REQ-030) -----------------------------------------------------------------


def test_the_request_takes_no_level():
    """REQ-030: el pedido de una matriz no recibe nivel: hay un solo proceso."""
    import inspect

    assert "level" not in inspect.signature(matrix.request_matrix).parameters


def test_the_proposal_records_the_single_process_and_no_level(operator_user, read_case):
    """REQ-030: la propuesta, el borrador y los hechos registran el proceso `completo` y
    ningún nivel."""
    requested, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    assert requested.run.process == "completo" and requested.run.level == ""
    assert requested.run.version.process == "completo" and requested.run.version.level == ""
    assert request_events().get().detail["process"] == "completo"
    assert "level" not in request_events().get().detail
    assert proposal_events().get().detail["process"] == "completo"
    assert "level" not in proposal_events().get().detail


def test_the_proposal_runs_the_passes_of_the_single_process(operator_user, script):
    """REQ-030: la propuesta corre las pasadas del proceso único (las de "alta" de T-093,
    sin marcadores ni segunda extracción) y lo registra en los parámetros y en los pedidos
    al modelo; no queda la anomalía de "nivel sin pasadas propias"."""
    script.when(PAGO, item([(PAGO, "economico")]))
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert requested.run.parameters["process"] == "completo"
    assert requested.run.parameters["passes"] == [
        "reglas", "extraccion", "completitud", "unificacion", "filtro", "filas_tecnicas",
        "consecuencias"]
    steps = list(dict.fromkeys(
        m.RunStep.objects.filter(run=requested.run).order_by("id")
        .values_list("pass_name", flat=True)))
    assert steps == ["extraccion", "completitud", "unificacion", "filtro", "filtro_2", "consecuencias"]
    assert "nivel_sin_pasadas_propias" not in [a["type"] for a in requested.run.anomalies]


def test_the_proposal_records_the_version_of_every_instruction(operator_user, read_case,
                                                                settings):
    """REQ-030: la propuesta registra la versión de cada instrucción que usó."""
    requested, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    versions = settings.MATRIX_PROMPT_VERSIONS
    assert requested.run.prompt_versions == {
        name: versions[name]
        for name in ("extraccion", "completitud", "filtro", "consecuencias")}


def test_the_settings_have_no_levels_and_name_the_process(settings):
    """REQ-030: la configuración ya no tiene niveles; tiene el proceso único."""
    for name in ("MATRIX_LEVELS", "MATRIX_LEVELS_OFFERED", "MATRIX_DEFAULT_LEVEL"):
        assert not hasattr(settings, name), name
    assert settings.MATRIX_PROCESS == "completo"


def test_no_live_reference_to_the_levels_or_the_second_extraction():
    """REQ-030: el código no conserva referencias vivas a los niveles ni a la segunda
    extracción (los modelos guardan `level` solo como dato histórico)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "evaluon"
    forbidden = ("MATRIX_LEVELS", "MATRIX_DEFAULT_LEVEL", "second_extraction",
                 "PassName.EXTRACCION_2", "--niveles", "_check_level")
    found = []
    for path in root.rglob("*"):
        if path.suffix not in (".py", ".html") or "migrations" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        found += [(path.name, word) for word in forbidden if word in text]

    assert found == []


# --- Pedido: lo que se registra (REQ-024, REQ-030) ----------------------------------------------


def test_request_queues_the_job_and_saves_the_run_and_the_event(operator_user, read_case):
    """REQ-030: el pedido encola `propose_matrix`, deja la propuesta con su proceso, su canal
    y los documentos con su lectura, y el hecho `matrix_request`."""
    document = read_case.documents.get()
    reading = document.readings.get()

    requested = matrix.request_matrix(operator_user, read_case)

    job = requested.job
    assert (job.kind, job.status, job.requested_by) == ("propose_matrix", "queued",
                                                         operator_user)
    assert job.procedure == read_case and job.document is None
    run = requested.run
    assert (run.job, run.process, run.channel, run.version) == (job, "completo", "screen", None)
    assert run.authorization_date == read_case.authorization_date
    expected = [{
        "document": document.pk, "title": "Pliego sintético", "kind": "pliego",
        "file_sha256": document.file_sha256, "reading": reading.pk,
        "sequence": 1, "canonical_sha256": reading.canonical_sha256,
    }]
    assert run.documents == expected
    event = request_events().get()
    assert event == requested.event
    assert (event.outcome, event.channel, event.user) == (Outcome.OK, Channel.SCREEN,
                                                          operator_user)
    assert event.detail == {
        "procedure": read_case.pk, "process": "completo",
        "run": run.pk, "job": job.pk, "documents": expected,
    }


def test_proposal_records_models_parameters_prompts_regime_and_corpus_version(
        operator_user, read_write_user, read_case, two_regimes, script, fake_ai):
    """REQ-030 (P6, P8): la propuesta registra los modelos con su huella, los parámetros, las
    versiones de instrucciones, el régimen a la fecha de autorización y la versión de la
    normativa."""
    version_event = audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND,
        user=read_write_user, creates_corpus_version=True,
    )
    read_case.authorization_date = date(2022, 12, 15)
    read_case.save()

    requested, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    run = requested.run
    assert run.authorization_date == date(2022, 12, 15)
    assert run.regime == [{"norm": two_regimes.old.pk, "name": "Disposición AFIP 297/03"}]
    assert run.corpus_version == version_event.corpus_version
    assert run.prompt_versions == {"extraccion": "matriz-extraccion-v2",
                                    "completitud": "matriz-completitud-v2",
                                    "filtro": "matriz-filtro-v2",
                                    "consecuencias": "matriz-consecuencias-v1"}
    assert set(run.models) == {"generation_batch", "embeddings", "reranker"}
    for model in run.models.values():
        assert len(model["sha256"]) == 64 and model["model"] and model["file"]
    assert run.models["generation_batch"]["engine_build"] == "b11347"
    parameters = run.parameters
    assert parameters["temperature"] == 0 and parameters["seed"] == 42
    assert parameters["thinking"] is False
    assert parameters["max_output_tokens"] == 4096
    assert parameters["batch_input_tokens"] == 1500
    assert parameters["generation_batch_timeout_seconds"] == 180
    assert parameters["rules_version"] == "tramos-2"
    event = proposal_events().get()
    assert event.outcome == Outcome.OK and event.channel == Channel.COMMAND
    assert event.user == operator_user
    assert event.corpus_version == version_event.corpus_version
    detail = event.detail
    for key in ("regime", "models", "parameters", "prompt_versions", "counts", "timings",
                "corpus_version", "authorization_date", "process", "documents"):
        assert key in detail, key
    assert detail["regime"] == run.regime
    assert detail["version"] == run.version.pk and detail["version_number"] == 1
    assert detail["run"] == run.pk and detail["job"] == requested.job.pk
    assert detail["counts"] == run.counts and detail["timings"] == run.timings


def test_regime_follows_the_authorization_date(operator_user, read_case, two_regimes):
    """REQ-030 (P8): el régimen de la propuesta es el de la fecha de autorización: 247/2022
    de 2023 en adelante."""
    read_case.authorization_date = date(2024, 5, 20)
    read_case.save()

    requested, _ = propose(operator_user, read_case)

    assert requested.run.regime == [
        {"norm": two_regimes.new.pk, "name": "Disposición AFIP 247/2022"}]


def test_timings_and_counts_are_saved(operator_user, read_case):
    """REQ-024: la propuesta guarda los tiempos por pasada y total, y las cuentas."""
    requested, _ = propose(operator_user, read_case)

    run = requested.run
    assert set(run.timings) >= {"reglas", "extraccion", "completitud", "filas_tecnicas",
                                "guardado", "total"}
    assert run.counts["requirements_by_class"] == {"economico": 2, "tecnico": 3}
    assert run.counts["requirements"] == 5
    assert run.counts["segments_by_type"]["clausula"] >= 4
    assert run.counts["model_requests_by_pass"] == {"extraccion": 1, "completitud": 1,
                                                    "filtro": 1, "filtro_2": 1,
                                                    "consecuencias": 1}
    assert run.counts["model_requests"] == 5


# --- Rechazos del pedido (REQ-024) ----------------------------------------------------------------


def test_request_without_documents_is_refused(operator_user):
    """REQ-024: sin ningún documento base no hay nada que proponer."""
    procedure = make_procedure(operator_user)

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, procedure)

    assert error.value.reason == "no_documents"
    assert nothing_was_queued()
    assert request_events(Outcome.REJECTED).get().detail["reason"] == "no_documents"


def test_request_while_a_base_document_is_being_read_is_refused(operator_user):
    """REQ-024: si algún documento base está en lectura o en espera de ella, se rechaza."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf(), title="Pliego")
    from evaluon.tenders.services import documents

    documents.load_document(operator_user, procedure,
                            data=tender_pdf([[para("ANEXO I - SINTÉTICO")]]),
                            file_name="anexo.pdf", kind="anexo", title="Anexo sintético")

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, procedure)

    assert error.value.reason == "reading_in_progress"
    assert "Anexo sintético" in str(error.value)
    assert nothing_was_queued()


def test_request_with_a_failed_reading_is_refused(operator_user):
    """REQ-024: un documento base cuya lectura falló no se deja afuera: se rechaza el pedido
    con ese motivo."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, synthetic_tender_pdf()[:400], title="Dañado")

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, procedure)

    assert error.value.reason == "reading_failed"
    assert "Dañado" in str(error.value)
    assert nothing_was_queued()


def test_request_with_a_draft_open_is_refused(operator_user, read_case):
    """REQ-024: con un borrador abierto no se pide otra propuesta."""
    _, job = propose(operator_user, read_case)
    assert job.status == "done", job.error

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, read_case)

    assert error.value.reason == "draft_open"
    assert m.MatrixRun.objects.count() == 1
    assert request_events(Outcome.REJECTED).get().detail["reason"] == "draft_open"


def test_second_request_while_the_first_is_waiting_is_refused(operator_user, read_case):
    """REQ-024: con un pedido de propuesta en espera o en curso no se encola otro."""
    matrix.request_matrix(operator_user, read_case)

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, read_case)

    assert error.value.reason == "request_in_progress"
    assert m.Job.objects.filter(kind="propose_matrix").count() == 1


def test_discarded_draft_allows_a_new_proposal_with_the_next_number(operator_user,
                                                                    evaluator_user,
                                                                    read_case):
    """REQ-024: con el borrador descartado se puede pedir otra propuesta, que crea la versión
    siguiente sin tocar la anterior."""
    first, _ = propose(operator_user, read_case)
    before = signature(first.run.version)
    version = first.run.version
    version.status = m.VersionStatus.DISCARDED
    version.discarded_by = evaluator_user
    from django.utils import timezone
    version.discarded_at = timezone.now()
    version.save()

    second, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    assert second.run.version.number == 2
    assert second.run.version.pk != version.pk
    assert signature(first.run.version) == before == signature(second.run.version)


def test_failed_proposal_does_not_block_a_new_request(operator_user, read_case, script):
    """ADR-0018: un pedido fallido no deja borrador; se puede volver a pedir."""
    script.fail("unavailable")
    first, job = propose(operator_user, read_case)
    assert job.status == "failed"

    script.recover()
    second, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    assert second.run.version.number == 1
    assert first.run.version is None


# --- Circulares y respuestas: se procesan aparte (T-083) ----------------------------------------


def test_circulars_do_not_block_the_request_and_are_processed(operator_user, read_case,
                                                              script, fake_reranker):
    """REQ-031: las circulares y respuestas no bloquean el pedido ni entran en los documentos
    base de la propuesta; la propuesta las procesa aparte (T-083) y ya no las anota como no
    procesadas."""
    from evaluon.tenders.services import documents

    circular = documents.load_document(
        operator_user, read_case,
        data=tender_pdf([[para("CIRCULAR MODIFICATORIA N° 1",
                               "1. Se modifica el plazo de entrega.")]], header=None),
        file_name="circular.pdf", kind="circular_modificatoria", title="Circular 1",
        issued_on=date(2025, 12, 1),
    )

    requested, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    assert [d["title"] for d in requested.run.documents] == ["Pliego sintético"]
    assert not any(a["type"] == "documentos_no_procesados" for a in requested.run.anomalies)
    assert requested.run.counts["circulars"]["documents"][0]["document"] == \
        circular.document.pk
    assert m.RunStep.objects.filter(run=requested.run, pass_name="circulares").exists()
    assert not any("plazo de entrega" in block["text"]
                   for blocks in script.calls for block in blocks.values())


# --- Roles (REQ-024) ------------------------------------------------------------------------------


def test_user_without_commission_role_cannot_request(no_commission_user, read_case):
    """REQ-024: sin rol de la Comisión no se pide la matriz; el rechazo queda como `rejected`."""
    with pytest.raises(RoleRejected):
        matrix.request_matrix(no_commission_user, read_case)

    assert nothing_was_queued()
    event = AuditEvent.objects.get(event_type=EventType.REJECTED)
    assert event.detail["operation"] == "evaluon.tenders.services.matrix.request_matrix"
    assert event.detail["required_commission_role"] == "operator"
    assert not request_events().exists()


def test_operator_and_evaluator_can_request(operator_user, evaluator_user, read_case):
    """REQ-024: el operador y el evaluador piden la matriz."""
    requested = matrix.request_matrix(evaluator_user, read_case)
    assert requested.job.requested_by == evaluator_user
    run_jobs()
    assert m.MatrixVersion.objects.get().created_by == evaluator_user


# --- El manejador y el worker (ADR-0018) ------------------------------------------------------------


def test_propose_matrix_handler_is_registered():
    """ADR-0018: `propose_matrix` está en `jobs.HANDLERS`, por su ruta."""
    assert jobs.HANDLERS[m.JobKind.PROPOSE_MATRIX] == \
        "evaluon.tenders.services.matrix.run_propose_matrix"
    assert jobs._handler(m.JobKind.PROPOSE_MATRIX) is matrix.run_propose_matrix


def test_worker_command_proposes_the_matrix_and_the_notice_waits(operator_user,
                                                                 evaluator_user,
                                                                 read_case):
    """ADR-0018: `procesar_pedidos` atiende el pedido; queda hecho y con el aviso de fin
    para quien lo pidió, y no para otro."""
    requested = matrix.request_matrix(operator_user, read_case)

    call_command("procesar_pedidos", "--hasta-vaciar")

    requested.job.refresh_from_db()
    assert requested.job.status == "done" and requested.job.finished_at is not None
    assert requested.job.pk in [job.pk for job in jobs.unseen_finished(operator_user)]
    assert not jobs.unseen_finished(evaluator_user).exists()
    version = m.MatrixVersion.objects.get()
    assert (version.number, version.status, version.run) == (1, "draft", requested.run)
    assert version.created_by == operator_user


def test_draft_comes_complete_with_its_rows(operator_user, read_case):
    """ADR-0018: la versión borrador sale con sus requisitos, citas, pendientes y
    disposiciones; todas las citas formales y económicas se comprueban al confirmar."""
    requested, job = propose(operator_user, read_case)

    assert job.status == "done", job.error
    version = requested.run.version
    assert requested.run.version == version
    assert m.Requirement.objects.filter(version=version).count() == 5
    assert m.Disposition.objects.filter(run=requested.run).count() == 19
    assert m.PendingItem.objects.filter(version=version).count() == 1
    from tests.tenders.scripted import check_deferred
    check_deferred()
