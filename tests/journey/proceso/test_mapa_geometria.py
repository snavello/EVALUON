"""Geometría del mapa del proceso (T-349, rehecha en T-363; REQ-158): Python puro, sin navegador.

La aritmética de las posiciones no estaba probada: estos tests son la prueba. La geometría ya no es una
constante: es una función del contenido (`mapa.geometria(k, m)`, con `k` el escalón de la fila de arriba y
`m` el de la de abajo), así que cada regla se prueba para TODOS los pares de escalones. Las cajas de las
tarjetas se toman con el alto de su escalón: como el alto estimado es siempre mayor o igual que el real
(lo mide un navegador aparte), si con ese alto no se pisan ni las toca un conector, tampoco con el real.
"""

import re
from itertools import product
from pathlib import Path

from evaluon.journey.proceso import mapa

MARGEN = 12
OCHO = {(1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7)}
CSS = Path(__file__).resolve().parents[3] / "evaluon" / "static" / "journey" / "mapa.css"
PARES = list(product(range(len(mapa.ESCALONES)), repeat=2))


def _cajas(g):
    """`{n: (x0, y0, x1, y1)}` con el alto del escalón de su fila."""
    cajas = {}
    for n, (x, y) in g.posiciones.items():
        alto = mapa.ESCALONES[g.arriba if n in mapa.FILA_ARRIBA else g.abajo]
        cajas[n] = (x, y, x + mapa.ANCHO, y + alto)
    return cajas


def _entra(tramo, caja, margen):
    """¿El tramo (horizontal o vertical) entra en el interior de la caja agrandada por `margen`?
    Rozar el borde agrandado no cuenta."""
    (ax, ay), (bx, by) = tramo
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    return min(ax, bx) < x1 and max(ax, bx) > x0 and min(ay, by) < y1 and max(ay, by) > y0


def test_REQ_158_las_siete_tarjetas_caben_en_el_lienzo_en_todos_los_escalones():
    """REQ-158: las siete tarjetas, con el alto de su escalón, entran en el lienzo."""
    for k, m in PARES:
        g = mapa.geometria(k, m)
        assert sorted(g.posiciones) == [1, 2, 3, 4, 5, 6, 7]
        ancho, alto = g.lienzo
        for n, (x0, y0, x1, y1) in _cajas(g).items():
            assert x0 >= 0 and y0 >= 0 and x1 <= ancho and y1 <= alto, (k, m, n)


def test_REQ_158_ninguna_tarjeta_se_superpone_en_ningun_escalon():
    """REQ-158: ninguna tarjeta pisa a otra aunque las dos midan lo que dice su escalón."""
    for k, m in PARES:
        cajas = _cajas(mapa.geometria(k, m))
        for a in cajas:
            for b in cajas:
                if a < b:
                    ax0, ay0, ax1, ay1 = cajas[a]
                    bx0, by0, bx1, by1 = cajas[b]
                    assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, (k, m, a, b)


def test_REQ_158_los_conectores_son_exactamente_los_ocho():
    """REQ-158: 1→2, 2→4, 3→4, 3→5, 4→5, 4→6, 4→7 y 6→7, y nada más."""
    assert set(mapa.CONECTORES) == OCHO and len(mapa.CONECTORES) == 8
    for k, m in PARES:
        trazos = mapa.geometria(k, m).trazos
        assert {(c.origen, c.destino) for c in trazos} == OCHO and len(trazos) == 8


def test_REQ_158_ningun_tramo_corta_una_tarjeta_ni_su_texto_en_ningun_escalon():
    """REQ-158: ningún tramo de conector entra en una tarjeta ajena, ni a 12 px de ella, ni en el
    interior de las dos suyas (solo toca su borde). Con la caja del escalón, o sea con el alto máximo
    estimado de cada tarjeta: nunca pasa sobre su texto ni queda tapado."""
    for k, m in PARES:
        g = mapa.geometria(k, m)
        cajas = _cajas(g)
        for c in g.trazos:
            assert c.tramos
            for tramo in c.tramos:
                for n, caja in cajas.items():
                    propio = n in (c.origen, c.destino)
                    assert not _entra(tramo, caja, 0 if propio else MARGEN), (k, m, c.origen, c.destino, n, tramo)


