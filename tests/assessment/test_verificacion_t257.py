"""T-257, corrección de la verificación (`verificacion/T-257.md`, D-257-1 a D-257-7): cada fila de
las tablas del registro, con su contraejemplo inventado (P4). Ante la duda, la regla no propone
«cumple» ni «no aplica»: queda «no determinado» con su pregunta (decisión del Coordinador). Sin
red ni modelo."""

import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, criteria, not_applicable
from evaluon.portal import models as pm
from tests.assessment.test_ajuste_t240 import chosen_form
from tests.assessment.test_comite_t257 import (
    NEGATIVE,
    OPTION,
    PHYSICAL,
    VAT,
    apply,
    condition,
    pair_with,
    quoted,
)
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import located, portal_data

pytestmark = pytest.mark.django_db


def cited(text, result, quote, datum=""):
    """Una condición con su cita de la oferta ubicada, como la arma `_check_conditions`."""
    item = condition(text, result, datum)
    item["cita"] = {"tipo": "oferta", "documento": "Nota", "pagina": 1, "texto": quote}
    return item


# --- D-257-1: un documento pedido en negativo no se cumple por ausencia ---------------------------

DOCUMENT_IN_NEGATIVE = [
    "No se aceptarán ofertas sin la constancia de inscripción en el registro de proveedores.",
    "No se considerarán las ofertas que carezcan de la firma del representante legal.",
    "No se admitirán ofertas que omitan la declaración jurada de intereses.",
    "No se tomarán en cuenta las ofertas desprovistas del certificado fiscal vigente.",
]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", DOCUMENT_IN_NEGATIVE)
def test_a_document_asked_in_negative_is_not_met_by_absence(offer, text):
    """REQ-104 (D-257-1): «No se aceptarán ofertas sin…», «que carezcan / omitan / desprovistas de…»
    piden el documento: queda «no se encontró el documento», nunca «cumple por ausencia»."""
    assert not criteria.by_absence(text)
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    name, result = apply(offer, pair_with(text, combined, [
        condition("Presentar el documento que pide el pliego", "no_consta")]))
    assert name != "cumple_por_ausencia" and result.outcome == "sin_documento"


@pytest.mark.parametrize("text, form", [
    ("No se aceptarán ofertas condicionadas a la variación del tipo de cambio.", "condicionar"),
    # reverificación de T-257: solo la prohibición de condicionar y el plazo con su prórroga
    ("La oferta se formulará sin reservas sobre las condiciones del llamado.", ""),
    ("Los precios serán fijos e inamovibles.", ""),
    ("Los oferentes mantendrán su oferta por noventa días corridos.", "mantenimiento"),
    ("La oferta se considerará prorrogada automáticamente por un lapso igual.", "mantenimiento"),
    ("No se aceptarán ofertas variantes.", ""),
    ("Se cotizará en pesos.", ""),
])
def test_the_absence_is_a_closed_list_of_forms(text, form):
    """REQ-104 (D-257-1): la ausencia vale solo para la lista cerrada: no condicionar, sin reservas,
    precio fijo, el plazo de mantenimiento y su prórroga. Lo demás no es ausencia."""
    assert criteria.absence_form(text) == form


# --- D-257-2: lo que el contraste rechazó no se cumple por ausencia -------------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("quote", [
    "La presente oferta queda sujeta a la variación del tipo de cambio.",
    "Acepto el pliego.",
])
def test_a_cumple_the_contrast_rejected_is_not_met_by_absence(offer, quote):
    """REQ-104 (D-257-2, decisión del Coordinador): si el contraste rechazó el «cumple» del modelo,
    queda «no determinado» (con la pregunta que arma el código), nunca «cumple por ausencia» ni
    «ninguno lo contradice»."""
    combined = combine.Combined(outcome="no_determinado", doubt="sin_corroborar",
                                proposed="cumple", citations=[located(quote)], ask=True)
    records = [cited("La oferta no está condicionada a la variación del tipo de cambio", "cumple",
                     quote, "sin condiciones")]
    name, result = apply(offer, pair_with(NEGATIVE, combined, records, group_result="cumple"))
    assert name != "cumple_por_ausencia"
    assert result.outcome == "no_determinado" and result.doubt == "sin_corroborar"
    assert "ninguno lo contradice" not in result.explanation and result.ask


