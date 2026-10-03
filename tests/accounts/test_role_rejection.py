"""Registro de las operaciones rechazadas por rol (T-038, REQ-016, REQ-012; plan 001,
"Acceso" y "Registro de auditoría").

La comprobación de rol de `permissions.require_role` registra el rechazo antes de
rechazar: el hecho `rejected` lleva el usuario, la operación intentada y el canal. Como
todas las funciones de negocio comprueban el rol con ella, cualquier operación rechazada
queda registrada sin que cada función lo haga por su cuenta.

No confundir el hecho `rejected` (`event_type`, rechazo por rol) con el resultado
`rejected` (`outcome`) de otros hechos, como una validación rechazada por claves
repetidas: las consultas filtran por `event_type`.

Los datos de prueba son sintéticos (P4).
"""

from io import StringIO

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.management import CommandError, call_command
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import path

from evaluon import urls as project_urls
from evaluon.accounts import permissions
from evaluon.accounts.models import Role
from evaluon.accounts.permissions import RoleRejected, require_role
from evaluon.audit.models import AuditEvent
from evaluon.norms.models import Document, Norm, Reading
from evaluon.norms.services import listing, loading, validation
from evaluon.queries import services as queries
from tests.conftest import TEST_PASSWORD


def rejections():
    return list(AuditEvent.objects.filter(event_type="rejected").order_by("pk"))


@pytest.fixture
def typed_input(monkeypatch):
    """Simula la clave escrita por teclado y, en `validar_informe`, la confirmación."""
    from evaluon.norms.management.commands import validar_informe

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    monkeypatch.setattr(validar_informe, "ask_confirmation", lambda prompt: "si")


@pytest.fixture
def pending_reading(make_norm, make_document, make_reading):
    document = make_document(make_norm(), in_use=False, version_number=None)
    return make_reading(document, [("art-1", "Artículo 1. Texto sintético.")],
                        status="pending", passages=False)


# Una pantalla de escritura como la que puede sumar una feature siguiente: traduce y
# llama a la función de negocio con el usuario de la sesión, sin comprobar el rol.
def write_screen(request):
    try:
        loading.load_norm(request.user, data=b"%PDF-", file_name="sintetico.pdf")
    except RoleRejected:
        return HttpResponseForbidden("Su usuario no tiene permiso.")
    return HttpResponse("cargado")


urlpatterns = project_urls.urlpatterns + [path("escritura-de-prueba/", write_screen)]


# --- Comandos ------------------------------------------------------------------------


@pytest.mark.django_db
def test_read_user_running_cargar_norma_is_rejected_and_recorded(
    typed_input, read_user, tmp_path
):
    """REQ-016, REQ-012: un usuario de lectura que corre `cargar_norma` es rechazado, no
    se incorpora nada y queda el hecho `rejected` con el usuario, la operación y el
    canal `command`."""
    synthetic = tmp_path / "sintetico.pdf"
    synthetic.write_bytes(b"%PDF- archivo sintetico")

    with pytest.raises(CommandError, match="no tiene permiso"):
        call_command(
            "cargar_norma", str(synthetic),
            "--categoria", "regimen_especifico", "--tipo", "Disposición",
            "--numero", "1", "--anio", "2099", "--organismo", "AFIP",
            "--titulo", "Norma sintética", "--nombre", "Disposición sintética 1/2099",
            "--fecha-publicacion", "2099-01-01", "--fecha-vigencia", "2099-01-02",
            "--fuente", "https://example.org/sintetica",
            usuario=read_user.username, stdout=StringIO(), stderr=StringIO(),
        )

    assert not Norm.objects.exists()
    assert not Document.objects.exists()
    assert not AuditEvent.objects.filter(event_type="load").exists()
    [event] = rejections()
    assert event.outcome == "rejected"
    assert event.channel == "command"
    assert event.user_id == read_user.pk
    assert event.username == read_user.username
    assert event.detail["operation"] == "evaluon.norms.services.loading.load_norm"
    assert event.detail["command"] == "cargar_norma"
    assert event.detail["required_role"] == Role.READ_WRITE
    assert event.detail["user_role"] == Role.READ