def test_REQ_158_el_trazo_sale_y_entra_a_24_px_del_borde_superior():
    """REQ-158: sale del borde derecho a y+24 y entra a y+24 del destino (por su borde izquierdo, o por
    el derecho en un lazo de la misma columna), con punta: el alto de la tarjeta no los mueve."""
    assert mapa.SALIDA_Y == 24
    for k, m in PARES:
        g = mapa.geometria(k, m)
        for c in g.trazos:
            ox, oy = g.posiciones[c.origen]
            dx, dy = g.posiciones[c.destino]
            lazo = dx == ox
            entrada = (dx + mapa.ANCHO if lazo else dx, dy + 24)
            assert c.tramos[0][0] == (ox + mapa.ANCHO, oy + 24)
            assert c.tramos[-1][1] == entrada
            assert c.d.startswith("M ")
            assert len(c.punta) == 3 and c.punta[0] == entrada
            sentido = 1 if lazo else -1  # la punta apunta a la izquierda en un lazo y a la derecha si no
            assert all(p[0] == entrada[0] + sentido * mapa.PUNTA for p in c.punta[1:])
            for (ax, _), (bx, _) in c.tramos:  # todo queda en el hueco de la derecha del origen o entre columnas
                if lazo:
                    assert ox + mapa.ANCHO <= min(ax, bx) and max(ax, bx) <= ox + mapa.ANCHO + mapa.HUECO
                else:
                    assert ox + mapa.ANCHO <= min(ax, bx) and max(ax, bx) <= dx


def test_REQ_158_el_codo_tiene_lugar_para_su_radio_y_la_punta():
    """REQ-158: el tramo vertical es más largo que dos radios y entre el codo y la tarjeta cabe la punta."""
    for k, m in PARES:
        for c in mapa.geometria(k, m).trazos:
            for (ax, ay), (bx, by) in c.tramos:
                if ax == bx:
                    assert abs(by - ay) >= 2 * mapa.RADIO
            (xa, _), (xb, _) = c.tramos[-1]
            assert abs(xb - xa) == 0 or abs(xb - xa) >= mapa.RADIO + mapa.PUNTA, (c.origen, c.destino)


def test_REQ_158_hay_exactamente_tres_formas_de_conector():
    """REQ-158: rectos (1→2, 2→4, 4→6, 3→5), codos (3→4 sube y 4→7 baja) y lazos (4→5, 6→7); 4→5 y 4→7
    comparten el tronco y se bifurcan abajo; 3→4 pasa por el hueco que precede a la columna de 4."""
    g = mapa.geometria(5, 5)
    por = {(c.origen, c.destino): c for c in g.trazos}
    assert {k for k, c in por.items() if len(c.tramos) == 1} == {(1, 2), (2, 4), (4, 6), (3, 5)}
    assert {k for k, c in por.items() if g.posiciones[k[0]][0] == g.posiciones[k[1]][0]} == {(4, 5), (6, 7)}
    assert {k for k, c in por.items() if len(c.tramos) == 3 and g.posiciones[k[0]][0] != g.posiciones[k[1]][0]} == {
        (3, 4), (4, 7)}
    assert por[(4, 5)].tramos[1] == por[(4, 7)].tramos[1]  # mismo tronco vertical
    x4 = g.posiciones[4][0]
    assert por[(3, 4)].tramos[1][0][0] == x4 - mapa.HUECO // 2  # sube por el hueco anterior a la columna 3
    assert por[(3, 4)].tramos[1][1][1] < por[(3, 4)].tramos[1][0][1]  # sube
    assert por[(4, 7)].tramos[1][1][1] > por[(4, 7)].tramos[1][0][1]  # baja


def test_REQ_158_el_recorrido_se_lee_de_izquierda_a_derecha_y_de_arriba_abajo():
    """REQ-158: arriba 1, 2, 4, 6 de izquierda a derecha; abajo 3 bajo 1, 5 bajo 4 y 7 bajo 6; Dictamen (7)
    queda abajo a la derecha, y la columna 2 queda libre abajo (por ahí pasa 3→5)."""
    g = mapa.geometria(4, 4)
    p = g.posiciones
    assert p[1][0] < p[2][0] < p[4][0] < p[6][0] and len({p[n][1] for n in (1, 2, 4, 6)}) == 1
    assert p[3][0] == p[1][0] and p[5][0] == p[4][0] and p[7][0] == p[6][0]
    assert len({p[n][1] for n in (3, 5, 7)}) == 1 and p[3][1] > p[1][1]
    assert p[7][0] == max(x for x, _ in p.values()) and p[7][1] == max(y for _, y in p.values())
    assert all(p[n][0] != p[2][0] for n in (3, 5, 7))  # nada abajo de la tarjeta 2


