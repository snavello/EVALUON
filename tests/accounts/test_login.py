"""Ingreso, página pública única y comprobación de rol (T-006, REQ-016).

Las páginas protegidas de estas pruebas son vistas definidas solo acá, sin decorador
propio: demuestran que la exigencia de sesión vale para cualquier página que se agregue,
no solo para las que existen hoy. La raíz la ocupa la pantalla de consulta (T-016).
"""

import re

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.urls import path, reverse

from evaluon import urls as project_urls
from tests.conftest import TEST_PASSWORD

ERROR_MESSAGE = "Usuario o clave incorrectos"


def protected_page(request):
    return HttpResponse("página protegida")


# Urlconf de estas pruebas: las rutas reales del proyecto más dos páginas sin decorador.
urlpatterns = project_urls.urlpatterns + [
    path("", protected_page),
    path("otra-pagina/", protected_page),
]

pytestmark = pytest.mark.urls("tests.accounts.test_login")


def login_url():
    return resolve_url(settings.LOGIN_URL)


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/", "/otra-pagina/", "/otra-pagina/?q=1"])
def test_without_session_any_page_redirects_to_login(client, url):
    """REQ-016: sin sesión iniciada, cualquier página redirige al ingreso, que pide
    usuario y clave."""
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"].startswith(login_url() + "?next=")

    login_page = client.get(response["Location"])
    assert login_page.status_code == 200
    body = login_page.content.decode()
    assert 'name="username"' in body
    assert 'name="password"' in body


@pytest.mark.django_db
def test_logout_without_session_redirects_to_login(client):
    """REQ-016: la salida también exige sesión; sin ella se va al ingreso."""
    response = client.post(reverse("accounts:logout"))

    assert response.status_code == 302
    assert response["Location"].startswith(login_url())


@pytest.mark.django_db
def test_login_page_is_public_and_only_uses_own_resources(client):
    """REQ-016: la de ingreso es la única página sin sesión. Lleva la política de
    contenido que solo permite recursos del propio servidor y no referencia
    direcciones externas (funcionamiento sin conexión)."""
    response = client.get(login_url())

    assert response.status_code == 200
    # Valor exacto: cualquier fuente o directiva de más ampliaría la política.
    assert response["Content-Security-Policy"] == "default-src 'self'"
    body = response.content.decode()
    assert not re.search(r"""(src|href|action)\s*=\s*["']?(https?:)?//""", body)
    assert "csrfmiddlewaretoken" in body
    assert "Usuario" in body and "Clave" in body


@pytest.mark.django_db
def test_login_with_valid_credentials_redirects_to_root(client, read_user):
    """REQ-016: con usuario y clave correctos se ingresa y se va a la raíz, donde está
    la pantalla de consulta."""
    response = client.post(
        login_url(), {"username": "lectura", "password": TEST_PASSWORD}
    )

    assert response.status_code == 302
    assert response["Location"] == "/"
    assert client.session["_auth_user_id"] == str(read_user.pk)
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_login_honours_next(client, read_user):
    """REQ-016: después del ingreso se vuelve a la página que se había pedido."""
    response = client.post(
        login_url() + "?next=/otra-pagina/",
        {"username": "lectura", "password": TEST_PASSWORD},
    )

    assert response.status_code == 302
    assert response["Location"] == "/otra-pagina/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "username, password",
    [
        ("lectura", "clave-equivocada-de-prueba"),
        ("no-existe", TEST_PASSWORD),
        ("inactivo", TEST_PASSWORD),
    ],
)
def test_failed_login_shows_single_message(client, read_user, username, password):
    """REQ-016: clave incorrecta, usuario inexistente o usuario dado de baja dan el
    mismo mensaje, sin decir cuál de los dos datos falló, y no inician sesión."""
    from evaluon.accounts.models import Role

    get_user_model().objects.create_user(
        username="inactivo", password=TEST_PASSWORD, role=Role.READ, is_active=False
    )

    response = client.post(login_url(), {"username": username, "password": password})

    assert response.status_code == 200
    body = response.content.decode()
    assert body.count(ERROR_MESSAGE) == 1
    assert "_auth_user_id" not in client.session
    errors = response.context["form"].non_field_errors()
    assert list(errors) == [ERROR_MESSAGE]


@pytest.mark.django_db
def test_user_model_has_role_and_no_groups(read_user, read_write_user):
    """REQ-016: cada usuario tiene uno de los dos roles; no se usan los grupos ni el
    panel de administración de Django."""
    from evaluon.accounts.models import Role

    assert {choice for choice, _ in Role.choices} == {"read", "read_write"}
    assert read_user.role == "read"
    assert read_write_user.role == "read_write"
    assert get_user_model()._meta.db_table == "accounts_user"
    assert not hasattr(read_user, "groups")
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_role_must_be_one_of_the_two(db):
    """REQ-016: la base no acepta un rol distinto de lectura o lectura y escritura."""
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        get_user_model().objects.create_user(
            username="otro", password=TEST_PASSWORD, role="admin"
        )


@pytest.mark.django_db
def test_role_check_for_business_functions(read_user, read_write_user):
    """REQ-016: lectura permite consultar y buscar; lectura y escritura además permite
    cargar y validar. La comprobación rechaza a quien no tiene el rol, a un usuario
    dado de baja y a quien no ingresó."""
    from evaluon.accounts.models import Role
    from evaluon.accounts.permissions import RoleRejected, require_role

    require_role(read_user, Role.READ)
    require_role(read_write_user, Role.READ)
    require_role(read_write_user, Role.READ_WRITE)

    with pytest.raises(RoleRejected) as excinfo:
        require_role(read_user, Role.READ_WRITE)
    assert isinstance(excinfo.value, PermissionDenied)

    read_write_user.is_active = False
    with pytest.raises(RoleRejected):
        require_role(read_write_user, Role.READ)
    with pytest.raises(RoleRejected):
        require_role(AnonymousUser(), Role.READ)
    with pytest.raises(RoleRejected):
        require_role(None, Role.READ)
