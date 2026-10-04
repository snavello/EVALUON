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
    result = dedup.unify([first, second], 0.9, containment=True)
    assert result.body == [first]
    assert result.repeated == {id(first[1]): [second]}
    assert merged_keys(result) == [("a/1", "b/1", "igual")]


def test_normalization_ignores_accents_case_spaces_and_punctuation():
    """REQ-033: el texto se compara sin tildes, en minúsculas y con espacios y signos
    colapsados."""
    assert dedup.normalize("  El  PLAZO,  de pagó: 30 días. ") == "el plazo de pago 30 dias"
    result = dedup.unify([row("a", "Plazo de pago: 30 días."),
                          row("b", "plazo  de pago 30 dias")])
    assert len(result.body) == 1


def test_a_row_contained_in_another_is_merged():
    """REQ-033: una fila cuyo texto está contenido en el de otra, que no le agrega una
    condición (solo una palabra suelta), se une a ella."""
    first = row("a", "garantía de mantenimiento de oferta del 5 % del monto")
    second = row("b", "la garantía de mantenimiento de oferta del 5 % del monto total")
    result = dedup.unify([first, second], 0.9, containment=True)
    assert result.body == [first]
    assert merged_keys(result) == [("a", "b", "contenida")]


def test_a_very_short_fragment_is_not_merged_by_containment():
    """REQ-033: un fragmento de una o dos palabras está en cualquier fila y no se une."""
    result = dedup.unify([row("a", "garantía"), row("b", "garantía del cinco por ciento")],
                         0.9, containment=True)
    assert len(result.body) == 2


def test_similar_words_merge_only_from_the_threshold():
    """REQ-033: la similitud de palabras (sin las de uso común) une desde el umbral."""
    a = row("a", "El oferente deberá presentar la constancia de inscripción vigente en el "
                 "registro de proveedores del organismo contratante")
    b = row("b", "El oferente deberá presentar constancia de inscripción vigente en el "
                 "registro de proveedores del organismo contratante hoy")
    assert len(dedup.unify([a, b], 0.7, containment=True).body) == 1
    assert len(dedup.unify([a, b], 0.99, containment=True).body) == 2


def test_distinct_conditions_do_not_merge():
    """REQ-033: dos condiciones distintas no se unen."""
    assert len(dedup.unify([row("a", GAR_QUOTE), row("b", PAGO_QUOTE)], 0.9, containment=True).body) == 2


def test_two_rows_of_one_segment_with_disjoint_quotes_are_not_merged():
    """REQ-033: dos filas de un mismo tramo con citas que no se superponen son condiciones
    distintas, aunque el texto sea igual."""
    text = "Se acepta moneda nacional. Se acepta moneda nacional."
    unit = SimpleNamespace(segment=SimpleNamespace(pk=7, key="a", text=text))
    one, two = (unit, Found("economico", (0, 25))), (unit, Found("economico", (26, 51)))
    assert len(dedup.unify([one, two], 0.9, containment=True).body) == 2


def test_wide_quotes_are_neither_merged_nor_absorb_others():
    """REQ-033: una cita amplia (el tramo entero) no se junta con otra fila, entre primera o
    segunda."""
    wide, other = row("a", MANT_QUOTE, flag=WIDE), row("b", MANT_QUOTE)
    assert len(dedup.unify([wide, other], 0.9, containment=True).body) == 2
    assert len(dedup.unify([other, row("c", MANT_QUOTE, flag=WIDE)], 0.9, containment=True).body) == 2


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
    for options in ({}, {"threshold": 0.9, "containment": True}):
        assert len(dedup.unify([row("a", one), row("b", two)], **options).body) == 2
        assert len(dedup.unify([row("a", two), row("b", one)], **options).body) == 2


def test_a_long_phrase_equal_but_for_punctuation_still_merges():
    """REQ-033: la cautela no impide unir lo realmente igual."""
    text = LONG.format("podrán", "durante la ejecución")
    assert len(dedup.unify([row("a", text), row("b", text.upper() + ".")]).body) == 1


