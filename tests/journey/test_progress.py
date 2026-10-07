"""Avance fino de los pedidos (T-184; REQ-067; ADR-0045 3.B): `progress_of` usa la columna
`progress` cuando tiene datos y, vacía, cae al cálculo del corte; la evaluación y la ficha
anotan oferta k de N, requisito x de y, contraste y reglas en lenguaje llano y sin datos
personales, sin cambiar sus resultados. Caso chico y textos inventados (P4); modelo simulado."""

import datetime

import pytest
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate
from evaluon.audit.models import Channel
from evaluon.journey import progress
from evaluon.offers.services import sheets
from evaluon.tenders import jobs
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.assessment.fakes import model, says  # noqa: F401 - el modelo simulado de la 004
from tests.offers.conftest import pick, script  # noqa: F401 - el guion de la ficha (008)

pytestmark = pytest.mark.django_db

DECLARATION = "Declaro bajo juramento que me encuentro habilitado para contratar"


def running(procedure, user, kind=JobKind.BUILD_SHEET, target=1):
    return Job.objects.create(
        kind=kind, procedure=procedure, requested_by=user, target_id=target,
        status=JobStatus.RUNNING,
        started_at=timezone.now() - datetime.timedelta(seconds=30))


def test_progress_of_uses_the_column_when_it_has_data(procedure, operator_user):
    """REQ-067: con la columna cargada, el paso, la cuenta y los últimos pasos salen de ella."""
    job = running(procedure, operator_user)
    jobs.report(job, "Buscando en la oferta el requisito 3", 2, 10, "Ficha de la oferta 1")
    jobs.report(job, "Buscando en la oferta el requisito 4", 3, 10, "Ficha de la oferta 1")
    data = progress.progress_of(Job.objects.get(pk=job.pk))
    assert data["step"] == "Ficha de la oferta 1: Buscando en la oferta el requisito 4"
    assert (data["done"], data["total"], data["percent"]) == (3, 10, 30)
    assert [r["text"] for r in data["recent"]] == [
        "Buscando en la oferta el requisito 3", "Buscando en la oferta el requisito 4"]


def test_progress_of_falls_back_to_the_cut_calculation_with_an_empty_column(
        procedure, two_offers, simulate, operator_user):
    """REQ-067: con la columna vacía, la evaluación sigue mostrando "N de M ofertas evaluadas"."""
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    data = progress.progress_of(Job.objects.get(pk=made.job.pk))
    assert data["step"] == "1 de 2 ofertas evaluadas"
    assert (data["done"], data["total"], data["percent"]) == (1, 2, 50)
    assert data["recent"] == [] and data["detail_total"] is None


def test_evaluation_keeps_the_offer_count_and_adds_the_fine_one(
        procedure, two_offers, simulate, operator_user):
    """REQ-067: en la evaluación, `done`/`total` siguen siendo ofertas, el requisito x de y va
    aparte y `recent` está acotada."""
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    for number in range(30):
        jobs.report(made.job, f"Leyendo el requisito {number}", number, 30, "Oferta 2 de 2")
    data = progress.progress_of(Job.objects.get(pk=made.job.pk))
    assert (data["done"], data["total"]) == (1, 2)
    assert (data["detail_done"], data["detail_total"]) == (29, 30)
    assert len(data["recent"]) == progress.RECENT_LIMIT
    assert data["step"].startswith("Oferta 2 de 2: Leyendo el requisito 29")


def test_a_waiting_job_shows_no_fine_steps(procedure, operator_user):
    """REQ-067: un pedido en espera muestra "En espera", sin pasos."""
    job = Job.objects.create(kind=JobKind.BUILD_SHEET, procedure=procedure,
                             requested_by=operator_user, target_id=1)
    jobs.report(job, "Paso", 1, 2)
    data = progress.progress_of(Job.objects.get(pk=job.pk))
    assert data["step"] == "En espera" and data["recent"] == []


def cumple_declaration(call):
    if "declaración jurada" in call.requirement and call.quote(DECLARATION):
        return says("cumple", call.quote(DECLARATION), exigence="condicion")
    return None


def run_evaluation(user, procedure, **kwargs):
    requested = evaluate.request_evaluation(user, procedure, **kwargs)
    try:
        runs = evaluate.execute(requested.request, user, channel=am.Channel.EVAL,
                                audit_channel=Channel.EVAL, job=requested.job)
    finally:
        jobs.finish(requested.job)
    return requested, runs


def test_the_evaluation_reports_offers_requirements_and_contrast(
        procedure, two_offers, operator_user, model, monkeypatch):
    """REQ-067: la evaluación informa oferta k de N, requisito x de y y el contraste, en
    lenguaje llano y sin nombres de oferentes."""
    model.evaluates(cumple_declaration)
    seen = []
    real = jobs.report

    def spy(job, step, done=None, total=None, scope=""):
        seen.append((step, done, total, scope))
        return real(job, step, done, total, scope)

    monkeypatch.setattr(jobs, "report", spy)
    requested, runs = run_evaluation(operator_user, procedure)

    assert len(runs) == 2
    assert {"Oferta 1 de 2", "Oferta 2 de 2"} <= {s[3] for s in seen}
    assert any(s[0] == "Empezando la oferta 2 de 2" and s[1:3] == (1, 2) for s in seen)
    reading = [s for s in seen if s[0].startswith("Leyendo el requisito")]
    assert reading and all(s[2] and s[1] < s[2] for s in reading)
    assert any(s[0].startswith("Contrastando") for s in seen)
    assert seen[-1][0] == "Guardando la evaluación de la oferta"
    assert not any("Segundo oferente" in s[0] + s[3] for s in seen)
    stored = Job.objects.get(pk=requested.job.pk).progress
    assert 0 < len(stored["recent"]) <= jobs.RECENT_STEPS


def test_the_evaluation_gives_the_same_results_with_and_without_reporting(
        procedure, two_offers, operator_user, model, monkeypatch):
    """REQ-067: informar el avance no cambia los resultados."""
    model.evaluates(cumple_declaration)
    _, runs = run_evaluation(operator_user, procedure, offers=[two_offers[0]])
    with_report = sorted((r.requirement.number, r.outcome) for r in runs[0].results.all())
    monkeypatch.setattr(jobs, "report", lambda *args, **kwargs: True)
    _, again = run_evaluation(operator_user, procedure, offers=[two_offers[0]])
    without = sorted((r.requirement.number, r.outcome) for r in again[0].results.all())
    assert with_report == without and with_report


def test_the_sheet_reports_each_requirement(procedure, offer, operator_user, script):
    """REQ-067: la ficha informa un paso por requisito y el cierre, sin datos personales."""
    script.choose(pick("Declaro bajo juramento", when="declaración jurada"))
    job = Job.objects.create(kind=JobKind.BUILD_SHEET, procedure=procedure,
                             requested_by=operator_user, target_id=offer.pk,
                             status=JobStatus.RUNNING, started_at=timezone.now())
    sheet = sheets.build_sheet(offer, operator_user, job=job)
    stored = Job.objects.get(pk=job.pk).progress
    assert stored["step"] == "Guardando la ficha"
    assert stored["done"] == stored["total"] == sheet.entries.count()
    assert stored["scope"] == f"Ficha de la oferta {offer.number}"
    assert all(r["text"] for r in stored["recent"])
