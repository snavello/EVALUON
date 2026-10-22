"""Textos de los mosaicos de Ofertas y Evaluación (REQ-126, REQ-141; T-335): singular con la cifra
1 y el nombre de la categoría de la dona. Todo el material es inventado (P4)."""

from types import SimpleNamespace

from evaluon.journey.tablero import charts, economico
from evaluon.journey.temas import s3_ofertas, s4_propuesta


def figures(**cuenta):
    offer = s4_propuesta.OfferFigures(number=1, **cuenta)
    return s4_propuesta.Figures(offers=(offer,), unevaluated=(), total_offers=1, requirements=9,
                                version=1, heat=())


def tile(fig, key):
    return {t.key: t for t in s4_propuesta.tiles(None, None, {"tablero": fig})}[key]


def test_el_orden_economico_dice_oferta_ordenada_en_singular():
    """REQ-130: «1 oferta ordenada», no «1 ofertas ordenadas»."""
    def mosaico(count):
        view = SimpleNamespace(state=economico.STATE_ORDERED, warning="", high=None, count=count,
                               chart=SimpleNamespace(has_data=False), missing="", opening_day="")
        return s3_ofertas._tile_orden(view)
    assert mosaico(1).unit == "oferta ordenada"
    assert mosaico(2).unit == "ofertas ordenadas" and mosaico(0).unit == "ofertas ordenadas"


def test_no_cumple_y_no_determinado_dicen_requisito_en_singular():
    """REQ-126: «1 requisito» y «2 requisitos» en los dos mosaicos de cifras."""
    uno = figures(ok=5, no=1, nd=1, pe=2)
    assert tile(uno, "nocumple").unit == "requisito"
    assert tile(uno, "nodeterminado").unit == "requisito"
    dos = figures(ok=3, no=2, nd=2, pe=2)
    assert tile(dos, "nocumple").unit == "requisitos"
    assert tile(dos, "nodeterminado").unit == "requisitos"
    cero = figures(ok=9)
    assert tile(cero, "nocumple").unit == "requisitos"


def test_la_categoria_pe_de_la_dona_se_llama_sin_resultado():
    """REQ-141: en la dona, «Pendiente» pasa a «Sin resultado» (no choca con la columna
    «Pendiente» de la tabla, que es «sin decidir por la Comisión»); se cuenta igual."""
    dona = charts.Donuts(uid="d", title="Resultado por oferta",
                         items=[charts.DonutItem("Of. 1", ok=5, no=1, nd=1, pe=2)])
    nombres = [l["name"] for l in dona.legend]
    assert nombres == ["Cumple", "No cumple", "No determinado", "Sin resultado"]
    assert "2 sin resultado" in dona.description and "pendiente" not in dona.description
    assert dona.items[0].counts["pe"] == 2


def test_el_mosaico_del_resultado_explica_sin_resultado():
    """REQ-141: el texto del mosaico dice qué es «Sin resultado» y no usa «Pendiente» para eso."""
    sub = tile(figures(ok=5, no=1, nd=1, pe=2), "resultado").sub
    assert "Sin resultado" in sub and "Pendiente" not in sub
