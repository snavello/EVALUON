"""T-257 (frente evaluación de la ronda del comité, spec 015): lo que la mesa de comité del 2026-10-12
encontró en la evaluación y los criterios que el responsable decidió ese día. Un bloque por punto
del encargo. Textos y datos inventados (P4); sin red ni modelo (la prueba con el modelo es la de la
GPU, en `verificacion/`).

1. «No aplica (opción no usada)» para la condición de una opción que la oferta no usa (REQ-103,
   REQ-105) y la regla de respaldo de la instrucción `evaluacion-v11`.
2. La regla de la forma de garantía corre antes que la de externos (REQ-103).
3. La regla del Portal conserva las condiciones y la pregunta, compara la cantidad y no da «cumple»
   con datos que el Portal no trae (REQ-103, REQ-104, REQ-105).
4. El contraste recibe el bloque del Portal completo de la oferta (REQ-104).
5. Las circulares que aclaran llegan a la evaluación con su texto (REQ-104).
6. Los criterios del 2026-10-12: IVA del Portal, cumple por ausencia, prórroga en la fila del plazo
   y presentación física (REQ-103, REQ-104, REQ-105).
7. La declaración aceptada en el Portal y la constancia del Registro (REQ-104): instrucción.
"""

import datetime
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.conf import settings

from evaluon.assessment import combine, grounds, not_applicable, prompting, rules
from evaluon.assessment.services import evaluate
from evaluon.journey.temas import s4_propuesta
from evaluon.portal import models as pm
from tests.assessment.test_ajuste_t240 import chosen_form
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import located, portal_data

pytestmark = pytest.mark.django_db

TITLES = ["Nota de presentación", "Planilla de cotización"]


def condition(text, result, datum="", model=None):
    return {"condicion": text, "dato": datum, "resultado": result,
            "resultado_modelo": model or result, "cita": None}


def pair_with(text, combined, records=(), *, opcion="", items=(), group_result=None):
    """Un par como el de `evaluate.py`: el resultado unido, un grupo con sus condiciones ya
    controladas y el requisito con la opción que nombró la matriz."""
    group = SimpleNamespace(index=0, result=group_result or "no_consta",
                            citations=list(combined.citations), portal=list(combined.portal),
                            unreadable=None, external=False)
    return SimpleNamespace(
        combined=combined, text=SimpleNamespace(text=text), datos=[],
        requirement=SimpleNamespace(items=list(items), category="formal", number=7,
                                    proposed={"opcion": opcion} if opcion else {}),
        groups=[group], conditions={0: [dict(r) for r in records]})


def ctx_of(offer):
    documents = [SimpleNamespace(document=SimpleNamespace(title=t)) for t in TITLES]
    return SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=documents))


def apply(offer, pair):
    return rules.apply(pair, ctx_of(offer)), pair.combined


# --- 1. «No aplica (opción no usada)» -----------------------------------------------------------

OPTION = ("Si el oferente se presenta como cooperativa de trabajo, acompañará la constancia de su "
          "matrícula en el registro de cooperativas.")


@pytest.mark.parametrize("combined", [
    # el modelo no encontró nada: «no se encontró el documento» antes de T-257
    combine.Combined(outcome="sin_documento", exigence="documento"),
    # el modelo lo marcó externo sin citar nada (antes: «falta la hoja de compliance»)
    combine.Combined(outcome="no_determinado", doubt="externo"),
    # el modelo no lo pudo determinar
    combine.Combined(outcome="no_determinado", doubt="sin_dato", question="¿Aplica?"),
])
def test_the_condition_of_an_option_the_offer_does_not_use_does_not_apply(offer, combined):
    """REQ-103, REQ-105 (H-C2-1, A-1): la fila que la matriz ata a una opción (`opcion`) y que ni
    los documentos ni el Portal muestran que la oferta use no aplica: «No aplica (opción no usada)»,
    sin pregunta, con la opción y los documentos leídos en la explicación; nunca «no se encontró el
    documento» ni un pedido de hoja de compliance."""
    pair = pair_with(OPTION, combined, [condition("Acompañar la constancia", "no_consta")],
                     opcion="mipyme")
    name, result = apply(offer, pair)
    assert name == "opcion_no_usada"
    assert result.facts["aplica"] is False and result.facts["opcion"] == "mipyme"
    assert result.facts["version_reglas"] == settings.ASSESSMENT_RULES_VERSION == "reglas-v12"
    assert result.question == "" and not result.ask and result.citations == []
    assert "MiPyME" in result.explanation and "Nota de presentación" in result.explanation
    assert not_applicable.result_label(result) == "No aplica (opción no usada)"
    assert not_applicable.outcome_key(result) == "no_aplica"


