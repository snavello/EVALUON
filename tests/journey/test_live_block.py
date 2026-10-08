"""Bloque de etapas del sondeo (REQ-067): cambia sin recargar y avisa al terminar o fallar."""

from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.tenders.models import Job, JobStatus
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import make_run

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parents[2] / "evaluon" / "static" / "journey"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def block(client, procedure):
    return client.get(reverse("journey:stages", args=[procedure.pk]))


def test_the_block_goes_from_in_progress_to_ready_without_the_full_page(
        client, procedure, two_offers, simulate, operator_user):
    """REQ-067: el bloque pasa de "en curso" a "lista" cuando el pedido termina, y es solo el
    bloque (no la página completa)."""
    log_in(client, operator_user)
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    first = block(client, procedure)
    assert first.status_code == 200
    html = first.content.decode()
    assert 'data-stage="evaluacion" data-state="en_curso"' in html and "1 de 2" in html
    assert "<html" not in html and "site-header" not in html
    Job.objects.filter(pk=made.job.pk).update(status=JobStatus.DONE)
    make_run(made.request, two_offers[1], made.request.matrix_version)
    second = block(client, procedure).content.decode()
    assert 'data-stage="evaluacion" data-state="lista"' in second


def test_the_block_shows_the_reason_of_a_failure(client, procedure, two_offers, simulate,
                                                 operator_user):
    """REQ-067: una falla se ve con su motivo, también en el atributo que lee el aviso."""
    log_in(client, operator_user)
    simulate(two_offers, JobStatus.FAILED, error="el motor devolvió un error")
    html = block(client, procedure).content.decode()
    assert 'data-stage="evaluacion" data-state="con_error"' in html
    assert html.count("el motor devolvió un error") >= 2


def test_the_block_does_not_mark_notices_as_seen(client, procedure, two_offers, simulate,
                                                 evaluator_user):
    """REQ-067: pedir el bloque no consume el aviso de fin de quien pidió el trabajo."""
    log_in(client, evaluator_user)
    made = simulate(two_offers, JobStatus.DONE, done=2)
    assert made.job.seen_at is None
    block(client, procedure)
    block(client, procedure)
    made.job.refresh_from_db()
    assert made.job.seen_at is None


def test_the_page_has_the_status_region_and_polls_the_block(client, procedure, operator_user):
    """REQ-067: la página trae el bloque, la región de aviso y la dirección del sondeo."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:procedimiento", args=[procedure.pk])
                      ).content.decode()
    assert 'role="status"' in html
    assert reverse("expedientes:barra", args=[procedure.pk]) in html
    assert "journey/recorrido.js" in html and "journey/recorrido.css" in html


def test_the_script_polls_every_5_seconds_and_never_reloads():
    """REQ-067: intervalo de 5000 ms (no más de 10 s) y ninguna recarga de la página."""
    script = (STATIC / "recorrido.js").read_text(encoding="utf-8")
    assert "INTERVAL_MS = 5000" in script
    for forbidden in ("location.reload", "location.href", "location.assign"):
        assert forbidden not in script
    assert "document.hidden" in script
    assert "fetch(" in script
