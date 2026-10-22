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
    horizontal, y el encabezado queda en dos columnas."""
    bloque = _bloque(_css(), 1100)
    assert re.search(r"header\.top \.top-in \{[^}]*grid-template-columns: 1fr auto", bloque)
    assert re.search(r"header\.top nav\.tabs \{[^}]*grid-row: 2", bloque)
    assert re.search(r"header\.top nav\.tabs \{[^}]*overflow-x: auto", bloque)
    assert re.search(r"header\.top nav\.tabs \{[^}]*justify-self: stretch", bloque)


def test_reglas_para_640_px_en_el_css_servido():
    """REQ-133: a 640 px el recorrido y el encabezado se achican, el nombre del usuario sale y
    el menú del procedimiento se acota al ancho de la pantalla."""
    bloque = _bloque(_css(), 640)
    assert re.search(r"header\.top \.top-in \{[^}]*padding", bloque)
    assert re.search(r"\.camino \{[^}]*padding", bloque)
    assert re.search(r"header\.top \.sel-user \{[^}]*display: none", bloque)
    assert re.search(r"header\.top \.sel-proc \.menu \{[^}]*max-width", bloque)


def test_las_pildoras_no_parten_el_nombre():
    """REQ-133: la píldora no parte la palabra ni se encoge: en una pantalla angosta se desplaza."""
    css = re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)
    assert re.search(r"nav\.tabs \.tab \{[^}]*white-space: nowrap", css)
    assert re.search(r"nav\.tabs \.tab \{[^}]*flex: none", css)
