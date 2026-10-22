"""Indicador de avance del encabezado con la estética nueva (REQ-140; T-330): anillo con el
porcentaje global, o giro sin porcentaje cuando no se sabe, enlazado al primer panel y sondeado
cada 5 s (REQ-067, D-9). Todo el material es inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey.views.avance import avance_of
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.test_window import make_job

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parents[2] / "evaluon" / "static" / "journey"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def fragment(client, procedure):
    return client.get(reverse("expedientes:avance", args=[procedure.pk])).content.decode()


def test_the_ring_shows_the_overall_percent_not_only_finished_offers(
        client, procedure, two_offers, simulate, progress_steps, operator_user):
    """REQ-140: una oferta hecha y la otra en el requisito 14 de 23 marca 80 %, no 50 %: el
    indicador se mueve durante la primera oferta."""
    log_in(client, operator_user)
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    progress_steps(made.job, ["Evaluando el requisito 14 de 23"], done=14, total=23,
                   scope="Oferta 2 de 2")
    assert avance_of(procedure)["percent"] == 80
    html = fragment(client, procedure)
    assert "80 %" in html and 'stroke-dasharray="80 100"' in html
    assert "50 %" not in html


def test_the_ring_is_lime_with_an_ink_outline_for_the_light_theme(
        client, procedure, two_offers, simulate, operator_user):
    """REQ-133, REQ-140: el valor del anillo es lima y lleva un contorno --ink debajo (en el tema
    gris y blanco el lima solo no se distingue del fondo)."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    html = fragment(client, procedure)
    assert 'class="anillo-borde"' in html and 'class="anillo-valor"' in html
    assert html.index("anillo-borde") < html.index("anillo-valor")


@pytest.mark.parametrize("kind_name", ["PROPOSE_MATRIX", "READ_DOCUMENT", "PORTAL_EXPLORE"])
def test_a_request_without_a_total_spins_and_shows_no_percent(client, procedure, operator_user,
                                                              kind_name):
    """REQ-140 (D-10): sin total, el anillo gira (sin valor) y el texto dice la tarea, no un %."""
    log_in(client, operator_user)
    make_job(procedure, operator_user, getattr(JobKind, kind_name))
    assert avance_of(procedure)["percent"] is None
    html = fragment(client, procedure)
    assert "anillo-giro" in html and "anillo-valor" not in html
    assert "%" not in html
    assert "En curso" in html


def test_a_waiting_request_spins_with_the_word_waiting(client, procedure, two_offers, simulate,
                                                      operator_user):
    """REQ-140, REQ-141: en espera el anillo no marca nada y dice «En espera»."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.QUEUED)
    html = fragment(client, procedure)
    assert "En espera" in html and "%" not in html and "anillo-valor" not in html


def test_the_indicator_links_to_the_first_panel_and_names_the_task(
        client, procedure, two_offers, simulate, operator_user):
    """REQ-140: el indicador es un enlace al primer panel, con el nombre accesible completo."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    html = fragment(client, procedure)
    assert f'href="{reverse("expedientes:procedimiento", args=[procedure.pk])}"' in html
    assert re.search(r'aria-label="Evaluando las ofertas: 50 % hecho\. Ver el primer panel"', html)


def test_no_indicator_without_an_active_request(client, procedure, two_offers, simulate,
                                                operator_user):
    """REQ-140: terminado o fallido, el encabezado no dibuja nada."""
    log_in(client, operator_user)
    for status in (JobStatus.DONE, JobStatus.FAILED):
        simulate(two_offers, status, done=2)
        assert avance_of(procedure) is None
        assert "<svg" not in fragment(client, procedure)
    Job.objects.all().delete()
    assert avance_of(procedure) is None


def test_the_poll_interval_is_10_seconds_or_less():
    """REQ-140, REQ-067, D-9: `recorrido.js` sondea cada 5 s, dentro de los 10 s."""
    js = (STATIC / "recorrido.js").read_text(encoding="utf-8")
    interval = int(re.search(r"INTERVAL_MS\s*=\s*(\d+)", js).group(1))
    assert interval <= 10000


def test_the_indicator_styles_moved_to_avance_css_and_respect_reduced_motion():
    """REQ-140: los estilos del anillo están en `avance.css`, con tokens y sin movimiento cuando
    el equipo pide reducirlo."""
    css = (STATIC / "avance.css").read_text(encoding="utf-8")
    sin = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert ".avance-enc" in sin and ".anillo-giro" in sin and ".anillo-borde" in sin
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sin)
    assert "prefers-reduced-motion" in sin
    assert ".avance-enc" not in (STATIC / "camino.css").read_text(encoding="utf-8")
