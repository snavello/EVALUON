"""Registrar el enlace del proceso (REQ-045; T-141; plan 012, "Flujo, paso 1")."""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.portal.models import PortalLink
from evaluon.portal.services import links
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.portal.fakeportal import LINK_URL, portal_settings  # noqa: F401
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db


def test_valid_link_is_saved_and_queues_the_exploration(operator_user, portal_settings):
    """REQ-045: el enlace válido queda registrado y se encola portal_explore sin procedimiento."""
    link = links.register_link(operator_user, LINK_URL)
    assert PortalLink.objects.get().url == LINK_URL
    job = Job.objects.get()
    assert (job.kind, job.status, job.procedure_id, job.target_id) == (
        JobKind.PORTAL_EXPLORE, JobStatus.QUEUED, None, link.pk)
    assert job.requested_by == operator_user
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_LINK)
    assert event.outcome == Outcome.OK
    assert event.user == operator_user
    assert event.detail["url"] == LINK_URL


@pytest.mark.parametrize("url, reason", [
    ("https://otro.ejemplo.test/PLIEGO/VistaPreviaPliegoCiudadano.aspx?qs=x", "otro sitio"),
    ("http://portal.ejemplo.test/PLIEGO/VistaPreviaPliegoCiudadano.aspx?qs=x", "HTTP"),
    ("https://portal.ejemplo.test/PLIEGO/VistaPreviaPliegoCiudadano.aspx", "sin qs"),
    ("https://portal.ejemplo.test/otra/pagina.aspx?qs=x", "no es la página del proceso"),
    ("", "vacío"),
])
def test_bad_link_is_refused_with_an_explanation_and_a_fact(
        operator_user, portal_settings, url, reason):
    """REQ-045: se rechaza y se explica por qué; no se guarda nada; queda el hecho fallido."""
    with pytest.raises(links.LinkRefused) as refused:
        links.register_link(operator_user, url)
    assert str(refused.value)
    assert not PortalLink.objects.exists()
    assert not Job.objects.exists()
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_LINK)
    assert event.outcome == Outcome.FAILED
    assert event.detail["reason"] == str(refused.value)


def test_repeated_link_is_refused(operator_user, portal_settings):
    """REQ-045: un proceso ya registrado no se registra otra vez."""
    links.register_link(operator_user, LINK_URL)
    with pytest.raises(links.LinkRefused, match="ya está registrado"):
        links.register_link(operator_user, LINK_URL)
    assert PortalLink.objects.count() == 1
    assert Job.objects.count() == 1


def test_user_without_commission_role_is_rejected(no_commission_user, portal_settings):
    """REQ-045, P6: sin rol de la Comisión no se registra y queda el hecho rejected."""
    with pytest.raises(RoleRejected):
        links.register_link(no_commission_user, LINK_URL)
    assert not PortalLink.objects.exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 1


def test_stop_following_and_list(operator_user, portal_settings):
    """REQ-045: dejar de seguir cambia el enlace y deja el hecho; la lista muestra el pedido."""
    link = links.register_link(operator_user, LINK_URL)
    (row,) = links.list_links(operator_user)
    assert row.link == link and row.last_job.kind == JobKind.PORTAL_EXPLORE
    assert row.pending == 0
    links.stop_following(operator_user, link.pk)
    link.refresh_from_db()
    assert link.following is False
    assert AuditEvent.objects.filter(
        event_type=EventType.PORTAL_LINK, detail__action="dejar_de_seguir").count() == 1
