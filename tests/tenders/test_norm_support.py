"""Respaldo normativo de cada sugerencia de condición (REQ-036, REQ-022; plan 003, "Consulta
normativa"; ADR-0022; ADR-0010; T-109).

Normas, pliegos y datos sintéticos (P4). El modelo es el doble de `tests/conftest.py`: acá
se le agrega la respuesta del pedido de respaldo (`SupportScript`), y el recuperador es el de
la 001 sobre las normas de prueba, con los dobles de embeddings y reranker. Principio de la
spec: la norma solo confirma; que una condición no figure en ella nunca es motivo para
descartarla ni para tocar su estado.
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.ai import ServiceTimeoutError
from evaluon.ai import generation as generation_client
from evaluon.audit import services as audit_services
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.queries import retrieval
from evaluon.tenders import models as m
from evaluon.tenders.proposal import norm_support
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import load_and_read, make_procedure, propose
from tests.tenders.scripted import item  # noqa: F401  (se usa con `script.when`)
from tests.tenders.test_consequences import marks, regimes  # noqa: F401  (fixtures)
from tests.tenders.test_filter import (  # noqa: F401  (fixtures y ayudas)
    FRAG_1,
    KEEP,
    SENT_1,
    discard,
    filt,
    pliego,
    script,
)
from tests.tenders.test_suggestions import case, make_suggestion  # noqa: F401

pytestmark = pytest.mark.django_db

GARANTIAS = "Garantías sintéticas"
OBJETO_VIEJO = "Objeto del régimen sintético anterior"
OBJETO_NUEVO = "OBJETO. Régimen sintético vigente"
APRUEBA = "Apruébase el régimen sintético de contrataciones"
QUESTION_START = "El pliego de un procedimiento de contratación dice"
AFTER = date(2023, 1, 2)
BEFORE = date(2023, 1, 1)


# --- El doble del pedido de respaldo ---------------------------------------------------------

_BLOCK = re.compile(r"\[(N\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)


class SupportScript:
    """Responde el pedido de respaldo (el del esquema con `exige` y `cita`) y deja pasar los
    demás al guion del filtro. `says(texto, exige, cita)`: a toda unidad cuyo bloque contiene
    `texto` le responde `exige` y `cita` (por omisión, la propia `texto`). Sin regla, `no`.
    `raw(salida)` responde esa salida sin tocar; `failing` hace fallar el servicio en este
    pedido. `requests` guarda `(bloques, mensajes, esquema)` de cada pedido."""

    def __init__(self, filt, fake, monkeypatch):
        self.filt = filt
        self.fake = fake
        self.rules = []
        self.requests = []
        self.output = None
        self.failing = False
        monkeypatch.setattr(generation_client, "generate", self._generate)

    def says(self, needle, exige="si", cita=None):
        self.rules.insert(0, (needle, exige, needle if cita is None else cita))

    def raw(self, output):
        self.output = output

    def _generate(self, messages, schema, **options):
        first = next(iter(schema.get("properties", {}).values()), {}).get("properties", {})
        if "exige" not in first:
            return self.filt._generate(messages, schema, **options)
        blocks = dict(_BLOCK.findall(messages[-1]["content"]))
        self.requests.append((blocks, messages, schema))
        if self.failing:
            self.fake.timeout()
        elif self.output is not None:
            self.fake.respond(self.output)
        else:
            answer = {}
            for alias, body in blocks.items():
                answer[alias] = {"exige": "no", "cita": ""}
                for needle, exige, cita in self.rules:
                    if needle in body:
                        answer[alias] = {"exige": exige, "cita": cita}
                        break
            self.fake.respond(json.dumps(answer, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)

    def shown(self):
        """Los textos de las unidades de todos los pedidos."""
        return " ".join(body for blocks, _, _ in self.requests for body in blocks.values())


@pytest.fixture(autouse=True)
def short_quotes_allowed(monkeypatch):
    """Las normas de prueba de la 001 tienen artículos de dos palabras: salvo en las pruebas
    del largo mínimo, que lo fijan, no se exige largo."""
    monkeypatch.setattr(norm_support, "MIN_CITE_WORDS", 1)


@pytest.fixture
def support(filt, fake_generation, monkeypatch):  # noqa: F811
    return SupportScript(filt, fake_generation, monkeypatch)


@pytest.fixture
def spy(monkeypatch):
    """Mira la recuperación de la 001 que hace el respaldo (por su pregunta fija). `fail`
    la hace fallar; `paths` la limita a esos caminos."""
    real = retrieval.retrieve
    state = SimpleNamespace(calls=[], fail=False, paths=None)

    def wrapper(question, reference_date, **options):
        if question.startswith(QUESTION_START):
            state.calls.append((question, reference_date))
            if state.fail:
                raise ServiceTimeoutError("reranker: falla simulada", service="reranker")
            if state.paths:
                options["paths"] = state.paths
        return real(question, reference_date, **options)

    monkeypatch.setattr(retrieval, "retrieve", wrapper)
    return state


@pytest.fixture
def corpus(read_write_user):
    """Una versión de la normativa registrada (el respaldo la guarda)."""
    return audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND,
        user=read_write_user, creates_corpus_version=True).corpus_version


def run_case(user, script, filt, *, authorization_date=AFTER, text=SENT_1, fragment=FRAG_1,
             a=KEEP, b="duda"):
    """Una propuesta con una fila formal que el filtro deja como sugerencia (por omisión,
    "mantener" y "duda")."""
    script.when(text, item([(fragment, "formal")]))
    filt.when(fragment, a, b)
    procedure = make_procedure(user, authorization_date)
    load_and_read(user, procedure, pliego(text))
    requested, job = propose(user, procedure)
    assert job.status == "done", job.error
    return requested.run


def formal(run):
    return list(m.Requirement.objects.filter(version=run.version).exclude(category="tecnico")
                .order_by("number"))


def supports(run):
    return list(m.NormSupport.objects.filter(requirement__version=run.version).order_by("id"))


def steps(run):
    return list(m.RunStep.objects.filter(run=run, pass_name="respaldo_normativo")
                .order_by("id"))


def assert_untouched(run):
    """La sugerencia sigue siendo la que el filtro dejó: mismo estado y mismo motivo."""
    [row] = formal(run)
    assert row.state == "sugerido" and row.doubt_reason == "duda"
    assert row.origin == "propuesto" and row.quotes.get().text == FRAG_1


# --- Respaldo encontrado ---------------------------------------------------------------------


def test_a_norm_that_requires_the_condition_gives_support_with_the_literal_quote(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: una sugerencia que una norma vigente exige recibe respaldo con la norma, la
    ruta, el puntaje y la cita literal, igual al recorte de la unidad; la sugerencia sigue
    siendo sugerencia."""
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    [saved] = supports(run)
    unit = regimes.new_units["anexo/art-2"]
    assert saved.unit_id == unit.pk and saved.score == 0.9
    assert saved.text == GARANTIAS == unit.text[saved.char_start:saved.char_end]
    assert saved.unit_label == f"Disposición AFIP 247/2022, {unit.path.replace(' › ', ', ')}"
    assert saved.regime == "Disposición AFIP 247/2022"
    assert saved.corpus_version == run.corpus_version == corpus
    assert saved.step.pass_name == "respaldo_normativo" and saved.step.run_id == run.pk
    assert saved.requirement.pk == formal(run)[0].pk
    assert_untouched(run)
    assert run.counts["norm_support"]["with_support"] == 1
    assert run.counts["norm_support"]["supports"] == 1