def test_the_option_the_offer_shows_it_uses_is_evaluated_as_always(offer):
    """REQ-103: si la oferta muestra que usa la opción (el modelo ubicó un texto), la fila se evalúa
    como cualquier otra: la regla no decide."""
    combined = combine.Combined(outcome="cumple", citations=[located("Matrícula N° 12.")])
    pair = pair_with(OPTION, combined, [condition("Acompañar la constancia", "cumple")],
                     opcion="mipyme", group_result="cumple")
    name, result = apply(offer, pair)
    assert name != "opcion_no_usada" and result.outcome == "cumple"
    assert "aplica" not in result.facts


def test_a_partial_quote_in_the_portal_shows_the_partial_quote_option(offer, procedure, portal):
    """REQ-103: para la cotización parcial, el Portal muestra si la oferta la usa: si cotizó menos
    que lo pedido en un renglón, la usa y la fila se evalúa; si cotizó todo, no aplica."""
    portal_data(portal, offer)
    line = pm.PortalLine.objects.create(procedure=procedure, number=1, description="x",
                                        quantity=Decimal("10"), item=portal)
    quote = pm.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("5"),
                                          quantity=Decimal("4"))
    text = "Quienes coticen una parte del renglón indicarán el plazo de entrega de esa parte."
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, _ = apply(offer, pair_with(text, combined, opcion="cotizacion_parcial"))
    assert name != "opcion_no_usada"
    quote.quantity = Decimal("10")
    quote.save()
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(text, combined, opcion="cotizacion_parcial"))
    assert name == "opcion_no_usada" and not_applicable.is_not_applicable(result)


def test_without_the_option_name_or_with_unread_pages_the_rule_says_nothing(offer):
    """REQ-103: sin `opcion` (una matriz validada antes de T-258) la regla no rige y queda la
    instrucción; con partes de la oferta sin leer no se afirma que no la usa."""
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    name, _ = apply(offer, pair_with(OPTION, combined))
    assert name != "opcion_no_usada"
    combined = combine.Combined(outcome="no_determinado", doubt="lectura_incompleta",
                                unread_warning=True)
    name, _ = apply(offer, pair_with(OPTION, combined, opcion="mipyme"))
    assert name != "opcion_no_usada"


def test_the_guarantee_form_keeps_its_own_label():
    """REQ-103: la forma de garantía no elegida sigue con su texto; cada regla, el suyo."""
    guarantee = SimpleNamespace(outcome="cumple", facts={"aplica": False,
                                                         "regla": "forma_garantia_no_elegida"})
    assert not_applicable.result_label(guarantee) == "No aplica (forma de garantía no elegida)"


