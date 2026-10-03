"""Consulta completa: recuperación de T-032 y T-033, generación de T-034 y registro
(T-040; plan 001, "Recuperación", "Reordenamiento", "Conteo de tokens", "Generación",
"Cita", "Abstención", "Forma de la respuesta" y "Registro de auditoría", fila
"Consulta").

`queries.services.ask` con los dobles de `tests/conftest.py`: el reranker puntúa por
marcas en el texto del pasaje y el de generación cuenta un token por palabra. Cada
prueba arma su propia normativa sintética (P4): un régimen específico con marca de
régimen general, y según el caso un dictamen legal o una norma del marco nacional.
"""

from datetime import date

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection

from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import generation as generation_client
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.queries import answering, retrieval, services
from evaluon.queries.models import Query
from tests.conftest import count_words

pytestmark = pytest.mark.django_db

QUESTION = "¿Qué garantía sintética corresponde en la contratación?"
DATE = date(2024, 5, 20)

# Marcas de texto que puntúa el doble del reranker.
ARTICLE = "[articulo-regimen]"
DICTAMEN = "[punto-dictamen]"
MARCO = "[articulo-marco]"
MODIFIER = "[modificatoria]"


# --- Normativa sintética -----------------------------------------------------------------


@pytest.fixture
def corpus(make_norm, make_document, make_reading):
    """`corpus(categoría, [(clave, texto), …], general_regime=False)`: una norma validada
    de esa categoría, vigente desde 2000, con esas unidades y un pasaje por unidad base.
    Devuelve `(norma, unidades por clave)`."""

    def _make(category, units, general_regime=False, passages=True):
        norm = make_norm(category=category, general_regime=general_regime)
        reading = make_reading(make_document(norm), units, passages=passages)
        return norm, reading.units_by_key

    return _make


@pytest.fixture
def regime(corpus):
    """Un régimen específico con marca de régimen general y su artículo 5."""
    norm, units = corpus("regimen_especifico", [
        ("art-5", f"ARTICULO 5.- {ARTICLE} La garantía sintética es del cinco por "
                  "ciento del valor total de la oferta."),
    ], general_regime=True)
    return norm, units["art-5"]


@pytest.fixture
def dictamen(corpus):
    norm, units = corpus("dictamen_legal", [
        ("punto-3", f"3. {DICTAMEN} La garantía sintética se interpreta sobre el valor "
                    "total adjudicado."),
    ])
    return norm, units["punto-3"]


@pytest.fixture
def marco(corpus):
    norm, units = corpus("marco_nacional", [
        ("art-78", f"ARTICULO 78.- {MARCO} La garantía sintética de mantenimiento de "
                   "oferta es del diez por ciento."),
    ])
    return norm, units["art-78"]


def ask(user, reference_date=DATE, question=QUESTION, **kwargs):
    return services.ask(user, question, reference_date, **kwargs)


def event_of(query):
    return AuditEvent.objects.get(pk=query.event_id)


def literal(unit):
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def base_tokens(question=QUESTION, reference_date=DATE):
    """Instrucciones y comienzo del mensaje, contados como el doble (palabras)."""
    return (count_words(answering.load_instructions())
            + count_words(answering.request_head(question, reference_date)))


def block_tokens(unit):
    return count_words(answering.unit_block("[U1]", unit))


# --- REQ-018 y REQ-019 de punta a punta ------------------------------------------------


