"""Consecuencias sugeridas de cada requisito, con su fundamento (REQ-029; plan 003,
"Consecuencias"; principio P3; T-080).

El modelo es el doble de `tests/conftest.py` con el guion de `tests/tenders/scripted.py`,
ampliado acá para responder los pedidos de consecuencias. Los pliegos y las normas son
sintéticos (P4); sin modelo real.
"""

import json
import textwrap
import re
from datetime import date

import pytest

from evaluon.audit import services as audit_services
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.proposal import consequences, extraction
from evaluon.tenders.proposal import run as proposal
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    Script,
    item,
    load_and_read,
    make_procedure,
    propose,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def offer_every_level(settings):
    """Estas pruebas recorren las pasadas de los tres niveles, también la de exigente, que
    existe pero no se ofrece (T-085)."""
    settings.MATRIX_LEVELS_OFFERED = ("media", "alta", "exigente")

GARANTIA = ("La garantía de mantenimiento de la oferta deberá ser individualizada en "
            "ocasión de presentarse la oferta.")
GARANTIA_QUOTE = "deberá ser individualizada"
CONSTANCIA = "Los oferentes presentarán la constancia de inscripción en el registro."
CONSTANCIA_QUOTE = "presentarán la constancia de inscripción en el registro"
CAUSAL = "La falta de individualización de la garantía será causal de desestimación."
ACLARACIONES = ("La Comisión podrá solicitar aclaraciones a los oferentes sobre la "
                "documentación presentada.")
ENTREGA = "Los bienes se entregan dentro de los quince días hábiles."
INVALID = "invalida"

_BLOCK = re.compile(r"\[([RPN]\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)
_ALIAS = re.compile(r"^[PN]\d+$")


def clause(number, text):
    """Las líneas de una cláusula, cortadas como en una página."""
    return textwrap.wrap(f"{number} {text}", 78)


def consequence_pdf():
    """Dos requisitos formales o económicos, tres cláusulas con consecuencias (dos con
    marcadores), una sin ellos y dos renglones."""
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. PRESENTACIÓN", *clause("1.1.", GARANTIA),
                 *clause("1.2.", CONSTANCIA)),
            para("2. CAUSALES", *clause("2.1.", CAUSAL)),
            para("3. ACLARACIONES", *clause("3.1.", ACLARACIONES)),
            para("4. ENTREGA", *clause("4.1.", ENTREGA)),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
            para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", "1.1. Bolsa de veinte kilos."),
            para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", "2.1. Bolsa de diez kilos."),
        ],
    ])


