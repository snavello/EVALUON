"""El Portal como fuente (REQ-062, REQ-103; plan 004, "El Portal como fuente"; ADR-0043,
ADR-0053; T-169, T-233).
Decisión literal del 2026-10-10 (ADR-0053, «Propone cumple»): el dato del Portal que coincide con
lo que exige el pliego propone «cumple» con la cita del Portal; si difiere, «no cumple» o la
diferencia. Reemplaza en eso al ADR-0043 («Debiste informar que el doc esta en el portal o que
falta coincidencia»), que citaba el Portal y no decidía.
Datos inventados (P4); el modelo es un guion y no hay red."""

import socket
from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, portal_facts, prompting, rules
from evaluon.assessment.citations import ANOMALY_NOT_FOUND
from evaluon.portal import models as pm
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import number_of, results_of, run_all
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

GUARANTEE = "garantía de mantenimiento"
POLICY = ("Aseguradora Ejemplo S.A. garantiza, hasta la suma de $ 21.750, el cumplimiento de la "
          "obligación del oferente de mantener su oferta.")
AMOUNT = "hasta la suma de $ 21.750"


def portal_data(portal, offer, *, amount="21750.00", cuit="30-00000000-0", total="435000.00"):
    """Los datos del Portal de la oferta con una garantía de mantenimiento."""
    data = pm.PortalOfferData.objects.create(
        offer=offer, cuit=cuit, currency="ARS", total=Decimal(total), item=portal)
    pm.PortalGuarantee.objects.create(
        offer_data=data, guarantee_type="Garantía de mantenimiento de oferta",
        guarantee_form="Póliza de caución", amount=Decimal(amount), item=portal)
    return data


@pytest.fixture
def with_policy(procedure, operator_user, fake_ai):
    """Una oferta que trae la póliza (la garantía está en la oferta)."""
    return make_offer(procedure, operator_user, "Oferente con póliza", {"poliza.pdf": [POLICY]})


def reads_policy(model, *, datos=AMOUNT):
    def function(call):
        if GUARANTEE in call.requirement:
            return says("cumple", call.quote(POLICY.split(", el ")[0]), exigence="documento",
                        datos=[(call.alias_with(POLICY[:20]), datos)])
    model.evaluates(function)


def guarantee_result(procedure, runs):
    return results_of(runs[0])[number_of(procedure, GUARANTEE)]


@pytest.mark.decision_literal
def test_a_guarantee_that_is_five_percent_of_the_portal_total_proposes_cumple_with_the_portal_citation(
        offer, operator_user, procedure, model, portal):
    """REQ-103, ADR-0053: el pliego exige el 5 % del total cotizado, el Portal informa exactamente
    el 5 % del total y la oferta no lo trae: «cumple» con la cita del Portal escrita por el
    sistema, «Fuente: Portal», sin contraste del modelo y sin pregunta."""
    portal_data(portal, offer)
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    assert (result.outcome, result.doubt) == ("cumple", "")
    cite = result.citations.get(kind="portal")
    assert cite.portal_kind == "garantia" and cite.portal_item_id == portal.pk
    assert "21750.00" in cite.text and "Póliza de caución" in cite.text
    assert cite.label == "Portal: acta de apertura"
    assert result.facts["regla"] == "portal_cumple"
    assert result.facts["version_reglas"] == "reglas-v9"
    assert result.facts["portal"]["tipo"] == "garantia"
    assert result.facts["portal"]["valor"] == "21750.00"
    assert result.facts["comparacion"]["exigido"] == "21750.00"
    assert result.facts["comparacion"]["estado"] == "coincide"
    assert "Fuente: Portal" in result.explanation
    assert not result.citations.filter(kind="oferta").exists()
    assert result.citations.filter(kind="pliego").exists()
    assert not result.questions.exists()
    assert not [c for c in model.contrast_calls if "garantía" in c.user]
    assert runs[0].counts["by_rule"]["portal_cumple"] == 1
    assert runs[0].counts["portal"] == {"citations": 1, "items": [portal.pk]}