def test_article_is_cited_before_the_dictamen_and_each_citation_has_its_category(
    read_user, regime, dictamen, fake_ai
):
    """REQ-018: con un artículo del régimen específico y un dictamen legal pertinentes,
    la respuesta cita primero el artículo y después el dictamen, aunque el modelo los
    devuelva al revés, y cada cita lleva la categoría de su documento."""
    _, article = regime
    _, point = dictamen
    fake_ai.reranker.scores = {ARTICLE: 0.9, DICTAMEN: 0.8}
    # El pedido muestra el artículo como U1 y el dictamen como U2; el modelo responde
    # primero con el dictamen y cita al revés.
    fake_ai.generation.answer([
        {"text": "El dictamen interpreta la garantía.", "citations": ["U2"],
         "regimes_differ": False},
        {"text": "La garantía es del cinco por ciento.", "citations": ["U2", "U1"],
         "regimes_differ": False},
    ])

    query = ask(read_user)

    result = query.result
    assert result["status"] == "grounded"
    assert [s["citations"] for s in result["statements"]] == [
        [article.pk, point.pk], [point.pk]]
    assert result["units"][str(article.pk)]["category"] == "regimen_especifico"
    assert result["units"][str(point.pk)]["category"] == "dictamen_legal"
    assert answering.citation_texts(result) == {article.pk: literal(article),
                                                point.pk: literal(point)}
    # El modelo recibió el artículo antes que el dictamen.
    [(messages, _)] = fake_ai.generation.calls
    content = messages[1]["content"]
    assert content.index(ARTICLE) < content.index(DICTAMEN)


def test_regime_and_national_framework_differ_shows_both_texts_and_the_flag(
    read_user, regime, marco, fake_ai
):
    """REQ-019: cuando el régimen específico y el marco nacional regulan el punto de
    manera distinta, la respuesta trae los dos textos y la marca `regimes_differ`, con
    la cita del régimen específico primero."""
    _, article = regime
    _, national = marco
    fake_ai.reranker.scores = {ARTICLE: 0.9, MARCO: 0.85}
    fake_ai.generation.answer([
        {"text": "El régimen fija cinco por ciento y el marco diez.",
         "citations": ["U2", "U1"], "regimes_differ": True},
    ])

    query = ask(read_user)

    result = query.result
    assert result["status"] == "grounded"
    [statement] = result["statements"]
    assert statement["regimes_differ"] is True
    assert statement["citations"] == [article.pk, national.pk]
    assert result["units"][str(article.pk)]["category"] == "regimen_especifico"
    assert result["units"][str(national.pk)]["category"] == "marco_nacional"
    assert answering.citation_texts(result) == {article.pk: literal(article),
                                                national.pk: literal(national)}
    assert not [a for a in query.anomalies if a["type"] == "regimes_flag_dropped"]


def test_regimes_flag_dropped_is_recorded_in_the_event(read_user, regime, marco,
                                                       fake_ai):
    """REQ-019, REQ-012: una marca `regimes_differ` sin una cita del régimen específico
    y otra del marco nacional se apaga, y la anomalía `regimes_flag_dropped` queda en la
    consulta y en su hecho."""
    _, article = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9, MARCO: 0.85}
    fake_ai.generation.answer([
        {"text": "Solo el régimen.", "citations": ["U1"], "regimes_differ": True},
    ])

    query = ask(read_user)

    assert query.result["statements"][0]["regimes_differ"] is False
    assert query.result["statements"][0]["citations"] == [article.pk]
    dropped = [a for a in event_of(query).detail["anomalies"]
               if a["type"] == "regimes_flag_dropped"]
    assert len(dropped) == 1
    assert dropped[0]["statement"] == 0
    assert event_of(query).detail["anomalies"] == query.anomalies


# --- Recuperación, selección y generación conectadas -------------------------------------


