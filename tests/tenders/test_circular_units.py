"""Unidades de cambio de una circular, aplicadas por clave y sin modelo (REQ-031, REQ-028;
plan 003, "Rediseño de la pasada de circulares", entrega 1; ADR-0023; T-113).

Cada forma del diagnóstico (`verificacion/T-113-diagnostico.md`) con textos inventados que
reproducen su *forma*, no el texto de ningún caso (P4): una cláusula reemplazada con varias
citas, un anexo que deja de ser requisito y la cláusula que manda presentarlo, una lista de
datos del trámite, el par "Donde dice / Debe decir" en tramos separados, un anexo de una norma
externa, una cita común a varios renglones y la cláusula nueva. Los pliegos y circulares son
PDF sintéticos (`tests/tenders/pdfs.py`); el modelo es el doble con guion de
`test_circulars.py`. Las pruebas de partición, de verbos y de coincidencia no necesitan base.
"""

import hashlib
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import circular_units as units
from evaluon.tenders.proposal import circulars
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    PAGO,
    item,
    load_and_read,
    make_procedure,
)
from tests.tenders.test_circulars import (  # noqa: F401  (case es una fixture)
    RAM,
    CircularScript,
    add_circular,
    case,
    narrative_circular,
    requirement_with,
    row_of_item,
    run_proposal,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def script(fake_generation, monkeypatch):
    return CircularScript(fake_generation, monkeypatch)


def model_requests(script, *needles):
    """Los pedidos de circulares al modelo cuyo tramo contiene alguna de las frases."""
    return [r for r in script.requests if any(n in r["tramo"] for n in needles)]


def unit_steps(**filters):
    return list(m.RunStep.objects.filter(pass_name="circulares", request__has_key="unidad",
                                         **filters).order_by("id"))


def add_paras(user, procedure, title, issued_on, *paragraphs):
    """Una circular de párrafos sueltos: cada uno, un tramo (los rótulos "Donde dice" y "Debe
    decir" van en tramos aparte)."""
    return load_and_read(user, procedure, narrative_circular(*paragraphs),
                         kind="circular_modificatoria", title=title, issued_on=issued_on)


def every_segment_has_a_disposition(document, run):
    reading = document.readings.get()
    pks = {s.pk for s in reading.segments.all()}
    got = {d.segment_id for d in m.Disposition.objects.filter(run=run,
                                                              segment__reading=reading)}
    return pks == got


# --- Cláusula reemplazada con varias citas (M-013) -------------------------------------------------------

GA = "La garantía de oferta será del cinco por ciento del monto."
GB = "La garantía se constituirá en pesos."
PLAZO = "El plazo de entrega será de diez días hábiles."


def guarantee_case(user, script):
    pdf = tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("3. GARANTÍAS", f"3.1. {GA} {GB}"),
        para("4. PLAZOS", f"4.1. {PLAZO}"),
    ]])
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf)
    script.when(GA, item([(GA, "formal"), (GB, "formal")]))
    script.when(PLAZO, item([(PLAZO, "formal")]))
    return procedure


def test_a_replaced_clause_gives_a_source_to_each_of_its_citations(operator_user, script):
    """REQ-031 (M-013): "se reemplaza el apartado 3.1 por el siguiente" alcanza las dos
    citas de la cláusula, no una sola: cada una recibe su fuente `modifica` con el texto
    nuevo; una cláusula que no nombra no cambia. Sin el modelo."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Se reemplaza el apartado 3.1 por el siguiente: La garantía de oferta "
                 "será del diez por ciento y se constituirá en dólares.")

    version, run = run_proposal(operator_user, procedure)

    for text in (GA, GB):
        source = requirement_with(version, text).sources.get()
        assert source.effect == "modifica" and source.issued_on == date(2025, 12, 1)
        assert source.text == ("La garantía de oferta será del diez por ciento y se "
                               "constituirá en dólares.")
        canonical = source.segment.reading.canonical_text
        assert canonical[source.char_start:source.char_end] == source.text
    assert not requirement_with(version, PLAZO).sources.exists()
    assert not model_requests(script, "apartado 3.1")
    step = unit_steps()[0]
    assert step.parsed["resultado"] == "aplicada" and step.parsed["cambio"] == "reemplaza"
    assert step.parsed["objetivo"] == {"tipo": "clausula", "referencia": ["3.1"]}
    assert len(step.parsed["fuentes"]) == 2 and step.request["sin_modelo"] is True


def test_a_suppressed_clause_leaves_every_citation_removed(operator_user, script):
    """REQ-031: "se suprime la cláusula 3.1" quita las dos citas de la cláusula."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Se suprime la cláusula 3.1.")

    version, _ = run_proposal(operator_user, procedure)

    assert requirement_with(version, GA).state == "quitado"
    assert requirement_with(version, GB).state == "quitado"
    assert requirement_with(version, PLAZO).state == "propuesto"