@pytest.mark.decision_literal
def test_the_same_amount_in_both_proposes_cumple_with_the_offer_and_the_portal_citations(
        with_policy, operator_user, procedure, model, portal):
    """REQ-103: el Portal y la oferta dicen lo mismo y coincide con el pliego: «cumple» con la
    cita de la oferta y la del Portal."""
    portal_data(portal, with_policy)
    reads_policy(model)
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    assert result.outcome == "cumple" and result.doubt == ""
    assert result.citations.filter(kind="oferta").exists()
    assert result.citations.get(kind="portal").portal_item_id == portal.pk
    assert result.facts["regla"] == "portal_cumple"
    assert result.facts["portal"]["valor"] == "21750.00"


@pytest.mark.decision_literal
def test_different_amounts_are_a_lack_of_coincidence_with_both_citations(
        with_policy, operator_user, procedure, model, portal):
    """REQ-062, decisión 4: la oferta dice 21.750 y el Portal 25000.00: «no determinado», «falta
    de coincidencia», con la cita de la oferta y la del Portal."""
    portal_data(portal, with_policy, amount="25000.00")
    reads_policy(model)
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    assert (result.outcome, result.doubt) == ("no_determinado", "falta_coincidencia")
    assert result.citations.filter(kind="oferta").exists()
    assert "25000.00" in result.citations.get(kind="portal").text
    assert result.facts["regla"] == "portal_falta_coincidencia"
    assert "21750" in result.facts["oferta_valor"]
    assert "25000.00" in result.explanation
    assert not result.questions.exists()


def test_a_requirement_that_is_not_of_the_portal_has_no_portal_citation(
        offer, operator_user, procedure, model, portal):
    """REQ-062: un requisito que no pide un dato del Portal sale como antes, sin cita del
    Portal ni regla del Portal."""
    portal_data(portal, offer)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "sesenta días")]
    assert not result.citations.filter(kind="portal").exists()
    assert not str(result.facts.get("regla", "")).startswith("portal")


def test_without_portal_data_for_the_offer_nothing_is_said(
        offer, operator_user, procedure, model):
    """REQ-062: si el Portal no tiene el dato de esa oferta, el resultado no cambia."""
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    assert result.outcome != "cumple" or result.facts.get("regla") != "portal_cumple"
    assert not result.citations.filter(kind="portal").exists()


def test_data_that_cannot_be_located_is_not_compared(
        with_policy, operator_user, procedure, model, portal):
    """REQ-062: un `datos` que no está en la oferta no se compara ni se afirma nada: no hay
    falta de coincidencia; la cita del Portal se agrega y el resultado de la oferta sigue."""
    portal_data(portal, with_policy, amount="25000.00")
    reads_policy(model, datos="la suma de $ 99.999")
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    # El Portal informa 25000.00 y el pliego exige el 5 % de 435000.00: no coinciden y la oferta
    # concluyó «cumple» con otro texto: la Comisión verifica cuál rige.
    assert (result.outcome, result.doubt) == ("no_determinado", "falta_coincidencia")
    assert result.facts["regla"] == "portal_falta_coincidencia"
    assert result.citations.filter(kind="portal").count() == 1
    assert any(a["type"] == ANOMALY_NOT_FOUND for a in runs[0].anomalies)


def test_a_cumple_by_the_portal_never_comes_without_the_portal_citation(
        offer, operator_user, procedure, model, portal):
    """P3, REQ-103: un «cumple» por la regla del Portal siempre lleva la cita del Portal."""
    portal_data(portal, offer)
    _, runs = run_all(operator_user, procedure)
    result = guarantee_result(procedure, runs)
    assert result.outcome == "cumple" and result.citations.filter(kind="portal").count() == 1


def test_the_portal_citation_text_is_the_row_as_it_is(
        offer, operator_user, procedure, model, portal):
    """REQ-062: el texto de la cita lo escribe el sistema desde las columnas de la fila, con el
    monto tal cual."""
    data = portal_data(portal, offer, amount="21750.00")
    guarantee = data.guarantees.get()
    _, runs = run_all(operator_user, procedure)
    cite = guarantee_result(procedure, runs).citations.get(kind="portal")
    assert cite.text == (f"Garantía: tipo {guarantee.guarantee_type}, forma "
                         f"{guarantee.guarantee_form}, monto {guarantee.amount}")


