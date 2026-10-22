"""Archivos estáticos de la feature 017: tipografía alojada y marca nueva (REQ-133, REQ-142; T-310).
No usa la base de datos ni la red. Material público (P4); nada se pide a un dominio externo (P5)."""

import hashlib
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "evaluon" / "static"
FUENTES = STATIC / "diseno" / "fuentes"
MARCA = STATIC / "marca"
WOFF2 = ("hanken-grotesk-latin.woff2", "hanken-grotesk-latin-ext.woff2")
SVG_NUEVOS = ("logotipo-claro.svg", "logotipo-negro.svg", "isotipo-claro.svg", "isotipo-negro.svg")
XMLNS = 'xmlns="http://www.w3.org/2000/svg"'
EXTERNA = re.compile(r"https?://|//[a-z0-9.-]+\.[a-z]{2,}|@import\s+url|fonts\.googleapis", re.I)


@pytest.mark.parametrize("nombre", WOFF2)
def test_las_fuentes_existen_y_son_woff2(nombre):
    """REQ-133: los dos subconjuntos de Hanken Grotesk están alojados, no vacíos y son woff2
    de verdad (cabecera «wOF2»)."""
    ruta = FUENTES / nombre
    assert ruta.is_file() and ruta.stat().st_size > 1000
    assert ruta.read_bytes()[:4] == b"wOF2"


def test_la_licencia_nombra_ofl_y_las_huellas_coinciden():
    """REQ-133: LICENCIA.txt nombra la SIL OFL 1.1, el origen y la huella SHA-256 de cada archivo."""
    texto = (FUENTES / "LICENCIA.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in texto and "1.1" in texto
    assert "Hanken Grotesk" in texto and "https://cdn.jsdelivr.net/npm/@fontsource-variable/" in texto
    for nombre in WOFF2:
        huella = hashlib.sha256((FUENTES / nombre).read_bytes()).hexdigest()
        assert nombre in texto and huella in texto, nombre


def test_los_font_face_de_tokens_apuntan_a_archivos_locales():
    """REQ-133: si tokens.css declara @font-face, cada url() es un archivo local que existe
    (vale en cualquier orden de integración con T-309)."""
    tokens = STATIC / "diseno" / "tokens.css"
    css = tokens.read_text(encoding="utf-8")
    for url in re.findall(r"@font-face[^}]*?url\(\s*['\"]?([^)'\"]+)", css, re.S):
        assert not url.startswith(("http", "//", "data:")), url
        assert (tokens.parent / url).resolve().is_file(), url


@pytest.mark.parametrize("nombre", SVG_NUEVOS)
def test_los_svg_de_la_marca_existen_y_no_tienen_texto(nombre):
    """REQ-142: los cuatro SVG de la marca 017 están en static/marca/ con las letras dibujadas
    como formas (sin <text>)."""
    ruta = MARCA / nombre
    assert ruta.is_file() and ruta.stat().st_size > 200
    svg = ruta.read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<svg") and "<text" not in svg


@pytest.mark.parametrize("nombre", SVG_NUEVOS)
def test_los_svg_de_la_marca_son_los_aprobados(nombre):
    """REQ-142: la copia es idéntica a la aprobada en docs/diseno/marca/017/."""
    origen = Path(__file__).resolve().parents[1] / "docs" / "diseno" / "marca" / "017" / nombre
    assert (MARCA / nombre).read_bytes() == origen.read_bytes()


def test_ningun_archivo_apunta_a_un_dominio_externo():
    """REQ-133, REQ-142 (P5): ni las fuentes, ni la licencia, ni los SVG nuevos piden nada a un
    dominio externo; del SVG solo se admite el espacio de nombres xmlns, que no es un enlace."""
    for nombre in SVG_NUEVOS:
        svg = (MARCA / nombre).read_text(encoding="utf-8")
        assert not EXTERNA.search(svg.replace(XMLNS, "")), nombre
        assert "xlink:href" not in svg and "<image" not in svg, nombre
    for nombre in WOFF2:
        assert b"http://" not in (FUENTES / nombre).read_bytes()[:200], nombre
