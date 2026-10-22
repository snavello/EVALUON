"""Vista mínima del indicador de avance en el encabezado (REQ-140; T-312): solo con un pedido en
espera o en curso, con el porcentaje de la cuenta gruesa, enlazado al primer panel y con el
sondeo de `recorrido.js`. La estética final es de T-330. Todo el material es inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.tenders.models import JobStatus
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parents[2] / "evaluon"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def fragment(client, procedure):
    return client.get(reverse("expedientes:avance", args=[procedure.pk]))


def test_without_a_request_the_indicator_is_not_drawn(client, procedure, operator_user):
    """REQ-140: sin pedido, el fragmento no dibuja nada y la página trae solo el contenedor."""
    log_in(client, operator_user)
    response = fragment(client, procedure)
    assert response.status_code == 200 and "<svg" not in response.content.decode()
    assert response["Cache-Control"] == "no-store"
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    assert 'id="avance-encabezado"' in html and 'class="avance-anillo"' not in html


def test_a_running_request_draws_the_ring_with_the_percent(client, procedure, two_offers,
                                                          simulate, operator_user):
    """REQ-140: evaluando 1 de 2 ofertas, el anillo marca 50 % y enlaza al primer panel."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    html = fragment(client, procedure).content.decode()
    assert "<html" not in html and "<svg" in html
    assert "50 %" in html
    assert f'href="{reverse("expedientes:procedimiento", args=[procedure.pk])}"' in html
    assert 'stroke-dasharray="50 100"' in html


def test_the_indicator_is_in_the_header_of_every_section_with_the_poll_url(
        client, procedure, two_offers, simulate, operator_user):
    """REQ-140: en las cinco secciones el indicador está y trae `data-poll-url` para el sondeo."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    poll = reverse("expedientes:avance", args=[procedure.pk])
    for key in ("procedimiento", "pliego", "ofertas", "evaluacion", "normativas"):
        html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
        assert f'data-poll-url="{poll}"' in html, key
        assert "50 %" in html, key
        assert html.index('id="avance-encabezado"') < html.index('id="seccion-titulo"'), key


def test_a_waiting_request_shows_it_without_inventing_a_percent(client, procedure, two_offers,
                                                               simulate, operator_user):
    """REQ-140, REQ-141: en espera hay indicador, pero ninguna cifra que no se sepa."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.QUEUED)
    html = fragment(client, procedure).content.decode()
    assert "<svg" in html and "En espera" in html
    assert "%" not in html


def test_a_finished_or_failed_request_does_not_draw_the_indicator(client, procedure, two_offers,
                                                                 simulate, operator_user):
    """REQ-140: un pedido terminado o fallido ya no es un proceso en curso."""
    log_in(client, operator_user)
    for status in (JobStatus.DONE, JobStatus.FAILED):
        simulate(two_offers, status, done=2)
        assert "<svg" not in fragment(client, procedure).content.decode(), status


def test_the_fragment_of_a_missing_procedure_is_a_404(client, operator_user):
    """REQ-140: el fragmento de un procedimiento que no existe no se arma."""
    log_in(client, operator_user)
    assert client.get(reverse("expedientes:avance", args=[999999])).status_code == 404


def test_the_indicator_has_no_inline_styles_or_scripts_and_no_hexadecimal_colors():
    """Plan 017: la plantilla del indicador usa clases y atributos de presentación, sin
    `style=`, scripts en línea ni colores fijos."""
    text = (ROOT / "templates" / "journey" / "_avance_encabezado.html").read_text(
        encoding="utf-8")
    assert " style=" not in text and "<style" not in text and "<script" not in text
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text)


def test_the_poll_script_reads_the_poll_url_of_the_indicator():
    """REQ-140: `recorrido.js` sondea todo `[data-poll-url]`, también el indicador."""
    js = (ROOT / "static" / "journey" / "recorrido.js").read_text(encoding="utf-8")
    assert "[data-poll-url]" in js


def test_no_ring_in_any_section_without_a_request_in_progress(client, procedure, two_offers,
                                                             simulate, operator_user):
    """REQ-140, REQ-141 (T-336): sin pedidos en espera ni en curso (ninguno o solo terminados),
    ninguna página de sección trae el anillo; con un pedido en curso, sí."""
    log_in(client, operator_user)
    for status in (None, JobStatus.DONE):
        if status:
            simulate(two_offers, status, done=2)
        for key in ("procedimiento", "ofertas"):
            html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
            assert 'id="avance-encabezado"' in html and "avance-anillo" not in html, (key, status)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    for key in ("procedimiento", "ofertas"):
        html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
        assert "avance-anillo" in html, key
