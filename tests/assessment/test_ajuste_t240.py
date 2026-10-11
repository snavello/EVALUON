"""T-240 (ronda de ajuste única de la 015, ADR-0025): los hallazgos de código de la medición T-239
que tocan la evaluación. Un bloque por hallazgo. Textos y datos inventados (P4); sin red ni modelo.

- H-1: el número de una cláusula («11.10.») no es un monto exigido (REQ-103).
- H-2: el requisito de una forma de garantía no aplica a la oferta que eligió otra (REQ-103,
  decisión del 2026-10-10 «Requisito de la forma elegida»).
"""

from decimal import Decimal
from types import SimpleNamespace

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


# --- H-2: el requisito de una forma de garantía solo se evalúa en la oferta que la eligió -----------

PAGARE_LIMIT = ("Si se trata de pagaré, el oferente deberá tener en cuenta que el mismo no podrá "
                "superar los DOSCIENTOS SESENTA (260) MÓDULOS y no será combinable con otra forma "
                "de garantía.")
PAGARE_COPY = ("Será requisito no susceptible de subsanación adjuntar con la oferta copia del "
               "pagaré.")
POLICY_UPLOAD = ("Adicionalmente, el oferente deberá cargar el documento electrónico de la póliza "
                 "de seguro de caución electrónica en el Portal de Compras: “Paso 3 Requisitos "
                 "mínimos administrativos”. En su defecto y de contarse en la oferta con constancias de la "
                 "constitución o la individualización de la garantía de mantenimiento de la oferta, el "
                 "Organismo requerirá su presentación.")
NOT_ELECTRONIC = ("En el caso de optar por garantías no electrónicas, el original de la garantía "
                  "deberá ser presentado en la Mesa de Entrada.")


def chosen_form(portal, offer, form, amount="21750.00"):
    """El Portal informa una garantía de mantenimiento de la oferta en la forma `form`."""
    data = pm.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", currency="ARS", total=Decimal("435000.00"), item=portal)
    pm.PortalGuarantee.objects.create(
        offer_data=data, guarantee_type="Mantenimiento oferta", guarantee_form=form,
        amount=Decimal(amount), item=portal)
    return data


def apply(offer, text, outcome="no_determinado", doubt="falta_coincidencia", **fields):
    pair = pair_of(text, combine.Combined(outcome=outcome, doubt=doubt, **fields))
    return rules.apply(pair, SimpleNamespace(offer=offer)), pair.combined


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, form", [
    (PAGARE_LIMIT, "Seguros"),        # el límite del pagaré en una oferta con póliza
    (PAGARE_COPY, "Seguros"),         # la copia del pagaré en una oferta con póliza
    (POLICY_UPLOAD, "Pagare"),        # la póliza que se carga en el Portal en una oferta con pagaré
    (NOT_ELECTRONIC, "Seguros"),      # el original de las garantías no electrónicas, con póliza
])
def test_the_requirement_of_a_form_not_chosen_does_not_apply(offer, portal, text, form):
    """REQ-103, decisión del 2026-10-10 «Requisito de la forma elegida»: el requisito de una forma
    de garantía que la oferta no eligió no aplica: «cumple» con la explicación «No aplica», la
    cita del Portal que muestra la forma elegida y sin pregunta (antes: «no cumple» o «falta de
    coincidencia» en condiciones de la póliza evaluadas en el pagaré y al revés)."""
    chosen_form(portal, offer, form)
    name, combined = apply(offer, text)
    assert name == "forma_garantia_no_elegida"
    assert (combined.outcome, combined.doubt) == ("cumple", "")
    assert combined.explanation.startswith("No aplica:") and form in combined.explanation
    assert combined.facts["aplica"] is False and combined.facts["regla"] == name
    assert combined.facts["version_reglas"] == "reglas-v10"
    assert combined.question == "" and not combined.ask
    assert combined.citations == [] and len(combined.portal) == 1
    assert combined.portal[0]["kind"] == "garantia" and form in combined.portal[0]["text"]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, form", [
    (PAGARE_LIMIT, "Pagare"),
    (PAGARE_COPY, "Pagare"),
    (POLICY_UPLOAD, "Seguros"),
    (NOT_ELECTRONIC, "Pagare"),
])
def test_the_requirement_of_the_form_chosen_is_evaluated_as_always(offer, portal, text, form):
    """REQ-103, «Requisito de la forma elegida»: en la oferta que eligió esa forma el requisito se
    evalúa: la regla de la forma no decide y queda lo que concluyó el modelo."""
    chosen_form(portal, offer, form)
    name, combined = apply(offer, text, outcome="cumple", doubt="")
    assert name != "forma_garantia_no_elegida"
    assert combined.outcome == "cumple" and not combined.explanation.startswith("No aplica")
    assert "aplica" not in combined.facts


@pytest.mark.parametrize("text", [
    # nombra dos formas: vale para todas las ofertas
    "La garantía se constituirá con pagaré o con póliza de seguro de caución.",
    # nombra una forma sin condicionarla ni pedir su documento
    "La garantía de mantenimiento se constituirá mediante póliza de seguro de caución.",
    # no es una forma de garantía
    "Se acompañará una póliza de seguro de responsabilidad civil.",
    # ninguna forma
    "Constituir una garantía de mantenimiento de la oferta del cinco por ciento (5 %).",
])
def test_a_requirement_that_is_not_of_one_form_applies_to_every_offer(offer, portal, text):
    """REQ-103: solo es «de una forma» el requisito que nombra una sola y la condiciona o pide su
    documento; los demás valen para todas las ofertas."""
    chosen_form(portal, offer, "Seguros" if "pagaré" in text.lower() else "Pagare")
    name, _ = apply(offer, text)
    assert name != "forma_garantia_no_elegida"