def test_selection_receives_the_tokens_of_instructions_and_question(
    read_user, regime, fake_ai, monkeypatch
):
    """REQ-008: la selección recibe los tokens de las instrucciones con el comienzo del
    mensaje (fecha y pregunta), contados con `generation.count_tokens`, y la generación
    recibe la fecha de autorización y los tramos de la selección."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    seen = {}
    original_select = retrieval.select_units
    original_answer = answering.answer

    def select_spy(result, prompt_tokens):
        seen["prompt_tokens"] = prompt_tokens
        seen["selection"] = original_select(result, prompt_tokens)
        return seen["selection"]

    def answer_spy(question, unit_ids, reference_date=None, passages=None):
        seen["answer"] = (question, list(unit_ids), reference_date, passages)
        return original_answer(question, unit_ids, reference_date, passages=passages)

    monkeypatch.setattr(retrieval, "select_units", select_spy)
    monkeypatch.setattr(answering, "answer", answer_spy)

    query = ask(read_user)

    assert seen["prompt_tokens"] == base_tokens()
    assert seen["answer"] == (QUESTION, seen["selection"].unit_ids, DATE,
                              seen["selection"].passages)
    assert query.prompt_version == answering.PROMPT_VERSION_WITH_DATE == "consulta-v2"
    assert query.status == "grounded"


def test_path_counts_and_selection_are_in_the_record(read_user, regime, dictamen,
                                                     fake_ai, monkeypatch):
    """REQ-012: el registro guarda `path_counts` de la recuperación y la selección
    completa (`Selection.as_record()`), en la consulta y en su hecho."""
    fake_ai.reranker.scores = {ARTICLE: 0.9, DICTAMEN: 0.8}
    seen = {}
    original_retrieve = retrieval.retrieve
    original_select = retrieval.select_units

    def retrieve_spy(question, reference_date):
        seen["found"] = original_retrieve(question, reference_date)
        return seen["found"]

    def select_spy(result, prompt_tokens):
        seen["selection"] = original_select(result, prompt_tokens)
        return seen["selection"]

    monkeypatch.setattr(retrieval, "retrieve", retrieve_spy)
    monkeypatch.setattr(retrieval, "select_units", select_spy)

    query = ask(read_user)

    found = seen["found"]
    assert found.path_counts
    assert query.selected["retrieval"]["path_counts"] == found.path_counts
    assert query.selected["selection"] == seen["selection"].as_record()
    assert event_of(query).detail["selected"] == query.selected


def test_unit_added_by_relation_is_recorded(read_user, regime, corpus, make_relation,
                                            fake_ai):
    """REQ-012: la unidad que modifica a una seleccionada entra por relación, no por
    puntaje, y queda en el registro como agregada por relación, con la unidad que
    modifica; la respuesta la trae en `units`."""
    regime_norm, article = regime
    modifier_norm, modifier_units = corpus("regimen_especifico", [
        ("art-1", f"ARTICULO 1.- {MODIFIER} Sustitúyese el texto sintético."),
    ])
    modifier = modifier_units["art-1"]
    make_relation(modifier_norm, regime_norm, "modifica", source_unit_key="art-1",
                  target_unit_key="art-5", effective_date=date(2020, 1, 1))
    fake_ai.reranker.scores = {ARTICLE: 0.9, MODIFIER: 0.1}

    query = ask(read_user)

    assert [u["unit"] for u in query.selected["sent"]] == [article.pk]
    assert query.selected["added"] == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert str(modifier.pk) in query.result["units"]


def test_candidates_carry_path_score_and_text_origin(read_user, regime, fake_ai):
    """REQ-012: cada candidato queda con su camino de entrada, su puntaje y el origen de
    su texto."""
    _, article = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}

    query = ask(read_user)

    [candidate] = [c for c in query.candidates if c["unit"] == article.pk]
    assert candidate["path"]
    assert set(candidate["path"]) <= set(retrieval.ALL_PATHS)
    assert candidate["score"] == 0.9
    assert candidate["text_origin"] == article.text_origin == "pdf_text"


# --- Registro completo (REQ-012, fila "Consulta") ----------------------------------------


def test_record_has_everything_of_the_query_row(read_user, regime, fake_ai,
                                               settings):
    """REQ-012: el registro de una consulta respondida permite ver todo lo de la fila
    "Consulta" de "Registro de auditoría": pregunta, fecha de autorización, régimen
    aplicado, avisos, modelos con nombre y huella, compilación del motor, contexto,
    temperatura, semilla, pensamiento y máximo de salida, versión de las instrucciones y
    pedido completo, parámetros de búsqueda, candidatos, unidades enviadas, agregadas y
    dejadas afuera, puntaje más alto, decisión de abstención y motivo, salida sin tocar,
    anomalías, respuesta final y tiempos por etapa."""
    regime_norm, article = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}

    query = ask(read_user)

    event = event_of(query)
    detail = event.detail
    assert detail["question"] == query.question == QUESTION
    assert detail["reference_date"] == DATE.isoformat()
    assert query.reference_date == DATE
    assert detail["regime"] == [{"norm": regime_norm.pk, "name": regime_norm.citation}]
    assert detail["notices"] == query.result["notices"] == []

    parameters = query.parameters
    generation = parameters["generation"]
    assert generation["model"] == settings.GENERATION_MODEL
    assert generation["sha256"] == settings.GENERATION_MODEL_SHA256
    assert generation["engine_build"] == settings.GENERATION_ENGINE_BUILD
    assert generation["context_tokens"] == settings.GENERATION_CONTEXT_TOKENS
    assert generation["temperature"] == settings.GENERATION_TEMPERATURE
    assert generation["seed"] == settings.GENERATION_SEED
    assert generation["thinking"] == settings.GENERATION_THINKING
    assert generation["max_output_tokens"] == settings.GENERATION_MAX_OUTPUT_TOKENS
    for name, prefix in (("embeddings", "EMBEDDINGS"), ("reranker", "RERANKER")):
        assert parameters[name]["model"] == getattr(settings, f"{prefix}_MODEL")
        assert parameters[name]["sha256"] == getattr(settings, f"{prefix}_MODEL_SHA256")
    # Los de búsqueda van en el primer nivel; `reranker` es el modelo y `rerank`, si el
    # reranker estuvo encendido.
    search = parameters
    assert search["candidates_per_path"] == settings.RETRIEVAL_CANDIDATES_PER_PATH
    assert search["rerank_threshold"] == settings.RERANK_THRESHOLD
    assert search["paths"] == list(retrieval.ALL_PATHS)
    assert search["rerank"] is True
    assert search["units_per_category"] == settings.SELECTION_UNITS_PER_CATEGORY
    assert search["considerandos"] == settings.SELECTION_CONSIDERANDOS
    assert search["template_margin_tokens"] == settings.PROMPT_TEMPLATE_MARGIN_TOKENS
    assert search["unit_by_passages_from_tokens"] == \
        settings.UNIT_BY_PASSAGES_FROM_TOKENS

    assert query.prompt_version == "consulta-v2"
    assert query.request["messages"][0]["content"] == answering.load_instructions()
    assert QUESTION in query.request["messages"][1]["content"]
    assert query.raw_output.startswith('{"status": "grounded"')
    assert article.pk in [c["unit"] for c in query.candidates]
    assert [u["unit"] for u in query.selected["sent"]] == [article.pk]
    assert query.selected["added"] == []
    assert query.selected["left_out"] == []
    assert query.max_score == 0.9
    assert query.selected["abstention"] == {"abstained": False, "reason": None}
    assert query.anomalies == []
    assert {"regimes", "retrieval", "selection", "generation", "total"} <= \
        set(query.timings)

    # El hecho lleva lo mismo que la fila.
    for column in ("parameters", "candidates", "selected", "max_score",
                   "prompt_version", "request", "raw_output", "anomalies", "timings"):
        assert detail[column] == getattr(query, column), column
    assert detail["result"] == query.result
    assert detail["status"] == query.status == "grounded"
    assert detail["reason"] is None


def test_abstention_decision_is_recorded_with_its_reason(read_user, regime, fake_ai):
    """REQ-009, REQ-012: un "no determinado" deja registrada la decisión de abstención
    con su motivo."""
    fake_ai.reranker.scores = {ARTICLE: 0.2}

    query = ask(read_user)

    assert (query.status, query.reason) == ("undetermined", "below_threshold")
    assert query.selected["abstention"] == {"abstained": True,
                                            "reason": "below_threshold"}
    assert event_of(query).detail["selected"]["abstention"] == \
        query.selected["abstention"]


# --- Versión de la normativa de la instantánea -----------------------------------------


def _new_corpus_version(user):
    return audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND, user=user,
        creates_corpus_version=True,
    ).corpus_version


def test_corpus_version_is_the_one_of_the_search_even_if_a_norm_is_validated_meanwhile(
    read_user, read_write_user, regime, fake_ai, monkeypatch
):
    """REQ-012 (P6, P8; decisión del responsable del 2026-10-03): la consulta y su hecho
    registran la versión de la normativa con que se hizo la búsqueda, aunque se valide
    otra norma mientras el modelo genera."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    searched_with = _new_corpus_version(read_write_user)
    delegate = fake_ai.generation.generate
    created = []

    def generate_while_validating(messages, schema):
        created.append(_new_corpus_version(read_write_user))
        return delegate(messages, schema)

    monkeypatch.setattr(generation_client, "generate", generate_while_validating)

    query = ask(read_user)

    assert created and created[0] > searched_with
    assert audit_services.current_corpus_version() == created[0]
    assert query.corpus_version == searched_with
    assert event_of(query).corpus_version == searched_with