def test_the_negative_requirement_without_any_text_is_still_met_by_absence(offer):
    """REQ-104 (R54, decisión del responsable): sin ninguna cita, con el contraste sin rechazo y la
    lectura completa, el requisito negativo sigue por ausencia."""
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato", exigence="condicion")
    records = [condition("La oferta no está condicionada a la variación del tipo de cambio",
                         "no_consta")]
    name, result = apply(offer, pair_with(NEGATIVE, combined, records))
    assert name == "cumple_por_ausencia" and "ninguno lo contradice" in result.explanation


# --- D-257-3: un texto dudoso frena la ausencia y el IVA -------------------------------------------


def test_a_doubtful_text_in_the_group_stops_the_absence(offer):
    """REQ-104 (D-257-3 a): la cita del grupo, aunque no esté en la condición, frena la ausencia."""
    combined = combine.Combined(outcome="no_determinado", doubt="duda", citations=[
        located("Los precios podrán revisarse si cambian las condiciones del mercado.")])
    records = [condition("Los precios son fijos e inamovibles", "no_determinado")]
    name, result = apply(offer, pair_with("Los precios cotizados serán fijos e inamovibles.",
                                          combined, records))
    assert name != "cumple_por_ausencia" and result.outcome != "cumple"
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato", citations=[
        located("Los precios podrán revisarse si cambian las condiciones del mercado.")])
    name, result = apply(offer, pair_with("Los precios cotizados serán fijos e inamovibles.",
                                          combined, records))
    assert name != "cumple_por_ausencia" and result.outcome != "cumple"


@pytest.mark.decision_literal
def test_the_vat_criterion_stops_if_the_offer_says_something_about_the_tax(offer, portal):
    """REQ-103 (D-257-3 b): si un documento dice que el precio no incluye el IVA (en la condición o
    en el par), el criterio del IVA no rige: nunca «cumple»."""
    portal_data(portal, offer)
    quote = "Los precios cotizados no incluyen IVA."
    records = [condition("Cotizar en pesos argentinos", "cumple", "ARS"),
               cited("Incluir el IVA", "no_determinado", quote)]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(VAT, combined, records))
    assert result.outcome != "cumple"
    combined = combine.Combined(outcome="sin_documento", citations=[located(quote)])
    name, result = apply(offer, pair_with(VAT, combined))
    assert result.outcome != "cumple"


def test_a_price_adjustment_stops_the_fixed_price_by_absence(offer, procedure, portal):
    """REQ-104 (D-257-3 b): el precio fijo con una cita que dice que los precios se ajustan no se
    cumple por ausencia ni se escribe «ninguno lo contradice»."""
    quoted(procedure, offer, portal)
    text = "Cotizar el valor unitario de cada renglón; los precios serán fijos e inamovibles."
    records = [condition("Cotizar el valor unitario de cada renglón", "cumple", "100.0000"),
               cited("Los precios son fijos e inamovibles", "no_determinado",
                     "Los precios se ajustarán mensualmente según el índice de precios.")]
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(text, combined, records))
    assert result.outcome != "cumple" and "ninguno lo contradice" not in result.explanation


# --- D-257-4: también la condición única se mira --------------------------------------------------


def test_a_single_condition_with_a_datum_is_not_met_by_absence(offer):
    """REQ-104 (D-257-4): con una sola condición que pide un dato (el plazo de entrega), no hay
    ausencia."""
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    text = "Los precios serán fijos e inamovibles y la oferta indicará el plazo de entrega."
    name, result = apply(offer, pair_with(text, combined, [
        condition("Indicar el plazo de entrega", "no_consta")]))
    assert name != "cumple_por_ausencia" and result.outcome != "cumple"


