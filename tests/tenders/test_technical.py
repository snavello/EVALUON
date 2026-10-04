"""Filas técnicas por renglón y sus controles (REQ-024, REQ-025, REQ-028; plan 003, "Filas
técnicas por renglón" y "Qué es un requisito y su clase"; ADR-0019, decisión 3 bis;
T-073).

Pliegos sintéticos y el doble del modelo con guion (`tests/tenders/scripted.py`); sin
datos de personas (P4).
"""

from types import SimpleNamespace

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import technical
from evaluon.tenders.proposal.extraction import ALL_ITEMS, Unit
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    ENTREGA,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offer_every_level(settings):
    """Estas pruebas recorren las pasadas de los tres niveles, también la de exigente, que
    existe pero no se ofrece (T-085)."""
    settings.MATRIX_LEVELS_OFFERED = ("media", "alta", "exigente")


@pytest.fixture
def three(operator_user, script):
    """El pliego de tres renglones leído; el modelo marca la entrega (fuera de las secciones
    técnicas) como técnica para todos los renglones y descarta el resto."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, three_items_pdf())
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))
    return procedure, document


def rows_of(run):
    """Las filas técnicas de la propuesta: `{renglón: [(clave, alcance), …]}`."""
    rows = {}
    for requirement in m.Requirement.objects.filter(
            version=run.version, category="tecnico").order_by("number"):
        number = requirement.items[0] if requirement.items else None
        rows[number] = [(q.segment.key, q.scope) for q in
                        requirement.quotes.order_by("order").select_related("segment")]
    return rows


def pending_of(run):
    return {p.segment.key: p.reason for p in
            m.PendingItem.objects.filter(version=run.version).select_related("segment")}


# --- Una fila por renglón (REQ-024, REQ-025) -----------------------------------------------


def test_three_items_make_three_rows_with_their_own_and_general_segments(operator_user,
                                                                         three):
    """REQ-024, REQ-025: un pliego de tres renglones da tres filas técnicas, cada una con
    los tramos propios de su renglón y los generales, en el orden del pliego."""
    procedure, _ = three

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert rows_of(requested.run) == {
        1: [("sec-i/3.1", "general"), ("sec-ii/1.1", "general"),
            ("sec-iii/1", "propia"), ("sec-iii/1.1", "propia")],
        2: [("sec-i/3.1", "general"), ("sec-ii/1.1", "general"),
            ("sec-iii/2", "propia"), ("sec-iii/2.1", "propia"),
            ("sec-iii/2.2", "propia")],
        3: [("sec-i/3.1", "general"), ("sec-ii/1.1", "general"),
            ("sec-iii/3", "propia")],
    }
    technical_rows = requested.run.counts["technical_rows"]
    assert technical_rows == [
        {"item": 1, "quotes": 4, "own": 2, "general": 2},
        {"item": 2, "quotes": 5, "own": 3, "general": 2},
        {"item": 3, "quotes": 3, "own": 1, "general": 2},
    ]
    assert requested.run.counts["items"] == [1, 2, 3]


def test_each_quote_is_the_whole_segment_and_equals_the_canonical_slice(operator_user,
                                                                        three):
    """REQ-025: la cita de una fila técnica es el tramo entero y su texto es igual al
    recorte del texto canónico."""
    procedure, document = three

    requested, _ = propose(operator_user, procedure)

    reading = document.readings.get()
    quotes = m.RequirementQuote.objects.filter(
        requirement__version=requested.run.version, requirement__category="tecnico")
    assert quotes.count() == 12
    for quote in quotes.select_related("segment"):
        segment = quote.segment
        assert (quote.char_start, quote.char_end) == (segment.char_start, segment.char_end)
        assert quote.text == segment.text
        assert reading.canonical_text[quote.char_start:quote.char_end] == quote.text
        assert quote.quote_flag == ""
        assert quote.scope in ("propia", "general")


def test_technical_requirement_is_made_by_a_rule(operator_user, three):
    """REQ-024: la fila técnica la arma una regla: sin pedido al modelo ni pasadas,
    un renglón, y numerada después de los formales y económicos."""
    procedure, _ = three

    requested, _ = propose(operator_user, procedure)

    requirements = list(m.Requirement.objects.filter(version=requested.run.version)
                        .order_by("number"))
    assert [(r.number, r.category, r.items) for r in requirements] == [
        (1, "tecnico", [1]), (2, "tecnico", [2]), (3, "tecnico", [3])]
    for requirement in requirements:
        assert requirement.step is None and requirement.passes == []
        assert requirement.origin == "propuesto" and requirement.state == "propuesto"
        assert requirement.proposed["category"] == "tecnico"
        assert requirement.proposed["items"] == requirement.items
        assert [q["scope"] for q in requirement.proposed["quotes"]] == [
            q.scope for q in requirement.quotes.order_by("order")]


def test_technical_rows_follow_the_formal_and_economic_requirements(operator_user, three,
                                                                    script):
    """REQ-024: los formales y económicos van primero; las filas técnicas, después."""
    procedure, _ = three
    script.when("5 %", item([("constituir una garantía del 5 % del monto", "economico")]))

    requested, _ = propose(operator_user, procedure)

    categories = list(m.Requirement.objects.filter(version=requested.run.version)
                      .order_by("number").values_list("category", flat=True))
    assert categories == ["economico", "tecnico", "tecnico", "tecnico"]


# --- Tramos marcados por el modelo (REQ-024) ----------------------------------------------


def test_segment_marked_for_all_enters_the_three_rows(operator_user, three):
    """REQ-024: un tramo marcado `todos` entra en la fila de cada renglón, como cita
    general; el tramo queda con disposición técnica."""
    procedure, _ = three

    requested, _ = propose(operator_user, procedure)

    for number, quotes in rows_of(requested.run).items():
        assert ("sec-i/3.1", "general") in quotes, number
    disposition = m.Disposition.objects.get(run=requested.run, segment__key="sec-i/3.1")
    assert disposition.outcome == "tecnico" and disposition.source == "modelo"


def test_segment_marked_for_some_items_is_own_in_those_rows_only(operator_user, three,
                                                                 script):
    """REQ-024: un tramo marcado para algunos renglones va como cita propia en cada uno de
    ellos y en ningún otro."""
    procedure, _ = three
    script.when(ENTREGA, item(technical=["2", "3"]))

    requested, _ = propose(operator_user, procedure)

    rows = rows_of(requested.run)
    assert ("sec-i/3.1", "propia") not in rows[1]
    assert ("sec-i/3.1", "general") not in rows[1]
    assert ("sec-i/3.1", "propia") in rows[2]
    assert ("sec-i/3.1", "propia") in rows[3]
    # El renglón 3 ya tiene un tramo propio más allá de su encabezado: no queda pendiente.
    assert "sec-iii/3" not in pending_of(requested.run)


def test_mark_for_a_number_that_is_not_an_item_goes_general_and_is_noted(operator_user,
                                                                         three,
                                                                         script):
    """REQ-024: una marca para un número que no es de ningún renglón no se pierde: el tramo
    va como general (ante la duda, de más) y se anota la anomalía."""
    procedure, _ = three
    script.when(ENTREGA, item(technical=["9"]))

    requested, _ = propose(operator_user, procedure)

    for quotes in rows_of(requested.run).values():
        assert ("sec-i/3.1", "general") in quotes
    assert any(a["type"] == "tecnico_renglon_desconocido" and a["renglon"] == 9
               for a in requested.run.anomalies)


def test_segment_with_requirements_and_a_technical_mark_is_in_a_row_too(operator_user,
                                                                        three,
                                                                        script):
    """REQ-024: un tramo con requisitos formales o económicos y además marcado como técnico
    queda `requisitos` y entra igual en las filas."""
    procedure, _ = three
    script.when(ENTREGA, item([("dentro de los 15 días hábiles", "economico")],
                              technical=[ALL_ITEMS]))

    requested, _ = propose(operator_user, procedure)

    disposition = m.Disposition.objects.get(run=requested.run, segment__key="sec-i/3.1")
    assert disposition.outcome == "requisitos"
    assert ("sec-i/3.1", "general") in rows_of(requested.run)[1]
    assert m.Requirement.objects.filter(version=requested.run.version,
                                        category="economico").count() == 1


# --- Renglón sin especificaciones (REQ-028) -----------------------------------------------


def test_item_without_specifications_keeps_its_row_and_a_pending(operator_user, three):
    """REQ-028: un renglón sin tramos propios más allá de su encabezado conserva su fila
    (con los tramos generales) y deja un pendiente en el tramo de su encabezado."""
    procedure, _ = three

    requested, _ = propose(operator_user, procedure)

    # La garantía descartada por el modelo tiene marcadores de obligación: es otro pendiente.
    assert pending_of(requested.run) == {"sec-i/1.1": "marcadores",
                                         "sec-iii/3": "renglon_sin_especificaciones"}
    assert 3 in rows_of(requested.run)
    assert [key for key, scope in rows_of(requested.run)[3] if scope == "general"] == [
        "sec-i/3.1", "sec-ii/1.1"]


def test_item_with_specifications_has_no_pending(operator_user, script):
    """REQ-028: con especificaciones en los tres renglones no queda ningún pendiente por
    esa causa."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf(third_item_specs=True))

    requested, _ = propose(operator_user, procedure)

    assert "renglon_sin_especificaciones" not in pending_of(requested.run).values()
    assert dict(rows_of(requested.run)[3])["sec-iii/3.1"] == "propia"


