"""Evaluación: el razonamiento primero y cada condición del requisito con su dato, su cita y su
resultado (REQ-104, REQ-105, REQ-106; plan 015, "Flujo de IA · Evaluación"; ADR-0055; T-237).

La decisión literal «Unidad de la fila» (spec 015): la evaluación revisa todas las condiciones de la
fila, cada una con su dato y su resultado visible por separado; «cumple» solo si se cumplen todas,
«no cumple» si falla alguna, «no determinado» diciendo cuál falta. El modelo es un guion
(`fakes.py`); textos inventados (P4).
"""

import hashlib
import json

import pytest
from django.conf import settings

from evaluon.assessment import citations, prompting
from evaluon.assessment import models as am
from tests.assessment.fakes import first_user, model, says  # noqa: F401
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    results_of,
    run_all,
)

pytestmark = pytest.mark.django_db

C = prompting.Condition


def conds(*results):
    return [C(f"condición {i}", "dato", 1, r) for i, r in enumerate(results, start=1)]


# --- El esquema, en el orden en que el modelo escribe --------------------------------------------


def test_the_evaluation_schema_goes_reasoning_citations_flags_conditions_then_verdict():
    """REQ-104, REQ-106: `razonamiento` primero, después las citas, `externo` e `ilegible`, las
    condiciones y, al final, resultado, explicación y pregunta."""
    schema = prompting.evaluation_schema(["D1"], [], ["P1"])
    order = list(schema["properties"])
    assert order[:4] == ["razonamiento", "citas", "fundamentos", "externo"]
    assert order.index("externo") < order.index("ilegible") < order.index("condiciones")
    assert (order.index("condiciones") < order.index("resultado") < order.index("explicacion")
            < order.index("pregunta"))
    assert order[-1] == "pregunta"
    assert schema["properties"]["razonamiento"]["maxLength"] == prompting.REASONING_MAX_CHARS
    assert {"razonamiento", "condiciones", "externo", "ilegible"} <= set(schema["required"])
    condition = schema["properties"]["condiciones"]["items"]
    assert list(condition["properties"]) == ["condicion", "dato", "cita", "resultado"]
    assert condition["properties"]["resultado"]["enum"] == list(prompting.RESULTS)
    assert condition["properties"]["cita"]["enum"] == list(range(settings.ASSESSMENT_MAX_CITATIONS + 1))
    assert schema["properties"]["condiciones"]["minItems"] == 1


def test_the_contrast_and_clauses_schemas_reason_first():
    """REQ-104, REQ-106: el contraste razona antes de responder; el contraste por cláusula,
    antes de la lista, y en cada cláusula el motivo va antes del estado."""
    assert list(prompting.CONTRAST_SCHEMA["properties"]) == ["razonamiento", "respuesta"]
    clauses = prompting.CLAUSES_SCHEMA["properties"]
    assert list(clauses)[0] == "razonamiento"
    item = list(clauses["clausulas"]["items"]["properties"])
    assert item.index("motivo") < item.index("estado")


def test_the_output_is_read_with_and_without_reasoning_and_conditions():
    """REQ-104: la salida de `evaluacion-v6` trae razonamiento y condiciones; una salida
    guardada antes, no, y se sigue leyendo."""
    new = says("cumple", ("D1", "Texto."), reasoning="Primero razono.")
    parsed = prompting.parse_evaluation(json.dumps(new), ["D1"], [])
    assert parsed.reasoning == "Primero razono." and parsed.conditions[0].result == "cumple"
    old = {k: v for k, v in new.items() if k not in ("razonamiento", "condiciones")}
    parsed = prompting.parse_evaluation(json.dumps(old), ["D1"], [])
    assert parsed.reasoning == "" and parsed.conditions == [] and parsed.result == "cumple"
    broken = {**new, "condiciones": [{"condicion": "x", "dato": "", "cita": "uno",
                                      "resultado": "cumple"}]}
    with pytest.raises(prompting.InvalidOutput):
        prompting.parse_evaluation(json.dumps(broken), ["D1"], [])
    wrong = {**new, "condiciones": [{"condicion": "x", "dato": "", "cita": 0,
                                     "resultado": "quizás"}]}
    with pytest.raises(prompting.InvalidOutput):
        prompting.parse_evaluation(json.dumps(wrong), ["D1"], [])


