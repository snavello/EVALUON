"""Consulta de punta a punta con su registro (T-019; plan 001, "Fecha de autorización y
régimen aplicado", "Abstención", "Forma de la respuesta" y "Registro de auditoría").

La función de consulta de `queries/services.py` con los dobles de los tres clientes de
IA y los dos regímenes de prueba de `two_regimes` (T-009). Los datos son sintéticos (P4).
"""

from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import ServiceUnavailableError
from evaluon.ai import generation as generation_client
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.queries import answering, services
from evaluon.queries.models import Query

pytestmark = pytest.mark.django_db

QUESTION = "¿Cuál es el objeto del régimen de contrataciones?"

# Marcas del texto de cada artículo 1 de anexo, para el doble del reranker.
OLD_MARK = "Objeto del régimen sintético anterior"
NEW_MARK = "OBJETO. Régimen sintético vigente"


@pytest.fixture
def relevant(fake_ai):
    """Los dobles con el artículo 1 del anexo de cada régimen como único pertinente."""
    fake_ai.reranker.scores = {OLD_MARK: 0.9, NEW_MARK: 0.9}
    return fake_ai


def ask(user, reference_date, question=QUESTION, **kwargs):
    return services.ask(user, question, reference_date, **kwargs)


def query_event(query):
    return AuditEvent.objects.get(pk=query.event_id)


def literal(unit):
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


# --- Respuesta con fundamento y régimen aplicado ---------------------------------------


def test_answer_cites_the_article_with_its_literal_text(read_user, two_regimes, relevant):
    """REQ-008: la respuesta cita el artículo que la sostiene por su `id`, y el texto
    citado es igual a `canonical_text[char_start:char_end]` de su lectura."""
    article = two_regimes.new_units["anexo/art-1"]

    query = ask(read_user, two_regimes.after_v)

    result = query.result
    assert query.status == "grounded"
    assert result["status"] == "grounded"
    assert result["reason"] is None
    assert len(result["statements"]) == 1
    assert result["statements"][0]["citations"] == [article.pk]
    assert set(result["units"]) == {str(article.pk)}
    assert result["units"][str(article.pk)]["norm"] == two_regimes.new.citation
    assert answering.citation_texts(result) == {article.pk: literal(article)}


def test_result_has_the_shape_of_the_plan(read_user, two_regimes, relevant):
    """REQ-008, REQ-020: el resultado guardado lleva `query_id`, `reference_date`,
    `regime` y `notices` (vacío) además de lo que arma la generación."""
    query = ask(read_user, two_regimes.after_v)

    result = query.result
    assert list(result) == ["query_id", "status", "reason", "reference_date", "regime",
                            "notices", "statements", "units"]
    assert result["query_id"] == query.pk
    assert result["reference_date"] == two_regimes.after_v.isoformat()
    assert result["regime"] == [
        {"norm": two_regimes.new.pk, "name": two_regimes.new.citation}
    ]
    assert result["notices"] == []


def test_same_question_cites_each_regime_according_to_the_date(
    read_user, two_regimes, relevant
):
    """REQ-020: la misma pregunta con una fecha anterior a V cita el primer régimen y con
    una posterior cita el segundo; cada resultado indica su régimen y su fecha."""
    old_article = two_regimes.old_units["anexo-i/art-1"]
    new_article = two_regimes.new_units["anexo/art-1"]

    before = ask(read_user, two_regimes.before_v).result
    after = ask(read_user, two_regimes.after_v).result

    assert before["status"] == after["status"] == "grounded"
    assert before["statements"][0]["citations"] == [old_article.pk]
    assert before["units"][str(old_article.pk)]["norm"] == two_regimes.old.citation
    assert before["reference_date"] == two_regimes.before_v.isoformat()
    assert before["regime"] == [
        {"norm": two_regimes.old.pk, "name": two_regimes.old.citation}
    ]
    assert after["statements"][0]["citations"] == [new_article.pk]
    assert after["units"][str(new_article.pk)]["norm"] == two_regimes.new.citation
    assert after["reference_date"] == two_regimes.after_v.isoformat()
    assert after["regime"] == [
        {"norm": two_regimes.new.pk, "name": two_regimes.new.citation}
    ]


def test_retrieval_receives_the_authorization_date(read_user, two_regimes, relevant,
                                                   monkeypatch):
    """REQ-020: la recuperación recibe la fecha de autorización de la consulta, no la del
    día."""
    from evaluon.queries import retrieval

    received = []
    original = retrieval.retrieve

    def spy(question, reference_date):
        received.append(reference_date)
        return original(question, reference_date)

    monkeypatch.setattr(retrieval, "retrieve", spy)

    ask(read_user, two_regimes.before_v)

    assert received == [two_regimes.before_v]


