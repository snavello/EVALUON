"""Listado de procedimientos, alta y borrador del pliego con la estética nueva (REQ-133, REQ-132;
plan 017, T-324). Solo presentación: las tres páginas cargan en los dos temas, con los tokens y sin
estilos en línea ni colores sueltos. El recorrido del encabezado lo entrega T-311 y se comprueba al
integrar. Todo el material es inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s1_pliego import proposed

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parents[2] / "evaluon"
CSS = ROOT / "static" / "journey" / "procedimientos.css"
TEMPLATES = [ROOT / "templates" / "journey" / name
             for name in ("expedientes.html", "nuevo.html", "s1_pliego_borrador.html")]
THEMES = ("claro", "negro")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def pages(client, user):
    """Las tres páginas como las ve `user`: el listado, el alta y un borrador de pliego leído."""
    draft = proposed(client, user)
    return {"listado": reverse("expedientes:index"), "alta": reverse("expedientes:nuevo"),
            "borrador": reverse("expedientes:s1_pliego_borrador", args=[draft.pk])}


@pytest.mark.parametrize("theme", THEMES)
def test_the_three_pages_load_in_both_themes_with_the_new_sheet(client, operator_user, procedure,
                                                                 theme):
    """REQ-133: listado, alta y borrador cargan en el tema claro y en el negro, enlazan la hoja
    propia sobre los tokens, no traen `style=` ni colores en hexadecimal."""
    operator_user.theme = theme
    operator_user.save()
    urls = pages(client, operator_user)
    for name, url in urls.items():
        response = client.get(url)
        assert response.status_code == 200, name
        html = response.content.decode()
        # El sprite de íconos es compartido (símbolo blanco de los estados): no es de estas páginas.
        html = re.sub(r"<svg class=\"sprite\".*?</svg>", "", html, flags=re.S)
        assert "journey/procedimientos.css" in html, name
        assert 'class="app procedimientos' in html or "app procedimientos" in html, name
        assert " style=" not in html and "<style" not in html, name
        assert not re.search(r"(color|background|fill|stroke)\s*[:=]\s*[\"']?#[0-9A-Fa-f]{3,8}\b",
                             html), name


def test_the_list_keeps_its_table_and_its_actions(client, operator_user, procedure):
    """REQ-133: el listado sigue siendo una tabla con un enlace por procedimiento y el botón de
    alta: se cambia la estética, no el comportamiento."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:index")).content.decode()
    assert 'id="t-expedientes"' in html
    assert reverse("expedientes:portada", args=[procedure.pk]) in html
    assert reverse("expedientes:nuevo") in html and "Nuevo procedimiento" in html


def test_the_sheet_uses_only_tokens(client):
    """REQ-133: la hoja propia existe, no tiene colores en hexadecimal ni valores de la paleta
    vieja y se limita a las tres páginas."""
    css = CSS.read_text(encoding="utf-8")
    assert "body.procedimientos" in css
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", css)
    assert "http://" not in css and "https://" not in css
    assert "--ev-azul" not in css and "--ev-beige" not in css


def test_the_templates_carry_no_inline_styles_or_colors():
    """REQ-133: las tres plantillas no traen `style=` ni colores sueltos (la CSP solo permite
    recursos propios)."""
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        assert " style=" not in text and "<style" not in text, path.name
        assert not re.search(r"(?<!href=\")#[0-9A-Fa-f]{6}\b", text), path.name
