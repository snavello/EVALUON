"""El componente de tablero: el contrato `Tile`, el mosaico, las hojas y el script (REQ-126,
REQ-127, REQ-141; plan 017, «Tablero: mosaicos y detalle»; ADR-0076). Datos inventados (P4).

La lógica de «debajo de la fila» y la animación se revisan en el navegador (T-316); acá se prueba
lo que dice el HTML, el CSS y el script."""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.template.loader import render_to_string

from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Detail, Tile, detail_id

RAIZ = Path(__file__).resolve().parents[2] / "evaluon"
CSS = RAIZ / "static" / "journey" / "tablero.css"
JS = RAIZ / "static" / "journey" / "tablero.js"
PLANTILLAS = RAIZ / "templates" / "journey"
NUEVAS = ("_tablero.html", "_mosaico.html", "seccion.html", "seccion_base.html")


def mosaico(**campos):
    base = dict(key="uno", title="Ofertas del acta", detail="d-s3-ofertas", big="3", unit="ofertas",
                sub="Todas con su total")
    base.update(campos)
    return render_to_string("journey/_mosaico.html", {"tile": Tile(**base)})


def columnas():
    return charts.Columns(uid="c", title="Totales", items=[
        charts.ColumnItem("Of. 1", Decimal("1100"), "1,1 M"),
        charts.ColumnItem("Of. 2", Decimal("1000"), "1,0 M", highlight=True)])


def css_limpio():
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


# --- El contrato ------------------------------------------------------------------------------


def test_los_ids_de_los_detalles_siguen_la_definicion_compartida():
    """REQ-127: `d-` más la clave del tema con el guion bajo cambiado por guion."""
    assert detail_id("s3_ofertas") == "d-s3-ofertas"
    assert detail_id("s4_dictamen") == "d-s4-dictamen"


def test_sin_cifra_no_hay_dato_y_cero_si_es_un_dato():
    """REQ-141: `big` en `None` es «sin dato»; el cero es un dato que el sistema tiene."""
    assert not Tile(key="a", title="A", detail="d-a").has_data
    assert not Tile(key="a", title="A", detail="d-a", big="").has_data
    assert Tile(key="a", title="A", detail="d-a", big=0).has_data
    assert Tile(key="a", title="A", detail="d-a", big="0").has_data


def test_sin_cifra_el_texto_por_omision_dice_pendiente_y_no_hay_otra_cifra():
    """REQ-141: no existe un valor por omisión para la cifra; el texto de falta sí."""
    tile = Tile(key="a", title="A", detail="d-a")
    assert tile.big is None and tile.missing == "Pendiente"


@pytest.mark.parametrize("campos", [{"width": 3}, {"width": 0}, {"tone": "rojo"}])
def test_un_mosaico_mal_declarado_se_rechaza(campos):
    """REQ-126: ancho de 1, 2 o 4 columnas; tono vacío o `dark`."""
    with pytest.raises(ValueError):
        Tile(key="a", title="A", detail="d-a", **campos)


def test_un_mosaico_sin_detalle_ni_enlace_se_rechaza():
    """REQ-127: todo mosaico abre un detalle (o es un enlace a otra pantalla)."""
    with pytest.raises(ValueError):
        Tile(key="a", title="A", detail="")
    assert Tile(key="a", title="A", detail="", href="/expedientes/1/evaluacion/#d-s4-dictamen")


def test_el_detalle_extra_lleva_id_titulo_y_plantilla():
    """REQ-127: un tema puede declarar un detalle propio además del de su parcial."""
    detail = Detail("d-s3-orden", "Orden económico", "journey/_economico.html", {"orden": None})
    assert detail.id == "d-s3-orden" and detail.context == {"orden": None}


# --- El mosaico -------------------------------------------------------------------------------


