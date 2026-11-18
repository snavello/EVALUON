"""Geometría constante del mapa del proceso (T-349, rehecha en T-363; REQ-158): Python puro, sin navegador.

La aritmética de las posiciones no estaba probada: estos tests son la prueba. Las cajas de las
tarjetas se toman con su alto MÁXIMO (`mapa.ALTO_MAXIMO`), que es el peor caso: si con ese alto no se
pisan ni las toca un conector, tampoco con el alto real, que es siempre menor o igual.
"""

import re
from pathlib import Path

from evaluon.journey.proceso import mapa

MARGEN = 12
OCHO = {(1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7)}
CSS = Path(__file__).resolve().parents[3] / "evaluon" / "static" / "journey" / "mapa.css"


def _caja(n):
    x, y = mapa.POSICIONES[n]
    return x, y, x + mapa.ANCHO, y + mapa.ALTO_MAXIMO


def _entra(tramo, caja, margen):
    """¿El tramo (horizontal o vertical) entra en el interior de la caja agrandada por `margen`?
    Rozar el borde agrandado no cuenta."""
    (ax, ay), (bx, by) = tramo
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    return min(ax, bx) < x1 and max(ax, bx) > x0 and min(ay, by) < y1 and max(ay, by) > y0


def test_REQ_158_las_siete_tarjetas_caben_en_el_lienzo_con_su_alto_maximo():
    """REQ-158: las siete tarjetas, con el alto máximo, entran en el lienzo."""
    assert sorted(mapa.POSICIONES) == [1, 2, 3, 4, 5, 6, 7]
    ancho, alto = mapa.LIENZO
    for n in mapa.POSICIONES:
        x0, y0, x1, y1 = _caja(n)
        assert x0 >= 0 and y0 >= 0 and x1 <= ancho and y1 <= alto, n


def test_REQ_158_ninguna_tarjeta_se_superpone_ni_con_su_alto_maximo():
    """REQ-158: ninguna tarjeta pisa a otra aunque las dos midan el máximo."""
    for a in mapa.POSICIONES:
        for b in mapa.POSICIONES:
            if a < b:
                ax0, ay0, ax1, ay1 = _caja(a)
                bx0, by0, bx1, by1 = _caja(b)
                assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, (a, b)


def test_REQ_158_los_conectores_son_exactamente_los_ocho():
    """REQ-158: 1→2, 2→4, 3→4, 3→5, 4→5, 4→6, 4→7 y 6→7, y nada más."""
    assert set(mapa.CONECTORES) == OCHO and len(mapa.CONECTORES) == 8
    assert {(c.origen, c.destino) for c in mapa.TRAZOS} == OCHO
    assert len(mapa.TRAZOS) == 8


def test_REQ_158_ningun_tramo_corta_una_tarjeta_con_margen():
    """REQ-158: ningún tramo de conector entra en una tarjeta ajena ni a 12 px de ella (con el alto
    máximo, o sea: nunca sobre su texto) ni en el interior de las dos suyas; solo toca su borde."""
    for c in mapa.TRAZOS:
        assert c.tramos
        for tramo in c.tramos:
            for n in mapa.POSICIONES:
                propio = n in (c.origen, c.destino)
                assert not _entra(tramo, _caja(n), 0 if propio else MARGEN), (c.origen, c.destino, n, tramo)


def test_REQ_158_el_trazo_sale_y_entra_a_24_px_del_borde_superior():
    """REQ-158: sale del borde derecho a y+24 y entra a y+24 del destino (por su borde izquierdo, o por
    el derecho en un lazo de la misma columna), con punta: el alto de la tarjeta no los mueve."""
    for c in mapa.TRAZOS:
        ox, oy = mapa.POSICIONES[c.origen]
        dx, dy = mapa.POSICIONES[c.destino]
        lazo = dx == ox
        entrada = (dx + mapa.ANCHO if lazo else dx, dy + mapa.SALIDA_Y)
        assert mapa.SALIDA_Y == 24
        assert c.tramos[0][0] == (ox + mapa.ANCHO, oy + 24)
        assert c.tramos[-1][1] == entrada
        assert c.d.startswith("M ")
        assert len(c.punta) == 3 and c.punta[0] == entrada
        sentido = 1 if lazo else -1  # la punta apunta hacia la izquierda en un lazo y hacia la derecha si no
        assert all(p[0] == entrada[0] + sentido * mapa.PUNTA for p in c.punta[1:])
        for (ax, _), (bx, _) in c.tramos:  # todo queda en el hueco de la derecha del origen o entre columnas
            if lazo:
                assert ox + mapa.ANCHO <= min(ax, bx) and max(ax, bx) <= ox + mapa.ANCHO + mapa.HUECO
            else:
                assert ox + mapa.ANCHO <= min(ax, bx) and max(ax, bx) <= dx


def test_REQ_158_el_codo_tiene_lugar_para_su_radio_y_la_punta():
    """REQ-158: el tramo vertical es más largo que dos radios y entre el codo y la tarjeta cabe la punta."""
    for c in mapa.TRAZOS:
        for (ax, ay), (bx, by) in c.tramos:
            if ax == bx:
                assert abs(by - ay) >= 2 * mapa.RADIO
        (xa, ya), (xb, yb) = c.tramos[-1]
        assert abs(xb - xa) == 0 or abs(xb - xa) >= mapa.RADIO + mapa.PUNTA, (c.origen, c.destino)


