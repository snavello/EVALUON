"""T-240 (ronda de ajuste única de la 015, ADR-0025): los hallazgos de código de la medición T-239
que tocan la evaluación. Un bloque por hallazgo. Textos y datos inventados (P4); sin red ni modelo.

- H-1: el número de una cláusula («11.10.») no es un monto exigido (REQ-103).
"""

from types import SimpleNamespace
from decimal import Decimal

import pytest

from evaluon.assessment import combine, portal_facts, rules
from evaluon.portal import models as pm  # noqa: F401
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import pair_of, portal_data

pytestmark = pytest.mark.django_db


# --- H-1: el número de cláusula no es un monto --------------------------------------------------


@pytest.mark.parametrize("text", [
    "11.10. Cláusula de ejemplo",
    "17.12. Constituir la garantía. 11.10. Otro punto del pliego.",
    "Conforme al punto 11.10 del pliego, el original se presentará en la oficina.",
    "Según los puntos 11.9, 11.10 y 11.11 del pliego.",
    "Ver el artículo 18.10 de la disposición.",
    "Cláusula N° 13.20 y anexo 4.50 del pliego.",
])
def test_a_clause_number_is_not_an_amount(text):
    """REQ-103, T-240 (H-1): «11.10.» al comienzo de una cláusula, o un número de punto o artículo,
    no se lee como monto."""
    assert portal_facts.amounts(text) == []


@pytest.mark.parametrize("text, expected", [
    ("11.10. La garantía será de $ 21.750,00.", [Decimal("21750.00")]),
    ("Constituir una garantía por $ 11.10.", [Decimal("11.10")]),
    ("El Portal informa 5045030.00 de garantía.", [Decimal("5045030.00")]),
    ("17.12. Hasta la suma de $ 3000 en el punto 17.12.", [Decimal("3000")]),
])
def test_an_amount_next_to_a_clause_number_is_still_read(text, expected):
    """REQ-103, T-240 (H-1): lo que sí es un monto se sigue leyendo (con `$`, con separador de miles
    o con dos decimales fuera de un número de cláusula)."""
    assert portal_facts.amounts(text) == expected


def test_the_clause_number_is_not_the_amount_the_pliego_requires(offer, portal):
    """REQ-103, T-240 (H-1): un requisito que empieza con su número («11.10.») y no fija monto ni
    porcentaje no se compara con «11.10»: el Portal no contradice nada (antes: «no cumple»,
    «el pliego exige el monto de 11.10», en ofertas que el dictamen admite)."""
    portal_data(portal, offer, amount="5045030.00")
    text = "11.10. Constituir la garantía de mantenimiento de la oferta en la forma elegida."
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    rules.apply(pair, SimpleNamespace(offer=offer))
    assert pair.combined.outcome != "no_cumple"
    assert pair.combined.facts["comparacion"]["exigido"] != "11.10"
    assert "11.10" not in pair.combined.explanation
