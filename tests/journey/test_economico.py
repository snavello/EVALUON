"""Orden económico del tablero (REQ-130, REQ-141; plan 017, «Orden económico»; ADR-0077, D;
T-314).

Ordena las ofertas de menor a mayor total (`ordering.economic_order` sobre
`PortalOfferData.total`), marca la más baja y la más alta y calcula cuánto se aparta cada una de
la más baja. No hay monto estimado. Sin ofertas muestra el día de la apertura y «Pendiente»;
con ofertas sin total, solo la cantidad y «Falta el total». Todo el texto es inventado (P4).
"""

import re
from decimal import Decimal

import pytest
from django.template.loader import render_to_string

from evaluon.journey.tablero import charts, economico
from evaluon.offers.models import Offer
from evaluon.portal import models as pm

pytestmark = pytest.mark.django_db


@pytest.fixture
def portal(procedure, operator_user):
    """Un ítem del Portal del que cuelgan los datos de las ofertas y el cronograma."""
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=operator_user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1, origin="importacion")
    return pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o", payload={},
                                        content_sha256="b" * 64, page=page)


@pytest.fixture
def make(procedure, operator_user, portal):
    """`make(número, total, moneda)`: una oferta con sus datos del Portal; `total=None` deja el
    dato sin total y `total=False` no crea los datos del Portal."""

    def build(number, total, currency="ARS"):
        offer = Offer.objects.create(procedure=procedure, number=number,
                                     bidder=f"Oferente Sintético {number}",
                                     created_by=operator_user)
        if total is not False:
            pm.PortalOfferData.objects.create(offer=offer, cuit=f"30-0000000{number}-0",
                                              currency=currency, total=total, item=portal)
        return offer

    return build


@pytest.fixture
def opening(procedure, portal):
    """El cronograma del procedimiento, con la apertura el 22/09/2026."""
    pm.PortalProcedureData.objects.create(
        procedure=procedure, file_number="EX-SINT-1", item=portal,
        schedule={"Publicación": "01/09/2026", "Apertura de ofertas": "22/09/2026 11:00"})


def fila(vista, number):
    return next(r for r in vista.rows if r.number == number)


def digitos(html):
    """Lo que en el HTML son cifras (sin las de atributos ni el número de oferta)."""
    return re.findall(r"\d", re.sub(r"<[^>]+>", " ", html))


# --- Con ofertas ---------------------------------------------------------------------------------


def test_tres_ofertas_de_menor_a_mayor_con_la_mas_baja_y_la_mas_alta(make, procedure):
    """REQ-130: tres ofertas quedan de menor a mayor, la más baja y la más alta marcadas, y cada
    una con su diferencia porcentual con la más baja."""
    make(1, Decimal("1100.00"))
    make(2, Decimal("1000.00"))
    make(3, Decimal("1250.00"))
    vista = economico.economic_view(procedure)
    assert vista.state == economico.STATE_ORDERED
    assert [r.number for r in vista.rows] == [2, 1, 3]
    assert [r.position for r in vista.rows] == [1, 2, 3]
    assert [r.is_low for r in vista.rows] == [True, False, False]
    assert [r.is_high for r in vista.rows] == [False, False, True]
    assert [r.diff_pct for r in vista.rows] == [Decimal("0.0"), Decimal("10.0"), Decimal("25.0")]
    assert vista.low.number == 2 and vista.high.number == 3
    assert vista.count == 3


def test_la_diferencia_se_dice_con_signo_y_en_castellano(make, procedure):
    """REQ-130: la más baja no se aparta de sí misma («—» y no «0 %»); las demás, «+10,0 %»."""
    make(1, Decimal("1100.00"))
    make(2, Decimal("1000.00"))
    vista = economico.economic_view(procedure)
    assert fila(vista, 2).diff_text == ""
    assert fila(vista, 1).diff_text == "+10,0 %"


def test_un_empate_comparte_la_posicion(make, procedure):
    """REQ-130: dos ofertas con el mismo total tienen la misma posición y la siguiente salta."""
    make(1, Decimal("1000.00"))
    make(2, Decimal("1000.00"))
    make(3, Decimal("1300.00"))
    vista = economico.economic_view(procedure)
    assert [(r.number, r.position) for r in vista.rows] == [(1, 1), (2, 1), (3, 3)]
    assert fila(vista, 1).is_low and fila(vista, 2).is_low
    assert fila(vista, 3).is_high


def test_con_una_sola_oferta_es_la_mas_baja_y_no_la_mas_alta(make, procedure):
    """REQ-141: con un solo total (o todos iguales) no hay «más alta» que no sea la misma; no se
    inventa una diferencia."""
    make(1, Decimal("1000.00"))
    vista = economico.economic_view(procedure)
    assert vista.low.number == 1 and vista.high is None
    assert not vista.rows[0].is_high


