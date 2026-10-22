"""Siempre se sabe el camino (REQ-132) y la portada del procedimiento es el primer panel
(REQ-128): el recorrido arriba y, en cada sección, la línea «Hay: … · Falta: …»; la portada
redirige a `procedimiento/` conservando la consulta. Todo el material es inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.audit.models import Channel
from evaluon.journey.sections import SECTIONS, sections_for
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

KEYS = [module.KEY for module in SECTIONS]
TEMPLATES = Path(__file__).resolve().parents[2] / "evaluon" / "templates" / "journey"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def url(key, procedure):
    return reverse(f"expedientes:{key}", args=[procedure.pk])


def hay_falta(html):
    """El bloque «Hay · Falta» de la página."""
    return re.search(r'<div class="hay-falta".*?<!-- /hay-falta -->', html, re.S).group(0)


@pytest.mark.parametrize("key", KEYS)
def test_every_section_has_the_path_and_the_hay_falta_line(client, procedure, matrix,
                                                          operator_user, key):
    """REQ-132: en cada una de las cinco secciones están el recorrido y la línea «Hay … Falta …»."""
    log_in(client, operator_user)
    html = client.get(url(key, procedure)).content.decode()
    header = re.search(r'<header class="top".*?</header>', html, re.S).group(0)
    assert header.count('<nav class="camino"') == 1
    assert "Procedimientos" in header and procedure.number in header
    block = hay_falta(html)
    assert html.count('class="hay-falta"') == 1
    assert "Hay:" in block and 'class="hf-fila hf-falta"' in block and "Falta" in block
    assert 'id="seccion-resumen"' in block
    assert html.index('id="seccion-titulo"') < html.index('class="hay-falta"')


@pytest.mark.parametrize("key", KEYS)
def test_hay_comes_from_the_summary_and_falta_from_the_missing_with_their_action(
        client, procedure, operator_user, key):
    """REQ-132: «Hay» es el resumen de la sección; «Falta» lleva cada faltante con su acción."""
    log_in(client, operator_user)
    section = sections_for(operator_user, procedure, channel=Channel.SCREEN).get(key)
    html = client.get(url(key, procedure)).content.decode()
    block = hay_falta(html)
    for _label, detail in section.summary:
        assert str(detail).strip() in block
    falta = re.search(r'<p class="falta">(.*?)</p>', block, re.S)
    if not section.tema_missing:
        assert falta is None
        return
    assert falta is not None
    for item in section.tema_missing:
        assert shown(item.text) in falta.group(1)
        if item.url:
            assert f'href="{item.url}"' in falta.group(1)
            assert (item.action or "Ver") in falta.group(1)


def shown(text):
    """Cómo se muestra un faltante (T-336): sin el «Falta » o «Faltan » del comienzo y con la
    primera letra en mayúscula."""
    text = str(text).strip()
    for start in ("Faltan ", "Falta "):
        if text.startswith(start):
            text = text[len(start):]
            break
    return text[:1].upper() + text[1:]


def test_the_label_is_always_there_and_the_word_is_not_repeated(client, procedure, operator_user):
    """T-336, REQ-132: la etiqueta «Falta:» va siempre; el texto de cada faltante pierde el
    «Falta »/«Faltan » del comienzo y sigue entero, con su acción."""
    log_in(client, operator_user)
    visto = False
    for key in KEYS:
        section = sections_for(operator_user, procedure, channel=Channel.SCREEN).get(key)
        if not section.tema_missing:
            continue
        block = hay_falta(client.get(url(key, procedure)).content.decode())
        etiqueta = re.search(r'<span class="hf-et"><i class="hf-punto hf-punto-falta"[^>]*></i>'
                             r'(.*?)</span>', block, re.S).group(1).strip()
        assert etiqueta == "Falta:", (key, etiqueta)
        falta = re.search(r'<p class="falta">(.*?)</p>', block, re.S).group(1)
        assert shown(section.tema_missing[0].text) in falta
        if str(section.tema_missing[0].text).strip().startswith("Falta"):
            assert str(section.tema_missing[0].text).strip() not in falta
            visto = True
    assert visto, "ningun caso de prueba tiene un faltante que empiece con Falta"


def test_without_anything_missing_the_line_says_so_without_a_missing_list(
        client, procedure, matrix, operator_user):
    """REQ-132: sin faltantes, «Falta» lo dice y no inventa una lista."""
    log_in(client, operator_user)
    for key in KEYS:
        section = sections_for(operator_user, procedure, channel=Channel.SCREEN).get(key)
        if section.tema_missing:
            continue
        block = hay_falta(client.get(url(key, procedure)).content.decode())
        assert "Falta:" in block and 'class="falta"' not in block
        assert "<b>Falta:</b>" not in block and "Ningún faltante registrado" in block
        return
    pytest.skip("todas las secciones tienen faltantes en este caso")


def test_the_front_page_redirects_to_the_first_panel_keeping_the_query(client, procedure,
                                                                       operator_user):
    """REQ-128, REQ-132: `expedientes/<id>/` redirige (302) a `procedimiento/` con la consulta."""
    log_in(client, operator_user)
    base = reverse("expedientes:portada", args=[procedure.pk])
    first = url("procedimiento", procedure)
    response = client.get(base)
    assert response.status_code == 302 and response["Location"] == first
    response = client.get(base, {"oferta": "3", "ficha": "2"})
    assert response.status_code == 302
    assert response["Location"] == f"{first}?oferta=3&ficha=2"


def test_the_first_panel_is_the_first_section_with_the_path(client, procedure, operator_user):
    """REQ-128: al seguir la redirección se llega al cuerpo de la sección 1, con el camino."""
    log_in(client, operator_user)
    response = client.get(reverse("expedientes:portada", args=[procedure.pk]), follow=True)
    assert response.status_code == 200
    html = response.content.decode()
    assert response.redirect_chain[-1][0] == url("procedimiento", procedure)
    assert 'id="seccion-titulo"' in html and 'class="hay-falta"' in html


def test_the_front_page_of_a_missing_procedure_is_a_404(client, operator_user):
    """REQ-132: la portada de un procedimiento que no existe no redirige a ningún lado."""
    log_in(client, operator_user)
    assert client.get(reverse("expedientes:portada", args=[999999])).status_code == 404


def test_the_old_front_page_template_is_gone():
    """REQ-128: sin referencias, la plantilla de la portada vieja se retira."""
    assert not (TEMPLATES / "portada.html").exists()


def test_hay_falta_has_no_inline_styles_or_scripts():
    """Plan 017: sin `style=` ni scripts en línea en la plantilla nueva."""
    text = (TEMPLATES / "_hay_falta.html").read_text(encoding="utf-8")
    assert " style=" not in text and "<style" not in text and "<script" not in text
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text)
