"""El modelo extrae la lista de cambios de una unidad de circular (REQ-031, REQ-028; plan 003,
"Rediseño de la pasada de circulares", entrega 2; ADR-0023; T-115).

El doble del modelo es el de `test_circulars.py` ampliado: responde los pedidos de la
extracción (esquema con `cambios`) con lo que dice el guion. Todo el texto es inventado y
no repite el de ningún caso (P4); sin modelo real ni GPU. Las circulares de estas pruebas
no tienen un verbo que la entrega 1 reconozca, para que la unidad llegue a la extracción.
"""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import circular_changes as changes
from evaluon.tenders.proposal import extraction
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import PAGO, load_and_read
from tests.tenders.test_circular_units import (
    GA,
    GB,
    HASHES,
    PLAZO,
    _shingles,
    guarantee_case,
    unit_steps,
)
from tests.tenders.test_circulars import (  # noqa: F401  (case es una fixture)
    RAM,
    CircularScript,
    add_circular,
    case,
    requirement_with,
    row_of_item,
    run_proposal,
)

pytestmark = pytest.mark.django_db

NEW_GUARANTEE = "La garantía de oferta pasa a ser del diez por ciento y se constituirá en dólares"
GUARANTEE_LINE = f"1. {NEW_GUARANTEE}, conforme a la cláusula 3.1."


def change(kind, target="ninguno", reference="", old="", new=""):
    return {"tipo": kind, "objetivo": target, "referencia": reference, "texto_anterior": old,
            "texto_nuevo": new}