@pytest.mark.django_db
def test_read_user_running_validar_informe_is_rejected_and_recorded(
    typed_input, read_user, pending_reading, fake_embeddings
):
    """REQ-016, REQ-012: un usuario de lectura que corre `validar_informe` es
    rechazado, la lectura sigue pendiente y queda el hecho `rejected` con el usuario,
    la operación y el canal `command`."""
    with pytest.raises(CommandError, match="no tiene permiso"):
        call_command("validar_informe", str(pending_reading.pk),
                     usuario=read_user.username, stdout=StringIO(), stderr=StringIO())

    assert Reading.objects.get(pk=pending_reading.pk).status == "pending"
    assert fake_embeddings.calls == []
    assert not AuditEvent.objects.filter(event_type="validation").exists()
    [event] = rejections()
    assert event.outcome == "rejected"
    assert event.channel == "command"
    assert event.user_id == read_user.pk
    assert event.detail["operation"] == (
        "evaluon.norms.services.validation.reading_summary"
    )
    assert event.detail["command"] == "validar_informe"
    assert event.detail["required_role"] == Role.READ_WRITE


@pytest.mark.django_db
def test_allowed_command_leaves_no_rejection(typed_input, read_user):
    """REQ-016, REQ-012: un usuario de lectura que corre un comando de lectura no deja
    hecho `rejected`."""
    call_command("listar_normas", usuario=read_user.username, stdout=StringIO())

    assert rejections() == []


# --- Pantalla ------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.urls("tests.accounts.test_role_rejection")
def test_rejection_from_screen_is_recorded_with_screen_channel(client, read_user):
    """REQ-016, REQ-012: una pantalla que llama a una función de negocio con el usuario
    de la sesión deja, si el rol no alcanza, el hecho `rejected` con el usuario, la
    operación y el canal `screen`; no se incorpora nada."""
    client.force_login(read_user)

    response = client.post("/escritura-de-prueba/")

    assert response.status_code == 403
    assert not Norm.objects.exists()
    [event] = rejections()
    assert event.channel == "screen"
    assert event.user_id == read_user.pk
    assert event.detail["operation"] == "evaluon.norms.services.loading.load_norm"
    assert "command" not in event.detail


# --- Cualquier función de negocio ----------------------------------------------------


def _load(user, reading):
    loading.load_norm(user, data=b"%PDF-", file_name="sintetico.pdf")


def _summary(user, reading):
    validation.reading_summary(user, reading.pk)


def _validate(user, reading):
    validation.validate_reading(user, reading.pk)


def _list(user, reading):
    listing.list_norms(user)


def _report(user, reading):
    listing.reading_report(user, reading.pk)


def _ask(user, reading):
    queries.ask(user, "¿Qué plazo tiene la impugnación?")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "call, operation, who",
    [
        (_load, "evaluon.norms.services.loading.load_norm", "lectura"),
        (_summary, "evaluon.norms.services.validation.reading_summary", "lectura"),
        (_validate, "evaluon.norms.services.validation.validate_reading", "lectura"),
        (_list, "evaluon.norms.services.listing.list_norms", "anonimo"),
        (_report, "evaluon.norms.services.listing.reading_report", "anonimo"),
        (_ask, "evaluon.queries.services.ask", "anonimo"),
        (_ask, "evaluon.queries.services.ask", "de-baja"),
    ],
)
def test_every_business_function_records_its_rejection(
    read_user, pending_reading, fake_ai, call, operation, who
):
    """REQ-016, REQ-012: toda función de negocio que rechaza por rol deja el hecho
    `rejected` con la operación intentada, sin registrar la operación misma. Sin
    usuario identificado, el hecho queda sin usuario."""
    if who == "anonimo":
        user = AnonymousUser()
    else:
        user = read_user
        if who == "de-baja":
            user.is_active = False
            user.save()

    with pytest.raises(RoleRejected):
        call(user, pending_reading)

    [event] = rejections()
    assert event.outcome == "rejected"
    assert event.detail["operation"] == operation
    if who == "anonimo":
        assert event.user_id is None
        assert event.username == ""
        assert event.detail["user_role"] is None
    else:
        assert event.user_id == read_user.pk
        assert event.detail["user_role"] == Role.READ
    assert AuditEvent.objects.exclude(event_type="rejected").count() == 0


@pytest.mark.django_db
def test_explicit_operation_and_channel_override(read_user):
    """REQ-012: quien comprueba el rol puede nombrar la operación y el canal; si no, se
    toman de la función que llama y de cómo ingresó el usuario."""
    with pytest.raises(RoleRejected):
        require_role(
            read_user, Role.READ_WRITE, operation="correr_algo", channel="eval"
        )

    [event] = rejections()
    assert event.detail["operation"] == "correr_algo"
    assert event.channel == "eval"


@pytest.mark.django_db
def test_allowed_role_leaves_no_rejection(read_user, read_write_user):
    """REQ-016: un rol suficiente no deja hecho `rejected`."""
    require_role(read_user, Role.READ)
    require_role(read_write_user, Role.READ_WRITE)

    assert not AuditEvent.objects.exists()
