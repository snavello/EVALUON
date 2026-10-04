"""Niveles alta y exigente: completitud, segunda extracción y unión (REQ-024, REQ-025,
REQ-030; plan 003, "Pasadas"; ADR-0019, decisión 5; T-078).

El modelo es el doble de `tests/conftest.py` con el guion de `tests/tenders/scripted.py`,
ampliado acá para responder también la completitud y para distinguir la primera de la
segunda extracción. Los pliegos son sintéticos (P4); sin modelo real.
"""

import json
import textwrap
from types import SimpleNamespace

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import completeness, extraction
from evaluon.tenders.proposal.extraction import ALL_ITEMS, Found, Outcome
from evaluon.tenders.proposal.quotes import WIDE
from tests.tenders.pdfs import para, table, tender_pdf
from tests.tenders.scripted import (
    ENTREGA,
    Script,
    item,
    load_and_read,
    make_procedure,
    propose,
    three_items_pdf,
)

pytestmark = pytest.mark.django_db

DOCS = ("La oferta deberá incluir la declaración jurada de habilidad para contratar y la "
        "constancia de inscripción en el registro de proveedores.")
DJ = "la declaración jurada de habilidad para contratar"
CONSTANCIA = "la constancia de inscripción en el registro de proveedores"
MANT = "Los oferentes deberán mantener la oferta durante 60 días corridos."
MANT_QUOTE = "mantener la oferta durante 60 días corridos"
NOALT = "No se aceptarán ofertas alternativas sin garantía de mantenimiento de la oferta."
OBJETO = "El objeto de la contratación es la adquisición de bienes sintéticos."
TECNICO = "Los bienes deberán tener vencimiento mayor a once meses."
RENGLON = "Bolsa de veinte kilogramos con rótulo sintético."

INVALID = "invalida"  # respuesta de la completitud con la forma rota


def clause(number, text):
    """Las líneas de una cláusula, cortadas como en una página."""
    return textwrap.wrap(f"{number} {text}", 78)


def completeness_pdf():
    """Condiciones con dos requisitos juntos, uno solo, un tramo con marcadores y otro sin;
    especificaciones técnicas con marcadores, y dos renglones."""
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. PRESENTACIÓN", *clause("1.1.", DOCS), *clause("1.2.", MANT)),
            para("2. CONDICIONES", *clause("2.1.", NOALT), *clause("2.2.", OBJETO)),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS GENERALES"),
            para("1. CLÁUSULAS GENERALES", *clause("1.1.", TECNICO)),
        ],
        [
            para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
            para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", *clause("1.1.", RENGLON)),
            para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", *clause("2.1.", RENGLON)),
        ],
    ])


def fix(missing=(), splits=()):
    """Lo que la completitud devuelve para un tramo."""
    return {
        "faltantes": [{"cita": quote, "clase": kind} for quote, kind in missing],
        "divisiones": [
            {"original": original,
             "partes": [{"cita": quote, "clase": kind} for quote, kind in parts]}
            for original, parts in splits
        ],
    }


