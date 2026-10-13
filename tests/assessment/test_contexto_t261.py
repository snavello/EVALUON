"""Lo que entra en un pedido de lectura de la evaluación (T-261, D-260-1; REQ-104).

Con el 27B, la oferta 3 del caso-00 fallaba entera porque un pedido de lectura (un grupo de
documentos que llenaba `ASSESSMENT_GROUP_TOKENS` y una fila técnica larga) pasaba del contexto del
motor de lotes. Ahora el tope de los documentos de cada grupo es lo que realmente entra (el contexto
menos la instrucción, el Portal, el requisito, las respuestas, las normas, la salida reservada y un
margen); un pedido que igual no entra se parte en dos y, si ni así entra, el requisito queda «no
determinado» con el motivo y su anomalía, y la oferta sigue.

El motor es el doble con guion (`fakes.py`, una palabra un token) con un contexto chico: rechaza,
como `llama-server`, un pedido cuyos mensajes pasan del contexto. Textos inventados (P4).
"""

import pytest
from django.conf import settings as django_settings

from evaluon.ai import InputTooLongError
from evaluon.ai import generation as generation_client
from evaluon.assessment import prompting, sizing
from evaluon.assessment.services import evaluate
from evaluon.audit.models import AuditEvent, EventType
from tests.assessment.fakes import model, says  # noqa: F401
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    results_of,
    run_all,
    sheets_firm,
    words,
)
from tests.conftest import count_words
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

# Lo que se reserva para la salida de un pedido de lectura (sin razonamiento en las pruebas).
OUTPUT = prompting.evaluation_max_tokens()


def reading_tokens(messages):
    """Los tokens de los mensajes como los cuenta el doble del motor."""
    return sum(count_words(str(m.get("content", ""))) for m in messages)


@pytest.fixture
def engine(model, monkeypatch):
    """El doble del motor con su contexto (`GENERATION_BATCH_CONTEXT_TOKENS`): rechaza, como
    `llama-server`, un pedido cuyos mensajes pasan del contexto, y anota los tokens y el máximo de
    salida de cada pedido de lectura que sí respondió. `engine.reject` es una función que recibe
    los mensajes y dice si el motor los rechaza igual (una cuenta que no coincide)."""

    class Engine:
        reject = None
        readings = []
        rejected = 0

    respond = model.respond

    def guarded(messages, schema, **kwargs):
        tokens = reading_tokens(messages)
        context = django_settings.GENERATION_BATCH_CONTEXT_TOKENS
        if tokens >= context or (Engine.reject and Engine.reject(messages, schema)):
            Engine.rejected += 1
            raise InputTooLongError(
                f"request ({tokens} tokens) exceeds the available context size "
                f"({context} tokens), try increasing it", service="generation")
        if "condiciones" in schema["properties"]:
            Engine.readings.append((tokens, kwargs.get("max_tokens")))
        return respond(messages, schema, **kwargs)

    Engine.readings = []
    monkeypatch.setattr(generation_client, "generate", guarded)
    return Engine


def cumple_declaration(call):
    """Un guion: la declaración jurada cumple en el grupo que la tiene; el resto, "no consta"."""
    if "declaración jurada" in call.requirement and call.alias_with(DECLARATION):
        return says("cumple", call.quote(DECLARATION), exigence="condicion")
    return None


def context_for(documents_room):
    """Un contexto en que, para un requisito sin nada más que la instrucción, quedan
    `documents_room` tokens para los documentos después de la salida y el margen."""
    system = count_words(prompting.load_prompt("evaluacion"))
    return system + OUTPUT + sizing.REQUEST_MARGIN_TOKENS + documents_room


# --- La cuenta -----------------------------------------------------------------------------


