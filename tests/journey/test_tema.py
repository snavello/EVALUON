"""Tema gris y blanco o negro: se guarda en el usuario y lo dibuja el servidor (REQ-134, REQ-142;
ADR-0074; T-311). Todo el material es inventado (P4)."""

import re

import pytest
from django.contrib.staticfiles import finders
from django.test import Client
from django.urls import reverse

from evaluon.accounts.models import Theme
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

TEMA = "accounts:tema"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def html_tag(html):
    return re.search(r"<html[^>]*>", html).group(0)


def set_theme(client, value, **extra):
    return client.post(reverse(TEMA), {"tema": value, **extra})


def test_the_start_theme_is_light(client, operator_user):
    """REQ-134: el tema de inicio es gris y blanco: `<html>` no lleva `data-theme`."""
    log_in(client, operator_user)
    assert operator_user.theme == Theme.LIGHT
    html = client.get(reverse("expedientes:index")).content.decode()
    assert "data-theme" not in html_tag(html)


def test_choosing_black_is_saved_and_a_new_client_sees_it(client, operator_user, procedure):
    """REQ-134: elegir negro, entrar con otro cliente y ver `data-theme="negro"`."""
    log_in(client, operator_user)
    response = set_theme(client, "negro", next=reverse("expedientes:index"))
    assert response.status_code == 302 and response["Location"] == reverse("expedientes:index")
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.DARK
    other = Client()
    log_in(other, operator_user)
    for url in (reverse("expedientes:index"), reverse("expedientes:pliego", args=[procedure.pk]),
                reverse("queries:screen")):
        assert 'data-theme="negro"' in html_tag(other.get(url).content.decode()), url


def test_choosing_light_again_returns_to_the_start_theme(client, operator_user):
    """REQ-134: vuelve a gris y blanco."""
    log_in(client, operator_user)
    set_theme(client, "negro")
    set_theme(client, "claro")
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.LIGHT
    html = client.get(reverse("expedientes:index")).content.decode()
    assert "data-theme" not in html_tag(html)


@pytest.mark.parametrize("value", ["", "rojo", "NEGRO", "negro ", "claro,negro", "1"])
def test_an_invalid_value_is_rejected_and_nothing_changes(client, operator_user, value):
    """REQ-134: un valor que no es `claro` ni `negro` da 400 y no toca el perfil."""
    log_in(client, operator_user)
    set_theme(client, "negro")
    response = set_theme(client, value)
    assert response.status_code == 400
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.DARK


def test_a_missing_value_is_rejected(client, operator_user):
    """REQ-134: sin `tema` también da 400."""
    log_in(client, operator_user)
    assert client.post(reverse(TEMA), {}).status_code == 400


@pytest.mark.parametrize("target", [
    "https://evil.example/x", "//evil.example/x", "http://evil.example/", "javascript:alert(1)",
    "/\\evil.example", "\\\\evil.example", "ftp://evil.example"])
def test_an_external_next_is_rejected_and_goes_to_the_start_page(client, operator_user, target):
    """REQ-134 (ADR-0074): `next` solo vale si es del mismo sitio; si no, vuelve a la entrada."""
    log_in(client, operator_user)
    response = set_theme(client, "negro", next=target)
    assert response.status_code == 302
    assert response["Location"] == reverse("inicio")
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.DARK  # el valor era bueno: se guarda


def test_a_missing_next_goes_to_the_start_page(client, operator_user):
    """REQ-134: sin `next`, a la entrada."""
    log_in(client, operator_user)
    assert set_theme(client, "negro")["Location"] == reverse("inicio")


def test_a_same_site_next_with_query_is_kept(client, operator_user, procedure):
    """REQ-134: la vuelta conserva la consulta y el ancla de la página de origen."""
    log_in(client, operator_user)
    target = reverse("expedientes:ofertas", args=[procedure.pk]) + "?oferta=3#d-s3-ofertas"
    assert set_theme(client, "negro", next=target)["Location"] == target


def test_only_post_is_accepted(client, operator_user):
    """REQ-134: un GET no cambia el tema (405)."""
    log_in(client, operator_user)
    assert client.get(reverse(TEMA), {"tema": "negro"}).status_code == 405
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.LIGHT