class LevelScript(Script):
    """El guion de `scripted.py` más: respuestas de la completitud (`complete_when`),
    respuestas de una extracción en particular (`when_pass`) y el registro de lo que se le
    mandó a la completitud (`completeness_calls`)."""

    def __init__(self, fake, monkeypatch):
        super().__init__(fake, monkeypatch)
        self.pass_rules = []
        self.complete_rules = []
        self.completeness_calls = []
        self.extraction_pass = None

    def when_pass(self, pass_name, needle, answer):
        self.pass_rules.insert(0, (pass_name, needle, answer))

    def complete_when(self, needle, answer):
        self.complete_rules.insert(0, (needle, answer))

    def reset(self):
        self.rules.clear()
        self.pass_rules.clear()
        self.complete_rules.clear()

    def _answer(self, blocks):
        result = super()._answer(blocks)
        for alias, block in blocks.items():
            for pass_name, needle, answer in self.pass_rules:
                if pass_name == self.extraction_pass and needle in block["text"]:
                    result[alias] = answer
                    break
        return result

    def _generate(self, messages, schema, **options):
        first = next(iter(schema["properties"].values()))["properties"]
        if "faltantes" not in first:
            return super()._generate(messages, schema, **options)
        from tests.tenders.scripted import parse_blocks
        blocks = parse_blocks(messages[-1]["content"])
        self.completeness_calls.append({alias: {**block, "raw": messages[-1]["content"]}
                                        for alias, block in blocks.items()})
        answer = {}
        for alias, block in blocks.items():
            answer[alias] = fix()
            for needle, value in self.complete_rules:
                if needle in block["text"]:
                    answer[alias] = {"faltantes": "basura"} if value == INVALID else value
                    break
        self.fake.respond(json.dumps(answer, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)

    def sent_to_completeness(self):
        """Los textos de todos los tramos que llegaron a la completitud."""
        return [block["text"] for call in self.completeness_calls
                for block in call.values()]


@pytest.fixture
def script(fake_generation, monkeypatch):
    double = LevelScript(fake_generation, monkeypatch)
    original = extraction.Extractor.ask

    def ask(self, units, retry_of=None):
        double.extraction_pass = self.pass_name
        return original(self, units, retry_of)

    monkeypatch.setattr(extraction.Extractor, "ask", ask)
    return double


def standard(script):
    """El modelo encuentra los mantenimientos y nada más."""
    script.when(MANT, item([(MANT_QUOTE, "formal")]))


def run_level(user, level, pdf=None):
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf or completeness_pdf())
    requested, job = propose(user, procedure, level=level)
    assert job.status == "done", job.error
    return requested.run


def body(run):
    """Requisitos formales y económicos: `{clave del tramo: [(texto, pasadas, clase)]}`."""
    result = {}
    for requirement in m.Requirement.objects.filter(version=run.version).exclude(
            category="tecnico").order_by("number"):
        quote = requirement.quotes.get()
        result.setdefault(quote.segment.key, []).append(
            (quote.text, requirement.passes, requirement.category))
    return result


def disposition(run, key):
    return m.Disposition.objects.get(run=run, segment__key=key)


def pending(run):
    return {p.segment.key: p.reason for p in
            m.PendingItem.objects.filter(version=run.version).select_related("segment")}


def check_quotes_are_canonical(run):
    """REQ-025: cada cita guardada es igual al recorte del texto canónico de su lectura."""
    count = 0
    for quote in m.RequirementQuote.objects.filter(
            requirement__version=run.version).select_related("segment__reading"):
        canonical = quote.segment.reading.canonical_text
        assert canonical[quote.char_start:quote.char_end] == quote.text
        count += 1
    assert count


def step_passes(run):
    return [step.pass_name for step in m.RunStep.objects.filter(run=run).order_by("id")]


# --- Alta: completitud ---------------------------------------------------------------------


def test_alta_adds_the_missing_requirement_with_a_verified_quote(operator_user, script):
    """REQ-024, REQ-025, REQ-030: en alta, un faltante que la completitud devuelve se suma al
    tramo con su cita ubicada en el texto del pliego; el tramo se mandó con lo ya encontrado."""
    standard(script)
    script.when(DOCS, item([(DJ, "formal")]))
    script.complete_when("constancia", fix(missing=[(CONSTANCIA, "formal")]))

    run = run_level(operator_user, "alta")

    assert body(run)["sec-i/1.1"] == [
        (DJ, ["extraccion"], "formal"),
        (CONSTANCIA, ["completitud"], "formal"),
    ]
    check_quotes_are_canonical(run)
    sent = next(call for call in script.completeness_calls
                if any("constancia" in b["text"] for b in call.values()))
    assert f"1. {DJ} (formal)" in next(iter(sent.values()))["raw"]
    added = m.Requirement.objects.get(version=run.version, passes=["completitud"])
    assert added.step.pass_name == "completitud"
    assert run.counts["completeness"]["added"] == 1
    assert disposition(run, "sec-i/1.1").outcome == "requisitos"