def test_the_instruction_v11_resolves_the_option_without_saying_the_document_is_missing():
    """REQ-104, REQ-105 (H2 de las instrucciones): sin `opcion`, la instrucción vigente dice que la
    condición de una opción que la oferta no muestra usar nunca es «no_consta» (que el sistema
    escribe «no se encontró el documento») y que lo que solo se permite («podrá…») no es una
    condición; con frases genéricas (no las del caso) y un ejemplo de otro rubro."""
    assert settings.ASSESSMENT_PROMPT_VERSIONS["evaluacion"] == "evaluacion-v11"
    text = prompting.load_prompt("evaluacion")
    rule = text[text.index("- Condición de una opción"):]
    rule = rule[:rule.index("\n")]
    assert 'nunca es "no_consta" ni "no_cumple"' in rule
    assert "revestir la condición" not in text and "MiPyME" not in text
    assert 'Lo que la oración solo permite ("podrá…"' in text
    assert "Nunca es \"no_consta\" la condición de una opción" in text
    examples = [json.loads(line) for line in text[text.index("EJEMPLOS"):].splitlines()
                if line.startswith("{")]
    option = [e for e in examples if "cooperativa" in e["razonamiento"]]
    assert option and option[0]["resultado"] == "no_determinado" and option[0]["pregunta"]
    allowed = [e for e in examples if "solo se permite" in e["razonamiento"]]
    assert allowed and len(allowed[0]["condiciones"]) == 1


# --- 2. La forma de garantía antes que los externos ----------------------------------------------

POLICY_SSN = ("En caso de tratarse de una póliza de seguro de caución, deberá ajustarse a la "
              "Resolución N° 219/2018 de la Superintendencia de Seguros de la Nación.")
NOT_ELECTRONIC_DOC = ("En el caso de optar por garantías no electrónicas, el original de la "
                      "garantía deberá entregarse en la oficina de recepción.")


def test_the_guarantee_form_rule_goes_before_the_externals():
    """REQ-103 (H-C2-1): la regla de la forma de garantía corre antes que la de externos."""
    names = [rule.__module__.rsplit(".", 1)[-1] for rule in rules.RULES]
    assert names.index("guarantee_form") < names.index("externals")


@pytest.mark.decision_literal
def test_a_policy_requirement_the_catalog_marks_external_does_not_apply_to_a_pagare(offer, portal):
    """REQ-103, «Requisito de la forma elegida» (O1 R33): un requisito de la póliza que el catálogo
    marca externo (la Superintendencia) no aplica a la oferta que eligió pagaré: antes salía
    «falta la hoja de compliance»."""
    chosen_form(portal, offer, "Pagare")
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(POLICY_SSN, combined))
    assert name == "forma_garantia_no_elegida" and result.doubt != "externo"
    assert not_applicable.is_not_applicable(result)


@pytest.mark.decision_literal
def test_a_requirement_the_model_marked_external_does_not_apply_to_another_form(offer, portal):
    """REQ-103 (O2 R41): el original de una garantía no electrónica, que el modelo marcó externo,
    no aplica a la oferta con póliza."""
    chosen_form(portal, offer, "Seguros")
    combined = combine.Combined(outcome="no_determinado", doubt="externo")
    pair = pair_with(NOT_ELECTRONIC_DOC, combined)
    pair.external_flagged = True
    name, result = apply(offer, pair)
    assert name == "forma_garantia_no_elegida" and not_applicable.is_not_applicable(result)


# --- 3. La regla del Portal ----------------------------------------------------------------------


def quoted(procedure, offer, portal, *, asked="10", offered="10", numbers=(1, 2)):
    portal_data(portal, offer)
    for number in numbers:
        line = pm.PortalLine.objects.create(procedure=procedure, number=number, description="x",
                                            quantity=Decimal(asked), item=portal)
        pm.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("100.0000"),
                                      quantity=Decimal(offered))


def test_the_portal_rule_keeps_the_model_conditions_and_question(offer, procedure, portal):
    """REQ-104, REQ-105 (H-C2-6, A-2): el dato del Portal resuelve solo la condición que cubre; la
    que queda sin dato sigue a la vista, con la pregunta, y la celda no es «cumple» ni «falta de
    coincidencia» (antes: «cumple» o «falta coincidencia» sin condiciones ni pregunta)."""
    quoted(procedure, offer, portal)
    text = "Cotizar el valor unitario de cada renglón e indicar la marca de cada producto."
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato",
                                question="¿La Comisión da por cumplida la condición de la marca?")
    records = [condition("Cotizar el valor unitario de cada renglón", "no_consta"),
               condition("Indicar la marca de cada producto", "no_consta")]
    name, result = apply(offer, pair_with(text, combined, records))
    assert name == "portal_cubre_parte"
    assert (result.outcome, result.doubt) == ("no_determinado", "sin_dato")
    shown = result.facts["condiciones"]
    assert shown[0]["resultado"] == "cumple" and shown[0]["cubierta_por"] == "portal"
    assert shown[1]["resultado"] == "no_consta" and "cubierta_por" not in shown[1]
    assert "marca" in result.question and result.ask
    assert "Falta coincidencia" not in result.explanation and result.portal


