"""Tipos de hecho nuevos de la 014 (T-193; plan 014, "Registro de auditoría"; P6)."""

import pytest
from django.db import IntegrityError, transaction

from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome

pytestmark = pytest.mark.django_db

NEW = ["document_change", "procedure_proposal", "offer_proposal", "discard_decision",
       "norm_upload", "eval_export"]


@pytest.mark.parametrize("event_type", NEW)
def test_each_new_event_type_can_be_recorded(event_type, read_write_user):
    """REQ-091, REQ-093, REQ-094, REQ-099: la base acepta cada tipo nuevo."""
    event = audit.record(event_type, outcome=Outcome.OK, channel=Channel.SCREEN,
                         user=read_write_user, detail={"huella": "x"})
    assert AuditEvent.objects.get(pk=event.pk).event_type == event_type


def test_the_new_types_are_in_the_enumeration():
    assert set(NEW) <= set(EventType.values)


def test_an_unknown_type_is_still_rejected():
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(event_type="inventado", outcome=Outcome.OK,
                                  channel=Channel.SCREEN)