def test_the_group_budget_discounts_everything_that_goes_with_the_documents(settings):
    """REQ-104 (T-261): el tope de documentos es el contexto menos lo fijo del pedido, la salida y
    el margen; `ASSESSMENT_GROUP_TOKENS` es el techo y el tope nunca es negativo."""
    assert sizing.documents_budget(10_000, 2_000, context=32_768, ceiling=20_000,
                                   margin=1_024) == 19_744
    assert sizing.documents_budget(13_000, 2_000, context=32_768, ceiling=20_000,
                                   margin=1_024) == 16_744
    assert sizing.documents_budget(1_000, 2_000, context=32_768, ceiling=20_000,
                                   margin=1_024) == 20_000
    assert sizing.documents_budget(40_000, 2_000, context=32_768, ceiling=20_000) == 0
    settings.GENERATION_BATCH_CONTEXT_TOKENS = 30_000
    settings.ASSESSMENT_GROUP_TOKENS = 25_000
    assert sizing.documents_budget(5_000, 2_000) == 30_000 - 5_000 - 2_000 - 1_024


def test_the_reserved_output_adds_the_reasoning_cap_only_when_the_step_thinks(settings):
    """REQ-104, REQ-107 (T-261): con el razonamiento de la lectura encendido se reserva también
    su tope; apagado, solo el máximo de salida."""
    settings.GENERATION_BATCH_REASONING = {**settings.GENERATION_BATCH_REASONING,
                                           "evaluation": "off"}
    assert sizing.reserved_output(2_000, "evaluation") == 2_000
    settings.GENERATION_BATCH_REASONING = {**settings.GENERATION_BATCH_REASONING,
                                           "evaluation": "low"}
    low = settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS["low"]
    assert sizing.reserved_output(2_000, "evaluation") == 2_000 + low
    assert sizing.reserved_output(2_000) == 2_000


def test_a_request_is_counted_as_it_goes_out(fake_generation, settings):
    """REQ-104 (T-261): la cuenta de un pedido armado suma cada mensaje con el tokenizador del
    motor de lotes y lo que agrega la plantilla."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = 100
    messages = [{"role": "system", "content": "uno dos tres"},
                {"role": "user", "content": "cuatro cinco"}]
    assert sizing.messages_tokens(messages) == 5 + sizing.TEMPLATE_TOKENS
    assert sizing.request_fits(messages, 100 - 5 - sizing.TEMPLATE_TOKENS) == (
        True, 5 + sizing.TEMPLATE_TOKENS)
    assert sizing.request_fits(messages, 100 - 4 - sizing.TEMPLATE_TOKENS) == (
        False, 5 + sizing.TEMPLATE_TOKENS)


# --- Una oferta grande que hoy desborda ----------------------------------------------------


@pytest.fixture
def large_offer(procedure, operator_user, settings):
    """Una oferta inventada de siete documentos de unas mil palabras, que con el tope de siempre
    entra en un solo grupo (`ASSESSMENT_GROUP_TOKENS`) pero cuyo pedido no entra en el contexto."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = context_for(3_000)
    pages = {"declaracion.pdf": [f"{DECLARATION}. {words(990, 'a')}"]}
    for number in range(1, 7):
        pages[f"anexo-{number}.pdf"] = [f"Anexo {number}. {words(1000, f'x{number}-')}"]
    return make_offer(procedure, operator_user, "Oferente grande", pages)


