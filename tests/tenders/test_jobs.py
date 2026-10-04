"""Pedidos en segundo plano (T-071; plan 003, "Componentes" y "Pedidos y propuestas";
ADR-0018, "Cómo funciona").

Proponer la matriz de un pliego lleva minutos (REQ-024, REQ-030 y el tiempo por nivel de
la spec): el pedido queda en `tenders_job` y lo atiende `procesar_pedidos` en el servicio
`worker`. Se prueba que dos tomas a la vez no toman el mismo pedido, que un pedido que
falla queda `failed` con su motivo, que uno que quedó `running` al arrancar pasa a
`failed` "interrumpido", y el aviso de fin. Los manejadores son de prueba: los reales
los registran T-072 y T-073. Todos los textos son sintéticos (P4).
"""

import itertools
import threading
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection, transaction

from evaluon.ai import ServiceTimeoutError
from evaluon.tenders import jobs
from evaluon.tenders import models as m

_counter = itertools.count(1)


@pytest.fixture
def procedure(read_write_user):
    return m.Procedure.objects.create(
        number=f"PROC-PEDIDOS-{next(_counter)}",
        procedure_type="Licitación pública",
        subject="Objeto sintético",
        authorization_date=date(2025, 11, 14),
        created_by=read_write_user,
    )


@pytest.fixture
def handlers(monkeypatch):
    """Tabla de manejadores vacía para la prueba; `handlers[tipo] = función`."""
    table = {}
    monkeypatch.setattr(jobs, "HANDLERS", table)
    return table


def enqueue(procedure, user, kind=m.JobKind.PROPOSE_MATRIX):
    return jobs.enqueue(kind, procedure=procedure, requested_by=user)


# --- Encolar y tomar -------------------------------------------------------------------


@pytest.mark.django_db
def test_enqueue_creates_a_queued_job(procedure, read_write_user):
    """REQ-024, REQ-030: pedir una propuesta deja un pedido `queued`, con quién lo pidió
    y cuándo, sin empezar."""
    job = enqueue(procedure, read_write_user)
    job.refresh_from_db()
    assert job.status == m.JobStatus.QUEUED
    assert job.requested_by == read_write_user
    assert job.requested_at is not None
    assert job.started_at is None and job.finished_at is None


@pytest.mark.django_db
def test_claim_takes_the_oldest_queued_job_and_marks_it_running(procedure, read_write_user):
    """REQ-024: la toma devuelve el pedido más antiguo en espera, ya `running` y con su
    hora de inicio; sin pedidos en espera devuelve `None`."""
    first = enqueue(procedure, read_write_user)
    second = enqueue(procedure, read_write_user)

    taken = jobs.claim()
    assert taken.pk == first.pk
    first.refresh_from_db()
    assert first.status == m.JobStatus.RUNNING
    assert first.started_at is not None

    assert jobs.claim().pk == second.pk
    assert jobs.claim() is None


@pytest.mark.django_db(transaction=True)
def test_claim_skips_a_job_locked_by_another_claim(procedure, read_write_user):
    """REQ-024: mientras otra toma tiene el pedido bloqueado (y todavía no lo marcó
    `running`), una segunda toma no espera ni lo toma: pasa al siguiente. Con un solo
    pedido, bloqueado, no toma nada."""
    first = enqueue(procedure, read_write_user)
    second = enqueue(procedure, read_write_user)
    result = {}

    def other_worker(key):
        try:
            job = jobs.claim()
            result[key] = job.pk if job else None
        finally:
            connection.close()

    with transaction.atomic():
        m.Job.objects.select_for_update().get(pk=first.pk)
        thread = threading.Thread(target=other_worker, args=("con_dos",))
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), "la toma esperó al pedido bloqueado"
    assert result["con_dos"] == second.pk

    first.refresh_from_db()
    assert first.status == m.JobStatus.QUEUED

    with transaction.atomic():
        m.Job.objects.select_for_update().get(pk=first.pk)
        thread = threading.Thread(target=other_worker, args=("con_uno",))
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), "la toma esperó al pedido bloqueado"
    assert result["con_uno"] is None


