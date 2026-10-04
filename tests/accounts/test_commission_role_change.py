"""Cambio del rol de la Comisión de un usuario existente (T-088; REQ-026; plan 003,
"Roles").

El comando `rol_comision` pide la clave de quien cambia (como los demás comandos), cambia
el rol y deja el hecho `user_role_changed` con quién, el afectado, el antes y el después.
Usuarios y claves sintéticos (P4).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.accounts.models import CommissionRole, Role
from evaluon.audit.models import AuditEvent
from tests.conftest import TEST_PASSWORD


@pytest.fixture(autouse=True)
def typed_password(monkeypatch):
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)


def make_user(username, role=Role.READ_WRITE, commission_role=""):
    return get_user_model().objects.create_user(
        username=username,
        password=TEST_PASSWORD,
        role=role,
        commission_role=commission_role,
    )


def changes():
    return list(AuditEvent.objects.filter(event_type="user_role_changed"))


@pytest.mark.django_db
def test_change_records_who_target_before_and_after():
    """REQ-026: el cambio deja el hecho con quién, a quién, el valor de antes y el de
    después, por comando."""
    admin = make_user("quien-cambia")
    target = make_user("afectado", commission_role=CommissionRole.OPERATOR)

    call_command("rol_comision", "afectado", "evaluador", usuario="quien-cambia")

    target.refresh_from_db()
    assert target.commission_role == CommissionRole.EVALUATOR
    (event,) = changes()
    assert event.user == admin
    assert event.channel == "command"
    assert event.outcome == "ok"
    assert event.detail["changed_user"] == "afectado"
    assert event.detail["changed_user_id"] == target.pk
    assert event.detail["commission_role_before"] == CommissionRole.OPERATOR
    assert event.detail["commission_role_after"] == CommissionRole.EVALUATOR


@pytest.mark.django_db
def test_ninguno_removes_the_role():
    """REQ-026: `ninguno` deja al usuario sin rol de la Comisión."""
    make_user("quien-cambia")
    target = make_user("afectado", commission_role=CommissionRole.EVALUATOR)
    call_command("rol_comision", "afectado", "ninguno", usuario="quien-cambia")
    target.refresh_from_db()
    assert target.commission_role == ""
    assert changes()[0].detail["commission_role_after"] == ""


@pytest.mark.django_db
def test_same_value_is_recorded_for_regularization():
    """REQ-026: repetir el valor vigente deja el hecho igual (regularización de un
    cambio hecho antes sin registro)."""
    make_user("quien-cambia")
    make_user("afectado", commission_role=CommissionRole.EVALUATOR)
    call_command("rol_comision", "afectado", "evaluador", usuario="quien-cambia")
    (event,) = changes()
    assert event.detail["commission_role_before"] == event.detail["commission_role_after"]


@pytest.mark.django_db
def test_unknown_user_is_rejected_without_changes():
    """REQ-026: un usuario inexistente se rechaza y no queda ningún hecho de cambio."""
    make_user("quien-cambia")
    with pytest.raises(CommandError, match="No existe"):
        call_command("rol_comision", "nadie", "evaluador", usuario="quien-cambia")
    assert changes() == []


@pytest.mark.django_db
def test_invalid_value_is_rejected_without_changes():
    """REQ-026: un valor inválido se rechaza y el rol queda como estaba."""
    make_user("quien-cambia")
    target = make_user("afectado", commission_role=CommissionRole.OPERATOR)
    with pytest.raises(CommandError):
        call_command("rol_comision", "afectado", "presidente", usuario="quien-cambia")
    target.refresh_from_db()
    assert target.commission_role == CommissionRole.OPERATOR
    assert changes() == []


@pytest.mark.django_db
def test_wrong_password_changes_nothing(monkeypatch):
    """REQ-026: con clave incorrecta no se cambia nada."""
    make_user("quien-cambia")
    target = make_user("afectado")
    monkeypatch.setattr(permissions, "read_password", lambda prompt: "incorrecta-xyz")
    with pytest.raises(CommandError):
        call_command("rol_comision", "afectado", "evaluador", usuario="quien-cambia")
    target.refresh_from_db()
    assert target.commission_role == ""
    assert changes() == []


@pytest.mark.django_db
def test_read_only_user_cannot_change_roles():
    """REQ-026: quien solo tiene rol de lectura se rechaza (hecho `rejected`) y no
    cambia nada."""
    make_user("lector", role=Role.READ)
    target = make_user("afectado")
    with pytest.raises(permissions.RoleRejected):
        call_command("rol_comision", "afectado", "evaluador", usuario="lector")
    target.refresh_from_db()
    assert target.commission_role == ""
    assert changes() == []
    assert AuditEvent.objects.filter(event_type="rejected").count() == 1
