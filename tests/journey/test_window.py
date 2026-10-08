"""Ventana del proceso (T-187; REQ-070): el panel muestra en vivo y en lenguaje llano el paso
actual, los últimos pasos con su hora, lo hecho y lo que falta, y queda con el resumen al
terminar; viaja en el mismo bloque del sondeo. Pedido simulado, textos inventados (P4)."""

import re
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

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
    simulate(two_offers, JobStatus.FAILED, error="AIServiceError: x")
    html = block(client, procedure)
    assert 'data-window-state="failed"' in html and 'role="alert"' in html
    assert 'data-nombre="Falló"' in html


def test_failure_reason_is_plain_language(client, procedure, two_offers, simulate,
                                          operator_user):
    """REQ-070: el motivo se dice en lenguaje llano, sin tipos de error ni direcciones
    internas; el texto técnico queda en el registro del pedido."""
    log_in(client, operator_user)
    raw = "timeout: http://generation_batch:8080/v1 no respondió"
    made = simulate(two_offers, JobStatus.FAILED, error=raw)
    window = re.search(r'<section.*?id="process-window".*?</section>',
                       block(client, procedure), re.S).group(0)
    assert "el motor de IA no respondió a tiempo" in window
    for technical in ("http", "generation_batch", "8080", "timeout", "Error"):
        assert technical not in window
    made.job.refresh_from_db()
    assert made.job.error == raw
    assert "no se pudo leer el documento" in window_for_error("UnreadableFile: a.pdf")
    assert "Traceback" not in window_for_error("KeyError: 'x'")


def window_for_error(error):
    from evaluon.journey.window import plain_reason
    return plain_reason(error)


def test_active_job_wins_over_a_finished_one(procedure, two_offers, simulate):
    """REQ-070: si hay uno en curso, se muestra ese y no el último terminado."""
    simulate(two_offers, JobStatus.DONE, done=2)
    running = simulate(two_offers, JobStatus.RUNNING, done=0)
    assert window_for(procedure)["job_id"] == running.job.pk


def test_active_job_wins_over_a_newer_finished_one(procedure, two_offers, simulate):
    """REQ-070: el activo gana aunque haya uno terminado pedido después."""
    running = simulate(two_offers, JobStatus.RUNNING, done=0)
    done = simulate(two_offers, JobStatus.DONE, done=2)
    Job.objects.filter(pk=done.job.pk).update(
        requested_at=running.job.requested_at + timedelta(minutes=5))
    assert window_for(procedure)["job_id"] == running.job.pk


def test_steps_show_local_time_and_date_when_not_today():
    """REQ-070: la hora es local (Buenos Aires, UTC-3) y lleva fecha si no es de hoy."""
    from evaluon.journey.window import _steps
    now = datetime(2026, 10, 7, 18, 0, tzinfo=dt_timezone.utc)
    recent = [{"at": "2026-10-05T17:53:43+00:00", "text": "viejo"},
              {"at": "2026-10-07T17:53:43+00:00", "text": "hoy"}]
    steps = _steps(recent, now)
    assert steps[0]["time"] == "14:53:43" and steps[1]["time"] == "5/10 14:53:43"


def test_icon_is_focusable_and_name_shows_with_focus(client, procedure, two_offers, simulate,
                                                     operator_user):
    """REQ-070: el ícono recibe el foco y su nombre aparece con el foco, no solo con el mouse."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    html = block(client, procedure)
    assert re.search(r'class="pw-icon[^"]*"\s+tabindex="0"', html)
    css = (Path(__file__).resolve().parents[2] / "evaluon" / "static" / "journey"
           / "recorrido.css").read_text(encoding="utf-8")
    assert ".pw-icon:focus::after" in css and "attr(data-nombre)" in css


def test_finished_job_is_complete_for_24_hours_then_one_line(procedure, two_offers, simulate,
                                                             progress_steps):
    """REQ-070: terminado o fallido se ve completo hasta 24 h; después, una línea con fecha y
    sin pasos. En espera o en curso, siempre completo."""
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    progress_steps(made.job, STEPS, done=1, total=3, scope="Oferta 2 de 2")
    finished = timezone.now()
    Job.objects.filter(pk=made.job.pk).update(status=JobStatus.DONE, finished_at=finished)
    soon = window_for(procedure, now=finished + timedelta(hours=23))
    assert soon["state"] == "done" and soon["steps"]
    late = window_for(procedure, now=finished + timedelta(hours=25))
    local = timezone.localtime(finished)
    assert late["state"] == "old" and "steps" not in late
    assert late["last_line"] == (f"Último pedido: terminó el {local.day}/{local.month} "
                                 f"a las {local:%H:%M}")
    Job.objects.filter(pk=made.job.pk).update(status=JobStatus.RUNNING)
    assert window_for(procedure, now=finished + timedelta(days=9))["state"] == "running"


def test_window_is_in_the_page_and_in_the_polled_block(client, procedure, two_offers, simulate,
                                                       operator_user):
    """REQ-070 y REQ-067: la página y el bloque del sondeo traen la misma ventana, con los
    estilos de la guía; ningún formulario ni acción de decisión."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.RUNNING, done=1)
    page = client.get(reverse("expedientes:portada", args=[procedure.pk])).content.decode()
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