def test_the_contrast_and_clauses_are_read_in_the_new_and_the_old_shape():
    """REQ-104: el contraste lee `razonamiento` y `respuesta` (y la forma anterior con `motivo`);
    el de cláusulas lee la forma nueva y la anterior."""
    assert prompting.parse_contrast('{"razonamiento": "Porque sí.", "respuesta": "si"}') == (
        "si", "Porque sí.")
    assert prompting.parse_contrast('{"respuesta": "no", "motivo": "Porque no."}') == (
        "no", "Porque no.")
    for bad in ('{"respuesta": "si"}', '{"razonamiento": "x"}', '{"razonamiento": "x", '
                '"respuesta": "tal vez"}'):
        with pytest.raises(prompting.InvalidOutput):
            prompting.parse_contrast(bad)
    row = {"clausula": "3.1", "motivo": "m", "estado": "coincide", "cita": ""}
    new = json.dumps({"razonamiento": "r", "clausulas": [row], "pregunta": ""})
    old = json.dumps({"clausulas": [{k: v for k, v in row.items() if k != "cita"}],
                      "pregunta": ""})
    assert prompting.parse_clauses(new)[0][0][1] == "coincide"
    assert prompting.parse_clauses(old)[0][0][1] == "coincide"


# --- El resultado se deriva de las condiciones ---------------------------------------------------


@pytest.mark.parametrize("results, expected", [
    (["cumple"], "cumple"),
    (["cumple", "cumple", "cumple"], "cumple"),
    (["cumple", "no_cumple"], "no_cumple"),
    (["cumple", "no_cumple", "no_determinado"], "no_cumple"),       # falla una: no cumple
    (["no_cumple", "no_consta"], "no_cumple"),
    (["cumple", "no_determinado"], "no_determinado"),               # falta el dato de una
    (["cumple", "no_consta"], "no_determinado"),
    (["no_determinado", "no_consta"], "no_determinado"),
    (["no_consta", "no_consta"], "no_consta"),
    (["no_determinado"], "no_determinado"),
])
def test_the_result_is_derived_from_the_conditions(results, expected):
    """REQ-104: «cumple» solo si se cumplen todas; «no cumple» si falla alguna; «no consta» si
    ninguna tiene nada; si falta el dato de alguna, «no determinado»."""
    assert prompting.derive_result(conds(*results)) == expected


def test_there_is_no_derived_result_without_conditions():
    assert prompting.derive_result([]) is None


def test_the_missing_condition_is_named():
    """REQ-104: un «no determinado» dice cuál condición falta."""
    items = [C("La cotización se hace en pesos argentinos.", "ARS", 1, "cumple"),
             C("La cotización incluye IVA.", "", 0, "no_determinado")]
    note = prompting.missing_note(items)
    assert "IVA" in note and "pesos" not in note and note.startswith("Falta el dato de la condición")
    assert prompting.missing_note(conds("cumple", "no_cumple")) == ""
    both = prompting.missing_note([C("A.", "", 0, "no_consta"), C("B.", "", 0, "no_determinado")])
    assert "las condiciones" in both and "«A»" in both and "«B»" in both


# --- De punta a punta ----------------------------------------------------------------------------


def declaration_call(call):
    return "declaración jurada" in call.requirement


def two_conditions(call, *, second="no_determinado", second_cite=0, first="cumple"):
    alias = call.alias_with(DECLARATION)
    return says(
        "cumple", (alias, DECLARATION),
        conditions=[("El oferente declara que está habilitado para contratar.", DECLARATION, 1,
                     first),
                    ("La declaración está firmada por el representante.", "", second_cite,
                     second)])


