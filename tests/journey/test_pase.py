"""Pase de hoja entre secciones con transiciones entre documentos (REQ-139; ADR-0075; T-311).
Los tests leen `pase.css` y `pase.js` y las plantillas; el efecto en el navegador se revisa a mano
en Edge (T-316). Todo el material es inventado (P4)."""

import re

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from tests.accounts.test_session import TEST_PASSWORD

LIMITE = 0.5
LIMITE_REDUCIDO = 0.15


def leer(nombre):
    ruta = finders.find(nombre)
    assert ruta, f"{nombre} no está en los estáticos"
    return open(ruta, encoding="utf-8").read()


def sin_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def segundos(texto):
    """Todas las duraciones (`0.44s`, `440ms`) de un trozo de CSS, en segundos."""
    salida = [float(n) for n in re.findall(r"(?<![\w.-])(\d*\.?\d+)s\b", texto)]
    salida += [float(n) / 1000 for n in re.findall(r"(?<![\w.-])(\d+)ms\b", texto)]
    return salida


def bloque_reducido(css):
    """El cuerpo del `@media (prefers-reduced-motion: reduce)`, con llaves balanceadas."""
    inicio = css.index("@media (prefers-reduced-motion: reduce)")
    abre = css.index("{", inicio)
    nivel, i = 0, abre
    while True:
        nivel += css[i] == "{"
        nivel -= css[i] == "}"
        if nivel == 0:
            return css[abre + 1:i]
        i += 1


def test_the_navigation_opts_into_view_transitions():
    """REQ-139: `@view-transition { navigation: auto; }` en la hoja del pase."""
    css = sin_comentarios(leer("journey/pase.css"))
    assert re.search(r"@view-transition\s*\{\s*navigation:\s*auto;?\s*\}", css)


def test_three_elements_have_a_view_transition_name():
    """REQ-139: el `<main>` es `hoja`, el encabezado `cabecera` (queda quieto) y la pestaña
    activa `pildora` (la desliza el navegador)."""
    css = sin_comentarios(leer("journey/pase.css"))
    assert re.search(r"main\s*\{[^}]*view-transition-name:\s*hoja", css)
    assert re.search(r"header\.top\s*\{[^}]*view-transition-name:\s*cabecera", css)
    assert re.search(r'\[aria-current="?page"?\][^{]*\{[^}]*view-transition-name:\s*pildora', css)


def test_the_header_stays_still_and_the_pill_slides_with_the_default():
    """REQ-139: la cabecera no se anima (ni vieja ni nueva) y la píldora usa el deslizamiento
    del navegador (sin animación propia)."""
    css = sin_comentarios(leer("journey/pase.css"))
    assert re.search(r"::view-transition-(old|group)\(cabecera\)[^{]*\{[^}]*animation:\s*none", css) \
        or re.search(r"::view-transition-old\(cabecera\)[^{]*,[^{]*::view-transition-new\(cabecera\)"
                     r"[^{]*\{[^}]*animation:\s*none", css)
    assert "::view-transition-old(pildora)" not in css or "animation: none" not in re.search(
        r"::view-transition-old\(pildora\)[^{]*\{[^}]*\}", css).group(0)


def test_the_sheet_turns_on_the_left_edge_in_at_most_half_a_second():
    """REQ-139: la hoja vieja gira sobre su borde izquierdo (`rotateY`) y dura 0,5 s o menos;
    solo `transform` y `opacity` (los acelera el navegador)."""
    css = sin_comentarios(leer("journey/pase.css"))
    fuera_de_reducido = css.replace(bloque_reducido(css), "")
    assert "rotateY(" in fuera_de_reducido and "perspective" in fuera_de_reducido
    assert re.search(r"transform-origin:\s*(0(%|px)?|left)\s+(50%|center)", fuera_de_reducido)
    duraciones = segundos(fuera_de_reducido)
    assert duraciones, "no hay duración declarada"
    assert max(duraciones) <= LIMITE, duraciones
    assert max(duraciones) >= 0.3  # es un giro de verdad, no un corte
    animadas = set(re.findall(r"^\s*(?:from|to|\d+%)\s*\{([^}]*)\}", fuera_de_reducido, re.M))
    for cuerpo in animadas:
        for propiedad in re.findall(r"([\w-]+)\s*:", cuerpo):
            assert propiedad in {"transform", "opacity"}, propiedad