def test_the_level_limit_keeps_a_clause_apart_from_one_that_starts_with_its_number():
    """REQ-031: `7.5.4` alcanza `7.5.4`, `7.5.4.1` y su viñeta, pero no `7.5.41`."""
    def cite(key):
        return SimpleNamespace(segment=SimpleNamespace(key=key))

    candidates = [cite("sec-i/7.5.4"), cite("sec-i/7.5.4.1"), cite("sec-i/7.5.4/v-2"),
                  cite("sec-i/7.5.41"), cite("sec-i/7.5.5")]
    found = units.clause_candidates(candidates, "7.5.4")
    assert [c.segment.key for c in found] == ["sec-i/7.5.4", "sec-i/7.5.4.1",
                                              "sec-i/7.5.4/v-2"]


def test_a_clause_number_in_two_sections_is_ambiguous_and_goes_to_the_fallback(
        operator_user, case, script):
    """REQ-031: la cláusula 2.1 existe en la sección I y en la II del pliego: la unidad no
    decide por el número, queda registrada con su motivo y pasa al respaldo."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en la cláusula 2.1 el plazo de pago por 60 días corridos.")

    version, run = run_proposal(operator_user, case)

    assert unit_steps()[0].parsed["motivo"] == "clave_ambigua"
    assert model_requests(script, "plazo de pago")
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


# --- Anexo que deja de ser requisito (M-029) ------------------------------------------------------------------

ANEXO = "cada oferente cargará y presentará la planilla del anexo"
PASO = "El precio de referencia figura en el Anexo VI del presente pliego."
ANEXO_ROW = "El oferente informará su razón social y su domicilio."


def annex_case(user, script):
    pdf = tender_pdf([
        [para("SECCIÓN I - CONDICIONES PARTICULARES"),
         para("1. ECONOMÍA", f"1.1. ANEXO VI - PLANILLA SINTÉTICA: {ANEXO}."),
         para("2. PRECIO", f"2.1. {PASO}"),
         para("3. PAGO", f"3.1. {PAGO}")],
        [para("SECCIÓN IV - ANEXOS"),
         para("ANEXO VI - PLANILLA SINTÉTICA"), para(ANEXO_ROW)],
    ])
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf)
    script.when(ANEXO, item([(ANEXO, "formal")]))
    script.when(PASO, item([(PASO, "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(ANEXO_ROW, item([(ANEXO_ROW, "formal")]))
    return procedure


def test_an_annex_that_is_not_a_requirement_reaches_its_content_and_the_clause_that_asks(
        operator_user, script):
    """REQ-031 (M-029): "el Anexo VI no será considerado como un requisito" da `suprime` en
    las citas del anexo y en la cláusula que manda completarlo y adjuntarlo; no en la cláusula
    que lo menciona de pasada ni en una ajena. Sin el modelo."""
    procedure = annex_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Queda sin efecto como exigencia lo informado en el Anexo VI.")

    version, _ = run_proposal(operator_user, procedure)

    for text in (ANEXO, ANEXO_ROW):
        requirement = requirement_with(version, text)
        assert requirement.state == "quitado"
        assert requirement.sources.get().effect == "suprime"
    assert requirement_with(version, PASO).state == "propuesto"
    assert requirement_with(version, PAGO).state == "propuesto"
    assert not model_requests(script, "Queda sin efecto como exigencia")
    assert unit_steps()[0].parsed["objetivo"]["tipo"] == "anexo"


def test_an_annex_of_an_external_rule_is_not_an_annex_of_the_tender():
    """REQ-031: "Anexo IV de la Disposición N° …" no es un anexo del pliego; el Anexo IV a
    secas sí."""
    assert circulars.named_annexes("conforme el Anexo IV de la Disposición N° 12/20") == set()
    assert circulars.named_annexes("el Anexo II del Decreto 5, la Resolución y el Anexo 3") == {"3"}
    assert circulars.named_annexes("el Anexo IV, de la Ley 25.000") == set()
    assert circulars.named_annexes("el Anexo IV debe completarse") == {"iv"}


def test_an_annex_of_an_external_rule_does_not_add_the_citations_of_that_annex(
        operator_user, script, fake_reranker, settings):
    """REQ-031 (diagnóstico: 540 aludidas): un tramo que cita "el Anexo IV de la Disposición
    N° …" no trae al modelo las citas del Anexo IV del pliego."""
    settings.MATRIX_CIRCULAR_CANDIDATES = 0
    pdf = tender_pdf([
        [para("SECCIÓN I - CONDICIONES PARTICULARES"), para("1. PAGO", f"1.1. {PAGO}")],
        [para("SECCIÓN IV - ANEXOS"), para("ANEXO IV - DECLARACIÓN SINTÉTICA"), para(ANEXO_ROW)],
    ])
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, pdf)
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(ANEXO_ROW, item([(ANEXO_ROW, "formal")]))
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Se aclara que los plazos son los del Anexo IV de la Disposición N° 12.")

    run_proposal(operator_user, procedure)

    request = next(r for r in script.requests if "plazos son los" in r["tramo"])
    assert ANEXO_ROW not in " ".join(request["cites"].values())