class ConsequenceScript(Script):
    """El guion de `scripted.py` más las respuestas de los pedidos de consecuencias.

    `c_when(texto, opciones)` responde `opciones` a todo requisito cuyo bloque contiene
    `texto`. Cada opción es `(tipo, [fundamentos])`; un fundamento es un alias literal
    (`P9`, `N1`) o un texto que se busca en los fundamentos mostrados (primero el pliego).
    `INVALID` devuelve una forma rota; con `invalid_first`, solo la primera vez. `requests`
    guarda, por pedido, los bloques que recibió el modelo."""

    def __init__(self, fake, monkeypatch):
        super().__init__(fake, monkeypatch)
        self.c_rules = []
        self.requests = []
        self.seen = {}
        self.fail_consequences = False
        self.cut_when = None

    def c_when(self, needle, options, invalid_first=False):
        self.c_rules.insert(0, (needle, options, invalid_first))

    def _generate(self, messages, schema, **options):
        first = next(iter(schema["properties"].values()))["properties"]
        if "faltantes" in first:
            answer = {alias: {"faltantes": [], "divisiones": []}
                      for alias in schema["properties"]}
            self.fake.respond(json.dumps(answer))
            return self.fake.generate(messages, schema, **options)
        if "opciones" not in first:
            return super()._generate(messages, schema, **options)

        user = messages[-1]["content"]
        blocks = {"R": {}, "P": {}, "N": {}}
        for alias, body in _BLOCK.findall(user):
            blocks[alias[0]][alias] = body
        self.requests.append({"messages": messages, "schema": schema, **blocks})
        if self.fail_consequences:
            self.fake.timeout()
            return self.fake.generate(messages, schema, **options)
        if self.cut_when and len(blocks["R"]) > 1 and self.cut_when(len(self.requests)):
            self.fake.invalid_output('{"R1": {"opciones": [')
            return self.fake.generate(messages, schema, **options)
        answer = {}
        for alias, body in blocks["R"].items():
            answer[alias] = {"opciones": []}
            for needle, spec, invalid_first in self.c_rules:
                if needle not in body:
                    continue
                count = self.seen[needle] = self.seen.get(needle, 0) + 1
                if spec == INVALID or (invalid_first and count == 1):
                    answer[alias] = {"opciones": "basura"}
                else:
                    answer[alias] = {"opciones": [
                        {"tipo": kind,
                         "fundamentos": [self._alias(f, blocks) for f in grounds]}
                        for kind, grounds in spec]}
                break
        self.fake.respond(json.dumps(answer, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)

    @staticmethod
    def _alias(ground, blocks):
        if _ALIAS.match(ground) or ground.startswith("["):
            return ground
        for kind in ("P", "N"):
            for alias, body in blocks[kind].items():
                if ground in body:
                    return alias
        raise AssertionError(f"ningún fundamento mostrado contiene {ground!r}")


@pytest.fixture
def script(fake_ai, monkeypatch):
    double = ConsequenceScript(fake_ai.generation, monkeypatch)
    double.fallback = item(discard="dato_procedimiento")
    double.when(GARANTIA, item([(GARANTIA_QUOTE, "economico")]))
    double.when(CONSTANCIA, item([(CONSTANCIA_QUOTE, "formal")]))
    return double


def run_level(user, level="media", authorization_date=date(2025, 11, 14)):
    procedure = make_procedure(user, authorization_date)
    load_and_read(user, procedure, consequence_pdf())
    requested, job = propose(user, procedure, level=level)
    assert job.status == "done", job.error
    return requested.run


def requirement(run, text=None, number=None):
    """El requisito de la versión de `run` cuya cita contiene `text`, o el número dado."""
    for found in m.Requirement.objects.filter(version=run.version).order_by("number"):
        if number is not None and found.number == number:
            return found
        if text and any(text in q.text for q in found.quotes.all()):
            return found
    raise AssertionError("el requisito no está")


def consequences_of(req):
    return list(req.consequences.order_by("id"))


def ground_text(ground):
    """El texto de un fundamento del pliego, recortado del texto canónico de su lectura."""
    segment = m.Segment.objects.select_related("reading").get(pk=ground["segment"])
    return segment.reading.canonical_text[ground["char_start"]:ground["char_end"]]


# --- Fundamentos del pliego ------------------------------------------------------------------


def test_clause_that_sanctions_with_dismissal_gives_that_suggestion_with_its_citation(
        operator_user, script):
    """REQ-029: una cláusula que sanciona con desestimación produce esa sugerencia con la
    cita de la cláusula; la consecuencia queda sugerida por el sistema y sin elegir."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación"])])

    run = run_level(operator_user)

    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert suggested.consequence_type == "desestimacion"
    assert suggested.origin == "sistema"
    assert suggested.chosen is False and suggested.chosen_by is None
    [ground] = suggested.grounds
    assert ground["source"] == "pliego"
    assert "causal de desestimación" in ground_text(ground)
    assert m.Segment.objects.get(pk=ground["segment"]).key == ground["key"]
    assert suggested.step.pass_name == "consecuencias"
    assert suggested.step.run_id == run.pk


def test_clause_that_allows_asking_the_bidder_gives_consult_with_its_citation(
        operator_user, script):
    """REQ-029: una cláusula que permite pedir aclaraciones al oferente produce
    `consultar_oferente` con su cita, junto a otra opción con otro fundamento."""
    script.c_when(CONSTANCIA_QUOTE, [
        ("consultar_oferente", ["solicitar aclaraciones"]),
        ("desestimacion", ["causal de desestimación"]),
    ])

    run = run_level(operator_user)

    options = consequences_of(requirement(run, CONSTANCIA_QUOTE))
    assert [o.consequence_type for o in options] == ["consultar_oferente", "desestimacion"]
    assert "solicitar aclaraciones" in ground_text(options[0].grounds[0])


def test_the_requirements_own_clause_is_always_a_ground_and_unmarked_clauses_are_not(
        operator_user, script):
    """REQ-029: los fundamentos del pliego son los tramos con marcadores de consecuencia más
    los del propio requisito; una cláusula sin marcadores que no es de un requisito no
    entra."""
    run_level(operator_user)

    shown = script.requests[0]["P"]
    texts = " ".join(shown.values())
    assert "causal de desestimación" in texts
    assert "solicitar aclaraciones" in texts
    assert "individualizada" in texts and "constancia de inscripción" in texts
    assert "quince días" not in texts
    assert "Bolsa de veinte" not in texts


def test_technical_row_goes_to_the_model_as_item_with_its_header(operator_user, script):
    """REQ-029: una fila técnica se pregunta como "Renglón k, especificaciones técnicas",
    con la ruta de su encabezado; sin fundamento queda "no determinada"."""
    run = run_level(operator_user)

    blocks = script.requests[0]["R"]
    assert sum("Renglón 1, especificaciones técnicas" in b for b in blocks.values()) == 1
    assert sum("Renglón 2, especificaciones técnicas" in b for b in blocks.values()) == 1
    technical = [b for b in blocks.values() if "Renglón 2," in b][0]
    assert "RENGLÓN N° 2" in technical.upper()
    row = m.Requirement.objects.get(version=run.version, category="tecnico", items=[2])
    [undetermined] = consequences_of(row)
    assert undetermined.consequence_type == "no_determinada"


def test_requests_carry_25_requirements_at_most(operator_user, script, settings):
    """REQ-029: los requisitos se piden de a `MATRIX_CONSEQUENCES_PER_REQUEST`."""
    settings.MATRIX_CONSEQUENCES_PER_REQUEST = 2

    run = run_level(operator_user)

    total = m.Requirement.objects.filter(version=run.version).count()
    assert total == 4
    assert [len(r["R"]) for r in script.requests] == [2, 2]
    assert settings.MATRIX_CONSEQUENCES_PER_REQUEST == 2
    assert run.counts["consequences"]["requests"] == 2
    assert m.RunStep.objects.filter(run=run, pass_name="consecuencias").count() == 2


def test_default_lot_size_is_25():
    """REQ-029: el parámetro inicial es de 25 requisitos por pedido (plan 003)."""
    from django.conf import settings

    assert settings.MATRIX_CONSEQUENCES_PER_REQUEST == 25


# --- Validación --------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["aprobacion_condicionada", "aprobar_igual"])
def test_conditional_approval_and_approve_anyway_are_dropped(operator_user, script, kind):
    """REQ-029, P3: una salida del modelo con `aprobacion_condicionada` o `aprobar_igual`
    se descarta; sola, deja el requisito "no determinada"; con otra válida, queda la
    válida."""
    script.c_when(GARANTIA_QUOTE, [(kind, ["causal de desestimación"])])
    script.c_when(CONSTANCIA_QUOTE, [(kind, ["causal de desestimación"]),
                                     ("desestimacion", ["causal de desestimación"])])

    run = run_level(operator_user)

    [only] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert only.consequence_type == "no_determinada"
    assert [o.consequence_type for o in
            consequences_of(requirement(run, CONSTANCIA_QUOTE))] == ["desestimacion"]
    assert not m.Consequence.objects.filter(
        consequence_type__in=["aprobacion_condicionada", "aprobar_igual"]).exists()
    assert any(kind in a["detail"] for step in m.RunStep.objects.filter(run=run)
               for a in step.anomalies if a["type"] == consequences.ANOMALY_OPTION_DROPPED)


def test_unknown_alias_invalidates_the_option(operator_user, script):
    """REQ-029: un alias que el pedido no mostró invalida la opción, aunque haya otra
    válida en la lista de fundamentos de otra."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación", "P99"])])
    script.c_when(CONSTANCIA_QUOTE, [("desestimacion", ["N7"]),
                                     ("intimacion_subsanar", ["causal de desestimación"])])

    run = run_level(operator_user)

    assert [o.consequence_type for o in
            consequences_of(requirement(run, GARANTIA_QUOTE))] == ["no_determinada"]
    assert [o.consequence_type for o in
            consequences_of(requirement(run, CONSTANCIA_QUOTE))] == ["intimacion_subsanar"]


