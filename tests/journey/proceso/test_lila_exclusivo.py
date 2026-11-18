"""«Vence hoy» (lila) y «Vencido» (rojo brillante) solo viven en `proceso.css` y `mapa.css`
(REQ-156, REQ-157; plan 018, «Cómo se evita la confusión con el lila del estado externo»).

- `--hoy*` y `--vencido*` no aparecen en ninguna otra hoja, plantilla ni script.
- Las pantallas nuevas (`proceso.css`, `mapa.css`, `cuadro.css` y sus plantillas) no usan el lila de
  «externo»: ni `--ext*` ni `ev-externo`.
- Cada estado lleva texto además del color y los dos temas definen los seis tokens.
"""

import re
from pathlib import Path

import pytest

from tests.journey.test_contraste import color, variables

RAIZ = Path(__file__).resolve().parents[3] / "evaluon"
ESTATICOS = RAIZ / "static"
PLANTILLAS = RAIZ / "templates"
PERMITIDAS = {"journey/proceso.css", "journey/mapa.css"}
HOJAS_NUEVAS = ("journey/proceso.css", "journey/mapa.css", "journey/cuadro.css")
PLANTILLAS_NUEVAS = ("portada", "_acciones", "_foto_pasos", "_mapa", "_plazos", "cuadro", "_cuadro")
TOKENS = ESTATICOS / "diseno" / "tokens.css"
SEIS = ("--hoy", "--hoy-bg", "--hoy-ink", "--vencido", "--vencido-bg", "--vencido-ink")

PROPIOS = re.compile(r"--(?:hoy|vencido)(?:-bg|-ink)?(?![\w-])")
AJENOS = re.compile(r"--ext(?![a-z])|ev-externo")


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.S)
    return re.sub(r"\{#.*?#\}|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", texto, flags=re.S)


def _archivos():
    for carpeta in (ESTATICOS, PLANTILLAS):
        for p in carpeta.rglob("*"):
            if p.is_file() and p.suffix in {".css", ".html", ".js"}:
                yield carpeta, p


def test_hoy_y_vencido_solo_estan_en_proceso_y_mapa():
    """REQ-157: `--hoy*` y `--vencido*` solo se nombran en proceso.css y mapa.css (y se definen en tokens.css)."""
    fuera = []
    for carpeta, p in _archivos():
        rel = p.relative_to(carpeta).as_posix()
        if p == TOKENS or (carpeta == ESTATICOS and rel in PERMITIDAS):
            continue
        if PROPIOS.search(_sin_comentarios(p.read_text(encoding="utf-8", errors="ignore"))):
            fuera.append(rel)
    assert fuera == []


def test_las_pantallas_nuevas_no_usan_el_lila_de_externo():
    """REQ-157: en las hojas y plantillas nuevas no hay `--ext*` ni `ev-externo`."""
    usan = []
    for nombre in HOJAS_NUEVAS:
        p = ESTATICOS / nombre
        if p.exists() and AJENOS.search(_sin_comentarios(p.read_text(encoding="utf-8"))):
            usan.append(nombre)
    for nombre in PLANTILLAS_NUEVAS:
        p = PLANTILLAS / "journey" / f"{nombre}.html"
        if p.exists() and AJENOS.search(_sin_comentarios(p.read_text(encoding="utf-8"))):
            usan.append(f"{nombre}.html")
    assert usan == []


def test_proceso_css_usa_los_seis_tokens_y_ningun_color_suelto():
    """REQ-156, REQ-157: proceso.css usa los seis tokens y ningún color fijo."""
    css = _sin_comentarios((ESTATICOS / "journey" / "proceso.css").read_text(encoding="utf-8"))
    for token in SEIS:
        assert re.search(re.escape(token) + r"(?![\w-])", css), token
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", css) == []


@pytest.mark.parametrize("tema", ["claro", "negro"])
def test_los_dos_temas_definen_los_seis_tokens(tema):
    """REQ-156: «Vence hoy» y «Vencido» existen en los dos temas y no se confunden con `--no` ni `--ext`."""
    v = variables(TOKENS.read_text(encoding="utf-8"), tema)
    for token in SEIS:
        assert token in v, f"{token} en {tema}"
    assert v["--vencido"] != v["--no"]
    assert v["--hoy-bg"] != v["--ext-bg"] and v["--hoy-ink"] != v["--ext-ink"]


def test_las_etiquetas_llevan_simbolo_ademas_del_color():
    """REQ-156: cada estado tiene una clase de etiqueta propia con símbolo (no solo color) en proceso.css."""
    css = (ESTATICOS / "journey" / "proceso.css").read_text(encoding="utf-8")
    for clase in ("hecho", "en-curso", "todavia-no", "con-error"):
        assert f".pr-estado.{clase}::before" in css, clase


# --- «Vence hoy» no se confunde con «externo» ni «Vencido» con «Con error» -----------------

DISTANCIA_MINIMA = 20.0  # ΔE (CIE76) mínimo entre `--hoy` y `--ext`; ~20 se distingue a simple vista


def _lab(rgb):
    """RGB 0-255 a CIE Lab (D65)."""
    lin = [(c / 255 / 12.92) if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    x = 0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = 0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def distancia(css: str, tema: str) -> float:
    v = variables(css, tema)
    a, b = _lab(color("--hoy", v)), _lab(color("--ext", v))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


@pytest.mark.parametrize("tema", ["claro", "negro"])
def test_hoy_es_distinto_de_ext_y_esta_a_distancia_minima(tema):
    """REQ-157: el lila de «Vence hoy» no es el de «externo»: distinto y a ΔE >= 20 en cada tema."""
    css = TOKENS.read_text(encoding="utf-8")
    v = variables(css, tema)
    assert v["--hoy"].lower() != v["--ext"].lower()
    assert distancia(css, tema) >= DISTANCIA_MINIMA


def test_el_test_de_distancia_falla_con_los_valores_viejos():
    """REQ-157 (prueba de alteración): con `--hoy` igual a `--ext`, como estaba, la distancia es 0 y no pasa."""
    css = TOKENS.read_text(encoding="utf-8")
    viejo = css.replace(variables(css, "claro")["--hoy"], variables(css, "claro")["--ext"], 1)
    assert viejo != css
    assert distancia(viejo, "claro") < DISTANCIA_MINIMA


@pytest.mark.parametrize("tema", ["claro", "negro"])
def test_vencido_bg_es_el_relleno_pleno(tema):
    """REQ-157 (aviso A3): `--vencido-bg` es `var(--vencido)`; eso distingue «Vencido» (rellena) de «Con error» (teñida)."""
    v = variables(TOKENS.read_text(encoding="utf-8"), tema)
    assert v["--vencido-bg"] == "var(--vencido)"