class ExtractionScript(CircularScript):
    """`x_when(texto_de_la_unidad, *salidas)`: responde a todo pedido de extracción cuya unidad
    contiene el texto, una salida por pedido (la última se repite). Una salida es la lista de
    cambios, un texto sin tocar o `"timeout"`. Sin regla, no hay cambios. `extractions` guarda
    cada pedido."""

    def __init__(self, fake, monkeypatch):
        super().__init__(fake, monkeypatch)
        self.x_rules = []
        self.extractions = []

    def x_when(self, needle, *outputs):
        self.x_rules.insert(0, (needle, list(outputs)))

    def _generate(self, messages, schema, **options):
        if "cambios" not in schema.get("properties", {}):
            return super()._generate(messages, schema, **options)
        user = messages[-1]["content"]
        text = user.partition("\nTexto:\n")[2].rpartition("\n\nDevolvé")[0]
        self.extractions.append({"messages": messages, "schema": schema, "text": text})
        output = []
        for needle, outputs in self.x_rules:
            if needle in text:
                output = outputs.pop(0) if len(outputs) > 1 else outputs[0]
                break
        if output == "timeout":
            self.fake.timeout()
        elif isinstance(output, str):
            self.fake.respond(output)
        else:
            self.fake.respond(json.dumps({"cambios": output}, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)

    def asked(self, needle):
        return [e for e in self.extractions if needle in e["text"]]


@pytest.fixture
def script(fake_generation, monkeypatch):
    return ExtractionScript(fake_generation, monkeypatch)


def extraction_steps(needle=""):
    steps = m.RunStep.objects.filter(pass_name="circulares_cambios").order_by("id")
    return [s for s in steps if needle in s.request["messages"][-1]["content"]]


def fallback_asked(script, *needles):
    """Los pedidos del flujo de candidatas (respaldo) cuyo tramo contiene alguna frase."""
    return [r for r in script.requests if any(n in r["tramo"] for n in needles)]


def sources_of(version):
    return list(m.RequirementSource.objects.filter(requirement__version=version))


# --- Una cláusula con dos citas, por la lista de cambios ------------------------------------------------


def test_a_change_with_a_clause_target_is_applied_to_every_citation_of_the_clause(
        operator_user, script):
    """REQ-031: la unidad no tiene un verbo que la entrega 1 reconozca; el modelo devuelve un
    cambio de objetivo cláusula 3.1 y el código lo aplica por clave a las dos citas de la
    cláusula (una fuente cada una, con el texto de la circular), sin elegir citas del
    pliego."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when("pasa a ser", [change("reemplaza", "clausula", "3.1", "", NEW_GUARANTEE)])

    version, run = run_proposal(operator_user, procedure)

    for text in (GA, GB):
        source = requirement_with(version, text).sources.get()
        assert source.effect == "modifica" and source.issued_on == date(2025, 12, 1)
        assert source.text == NEW_GUARANTEE
        canonical = source.segment.reading.canonical_text
        assert canonical[source.char_start:source.char_end] == source.text
        assert source.step.pass_name == "circulares_cambios"
    assert not requirement_with(version, PLAZO).sources.exists()
    assert not fallback_asked(script, "pasa a ser")      # el flujo de candidatas no se usó
    step = unit_steps()[-1]
    assert step.parsed["resultado"] == "aplicada" and len(step.parsed["fuentes"]) == 2


def test_the_model_sees_only_the_unit_and_never_the_tender(operator_user, script):
    """REQ-031: el pedido lleva el documento y el texto de la unidad; ninguna cita del pliego.
    La salida está obligada por un esquema con los cinco campos de cada cambio."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)

    run_proposal(operator_user, procedure)

    request = script.asked("pasa a ser")[0]
    content = request["messages"][-1]["content"]
    assert "Circular N.º 4" in content and "pasa a ser" in content
    for text in (GA, GB, PLAZO, PAGO):
        assert text not in content and text not in request["messages"][0]["content"]
    assert "Citas del pliego" not in content
    item_schema = request["schema"]["properties"]["cambios"]["items"]
    assert set(item_schema["required"]) == {"tipo", "objetivo", "referencia",
                                            "texto_anterior", "texto_nuevo"}
    assert item_schema["properties"]["tipo"]["enum"] == [
        "reemplaza", "suprime", "agrega", "aclara", "dato_del_tramite"]
    assert item_schema["properties"]["objetivo"]["enum"] == [
        "clausula", "anexo", "renglon", "ninguno"]


def test_the_request_records_model_parameters_instructions_version_and_unit(
        operator_user, script, settings):
    """REQ-031 / P6: el pedido de la extracción queda en `tenders_run_step` con el modelo, los
    parámetros, la versión de las instrucciones, la unidad y lo que el modelo devolvió."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when("pasa a ser", [change("reemplaza", "clausula", "3.1", "", NEW_GUARANTEE)])

    run_proposal(operator_user, procedure)

    step = extraction_steps("pasa")[0]
    request = step.request
    assert request["model"] == settings.GENERATION_MODEL
    assert request["temperature"] == settings.GENERATION_TEMPERATURE
    assert request["seed"] == settings.GENERATION_SEED
    assert request["max_tokens"] == settings.MATRIX_MAX_OUTPUT_TOKENS
    assert request["instrucciones"] == "matriz-circulares-v5"
    assert request["unidad"]["tipo"] == "clausula" and len(request["unidad"]["tramos"]) == 1
    assert step.segment_keys == request["unidad"]["tramos"]
    assert step.parsed["valida"] is True
    assert step.parsed["cambios"][0]["objetivo"] == "clausula"
    assert json.loads(step.raw_output)["cambios"][0]["referencia"] == "3.1"
    assert step.request["messages"][0]["content"] == extraction.load_prompt("circulares_cambios")


# --- Lo que no tiene objetivo va al respaldo -----------------------------------------------------------


def test_a_change_without_a_target_goes_to_the_fallback_flow(operator_user, case, script):
    """REQ-031: un cambio de objetivo "ninguno" sin texto anterior no se puede ubicar por clave;
    el tramo pasa al flujo de candidatas y ahí el modelo elige la cita. La fuente queda con su
    pedido de la pasada `circulares`."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria del equipo pasa a ser de 32 GB de RAM.")
    script.x_when("pasa a ser", [change("reemplaza", "ninguno", "", "", "32 GB de RAM")])
    script.c_when("pasa a ser", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    assert fallback_asked(script, "pasa a ser")
    source = row_of_item(version, 1).sources.get()
    assert source.effect == "modifica" and source.step.pass_name == "circulares"
    last = unit_steps()[-1]
    assert last.parsed["resultado"] == "aplicada"
    assert last.parsed["objetivo"]["cambios"][0]["motivo"] == "sin_objetivo"


def test_the_old_text_of_a_change_finds_the_citation_without_the_fallback(
        operator_user, case, script):
    """REQ-031: con el texto anterior ("16 GB de RAM") el código ubica la única cita que lo
    contiene y aplica el cambio por clave: el flujo de candidatas no corre."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria pasa de 16 GB de RAM a 32 GB de RAM.")
    script.x_when("pasa de", [change("reemplaza", "ninguno", "", "16 GB de RAM",
                                     "32 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    source = row_of_item(version, 1).sources.get()
    assert source.effect == "modifica" and source.text == "32 GB de RAM"
    assert RAM in source.quote.text
    assert not row_of_item(version, 2).sources.exists()
    assert not fallback_asked(script, "pasa", "representante", "se abrirán")


def test_a_new_clause_the_tender_lacks_becomes_a_requirement(operator_user, case, script):
    """REQ-031: un cambio `agrega` de una cláusula que el pliego no tiene crea un requisito de
    origen `circular` con la cita literal en la circular."""
    document = add_circular(
        operator_user, case, "Circular N.º 3", date(2025, 12, 7),
        "1. Los oferentes deberán informar el nombre de su representante, cláusula 9.9.")
    script.x_when("representante", [change(
        "agrega", "clausula", "9.9", "",
        "Los oferentes deberán informar el nombre de su representante")])

    version, _ = run_proposal(operator_user, case)

    new = version.requirements.get(origin="circular")
    quote = new.quotes.get()
    assert quote.text == "Los oferentes deberán informar el nombre de su representante"
    assert quote.segment.reading.document == document
    assert not fallback_asked(script, "pasa", "representante", "se abrirán")


def test_data_of_the_procedure_creates_no_requirement(operator_user, case, script):
    """REQ-031: un cambio `dato_del_tramite` no tiene efecto: el tramo queda descartado como
    dato del procedimiento."""
    document = add_circular(operator_user, case, "Circular N.º 3", date(2025, 12, 7),
                            "1. Las ofertas se abrirán el 3 de marzo en la sede central.")
    script.x_when("se abrirán", [change("dato_del_tramite")])

    version, run = run_proposal(operator_user, case)

    assert not sources_of(version)
    segment = m.Segment.objects.get(reading__document=document, text__contains="se abrirán")
    disposition = m.Disposition.objects.get(run=run, segment=segment)
    assert disposition.outcome == "descartado"
    assert disposition.discard_reason == "dato_procedimiento"
    assert not fallback_asked(script, "pasa", "representante", "se abrirán")


# --- Citas literales verificadas contra la unidad ----------------------------------------------------------


def test_a_quote_that_is_not_in_the_unit_is_asked_again_and_then_not_applied(
        operator_user, script):
    """REQ-031: un texto nuevo que no está en la unidad se vuelve a pedir una vez; si sigue sin
    estar, el cambio no se aplica en firme y queda registrado. Nada se escribe con un texto
    que la circular no dice."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when("pasa a ser", [change("reemplaza", "clausula", "3.1", "",
                                        "La garantía será del veinte por ciento")])

    version, run = run_proposal(operator_user, procedure)

    steps = extraction_steps("pasa")
    assert len(steps) == 2 and steps[1].retry_of == steps[0]
    assert steps[0].anomalies[0]["type"] == "circular_cambio_cita_inexistente"
    assert not sources_of(version)
    types = {a["type"] for a in run.anomalies}
    assert {"circular_cambio_cita_inexistente", "circular_cambio_sin_resolver"} <= types
    assert step_motive() == "cita_inexistente"