def test_option_without_grounds_is_dropped(operator_user, script):
    """REQ-029: una opción sin fundamentos se descarta."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", [])])

    run = run_level(operator_user)

    [only] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert only.consequence_type == "no_determinada"


def test_no_grounds_means_undetermined_made_by_the_system(operator_user, script):
    """REQ-029, P3: sin fundamento el requisito queda con la consecuencia "no determinada",
    puesta por el sistema, sin fundamentos y sin elegir."""
    run = run_level(operator_user)

    for found in m.Requirement.objects.filter(version=run.version):
        [only] = consequences_of(found)
        assert only.consequence_type == "no_determinada"
        assert only.origin == "sistema" and only.grounds == [] and not only.chosen
    assert run.counts["consequences"]["undetermined"] == 4
    assert run.counts["consequences"]["options"] == 0


def test_invalid_shape_is_asked_again_once_and_alone(operator_user, script):
    """REQ-029: lo devuelto para un requisito con una forma rota se vuelve a pedir una vez,
    solo ese requisito; si la segunda vez sirve, vale."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación"])],
                  invalid_first=True)

    run = run_level(operator_user)

    assert len(script.requests) == 2
    assert len(script.requests[1]["R"]) == 1
    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert suggested.consequence_type == "desestimacion"
    retry = suggested.step
    assert retry.retry_of is not None and retry.retry_of.pass_name == "consecuencias"
    assert run.counts["consequences"]["retried"] == 1