def test_a_large_offer_that_overflowed_is_read_in_groups_that_fit_and_finishes(
        large_offer, operator_user, procedure, model, engine, settings):
    """REQ-104 (T-261, D-260-1): la oferta entra en `ASSESSMENT_GROUP_TOKENS` pero no en el
    contexto con la instrucción y la salida; antes se mandaba en un pedido que el motor rechazaba y
    la oferta quedaba sin evaluar. Ahora cada grupo se arma con lo que entra: ningún pedido pasa
    del contexto, la evaluación termina y la declaración se encuentra en su grupo."""
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure, offers=[large_offer])
    run = runs[0]
    context = settings.GENERATION_BATCH_CONTEXT_TOKENS
    assert engine.rejected == 0
    assert engine.readings and all(tokens + out <= context for tokens, out in engine.readings)
    # Con el tope de siempre, la oferta entraba en un solo grupo; con la instrucción, no entra.
    assert run.counts["tokens"] <= settings.ASSESSMENT_GROUP_TOKENS
    assert run.counts["tokens"] + count_words(prompting.load_prompt("evaluacion")) > context
    results = results_of(run)
    assert len(results) == len(sheets_firm(procedure))
    declaration = number_of(procedure, "declaración jurada")
    assert results[declaration].outcome == "cumple"
    groups = [c for c in model.calls if "declaración jurada" in c.requirement]
    assert len(groups) > 1 and all(len(c.documents) < 7 for c in groups)
    # P6: el contexto, el margen y el tope de cada requisito quedan en el registro.
    assert run.parameters["context_tokens"] == context
    assert run.parameters["request_margin_tokens"] == sizing.REQUEST_MARGIN_TOKENS
    budgets = run.counts["group_budgets"]
    assert set(budgets) == {str(r.number) for r in sheets_firm(procedure)}
    assert all(0 < budget < settings.ASSESSMENT_GROUP_TOKENS for budget in budgets.values())
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_BUILD, outcome="ok").count() == 1


def test_a_part_that_does_not_fit_even_split_is_not_determined_and_the_offer_goes_on(
        procedure, operator_user, model, engine, settings):
    """REQ-104 (T-261): una página que sola no entra en el contexto no se manda; esa parte queda
    «no determinado» por lectura incompleta con el motivo «el pedido no entra en el contexto» y su
    anomalía (P6), y la evaluación sigue con el resto de la oferta y con los demás requisitos."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = context_for(3_000)
    offer = make_offer(procedure, operator_user, "Oferente con una página enorme", {
        "declaracion.pdf": [f"{DECLARATION}. {words(50, 'a')}"],
        "planilla.pdf": [f"Planilla. {words(7000, 'p')}"]})
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    assert engine.rejected == 0
    # La página enorme nunca salió al motor.
    assert not any("Planilla." in text for c in model.calls for text in c.documents.values())
    results = results_of(run)
    assert len(results) == len(sheets_firm(procedure))
    declaration = results[number_of(procedure, "declaración jurada")]
    assert declaration.outcome == "no_determinado"
    assert declaration.doubt == "lectura_incompleta"
    assert evaluate.TOO_LONG_NOTE in declaration.explanation
    too_long = [a for a in run.anomalies if a["type"] == evaluate.ANOMALY_TOO_LONG]
    assert {a["requirement"] for a in too_long} == {r.number for r in sheets_firm(procedure)}
    assert all(a["tokens"] + a["output"] > a["context"] for a in too_long)
    event = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD)
    assert event.outcome == "ok"
    assert any(a["type"] == evaluate.ANOMALY_TOO_LONG for a in event.detail["anomalies"])


def test_without_room_for_any_document_nothing_is_asked_and_the_offer_finishes(
        offer, operator_user, procedure, model, engine, settings):
    """REQ-104 (T-261): si ni sin documentos entra el pedido (la instrucción y la salida llenan el
    contexto), no se manda nada: cada requisito queda «no determinado» con el motivo y su
    anomalía, y la evaluación de la oferta termina."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = count_words(prompting.load_prompt("evaluacion"))
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    assert not model.calls and engine.rejected == 0
    results = results_of(run)
    assert len(results) == len(sheets_firm(procedure))
    assert all(r.outcome == "no_determinado" and evaluate.TOO_LONG_NOTE in r.explanation
               for r in results.values())
    assert set(run.counts["group_budgets"].values()) == {0}
    assert {a["requirement"] for a in run.anomalies if a["type"] == evaluate.ANOMALY_TOO_LONG} \
        == {r.number for r in sheets_firm(procedure)}