def test_the_evaluation_makes_no_network_call(
        offer, operator_user, procedure, model, portal, monkeypatch):
    """P4: el Portal se lee de las tablas locales."""
    portal_data(portal, offer)

    def refuse(*args, **kwargs):
        raise AssertionError("sin red")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    _, runs = run_all(operator_user, procedure)
    assert guarantee_result(procedure, runs).outcome == "cumple"


# --- La regla sobre un par armado a mano: CUIT, total y cotización --------------------------------


def located(text):
    return SimpleNamespace(text=text, span=(1, 0, len(text)))


def pair_of(text, combined, datos=(), items=()):
    return SimpleNamespace(
        combined=combined, text=SimpleNamespace(text=text), datos=[located(t) for t in datos],
        requirement=SimpleNamespace(items=list(items), category="formal"), groups=[])


@pytest.mark.decision_literal
def test_a_cuit_that_differs_from_the_portal_is_a_lack_of_coincidence(offer, portal):
    """REQ-062, decisión 4: el CUIT de la oferta difiere del del Portal."""
    portal_data(portal, offer, cuit="30-00000000-0")
    ctx = SimpleNamespace(offer=offer)
    pair = pair_of("Informar el CUIT del oferente.", combine.Combined(
        outcome="cumple", citations=[located("CUIT 20-11111111-1")]),
        datos=["CUIT 20-11111111-1"])
    assert rules.apply(pair, ctx) == "portal_falta_coincidencia"
    assert pair.combined.doubt == "falta_coincidencia"
    assert pair.combined.portal[0]["text"] == "CUIT del oferente: 30-00000000-0"
    assert pair.combined.portal[0]["kind"] == "cuit"
    assert pair.combined.facts["portal"] == {
        "tipo": "cuit", "valor": "30-00000000-0", "valores": ["30-00000000-0"],
        "items": [portal.pk]}


def test_the_same_cuit_in_another_format_coincides(offer, portal):
    """REQ-062: el CUIT sin guiones es el mismo."""
    portal_data(portal, offer, cuit="30-00000000-0")
    pair = pair_of("Informar el CUIT del oferente.", combine.Combined(
        outcome="cumple", citations=[located("CUIT 30000000000")]),
        datos=["CUIT 30000000000"])
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple"


def test_the_total_of_the_offer_comes_from_the_portal_row(offer, portal):
    """REQ-062, REQ-103: el total de la oferta se cita desde `portal_offer_data` y, cargado,
    cumple; un total distinto en la oferta es falta de coincidencia."""
    portal_data(portal, offer, total="90000.00")
    ctx = SimpleNamespace(offer=offer)
    only = pair_of("Indicar el precio total de la oferta.",
                   combine.Combined(outcome="sin_documento"))
    assert rules.apply(only, ctx) == "portal_cumple"
    assert only.combined.outcome == "cumple"
    assert "90000.00" in only.combined.portal[0]["text"]
    other = pair_of("Indicar el precio total de la oferta.", combine.Combined(
        outcome="cumple", citations=[located("Total: $ 80.000,00")]),
        datos=["Total: $ 80.000,00"])
    assert rules.apply(other, ctx) == "portal_falta_coincidencia"


def test_a_quote_per_line_comes_from_the_portal_quote(offer, procedure, portal):
    """REQ-062: la cotización de un renglón no técnico se cita con precio y cantidad de la
    fila."""
    portal_data(portal, offer)
    line = pm.PortalLine.objects.create(procedure=procedure, number=2, description="x",
                                        item=portal)
    pm.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("120.5000"),
                                  quantity=Decimal("10.0000"))
    pair = pair_of("Cotizar el renglón 2.", combine.Combined(outcome="sin_documento"),
                   items=[2])
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    cite = pair.combined.portal[0]
    assert cite["kind"] == "cotizacion" and cite["label"] == "Portal: cuadro comparativo"
    assert "120.5000" in cite["text"] and "10.0000" in cite["text"]


# --- Qué exige el pliego, por clase de dato (ADR-0053; T-233) --------------------------------------

GUARANTEE_REQ = ("Constituir una garantía de mantenimiento de la oferta del cinco por ciento "
                 "(5 %) del monto cotizado.")
CTX_TOTAL = "435000.00"
PER_LINE_REQ = ("El oferente deberá cotizar el valor unitario de cada uno de los renglones "
                "ofrecidos.")


