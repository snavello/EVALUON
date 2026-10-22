"""Sin direcciones externas en lo que sirve la aplicación (REQ-133; P4, P5; plan 017,
«Criterio de aceptación numérico»: 0 direcciones externas).

Ninguna plantilla, hoja de estilo, script ni SVG nombra un dominio, un `@import url(http...)`
ni un servicio de fuentes remoto. El espacio de nombres `xmlns="http://www.w3.org/..."` de los SVG
no es un enlace (el navegador no lo descarga) y se admite.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "evaluon"
EXTENSIONES = {".html", ".css", ".js", ".svg"}
ARCHIVOS = sorted(
    p for carpeta in (RAIZ / "templates", RAIZ / "static") for p in carpeta.rglob("*")
    if p.is_file() and p.suffix in EXTENSIONES
)

ESPACIO_DE_NOMBRES = re.compile(r'xmlns(?::\w+)?\s*=\s*["\']http://www\.w3\.org/[^"\']*["\']')
PATRONES = {
    "dirección http(s)": re.compile(r"https?://", re.I),
    "dirección sin protocolo": re.compile(r"""(?:src|href|action)\s*=\s*["']//|url\(\s*["']?//""", re.I),
    "@import de otra hoja": re.compile(r"@import\s+(?:url\()?\s*[\"']?(?:https?:)?//", re.I),
    "servicio de fuentes remoto": re.compile(r"fonts\.(?:googleapis|gstatic)|use\.typekit|use\.fontawesome", re.I),
}


def externos(texto: str) -> list[str]:
    """Nombres de los patrones externos que aparecen en el texto, sin contar los xmlns."""
    limpio = ESPACIO_DE_NOMBRES.sub("", texto)
    return [nombre for nombre, patron in PATRONES.items() if patron.search(limpio)]


def test_se_revisan_plantillas_hojas_scripts_y_svg():
    """REQ-133: el recorrido cubre los cuatro tipos de archivo."""
    assert {p.suffix for p in ARCHIVOS} == EXTENSIONES
    assert len(ARCHIVOS) > 100


@pytest.mark.parametrize("ruta", ARCHIVOS, ids=lambda p: p.relative_to(RAIZ).as_posix())
def test_ningun_archivo_nombra_un_dominio_externo(ruta):
    """REQ-133 (0 direcciones externas): ni dominios, ni @import remoto, ni fuentes de terceros."""
    assert externos(ruta.read_text(encoding="utf-8")) == [], ruta.name


@pytest.mark.parametrize("texto,esperado", [
    ('<link rel="stylesheet" href="https://cdn.ejemplo.test/x.css">', "dirección http(s)"),
    ('<script src="//cdn.ejemplo.test/x.js"></script>', "dirección sin protocolo"),
    ('@import url("https://fonts.googleapis.com/css2?family=X");', "servicio de fuentes remoto"),
    ('@import "//cdn.ejemplo.test/x.css";', "@import de otra hoja"),
    ('a { background: url(//cdn.ejemplo.test/x.png) }', "dirección sin protocolo"),
])
def test_el_detector_encuentra_cada_forma(texto, esperado):
    """REQ-133 (prueba de alteración): el detector falla con cada forma de dirección externa."""
    assert esperado in externos(texto)


def test_el_espacio_de_nombres_de_los_svg_no_es_un_enlace():
    """REQ-133: `xmlns="http://www.w3.org/2000/svg"` se admite; un `href` a ese dominio, no."""
    assert externos('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>') == []
    assert externos('<svg xmlns:xlink="http://www.w3.org/1999/xlink"></svg>') == []
    assert externos('<a href="http://www.w3.org/2000/svg">x</a>') != []