def test_alta_splits_a_requirement_that_joins_two_conditions(operator_user, script):
    """REQ-024: un requisito agrupado (dos condiciones en una fila) se divide en las dos
    partes, cada una con su cita ubicada; la fila agrupada deja de estar."""
    standard(script)
    script.when(DOCS, item([(DOCS, "formal")]))
    script.complete_when("constancia", fix(splits=[
        (DOCS, [(DJ, "formal"), (CONSTANCIA, "formal")])]))

    run = run_level(operator_user, "alta")

    assert body(run)["sec-i/1.1"] == [
        (DJ, ["completitud"], "formal"),
        (CONSTANCIA, ["completitud"], "formal"),
    ]
    check_quotes_are_canonical(run)
    assert run.counts["completeness"]["split"] == 1


def test_alta_discarded_with_markers_goes_to_completeness_and_is_not_pending(
        operator_user, script):
    """REQ-024: un tramo que el modelo descartó teniendo marcadores de obligación pasa por la
    completitud; si ésta encuentra un requisito, lo suma; si no, queda descartado y no
    pendiente (en media, el mismo tramo queda pendiente)."""
    standard(script)
    script.when(DOCS, item([(DJ, "formal"), (CONSTANCIA, "formal")]))
    script.complete_when("alternativas", fix(missing=[(NOALT, "economico")]))

    run = run_level(operator_user, "alta")

    assert body(run)["sec-i/2.1"] == [(NOALT, ["completitud"], "economico")]
    assert disposition(run, "sec-i/2.1").outcome == "requisitos"
    assert "sec-i/2.1" not in pending(run)

    script.complete_rules.clear()
    run = run_level(operator_user, "alta")
    assert disposition(run, "sec-i/2.1").outcome == "descartado"
    assert disposition(run, "sec-i/2.1").discard_reason == "dato_procedimiento"
    assert "sec-i/2.1" not in pending(run)

    run = run_level(operator_user, "media")
    assert pending(run)["sec-i/2.1"] == "marcadores"


def test_completeness_sends_only_model_segments_with_requirements_or_markers(
        operator_user, script):
    """REQ-024: a la completitud solo llegan tramos formales y económicos que pasaron por el
    modelo: con requisitos o descartados con marcadores. No llegan los de secciones técnicas
    (aunque tengan "deberá"), ni los descartados sin marcadores."""
    standard(script)

    for level in ("alta", "exigente"):
        script.completeness_calls.clear()
        run = run_level(operator_user, level)
        sent = [text.split(" ", 1)[1] for text in script.sent_to_completeness()]
        assert sorted(sent) == sorted([DOCS, MANT, NOALT]), level
        assert disposition(run, "sec-ii/1.1").outcome == "tecnico"


def test_an_invalid_completeness_answer_is_asked_again_once_and_then_leaves_it_pending(
        operator_user, script):
    """REQ-024, REQ-028: una salida de la completitud con la forma rota se vuelve a pedir una
    vez, solo ese tramo; si sigue rota, el descartado con marcadores queda pendiente (como en
    media) y lo ya encontrado no cambia."""
    standard(script)
    script.complete_when("alternativas", INVALID)

    run = run_level(operator_user, "alta")

    asked = [b for call in script.completeness_calls for b in call.values()
             if b["text"].endswith(NOALT)]
    assert len(asked) == 2
    assert pending(run)["sec-i/2.1"] == "marcadores"
    assert disposition(run, "sec-i/2.1").outcome == "pendiente"
    assert body(run)["sec-i/1.2"] == [(MANT_QUOTE, ["extraccion"], "formal")]
    assert "completitud_sin_resultado" in [a["type"] for a in run.anomalies]


