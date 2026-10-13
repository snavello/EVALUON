"""La Consulta de normativa con el Qwen3.8-27B del motor de lotes (T-255, ADR-0057; REQ-107).

Un solo motor: con `docker-compose.consulta-27b.yml` la Consulta (`GENERATION_URL`) va a
`generation_batch`, el motor que carga el 27B para las evaluaciones y las matrices, y `generation`
(el 12B) no arranca. Ese motor atiende de a un pedido (`--parallel 1`), así que mientras corre un
trabajo de lotes la Consulta lo dice y no ejecuta ni guarda la pregunta.

Estas pruebas no usan la GPU ni el modelo: un servidor HTTP local hace de motor y guarda lo que
recibe, y los dobles de `tests/conftest.py` hacen de embeddings y reranker. Los datos son
sintéticos (P4). La medición de las evals de la 001 con el 27B (P7) es de la verificación.
"""

import json
from datetime import date

import pytest
from django.urls import reverse

import evaluon.ai as ai_client
from evaluon.ai import generation
from evaluon.audit.models import AuditEvent, Channel
from evaluon.queries import answering, services
from evaluon.queries.models import Query
from evaluon.tenders import models as tenders
from tests.conftest import REAL_IS_AVAILABLE, TEST_PASSWORD
from tests.queries.test_ai_clients import chat_completion, server  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db

# El 27B del motor de lotes (docker-compose.qwen38-27b.yml; huella de scripts/models.sha256).
ALIAS = "qwen3.8-27b-ud-q4_k_m"
MODEL_FILE = "Qwen3.8-27B-UD-Q4_K_M.gguf"
MODEL_SHA256 = "322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482"
ENGINE_CONTEXT = 32768

# El aviso de la Consulta ocupada, tal cual lo pidió el Coordinador (el código le suma el punto final).
BUSY = ("La consulta de normativa no está disponible mientras el sistema evalúa o arma una matriz; "
        "vuelva a intentar cuando termine")
# Con el motor compartido que no contesta (el 27B cargando tras un reinicio, o caído), tal cual lo
# pidió el Coordinador.
NOT_RESPONDING = ("La consulta de normativa no está disponible por ahora: el motor del modelo se está "
                  "encendiendo o no responde. Vuelva a intentarlo en unos minutos.")
# El de T-247, con `generation` aparte que no contesta (el 27B sin Consulta, o el 12B caído).
OFF = "La consulta de normativa no está disponible por ahora"
OFF_T247 = ("La consulta de normativa no está disponible por ahora: el equipo usa el modelo grande "
            "para las evaluaciones y deja apagado el motor de la consulta. Vuelva a intentarlo más tarde.")
FAILURE = "No se pudo completar la consulta"

QUESTION = "¿Qué garantía sintética corresponde en la contratación?"
DATE = date(2024, 5, 20)
ARTICLE = "[articulo-regimen]"

GROUNDED = json.dumps({"status": "grounded", "statements": [
    {"text": "La garantía sintética es del cinco por ciento.", "citations": ["U1"],
     "regimes_differ": False}]}, ensure_ascii=False)
ABSTAINED = json.dumps({"status": "undetermined", "statements": []})

# Pedidos que usan el motor de lotes mientras corren (evaluación, matriz, ficha y las dos
# propuestas de datos) y los que no (leer documentos: OCR en el `worker`; Portal: otro servicio).
ENGINE_KINDS = {tenders.JobKind.EVALUATE_OFFERS, tenders.JobKind.PROPOSE_MATRIX,
                tenders.JobKind.BUILD_SHEET, tenders.JobKind.PROPOSE_PROCEDURE,
                tenders.JobKind.PROPOSE_OFFER}
NO_ENGINE_KINDS = {tenders.JobKind.READ_DOCUMENT, tenders.JobKind.READ_OFFER_DOCUMENT,
                   tenders.JobKind.PORTAL_EXPLORE, tenders.JobKind.PORTAL_REVIEW}


# --- Armado -----------------------------------------------------------------------------------