# --- Los cuatro motivos de "no determinado" ----------------------------------------------


def assert_undetermined(query, reason, regime):
    result = query.result
    assert query.status == "undetermined"
    assert query.reason == reason
    assert result["status"] == "undetermined"
    assert result["reason"] == reason
    assert result["statements"] == []
    assert result["units"] == {}
    assert result["notices"] == []
    assert result["regime"] == regime
    assert result["query_id"] == query.pk


def test_no_regime_at_date_does_not_search_nor_call_the_model(
    read_user, two_regimes, fake_ai
):
    """REQ-009, REQ-020: sin régimen a la fecha, "no determinado" con
    `no_regime_at_date`, sin buscar ni llamar al modelo."""
    fake_ai.reranker.default = 0.9

    query = ask(read_user, two_regimes.before_all)

    assert_undetermined(query, "no_regime_at_date", [])
    assert query.result["reference_date"] == two_regimes.before_all.isoformat()
    assert fake_ai.embeddings.calls == []
    assert fake_ai.reranker.calls == []
    assert fake_ai.generation.calls == []
    assert query.candidates == []
    assert query.max_score is None
    assert query.request is None


def test_below_threshold_does_not_call_the_model(read_user, two_regimes, fake_ai):
    """REQ-009: si ninguna unidad alcanza el umbral, "no determinado" con
    `below_threshold`, sin llamar al modelo; los candidatos quedan en el registro."""
    query = ask(read_user, two_regimes.after_v)

    assert_undetermined(query, "below_threshold",
                        [{"norm": two_regimes.new.pk, "name": two_regimes.new.citation}])
    assert fake_ai.reranker.calls
    assert fake_ai.generation.calls == []
    assert query.candidates
    assert query.max_score == 0.0
    assert query.request is None
    assert query.prompt_version == ""


def test_model_abstained_is_undetermined(read_user, two_regimes, relevant):
    """REQ-009: el modelo recibe unidades y se abstiene: "no determinado" con
    `model_abstained`."""
    relevant.generation.abstain()

    query = ask(read_user, two_regimes.after_v)

    assert_undetermined(query, "model_abstained",
                        [{"norm": two_regimes.new.pk, "name": two_regimes.new.citation}])
    assert len(relevant.generation.calls) == 1


def test_invalid_citation_is_undetermined(read_user, two_regimes, relevant):
    """REQ-009: una afirmación que cita un alias no mostrado da "no determinado" con
    `invalid_citation`, sin afirmaciones; la falla queda en las anomalías."""
    relevant.generation.answer([{"text": "Afirmación sintética.", "citations": ["U9"]}])

    query = ask(read_user, two_regimes.after_v)

    assert_undetermined(query, "invalid_citation",
                        [{"norm": two_regimes.new.pk, "name": two_regimes.new.citation}])
    assert query.anomalies
    assert query.anomalies[0]["type"] == "invalid_citation"


# --- Fallas técnicas -----------------------------------------------------------------------


@pytest.mark.parametrize("client_name, mode, reason", [
    ("embeddings", "unavailable", "service_unavailable"),
    ("embeddings", "timeout", "timeout"),
    ("reranker", "timeout", "timeout"),
    ("reranker", "input_too_long", "input_too_long"),
    ("generation", "unavailable", "service_unavailable"),
    ("generation", "timeout", "timeout"),
    ("generation", "input_too_long", "input_too_long"),
    ("generation", "invalid_output", "invalid_output"),
])
def test_technical_failures_are_errors_never_undetermined(
    read_user, two_regimes, relevant, client_name, mode, reason
):
    """REQ-009: un servicio que no responde, una espera agotada, una salida inválida o
    un pedido que el motor rechaza por no entrar en el contexto dan `error` con su
    motivo, nunca "no determinado". La recuperación lanza sus fallas y la generación las
    devuelve: las dos terminan igual."""
    getattr(getattr(relevant, client_name), mode)()

    query = ask(read_user, two_regimes.after_v)

    assert query.status == "error"
    assert query.reason == reason
    result = query.result
    assert result["status"] == "error"
    assert result["reason"] == reason
    assert result["statements"] == []
    assert result["units"] == {}
    assert result["notices"] == []
    assert result["reference_date"] == two_regimes.after_v.isoformat()
    assert result["regime"] == [
        {"norm": two_regimes.new.pk, "name": two_regimes.new.citation}
    ]
    assert query_event(query).outcome == Outcome.FAILED