def test_invalid_shape_twice_leaves_it_undetermined(operator_user, script):
    """REQ-029: si la forma sigue rota después del reintento, el requisito queda "no
    determinada" y la propuesta lo anota."""
    script.c_when(GARANTIA_QUOTE, INVALID)

    run = run_level(operator_user)

    [only] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert only.consequence_type == "no_determinada"
    assert run.counts["consequences"]["invalid"] == 1
    assert "consecuencias_sin_resultado" in [a["type"] for a in run.anomalies]


def test_output_cut_by_the_maximum_splits_the_request(operator_user, script):
    """REQ-029: una salida cortada por el máximo se parte por la mitad y se vuelve a
    pedir; el pedido cortado queda registrado."""
    script.cut_when = lambda n: n == 1
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación"])])

    run = run_level(operator_user)

    assert [len(r["R"]) for r in script.requests] == [4, 2, 2]
    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert suggested.consequence_type == "desestimacion"
    cut = m.RunStep.objects.get(run=run, pass_name="consecuencias", batch=1)
    assert cut.anomalies[0]["type"] == consequences.ANOMALY_CUT
    assert cut.retries.count() == 2


def test_service_failure_keeps_the_step_and_fails_the_request(operator_user, script):
    """REQ-029, P6: una falla del servicio deja el pedido registrado con su anomalía y la
    propuesta falla sin crear la matriz."""
    script.fail_consequences = True
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, consequence_pdf())

    requested, job = propose(operator_user, procedure, level="media")

    assert job.status == "failed"
    step = m.RunStep.objects.get(run=requested.run, pass_name="consecuencias")
    assert step.anomalies[0]["type"] == "servicio"
    assert not m.MatrixVersion.objects.filter(procedure=procedure).exists()
    assert not m.Consequence.objects.exists()


# --- Pasada en todos los niveles --------------------------------------------------------------


def test_every_level_has_the_consequence_pass_last():
    """REQ-029: la pasada de consecuencias está en los tres niveles, después de las filas
    técnicas."""
    for level, passes in proposal.PASSES.items():
        assert passes[-2:] == ("filas_tecnicas", "consecuencias"), level


