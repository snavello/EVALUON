"""Las pantallas anteriores redirigen a su pestaña y la entrada lleva al último procedimiento
(REQ-075, REQ-100; T-219). Material inventado (P4)."""

import re

import pytest
from django.urls import reverse

from evaluon.accounts.models import CommissionRole
from evaluon.journey.views.inicio import COOKIE
from evaluon.offers.models import Offer
from evaluon.portal.models import PortalLink
from evaluon.tenders.models import Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.portal.fakeportal import LINK_URL, portal_settings  # noqa: F401

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(key, procedure):
    return reverse(f"expedientes:{key}", args=[procedure.pk])


def test_every_old_reading_page_redirects_to_its_tab(client, procedure, matrix, offer,
                                                      operator_user):
    """REQ-075: cada página de lectura anterior redirige a la pestaña equivalente."""
    log_in(client, operator_user)
    link = PortalLink.objects.create(url=LINK_URL, created_by=operator_user)
    expected = {
        reverse("tenders:procedures"): reverse("inicio"),
        reverse("tenders:procedure", args=[procedure.pk]): tab("pliego", procedure),
        reverse("tenders:matrix", args=[matrix.version.pk]): tab("pliego", procedure),
        reverse("offers:procedure_offers", args=[procedure.pk]): tab("ofertas", procedure),
        reverse("offers:offer", args=[offer.pk]): tab("ofertas", procedure),
        reverse("assessment:matrix", args=[procedure.pk]): tab("evaluacion", procedure),
        reverse("assessment:questions", args=[procedure.pk]): tab("evaluacion", procedure),
        reverse("portal:links"): reverse("expedientes:nuevo"),
        reverse("portal:proposal", args=[link.pk]):
            reverse("expedientes:nuevo_enlace", args=[link.pk]),
        reverse("journey:index"): reverse("inicio"),
        reverse("journey:procedure", args=[procedure.pk]): tab("procedimiento", procedure),
    }
    for old, new in expected.items():
        response = client.get(old)
        assert response.status_code == 302, old
        assert response["Location"] == new, old


def test_old_page_of_a_missing_object_is_a_404(client, operator_user):
    """REQ-075: una página vieja de un objeto que no existe no redirige a ningún lado."""
    log_in(client, operator_user)
    for name in ("tenders:matrix", "offers:offer", "portal:proposal"):
        assert client.get(reverse(name, args=[999999])).status_code == 404, name


def test_actions_keep_working_after_the_redirect(client, procedure, operator_user):
    """REQ-075: las rutas de acción (POST) se conservan; un envío rechazado vuelve marcado."""
    log_in(client, operator_user)
    for url in (reverse("tenders:procedures"),
                reverse("offers:procedure_offers", args=[procedure.pk]),
                reverse("portal:links")):
        response = client.post(url, {})
        assert response.status_code == 200, url
        assert "Salir" in response.content.decode()
    assert Offer.objects.filter(procedure=procedure).count() == 0


def test_entering_without_procedures_opens_the_new_procedure_screen(client, operator_user):
    """REQ-075: sin procedimientos, la entrada lleva a «Nuevo procedimiento»."""
    Procedure.objects.all().delete()
    log_in(client, operator_user)
    response = client.get("/")
    assert response.status_code == 302 and response["Location"] == reverse("expedientes:nuevo")


def test_entering_opens_the_last_procedure_the_user_opened(client, procedure, operator_user):
    """REQ-075: sin historia, el más reciente; después, el último que abrió el usuario."""
    older = procedure
    newer = Procedure.objects.create(number="PRUEBA-9/2026", subject="Otro objeto inventado",
                                     authorization_date=older.authorization_date,
                                     created_by=operator_user)
    log_in(client, operator_user)
    assert client.get("/")["Location"] == tab("procedimiento", newer)
    assert client.get(tab("pliego", older)).status_code == 200
    assert client.cookies[COOKIE.format(operator_user.pk)].value == str(older.pk)
    assert client.get("/")["Location"] == tab("procedimiento", older)
    client.cookies[COOKIE.format(operator_user.pk)] = "999999"
    assert client.get("/")["Location"] == tab("procedimiento", newer)


def test_login_lands_on_the_procedure_and_honours_next(client, procedure, operator_user):
    """REQ-075: al ingresar se llega al procedimiento; el `next` válido se respeta."""
    data = {"username": operator_user.username, "password": TEST_PASSWORD}
    response = client.post(reverse("accounts:login"), data)
    assert response["Location"] == "/"
    assert client.get("/")["Location"] == tab("procedimiento", procedure)
    client.logout()
    response = client.post(reverse("accounts:login"), {**data, "next": tab("ofertas", procedure)})
    assert response["Location"] == tab("ofertas", procedure)
    client.logout()
    response = client.post(reverse("accounts:login"), {**data, "next": "https://ajeno.example/"})
    assert response["Location"] == "/"


def test_login_page_has_the_visual_guide_and_no_old_menu(client):
    """REQ-100: el ingreso carga la guía visual y trae usuario y clave sin menú."""
    html = client.get(reverse("accounts:login")).content.decode()
    assert "diseno/tokens.css" in html and "journey/secciones.css" in html
    assert 'class="top"' in html and 'class="panel"' in html
    assert "Recorrido" not in html and "Importar del Portal" not in html
    html = client.post(reverse("accounts:login"), {"username": "x", "password": "y"}
                       ).content.decode()
    assert "Usuario o clave incorrectos" in html


@pytest.mark.parametrize("url_name", ["queries:screen", "expedientes:index", "inicio"])
def test_one_header_without_the_old_menu_on_every_page(client, procedure, operator_user,
                                                       url_name):
    """REQ-100: un solo encabezado (EVALUON, desplegable, usuario y Salir); sin menú viejo."""
    log_in(client, operator_user)
    response = client.get(reverse(url_name), follow=True)
    html = response.content.decode()
    header = html[html.index('<header class="top"'):html.index("</header>")]
    for old in ("Recorrido", "Importar del Portal", "Procedimientos<", 'class="site-nav"'):
        assert old not in header
    assert "EVALUON" in header and "Cambiar de procedimiento" in header
    assert operator_user.username in header and "Salir" in header
    assert "+ Nuevo procedimiento" in header and procedure.number in header
    assert html.count('<header class="top"') == 1


def test_no_tab_links_to_an_old_reading_page(client, procedure, matrix, offer, operator_user):
    """REQ-100: ningún enlace de las pestañas apunta a una página vieja de lectura."""
    log_in(client, operator_user)
    old = re.compile(
        r'href="(/procedimientos/(\d+/)?(#[^"]*)?|/procedimientos/matrices/\d+/|'
        r'/ofertas/(\d+/|procedimiento/\d+/)|/evaluacion/procedimiento/\d+/(preguntas/)?|'
        r'/importar/(\d+/)?|/recorrido/(\d+/)?)(#[^"]*)?"')
    for key in ("procedimiento", "pliego", "ofertas", "evaluacion", "normativas"):
        html = client.get(tab(key, procedure)).content.decode()
        assert not old.findall(html), (key, old.findall(html)[:3])