# --- Lista de datos del trámite (M-044) ---------------------------------------------------------------------------

VISITA_A = "El recorrido se realizará en la jornada indicada en el Anexo “JORNADA DE RECORRIDO” del portal."
VISITA_B = ("Los interesados presentarán la constancia de la visita indicada en el Anexo "
            "“JORNADA DE RECORRIDO” del portal.")


def visit_case(user, script, annex_title="Anexo JORNADA DE RECORRIDO",
               annex_head="ANEXO - JORNADA DE RECORRIDO"):
    procedure = make_procedure(user)
    load_and_read(user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. VISITA", f"1.1. {VISITA_A} {VISITA_B}"),
        para("2. PAGO", f"2.1. {PAGO}"),
    ]]))
    load_and_read(user, procedure,
                  tender_pdf([[para(annex_head, "Visita: 10 de junio.")]]),
                  kind=m.DocumentKind.ANEXO, title=annex_title)
    script.when(VISITA_A, item([(VISITA_A, "formal"), (VISITA_B, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    return procedure


LIST = ["II. SE PROGRAMAN OTRAS JORNADAS DE RECORRIDO", "JORNADA DE RECORRIDO: 21 de julio",
        "HORA: 10hs", "PUNTO DE ENCUENTRO: puerta principal", "REFERENTE: oficina de compras",
        "DIRECCIÓN: calle sintética 100"]


def test_a_list_of_procedure_data_creates_no_requirement_and_replaces_the_annex_once_per_citation(
        operator_user, script):
    """REQ-031 / REQ-028 (M-044): un apartado de líneas de fecha, hora y lugar no crea
    requisitos; sus tramos quedan `descartado` con `dato_procedimiento` y, como lleva el
    título del anexo que dos citas del pliego mencionan, da una sola fuente `modifica` por
    cada cita, con la lista entera como texto vigente (no la última línea) y el anexo como
    original. Sin el modelo."""
    procedure = visit_case(operator_user, script)
    document = load_and_read(operator_user, procedure, narrative_circular(*LIST),
                             kind="circular_modificatoria", title="Circular N.º 1",
                             issued_on=date(2025, 12, 1))

    version, run = run_proposal(operator_user, procedure)

    assert not version.requirements.filter(origin="circular").exists()
    assert not script.requests
    assert every_segment_has_a_disposition(document, run)
    for disposition in m.Disposition.objects.filter(run=run, segment__reading__document=document):
        assert (disposition.outcome, disposition.discard_reason) == ("descartado",
                                                                      "dato_procedimiento")
        assert disposition.source == "regla"
    sources = []
    for text in (VISITA_A, VISITA_B):
        requirement = requirement_with(version, text)
        source = requirement.sources.get()
        assert source.effect == "modifica"
        sources.append(source)
    for source in sources:
        assert "JORNADA DE RECORRIDO: 21 de julio" in source.text
        assert "DIRECCIÓN: calle sintética 100" in source.text
        assert "SE PROGRAMAN" not in source.text
        assert (source.segment.reading.canonical_text[source.char_start:source.char_end]
                == source.text)
    assert not requirement_with(version, PAGO).sources.exists()
    step = unit_steps()[0]
    assert step.parsed["cambio"] == "dato_del_tramite" and len(step.parsed["fuentes"]) == 2
    annex = m.Reading.objects.get(document__title="Anexo JORNADA DE RECORRIDO")
    for source in step.parsed["fuentes"]:
        original = source["original"]
        assert original is not None
        assert m.Segment.objects.get(pk=original["segmento"]).reading == annex
    for source in sources:
        assert source.original_segment.reading == annex
        text = annex.canonical_text[source.original_char_start:source.original_char_end]
        assert "10 de junio" in text


@pytest.mark.parametrize("annex_title, annex_head", [
    ("ANEXO_JORNADA_DE_RECORRIDO.pdf", "Planilla de datos"),    # el título es un nombre de archivo
    ("scan_0042.pdf", "ANEXO - JORNADA DE RECORRIDO"),         # el título está en el primer párrafo
])
def test_the_original_is_found_when_the_annex_title_is_a_file_name_or_is_in_its_first_line(
        operator_user, script, annex_title, annex_head):
    """REQ-031 (T-124): el anexo cuyo título de documento es un nombre de archivo (guiones
    bajos, extensión) o que lleva el título solo en su primer párrafo se encuentra: la fuente
    guarda el anexo como original."""
    procedure = visit_case(operator_user, script, annex_title, annex_head)
    load_and_read(operator_user, procedure, narrative_circular(*LIST),
                  kind="circular_modificatoria", title="Circular N.º 1",
                  issued_on=date(2025, 12, 1))

    version, _ = run_proposal(operator_user, procedure)

    annex = m.Reading.objects.get(document__title=annex_title)
    for text in (VISITA_A, VISITA_B):
        source = requirement_with(version, text).sources.get()
        assert source.original_segment.reading == annex
        assert "10 de junio" in annex.canonical_text[source.original_char_start:
                                                       source.original_char_end]


def test_a_pair_that_adds_an_obligation_creates_a_circular_requirement(operator_user, script):
    """REQ-031 (T-124, M-015): el lado "debe decir" repite la cláusula y suma una oración con
    obligación: además del `modifica` sobre lo existente, esa oración es un requisito formal
    de origen `circular` con su cita literal en el tramo de la circular; las oraciones que ya
    estaban no se duplican y el modelo no interviene."""
    extra = "Cada firmante deberá registrar la recepción de la muestra física."
    procedure = conflict_case(operator_user, script)
    document = add_paras(
        operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
        "DONDE DICE:", f"4.1. {OLD} {OLD_B}", "DEBE DECIR:", f"4.1. {NEW} {NEW_B}", extra)

    version, run = run_proposal(operator_user, procedure)

    new = version.requirements.get(origin="circular")
    assert new.category == "formal"
    quote = new.quotes.get()
    assert quote.text == extra
    assert quote.segment.reading.document == document
    for text in (OLD, OLD_B):
        assert [s.effect for s in requirement_with(version, text).sources.all()] == ["modifica"]
    assert not script.requests
    assert every_segment_has_a_disposition(document, run)


def test_a_pair_that_adds_nothing_obligatory_creates_no_requirement(operator_user, script):
    """REQ-031 (T-124): si el lado "debe decir" solo cambia la redacción de lo que ya está,
    no se crea ningún requisito."""
    procedure = conflict_case(operator_user, script)
    add_paras(operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
              "DONDE DICE:", f"4.1. {OLD} {OLD_B}", "DEBE DECIR:", f"4.1. {OLD} {OLD_B}")

    version, _ = run_proposal(operator_user, procedure)

    assert not version.requirements.filter(origin="circular").exists()


def test_the_original_of_a_source_must_be_a_cut_of_a_tender_reading(operator_user, script):
    """REQ-031 (T-114): la base no garantiza que el tramo del original sea de la lectura de
    las posiciones ni que sea del pliego; el servicio lo comprueba antes de guardar."""
    from evaluon.tenders.proposal import run as run_module

    procedure = visit_case(operator_user, script)
    document = load_and_read(operator_user, procedure, narrative_circular(*LIST),
                             kind="circular_modificatoria", title="Circular N.º 1",
                             issued_on=date(2025, 12, 1))
    annex = m.Reading.objects.get(document__title="Anexo JORNADA DE RECORRIDO")
    inside = annex.segments.order_by("order").first()
    circular_segment = document.readings.get().segments.order_by("order").first()
    circular_ids = {document.readings.get().pk}

    def source(segment, start, end):
        return SimpleNamespace(original=units.Original(segment, start, end))

    good = run_module._original_fields(
        source(inside, inside.char_start, inside.char_end), circular_ids)
    assert good["original_segment"] == inside
    with pytest.raises(RuntimeError):      # el tramo es de una circular
        run_module._original_fields(
            source(circular_segment, circular_segment.char_start, circular_segment.char_end),
            circular_ids)
    with pytest.raises(RuntimeError):      # las posiciones se pasan de la lectura
        run_module._original_fields(
            source(inside, inside.char_start, len(annex.canonical_text) + 5), circular_ids)
    assert run_module._original_fields(SimpleNamespace(original=None), circular_ids) == {}


def test_a_list_with_an_obligation_is_not_procedure_data():
    """REQ-031: una línea con un marcador de obligación ("deberán") hace que el apartado no
    sea una lista de datos: sigue su camino de unidad común."""
    def unit(*lines):
        members = [SimpleNamespace(segment=SimpleNamespace(
            text=t, segment_type="parrafo", key=f"pre/p-{i}")) for i, t in enumerate(lines)]
        return units.ChangeUnit(units.KIND_SECTION, members)

    plain = unit("II. NUEVAS FECHAS", "FECHA: 21 de julio", "HORA: 10hs", "LUGAR: sede")
    assert units.is_procedure_data(plain)
    obliged = unit("II. NUEVAS FECHAS", "FECHA: 21 de julio",
                   "Los oferentes deberán asistir con nota", "LUGAR: sede")
    assert not units.is_procedure_data(obliged)
    prose = unit("II. SE AJUSTA", "Se cambia el formato de la planilla de cotización en su "
                 "totalidad y se agregan columnas nuevas para cada renglón del pliego.",
                 "Se pide además otra cosa que no es corta ni lleva un rótulo con valor, "
                 "porque es una oración larga que sigue y sigue sin parar.")
    assert not units.is_procedure_data(prose)


def test_a_circular_without_headings_behaves_as_before(operator_user, case, script):
    """REQ-031: una circular de párrafos sueltos, sin cláusulas ni apartados, pasa tramo por
    tramo al modelo (como hoy) y no deja pedidos de unidad."""
    document = load_and_read(operator_user, case,
                             narrative_circular("Se cambia el formato.", "Otra línea suelta."),
                             kind="circular_modificatoria", title="Circular N.º 1",
                             issued_on=date(2025, 12, 1))

    _, run = run_proposal(operator_user, case)

    assert len(model_requests(script, "Se cambia el formato", "Otra línea suelta")) == 2
    assert not unit_steps()
    assert every_segment_has_a_disposition(document, run)


# --- "Donde dice / Debe decir" en tramos separados (M-015) --------------------------------------------------------

OLD = "Existirá conflicto de intereses cuando el oferente sea pariente del funcionario."
OLD_B = "Se informará por escrito."
NEW = "Existirá conflicto de intereses cuando el oferente tenga vínculo con el funcionario."
NEW_B = "Se informará por escrito y de inmediato."


def conflict_case(user, script):
    procedure = make_procedure(user)
    load_and_read(user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("4. CONFLICTO", f"4.1. {OLD} {OLD_B}"),
        para("5. PAGO", f"5.1. {PAGO}"),
    ]]))
    script.when(OLD, item([(OLD, "formal"), (OLD_B, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    return procedure


def test_where_it_says_and_must_say_in_separate_tramos_give_one_modifica(operator_user, script):
    """REQ-031 / REQ-028 (M-015): el rótulo "Donde dice", el texto viejo, el rótulo "Debe
    decir" y el texto nuevo, cada uno en su tramo, son una sola unidad: un `modifica` por cita
    de la cláusula con el texto nuevo, el texto viejo no produce efecto y ningún tramo del par
    queda sin disposición."""
    procedure = conflict_case(operator_user, script)
    document = add_paras(
        operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
        "DONDE DICE:", f"4.1. {OLD} {OLD_B}", "DEBE DECIR:", f"4.1. {NEW} {NEW_B}")

    version, run = run_proposal(operator_user, procedure)

    for text in (OLD, OLD_B):
        sources = list(requirement_with(version, text).sources.all())
        assert [s.effect for s in sources] == ["modifica"]
        assert sources[0].text == f"4.1. {NEW} {NEW_B}"
        assert "pariente" not in sources[0].text
    assert not requirement_with(version, PAGO).sources.exists()
    assert not script.requests
    assert every_segment_has_a_disposition(document, run)
    reading = document.readings.get()
    outcomes = {d.outcome for d in m.Disposition.objects.filter(run=run,
                                                                segment__reading=reading)}
    assert outcomes <= {"requisitos", "pendiente"} and "requisitos" in outcomes
    assert not m.Disposition.objects.filter(run=run, segment__reading=reading,
                                            outcome="descartado").exists()


def test_the_old_side_alone_finds_the_citation_when_no_clause_is_named(operator_user, script):
    """REQ-031: un par cuyo "debe decir" no empieza con número de cláusula ubica la cita por
    el texto anterior si es una sola."""
    procedure = conflict_case(operator_user, script)
    add_paras(operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
                 "DONDE DICE:", "pariente del funcionario", "DEBE DECIR:",
                 "vínculo con el funcionario")

    version, _ = run_proposal(operator_user, procedure)

    source = requirement_with(version, OLD).sources.get()
    assert source.effect == "modifica" and source.text == "vínculo con el funcionario"
    assert not requirement_with(version, OLD_B).sources.exists()


def test_two_pairs_in_one_unit_go_to_the_fallback(operator_user, script):
    """REQ-031: una unidad con dos pares no se aplica sola: va al respaldo con su motivo."""
    procedure = conflict_case(operator_user, script)
    add_paras(operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
                 "1. Se modifica la cláusula 4.1 así:", "DONDE DICE:", "uno", "DEBE DECIR:",
                 "dos", "DONDE DICE:", "tres", "DEBE DECIR:", "cuatro")

    version, _ = run_proposal(operator_user, procedure)

    assert unit_steps()[0].parsed["motivo"] == "varios_pares"
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


# --- Cita común a varios renglones ----------------------------------------------------------------------------------

GENERAL = "Los bienes tienen vencimiento mayor a once meses."


def shared_case(user, script):
    pdf = tender_pdf([
        [para("SECCIÓN I - ESPECIFICACIONES TÉCNICAS GENERALES"),
         para("9. CLÁUSULAS GENERALES", f"9.1. {GENERAL}")],
        [para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
         para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", "1.1. Bolsa de veinte kilos."),
         para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", "2.1. Bolsa de diez kilos.")],
    ])
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf)
    return procedure


def test_a_citation_common_to_several_items_gets_no_effect_if_the_unit_names_neither(
        operator_user, script):
    """REQ-031 (72 fuentes técnicas ajenas): una cita común a todos los renglones multiplica
    por cada renglón cualquier error de elección; si la unidad no nombra la cláusula ni el
    renglón, no recibe efecto, ni por el texto anterior de un par ni por el de un reemplazo."""
    procedure = shared_case(operator_user, script)
    add_paras(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "DONDE DICE:", GENERAL, "DEBE DECIR:",
                 "Los bienes tienen vencimiento mayor a doce meses.")
    add_circular(operator_user, procedure, "Circular N.º 2", date(2025, 12, 2),
                 "1. Reemplázase el vencimiento mayor a once meses por doce meses.")

    version, _ = run_proposal(operator_user, procedure)

    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    reasons = [s.parsed["motivo"] for s in unit_steps()]
    assert "texto_anterior_sin_coincidencia" in reasons and "sin_objetivo" in reasons


def test_a_citation_common_to_several_items_reaches_every_row_if_the_unit_names_its_clause(
        operator_user, script):
    """REQ-031: si la unidad nombra la cláusula de la cita común, el efecto alcanza la fila de
    cada renglón (una sola fuente por cita, cada fila con la suya)."""
    procedure = shared_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Se modifica la cláusula 9.1 por la siguiente: Los bienes tienen "
                 "vencimiento mayor a doce meses.")

    version, _ = run_proposal(operator_user, procedure)

    for number in (1, 2):
        row = row_of_item(version, number)
        source = row.sources.get()
        assert source.effect == "modifica" and "doce meses" in source.text
        assert source.quote == row.quotes.get(scope="general")
    assert not script.requests or not model_requests(script, "doce meses")


# --- El ejemplo de la spec: 16 GB a 32 GB ---------------------------------------------------------------------------------


def test_the_spec_example_is_applied_by_item_without_the_model(operator_user, case, script):
    """REQ-031 (criterio de aceptación): "16 GB de RAM" y una circular "32 GB", por la clave
    del renglón: la fila exige 32 GB, conserva el original y no se le pregunta al modelo."""
    add_paras(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")

    version, _ = run_proposal(operator_user, case)

    source = row_of_item(version, 1).sources.get()
    assert source.effect == "modifica" and source.text == "32 GB de RAM"
    assert RAM in source.quote.text
    assert not row_of_item(version, 2).sources.exists()
    assert not model_requests(script, "32 GB")
    assert unit_steps()[0].parsed["objetivo"] == {"tipo": "renglon", "referencia": [1]}


def test_the_spec_example_is_applied_by_the_old_text(operator_user, case, script):
    """REQ-031: el mismo cambio dicho como par, sin nombrar el renglón: el texto anterior
    "16 GB de RAM" ubica la única cita que lo contiene."""
    add_paras(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "DONDE DICE:", "16 GB de RAM", "DEBE DECIR:", "32 GB de RAM")

    version, _ = run_proposal(operator_user, case)

    source = row_of_item(version, 1).sources.get()
    assert source.effect == "modifica" and source.text == "32 GB de RAM"
    assert not row_of_item(version, 2).sources.exists()
    assert not model_requests(script, "32 GB")


# --- Clave inexistente, texto anterior ambiguo y cláusula nueva ---------------------------------------------------------


def test_a_missing_key_goes_to_the_fallback_and_is_not_lost(operator_user, case, script):
    """REQ-031: "se suprime la cláusula 9.9" cuando el pliego no la tiene: la unidad va al
    respaldo con su motivo y el tramo pasa por el modelo; ningún tramo queda sin disposición."""
    document = add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                            "1. Se suprime la cláusula 9.9.")

    _, run = run_proposal(operator_user, case)

    assert unit_steps()[0].parsed["motivo"] == "clave_inexistente"
    assert model_requests(script, "cláusula 9.9")
    assert every_segment_has_a_disposition(document, run)


def test_an_ambiguous_old_text_goes_to_the_fallback(operator_user, script):
    """REQ-031: un texto anterior que está en dos cláusulas distintas no se aplica solo."""
    pdf = tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PLAZO", "1.1. El plazo será de diez días hábiles."),
        para("2. ENTREGA", "2.1. La entrega se hará dentro del plazo de diez días hábiles."),
    ]])
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, pdf)
    script.when("El plazo será", item([("El plazo será de diez días hábiles", "formal")]))
    script.when("La entrega", item([("dentro del plazo de diez días hábiles", "formal")]))
    add_paras(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "DONDE DICE:", "diez días hábiles", "DEBE DECIR:", "veinte días hábiles")

    version, _ = run_proposal(operator_user, procedure)

    assert unit_steps()[0].parsed["motivo"] == "texto_anterior_ambiguo"
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