def test_the_portal_does_not_give_cumple_with_data_it_does_not_have(offer, portal):
    """REQ-103 (R123): el pliego pide consignar el número y la compañía de la garantía y el Portal
    solo trae tipo, forma y monto: nunca «cumple»; quedan las condiciones y la pregunta del
    modelo."""
    portal_data(portal, offer)
    text = ("El oferente consignará en el Portal, en el paso de ingreso de la garantía, el número "
            "del documento y la compañía emisora.")
    records = [condition("Consignar el número del documento", "no_determinado"),
               condition("Consignar la compañía emisora", "no_determinado")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato",
                                question="¿La Comisión verifica el número y la compañía?")
    name, result = apply(offer, pair_with(text, combined, records))
    assert result.outcome != "cumple" and name != "portal_cumple"
    assert result.question == "¿La Comisión verifica el número y la compañía?"
    assert len(result.facts["condiciones"]) == 2
    # sin condiciones del modelo, tampoco «cumple»
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento")))
    assert result.outcome != "cumple"


QUANTITY = "Se cotizará el precio de cada renglón por la cantidad total pedida."


@pytest.mark.decision_literal
def test_the_portal_rule_compares_the_quantity_offered_with_the_one_asked(offer, procedure,
                                                                           portal):
    """REQ-103 (R87, H6 de las omisiones): con un requisito que pide la cantidad, una cotización por
    menos que lo pedido no es «cumple» (antes: «cumple» por tener precio): «no determinado» con la
    diferencia a la vista."""
    quoted(procedure, offer, portal, asked="10", offered="6")
    name, result = apply(offer, pair_with(QUANTITY, combine.Combined(outcome="sin_documento")))
    assert result.outcome == "no_determinado" and result.doubt == "falta_coincidencia"
    assert "6 de 10" in result.explanation
    assert result.facts["comparacion"]["estado"] == "cantidad_parcial"


def test_the_whole_quantity_offered_is_cumple_and_says_so(offer, procedure, portal):
    """REQ-103: por la cantidad pedida, «cumple» citando el Portal y la explicación dice la
    cantidad (lo decisivo), no solo el precio."""
    quoted(procedure, offer, portal, asked="10", offered="10")
    name, result = apply(offer, pair_with(QUANTITY, combine.Combined(outcome="sin_documento")))
    assert name == "portal_cumple" and result.outcome == "cumple"
    assert "cantidad pedida" in result.explanation and "10 de 10" in result.explanation


# --- 4. El contraste con el bloque del Portal completo -------------------------------------------