def declaration_result(runs, procedure):
    return results_of(runs[0])[number_of(procedure, "declaración jurada")]


def test_a_missing_condition_makes_the_cell_undetermined_and_says_which(
        offer, operator_user, procedure, model):
    """REQ-104: el modelo da «cumple» pero a la segunda condición le falta el dato: la celda es
    «no determinado», la explicación nombra la que falta y las dos condiciones quedan visibles
    con su dato, su cita y su resultado."""
    model.evaluates(lambda call: two_conditions(call) if declaration_call(call) else None)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert result.outcome == "no_determinado"
    assert "firmada por el representante" in result.explanation
    first, second = result.facts["condiciones"]
    assert first["resultado"] == "cumple" and first["dato"] == DECLARATION
    assert first["cita"]["tipo"] == "oferta" and first["cita"]["texto"].startswith(DECLARATION)
    assert first["cita"]["pagina"] == 1 and first["cita"]["documento"]
    assert second["resultado"] == "no_determinado" and second["cita"] is None
    assert len(model.contrast_calls) == 0   # lo que no es «cumple» ni «no cumple» no se contrasta
    step = am.Step.objects.filter(run=runs[0], purpose="grupo").get(
        requirement__number=number_of(procedure, "declaración jurada"))
    assert step.parsed["resultado"] == "cumple" and step.parsed["resultado_derivado"] == (
        "no_determinado")
    assert any(a["type"] == "resultado_derivado" for a in step.anomalies)


def test_all_the_conditions_met_is_cumple_and_one_failing_is_no_cumple(
        offer, operator_user, procedure, model):
    """REQ-104: con las dos condiciones cumplidas la celda es «cumple»; si una falla, «no cumple»
    aunque la otra falte."""
    model.evaluates(lambda call: two_conditions(call, second="cumple", second_cite=1)
                    if declaration_call(call) else None)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert result.outcome == "cumple"
    assert [c["resultado"] for c in result.facts["condiciones"]] == ["cumple", "cumple"]

    model.evaluates(lambda call: two_conditions(call, first="no_cumple", second="no_determinado")
                    if declaration_call(call) else None)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert result.outcome == "no_cumple"
    assert [c["resultado"] for c in result.facts["condiciones"]] == ["no_cumple",
                                                                     "no_determinado"]


def test_a_condition_without_a_located_citation_is_not_met(offer, operator_user, procedure, model):
    """REQ-104, P3: una condición «cumple» cuya cita no se ubicó (o no existe) no vale: pasa a
    «no determinado» y queda la anomalía. Con dos citas, solo vale la que apunta a una ubicada."""
    def function(call):
        if not declaration_call(call):
            return None
        alias = call.alias_with(DECLARATION)
        return says("cumple", (alias, DECLARATION), (alias, "Texto que no está"),
                    conditions=[("Declara que está habilitado.", DECLARATION, 1, "cumple"),
                                ("Presenta la constancia.", "Texto que no está", 2, "cumple")])

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert result.outcome == "no_determinado"
    first, second = result.facts["condiciones"]
    assert first["resultado"] == "cumple" and second["resultado"] == "no_determinado"
    assert second["resultado_modelo"] == "cumple" and second["cita"] is None
    assert "Presenta la constancia" in result.explanation
    assert any(a["type"] == "condicion_sin_cita" for a in runs[0].anomalies)


def test_an_output_without_conditions_keeps_the_models_result(offer, operator_user, procedure,
                                                             model):
    """REQ-104: una salida sin `condiciones` (anterior a `evaluacion-v6`) sigue valiendo por su
    `resultado`; no hay condiciones para mostrar."""
    def function(call):
        if declaration_call(call):
            answer = says("cumple", (call.alias_with(DECLARATION), DECLARATION))
            del answer["condiciones"], answer["razonamiento"]
            return answer

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert result.outcome == "cumple" and "condiciones" not in result.facts


