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
    assert mapa.RADIO == 8 and mapa.PUNTA == 8 and mapa.PUNTA_MEDIO_ANCHO == 4 and mapa.SALIDA_Y == 24
    for k, m in PARES:
        for c in mapa.geometria(k, m).trazos:
            for (ax, ay), (bx, by) in c.tramos:
                if ax == bx:
                    assert abs(by - ay) >= 2 * c.radio
            (xa, _), (xb, _) = c.tramos[-1]
            assert abs(xb - xa) == 0 or abs(xb - xa) >= c.radio + mapa.PUNTA, (c.origen, c.destino)


def test_REQ_158_hay_exactamente_tres_formas_de_conector():
    """REQ-158: rectos (1→2, 2→4, 4→6, 3→5), codos (3→4 sube y 4→7 baja) y lazos (4→5, 6→7); 3→4 pasa por el
    hueco que precede a la columna de 4."""
    g = mapa.geometria(5, 5)
    por = {(c.origen, c.destino): c for c in g.trazos}
    assert {k for k, c in por.items() if len(c.tramos) == 1} == {(1, 2), (2, 4), (4, 6), (3, 5)}
    assert {k for k, c in por.items() if g.posiciones[k[0]][0] == g.posiciones[k[1]][0]} == {(4, 5), (6, 7)}
    assert {k for k, c in por.items() if len(c.tramos) == 3 and g.posiciones[k[0]][0] != g.posiciones[k[1]][0]} == {
        (3, 4), (4, 7)}
    x4 = g.posiciones[4][0]
    assert por[(3, 4)].tramos[1][0][0] == x4 - mapa.HUECO // 2  # sube por el hueco anterior a la columna 3
    assert por[(3, 4)].tramos[1][1][1] < por[(3, 4)].tramos[1][0][1]  # sube
    assert por[(4, 7)].tramos[1][1][1] > por[(4, 7)].tramos[1][0][1]  # baja


def test_REQ_158_4_a_5_y_4_a_7_bajan_por_troncos_separados_y_no_se_cruzan():
    """REQ-158 (H-B1, T-363): los dos conectores que bajan de la tarjeta 4 no comparten tronco: 4→5 baja a 12 px
    del borde derecho de la 4 y vuelve hacia la 5; 4→7 baja 8 px más a la derecha y sigue hacia la 7. Cada flecha
    se sigue de punta a punta: el tronco de 4→5 queda a la izquierda del de 4→7, y sus tramos finales apuntan
    a lados opuestos desde cada tronco, sin cruzarse."""
    for k, m in PARES:
        g = mapa.geometria(k, m)
        por = {(c.origen, c.destino): c for c in g.trazos}
        a, b = por[(4, 5)], por[(4, 7)]
        xa, xb = a.tramos[1][0][0], b.tramos[1][0][0]
        x0 = g.posiciones[4][0] + mapa.ANCHO
        assert xa == x0 + 12 and xb - xa == 8 and xb == g.posiciones[7][0] - 12
        assert a.tramos[2][1][0] < xa < xb < b.tramos[2][1][0]  # una vuelve a la izquierda, la otra sigue a la derecha
        assert a.tramos[1] != b.tramos[1] and a.radio == b.radio == 4


def _vertices(d):
    """Los puntos de una ruta de `mapa.trazo` (M, H, V, Q): inicio, esquinas (punto de control de cada Q) y fin."""
    tokens = d.split()
    x = y = 0.0
    inicio, esquinas, i = None, [], 0
    while i < len(tokens):
        c = tokens[i]
        if c == "M":
            x, y = float(tokens[i + 1]), float(tokens[i + 2]); inicio = (x, y); i += 3
        elif c == "H":
            x = float(tokens[i + 1]); i += 2
        elif c == "V":
            y = float(tokens[i + 1]); i += 2
        elif c == "Q":
            esquinas.append((float(tokens[i + 1]), float(tokens[i + 2])))
            x, y = float(tokens[i + 3]), float(tokens[i + 4]); i += 5
        else:
            raise AssertionError(c)
    return inicio, esquinas, (x, y)