def test_a_new_clause_the_tender_lacks_adds_a_requirement(operator_user, case, script):
    """REQ-031: "agrégase la cláusula 9.9: …" cuando el pliego no la tiene crea un requisito
    de origen `circular` con la cita literal en el tramo de la circular, sin modelo."""
    document = add_circular(
        operator_user, case, "Circular N.º 3", date(2025, 12, 7),
        "1. Agrégase la cláusula 9.9: Los oferentes deberán presentar una declaración jurada "
        "de domicilio.")

    version, run = run_proposal(operator_user, case)

    new = version.requirements.get(origin="circular")
    assert new.category == "formal"
    quote = new.quotes.get()
    assert quote.text == ("Los oferentes deberán presentar una declaración jurada de "
                          "domicilio.")
    assert quote.segment.reading.document == document
    assert not model_requests(script, "cláusula 9.9")
    assert every_segment_has_a_disposition(document, run)


def test_a_new_clause_that_the_tender_already_has_goes_to_the_fallback(operator_user, case,
                                                                       script):
    """REQ-031: agregar una cláusula con un número que el pliego ya tiene no crea un
    requisito por clave: va al respaldo."""
    add_circular(operator_user, case, "Circular N.º 3", date(2025, 12, 7),
                 "1. Agrégase la cláusula 2.1: Los oferentes deberán presentar una nota.")

    run_proposal(operator_user, case)

    assert unit_steps()[0].parsed["motivo"] == "clave_existente"


