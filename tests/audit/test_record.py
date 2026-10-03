"""Registro de auditoría: tabla `audit_event` y función de registro (T-007, REQ-012).

Un hecho registrado guarda momento, usuario, canal, resultado y detalle (plan 001,
"Modelo de datos" y "Registro de auditoría"). Solo se insertan filas.
"""

from datetime import timedelta

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
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


# --- Solo inserciones, garantizado por la base ------------------------------------


def stored_row(pk):
    return AuditEvent.objects.filter(pk=pk).values().get()


@pytest.fixture
def recorded_event(read_user):
    return services.record(
        "login", outcome="ok", channel="screen", user=read_user, detail={"a": 1}
    )


@pytest.mark.django_db
def test_queryset_update_is_rejected_by_the_database(recorded_event):
    """REQ-012: la base no admite modificar un hecho registrado con
    `QuerySet.update()`, que no pasa por `save()`; la fila queda igual."""
    before = stored_row(recorded_event.pk)

    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        AuditEvent.objects.filter(pk=recorded_event.pk).update(outcome="failed")

    assert "registro de auditoría" in str(rejected.value)
    assert stored_row(recorded_event.pk) == before


@pytest.mark.django_db
def test_bulk_update_is_rejected_by_the_database(recorded_event):
    """REQ-012: `bulk_update` tampoco modifica un hecho registrado."""
    before = stored_row(recorded_event.pk)
    recorded_event.outcome = "failed"

    with pytest.raises(DatabaseError), transaction.atomic():
        AuditEvent.objects.bulk_update([recorded_event], ["outcome"])

    assert stored_row(recorded_event.pk) == before


@pytest.mark.django_db
def test_queryset_delete_is_rejected_by_the_database(recorded_event):
    """REQ-012: la base no admite borrar un hecho registrado con `QuerySet.delete()`,
    que no pasa por `delete()` del modelo; la fila queda igual."""
    before = stored_row(recorded_event.pk)

    with pytest.raises(DatabaseError), transaction.atomic():
        AuditEvent.objects.filter(pk=recorded_event.pk).delete()

    assert stored_row(recorded_event.pk) == before


@pytest.mark.django_db
@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_event SET outcome = 'failed', detail = '{}' WHERE id = %s",
        "DELETE FROM audit_event WHERE id = %s",
    ],
)
def test_direct_sql_cannot_change_or_delete_an_event(recorded_event, sql):
    """REQ-012: ni un UPDATE ni un DELETE por SQL directo cambian o borran un hecho
    registrado; la fila queda igual."""
    before = stored_row(recorded_event.pk)

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql, [recorded_event.pk])

    assert stored_row(recorded_event.pk) == before


@pytest.mark.django_db
def test_insert_is_still_allowed_after_rejections(recorded_event):
    """REQ-012: el bloqueo es solo para modificar y borrar; agregar hechos sigue
    funcionando."""
    services.record("login_failed", outcome="failed", channel="screen", username="x")
    assert AuditEvent.objects.count() == 2


@pytest.mark.django_db
def test_deleting_a_user_with_events_does_not_reach_the_events(recorded_event):
    """REQ-012: borrar un usuario con hechos registrados no los borra en cascada: Django
    lo impide (PROTECT) y, por SQL directo, la clave foránea también; los hechos y el
    usuario quedan igual."""
    user = recorded_event.user
    before = stored_row(recorded_event.pk)

    with pytest.raises(ProtectedError), transaction.atomic():
        user.delete()

    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM accounts_user WHERE id = %s", [user.pk])
            # La clave foránea es diferida: se comprueba al cerrar la transacción.
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    assert stored_row(recorded_event.pk) == before
    assert type(user).objects.filter(pk=user.pk).exists()
