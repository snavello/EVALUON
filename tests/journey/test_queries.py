"""Rendimiento de las cinco pestañas (REQ-100, T-221). Todo el material es inventado (P4).

Fijan, con el caso chico, el máximo de consultas a la base por pestaña y que la matriz de
evaluación (la definición única del estado de cada par, ADR-0039) se calcule una sola vez por
carga. El umbral de tiempo (< 2 s con el procedimiento real) se mide aparte, en una base de
pruebas; acá se fija la causa de la lentitud: consultas repetidas."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.assessment.services import matrix as matrix_service
from evaluon.journey import memo, sections
from evaluon.tenders.models import JobStatus
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

# Máximo de consultas por pestaña con el caso chico (dos ofertas, un requisito firme): lo medido
# más un margen. Subirlo exige explicar por qué una pestaña consulta más.
LIMITS = {"procedimiento": 145, "pliego": 180, "ofertas": 140, "evaluacion": 145,
          "normativas": 135}


@pytest.fixture
def evaluated(two_offers, simulate):
    simulate(two_offers, JobStatus.DONE, done=2)
    return two_offers


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


@pytest.mark.parametrize("slug", sorted(LIMITS))
def test_each_tab_stays_under_its_query_limit(client, procedure, evaluated, operator_user, slug):
    """REQ-100: ninguna pestaña supera su máximo de consultas con el caso chico."""
    log_in(client, operator_user)
    client.get(reverse(f"expedientes:{slug}", args=[procedure.pk]))  # calienta cachés
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse(f"expedientes:{slug}", args=[procedure.pk]))
    assert response.status_code == 200
    assert len(queries) <= LIMITS[slug], f"{slug}: {len(queries)} consultas"


@pytest.mark.parametrize("slug", ["pliego", "evaluacion"])
def test_the_evaluation_matrix_is_computed_once_per_load(client, procedure, evaluated,
                                                         operator_user, monkeypatch, slug):
    """REQ-100: la etapa y los temas de la Evaluación piden la matriz y se calcula una sola vez."""
    calls = []
    real = matrix_service.matrix_page

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(matrix_service, "matrix_page", spy)
    log_in(client, operator_user)
    assert client.get(reverse(f"expedientes:{slug}", args=[procedure.pk])).status_code == 200
    assert len(calls) == 1


def test_the_memo_does_not_survive_the_request(procedure, evaluated, operator_user, simulate):
    """REQ-100: fuera de un alcance no se guarda nada; entre dos cargas se recalcula."""
    first = sections.sections_for(operator_user, procedure)
    with CaptureQueriesContext(connection) as queries:
        memo.matrix_page(operator_user, procedure.pk)
        memo.matrix_page(operator_user, procedure.pk)
    assert len(queries) > 0 and len(queries) % 2 == 0  # dos cálculos, sin memoria
    with memo.scope():
        assert memo.matrix_page(operator_user, procedure.pk) is memo.matrix_page(
            operator_user, procedure.pk)
    assert first.sections
