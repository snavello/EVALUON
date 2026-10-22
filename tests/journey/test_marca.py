"""La marca de la aplicación en la estética nueva: logotipo por tema en el encabezado, isotipo en
la pestaña y logotipo claro en el ingreso, con las letras dibujadas como formas (REQ-142, que
enmienda a REQ-108; T-267, T-310, T-311). Material inventado (P4)."""

import re
import xml.etree.ElementTree as ET

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

SVG_NS = "http://www.w3.org/2000/svg"
NS = {"s": SVG_NS}
LOGOS = ("marca/logotipo-claro.svg", "marca/logotipo-negro.svg")
ISOTIPOS = ("marca/isotipo-claro.svg", "marca/isotipo-negro.svg")
ALL_SVG = (*LOGOS, *ISOTIPOS)
VIEJOS = ("logotipo-encabezado.svg", "logotipo-ingreso.svg", "isotipo.svg")
TEXTO = 4.5


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def header_of(html):
    match = re.search(r'<header class="top".*?</header>', html, re.S)
    assert match, "la página no trae el encabezado"
    return match.group(0)


def assert_header_and_icon(html, theme="claro"):
    header = header_of(html)
    link = re.search(r'<a class="nombre" href="([^"]*)">(.*?)</a>', header, re.S)
    assert link, "el encabezado no trae el enlace .nombre"
    assert link.group(1) == reverse("inicio")
    imgs = re.findall(r"<img\b[^>]*>", link.group(2))
    assert len(imgs) == 2, "el logotipo va en dos versiones; la hoja muestra la del tema"
    assert f'src="{static("marca/logotipo-claro.svg")}"' in imgs[0] and "logo-claro" in imgs[0]
    assert f'src="{static("marca/logotipo-negro.svg")}"' in imgs[1] and "logo-negro" in imgs[1]
    assert sum('alt="EVALUON"' in i for i in imgs) == 1
    head = re.search(r"<head>.*?</head>", html, re.S).group(0)
    icon = re.search(r'<link rel="icon"[^>]*>', head)
    assert icon, "la pestaña no trae el ícono"
    assert 'type="image/svg+xml"' in icon.group(0)
    assert f'href="{static(f"marca/isotipo-{theme}.svg")}"' in icon.group(0)


def test_header_and_tab_icon_on_a_page_that_extends_base(client, operator_user):
    """REQ-142: una página que extiende base.html directo lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("queries:screen"))
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_header_and_tab_icon_on_a_section_page(client, operator_user, procedure):
    """REQ-142: una pestaña de un procedimiento lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("expedientes:pliego", args=[procedure.pk]))
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_header_and_tab_icon_on_the_start_page(client, operator_user, procedure):
    """REQ-142: la entrada (inicio) lleva logotipo e isotipo."""
    log_in(client, operator_user)
    response = client.get(reverse("inicio"), follow=True)
    assert response.status_code == 200
    assert_header_and_icon(response.content.decode())


def test_the_black_theme_gets_the_black_tab_icon(client, operator_user, procedure):
    """REQ-142: con el tema negro, la pestaña lleva el isotipo de la versión negra."""
    log_in(client, operator_user)
    client.post(reverse("accounts:tema"), {"tema": "negro"})
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    assert_header_and_icon(html, theme="negro")


def test_login_shows_the_light_logo_before_the_title(client):
    """REQ-142: en el ingreso, el logotipo claro va arriba de «Ingresar»; además la pestaña
    lleva el isotipo y no hay selector de tema (el visitante ve el tema de inicio)."""
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    html = response.content.decode()
    img = re.search(r'<img class="ingreso-logo"[^>]*>', html)
    assert img, "el ingreso no trae el logotipo"
    assert f'src="{static("marca/logotipo-claro.svg")}"' in img.group(0)
    assert 'alt=""' in img.group(0)
    assert html.index(img.group(0)) < html.index("<h1>Ingresar</h1>")
    head = re.search(r"<head>.*?</head>", html, re.S).group(0)
    assert f'href="{static("marca/isotipo-claro.svg")}"' in head


@pytest.mark.parametrize("viejo", VIEJOS)
def test_the_old_brand_files_are_gone_and_nobody_names_them(viejo, client, operator_user,
                                                          procedure):
    """REQ-142: los tres SVG de la marca de la 014 se retiraron de `static/marca/` y ninguna
    plantilla, hoja de estilo ni script los nombra."""
    assert finders.find(f"marca/{viejo}") is None
    raiz = finders.find("marca/logotipo-claro.svg").rsplit("static", 1)[0]
    for ruta in ("templates", "static"):
        import pathlib
        for archivo in pathlib.Path(raiz, ruta).rglob("*"):
            if archivo.suffix in {".html", ".css", ".js", ".py", ".svg"} and archivo.is_file():
                assert viejo not in archivo.read_text(encoding="utf-8"), archivo
    log_in(client, operator_user)
    for url in (reverse("expedientes:pliego", args=[procedure.pk]), reverse("accounts:login")):
        assert viejo not in client.get(url).content.decode()


