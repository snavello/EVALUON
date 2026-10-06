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


def test_from_link_to_loaded_procedure_through_the_screen(
        client, operator_user, evaluator_user, portal_client):
    """El circuito: enlace, exploración, propuesta, aprobar una parte y rechazar otra."""
    login(client, operator_user)
    proposal_url = register_and_explore(client)

    # Nada se carga solo con explorar.
    assert not Procedure.objects.exists() and not PortalLine.objects.exists()

    # El operador ve la propuesta pero no puede aprobar el procedimiento.
    page = client.get(proposal_url)
    assert page.status_code == 200
    html = page.content.decode()
    assert EXPECTED["procedimiento"]["numero"] in html
    assert "Este ítem lo aprueba un evaluador." in html
    procedure_item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    lines_item = PortalItem.objects.get(kind=ItemKind.RENGLONES)
    denied = client.post(reverse("portal:decide", args=[procedure_item.proposal.link_id]),
                         {"decision": "aprobar", "item": [procedure_item.pk],
                          f"fecha_{procedure_item.pk}": "2025-11-14"})
    assert denied.status_code == 403
    assert not Procedure.objects.exists()

    # El evaluador ve el texto dañado marcado y la fecha candidata, y decide.
    client.logout()
    login(client, evaluator_user)
    html = client.get(proposal_url).content.decode()
    assert '<mark class="damaged">' in html
    assert 'value="2025-11-14"' in html
    decide_url = reverse("portal:decide", args=[procedure_item.proposal.link_id])
    approved = client.post(decide_url, {"decision": "aprobar", "item": [procedure_item.pk],
                                        f"fecha_{procedure_item.pk}": "2025-11-14"})
    assert approved.status_code == 200
    rejected = client.post(decide_url, {"decision": "rechazar", "item": [lines_item.pk]})
    assert rejected.status_code == 200

    # Solo se cargó lo aprobado.
    procedure = Procedure.objects.get()
    assert procedure.number == EXPECTED["procedimiento"]["numero"]
    assert str(procedure.authorization_date) == "2025-11-14"
    assert not PortalLine.objects.exists()

    # Ambas decisiones con autor y fecha.
    procedure_item.refresh_from_db()
    lines_item.refresh_from_db()
    assert (procedure_item.state, lines_item.state) == (ItemState.CARGADO, ItemState.RECHAZADO)
    for item in (procedure_item, lines_item):
        assert item.decided_by == evaluator_user and item.decided_at is not None
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION).count() == 2


def test_approve_all_loads_the_six_lines(client, operator_user, evaluator_user, portal_client):
    """Aprobar todo carga el procedimiento y los 6 renglones con su cantidad."""
    login(client, operator_user)
    proposal_url = register_and_explore(client)
    client.logout()
    login(client, evaluator_user)
    procedure_item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    link_id = procedure_item.proposal.link_id
    response = client.post(reverse("portal:decide", args=[link_id]),
                           {"decision": "aprobar_todo",
                            f"fecha_{procedure_item.pk}": "2025-11-14"})
    assert response.status_code == 200
    assert PortalLine.objects.count() == 6
    assert sorted(int(l.quantity) for l in PortalLine.objects.all()) == sorted(
        w["cantidad"] for w in EXPECTED["renglones"])
    html = client.get(proposal_url).content.decode()
    assert "Cargado" in html and "decidido por" in html


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
    assert client.get(reverse("portal:links")).status_code == 403


def test_finish_notice_for_a_job_without_procedure(client, operator_user, portal_client):
    """Los avisos de fin sirven para pedidos del Portal, que no tienen procedimiento."""
    login(client, operator_user)
    proposal_url = register_and_explore(client)
    html = client.get(reverse("portal:links")).content.decode()
    assert "La exploración del Portal" in html and "terminó" in html
    assert proposal_url in html
    # Se muestra una sola vez.
    assert "La exploración del Portal" not in client.get(reverse("portal:links")).content.decode()


def test_finish_notice_of_a_failed_exploration(client, operator_user, portal_client):
    portal_client.serve("error-pantalla.html")
    login(client, operator_user)
    client.post(reverse("portal:links"), {"url": LINK_URL})
    job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert job.status == JobStatus.FAILED
    html = client.get(reverse("portal:links")).content.decode()
    assert "La exploración del Portal" in html and "falló" in html


def test_finish_notice_of_a_review(client, operator_user, portal_client):
    login(client, operator_user)
    register_and_explore(client)
    client.get(reverse("portal:links"))  # ve el aviso de la exploración
    link_id = PortalItem.objects.first().proposal.link_id
    jobs.enqueue("portal_review", procedure=None, requested_by=operator_user, target_id=link_id)
    jobs.run_next(kinds=PORTAL_JOB_KINDS)
    html = client.get(reverse("portal:links")).content.decode()
    assert "La revisión del Portal" in html
