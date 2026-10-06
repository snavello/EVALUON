"""Lectura del cuadro comparativo (REQ-047; T-143): precio y cantidad por oferente y renglón."""

from decimal import Decimal

from evaluon.portal.parsing.cuadro import parse_cuadro
from tests.portal.fakeportal import DATA, EXPECTED

CUADRO = (DATA / "cuadro-comparativo.html").read_bytes()


def test_eighteen_pairs_with_price_and_quantity():
    """REQ-047: los 18 pares oferta y renglón, iguales a los del calco."""
    cuadro = parse_cuadro(CUADRO)
    assert cuadro.issues == []
    got = {(q["renglon"], q["cuit"]): q for q in cuadro.quotes}
    assert len(cuadro.quotes) == len(got) == len(EXPECTED["pares_oferta_renglon"]) == 18
    for want in EXPECTED["pares_oferta_renglon"]:
        quote = got[(want["renglon"], want["cuit"])]
        assert quote["precio"] == Decimal(str(want["precio_unitario"]))
        assert quote["cantidad"] == Decimal(str(want["cantidad"]))
        assert quote["total"] == Decimal(str(want["total"]))


def test_bidders_with_cuit_and_total():
    cuadro = parse_cuadro(CUADRO)
    got = {b.cuit: b for b in cuadro.bidders}
    assert len(got) == 3
    for want in EXPECTED["ofertas"]:
        assert got[want["cuit"]].total == Decimal(str(want["total"]))
        assert got[want["cuit"]].bidder == want["proveedor"]
        assert got[want["cuit"]].order == want["orden_en_cuadro"]


def test_unreadable_price_is_reported_and_left_out():
    html = CUADRO.decode("utf-8").replace("$ 12,50", "sin precio", 1)
    cuadro = parse_cuadro(html.encode("utf-8"))
    assert len(cuadro.quotes) == 17
    assert any("precio" in issue for issue in cuadro.issues)


def test_page_without_bidders_reports_it():
    cuadro = parse_cuadro(b"<html><body>nada</body></html>")
    assert cuadro.quotes == [] and cuadro.issues