@pytest.mark.django_db(transaction=True)
def test_simultaneous_claims_never_take_the_same_job(procedure, read_write_user):
    """REQ-024: varias tomas a la vez, cada una con su conexión, reparten los pedidos:
    ninguno se toma dos veces y ninguno queda sin tomar."""
    queued = {enqueue(procedure, read_write_user).pk for _ in range(12)}
    taken = []
    lock = threading.Lock()
    start = threading.Barrier(4)
    errors = []

    def worker():
        try:
            start.wait(timeout=30)
            while True:
                job = jobs.claim()
                if job is None:
                    return
                with lock:
                    taken.append(job.pk)
        except Exception as error:  # noqa: BLE001 - se informa abajo
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not errors
    assert sorted(taken) == sorted(queued)
    assert len(taken) == len(set(taken))
    assert set(m.Job.objects.values_list("status", flat=True)) == {m.JobStatus.RUNNING}


# --- Ejecutar ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_run_next_calls_the_handler_of_the_kind_and_marks_done(
    procedure, read_write_user, handlers
):
    """REQ-024: el pedido se ejecuta con el manejador de su tipo, que recibe el pedido
    ya `running`; al volver sin error queda `done` con su hora de fin."""
    seen = []
    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: seen.append((job.pk, job.status))
    job = enqueue(procedure, read_write_user)

    assert jobs.run_next().pk == job.pk

    job.refresh_from_db()
    assert seen == [(job.pk, m.JobStatus.RUNNING)]
    assert job.status == m.JobStatus.DONE
    assert job.finished_at is not None
    assert job.error == ""
    assert jobs.run_next() is None


@pytest.mark.django_db
def test_a_failing_job_is_failed_with_its_reason(procedure, read_write_user, handlers):
    """REQ-024: un manejador que falla deja el pedido `failed` con el motivo y la hora de
    fin; no se reintenta solo y el `worker` sigue con el pedido siguiente."""

    def broken(job):
        raise ValueError("tramo sintético sin disposición")

    handlers[m.JobKind.PROPOSE_MATRIX] = broken
    failing = enqueue(procedure, read_write_user)
    following = enqueue(procedure, read_write_user)

    jobs.run_next()
    failing.refresh_from_db()
    assert failing.status == m.JobStatus.FAILED
    assert "tramo sintético sin disposición" in failing.error
    assert "ValueError" in failing.error
    assert failing.finished_at is not None

    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: None
    assert jobs.run_next().pk == following.pk
    failing.refresh_from_db()
    assert failing.status == m.JobStatus.FAILED


@pytest.mark.django_db
def test_a_technical_failure_of_the_engine_keeps_its_reason(
    procedure, read_write_user, handlers
):
    """REQ-024: una falla técnica del motor (espera agotada) deja el pedido `failed` con
    el motivo propio del cliente de IA (plan 003, "Fallas")."""

    def slow(job):
        raise ServiceTimeoutError("generation_batch: sin respuesta en 180 s",
                                  service="generation_batch")

    handlers[m.JobKind.PROPOSE_MATRIX] = slow
    job = enqueue(procedure, read_write_user)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert job.error.startswith("timeout: ")
    assert "sin respuesta en 180 s" in job.error


@pytest.mark.django_db
def test_a_kind_without_handler_fails(procedure, read_write_user, handlers):
    """REQ-024: un tipo de pedido sin manejador registrado no queda en espera para
    siempre: falla con ese motivo."""
    job = enqueue(procedure, read_write_user)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert "sin manejador" in job.error
    assert m.JobKind.PROPOSE_MATRIX in job.error


@pytest.mark.django_db
def test_handlers_are_resolved_by_dotted_path(procedure, read_write_user, handlers):
    """REQ-024: la tabla acepta la ruta de la función, para que los servicios que
    encolan pedidos puedan registrar su manejador sin importarse en círculo."""
    handlers[m.JobKind.PROPOSE_MATRIX] = "tests.tenders.test_jobs.dotted_handler"
    job = enqueue(procedure, read_write_user)
    jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.DONE
    assert DOTTED_CALLS == [job.pk]


DOTTED_CALLS = []


def dotted_handler(job):
    DOTTED_CALLS.append(job.pk)


@pytest.mark.django_db
def test_an_interruption_during_a_job_fails_it_as_interrupted(
    procedure, read_write_user, handlers
):
    """REQ-024: si el `worker` se detiene a mitad de un pedido (señal de parada), el
    pedido queda `failed` "interrumpido" y la parada sigue su curso: nunca queda
    `running` ni se da por terminado."""

    def stopped(job):
        raise SystemExit(0)

    handlers[m.JobKind.PROPOSE_MATRIX] = stopped
    job = enqueue(procedure, read_write_user)
    with pytest.raises(SystemExit):
        jobs.run_next()
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED
    assert job.error == jobs.INTERRUPTED