# --- Tramos de un renglón que el modelo descartó (REQ-024) ----------------------------------


def renglones_in_conditions_pdf():
    return tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", "1.1. Se cotiza por kilogramo."),
        para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", "2.1. Se cotiza por unidad."),
    ]], header=None)


def test_segment_of_an_item_that_the_model_discarded_enters_its_row(operator_user,
                                                                   script):
    """REQ-024: un tramo que cuelga de un renglón y que el modelo descartó entra igual en la
    fila de su renglón (ante la duda, de más); queda con disposición técnica y la anomalía
    anotada, y no pasa por la regla de marcadores."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, renglones_in_conditions_pdf())
    script.when("por kilogramo", item(discard="dato_procedimiento"))
    script.when("por unidad", item(technical=[ALL_ITEMS]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert rows_of(requested.run) == {
        1: [("sec-i/1.1", "propia")],
        2: [("sec-i/2.1", "propia")],
    }
    by_key = {d.segment.key: d for d in
              m.Disposition.objects.filter(run=requested.run).select_related("segment")}
    assert by_key["sec-i/1.1"].outcome == "tecnico" and by_key["sec-i/1.1"].source == "modelo"
    assert by_key["sec-i/1.1"].discard_reason == ""
    assert any(a["type"] == "descartado_en_renglon" and a["key"] == "sec-i/1.1"
               for a in requested.run.anomalies)
    assert pending_of(requested.run) == {}


def test_requirements_of_an_item_segment_carry_that_item(operator_user, script):
    """REQ-024: un requisito formal o económico de un tramo de un renglón lleva ese
    renglón, y no los que el modelo diga."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, renglones_in_conditions_pdf())
    script.when("por kilogramo", item([("Se cotiza por kilogramo.", "economico")]))

    requested, _ = propose(operator_user, procedure)

    requirement = m.Requirement.objects.get(version=requested.run.version,
                                            category="economico")
    assert requirement.items == [1]