def test_REQ_158_el_d_del_svg_recorre_los_tramos_y_las_puntas_son_las_de_la_constante():
    """REQ-158 (H-A5, T-363): el `d` de cada conector empieza donde empieza su primer tramo, tiene sus esquinas
    exactamente en los quiebres de los tramos y termina donde termina el último; y la punta tiene el largo y el
    ancho de `PUNTA` y `PUNTA_MEDIO_ANCHO` (un trazo que termine antes o una punta distinta fallan)."""
    for k, m in PARES:
        for c in mapa.geometria(k, m).trazos:
            inicio, esquinas, fin = _vertices(c.d)
            assert inicio == c.tramos[0][0] and fin == c.tramos[-1][1], (c.origen, c.destino)
            assert esquinas == [t[1] for t in c.tramos[:-1]], (c.origen, c.destino)
            (px, py), (bx1, by1), (bx2, by2) = c.punta
            assert (px, py) == c.tramos[-1][1]
            assert abs(bx1 - px) == abs(bx2 - px) == mapa.PUNTA and bx1 == bx2
            assert by1 == py - mapa.PUNTA_MEDIO_ANCHO and by2 == py + mapa.PUNTA_MEDIO_ANCHO


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
    dos_lineas = "Cargar el informe técnico del área (falta en 2 ofertas) y más"
    nombre = "Cumplimiento de ofertas con un nombre largo del paso"
    dato_largo = "Pliego, 12 anexos, 3 circulares y un dato más largo todavía"
    assert mapa.lineas(nombre, mapa.COLUMNA_NOMBRE, negrita=True) == 2
    assert mapa.lineas(dato_largo, mapa.COLUMNA_TEXTO) == 2 and mapa.lineas(dos_lineas, mapa.COLUMNA_TAREA) == 2
    assert mapa.alto_estimado(nombre, dato_largo, [(dos_lineas, True), (dos_lineas, False), (dos_lineas, False)],
                              True) == mapa.ALTO_MAXIMO + mapa.HOLGURA_ALTO == 297 + 14


def test_REQ_158_el_presupuesto_suma_el_alto_maximo():
    """REQ-158: `ALTO_MAXIMO` es la suma de las partes del presupuesto."""
    assert mapa.PRESUPUESTO_ALTO == mapa.ALTO_MAXIMO == sum(a for _, a in mapa.PRESUPUESTO) == 297


def test_REQ_158_regla_de_estimacion_de_lineas():
    """REQ-158 (T-363): la estimación cuenta por palabras con anchos de letra prudentes: vacío son 0 líneas;
    una frase corta, 1; una de 55 caracteres, 2 (y una de 74, que en el navegador entra justo en 2, se cuenta 3 por el 8 % de margen); una
    palabra larga sin espacios se parte y cuenta desde una línea nueva; agregar texto nunca baja la cuenta;
    las mayúsculas anchas y las letras desconocidas ocupan más que las minúsculas."""
    assert mapa.lineas("", 218) == 0 and mapa.lineas("   ", 218) == 0
    assert mapa.lineas("Evaluar las ofertas", 218) == 1
    assert mapa.lineas("Cargar el informe técnico del área (falta en 2 ofertas)", 218) == 2
    assert mapa.lineas("Resolver el punto número 1 que quedó pendiente de revisión por la Comisión", 218) == 3  # entra justo: se cuenta de más
    assert mapa.lineas("W" * 40, 218) > mapa.lineas("w" * 40, 218) >= mapa.lineas("i" * 40, 218)
    assert mapa.lineas("a" * 300, 218) >= 300 * 5 // 206  # una palabra sin espacios se parte
    assert mapa.lineas("uno " + "x" * 60 + " dos", 218) > mapa.lineas("uno dos", 218)
    assert mapa.lineas("日本語" * 20, 218) > mapa.lineas("abc" * 20, 218)  # carácter desconocido: ancho de sobra
    base = "Resolver el punto número 1 que quedó pendiente"
    for extra in ("", " de revisión", " por la Comisión de Evaluación", " y algo más largo todavía de lo esperable"):
        assert mapa.lineas(base + extra, 218) >= mapa.lineas(base, 218)
    assert mapa.lineas("Cumplimiento de ofertas (matriz)", mapa.COLUMNA_NOMBRE, negrita=True) == 2


