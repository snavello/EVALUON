"""Encabezado y pestañas en píldora legibles en pantallas angostas (REQ-133; antes REQ-100)."""

import re

from django.contrib.staticfiles import finders


def _css():
    path = finders.find("journey/secciones.css")
    assert path
    return open(path, encoding="utf-8").read()


def _bloque(css, ancho):
    match = re.search(r"@media \(max-width: %dpx\) \{(.*?)\n\}" % ancho, css, re.S)
    assert match, f"falta @media (max-width: {ancho}px)"
    return match.group(1)


def test_reglas_para_1100_px_en_el_css_servido():
    """REQ-133: a 1100 px las pestañas pasan a una segunda fila del encabezado, con desplazamiento
    horizontal, y el recorrido queda en la tercera."""
    bloque = _bloque(_css(), 1100)
    assert re.search(r'header\.top \{[^}]*grid-template-areas: "logo right" "tabs tabs" "camino camino"', bloque)
    assert re.search(r"header\.top nav\.tabs \{[^}]*overflow-x: auto", bloque)
    assert re.search(r"header\.top nav\.tabs \{[^}]*justify-self: stretch", bloque)


def test_reglas_para_640_px_en_el_css_servido():
    """REQ-133: a 640 px el encabezado se achica, el logotipo baja de tamaño y el menú del
    procedimiento se acota al ancho de la pantalla."""
    bloque = _bloque(_css(), 640)
    assert re.search(r"body\.app \{[^}]*--pad-x: 1rem", bloque)
    assert re.search(r"header\.top \.nombre img \{[^}]*height", bloque)
    assert re.search(r"header\.top \.sel-proc \.menu \{[^}]*max-width", bloque)


def test_el_encabezado_es_una_grilla_con_el_recorrido_debajo():
    """REQ-133: en pantalla ancha, logotipo, pestañas y controles arriba y el recorrido abajo; en
    el HTML el recorrido va antes de los controles del usuario."""
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    assert re.search(r'header\.top \{[^}]*grid-template-areas: "logo tabs right" "camino camino camino"', css)
    for area in ("logo", "tabs", "right", "camino"):
        assert re.search(r"grid-area: %s;" % area, css), area


def test_las_pildoras_no_parten_el_nombre():
    """REQ-133: la píldora no parte la palabra ni se encoge: en una pantalla angosta se desplaza."""
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    assert re.search(r"nav\.tabs \.tab \{[^}]*white-space: nowrap", css)
    assert re.search(r"nav\.tabs \.tab \{[^}]*flex: none", css)
