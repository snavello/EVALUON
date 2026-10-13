"""El fundamento se ve en «Descartes propuestos» y en el orden económico (REQ-103, REQ-104; P3;
dictamen de la 015, hallazgos 1 y 2; plan 015, T-264, barrido de las pantallas).

- La cita de la oferta de un motivo de descarte, si su página se leyó por visión, lleva la marca
  «leída por visión», el aviso de comparar con el original y el enlace al original (ADR-0041).
- El dato del Portal en que se apoya un motivo lleva el enlace a su página y la fecha en que se
  tomó (constitución 1.3, ADR-0053).
- El orden económico dice de qué páginas del Portal salen los precios y totales, y de qué ofertas.
Los resultados se guardan directo, sin el modelo; todo el material es inventado (P4)."""

from decimal import Decimal

import pytest

from tests.assessment.test_matrix import add_run, requirement, three  # noqa: F401 - fixtures
from tests.assessment.test_ordering import quote_data
from tests.assessment.test_result_fundamento import (  # noqa: F401 - `portal` es fixture
    PAGE_URL,
    SHOWN,
    portal,
)
from tests.journey.temas.test_s4_fundamento_pantallas import (
    LINK,
    MARK,
    NOTICE,
    evaluate_with,
    original_of,
    section,
    vision_reading,
)
from tests.journey.temas.test_s4_propuesta import log_in, page

pytestmark = pytest.mark.django_db


def test_a_discard_ground_marks_the_quote_only_when_it_was_read_by_vision(
        client, three, procedure, operator_user):  # noqa: F811
    """REQ-104, REQ-053, P3: en «Descartes propuestos», el motivo cuya cita de la oferta es de una
    página leída por visión lleva la marca, el aviso y el enlace al original; el de una página
    legible no."""
    a, b, c = three
    declaration = requirement(procedure, "declaración jurada")
    seen = vision_reading(b.documents.first())
    evaluate_with(operator_user, procedure, b, declaration, "no_cumple", ("oferta", seen, 2))
    evaluate_with(operator_user, procedure, c, declaration, "no_cumple",
                  ("oferta", c.documents.first().readings.get(), 1))
    log_in(client, operator_user)
    html = page(client, procedure)
    mine = section(html, f"desc-{b.number}", "</tr>")
    original = original_of(b.documents.first(), 2)
    assert mine.count(NOTICE) == 1 and MARK in mine
    assert f'<a href="{original}">{LINK}</a>' in mine
    theirs = section(html, f"desc-{c.number}", "</tr>")
    assert "La oferta dice:" in theirs and NOTICE not in theirs and MARK not in theirs


def test_a_discard_ground_decided_by_the_portal_gives_its_page_and_date(
        client, three, procedure, operator_user, portal):  # noqa: F811
    """REQ-103, P3: en «Descartes propuestos», un motivo que se apoya en el dato del Portal lo
    muestra con el enlace a su página y la fecha en que se tomó, en lugar de decir solo que no hay
    texto de la oferta."""
    _, b, _ = three
    declaration = requirement(procedure, "declaración jurada")
    evaluate_with(operator_user, procedure, b, declaration, "no_cumple", ("portal", portal))
    log_in(client, operator_user)
    mine = section(page(client, procedure), f"desc-{b.number}", "</tr>")
    assert "Sin texto de la oferta que lo respalde." in mine
    assert "Dato del Portal:</span> Garantía: tipo inventado, monto 1000.00" in mine
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in mine
    assert f"página consultada el {SHOWN}" in mine


def test_the_economic_order_says_which_portal_pages_the_prices_come_from(
        client, three, procedure, operator_user, portal):  # noqa: F811
    """REQ-103, P3: el orden económico (precios y totales del Portal) dice de qué página del
    Portal salen, con su enlace y la fecha en que se tomó, y a qué ofertas corresponde."""
    a, b, c = three
    declaration = requirement(procedure, "declaración jurada")
    for offer, total in ((a, "900"), (b, "100"), (c, "500")):
        add_run(operator_user, procedure, offer, {declaration: "cumple"})
        quote_data(portal, procedure, offer, total=Decimal(total),
                   prices={1: (Decimal("10"), 1), 2: (Decimal("10"), 1)})
    log_in(client, operator_user)
    source = section(page(client, procedure), "orden-fuente", "</p>")
    numbers = f"{a.number}, {b.number} y {c.number}"
    assert f"Precios y totales de las ofertas {numbers}" in source
    assert f'<a href="{PAGE_URL}">página del Portal</a>' in source
    assert f"página consultada el {SHOWN}" in source