@pytest.fixture
def one_engine(settings):
    """Un solo motor (ADR-0057): la Consulta y los pedidos de lotes van a la misma dirección y el
    modelo, el archivo, la huella y el contexto son los del 27B en los dos lados."""
    settings.GENERATION_URL = settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    settings.GENERATION_MODEL = settings.GENERATION_BATCH_MODEL = ALIAS
    settings.GENERATION_MODEL_FILE = settings.GENERATION_BATCH_MODEL_FILE = MODEL_FILE
    settings.GENERATION_MODEL_SHA256 = settings.GENERATION_BATCH_MODEL_SHA256 = MODEL_SHA256
    settings.GENERATION_CONTEXT_TOKENS = settings.GENERATION_BATCH_CONTEXT_TOKENS = ENGINE_CONTEXT
    return settings


@pytest.fixture
def two_engines(settings):
    """La instalación de la 001 a la 014 (y la vuelta al 12B): `generation` aparte de
    `generation_batch`."""
    settings.GENERATION_URL = "http://generation:8080"
    settings.GENERATION_BATCH_URL = "http://generation_batch:8080"
    return settings


@pytest.fixture
def engine_server(one_engine, server):  # noqa: F811
    """Un servidor HTTP local en el lugar del motor del 27B, único para la Consulta y los lotes.
    Cuenta los tokens con una cuenta fija (cinco por texto) y guarda cada pedido en
    `server.requests`."""
    one_engine.GENERATION_URL = one_engine.GENERATION_BATCH_URL = server.url
    server.route("/tokenize", {"tokens": [1, 2, 3, 4, 5]})
    return server


@pytest.fixture
def article(make_norm, make_document, make_reading):
    """Un régimen específico con marca de régimen general y su artículo 5 (la normativa de la
    Consulta, sintética)."""
    norm = make_norm(category="regimen_especifico", general_regime=True)
    reading = make_reading(make_document(norm), [
        ("art-5", f"ARTICULO 5.- {ARTICLE} La garantía sintética es del cinco por ciento del "
                  "valor total de la oferta."),
    ])
    return reading.units_by_key["art-5"]


@pytest.fixture
def add_job(read_user):
    """`add_job(tipo, estado)`: un pedido del `worker` en ese estado (por omisión, en curso), sin
    pasar por el modelo. Todo inventado."""
    procedure = tenders.Procedure.objects.create(
        number="SINT-CONSULTA-1", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14), created_by=read_user)

    def add(kind, status=tenders.JobStatus.RUNNING):
        return tenders.Job.objects.create(kind=kind, status=status, procedure=procedure,
                                          target_id=1, requested_by=read_user)

    return add


def literal(unit):
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


# --- El pedido de la Consulta al motor del 27B ---------------------------------------------------


def test_the_consulta_asks_the_batch_engine_without_reasoning_and_the_request_is_recorded(
        read_user, article, fake_embeddings, fake_reranker, engine_server, settings):
    """REQ-107, P6, ADR-0002: con un solo motor, la pregunta recorre la recuperación y el pedido
    sale a `generation_batch` (los tokens y la generación) con el modelo del 27B, el esquema JSON,
    la temperatura y la semilla de siempre y SIN razonamiento, aunque el servidor lo permita y todos
    los pasos de lotes estén encendidos en `low`; la cita es el texto literal de la base."""
    settings.GENERATION_BATCH_REASONING = {
        step: "low" for step in settings.GENERATION_BATCH_REASONING_STEPS}
    fake_reranker.scores = {ARTICLE: 0.9}
    engine_server.route("/v1/chat/completions", chat_completion(GROUNDED))

    query = services.ask(read_user, QUESTION, DATE)

    paths = [path for _, path, _ in engine_server.requests]
    assert paths.count("/v1/chat/completions") == 1 and "/tokenize" in paths
    [body] = [body for _, path, body in engine_server.requests if path == "/v1/chat/completions"]
    assert body["model"] == ALIAS
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert not {"reasoning_effort", "thinking_budget_tokens"} & set(body)
    assert body["max_tokens"] == settings.GENERATION_MAX_OUTPUT_TOKENS
    assert body["temperature"] == 0 and body["seed"] == settings.GENERATION_SEED
    assert body["stream"] is False
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"]["properties"]["statements"][
        "items"]["properties"]["citations"]["items"]["enum"] == ["U1"]
    # lo registrado es lo enviado
    assert query.request == body
    assert query.raw_output == GROUNDED
    assert query.status == "grounded"
    [statement] = query.result["statements"]
    assert statement["citations"] == [article.pk]
    assert answering.citation_texts(query.result)[article.pk] == literal(article)