def test_REQ_158_la_fila_de_abajo_empieza_despues_del_escalon_de_arriba():
    """REQ-158: la fila de abajo empieza `SEPARACION_FILAS` px después del alto de la de arriba, el lienzo
    termina `MARGEN` px después del alto de la de abajo y ambos crecen con el escalón."""
    for k, m in PARES:
        g = mapa.geometria(k, m)
        assert g.fila_b == mapa.Y_ARRIBA + mapa.ESCALONES[k] + mapa.SEPARACION_FILAS == mapa.y_fila_b(k)
        assert g.lienzo == (mapa.ANCHO_LIENZO, g.fila_b + mapa.ESCALONES[m] + mapa.MARGEN)
    alturas = [mapa.geometria(k, 0).lienzo[1] for k in range(len(mapa.ESCALONES))]
    assert alturas == sorted(set(alturas))
    assert mapa.geometria(3, 2) is mapa.geometria(3, 2)  # determinista y cacheada
    assert mapa.geometria(3, 2).clases == "fila-b-3 alto-b-2"


def _px(texto, propiedad):
    return int(re.search(rf"{propiedad}:\s*(\d+)px", texto).group(1))


def _regla(texto, selector):
    return re.search(rf"(?:^|\n){re.escape(selector)}\s*\{{([^}}]*)\}}", texto).group(1)


def test_REQ_158_el_alto_maximo_recalculado_desde_la_hoja_cabe_en_el_presupuesto():
    """REQ-158: se suma, con las medidas que declara `mapa.css`, el alto de una tarjeta en el peor caso
    (nombre y dato en 2 líneas, 3 tareas de 2 líneas, la etiqueta de una tarea, «+ N más» y
    advertencias) y es exactamente `mapa.ALTO_MAXIMO`; si alguien agranda un relleno, una línea o un
    margen sin tocar el presupuesto y la estimación, falla."""
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
    assert total == mapa.ALTO_MAXIMO, (total, mapa.ALTO_MAXIMO)
    assert dict(mapa.PRESUPUESTO)["tareas (3 × 2 líneas)"] == margen_tareas + 3 * una_tarea
    # y la estimación usa los mismos números: ese mismo caso da exactamente el máximo
    dos_lineas = "Resolver el punto número 1 que quedó pendiente de revisión por la Comisión"
    nombre = "Cumplimiento de ofertas con un nombre largo del paso"
    dato_largo = "Pliego, 12 anexos, 3 circulares y un dato más largo para que ocupe dos líneas"
    assert mapa.lineas(nombre, mapa.COLUMNA_NOMBRE, negrita=True) == 2
    assert mapa.lineas(dato_largo, mapa.COLUMNA_TEXTO) == 2 and mapa.lineas(dos_lineas, mapa.COLUMNA_TAREA) == 2
    assert mapa.alto_estimado(nombre, dato_largo, [(dos_lineas, True), (dos_lineas, False), (dos_lineas, False)],
                              True) == mapa.ALTO_MAXIMO == 297


def test_REQ_158_el_presupuesto_suma_el_alto_maximo():
    """REQ-158: `ALTO_MAXIMO` es la suma de las partes del presupuesto."""
    assert mapa.PRESUPUESTO_ALTO == mapa.ALTO_MAXIMO == sum(a for _, a in mapa.PRESUPUESTO) == 297


