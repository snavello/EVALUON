"""La pestaña de Normativas con la Consulta en el motor único (T-255, ADR-0057; REQ-107).

Mismo aviso que la pantalla de la Consulta (`tests/queries/test_consulta_motor_unico.py`): mientras
corre un trabajo que usa el motor de lotes (el 27B atiende evaluaciones y Consulta, de a un pedido),
la consulta de la pestaña lo dice, desactiva el botón y no ejecuta ni guarda la pregunta. Con el
motor libre, la Consulta anda. Los dobles de IA no usan la red ni la GPU. Los datos son
sintéticos (P4)."""

import pytest
from django.urls import reverse

from evaluon.journey.temas import s5_consulta
from evaluon.queries import services
from evaluon.queries.models import Query
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.conftest import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db

BUSY = ("La consulta de normativa no está disponible mientras el sistema evalúa o arma una matriz; "
        "vuelva a intentar cuando termine")


@pytest.fixture
def one_engine(settings):
    """Un solo motor: la Consulta va a la misma dirección que los pedidos de lotes."""
    settings.GENERATION_URL = settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    return settings


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def run_job(procedure, user, kind=JobKind.EVALUATE_OFFERS, status=JobStatus.RUNNING):
    return Job.objects.create(kind=kind, status=status, procedure=procedure, target_id=1,
                              requested_by=user)


def test_the_normativas_tab_says_it_and_does_not_let_ask_while_a_job_runs(
        client, operator_user, procedure, one_engine):
    """REQ-107: con una evaluación en curso, la consulta de la pestaña de Normativas dice que no
    está disponible mientras el sistema evalúa o arma una matriz, y desactiva el botón."""
    run_job(procedure, operator_user)
    log_in(client, operator_user)

    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()

    assert 'id="s5-consulta-apagada"' in html and BUSY in html
    assert 'id="s5-consulta-enviar" disabled' in html


def test_the_normativas_tab_has_no_notice_with_the_engine_free(
        client, operator_user, procedure, one_engine):
    """REQ-107: sin trabajo en curso la pestaña es la de siempre; un trabajo terminado o en espera
    no la apaga."""
    run_job(procedure, operator_user, status=JobStatus.DONE)
    run_job(procedure, operator_user, kind=JobKind.PROPOSE_MATRIX, status=JobStatus.QUEUED)
    log_in(client, operator_user)

    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()

    assert "s5-consulta-apagada" not in html and BUSY not in html
    assert 'id="s5-consulta-enviar" disabled' not in html
    assert 'id="s5-consulta-enviar"' in html


def test_asking_from_the_tab_while_a_job_runs_goes_back_with_the_notice(
        client, operator_user, procedure, one_engine, fake_ai):
    """REQ-107: la pregunta enviada desde la pestaña con el motor ocupado no se ejecuta ni se
    guarda; vuelve a la pestaña con el aviso."""
    run_job(procedure, operator_user, kind=JobKind.PROPOSE_MATRIX)
    log_in(client, operator_user)

    response = client.post(reverse("expedientes:s5_consultar", args=[procedure.pk]),
                           {"question": "¿Cuál es el objeto del régimen?"})

    assert response.status_code == 302
    shown = s5_consulta.unpack(response["Location"].split("aviso=")[1].split("#")[0])
    assert shown == {"ok": False, "text": services.BUSY_NOTICE}
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.generation.calls == []
    assert BUSY in client.get(response["Location"]).content.decode()


def test_asking_from_the_tab_with_the_engine_free_runs_the_consulta(
        client, operator_user, procedure, one_engine, fake_ai):
    """REQ-107: sin trabajo en curso la pregunta se ejecuta y se guarda, y la pestaña vuelve con su
    respuesta (no con un aviso)."""
    log_in(client, operator_user)

    response = client.post(reverse("expedientes:s5_consultar", args=[procedure.pk]),
                           {"question": "¿Cuál es el objeto del régimen?"})

    assert response.status_code == 302 and "consulta=" in response["Location"]
    assert "aviso=" not in response["Location"]
    assert Query.objects.count() == 1