# --- Completitud: casos del módulo ------------------------------------------------------------


def unit_of(text, section_class=""):
    segment = SimpleNamespace(pk=1, key="sec-i/1.1", text=text, section_class=section_class)
    return SimpleNamespace(segment=segment)


def test_overlap_is_a_fraction_of_the_shorter_quote():
    """REQ-024: la superposición de dos citas se mide sobre la más corta."""
    assert completeness.overlap((0, 10), (0, 10)) == 1
    assert completeness.overlap((0, 10), (5, 40)) == 0.5
    assert completeness.overlap((0, 10), (2, 100)) == 0.8
    assert completeness.overlap((0, 10), (10, 20)) == 0


def test_a_missing_requirement_that_repeats_a_found_one_is_not_added():
    """REQ-024: un faltante que se superpone en más de la mitad con un requisito ya
    encontrado del tramo no se suma."""
    unit = unit_of("Los oferentes deberán mantener la oferta durante 60 días corridos.")
    found = [Found("formal", (22, 64))]
    anomalies = []

    final, added, divided = completeness.apply(
        unit, found, [("la oferta durante 60 días corridos", "formal")], [], anomalies)

    assert final == found and (added, divided) == (0, 0)


def test_a_missing_quote_that_is_not_in_the_segment_is_kept_as_a_wide_quote():
    """REQ-025: un faltante cuya cita no está en el tramo queda con el tramo entero como
    cita (cita_amplia), una por clase, y la anomalía lo dice."""
    unit = unit_of("El pago se efectuará a los 90 días.")
    anomalies = []

    final, added, _ = completeness.apply(
        unit, [], [("texto que no está", "economico"), ("otro que tampoco", "economico")],
        [], anomalies)

    assert [(f.category, f.span, f.flag) for f in final] == [
        ("economico", (0, len(unit.segment.text)), WIDE)]
    assert completeness.passes_of(final[0]) == ["completitud"] and added == 1
    assert [a["type"] for a in anomalies] == ["completitud_cita_no_encontrada"] * 2


def test_a_split_with_a_part_outside_the_segment_leaves_the_requirement_as_it_was():
    """REQ-024, REQ-025: si no se ubican todas las partes de una división, el requisito queda
    como estaba, sin perder nada."""
    text = "Presentar la constancia y la declaración."
    unit = unit_of(text)
    found = [Found("formal", (0, len(text)))]
    anomalies = []

    final, _, divided = completeness.apply(
        unit, found, [], [(text, [("la constancia", "formal"), ("algo inventado", "formal")])],
        anomalies)

    assert final == found and divided == 0
    assert [a["type"] for a in anomalies] == ["completitud_division_no_aplicada"]


def test_union_keeps_the_fragment_over_a_wide_quote_of_the_same_class():
    """REQ-025: si una extracción dejó el tramo entero como cita y la otra un fragmento de la
    misma clase, queda el fragmento, con las pasadas de las dos."""
    unit = unit_of("Los oferentes deberán mantener la oferta durante 60 días corridos.")
    wide = Found("formal", (0, len(unit.segment.text)), flag=WIDE)
    fragment = Found("formal", (22, 64))
    first = Outcome(unit=unit, valid=True, found=[wide])
    second = Outcome(unit=unit, valid=True, found=[fragment])

    merged = completeness.union(first, second)

    assert merged.found == [fragment]
    assert completeness.passes_of(fragment) == ["extraccion_2", "extraccion"]


# --- Exigente: segunda extracción y unión --------------------------------------------------------


