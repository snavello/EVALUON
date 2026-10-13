"""La marca de la aplicación: logotipo en el encabezado, isotipo en la pestaña y logotipo claro
en el ingreso, con las letras dibujadas como formas (REQ-108; T-267). Material inventado (P4)."""

import re
import xml.etree.ElementTree as ET

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

SVG_NS = "http://www.w3.org/2000/svg"
LOGOS = ("marca/logotipo-encabezado.svg", "marca/logotipo-ingreso.svg")
ALL_SVG = (*LOGOS, "marca/isotipo.svg")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def header_of(html):
    match = re.search(r'<header class="top">.*?</header>', html, re.S)
    assert match, "la página no trae el encabezado"
    return match.group(0)


def assert_header_and_icon(html):
    header = header_of(html)
    link = re.search(r'<a class="nombre" href="([^"]*)">(.*?)</a>', header, re.S)
    assert link, "el encabezado no trae el enlace .nombre"
    assert link.group(1) == reverse("inicio")
    img = re.search(r"<img\b[^>]*>", link.group(2))
    assert img, "el enlace .nombre no lleva imagen"
    assert f'src="{static("marca/logotipo-encabezado.svg")}"' in img.group(0)
    assert 'alt="EVALUON"' in img.group(0)
    head = re.search(r"<head>.*?</head>", html, re.S).group(0)
    icon = re.search(r'<link rel="icon"[^>]*>', head)
    assert icon, "la pestaña no trae el ícono"
    assert 'type="image/svg+xml"' in icon.group(0)
    assert f'href="{static("marca/isotipo.svg")}"' in icon.group(0)


def test_header_and_tab_icon_on_a_page_that_extends_base(client, operator_user):
    """REQ-108: una página que extiende base.html directo lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("queries:screen"))
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_header_and_tab_icon_on_a_section_page(client, operator_user, procedure):
    """REQ-108: una pestaña de un procedimiento lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("expedientes:pliego", args=[procedure.pk]))
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_header_and_tab_icon_on_the_start_page(client, operator_user, procedure):
    """REQ-108: la entrada (inicio) lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("inicio"), follow=True)
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_login_shows_the_light_logo_before_the_title(client):
    """REQ-108: en el ingreso, el logotipo claro va arriba de «Ingresar»; además el encabezado
    y la pestaña de siempre."""
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    html = response.content.decode()
    img = re.search(r'<img class="ingreso-logo"[^>]*>', html)
    assert img, "el ingreso no trae el logotipo"
    assert f'src="{static("marca/logotipo-ingreso.svg")}"' in img.group(0)
    assert 'alt=""' in img.group(0)
    assert html.index(img.group(0)) < html.index("<h1>Ingresar</h1>")
    assert_header_and_icon(html)


@pytest.mark.parametrize("name", ALL_SVG)
def test_the_brand_files_exist_and_are_valid_xml(name):
    """REQ-108: los tres archivos existen donde los reúne collectstatic y son XML válido."""
    path = finders.find(name)
    assert path, f"{name} no está en los estáticos"
    root = ET.parse(path).getroot()
    assert root.tag == f"{{{SVG_NS}}}svg"


@pytest.mark.parametrize("name", ALL_SVG)
def test_the_brand_files_do_not_depend_on_fonts_or_other_resources(name):
    """REQ-108: la marca se ve igual en cualquier equipo: sin texto, imágenes, fuentes ni
    direcciones externas."""
    text = open(finders.find(name), encoding="utf-8").read()
    for forbidden in ("<text", "<image", "font-family", "@import", "<style", "<script"):
        assert forbidden not in text, (name, forbidden)
    addresses = re.findall(r"https?://[^\s\"'<>)]*", text)
    assert set(addresses) <= {SVG_NS}, (name, addresses)
    assert "xlink:href" not in text and "url(http" not in text


@pytest.mark.parametrize("name", LOGOS)
def test_the_logos_are_cropped_have_seven_letter_paths_and_no_outer_halo(name):
    """REQ-108: recorte a la placa, una forma por cada letra de EVALUON y sin el halo exterior."""
    root = ET.parse(finders.find(name)).getroot()
    assert root.get("viewBox") == "126 144 772 224"
    ns = {"s": SVG_NS}
    wordmark = root.find(".//s:g[@id='wordmark']", ns)
    assert wordmark is not None
    paths = wordmark.findall(".//s:path", ns)
    assert len(paths) == 7
    assert all(p.get("d") for p in paths)
    text = open(finders.find(name), encoding="utf-8").read()
    assert "url(#brillo)" not in text and 'id="brillo"' not in text


def test_the_tab_icon_is_the_split_isotype():
    """REQ-108: el isotipo es el aprobado para fondo claro, sin letras."""
    root = ET.parse(finders.find("marca/isotipo.svg")).getroot()
    assert root.tag == f"{{{SVG_NS}}}svg"
    assert root.find(f".//{{{SVG_NS}}}path") is not None