def test_the_consulta_keeps_abstaining_with_the_batch_engine(
        read_user, article, fake_embeddings, fake_reranker, engine_server):
    """REQ-107, ADR-0002: con el motor único, una salida «no determinado» sigue siendo «no
    determinado» (el motivo es el del modelo), sin fundamento inventado y sin falla técnica."""
    fake_reranker.scores = {ARTICLE: 0.9}
    engine_server.route("/v1/chat/completions", chat_completion(ABSTAINED))

    query = services.ask(read_user, QUESTION, DATE)

    assert query.status == "undetermined" and query.reason == "model_abstained"
    assert query.result["statements"] == []
    assert query.selected["abstention"] == {"abstained": True, "reason": "model_abstained"}


def test_the_record_names_the_engine_and_the_model_that_served_the_consulta(
        read_user, article, fake_embeddings, fake_reranker, engine_server, settings):
    """REQ-107, P6: el registro de la consulta dice el motor (`generation_batch`), su dirección y el
    modelo que la atendió (alias, archivo y huella del 27B), la compilación, el contexto real del
    motor y que no pensó; como la matriz y la evaluación, que registran el modelo y la dirección
    del motor de lotes."""
    fake_reranker.scores = {ARTICLE: 0.9}
    engine_server.route("/v1/chat/completions", chat_completion(GROUNDED))

    query = services.ask(read_user, QUESTION, DATE)

    served = query.parameters["generation"]
    assert served["engine"] == "generation_batch"
    assert served["url"] == settings.GENERATION_BATCH_URL == engine_server.url
    assert (served["model"], served["file"], served["sha256"]) == (ALIAS, MODEL_FILE, MODEL_SHA256)
    assert served["engine_build"] == settings.GENERATION_ENGINE_BUILD
    assert served["context_tokens"] == ENGINE_CONTEXT
    assert served["thinking"] is False
    # el hecho de auditoría lleva lo mismo
    assert AuditEvent.objects.get(pk=query.event_id).detail["parameters"]["generation"] == served


def test_the_record_names_the_separate_engine_when_there_are_two(two_engines):
    """REQ-107, P6: con `generation` aparte (la instalación de siempre y la vuelta al 12B) el
    registro dice `generation` y su dirección: la misma consulta, otro motor."""
    served = services.parameters()["generation"]

    assert served["engine"] == "generation"
    assert served["url"] == "http://generation:8080"