def test_el_mosaico_es_un_ancla_al_detalle():
    """REQ-127: sin JavaScript el mosaico es un ancla a la zona de detalles."""
    html = mosaico()
    assert re.search(r'<a [^>]*class="tile w1"', html)
    assert 'href="#d-s3-ofertas"' in html
    assert 'data-detail="d-s3-ofertas"' in html
    assert 'aria-controls="d-s3-ofertas"' in html
    assert "Ofertas del acta" in html and "Todas con su total" in html


def test_el_mosaico_con_dato_muestra_cifra_unidad_y_grafico():
    """REQ-126: cifra grande, su unidad y el gráfico del mosaico."""
    html = mosaico(chart=columnas(), width=2)
    assert re.search(r'class="big[^"]*">3<small>ofertas</small>', html)
    assert "<svg" in html and 'class="tile w2"' in html
    assert "Pendiente" not in html


def test_el_mosaico_oscuro_lleva_su_tono():
    """REQ-126: el tono `dark` es una clase del mosaico."""
    assert 'class="tile w4 dark"' in mosaico(width=4, tone="dark")


def test_el_mosaico_sin_cifra_dice_la_falta_y_no_dibuja_cifra_ni_grafico():
    """REQ-141: con `big` en `None` se dibuja `missing`; ni la cifra ni el gráfico (un gráfico
    vacío igual ocupa lugar)."""
    html = mosaico(big=None, unit="ofertas", chart=columnas(), missing="Falta cargar las ofertas")
    assert "Falta cargar las ofertas" in html
    assert 'class="big' not in html
    assert "<small>" not in html
    assert "<svg" not in html.replace('<svg class="i"', "")
    assert 'class="missing"' in html


def test_el_mosaico_sin_cifra_conserva_la_linea_de_apoyo():
    """REQ-141: la línea de apoyo explica la falta; sigue visible."""
    html = mosaico(big=None, sub="Todavía no hay ofertas")
    assert "Todavía no hay ofertas" in html


def test_el_mosaico_enlace_a_otra_pantalla_no_abre_detalle():
    """REQ-127: los mosaicos del primer panel enlazan a la sección con el detalle abierto."""
    html = mosaico(detail="", href="/expedientes/1/evaluacion/#d-s4-dictamen")
    assert 'href="/expedientes/1/evaluacion/#d-s4-dictamen"' in html
    assert "data-detail" not in html and "aria-controls" not in html


def test_el_texto_del_mosaico_se_escapa():
    """Seguridad: lo que escribe el tema se escapa."""
    html = mosaico(title="<b>x</b>", sub="<script>alert(1)</script>")
    assert "<script>" not in html and "&lt;b&gt;" in html


# --- Las hojas y el script --------------------------------------------------------------------


def test_el_detalle_se_despliega_en_cuatro_decimas_o_menos():
    """REQ-127 (criterio numérico): la transición de `grid-template-rows` dura 0,4 s o menos."""
    duraciones = [float(d) for d in re.findall(r"grid-template-rows\s+([\d.]+)s", css_limpio())]
    assert duraciones, "falta la transición de grid-template-rows"
    assert all(0 < d <= 0.4 for d in duraciones), duraciones


def test_con_reducir_movimiento_no_hay_transicion():
    """REQ-127 (ADR-0076): se respeta `prefers-reduced-motion`."""
    css = css_limpio()
    assert "prefers-reduced-motion" in css
    bloque = css[css.index("prefers-reduced-motion"):]
    assert "transition: none" in bloque


def test_las_clases_de_los_graficos_estan_declaradas_con_su_token():
    """REQ-126 (T-314): cada clase `g-*` de `charts.CLASSES` está en `tablero.css` y solo
    declara `color: var(--…)`."""
    css = css_limpio()
    esperado = {"ok": "ok", "no": "no", "nd": "nd", "pe": "pe", "ext": "ext", "lime": "lime",
                "ink": "ink", "s3": "s3", "mute": "s2", "ink2": "ink-2", "line": "line"}
    declaradas = {}
    for clase, cuerpo in re.findall(r"\.(g-[\w-]+)\s*\{([^{}]*)\}", css):
        declaradas[clase] = [d.strip() for d in cuerpo.split(";") if d.strip()]
    assert set(declaradas) == charts.CLASSES
    for sufijo, token in esperado.items():
        assert declaradas[f"g-{sufijo}"] == [f"color: var(--{token})"], sufijo
    assert re.search(r"\.grafico\s*\{[^}]*display:\s*block[^}]*width:\s*100%[^}]*height:\s*auto",
                     css)