def test_totales_en_cero_no_dividen(make, procedure):
    """REQ-141: si la más baja es cero, la diferencia porcentual no existe y no se inventa."""
    make(1, Decimal("0.00"))
    make(2, Decimal("500.00"))
    vista = economico.economic_view(procedure)
    assert [r.diff_pct for r in vista.rows] == [Decimal("0.0"), None]
    assert fila(vista, 2).diff_text == ""


def test_una_oferta_sin_total_va_al_final_y_dice_que_falta(make, procedure):
    """REQ-141: la oferta sin total queda al final, sin posición ni cifra, con «Falta el
    total»; no entra en la más alta ni en la más baja."""
    make(1, Decimal("1000.00"))
    make(2, Decimal("1200.00"))
    make(3, None)
    make(4, False)
    vista = economico.economic_view(procedure)
    assert [r.number for r in vista.rows] == [1, 2, 3, 4]
    for numero in (3, 4):
        r = fila(vista, numero)
        assert r.position is None and r.amount is None and r.amount_text == ""
        assert r.note == economico.NO_TOTAL_TEXT
        assert not r.is_low and not r.is_high and r.diff_text == ""
    assert vista.low.number == 1 and vista.high.number == 2
    assert vista.count == 4


def test_monedas_distintas_no_se_ordenan(make, procedure):
    """REQ-141: con monedas distintas no se ordena ni se compara; se avisa y no hay ni más
    baja, ni más alta, ni porcentajes."""
    make(1, Decimal("1000.00"), "ARS")
    make(2, Decimal("900.00"), "USD")
    vista = economico.economic_view(procedure)
    assert vista.warning
    assert vista.low is None and vista.high is None
    assert all(r.position is None and r.diff_pct is None and not r.is_low for r in vista.rows)
    assert vista.chart.has_data is False


def test_las_ofertas_descartadas_por_completo_no_entran(make, procedure):
    """REQ-130 (usa `economic_order` tal cual): una oferta descartada entera sale del orden."""
    a = make(1, Decimal("1000.00"))
    make(2, Decimal("1200.00"))

    class Entera:
        is_whole = True
        is_partial = False

    vista = economico.economic_view(procedure, discards={a.pk: Entera()})
    assert [r.number for r in vista.rows] == [2]


def test_el_grafico_es_un_lollipop_de_menor_a_mayor(make, procedure):
    """REQ-126: el gráfico del orden usa el protocolo de gráficos; la más baja y la más alta
    como indicadores y solo las ofertas con total."""
    make(1, Decimal("1100.00"))
    make(2, Decimal("1000.00"))
    make(3, Decimal("1250.00"))
    make(4, None)
    grafico = economico.economic_view(procedure).chart
    assert isinstance(grafico, charts.Lollipop)
    assert [r.label for r in grafico.rows] == [
        "Oferta 2", "Oferta 1", "Oferta 3"]
    assert [(r.low, r.high) for r in grafico.rows] == [(True, False), (False, False),
                                                       (False, True)]
    assert grafico.has_data
    assert "g-lime" in render_to_string(grafico.template, {"chart": grafico})


def test_el_formato_del_monto_es_el_argentino(make, procedure):
    """REQ-130: miles con punto y centavos con coma; la moneda distinta de pesos, con su
    nombre."""
    make(1, Decimal("1234567.80"))
    vista = economico.economic_view(procedure)
    assert vista.rows[0].amount_text == "$ 1.234.567,80"
    otra = economico._money(Decimal("10.00"), "USD")
    assert otra == "USD 10,00"


def test_sin_moneda_el_monto_va_sin_simbolo(make, procedure):
    """REQ-141 (H-2): con la moneda vacía no se afirma que sean pesos; el monto sale sin
    símbolo. Con «ARS» o «$» sí es «$»."""
    make(1, Decimal("1234567.80"), "")
    vista = economico.economic_view(procedure)
    assert vista.rows[0].amount_text == "1.234.567,80"
    assert economico._money(Decimal("5.00"), "") == "5,00"
    assert economico._money(Decimal("5.00"), "ARS") == "$ 5,00"
    assert economico._money(Decimal("5.00"), "$") == "$ 5,00"


def test_una_diferencia_menor_a_cinco_centesimas_no_queda_vacia(make, procedure):
    """REQ-130 (H-5): 1.000,04 sobre 1.000,00 se aparta 0,004 %; se dice «< 0,1 %» y no se deja
    la celda vacía. La más baja sigue sin texto."""
    make(1, Decimal("1000.00"))
    make(2, Decimal("1000.04"))
    make(3, Decimal("1000.50"))
    vista = economico.economic_view(procedure)
    assert fila(vista, 1).diff_text == ""
    assert fila(vista, 2).diff_text == "< 0,1 %"
    assert fila(vista, 2).diff_pct == Decimal("0.0")
    assert fila(vista, 3).diff_text == "+0,1 %"
    assert "< 0,1 %" in dibujar(vista).replace("&lt;", "<")