# --- Partición y tipo, sin base --------------------------------------------------------------------------------------------


def fake_unit(key, text, kind="parrafo", start=0):
    segment = SimpleNamespace(key=key, text=text, segment_type=kind, char_start=start,
                              char_end=start + len(text))
    return SimpleNamespace(segment=segment)


def test_the_circular_is_split_into_units_by_clause_heading_and_pair():
    """REQ-028: cláusula numerada con lo que cuelga, apartado romano, par con los tramos
    `no_ubicado` entre sus rótulos y tramo suelto."""
    tramos = [
        fake_unit("pre/p-1", "CIRCULAR SINTÉTICA"),
        fake_unit("1", "1. Se suprime la cláusula 3.1.", "clausula"),
        fake_unit("1/v-1", "- una viñeta", "vineta"),
        fake_unit("2", "2. Se modifica la cláusula 4.1:", "clausula"),
        fake_unit("2/p-1", "DONDE DICE:"),
        fake_unit("2/no-ubicado-1", "texto viejo", "no_ubicado"),
        fake_unit("2/p-2", "Debe decir:"),
        fake_unit("2/p-3", "texto nuevo"),
        fake_unit("pre/p-9", "II. NUEVAS FECHAS"),
        fake_unit("pre/p-10", "FECHA: 1"),
        fake_unit("pre/p-11", "DONDE DICE"),
        fake_unit("pre/p-12", "viejo"),
        fake_unit("pre/p-13", "DEBE DECIR"),
        fake_unit("pre/p-14", "nuevo"),
    ]
    got = [(u.kind, [m_.segment.key for m_ in u.members]) for u in units.partition(tramos)]
    assert got == [
        ("suelto", ["pre/p-1"]),
        ("clausula", ["1", "1/v-1"]),
        ("clausula", ["2", "2/p-1", "2/no-ubicado-1", "2/p-2", "2/p-3"]),
        ("apartado", ["pre/p-9", "pre/p-10", "pre/p-11", "pre/p-12", "pre/p-13", "pre/p-14"]),
    ]