@pytest.mark.django_db(transaction=True)
def test_regime_and_retrieval_share_a_snapshot_that_excludes_generation(
    read_user, regime, fake_ai, monkeypatch
):
    """REQ-012 (P6, P8): el régimen y la recuperación se leen dentro de una transacción
    `REPEATABLE READ`; la generación corre fuera de ella."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    seen = {}
    original_retrieve = retrieval.retrieve
    delegate = fake_ai.generation.generate

    def retrieve_spy(question, reference_date):
        with connection.cursor() as cursor:
            cursor.execute("SHOW transaction_isolation")
            seen["isolation"] = cursor.fetchone()[0]
        seen["retrieval_in_transaction"] = connection.in_atomic_block
        return original_retrieve(question, reference_date)

    def generate_spy(messages, schema):
        seen["generation_in_transaction"] = connection.in_atomic_block
        return delegate(messages, schema)

    monkeypatch.setattr(retrieval, "retrieve", retrieve_spy)
    monkeypatch.setattr(generation_client, "generate", generate_spy)

    query = ask(read_user)

    assert query.status == "grounded"
    assert seen == {"isolation": "repeatable read", "retrieval_in_transaction": True,
                    "generation_in_transaction": False}


# --- Rechazo por rol ------------------------------------------------------------------


@pytest.mark.parametrize("who", ["anonimo", "de-baja"])
def test_role_rejection_keeps_the_eval_channel_and_is_not_rolled_back(
    read_user, regime, fake_ai, who
):
    """REQ-016, REQ-012: un rechazo por rol en una consulta de las evals queda
    registrado con el canal `eval` y la operación `ask`, fuera de la transacción de la
    consulta (no se pierde), y no se consulta."""
    if who == "anonimo":
        user = AnonymousUser()
    else:
        user = read_user
        user.is_active = False
        user.save()

    with pytest.raises(RoleRejected):
        ask(user, channel=Channel.EVAL)

    [event] = AuditEvent.objects.filter(event_type=EventType.REJECTED)
    assert event.channel == Channel.EVAL
    assert event.detail["operation"] == "evaluon.queries.services.ask"
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == []


# --- Sin unidades que entren: falla técnica input_too_long ------------------------------


def assert_input_too_long(query, fake_ai):
    assert (query.status, query.reason) == ("error", "input_too_long")
    assert query.result["status"] == "error"
    assert query.result["reason"] == "input_too_long"
    assert query.result["statements"] == []
    assert event_of(query).outcome == Outcome.FAILED
    assert event_of(query).detail["reason"] == "input_too_long"
    assert fake_ai.generation.calls == []
    assert query.selected["abstention"] == {"abstained": False, "reason": None}


def test_prompt_exceeding_the_context_is_input_too_long(read_user, regime, fake_ai,
                                                        settings):
    """REQ-009, REQ-012 (decisión 2 del Coordinador): si las instrucciones con la
    pregunta no dejan espacio (`prompt_exceeds_context`), la consulta termina en falla
    técnica `input_too_long`, sin llamar al modelo, y la anomalía queda registrada."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    settings.GENERATION_CONTEXT_TOKENS = 1000

    query = ask(read_user)

    assert_input_too_long(query, fake_ai)
    assert [a["type"] for a in query.anomalies] == ["prompt_exceeds_context"]
    assert query.selected["selection"]["anomalies"][0]["type"] == \
        "prompt_exceeds_context"