def test_with_reduced_motion_the_pass_is_a_short_fade():
    """REQ-139: con «reducir movimiento», fundido de 0,15 s o menos y sin giro."""
    css = sin_comentarios(leer("journey/pase.css"))
    reducido = bloque_reducido(css)
    assert "rotateY" not in reducido and "opacity" in reducido
    duraciones = segundos(reducido)
    assert duraciones and max(duraciones) <= LIMITE_REDUCIDO, duraciones
    assert "::view-transition-old(hoja)" in reducido and "::view-transition-new(hoja)" in reducido


def test_the_direction_script_is_tiny_local_and_listens_to_pagereveal():
    """REQ-139 (ADR-0075): `pase.js` fija la dirección en `pagereveal` (unas 15 líneas), sin
    direcciones externas, sin `eval`."""
    js = leer("journey/pase.js")
    codigo = [l for l in js.splitlines() if l.strip() and not l.strip().startswith(("//", "/*", "*"))]
    assert len(codigo) <= 30, len(codigo)
    assert "pagereveal" in js and "dataset" in js
    for prohibido in ("http://", "https://", "eval(", "innerHTML", "document.write", "fetch("):
        assert prohibido not in js


def test_the_direction_selectors_exist_in_the_sheet():
    """REQ-139: las dos direcciones (adelante y atrás) están en la hoja y el script usa los
    mismos valores."""
    css = sin_comentarios(leer("journey/pase.css"))
    js = leer("journey/pase.js")
    valores = set(re.findall(r'data-pase="(\w+)"', css))
    assert {"adelante", "atras"} <= valores
    for valor in valores:
        assert f'"{valor}"' in js or f"'{valor}'" in js, valor


@pytest.mark.django_db
def test_every_page_links_the_pass_sheet_and_script_and_the_empty_sheets(client, operator_user,
                                                                       procedure):
    """REQ-139: `base.html` enlaza las seis hojas de la definición compartida y el script del
    pase; el icono de la pestaña es el isotipo nuevo."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    for url in (reverse("expedientes:pliego", args=[procedure.pk]), reverse("expedientes:index"),
                reverse("queries:screen")):
        html = client.get(url).content.decode()
        head = re.search(r"<head>.*?</head>", html, re.S).group(0)
        hojas = re.findall(r'<link rel="stylesheet" href="[^"]*/([\w.-]+\.css)"', head)
        for hoja in ("evaluon.css", "tokens.css", "secciones.css", "tablero.css", "pase.css",
                     "avance.css"):
            assert hoja in hojas, (url, hoja)
        assert hojas.index("tokens.css") < hojas.index("secciones.css") < hojas.index("tablero.css")
        assert "journey/pase.js" in head
        assert "marca/isotipo-claro.svg" in head


@pytest.mark.django_db
def test_the_active_tab_and_main_are_where_the_sheet_looks_for_them(client, operator_user,
                                                                  procedure):
    """REQ-139: hay un único `<main>` y una única pestaña con `aria-current="page"` en la
    barra de la página (la que lleva `view-transition-name: pildora`)."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:ofertas", args=[procedure.pk])).content.decode()
    assert html.count("<main") == 1
    bar = html[html.index('id="barra-secciones"'):html.index('id="journey-status"')]
    assert bar.count('aria-current="page"') == 1


def test_the_new_sheets_exist_with_only_a_comment():
    """REQ-126/REQ-140 (definición compartida 5): `tablero.css` y `avance.css` existen con un
    solo comentario; los llenan T-313 y T-330."""
    for nombre in ("journey/tablero.css", "journey/avance.css"):
        css = leer(nombre)
        assert css.lstrip().startswith("/*")
        assert sin_comentarios(css).strip() == "", nombre
