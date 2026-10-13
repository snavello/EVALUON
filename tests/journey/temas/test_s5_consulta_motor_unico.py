"""La pestaña de Normativas con la Consulta en el motor único (T-255, ADR-0057; REQ-107).

Mismo aviso que la pantalla de la Consulta (`tests/queries/test_consulta_motor_unico.py`): mientras
corre un trabajo que usa el motor de lotes (el 27B atiende evaluaciones y Consulta, de a un pedido),
la consulta de la pestaña lo dice, desactiva el botón y no ejecuta ni guarda la pregunta. Con el
motor libre, la Consulta anda. Los dobles de IA no usan la red ni la GPU. Los datos son
sintéticos (P4)."""

import pytest
from django.urls import reverse

from evaluon.ai import generation
from evaluon.journey.temas import s5_consulta
from evaluon.queries import services
from evaluon.queries.models import Query
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.conftest import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db

BUSY = ("La consulta de normativa no está disponible mientras el sistema evalúa o arma una matriz; "
        "vuelva a intentar cuando termine")
# Con el motor compartido sin contestar, y con `generation` aparte sin contestar (T-247).
NOT_RESPONDING = ("La consulta de normativa no está disponible por ahora: el motor del modelo se está "
                  "encendiendo o no responde. Vuelva a intentarlo en unos minutos.")
OFF_T247 = ("La consulta de normativa no está disponible por ahora: el equipo usa el modelo grande "
            "para las evaluaciones y deja apagado el motor de la consulta. Vuelva a intentarlo más tarde.")


@pytest.fixture
def one_engine(settings):
    """Un solo motor: la Consulta va a la misma dirección que los pedidos de lotes."""
    settings.GENERATION_URL = settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    return settings


@pytest.fixture
def two_engines(settings):
    """`generation` aparte de `generation_batch` (el 27B sin Consulta, o el 12B)."""
    settings.GENERATION_URL = "http://generation:8080"
    settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    return settings


@pytest.fixture
def engine_down(monkeypatch):
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)


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


def test_the_normativas_tab_says_the_shared_engine_is_starting_and_does_not_let_ask(
        client, operator_user, procedure, one_engine, engine_down, fake_ai):
    """REQ-107: con el motor compartido sin contestar (el 27B cargando, o caído) la pestaña dice que
    se está encendiendo o no responde y desactiva el botón; la pregunta enviada vuelve a la pestaña
    con el mismo aviso, sin ejecutarse ni guardarse."""
    log_in(client, operator_user)

    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()
    assert 'id="s5-consulta-apagada"' in html and NOT_RESPONDING in html
    assert 'id="s5-consulta-enviar" disabled' in html
    assert OFF_T247 not in html and BUSY not in html

    response = client.post(reverse("expedientes:s5_consultar", args=[procedure.pk]),
                           {"question": "¿Cuál es el objeto del régimen?"})
    assert response.status_code == 302
    shown = s5_consulta.unpack(response["Location"].split("aviso=")[1].split("#")[0])
    assert shown == {"ok": False, "text": services.NOT_RESPONDING_NOTICE}
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.generation.calls == []


def test_the_normativas_tab_with_two_engines_and_the_consulta_one_off_keeps_the_notice_of_t247(
        client, operator_user, procedure, two_engines, engine_down):
    """REQ-107: con `generation` aparte que no contesta, la pestaña dice lo de T-247."""
    log_in(client, operator_user)

    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()

    assert OFF_T247 in html and NOT_RESPONDING not in html
    assert 'id="s5-consulta-enviar" disabled' in html


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


def test_the_wait_text_of_the_tab_says_up_to_a_minute(client, operator_user, procedure):
    """REQ-107 (T-255): con el 27B una respuesta larga pasa de los 30 s (la prueba de humo midió 14 s
    para 294 tokens de salida; el tope de 800 tokens son unos 35 a 40 s) y el pedido espera hasta
    60 s: el texto de espera de la pestaña promete hasta un minuto, no medio."""
    log_in(client, operator_user)

    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()

    assert "Buscando en la normativa. Puede tardar hasta un minuto; no cierre la pestaña." in html
    assert "medio minuto" not in html