def test_las_clases_del_cuadro_economico_estan_declaradas():
    """REQ-130 (T-314): `_economico.html` usa clases que esta hoja tiene que declarar."""
    css = css_limpio()
    html = (PLANTILLAS / "_economico.html").read_text(encoding="utf-8")
    usadas = {c for g in re.findall(r'class="([^"]*)"', html) for c in g.split()}
    usadas -= {"sr-only"}
    sin_declarar = sorted(c for c in usadas if not re.search(rf"\.{re.escape(c)}\b", css))
    assert sin_declarar == []


def test_las_clases_de_los_graficos_que_usan_las_plantillas_son_las_declaradas():
    """REQ-126: ninguna plantilla de gráfico usa una clase `g-*` que la hoja no declare."""
    css = css_limpio()
    usadas = set()
    for plantilla in (PLANTILLAS / "graficos").glob("*.html"):
        usadas.update(re.findall(r"\bg-[\w-]+", plantilla.read_text(encoding="utf-8")))
    assert usadas, "las plantillas de gráficos no usan clases g-*"
    assert all(re.search(rf"\.{re.escape(c)}\s*\{{", css) for c in usadas if c in charts.CLASSES)


def test_la_hoja_solo_usa_tokens():
    """REQ-133: ni colores sueltos ni direcciones; todo color sale de `var(--…)`."""
    css = css_limpio()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"\b(rgb|rgba|hsl)\(", css)
    assert "http" not in css and "@import" not in css


def test_el_texto_no_lleva_opacidad():
    """REQ-133: ningún texto se atenúa con `opacity` (el contraste se mide con colores planos)."""
    assert "opacity" not in css_limpio()


def test_ink3_no_va_en_la_hoja_del_tablero():
    """REQ-133: `--ink-3` no tiene par con `--tile-h` (el mosaico abierto o en hover); la hoja
    del tablero no lo usa."""
    assert "--ink-3" not in css_limpio()


@pytest.mark.parametrize("nombre", NUEVAS)
def test_las_plantillas_nuevas_no_llevan_estilos_en_linea_ni_scripts(nombre):
    """ADR-0076: la política de contenido (`default-src 'self'`) no admite `style=` ni scripts
    en línea."""
    html = (PLANTILLAS / nombre).read_text(encoding="utf-8")
    assert "style=" not in html
    for etiqueta in re.findall(r"<script\b[^>]*>", html):
        assert "src=" in etiqueta, etiqueta
    assert not re.search(r"\son\w+=", html)


def test_el_script_es_chico_y_hace_lo_que_dice_el_plan():
    """REQ-127 (ADR-0076): pocas líneas; roles y atributos, el hash y el movimiento reducido."""
    js = JS.read_text(encoding="utf-8")
    codigo = [l for l in js.splitlines()
              if l.strip() and not l.strip().startswith(("//", "/*", "*"))]
    assert len(codigo) <= 100, len(codigo)
    for pieza in ("role", "aria-expanded", "aria-controls", "location.hash", "offsetTop",
                  "prefers-reduced-motion", "hashchange", "abre"):
        assert pieza in js, pieza
    assert "http" not in js and "eval(" not in js and "innerHTML" not in js


def test_la_zona_de_detalles_es_visible_sin_script():
    """ADR-0076: sin JavaScript los detalles quedan a la vista; solo `con-js` los oculta."""
    css = css_limpio()
    for selector, _ in re.findall(r"([^{}]+)\{([^{}]*display:\s*none[^{}]*)\}", css):
        if "detalles" in selector:
            assert "con-js" in selector, selector
    assert "grid-template-rows: 0fr" in css
