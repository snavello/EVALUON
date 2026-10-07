"""Avance fino de los pedidos en la cola (T-184; REQ-067; ADR-0045 3.B): `jobs.report` escribe en
`tenders_job.progress` con una escritura aparte, guarda una lista corta de los últimos pasos y
nunca hace fallar al pedido. Textos sintéticos (P4)."""

import itertools
from datetime import date

import pytest

from evaluon.tenders import jobs
from evaluon.tenders import models as m

pytestmark = pytest.mark.django_db

_counter = itertools.count(1)


@pytest.fixture
def procedure(read_write_user):
    return m.Procedure.objects.create(
        number=f"PROC-AVANCE-{next(_counter)}", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=read_write_user)


@pytest.fixture
def job(procedure, read_write_user):
    return jobs.enqueue(m.JobKind.EVALUATE_OFFERS, procedure=procedure,
                        requested_by=read_write_user, target_id=1)


def test_the_column_defaults_to_an_empty_object(job):
    """REQ-067: un pedido nuevo no tiene avance anotado."""
    job.refresh_from_db()
    assert job.progress == {}


def test_report_writes_the_step_and_the_count(job):
    """REQ-067: `report` deja el paso, la cuenta y el contexto en la columna."""
    assert jobs.report(job, "Leyendo el requisito 3", 2, 40, "Oferta 1 de 2") is True
    stored = m.Job.objects.get(pk=job.pk).progress
    assert (stored["step"], stored["done"], stored["total"], stored["scope"]) == (
        "Leyendo el requisito 3", 2, 40, "Oferta 1 de 2")
    assert [r["text"] for r in stored["recent"]] == ["Leyendo el requisito 3"]


def test_report_keeps_only_the_last_steps_and_skips_repeats(job):
    """REQ-067: la lista corta conserva los últimos pasos (acotada) y no repite el mismo."""
    for number in range(20):
        jobs.report(job, f"Paso {number}")
        jobs.report(job, f"Paso {number}")
    recent = m.Job.objects.get(pk=job.pk).progress["recent"]
    assert len(recent) == jobs.RECENT_STEPS
    assert [r["text"] for r in recent][-1] == "Paso 19"
    assert [r["text"] for r in recent][0] == f"Paso {20 - jobs.RECENT_STEPS}"


def test_report_truncates_long_texts(job):
    """REQ-067: un texto largo se acota."""
    jobs.report(job, "x" * 1000)
    assert len(m.Job.objects.get(pk=job.pk).progress["step"]) == jobs.STEP_MAX_CHARS


class BrokenJob:
    """Un `Job` cuya escritura falla: sirve para probar que el avance no rompe nada."""

    class objects:  # noqa: N801
        @staticmethod
        def filter(*args, **kwargs):
            raise RuntimeError("base caída")


def test_report_does_not_fail_when_the_write_fails(job, monkeypatch):
    """REQ-067: una falla al escribir el avance no sale de `report`."""
    monkeypatch.setattr(jobs, "Job", BrokenJob)
    assert jobs.report(job, "Paso") is False


def test_a_handler_that_reports_and_then_fails_keeps_the_progress(handlers_table, job):
    """REQ-067: el avance escrito sobrevive a una falla posterior del pedido."""
    def handler(running):
        jobs.report(running, "Leyendo el requisito 1", 0, 3)
        raise ValueError("falla posterior")
    handlers_table[m.JobKind.EVALUATE_OFFERS] = handler
    jobs.run_next()
    stored = m.Job.objects.get(pk=job.pk)
    assert stored.status == m.JobStatus.FAILED
    assert stored.progress["step"] == "Leyendo el requisito 1"


def test_a_handler_whose_report_fails_still_finishes(handlers_table, job, monkeypatch):
    """REQ-067: si `report` no puede escribir, el pedido termina bien."""
    real = jobs.Job

    def handler(running):
        monkeypatch.setattr(jobs, "Job", BrokenJob)
        try:
            jobs.report(running, "Paso", 0, 1)
        finally:
            monkeypatch.setattr(jobs, "Job", real)
    handlers_table[m.JobKind.EVALUATE_OFFERS] = handler
    jobs.run_next()
    assert m.Job.objects.get(pk=job.pk).status == m.JobStatus.DONE


def test_the_progress_is_not_an_audit_fact(job):
    """REQ-067: anotar el avance no deja ningún hecho de auditoría."""
    from evaluon.audit.models import AuditEvent
    before = AuditEvent.objects.count()
    jobs.report(job, "Paso", 1, 2)
    assert AuditEvent.objects.count() == before


@pytest.fixture
def handlers_table(monkeypatch):
    table = {}
    monkeypatch.setattr(jobs, "HANDLERS", table)
    return table
