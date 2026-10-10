"""Hallazgos de la medición T-171 (REQ-061, REQ-063, REQ-064; plan 004, enmienda 2026-10-06;
T-172). Datos inventados (P4); sin modelo."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, externals, rules, technical, unreadable
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401 - `portal` es fixture

pytestmark = pytest.mark.django_db

PRICE_LINE = "Renglón 6: resma de papel A4, precio unitario 120,50"
FOUND = {"documento": "pagare.pdf", "documento_id": 1, "archivo": "pagare.pdf", "pagina": 2,
         "paginas": [2]}


def doc(title, kind=""):
    return SimpleNamespace(document=SimpleNamespace(kind=kind, title=title, file_name=title))


def cite(title, text, kind=""):
    return SimpleNamespace(document=SimpleNamespace(kind=kind, title=title, file_name=title),
                           text=text, page=1)


def technical_pair(combined, *groups):
    return SimpleNamespace(
        combined=combined, groups=list(groups), text=SimpleNamespace(text="Renglón 6: resma"),
        requirement=SimpleNamespace(category="tecnico", items=[], number=1))


def ctx_with(*documents):
    return SimpleNamespace(offer=0, offer_text=SimpleNamespace(documents=list(documents)))


# --- H-3 y H-6: el documento técnico ---------------------------------------------------------


@pytest.mark.decision_literal
def test_a_price_line_is_not_a_technical_document():
    """REQ-061, H-3: una cita de la cotización (línea de precio) no hace `hay`; con la lectura
    completa y sin ficha, la oferta no tiene documento técnico."""
    line = cite("oferta-economica.pdf", PRICE_LINE, kind="economica")
    combined = combine.Combined(outcome="cumple", citations=[line])
    pair = technical_pair(combined, combine.GroupResult(0, "cumple", citations=[line]))
    decided = technical.rule(pair, ctx_with(doc("oferta-economica.pdf", "economica")))
    assert decided.facts["documento_tecnico"] == "no_se_encontro"
    assert (decided.outcome, decided.doubt) == ("no_determinado", "pendiente_informe_tecnico")
    assert decided.opinion == "cumple"


@pytest.mark.decision_literal
@pytest.mark.parametrize("title,kind", [("anexo.pdf", "tecnica"), ("Ficha técnica papel.pdf", ""),
                                        ("hoja_tecnica_A4.pdf", ""),
                                        ("Especificaciones técnicas firmadas.pdf", "")])
def test_a_real_technical_document_is_there(title, kind):
    """REQ-061, H-3: ficha, hoja técnica o especificación (por tipo o por nombre) es `hay`."""
    pair = technical_pair(combine.Combined(outcome="no_determinado", doubt="sin_dato"),
                          combine.GroupResult(0, "no_consta"))
    decided = technical.rule(pair, ctx_with(doc("oferta.pdf"), doc(title, kind)))
    assert decided.facts["documento_tecnico"] == "hay"


@pytest.mark.decision_literal
def test_a_citation_counts_only_through_its_technical_document():
    """REQ-061, H-A2: la cita de un documento que se llama ficha cuenta; el texto citado de un
    documento sin ese nombre no."""
    sheet = cite("Ficha del producto.pdf", "gramaje 75 g, 210 x 297 mm")
    decided = technical.rule(technical_pair(combine.Combined(outcome="cumple", citations=[sheet])),
                             ctx_with(doc("nota.pdf")))
    assert decided.facts["documento_tecnico"] == "hay"
    text_only = cite("anexo-3.pdf", "Ficha técnica: gramaje 75 g, 210 x 297 mm")
    decided = technical.rule(
        technical_pair(combine.Combined(outcome="cumple", citations=[text_only]),
                       combine.GroupResult(0, "cumple", citations=[text_only])),
        ctx_with(doc("anexo-3.pdf")))
    assert decided.facts["documento_tecnico"] == "no_se_encontro"


@pytest.mark.decision_literal
@pytest.mark.parametrize("title", ["Ficha de producto.pdf", "ficha.pdf", "Hoja de datos.pdf",
                                   "ficha_producto.pdf", "Catálogo 2026.pdf"])
def test_word_boundaries_recognize_a_document_named_ficha_or_hoja_de_datos(title):
    """REQ-061, H-A: «ficha» sola y «hoja de datos» cuentan (límites de palabra reales)."""
    assert technical._is_technical_document(doc(title).document)
    assert chr(8) not in technical._TECHNICAL_DOCUMENT.pattern


@pytest.mark.decision_literal
@pytest.mark.parametrize("title", ["fichaje-personal.pdf", "Planilla de beneficiarios.pdf",
                                   "nota.pdf"])
def test_a_word_that_only_contains_ficha_is_not_a_technical_document(title):
    """REQ-061, H-A: «fichaje» no es una ficha."""
    assert not technical._is_technical_document(doc(title).document)


@pytest.mark.decision_literal
def test_an_economic_document_is_never_technical_even_if_named_catalogo():
    """REQ-061, H-A2: la cotización de un artículo «folleto» o «catálogo» (tipo económica) no
    es un documento técnico, ni por su nombre ni por sus citas."""
    line = cite("Cotización folleto.pdf", "Renglón 3: Folleto institucional a color, precio "
                "unitario 45", kind="economica")
    pair = technical_pair(combine.Combined(outcome="cumple", citations=[line]),
                          combine.GroupResult(0, "cumple", citations=[line]))
    decided = technical.rule(pair, ctx_with(doc("Cotización folleto.pdf", "economica")))
    assert decided.facts["documento_tecnico"] == "no_se_encontro"


@pytest.mark.decision_literal
def test_a_complete_reading_without_a_technical_document_is_not_found_not_undetermined():
    """REQ-061, H-6: sin documento técnico y con la lectura completa: `no_se_encontro`; la fila
    sigue pendiente del informe (no se vuelve `sin_documento`)."""
    pair = technical_pair(combine.Combined(outcome="no_determinado", doubt="sin_dato"),
                          combine.GroupResult(0, "no_consta"))
    decided = technical.rule(pair, ctx_with(doc("nota.pdf")))
    assert decided.facts["documento_tecnico"] == "no_se_encontro"
    assert (decided.outcome, decided.doubt) == ("no_determinado", "pendiente_informe_tecnico")


@pytest.mark.decision_literal
def test_with_unread_parts_the_missing_technical_document_is_not_affirmed():
    """REQ-061, H-6: con partes sin leer sigue `no_determinado`."""
    pair = technical_pair(
        combine.Combined(outcome="no_determinado", doubt="lectura_incompleta",
                         unread_warning=True), combine.GroupResult(0, "no_consta"))
    decided = technical.rule(pair, ctx_with(doc("nota.pdf")))
    assert decided.facts["documento_tecnico"] == "no_determinado"


@pytest.mark.decision_literal
def test_the_line_comes_from_the_portal_quote_without_a_technical_document(
        offer, procedure, portal):  # noqa: F811
    """REQ-061, H-6: con la cotización del Portal cargada, `renglon_ofertado` es `si` aunque
    la oferta no tenga documento técnico ni la lectura cite el renglón."""
    quote_data(portal, procedure, offer, total=Decimal("900"),
               prices={1: (Decimal("120.50"), Decimal("10"))})
    requirement = SimpleNamespace(category="tecnico", items=[1], number=1)
    pair = SimpleNamespace(
        combined=combine.Combined(outcome="no_determinado", doubt="sin_dato"),
        groups=[combine.GroupResult(0, "no_consta")],
        text=SimpleNamespace(text="Renglón 1"), requirement=requirement)
    ctx = SimpleNamespace(offer=offer, offer_text=SimpleNamespace(documents=[doc("nota.pdf")]))
    decided = technical.rule(pair, ctx)
    assert decided.facts["documento_tecnico"] == "no_se_encontro"
    assert decided.facts["renglon_ofertado"] == "si"


# --- H-4: el ilegible rige en todos los pares que dependen del documento ----------------------


def guarantee_pair(text, outcome="no_determinado", doubt="lectura_incompleta", flagged=False):
    groups = [combine.GroupResult(0, "no_determinado", unreadable=FOUND if flagged else None)]
    return SimpleNamespace(
        combined=combine.Combined(outcome=outcome, doubt=doubt, unread_warning=True),
        text=SimpleNamespace(text=text), requirement=0, groups=groups)


@pytest.mark.decision_literal
def test_the_unreadable_rule_reaches_the_pairs_that_depend_on_the_same_document():
    """REQ-064, H-4 y H-B: el modelo señala el pagaré solo en un par; los pares que nombran el
    pagaré o la garantía que se integra con la oferta quedan `no_se_pudo_leer` (con el mismo
    documento y página); otro tema no."""
    copy = guarantee_pair("Adjuntar con la oferta copia del pagaré.", flagged=True)
    maintenance = guarantee_pair("Integrar una garantía de mantenimiento de la oferta.")
    individual = guarantee_pair("La garantía deberá ser individualizada al presentar la oferta.")
    signed = guarantee_pair("El pagaré se suscribirá en blanco.")
    other = guarantee_pair("El plazo de entrega será de diez días corridos.")
    pairs = [maintenance, individual, signed, copy, other]
    ctx = SimpleNamespace(offer=0, unreadable_flags=unreadable.collect(pairs))
    names = [rules.apply(p, ctx) for p in pairs]
    assert names == ["ilegible_informe"] * 4 + [None]
    for pair in (maintenance, individual, signed, copy):
        assert (pair.combined.outcome, pair.combined.doubt) == ("no_determinado",
                                                                "no_se_pudo_leer")
        assert pair.combined.facts["ilegible"]["pagina"] == 2
        assert "página 2" in pair.combined.question
    assert maintenance.combined.facts["ilegible"]["propagado"] is True
    assert "propagado" not in copy.combined.facts["ilegible"]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "La garantía técnica del bien será de doce meses.",
    "Garantía de fábrica de los equipos entregados.",
    "Para impugnar se integrará una garantía de impugnación.",
    "Garantía de cumplimiento de contrato del diez por ciento.",
    "El oferente presentará una póliza de responsabilidad civil.",
])
def test_the_unreadable_does_not_reach_other_guarantees(text):
    """REQ-064, H-B: una garantía técnica, de fábrica, de impugnación o de cumplimiento, o una
    forma distinta (póliza frente a pagaré), no recibe el ilegible del pagaré de la oferta."""
    copy = guarantee_pair("Adjuntar con la oferta copia del pagaré.", flagged=True)
    other = guarantee_pair(text)
    ctx = SimpleNamespace(offer=0, unreadable_flags=unreadable.collect([copy, other]))
    assert rules.apply(other, ctx) is None
    assert other.combined.doubt == "lectura_incompleta"


@pytest.mark.decision_literal
def test_the_unreadable_rule_does_not_override_a_conclusion_with_another_document():
    """REQ-064, H-4: un par de la garantía que otro documento respondió (cumple) no se pisa."""
    copy = guarantee_pair("Adjuntar con la oferta copia del pagaré.", flagged=True)
    concluded = guarantee_pair("Integrar una garantía de mantenimiento de la oferta.",
                               outcome="cumple", doubt="")
    ctx = SimpleNamespace(offer=0, unreadable_flags=unreadable.collect([copy, concluded]))
    assert rules.apply(concluded, ctx) is None
    assert concluded.combined.outcome == "cumple"


def test_without_a_flagged_document_nothing_is_propagated():
    """REQ-064, H-4: si el modelo no señaló ningún documento, la garantía sigue su camino."""
    maintenance = guarantee_pair("Integrar una garantía de mantenimiento de la oferta.")
    ctx = SimpleNamespace(offer=0, unreadable_flags=unreadable.collect([maintenance]))
    assert rules.apply(maintenance, ctx) is None
    assert maintenance.combined.doubt == "lectura_incompleta"


# --- H-5: la habilidad para contratar y la validación de la póliza son externas --------------

HABILITY = ("El Oferente deberá completar, suscribir y adjuntar la Declaración Jurada que se "
            "agrega como Anexo al presente Pliego. Deberá elegir la que le corresponda según "
            "sea persona jurídica o humana.")


@pytest.mark.decision_literal
@pytest.mark.parametrize("text,key", [
    # T-231 (E-6): la declaración de habilidad que la oferta trae dejó de ser externa (ver
    # tests/assessment/test_t231.py); queda la verificación de la habilidad por la Comisión.
    ("La Comisión verificará la habilidad para contratar del oferente en la evaluación.",
     "habilidad_contratar"),
    ("La póliza de caución debe estar emitida según los requisitos de la Resolución N° 10/2020 "
     "de la Superintendencia de Seguros de la Nación.", "seguros"),
    ("La Comisión verificará la validez de la póliza de caución.", "seguros"),
    # T-175: la norma de la Superintendencia sobre pólizas electrónicas es un externo.
    ("En caso de póliza de seguro de caución electrónica, debe estar emitida a nombre del "
     "organismo y cumplir la Resolución N° 219/2018.", "seguros"),
    ("Se consultará la póliza presentada ante el organismo de control.", "seguros"),
])
def test_the_catalog_recognizes_the_habilidad_declaration_and_the_policy_validation(text, key):
    """REQ-063, H-C: la declaración de habilidad (por la palabra o los supuestos del art. 18) y
    la validación de la póliza (Superintendencia o verbo de verificación) son externas."""
    assert key in [c.key for c in externals.match(text)]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    'El oferente deberá completar, suscribir y adjuntar la "Declaración Jurada de Intereses" '
    "que surge del Anexo I de la Resolución N° 11-E/2017.",
    "El oferente deberá completar, suscribir y adjuntar la Declaración Jurada de Intereses "
    "que se agrega como Anexo al presente Pliego.",
    "Deberá completar, suscribir y adjuntar la Declaración Jurada de aceptación de la "
    "jurisdicción que se agrega como Anexo.",
    "Presentar la póliza de caución en original firmada por el representante.",
    "En caso de póliza de seguro de caución electrónica, debe estar emitida a nombre del "
    "organismo y cumplir la Resolución N° 21/2018.",
])
def test_the_catalog_does_not_mark_other_declarations_or_policies(text):
    """REQ-063, H-C: otra declaración jurada «que se agrega como Anexo», una póliza que el
    oferente presenta o otro número de resolución no son externos."""
    assert externals.match(text) == []


def test_the_rules_version_is_v7():
    """T-175: la versión de las reglas sube a `reglas-v7` (T-172 la subió a v5, T-175 a v6)."""
    from django.conf import settings
    assert settings.ASSESSMENT_RULES_VERSION == "reglas-v7"
