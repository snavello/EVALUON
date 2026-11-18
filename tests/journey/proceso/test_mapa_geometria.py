"""Geometría constante del mapa del proceso (T-349, REQ-158): Python puro, sin navegador.

La aritmética de las posiciones del plan no estaba probada: estos tests son la prueba.
"""

from evaluon.journey.proceso import mapa

MARGEN = 12
OCHO = {(1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7)}


def _caja(n):
    x, y = mapa.POSICIONES[n]
    return x, y, x + mapa.ANCHO, y + mapa.ALTO


def _entra(tramo, caja, margen):
    """¿El tramo (horizontal o vertical) entra en el interior de la caja agrandada por `margen`?
    Rozar el borde agrandado no cuenta."""
    (ax, ay), (bx, by) = tramo
    x0, y0, x1, y1 = caja[0] - margen, caja[1] - margen, caja[2] + margen, caja[3] + margen
    return min(ax, bx) < x1 and max(ax, bx) > x0 and min(ay, by) < y1 and max(ay, by) > y0


def test_REQ_158_las_siete_tarjetas_caben_en_el_lienzo():
    """REQ-158: las siete tarjetas entran en el lienzo."""
    assert sorted(mapa.POSICIONES) == [1, 2, 3, 4, 5, 6, 7]
    ancho, alto = mapa.LIENZO
    for n in mapa.POSICIONES:
        x0, y0, x1, y1 = _caja(n)
        assert x0 >= 0 and y0 >= 0 and x1 <= ancho and y1 <= alto, n


def test_REQ_158_ninguna_tarjeta_se_superpone():
    """REQ-158: ninguna tarjeta pisa a otra."""
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
    """REQ-158: ningún tramo de conector corta una tarjeta con 12 px de margen, salvo en el
    borde de su tarjeta de origen o de destino (ahí solo puede tocar el borde)."""
    for c in mapa.TRAZOS:
        assert c.tramos
        for tramo in c.tramos:
            for n in mapa.POSICIONES:
                propio = n in (c.origen, c.destino)
                assert not _entra(tramo, _caja(n), 0 if propio else MARGEN), (c.origen, c.destino, n, tramo)


def test_REQ_158_el_trazo_sale_y_entra_por_los_bordes_a_28_px():
    """REQ-158: sale del borde derecho a y+28 y entra por el izquierdo a y+28, con punta."""
    for c in mapa.TRAZOS:
        ox, oy = mapa.POSICIONES[c.origen]
        dx, dy = mapa.POSICIONES[c.destino]
        assert c.tramos[0][0] == (ox + mapa.ANCHO, oy + 28)
        assert c.tramos[-1][1] == (dx, dy + 28)
        assert c.d.startswith("M ")
        assert len(c.punta) == 3 and c.punta[0] == (dx, dy + 28)
        for (ax, _), (bx, _) in c.tramos:  # todo queda entre las dos columnas
            assert ox + mapa.ANCHO <= min(ax, bx) and max(ax, bx) <= dx


def test_REQ_158_el_codo_tiene_lugar_para_su_radio():
    """REQ-158: el tramo vertical es más largo que dos radios (12 px)."""
    for c in mapa.TRAZOS:
        for (ax, ay), (bx, by) in c.tramos:
            if ax == bx:
                assert abs(by - ay) >= 2 * mapa.RADIO


def test_REQ_158_el_presupuesto_de_alto_cabe_en_la_tarjeta():
    """REQ-158: relleno 22 + encabezado 36 + dato 34 + pie 30 + 3 tareas × 30 + «+ N más» 26."""
    assert mapa.PRESUPUESTO_ALTO == 22 + 36 + 34 + 30 + 3 * 30 + 26 == 238
    assert mapa.PRESUPUESTO_ALTO <= mapa.ALTO


def test_REQ_158_constantes_del_plan():
    """REQ-158: lienzo, tarjeta y posiciones del plan."""
    assert mapa.LIENZO == (1130, 740) and mapa.ANCHO == 172 and mapa.ALTO == 240
    assert mapa.POSICIONES == {1: (10, 140), 2: (245, 140), 3: (245, 490), 4: (480, 250),
                               5: (715, 490), 6: (715, 10), 7: (950, 250)}
    assert mapa.COLUMNAS == (("Publicación", 10), ("Requisitos y ofertas", 245), ("Cruce", 480),
                             ("Análisis y decisión", 715), ("Cierre", 950))
