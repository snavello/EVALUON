"""Fixtures de la feature 013 (recorrido del procedimiento; T-179).

- Los de la 004 y la 008: usuarios de la Comisión, el procedimiento del caso chico con su
  matriz validada (`procedure`, `matrix`) y una oferta con documentos leídos (`offer`).
- `two_offers`: la oferta anterior y una segunda, las dos con documentos.
- `simulate`: arma un pedido de evaluación simulado (en espera, en curso con k ofertas hechas,
  terminado o fallido) sin pasar por el modelo. Todo el texto es inventado (P4).
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.assessment.conftest import (  # noqa: F401 - fixtures de la 004, la 008 y la 003
    evaluator_user,
    expected,
    matrix,
    no_commission_user,
    offer,
    operator_user,
    procedure,
)
from tests.offers.conftest import make_offer


@pytest.fixture
def two_offers(procedure, operator_user, offer):
    second = make_offer(procedure, operator_user, "Segundo oferente", {
        "oferta.pdf": ["Declaro estar habilitado para contratar con el Estado."]})
    return [offer, second]


def make_run(request, offer, version):
    """Una evaluación de `offer` dentro del pedido `request`."""
    number = offer.assessment_runs.count() + 1
    return am.Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=number,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})


@pytest.fixture
def simulate(procedure, matrix, evaluator_user):
    """`simulate(offers, status, done=0, error="")`: un pedido de evaluación en el estado
    pedido, con `done` ofertas evaluadas. Devuelve `SimpleNamespace(job, request, runs)`."""

    def build(offers, status, done=0, error=""):
        job = Job.objects.create(kind=JobKind.EVALUATE_OFFERS, procedure=procedure,
                                 requested_by=evaluator_user)
        request = am.Request.objects.create(
            procedure=procedure, matrix_version=matrix.version,
            offers=[o.pk for o in offers], requirements=None, cause=am.Cause.MATRIZ,
            requested_by=evaluator_user, job=job)
        Job.objects.filter(pk=job.pk).update(target_id=request.pk)
        runs = [make_run(request, o, matrix.version) for o in offers[:done]]
        now = timezone.now()  # después de las evaluaciones hechas: la falla las sigue
        fields = {"status": status}
        if status in (JobStatus.RUNNING, JobStatus.DONE, JobStatus.FAILED):
            fields["started_at"] = now - timedelta(seconds=125)
        if status in (JobStatus.DONE, JobStatus.FAILED):
            fields["finished_at"] = now
        if status == JobStatus.FAILED:
            fields["error"] = error or "el servicio de generación no respondió"
        Job.objects.filter(pk=job.pk).update(**fields)
        job.refresh_from_db()
        return SimpleNamespace(job=job, request=request, runs=runs)

    return build


@pytest.fixture
def progress_steps():
    """`progress_steps(job, steps, done, total, scope)`: anota en el pedido, con `jobs.report`,
    los pasos en lenguaje llano (inventados) como lo haría la evaluación."""
    from evaluon.tenders import jobs

    def apply(job, steps, done=None, total=None, scope=""):
        for text in steps:
            jobs.report(job, text, done, total, scope)
        job.refresh_from_db()
        return job

    return apply