# Textos difíciles (nombres de empresa en mayúsculas, letras anchas, números, «@ % —», tildes, palabras largas, emojis,
# escrituras no latinas, una URL) con el alto REAL de la tarjeta, medido una vez en Chrome 157 con la tipografía de la
# aplicación (Hanken Grotesk) y la hoja `mapa.css` de T-363. Cada caso es `(descripción, nombre del paso, dato, tareas,
# lleva etiqueta «Vence hoy» la primera, hay renglón de «+ N más» o advertencias, alto real en px)`. Si cambia la
# tipografía, el relleno o las líneas de la tarjeta hay que volver a medirlos; si cambia `mapa.py` y el estimado queda por
# debajo de uno, este test falla.
CASOS_MEDIDOS = (
    ('mayus_empresa: dato y 3 tareas', 'Carga de pliego', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Tre', ('Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José'), False, False, 342),
    ('mayus_empresa: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Tre', ('Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José', 'Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José'), True, True, 388),
    ('mayus_empresa: 1 tarea sin dato', 'Carga de pliego', '', ('Falta la hoja de compliance de CERRAJERIA Cerrajería José 1 S.R.L. JORGE Sánchez JORGE Trescientas José',), False, False, 159),
    ('mayus_anchas: dato y 3 tareas', 'Carga de pliego', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', ('WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM'), False, False, 300),
    ('mayus_anchas: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', ('WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM', 'WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM'), True, True, 346),
    ('mayus_anchas: 1 tarea sin dato', 'Carga de pliego', '', ('WWWWWWW MMMMMMM WWWWWWW MMMMMMM WWWWWWW MMMMMMM',), False, False, 145),
    ('numeros: dato y 3 tareas', 'Carga de pliego', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', ('0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555'), False, False, 300),
    ('numeros: 3 tareas con etiqueta y renglón', 'Carga de pliego', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', ('0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555', '0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555'), True, True, 346),
    ('numeros: 1 tarea sin dato', 'Carga de pliego', '', ('0000000000 1234567890 8888888888 0000000000 9999999999 0000000000 5555',), False, False, 145),
    ('simbolos: dato y 3 tareas', 'Carga de pliego', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', ('@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####'), False, False, 300),
    ('simbolos: 3 tareas con etiqueta y renglón', 'Carga de pliego', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', ('@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####', '@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####'), True, True, 346),
    ('simbolos: 1 tarea sin dato', 'Carga de pliego', '', ('@@@@ %%%% ———— #### &&&& @@@@ %%%% ———— #### &&&& @@@@ %%%% ———— ####',), False, False, 145),
    ('tildes: dato y 3 tareas', 'Carga de pliego', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', ('Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ'), False, False, 285),
    ('tildes: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', ('Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ', 'Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ'), True, True, 331),
    ('tildes: 1 tarea sin dato', 'Carga de pliego', '', ('Señalización ÁÉÍÓÚÑ año niñez ÑÑÑ Cañería Ñandú Ángel Úrsula Ómar ÁÉÍÓÚ',), False, False, 145),
    ('larga_sin_espacios: dato y 3 tareas', 'Carga de pliego', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', ('Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre'), False, False, 243),
    ('larga_sin_espacios: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', ('Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre', 'Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre'), True, True, 289),
    ('larga_sin_espacios: 1 tarea sin dato', 'Carga de pliego', '', ('Supercalifragilisticoespialidosoextraordinariamentelargaparaprobarelquiebre',), False, False, 131),
    ('emojis: dato y 3 tareas', 'Carga de pliego', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', ('Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅'), False, False, 243),
    ('emojis: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', ('Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅', 'Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅'), True, True, 289),
    ('emojis: 1 tarea sin dato', 'Carga de pliego', '', ('Revisar 🙂✅⚠️ la oferta 🙂✅⚠️ del proveedor 🙂✅⚠️ urgente 🙂✅',), False, False, 131),
    ('chino: dato y 3 tareas', 'Carga de pliego', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', ('日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語'), False, False, 243),
    ('chino: 3 tareas con etiqueta y renglón', 'Carga de pliego', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', ('日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語', '日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語'), True, True, 289),
    ('chino: 1 tarea sin dato', 'Carga de pliego', '', ('日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語日本語',), False, False, 131),
    ('url: dato y 3 tareas', 'Carga de pliego', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detal', ('Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle'), False, False, 357),
    ('url: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detal', ('Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle', 'Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle'), True, True, 403),
    ('url: 1 tarea sin dato', 'Carga de pliego', '', ('Ver https://www.compras.ejemplo.gob.ar/procedimientos/2026/licitacion-publica-000123/detalle',), False, False, 159),
    ('normal74: dato y 3 tareas', 'Carga de pliego', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', ('Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión'), False, False, 243),
    ('normal74: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', ('Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión', 'Resolver el punto número 10 que quedó pendiente de revisión por la Comisión'), True, True, 289),
    ('normal74: 1 tarea sin dato', 'Carga de pliego', '', ('Resolver el punto número 10 que quedó pendiente de revisión por la Comisión',), False, False, 131),
    ('error: dato y 3 tareas', 'Carga de pliego', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 incis', ('Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»'), False, False, 300),
    ('error: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 incis', ('Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»', 'Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»'), True, True, 346),
    ('error: 1 tarea sin dato', 'Carga de pliego', '', ('Resolver el error: «La oferta no trae el documento pedido por el pliego, artículo 14 inciso b»',), False, False, 145),
    ('guiones: dato y 3 tareas', 'Carga de pliego', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', ('Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II'), False, False, 285),
    ('guiones: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', ('Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II', 'Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II'), True, True, 331),
    ('guiones: 1 tarea sin dato', 'Carga de pliego', '', ('Falta la garantía de oferta — 5 % del monto — ver cláusula 12.3 (a)/(b) y anexo II',), False, False, 145),
    ('cuit: dato y 3 tareas', 'Carga de pliego', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', ('CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3'), False, False, 285),
    ('cuit: 3 tareas con etiqueta y renglón', 'Carga de pliego', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', ('CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3', 'CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3'), True, True, 331),
    ('cuit: 1 tarea sin dato', 'Carga de pliego', '', ('CUIT 30-12345678-9 CUIT 33-98765432-1 CUIT 20-11223344-5 CUIT 27-55667788-3',), False, False, 145),
    ('nombre 0', 'Cumplimiento de ofertas con un nombre larguísimo en mayúsculas CERRAJERIA', 'Pliego, 0 anexos, 0 circulares', ('Evaluar las ofertas', 'Proponer la matriz'), False, True, 210),
    ('nombre 1', 'WWWW MMMM WWWW MMMM WWWW MMMM', 'Pliego, 0 anexos, 0 circulares', ('Evaluar las ofertas', 'Proponer la matriz'), False, True, 194),
    ('nombre 2', 'Evaluación Comisión', 'Pliego, 0 anexos, 0 circulares', ('Evaluar las ofertas', 'Proponer la matriz'), False, True, 186),
    ('nombre 3', 'Carga de pliego', 'Pliego, 0 anexos, 0 circulares', ('Evaluar las ofertas', 'Proponer la matriz'), False, True, 186),
)


def test_REQ_158_el_alto_estimado_nunca_es_menor_que_el_real_medido_en_chrome():
    """REQ-158 (H-A1, T-363): para cada texto difícil, `alto_estimado` es mayor o igual que el alto real medido en
    Chrome (la holgura de una línea, 14 px, se le suma a propósito), y no se va de largo (más de 140 px: un
    estimador desbocado también dejaría un mapa lleno de aire)."""
    assert len(CASOS_MEDIDOS) == 43
    for descripcion, nombre, dato, tareas, etiqueta, resto, real in CASOS_MEDIDOS:
        estimado = mapa.alto_estimado(nombre, dato, [(t, etiqueta and i == 0) for i, t in enumerate(tareas)], resto)
        assert estimado >= real, (descripcion, estimado, real)
        assert estimado - real <= 140, (descripcion, estimado, real)


def test_REQ_158_el_estimador_cuenta_las_lineas_que_sobran_de_cada_tarea():
    """REQ-158 (H-A5, T-363): un estimador que topara las tareas en dos líneas o que ignorara una tarea no pasa:
    tres tareas de cuatro líneas suman 3 × 56 px más que tres de una."""
    cuatro = "palabra " * 22
    una = "palabra"
    assert mapa.lineas(cuatro, mapa.COLUMNA_TAREA) >= 4
    chico = mapa.alto_estimado("Carga de pliego", "", [(una, False)] * 3, False)
    grande = mapa.alto_estimado("Carga de pliego", "", [(cuatro, False)] * 3, False)
    assert grande - chico >= 3 * 14 * 3


def test_REQ_158_el_escalon_es_el_menor_que_alcanza():
    """REQ-158 (T-363): `escalon(alto)` es el menor de `ESCALONES` mayor o igual que el alto (el último si
    el alto los pasa) y los escalones son una lista corta de 12 en 12."""
    assert mapa.ESCALONES[0] == 120 and mapa.ESCALONES[-1] >= mapa.ALTO_MAXIMO
    assert all(b - a == 12 for a, b in zip(mapa.ESCALONES, mapa.ESCALONES[1:])) and len(mapa.ESCALONES) <= 30
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
    lienzo no es más ancho que la caja de 1144 px que le da la página (y a 1262 px de ventana entra justo, sin 1 px de sobra)."""
    assert mapa.VENTANA_MINIMA == mapa.ANCHO_LIENZO + 32 + 72 + 15 == 1262
    assert mapa.VENTANA_MINIMA <= 1280
    assert mapa.ANCHO_LIENZO <= 1176 - 32 and mapa.ANCHO_LIENZO == 1143


def test_REQ_158_constantes_de_la_disposicion():
    """REQ-158: cuatro columnas de 252 px con huecos de 32 y las casillas de las siete tarjetas."""
    assert mapa.ANCHO == 252 and mapa.HUECO == 32 and mapa.ANCHO_LIENZO == 1143 and mapa.MARGEN == 8
    assert mapa.X_COLUMNA == (8, 292, 576, 860)
    assert mapa.CASILLAS == {1: (0, 0), 2: (1, 0), 3: (0, 1), 4: (2, 0), 5: (2, 1), 6: (3, 0), 7: (3, 1)}
    assert mapa.FILA_ARRIBA == (1, 2, 4, 6) and mapa.FILA_ABAJO == (3, 5, 7)
    assert mapa.geometria(5, 5).posiciones == {1: (8, 8), 2: (292, 8), 3: (8, 200), 4: (576, 8), 5: (576, 200), 6: (860, 8), 7: (860, 200)}