# --- Pliego sin renglones (REQ-024) ---------------------------------------------------------


def specs_without_items_pdf():
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. ENTREGA", f"1.1. {ENTREGA}"),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS"),
            para("1. CARACTERÍSTICAS", "1.1. Envase cerrado y rotulado."),
        ],
    ])


def test_tender_without_items_has_one_row_without_item(operator_user, script):
    """REQ-024: si no hay renglones, el pliego tiene una sola fila técnica, sin renglón, con
    todos los tramos técnicos como citas propias; se anota que hay secciones técnicas
    sin renglones."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, specs_without_items_pdf())
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert rows_of(requested.run) == {
        None: [("sec-i/1.1", "propia"), ("sec-ii/1.1", "propia")]}
    requirement = m.Requirement.objects.get(version=requested.run.version,
                                            category="tecnico")
    assert requirement.items == []
    assert any(a["type"] == "secciones_tecnicas_sin_renglones"
               for a in requested.run.anomalies)
    assert pending_of(requested.run) == {}


def test_tender_without_technical_segments_has_no_technical_row(operator_user, script):
    """REQ-024: un pliego sin renglones y sin nada técnico no inventa una fila técnica."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PLAZO", "1.1. La oferta se mantiene sesenta días."),
    ]], header=None))

    requested, _ = propose(operator_user, procedure)

    assert rows_of(requested.run) == {}
    assert not any(a["type"] == "secciones_tecnicas_sin_renglones"
                   for a in requested.run.anomalies)