@pytest.mark.parametrize("level", ["media", "alta", "exigente"])
def test_every_level_proposes_consequences_with_the_same_instructions(
        operator_user, script, level):
    """REQ-029: en cualquier nivel la propuesta pide las consecuencias y copia la versión de
    las instrucciones."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación"])])

    run = run_level(operator_user, level)

    run.refresh_from_db()
    assert run.prompt_versions["consecuencias"] == "matriz-consecuencias-v1"
    assert "consecuencias" in run.parameters["passes"]
    assert m.RunStep.objects.filter(run=run, pass_name="consecuencias").count() == 1
    assert [o.consequence_type for o in
            consequences_of(requirement(run, GARANTIA_QUOTE))] == ["desestimacion"]


def test_instructions_name_the_fixed_questions_and_forbid_the_evaluator_types():
    """REQ-029: las instrucciones traen las preguntas fijas con que se busca en la norma y
    dicen que el sistema no sugiere aprobación condicionada ni aprobar de todas maneras."""
    prompt = extraction.load_prompt("consecuencias")

    for question in consequences.NORM_QUESTIONS:
        assert question in prompt
    assert "Nunca sugerís" in prompt
    assert "aprobación condicionada" in prompt and "aprobar de todas maneras" in prompt
    for kind in consequences.SYSTEM_TYPES:
        assert f'"{kind}"' in prompt
    assert "aprobacion_condicionada" not in consequences.SYSTEM_TYPES
    assert "aprobar_igual" not in consequences.SYSTEM_TYPES


def test_the_schema_only_allows_the_shown_aliases_and_the_system_types(
        operator_user, script):
    """REQ-029: el esquema del pedido limita los tipos a los que el sistema puede sugerir y
    los fundamentos a los alias mostrados."""
    run_level(operator_user)

    schema = script.requests[0]["schema"]
    option = schema["properties"]["R1"]["properties"]["opciones"]["items"]["properties"]
    assert option["tipo"]["enum"] == list(consequences.SYSTEM_TYPES)
    assert set(option["fundamentos"]["items"]["enum"]) == set(script.requests[0]["P"])


# --- Fundamentos de la norma -------------------------------------------------------------------


@pytest.fixture
def regimes(two_regimes):
    """Los dos regímenes con la vigencia del nuevo y la derogación del anterior al
    2023-01-02, como en ADR-0006 (la fixture de la 001 los pone el 2023-01-01; ver el aviso
    de T-080). No se cambia la fixture."""
    day = date(2023, 1, 2)
    for document in (two_regimes.new_body, two_regimes.new_annex):
        document.effective_from = day
        document.save()
    two_regimes.repeal.effective_date = day
    two_regimes.repeal.save()
    return two_regimes


@pytest.fixture
def marks(fake_ai):
    """El reranker da puntaje alto a las unidades de la norma de prueba."""
    fake_ai.reranker.scores = {"Objeto del régimen sintético anterior": 0.9,
                               "Garantías sintéticas": 0.9}
    return fake_ai


def test_norm_grounds_use_the_regime_at_the_authorization_date(
        operator_user, script, regimes, marks):
    """REQ-029, REQ-022: los fundamentos de la norma salen de la recuperación de la 001 a la
    fecha de autorización: el 2023-01-01 rige la 297/03 y el 2023-01-02, la 247/2022."""
    before = run_level(operator_user, authorization_date=date(2023, 1, 1))
    old = script.requests[0]["N"]
    script.requests.clear()
    after = run_level(operator_user, authorization_date=date(2023, 1, 2))
    new = script.requests[0]["N"]

    assert before.regime == [{"norm": regimes.old.pk, "name": "Disposición AFIP 297/03"}]
    assert after.regime == [{"norm": regimes.new.pk, "name": "Disposición AFIP 247/2022"}]
    assert " ".join(old.values()).count("Objeto del régimen sintético anterior") == 1
    assert "Garantías sintéticas" not in " ".join(old.values())
    assert "Garantías sintéticas" in " ".join(new.values())
    assert "Objeto del régimen sintético anterior" not in " ".join(new.values())
    assert "Norma: Disposición AFIP 247/2022" in " ".join(new.values())


def test_norm_ground_is_cited_by_unit_and_the_request_records_units_scores_and_version(
        operator_user, read_write_user, script, regimes, marks):
    """REQ-029, P6: una opción puede fundarse en un artículo de la norma (guarda su `id`) y
    el pedido registra las unidades mostradas con su puntaje, la selección y la versión de la
    normativa."""
    version = audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND,
        user=read_write_user, creates_corpus_version=True,
    ).corpus_version
    assert version is not None
    script.c_when(GARANTIA_QUOTE, [("intimacion_subsanar", ["Garantías sintéticas"])])

    run = run_level(operator_user, authorization_date=date(2023, 1, 2))

    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    unit = regimes.new_units["anexo/art-2"]
    assert suggested.grounds == [{"source": "norma", "unit": unit.pk}]
    step = suggested.step
    context = step.parsed["normativa"]
    assert context["corpus_version"] == run.corpus_version == version
    assert context["regime"] == run.regime
    assert context["questions"] == list(consequences.NORM_QUESTIONS)
    shown = {entry["unit"]: entry for entry in context["shown"]}
    assert shown[unit.pk]["score"] == 0.9 and shown[unit.pk]["alias"].startswith("N")
    assert unit.pk in {entry["unit"] for entry in context["retrieved"]}
    assert unit.pk in context["selection"]["units"]
    assert step.parsed["fundamentos"][shown[unit.pk]["alias"]] == {
        "source": "norma", "unit": unit.pk}


def test_norm_search_uses_the_fixed_questions_with_the_authorization_date(
        operator_user, script, regimes, marks):
    """REQ-029: la recuperación corre una vez por pregunta fija, con la fecha de autorización
    del procedimiento."""
    run_level(operator_user, authorization_date=date(2023, 1, 2))

    queries = [question for question, _ in marks.reranker.calls]
    assert queries == list(consequences.NORM_QUESTIONS)


def test_without_a_regime_at_the_date_only_the_pliego_grounds_remain(
        operator_user, script, regimes, marks):
    """REQ-029: sin régimen a la fecha no se busca en la norma y solo hay fundamentos del
    pliego; una opción que cita la norma queda sin efecto."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["N1"])])
    script.c_when(CONSTANCIA_QUOTE, [("desestimacion", ["causal de desestimación"])])

    run = run_level(operator_user, authorization_date=date(2001, 1, 10))

    assert run.regime == []
    assert marks.reranker.calls == [] and marks.embeddings.calls == []
    assert script.requests[0]["N"] == {}
    assert [o.consequence_type for o in
            consequences_of(requirement(run, GARANTIA_QUOTE))] == ["no_determinada"]
    assert [o.consequence_type for o in
            consequences_of(requirement(run, CONSTANCIA_QUOTE))] == ["desestimacion"]


