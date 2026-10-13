"""La pestaña de Normativas con el motor de la Consulta apagado (T-247, ADR-0057; REQ-107).

Mismo aviso que la pantalla de la Consulta (`tests/queries/test_consulta_apagada.py`): la consulta de
la pestaña dice que no está disponible por ahora, desactiva el botón y no ejecuta ni guarda la
pregunta. Los dobles de IA no usan la red ni la GPU. Los datos son sintéticos (P4)."""

import pytest
from django.urls import reverse

from evaluon.ai import generation
from evaluon.journey.temas import s5_consulta
from evaluon.queries import services
from evaluon.queries.models import Query
from tests.conftest import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db

NOTICE = "La consulta de normativa no está disponible por ahora"


@pytest.fixture
def engine_down(monkeypatch, settings):
    """`generation` aparte y apagado a propósito (el 27B sin Consulta): el caso de T-247. Con la
    Consulta en el motor de lotes (T-255) el aviso es otro: `test_s5_consulta_motor_unico.py`."""
    settings.GENERATION_URL = "http://generation:8080"
    settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def test_the_normativas_tab_says_it_and_does_not_let_ask(client, operator_user, procedure,
                                                         engine_down):
    """REQ-107: la consulta de la pestaña de Normativas dice que no está disponible y desactiva
    el botón."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()
    assert 'id="s5-consulta-apagada"' in html and NOTICE in html
    assert 'id="s5-consulta-enviar" disabled' in html


def test_the_normativas_tab_has_no_notice_with_the_engine_up(client, operator_user, procedure):
    """REQ-107: con el motor encendido la pestaña es la de siempre."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()
    assert "s5-consulta-apagada" not in html
    assert 'id="s5-consulta-enviar" disabled' not in html
    assert 'id="s5-consulta-enviar"' in html


def test_asking_from_the_tab_with_the_engine_off_goes_back_with_the_notice(
        client, operator_user, procedure, fake_ai, engine_down):
    """REQ-107: la pregunta enviada desde la pestaña no se ejecuta ni se guarda; vuelve a la
    pestaña con el aviso."""
    log_in(client, operator_user)
    response = client.post(reverse("expedientes:s5_consultar", args=[procedure.pk]),
                           {"question": "¿Cuál es el objeto del régimen?"})
    assert response.status_code == 302
    shown = s5_consulta.unpack(response["Location"].split("aviso=")[1].split("#")[0])
    assert shown == {"ok": False, "text": services.UNAVAILABLE_NOTICE}
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.generation.calls == []
    assert NOTICE in client.get(response["Location"]).content.decode()


def test_the_notice_is_plain_language_without_internal_names():
    """El aviso es para la Comisión, en llano, sin nombres internos."""
    for word in ("generation", "Qwen", "GPU", "docker", "gguf"):
        assert word not in services.UNAVAILABLE_NOTICE