def test_by_default_only_identical_normalized_texts_are_merged():
    """REQ-033: por omisión (similitud y contención apagadas) solo se unen los textos
    idénticos una vez normalizados; la contención y la similitud no."""
    assert dedup.MIN_SIMILARITY == 1.0 and dedup.USE_CONTAINMENT is False
    equal = dedup.unify([row("a", MANT_QUOTE), row("b", MANT_QUOTE)])
    contained = dedup.unify([row("a", GAR_QUOTE), row("b", GAR_TOTAL)])
    assert len(equal.body) == 1
    assert len(contained.body) == 2
    near = ("El oferente deberá presentar la constancia de inscripción vigente en el registro "
            "de proveedores del organismo contratante")
    assert len(dedup.unify([row("a", near), row("b", near + " hoy")]).body) == 2


@pytest.mark.parametrize("variant", [
    "  LOS OFERENTES   DEBERÁN mantener la oferta; durante 60 días corridos.",
    "a) Los oferentes deberán mantener la oferta durante 60 días corridos",
    "(b)  Los oferentes deberán mantener la oferta, durante 60 dias corridos.",
])
def test_by_default_identical_texts_merge_whatever_the_form(variant):
    """REQ-033: mayúsculas, tildes, puntuación, espacios, viñeta ("a)") y punto final no
    cuentan: lo idéntico normalizado se une por omisión."""
    result = dedup.unify([row("a", MANT), row("b", variant)])
    assert len(result.body) == 1
    assert merged_keys(result) == [("a", "b", "igual")]


UNITS = [
    ("horas contra días", "48 horas hábiles", "48 días hábiles"),
    ("kg contra g", "5 kg por bulto", "5 g por bulto"),
    ("mm contra cm", "5 mm de espesor", "5 cm de espesor"),
    ("pesos contra dólares", "5000 pesos", "5000 dólares"),
    ("y contra o", "acreditar experiencia y antecedentes",
     "acreditar experiencia o antecedentes"),
    ("ni contra y", "no presentar deudas ni sanciones", "no presentar deudas y sanciones"),
]


@pytest.mark.parametrize("label,one,two", UNITS, ids=[u[0] for u in UNITS])
def test_a_different_unit_or_conjunction_keeps_rows_apart(label, one, two):
    """REQ-033: la unidad que sigue a una cifra y las conjunciones ("y", "o", "ni") forman
    parte de la firma: con la similitud y la contención encendidas, en una frase larga, las
    filas quedan separadas."""
    frame = ("El oferente deberá entregar los bienes en el depósito central del organismo "
             "contratante dentro del plazo de {} contados desde la recepción de la orden de "
             "compra emitida por el área requirente")
    for first, second in ((one, two), (two, one)):
        for options in ({}, {"threshold": 0.9, "containment": True}):
            result = dedup.unify([row("a", frame.format(first)),
                                  row("b", frame.format(second))], **options)
            assert len(result.body) == 2


def test_the_subject_changing_is_not_merged_by_default():
    """REQ-033: "organismo" contra "ministerio" en un párrafo largo no se une por omisión."""
    text = ("El {} contratante notificará la adjudicación a todos los oferentes dentro del "
            "plazo establecido en el pliego de bases y condiciones particulares")
    assert len(dedup.unify([row("a", text.format("organismo")),
                            row("b", text.format("ministerio"))]).body) == 2


def test_the_floor_of_three_words_applies_to_containment():
    """REQ-033: con la contención encendida, un fragmento de menos de 3 palabras contenido
    en otra fila no la une, aunque sobre una sola palabra."""
    options = {"threshold": 1.0, "containment": True}
    assert len(dedup.unify([row("a", "plazo entrega"), row("b", "plazo entrega inmediata")],
                           **options).body) == 2
    assert len(dedup.unify([row("a", "plazo de entrega"),
                            row("b", "plazo de entrega inmediata")], **options).body) == 1


def test_containment_allows_at_most_one_extra_content_word():
    """REQ-033: con la contención encendida, la fila más larga no puede sumar más de una
    palabra con contenido (`MAX_EXTRA_WORDS`)."""
    options = {"threshold": 1.0, "containment": True}
    base = "garantía de mantenimiento de oferta del 5 % del monto"
    assert len(dedup.unify([row("a", base), row("b", base + " total")], **options).body) == 1
    assert len(dedup.unify([row("a", base), row("b", base + " total adjudicado")],
                           **options).body) == 2