def test_the_contrast_sees_the_whole_portal_block_of_the_offer(offer, portal, monkeypatch):
    """REQ-104 (H9): el contraste recibe todos los datos del Portal de la oferta, no solo lo que la
    evaluación citó: con el total puede comprobar el porcentaje de la garantía."""
    portal_data(portal, offer, total="435000.00", amount="21750.00")
    captured = {}

    def fake_generate(messages, schema, step, ctx, max_tokens=None, reasoning_step=None):
        captured["messages"] = messages
        return SimpleNamespace(content='{"razonamiento": "Alcanza.", "respuesta": "si"}')

    monkeypatch.setattr(evaluate, "_generate", fake_generate)
    ctx = evaluate.Context(offer, None, {}, lambda: 0.0)
    guarantee = ("Garantía: tipo Garantía de mantenimiento de oferta, forma Póliza de caución, "
                 "monto 21750.00")
    combined = combine.Combined(outcome="cumple", portal=[
        {"item": portal.pk, "kind": "garantia", "text": guarantee, "label": "x"}])
    pair = evaluate.PairData(
        requirement=SimpleNamespace(number=29, category="formal"),
        text=SimpleNamespace(render=lambda: "Requisito: garantía del 5 % del total cotizado."),
        combined=combined)
    evaluate._contrast_pair(ctx, pair)
    user = captured["messages"][1]["content"]
    assert "Total de la oferta: 435000.00 ARS" in user
    assert user.count(guarantee) == 1
    assert ctx.steps[-1].parsed["portal_oferta"] == ["Total de la oferta: 435000.00 ARS"]


# --- 5. Las circulares que aclaran ---------------------------------------------------------------


def test_a_clarifying_circular_reaches_the_evaluation_with_its_text():
    """REQ-104 (H8 de las omisiones): lo que una circular aclara o precisa llega al pedido con su
    fecha y su texto, junto a la cita (antes solo llegaban las que modifican o suprimen)."""
    quote = SimpleNamespace(pk=1, text="El original se entregará en la oficina de recepción.",
                            scope="", segment=None, char_start=0)
    requirement = SimpleNamespace(items=[], category="formal", number=41)
    clarifies = SimpleNamespace(quote_id=1, effect="aclara", issued_on=datetime.date(2026, 3, 5),
                                text="Resulta suficiente la carga electrónica del documento.")
    general = SimpleNamespace(quote_id=None, effect="aclara", issued_on=datetime.date(2026, 3, 6),
                              text="Las aclaraciones forman parte del pliego.")
    text = grounds.requirement_text(requirement, quotes=[quote], sources=[clarifies, general])
    block = text.render()
    assert "05/03/2026" in block and "Resulta suficiente la carga electrónica" in block
    assert "Las aclaraciones forman parte del pliego." in block
    # el texto vigente no cambia: la aclaración no es una modificación
    assert text.quotes[0].text == quote.text and not text.quotes[0].original


# --- 6a. IVA: el precio del Portal es final con IVA ----------------------------------------------

VAT = "Las cotizaciones se expresarán en pesos argentinos e incluirán el IVA."


