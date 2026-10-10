"""Rendimiento de las cinco pestañas (REQ-100, T-221). Todo el material es inventado (P4).

Fijan, con el caso chico, el máximo de consultas a la base por pestaña y que la matriz de
evaluación (la definición única del estado de cada par, ADR-0039) se calcule una sola vez por
carga. El umbral de tiempo (< 2 s con el procedimiento real) se mide aparte, en una base de
pruebas; acá se fija la causa de la lentitud: consultas repetidas."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.journey import memo, sections
from evaluon.tenders.models import JobStatus
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

# Máximo de consultas por pestaña con el caso chico (dos ofertas, un requisito firme): lo medido
# el 2026-10-10 con T-223 (procedimiento 106, pliego 120, ofertas 112, evaluación 100,
# normativas 98) más un 15 %, redondeado. Subirlo exige explicar por qué una pestaña consulta más.
LIMITS = {"procedimiento": 122, "pliego": 138, "ofertas": 129, "evaluacion": 115,
          "normativas": 113}


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


# --- Un caso con muchos requisitos (T-223) ------------------------------------------------------
# Umbral escrito antes de medir: con 3 ofertas y 50 requisitos o más, cada pestaña hace menos de
# 150 consultas, y con el doble de requisitos hace como máximo un 10 % más.
SCALE_LIMIT = 150
SCALE_GROWTH = 1.10


def make_case(procedure, operator_user, simulate):
    """Tres ofertas evaluadas (una evaluación terminada de cada una); devuelve sus evaluaciones
    por oferta."""
    from tests.offers.conftest import make_offer
    offers = list(procedure.offers.order_by("number"))
    while len(offers) < 3:
        offers.append(make_offer(procedure, operator_user, f"Oferente {len(offers) + 1}", {
            "oferta.pdf": ["Declaro estar habilitado para contratar con el Estado."]}))
    job = simulate(offers, JobStatus.DONE, done=3)
    return offers, {run.offer_id: run for run in job.runs}


def grow_case(procedure, operator_user, offers, runs, total):
    """Deja `total` requisitos firmes (copias de los del caso chico, con sus citas) y cada par
    evaluado: cumple, falta la hoja de compliance, falta el documento o no cumple; algunos con
    decisión de la Comisión y algunas preguntas. Todo inventado (P4)."""
    version = procedure.matrix_versions.get(number=1)
    base = list(version.requirements.order_by("number"))
    number = max(r.number for r in base)
    # Las filas de una matriz validada son de solo inserción en un borrador (disparador de la
    # base): para armar el caso grande se las deja pasar mientras dura esta carga.
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
    while version.requirements.count() < total:
        source = base[number % len(base)]
        quotes = list(source.quotes.all())
        number += 1
        source.pk, source.number, source.previous = None, number, None
        source.restored_from = None
        source.save()
        for quote in quotes:
            quote.pk, quote.requirement = None, source
            quote.save()
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = origin")
    event = audit.record(EventType.EVAL_DECISION, outcome=EventOutcome.OK,
                         channel=Channel.SCREEN, user=operator_user)
    kinds = [(am.Outcome.CUMPLE, ""), (am.Outcome.NO_DETERMINADO, am.Doubt.EXTERNO),
             (am.Outcome.SIN_DOCUMENTO, ""), (am.Outcome.NO_CUMPLE, "")]
    for index, requirement in enumerate(version.requirements.order_by("number")):
        for offer in offers:
            if am.Result.objects.filter(offer=offer, requirement=requirement).exists():
                continue
            outcome, doubt = kinds[(index + offer.pk) % len(kinds)]
            result = am.Result.objects.create(
                run=runs[offer.pk], offer=offer, requirement=requirement, outcome=outcome,
                doubt=doubt, exigence=am.Exigence.CONDICION, explanation="Inventado.")
            if index % 3 == 0:
                am.Decision.objects.create(result=result, action=am.Action.CONFIRMAR,
                                           user=operator_user, event=event)
            if outcome == am.Outcome.NO_DETERMINADO and index % 2 == 0:
                am.Question.objects.create(
                    procedure=procedure, requirement=requirement, offer=offer, result=result,
                    text="¿Está vigente la constancia?", reason="externo")


def count_queries(client, procedure, slug):
    client.get(reverse(f"expedientes:{slug}", args=[procedure.pk]))  # calienta cachés
    with CaptureQueriesContext(connection) as queries:
        response = client.get(reverse(f"expedientes:{slug}", args=[procedure.pk]))
    assert response.status_code == 200
    return len(queries)


@pytest.mark.parametrize("slug", sorted(LIMITS))
def test_a_big_case_stays_under_the_limit_and_does_not_grow_with_requirements(
        client, procedure, operator_user, simulate, slug):
    """REQ-100: con 3 ofertas y 50 requisitos cada pestaña hace menos de 150 consultas; con el
    doble de requisitos, como máximo un 10 % más (no hay consultas por requisito ni por par)."""
    log_in(client, operator_user)
    offers, runs = make_case(procedure, operator_user, simulate)
    grow_case(procedure, operator_user, offers, runs, 50)
    small = count_queries(client, procedure, slug)
    assert small < SCALE_LIMIT, f"{slug}: {small} consultas con 50 requisitos"
    grow_case(procedure, operator_user, offers, runs, 100)
    big = count_queries(client, procedure, slug)
    assert big <= small * SCALE_GROWTH, f"{slug}: {small} con 50 y {big} con 100 requisitos"


def test_the_quotes_of_the_pliego_do_not_load_the_whole_reading(procedure, matrix):
    """REQ-100, T-231 (E-11): las citas traen el tramo y el título del documento, no el texto
    canónico ni las páginas enteras de la lectura (una carga por cita multiplicaba cientos de
    miles de caracteres por cada requisito)."""
    from evaluon.journey import points

    ids = [r.pk for r in matrix.version.requirements.all()]
    found = points.quotes_of(ids)
    quotes = [q for group in found.values() for q in group]
    assert quotes
    for quote in quotes:
        deferred = quote.segment.reading.get_deferred_fields()
        assert {"canonical_text", "pages", "tables", "report"} <= deferred
        assert quote.segment.reading.document.title  # lo que sí se necesita