# --- Igual en los tres niveles (REQ-030) -----------------------------------------------------


def test_technical_rows_are_the_same_in_every_level(operator_user, script):
    """REQ-030: las filas técnicas las arma una regla: son las mismas en los tres niveles
    para el mismo pliego."""
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))
    results = {}
    for level in ("media", "alta", "exigente"):
        procedure = make_procedure(operator_user)
        load_and_read(operator_user, procedure, three_items_pdf())
        requested, job = propose(operator_user, procedure, level=level)
        assert job.status == "done", job.error
        results[level] = (rows_of(requested.run), pending_of(requested.run))

    assert results["media"] == results["alta"] == results["exigente"]
    assert len(results["media"][0]) == 3


# --- La regla sola ---------------------------------------------------------------------------


def make_unit(pk, position, *, items=(), key=None):
    segment = SimpleNamespace(pk=pk, items=list(items), key=key or f"k{pk}")
    return Unit(segment=segment, document_title="Pliego", position=position)


def test_rows_are_in_pliego_order_and_header_only_item_is_pending():
    """REQ-024, REQ-028: las citas van en el orden del pliego; el renglón cuyo único tramo
    propio es su encabezado queda pendiente en ese encabezado."""
    header1, header2 = make_unit(1, 10, items=[1]), make_unit(2, 20, items=[2])
    spec1 = make_unit(3, 11, items=[1])
    general = make_unit(4, 5)
    anomalies = []

    rows = technical.build_rows(
        [(1, header1.segment), (2, header2.segment)],
        [technical.Contribution(spec1), technical.Contribution(header2),
         technical.Contribution(general), technical.Contribution(header1)],
        anomalies,
    )

    assert [(r.number, [(q.segment.pk, q.scope) for q in r.quotes]) for r in rows] == [
        (1, [(4, "general"), (1, "propia"), (3, "propia")]),
        (2, [(4, "general"), (2, "propia")]),
    ]
    assert rows[0].pending is None
    assert rows[1].pending is header2.segment
    assert anomalies == []


def test_segment_of_an_unknown_item_is_noted_and_goes_general():
    """REQ-024: un tramo que cuelga de un renglón que la lectura no reconoce no se pierde."""
    header = make_unit(1, 1, items=[1])
    stray = make_unit(2, 2, items=[7])
    anomalies = []

    rows = technical.build_rows([(1, header.segment)],
                                [technical.Contribution(header),
                                 technical.Contribution(stray)], anomalies)

    assert [(q.segment.pk, q.scope) for q in rows[0].quotes] == [(1, "propia"),
                                                                 (2, "general")]
    assert anomalies[0]["type"] == "tecnico_renglon_desconocido"
    assert anomalies[0]["renglon"] == 7


def test_reading_items_give_each_item_its_header_once():
    """REQ-024: los renglones del pliego salen de `items` de las lecturas; si dos lecturas
    traen el mismo número, vale el de la primera."""
    first = SimpleNamespace(items=[{"number": 2, "key": "a"}, {"number": 1, "key": "b"}])
    second = SimpleNamespace(items=[{"number": 2, "key": "c"}, {"number": 3, "key": "d"}])
    segments = {"a": "A", "b": "B", "c": "C", "d": "D"}

    assert technical.reading_items([(first, segments), (second, segments)]) == [
        (1, "B"), (2, "A"), (3, "D")]
