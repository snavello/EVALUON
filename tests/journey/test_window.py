"""Ventana del proceso (T-187; REQ-070): el panel muestra en vivo y en lenguaje llano el paso
actual, los últimos pasos con su hora, lo hecho y lo que falta, y queda con el resumen al
terminar; viaja en el mismo bloque del sondeo. Pedido simulado, textos inventados (P4)."""

import re
from datetime import date
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey.window import window_for
from evaluon.tenders.models import Job, JobStatus, Procedure
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

STEPS = ["Leyendo el documento de la oferta", "Evaluando el requisito 1 de 3",
         "Una regla decidió el requisito 1: cumple"]


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def block(client, procedure):
    return client.get(reverse("journey:stages", args=[procedure.pk])).content.decode()


def test_no_job_no_window(client, operator_user):
    """REQ-070: sin pedidos no hay ventana."""
    empty = Procedure.objects.create(number="VACIO-SINTETICO", procedure_type="Prueba",
                                     subject="Procedimiento inventado sin pedidos",
                                     authorization_date=date(2026, 1, 5),
                                     created_by=operator_user)
    log_in(client, operator_user)
    assert window_for(empty) is None
    assert "process-window" not in block(client, empty)


def test_running_job_shows_step_done_left_and_recent_steps(
        client, procedure, two_offers, simulate, progress_steps, operator_user):
    """REQ-070: paso actual, oferta k de N, requisito x de y, lo que falta y los pasos con hora,
    del más nuevo al más viejo."""
    log_in(client, operator_user)
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    progress_steps(made.job, STEPS, done=1, total=3, scope="Oferta 2 de 2")
    html = block(client, procedure)
    assert 'id="process-window"' in html and 'data-window-state="running"' in html
    assert "Ahora: Oferta 2 de 2: Una regla decidió el requisito 1: cumple." in html
    assert "En esta oferta" in html and "Requisito 1 de 3" in html
    assert "Oferta 1 de 2" in html
    assert html.index("Una regla decidió") < html.index("Evaluando el requisito 1 de 3") \
        < html.index("Leyendo el documento de la oferta")
    assert len(re.findall(r'class="pw-time pw-num">\d\d:\d\d:\d\d<', html)) == 3
    data = window_for(procedure)
    assert data["main"]["left"] == 1 and data["detail"]["left"] == 2
    assert 'data-nombre="En curso"' in html


def test_waiting_job_says_waiting(client, procedure, two_offers, simulate, operator_user):
    """REQ-070: un pedido en espera se dice en espera y no inventa pasos."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.QUEUED)
    html = block(client, procedure)
    assert 'data-window-state="waiting"' in html and "en espera desde hace" in html
    assert "Todavía no hay pasos registrados." in html


def test_finished_job_stays_with_summary(client, procedure, two_offers, simulate,
                                         progress_steps, operator_user):
    """REQ-070: al terminar la ventana sigue visible con el resumen y los últimos pasos."""
    log_in(client, operator_user)
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    progress_steps(made.job, STEPS, done=1, total=3, scope="Oferta 2 de 2")
    Job.objects.filter(pk=made.job.pk).update(status=JobStatus.DONE)
    html = block(client, procedure)
    assert 'data-window-state="done"' in html and 'data-nombre="Terminado"' in html
    assert "Terminó en" in html and "Evaluando el requisito 1 de 3" in html
    assert "Ahora:" not in html


def test_failed_job_shows_reason(client, procedure, two_offers, simulate, operator_user):
    """REQ-070: la falla se resume con su motivo y se anuncia como alerta."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.FAILED, error="el motor devolvió un error")
    html = block(client, procedure)
    assert 'data-window-state="failed"' in html and 'role="alert"' in html
    assert "el motor devolvió un error" in html and 'data-nombre="Falló"' in html


def test_active_job_wins_over_a_finished_one(procedure, two_offers, simulate):
    """REQ-070: si hay uno en curso, se muestra ese y no el último terminado."""
    simulate(two_offers, JobStatus.DONE, done=2)
    running = simulate(two_offers, JobStatus.RUNNING, done=0)
    assert window_for(procedure)["job_id"] == running.job.pk


def test_window_is_in_the_page_and_in_the_polled_block(client, procedure, two_offers, simulate,
                                                       operator_user):
    """REQ-070 y REQ-067: la página y el bloque del sondeo traen la misma ventana, con los
    estilos de la guía; ningún formulario ni acción de decisión."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    page = client.get(reverse("journey:procedure", args=[procedure.pk])).content.decode()
    assert 'id="process-window"' in page and "diseno/tokens.css" in page
    assert "<form" not in block(client, procedure)


def test_window_uses_guide_tokens_and_no_external_addresses():
    """REQ-070: los estilos usan los tokens de la guía y no hay direcciones externas."""
    root = Path(__file__).resolve().parents[2] / "evaluon"
    css = (root / "static" / "journey" / "recorrido.css").read_text(encoding="utf-8")
    assert "var(--ev-icono-cumple)" in css and "var(--ev-superficie)" in css
    html = (root / "templates" / "journey" / "_window.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html


def test_window_has_no_inline_styles_or_handlers(client, procedure, two_offers, simulate,
                                                 operator_user):
    """REQ-070: la política de contenido solo admite el propio servidor; la ventana no usa
    estilos ni manejadores en línea."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    html = block(client, procedure)
    assert not re.search(r"\sstyle\s*=", html) and "<style" not in html
    assert not re.search(r"\son[a-z]+\s*=", html)
