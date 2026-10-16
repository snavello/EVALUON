"""Hecho `external_request` del uso externo (T-288; plan 016, "Modelo de datos"; ADR-0068; P6)."""

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome

pytestmark = pytest.mark.django_db

DETAIL = {
    "proveedor": "anthropic", "modelo": "claude-sonnet-5-5", "etapa": "verificador",
    "modo": "lotes", "resultado": "ok", "costo_usd": 0.0123,
    "uso": {"entrada": 3000, "salida": 600, "escritura_cache": 0, "lectura_cache": 0},
}


@pytest.fixture
def external_event():
    return audit.record("external_request", outcome=Outcome.OK, channel=Channel.EVAL,
                        detail=DETAIL)


def test_the_external_request_type_exists_and_fits_the_column():
    """REQ-122: el valor permitido existe y entra en la columna del tipo de hecho."""
    assert EventType.EXTERNAL_REQUEST == "external_request"
    assert "external_request" in EventType.values
    assert len("external_request") <= AuditEvent._meta.get_field("event_type").max_length


def test_an_external_request_is_recorded_with_its_detail(external_event):
    """REQ-122: un pedido externo queda como hecho, con su detalle intacto (P6)."""
    stored = AuditEvent.objects.get(pk=external_event.pk)
    assert stored.event_type == "external_request"
    assert stored.detail == DETAIL


def test_the_cost_of_the_requests_can_be_summed_from_the_detail(external_event):
    """REQ-122: el libro suma `detail.costo_usd` con una consulta sobre el JSON (ADR-0068)."""
    audit.record("external_request", outcome=Outcome.OK, channel=Channel.EVAL,
                 detail={**DETAIL, "costo_usd": 0.5})
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT sum((detail->>'costo_usd')::numeric) FROM audit_event "
            "WHERE event_type = 'external_request'")
        (total,) = cursor.fetchone()
    assert float(total) == pytest.approx(0.5123)


@pytest.mark.parametrize("sql", [
    "UPDATE audit_event SET detail = '{}' WHERE id = %s",
    "UPDATE audit_event SET outcome = 'failed' WHERE id = %s",
    "DELETE FROM audit_event WHERE id = %s",
])
def test_the_trigger_prevents_editing_or_deleting_an_external_request(external_event, sql):
    """REQ-122: el disparador de solo inserción sigue vigente para el tipo nuevo."""
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql, [external_event.pk])
    assert AuditEvent.objects.get(pk=external_event.pk).detail == DETAIL


def test_the_model_refuses_to_edit_or_delete_an_external_request(external_event):
    """REQ-122: tampoco desde el modelo."""
    external_event.detail = {}
    with pytest.raises(ValueError):
        external_event.save()
    with pytest.raises(ValueError):
        external_event.delete()


def test_an_unknown_type_is_still_rejected():
    """REQ-122: el valor nuevo no abrió la restricción a cualquier tipo."""
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.create(event_type="external_inventado", outcome=Outcome.OK,
                                  channel=Channel.EVAL)