def test_a_request_the_engine_rejects_is_split_and_then_not_determined(
        offer, operator_user, procedure, model, engine):
    """REQ-104 (T-261): si el motor rechaza un pedido por el contexto aunque la cuenta diera que
    entraba, el grupo se parte (hasta `MAX_SPLITS` veces); lo que ni así entra queda «no
    determinado» con su motivo, el pedido rechazado queda registrado (P6) y los demás requisitos
    se evalúan."""
    engine.reject = lambda messages, schema: ("condiciones" in schema["properties"]
                                              and "declaración jurada" in messages[1]["content"])
    model.evaluates(lambda call: says("cumple", call.quote(
        "La oferta mantiene su validez por sesenta días corridos."))
        if "mantenimiento" in call.requirement and call.alias_with("sesenta días") else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    number = number_of(procedure, "declaración jurada")
    results = results_of(run)
    assert results[number].outcome == "no_determinado"
    assert evaluate.TOO_LONG_NOTE in results[number].explanation
    assert len(results) == len(sheets_firm(procedure))
    # El grupo de los dos documentos se parte en dos y el de dos páginas, en sus páginas: el
    # grupo, el documento de dos páginas, cada una de sus páginas y la constancia (5 pedidos).
    assert engine.rejected == 5
    splits = [a for a in run.anomalies
              if a["type"] == evaluate.ANOMALY_SPLIT and a["requirement"] == number]
    assert [a["splits"] for a in splits] == [0, 1]
    rejected = run.steps.filter(requirement__number=number, purpose="grupo")
    assert rejected.count() == 5
    assert all(s.request and s.anomalies[0]["type"] == evaluate.ANOMALY_TOO_LONG
               and not s.raw_output for s in rejected)
    assert all(r.outcome != "no_determinado" or evaluate.TOO_LONG_NOTE not in r.explanation
               for n, r in results.items() if n != number)


def test_a_contrast_the_engine_rejects_leaves_the_conclusion_uncorroborated(
        offer, operator_user, procedure, model, engine):
    """REQ-104 (T-261): un contraste que el motor rechaza por el contexto no corta la oferta: el
    «cumple» queda sin corroborar, con la anomalía registrada."""
    engine.reject = lambda messages, schema: "respuesta" in schema["properties"]
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "no_determinado" and result.doubt == "sin_corroborar"
    assert "el pedido no entra en el contexto" in result.explanation
    assert any(a["type"] == evaluate.ANOMALY_TOO_LONG for a in runs[0].anomalies)


# --- Control: con ofertas chicas el armado no cambia ----------------------------------------


def test_a_small_offer_is_read_as_before(offer, operator_user, procedure, model, engine,
                                         settings):
    """REQ-104 (T-261), control: una oferta chica entra entera en un grupo para cada requisito,
    sin reescritura ni partición; el tope de cada requisito es `ASSESSMENT_GROUP_TOKENS` (el
    contexto sobra) y los mensajes son los de `prompting.build_evaluation_messages`."""
    model.evaluates(cumple_declaration)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    firm = sheets_firm(procedure)
    assert len(model.calls) == len(firm)
    assert all(set(c.documents) == {"D1", "D2"} for c in model.calls)
    assert not model.rewrite_calls
    assert set(run.counts["group_budgets"].values()) == {settings.ASSESSMENT_GROUP_TOKENS}
    assert not [a for a in run.anomalies
                if a["type"] in (evaluate.ANOMALY_SPLIT, evaluate.ANOMALY_TOO_LONG,
                                 evaluate.ANOMALY_RETRY_TOO_LONG)]
    first = model.calls[0]
    system = prompting.load_prompt("evaluacion")
    assert first.messages[0] == {"role": "system", "content": system}
    assert len(first.messages) == 2 and first.messages[1]["content"].endswith(prompting.CLOSING)
