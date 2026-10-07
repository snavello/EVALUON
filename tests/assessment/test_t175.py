"""T-175 (ronda extra de la 004, ADR-0025): el Portal como fuente completo (REQ-062), los
externos por el título del tramo y por la norma de la Superintendencia (REQ-063). Textos y datos
inventados (P4); sin red ni modelo."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, externals, grounds, portal_facts, rules
from evaluon.portal import models as pm
from tests.assessment.test_evaluate import requirement_of
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import located, pair_of, portal_data

pytestmark = pytest.mark.django_db

PER_LINE = "El oferente deberá cotizar el valor unitario de cada uno de los renglones ofrecidos."
INDIVIDUALIZED = ('El oferente deberá consignar en el Portal de Compras: "Paso 4 Ingreso de '
                  'Garantía" el número identificatorio en el campo titulado "Numero de '
                  'Documento".')


def quotes_of(portal, offer, procedure, prices=("100.0000", "250.5000")):
    """Los datos y las cotizaciones del Portal de la oferta: un renglón por precio."""
    portal_data(portal, offer)
    for number, price in enumerate(prices, start=1):
        line = pm.PortalLine.objects.create(
            procedure=procedure, number=number, description="x", item=portal)
        pm.PortalQuote.objects.create(
            offer=offer, line=line, price=Decimal(price), quantity=Decimal("10.0000"))


# --- Portal: cotización por renglón (causa 2) --------------------------------------------------


@pytest.mark.parametrize("text", [
    PER_LINE,
    "Por Renglón X",
    "Se podrá cotizar todos o algunos de los renglones del llamado.",
    "La cotización se hará por renglón.",
])
def test_a_text_that_asks_to_quote_per_line_is_a_quote_without_naming_a_line(text):
    """REQ-062: «cotizar todos o algunos renglones», «cada uno de los renglones» o «por renglón»
    piden la cotización por renglón aunque la fila no nombre un renglón."""
    assert portal_facts.kind_of(text, SimpleNamespace(items=[])) == "cotizacion"


@pytest.mark.parametrize("text", [
    "Cotizar en pesos con impuestos incluidos.",
    "El plazo de entrega se cuenta por semana.",
])
def test_quoting_without_a_line_is_not_a_per_line_quote(text):
    """REQ-062: sin mención de renglones, «cotizar» no es una cotización por renglón."""
    assert portal_facts.kind_of(text, SimpleNamespace(items=[])) is None


@pytest.mark.decision_literal
def test_the_per_line_quote_in_the_portal_is_cited_when_the_offer_does_not_bring_it(
        offer, procedure, portal):
    """REQ-062, decisión 4: la cotización por renglón está en las tablas del Portal y la oferta
    no la trae: «no determinado», «en el Portal», con una cita `portal` por cada fila de
    `portal_quote` de esa oferta y el texto de la fila."""
    quotes_of(portal, offer, procedure)
    pair = pair_of(PER_LINE, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_en_portal"
    assert pair.combined.doubt == "en_portal"
    cites = pair.combined.portal
    assert [c["kind"] for c in cites] == ["cotizacion", "cotizacion"]
    assert cites[0]["text"] == "Renglón 1: precio 100.0000, cantidad 10.0000"
    assert cites[1]["text"] == "Renglón 2: precio 250.5000, cantidad 10.0000"
    assert cites[0]["label"] == "Portal: cuadro comparativo"


@pytest.mark.decision_literal
def test_the_per_line_quote_that_coincides_adds_the_portal_citations(offer, procedure, portal):
    """REQ-062, decisión 4: la oferta trae el precio y coincide con el Portal: se suman las
    citas del Portal y el resultado no cambia."""
    quotes_of(portal, offer, procedure)
    text = "Renglón 2: precio unitario $ 250,50"
    pair = pair_of(PER_LINE, combine.Combined(outcome="cumple", citations=[located(text)]),
                   datos=[text])
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cita_agregada"
    assert pair.combined.outcome == "cumple"
    assert len(pair.combined.portal) == 2


@pytest.mark.decision_literal
def test_the_per_line_quote_that_differs_is_a_lack_of_coincidence(offer, procedure, portal):
    """REQ-062, decisión 4: el precio de la oferta no está entre los del Portal: falta de
    coincidencia, con la cita de la oferta y las del Portal."""
    quotes_of(portal, offer, procedure)
    text = "Renglón 2: precio unitario $ 999,00"
    pair = pair_of(PER_LINE, combine.Combined(outcome="cumple", citations=[located(text)]),
                   datos=[text])
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_falta_coincidencia"
    assert (pair.combined.outcome, pair.combined.doubt) == ("no_determinado",
                                                           "falta_coincidencia")
    assert len(pair.combined.portal) == 2 and pair.combined.citations


def test_a_named_line_still_cites_only_that_line(offer, procedure, portal):
    """REQ-062: con renglones nombrados en la fila, solo se cita el de la fila."""
    quotes_of(portal, offer, procedure)
    pair = pair_of("Cotizar el renglón 2.", combine.Combined(outcome="sin_documento"),
                   items=[2])
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_en_portal"
    assert [c["text"][:9] for c in pair.combined.portal] == ["Renglón 2"]


def test_without_quotes_in_the_portal_a_per_line_requirement_is_untouched(offer, portal):
    """REQ-062: sin cotizaciones cargadas para la oferta, el resultado no cambia."""
    portal_data(portal, offer)
    pair = pair_of(PER_LINE, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) is None


# --- Portal: garantía individualizada (causa 3) -----------------------------------------------


@pytest.mark.decision_literal
def test_the_guarantee_entered_in_the_portal_is_cited_when_the_offer_does_not_bring_it(
        offer, portal):
    """REQ-062, decisión 4: «Paso 4 Ingreso de Garantía» pide un dato que el Portal tiene: se
    cita la garantía del Portal aunque la oferta no la traiga."""
    data = portal_data(portal, offer, amount="21750.00")
    assert portal_facts.kind_of(INDIVIDUALIZED) == "garantia"
    pair = pair_of(INDIVIDUALIZED, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_en_portal"
    cite = pair.combined.portal[0]
    guarantee = data.guarantees.get()
    assert cite["kind"] == "garantia" and "21750.00" in cite["text"]
    assert guarantee.guarantee_form in cite["text"]


@pytest.mark.parametrize("text", [
    "La garantía de mantenimiento deberá ser individualizada al presentar la oferta.",
    "Deberá individualizar la garantía en el Portal.",
])
def test_the_individualized_guarantee_is_a_guarantee_of_the_portal(text):
    """REQ-062: la garantía «individualizada» entra al catálogo del Portal."""
    assert portal_facts.kind_of(text) == "garantia"


# --- Externos: título del tramo y norma de la Superintendencia (causa 5) -----------------------


def _quote(text, start, segment):
    return SimpleNamespace(segment=segment, char_start=start)


def _segment(label="", path="", text="", start=0):
    return SimpleNamespace(label=label, path=path, text=text, char_start=start)


def test_the_heading_of_the_segment_is_its_title_and_the_text_before_the_quote():
    """REQ-063: el título del tramo (encabezado, apartado más cercano de la ruta y lo que
    antecede a la cita en el tramo) se suma al texto que mira la regla de externos."""
    lead = "Anexo I o II - Declaración jurada de habilidad para contratar: "
    quote = "El oferente deberá completar, suscribir y adjuntar la declaración jurada."
    segment = _segment(text=lead + quote, start=100,
                       path="Sección I › 7. Presentación › 7.5. Requisitos › Párrafo 3")
    heading = grounds.segment_heading(_quote(quote, 100 + len(lead), segment))
    assert "habilidad para contratar" in heading and "Requisitos" in heading
    assert "Párrafo" not in heading and "Presentación" not in heading


def test_the_title_of_the_segment_makes_a_quote_external_that_alone_was_not():
    """REQ-063: la cita sola («completar, suscribir y adjuntar la declaración jurada») no dice
    de qué es la declaración; con el título del tramo, sí."""
    quote = "El oferente deberá completar, suscribir y adjuntar la declaración jurada."
    title = "Declaración jurada de habilidad para contratar"
    assert externals.match(quote) == []
    assert [c.key for c in externals.match(f"{title} {quote}")] == ["habilidad_contratar"]


def test_the_title_does_not_make_external_another_declaration_nor_a_policy():
    """REQ-063: una declaración jurada de intereses o una póliza que el oferente presenta no
    son externas aunque el tramo tenga título."""
    interests = ("Declaración jurada de intereses (Decreto 202/17) El oferente deberá completar, "
                 "suscribir y adjuntar la declaración jurada que se agrega como Anexo.")
    policy = ("Garantía de mantenimiento de la oferta La póliza de seguro de caución "
              "electrónica deberá adjuntarse a la oferta, firmada por el oferente.")
    assert externals.match(interests) == []
    assert externals.match(policy) == []


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "debe estar emitida según los requisitos establecidos en la Resolución N° 219/2018",
    "La póliza respetará la Resolución SSN 219/2018 y sus modificatorias.",
    "emitida conforme a la RESOLUCIÓN Nº 219/18.",
])
def test_the_norm_of_the_superintendence_on_electronic_policies_is_a_check_before_it(text):
    """REQ-063: la Resolución SSN 219/2018 (pólizas de caución electrónicas) rige en todos los
    pliegos de la AFIP/ARCA: quien la nombra se verifica ante la Superintendencia."""
    assert "seguros" in [c.key for c in externals.match(text)]


@pytest.mark.parametrize("text", [
    "La póliza de caución se presentará en original firmada por el representante.",
    "Conforme la Resolución N° 21/2018 de otra materia, se informará el domicilio.",
    "Resolución 219/2017 sobre otra materia.",
])
def test_other_resolutions_and_presented_policies_are_not_external(text):
    """REQ-063: otro número de resolución o una póliza presentada no son externos."""
    assert externals.match(text) == []


def test_the_requirement_text_has_the_title_context_and_the_text_stays_the_same(procedure):
    """REQ-063: `context` suma el título del tramo; `text` (el del pedido al modelo y de la
    búsqueda) no cambia."""
    requirement = requirement_of(procedure, "declaración jurada")
    text = grounds.requirement_text(requirement)
    assert text.text in text.context
    assert text.text == " ".join(q.text for q in requirement.quotes.order_by("order"))


def test_the_opening_of_the_quote_lets_the_portal_recognize_a_cut_condition(offer, portal):
    """REQ-062: la cita recorta solo «el número identificatorio…»; lo que la antecede en el
    tramo dice «Ingreso de Garantía»: la garantía del Portal se cita. Sin títulos de la ruta."""
    lead = '11.8. El oferente deberá consignar en el Portal de Compras: "Paso 4 Ingreso de Garantía" '
    quote = 'el número identificatorio en el campo titulado "Numero de Documento"'
    segment = _segment(text=lead + quote, start=0, path="Sección I › 11. Garantía de mantenimiento")
    q = _quote(quote, len(lead), segment)
    assert "Garantía de mantenimiento" not in grounds.segment_heading(q, titles=False)
    assert "Ingreso de Garantía" in grounds.segment_heading(q, titles=False)
    portal_data(portal, offer, amount="21750.00")
    pair = pair_of(quote, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) is None
    pair.text = SimpleNamespace(text=quote, opening=grounds.segment_heading(q, titles=False)
                                + " " + quote)
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_en_portal"
    assert pair.combined.portal[0]["kind"] == "garantia"


def test_the_lead_of_the_quote_is_only_the_sentence_where_it_starts():
    """REQ-063: lo que antecede a la cita en otra oración del tramo es otra condición: no se
    suma (así una condición vecina no hereda la habilidad de la anterior); el punto de «11.8.»
    no corta la oración."""
    first = "Declaración jurada de habilidad para contratar: completar y adjuntar la declaración. "
    second = "Deberá elegir la que le corresponda."
    segment = _segment(text=first + second, start=0)
    assert "habilidad" not in grounds.segment_heading(_quote(second, len(first), segment))
    numbered = '11.8. El oferente deberá consignar "Ingreso de Garantía" el número'
    cut = len(numbered) - len("el número")
    assert "Ingreso de Garantía" in grounds.segment_heading(
        _quote("el número", cut, _segment(text=numbered, start=0)))