def test_exigente_union_does_not_duplicate_overlapping_requirements(operator_user, script):
    """REQ-024: en exigente, un requisito que las dos extracciones encuentran, con citas que
    se superponen, queda una vez (con las dos pasadas); el que solo encuentra la segunda
    se suma."""
    standard(script)
    longer = "La oferta deberá incluir " + DJ
    script.when_pass("extraccion", DOCS, item([(DJ, "formal")]))
    script.when_pass("extraccion_2", DOCS, item([(longer, "formal"), (CONSTANCIA, "formal")]))

    run = run_level(operator_user, "exigente")

    assert body(run)["sec-i/1.1"] == [
        (DJ, ["extraccion", "extraccion_2"], "formal"),
        (CONSTANCIA, ["extraccion_2"], "formal"),
    ]
    check_quotes_are_canonical(run)


def test_exigente_keeps_what_only_one_extraction_found_in_a_discarded_segment(
        operator_user, script):
    """REQ-024: un tramo descartado en una extracción y con requisitos en la otra queda con
    lo encontrado, sin importar cuál lo encontró."""
    script.when_pass("extraccion", MANT, item(discard="dato_procedimiento"))
    script.when_pass("extraccion_2", MANT, item([(MANT_QUOTE, "formal")]))
    script.when_pass("extraccion", NOALT, item([(NOALT, "economico")]))
    script.when_pass("extraccion_2", NOALT, item(discard="dato_procedimiento"))

    run = run_level(operator_user, "exigente")

    found = body(run)
    assert found["sec-i/1.2"] == [(MANT_QUOTE, ["extraccion_2"], "formal")]
    assert found["sec-i/2.1"] == [(NOALT, ["extraccion"], "economico")]
    assert disposition(run, "sec-i/1.2").outcome == "requisitos"
    assert disposition(run, "sec-i/2.1").outcome == "requisitos"
    assert "sec-i/1.2" not in pending(run) and "sec-i/2.1" not in pending(run)


def test_second_extraction_shifts_the_batches_by_half_a_batch(operator_user, script):
    """REQ-024: la segunda extracción pide los mismos tramos con los lotes desplazados: su
    primer pedido lleva la mitad de los tramos del primer lote de la primera, y los dos
    juntos cubren todos los tramos que pasan por el modelo."""
    standard(script)

    run = run_level(operator_user, "exigente")

    steps = m.RunStep.objects.filter(run=run, retry_of=None).order_by("id")
    first = [s for s in steps if s.pass_name == "extraccion"]
    second = [s for s in steps if s.pass_name == "extraccion_2"]
    assert len(first) == 1 and len(second) == 2
    keys = first[0].segment_keys
    assert second[0].segment_keys == keys[:len(keys) // 2]
    assert second[0].segment_keys + second[1].segment_keys == keys
    assert run.counts["model_requests_by_pass"]["extraccion_2"] == 2


def test_technical_rows_are_the_same_in_the_three_levels(operator_user, script):
    """REQ-024, REQ-030: las filas técnicas son las mismas en media, alta y exigente para el
    mismo pliego, también cuando solo una de las dos extracciones marca el tramo como
    técnico."""
    rows = {}
    for level in ("media", "alta", "exigente"):
        script.reset()
        if level == "exigente":
            script.when_pass("extraccion", ENTREGA, item(discard="dato_procedimiento"))
            script.when_pass("extraccion_2", ENTREGA, item(technical=[ALL_ITEMS]))
        else:
            script.when(ENTREGA, item(technical=[ALL_ITEMS]))
        run = run_level(operator_user, level, three_items_pdf())
        rows[level] = [
            (r.items, [(q.segment.key, q.scope) for q in
                       r.quotes.order_by("order").select_related("segment")])
            for r in m.Requirement.objects.filter(version=run.version, category="tecnico")
            .order_by("number")
        ]

    assert len(rows["media"]) == 3
    assert rows["media"] == rows["alta"] == rows["exigente"]
    assert ("sec-i/3.1", "general") in rows["exigente"][0][1]


def test_each_level_records_its_own_passes(operator_user, script):
    """REQ-030: cada nivel registra sus pasadas en la propuesta, en los pedidos al modelo y en
    las versiones de las instrucciones; sin la anomalía de "nivel sin pasadas propias"."""
    standard(script)
    expected = {
        "media": (["extraccion"], ["extraccion"]),
        "alta": (["extraccion", "completitud"], ["extraccion", "completitud"]),
        "exigente": (["extraccion", "extraccion_2", "completitud"],
                     ["extraccion", "extraccion_2", "completitud"]),
    }
    for level, (steps, _) in expected.items():
        run = run_level(operator_user, level)
        assert list(dict.fromkeys(step_passes(run))) == steps, level
        assert "nivel_sin_pasadas_propias" not in [a["type"] for a in run.anomalies]
        assert run.level == level and run.version.level == level
        prompts = list(run.prompt_versions)
        assert prompts == (["extraccion", "completitud"] if level != "media"
                           else ["extraccion"])
    assert run.parameters["passes"] == [
        "reglas", "extraccion", "extraccion_2", "union", "completitud", "filas_tecnicas"]


# --- Citas sobre tramos con saltos de línea y espacios distintos (O1 de T-073) -----------------------

TABLA_TEXT = "deberá mantener la oferta durante:\n60 días corridos"


def table_pdf():
    """Un tramo de tabla: sus filas quedan separadas por saltos de línea reales."""
    return tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PLAZOS"),
        table(("CONCEPTO", "DETALLE"),
              ("El oferente deberá mantener", "la oferta durante:"),
              ("60 días corridos", "como mínimo")),
    ]])


