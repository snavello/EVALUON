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
def test_a_cited_technical_text_counts_as_the_technical_document():
    """REQ-061, H-3: la cita de una ficha técnica de un documento sin tipo cuenta."""
    line = cite("anexo-3.pdf", "Ficha técnica: gramaje 75 g, 210 x 297 mm")
    combined = combine.Combined(outcome="cumple", citations=[line])
    decided = technical.rule(technical_pair(combined), ctx_with(doc("anexo-3.pdf")))
    assert decided.facts["documento_tecnico"] == "hay"


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
def test_the_unreadable_rule_reaches_every_pair_that_depends_on_the_document():
    """REQ-064, H-4: el modelo señala el pagaré solo en un par; los otros dos de la garantía
    quedan igual `no_se_pudo_leer`, con el mismo documento y página; uno de otro tema no."""
    copy = guarantee_pair("Adjuntar con la oferta copia del pagaré.", flagged=True)
    maintenance = guarantee_pair("Integrar una garantía de mantenimiento de la oferta.")
    individual = guarantee_pair("La garantía deberá ser individualizada al presentar la oferta.")
    other = guarantee_pair("El plazo de entrega será de diez días corridos.")
    pairs = [maintenance, individual, copy, other]
    ctx = SimpleNamespace(offer=0, unreadable_flags=unreadable.collect(pairs))
    names = [rules.apply(p, ctx) for p in pairs]
    assert names == ["ilegible_informe"] * 3 + [None]
    for pair in (maintenance, individual, copy):
        assert (pair.combined.outcome, pair.combined.doubt) == ("no_determinado",
                                                                "no_se_pudo_leer")
        assert pair.combined.facts["ilegible"]["pagina"] == 2
        assert "página 2" in pair.combined.question
    assert maintenance.combined.facts["ilegible"]["propagado"] is True
    assert "propagado" not in copy.combined.facts["ilegible"]


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
    ("ANEXO I o II - DECLARACIÓN JURADA HABILIDAD PARA CONTRATAR: completar, suscribir y "
     "adjuntar.", "habilidad_contratar"),
    (HABILITY, "habilidad_contratar"),
    ("En caso de una póliza de seguro de caución electrónica debe estar emitida según los "
     "requisitos establecidos en la Resolución N° 219/2018", "seguros"),
    ("Debe cumplir la Resolución Nº 219/2018.", "seguros"),
])
def test_the_catalog_recognizes_the_habilidad_declaration_and_the_policy_validation(text, key):
    """REQ-063, H-5: la declaración jurada de habilidad y la validación de la póliza ante la
    Superintendencia son externas (hoja de compliance)."""
    assert key in [c.key for c in externals.match(text)]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    'El oferente deberá completar, suscribir y adjuntar la "Declaración Jurada de Intereses" '
    "que surge del Anexo I de la Resolución N° 11-E/2017.",
    "Presentar la póliza de caución en original firmada por el representante.",
])
def test_the_catalog_does_not_mark_other_declarations_or_policies(text):
    """REQ-063, H-5: la declaración de intereses y una póliza que se presenta no son externas."""
    assert externals.match(text) == []


def test_the_rules_version_is_v4():
    """T-172: la versión de las reglas sube a `reglas-v4`."""
    from django.conf import settings
    assert settings.ASSESSMENT_RULES_VERSION == "reglas-v4"
