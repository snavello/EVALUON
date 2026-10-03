"""Registro de auditoría: tabla `audit_event` y función de registro (T-007, REQ-012).

Un hecho registrado guarda momento, usuario, canal, resultado y detalle (plan 001,
"Modelo de datos" y "Registro de auditoría"). Solo se insertan filas.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from evaluon.audit import services
from evaluon.audit.models import AuditEvent


@pytest.mark.django_db
def test_recorded_event_keeps_moment_user_channel_outcome_and_detail(read_user):
    """REQ-012: un hecho registrado guarda momento, usuario, canal, resultado y detalle,
    y se lee igual desde la base."""
    before = timezone.now()
    event = services.record(
        "query",
        outcome="ok",
        channel="screen",
        user=read_user,
        detail={"question": "¿Qué plazo tiene la impugnación?", "units": ["art-5"]},
    )
    after = timezone.now()

    stored = AuditEvent.objects.get(pk=event.pk)
    assert before - timedelta(seconds=1) <= stored.occurred_at <= after
    assert stored.event_type == "query"
    assert stored.outcome == "ok"
    assert stored.channel == "screen"
    assert stored.user_id == read_user.pk
    assert stored.username == read_user.username
    assert stored.detail == {
        "question": "¿Qué plazo tiene la impugnación?",
        "units": ["art-5"],
    }


@pytest.mark.django_db
def test_table_is_audit_event_with_plan_columns():
    """REQ-012: la tabla se llama `audit_event` y tiene las columnas del plan."""
    assert AuditEvent._meta.db_table == "audit_event"
    with connection.cursor() as cursor:
        columns = {
            c.name for c in connection.introspection.get_table_description(
                cursor, "audit_event"
            )
        }
    assert {
        "id",
        "occurred_at",
        "event_type",
        "outcome",
        "channel",
        "user_id",
        "username",
        "corpus_version",
        "detail",
    } <= columns


@pytest.mark.django_db
def test_event_without_acting_user_keeps_username_as_written():
    """REQ-012: un hecho sin usuario (por ejemplo, un ingreso fallido) guarda el nombre
    tal como se escribió; `corpus_version` queda vacío hasta T-008."""
    event = services.record(
        "login_failed", outcome="failed", channel="command", username="no-existe"
    )

    stored = AuditEvent.objects.get(pk=event.pk)
    assert stored.user is None
    assert stored.username == "no-existe"
    assert stored.detail == {}
    assert stored.corpus_version is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field, value",
    [("event_type", "otro"), ("outcome", "quizas"), ("channel", "correo")],
)
def test_values_outside_the_plan_are_not_saved(field, value):
    """REQ-012: tipo de hecho, resultado y canal solo admiten los valores del plan."""
    values = {"event_type": "query", "outcome": "ok", "channel": "screen"}
    values[field] = value
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(**values)


@pytest.mark.django_db
def test_recorded_event_cannot_be_changed_or_deleted(read_user):
    """REQ-012: solo se insertan filas; un hecho registrado no se modifica ni se borra."""
    event = services.record("login", outcome="ok", channel="screen", user=read_user)

    event.outcome = "failed"
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()

    stored = AuditEvent.objects.get(pk=event.pk)
    assert stored.outcome == "ok"
