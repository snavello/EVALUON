"""T-257, reverificación (`verificacion/T-257.md`, 482b886): los 22 contraejemplos nuevos (N1 a N7),
con la decisión estricta del Coordinador: menos «cumple» automáticos, pero ninguno sin fundamento
(P3). Y los positivos que tienen que seguir dando «cumple»: el requisito negativo y el plazo de
mantenimiento con su prórroga (formas de R54 y R62 del caso-00, con textos inventados) y el IVA sin
mención. Textos inventados (P4); sin red ni modelo."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, criteria, not_applicable, portal_facts
from tests.assessment.test_ajuste_t240 import chosen_form
from tests.assessment.test_comite_t257 import (
    NEGATIVE,
    OPTION,
    TITLES,
    VAT,
    apply,
    condition,
    pair_with,
    quoted,
)
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import located, portal_data
from tests.assessment.test_verificacion_t257 import cited

pytestmark = pytest.mark.django_db

UNDETERMINED = combine.Combined(outcome="no_determinado", doubt="sin_dato", exigence="condicion")


def undetermined(**fields):
    return combine.Combined(**{"outcome": "no_determinado", "doubt": "sin_dato",
                               "exigence": "condicion", **fields})


# --- Positivos que siguen dando «cumple» ------------------------------------------------------------

NEGATIVE_LIKE_R54 = ("No se aceptarán ofertas condicionadas a futuros aumentos de costos o a "
                     "cualquier otra condición.")
TERM_LIKE_R62 = (
    "De acuerdo con lo establecido en el artículo 9 del reglamento de compras, los oferentes deberán "
    "mantener y garantizar, en el caso que corresponda, su oferta por un plazo de NOVENTA (90) días "
    "corridos contados a partir de la fecha del acto de apertura. El día de la apertura quedará "
    "excluido del cómputo del plazo. La oferta se considerará prorrogada automáticamente por un lapso "
    "igual al inicial y así sucesivamente.")


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [NEGATIVE_LIKE_R54, TERM_LIKE_R62])
def test_the_forms_of_r54_and_r62_are_still_met_by_absence(offer, text):
    """REQ-104 (decisiones del 2026-10-12, «Cumple por ausencia» y «En la misma fila del plazo»): la
    oración entera de la prohibición de condicionar, y la del plazo de mantenimiento con su cómputo y
    su prórroga, sin nada del modelo sobre la condición, siguen «cumple por ausencia»."""
    records = [condition("La oferta cumple lo que pide la oración", "no_consta")]
    name, result = apply(offer, pair_with(text, undetermined(), records))
    assert name == "cumple_por_ausencia" and result.outcome == "cumple"
    assert all(t in result.explanation for t in TITLES)


@pytest.mark.decision_literal
def test_the_vat_without_any_mention_is_still_presumed(offer, portal):
    """REQ-103 (decisión del 2026-10-12 «Precio del Portal = final con IVA»): si ni los documentos ni
    el modelo dicen nada del impuesto ni del precio, el IVA se presume y la celda es «cumple»."""
    portal_data(portal, offer)
    records = [condition("Cotizar en pesos argentinos", "cumple", "ARS"),
               condition("Incluir el IVA", "no_consta")]
    ctx_pages = [{"page": 1, "text": "Nota de presentación de la oferta de limpieza.",
                  "readable": True}]
    pair = pair_with(VAT, undetermined(), records)
    ctx = SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=[SimpleNamespace(
        document=SimpleNamespace(title=TITLES[0]), pages=ctx_pages)]))
    from evaluon.assessment import rules

    assert rules.apply(pair, ctx) == "portal_cumple" and pair.combined.outcome == "cumple"


# --- N1: la ausencia, solo para la oración entera de una forma cerrada ------------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, records", [
    ("No se aceptarán ofertas condicionadas. El oferente acompañará una declaración jurada de no "
     "condicionamiento de la oferta.",
     [condition("La oferta no está condicionada", "no_consta"),
      condition("Acompañar la declaración jurada de no condicionamiento", "no_consta")]),
    ("Se presentará una declaración jurada que indique el plazo de mantenimiento de la oferta.",
     [condition("Presentar la declaración jurada con el plazo de mantenimiento", "no_consta")]),
    ("La adjudicación quedará condicionada a la presentación del certificado de aptitud ambiental.",
     [condition("La adjudicación quedará condicionada a la presentación del certificado de "
                "aptitud ambiental", "no_consta")]),
])
def test_n1_a_document_named_in_the_sentence_is_never_absence(offer, text, records):
    """REQ-104 (N1a a N1c): si la oración nombra un documento, no es ausencia: «no se encontró el
    documento»."""
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    name, result = apply(offer, pair_with(text, combined, records))
    assert name != "cumple_por_ausencia" and result.outcome == "sin_documento"


@pytest.mark.decision_literal
@pytest.mark.parametrize("model", ["cumple", "no_determinado"])
def test_n2_a_datum_of_the_model_about_the_condition_stops_the_absence(offer, model):
    """REQ-104 (N2): el modelo describe una condición en el dato («queda sujeta a la aprobación del
    directorio»), aunque sin cita ubicada: no es ausencia ni «ninguno lo contradice»."""
    records = [condition("La oferta no está condicionada", "no_determinado",
                         "La oferta queda sujeta a la aprobación del directorio", model=model)]
    name, result = apply(offer, pair_with(NEGATIVE, undetermined(), records))
    assert name != "cumple_por_ausencia" and result.outcome == "no_determinado"
    assert "ninguno lo contradice" not in result.explanation


# --- N3: el IVA solo si la oferta no dice nada del impuesto ni del precio ---------------------------


@pytest.mark.decision_literal
def test_n3a_a_datum_about_net_prices_stops_the_vat(offer, portal):
    """REQ-103 (N3a): el dato del modelo dice «precios netos»: el IVA no se presume."""
    portal_data(portal, offer)
    quote = "Cotizamos en pesos argentinos."
    records = [cited("Cotizar en pesos", "cumple", quote, "pesos"),
               condition("Incluir el IVA", "no_determinado", "La planilla dice precios netos")]
    name, result = apply(offer, pair_with(VAT, undetermined(citations=[located(quote)]), records))
    assert result.outcome != "cumple"


@pytest.mark.decision_literal
def test_n3b_a_citation_with_net_prices_stops_the_vat(offer, portal):
    """REQ-103 (N3b; falla si se quita `PRICE_TALK`): la cita que sostiene «Cotizar en pesos» dice
    «Precios netos»: no hay otra guarda que lo frene, y el IVA no se presume."""
    portal_data(portal, offer)
    quote = "Precios netos en pesos argentinos."
    records = [cited("Cotizar en pesos", "cumple", quote, "pesos argentinos"),
               condition("Incluir el IVA", "no_consta")]
    name, result = apply(offer, pair_with(VAT, undetermined(citations=[located(quote)]), records))
    assert result.outcome != "cumple" and "iva_precio_final_portal" not in str(
        result.facts.get("criterios"))


def test_n3b_without_price_talk_the_vat_would_be_presumed(offer, portal, monkeypatch):
    """REQ-103: el control de la prueba anterior. Sin `PRICE_TALK` («netos»), el mismo par daría
    «cumple»: es esa guarda la que lo frena."""
    portal_data(portal, offer)
    monkeypatch.setattr(criteria, "PRICE_TALK", criteria.re.compile(r"(?!x)x"))
    quote = "Precios netos en pesos argentinos."
    records = [cited("Cotizar en pesos", "cumple", quote, "pesos argentinos"),
               condition("Incluir el IVA", "no_consta")]
    name, result = apply(offer, pair_with(VAT, undetermined(citations=[located(quote)]), records))
    assert result.outcome == "cumple"


def test_n3c_a_price_update_in_the_datum_is_not_a_fixed_price(offer, procedure, portal):
    """REQ-103, REQ-104 (N3c): el dato dice que los precios se actualizan por un índice: ni ausencia
    ni «cumple»."""
    quoted(procedure, offer, portal)
    text = "Cotizar el valor unitario de cada renglón; los precios serán fijos e inamovibles."
    records = [condition("Cotizar el valor unitario de cada renglón", "cumple", "100.0000"),
               condition("Los precios son fijos e inamovibles", "no_determinado",
                         "La planilla dice que los precios se actualizan por el índice de precios")]
    name, result = apply(offer, pair_with(text, undetermined(), records))
    assert result.outcome != "cumple" and "Cumple por ausencia" not in result.explanation


def test_the_offer_documents_that_talk_about_the_tax_stop_the_vat(offer, portal):
    """REQ-103 (decisión del Coordinador): si los documentos de la oferta hablan del impuesto o del
    precio («más IVA»), aunque el modelo no lo cite, el IVA no se presume."""
    portal_data(portal, offer)
    records = [condition("Cotizar en pesos argentinos", "cumple", "ARS"),
               condition("Incluir el IVA", "no_consta")]
    pages = [{"page": 1, "text": "Los precios de la planilla son más IVA.", "readable": True}]
    ctx = SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=[SimpleNamespace(
        document=SimpleNamespace(title=TITLES[0]), pages=pages)]))
    from evaluon.assessment import rules

    pair = pair_with(VAT, undetermined(), records)
    rules.apply(pair, ctx)
    assert pair.combined.outcome != "cumple"


# --- N4: lo que la oración pide además ----------------------------------------------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "Los precios serán fijos e inamovibles y la oferta indicará el plazo de entrega.",
    "Los oferentes deberán mantener su oferta por sesenta días y acompañar el certificado de "
    "capacidad financiera.",
    "La oferta no podrá estar condicionada y deberá indicar el plazo de entrega en días hábiles.",
    "El oferente cotizará el valor unitario de cada renglón; los precios serán fijos e inamovibles, "
    "incluirán los impuestos y se expresarán en moneda nacional.",
])
def test_n4_a_sentence_that_asks_something_else_is_not_absence(offer, text):
    """REQ-104 (N4a, N4b, N4c, N4e): la oración entera tiene que ser la forma cerrada; con otra
    exigencia (el plazo de entrega, un certificado, el valor unitario), no hay ausencia."""
    records = [condition(text.rstrip("."), "no_consta")]
    name, result = apply(offer, pair_with(text, undetermined(), records))
    assert name != "cumple_por_ausencia" and result.outcome != "cumple"


@pytest.mark.decision_literal
@pytest.mark.parametrize("with_condition", [True, False])
def test_n4d_the_portal_does_not_bring_color_or_size(offer, procedure, portal, with_condition):
    """REQ-103 (N4d): el Portal no trae color ni talle: con una condición o sin condiciones, no es
    «cumple»."""
    quoted(procedure, offer, portal)
    text = "Cotizar por renglón indicando el color y el talle de cada prenda."
    records = ([condition("Cotizar por renglón indicando el color y el talle", "no_consta")]
               if with_condition else [])
    combined = undetermined() if with_condition else combine.Combined(outcome="sin_documento")
    name, result = apply(offer, pair_with(text, combined, records, items=[1, 2]))
    assert result.outcome != "cumple" and name != "portal_cumple"


# --- N5: el Portal, solo con exactamente un dato de su lista -------------------------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("with_condition", [True, False])
def test_n5b_a_reference_and_a_name_are_not_portal_data(offer, portal, with_condition):
    """REQ-103 (N5b): la referencia de la póliza y la denominación de quien la otorga no son datos
    del Portal: no es «cumple»."""
    portal_data(portal, offer)
    text = ("En el Paso 4 Ingreso de Garantía se consignará la referencia de la póliza y la "
            "denominación de la empresa que la otorga.")
    records = ([condition("Consignar la referencia de la póliza y la denominación de la empresa",
                          "no_consta")] if with_condition else [])
    combined = undetermined() if with_condition else combine.Combined(outcome="sin_documento")
    name, result = apply(offer, pair_with(text, combined, records))
    assert result.outcome != "cumple" and name != "portal_cumple"


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "Los oferentes cotizarán íntegramente cada renglón.",
    "Se cotizará el volumen requerido en cada renglón.",
    "Se cotizarán los kilos pedidos de cada renglón.",
])
def test_n5c_a_quantity_said_with_another_unit_is_not_resolved(offer, procedure, portal, text):
    """REQ-103 (N5c): con 4 de 10 unidades cotizadas, «íntegramente», «el volumen» o «los kilos» no
    son el dato de cantidad del Portal: no es «cumple»."""
    quoted(procedure, offer, portal, asked="10", offered="4")
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento"),
                                          items=[1, 2]))
    assert result.outcome == "no_determinado" and name != "portal_cumple"


# --- N6: «no aplica» solo con el campo `usa_opcion` en «no» ----------------------------------------------


@pytest.mark.decision_literal
def test_n6_without_the_field_saying_no_the_option_is_undetermined(offer):
    """REQ-103, REQ-105 (N6): el modelo explica que la oferta es una cooperativa, sin dato ni cita;
    la regla lee el campo `usa_opcion`, no el texto: sin «no», «no determinado» con la pregunta; con
    «si», se evalúa; solo con «no», «no aplica»."""
    explanation = ("La nota de presentación declara que el oferente es una cooperativa de trabajo, "
                   "pero no se adjunta la constancia de matrícula.")
    records = [condition("Acompañar la constancia de matrícula", "no_determinado")]
    combined = undetermined(explanation=explanation)
    name, result = apply(offer, pair_with(OPTION, combined, records, opcion="mipyme"))
    assert name == "opcion_sin_determinar" and not not_applicable.is_not_applicable(result)
    name, result = apply(offer, pair_with(OPTION, undetermined(explanation=explanation), records,
                                          opcion="mipyme", option_use="si"))
    assert name not in ("opcion_no_usada", "opcion_sin_determinar")
    name, result = apply(offer, pair_with(OPTION, undetermined(), records, opcion="mipyme",
                                          option_use="no"))
    assert name == "opcion_no_usada"


def test_the_option_field_is_read_from_the_model_output():
    """REQ-105, REQ-106: `usa_opcion` está en el esquema de la instrucción vigente, en su orden, y se
    lee de la salida del modelo («si», «no», «no_consta»)."""
    from evaluon.assessment import prompting

    schema = prompting.evaluation_schema(["D1"], [], [])
    order = list(schema["properties"])
    assert order.index("exigencia") + 1 == order.index("usa_opcion")
    assert "usa_opcion" in schema["required"]
    assert schema["properties"]["usa_opcion"]["enum"] == ["si", "no", "no_consta"]
    import json

    from tests.assessment.fakes import says

    raw = {**says("no_determinado"), "usa_opcion": "no"}
    assert prompting.parse_evaluation(json.dumps(raw), ["D1"], []).option_use == "no"
    with pytest.raises(prompting.InvalidOutput):
        prompting.parse_evaluation(json.dumps({**raw, "usa_opcion": "tal vez"}), ["D1"], [])
    assert "\"usa_opcion\"" in prompting.load_prompt("evaluacion")


# --- N7: la presentación física, solo como obligación del oferente al ofertar ------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "Las consultas podrán presentarse en la Mesa de Entradas y deberán indicar el número del "
    "procedimiento.",
    "El adjudicatario deberá entregar los bienes en la Mesa de Entradas del organismo.",
])
def test_n7_a_presentation_that_is_not_the_offerors_at_the_offer_is_not_no_cumple(offer, text):
    """REQ-104 (N7a, N7b): el «deberán» que no es de la presentación, o la obligación del
    adjudicatario en la ejecución, no son la presentación física de la oferta: no es «no cumple»."""
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento")))
    assert name != "presentacion_fisica_no_consta" and result.outcome != "no_cumple"


def test_the_offerors_physical_presentation_at_the_offer_is_still_no_cumple(offer, portal):
    """REQ-104: «el oferente deberá presentar… en Mesa de Entrada» y no consta: «no cumple» con el
    aviso de que puede faltar cargarlo."""
    chosen_form(portal, offer, "Pagare")
    text = "El oferente deberá presentar el original del pagaré en la Mesa de Entrada del organismo."
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento")))
    assert name == "presentacion_fisica_no_consta" and "Puede faltar cargarlo" in result.explanation
    assert portal_facts  # el Portal no interviene: la presentación física decide antes