@pytest.mark.decision_literal
def test_the_portal_price_is_taken_as_final_with_vat(offer, portal):
    """REQ-103, decisión del 2026-10-12 «Precio del Portal = final con IVA» (R10, R47): con el
    total en pesos en el Portal y la oferta sin decir lo contrario, «cumple» citando el Portal y el
    criterio, registrado con su versión (antes: «no determinado», «el Portal no informa el
    impuesto»)."""
    portal_data(portal, offer)
    records = [condition("Cotizar en pesos argentinos", "cumple", "ARS"),
               condition("Incluir el IVA", "no_consta")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato", question="¿IVA?")
    name, result = apply(offer, pair_with(VAT, combined, records))
    assert name == "portal_cumple" and result.outcome == "cumple" and result.portal
    assert "precio final con IVA incluido" in result.explanation
    criterion = result.facts["criterios"][0]
    assert criterion["nombre"] == "iva_precio_final_portal"
    assert criterion["version_reglas"] == "reglas-v12" and "2026-10-12" in criterion["decision"]
    assert result.facts["condiciones"][1]["cubierta_por"] == "iva_precio_final_portal"


@pytest.mark.decision_literal
def test_the_vat_criterion_does_not_apply_if_the_offer_says_otherwise(offer, portal):
    """REQ-103, «salvo que la oferta diga lo contrario»: si un documento dice que el precio no
    incluye el impuesto, nunca «cumple»."""
    portal_data(portal, offer)
    records = [condition("Cotizar en pesos argentinos", "cumple", "ARS"),
               condition("Incluir el IVA", "no_cumple", "precios sin IVA")]
    combined = combine.Combined(outcome="no_cumple", citations=[located("Precios sin IVA.")])
    name, result = apply(offer, pair_with(VAT, combined, records, group_result="no_cumple"))
    assert result.outcome != "cumple"


# --- 6b y 6c. Cumple por ausencia, con la prórroga en la fila del plazo ----------------------------

NEGATIVE = "No se aceptarán ofertas condicionadas a la variación del tipo de cambio."
TERM = ("Los oferentes deberán mantener su oferta por noventa días corridos desde la apertura. La "
        "oferta se considerará prorrogada automáticamente por un lapso igual.")


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, combined", [
    (NEGATIVE, combine.Combined(outcome="no_determinado", doubt="sin_dato", question="¿?")),
    # el modelo propuso «cumple» con una aceptación general y el contraste no lo corroboró
    (NEGATIVE, combine.Combined(outcome="no_determinado", doubt="sin_corroborar",
                                proposed="cumple", citations=[located("Acepto el pliego.")])),
    (TERM, combine.Combined(outcome="no_determinado", doubt="sin_dato")),
    (TERM, combine.Combined(outcome="sin_documento", exigence="condicion")),
])
def test_a_negative_or_suppletory_requirement_nothing_contradicts_is_met_by_absence(
        offer, text, combined):
    """REQ-104, decisiones del 2026-10-12 «Cumple por ausencia, con fundamento» y «En la misma
    fila del plazo» (R54, R62; constitución 1.4): «cumple» nombrando los documentos leídos y
    diciendo que ninguno lo contradice, sin citas de la oferta, con el criterio registrado (antes:
    «no determinado» o «no se encontró el documento»)."""
    records = [condition("La oferta no está condicionada / se mantiene la oferta", "no_consta")]
    records[0]["condicion"] = ("La oferta no está condicionada a la variación del tipo de cambio"
                               if text == NEGATIVE else
                               "Mantener la oferta por noventa días con su prórroga automática")
    name, result = apply(offer, pair_with(text, combined, records))
    assert name == "cumple_por_ausencia" and result.outcome == "cumple"
    assert "ninguno lo contradice" in result.explanation
    assert all(t in result.explanation for t in TITLES)
    assert result.citations == [] and result.question == ""
    criterion = result.facts["criterios"][0]
    assert criterion["nombre"] == "ausencia_verificada" and criterion["documentos_leidos"] == TITLES
    assert criterion["version_reglas"] == "reglas-v12" and "2026-10-12" in criterion["decision"]
    assert result.facts["condiciones"][0]["por_ausencia"] is True


@pytest.mark.decision_literal
def test_what_contradicts_it_stays_no_cumple_with_its_citation(offer):
    """REQ-104, «si alguno lo contradice, no cumple con la cita»: la oferta limita el plazo o se
    condiciona: queda el «no cumple» del modelo, con su cita."""
    cite = located("La oferta se mantiene por treinta días, sin prórroga.")
    combined = combine.Combined(outcome="no_cumple", citations=[cite])
    records = [condition("Mantener la oferta por noventa días", "no_cumple", "treinta días")]
    name, result = apply(offer, pair_with(TERM, combined, records, group_result="no_cumple"))
    assert name != "cumple_por_ausencia" and result.outcome == "no_cumple"
    assert result.citations == [cite]