def step_motive():
    last = unit_steps()[-1]
    return last.parsed["objetivo"]["cambios"][0]["motivo"]


def test_a_quote_fixed_by_the_second_request_is_applied(operator_user, script):
    """REQ-031: si el reintento devuelve el texto tal como está en la unidad, el cambio se
    aplica; el segundo pedido queda enlazado al primero."""
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when(
        "pasa a ser",
        [change("reemplaza", "clausula", "3.1", "", "La garantía será del diez por ciento")],
        [change("reemplaza", "clausula", "3.1", "", NEW_GUARANTEE)])

    version, _ = run_proposal(operator_user, procedure)

    steps = extraction_steps("pasa")
    assert len(steps) == 2 and steps[1].retry_of == steps[0]
    assert {s.text for s in sources_of(version)} == {NEW_GUARANTEE}
    assert len(sources_of(version)) == 2


# --- Repetición y estabilidad ----------------------------------------------------------------------------------


def test_equal_repetitions_are_accepted(operator_user, script, settings):
    """REQ-031: con dos repeticiones que dan el mismo cambio (mismo tipo, objetivo y texto) el
    cambio se acepta; cada repetición queda como un pedido."""
    settings.CIRCULAR_EXTRACTION_REPEATS = 2
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when("pasa a ser", [change("reemplaza", "clausula", "3.1", "", NEW_GUARANTEE)])

    version, run = run_proposal(operator_user, procedure)

    assert len(script.asked("pasa a ser")) == 2
    assert [s.request["repeticion"] for s in extraction_steps("pasa")] == [1, 2]
    assert len(sources_of(version)) == 2
    assert "circular_cambio_no_estable" not in {a["type"] for a in run.anomalies}