def test_input_too_long_from_the_engine_is_recorded_with_its_request(
    read_user, two_regimes, relevant
):
    """REQ-009, REQ-012: un rechazo del motor por entrada demasiado larga da `error` con
    `input_too_long`, y el pedido que se intentó queda en el registro."""
    relevant.generation.input_too_long()

    query = ask(read_user, two_regimes.after_v)

    assert (query.status, query.reason) == ("error", "input_too_long")
    assert query.request["messages"]
    assert query.raw_output == ""
    [error] = [a for a in query.anomalies if a["type"] == "service_error"]
    assert error["service"] == "generation"
    assert error["reason"] == "input_too_long"


def test_unknown_http_error_keeps_status_and_detail(
    read_user, two_regimes, relevant, monkeypatch
):
    """REQ-012: un error HTTP desconocido del motor llega como `service_unavailable` con
    `status` y `detail`, y los dos quedan en la consulta y en su hecho, para distinguir
    un servicio caído de un pedido mal armado."""
    detail = {"error": {"type": "invalid_request_error", "message": "pedido sintético"}}

    def fail(messages, schema):
        raise ServiceUnavailableError("generation: HTTP 400", service="generation",
                                      status=400, detail=detail)

    monkeypatch.setattr(generation_client, "generate", fail)

    query = ask(read_user, two_regimes.after_v)

    assert (query.status, query.reason) == ("error", "service_unavailable")
    [error] = [a for a in query.anomalies if a["type"] == "service_error"]
    assert error["status"] == 400
    assert error["detail"] == detail
    assert error["service"] == "generation"
    assert query_event(query).detail["anomalies"] == query.anomalies


def test_retrieval_failure_keeps_status_and_detail(
    read_user, two_regimes, fake_ai, monkeypatch
):
    """REQ-012: una falla de un cliente de la recuperación también deja su servicio,
    `status` y `detail` en la consulta."""
    from evaluon.ai import embeddings as embeddings_client

    def fail(texts):
        raise ServiceUnavailableError("embeddings: HTTP 502", service="embeddings",
                                      status=502, detail="Bad Gateway")

    monkeypatch.setattr(embeddings_client, "embed", fail)

    query = ask(read_user, two_regimes.after_v)

    assert (query.status, query.reason) == ("error", "service_unavailable")
    [error] = [a for a in query.anomalies if a["type"] == "service_error"]
    assert (error["service"], error["status"], error["detail"]) == (
        "embeddings", 502, "Bad Gateway")
    assert fake_ai.generation.calls == []


# --- Registro de la consulta -------------------------------------------------------------


def test_record_shows_everything_needed_to_rebuild_the_query(
    read_user, two_regimes, relevant
):
    """REQ-012: el registro de una consulta respondida muestra la pregunta, la fecha de
    autorización, el régimen aplicado, las unidades recuperadas, la respuesta, la versión
    de la normativa, el usuario y la fecha, en `queries_query` y en su hecho `query`."""
    version_event = audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND,
        user=read_user, creates_corpus_version=True,
    )

    query = ask(read_user, two_regimes.after_v)

    event = query_event(query)
    article = two_regimes.new_units["anexo/art-1"]
    # La consulta.
    assert query.question == QUESTION
    assert query.reference_date == two_regimes.after_v
    assert query.result["regime"][0]["name"] == two_regimes.new.citation
    assert query.corpus_version == version_event.corpus_version
    assert query.user == read_user
    assert query.asked_at is not None
    assert article.pk in [c["unit"] for c in query.candidates]
    assert all({"passage", "unit", "path", "score"} <= set(c) for c in query.candidates)
    assert [u["unit"] for u in query.selected["sent"]] == [article.pk]
    assert query.max_score == 0.9
    assert query.prompt_version == answering.PROMPT_VERSION
    assert query.request["messages"]
    assert query.raw_output
    assert query.parameters["rerank_threshold"] == 0.5
    assert query.parameters["generation"]["model"]
    assert {"regimes", "retrieval", "generation", "total"} <= set(query.timings)
    # Su hecho: el mismo usuario y la misma versión, y el detalle completo.
    assert event.event_type == EventType.QUERY
    assert event.outcome == Outcome.OK
    assert event.channel == Channel.SCREEN
    assert event.user == query.user
    assert event.corpus_version == query.corpus_version
    detail = event.detail
    assert detail["query_id"] == query.pk
    assert detail["question"] == QUESTION
    assert detail["reference_date"] == two_regimes.after_v.isoformat()
    assert detail["regime"] == query.result["regime"]
    assert detail["result"] == query.result
    assert detail["candidates"] == query.candidates
    assert detail["selected"] == query.selected
    assert detail["max_score"] == query.max_score
    assert detail["prompt_version"] == query.prompt_version
    assert detail["request"] == query.request
    assert detail["raw_output"] == query.raw_output
    assert detail["parameters"] == query.parameters
    assert detail["anomalies"] == query.anomalies
    assert detail["timings"] == query.timings
    assert detail["status"] == "grounded"
    assert detail["reason"] is None