def test_a_pair_that_starts_a_unit_by_itself_keeps_its_tramos():
    """REQ-028: un par que no cuelga de una cláusula es una unidad `par` con todo hasta el
    próximo límite, tablas incluidas."""
    tramos = [
        fake_unit("pre/p-1", "Donde dice: algo"),
        fake_unit("pre/p-2", "viejo"),
        fake_unit("pre/p-3", "tabla", "tabla"),
        fake_unit("pre/p-4", "Debe decir:"),
        fake_unit("pre/p-5", "nuevo"),
        fake_unit("1", "1. Otro cambio.", "clausula"),
    ]
    got = [(u.kind, len(u.members)) for u in units.partition(tramos)]
    assert got == [("par", 5), ("clausula", 1)]


@pytest.mark.parametrize("text,expected", [
    ("Se reemplaza el apartado 6.2 por el siguiente", "reemplaza"),
    ("Reemplázase en el Renglón 2 la memoria por otra", "reemplaza"),
    ("Sustitúyese el plazo por otro", "reemplaza"),
    ("Se suprime la cláusula 5", "suprime"),
    ("Elimínase el requisito de la nota", "suprime"),
    ("Déjase sin efecto la exigencia", "suprime"),
    ("No es requisito presentar la planilla del Anexo VI", "suprime"),
    ("Agrégase la cláusula 9.9", "agrega"),
    ("Se incorpora el siguiente requisito", "agrega"),
    ("Se aclara que el plazo es hábil", "aclara"),
    ("Se informa que la apertura es en la sede", "aclara"),
    ("Aclárase que se elimina la nota", "suprime"),
    ("Las ofertas se abrirán en la fecha indicada", ""),
])
def test_the_type_of_change_comes_from_a_closed_list_of_verbs(text, expected):
    """REQ-031: el tipo de cambio sale de verbos y rótulos de lista cerrada; suprimir pesa más
    que aclarar; sin verbo reconocible no hay tipo."""
    assert units.detect_change(text) == expected