def test_different_repetitions_are_not_applied_and_go_to_the_fallback(operator_user, script,
                                                                      settings):
    """REQ-031: si las repeticiones dan cambios distintos, el cambio no se aplica en firme: va
    al flujo de candidatas con la anomalía "no estable"."""
    settings.CIRCULAR_EXTRACTION_REPEATS = 2
    procedure = guarantee_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 4", date(2025, 12, 1), GUARANTEE_LINE)
    script.x_when(
        "pasa a ser",
        [change("reemplaza", "clausula", "3.1", "", NEW_GUARANTEE)],
        [change("aclara", "clausula", "3.1", "", NEW_GUARANTEE)])

    version, run = run_proposal(operator_user, procedure)

    assert not sources_of(version)
    assert "circular_cambio_no_estable" in {a["type"] for a in run.anomalies}
    assert fallback_asked(script, "pasa a ser")      # el respaldo
    assert step_motive() == "no_estable"


# --- Respaldo cuando el modelo falla ---------------------------------------------------------------------------


@pytest.mark.parametrize("output", ["timeout", "esto no es json", '{"otra": []}',
                                    '{"cambios": [{"tipo": "inventa"}]}', []])
def test_when_the_model_fails_or_returns_nothing_valid_the_unit_goes_to_the_fallback(
        operator_user, case, script, output):
    """REQ-031: falla del servicio, salida que no es JSON, sin la forma, con un tipo inventado o
    sin cambios: toda la unidad pasa al flujo de candidatas y el resultado es el de la
    entrega 1. El pedido fallido queda registrado."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria pasa de 16 GB de RAM a 32 GB de RAM.")
    script.x_when("pasa de", output)
    script.c_when("pasa de", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, run = run_proposal(operator_user, case)

    assert extraction_steps("pasa") or output == []
    assert fallback_asked(script, "pasa de")
    source = row_of_item(version, 1).sources.get()
    assert source.step.pass_name == "circulares" and source.text == "32 GB de RAM"
    if output != []:
        assert extraction_steps("pasa")[0].anomalies
    assert all(m.Disposition.objects.filter(run=run, segment=s).exists()
               for s in m.Segment.objects.filter(reading__document__title="Circular N.º 1"))


def test_with_the_extraction_off_the_result_is_the_one_of_the_first_delivery(
        operator_user, case, script, settings):
    """REQ-031: con `CIRCULAR_EXTRACTION_ENABLED` en falso no hay pedidos de extracción y la
    unidad que la entrega 1 no resuelve va al flujo de candidatas, como antes."""
    settings.CIRCULAR_EXTRACTION_ENABLED = False
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria pasa de 16 GB de RAM a 32 GB de RAM.")
    script.x_when("pasa de", [change("reemplaza", "ninguno", "", "16 GB de RAM",
                                     "32 GB de RAM")])
    script.c_when("pasa de", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    assert not script.extractions and not extraction_steps("pasa")
    assert row_of_item(version, 1).sources.get().step.pass_name == "circulares"


# --- Un cambio resuelto y otro no, en la misma unidad ---------------------------------------------------


def test_only_the_tramos_of_an_unresolved_change_go_to_the_fallback(operator_user, case,
                                                                     script):
    """REQ-031: una unidad con dos cambios, uno resuelto por el texto anterior y otro sin
    objetivo, aplica el primero por clave y manda al respaldo solo el tramo del segundo."""
    document = add_circular(
        operator_user, case, "Circular N.º 5", date(2025, 12, 2),
        "1. Cambios de la planilla comparativa:",
        "• La memoria pasa de 16 GB de RAM a 32 GB de RAM.",
        "• La pantalla pasa a ser de otra medida.")
    script.x_when("Cambios de la planilla", [
        change("reemplaza", "ninguno", "", "16 GB de RAM", "32 GB de RAM"),
        change("reemplaza", "ninguno", "", "", "otra medida")])
    script.c_when("otra medida", sin_efecto="dato_procedimiento")

    version, _ = run_proposal(operator_user, case)

    assert row_of_item(version, 1).sources.get().text == "32 GB de RAM"
    asked = [r["tramo"] for r in script.requests]
    assert any("otra medida" in t for t in asked)
    assert not any("16 GB" in t for t in asked)
    assert all(m.Disposition.objects.filter(segment=s).exists()
               for s in m.Segment.objects.filter(reading__document=document))


# --- Aviso de T-113: un par aplicado con un tramo no ubicado ---------------------------------------------


def test_an_applied_pair_with_an_unlocated_tramo_stays_pending_for_its_reading(
        operator_user, case, script):
    """REQ-028 (aviso de T-113): un par "Donde dice / Debe decir" aplicado por clave con un
    tramo `no_ubicado` deja a ese tramo con disposición `requisitos`, pero sigue en "Pendiente
    de revisión" por el motivo de la lectura."""
    pdf = tender_pdf([[para("CIRCULAR SINTÉTICA"),
                       para("SECCIÓN I - CONDICIONES PARTICULARES"),
                       para("DONDE DICE:"),
                       para("a los 90 días corridos de la factura"),
                       para("DEBE DECIR:"),
                       para("a los 60 días corridos de la factura")]], header=None)
    document = load_and_read(operator_user, case, pdf, kind="circular_modificatoria",
                             title="Circular N.º 2", issued_on=date(2025, 12, 1))
    unlocated = list(m.Segment.objects.filter(reading__document=document,
                                              segment_type="no_ubicado"))
    assert unlocated, "la circular de prueba debe dejar tramos no ubicados"

    version, run = run_proposal(operator_user, case)

    source = requirement_with(version, PAGO).sources.get()
    assert source.effect == "modifica" and "60 días" in source.text
    assert not fallback_asked(script, "60 días", "90 días")
    assert not script.asked("60 días")
    for segment in unlocated:
        assert m.Disposition.objects.get(run=run, segment=segment).outcome == "requisitos"
        assert version.pending_items.filter(segment=segment, reason="no_ubicado").exists()


