"""Proceso único: completitud y sin segunda extracción (REQ-024, REQ-025,
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
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.proposal.extraction import ALL_ITEMS, Found
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
DJ_FULL = "La oferta deberá incluir " + DJ
CONSTANCIA = "la constancia de inscripción en el registro de proveedores"
MANT = "Los oferentes deberán mantener la oferta durante 60 días corridos."
MANT_QUOTE = "mantener la oferta durante 60 días corridos"
NOALT = "No se aceptarán ofertas alternativas sin certificado de inscripción en el registro."
OBJETO = "El objeto de la contratación es la adquisición de bienes sintéticos."
TECNICO = "Los bienes deberán tener vencimiento mayor a once meses."
RENGLON = "Bolsa de veinte kilogramos con rótulo sintético."

INVALID = "invalida"  # respuesta de la completitud con la forma rota


def clause(number, text):
    """Las líneas de una cláusula, cortadas como en una página."""
    return textwrap.wrap(f"{number} {text}", 78)


def completeness_pdf(docs=DOCS):
    """Condiciones con dos requisitos juntos, uno solo, un tramo con marcadores y otro sin;
    especificaciones técnicas con marcadores, y dos renglones. `docs` es el texto de la
    cláusula 1.1."""
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. PRESENTACIÓN", *clause("1.1.", docs), *clause("1.2.", MANT)),
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


def fix(missing=()):
    """Lo que la completitud devuelve para un tramo (T-236: solo los faltantes; ya no hay
    divisiones)."""
    return {"faltantes": [{"cita": quote, "clase": kind} for quote, kind in missing]}


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


def run_level(user, pdf=None):
    procedure = make_procedure(user)
    load_and_read(user, procedure, pdf or completeness_pdf())
    requested, job = propose(user, procedure)
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


# --- Completitud ---------------------------------------------------------------------------


DOMICILIO = "Los oferentes deberán acreditar un domicilio constituido en la ciudad."
DOMICILIO_QUOTE = "acreditar un domicilio constituido"


def test_alta_adds_the_missing_requirement_with_a_verified_quote(operator_user, script):
    """REQ-024, REQ-025, REQ-030, REQ-101: un faltante que la completitud devuelve se suma al
    tramo con su cita ubicada en el texto del pliego, ampliada a su oración; el tramo se
    mandó con lo ya encontrado (la oración completa que halló la extracción)."""
    standard(script)
    script.when(DOCS, item([(DJ, "formal")]))
    script.complete_when("domicilio", fix(missing=[(DOMICILIO_QUOTE, "formal")]))

    run = run_level(operator_user, completeness_pdf(docs=f"{DOCS} {DOMICILIO}"))

    assert body(run)["sec-i/1.1"] == [
        (DOCS, ["extraccion"], "formal"),
        (DOMICILIO, ["completitud"], "formal"),
    ]
    check_quotes_are_canonical(run)
    sent = next(call for call in script.completeness_calls
                if any("domicilio" in b["text"] for b in call.values()))
    assert f"1. {DOCS} (formal)" in next(iter(sent.values()))["raw"]
    added = m.Requirement.objects.get(version=run.version, passes=["completitud"])
    assert added.step.pass_name == "completitud"
    assert run.counts["completeness"]["added"] == 1
    assert disposition(run, "sec-i/1.1").outcome == "requisitos"
    step = added.step
    (record,) = step.parsed["tramos"]["T1"]["requisitos_agregados"]
    assert record["fragmentos"][0]["texto"] == DOMICILIO_QUOTE
    segment = added.quotes.get().segment
    assert segment.text[record["oracion"]["inicio"]:record["oracion"]["fin"]] == DOMICILIO


def test_a_missing_requirement_inside_a_sentence_already_found_is_not_added(
        operator_user, script):
    """REQ-101: la constancia es parte de la misma oración que la extracción ya halló: una
    fila por oración, así que la completitud no suma otra."""
    standard(script)
    script.when(DOCS, item([(DJ, "formal")]))
    script.complete_when("constancia", fix(missing=[(CONSTANCIA, "formal")]))

    run = run_level(operator_user)

    assert body(run)["sec-i/1.1"] == [(DOCS, ["extraccion"], "formal")]
    assert run.counts["completeness"]["added"] == 0


def test_alta_discarded_with_markers_goes_to_completeness_and_is_not_pending(
        operator_user, script):
    """REQ-024: un tramo que el modelo descartó teniendo marcadores de obligación pasa por la
    completitud; si ésta encuentra un requisito, lo suma; si no, queda descartado y no
    pendiente."""
    standard(script)
    script.when(DOCS, item([(DJ, "formal"), (CONSTANCIA, "formal")]))
    script.complete_when("alternativas", fix(missing=[(NOALT, "economico")]))

    run = run_level(operator_user)

    assert body(run)["sec-i/2.1"] == [(NOALT, ["completitud"], "economico")]
    assert disposition(run, "sec-i/2.1").outcome == "requisitos"
    assert "sec-i/2.1" not in pending(run)

    script.complete_rules.clear()
    run = run_level(operator_user)
    assert disposition(run, "sec-i/2.1").outcome == "descartado"
    assert disposition(run, "sec-i/2.1").discard_reason == "dato_procedimiento"
    assert "sec-i/2.1" not in pending(run)


def test_completeness_sends_only_model_segments_with_requirements_or_markers(
        operator_user, script):
    """REQ-024: a la completitud solo llegan tramos formales y económicos que pasaron por el
    modelo: con requisitos o descartados con marcadores. No llegan los de secciones técnicas
    (aunque tengan "deberá"), ni los descartados sin marcadores."""
    standard(script)

    run = run_level(operator_user)
    sent = [text.split(" ", 1)[1] for text in script.sent_to_completeness()]
    assert sorted(sent) == sorted([DOCS, MANT, NOALT])
    assert disposition(run, "sec-ii/1.1").outcome == "tecnico"


def test_an_invalid_completeness_answer_is_asked_again_once_and_then_leaves_it_pending(
        operator_user, script):
    """REQ-024, REQ-028: una salida de la completitud con la forma rota se vuelve a pedir una
    vez, solo ese tramo; si sigue rota, el descartado con marcadores queda pendiente y lo ya
    encontrado no cambia."""
    standard(script)
    script.complete_when("alternativas", INVALID)

    run = run_level(operator_user)

    asked = [b for call in script.completeness_calls for b in call.values()
             if b["text"].endswith(NOALT)]
    assert len(asked) == 2
    assert pending(run)["sec-i/2.1"] == "marcadores"
    assert disposition(run, "sec-i/2.1").outcome == "pendiente"
    assert body(run)["sec-i/1.2"] == [(MANT, ["extraccion"], "formal")]
    assert "completitud_sin_resultado" in [a["type"] for a in run.anomalies]


# --- Completitud: casos del módulo ------------------------------------------------------------


def unit_of(text, section_class=""):
    segment = SimpleNamespace(pk=1, key="sec-i/1.1", text=text, section_class=section_class)
    return SimpleNamespace(segment=segment)


def test_containment_is_the_fraction_of_the_inner_quote_inside_the_outer():
    """REQ-024: cuánto de una cita está dentro de otra se mide sobre sus propios caracteres."""
    assert completeness.containment((0, 10), (0, 10)) == 1
    assert completeness.containment((0, 10), (5, 40)) == 0.5
    assert completeness.containment((5, 40), (0, 10)) == pytest.approx(5 / 35)
    assert completeness.containment((0, 10), (10, 20)) == 0


def test_a_missing_requirement_that_repeats_a_found_one_is_not_added():
    """REQ-024: un faltante que se superpone en más de la mitad con un requisito ya
    encontrado del tramo no se suma."""
    unit = unit_of("Los oferentes deberán mantener la oferta durante 60 días corridos.")
    found = [Found("formal", (22, 64))]
    anomalies = []

    final, added = completeness.apply(
        unit, found, [("la oferta durante 60 días corridos", "formal")], anomalies)

    assert final == found and added == 0


def test_a_missing_quote_that_is_not_in_the_segment_is_kept_as_a_wide_quote():
    """REQ-025: un faltante cuya cita no está en el tramo queda con el tramo entero como
    cita (cita_amplia), una por clase, y la anomalía lo dice."""
    unit = unit_of("El pago se efectuará a los 90 días.")
    anomalies = []

    final, added = completeness.apply(
        unit, [], [("texto que no está", "economico"), ("otro que tampoco", "economico")],
        anomalies)

    assert [(f.category, f.span, f.flag) for f in final] == [
        ("economico", (0, len(unit.segment.text)), WIDE)]
    assert completeness.passes_of(final[0]) == ["completitud"] and added == 1
    assert [a["type"] for a in anomalies] == ["completitud_cita_no_encontrada"] * 2


def test_a_missing_requirement_is_added_next_to_a_wide_quote_of_its_class():
    """REQ-024: un faltante bien ubicado se suma aunque el tramo ya tenga una cita amplia de
    su clase."""
    unit = unit_of("Los oferentes deberán mantener la oferta durante 60 días corridos.")
    wide = Found("formal", (0, len(unit.segment.text)), flag=WIDE)

    final, added = completeness.apply(
        unit, [wide], [("mantener la oferta durante 60 días corridos", "formal")], [])

    assert added == 1 and [f.flag for f in final] == [WIDE, ""]


def test_only_model_dispositions_reach_the_completeness():
    """REQ-024: a la completitud solo llegan tramos que pasaron por el modelo. Un título
    descartado por regla con una palabra de obligación no llega."""
    title = unit_of("DOCUMENTACIÓN QUE DEBERÁ PRESENTARSE")
    loaded = SimpleNamespace(units=[title])

    by_rule = {1: proposal.Decision("descartado", discard_reason="titulo")}
    by_model = {1: proposal.Decision("descartado", discard_reason="dato_procedimiento",
                                     source="modelo")}

    assert proposal.completeness_candidates(loaded, by_rule) == []
    assert [c.unit for c in proposal.completeness_candidates(loaded, by_model)] == [title]


def test_the_class_of_every_requirement_is_validated_in_the_answer():
    """REQ-028: una clase fuera de formal y económico (por ejemplo, técnico) invalida la salida
    de la completitud, y una salida con `divisiones` (que ya no existen) tampoco vale."""
    good = {"cita": "x", "clase": "formal"}
    bad = {"cita": "x", "clase": "tecnico"}

    assert completeness.shape_item({"faltantes": [good]})
    with pytest.raises(completeness.InvalidItem):
        completeness.shape_item({"faltantes": [bad]})
    with pytest.raises(completeness.InvalidItem):
        completeness.shape_item({"faltantes": [], "divisiones": []})


# --- Proceso único: pasadas y filas técnicas ---------------------------------------------------


def test_the_single_process_has_no_second_extraction(operator_user, script):
    """REQ-030: el proceso único no hace segunda extracción ni unión: las pasadas registradas
    son extracción, completitud y consecuencias, y los parámetros nombran las del proceso."""
    standard(script)

    run = run_level(operator_user)

    assert list(dict.fromkeys(step_passes(run))) == ["extraccion", "completitud",
                                                      "unificacion", "filtro", "filtro_2", "consecuencias"]
    assert run.parameters["passes"] == [
        "reglas", "extraccion", "completitud", "union_oraciones", "unificacion", "filtro",
        "filas_tecnicas", "consecuencias"]
    assert "extraccion_2" not in run.counts["model_requests_by_pass"]
    assert not hasattr(completeness, "second_extraction")
    assert not hasattr(completeness, "union")


def test_the_process_records_its_process_and_the_instructions_it_used(operator_user, script):
    """REQ-030: la propuesta registra el proceso en la propuesta y en la versión, y las
    versiones de las instrucciones de extracción, completitud y consecuencias."""
    standard(script)

    run = run_level(operator_user)

    assert run.process == "completo" and run.version.process == "completo"
    assert set(run.prompt_versions) == {"extraccion", "completitud", "union", "filtro",
                                        "consecuencias", "definiciones", "huellas"}
    assert set(run.prompt_versions["huellas"]) == {"extraccion", "completitud", "union", "filtro",
                                                   "consecuencias", "definiciones"}


def test_technical_rows_come_from_the_rule_and_a_marked_segment_joins_them(
        operator_user, script):
    """REQ-024, REQ-030: las filas técnicas son una por renglón y un tramo marcado como
    técnico para todos los renglones entra en las tres."""
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))
    run = run_level(operator_user, three_items_pdf())
    rows = [
        (r.items, [(q.segment.key, q.scope) for q in
                   r.quotes.order_by("order").select_related("segment")])
        for r in m.Requirement.objects.filter(version=run.version, category="tecnico")
        .order_by("number")
    ]

    assert len(rows) == 3
    assert ("sec-i/3.1", "general") in rows[0][1]


# --- Citas sobre tramos con saltos de línea y espacios distintos (O1 de T-073) -----------------------

# Las celdas de una fila van separadas por una tabulación (T-259, `tables.with_cells`): la cita
# que el modelo copia con espacios se ubica igual y su recorte literal trae la tabulación.
TABLA_TEXT = "deberá mantener\tla oferta durante:\n60 días corridos"


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


def test_extraction_quote_across_line_breaks_and_double_spaces(operator_user, script):
    """REQ-025: la cita que el modelo copia de un tramo de tabla, con espacios dobles y un
    espacio donde el tramo tiene un salto de línea, se ubica y se guarda como el recorte
    literal del tramo (con su salto de línea)."""
    script.when("CONCEPTO", item([("deberá  mantener la oferta  durante: 60 días corridos",
                                   "formal")]))

    run = run_level(operator_user, table_pdf())

    _, quote = table_requirement(run)
    assert "\n" in quote.text
    assert quote.text == TABLA_TEXT
    assert quote.quote_flag == ""
    check_quotes_are_canonical(run)


def test_a_table_quote_stays_the_models_fragment(operator_user, script):
    """REQ-101: el texto de una tabla no tiene oraciones (sus celdas son líneas): la cita de un
    tramo `tabla` no se amplía y queda en el fragmento que señaló el modelo."""
    script.when("CONCEPTO", item([("la oferta durante:", "formal")]))

    run = run_level(operator_user, table_pdf())

    _, quote = table_requirement(run)
    assert quote.text == "la oferta durante:"
    assert quote.quote_flag == ""
    check_quotes_are_canonical(run)


def test_completeness_quote_across_line_breaks_and_double_spaces(operator_user, script):
    """REQ-025: lo mismo para la cita de un requisito que suma la completitud sobre un tramo
    de tabla descartado con marcadores: se ubica pese a los espacios y se guarda literal."""
    script.complete_when("CONCEPTO", fix(missing=[
        ("deberá   mantener la oferta durante:  60 días corridos", "formal")]))

    run = run_level(operator_user, table_pdf())

    requirement, quote = table_requirement(run)
    assert requirement.passes == ["completitud"]
    assert quote.text == TABLA_TEXT and "\n" in quote.text
    assert quote.quote_flag == ""
    check_quotes_are_canonical(run)


# --- T-093: instrucciones v2, marcadores nuevos y tablas que no se descartan ----------------------

ENUM = ("Los precios se expresarán en dólares estadounidenses, no incluirán el flete y "
        "serán válidos por 30 días.")
ENUM_PARTS = [("Los precios se expresarán en dólares estadounidenses", "economico"),
              ("no incluirán el flete", "economico"),
              ("serán válidos por 30 días", "economico")]
EFECTO = "Las ofertas que no acompañen el certificado de visita quedarán descalificadas."


def enumeration_pdf():
    return tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PRECIOS", *clause("1.1.", ENUM)),
        para("2. VISITA", *clause("2.1.", EFECTO)),
    ]])


@pytest.mark.parametrize("name", ["extraccion", "completitud"])
def test_prompts_v4_are_active_and_teach_sentences_effects_and_the_definitions(name):
    """REQ-101, REQ-102: las instrucciones activas son las v4 (T-236): llevan el bloque común de
    definiciones, piden la oración completa (una fila por unidad de sentido, sin dividir
    enumeraciones) y reconocen las condiciones dichas como efecto. Las v1 siguen como estaban."""
    from django.conf import settings

    assert settings.MATRIX_PROMPT_VERSIONS[name] == {
        "extraccion": "matriz-extraccion-v10", "completitud": "matriz-completitud-v6"}[name]
    text = extraction.load_prompt(name)
    assert extraction.DEFINITIONS_MARK not in text
    for phrase in ("QUÉ ES UN REQUISITO DE LA OFERTA", "Una fila es una unidad de sentido",
                   "se considerará", "se entenderá", "quedará", "oración completa"):
        assert phrase in text
    old = (extraction.PROMPTS_DIR / f"matriz-{name}-v1.md").read_text(encoding="utf-8")
    assert "se entenderá" not in old and "comas o por" not in old


@pytest.mark.parametrize("name", ["extraccion", "completitud"])
def test_prompts_v4_have_none_of_the_rules_that_push_to_the_error(name):
    """REQ-101, REQ-102 (ADR-0054, reglas 3 y 7): ni «dividí», ni «fragmento más corto», ni
    «divisiones»; «ante la duda, proponé de más» queda solo en la extracción y limitado a lo
    que le exige algo a todas las ofertas."""
    text = extraction.load_prompt(name).lower()
    for phrase in ("dividí", "fragmento más corto", "divisiones", "ante la duda, proponé de más",
                   "forma y plazo de pago", "forma de presentar la oferta)", "mantené"):
        assert phrase not in text
    if name == "extraccion":
        assert "ante la duda de si una oración le exige algo a todas las ofertas" in text


def test_the_completeness_asks_only_for_missing_requirements():
    """REQ-101 (ADR-0054, regla 3): la completitud no divide: su esquema solo trae `faltantes`."""
    schema = completeness.build_schema(["T1"])

    assert list(schema["properties"]["T1"]["properties"]) == ["faltantes"]
    assert schema["properties"]["T1"]["required"] == ["faltantes"]


@pytest.mark.parametrize("text", [
    "Se considerará válida la oferta", "SE ENTENDERÁ que acepta", "La oferta quedará excluida",
    "las ofertas quedarán descalificadas", "Se considerarán prorrogadas",
])
def test_effect_markers_are_obligation_markers(text):
    """REQ-028: "se considerará", "se entenderá" y "quedará" (también en plural y sin
    tildes ni mayúsculas) son marcadores de obligación."""
    assert proposal.has_obligation_markers(text)


def test_extraction_gives_one_row_per_sentence_for_an_enumeration(operator_user, script):
    """REQ-025, REQ-101 (decisión del 2026-10-10, «una fila por oración»): la oración con tres
    condiciones que el modelo devuelve en tres fragmentos queda en un solo requisito, con la
    oración completa como cita literal."""
    script.when(ENUM, item(ENUM_PARTS))

    run = run_level(operator_user, enumeration_pdf())

    rows = body(run)["sec-i/1.1"]
    assert [text for text, _, _ in rows] == [ENUM]
    check_quotes_are_canonical(run)


def test_effect_condition_is_a_candidate_and_is_added_by_completeness(operator_user, script):
    """REQ-028, REQ-024: un tramo que el modelo descartó y dice la condición como efecto
    ("quedarán…") llega a la completitud por el marcador, y el requisito que ésta agrega
    queda en la matriz."""
    script.complete_when(EFECTO, fix(missing=[(EFECTO, "formal")]))

    run = run_level(operator_user, enumeration_pdf())

    assert any(EFECTO in text for text in script.sent_to_completeness())
    assert [text for text, _, _ in body(run)["sec-i/2.1"]] == [EFECTO]


def plain_table_pdf():
    """Una tabla sin marcadores de obligación."""
    return tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. DATOS"),
        table(("CONCEPTO", "OPCIÓN"), ("Modalidad", "Por lote X"), ("Idioma", "Español")),
    ]])


@pytest.mark.parametrize("pdf", [table_pdf, plain_table_pdf], ids=["con_marcadores", "sin_marcadores"])
def test_a_table_is_never_discarded(operator_user, script, pdf):
    """REQ-028: si el modelo descarta un tramo de tabla (con o sin marcadores de obligación),
    el tramo queda pendiente con el motivo `tabla`, no descartado."""
    run = run_level(operator_user, pdf())

    tables = m.Segment.objects.filter(
        reading__document__procedure=run.procedure, segment_type="tabla")
    assert tables.exists()
    for segment in tables:
        found = m.Disposition.objects.get(run=run, segment=segment)
        assert found.outcome == "pendiente"
        assert found.discard_reason == ""
        assert pending(run)[segment.key] == "tabla"
    assert not m.Disposition.objects.filter(
        run=run, segment__in=tables, outcome="descartado").exists()


def test_a_table_with_rows_proposed_by_completeness_stays_a_requirement(operator_user, script):
    """REQ-028: la regla de tablas no quita lo que la completitud le encontró a una tabla:
    queda con requisitos y sigue figurando como pendiente de lectura."""
    script.complete_when("CONCEPTO", fix(missing=[
        ("deberá mantener la oferta durante: 60 días corridos", "formal")]))

    run = run_level(operator_user, table_pdf())

    key = m.Segment.objects.get(
        reading__document__procedure=run.procedure, segment_type="tabla").key
    assert disposition(run, key).outcome == "requisitos"
    assert pending(run)[key] == "tabla"


def test_every_request_of_the_completeness_records_its_instruction(operator_user, script):
    """REQ-106, P6: el `parsed` de cada pedido de la completitud trae el nombre, la versión y la
    huella de su instrucción y la versión y la huella del bloque común."""
    standard(script)

    run = run_level(operator_user)

    found = list(m.RunStep.objects.filter(run=run, pass_name="completitud"))
    assert found
    expected = extraction.load_instruction("completitud").record
    assert expected["version"] == "matriz-completitud-v6"
    for step in found:
        assert step.parsed["instruccion"] == expected
        assert step.parsed["instruccion"]["definiciones"]["version"] == "matriz-definiciones-v7"
