"""Filtro de precisión y reparto de cada fila en firme, sugerencia o descartada (REQ-024,
REQ-033, REQ-035; plan 003, "Filtro de precisión" y "Tres destinos en vez de dos"; ADR-0021
y ADR-0022; T-102).

El modelo es el doble de `tests/conftest.py`; `FilterScript` le agrega las respuestas de las
dos preguntas del filtro (A: mantener o descartar con motivo e indicio; B: si la oferta
puede condicionarlo) y deja pasar los demás pedidos al guion de `tests/tenders/scripted.py`.
Los pliegos y los textos son inventados (P4). Principio de la spec: un requisito que falta no
lo evalúa nadie; ante la duda, la fila se queda.
"""

import hashlib
import json
import re
import textwrap
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluon.ai import generation as generation_client
from evaluon.tenders import models as m
from evaluon.tenders.proposal import filter as row_filter
from evaluon.tenders.proposal.extraction import Found
from evaluon.tenders.proposal.quotes import WIDE
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import item, load_and_read, make_procedure, propose
from tests.tenders.test_circulars import (
    PAGO,
    VISITA,
    VISITA_QUOTE,
    CircularScript,
    add_circular,
    tender,
)

pytestmark = pytest.mark.django_db

SENT_1 = "El adjudicatario armará los gazebos en el predio ferial."
FRAG_1 = "armará los gazebos en el predio ferial"
SENT_2 = "Los oferentes deberán cotizar el alquiler por jornada."
FRAG_2 = "cotizar el alquiler por jornada"
CLAUSE = f"{SENT_1} {SENT_2}"

KEEP = "mantener"


def discard(motive="ejecucion_contrato", clue=SENT_1):
    """La respuesta de A que descarta con motivo e indicio."""
    return ("descartar", motive, clue)


# --- El doble del modelo con las dos preguntas ------------------------------------------------