def test_the_cell_shows_no_conditions_when_a_rule_decided(offer, operator_user, procedure, model):
    """REQ-104: si decidió una regla (aquí, la externa) la celda dice la regla y no las
    condiciones que escribió el modelo."""
    def function(call):
        if declaration_call(call):
            return says("no_determinado", external=True, conditions=[
                ("Se verifica en el Registro.", "", 0, "no_determinado")])

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    result = declaration_result(runs, procedure)
    assert "condiciones" not in result.facts


# --- Cada pedido guarda la versión y la huella de su instrucción (P6) ----------------------------


def test_every_request_records_the_version_and_hash_of_its_instruction(
        offer, operator_user, procedure, model):
    """REQ-106, P6: el `parsed` de cada pedido (lectura, contraste, también el inválido) y la
    corrida guardan la versión y la huella SHA-256 de la instrucción que se usó."""
    model.evaluates(lambda call: says("cumple", (call.alias_with(DECLARATION), DECLARATION))
                    if declaration_call(call) else None)
    _, runs = run_all(operator_user, procedure)
    run = runs[0]
    for name in ("evaluacion", "contraste", "clausulas"):
        version = settings.ASSESSMENT_PROMPT_VERSIONS[name]
        text = (prompting.PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")
        assert run.prompt_versions[name] == version
        assert run.prompt_versions["huellas"][name] == hashlib.sha256(
            text.replace("\r\n", "\n").encode()).hexdigest()
    steps = list(am.Step.objects.filter(run=run).exclude(purpose="reescritura"))
    assert steps
    for step in steps:
        record = step.parsed["instruccion"]
        assert record["version"] == settings.ASSESSMENT_PROMPT_VERSIONS[record["nombre"]]
        assert record["sha256"] == run.prompt_versions["huellas"][record["nombre"]]
        assert step.request["messages"][0]["content"] == prompting.load_prompt(record["nombre"])
    contrast = next(s for s in steps if s.purpose == "contraste")
    assert contrast.parsed["razonamiento"] and contrast.parsed["motivo"]


def test_an_invalid_output_still_records_its_instruction(offer, operator_user, procedure, model):
    """REQ-106, P6: el pedido cuya salida no tiene la forma pedida también deja su instrucción."""
    model.evaluates(lambda call: "esto no es JSON" if declaration_call(call) else None)
    _, runs = run_all(operator_user, procedure)
    steps = am.Step.objects.filter(
        run=runs[0], requirement__number=number_of(procedure, "declaración jurada"),
        purpose="grupo")
    assert steps.count() == 2
    for step in steps:
        assert step.parsed["instruccion"]["nombre"] == "evaluacion"
        assert step.parsed["instruccion"]["sha256"]


def test_the_read_request_allows_for_the_reasoning_tokens(offer, operator_user, procedure, model,
                                                          fake_generation):
    """REQ-104: el máximo de salida del pedido de lectura suma lo que ocupan el razonamiento y las
    condiciones, y la corrida lo registra."""
    model.evaluates(lambda call: None)
    _, runs = run_all(operator_user, procedure)
    grupo = am.Step.objects.filter(run=runs[0], purpose="grupo").first()
    assert grupo.request["max_tokens"] == prompting.evaluation_max_tokens() > (
        settings.ASSESSMENT_MAX_OUTPUT_TOKENS)
    assert runs[0].parameters["evaluation_max_output_tokens"] == prompting.evaluation_max_tokens()


# --- El reintento conserva lo anterior -----------------------------------------------------------


def test_the_retry_shows_the_model_its_previous_answer_and_the_unlocated_citation(
        offer, operator_user, procedure, model):
    """REQ-104, ADR-0055 regla 7: el reintento mantiene el primer mensaje del usuario, suma la
    respuesta anterior como turno del asistente y una corrección que nombra la cita que no se
    ubicó y pide la oración completa (no sugiere «no determinado»)."""
    def function(call):
        if declaration_call(call):
            retried = len(call.messages) > 2
            text = DECLARATION if retried else "Texto que no está"
            return says("cumple", (call.alias_with(DECLARATION), text))

    model.evaluates(function)
    _, runs = run_all(operator_user, procedure)
    asked = [c for c in model.calls if declaration_call(c)]
    assert len(asked) == 2
    first, second = asked
    assert [m["role"] for m in second.messages] == ["system", "user", "assistant", "user"]
    assert first_user(second.messages) == first_user(first.messages)
    assert json.loads(second.messages[2]["content"])["citas"][0]["texto"] == "Texto que no está"
    correction = second.messages[3]["content"]
    assert "«Texto que no está»" in correction and "oración completa" in correction
    assert "no_determinado" in correction and "ante la duda" not in correction.lower()
    assert declaration_result(runs, procedure).outcome == "cumple"


def test_the_contrast_retry_keeps_the_previous_answer(offer, operator_user, procedure, model):
    """REQ-104: también el reintento del contraste muestra la respuesta anterior."""
    answers = iter(["no es JSON", None])

    def contrast(call):
        return next(answers)

    model.evaluates(lambda call: says("cumple", (call.alias_with(DECLARATION), DECLARATION))
                    if declaration_call(call) else None)
    model.contrasts(contrast)
    _, runs = run_all(operator_user, procedure)
    second = model.contrast_calls[1]
    assert [m["role"] for m in second.messages] == ["system", "user", "assistant", "user"]
    assert second.messages[2]["content"] == "no es JSON"
    assert declaration_result(runs, procedure).outcome == "cumple"


# --- La cita de la oferta es la oración completa, leída con el módulo de la matriz ---------------


def test_the_citation_widens_with_the_sentences_module_of_the_matrix():
    """REQ-104: la cita se amplía a la oración completa con `sentences.py` (T-234): incluye la
    oración corta contigua que continúa con una anáfora y no corta en las abreviaturas. Una
    oración que empieza con «Deberá…» sin anáfora no se une por código (regla del Coordinador
    del 2026-10-11, T-234b): la junta el modelo si es del mismo asunto."""
    text = ("Cláusula primera. La garantía se constituye según el art. 5 del pliego. "
            "La misma será por el cinco por ciento del total. Otra cosa distinta.")
    start = text.index("del pliego")
    begin, end, unit, too_long = citations.widen(text, (start, start + 10))
    assert text[begin:end] == ("La garantía se constituye según el art. 5 del pliego. "
                               "La misma será por el cinco por ciento del total.")
    assert not too_long and unit == (begin, end)
    plain = text.replace("La misma será", "Deberá ser")
    begin, end, _, _ = citations.widen(plain, (start, start + 10))
    assert plain[begin:end] == "La garantía se constituye según el art. 5 del pliego."


def test_a_very_long_sentence_stays_as_the_fragment(settings):
    """REQ-104: una oración que pasa del largo máximo de una cita no se usa: queda el fragmento."""
    settings.ASSESSMENT_CITATION_MAX_CHARS = 40
    text = "Una oración muy larga que sigue y sigue sin un solo punto hasta el final. Otra."
    begin, end, unit, too_long = citations.widen(text, (4, 20))
    assert too_long and (begin, end) == (4, 20) and unit is not None


def test_context_is_read_around_the_citation_not_in_the_whole_document():
    """T-237: las oraciones vecinas salen de una ventana alrededor de la cita; en un documento
    largo la lectura no depende de su tamaño."""
    filler = "Texto de relleno del documento. " * 4000
    text = filler + "La oferta vale sesenta días. Plazo de entrega: diez días corridos. " + filler
    at = text.index("Plazo de entrega")
    assert citations._sentence_at(text, at) == (at, at + len("Plazo de entrega: diez días corridos."))
    before, _ = citations._sentence_at(text, at - 3)
    assert text[before:before + 8] == "La ofert"