@pytest.mark.decision_literal
def test_the_portal_does_not_cover_the_brand_with_one_condition_or_none(offer, procedure, portal):
    """REQ-103 (D-257-4): el Portal no trae la marca ni el modelo: con una condición que lo junta
    todo, o sin condiciones, no es «cumple»."""
    quoted(procedure, offer, portal)
    text = "Cotizar por renglón indicando la marca y el modelo de cada producto ofrecido."
    combined = combine.Combined(outcome="no_determinado", doubt="sin_dato")
    name, result = apply(offer, pair_with(text, combined, [
        condition("Cotizar por renglón indicando la marca y el modelo", "no_consta")],
        items=[1, 2]))
    assert result.outcome != "cumple" and name != "portal_cumple"
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento"),
                                          items=[1, 2]))
    assert result.outcome != "cumple" and name != "portal_cumple"


# --- D-257-5: lo que el Portal no trae, dicho con otras palabras ------------------------------------

COVERS_TERM = ("Constituir una garantía de mantenimiento de la oferta del cinco por ciento (5 %) del "
               "monto cotizado, que deberá cubrir el plazo de mantenimiento de la oferta.")
IDENTIFIER = ("En el Paso 4 Ingreso de Garantía se consignará el identificador de la póliza y la "
              "razón social de quien la emite.")


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, records", [
    (COVERS_TERM, [condition("La garantía es del cinco por ciento del monto cotizado", "no_consta"),
                   condition("La garantía cubre el plazo de mantenimiento de la oferta",
                             "no_consta")]),
    (COVERS_TERM, []),
    (IDENTIFIER, [condition("Consignar el identificador de la póliza y la razón social",
                            "no_consta")]),
    (IDENTIFIER, []),
])
def test_the_portal_does_not_resolve_data_it_does_not_bring(offer, portal, text, records):
    """REQ-103 (D-257-5): que la garantía cubra el plazo, su identificador o la razón social de
    quien la emite no son datos del Portal: no es «cumple»."""
    portal_data(portal, offer)
    combined = combine.Combined(outcome="no_determinado" if records else "sin_documento",
                                doubt="sin_dato" if records else "")
    name, result = apply(offer, pair_with(text, combined, records))
    assert result.outcome != "cumple" and name != "portal_cumple"


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "Se deberá cotizar la totalidad de las unidades solicitadas en cada renglón.",
    "Los oferentes cotizarán por el total de lo solicitado en cada renglón.",
    "Se cotizará cada renglón completo, sin fraccionar lo pedido.",
])
def test_the_quantity_said_with_other_words_is_compared(offer, procedure, portal, text):
    """REQ-103 (D-257-5): con 4 de 10 unidades cotizadas, la totalidad dicha con otras palabras no
    es «cumple»: «no determinado» con la diferencia."""
    quoted(procedure, offer, portal, asked="10", offered="4")
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento"),
                                          items=[1, 2]))
    assert result.outcome == "no_determinado" and "4 de 10" in result.explanation


# --- D-257-6: «No aplica (opción no usada)» solo sin ninguna evidencia de uso ------------------------


@pytest.mark.decision_literal
@pytest.mark.parametrize("combined, records", [
    # el modelo encontró el certificado pero su cita no se ubicó
    (combine.Combined(outcome="no_determinado", doubt="sin_cita"),
     [condition("Acompañar el certificado", "no_determinado", "Certificado N° 12", model="cumple")]),
    # el dato del modelo dice que es MiPyME, sin cita
    (combine.Combined(outcome="no_determinado", doubt="duda"),
     [condition("Revestir la condición", "no_determinado", "la empresa es MiPyME")]),
])
def test_an_option_the_model_says_it_uses_without_a_citation_is_undetermined(
        offer, combined, records):
    """REQ-103, REQ-105 (D-257-6): si el modelo dice que la oferta usa la opción sin una cita
    ubicada, no es «no aplica»: «no determinado» con la pregunta de si la opción aplica."""
    name, result = apply(offer, pair_with(OPTION, combined, records, opcion="mipyme"))
    assert name == "opcion_sin_determinar"
    assert result.outcome == "no_determinado" and not not_applicable.is_not_applicable(result)
    assert "¿La oferta usa la opción «MiPyME»?" in result.question and result.ask