_BLOCK = re.compile(r"\[(F\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)


class FilterScript:
    """Responde los pedidos del filtro. `when(texto, a, b)`: a toda fila cuyo fragmento
    contiene `texto` le responde `a` en la pregunta A y `b` en la B. `a` es `KEEP`,
    `discard(...)`, o `"invalida"`; `b` es `si`, `no`, `duda` o `"invalida"`. Sin regla, la fila
    se mantiene con `si`. `requests` guarda `(pregunta, {alias: fragmento}, mensajes,
    esquema)` de cada pedido; `raw(pregunta, salidas)` responde esas salidas sin tocar;
    `failing` hace fallar el servicio en los pedidos del filtro."""

    def __init__(self, script, monkeypatch):
        self.script = script
        self.rules = []
        self.requests = []
        self.queued = {"a": [], "b": []}
        self.failing = False
        monkeypatch.setattr(generation_client, "generate", self._generate)

    def when(self, needle, a=KEEP, b="si"):
        self.rules.insert(0, (needle, a, b))

    def raw(self, kind, outputs):
        self.queued[kind] = list(outputs)

    def fragments(self, kind="a"):
        return [fragment for k, blocks, _, _ in self.requests if k == kind
                for fragment in blocks.values()]

    def _answer(self, kind, fragment):
        a, b = KEEP, "si"
        for needle, rule_a, rule_b in self.rules:
            if needle in fragment:
                a, b = rule_a, rule_b
                break
        if kind == "b":
            return {"respuesta": "quizá" if b == "invalida" else b}
        if a == "invalida":
            return {"decision": "quizá", "motivo": "", "indicio": ""}
        if a == KEEP:
            return {"decision": KEEP, "motivo": "", "indicio": ""}
        decision, motive, clue = a
        return {"decision": decision, "motivo": motive, "indicio": clue}

    def _generate(self, messages, schema, **options):
        first = next(iter(schema.get("properties", {}).values()), {}).get("properties", {})
        kind = "a" if "decision" in first else "b" if "respuesta" in first else None
        if kind is None:
            return self.script._generate(messages, schema, **options)
        blocks = {alias: body.split("Fragmento:\n", 1)[1].split("\nTexto del tramo", 1)[0]
                  for alias, body in _BLOCK.findall(messages[-1]["content"])}
        self.requests.append((kind, blocks, messages, schema))
        fake = self.script.fake
        if self.failing:
            fake.timeout()
        elif self.queued[kind]:
            output = self.queued[kind].pop(0)
            if isinstance(output, tuple):
                fake.invalid_output(output[1])
            else:
                fake.respond(output)
        else:
            fake.respond(json.dumps(
                {alias: self._answer(kind, fragment) for alias, fragment in blocks.items()},
                ensure_ascii=False))
        return fake.generate(messages, schema, **options)


@pytest.fixture
def script(fake_generation, monkeypatch):
    return CircularScript(fake_generation, monkeypatch)


@pytest.fixture
def filt(script, monkeypatch):
    return FilterScript(script, monkeypatch)


# --- Ayudas -----------------------------------------------------------------------------------


def pliego(*clauses, title="SECCIÓN I - CONDICIONES PARTICULARES"):
    """Un pliego con una sección de condiciones, una cláusula por texto, y una sección
    técnica con dos renglones."""
    return tender_pdf([
        [para(title),
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


def one_row(script):
    script.when(SENT_1, item([(FRAG_1, "formal")]))


def formal_rows(run):
    return list(m.Requirement.objects.filter(version=run.version)
                .exclude(category="tecnico").order_by("number"))


def destination(run):
    """El destino de la única fila formal de una propuesta."""
    discarded = list(m.DiscardedRow.objects.filter(run=run))
    rows = formal_rows(run)
    assert len(discarded) + len(rows) == 1, (discarded, rows)
    if discarded:
        return ("descartada", discarded[0].reason)
    row = rows[0]
    if row.state == "sugerido":
        return ("sugerencia", row.doubt_reason)
    assert row.state == "propuesto" and row.doubt_reason == ""
    return ("firme",)


# --- La tabla de destinos del plan, una fila por renglón ----------------------------------------

TABLE = [
    ("descartar valido y no", discard(), "no", ("descartada", "ejecucion_contrato")),
    ("mantener y si", KEEP, "si", ("firme",)),
    ("mantener y duda", KEEP, "duda", ("sugerencia", "duda")),
    ("mantener y no", KEEP, "no", ("sugerencia", "no_coinciden")),
    ("descartar valido y si", discard(), "si", ("sugerencia", "no_coinciden")),
    ("descartar valido y duda", discard(), "duda", ("sugerencia", "duda")),
    ("indicio que no esta, no", discard(clue="Texto que el tramo no tiene."), "no",
     ("sugerencia", "descarte_sin_sustento")),
    ("indicio que no esta, si", discard(clue="Texto que el tramo no tiene."), "si",
     ("sugerencia", "descarte_sin_sustento")),
    ("indicio vacio", discard(clue=""), "no", ("sugerencia", "descarte_sin_sustento")),
    ("motivo fuera de la lista, no", discard(motive="motivo_inventado"), "no",
     ("sugerencia", "descarte_sin_sustento")),
    ("motivo fuera de la lista, duda", discard(motive="motivo_inventado"), "duda",
     ("sugerencia", "descarte_sin_sustento")),
    ("unica opinion: descartar", discard(), "invalida", ("sugerencia", "opinion_incompleta")),
    ("unica opinion: no", "invalida", "no", ("sugerencia", "opinion_incompleta")),
    ("unica opinion: duda", "invalida", "duda", ("sugerencia", "opinion_incompleta")),
    ("unica opinion que mantiene", KEEP, "invalida", ("firme",)),
    ("unica opinion que dice si", "invalida", "si", ("firme",)),
    ("dos opiniones invalidas", "invalida", "invalida", ("firme",)),
]


@pytest.mark.parametrize("label,a,b,expected", TABLE, ids=[t[0] for t in TABLE])
def test_each_row_of_the_destination_table(operator_user, script, filt, label, a, b, expected):
    """REQ-033, REQ-035: el destino de cada fila sale de la tabla del plan: se descarta solo
    con las cuatro condiciones; es firme con (mantener, si), con una única opinión que
    mantiene o dice si, o sin ninguna válida; todo lo demás es sugerencia."""
    one_row(script)
    filt.when(FRAG_1, a, b)

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == expected


def test_a_discarded_row_keeps_its_quote_reason_clue_and_both_votes(operator_user, script,
                                                                    filt):
    """REQ-033: la descartada queda en la tabla con su cita literal, el motivo, el indicio
    literal, las dos respuestas y los pedidos que las produjeron."""
    one_row(script)
    filt.when(FRAG_1, discard("ejecucion_contrato", SENT_1), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    row = m.DiscardedRow.objects.get(run=run)
    canonical = row.segment.reading.canonical_text
    assert row.text == FRAG_1 and canonical[row.char_start:row.char_end] == FRAG_1
    assert row.version == run.version and row.category == "formal" and row.order == 1
    assert row.reason == "ejecucion_contrato"
    assert row.evidence_segment == row.segment and row.evidence_text == SENT_1
    assert canonical[row.evidence_start:row.evidence_end] == SENT_1
    assert row.vote_a == {"decision": "descartar", "motivo": "ejecucion_contrato",
                          "indicio": SENT_1}
    assert row.vote_b == {"respuesta": "no"}
    assert (row.step_a.pass_name, row.step_b.pass_name) == ("filtro", "filtro_2")
    assert row.source_pass == "extraccion" and row.passes == ["extraccion"]
    assert row.extra_quotes == []
    assert not formal_rows(run)
    assert run.counts["filter"]["discarded"] == 1
    assert run.counts["filter"]["discarded_by_reason"] == {"ejecucion_contrato": 1}
    assert run.counts["filter"]["discarded_by_pass"] == {"extraccion": 1}


def test_a_discarded_row_stores_the_repeated_quotes_as_segment_and_positions(
        operator_user, script, filt):
    """REQ-033: las citas de las repetidas unificadas se guardan como lista de
    `{segment (id del tramo), char_start, char_end, text}`, cada una igual al recorte."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")

    run = run_with(operator_user, pliego(CLAUSE, CLAUSE))

    row = m.DiscardedRow.objects.get(run=run)
    assert len(row.extra_quotes) == 1
    extra = row.extra_quotes[0]
    assert set(extra) == {"segment", "char_start", "char_end", "text"}
    other = m.Segment.objects.get(pk=extra["segment"])
    assert other.key == "sec-i/2.1" and other.pk != row.segment_id
    assert other.reading.canonical_text[extra["char_start"]:extra["char_end"]] == FRAG_1
    assert extra["text"] == FRAG_1


def test_a_suggestion_is_a_requirement_with_quote_class_items_and_doubt(
        operator_user, script, filt):
    """REQ-035: la sugerencia es un requisito `sugerido` con la cita, las citas `repetida`,
    la clase y los renglones de la fila, el motivo de la duda y las dos respuestas con el
    indicio literal y los pedidos."""
    one_row(script)
    filt.when(FRAG_1, discard("formulario", SENT_1), "duda")

    run = run_with(operator_user, pliego(CLAUSE, CLAUSE))

    row = formal_rows(run)[0]
    assert (row.state, row.doubt_reason, row.origin) == ("sugerido", "duda", "propuesto")
    assert row.category == "formal" and row.items == []
    assert [(q.scope, q.text) for q in row.quotes.order_by("order")] == [
        ("", FRAG_1), ("repetida", FRAG_1)]
    assert [q["scope"] for q in row.proposed["quotes"]] == ["", "repetida"]
    doubt = row.doubt
    assert doubt["vote_a"] == {"decision": "descartar", "motivo": "formulario",
                               "indicio": SENT_1}
    assert doubt["vote_b"] == {"respuesta": "duda"}
    assert doubt["evidence"]["text"] == SENT_1
    steps = m.RunStep.objects.filter(run=run)
    assert steps.get(pk=doubt["step_a"]).pass_name == "filtro"
    assert steps.get(pk=doubt["step_b"]).pass_name == "filtro_2"
    assert not m.DiscardedRow.objects.filter(run=run).exists()
    assert run.counts["filter"]["suggestions"] == 1
    assert run.counts["filter"]["suggestions_by_reason"] == {"duda": 1}


def test_a_suggestion_without_a_clue_has_no_evidence(operator_user, script, filt):
    """REQ-035: un descarte cuyo indicio no está en el tramo no guarda indicio; la sugerencia
    lo dice con `descarte_sin_sustento` y conserva lo que dijo el modelo."""
    one_row(script)
    filt.when(FRAG_1, discard(clue="Texto que el tramo no tiene."), "no")

    row = formal_rows(run_with(operator_user, pliego(CLAUSE)))[0]

    assert row.doubt["evidence"] is None
    assert row.doubt["vote_a"]["indicio"] == "Texto que el tramo no tiene."


def test_the_whole_tramo_is_discarded_only_if_every_row_was(operator_user, script, filt):
    """REQ-033: un tramo cuyas filas se descartaron todas queda `descartado` con origen
    `filtro`; uno con alguna fila firme o una sugerencia queda `requisitos`."""
    two = "El oferente deberá firmar cada hoja de la planilla. La caución se devuelve al finalizar el alquiler."
    three = "Se cotizará en pesos por jornada y por unidad."
    script.when(SENT_1, item([(FRAG_1, "formal")]))
    script.when(two, item([("firmar cada hoja de la planilla", "formal"),
                           ("La caución se devuelve al finalizar el alquiler", "formal")]))
    script.when(three, item([(three, "economico")]))
    filt.when(FRAG_1, discard("ejecucion_contrato", SENT_1), "no")
    filt.when("La caución", discard("ejecucion_contrato", "La caución se devuelve al finalizar el alquiler."),
              "no")
    filt.when("Se cotizará", KEEP, "duda")

    run = run_with(operator_user, pliego(SENT_1, two, three))

    def disposition(key):
        return m.Disposition.objects.get(run=run, segment__key=key)

    gone = disposition("sec-i/1.1")
    assert (gone.outcome, gone.source, gone.discard_reason) == (
        "descartado", "filtro", "ejecucion_contrato")
    assert gone.step.pass_name == "filtro"
    assert disposition("sec-i/2.1").outcome == "requisitos"
    assert disposition("sec-i/3.1").outcome == "requisitos"
    assert m.DiscardedRow.objects.filter(run=run).count() == 2
    assert [r.state for r in formal_rows(run)] == ["propuesto", "sugerido"]


def test_the_disposition_reason_for_motives_the_tramo_list_lacks(operator_user, script, filt):
    """REQ-033: `consecuencia_sancion` está en la lista del filtro; la disposición del tramo
    (lista del ADR-0019) lo registra con el motivo más cercano y la fila descartada conserva
    el exacto."""
    one_row(script)
    clue = SENT_1
    filt.when(FRAG_1, discard("consecuencia_sancion", clue), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    assert m.DiscardedRow.objects.get(run=run).reason == "consecuencia_sancion"
    assert m.Disposition.objects.get(run=run, segment__key="sec-i/1.1").outcome == "descartado"


# --- Lo que no se filtra ---------------------------------------------------------------------


def test_rows_out_of_scope_are_not_candidates():
    """REQ-033: ni las de cita amplia, ni las de un tramo `tabla`, ni las de una sección
    titulada como formal o económica pasan por el modelo; la normal, sí."""

    def unit(kind="clausula", section=""):
        segment = SimpleNamespace(pk=1, key="a", text="x" * 30, segment_type=kind,
                                  section_class=section)
        return SimpleNamespace(segment=segment, document_title="d")

    normal = (unit(), Found("formal", (0, 10)))
    wide = (unit(), Found("formal", (0, 30), WIDE))
    table = (unit("tabla"), Found("economico", (0, 10)))
    formal_section = (unit(section="formal"), Found("formal", (0, 10)))
    economic_section = (unit(section="economico"), Found("economico", (0, 10)))

    rows = row_filter.candidates([normal, wide, table, formal_section, economic_section])

    assert [row.found for row in rows] == [normal[1]]
    assert rows[0].order == 1


def test_wide_quote_and_formal_section_rows_stay_firm_and_never_reach_the_model(
        operator_user, script, filt):
    """REQ-033, REQ-035: una fila de cita amplia y una de una sección titulada como formal
    nunca van al modelo y quedan firmes, aunque el modelo las descartaría."""
    script.when("Se pide la caución.", item([("texto que el tramo no tiene", "formal")]))
    filt.when("", discard(), "no")  # descartaría todo lo que le llegue

    run = run_with(operator_user, pliego("Se pide la caución."))
    wide = formal_rows(run)
    assert [(r.state, r.quotes.get().quote_flag) for r in wide] == [
        ("propuesto", "cita_amplia")]
    assert not filt.fragments("a")

    script.when("Se exige la fianza.", item([("Se exige la fianza.", "formal")]))
    run = run_with(operator_user, pliego("Se exige la fianza.",
                                         title="SECCIÓN I - REQUISITOS FORMALES"))
    assert [r.state for r in formal_rows(run)] == ["propuesto"]
    assert not filt.fragments("a")
    assert not m.DiscardedRow.objects.exists()


def test_technical_rows_never_go_to_the_model(operator_user, script, filt):
    """REQ-033: las filas técnicas (una por renglón) no se mandan al modelo y quedan como
    estaban."""
    one_row(script)
    filt.when("", discard(), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    assert m.Requirement.objects.filter(version=run.version, category="tecnico",
                                        state="propuesto").count() == 2
    assert all("Bolsa" not in fragment for fragment in filt.fragments("a") + filt.fragments("b"))


def test_a_circular_row_is_never_filtered_and_a_suggestion_is_reached_by_circulars(
        operator_user, script, filt):
    """REQ-031, REQ-033, REQ-035: la fila que agrega una circular no pasa por el filtro; la
    pasada de circulares alcanza una sugerencia como a cualquier fila no quitada."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender())
    script.when(VISITA, item([(VISITA_QUOTE, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    add_circular(operator_user, procedure, "Circular N.º 2", date(2025, 12, 5),
                 "1. Déjase sin efecto la exigencia de la constancia de visita.")
    add_circular(operator_user, procedure, "Circular N.º 3", date(2025, 12, 7),
                 "1. Los oferentes deberán presentar una declaración jurada de aptitud "
                 "fiscal.")
    script.c_when("sin efecto", efectos=[("constancia de visita", "suprime",
                                          "Déjase sin efecto la exigencia")])
    script.c_when("declaración jurada", nuevos=[
        ("presentar una declaración jurada de aptitud fiscal", "formal")])
    filt.when(VISITA_QUOTE, KEEP, "duda")
    filt.when("declaración jurada", discard(), "no")

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    version = requested.run.version
    assert all("declaración jurada" not in fragment for fragment in filt.fragments("a"))
    new = version.requirements.get(origin="circular")
    assert new.state == "propuesto" and new.doubt_reason == ""
    visit = version.requirements.get(quotes__text=VISITA_QUOTE)
    assert visit.state == "quitado" and visit.doubt_reason == "duda"
    assert visit.sources.get().effect == "suprime"


# --- Fallas ------------------------------------------------------------------------------------


def test_a_service_failure_leaves_every_row_firm_and_keeps_the_steps(operator_user, script,
                                                                      filt):
    """REQ-033, REQ-035: una falla técnica del modelo deja la fila firme (nunca fabrica una
    duda) y los pedidos fallidos quedan registrados."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")
    filt.failing = True

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == ("firme",)
    steps = m.RunStep.objects.filter(run=run, pass_name__in=["filtro", "filtro_2"])
    assert sorted(s.pass_name for s in steps) == ["filtro", "filtro_2"]
    assert all(s.anomalies[0]["type"] == "servicio" for s in steps)
    assert run.counts["filter"]["firm_by_failure"] == 1
    assert run.counts["filter"]["failed_requests"] == 2
    assert not m.DiscardedRow.objects.exists()


def test_only_one_question_failing_makes_a_discard_a_suggestion(operator_user, script, filt):
    """REQ-035: si una pregunta da una salida inválida y la otra dice descartar, la fila es
    una sugerencia por opinión incompleta, no una descartada ni una firme."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")
    filt.raw("b", ["no es JSON"])

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == ("sugerencia", "opinion_incompleta")
    row = formal_rows(run)[0]
    assert row.doubt["vote_b"] is None and row.doubt["vote_a"]["decision"] == "descartar"


def test_text_that_is_not_json_or_a_missing_alias_keeps_the_row(operator_user, script, filt):
    """REQ-033: una salida que no es JSON, o sin la propiedad de una fila, no da opinión; la
    fila queda firme."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")
    filt.raw("a", ["esto no es JSON"])
    filt.raw("b", [json.dumps({})])

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == ("firme",)
    assert run.counts["filter"]["firm_by_failure"] == 1


def test_a_cut_batch_is_split_in_two(operator_user, script, filt, settings):
    """REQ-033: un lote cuya salida se corta por el máximo se parte en dos y cada mitad se
    repite; ninguna fila se pierde."""
    script.when(SENT_1, item([(FRAG_1, "formal")]))
    script.when(SENT_2, item([(FRAG_2, "formal")]))
    filt.when(FRAG_1, discard(), "no")
    filt.raw("a", [("corte", '{"F1": {"decision": "desc')])

    run = run_with(operator_user, pliego(SENT_1, SENT_2))

    sizes = [len(blocks) for kind, blocks, _, _ in filt.requests if kind == "a"]
    assert sizes == [2, 1, 1]
    assert run.counts["filter"]["split_batches"] == 1
    assert (m.DiscardedRow.objects.filter(run=run).count(),
            [r.state for r in formal_rows(run)]) == (1, ["propuesto"])
    first = m.RunStep.objects.filter(run=run, pass_name="filtro").order_by("id")[0]
    assert first.anomalies[0]["type"] == "filtro_salida_cortada"


def test_rows_go_to_the_model_in_batches_of_the_configured_size(operator_user, script, filt,
                                                                settings):
    """REQ-033: las filas van en lotes de `FILTER_BATCH_ROWS`, cada pregunta en su pedido, y
    cada pedido queda en `tenders_run_step` con la pasada (`filtro`, `filtro_2`)."""
    settings.FILTER_BATCH_ROWS = 2
    texts = [f"El oferente cotizará el artículo número {n} del listado." for n in range(1, 6)]
    for text in texts:
        script.when(text, item([(text, "economico")]))

    run = run_with(operator_user, pliego(*texts))

    assert [len(b) for k, b, _, _ in filt.requests if k == "a"] == [2, 2, 1]
    assert [len(b) for k, b, _, _ in filt.requests if k == "b"] == [2, 2, 1]
    assert m.RunStep.objects.filter(run=run, pass_name="filtro").count() == 3
    assert m.RunStep.objects.filter(run=run, pass_name="filtro_2").count() == 3
    assert run.counts["model_requests_by_pass"]["filtro"] == 3
    assert len(formal_rows(run)) == 5


def test_the_two_questions_are_independent_and_asked_with_structured_output(
        operator_user, script, filt):
    """REQ-033: la pregunta B no ve lo que respondió A; ambas piden salida estructurada con
    una propiedad obligatoria por alias, y el motivo de A es de la lista cerrada."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    (_, _, messages_a, schema_a), (_, _, messages_b, schema_b) = [
        r for r in filt.requests if r[0] in ("a", "b")][:2]
    assert schema_a["required"] == ["F1"] and schema_b["required"] == ["F1"]
    motives = schema_a["properties"]["F1"]["properties"]["motivo"]["enum"]
    assert "consecuencia_sancion" in motives and "consecuencia_o_sancion" not in motives
    assert "ejecucion_contrato" in motives
    assert "descartar" not in messages_b[-1]["content"].lower()
    assert "ejecucion_contrato" not in messages_b[0]["content"]
    assert "<<<" in messages_a[-1]["content"] and ">>>" in messages_a[-1]["content"]
    assert m.RunStep.objects.filter(run=run, pass_name="filtro").get().request[
        "messages"][0]["content"] == messages_a[0]["content"]


# --- Las consecuencias, la configuración y el registro --------------------------------------------


def test_consequences_are_asked_for_firm_rows_and_suggestions_not_for_discarded(
        operator_user, script, filt):
    """REQ-029, REQ-033, REQ-035: las consecuencias se piden para las filas firmes y para las
    sugerencias, y no para las descartadas."""
    keep = "El oferente deberá acompañar la planilla de cotización firmada."
    doubt = "Los precios incluirán el traslado de los gazebos."
    script.when(SENT_1, item([(FRAG_1, "formal")]))
    script.when(keep, item([(keep, "formal")]))
    script.when(doubt, item([(doubt, "economico")]))
    filt.when(FRAG_1, discard(), "no")
    filt.when(doubt, KEEP, "duda")

    run = run_with(operator_user, pliego(SENT_1, keep, doubt))

    asked = "\n".join(call[-1]["content"] for call in script.consequence_calls)
    assert keep in asked and doubt in asked and FRAG_1 not in asked
    states = {r.quotes.get().text: r.state for r in formal_rows(run)}
    assert states == {keep: "propuesto", doubt: "sugerido"}
    for row in formal_rows(run):
        assert row.consequences.exists()


def test_with_the_filter_off_the_matrix_is_the_one_from_before(operator_user, script, filt,
                                                               settings):
    """REQ-033: con `FILTER_ENABLED` en falso se saltea la pasada: sin pedidos del filtro,
    sin descartadas ni sugerencias, y sin la pasada en los parámetros."""
    settings.FILTER_ENABLED = False
    one_row(script)
    filt.when(FRAG_1, discard(), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    assert not filt.requests
    assert destination(run) == ("firme",)
    assert "filtro" not in run.parameters["passes"]
    assert "filtro" not in run.prompt_versions
    assert "filter" not in run.counts
    assert not m.RunStep.objects.filter(run=run, pass_name__in=["filtro", "filtro_2"]).exists()


def test_with_suggestions_off_what_would_be_a_suggestion_stays_firm(operator_user, script,
                                                                    filt, settings):
    """REQ-035: con `SUGGESTIONS_ENABLED` en falso no hay sugerencias: la fila que lo sería
    queda firme; el descarte con las cuatro condiciones sigue funcionando."""
    settings.SUGGESTIONS_ENABLED = False
    texts = ["El oferente cotizará el gazebo grande.", "El oferente cotizará el gazebo chico."]
    for text in texts:
        script.when(text, item([(text, "economico")]))
    script.when(SENT_1, item([(FRAG_1, "formal")]))
    filt.when("gazebo grande", KEEP, "duda")
    filt.when("gazebo chico", KEEP, "no")
    filt.when(FRAG_1, discard(), "no")

    run = run_with(operator_user, pliego(*texts, SENT_1))

    assert [r.state for r in formal_rows(run)] == ["propuesto", "propuesto"]
    assert m.DiscardedRow.objects.filter(run=run).count() == 1
    assert run.counts["filter"]["suggestions"] == 0
    assert run.parameters["suggestions_enabled"] is False


def test_the_proposal_records_the_filter_in_parameters_and_counts(operator_user, script,
                                                                  filt):
    """REQ-033, P6: la propuesta registra los parámetros del filtro, la versión de sus
    instrucciones y las cuentas por destino, por motivo y por pasada."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    assert run.parameters["filter_enabled"] is True
    assert run.parameters["filter_batch_rows"] == 15
    assert "consecuencia_sancion" in run.parameters["filter_motives"]
    assert run.prompt_versions["filtro"] == "matriz-filtro-v1"
    assert run.parameters["passes"].index("filtro") == run.parameters["passes"].index(
        "unificacion") + 1
    stats = run.counts["filter"]
    assert (stats["rows"], stats["firm"], stats["suggestions"], stats["discarded"]) == (
        1, 0, 0, 1)
    assert "filtro" in run.timings


# --- Generalidad: ninguna ancla de los casos ---------------------------------------------------------

HASHES = Path(__file__).parent / "fixtures" / "case_anchor_hashes.txt"
SHINGLE = 5


def _shingles(text):
    import unicodedata

    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    for i in range(len(words) - SHINGLE + 1):
        yield " ".join(words[i:i + SHINGLE])


def test_no_instruction_test_or_example_of_the_filter_repeats_five_words_of_a_case_anchor():
    """REQ-033 (generalidad): ni las instrucciones del filtro, ni su módulo, ni estos tests
    repiten cinco palabras seguidas de las anclas de los casos. Las anclas no están en el
    repositorio (P4): `fixtures/case_anchor_hashes.txt` guarda solo la huella SHA-256 de cada
    secuencia de cinco palabras."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    files = [Path(__file__), Path(row_filter.__file__),
             Path(row_filter.__file__).parent.parent / "prompts" / "matriz-filtro-v1.md"]
    hits = []
    for path in files:
        for shingle in _shingles(path.read_text(encoding="utf-8")):
            digest = hashlib.sha256(shingle.encode()).hexdigest()
            if digest in known:
                hits.append(f"{path.name}: {digest[:12]}")
    assert not hits, hits


def test_the_instructions_use_the_motives_of_the_settings(settings):
    """REQ-033: las instrucciones nombran cada motivo de `FILTER_MOTIVES` y ningún otro
    nombre de motivo."""
    first, second = row_filter.load_prompts()
    for motive in settings.FILTER_MOTIVES:
        assert f'"{motive}"' in first
    assert "consecuencia_o_sancion" not in first + second


# --- Bordes que no pueden perder una fila ---------------------------------------------------------


def test_a_repeated_id_in_the_output_is_invalid_for_that_row(operator_user, script, filt):
    """REQ-033: si el modelo repite el id de una fila ("mantener" y después "descartar"),
    la salida de esa fila no vale y no descarta: con la otra pregunta que descarta, la fila
    queda como sugerencia por opinión incompleta."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")
    keep = {"decision": KEEP, "motivo": "", "indicio": ""}
    drop = {"decision": "descartar", "motivo": "ejecucion_contrato", "indicio": SENT_1}
    filt.raw("a", [f'{{"F1": {json.dumps(keep)}, "F1": {json.dumps(drop)}}}'])

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == ("sugerencia", "opinion_incompleta")
    assert not m.DiscardedRow.objects.filter(run=run).exists()
    step = m.RunStep.objects.get(run=run, pass_name="filtro")
    assert step.anomalies[0]["type"] == "filtro_fila_repetida"


def test_a_repeated_field_inside_a_row_is_invalid(operator_user, script, filt):
    """REQ-033: un campo repetido dentro de la respuesta de una fila también la invalida."""
    one_row(script)
    filt.when(FRAG_1, discard(), "no")
    filt.raw("a", ['{"F1": {"decision": "mantener", "decision": "descartar", '
                   f'"motivo": "ejecucion_contrato", "indicio": "{SENT_1}"}}}}'])

    assert destination(run_with(operator_user, pliego(CLAUSE))) == (
        "sugerencia", "opinion_incompleta")


@pytest.mark.parametrize("clue", ["a", "predio", "los gazebos", "armará los gazebos"])
def test_a_trivial_clue_cannot_support_a_discard(operator_user, script, filt, clue):
    """REQ-033: un indicio de una letra, una palabra suelta o menos de `MIN_CLUE_WORDS`
    palabras con contenido, aunque esté en el tramo, no sostiene el descarte: la fila queda
    como sugerencia sin sustento."""
    assert row_filter.MIN_CLUE_WORDS == 4
    one_row(script)
    filt.when(FRAG_1, discard(clue=clue), "no")

    run = run_with(operator_user, pliego(CLAUSE))

    assert destination(run) == ("sugerencia", "descarte_sin_sustento")
    assert not m.DiscardedRow.objects.filter(run=run).exists()