def test_no_unit_fitting_the_space_is_input_too_long(read_user, regime, fake_ai,
                                                     settings):
    """REQ-009, REQ-012 (decisión 2 del Coordinador): si ninguna unidad entra en el
    espacio (`unit_ids` vacío), la consulta termina en falla técnica `input_too_long`,
    no en "no determinado", y la unidad queda registrada como fuera por espacio."""
    _, article = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    settings.GENERATION_CONTEXT_TOKENS = (
        base_tokens() + settings.GENERATION_MAX_OUTPUT_TOKENS
        + settings.PROMPT_TEMPLATE_MARGIN_TOKENS + 3)

    query = ask(read_user)

    assert_input_too_long(query, fake_ai)
    assert [entry["unit"] for entry in query.selected["left_out"]] == [article.pk]
    assert query.selected["sent"] == []


def test_final_check_drops_units_from_the_end_of_the_priority(
    read_user, regime, marco, fake_ai, settings, monkeypatch
):
    """REQ-012, REQ-019 (decisión 3 del Coordinador): antes de llamar al modelo se
    cuenta el pedido completo; si no entra en el contexto, se sacan unidades desde el
    final de la prioridad y quedan registradas como fuera por espacio."""
    _, article = regime
    _, national = marco
    fake_ai.reranker.scores = {ARTICLE: 0.9, MARCO: 0.95}
    # Solo entra el artículo del régimen en el pedido completo.
    settings.GENERATION_CONTEXT_TOKENS = (
        base_tokens() + block_tokens(article) + settings.GENERATION_MAX_OUTPUT_TOKENS
        + settings.PROMPT_TEMPLATE_MARGIN_TOKENS)
    original_select = retrieval.select_units

    def generous_select(result, prompt_tokens):
        # Una selección que no descuenta las instrucciones: deja pasar las dos.
        return original_select(result, 0)

    monkeypatch.setattr(retrieval, "select_units", generous_select)

    query = ask(read_user)

    assert query.status == "grounded"
    assert [u["unit"] for u in query.selected["sent"]] == [article.pk]
    assert query.selected["selection"]["units"] == [article.pk, national.pk]
    [dropped] = [entry for entry in query.selected["left_out"]
                 if entry["unit"] == national.pk]
    assert dropped["check"] == "request"
    check = query.selected["request_check"]
    assert check["removed"] == [national.pk]
    assert check["tokens"] <= check["limit"]
    [(messages, _)] = fake_ai.generation.calls
    assert MARCO not in messages[1]["content"]
    assert ARTICLE in messages[1]["content"]