def test_the_consultation_is_recorded_with_question_units_scores_answer_and_version(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036, P6, P8: cada consulta queda en `tenders_run_step` con la pregunta, las
    unidades recuperadas y mostradas con su puntaje, la respuesta del modelo y la versión de
    la normativa."""
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    [step] = steps(run)
    assert step.request["question"].startswith(QUESTION_START)
    assert FRAG_1 in step.request["question"]
    assert step.request["corpus_version"] == run.corpus_version == corpus
    assert step.request["regime"] == run.regime
    unit = regimes.new_units["anexo/art-2"]
    shown = {entry["unit"]: entry for entry in step.request["shown"]}
    assert shown[unit.pk]["score"] == 0.9 and shown[unit.pk]["alias"].startswith("N")
    assert unit.pk in {entry["unit"] for entry in step.request["retrieved"]}
    assert json.loads(step.raw_output)[shown[unit.pk]["alias"]]["exige"] == "si"
    assert step.parsed["respaldos"] == 1
    assert step.request["request"]["messages"][0]["role"] == "system"
    assert run.prompt_versions["respaldo"] == "matriz-respaldo-v1"
    assert "respaldo_normativo" in run.parameters["passes"]
    assert run.parameters["norm_support_min_score"] == norm_support.settings.NORM_SUPPORT_MIN_SCORE
    assert "respaldo_normativo" in run.timings


def test_at_most_two_supports_are_kept_the_ones_with_the_highest_score(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: hasta dos respaldos por sugerencia, los de mayor puntaje."""
    marks.reranker.scores.update({OBJETO_NUEVO: 0.8, APRUEBA: 0.7})
    support.says(GARANTIAS)
    support.says(OBJETO_NUEVO)
    support.says(APRUEBA)

    run = run_case(operator_user, script, filt)

    saved = supports(run)
    assert [s.score for s in saved] == [0.9, 0.8]
    assert {s.text for s in saved} == {GARANTIAS, OBJETO_NUEVO}
    assert_untouched(run)


@pytest.mark.parametrize("authorization_date, norm, needle, other", [
    (BEFORE, "Disposición AFIP 297/03", OBJETO_VIEJO, GARANTIAS),
    (AFTER, "Disposición AFIP 247/2022", GARANTIAS, OBJETO_VIEJO),
])
def test_the_regime_in_force_at_the_authorization_date_is_the_one_consulted(
        operator_user, script, filt, support, regimes, marks, corpus, spy,  # noqa: F811
        authorization_date, norm, needle, other):
    """REQ-022, REQ-036: antes del 2023-01-02 la consulta ve la 297/03 y desde esa fecha la
    247/2022; el respaldo es de la norma que regía y la consulta se hizo a esa fecha."""
    support.says(needle)

    run = run_case(operator_user, script, filt, authorization_date=authorization_date)

    [saved] = supports(run)
    assert norm in saved.unit_label and saved.regime == norm
    assert saved.text == needle
    assert other not in support.shown()
    assert [d for _, d in spy.calls] == [authorization_date]
    assert run.regime[0]["name"] == norm


def test_a_fragment_that_names_arca_finds_a_unit_of_the_afip_norm(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """ADR-0010, REQ-036: AFIP y ARCA son el mismo organismo: un fragmento que nombra a ARCA
    recupera una unidad de la norma de AFIP (acá, solo por el camino de las palabras, que es
    el que lo resuelve)."""
    spy.paths = (retrieval.WORDS,)
    sentence = "La ARCA exigirá a los oferentes las garantías sintéticas del procedimiento."
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt, text=sentence, fragment=sentence)

    [step] = steps(run)
    assert "ARCA" in step.request["question"]
    [saved] = supports(run)
    assert "AFIP" in saved.unit_label and saved.text == GARANTIAS


# --- Sin respaldo, y la sugerencia queda igual -----------------------------------------------

NO_SUPPORT = {
    "el modelo dice que no": dict(exige="no", cita=""),
    "cita que no esta en la unidad": dict(exige="si", cita="Texto que la unidad no tiene."),
    "cita vacia": dict(exige="si", cita=""),
    "cita de otra unidad": dict(exige="si", cita=OBJETO_VIEJO),
}


@pytest.mark.parametrize("answer", list(NO_SUPPORT.values()), ids=list(NO_SUPPORT))
def test_no_support_when_the_model_says_no_or_the_quote_is_not_in_the_unit(
        operator_user, script, filt, support, regimes, marks, corpus, spy, answer):  # noqa: F811
    """REQ-036, ADR-0004: con `exige` en `no`, o una cita que no está palabra por palabra en
    la unidad, no hay respaldo; la sugerencia queda como estaba."""
    support.says(GARANTIAS, **answer)

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert_untouched(run)
    assert steps(run)  # la consulta quedó registrada igual
    assert run.counts["norm_support"]["with_support"] == 0


@pytest.mark.parametrize("output", [
    '{"N9": {"exige": "si", "cita": "Garantías sintéticas"}}',
    "no es JSON",
    '{"N1": "si"}',
    '{"N1": {"exige": "quizá", "cita": "Garantías sintéticas"}}',
    "[]",
], ids=["alias inexistente", "no es JSON", "forma rota", "exige fuera de lista", "no es objeto"])
def test_an_invalid_output_or_a_missing_alias_gives_no_support(
        operator_user, script, filt, support, regimes, marks, corpus, spy, output):  # noqa: F811
    """REQ-036: un alias inexistente o una salida inválida no producen respaldo; la sugerencia
    sigue y la anomalía queda en la propuesta."""
    support.raw(output)

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert_untouched(run)
    assert any(a["type"].startswith("respaldo_") for a in run.anomalies)


def test_a_score_below_the_threshold_is_not_support_even_if_the_model_says_yes(
        operator_user, script, filt, support, regimes, marks, corpus, spy, settings):  # noqa: F811
    """REQ-036: con puntaje por debajo de `NORM_SUPPORT_MIN_SCORE` no hay respaldo, aunque el
    modelo diga que sí y la cita esté: ni se le muestra la unidad."""
    settings.NORM_SUPPORT_MIN_SCORE = 0.95
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert not support.requests
    assert_untouched(run)
    [step] = steps(run)
    assert step.parsed["respaldos"] == 0
    assert step.request["min_score"] == 0.95


def test_a_norm_that_nobody_scores_gives_no_support_and_the_suggestion_stays(
        operator_user, script, filt, support, regimes, fake_ai, corpus, spy):  # noqa: F811
    """REQ-036: si nada alcanza el umbral del reranker, la sugerencia queda sin respaldo,
    exactamente como estaba (nunca se quita ni se marca)."""
    fake_ai.reranker.scores = {}

    run = run_case(operator_user, script, filt)

    assert supports(run) == [] and not support.requests
    assert_untouched(run)


def test_only_norm_units_count_not_opinions_or_audit_recommendations(
        operator_user, script, filt, support, regimes, marks, corpus, spy,  # noqa: F811
        make_norm, make_document, make_reading):
    """REQ-036: solo cuentan las unidades de normas; un dictamen no exige, interpreta."""
    opinion = make_norm(category="dictamen_legal", citation="Dictamen sintético 1/2020")
    reading = make_reading(make_document(opinion, effective_from=date(2020, 1, 1)),
                           [("art-1", "ARTÍCULO 1°.- Dictamen sobre garantías sintéticas "
                                      "de dictamen.")])
    marks.reranker.scores["sobre garantías sintéticas de dictamen"] = 0.99
    support.says(GARANTIAS)
    unit = reading.units_by_key["art-1"]

    run = run_case(operator_user, script, filt)

    assert unit.pk in {e["unit"] for e in steps(run)[0].request["retrieved"]}
    assert "de dictamen" not in support.shown()
    assert [s.text for s in supports(run)] == [GARANTIAS]


# --- La norma nunca cambia el estado de una fila ---------------------------------------------


@pytest.mark.parametrize("scenario", [
    "con respaldo", "modelo dice que no", "cita falsa", "salida invalida", "pedido falla",
    "recuperacion falla", "sin regimen", "apagada",
])
def test_no_outcome_of_the_consultation_changes_the_state_of_a_row(
        operator_user, script, filt, support, regimes, marks, corpus, spy, settings,  # noqa: F811
        scenario):
    """REQ-036 (la norma solo confirma): con respaldo, sin él, con cada falla posible, sin
    régimen o con la pasada apagada, la fila sigue `sugerido`, con su motivo, su origen y su
    cita; no se agrega ni se pierde ninguna fila."""
    authorization_date = AFTER
    support.says(GARANTIAS)
    if scenario == "modelo dice que no":
        support.rules.clear()
    elif scenario == "cita falsa":
        support.rules.clear()
        support.says(GARANTIAS, "si", "Texto que la unidad no tiene.")
    elif scenario == "salida invalida":
        support.raw("basura")
    elif scenario == "pedido falla":
        support.failing = True
    elif scenario == "recuperacion falla":
        spy.fail = True
    elif scenario == "sin regimen":
        authorization_date = date(2001, 1, 10)
    elif scenario == "apagada":
        settings.NORM_SUPPORT_ENABLED = False

    run = run_case(operator_user, script, filt, authorization_date=authorization_date)

    assert_untouched(run)
    assert len(formal(run)) == 1 and not m.DiscardedRow.objects.filter(run=run).exists()
    assert run.counts["filter"]["suggestions"] == 1
    assert len(supports(run)) == (1 if scenario == "con respaldo" else 0)
    assert not m.RequirementChange.objects.filter(requirement__version=run.version).exists()


def test_the_support_pass_has_no_way_to_change_a_verdict_or_a_row(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: `Supporter.support` recibe los veredictos del filtro y no toca ninguno:
    destino, motivo y fila siguen igual, haya o no respaldo."""
    from evaluon.tenders.proposal import filter as row_filter

    support.says(GARANTIAS)
    run = run_case(operator_user, script, filt)
    run.refresh_from_db()
    row = SimpleNamespace(
        segment=m.Segment.objects.filter(key__isnull=False).first(), found=object(),
        text=FRAG_1)
    verdict = row_filter.Verdict(row=row, destination=row_filter.SUGERENCIA,
                                 doubt_reason="duda")

    result = norm_support.Supporter(run).support([verdict])

    assert verdict.destination == row_filter.SUGERENCIA and verdict.doubt_reason == "duda"
    assert verdict.row is row and row.text == FRAG_1
    assert [s.text for s in result.supports[id(row.found)]] == [GARANTIAS]
    assert not hasattr(result, "destination")


# --- Fallas y bordes -------------------------------------------------------------------------


def test_a_failure_of_the_retrieval_leaves_the_suggestion_without_support_and_with_the_anomaly(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: una falla de la recuperación deja la sugerencia sin respaldo, con su
    anomalía, y la propuesta termina."""
    spy.fail = True

    run = run_case(operator_user, script, filt)

    assert supports(run) == [] and not support.requests
    assert_untouched(run)
    assert run.counts["norm_support"]["failed_retrieval"] == 1
    [step] = steps(run)
    assert [a["type"] for a in step.anomalies] == [norm_support.ANOMALY_RETRIEVAL]
    assert norm_support.ANOMALY_RETRIEVAL in [a["type"] for a in run.anomalies]


def test_a_failure_of_the_model_request_leaves_the_suggestion_without_support_and_with_the_anomaly(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: una falla del pedido al modelo deja la sugerencia sin respaldo, con su
    anomalía, y la propuesta termina."""
    support.failing = True

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert_untouched(run)
    assert run.counts["norm_support"]["failed_requests"] == 1
    [step] = steps(run)
    assert [a["type"] for a in step.anomalies] == [norm_support.ANOMALY_SERVICE]
    assert step.request["question"].startswith(QUESTION_START)


def test_without_a_regime_at_the_date_nothing_is_consulted(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-022, REQ-036: sin régimen a la fecha de autorización no hay consulta; la
    sugerencia sigue, con la anomalía `sin_regimen`."""
    run = run_case(operator_user, script, filt, authorization_date=date(2001, 1, 10))

    assert run.regime == []
    assert spy.calls == [] and not support.requests and steps(run) == []
    assert supports(run) == []
    assert_untouched(run)
    assert norm_support.ANOMALY_NO_REGIME in [a["type"] for a in run.anomalies]
    assert run.counts["norm_support"]["no_regime"] == 1


def test_firm_discarded_and_technical_rows_are_not_consulted(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: solo las sugerencias se consultan: no las firmes, ni las descartadas, ni las
    técnicas."""
    firm = "Los oferentes deberán cotizar el alquiler por jornada."
    dropped = "El adjudicatario armará los gazebos en el predio ferial."
    doubt = "Los precios incluirán el traslado de los gazebos."
    for text in (firm, doubt, dropped):
        script.when(text, item([(text, "formal")]))
    filt.when(firm, KEEP, "si")
    filt.when(dropped, discard(clue=dropped), "no")
    filt.when(doubt, KEEP, "duda")
    support.says(GARANTIAS)
    procedure = make_procedure(operator_user, AFTER)
    load_and_read(operator_user, procedure, pliego(firm, doubt, dropped))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    states = {r.quotes.get().text: r.state for r in formal(run)}
    assert states == {firm: "propuesto", doubt: "sugerido"}
    assert m.DiscardedRow.objects.filter(run=run).count() == 1
    assert m.Requirement.objects.filter(version=run.version, category="tecnico").exists()
    assert len(spy.calls) == 1 and doubt in spy.calls[0][0]
    assert firm not in spy.calls[0][0] and dropped not in spy.calls[0][0]
    assert run.counts["norm_support"]["suggestions"] == 1
    assert {s.requirement.quotes.get().text for s in supports(run)} == {doubt}


def test_with_the_pass_off_there_is_no_consultation(
        operator_user, script, filt, support, regimes, marks, corpus, spy, settings):  # noqa: F811
    """REQ-036: con `NORM_SUPPORT_ENABLED` en falso se saltea la pasada: sin consulta, sin
    pedidos, sin respaldo y sin la pasada ni sus instrucciones en la propuesta."""
    settings.NORM_SUPPORT_ENABLED = False
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    assert spy.calls == [] and not support.requests and steps(run) == []
    assert supports(run) == []
    assert "respaldo_normativo" not in run.parameters["passes"]
    assert "respaldo" not in run.prompt_versions
    assert "norm_support" not in run.counts
    assert_untouched(run)


# --- La pregunta y las instrucciones ---------------------------------------------------------


def test_the_fragment_is_trimmed_at_a_sentence_boundary():
    """REQ-036: el fragmento va recortado a un límite de oración si pasa del máximo; si cabe,
    no se toca."""
    text = "Primera oración corta. Segunda oración que sigue. Tercera oración final."
    assert norm_support.trim_fragment(text, 200) == text
    assert norm_support.trim_fragment(text, 40) == "Primera oración corta."
    assert norm_support.trim_fragment("palabra " * 20, 30).endswith("palabra")
    assert len(norm_support.trim_fragment("x" * 100, 30)) == 30


def test_the_question_carries_the_trimmed_fragment(
        operator_user, script, filt, support, regimes, marks, corpus, spy, settings):  # noqa: F811
    """REQ-036: la pregunta de la consulta lleva el fragmento recortado a
    `NORM_SUPPORT_QUERY_MAX_CHARS`."""
    settings.NORM_SUPPORT_QUERY_MAX_CHARS = 40
    long = "Los oferentes cotizarán el gazebo. Además presentarán la constancia de inscripción."

    run_case(operator_user, script, filt, text=long, fragment=long)

    [(question, _)] = spy.calls
    assert "Los oferentes cotizarán el gazebo." in question
    assert "constancia" not in question


def test_the_instructions_have_the_two_fields_and_synthetic_examples():
    """REQ-036: las instrucciones piden `exige` (`si` o `no`) y `cita` literal, con ejemplos
    inventados; la versión es la que fija `MATRIX_PROMPT_VERSIONS`."""
    from django.conf import settings as django_settings

    from evaluon.tenders.proposal import extraction

    prompt = extraction.load_prompt("respaldo")
    assert django_settings.MATRIX_PROMPT_VERSIONS["respaldo"] == "matriz-respaldo-v1"
    assert '"exige"' in prompt and '"cita"' in prompt
    assert "letra por letra" in prompt and "inventados" in prompt
    schema = norm_support.build_schema(["N1", "N2"])
    assert schema["required"] == ["N1", "N2"]
    assert schema["properties"]["N1"]["properties"]["exige"]["enum"] == ["si", "no"]


# --- Generalidad: ninguna ancla de los casos -------------------------------------------------

HASHES = Path(__file__).parent / "fixtures" / "case_anchor_hashes.txt"
SHINGLE = 5


def _shingles(text):
    import unicodedata

    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    for i in range(len(words) - SHINGLE + 1):
        yield " ".join(words[i:i + SHINGLE])


def test_no_instruction_module_or_test_of_the_support_repeats_five_words_of_a_case_anchor():
    """REQ-036 (generalidad): ni las instrucciones del respaldo, ni su módulo, ni estos tests
    repiten cinco palabras seguidas de las anclas de los casos (huellas SHA-256 en
    `fixtures/case_anchor_hashes.txt`; las anclas no están en el repositorio, P4)."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    files = [Path(__file__), Path(norm_support.__file__),
             Path(norm_support.__file__).parent.parent / "prompts" / "matriz-respaldo-v1.md"]
    hits = []
    for path in files:
        for shingle in _shingles(path.read_text(encoding="utf-8")):
            digest = hashlib.sha256(shingle.encode()).hexdigest()
            if digest in known:
                hits.append(f"{path.name}: {digest[:12]}")
    assert not hits, hits


# --- La pantalla con el indicio en el formato real (aviso de T-112) --------------------------

REAL_EVIDENCE = {"segment": 1, "char_start": 10, "char_end": 40,
                 "text": "indicio literal del tramo"}


# --- Largo mínimo de la cita -----------------------------------------------------------------

LARGA = "los oferentes deberán acompañar el certificado de calibración de cada balanza ofrecida"


@pytest.fixture
def long_norm(make_norm, make_document, make_reading, marks):  # noqa: F811
    norm = make_norm(category="marco_nacional", citation="Decreto sintético 5/2020")
    reading = make_reading(make_document(norm), [
        ("art-5", f"ARTÍCULO 5°.- Se establece que {LARGA}.")])
    marks.reranker.scores["Se establece que"] = 0.95
    return reading.units_by_key["art-5"]


def test_a_quote_of_four_content_words_or_more_is_support(
        operator_user, script, filt, support, regimes, long_norm, corpus, spy, monkeypatch):  # noqa: F811
    """REQ-036: con el largo mínimo de verdad (4 palabras con contenido), una cita larga
    sigue siendo respaldo."""
    monkeypatch.setattr(norm_support, "MIN_CITE_WORDS", 4)
    support.says("Se establece que", "si", LARGA)

    run = run_case(operator_user, script, filt)

    [saved] = supports(run)
    assert saved.unit_id == long_norm.pk and saved.text == LARGA


@pytest.mark.parametrize("cite", ["certificado de calibración de", "certificado de calibración", "certificado"])
def test_a_literal_quote_that_is_too_short_is_not_support_and_leaves_an_anomaly(
        operator_user, script, filt, support, regimes, long_norm, corpus, spy,  # noqa: F811
        monkeypatch, cite):
    """REQ-036: una cita literal de una, dos o tres palabras con contenido no marca "la norma
    la exige": sin respaldo, con la anomalía, y la sugerencia queda igual."""
    monkeypatch.setattr(norm_support, "MIN_CITE_WORDS", 4)
    assert cite in long_norm.text
    support.says("Se establece que", "si", cite)

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert_untouched(run)
    assert norm_support.ANOMALY_QUOTE_SHORT in [a["type"] for a in run.anomalies]


def test_the_minimum_is_the_one_of_the_filters_clue():
    """REQ-036: el mínimo es el mismo del indicio del filtro (T-102)."""
    from evaluon.tenders.proposal import filter as row_filter

    import inspect

    assert "MIN_CITE_WORDS = 4" in inspect.getsource(norm_support)
    assert row_filter.MIN_CLUE_WORDS == 4


# --- Unidades con cambios vigentes, considerandos y "no" con cita literal --------------------


def test_a_unit_with_a_change_in_force_at_the_date_gives_no_support_and_is_not_shown(
        operator_user, script, filt, support, regimes, marks, corpus, spy,  # noqa: F811
        make_norm, make_document, make_reading, make_relation):
    """REQ-036, REQ-007: si una relación `modifica` rige a la fecha sobre la unidad, el texto
    vigente no es el original: la unidad no se le muestra al modelo, no hay respaldo (aunque la
    cita esté en el original) y queda la anomalía. La sugerencia sigue igual."""
    modifier = make_norm(citation="Disposición sintética 9/2022")
    make_reading(make_document(modifier, effective_from=date(2022, 12, 1)),
                 [("art-1", "ARTÍCULO 1°.- Sustitúyese el artículo 2°.")])
    make_relation(modifier, regimes.new, "modifica", target_unit_key="anexo/art-2",
                  effective_date=date(2023, 1, 1))
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    assert supports(run) == []
    assert GARANTIAS not in support.shown()
    assert_untouched(run)
    unit = regimes.new_units["anexo/art-2"]
    assert {"type": norm_support.ANOMALY_UNIT_CHANGED, "unit": unit.pk} in steps(run)[0].anomalies


def test_a_change_that_starts_after_the_date_does_not_exclude_the_unit(
        operator_user, script, filt, support, regimes, marks, corpus, spy,  # noqa: F811
        make_norm, make_document, make_reading, make_relation):
    """REQ-036: un cambio que rige después de la fecha de autorización no cuenta: la unidad
    sigue siendo la vigente y da respaldo."""
    modifier = make_norm(citation="Disposición sintética 9/2022")
    make_reading(make_document(modifier, effective_from=date(2024, 1, 1)),
                 [("art-1", "ARTÍCULO 1°.- Sustitúyese el artículo 2°.")])
    make_relation(modifier, regimes.new, "modifica", target_unit_key="anexo/art-2",
                  effective_date=date(2024, 1, 1))
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    assert [s.text for s in supports(run)] == [GARANTIAS]


def test_a_literal_quote_with_exige_no_is_not_support(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036: `exige` en `no` con una cita que sí está literal en la unidad no es respaldo."""
    support.says(GARANTIAS, "no", GARANTIAS)

    run = run_case(operator_user, script, filt)

    assert support.requests and supports(run) == []
    assert_untouched(run)


def test_a_considerando_among_the_units_is_excluded(
        operator_user, script, filt, support, regimes, marks, corpus, spy,  # noqa: F811
        make_norm, make_document, make_reading):
    """REQ-036: un considerando de una norma del régimen no se muestra ni da respaldo, aunque
    tenga el puntaje más alto."""
    reading = make_reading(make_document(make_norm(category="marco_nacional",
                                                   citation="Decreto sintético 7/2020")), [
        {"key": "considerando-1", "unit_type": "considerando",
         "text": "Que la garantía de curso sintética es necesaria para el procedimiento."}])
    marks.reranker.scores["garantía de curso sintética"] = 0.99
    support.says(GARANTIAS)

    run = run_case(operator_user, script, filt)

    unit = reading.units_by_key["considerando-1"]
    assert unit.pk in {e["unit"] for e in steps(run)[0].request["retrieved"]}
    assert "garantía de curso sintética" not in support.shown()
    assert [s.text for s in supports(run)] == [GARANTIAS]


def test_the_offer_guarantee_a_pliego_takes_for_granted_is_consulted_by_the_condition(
        operator_user, script, filt, support, regimes, marks, corpus, spy):  # noqa: F811
    """REQ-036, T-178: la sugerencia que entra porque el pliego solo nombra la garantía de la
    oferta al decir qué pasa si falta se consulta con la condición nombrada y no con la
    oración de la sanción, que no se parece a ningún artículo."""
    # La frase se arma con un hueco: no repite palabras de las anclas de los casos.
    phrase = "garantía de {} de la oferta".format("mantenimiento")
    sentence = f"La falta de presentación en término determinará la pérdida de la {phrase}."
    procedure = make_procedure(operator_user, AFTER)
    load_and_read(operator_user, procedure, pliego(sentence))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    [(question, _)] = spy.calls
    assert phrase in question and "falta de presentación" not in question
    [row] = formal(requested.run)
    assert row.state == "sugerido" and row.quotes.get().text == sentence