@pytest.mark.decision_literal
@pytest.mark.parametrize("amount, regla, outcome", [
    ("21750.00", "portal_cumple", "cumple"),        # exactamente el 5 % del total
    ("21750.01", "portal_cumple", "cumple"),        # un centavo de diferencia: tolerancia
    ("21749.99", "portal_cumple", "cumple"),
    ("21750.02", "portal_no_cumple", "no_cumple"),  # dos centavos: ya difiere
    ("20000.00", "portal_no_cumple", "no_cumple"),  # una diferencia mayor
])
def test_the_guarantee_is_compared_with_the_percentage_of_the_portal_total(
        offer, portal, amount, regla, outcome):
    """REQ-103, ADR-0053: garantía contra el porcentaje del total del Portal, con la tolerancia de
    un centavo: coincide, «cumple»; no coincide, «no cumple» con la diferencia y la cita del
    Portal."""
    portal_data(portal, offer, amount=amount, total=CTX_TOTAL)
    pair = pair_of(GUARANTEE_REQ, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == regla
    assert pair.combined.outcome == outcome and pair.combined.doubt == ""
    assert pair.combined.portal and pair.combined.portal[0]["kind"] == "garantia"
    assert pair.combined.facts["comparacion"]["exigido"] == "21750.00"
    assert pair.combined.facts["version_reglas"] == "reglas-v9"
    if outcome == "no_cumple":
        assert amount in pair.combined.explanation and "21750.00" in pair.combined.explanation
        assert "diferencia" in pair.combined.explanation
    else:
        assert pair.combined.explanation.startswith("Fuente: Portal")
    assert pair.combined.question == ""


def test_a_guarantee_that_adds_up_in_two_instruments_coincides(offer, portal):
    """REQ-103: la garantía en dos instrumentos que suman el 5 % del total coincide."""
    data = portal_data(portal, offer, amount="10000.00", total=CTX_TOTAL)
    pm.PortalGuarantee.objects.create(
        offer_data=data, guarantee_type="Garantía de mantenimiento de oferta",
        guarantee_form="Pagaré", amount=Decimal("11750.00"), item=portal)
    pair = pair_of(GUARANTEE_REQ, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"


@pytest.mark.parametrize("text", [
    "Constituir una garantía de mantenimiento de la oferta.",
    "La garantía de mantenimiento de la oferta será del 5 % y del 10 % según el caso.",
])
def test_a_guarantee_without_one_readable_amount_is_not_comparable(offer, portal, text):
    """REQ-103, ADR-0053 (regla 3): sin un valor exigido que se pueda leer no se compara:
    «no determinado», «falta coincidencia», con el dato del Portal a la vista y sin «cumple»."""
    portal_data(portal, offer)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert (pair.combined.outcome, pair.combined.doubt) == ("no_determinado", "falta_coincidencia")
    assert "21750.00" in pair.combined.explanation and pair.combined.portal


def test_a_guarantee_without_the_portal_total_is_not_comparable(offer, portal):
    """REQ-103: el porcentaje se calcula sobre el total del Portal; sin total no se compara."""
    data = portal_data(portal, offer)
    pm.PortalOfferData.objects.filter(pk=data.pk).update(total=None)
    pair = pair_of(GUARANTEE_REQ, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert pair.combined.outcome == "no_determinado"


def test_a_guarantee_with_a_fixed_amount_is_compared_with_that_amount(offer, portal):
    """REQ-103: el pliego puede fijar un monto en lugar de un porcentaje."""
    portal_data(portal, offer, amount="21750.00")
    exact = pair_of("Constituir una garantía de oferta por $ 21.750,00.",
                    combine.Combined(outcome="sin_documento"))
    assert rules.apply(exact, SimpleNamespace(offer=offer)) == "portal_cumple"
    other = pair_of("Constituir una garantía de oferta por $ 30.000,00.",
                    combine.Combined(outcome="sin_documento"))
    assert rules.apply(other, SimpleNamespace(offer=offer)) == "portal_no_cumple"


@pytest.mark.parametrize("word", ["cinco por ciento", "5%", "5 %", "cinco (5) por ciento",
                                  "5,0 por ciento"])
def test_the_percentage_is_read_in_words_and_figures(word):
    """REQ-103: el porcentaje que fija el requisito se lee de «cinco por ciento», «5 %»…"""
    assert portal_facts.required_percent(f"garantía de oferta del {word} del monto") == 5


def test_two_different_percentages_are_not_read():
    """REQ-103: con dos porcentajes distintos no se supone ninguno."""
    assert portal_facts.required_percent("el 5 % o el 10 % del monto") is None


def line_quotes(offer, procedure, portal, numbers=(1, 2, 3), quoted=(1, 2, 3)):
    """Renglones del procedimiento y los que el Portal tiene cotizados para la oferta."""
    portal_data(portal, offer)
    for number in numbers:
        line = pm.PortalLine.objects.create(procedure=procedure, number=number,
                                            description="x", item=portal)
        if number in quoted:
            pm.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("100.0000"),
                                          quantity=Decimal("10.0000"))


@pytest.mark.decision_literal
def test_the_per_line_quote_with_every_line_quoted_proposes_cumple(offer, procedure, portal):
    """REQ-103, ADR-0053: todos los renglones del procedimiento tienen precio en el Portal:
    «cumple» con una cita del Portal por renglón."""
    line_quotes(offer, procedure, portal)
    pair = pair_of(PER_LINE_REQ, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple"
    assert [c["kind"] for c in pair.combined.portal] == ["cotizacion"] * 3


@pytest.mark.decision_literal
def test_the_per_line_quote_with_missing_lines_proposes_no_cumple_with_the_difference(
        offer, procedure, portal):
    """REQ-103, ADR-0053: faltan los precios de algunos renglones: «no cumple» y dice cuáles."""
    line_quotes(offer, procedure, portal, quoted=(1,))
    pair = pair_of(PER_LINE_REQ, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_no_cumple"
    assert pair.combined.outcome == "no_cumple"
    assert "2, 3" in pair.combined.explanation
    assert pair.combined.facts["comparacion"]["diferencia"] == "2, 3"


@pytest.mark.decision_literal
@pytest.mark.parametrize("cuit, regla, outcome", [
    ("30-00000000-0", "portal_cumple", "cumple"),
    ("30-0000000", "portal_no_cumple", "no_cumple"),   # le faltan dígitos
])
def test_the_cuit_needs_eleven_digits(offer, portal, cuit, regla, outcome):
    """REQ-103, ADR-0053: el CUIT del Portal cumple con los once dígitos; con menos no cumple."""
    portal_data(portal, offer, cuit=cuit)
    pair = pair_of("Informar el CUIT del oferente.", combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == regla
    assert pair.combined.outcome == outcome and pair.combined.portal[0]["kind"] == "cuit"


@pytest.mark.parametrize("text, currency, regla", [
    ("Indicar el precio total de la oferta.", "ARS", "portal_cumple"),
    ("Indicar el precio total de la oferta en pesos.", "ARS", "portal_cumple"),
    ("Indicar el precio total de la oferta en pesos.", "USD", "portal_no_cumple"),
    ("Indicar el precio total de la oferta en dólares.", "USD", "portal_cumple"),
    ("Indicar el precio total de la oferta en pesos.", "", "portal_falta_coincidencia"),
])
def test_the_total_is_loaded_and_has_the_currency_the_requirement_fixes(
        offer, portal, text, currency, regla):
    """REQ-103, ADR-0053: el total cargado cumple; si el requisito fija la moneda, tiene que
    coincidir; sin moneda legible en el Portal no se compara."""
    portal_data(portal, offer, total="90000.00")
    pm.PortalOfferData.objects.filter(offer=offer).update(currency=currency)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == regla


# --- Texto de la oferta y Portal juntos ---------------------------------------------------------


def test_an_offer_that_says_no_cumple_against_a_portal_that_coincides_is_a_lack_of_coincidence(
        offer, portal):
    """REQ-103, ADR-0053 (regla 4): si el Portal coincide con el pliego y el texto de la oferta
    concluyó «no cumple», las fuentes se contradicen: nunca se pisa con «cumple»."""
    portal_data(portal, offer)
    pair = pair_of(GUARANTEE_REQ, combine.Combined(
        outcome="no_cumple", citations=[located("la garantía no se acompaña")]))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert pair.combined.outcome == "no_determinado"
    assert pair.combined.citations and pair.combined.portal


def test_an_offer_that_says_cumple_against_a_portal_that_differs_is_a_lack_of_coincidence(
        offer, portal):
    """REQ-103: el Portal difiere del pliego y la oferta concluyó «cumple» con otro texto: la
    Comisión verifica cuál rige; ningún «cumple» con un dato que no coincide."""
    portal_data(portal, offer, amount="20000.00")
    pair = pair_of(GUARANTEE_REQ, combine.Combined(
        outcome="cumple", citations=[located("garantiza hasta $ 21.750")]))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert pair.combined.outcome == "no_determinado"


def test_a_portal_citation_the_model_already_brought_is_not_repeated(offer, portal):
    """REQ-103: la cita del Portal que el modelo ya trajo con su alias no se duplica."""
    portal_data(portal, offer)
    guarantee = portal_facts.read(offer, "garantia", GUARANTEE_REQ, [])[0]
    pair = pair_of(GUARANTEE_REQ, combine.Combined(outcome="cumple",
                                                   portal=[guarantee.citation()]))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert len(pair.combined.portal) == 1


# --- Catálogo, valores e instrucción ------------------------------------------------------------


@pytest.mark.parametrize("text, kind", [
    ("Constituir una garantía de mantenimiento de la oferta del cinco por ciento.", "garantia"),
    ("Acompañar la garantía de oferta.", "garantia"),
    ("Informar el CUIT del oferente.", "cuit"),
    ("Indicar el precio total de la oferta.", "total"),
])
def test_the_catalog_recognizes_what_the_portal_has(text, kind):
    """REQ-062: el catálogo reconoce los requisitos que piden un dato del Portal."""
    assert portal_facts.kind_of(text) == kind


@pytest.mark.parametrize("text", [
    "El plazo de entrega será de diez días corridos.", "Presentar la declaración jurada.", ""])
def test_the_catalog_does_not_mark_the_rest(text):
    """REQ-062: un requisito que no pide un dato del Portal no entra al catálogo."""
    assert portal_facts.kind_of(text) is None


def test_a_quote_requirement_needs_a_line():
    """REQ-062: sin renglón, «cotizar» no es una cotización por renglón."""
    assert portal_facts.kind_of("Cotizar en pesos.", SimpleNamespace(items=[])) is None
    assert portal_facts.kind_of("Cotizar el renglón.", SimpleNamespace(items=[1])) == "cotizacion"


@pytest.mark.parametrize("text, expected", [
    ("hasta la suma de $ 21.750, el", [Decimal("21750")]),
    ("Total: $ 80.000,50.", [Decimal("80000.50")]),
    ("el 5 % del monto, vence el 15/10/2026", []),
    ("$ 3000 más $ 1.500,00", [Decimal("3000"), Decimal("1500.00")]),
])
def test_the_amounts_are_read_with_argentine_format(text, expected):
    """REQ-062: el monto se lee por regla: punto de miles, coma decimal; un número suelto no
    es un monto."""
    assert portal_facts.amounts(text) == expected


def test_the_cuits_are_read_with_or_without_dashes():
    """REQ-062: el CUIT se lee con o sin guiones."""
    assert portal_facts.cuits("CUIT 30-00000000-0 y 20111111111") == [
        "30000000000", "20111111111"]


def test_the_instruction_v5_asks_for_data_and_the_schema_allows_it():
    """REQ-062: la versión nueva de la instrucción trae `datos`."""
    assert "datos" in prompting.evaluation_schema(["D1"], [])["properties"]
    assert '"datos"' in prompting.load_prompt("evaluacion")
    content = ('{"resultado": "cumple", "exigencia": "documento", "citas": [], "fundamentos": [],'
               ' "explicacion": "x", "externo": false, "pregunta": "",'
               ' "datos": [{"documento": "D1", "texto": "$ 5"}]}')
    assert prompting.parse_evaluation(content, ["D1"], []).data == [("D1", "$ 5")]
    with pytest.raises(prompting.InvalidOutput):
        prompting.parse_evaluation(content.replace('"datos": [{', '"datos": [5, {'), ["D1"], [])