def test_the_introducer_skips_its_own_number_and_stops_at_the_new_text():
    """REQ-031: el encabezado de la unidad es lo que dice antes de su texto nuevo."""
    assert units.introducer("1. Se reemplaza el apartado 6.2 por el siguiente: Los "
                            "oferentes") == "Se reemplaza el apartado 6.2 por el siguiente"
    assert units.introducer("II. SE AJUSTA. Otra oración") == "SE AJUSTA"
    assert units.introducer("Reemplázase la cláusula 2.1 el plazo por 3.5 días.") == (
        "Reemplázase la cláusula 2.1 el plazo por 3.5 días")


def test_the_old_text_is_found_by_contained_words_without_the_names_of_the_target():
    """REQ-031: "memoria de 16 GB de RAM" coincide con la cita que dice "16 GB de RAM", pero
    "en el Renglón N° 1" no coincide con el encabezado del renglón."""
    def cite(text, key="sec-ii/1.1", reading=1):
        return SimpleNamespace(text=text, segment=SimpleNamespace(key=key, reading_id=reading))

    pool = [cite("1. RENGLÓN N° 1 - COMPUTADORA SINTÉTICA", "sec-ii/1"),
            cite("La computadora tendrá 16 GB de RAM.")]
    cleaned = units._without_names("en el Renglón N° 1 la memoria de 16 GB de RAM")
    found, reason = units.match_old_text(cleaned, pool)
    assert reason == "" and found == [pool[1]]
    assert units.match_old_text(units._without_names("en el Renglón N° 1 la memoria"),
                                pool)[1] == "texto_anterior_sin_coincidencia"