def test_without_the_portal_form_the_rule_says_nothing(offer, portal):
    """REQ-103: sin garantía del Portal, o con una forma que no se reconoce, la regla no decide:
    queda lo que concluyó el modelo (que la instrucción guía)."""
    name, combined = apply(offer, PAGARE_LIMIT, outcome="cumple", doubt="")
    assert name != "forma_garantia_no_elegida" and combined.outcome == "cumple"
    chosen_form(portal, offer, "Efectivo")
    name, _ = apply(offer, PAGARE_LIMIT)
    assert name != "forma_garantia_no_elegida"


def test_the_guarantee_of_another_obligation_is_not_the_form_chosen(offer, portal):
    """REQ-103: la garantía de cumplimiento que informe el Portal no cuenta como la forma elegida
    para la oferta."""
    data = chosen_form(portal, offer, "Seguros")
    pm.PortalGuarantee.objects.filter(offer_data=data).update(guarantee_type="Cumplimiento de contrato")
    name, _ = apply(offer, PAGARE_LIMIT)
    assert name != "forma_garantia_no_elegida"


# --- La regla del Portal no compara lo que el requisito no pide (T-239: 8 «no determinado» de código) --

QUOTE_PER_LINE = ("Cuando se admita la cotización parcial para las cooperativas, el resto de los "
                  "oferentes podrá cotizar en el apartado «oferta alternativa del SESENTA POR "
                  "CIENTO (60 %)» del Portal diferentes precios según los porcentajes de "
                  "adjudicación posibles hasta los cuales el organismo podrá adjudicar, sin "
                  "perjuicio de que deberán presentar la cotización por la cantidad total de "
                  "cada renglón.")


def quoted_lines(offer, procedure, portal, numbers=(1, 2, 3)):
    portal_data(portal, offer)
    for number in numbers:
        line = pm.PortalLine.objects.create(
            procedure=procedure, number=number, description="x", item=portal)
        pm.PortalQuote.objects.create(
            offer=offer, line=line, price=Decimal("100.0000"), quantity=Decimal("10.0000"))


@pytest.mark.decision_literal
def test_an_alternative_percentage_and_a_hasta_that_are_not_about_the_price_do_not_block_the_quote(
        offer, procedure, portal):
    """REQ-103, T-240: «hasta los cuales…» y «oferta alternativa del 60 %» describen la oferta
    alternativa y la adjudicación, no un tope ni un porcentaje del precio: el Portal tiene el precio
    de todos los renglones y el requisito pide la cotización de cada renglón, entonces «cumple»
    con la cita del Portal (antes: «tope que el sistema no compara»)."""
    quoted_lines(offer, procedure, portal)
    pair = pair_of(QUOTE_PER_LINE, combine.Combined(outcome="no_determinado", doubt="duda"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple" and pair.combined.portal


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "El oferente deberá cotizar cada renglón con un descuento del 10 % sobre el precio de lista.",
    "El precio unitario de cada renglón será de hasta $ 500,00.",
    "El oferente deberá cotizar el precio unitario de cada renglón, con un recargo de hasta "
    "5 % sobre el total.",
])
def test_a_percentage_or_a_hasta_that_is_about_the_price_still_blocks_the_quote(
        offer, procedure, portal, text):
    """REQ-103, D-233-1: un descuento, un recargo o un «hasta» con un valor sobre el precio siguen
    sin compararse: nunca «cumple»."""
    quoted_lines(offer, procedure, portal)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    rules.apply(pair, SimpleNamespace(offer=offer))
    assert pair.combined.outcome != "cumple"
    assert pair.combined.facts["regla"] != "portal_cumple"


@pytest.mark.decision_literal
def test_loading_the_policy_in_the_portal_is_met_by_the_guarantee_the_portal_informs(offer, portal):
    """REQ-103, T-240: «cargar el documento de la póliza en el Portal» con una póliza como forma
    elegida: el Portal informa esa garantía, «cumple» con la cita del Portal aunque el modelo no
    la haya visto (antes: «tope que el sistema no compara», por «Requisitos mínimos»)."""
    chosen_form(portal, offer, "Seguros")
    pair = pair_of(POLICY_UPLOAD, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple" and pair.combined.portal[0]["kind"] == "garantia"
    assert pair.combined.explanation.startswith("Fuente: Portal")


@pytest.mark.parametrize("text, form", [
    (PAGARE_COPY, "Pagare"),         # la copia del pagaré se mira en los documentos
    (NOT_ELECTRONIC, "Pagare"),      # el original en la Mesa de Entrada no lo resuelve el Portal
    ("El original de la garantía se presentará en la Mesa de Entrada.", "Seguros"),
])
def test_a_requirement_about_a_guarantee_document_is_not_decided_by_the_portal_amount(
        offer, portal, text, form):
    """REQ-103, T-240: un requisito sobre el documento de la garantía (copia, original, Mesa de
    Entrada) no pide un monto: el Portal no decide, queda lo que concluyó el modelo y no hay
    «falta de coincidencia» por un monto que nadie pidió."""
    chosen_form(portal, offer, form)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) is None
    assert pair.combined.outcome == "sin_documento"