def test_user_and_corpus_version_match_the_event_without_versions(
    read_write_user, two_regimes, relevant
):
    """REQ-012: usuario y versión de la normativa de la consulta son los de su hecho,
    también cuando todavía no hay ninguna versión."""
    query = ask(read_write_user, two_regimes.after_v)

    event = query_event(query)
    assert query.user == event.user == read_write_user
    assert query.corpus_version == event.corpus_version


def test_query_and_event_are_inserted_once(read_user, two_regimes, relevant):
    """REQ-012: cada consulta deja una sola fila en `queries_query` y un solo hecho
    `query`, y el `query_id` del resultado es el de la fila."""
    events_before = AuditEvent.objects.filter(event_type=EventType.QUERY).count()

    query = ask(read_user, two_regimes.after_v)

    assert Query.objects.count() == 1
    assert AuditEvent.objects.filter(event_type=EventType.QUERY).count() == \
        events_before + 1
    assert Query.objects.get().result["query_id"] == query.pk


def test_asked_at_is_the_moment_of_the_question(read_user, two_regimes, relevant,
                                                monkeypatch):
    """REQ-012: `asked_at` es el momento en que se hizo la pregunta, que la función
    pasa al guardar, y no el de la inserción."""
    instant = datetime(2026, 1, 2, 15, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)

    query = ask(read_user, two_regimes.after_v)

    assert Query.objects.get(pk=query.pk).asked_at == instant
    assert query_event(query).occurred_at != instant


def test_channel_is_recorded(read_user, two_regimes, relevant):
    """REQ-012: el hecho registra el canal por el que llegó la consulta."""
    query = ask(read_user, two_regimes.after_v, channel=Channel.EVAL)

    assert query_event(query).channel == Channel.EVAL


def test_no_regime_query_is_recorded_too(read_user, two_regimes, fake_ai):
    """REQ-012: una consulta sin régimen a la fecha también queda registrada, con su
    fecha y el régimen vacío."""
    query = ask(read_user, two_regimes.before_all)

    event = query_event(query)
    assert event.detail["reference_date"] == two_regimes.before_all.isoformat()
    assert event.detail["regime"] == []
    assert event.detail["result"] == query.result


# --- Fecha de autorización y rol -----------------------------------------------------------


def test_empty_date_uses_today_in_buenos_aires(read_user, two_regimes, relevant,
                                               monkeypatch):
    """REQ-020: con la fecha vacía se usa la del día, en hora de Buenos Aires."""
    # 02:30 en hora universal del 4 de octubre son las 23:30 del 3 en Buenos Aires.
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)

    query = ask(read_user, None)

    assert query.reference_date.isoformat() == "2026-10-03"
    assert query.result["reference_date"] == "2026-10-03"
    assert query.result["regime"][0]["name"] == two_regimes.new.citation


def test_future_date_is_rejected_without_query_or_record(
    read_user, two_regimes, fake_ai, monkeypatch
):
    """REQ-020: una fecha posterior al día se rechaza sin consultar y sin dejar registro
    de consulta."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    events_before = AuditEvent.objects.count()

    with pytest.raises(services.FutureDate):
        ask(read_user, datetime(2026, 10, 4).date())

    assert Query.objects.count() == 0
    assert AuditEvent.objects.count() == events_before
    assert fake_ai.embeddings.calls == []
    assert fake_ai.generation.calls == []


def test_user_without_session_is_rejected(two_regimes, fake_ai):
    """REQ-016: la función comprueba el rol; sin usuario válido no consulta ni guarda."""
    with pytest.raises(RoleRejected):
        ask(AnonymousUser(), two_regimes.after_v)

    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == []


def test_blank_question_is_rejected(read_user, two_regimes, fake_ai):
    """REQ-013: una pregunta vacía no es una consulta: no se consulta ni se guarda."""
    with pytest.raises(services.QueryRefused):
        ask(read_user, two_regimes.after_v, question="   ")

    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == []
