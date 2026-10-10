"""Encabezado y pestañas legibles en pantallas angostas (REQ-100)."""

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
    """REQ-100: a 1100 px el texto de las pestañas se achica y el desplegable se acota."""
    bloque = _bloque(_css(), 1100)
    assert "nav.tabs .t-nombre" in bloque and "font-size: var(--ev-t-xs)" in bloque
    assert "header.top .sel-proc" in bloque


def test_reglas_para_900_px_en_el_css_servido():
    """REQ-100: a 900 px las pestañas apilan ícono y nombre, el desplegable tiene ancho
    mínimo, el indicador de proceso se oculta y el encabezado parte en dos líneas."""
    bloque = _bloque(_css(), 900)
    assert "flex-direction: column" in bloque
    assert "nav.tabs .off" in bloque
    assert re.search(r"header\.top \.sel-proc \{[^}]*min-width", bloque)
    assert re.search(r"header\.top \.chip-proceso \{ display: none", bloque)
    assert re.search(r"header\.top \.wrap \{[^}]*flex-wrap: wrap", bloque)
