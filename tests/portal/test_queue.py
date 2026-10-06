"""Cola compartida entre `worker` y `portal_worker` (T-138; plan 012, "Cola compartida";
ADR-0031).

Dos consumidores de la misma tabla `tenders_job`, con filtro por tipo: uno no toma ni corta
los pedidos del otro. Los manejadores son de prueba (los reales son de T-141). Datos
sintéticos (P4).
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from evaluon.portal.models import PortalLink
from evaluon.tenders import jobs
from evaluon.tenders import models as m

PORTAL = m.PORTAL_JOB_KINDS


@pytest.fixture
def handlers(monkeypatch):
    table = {}
    monkeypatch.setattr(jobs, "HANDLERS", table)
    return table


@pytest.fixture
def link(read_write_user):
    return PortalLink.objects.create(
        url="https://portal.ejemplo.test/PLIEGO/x.aspx?qs=1", created_by=read_write_user)


def portal_job(link, user, kind=m.JobKind.PORTAL_EXPLORE):
    """Pedido del Portal: sin procedimiento, con el enlace como objeto."""
    return jobs.enqueue(kind, procedure=None, requested_by=user, target_id=link.pk)


def tender_job(procedure, user):
    return jobs.enqueue(m.JobKind.PROPOSE_MATRIX, procedure=procedure, requested_by=user)


def test_portal_kinds_are_the_two_new_types():
    """REQ-045: los dos tipos del Portal, y solo ellos, son los que atiende `portal_worker`."""
    assert set(PORTAL) == {"portal_explore", "portal_review"}


def test_portal_handlers_are_registered():
    """REQ-045: los dos tipos tienen manejador (la función la crea T-141)."""
    assert set(PORTAL) <= set(jobs.HANDLERS)


def test_claim_by_kind_does_not_take_the_other_consumers_jobs(
        procedure, link, read_write_user):
    """REQ-045: `portal_worker` solo toma pedidos del Portal y el `worker` no toma los del
    Portal, aunque el pedido del otro sea el más antiguo."""
    matrix = tender_job(procedure, read_write_user)
    explore = portal_job(link, read_write_user)

    assert jobs.claim(exclude=PORTAL) == matrix
    assert jobs.claim(exclude=PORTAL) is None
    assert m.Job.objects.get(pk=explore.pk).status == m.JobStatus.QUEUED
    assert jobs.claim(kinds=PORTAL) == explore
    assert jobs.claim(kinds=PORTAL) is None


def test_portal_consumer_ignores_older_tender_jobs(procedure, link, read_write_user):
    """REQ-045: con un pedido de matriz más antiguo en espera, `portal_worker` toma el
    del Portal y deja el otro en espera."""
    matrix = tender_job(procedure, read_write_user)
    explore = portal_job(link, read_write_user)
    assert jobs.claim(kinds=PORTAL) == explore
    assert m.Job.objects.get(pk=matrix.pk).status == m.JobStatus.QUEUED


def test_claim_without_filter_takes_any_kind(procedure, link, read_write_user):
    """Sin filtro, `claim` sigue atendiendo todos los tipos, en orden de llegada."""
    first = tender_job(procedure, read_write_user)
    second = portal_job(link, read_write_user)
    assert jobs.claim() == first
    assert jobs.claim() == second


def test_fail_interrupted_only_touches_its_own_kinds(procedure, link, read_write_user):
    """REQ-045: al arrancar, cada consumidor pasa a fallidos solo sus pedidos en curso."""
    matrix = tender_job(procedure, read_write_user)
    explore = portal_job(link, read_write_user)
    m.Job.objects.update(status=m.JobStatus.RUNNING)

    assert jobs.fail_interrupted(exclude=PORTAL) == 1
    assert m.Job.objects.get(pk=matrix.pk).status == m.JobStatus.FAILED
    assert m.Job.objects.get(pk=matrix.pk).error == jobs.INTERRUPTED
    assert m.Job.objects.get(pk=explore.pk).status == m.JobStatus.RUNNING

    assert jobs.fail_interrupted(kinds=PORTAL) == 1
    assert m.Job.objects.get(pk=explore.pk).status == m.JobStatus.FAILED

    assert jobs.fail_interrupted() == 0


def test_run_next_by_kind_runs_the_right_handler(
        procedure, link, read_write_user, handlers):
    """REQ-045: `run_next` con tipos ejecuta el manejador del Portal y termina el pedido;
    el pedido de la 003 queda esperando."""
    seen = []
    handlers[m.JobKind.PORTAL_EXPLORE] = lambda job: seen.append(job.target_id)
    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: seen.append("matriz")
    matrix = tender_job(procedure, read_write_user)
    explore = portal_job(link, read_write_user)

    assert jobs.run_next(kinds=PORTAL) == explore
    assert seen == [link.pk]
    assert m.Job.objects.get(pk=explore.pk).status == m.JobStatus.DONE
    assert m.Job.objects.get(pk=matrix.pk).status == m.JobStatus.QUEUED
    assert jobs.run_next(kinds=PORTAL) is None


def test_procesar_pedidos_ignores_portal_jobs(procedure, link, read_write_user, handlers):
    """REQ-045: el comando del `worker` atiende el pedido de matriz, no toca el del Portal
    y no pasa a fallido uno del Portal que está en curso."""
    handlers[m.JobKind.PROPOSE_MATRIX] = lambda job: None
    matrix = tender_job(procedure, read_write_user)
    waiting = portal_job(link, read_write_user)
    running = portal_job(link, read_write_user, m.JobKind.PORTAL_REVIEW)
    m.Job.objects.filter(pk=running.pk).update(status=m.JobStatus.RUNNING)

    call_command("procesar_pedidos", "--hasta-vaciar", stdout=StringIO())

    assert m.Job.objects.get(pk=matrix.pk).status == m.JobStatus.DONE
    assert m.Job.objects.get(pk=waiting.pk).status == m.JobStatus.QUEUED
    assert m.Job.objects.get(pk=running.pk).status == m.JobStatus.RUNNING


def test_procesar_portal_attends_only_portal_jobs(procedure, link, read_write_user, handlers):
    """REQ-045: `procesar_portal` atiende los pedidos del Portal, no toma el de la 003 y
    no corta sus pedidos en curso; sí corta los suyos."""
    handlers[m.JobKind.PORTAL_EXPLORE] = lambda job: None
    matrix = tender_job(procedure, read_write_user)
    running_matrix = tender_job(procedure, read_write_user)
    m.Job.objects.filter(pk=running_matrix.pk).update(status=m.JobStatus.RUNNING)
    explore = portal_job(link, read_write_user)
    stuck = portal_job(link, read_write_user, m.JobKind.PORTAL_REVIEW)
    m.Job.objects.filter(pk=stuck.pk).update(status=m.JobStatus.RUNNING)
    out = StringIO()

    call_command("procesar_portal", "--hasta-vaciar", stdout=out)

    assert m.Job.objects.get(pk=explore.pk).status == m.JobStatus.DONE
    assert m.Job.objects.get(pk=stuck.pk).status == m.JobStatus.FAILED
    assert m.Job.objects.get(pk=stuck.pk).error == jobs.INTERRUPTED
    assert m.Job.objects.get(pk=matrix.pk).status == m.JobStatus.QUEUED
    assert m.Job.objects.get(pk=running_matrix.pk).status == m.JobStatus.RUNNING
    assert "portal_explore" in out.getvalue()


# --- Restricciones de la base --------------------------------------------------------


def test_procedure_may_be_null_only_for_portal_jobs(procedure, link, read_write_user):
    """REQ-045: `procedure` admite nulo solo en `portal_explore` y `portal_review`."""
    for kind in PORTAL:
        assert portal_job(link, read_write_user, kind).procedure is None
    for kind in (m.JobKind.READ_DOCUMENT, m.JobKind.PROPOSE_MATRIX,
                 m.JobKind.READ_OFFER_DOCUMENT, m.JobKind.BUILD_SHEET):
        with pytest.raises(IntegrityError), transaction.atomic():
            m.Job.objects.create(
                kind=kind, procedure=None, requested_by=read_write_user, target_id=1)


def test_portal_jobs_require_a_target(link, read_write_user):
    """REQ-045: un pedido del Portal sin enlace se rechaza en la base."""
    for kind in PORTAL:
        with pytest.raises(IntegrityError), transaction.atomic():
            m.Job.objects.create(kind=kind, procedure=None, requested_by=read_write_user)


def test_portal_job_with_a_procedure_is_allowed(procedure, link, read_write_user):
    """El pedido de revisión de un enlace ya asociado puede nombrar su procedimiento."""
    job = jobs.enqueue(
        m.JobKind.PORTAL_REVIEW, procedure=procedure, requested_by=read_write_user,
        target_id=link.pk)
    assert job.procedure == procedure
