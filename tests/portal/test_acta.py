"""Lectura del acta de apertura (REQ-047; T-143): una oferta por CUIT, con sus garantías."""

from datetime import date
from decimal import Decimal

from evaluon.portal.parsing.acta import parse_acta, parse_amount
from tests.portal.fakeportal import DATA, EXPECTED

ACTA = (DATA / "acta-apertura.html").read_bytes()


def with_rows(extra_rows):
    """El acta del calco con filas de más antes del cierre de la tabla de ofertas."""
    html = ACTA.decode("utf-8")
    start = html.index('id="ctl00_CPH1_UCVistaPreviaActa_gvOfertas"')
    end = html.index("</table>", start)
    return (html[:end] + extra_rows + html[end:]).encode("utf-8")


def row(name, cuit, total, kind="Mantenimiento oferta", form="Seguros", amount="100,00",
        confirmed="30/11/2025"):
    cells = [name, cuit, confirmed, "Peso Argentino", total, total, kind, form, amount]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def test_three_offers_with_total_and_guarantee():
    """REQ-047: las 3 ofertas del acta con oferente, CUIT, fecha, moneda, total y garantía."""
    acta = parse_acta(ACTA)
    assert acta.issues == []
    assert len(acta.offers) == len(EXPECTED["ofertas"]) == 3
    for got, want in zip(sorted(acta.offers, key=lambda o: o.cuit),
                         sorted(EXPECTED["ofertas"], key=lambda o: o["cuit"])):
        assert got.bidder == want["proveedor"]
        assert got.cuit == want["cuit"]
        assert got.currency == want["moneda"]
        assert got.total == Decimal(str(want["total"]))
        day, month, year = (int(p) for p in want["confirmada"].split("/"))
        assert got.confirmed_on == date(year, month, day)
        (guarantee,) = got.guarantees
        assert guarantee == {"tipo": want["garantia"]["tipo"], "forma": want["garantia"]["forma"],
                             "monto": Decimal(str(want["garantia"]["monto"]))}


def test_same_bidder_in_two_rows_is_one_offer_with_both_guarantees():
    """El acta repite la oferta por cada garantía: se agrupa por CUIT y no se duplica."""
    extra = row("ALBERTO DEMO TRES", "20000000036", "195823,50", amount="65000")
    acta = parse_acta(with_rows(extra))
    assert len(acta.offers) == 3
    alberto = next(o for o in acta.offers if o.cuit == "20000000036")
    assert [g["monto"] for g in alberto.guarantees] == [Decimal("9791.17"), Decimal("65000")]
    assert alberto.total == Decimal("195823.50")


def test_repeated_identical_rows_and_empty_guarantee_rows_are_dropped():
    """Las filas idénticas y las que no traen garantía no suman garantías."""
    extra = (row("ALBERTO DEMO TRES", "20000000036", "195823,50", form="Pagare", amount="9791,17")
             + row("ALBERTO DEMO TRES", "20000000036", "195823,50", kind="", form="", amount="")
             + row("Otro Demo Cuatro", "20111111113", "1000,00", kind="", form="", amount=""))
    acta = parse_acta(with_rows(extra))
    alberto = next(o for o in acta.offers if o.cuit == "20000000036")
    assert len(alberto.guarantees) == 1
    cuatro = next(o for o in acta.offers if o.cuit == "20111111113")
    assert cuatro.guarantees == [] and cuatro.total == Decimal("1000")


def test_two_totals_for_one_cuit_are_reported():
    acta = parse_acta(with_rows(row("ALBERTO DEMO TRES", "20000000036", "1,00")))
    assert any("dos totales distintos" in issue for issue in acta.issues)
    alberto = next(o for o in acta.offers if o.cuit == "20000000036")
    assert alberto.total == Decimal("195823.50")


def test_row_without_valid_cuit_is_reported_not_invented():
    acta = parse_acta(with_rows(row("Sin Cuit Demo", "123", "10,00")))
    assert len(acta.offers) == 3
    assert any("CUIT" in issue for issue in acta.issues)


def test_page_without_the_offers_table_reports_it():
    acta = parse_acta(b"<html><body>nada</body></html>")
    assert acta.offers == [] and acta.issues


def test_argentine_amounts():
    assert parse_amount("$ 1.424.715.600,00") == Decimal("1424715600.00")
    assert parse_amount("195823,50") == Decimal("195823.50")
    assert parse_amount("178376") == Decimal("178376")
    assert parse_amount("1.500") == Decimal("1500")
    assert parse_amount("") is None


def test_same_cuit_with_different_names_is_reported_and_stays_one_offer():
    """REQ-047: el mismo CUIT con nombres distintos en el acta se informa; una sola oferta."""
    acta = parse_acta(with_rows(row("OTRO NOMBRE SA", "20000000036", "195823,50", amount="1,00")))
    assert any("nombres distintos" in issue for issue in acta.issues)
    assert len([o for o in acta.offers if o.cuit == "20000000036"]) == 1
    alberto = next(o for o in acta.offers if o.cuit == "20000000036")
    assert alberto.bidder != "OTRO NOMBRE SA"