def test_csrf_is_required(operator_user):
    """REQ-134: sin la marca de CSRF el pedido se rechaza (403) y el tema no cambia."""
    strict = Client(enforce_csrf_checks=True)
    log_in(strict, operator_user)
    assert strict.post(reverse(TEMA), {"tema": "negro"}).status_code == 403
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.LIGHT


def test_an_anonymous_visitor_is_sent_to_the_login_and_changes_nothing(client, operator_user):
    """REQ-134: el tema es del usuario; sin sesión se redirige al ingreso."""
    response = set_theme(client, "negro")
    assert response.status_code == 302 and reverse("accounts:login") in response["Location"]
    operator_user.refresh_from_db()
    assert operator_user.theme == Theme.LIGHT


def test_the_login_page_is_always_in_the_start_theme(client):
    """ADR-0074: el visitante anónimo ve el tema de inicio y no ve el selector."""
    html = client.get(reverse("accounts:login")).content.decode()
    assert "data-theme" not in html_tag(html)
    assert 'class="preferencia"' not in html and reverse(TEMA) not in html


def test_the_read_only_user_can_change_the_theme_and_sees_the_selector(
        client, procedure, no_commission_user):
    """REQ-134: el usuario de lectura puede cambiar el tema: el selector sobrevive a
    `without_actions` y el pedido se acepta."""
    log_in(client, no_commission_user)
    page = reverse("expedientes:pliego", args=[procedure.pk])
    html = client.get(page).content.decode()
    assert f'action="{reverse(TEMA)}"' in html and 'class="preferencia"' in html
    assert 'name="tema" value="negro"' in html and 'name="tema" value="claro"' in html
    response = set_theme(client, "negro", next=page)
    assert response.status_code == 302 and response["Location"] == page
    no_commission_user.refresh_from_db()
    assert no_commission_user.theme == Theme.DARK
    assert 'data-theme="negro"' in html_tag(client.get(page).content.decode())


def test_the_read_only_user_still_loses_the_action_forms(client, procedure, no_commission_user):
    """REQ-134: dejar pasar los formularios `preferencia` no deja pasar ningún otro formulario
    de acción; «Salir» sigue."""
    log_in(client, no_commission_user)
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    actions = [m.group(1) for m in re.finditer(r'<form[^>]*method="post"[^>]*action="([^"]+)"', html)]
    assert sorted(actions) == sorted([reverse(TEMA), reverse("accounts:logout")]), actions


def test_the_selector_marks_the_current_theme_and_keeps_the_page(client, operator_user, procedure):
    """REQ-134: dos botones de un formulario; el del tema actual está presionado; `next` es la
    página actual con su consulta."""
    log_in(client, operator_user)
    url = reverse("expedientes:pliego", args=[procedure.pk]) + "?x=1"
    html = client.get(url).content.decode()
    form = re.search(r'<form[^>]*class="preferencia"[^>]*>.*?</form>', html, re.S).group(0)
    assert 'method="post"' in form and "csrfmiddlewaretoken" in form
    assert form.count("<button") == 2
    claro = re.search(r'<button[^>]*value="claro"[^>]*>', form).group(0)
    negro = re.search(r'<button[^>]*value="negro"[^>]*>', form).group(0)
    assert 'aria-pressed="true"' in claro and 'aria-pressed="false"' in negro
    assert 'aria-label="Gris y blanco"' in claro and 'aria-label="Negro"' in negro
    assert re.search(r'name="next" value="[^"]*pliego[^"]*x=1', form)
    set_theme(client, "negro")
    form = re.search(r'<form[^>]*class="preferencia"[^>]*>.*?</form>',
                     client.get(url).content.decode(), re.S).group(0)
    assert 'aria-pressed="true"' in re.search(r'<button[^>]*value="negro"[^>]*>', form).group(0)