def test_la_nota_de_la_mas_alta_es_corta(make, procedure):
    """REQ-130 (H-1): la nota del gráfico no repite «sobre la más baja»; el título lo dice."""
    make(1, Decimal("87450123.50"))
    make(2, Decimal("207800999.99"))
    grafico = economico.economic_view(procedure).chart
    assert [r.note for r in grafico.rows] == ["La más baja", "La más alta · +137,6 %"]
    assert "más baja" in grafico.title


def test_los_ids_del_cuadro_y_del_grafico_se_derivan_del_uid(make, procedure):
    """REQ-126 (H-3): dos cuadros en una página no repiten ids si reciben `uid` distintos."""
    make(1, Decimal("1000.00"))
    make(2, Decimal("1200.00"))
    a = economico.economic_view(procedure, uid="orden-a")
    b = economico.economic_view(procedure, uid="orden-b")
    html = dibujar(a) + render_to_string(a.chart.template, {"chart": a.chart})         + dibujar(b) + render_to_string(b.chart.template, {"chart": b.chart})
    ids = re.findall(r'id="([^"]+)"', html)
    assert len(ids) == len(set(ids)), ids
    assert 'id="orden-a"' in html and 'id="orden-b"' in html
    assert economico.economic_view(procedure).uid == "economico"


# --- Sin ofertas y sin totales --------------------------------------------------------------------


def test_sin_ofertas_el_dia_de_la_apertura_y_pendiente_sin_cifras(procedure, opening):
    """REQ-130: sin ofertas cargadas, el día de la apertura (del cronograma) y «Pendiente»,
    ninguna cifra de monto."""
    vista = economico.economic_view(procedure)
    assert vista.state == economico.STATE_PENDING
    assert vista.opening_day == "22/09/2026"
    assert vista.missing == "Pendiente"
    assert vista.rows == [] and vista.count == 0
    assert vista.low is None and vista.high is None
    assert vista.chart.has_data is False


def test_sin_ofertas_y_sin_cronograma_no_inventa_el_dia(procedure):
    """REQ-141: sin cronograma no hay día de apertura; sigue «Pendiente»."""
    vista = economico.economic_view(procedure)
    assert vista.state == economico.STATE_PENDING
    assert vista.opening_day is None and vista.missing == "Pendiente"


def test_ofertas_sin_ningun_total_solo_la_cantidad_y_falta_el_total(make, procedure):
    """REQ-141: con ofertas pero sin total en ninguna, solo se dice cuántas son y «Falta el
    total»; ni cifra de monto, ni orden, ni más baja."""
    make(1, None)
    make(2, False)
    vista = economico.economic_view(procedure)
    assert vista.state == economico.STATE_NO_TOTAL
    assert vista.count == 2
    assert vista.missing == "Falta el total"
    assert vista.rows == []
    assert vista.low is None and vista.high is None and vista.chart.has_data is False


# --- Detalle (`_economico.html`) ------------------------------------------------------------------


def dibujar(vista):
    return render_to_string("journey/_economico.html", {"orden": vista})


def test_el_detalle_con_tres_ofertas(make, procedure):
    """REQ-130: el cuadro lista las tres de menor a mayor, con «La más baja», «La más alta» y la
    diferencia con la más baja."""
    make(1, Decimal("1100.00"))
    make(2, Decimal("1000.00"))
    make(3, Decimal("1250.00"))
    html = dibujar(economico.economic_view(procedure))
    assert html.index("$ 1.000,00") < html.index("$ 1.100,00") < html.index("$ 1.250,00")
    assert "La más baja" in html and "La más alta" in html
    assert "+10,0 %" in html and "+25,0 %" in html
    assert "estimado" not in html.lower()
    assert "style=" not in html


def test_el_detalle_sin_ofertas_no_tiene_cifras(procedure, opening):
    """REQ-130: sin ofertas, el día de la apertura y «Pendiente»; ninguna cifra salvo el día."""
    html = dibujar(economico.economic_view(procedure))
    assert "22/09/2026" in html and "Pendiente" in html
    assert "$" not in html and "%" not in html
    sin_dia = re.sub(r"22/09/2026", "", re.sub(r"<[^>]+>", " ", html))
    assert digitos(sin_dia) == []


def test_el_detalle_sin_totales_dice_falta_el_total(make, procedure):
    """REQ-141: ofertas sin total, «Falta el total» y la cantidad, sin cifra inventada."""
    make(1, None)
    make(2, None)
    html = dibujar(economico.economic_view(procedure))
    assert "Falta el total" in html
    sin_cantidad = re.sub(r"<[^>]+>", " ", html).replace("2 ofertas", "")
    assert digitos(sin_cantidad) == []
    assert "$" not in html


def test_el_detalle_avisa_las_monedas_distintas(make, procedure):
    """REQ-141: el aviso de monedas distintas llega al detalle."""
    make(1, Decimal("1000.00"), "ARS")
    make(2, Decimal("900.00"), "USD")
    vista = economico.economic_view(procedure)
    assert vista.warning in dibujar(vista)