def test_the_unit_steps_without_a_model_carry_no_messages(operator_user, case, script):
    """REQ-031 (aviso de T-113): el paso de una unidad resuelta sin modelo no lleva `messages`;
    el de la extracción sí."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. La memoria pasa de 16 GB de RAM a 32 GB de RAM.")
    script.x_when("pasa de", [change("reemplaza", "ninguno", "", "16 GB de RAM",
                                     "32 GB de RAM")])

    run_proposal(operator_user, case)

    assert all("messages" not in s.request for s in unit_steps())
    assert all("messages" in s.request for s in extraction_steps("pasa"))


# --- Forma de la salida, sin base --------------------------------------------------------------------------------


def test_the_shape_of_the_output_is_checked():
    """REQ-031: `shape` acepta la lista con los cinco campos y rechaza lo demás."""
    good = changes.shape({"cambios": [change("suprime", "anexo", "III", "", "no es requisito")]})
    assert good[0].type == "suprime" and good[0].reference == "III"
    for bad in ({}, {"cambios": "x"}, {"cambios": [{"tipo": "suprime"}]},
                {"cambios": [change("inventa")]}, {"cambios": [change("aclara", "otro")]},
                {"cambios": [], "extra": 1}, [], {"cambios": [{**change("aclara"), "x": ""}]}):
        with pytest.raises(changes.InvalidOutput):
            changes.shape(bad)


# --- Generalidad: ninguna ancla de los casos 00, 01 y 02 -----------------------------------------------------


def test_the_v5_instructions_and_the_module_repeat_no_case_anchor():
    """REQ-031 (generalidad): ni las instrucciones v5 ni sus ejemplos ni el módulo repiten
    cinco palabras seguidas de las anclas de los casos 00, 01 y 02 (huellas en
    `fixtures/case_anchor_hashes.txt`, como en `test_circular_units`)."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    files = [extraction.PROMPTS_DIR / "matriz-circulares-v5.md", Path(changes.__file__)]
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        hits += [f"{path.name}: {hashlib.sha256(s.encode()).hexdigest()[:12]}"
                 for s in _shingles(text) if hashlib.sha256(s.encode()).hexdigest() in known]
    assert not hits, hits


