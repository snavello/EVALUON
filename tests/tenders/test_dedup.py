"""Unificación de las filas que repiten la misma condición (REQ-025, REQ-033; plan 003,
"Unificación de repetidas"; ADR-0021; T-101).

Las pruebas de la regla usan filas inventadas; las del proceso usan el doble del modelo con
el guion de `tests/tenders/scripted.py` y pliegos sintéticos (P4). Sin modelo real.
"""

import textwrap
from types import SimpleNamespace

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import dedup
from evaluon.tenders.proposal.extraction import Found
from evaluon.tenders.proposal.quotes import WIDE
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (  # noqa: F401  (script es una fixture)
    item,
    load_and_read,
    make_procedure,
    propose,
    script,
)

pytestmark = pytest.mark.django_db

MANT = "Los oferentes deberán mantener la oferta durante 60 días corridos."
MANT_QUOTE = "mantener la oferta durante 60 días corridos"
MANT_LONG = "mantener la oferta durante 60 días corridos desde la apertura de sobres"
GAR = "Los oferentes deberán constituir una garantía del 5 % del monto."
GAR_QUOTE = "constituir una garantía del 5 % del monto"
GAR_TOTAL = GAR_QUOTE + " total"
PAGO = "El pago se efectuará a los 90 días corridos de la factura."
PAGO_QUOTE = "se efectuará a los 90 días corridos de la factura"


# --- La regla, sin base ------------------------------------------------------------------


def row(key, text, flag=""):
    """Una fila `(unidad, Found)` cuyo tramo es `text` y cuyo fragmento es todo el texto."""
    segment = SimpleNamespace(pk=abs(hash(key)) % 10**6, key=key, text=text)
    return SimpleNamespace(segment=segment), Found("formal", (0, len(text)), flag)


def merged_keys(result):
    return [(p["queda"]["segment"], p["repetida"]["segment"], p["motivo"])
            for p in result.pairs]


def test_equal_text_in_other_segments_is_merged_keeping_the_first():
    """REQ-033: dos filas con el mismo fragmento en tramos distintos dan una fila; queda la
    primera en el orden del pliego y la otra pasa a ser su cita repetida."""
    first, second = row("a/1", MANT_QUOTE), row("b/1", MANT_QUOTE.upper())
    result = dedup.unify([first, second], 0.9)
    assert result.body == [first]
    assert result.repeated == {id(first[1]): [second]}
    assert merged_keys(result) == [("a/1", "b/1", "igual")]


def test_normalization_ignores_accents_case_spaces_and_punctuation():
    """REQ-033: el texto se compara sin tildes, en minúsculas y con espacios y signos
    colapsados."""
    assert dedup.normalize("  El  PLAZO,  de pagó: 30 días. ") == "el plazo de pago 30 dias"
    result = dedup.unify([row("a", "Plazo de pago: 30 días."),
                          row("b", "plazo  de pago 30 dias")], 0.9)
    assert len(result.body) == 1


def test_a_row_contained_in_another_is_merged():
    """REQ-033: una fila cuyo texto está contenido en el de otra, que no le agrega una
    condición (solo una palabra suelta), se une a ella."""
    first = row("a", "garantía de mantenimiento de oferta del 5 % del monto")
    second = row("b", "la garantía de mantenimiento de oferta del 5 % del monto total")
    result = dedup.unify([first, second], 0.9)
    assert result.body == [first]
    assert merged_keys(result) == [("a", "b", "contenida")]


def test_a_very_short_fragment_is_not_merged_by_containment():
    """REQ-033: un fragmento de una o dos palabras está en cualquier fila y no se une."""
    result = dedup.unify([row("a", "garantía"), row("b", "garantía del cinco por ciento")],
                         0.9)
    assert len(result.body) == 2


def test_similar_words_merge_only_from_the_threshold():
    """REQ-033: la similitud de palabras (sin las de uso común) une desde el umbral."""
    a = row("a", "El oferente deberá presentar la constancia de inscripción vigente en el "
                 "registro de proveedores del organismo contratante")
    b = row("b", "El oferente deberá presentar constancia de inscripción vigente en el "
                 "registro de proveedores del organismo contratante hoy")
    assert len(dedup.unify([a, b], 0.7).body) == 1
    assert len(dedup.unify([a, b], 0.99).body) == 2


def test_distinct_conditions_do_not_merge():
    """REQ-033: dos condiciones distintas no se unen."""
    assert len(dedup.unify([row("a", GAR_QUOTE), row("b", PAGO_QUOTE)], 0.9).body) == 2


def test_two_rows_of_one_segment_with_disjoint_quotes_are_not_merged():
    """REQ-033: dos filas de un mismo tramo con citas que no se superponen son condiciones
    distintas, aunque el texto sea igual."""
    text = "Se acepta moneda nacional. Se acepta moneda nacional."
    unit = SimpleNamespace(segment=SimpleNamespace(pk=7, key="a", text=text))
    one, two = (unit, Found("economico", (0, 25))), (unit, Found("economico", (26, 51)))
    assert len(dedup.unify([one, two], 0.9).body) == 2