def test_REQ_158_hay_exactamente_tres_formas_de_conector():
    """REQ-158: rectos (1→2, 2→4, 3→5, 4→7), codos (3→4, 4→6) y lazos (4→5, 6→7); solo los lazos vuelven
    por el borde derecho."""
    rectos = {(c.origen, c.destino) for c in mapa.TRAZOS if len(c.tramos) == 1}
    lazos = {(c.origen, c.destino) for c in mapa.TRAZOS
             if mapa.POSICIONES[c.origen][0] == mapa.POSICIONES[c.destino][0]}
    assert rectos == {(1, 2), (2, 4), (3, 5), (4, 7)}
    assert lazos == {(4, 5), (6, 7)}
    assert OCHO - rectos - lazos == {(3, 4), (4, 6)}


def _px(texto, propiedad):
    return int(re.search(rf"{propiedad}:\s*(\d+)px", texto).group(1))


def _regla(texto, selector):
    return re.search(rf"(?:^|\n){re.escape(selector)}\s*\{{([^}}]*)\}}", texto).group(1)


def test_REQ_158_el_alto_maximo_recalculado_desde_la_hoja_cabe_en_el_presupuesto():
    """REQ-158: se suma, con las medidas que declara `mapa.css`, el alto de una tarjeta en el peor caso
    (nombre y dato en 2 líneas, 3 tareas de 2 líneas, la etiqueta de una tarea, «+ N más» y
    advertencias) y no puede pasar de `mapa.ALTO_MAXIMO`; si alguien agranda un relleno, una línea o
    un margen sin tocar el presupuesto, falla."""
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    nodo = _regla(css, ".mp-nodo")
    relleno = re.search(r"padding:\s*(\d+)px \d+px (\d+)px", nodo)
    borde = 2 * _px(nodo, "border")
    assert _px(nodo, "line-height") == 14
    encabezado = max(_px(_regla(css, ".mp-enc"), "min-height"), 2 * _px(_regla(css, ".mp .mp-nom"), "line-height"))
    margen_dato = int(re.search(r"margin:\s*(\d+)px", _regla(css, ".mp-dato")).group(1))
    dato = margen_dato + 2 * _px(_regla(css, ".mp-dato"), "line-height")
    pie = _px(_regla(css, ".mp-pie"), "min-height") + int(re.search(r"margin:\s*(\d+)px", _regla(css, ".mp-pie")).group(1))
    margen_tareas = int(re.search(r"margin:\s*(\d+)px", _regla(css, ".mp-tareas")).group(1))
    relleno_tarea = int(re.search(r"padding:\s*(\d+)px", _regla(css, ".mp-tarea a")).group(1))
    una_tarea = 1 + 2 * relleno_tarea + 2 * _px(_regla(css, ".mp-txt"), "line-height")
    etiqueta = (int(re.search(r"margin-top:\s*(\d+)px", _regla(css, ".mp-tarea .mp-hoy, .mp-tarea .mp-vencido")).group(1))
                + _px(_regla(css, ".mp-tarea .mp-hoy, .mp-tarea .mp-vencido"), "line-height")
                + 2 * 1)  # el borde de 1 px
    resto = 1 + 2 * int(re.search(r"padding:\s*(\d+)px", _regla(css, ".mp-resto")).group(1)) \
        + _px(_regla(css, ".mp-resto"), "line-height")
    total = (int(relleno.group(1)) + int(relleno.group(2)) + borde + encabezado + dato + pie
             + margen_tareas + 3 * una_tarea + etiqueta + resto)
    assert total <= mapa.ALTO_MAXIMO, (total, mapa.ALTO_MAXIMO)
    assert total >= mapa.ALTO_MAXIMO - 4, "el presupuesto dejó de ser el real: ajustalo para no desperdiciar alto"
    assert dict(mapa.PRESUPUESTO)["tareas (3 × 2 líneas)"] == margen_tareas + 3 * una_tarea


def test_REQ_158_el_presupuesto_suma_el_alto_maximo():
    """REQ-158: `ALTO_MAXIMO` es la suma de las partes del presupuesto."""
    assert mapa.PRESUPUESTO_ALTO == mapa.ALTO_MAXIMO == sum(a for _, a in mapa.PRESUPUESTO) == 297


def test_REQ_158_el_lienzo_entra_entero_a_1280_px_de_ventana():
    """REQ-158: el lienzo, el relleno de la caja del mapa (2 × 16), los márgenes de la página (2 × 36: el
    contenido llega a 1176 px y no crece más) y una barra de desplazamiento de 15 px caben en 1280 px; y el
    lienzo no es más ancho que la caja de 1144 px que le da la página."""
    assert mapa.VENTANA_MINIMA == mapa.LIENZO[0] + 32 + 72 + 15 == 1263
    assert mapa.VENTANA_MINIMA <= 1280
    assert mapa.LIENZO[0] <= 1176 - 32


def test_REQ_158_constantes_de_la_disposicion():
    """REQ-158: cuatro columnas de 252 px con huecos de 32, dos carriles y las posiciones de las siete."""
    assert mapa.ANCHO == 252 and mapa.HUECO == 32 and mapa.LIENZO == (1144, 624)
    assert mapa.POSICIONES == {1: (8, 8), 2: (292, 8), 3: (292, 319), 4: (576, 8),
                               5: (576, 319), 6: (860, 319), 7: (860, 8)}
    assert mapa.COLUMNAS == (("Publicación", 8), ("Requisitos y ofertas", 292),
                             ("Cruce y comparación", 576), ("Evaluación y dictamen", 860))
    # el camino principal va arriba y todas las tarjetas de una columna comparten su x
    assert {mapa.POSICIONES[n][1] for n in (1, 2, 4, 7)} == {8}
    assert {mapa.POSICIONES[n][1] for n in (3, 5, 6)} == {319}