def test_absence_needs_a_complete_reading_and_only_absence_conditions(offer):
    """REQ-104, P3: la ausencia se verifica en la lectura completa; una fila que además pide un dato
    (el valor unitario) no se resuelve por ausencia."""
    combined = combine.Combined(outcome="no_determinado", doubt="lectura_incompleta",
                                unread_warning=True)
    records = [condition("La oferta no está condicionada", "no_consta")]
    name, _ = apply(offer, pair_with(NEGATIVE, combined, records))
    assert name != "cumple_por_ausencia"
    text = "Los precios serán fijos e inamovibles y se indicará el valor unitario de cada ítem."
    records = [condition("Los precios son fijos e inamovibles", "no_consta"),
               condition("Indicar el valor unitario de cada ítem", "no_consta")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, _ = apply(offer, pair_with(text, combined, records))
    assert name != "cumple_por_ausencia"


def test_a_fixed_price_condition_is_covered_by_absence_with_the_portal(offer, procedure, portal):
    """REQ-103, REQ-104 (R47): el valor unitario lo da el Portal, el impuesto el criterio del IVA y
    «fijos e inamovibles» la ausencia: «cumple» con los dos criterios registrados."""
    quoted(procedure, offer, portal)
    text = ("Cotizar el valor unitario de cada renglón; los precios serán fijos e inamovibles e "
            "incluirán los impuestos.")
    records = [condition("Cotizar el valor unitario de cada renglón", "cumple", "100.0000"),
               condition("Los precios son fijos e inamovibles", "no_consta"),
               condition("Los precios incluyen los impuestos", "no_consta")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(text, combined, records))
    assert name == "portal_cumple" and result.outcome == "cumple"
    used = [c["nombre"] for c in result.facts["criterios"]]
    assert used == ["iva_precio_final_portal", "ausencia_verificada"]
    assert "ninguno lo contradice" in result.explanation


@pytest.mark.parametrize("text, expected", [
    ("No se aceptarán ofertas condicionadas a la variación del tipo de cambio.", True),
    ("La oferta se considerará prorrogada automáticamente por un lapso igual al inicial.", True),
    ("Los precios serán fijos e inamovibles.", True),
    # no son ausencia: un tope, la garantía y la doble negación que pide presentar algo
    ("El pagaré no podrá superar los cien módulos.", False),
    ("Constituir la garantía de mantenimiento de la oferta del cinco por ciento.", False),
    ("No se considerarán las ofertas que no incluyan la declaración jurada firmada.", False),
])
def test_what_is_negative_or_suppletory(text, expected):
    """REQ-104 (decisión del 2026-10-12): qué requisito se cumple por ausencia y cuál no (un
    catálogo corto sobre el texto, versionado con las reglas)."""
    from evaluon.assessment import criteria

    assert criteria.by_absence(text) is expected


# --- 6d. La presentación física ---------------------------------------------------------------

PHYSICAL = ("Cuando se opte por garantías no electrónicas, el original de la garantía deberá ser "
            "presentado en la Mesa de Entrada del organismo.")
MARKED = ("La documentación se adjuntará en el Portal y, en caso de que el sistema indique "
          "\"Requiere presentar en Mesa de Entrada\", deberá también presentarse físicamente.")


@pytest.mark.decision_literal
def test_a_physical_presentation_that_does_not_appear_is_no_cumple(offer, portal):
    """REQ-104, REQ-105, decisión del 2026-10-12 sobre la presentación física (O1 R41): lo que hay
    que presentar en la Mesa de Entrada y no consta entre los documentos ni en la hoja de
    compliance es «no cumple», con el texto que avisa que puede faltar cargarlo."""
    chosen_form(portal, offer, "Pagare")
    combined = combine.Combined(outcome="no_determinado", doubt="externo")
    name, result = apply(offer, pair_with(PHYSICAL, combined))
    assert name == "presentacion_fisica_no_consta" and result.outcome == "no_cumple"
    assert "Puede faltar cargarlo" in result.explanation
    assert "Nota de presentación" in result.explanation
    assert result.facts["hoja_compliance"] is False


def test_the_physical_presentation_of_another_form_or_shown_is_not_no_cumple(offer, portal):
    """REQ-103, REQ-104: con póliza el original no aplica (forma no elegida); si el modelo ubicó la
    constancia de la presentación, sigue el flujo de siempre."""
    chosen_form(portal, offer, "Seguros")
    name, result = apply(offer, pair_with(PHYSICAL, combine.Combined(outcome="sin_documento")))
    assert name == "forma_garantia_no_elegida"
    pm.PortalOfferData.objects.filter(offer=offer).delete()
    chosen_form(portal, offer, "Pagare")
    cite = located("Recibido en Mesa de Entrada el 3 de marzo.")
    combined = combine.Combined(outcome="cumple", citations=[cite])
    name, result = apply(offer, pair_with(PHYSICAL, combined, group_result="cumple"))
    assert name != "presentacion_fisica_no_consta" and result.outcome == "cumple"


def test_a_presentation_tied_to_the_portal_mark_asks_the_commission(offer):
    """REQ-105: si la presentación depende de la marca «Requiere presentar» del Portal, que el
    sistema no importa, «no determinado» con la pregunta a la Comisión y el aviso (nunca «no se
    encontró el documento»)."""
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    name, result = apply(offer, pair_with(MARKED, combined))
    assert name == "presentacion_fisica_sin_marca"
    assert result.outcome == "no_determinado" and "Requiere presentar" in result.question
    assert not combine.addresses_offeror(result.question)
    assert "puede faltar cargarlo" in result.explanation


# --- 7. La declaración aceptada en el Portal y la constancia del Registro --------------------------


def test_the_instruction_uses_the_declaration_accepted_in_the_portal_and_the_registry():
    """REQ-104 (O3 R22, O3 R20): la instrucción dice que la declaración que el oferente aceptó en el
    Portal (según el comprobante) es la cita de esa declaración, y que la constancia de un registro
    que trae la oferta o que cargó la Comisión se usa como documento de la oferta, no como
    externo."""
    text = prompting.load_prompt("evaluacion")
    rule = text[text.index("- Declaraciones aceptadas en el Portal"):]
    rule = rule[:rule.index("\n")]
    assert "aceptó en el Portal la declaración jurada" in rule
    assert "que cargó la Comisión" in rule and "no es externo" in rule


def test_the_cell_says_what_resolved_each_condition():
    """REQ-104 (H-C2-8): en la celda, la condición que resolvió el sistema dice con qué: el dato del
    Portal, el criterio del IVA o la ausencia."""
    facts = {"condiciones": [
        {"condicion": "Cotizar el valor unitario", "dato": "", "resultado": "cumple",
         "cubierta_por": "portal", "cita": None},
        {"condicion": "Incluir el IVA", "dato": "", "resultado": "cumple",
         "cubierta_por": "iva_precio_final_portal", "cita": None},
        {"condicion": "La oferta no está condicionada", "dato": "", "resultado": "cumple",
         "por_ausencia": True, "cita": None}]}
    where = [v["where"] for v in s4_propuesta.condition_views(facts)]
    assert where[0] == "dato del Portal de Compras"
    assert "con IVA" in where[1] and "ausencia" in where[2]


def test_the_instruction_v11_keeps_the_cases_and_does_not_copy_the_case_scenario():
    """REQ-104, REQ-106 (T-240, D-240-3 y O-240-2, con los criterios del 2026-10-12): la v11 sigue
    diciendo qué hacer con el requisito de referencia, el negativo, el mantenimiento con su prórroga,
    la forma de garantía no elegida, la opción y la coherencia; el negativo y el mantenimiento sin
    nada en contra van «no_consta» para que el sistema los proponga por ausencia; el impuesto lo
    resuelve el criterio del Portal; y no trae el escenario «pesos e IVA» del caso que se mide."""
    body = prompting.load_prompt("evaluacion")
    for phrase in ("Requisito de referencia", "Requisito negativo",
                   "Mantenimiento de la oferta y su prórroga", "limita o rechaza la prórroga",
                   "Forma de garantía que la oferta no eligió", "Condición de una opción",
                   "Impuesto incluido en el precio", "Coherencia",
                   "si todas cumplen, la pregunta va vacía"):
        assert phrase in body, phrase
    assert body.count("ningún documento lo contradice") >= 2
    assert "el sistema lo propone por ausencia" in body
    assert "IVA" not in body and "pesos" not in body
    assert "solo con su propio dato (no vacío) y su propia cita" in body