def test_wide_quotes_are_neither_merged_nor_absorb_others():
    """REQ-033: una cita amplia (el tramo entero) no se junta con otra fila, entre primera o
    segunda."""
    wide, other = row("a", MANT_QUOTE, flag=WIDE), row("b", MANT_QUOTE)
    assert len(dedup.unify([wide, other], 0.9).body) == 2
    assert len(dedup.unify([other, row("c", MANT_QUOTE, flag=WIDE)], 0.9).body) == 2


LONG = ("Los oferentes {} subcontratar parcialmente la prestación objeto de la contratación "
        "con terceros inscriptos en el registro de proveedores del organismo contratante, "
        "siempre que la documentación respaldatoria esté completa, actualizada, legible y "
        "presentada en la sede central del organismo dentro del plazo establecido para la "
        "recepción de las ofertas, {}")
ADVERSE = [
    ("negación y afirmación, frase larga",
     LONG.format("podrán", "durante la ejecución"), LONG.format("no podrán", "durante la ejecución")),
    ("afirmación contenida en la negación",
     "podrá subcontratar parcialmente la prestación",
     "no podrá subcontratar parcialmente la prestación"),
    ("60 contra 90 días en un párrafo largo",
     LONG.format("podrán", "con validez de 60 días"), LONG.format("podrán", "con validez de 90 días")),
    ("deberán contra no deberán",
     LONG.format("deberán", "y firmada"), LONG.format("no deberán", "y firmada")),
    ("firmada contra sin firmar",
     LONG.format("deberán", "firmada por el oferente"), LONG.format("deberán", "sin firmar por el oferente")),
    ("sujeto y objeto intercambiados",
     "El organismo contratante notificará al oferente adjudicatario la orden de compra emitida",
     "El oferente adjudicatario notificará al organismo contratante la orden de compra emitida"),
    ("calificador agregado",
     "garantía del 5 % del monto",
     "garantía del 5 % del monto de cada renglón cotizado y adjudicado por separado"),
    ("10 % contra 20 %", "garantía del 10 % del monto adjudicado", "garantía del 20 % del monto adjudicado"),
    ("un modal contra otro",
     LONG.format("deberán", "durante la ejecución"), LONG.format("podrán", "durante la ejecución")),
    ("mínimo contra máximo", "plazo mínimo de entrega de bienes", "plazo máximo de entrega de bienes"),
]


@pytest.mark.parametrize("label,one,two", ADVERSE, ids=[a[0] for a in ADVERSE])
def test_conditions_that_differ_in_figures_negations_modals_or_order_stay_apart(
        label, one, two):
    """REQ-033: la unificación es conservadora; ante la duda no une. Dos condiciones que se
    distinguen por una cifra, una negación, un modal, un calificador o el orden de las
    palabras quedan como filas separadas, en cualquier orden de entrada."""
    assert len(dedup.unify([row("a", one), row("b", two)], 0.9).body) == 2
    assert len(dedup.unify([row("a", two), row("b", one)], 0.9).body) == 2


def test_a_long_phrase_equal_but_for_punctuation_still_merges():
    """REQ-033: la cautela no impide unir lo realmente igual."""
    text = LONG.format("podrán", "durante la ejecución")
    assert len(dedup.unify([row("a", text), row("b", text.upper() + ".")], 0.9).body) == 1


def test_threshold_one_merges_only_equal_texts():
    """REQ-033: con el umbral en 1,0 solo se unen las filas de texto igual."""
    equal = dedup.unify([row("a", MANT_QUOTE), row("b", MANT_QUOTE)], 1.0)
    contained = dedup.unify([row("a", GAR_QUOTE), row("b", GAR_TOTAL)], 1.0)
    assert len(equal.body) == 1
    assert len(contained.body) == 2


def test_a_third_repetition_joins_the_same_group():
    """REQ-033: una tercera fila con la misma condición suma otra cita a la misma fila."""
    rows = [row("a", MANT_QUOTE), row("b", MANT_QUOTE), row("c", MANT_QUOTE)]
    result = dedup.unify(rows, 0.9)
    assert result.body == [rows[0]]
    assert result.repeated[id(rows[0][1])] == rows[1:]


# --- En el proceso -----------------------------------------------------------------------


def pliego(*clauses):
    """Un pliego con una sección de condiciones, una cláusula por texto, y una sección
    técnica con dos renglones."""
    return tender_pdf([
        [para("SECCIÓN I - CONDICIONES PARTICULARES"),
         *[para(f"{n}. CLÁUSULA {n}", *textwrap.wrap(f"{n}.1. {text}", 78))
           for n, text in enumerate(clauses, start=1)]],
        [para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
         para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", "1.1. Bolsa de veinte kilogramos."),
         para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", "2.1. Bolsa de diez kilogramos.")],
    ])


def run_with(user, pdf):
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf)
    requested, job = propose(user, procedure)
    assert job.status == "done", job.error
    return requested.run