def test_final_check_without_any_unit_left_is_input_too_long(
    read_user, regime, fake_ai, settings, monkeypatch
):
    """REQ-009 (decisiones 2 y 3 del Coordinador): si el control del pedido completo
    saca todas las unidades, la consulta termina en falla técnica `input_too_long`."""
    _, article = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    settings.GENERATION_CONTEXT_TOKENS = (
        base_tokens() + settings.GENERATION_MAX_OUTPUT_TOKENS
        + settings.PROMPT_TEMPLATE_MARGIN_TOKENS + 3)
    original_select = retrieval.select_units
    monkeypatch.setattr(retrieval, "select_units",
                        lambda result, prompt_tokens: original_select(result, 0))

    query = ask(read_user)

    assert_input_too_long(query, fake_ai)
    assert query.selected["request_check"]["removed"] == [article.pk]
    assert query.selected["sent"] == []


# --- Unión vacía ------------------------------------------------------------------------


def test_no_candidates_is_recorded_apart_from_below_threshold(read_user, corpus,
                                                              fake_ai):
    """REQ-009, REQ-012 (decisión 4 del Coordinador): si la recuperación no trae ningún
    candidato, quien consulta ve "no determinado" como con `below_threshold`, pero la
    decisión de abstención queda registrada con el motivo propio `no_candidates`, sin
    llamar al reranker ni al modelo."""
    corpus("regimen_especifico", [("art-1", "ARTICULO 1.- Texto sintético.")],
           general_regime=True, passages=False)

    query = ask(read_user)

    assert query.status == "undetermined"
    assert query.result["status"] == "undetermined"
    assert query.result["statements"] == []
    # La columna `reason` solo admite los cuatro motivos del plan (restricción
    # `queries_query_reason_matches_status`): el motivo propio va en la decisión.
    assert query.reason == query.result["reason"] == "below_threshold"
    assert query.candidates == []
    assert query.selected["abstention"] == {"abstained": True,
                                            "reason": "no_candidates"}
    assert event_of(query).detail["selected"]["abstention"]["reason"] == \
        "no_candidates"
    assert fake_ai.reranker.calls == []
    assert fake_ai.generation.calls == []