def test_the_consulta_waits_for_its_own_timeout_and_never_for_the_reasoning_extra(
        monkeypatch, one_engine, settings):
    """REQ-107, ADR-0005: el pedido de la Consulta no fija su espera (vale `AI_TIMEOUT_SECONDS`) y
    nunca suma la espera extra de un paso que piensa, que son 900 s y la dejarían muy por encima de
    los 120 s de Gunicorn (el tope contra Gunicorn lo comprueba tests/test_compose_env.py)."""
    seen = {}

    def post(service, base_url, path, body, *, timeout=None):
        seen.update(base_url=base_url, path=path, body=body, timeout=timeout)
        return chat_completion(GROUNDED)

    monkeypatch.setattr(generation, "post_json", post)
    settings.GENERATION_BATCH_REASONING = {
        step: "low" for step in settings.GENERATION_BATCH_REASONING_STEPS}

    result = generation.generate([{"role": "user", "content": "x"}], {"type": "object"})

    assert seen["base_url"] == settings.GENERATION_URL == settings.GENERATION_BATCH_URL
    assert seen["timeout"] is None  # `post_json` toma `AI_TIMEOUT_SECONDS`
    assert seen["body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert result.reasoning_level is None and result.reasoning_record() is None


# --- El motor del 27B responde su salud -----------------------------------------------------------


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_availability_asks_the_health_of_the_batch_engine(monkeypatch, one_engine):
    """REQ-107: con la Consulta en el motor de lotes, `is_available()` pregunta `/health` de
    `generation_batch` con la espera corta de 2 s, y 200 es «disponible»."""
    asked = []

    def urlopen(url, timeout=None):
        asked.append((url, timeout))
        return _Response(200)

    monkeypatch.setattr(ai_client.urllib.request, "urlopen", urlopen)

    assert REAL_IS_AVAILABLE() is True
    assert asked == [("http://generation_batch:8080/health", 2)]


def test_availability_is_false_while_the_batch_engine_loads_the_model(monkeypatch, one_engine):
    """REQ-107: el 27B tarda de 3 a 10 minutos en cargar y el motor responde 503 hasta entonces: la
    Consulta dice «no disponible» en lugar de recorrer la recuperación y fallar."""
    monkeypatch.setattr(ai_client.urllib.request, "urlopen",
                        lambda url, timeout=None: _Response(503))

    assert REAL_IS_AVAILABLE() is False


# --- Un motor, un pedido a la vez: la Consulta con un trabajo de lotes en curso ----------------------


def test_the_job_kinds_are_all_classified_as_using_the_batch_engine_or_not():
    """REQ-107: cada tipo de pedido del `worker` está o no está entre los que ocupan el motor de
    lotes mientras corren; un tipo nuevo obliga a decidirlo acá (la Consulta lo vería libre y se
    quedaría esperando detrás de él, o lo vería ocupado sin estarlo)."""
    assert set(tenders.JobKind) == ENGINE_KINDS | NO_ENGINE_KINDS
    assert not ENGINE_KINDS & NO_ENGINE_KINDS
    assert set(services.BATCH_ENGINE_JOB_KINDS) == ENGINE_KINDS
    assert set(tenders.PORTAL_JOB_KINDS) <= NO_ENGINE_KINDS  # los atiende `portal_worker`


@pytest.mark.parametrize("kind", sorted(ENGINE_KINDS))
def test_a_running_batch_job_makes_the_consulta_say_it_is_busy(add_job, one_engine, kind):
    """REQ-107: con un solo motor, un pedido en curso de cualquiera de los tipos que lo usan hace
    que la Consulta devuelva el aviso."""
    add_job(kind)

    assert services.consulta_notice() == services.BUSY_NOTICE
    assert services.consulta_available() is False


def test_the_busy_notice_is_the_exact_text_in_plain_language():
    """REQ-107: el texto del aviso es el pedido, en llano, sin nombres internos."""
    assert services.BUSY_NOTICE == BUSY + "."
    for word in ("generation", "Qwen", "GPU", "docker", "gguf", "motor"):
        assert word not in services.BUSY_NOTICE


def test_a_busy_engine_is_not_probed_with_the_health_check(add_job, one_engine, monkeypatch):
    """REQ-107: con un trabajo en curso la Consulta no espera la salud del motor (que tiene un tope
    de 2 s y no dice nada que el pedido en curso no diga)."""
    add_job(tenders.JobKind.PROPOSE_MATRIX)

    def never(timeout=None):
        raise AssertionError("no se pregunta la salud con un trabajo de lotes en curso")

    monkeypatch.setattr(generation, "is_available", never)

    assert services.consulta_notice() == services.BUSY_NOTICE


@pytest.mark.parametrize("status", [tenders.JobStatus.QUEUED, tenders.JobStatus.DONE,
                                    tenders.JobStatus.FAILED])
def test_a_job_that_is_not_running_does_not_block_the_consulta(add_job, one_engine, status):
    """REQ-107: en espera, terminado o fallido no ocupa el motor: la Consulta anda. (En espera, el
    `worker` lo toma en segundos; si está caído nada corre y el motor está libre.)"""
    add_job(tenders.JobKind.EVALUATE_OFFERS, status)

    assert services.consulta_notice() == ""
    assert services.consulta_available() is True


@pytest.mark.parametrize("kind", [tenders.JobKind.READ_OFFER_DOCUMENT,
                                  tenders.JobKind.PORTAL_EXPLORE, tenders.JobKind.PORTAL_REVIEW])
def test_a_running_job_that_does_not_use_the_engine_does_not_block_it(add_job, one_engine, kind):
    """REQ-107: leer el documento de una oferta (OCR) o explorar el Portal (otro servicio) no ocupa
    el motor de lotes: la Consulta anda."""
    add_job(kind)

    assert services.consulta_notice() == ""


def test_with_two_engines_a_batch_job_does_not_block_the_consulta(add_job, two_engines):
    """REQ-107: con `generation` aparte (la vuelta al 12B) la Consulta no espera detrás de las
    evaluaciones: el aviso es solo del motor único."""
    add_job(tenders.JobKind.EVALUATE_OFFERS)

    assert services.consulta_notice() == ""
    assert generation.shares_batch_engine() is False


def test_a_shared_engine_that_does_not_answer_says_it_is_starting_or_not_responding(
        one_engine, monkeypatch):
    """REQ-107: sin trabajo en curso, el motor compartido que no contesta (el 27B cargando tras un
    reinicio, de 3 a 10 minutos, o caído) dice que se está encendiendo o no responde, en las
    palabras pedidas: es el motor de las evaluaciones, no uno que el equipo dejó apagado a propósito."""
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)

    assert services.consulta_notice() == services.NOT_RESPONDING_NOTICE == NOT_RESPONDING
    assert services.consulta_available() is False
    assert "deja apagado" not in services.NOT_RESPONDING_NOTICE
    for word in ("generation", "Qwen", "GPU", "docker", "gguf"):
        assert word not in services.NOT_RESPONDING_NOTICE