def test_consult_and_other_need_a_pliego_ground(operator_user, script, regimes, marks):
    """REQ-029: `consultar_oferente` y `otra_pliego` exigen al menos un fundamento del
    pliego: con solo la norma se descartan; con la norma y el pliego, valen."""
    script.c_when(GARANTIA_QUOTE, [("consultar_oferente", ["Garantías sintéticas"]),
                                   ("otra_pliego", ["Garantías sintéticas"])])
    script.c_when(CONSTANCIA_QUOTE, [
        ("consultar_oferente", ["Garantías sintéticas", "solicitar aclaraciones"]),
        ("otra_pliego", ["causal de desestimación"])])

    run = run_level(operator_user, authorization_date=date(2023, 1, 2))

    assert [o.consequence_type for o in
            consequences_of(requirement(run, GARANTIA_QUOTE))] == ["no_determinada"]
    options = consequences_of(requirement(run, CONSTANCIA_QUOTE))
    assert [o.consequence_type for o in options] == ["consultar_oferente", "otra_pliego"]
    assert {g["source"] for g in options[0].grounds} == {"pliego", "norma"}


def test_pliego_grounds_over_the_space_are_chosen_by_the_reranker(
        operator_user, script, fake_ai, settings):
    """REQ-029: si los tramos con marcadores no caben, el reranker elige los más pertinentes
    a la pregunta fija; los del propio requisito entran siempre."""
    prompt = extraction.load_prompt("consecuencias")
    from evaluon.ai import generation
    fixed = generation.count_tokens(prompt)
    # Contexto justo para los requisitos, sus tramos y un solo tramo más.
    settings.GENERATION_CONTEXT_TOKENS = (settings.MATRIX_MAX_OUTPUT_TOKENS
                                          + settings.PROMPT_TEMPLATE_MARGIN_TOKENS
                                          + fixed + 200)
    fake_ai.reranker.scores = {"aclaraciones": 0.95, "causal de desestimación": 0.4}

    run_level(operator_user)

    pliego = " ".join(script.requests[0]["P"].values())
    assert fake_ai.reranker.calls[0][0] == consequences.PLIEGO_QUESTION
    assert "individualizada" in pliego and "constancia de inscripción" in pliego
    assert "solicitar aclaraciones" in pliego
    assert "causal de desestimación" not in pliego