def test_REQ_158_regla_de_estimacion_de_lineas():
    """REQ-158 (T-363): la estimación cuenta por palabras con anchos de letra prudentes: vacío son 0 líneas;
    una frase corta, 1; una de 74 caracteres, 2 (y 3 si es la de «número 10», que casi no entra); una
    palabra larga sin espacios se parte y cuenta desde una línea nueva; agregar texto nunca baja la cuenta;
    las mayúsculas anchas y las letras desconocidas ocupan más que las minúsculas."""
    assert mapa.lineas("", 218) == 0 and mapa.lineas("   ", 218) == 0
    assert mapa.lineas("Evaluar las ofertas", 218) == 1
    assert mapa.lineas("Resolver el punto número 1 que quedó pendiente de revisión por la Comisión", 218) == 2
    assert mapa.lineas("Resolver el punto número 10 que quedó pendiente de revisión por la Comisión", 218) == 3
    assert mapa.lineas("W" * 40, 218) > mapa.lineas("w" * 40, 218) >= mapa.lineas("i" * 40, 218)
    assert mapa.lineas("a" * 300, 218) >= 300 * 5 // 206  # una palabra sin espacios se parte
    assert mapa.lineas("uno " + "x" * 60 + " dos", 218) > mapa.lineas("uno dos", 218)
    assert mapa.lineas("日本語" * 20, 218) > mapa.lineas("abc" * 20, 218)  # carácter desconocido: ancho de sobra
    base = "Resolver el punto número 1 que quedó pendiente"
    for extra in ("", " de revisión", " por la Comisión de Evaluación", " y algo más largo todavía de lo esperable"):
        assert mapa.lineas(base + extra, 218) >= mapa.lineas(base, 218)
    assert mapa.lineas("Cumplimiento de ofertas (matriz)", mapa.COLUMNA_NOMBRE, negrita=True) == 2


def test_REQ_158_el_escalon_es_el_menor_que_alcanza():
    """REQ-158 (T-363): `escalon(alto)` es el menor de `ESCALONES` mayor o igual que el alto (el último si
    el alto los pasa) y los escalones son una lista corta de 24 en 24."""
    assert mapa.ESCALONES[0] == 120 and mapa.ESCALONES[-1] >= mapa.ALTO_MAXIMO
    assert all(b - a == 24 for a, b in zip(mapa.ESCALONES, mapa.ESCALONES[1:])) and len(mapa.ESCALONES) <= 16
    for alto in range(0, mapa.ESCALONES[-1] + 50):
        i = mapa.escalon(alto)
        assert i == len(mapa.ESCALONES) - 1 or mapa.ESCALONES[i] >= alto
        assert i == 0 or mapa.ESCALONES[i - 1] < alto
    assert mapa.escalon(120) == 0 and mapa.escalon(121) == 1


def test_REQ_158_el_alto_estimado_crece_con_el_contenido():
    """REQ-158 (T-363): más tareas, más líneas, una etiqueta, el renglón de «+ N más» o un nombre de dos
    líneas dan un alto mayor o igual; el vacío es el mínimo."""
    vacio = mapa.alto_estimado("Carga de pliego", "", [], False)
    una = mapa.alto_estimado("Carga de pliego", "Pliego, 0 anexos", [("Evaluar", False)], False)
    assert vacio < una
    assert mapa.alto_estimado("Carga de pliego", "Pliego, 0 anexos", [("Evaluar", True)], False) == una + 19
    assert mapa.alto_estimado("Carga de pliego", "Pliego, 0 anexos", [("Evaluar", False)], True) == una + 27
    assert mapa.alto_estimado("Cumplimiento de ofertas con un nombre largo del paso", "", [], False) > vacio


def test_REQ_158_el_lienzo_entra_entero_a_1280_px_de_ventana():
    """REQ-158: el lienzo, el relleno de la caja del mapa (2 × 16), los márgenes de la página (2 × 36: el
    contenido llega a 1176 px y no crece más) y una barra de desplazamiento de 15 px caben en 1280 px; y el
    lienzo no es más ancho que la caja de 1144 px que le da la página."""
    assert mapa.VENTANA_MINIMA == mapa.ANCHO_LIENZO + 32 + 72 + 15 == 1263
    assert mapa.VENTANA_MINIMA <= 1280
    assert mapa.ANCHO_LIENZO <= 1176 - 32


def test_REQ_158_constantes_de_la_disposicion():
    """REQ-158: cuatro columnas de 252 px con huecos de 32 y las casillas de las siete tarjetas."""
    assert mapa.ANCHO == 252 and mapa.HUECO == 32 and mapa.ANCHO_LIENZO == 1144 and mapa.MARGEN == 8
    assert mapa.X_COLUMNA == (8, 292, 576, 860)
    assert mapa.CASILLAS == {1: (0, 0), 2: (1, 0), 3: (0, 1), 4: (2, 0), 5: (2, 1), 6: (3, 0), 7: (3, 1)}
    assert mapa.FILA_ARRIBA == (1, 2, 4, 6) and mapa.FILA_ABAJO == (3, 5, 7)
    assert mapa.geometria(5, 5).posiciones == {1: (8, 8), 2: (292, 8), 3: (8, 264), 4: (576, 8),
                                               5: (576, 264), 6: (860, 8), 7: (860, 264)}
