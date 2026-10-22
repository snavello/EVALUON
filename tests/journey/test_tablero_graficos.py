"""Los siete gráficos SVG del tablero (REQ-126, REQ-141; plan 017, «Gráficos»; T-314).

Cada gráfico es una dataclass de `evaluon/journey/tablero/charts.py` con la plantilla que lo
dibuja. Todo SVG usa atributos de presentación y `currentColor`, nunca `style=` (la política de
contenido es `default-src 'self'`), y toda marca lima lleva su contorno `--ink` (guía visual, 4).
Los datos son inventados (P4).
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.utils import translation

from evaluon.journey.tablero import charts

RAIZ = Path(__file__).resolve().parents[2] / "evaluon" / "templates" / "journey" / "graficos"
NOMBRES = ("bars", "donuts", "lollipop", "timeline", "stack", "columns", "heat")
MARCAS = re.compile(r"<(?:circle|rect|path|line|polyline|polygon|ellipse)\b")
ETIQUETAS = re.compile(r"<[^>]+>")


def con_datos():
    """Un gráfico de cada tipo con los datos mínimos."""
    return {
        "bars": charts.Bars(uid="b", title="Avance", rows=[
            charts.BarRow("Pliego", 75, "75 %"), charts.BarRow("Ofertas", 100, "100 %", "lime")],
            maximum=100),
        "donuts": charts.Donuts(uid="d", title="Resultado por oferta", items=[
            charts.DonutItem("Oferta 1", ok=10, no=2, nd=1, pe=0),
            charts.DonutItem("Oferta 2", ok=0, no=0, nd=0, pe=13)]),
        "lollipop": charts.Lollipop(uid="l", title="Orden económico", rows=[
            charts.LollipopRow("Oferta 2", Decimal("1000"), "$ 1.000,00", "la más baja", low=True),
            charts.LollipopRow("Oferta 1", Decimal("1100"), "$ 1.100,00", "+10 %"),
            charts.LollipopRow("Oferta 3", Decimal("1250"), "$ 1.250,00", "la más alta",
                               high=True)]),
        "timeline": charts.Timeline(uid="t", title="Plazos", events=[
            charts.TimelineEvent("Apertura", "22/09", "past"),
            charts.TimelineEvent("Hoy", "21/10", "now"),
            charts.TimelineEvent("Vence el mantenimiento", "21/11", "future"),
            charts.TimelineEvent("Dictamen de la Comisión", "Pendiente", "pending")]),
        "stack": charts.Stack(uid="s", title="Requisitos por tipo", parts=[
            charts.StackPart("Formales", 6), charts.StackPart("Técnicos", 9),
            charts.StackPart("Económicos", 4), charts.StackPart("Externos", 4, "ext")]),
        "columns": charts.Columns(uid="c", title="Totales", items=[
            charts.ColumnItem("Of. 1", Decimal("1100"), "1,1 M"),
            charts.ColumnItem("Of. 2", Decimal("1000"), "1,0 M", highlight=True),
            charts.ColumnItem("Of. 3", Decimal("1250"), "1,25 M")]),
        "heat": charts.Heat(uid="h", title="Cumplimiento por tipo", columns=["Of. 1", "Of. 2"],
                            rows=[charts.HeatRow("Formales", [charts.HeatCell(5, 6),
                                                             charts.HeatCell(2, 6)]),
                                  charts.HeatRow("Técnicos", [charts.HeatCell(0, 9), None])]),
    }


def sin_datos():
    """Un gráfico de cada tipo con series vacías o valores `None`."""
    return {
        "bars": charts.Bars(uid="b", title="Avance", rows=[charts.BarRow("Pliego", None)]),
        "donuts": charts.Donuts(uid="d", title="Resultado", items=[]),
        "lollipop": charts.Lollipop(uid="l", title="Orden", rows=[
            charts.LollipopRow("Oferta 1", None, "")]),
        "timeline": charts.Timeline(uid="t", title="Plazos", events=[]),
        "stack": charts.Stack(uid="s", title="Tipos", parts=[charts.StackPart("Formales", None)]),
        "columns": charts.Columns(uid="c", title="Totales", items=[
            charts.ColumnItem("Of. 1", None)]),
        "heat": charts.Heat(uid="h", title="Calor", columns=["Of. 1"], rows=[
            charts.HeatRow("Formales", [None])]),
    }


def dibujar(grafico):
    return render_to_string(grafico.template, {"chart": grafico})


def etiquetas(html):
    return ETIQUETAS.findall(html)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_cada_grafico_se_dibuja_con_datos_minimos(nombre):
    """REQ-126: con datos mínimos el gráfico se dibuja con marcas, título y descripción."""
    grafico = con_datos()[nombre]
    assert grafico.has_data
    html = dibujar(grafico)
    assert html.lstrip().startswith("<svg")
    assert len(MARCAS.findall(html)) > 0
    assert 'role="img"' in html


@pytest.mark.parametrize("nombre", NOMBRES)
def test_cada_grafico_se_dibuja_sin_datos_y_sin_marcas(nombre):
    """REQ-141: valores `None` o series vacías no dibujan ninguna marca ni cifra inventada."""
    grafico = sin_datos()[nombre]
    assert not grafico.has_data
    html = dibujar(grafico)
    assert "<svg" in html
    assert MARCAS.findall(html) == []
    sin_titulo = re.sub(r"<(title|desc)[^>]*>.*?</\1>", "", html, flags=re.S)
    assert not re.search(r">\s*\d", sin_titulo)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_titulo_y_descripcion_accesibles(nombre):
    """REQ-126: el SVG nombra su título y su descripción con ids que existen en el SVG."""
    grafico = con_datos()[nombre]
    html = dibujar(grafico)
    ids = re.search(r'aria-labelledby="([^"]+)"', html).group(1).split()
    assert len(ids) == 2
    for ident in ids:
        assert f'id="{ident}"' in html
    assert f">{grafico.title}</title>" in html
    assert "<desc" in html


@pytest.mark.parametrize("nombre", NOMBRES)
def test_la_descripcion_automatica_dice_los_datos(nombre):
    """REQ-126: sin descripción escrita, la accesible se arma con los datos del gráfico."""
    grafico = con_datos()[nombre]
    assert len(grafico.description) > 10


@pytest.mark.parametrize("nombre", NOMBRES)
def test_el_color_sale_de_currentcolor_y_de_las_clases(nombre):
    """REQ-133: `fill` y `stroke` valen solo `currentColor` o `none`; nada de colores sueltos
    ni de `var()` dentro del SVG (el color lo da la clase `g-*`)."""
    html = dibujar(con_datos()[nombre])
    for atributo, valor in re.findall(r'\b(fill|stroke|color)="([^"]*)"', html):
        assert valor in ("currentColor", "none"), (atributo, valor)
    assert "#" not in "".join(re.findall(r'(?:fill|stroke)="[^"]*"', html))
    assert "var(" not in html
    clases = {c for grupo in re.findall(r'class="([^"]*)"', html) for c in grupo.split()}
    assert {c for c in clases if c.startswith("g-")} <= charts.CLASSES


@pytest.mark.parametrize("nombre", NOMBRES)
def test_no_hay_estilos_scripts_ni_direcciones(nombre):
    """REQ-133: ni `style=`, ni scripts, ni manejadores, ni enlaces, ni dominios (CSP
    `default-src 'self'`)."""
    html = dibujar(con_datos()[nombre])
    for prohibido in ("style=", "<script", "href=", "xlink", "http:", "https:", "javascript:"):
        assert prohibido not in html, prohibido
    assert not re.search(r"\son\w+=", html)
    texto = " ".join(re.findall(r">([^<]+)<", html))
    assert not re.search(r"\b[\w-]+\.(?:com|org|net|gob|ar|io)\b", texto, re.I)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_las_plantillas_no_tienen_estilos_ni_dominios(nombre):
    """REQ-133: el archivo de cada plantilla de gráfico está limpio, con o sin datos."""
    texto = (RAIZ / f"_{nombre}.html").read_text(encoding="utf-8")
    assert "style=" not in texto
    assert not re.search(r"https?:|<script|xlink:href|\sxmlns", texto)
    assert not re.search(r"<text[^>]*>\s*[\w.-]+\.(?:com|org|net|gob|ar)\b", texto)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_los_numeros_no_salen_con_coma_decimal(nombre):
    """REQ-126: con la localización argentina los números del SVG siguen con punto decimal
    (una coma rompe el dibujo)."""
    with translation.override("es-ar"):
        html = dibujar(con_datos()[nombre])
    for valor in re.findall(r'\b(?:cx|cy|x|y|x1|x2|y1|y2|r|width|height|opacity|fill-opacity|'
                            r'stroke-width|stroke-dasharray|stroke-dashoffset)="([^"]*)"', html):
        assert "," not in valor, valor
    assert "viewBox=" in html
    assert "," not in re.search(r'viewBox="([^"]*)"', html).group(1)


@pytest.mark.parametrize("nombre", NOMBRES)
def test_toda_marca_lima_lleva_su_contorno_ink(nombre):
    """REQ-133 (guía visual, 4): en el tema claro el lima no contrasta; toda marca `g-lime`
    va sobre una marca `g-ink` un poco mayor, inmediatamente antes."""
    html = dibujar(con_datos()[nombre])
    tags = etiquetas(html)
    for i, tag in enumerate(tags):
        if "g-lime" in tag:
            assert "g-ink" in tags[i - 1], (tags[i - 1], tag)


def test_las_marcas_lima_existen_donde_se_resalta():
    """REQ-133: la más baja (lollipop), la columna destacada, la barra completa y «hoy» llevan
    lima; así el test anterior no es vacío."""
    for nombre in ("lollipop", "columns", "bars", "timeline"):
        assert "g-lime" in dibujar(con_datos()[nombre]), nombre


def test_un_tono_desconocido_falla():
    """El tono viene de una lista cerrada: una errata no pasa a CSS."""
    with pytest.raises(ValueError):
        charts.BarRow("X", 1, tone="rojo")
    with pytest.raises(ValueError):
        charts.StackPart("X", 1, tone="fucsia")
    with pytest.raises(ValueError):
        charts.TimelineEvent("X", "1/1", "mañana")


# --- Cada tipo en particular -------------------------------------------------------------------


def test_barras_la_proporcion_y_none():
    """REQ-126: el ancho de la barra es proporcional al máximo; una fila sin valor no se dibuja."""
    grafico = charts.Bars(uid="b", title="t", maximum=100, rows=[
        charts.BarRow("A", 50, "50 %"), charts.BarRow("B", None), charts.BarRow("C", 100)])
    filas = grafico.geometry
    assert [f["label"] for f in filas] == ["A", "C"]
    assert float(filas[0]["w"]) * 2 == pytest.approx(float(filas[1]["w"]))


def test_donas_los_arcos_suman_el_total_y_conservan_los_estados():
    """REQ-126: la dona de una oferta reparte el círculo según sus cuatro estados, cada uno con
    su clase; sin ningún requisito no hay arcos."""
    html = dibujar(con_datos()["donuts"])
    for clase in ("g-ok", "g-no", "g-nd", "g-pe"):
        assert clase in html
    assert ">10/13<" in html
    vacia = charts.Donuts(uid="d", title="t", items=[charts.DonutItem("O", 0, 0, 0, 0)])
    assert not vacia.has_data
    assert MARCAS.findall(dibujar(vacia)) == []


def test_lollipop_ordena_por_valor_y_marca_la_mas_baja_y_la_mas_alta():
    """REQ-130: la más baja con lima y contorno, la más alta en negro; a mayor valor, más a la
    derecha; los empatados quedan en el mismo punto."""
    grafico = charts.Lollipop(uid="l", title="t", rows=[
        charts.LollipopRow("A", Decimal("100"), "100", low=True),
        charts.LollipopRow("B", Decimal("100"), "100", low=True),
        charts.LollipopRow("C", Decimal("150"), "150", high=True)])
    puntos = grafico.geometry
    assert puntos[0]["x"] == puntos[1]["x"]
    assert float(puntos[2]["x"]) > float(puntos[0]["x"])
    html = dibujar(grafico)
    assert "la más baja" not in html  # el texto lo escribe quien arma la fila
    assert html.count("g-lime") == 2
    assert "g-ink" in html


def test_lollipop_con_un_solo_valor_o_todos_iguales_no_divide_por_cero():
    """REQ-141: un solo valor, o todos iguales, se dibuja igual."""
    uno = charts.Lollipop(uid="l", title="t", rows=[
        charts.LollipopRow("A", Decimal("100"), "100", low=True)])
    assert MARCAS.findall(dibujar(uno))
    cero = charts.Lollipop(uid="l", title="t", rows=[
        charts.LollipopRow("A", Decimal("0"), "0", low=True)])
    assert MARCAS.findall(dibujar(cero))


def test_linea_de_tiempo_estados():
    """REQ-131 (soporte): pasado, hoy, futuro y pendiente se distinguen por forma, no solo por
    color; el pendiente dice «Pendiente» y no una fecha."""
    html = dibujar(con_datos()["timeline"])
    assert "Pendiente" in html
    assert "22/09" in html and "21/11" in html
    assert html.count("<circle") >= 4


def test_apilado_deja_un_hueco_entre_series_vecinas():
    """Guía visual: `--s2` y `--s3` a 1,54:1 en el tema negro; entre series vecinas hay un
    hueco, así que la diferencia no depende solo del color."""
    partes = con_datos()["stack"].geometry
    for a, b in zip(partes, partes[1:]):
        assert float(b["x"]) - (float(a["x"]) + float(a["w"])) >= 1
    assert len({p["tone"] for p in partes}) == len(partes)


def test_apilado_ignora_valores_none_pero_conserva_la_leyenda_de_los_que_existen():
    """REQ-141: un tipo sin valor no ocupa lugar."""
    grafico = charts.Stack(uid="s", title="t", parts=[
        charts.StackPart("Formales", 3), charts.StackPart("Técnicos", None)])
    assert [p["label"] for p in grafico.geometry] == ["Formales"]


def test_columnas_proporcionales_y_la_destacada():
    """REQ-126: la altura es proporcional al mayor valor y solo la destacada lleva lima."""
    columnas = con_datos()["columns"].geometry
    altos = {c["label"]: float(c["h"]) for c in columnas}
    assert altos["Of. 3"] > altos["Of. 1"] > altos["Of. 2"]
    assert altos["Of. 2"] / altos["Of. 3"] == pytest.approx(1000 / 1250, abs=0.01)
    assert sum(1 for c in columnas if c["highlight"]) == 1


def test_calor_celdas_con_ratio_y_sin_dato():
    """REQ-141: la celda sin dato (`None`) o con total 0 no dibuja marca ni cifra."""
    grafico = charts.Heat(uid="h", title="t", columns=["A", "B", "C"], rows=[
        charts.HeatRow("Formales", [charts.HeatCell(3, 6), None, charts.HeatCell(0, 0)])])
    html = dibujar(grafico)
    assert ">3/6<" in html
    assert "0/0" not in html
    celdas = grafico.geometry["cells"]
    assert len(celdas) == 1
    assert float(celdas[0]["opacity"]) == pytest.approx(0.5 * 0.55)


def test_los_textos_se_escapan():
    """Un nombre con marcas HTML no abre una etiqueta (los nombres de oferentes los escribe una
    persona)."""
    grafico = charts.Bars(uid="b", title="t", rows=[charts.BarRow("<b>x</b>", 1, "1")])
    html = dibujar(grafico)
    assert "<b>" not in html and "&lt;b&gt;" in html


# --- Correcciones de la verificación (H-1 y H-3) ----------------------------------------------------


def _ancho_estimado(texto, tamano):
    """Ancho en unidades del SVG, por caracteres (0,6 del cuerpo por letra: cota alta)."""
    return len(texto) * 0.6 * tamano


def test_lollipop_la_nota_de_la_mas_alta_entra_en_el_dibujo():
    """REQ-130 (H-1): con totales de ocho cifras la nota de la más alta no pasa el borde
    derecho del `viewBox`; el texto completo queda en la descripción."""
    grafico = charts.Lollipop(uid="l", title="t", rows=[
        charts.LollipopRow("Oferta 1", Decimal("87450123.50"), "$ 87.450.123,50", "La más baja",
                           low=True),
        charts.LollipopRow("Oferta 2", Decimal("103200000.00"), "$ 103.200.000,00", "+18,0 %"),
        charts.LollipopRow("Oferta 3", Decimal("207800999.99"), "$ 207.800.999,99",
                           "La más alta · +137,6 % sobre la más baja", high=True)])
    ancho = float(grafico.view_box.split()[2])
    for punto in grafico.geometry:
        inicio = float(punto["vx"])
        assert inicio + _ancho_estimado(punto["text"], 12) <= ancho
        assert inicio + _ancho_estimado(punto["note"], 10) <= ancho
    assert "sobre la más baja" in grafico.description


def test_lollipop_ancho_por_omision_no_cambia_con_textos_cortos():
    """REQ-130 (H-1): con textos cortos el dibujo conserva su ancho de siempre."""
    assert con_datos()["lollipop"].view_box.split()[2] == "560"


def test_dos_graficos_del_mismo_tipo_no_repiten_ids():
    """REQ-126 (H-3): sin `uid`, cada gráfico genera ids propios; con `uid`, los suyos."""
    a, b = charts.Bars(rows=[charts.BarRow("A", 1)]), charts.Bars(rows=[charts.BarRow("B", 1)])
    assert a.title_id != b.title_id and a.desc_id != b.desc_id
    html = dibujar(a) + dibujar(b)
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids)) == 4
    assert charts.Bars(uid="x").title_id == "x-t"
