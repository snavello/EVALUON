"""Errores gruesos de la revisión C en la evaluación (REQ-062, REQ-063; plan 014, T-231): la falta
de coincidencia con el Portal compara el mismo dato y tolera un centavo, una misma diferencia no
se marca tres veces en la oferta, y la declaración jurada de habilidad que la oferta trae no es un
requisito externo. Datos inventados (P4)."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, externals, rules
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import located, pair_of, portal_data

pytestmark = pytest.mark.django_db

GUARANTEE_REQ = "Constituir la garantía de mantenimiento de la oferta del 5 % del monto total."


def numbered(pair, number):
    pair.requirement.number = number
    return pair


def guarantee_pair(number, fragment, *, cited=True):
    citations = [located(fragment)] if cited else []
    return numbered(pair_of(GUARANTEE_REQ, combine.Combined(outcome="cumple",
                                                            citations=citations),
                            datos=[fragment]), number)


# --- E-5: se compara el mismo dato ---------------------------------------------------------------


def test_the_guarantee_is_not_compared_with_the_total_of_the_offer(offer, portal):
    """REQ-062, E-5: si el fragmento que la oferta trae es el total, no se compara contra la
    garantía del Portal: no hay «falta coincidencia» entre garantía y total."""
    portal_data(portal, offer, amount="4620585.50", total="92411710.00")
    pair = guarantee_pair(29, "Total de la oferta: $ 92.411.710,00")
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cita_agregada"
    assert pair.combined.doubt != "falta_coincidencia"
    assert pair.combined.outcome == "cumple"


def test_the_guarantee_is_still_compared_with_the_guarantee(offer, portal):
    """REQ-062, E-5: una garantía distinta de la del Portal sigue siendo falta de coincidencia,
    y el texto dice los dos montos de la garantía."""
    portal_data(portal, offer, amount="4620585.50", total="92411710.00")
    pair = guarantee_pair(29, "garantiza hasta la suma de $ 3.000.000,00")
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert "4620585.50" in pair.combined.explanation
    assert "3000000" in pair.combined.explanation


def test_the_total_is_not_compared_with_the_guarantee(offer, portal):
    """REQ-062, E-5: al revés, si el requisito pide el total y el fragmento es la garantía."""
    portal_data(portal, offer, amount="4620585.50", total="92411710.00")
    pair = numbered(pair_of("Indicar el precio total de la oferta.", combine.Combined(
        outcome="cumple", citations=[located("garantiza hasta $ 4.620.585,50")]),
        datos=["garantiza hasta $ 4.620.585,50"]), 5)
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cita_agregada"


# --- E-7: un centavo de redondeo y una sola vez por oferta ------------------------------------------


def test_a_difference_of_one_cent_is_rounding_not_a_lack_of_coincidence(offer, portal):
    """REQ-062, E-7: el Portal informa 4819384.47 y la oferta 4819384.48: coinciden."""
    portal_data(portal, offer, amount="4819384.47", total="96387689.50")
    pair = guarantee_pair(29, "garantiza hasta la suma de $ 4.819.384,48")
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cita_agregada"
    assert pair.combined.outcome == "cumple"


def test_two_cents_are_still_a_lack_of_coincidence(offer, portal):
    """REQ-062, E-7: la tolerancia es de un centavo y no más."""
    portal_data(portal, offer, amount="4819384.47", total="96387689.50")
    pair = guarantee_pair(29, "garantiza hasta la suma de $ 4.819.384,49")
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"


def test_the_same_difference_keeps_the_lack_of_coincidence_and_says_which_requirement_has_it(
        offer, portal):
    """REQ-062, E-7, D-1: la misma diferencia en tres requisitos de la misma oferta sigue siendo
    «falta coincidencia» en los tres; el segundo y el tercero explican «misma diferencia que en
    el requisito 29» y no repiten la pregunta (no hay ninguna)."""
    portal_data(portal, offer, amount="4819384.47", total="96387689.50")
    ctx = SimpleNamespace(offer=offer)
    fragment = "garantiza hasta la suma de $ 3.000.000,00"
    pairs = [guarantee_pair(number, fragment) for number in (29, 32, 39)]
    assert [rules.apply(pair, ctx) for pair in pairs] == ["portal_falta_coincidencia"] * 3
    assert [p.combined.doubt for p in pairs] == ["falta_coincidencia"] * 3
    assert "misma diferencia que en el requisito" not in pairs[0].combined.explanation
    for repeated in pairs[1:]:
        assert "misma diferencia que en el requisito 29" in repeated.combined.explanation
        assert repeated.combined.question == ""
        assert repeated.combined.facts["diferencia_ya_senalada"] == 29
        assert repeated.combined.portal  # la cita del Portal sigue


def test_a_difference_in_another_offer_is_explained_from_scratch(offer, portal):
    """REQ-062, E-7: el contexto es el de la oferta: en otra evaluación la primera vez no remite a
    ningún otro requisito."""
    portal_data(portal, offer, amount="4819384.47", total="96387689.50")
    fragment = "garantiza hasta la suma de $ 3.000.000,00"
    first = guarantee_pair(29, fragment)
    assert rules.apply(first, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    again = guarantee_pair(29, fragment)
    assert rules.apply(again, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert "misma diferencia que en el requisito" not in again.combined.explanation


# --- E-6: la declaración jurada que la oferta trae no es externa -----------------------------------


@pytest.mark.parametrize("text", [
    "ANEXO I o II - DECLARACIÓN JURADA HABILIDAD PARA CONTRATAR: completar, suscribir y "
    "adjuntar.",
    "El oferente deberá completar, suscribir y adjuntar la declaración jurada de habilidad para "
    "contratar que se agrega como Anexo.",
    "Presentar la declaración jurada de habilidad para el Estado, anexo B.",
    "Declaración jurada sobre causas penales, sanciones o inhabilidad del artículo 18.",
    "Declaración jurada de habilidad para contratar: no estar comprendido en las causales del "
    "artículo 18 ni tener causas penales.",
])
def test_the_habilidad_declaration_that_the_offer_brings_is_not_external(text):
    """REQ-063, E-6: completar y adjuntar la declaración jurada de habilidad es un documento de
    la oferta; no lleva «falta la hoja de compliance»."""
    assert "habilidad_contratar" not in [c.key for c in externals.match(text)]


@pytest.mark.parametrize("text", [
    "La habilidad para contratar del oferente se verificará en la etapa de evaluación.",
    "La Comisión consultará el Registro de Proveedores para constatar la habilidad para "
    "contratar de cada oferente.",
])
def test_the_check_of_the_habilidad_by_the_commission_stays_external(text):
    """REQ-063, E-6: lo externo es la consulta que hace la Comisión, no la declaración."""
    assert "habilidad_contratar" in [c.key for c in externals.match(text)]


def test_the_catalog_matches_long_texts_without_slowing_down():
    """REQ-100, E-11: reconocer un requisito largo no tarda (el patrón de la declaración jurada
    recorría el texto entero por cada coincidencia parcial)."""
    import time

    text = ("El oferente deberá completar, suscribir y adjuntar la declaración jurada. " * 200
            + "Anexo. ")
    started = time.perf_counter()
    for _ in range(20):
        externals.match(text)
    assert time.perf_counter() - started < 1.0
