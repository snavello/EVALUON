"""Disparo de la revisión periódica (REQ-050; ADR-0033; T-144). Reloj falso, sin red."""

from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType
from evaluon.portal.management.commands.procesar_portal import Command
from evaluon.portal.models import PortalLink
from evaluon.portal.services import links, schedule
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.conftest import TEST_PASSWORD
from tests.portal.fakeportal import (  # noqa: F401
    LINK_URL,
    explore_link,
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

BA = ZoneInfo("America/Argentina/Buenos_Aires")
MONDAY_8 = datetime(2026, 10, 5, 8, 0, tzinfo=BA)  # 2026-10-05 es lunes


def reviews():
    return Job.objects.filter(kind=JobKind.PORTAL_REVIEW)


@pytest.fixture
def link(operator_user, portal_settings):
    link = links.register_link(operator_user, LINK_URL)
    Job.objects.all().update(status=JobStatus.DONE)  # la exploración ya se atendió
    return link


def test_a_review_is_queued_on_a_working_day_after_the_hour(link, operator_user):
    """REQ-050: lunes, después de las 7:00: una revisión, pedida a nombre de quien registró."""
    (job,) = schedule.enqueue_due(MONDAY_8)
    assert job.kind == JobKind.PORTAL_REVIEW and job.target_id == link.pk
    assert job.requested_by == operator_user and job.status == JobStatus.QUEUED
    link.refresh_from_db()
    assert link.last_review_on == MONDAY_8.date()
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_LINK,
                                     detail__action="revisar").count() == 1


def test_no_review_on_a_weekend_or_before_the_hour(link):
    """REQ-050: sábado, domingo y antes de las 7:00 no se revisa."""
    for moment in (datetime(2026, 10, 3, 9, 0, tzinfo=BA), datetime(2026, 10, 4, 9, 0, tzinfo=BA),
                   datetime(2026, 10, 5, 6, 59, tzinfo=BA)):
        assert schedule.enqueue_due(moment) == []
    assert not reviews().exists()


def test_the_review_hour_uses_the_application_time_zone(link):
    """7:00 de Buenos Aires son las 10:00 UTC: un reloj en UTC se convierte antes de comparar."""
    utc = ZoneInfo("UTC")
    assert schedule.enqueue_due(datetime(2026, 10, 5, 9, 30, tzinfo=utc)) == []
    assert len(schedule.enqueue_due(datetime(2026, 10, 5, 10, 0, tzinfo=utc))) == 1


def test_a_link_already_reviewed_today_is_not_reviewed_again(link):
    """REQ-050: una sola revisión por día, aunque el pedido ya se haya atendido."""
    (job,) = schedule.enqueue_due(MONDAY_8)
    Job.objects.filter(pk=job.pk).update(status=JobStatus.DONE)
    assert schedule.enqueue_due(MONDAY_8.replace(hour=15)) == []
    assert len(schedule.enqueue_due(datetime(2026, 10, 6, 7, 0, tzinfo=BA))) == 1


def test_a_link_without_following_or_with_a_pending_job_is_skipped(link):
    """ADR-0033: sin seguimiento no se revisa; con un pedido en espera no se apila otro."""
    Job.objects.filter(pk=Job.objects.get().pk).update(status=JobStatus.QUEUED)
    assert schedule.enqueue_due(MONDAY_8) == []
    Job.objects.all().update(status=JobStatus.DONE)
    PortalLink.objects.filter(pk=link.pk).update(following=False)
    assert schedule.enqueue_due(MONDAY_8) == []


def test_review_now_does_not_pile_up_requests(link, operator_user):
    """REQ-050: «Revisar ahora» encola una revisión; pulsarlo de nuevo no apila otra."""
    first, created = schedule.review_now(operator_user, link.pk, now=MONDAY_8)
    again, created_again = schedule.review_now(operator_user, link.pk, now=MONDAY_8)
    assert created and not created_again and first.pk == again.pk
    assert reviews().count() == 1
    assert first.requested_by == operator_user


def test_review_now_needs_a_commission_role(link, no_commission_user):
    """P6: sin rol de la Comisión no se pide la revisión."""
    with pytest.raises(RoleRejected):
        schedule.review_now(no_commission_user, link.pk)
    assert not reviews().exists()


def test_the_command_queues_the_daily_review_with_a_fake_clock(link, monkeypatch, portal_client):
    """ADR-0033: `procesar_portal` encola la revisión en cada vuelta, con el reloj inyectado."""
    monkeypatch.setattr(Command, "clock", staticmethod(lambda: MONDAY_8))
    out = StringIO()
    call_command("procesar_portal", "--hasta-vaciar", stdout=out)
    assert reviews().count() == 1
    assert "Revisión pedida" in out.getvalue()
    assert reviews().get().status in (JobStatus.DONE, JobStatus.FAILED)