def test_the_partial_quote_option_without_portal_lines_is_undetermined(offer):
    """REQ-103 (D-257-6): en la cotización parcial, sin los renglones del Portal no se puede afirmar
    que la oferta no la usa: «no determinado»."""
    text = "Quienes coticen una parte del renglón indicarán el plazo de entrega de esa parte."
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    name, result = apply(offer, pair_with(text, combined, opcion="cotizacion_parcial",
                                          option_use="no"))
    assert name == "opcion_sin_determinar" and result.outcome == "no_determinado"
    assert "el Portal no tiene los renglones" in result.explanation


def test_without_the_requirement_citation_the_option_rule_says_nothing(offer):
    """REQ-103 (D-257-6): sin la cita del requisito ubicada en el pliego, la regla no decide."""
    combined = combine.Combined(outcome="sin_documento", exigence="documento")
    pair = pair_with(OPTION, combined, opcion="mipyme")
    pair.text = SimpleNamespace(text=OPTION, quotes=[])
    name, result = apply(offer, pair)
    assert name not in ("opcion_no_usada", "opcion_sin_determinar")


# --- D-257-7: la presentación física, solo cuando obliga y sin una circular que la cambie -----------


def with_circular(effect):
    source = SimpleNamespace(quote_id=1, effect=effect, issued_on=datetime.date(2026, 3, 5),
                             text="Resulta suficiente la carga electrónica de la garantía.")
    quote = SimpleNamespace(text=PHYSICAL, clarifications=[source] if effect == "aclara" else [],
                            suppressed=effect == "suprime", original="")
    return SimpleNamespace(text=PHYSICAL, quotes=[quote], clarifications=[])


@pytest.mark.decision_literal
@pytest.mark.parametrize("effect", ["aclara", "suprime"])
def test_a_circular_on_the_physical_presentation_avoids_the_no_cumple(offer, portal, effect):
    """REQ-104 (D-257-7): si una circular aclara (o suprime) la presentación física, no es «no
    cumple»: «no determinado» con la pregunta."""
    chosen_form(portal, offer, "Pagare")
    pair = pair_with(PHYSICAL, combine.Combined(outcome="sin_documento"))
    pair.text = with_circular(effect)
    name, result = apply(offer, pair)
    assert name == "presentacion_fisica_con_circular"
    assert result.outcome == "no_determinado" and result.question


@pytest.mark.parametrize("text", [
    "Las consultas al pliego podrán presentarse por escrito en la Mesa de Entradas del organismo.",
    "Una vez adjudicado, el oferente podrá retirar el original de la garantía en la Mesa de "
    "Entradas.",
])
def test_a_phrase_that_does_not_oblige_is_not_a_physical_presentation(offer, text):
    """REQ-104 (D-257-7): lo que solo se permite («podrán presentarse», «podrá retirar») no obliga:
    no es «no cumple»."""
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento")))
    assert name != "presentacion_fisica_no_consta" and result.outcome != "no_cumple"


def test_the_physical_presentation_that_obliges_is_still_no_cumple(offer, portal):
    """REQ-104: lo que obliga («deberá ser presentado») y no consta sigue «no cumple» con el aviso."""
    chosen_form(portal, offer, "Pagare")
    name, result = apply(offer, pair_with(PHYSICAL, combine.Combined(outcome="sin_documento")))
    assert name == "presentacion_fisica_no_consta" and "Puede faltar cargarlo" in result.explanation


def test_a_partial_quote_shows_the_option_and_full_quotes_do_not(offer, procedure, portal):
    """REQ-103: con los renglones del Portal, la cotización parcial se ve (4 de 10) y se evalúa; con
    todo cotizado, «no aplica»."""
    portal_data(portal, offer)
    line = pm.PortalLine.objects.create(procedure=procedure, number=1, description="x",
                                        quantity=Decimal("10"), item=portal)
    pm.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("5"), quantity=Decimal("10"))
    text = "Quienes coticen una parte del renglón indicarán el plazo de entrega de esa parte."
    name, result = apply(offer, pair_with(text, combine.Combined(outcome="sin_documento"),
                                          opcion="cotizacion_parcial", option_use="no"))
    assert name == "opcion_no_usada"