# --- Generalidad: ninguna ancla de los casos 00, 01 y 02 -------------------------------------------------------------------

HASHES = Path(__file__).parent / "fixtures" / "case_anchor_hashes.txt"
SHINGLE = 5
_SCANNED = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".html"}


def _shingles(text):
    import unicodedata

    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    for i in range(len(words) - SHINGLE + 1):
        yield " ".join(words[i:i + SHINGLE])


def test_no_test_or_fixture_repeats_five_words_of_a_case_anchor():
    """REQ-031 (generalidad): ningún test ni fixture de las pruebas de esta feature ni el
    módulo de unidades repite cinco palabras seguidas de las anclas de los casos 00, 01 y 02.
    Las anclas no están en el repositorio (P4): `fixtures/case_anchor_hashes.txt` guarda solo
    la huella SHA-256 de cada secuencia de cinco palabras (sin tildes ni mayúsculas); se genera
    leyendo los campos `ancla*` de las listas esperadas locales."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    root = Path(__file__).parent
    files = [p for p in root.glob("test_circular*.py")]
    files.append(Path(units.__file__))
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for shingle in _shingles(text):
            if hashlib.sha256(shingle.encode()).hexdigest() in known:
                hits.append(f"{path.name}: {hashlib.sha256(shingle.encode()).hexdigest()[:12]}")
    assert not hits, hits