def test_with_two_engines_the_one_of_the_consulta_off_keeps_the_notice_of_t247(
        two_engines, monkeypatch):
    """REQ-107: con `generation` aparte que no contesta (el 27B sin Consulta, o el 12B caído) queda
    el texto de T-247, que dice que el equipo dejó apagado el motor de la Consulta."""
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)

    assert services.consulta_notice() == services.UNAVAILABLE_NOTICE == OFF_T247
    assert services.consulta_available() is False


def test_the_same_address_with_a_closing_slash_is_one_engine(settings):
    """REQ-107: `http://x:8080` y `http://x:8080/` son el mismo motor (como en `model_for`)."""
    settings.GENERATION_URL = "http://generation_batch:8080/"
    settings.GENERATION_BATCH_URL = "http://generation_batch:8080"

    assert generation.shares_batch_engine() is True


# --- Las pantallas ---------------------------------------------------------------------------------


def test_the_screen_says_it_and_does_not_run_the_question_while_a_job_runs(
        client, read_user, add_job, one_engine, fake_ai):
    """REQ-107: con una evaluación en curso, `/consulta/` trae el aviso con el botón desactivado; la
    pregunta enviada no recorre la recuperación, no llama al modelo, no deja una consulta fallida y
    la pantalla conserva lo escrito."""
    add_job(tenders.JobKind.EVALUATE_OFFERS)
    log_in(client, read_user)

    html = client.get(reverse("queries:screen")).content.decode()
    assert BUSY in html and 'id="query-unavailable"' in html
    assert 'id="query-submit" disabled' in html
    assert OFF not in html and FAILURE not in html

    response = client.post(reverse("queries:screen"),
                           {"question": "¿Qué garantía se exige al ofertar?", "reference_date": ""})
    assert response.status_code == 200
    html = response.content.decode()
    assert BUSY in html and FAILURE not in html
    assert "¿Qué garantía se exige al ofertar?" in html
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.reranker.calls == []
    assert fake_ai.generation.calls == []


def test_the_screen_says_the_shared_engine_is_starting_and_does_not_run_the_question(
        client, read_user, one_engine, fake_ai, monkeypatch):
    """REQ-107: con el motor compartido sin contestar (el 27B cargando, o caído), `/consulta/` trae
    el aviso de que se está encendiendo o no responde, con el botón desactivado; la pregunta no
    recorre la recuperación ni se guarda, y no se muestra como falla técnica ni como Consulta
    ocupada ni con el texto de T-247."""
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)
    log_in(client, read_user)

    html = client.get(reverse("queries:screen")).content.decode()
    assert NOT_RESPONDING in html and 'id="query-unavailable"' in html
    assert 'id="query-submit" disabled' in html
    assert OFF_T247 not in html and BUSY not in html and FAILURE not in html

    response = client.post(reverse("queries:screen"),
                           {"question": "¿Qué garantía se exige al ofertar?", "reference_date": ""})
    assert response.status_code == 200
    html = response.content.decode()
    assert NOT_RESPONDING in html and FAILURE not in html
    assert "¿Qué garantía se exige al ofertar?" in html
    assert Query.objects.count() == 0
    assert fake_ai.embeddings.calls == [] and fake_ai.reranker.calls == []
    assert fake_ai.generation.calls == []