def test_the_selector_is_in_the_single_header_of_every_page(client, operator_user, procedure):
    """REQ-134: está en el encabezado de cualquier página con sesión (con o sin pestañas)."""
    log_in(client, operator_user)
    for url in (reverse("expedientes:index"), reverse("expedientes:nuevo"),
                reverse("expedientes:pliego", args=[procedure.pk]), reverse("queries:screen")):
        html = client.get(url).content.decode()
        header = re.search(r'<header class="top".*?</header>', html, re.S).group(0)
        assert 'class="preferencia"' in header, url
        assert html.count('class="preferencia"') == 1, url


def test_the_page_writes_the_two_logos_and_the_sheet_shows_the_one_of_the_theme(
        client, operator_user, procedure):
    """REQ-142: el encabezado trae los dos `<img>` del logotipo (claro y negro) y la hoja de
    estilo muestra solo el del tema; la pestaña lleva el isotipo."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    header = re.search(r'<header class="top".*?</header>', html, re.S).group(0)
    imgs = re.findall(r"<img\b[^>]*>", header)
    assert len(imgs) == 2
    assert "marca/logotipo-claro" in imgs[0] and "marca/logotipo-negro" in imgs[1]
    assert all('alt="EVALUON"' in i or 'alt=""' in i for i in imgs)
    assert sum('alt="EVALUON"' in i for i in imgs) == 1  # un solo nombre accesible
    css = open(finders.find("journey/secciones.css"), encoding="utf-8").read()
    assert re.search(r'\[data-theme="negro"\][^{]*\.logo-claro\s*\{[^}]*display:\s*none', css)
    assert re.search(r"\.logo-negro\s*\{[^}]*display:\s*none", css)
    assert re.search(r'\[data-theme="negro"\][^{]*\.logo-negro\s*\{[^}]*display:\s*(block|inline)', css)


def test_the_header_uses_only_tokens_for_color():
    """REQ-133 (aviso de T-309): el encabezado nuevo no usa blanco ni colores fijos, ni los
    tokens transitorios `--hdr*` ni los alias `--ev-azul-200/800`; todo sale de los tokens."""
    css = open(finders.find("journey/secciones.css"), encoding="utf-8").read()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(|(?<![\w-])(?:white|black)(?![\w-])", css)
    assert "--hdr" not in css and "--ev-azul-200" not in css and "--ev-azul-800" not in css


def test_the_icon_sprite_reads_the_state_tokens():
    """REQ-133: los símbolos del sprite no llevan blanco fijo: la hoja les da
    `--ev-icono-simbolo`, y los círculos siguen en `currentColor` (el color del estado lo pone
    la hoja con `--ev-icono-*`)."""
    from django.template.loader import render_to_string
    sprite = render_to_string("journey/_sprite.html")
    assert "#fff" not in sprite.lower() and "white" not in sprite.lower()
    assert sprite.count('fill="currentColor"') >= 5
    for name in ("cumple", "nocumple", "nodet", "na", "pend"):
        assert f'id="i-{name}"' in sprite
    css = open(finders.find("journey/secciones.css"), encoding="utf-8").read()
    assert re.search(r"\.sprite [^{]*\{[^}]*stroke:\s*var\(--ev-icono-simbolo\)", css)
    assert re.search(r"\.sprite [^{]*\{[^}]*fill:\s*var\(--ev-icono-simbolo\)", css)
    for state, token in (("cumple", "cumple"), ("nocumple", "nocumple"), ("nodet", "nodeterminado"),
                         ("pend", "pendiente")):
        assert re.search(rf"\.est\.{state}\s*\{{\s*color:\s*var\(--ev-icono-{token}\)", css)


def test_the_state_icon_keeps_its_form_and_its_name():
    """REQ-133: el ícono de estado conserva su forma y el nombre al pasar el mouse."""
    from django.template.loader import render_to_string
    icon = render_to_string("journey/_icono.html", {"icon": "nocumple", "name": "No cumple"})
    assert 'class="est nocumple"' in icon and 'title="No cumple"' in icon
    assert 'data-nombre="No cumple"' in icon and "#i-nocumple" in icon
    css = open(finders.find("journey/secciones.css"), encoding="utf-8").read()
    assert "content: attr(data-nombre)" in css
    assert ".est:hover::after" in css and ".est:focus-visible::after" in css