def formal_rows(run):
    return list(m.Requirement.objects.filter(version=run.version)
                .exclude(category="tecnico").order_by("number"))


def check_literal(run):
    quotes = m.RequirementQuote.objects.filter(
        requirement__version=run.version).select_related("segment__reading")
    assert quotes
    for quote in quotes:
        canonical = quote.segment.reading.canonical_text
        assert canonical[quote.char_start:quote.char_end] == quote.text


def test_the_same_fragment_in_two_segments_gives_one_row_with_two_quotes(
        operator_user, script):
    """REQ-025, REQ-033: el mismo fragmento en dos tramos da una fila con dos citas, cada
    una igual al recorte del texto canónico; la segunda es una cita `repetida`."""
    script.when(MANT, item([(MANT_QUOTE, "formal")]))
    script.when(GAR, item([(GAR_QUOTE, "economico")]))

    run = run_with(operator_user, pliego(MANT, GAR, MANT))

    rows = formal_rows(run)
    assert len(rows) == 2
    mant = rows[0]
    assert [(q.segment.key, q.scope) for q in mant.quotes.order_by("order")] == [
        ("sec-i/1.1", ""), ("sec-i/3.1", "repetida")]
    assert [q.text for q in mant.quotes.all()] == [MANT_QUOTE, MANT_QUOTE]
    assert [q["scope"] for q in mant.proposed["quotes"]] == ["", "repetida"]
    assert len(rows[1].quotes.all()) == 1
    check_literal(run)
    assert run.counts["unification"]["merged"] == 1
    assert run.counts["unification"]["rows_before"] == 3
    assert run.counts["unification"]["rows_after"] == 2


def test_a_row_contained_in_another_is_merged_in_the_process(operator_user, script):
    """REQ-033: una fila contenida en otra se une; queda la primera del pliego."""
    script.when(GAR, item([(GAR_QUOTE, "economico")]))
    script.when("monto total", item([(GAR_TOTAL, "economico")]))

    run = run_with(operator_user, pliego(GAR, GAR.replace("monto.", "monto total.")))

    rows = formal_rows(run)
    assert len(rows) == 1
    assert [q.scope for q in rows[0].quotes.order_by("order")] == ["", "repetida"]
    check_literal(run)


def test_two_conditions_of_one_segment_stay_apart(operator_user, script):
    """REQ-033: dos condiciones distintas de un mismo tramo no se unen."""
    script.when(GAR, item([(GAR_QUOTE, "economico"), (PAGO_QUOTE, "economico")]))

    run = run_with(operator_user, pliego(f"{GAR} {PAGO}"))

    assert len(formal_rows(run)) == 2
    assert not m.RequirementQuote.objects.filter(
        requirement__version=run.version, scope="repetida").exists()
    assert run.counts["unification"]["merged"] == 0


def test_technical_rows_stay_as_they_are(operator_user, script):
    """REQ-033: las filas técnicas no se tocan: una por renglón, sin citas repetidas."""
    script.when(MANT, item([(MANT_QUOTE, "formal")]))

    run = run_with(operator_user, pliego(MANT, MANT))

    technical = m.Requirement.objects.filter(version=run.version, category="tecnico")
    assert technical.count() == 2
    assert not m.RequirementQuote.objects.filter(
        requirement__in=technical, scope="repetida").exists()
    assert len(formal_rows(run)) == 1


def test_the_step_lists_the_pairs_and_the_threshold(operator_user, script):
    """REQ-033: el registro de la pasada (`unificacion`) tiene la versión de la regla, el
    umbral y los pares unidos."""
    script.when(MANT, item([(MANT_QUOTE, "formal")]))

    run = run_with(operator_user, pliego(MANT, GAR, MANT))

    step = m.RunStep.objects.get(run=run, pass_name="unificacion")
    assert step.request["rule"] == dedup.RULE_VERSION
    assert step.request["min_similarity"] == 0.9
    assert step.parsed["merged"] == 1
    pair = step.parsed["pairs"][0]
    assert pair["queda"]["segment"] == "sec-i/1.1"
    assert pair["repetida"]["segment"] == "sec-i/3.1"
    assert pair["repetida"]["text"] == MANT_QUOTE
    assert run.parameters["dedup_min_similarity"] == 0.9
    assert "unificacion" in run.parameters["passes"]


def test_threshold_one_in_the_process_merges_only_equal_texts(
        operator_user, script, settings):
    """REQ-033: con `DEDUP_MIN_SIMILARITY` en 1,0 la fila contenida no se une; la igual sí."""
    settings.DEDUP_MIN_SIMILARITY = 1.0
    script.when(GAR, item([(GAR_QUOTE, "economico")]))
    script.when("monto total", item([(GAR_TOTAL, "economico")]))

    run = run_with(operator_user, pliego(
        GAR, GAR.replace("monto.", "monto total."), GAR))

    rows = formal_rows(run)
    assert len(rows) == 2
    assert [q.scope for q in rows[0].quotes.order_by("order")] == ["", "repetida"]
    assert run.counts["unification"]["min_similarity"] == 1.0
