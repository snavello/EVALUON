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

from tests.journey.test_contraste import variables

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
