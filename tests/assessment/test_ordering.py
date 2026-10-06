"""Descarte parcial por renglón y orden económico con los datos del Portal (REQ-059; plan 004,
"Decisiones del responsable", puntos 2 y 3; T-152). Caso chico y cotizaciones inventadas (P4)."""

from decimal import Decimal

import pytest
from django.urls import reverse

from evaluon.assessment import ordering
from evaluon.portal import models as pm
from tests.assessment.test_matrix import (  # noqa: F401 - `three` es una fixture
    add_run,
    discard_of,
    open_matrix,
    page_of,
    requirement,
    three,
)
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def portal(procedure, operator_user):
    """Un ítem de oferta del Portal, del que cuelgan los datos."""
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=operator_user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1,
                                                origin="importacion")
    item = pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o",
                                        payload={}, content_sha256="b" * 64, page=page)
    return item


def quote_data(portal, procedure, offer, *, total, currency="ARS", prices=None):
    """Los datos del Portal de una oferta: total, moneda y `{renglón: (precio, cantidad)}`."""
    pm.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", currency=currency, total=total, item=portal)
    for number, (price, quantity) in (prices or {}).items():
        line, _ = pm.PortalLine.objects.get_or_create(
            procedure=procedure, number=number,
            defaults={"description": f"Renglón {number}", "item": portal})
        pm.PortalQuote.objects.create(offer=offer, line=line, price=price, quantity=quantity)


def order_of(user, procedure):
    return page_of(user, procedure).order


def positions(rows):
    return [(r.offer.number, r.position) for r in rows]


def test_the_total_order_is_the_one_of_the_portal_data_and_a_missing_one_goes_last(
        three, portal, procedure, operator_user):
    """REQ-059: orden por precio total igual al de los datos del Portal; una oferta sin datos
    queda al final, sin posición."""
    a, b, c = three
    quote_data(portal, procedure, a, total=Decimal("900.00"))
    quote_data(portal, procedure, c, total=Decimal("500.00"))
    order = order_of(operator_user, procedure)
    assert positions(order.totals) == [(c.number, 1), (a.number, 2), (b.number, None)]
    assert order.totals[-1].note == ordering.NO_PORTAL_DATA
    assert order.warning == ""


def test_equal_totals_share_the_position(three, portal, procedure, operator_user):
    """Empatados comparten posición y el siguiente salta."""
    a, b, c = three
    for offer, total in ((a, "500.00"), (b, "500.00"), (c, "700.00")):
        quote_data(portal, procedure, offer, total=Decimal(total))
    assert positions(order_of(operator_user, procedure).totals) == [
        (a.number, 1), (b.number, 1), (c.number, 3)]


def test_the_order_per_line_uses_the_price_times_the_quantity(
        three, portal, procedure, operator_user):
    """REQ-059: orden por renglón con la cotización del Portal; el que no cotizó va al final."""
    a, b, c = three
    quote_data(portal, procedure, a, total=Decimal("1"), prices={1: (Decimal("10"), 5),
                                                               2: (Decimal("7"), 1)})
    quote_data(portal, procedure, b, total=Decimal("2"), prices={1: (Decimal("20"), 1)})
    quote_data(portal, procedure, c, total=Decimal("3"), prices={1: (Decimal("12"), 2),
                                                               2: (Decimal("6"), 2)})
    lines = {line.line.number: line for line in order_of(operator_user, procedure).lines}
    assert positions(lines[1].rows) == [(b.number, 1), (c.number, 2), (a.number, 3)]
    assert positions(lines[2].rows) == [(a.number, 1), (c.number, 2), (b.number, None)]
    assert lines[2].rows[-1].note == ordering.NO_PRICE