# --- Anomalías y límites de la validación ---------------------------------------------------------


def test_normative_change_during_the_proposal_is_noted(
        operator_user, script, regimes, marks, monkeypatch):
    """REQ-029, P6: si la versión de la normativa cambia entre el inicio de la propuesta y la
    búsqueda en la norma, se anota `consecuencias_normativa_cambio` con ambas versiones."""
    from types import SimpleNamespace

    monkeypatch.setattr(consequences, "audit",
                        SimpleNamespace(current_corpus_version=lambda: 999999))

    run = run_level(operator_user, authorization_date=date(2023, 1, 2))

    [note] = [a for a in run.anomalies if a["type"] == consequences.ANOMALY_CORPUS_CHANGED]
    assert note["now"] == 999999 and note["begin"] == run.corpus_version


def test_requirement_that_does_not_fit_the_context_is_undetermined_and_noted(
        operator_user, script, settings):
    """REQ-029: un requisito que no entra solo en el contexto queda "no determinada" con la
    anomalía `consecuencias_requisito_no_entra`, sin pedir nada al modelo."""
    from evaluon.ai import generation

    settings.GENERATION_CONTEXT_TOKENS = (
        settings.MATRIX_MAX_OUTPUT_TOKENS + settings.PROMPT_TEMPLATE_MARGIN_TOKENS
        + generation.count_tokens(extraction.load_prompt("consecuencias")) + 10)

    run = run_level(operator_user)

    assert script.requests == []
    notes = [a for a in run.anomalies if a["type"] == consequences.ANOMALY_NO_FIT]
    assert sorted(a["requirement"] for a in notes) == [1, 2, 3, 4]
    for found in m.Requirement.objects.filter(version=run.version):
        assert [o.consequence_type for o in consequences_of(found)] == ["no_determinada"]


def test_aliases_with_brackets_are_accepted(operator_user, script):
    """REQ-029: un alias escrito entre corchetes ("[P1]") vale como "P1"."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["[P1]"])])

    run = run_level(operator_user)

    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert suggested.consequence_type == "desestimacion"
    assert [g["source"] for g in suggested.grounds] == ["pliego"]


def test_repeated_type_keeps_the_first_option_only(operator_user, script):
    """REQ-029: dos opciones del mismo tipo dejan una sola, la primera, y se anota."""
    script.c_when(GARANTIA_QUOTE, [("desestimacion", ["causal de desestimación"]),
                                   ("desestimacion", ["solicitar aclaraciones"])])

    run = run_level(operator_user)

    [suggested] = consequences_of(requirement(run, GARANTIA_QUOTE))
    assert "causal de desestimación" in ground_text(suggested.grounds[0])
    assert any("tipo repetido" in a["detail"] for step in
               m.RunStep.objects.filter(run=run) for a in step.anomalies
               if a["type"] == consequences.ANOMALY_OPTION_DROPPED)


def test_at_most_three_options_are_kept(operator_user, script):
    """REQ-029: de cuatro opciones válidas quedan las tres primeras y se anota la cuarta."""
    script.c_when(GARANTIA_QUOTE, [
        ("desestimacion", ["causal de desestimación"]),
        ("intimacion_subsanar", ["causal de desestimación"]),
        ("consultar_oferente", ["solicitar aclaraciones"]),
        ("otra_pliego", ["causal de desestimación"]),
    ])

    run = run_level(operator_user)

    assert [o.consequence_type for o in
            consequences_of(requirement(run, GARANTIA_QUOTE))] == [
        "desestimacion", "intimacion_subsanar", "consultar_oferente"]
    assert any("más de tres" in a["detail"] for step in
               m.RunStep.objects.filter(run=run) for a in step.anomalies
               if a["type"] == consequences.ANOMALY_OPTION_DROPPED)