def test_the_screen_with_two_engines_and_the_consulta_one_off_keeps_the_notice_of_t247(
        client, read_user, two_engines, fake_ai, monkeypatch):
    """REQ-107: con `generation` aparte que no contesta, la pantalla dice lo de T-247 y no lo del
    motor compartido; la pregunta tampoco se ejecuta ni se guarda."""
    monkeypatch.setattr(generation, "is_available", lambda timeout=None: False)
    log_in(client, read_user)

    html = client.get(reverse("queries:screen")).content.decode()
    assert OFF_T247 in html and NOT_RESPONDING not in html
    assert 'id="query-submit" disabled' in html

    client.post(reverse("queries:screen"),
                {"question": "¿Qué garantía se exige al ofertar?", "reference_date": ""})
    assert Query.objects.count() == 0 and fake_ai.generation.calls == []


def test_the_page_of_a_saved_query_also_says_it_while_a_job_runs(
        client, read_user, add_job, one_engine):
    """REQ-107: la página de una consulta ya guardada trae el aviso (el formulario de arriba queda
    desactivado)."""
    from tests.queries.test_screen import save_query

    query = save_query(read_user, {"status": "undetermined", "reason": "below_threshold",
                                   "reference_date": "2024-05-20", "regime": [], "notices": [],
                                   "statements": [], "units": {}, "query_id": None})
    add_job(tenders.JobKind.PROPOSE_MATRIX)
    log_in(client, read_user)

    html = client.get(reverse("queries:query", args=[query.pk])).content.decode()

    assert BUSY in html and 'id="query-submit" disabled' in html


def test_direct_search_keeps_working_while_a_job_runs(
        client, read_user, add_job, one_engine, article):
    """REQ-107: la búsqueda directa no usa el modelo y sigue andando con el motor ocupado: muestra
    sus resultados (y la pantalla, el aviso de la Consulta)."""
    add_job(tenders.JobKind.EVALUATE_OFFERS)
    log_in(client, read_user)

    response = client.post(reverse("queries:search"), {
        "search-norm": "", "search-article": "", "search-words": "sintética",
        "search-reference_date": ""})

    assert response.status_code == 200
    html = response.content.decode()
    assert 'class="search-results"' in html and "ARTICULO 5" in html
    assert BUSY in html


def test_with_the_engine_free_the_consulta_runs(
        client, read_user, one_engine, article, fake_ai):
    """REQ-107: sin trabajo en curso la pantalla es la de siempre y la pregunta se ejecuta (recorre
    la recuperación y llama al modelo) y se guarda: la Consulta anda con el motor libre."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    log_in(client, read_user)
    html = client.get(reverse("queries:screen")).content.decode()
    assert BUSY not in html and 'id="query-submit" disabled' not in html

    response = client.post(reverse("queries:screen"),
                           {"question": QUESTION, "reference_date": ""})

    assert response.status_code == 302
    [query] = Query.objects.all()
    assert query.status == "grounded"
    assert fake_ai.embeddings.calls and len(fake_ai.generation.calls) == 1


def test_a_finished_job_frees_the_consulta_again(client, read_user, add_job, one_engine):
    """REQ-107: al terminar el trabajo el aviso desaparece solo, sin tocar nada."""
    job = add_job(tenders.JobKind.PROPOSE_MATRIX)
    log_in(client, read_user)
    assert BUSY in client.get(reverse("queries:screen")).content.decode()

    tenders.Job.objects.filter(pk=job.pk).update(status=tenders.JobStatus.DONE)

    html = client.get(reverse("queries:screen")).content.decode()
    assert BUSY not in html and 'id="query-submit" disabled' not in html


def test_the_evals_and_the_commands_are_not_refused_by_a_running_job(
        read_user, add_job, one_engine, article, fake_ai):
    """REQ-107: el aviso es de las pantallas; `services.ask` (el camino de las evals y de los
    comandos) no consulta la cola de pedidos y responde igual."""
    add_job(tenders.JobKind.EVALUATE_OFFERS)
    fake_ai.reranker.scores = {ARTICLE: 0.9}

    query = services.ask(read_user, QUESTION, DATE, channel=Channel.EVAL)

    assert query.status == "grounded"