def test_different_currencies_are_not_ordered_and_the_page_warns(
        three, portal, procedure, operator_user, client):
    """REQ-059: monedas distintas, sin orden y con aviso."""
    a, b, c = three
    quote_data(portal, procedure, a, total=Decimal("900"), currency="ARS")
    quote_data(portal, procedure, b, total=Decimal("100"), currency="USD")
    quote_data(portal, procedure, c, total=Decimal("800"), currency="ARS")
    order = order_of(operator_user, procedure)
    assert all(r.position is None for r in order.totals[:2])
    assert "monedas distintas" in order.warning
    log_in(client, operator_user)
    text = text_of(client.get(reverse("assessment:matrix", args=[procedure.pk])))
    assert "monedas distintas" in text


def test_a_discarded_offer_is_left_out_of_the_order(three, portal, procedure, operator_user):
    """REQ-059: se ordena lo no descartado."""
    a, b, c = three
    quote_data(portal, procedure, a, total=Decimal("900"))
    quote_data(portal, procedure, b, total=Decimal("100"))
    quote_data(portal, procedure, c, total=Decimal("800"))
    add_run(operator_user, procedure, b, {requirement(procedure, "declaración jurada"):
                                          "no_cumple"})
    order = order_of(operator_user, procedure)
    assert positions(order.totals) == [(c.number, 1), (a.number, 2)]


def test_a_technical_no_cumple_discards_only_that_line_and_the_offer_stays_in_the_total(
        three, portal, procedure, operator_user):
    """REQ-059 (descarte parcial, dictamen del caso-00): un "no cumple" de la fila técnica de un
    renglón descarta ese renglón y no la oferta; sale del orden de ese renglón y sigue en el
    total y en los otros renglones."""
    a, b, c = three
    quote_data(portal, procedure, a, total=Decimal("900"), prices={1: (Decimal("10"), 1),
                                                                 2: (Decimal("10"), 1)})
    quote_data(portal, procedure, b, total=Decimal("100"), prices={1: (Decimal("5"), 1),
                                                                 2: (Decimal("5"), 1)})
    add_run(operator_user, procedure, b, {requirement(procedure, item=2): "no_cumple",
                                          requirement(procedure, item=1): "cumple"})
    page = page_of(operator_user, procedure)
    discard = discard_of(page, b)
    assert discard.is_partial and not discard.is_whole and discard.items == [2]
    assert discard.by_item[2][0].item == 2
    lines = {line.line.number: line for line in page.order.lines}
    assert (b.number, 1) in positions(lines[1].rows)
    assert b.number not in [r.offer.number for r in lines[2].rows]
    total = next(r for r in page.order.totals if r.offer.pk == b.pk)
    assert total.position == 1 and "renglones descartados: 2" in total.note


def test_an_economic_no_cumple_discards_through_a_single_constant(
        three, procedure, operator_user, monkeypatch):
    """Decisión 3 del responsable: un "no cumple" económico también descarta; el alcance está
    detrás de `DISCARD_CATEGORIES`."""
    a = three[0]
    add_run(operator_user, procedure, a, {requirement(procedure, "validez de la oferta"):
                                          "no_cumple"})
    assert discard_of(page_of(operator_user, procedure), a).is_whole
    monkeypatch.setattr(ordering, "DISCARD_CATEGORIES", ("formal", "tecnico"))
    assert discard_of(page_of(operator_user, procedure), a) is None


def test_a_consequence_not_yet_chosen_is_shown_as_such(three, procedure, operator_user):
    """La consecuencia prevista: si todavía no se eligió, se muestran las propuestas
    aclarándolo."""
    from evaluon.tenders import models as m

    declaration = requirement(procedure, "declaración jurada")
    open_matrix()
    m.Consequence.objects.create(requirement=declaration, consequence_type="desestimacion",
                                 grounds=[], origin="sistema")
    add_run(operator_user, procedure, three[0], {declaration: "no_cumple"})
    ground = discard_of(page_of(operator_user, procedure), three[0]).whole[0]
    assert ground.consequences == ["Desestimación sin posibilidad de subsanar (sin elegir)"]
