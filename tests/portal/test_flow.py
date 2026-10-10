"""Corte vertical de punta a punta con el calco y un portal de mentira, por la pantalla
(REQ-045, REQ-046, REQ-048, REQ-049; T-141). Sin red: el transporte es `FakePortal`.

Umbral del caso chico: 100 % de los datos del procedimiento, 6 de 6 renglones, nada cargado
sin aprobación, ambas decisiones con autor y fecha, el operador no aprueba el procedimiento.
"""

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.portal.models import ItemKind, ItemState, PortalItem, PortalLine
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS, Job, JobStatus, Procedure
from tests.conftest import TEST_PASSWORD
from tests.portal.fakeportal import (  # noqa: F401
    EXPECTED,
    LINK_URL,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db


def login(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def register_and_explore(client):
    response = client.post(reverse("portal:links"), {"url": LINK_URL})
    assert response.status_code == 302
    job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert job.status == JobStatus.DONE, job.error
    return response.url


def test_approve_all_is_not_offered_to_the_operator(
        client, operator_user, portal_client):
    login(client, operator_user)
    proposal_url = register_and_explore(client)
    assert "Aprobar todo" not in client.get(proposal_url).content.decode()


def test_refused_link_shows_the_reason(client, operator_user, portal_settings):
    """REQ-045: el enlace que no sirve se rechaza con su explicación en pantalla."""
    login(client, operator_user)
    response = client.post(reverse("portal:links"), {"url": "http://otro.ejemplo.test/x"})
    assert response.status_code == 200
    assert "No se puede usar ese enlace" in response.content.decode()
    assert not Job.objects.exists()


def test_user_without_commission_role_gets_403(client, no_commission_user, portal_settings):
    login(client, no_commission_user)
    assert client.get(reverse("portal:links"), follow=True).status_code == 403


def test_finish_notice_of_a_failed_exploration(client, operator_user, portal_client):
    portal_client.serve("error-pantalla.html")
    login(client, operator_user)
    client.post(reverse("portal:links"), {"url": LINK_URL})
    job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert job.status == JobStatus.FAILED
    html = client.get(reverse("portal:links"), follow=True).content.decode()
    assert "La exploración del Portal" in html and "falló" in html


def test_finish_notice_of_a_review(client, operator_user, portal_client):
    login(client, operator_user)
    register_and_explore(client)
    client.get(reverse("portal:links"), follow=True)  # ve el aviso de la exploración
    link_id = PortalItem.objects.first().proposal.link_id
    jobs.enqueue("portal_review", procedure=None, requested_by=operator_user, target_id=link_id)
    jobs.run_next(kinds=PORTAL_JOB_KINDS)
    html = client.get(reverse("portal:links"), follow=True).content.decode()
    assert "La revisión del Portal" in html
