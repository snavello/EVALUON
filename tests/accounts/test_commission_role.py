"""Rol de la Comisión de los usuarios (T-068; REQ-026, REQ-027, REQ-029; plan 003,
"Roles").

El rol de la Comisión (`commission_role`) es un campo aparte del rol de la normativa
(`role`): `''` (ninguno), `operator` o `evaluator`. El evaluador puede hacer todo lo que
hace el operador; la decisión (confirmar, elegir la consecuencia, validar) queda en
manos de un evaluador. El rechazo se registra como en la 001, con el hecho `rejected`.

Los usuarios y las claves son sintéticos (P4).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction

from evaluon.accounts import permissions
from evaluon.accounts.models import CommissionRole, Role
from evaluon.accounts.permissions import RoleRejected, require_commission_role
from evaluon.audit.models import AuditEvent
from tests.conftest import TEST_PASSWORD

NEW_PASSWORD = "otra-clave-sintetica-larga"


def make_user(username, commission_role, role=Role.READ):
    return get_user_model().objects.create_user(
        username=username,
        password=TEST_PASSWORD,
        role=role,
        commission_role=commission_role,
    )


def rejections():
    return list(AuditEvent.objects.filter(event_type="rejected").order_by("pk"))


# --- Modelo ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_without_commission_role_by_default():
    """REQ-026: un usuario creado sin rol de la Comisión no tiene ninguno (`''`), y el
    rol de la normativa sigue como estaba."""
    user = get_user_model().objects.create_user(
        username="sin-comision", password=TEST_PASSWORD, role=Role.READ_WRITE
    )
    user.refresh_from_db()
    assert user.commission_role == ""
    assert user.role == Role.READ_WRITE


@pytest.mark.django_db
def test_database_rejects_unknown_commission_role():
    """REQ-026: la base no acepta un rol de la Comisión fuera de los tres valores."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_user("invalido", "presidente")


# --- Comprobación ---------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "commission_role", [CommissionRole.OPERATOR, CommissionRole.EVALUATOR]
)
def test_operator_and_evaluator_pass_where_operator_is_required(commission_role):
    """REQ-026: donde se exige operador pasan el operador y el evaluador (el evaluador
    puede hacer todo lo que hace el operador), sin hecho `rejected`."""
    user = make_user("comision", commission_role)

    require_commission_role(user, CommissionRole.OPERATOR)

    assert rejections() == []


@pytest.mark.django_db
def test_evaluator_passes_where_evaluator_is_required():
    """REQ-027, REQ-029: el evaluador pasa donde se exige evaluador."""
    user = make_user("evaluador", CommissionRole.EVALUATOR)

    require_commission_role(user, CommissionRole.EVALUATOR)

    assert rejections() == []


@pytest.mark.django_db
def test_operator_is_rejected_where_evaluator_is_required_and_recorded():
    """REQ-027, REQ-029: el operador no pasa donde se exige evaluador (la decisión es
    de un evaluador, P3); el rechazo queda como hecho `rejected` con el usuario, la
    operación, el rol exigido y el del usuario."""
    user = make_user("operador", CommissionRole.OPERATOR)

    with pytest.raises(RoleRejected):
        require_commission_role(
            user, CommissionRole.EVALUATOR, operation="validar la matriz"
        )

    [event] = rejections()
    assert event.user == user
    assert event.outcome == "rejected"
    assert event.channel == "screen"
    assert event.detail["operation"] == "validar la matriz"
    assert event.detail["required_commission_role"] == "evaluator"
    assert event.detail["user_commission_role"] == "operator"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "required", [CommissionRole.OPERATOR, CommissionRole.EVALUATOR]
)
def test_user_without_commission_role_is_rejected_and_recorded(required):
    """REQ-026: un usuario sin rol de la Comisión es rechazado, aunque tenga el rol de
    lectura y escritura de la normativa, y queda el hecho `rejected` con la función que
    pidió la comprobación como operación."""
    user = make_user("escritura-normas", "", role=Role.READ_WRITE)

    with pytest.raises(RoleRejected):
        require_commission_role(user, required)

    [event] = rejections()
    assert event.user == user
    assert event.detail["required_commission_role"] == str(required)
    assert event.detail["user_commission_role"] == ""
    assert event.detail["operation"].endswith(
        "test_user_without_commission_role_is_rejected_and_recorded"
    )


@pytest.mark.django_db
def test_inactive_evaluator_is_rejected():
    """REQ-026: un evaluador dado de baja es rechazado y queda registrado."""
    user = make_user("evaluador-baja", CommissionRole.EVALUATOR)
    user.is_active = False
    user.save()

    with pytest.raises(RoleRejected):
        require_commission_role(user, CommissionRole.OPERATOR)

    assert len(rejections()) == 1


@pytest.mark.django_db
def test_anonymous_is_rejected_without_user():
    """REQ-026: sin usuario identificado se rechaza y el hecho queda sin usuario."""
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(RoleRejected):
        require_commission_role(AnonymousUser(), CommissionRole.OPERATOR)

    [event] = rejections()
    assert event.user is None
    assert event.detail["user_commission_role"] is None


# --- crear_usuario --------------------------------------------------------------------


@pytest.fixture
def typed_passwords(monkeypatch):
    monkeypatch.setattr(permissions, "read_password", lambda prompt: NEW_PASSWORD)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rol_comision, commission_role",
    [("operador", CommissionRole.OPERATOR), ("evaluador", CommissionRole.EVALUATOR)],
)
def test_crear_usuario_with_commission_role(
    typed_passwords, rol_comision, commission_role
):
    """REQ-026: `crear_usuario --rol-comision evaluador` (u `operador`) crea el usuario
    con ese rol de la Comisión, y el hecho `user_created` lo registra."""
    call_command("crear_usuario", "ana", rol="lectura", rol_comision=rol_comision)

    user = get_user_model().objects.get(username="ana")
    assert user.commission_role == commission_role
    assert user.role == Role.READ

    event = AuditEvent.objects.get(event_type="user_created")
    assert event.detail["commission_role"] == commission_role


@pytest.mark.django_db
def test_crear_usuario_without_commission_role(typed_passwords):
    """REQ-026: sin `--rol-comision`, el usuario no tiene rol de la Comisión y el hecho
    `user_created` lo registra vacío."""
    call_command("crear_usuario", "beto", rol="lectura-escritura")

    user = get_user_model().objects.get(username="beto")
    assert user.commission_role == ""

    event = AuditEvent.objects.get(event_type="user_created")
    assert event.detail["commission_role"] == ""


@pytest.mark.django_db
def test_crear_usuario_rejects_unknown_commission_role(typed_passwords):
    """REQ-026: un rol de la Comisión que no existe no da de alta a nadie."""
    from django.core.management import CommandError

    with pytest.raises(CommandError):
        call_command("crear_usuario", "caro", rol="lectura", rol_comision="presidente")

    assert not get_user_model().objects.filter(username="caro").exists()