@pytest.mark.django_db
def test_running_jobs_at_start_are_failed_as_interrupted(procedure, read_write_user):
    """REQ-024: al arrancar, los pedidos que quedaron `running` (el `worker` se cayó a
    mitad de camino) pasan a `failed` con el motivo "interrumpido"; los que esperan y
    los terminados no cambian."""
    running = enqueue(procedure, read_write_user)
    jobs.claim()
    queued = enqueue(procedure, read_write_user)
    done = enqueue(procedure, read_write_user)
    m.Job.objects.filter(pk=done.pk).update(status=m.JobStatus.DONE)

    assert jobs.fail_interrupted() == 1

    running.refresh_from_db()
    assert running.status == m.JobStatus.FAILED
    assert running.error == "interrumpido"
    assert running.finished_at is not None
    assert m.Job.objects.get(pk=queued.pk).status == m.JobStatus.QUEUED
    assert m.Job.objects.get(pk=done.pk).status == m.JobStatus.DONE


# --- Aviso de fin -----------------------------------------------------------------------


@pytest.mark.django_db
def test_finished_unseen_jobs_are_listed_until_marked_seen(
    procedure, read_write_user, read_user, handlers
):
    """REQ-024: el aviso de fin lista los pedidos de la persona que terminaron (bien o
    mal) y todavía no vio, del más reciente al más antiguo; no los de otra persona ni
    los que siguen en curso. Marcados como vistos, dejan de figurar."""
    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: None
    done = enqueue(procedure, read_write_user)
    jobs.run_next()
    failed = enqueue(procedure, read_write_user)
    jobs.fail(jobs.claim(), "motivo sintético")
    other = enqueue(procedure, read_user)
    jobs.run_next()
    enqueue(procedure, read_write_user)  # sigue en espera
    running = enqueue(procedure, read_write_user)
    m.Job.objects.filter(pk=running.pk).update(status=m.JobStatus.RUNNING)

    unseen = list(jobs.unseen_finished(read_write_user))
    assert [job.pk for job in unseen] == [failed.pk, done.pk]
    assert [job.pk for job in jobs.unseen_finished(read_user)] == [other.pk]

    assert jobs.mark_seen(read_write_user, [done.pk, other.pk]) == 1
    assert [job.pk for job in jobs.unseen_finished(read_write_user)] == [failed.pk]
    assert [job.pk for job in jobs.unseen_finished(read_user)] == [other.pk]

    first_seen = m.Job.objects.get(pk=done.pk).seen_at
    assert first_seen is not None
    jobs.mark_seen(read_write_user, [done.pk])
    assert m.Job.objects.get(pk=done.pk).seen_at == first_seen


# --- Comando procesar_pedidos -----------------------------------------------------------


@pytest.mark.django_db
def test_command_closes_interrupted_jobs_and_processes_the_queue(
    procedure, read_write_user, handlers
):
    """REQ-024: `procesar_pedidos --hasta-vaciar` cierra primero los interrumpidos y
    después atiende los pedidos de a uno, en orden, hasta vaciar la cola."""
    order = []
    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: order.append(job.pk)
    interrupted = enqueue(procedure, read_write_user)
    jobs.claim()
    first = enqueue(procedure, read_write_user)
    second = enqueue(procedure, read_write_user)

    out = StringIO()
    call_command("procesar_pedidos", "--hasta-vaciar", stdout=out)

    assert order == [first.pk, second.pk]
    statuses = dict(m.Job.objects.values_list("pk", "status"))
    assert statuses == {
        interrupted.pk: m.JobStatus.FAILED,
        first.pk: m.JobStatus.DONE,
        second.pk: m.JobStatus.DONE,
    }
    text = out.getvalue()
    assert "1 pedido interrumpido" in text
    assert f"Pedido {first.pk}" in text and f"Pedido {second.pk}" in text


@pytest.mark.django_db
def test_command_waits_between_polls_when_the_queue_is_empty(monkeypatch, settings):
    """REQ-024: con la cola vacía, el comando espera `WORKER_POLL_SECONDS` antes de
    volver a mirar (ADR-0018)."""
    from evaluon.tenders.management.commands import procesar_pedidos

    settings.WORKER_POLL_SECONDS = 7
    waits = []

    def fake_sleep(seconds):
        waits.append(seconds)
        if len(waits) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(procesar_pedidos.time, "sleep", fake_sleep)
    call_command("procesar_pedidos", stdout=StringIO())
    assert waits == [7, 7]