@pytest.mark.parametrize("name", ALL_SVG)
def test_the_brand_files_exist_and_are_valid_xml(name):
    """REQ-142: los cuatro archivos existen donde los reúne collectstatic y son XML válido."""
    path = finders.find(name)
    assert path, f"{name} no está en los estáticos"
    root = ET.parse(path).getroot()
    assert root.tag == f"{{{SVG_NS}}}svg"


@pytest.mark.parametrize("name", ALL_SVG)
def test_the_brand_files_do_not_depend_on_fonts_or_other_resources(name):
    """REQ-142: la marca se ve igual en cualquier equipo: sin texto, imágenes, fuentes ni
    direcciones externas."""
    text = open(finders.find(name), encoding="utf-8").read()
    for forbidden in ("<text", "<image", "font-family", "@import", "<style", "<script"):
        assert forbidden not in text, (name, forbidden)
    addresses = re.findall(r"https?://[^\s\"'<>)]*", text)
    assert set(addresses) <= {SVG_NS}, (name, addresses)
    assert "xlink:href" not in text and "url(http" not in text


@pytest.mark.parametrize("name", LOGOS)
def test_the_logos_are_cropped_and_have_seven_letter_paths(name):
    """REQ-142: recorte a la placa y una forma por cada letra de EVALUON (cinco de EVALU y dos
    de ON)."""
    root = ET.parse(finders.find(name)).getroot()
    assert root.get("viewBox") == "126 144 772 224"
    wordmark = root.find(".//s:g[@id='wordmark']", NS)
    assert wordmark is not None
    groups = wordmark.findall("s:g", NS)
    assert [len(g.findall("s:path", NS)) for g in groups] == [5, 2]
    assert all(p.get("d") for g in groups for p in g.findall("s:path", NS))


@pytest.mark.parametrize("name", ISOTIPOS)
def test_the_tab_icons_are_the_split_isotype(name):
    """REQ-142: el isotipo es el «E + on» partido, con formas (sin letras)."""
    root = ET.parse(finders.find(name)).getroot()
    assert root.get("viewBox") == "0 0 512 512"
    assert root.find(".//s:path", NS) is not None
    assert root.find(".//s:g[@id='wordmark']", NS) is not None


# --- Versión por tema y contraste de las letras sobre su placa --------------------------------


def _hex(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b):
    la, lb = _lum(_hex(a)), _lum(_hex(b))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _stops(root, gradient):
    node = root.find(f".//s:linearGradient[@id='{gradient}']", NS)
    assert node is not None, gradient
    return [s.get("stop-color") for s in node.findall("s:stop", NS)]


def _letters(root):
    """(relleno de EVALU, relleno de ON) del `wordmark`."""
    groups = root.find(".//s:g[@id='wordmark']", NS).findall("s:g", NS)
    assert len(groups) == 2
    return groups[0].get("fill"), groups[1].get("fill")


@pytest.mark.parametrize("name", ALL_SVG)
def test_the_letters_read_on_their_plate_at_4_5_to_1(name):
    """REQ-142: las letras de EVALU sobre su placa y las de ON sobre el lima se leen con
    contraste de 4,5:1 o más, en el peor tramo del degradado."""
    root = ET.parse(finders.find(name)).getroot()
    evalu, on = _letters(root)
    for stop in _stops(root, "gIzq"):
        assert _ratio(evalu, stop) >= TEXTO, (name, evalu, stop)
    for stop in _stops(root, "gDer"):
        assert _ratio(on, stop) >= TEXTO, (name, on, stop)


def test_the_two_themes_have_the_two_versions_of_the_plate():
    """REQ-142: tema gris y blanco, placa EVALU en negro y ON en lima; tema negro, placa EVALU
    en gris y ON en lima (misma forma, otro color)."""
    claro = ET.parse(finders.find("marca/logotipo-claro.svg")).getroot()
    negro = ET.parse(finders.find("marca/logotipo-negro.svg")).getroot()
    assert _stops(claro, "gIzq")[-1].upper() == "#0B0C0E"  # negro
    assert min(_lum(_hex(s)) for s in _stops(negro, "gIzq")) > _lum(_hex("#2A2C31")) - 1e-9
    assert max(_lum(_hex(s)) for s in _stops(negro, "gIzq")) < 0.12  # sigue siendo gris oscuro
    assert _lum(_hex(_stops(negro, "gIzq")[0])) > _lum(_hex(_stops(claro, "gIzq")[0]))
    assert _stops(claro, "gDer") == _stops(negro, "gDer")  # el lima es el mismo
    assert all(_hex(s)[1] > 200 and _hex(s)[0] > 150 and _hex(s)[2] < 100
               for s in _stops(claro, "gDer"))  # lima: verde alto, azul bajo
    for root in (claro, negro):
        assert root.find(".//s:g[@id='icon']", NS) is not None
        assert root.find(".//s:radialGradient[@id='gHalo']", NS) is not None  # el halo


def test_the_contrast_check_bites():
    """REQ-142 (prueba de alteración): letras claras sobre una placa clara no pasan."""
    assert _ratio("#F2F2F2", "#B2DE18") < TEXTO
    assert _ratio("#F2F2F2", "#0B0C0E") >= TEXTO