def test_the_active_extraction_instructions_are_v5_with_synthetic_examples(settings):
    """REQ-031: la versión activa de `circulares_cambios` es la v5, con ejemplos de la forma
    de la salida y de cada tipo."""
    assert settings.MATRIX_PROMPT_VERSIONS["circulares_cambios"] == "matriz-circulares-v5"
    prompt = extraction.load_prompt("circulares_cambios")
    for word in ("reemplaza", "suprime", "agrega", "aclara", "dato_del_tramite",
                 "Donde dice", "Debe decir", "No ves el pliego"):
        assert word in prompt
    assert prompt.count('{"cambios"') >= 8


def test_a_source_reached_by_the_key_and_by_the_fallback_is_saved_once(operator_user, case,
                                                                        script):
    """REQ-031 (D1): una circular de un solo tramo con dos cambios, uno resuelto por el texto
    anterior y otro sin objetivo, manda el tramo también al respaldo; si este elige la misma
    cita con el mismo fragmento, la fuente (requisito, efecto, tramo y posiciones) queda una
    sola vez."""
    add_circular(operator_user, case, "Circular N.º 6", date(2025, 12, 2),
                 "1. La memoria pasa de 16 GB de RAM a 32 GB de RAM y la pantalla pasa a ser "
                 "de otra medida.")
    script.x_when("pasa de", [
        change("reemplaza", "ninguno", "", "16 GB de RAM", "32 GB de RAM"),
        change("reemplaza", "ninguno", "", "", "otra medida")])
    script.c_when("pasa de", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    assert fallback_asked(script, "pasa de")          # el respaldo corrió
    sources = list(row_of_item(version, 1).sources.all())
    assert len(sources) == 1 and sources[0].text == "32 GB de RAM"