# --- Armado público del pedido -----------------------------------------------------------


def test_build_request_is_what_answer_sends_without_calling_the_model(
    read_user, regime, marco, fake_ai
):
    """REQ-008, REQ-012: `answering.build_request` arma los mensajes y el esquema del
    pedido sin llamar al modelo, y son exactamente los que `answer` envía al motor."""
    _, article = regime
    _, national = marco

    built = answering.build_request(QUESTION, [national.pk, article.pk], DATE)

    assert fake_ai.generation.calls == []
    assert built.prompt_version == "consulta-v2"
    assert built.aliases == {"U1": article.pk, "U2": national.pk}
    assert built.shown == {article.pk, national.pk}
    answering.answer(QUESTION, [national.pk, article.pk], DATE)
    [(messages, schema)] = fake_ai.generation.calls
    assert built.messages == messages
    assert built.schema == schema


def test_final_check_counts_the_public_request(read_user, regime, fake_ai, monkeypatch):
    """REQ-012: el control final del pedido cuenta lo que arma
    `answering.build_request`, el mismo camino que usa `answer`."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    calls = []
    original = answering.build_request

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(answering, "build_request", spy)

    query = ask(read_user)

    assert query.status == "grounded"
    # Una vez en el control final y otra dentro de `answer`.
    assert len(calls) == 2
    assert query.selected["request_check"]["tokens"] == sum(
        count_words(m["content"]) for m in query.request["messages"])


def test_priority_order_is_public(regime, marco, dictamen):
    """REQ-018, REQ-019: la prioridad del espacio es pública en `retrieval`: la mejor
    de cada categoría en el orden de las categorías."""
    _, article = regime
    _, national = marco
    _, point = dictamen

    order = retrieval.priority_order([point, national, article])

    assert [unit.pk for unit in order] == [article.pk, national.pk, point.pk]


def test_final_check_drops_a_unit_shown_by_passages(
    read_user, regime, make_norm, make_document, make_reading, make_passage, fake_ai,
    settings, monkeypatch
):
    """REQ-012 (decisión 3 del Coordinador): si el control final saca una unidad larga
    que se mostraba por pasajes, sus tramos dejan de pedirse y la consulta sigue con lo
    que entra."""
    _, article = regime
    head = f"ARTICULO 78.- {MARCO} La garantía sintética es del diez por ciento."
    tail = " ".join(["relleno"] * (settings.UNIT_BY_PASSAGES_FROM_TOKENS + 100))
    text = f"{head}\n{tail}"
    reading = make_reading(make_document(make_norm(category="marco_nacional")),
                           [("art-78", text)], passages=False)
    long_unit = reading.units_by_key["art-78"]
    make_passage(long_unit, char_start=0, char_end=len(head), text=head)
    make_passage(long_unit, char_start=len(head) + 1, char_end=len(text), text=tail)
    fake_ai.reranker.scores = {ARTICLE: 0.9, MARCO: 0.95}
    settings.GENERATION_CONTEXT_TOKENS = (
        base_tokens() + block_tokens(article) + settings.GENERATION_MAX_OUTPUT_TOKENS
        + settings.PROMPT_TEMPLATE_MARGIN_TOKENS)
    original_select = retrieval.select_units
    monkeypatch.setattr(retrieval, "select_units",
                        lambda result, prompt_tokens: original_select(result, 0))

    query = ask(read_user)

    assert query.selected["selection"]["passages"] == {
        str(long_unit.pk): [[0, len(head)]]}
    assert query.selected["request_check"]["removed"] == [long_unit.pk]
    assert query.status == "grounded"
    assert [u["unit"] for u in query.selected["sent"]] == [article.pk]