def table_requirement(run):
    requirement = m.Requirement.objects.get(version=run.version)
    return requirement, requirement.quotes.get()


@pytest.mark.parametrize("level", ["media", "alta", "exigente"])
def test_extraction_quote_across_line_breaks_and_double_spaces(operator_user, script, level):
    """REQ-025: la cita que el modelo copia de un tramo de tabla, con espacios dobles y un
    espacio donde el tramo tiene un salto de línea, se ubica y se guarda como el recorte
    literal del tramo (con su salto de línea)."""
    script.when("CONCEPTO", item([("deberá  mantener la oferta  durante: 60 días corridos",
                                   "formal")]))

    run = run_level(operator_user, level, table_pdf())

    _, quote = table_requirement(run)
    assert "\n" in quote.text
    assert quote.text == TABLA_TEXT
    assert quote.quote_flag == ""
    check_quotes_are_canonical(run)


def test_completeness_quote_across_line_breaks_and_double_spaces(operator_user, script):
    """REQ-025: lo mismo para la cita de un requisito que suma la completitud sobre un tramo
    de tabla descartado con marcadores: se ubica pese a los espacios y se guarda literal."""
    script.complete_when("CONCEPTO", fix(missing=[
        ("deberá   mantener la oferta durante:  60 días corridos", "formal")]))

    run = run_level(operator_user, "alta", table_pdf())

    requirement, quote = table_requirement(run)
    assert requirement.passes == ["completitud"]
    assert quote.text == TABLA_TEXT and "\n" in quote.text
    assert quote.quote_flag == ""
    check_quotes_are_canonical(run)


def test_completeness_split_across_line_breaks(operator_user, script):
    """REQ-025: una división cuyas partes cruzan el salto de línea del tramo también queda con
    citas literales."""
    script.when("CONCEPTO", item([("deberá mantener la oferta durante: 60 días corridos",
                                   "formal")]))
    script.complete_when("CONCEPTO", fix(splits=[(
        "deberá mantener la oferta durante: 60 días corridos",
        [("deberá mantener la oferta", "formal"), ("durante: 60  días corridos", "formal")],
    )]))

    run = run_level(operator_user, "alta", table_pdf())

    texts = [q.text for q in m.RequirementQuote.objects.filter(
        requirement__version=run.version).order_by("char_start")]
    assert texts == ["deberá mantener la oferta", "durante:\n60 días corridos"]
    check_quotes_are_canonical(run)