def test_similar_rows_of_one_segment_with_disjoint_quotes_stay_apart():
    """REQ-033: con la similitud encendida, dos filas muy parecidas de un mismo tramo, con
    citas que no se superponen, son condiciones distintas y no se unen."""
    text = "Se acepta moneda nacional del país. Se acepta moneda nacional del pais"
    unit = SimpleNamespace(segment=SimpleNamespace(pk=9, key="a", text=text))
    one, two = (unit, Found("economico", (0, 34))), (unit, Found("economico", (36, 70)))
    assert len(dedup.unify([one, two], 0.9, containment=True).body) == 2
    other = SimpleNamespace(segment=SimpleNamespace(pk=10, key="b", text=text))
    moved = (other, Found("economico", (36, 70)))
    assert len(dedup.unify([one, moved], 0.9, containment=True).body) == 1


def test_a_third_repetition_joins_the_same_group():
    """REQ-033: una tercera fila con la misma condición suma otra cita a la misma fila."""
    rows = [row("a", MANT_QUOTE), row("b", MANT_QUOTE), row("c", MANT_QUOTE)]
    result = dedup.unify(rows, 0.9, containment=True)
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


@pytest.fixture
def loose(monkeypatch):
    """Enciende la similitud y la contención, apagadas por omisión."""
    monkeypatch.setattr(dedup, "MIN_SIMILARITY", 0.9)
    monkeypatch.setattr(dedup, "USE_CONTAINMENT", True)


def test_a_row_contained_in_another_is_merged_in_the_process(operator_user, script, loose):
    """REQ-033: con la contención encendida, una fila contenida en otra se une; queda la
    primera del pliego."""
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
    assert step.request["min_similarity"] == 1.0
    assert step.request["containment"] is False
    assert step.parsed["merged"] == 1
    pair = step.parsed["pairs"][0]
    assert pair["queda"]["segment"] == "sec-i/1.1"
    assert pair["repetida"]["segment"] == "sec-i/3.1"
    assert pair["repetida"]["text"] == MANT_QUOTE
    assert run.parameters["dedup_min_similarity"] == 1.0
    assert run.parameters["dedup_containment"] is False
    assert "unificacion" in run.parameters["passes"]


def test_by_default_a_contained_row_is_not_merged_in_the_process(operator_user, script):
    """REQ-033: por omisión la fila contenida no se une; la idéntica sí."""
    script.when(GAR, item([(GAR_QUOTE, "economico")]))
    script.when("monto total", item([(GAR_TOTAL, "economico")]))

    run = run_with(operator_user, pliego(
        GAR, GAR.replace("monto.", "monto total."), GAR))

    rows = formal_rows(run)
    assert len(rows) == 2
    assert [q.scope for q in rows[0].quotes.order_by("order")] == ["", "repetida"]
    assert run.counts["unification"]["min_similarity"] == 1.0


def test_a_sign_stuck_to_a_digit_keeps_rows_apart():
    """REQ-033: "-5" no es "5": la normalización conserva el signo pegado a una cifra, así
    que "temperatura de -5 grados" y "temperatura de 5 grados" no se unen, ni por omisión ni
    con la similitud encendida, en ambos órdenes."""
    minus = "La temperatura de conservación será de -5 grados centígrados"
    plus = "La temperatura de conservación será de 5 grados centígrados"
    assert dedup.normalize(minus) != dedup.normalize(plus)
    for options in ({}, {"threshold": 0.9, "containment": True}):
        assert len(dedup.unify([row("a", minus), row("b", plus)], **options).body) == 2
        assert len(dedup.unify([row("a", plus), row("b", minus)], **options).body) == 2
    # Un guion entre cifras sigue siendo puntuación.
    assert dedup.normalize("plazo de 10-20 días") == dedup.normalize("plazo de 10 20 días")


def test_the_signature_has_the_figures():
    """REQ-033: con la similitud encendida (sin contención), dos frases largas que solo
    cambian una cifra quedan separadas: la firma lleva las cifras."""
    text = ("El oferente deberá mantener la oferta durante {} días corridos contados desde la "
            "fecha del acto de apertura de sobres, en las condiciones establecidas en el "
            "pliego de bases y condiciones particulares de la contratación")
    one, two = text.format(60), text.format(90)
    assert dedup.signature(dedup.normalize(one)) != dedup.signature(dedup.normalize(two))
    assert len(dedup.unify([row("a", one), row("b", two)], 0.9,
                           containment=False).body) == 2
    assert len(dedup.unify([row("a", one), row("b", one)], 0.9,
                           containment=False).body) == 1
