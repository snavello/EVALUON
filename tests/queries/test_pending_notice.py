"""Aviso de modificatorias sin cargar en la respuesta y en la búsqueda (T-052; plan 001,
"Aviso de modificatorias sin cargar (REQ-021)", "Forma de la respuesta" y "Registro de
auditoría").

Una norma con modificatorias anotadas como no cargadas (`norms_pending_amendment`) lleva
un aviso en toda respuesta o búsqueda que muestre una unidad suya. El aviso lo arma el
código, con la cuenta de `amendments.pending_count`; el modelo no lo recibe ni lo
redacta. Queda en `queries_query.result` y en el hecho `query`, y en el detalle del hecho
`search`. La pantalla lo muestra en un recuadro de texto fijo, uno por norma.

Con los dobles de `tests/conftest.py`: el reranker puntúa por marcas en el texto del
pasaje. Los textos son sintéticos (P4); el nombre de cita del régimen imita el de la
Disposición AFIP 297/03 para el texto del aviso.
"""

import html
import re
from datetime import date

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.norms.services import amendments
from evaluon.queries import services
from evaluon.queries.models import Query
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

QUESTION = "¿Qué garantía sintética corresponde en la contratación?"
DATE = date(2024, 5, 20)

ARTICLE = "[articulo-regimen]"
DICTAMEN = "[punto-dictamen]"
MODIFIER = "[modificatoria]"

REGIME_NAME = "Disposición AFIP 297/03"
NOTICE_TAIL = ("que todavía no están cargadas en el sistema. Puede haber cambios en este "
               "texto que el sistema no conoce.")


def notice_text(name, pending):
    """El texto fijo del aviso, sin artículo delante del nombre (decisión del
    Coordinador), en plural o en singular."""
    if pending == 1:
        return (f"{name} tiene 1 modificatoria que todavía no está cargada en el "
                "sistema. Puede haber cambios en este texto que el sistema no conoce.")
    return f"{name} tiene {pending} modificatorias {NOTICE_TAIL}"


def notice(norm, pending):
    return {"type": "pending_amendments", "norm": norm.pk, "name": norm.citation,
            "pending": pending}


# --- Normativa sintética -----------------------------------------------------------------


@pytest.fixture
def regime(make_norm, make_document, make_reading, make_pending_amendment):
    """Régimen específico con marca de régimen general, su artículo 5 y dos
    modificatorias anotadas como no cargadas (disposición 8801/2010 y 8802/2011)."""
    norm = make_norm(norm_type="disposicion", number="297", year=2003, issuer="afip",
                     citation=REGIME_NAME, general_regime=True)
    reading = make_reading(make_document(norm), [
        ("art-5", f"ARTICULO 5.- {ARTICLE} La garantía sintética es del cinco por "
                  "ciento del valor total de la oferta."),
    ])
    first = make_pending_amendment(norm, number="8801", year=2010)
    second = make_pending_amendment(norm, number="8802", year=2011)
    return norm, reading.units_by_key["art-5"], (first, second)


@pytest.fixture
def dictamen(make_norm, make_document, make_reading):
    """Dictamen legal sin modificatorias anotadas."""
    norm = make_norm(category="dictamen_legal", citation="Dictamen sintético 7/2021")
    reading = make_reading(make_document(norm), [
        ("punto-3", f"3. {DICTAMEN} La garantía sintética se interpreta sobre el valor "
                    "total adjudicado."),
    ])
    return norm, reading.units_by_key["punto-3"]


@pytest.fixture
def load_amendment(make_norm, make_document, make_reading, make_relation):
    """`load_amendment(régimen, anotada)`: carga la norma de una modificatoria anotada,
    con su lectura validada y en uso, registra su relación hacia el régimen (con fecha
    posterior a la consultada, para no cambiar lo que se muestra) y llama al paso a
    cargada de T-051."""

    def _load(target, entry):
        norm = make_norm(norm_type=entry.norm_type, number=entry.number,
                         year=entry.year, issuer=entry.issuer,
                         citation=f"Disposición sintética {entry.number}/{entry.year}")
        make_reading(make_document(norm), [
            ("art-1", "ARTICULO 1.- Modificación sintética sin marca."),
        ])
        make_relation(norm, target, "modifica", effective_date=date(2025, 1, 1))
        amendments.mark_loaded(target)
        return norm

    return _load


def ask(user, reference_date=DATE, question=QUESTION):
    return services.ask(user, question, reference_date)


def event_of(query):
    return AuditEvent.objects.get(pk=query.event_id)


def log_in(client):
    assert client.login(username="lectura", password=TEST_PASSWORD)


def query_page(client, query):
    response = client.get(reverse("queries:query", args=[query.pk]))
    assert response.status_code == 200
    return response.content.decode()


def notice_boxes(body):
    """Texto de cada recuadro de aviso de modificatorias sin cargar de la página."""
    return [re.sub(r"\s+", " ", html.unescape(text)).strip()
            for text in re.findall(r'<p class="pending-notice"[^>]*>(.*?)</p>', body,
                                   re.S)]


# --- Respuesta ---------------------------------------------------------------------------


def test_answer_citing_the_norm_carries_the_notice_with_two(read_user, regime, fake_ai):
    """REQ-021, REQ-012: una respuesta que cita una unidad de una norma con dos
    modificatorias sin cargar lleva un aviso de esa norma con la cantidad 2, guardado en
    `queries_query.result` y en el hecho `query`."""
    norm, article, _ = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}

    query = ask(read_user)

    assert query.result["status"] == "grounded"
    assert query.result["notices"] == [notice(norm, 2)]
    stored = Query.objects.get(pk=query.pk)
    assert stored.result["notices"] == [notice(norm, 2)]
    detail = event_of(query).detail
    assert detail["notices"] == [notice(norm, 2)]
    assert detail["result"]["notices"] == [notice(norm, 2)]


def test_screen_shows_the_notice_with_two(client, read_user, regime, fake_ai):
    """REQ-021: la pantalla de una respuesta que cita la norma muestra el recuadro con
    el nombre de la norma y la cantidad 2, arriba de las afirmaciones y debajo de la
    línea de régimen aplicado."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    log_in(client)

    response = client.post(reverse("queries:screen"),
                           {"question": QUESTION, "reference_date": DATE.isoformat()})
    assert response.status_code == 302
    body = client.get(response["Location"]).content.decode()

    assert notice_boxes(body) == [notice_text(REGIME_NAME, 2)]
    box = body.index('class="pending-notice"')
    assert body.index('class="regime-line"') < box < body.index('class="statements"')


def test_answer_citing_only_another_norm_has_no_notice(client, read_user, regime,
                                                       dictamen, fake_ai):
    """REQ-021: una respuesta que solo cita una norma sin modificatorias sin cargar no
    lleva aviso, aunque la recuperación haya traído una unidad de la norma que sí las
    tiene."""
    _, point = dictamen
    fake_ai.reranker.scores = {ARTICLE: 0.9, DICTAMEN: 0.8}
    # U1 es el artículo del régimen y U2 el punto del dictamen: se cita solo el U2.
    fake_ai.generation.answer([
        {"text": "El dictamen interpreta la garantía.", "citations": ["U2"],
         "regimes_differ": False},
    ])

    query = ask(read_user)

    assert query.result["status"] == "grounded"
    assert query.result["statements"][0]["citations"] == [point.pk]
    assert query.result["notices"] == []
    assert event_of(query).detail["notices"] == []
    log_in(client)
    assert notice_boxes(query_page(client, query)) == []


def test_unit_shown_because_it_modifies_counts_for_the_notice(
    read_user, regime, make_norm, make_document, make_reading, make_relation,
    make_pending_amendment, fake_ai
):
    """REQ-021: cuentan también las unidades que se muestran por haber modificado a una
    citada. Un aviso por norma, en el orden en que se muestran: primero la citada y
    después la que la modifica."""
    norm, article, _ = regime
    modifier_norm = make_norm(citation="Disposición sintética 400/2015")
    modifier = make_reading(make_document(modifier_norm), [
        ("art-1", f"ARTICULO 1.- {MODIFIER} Sustitúyese el texto sintético."),
    ]).units_by_key["art-1"]
    make_relation(modifier_norm, norm, "modifica", source_unit_key="art-1",
                  target_unit_key="art-5", effective_date=date(2020, 1, 1))
    make_pending_amendment(modifier_norm)
    fake_ai.reranker.scores = {ARTICLE: 0.9, MODIFIER: 0.1}

    query = ask(read_user)

    assert str(modifier.pk) in query.result["units"]
    assert query.result["notices"] == [notice(norm, 2), notice(modifier_norm, 1)]


def test_undetermined_has_no_notice(client, read_user, regime, fake_ai):
    """REQ-021: un "no determinado" no muestra unidades y no lleva aviso, ni en el
    resultado ni en el hecho ni en la pantalla."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    fake_ai.generation.abstain()

    query = ask(read_user)

    assert query.result["status"] == "undetermined"
    assert query.result["notices"] == []
    assert event_of(query).detail["notices"] == []
    log_in(client)
    assert notice_boxes(query_page(client, query)) == []


def test_below_threshold_has_no_notice(read_user, regime, fake_ai):
    """REQ-021: un "no determinado" porque nada alcanza el umbral no lleva aviso."""
    fake_ai.reranker.scores = {ARTICLE: 0.1}

    query = ask(read_user)

    assert query.result["status"] == "undetermined"
    assert query.result["notices"] == []


def test_technical_failure_has_no_notice(read_user, regime, fake_ai):
    """REQ-021: una falla técnica no muestra unidades y no lleva aviso."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    fake_ai.generation.timeout()

    query = ask(read_user)

    assert query.result["status"] == "error"
    assert query.result["notices"] == []
    assert event_of(query).detail["notices"] == []


def test_request_to_the_engine_does_not_carry_the_notice(read_user, regime, fake_ai):
    """REQ-021: el modelo no recibe ni redacta el aviso: el pedido enviado al motor no
    tiene su texto ni la cantidad de modificatorias."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}

    query = ask(read_user)

    assert query.result["notices"]
    [(messages, schema)] = fake_ai.generation.calls
    sent = " ".join(str(m.get("content", "")) for m in messages) + str(schema)
    sent += str(query.request)
    for fragment in ("modificatoria", "todavía no", "pending", "Puede haber cambios"):
        assert fragment not in sent, fragment


def test_count_is_the_one_read_before_generating(read_user, regime, fake_ai,
                                                 make_pending_amendment, monkeypatch):
    """REQ-021, REQ-012: la cuenta del aviso se lee con la normativa con que se armó la
    respuesta, antes de llamar al modelo: una modificatoria anotada mientras el modelo
    responde no cambia el aviso de esa consulta."""
    norm, _, _ = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    original = fake_ai.generation.generate

    def generate_and_annotate(messages, schema):
        make_pending_amendment(norm, number="8899", year=2012)
        return original(messages, schema)

    monkeypatch.setattr("evaluon.ai.generation.generate", generate_and_annotate)

    query = ask(read_user)

    assert amendments.pending_count(norm) == 3
    assert query.result["notices"] == [notice(norm, 2)]


def test_notice_goes_down_to_one_and_disappears(client, read_user, regime,
                                                load_amendment, fake_ai):
    """REQ-021: cargada, validada y relacionada una de las dos modificatorias, una
    consulta nueva muestra 1, en singular; con las dos, el aviso deja de aparecer. La
    consulta hecha antes sigue mostrando su aviso con 2."""
    norm, _, (first, second) = regime
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    log_in(client)
    before = ask(read_user)

    load_amendment(norm, first)
    with_one = ask(read_user)

    assert with_one.result["notices"] == [notice(norm, 1)]
    assert notice_boxes(query_page(client, with_one)) == [notice_text(REGIME_NAME, 1)]

    load_amendment(norm, second)
    with_none = ask(read_user)

    assert with_none.result["status"] == "grounded"
    assert with_none.result["notices"] == []
    assert notice_boxes(query_page(client, with_none)) == []
    assert notice_boxes(query_page(client, before)) == [notice_text(REGIME_NAME, 2)]


def test_page_keeps_citation_markup_and_shows_no_internal_names(client, read_user,
                                                                regime, fake_ai):
    """REQ-021, REQ-013: el recuadro no rompe el marcado de las citas (anclas sin
    repetir) y la página no muestra el tipo interno del aviso ni sus claves."""
    fake_ai.reranker.scores = {ARTICLE: 0.9}
    log_in(client)

    body = query_page(client, ask(read_user))

    assert notice_boxes(body)
    assert '<details class="citation"' in body
    ids = re.findall(r'\sid="([^"]+)"', body)
    assert len(ids) == len(set(ids))
    for name in ("pending_amendments", "pending", "notices", "None"):
        assert name not in body.replace("pending-notice", ""), name


# --- Búsqueda ----------------------------------------------------------------------------


def search_events():
    return list(AuditEvent.objects.filter(event_type=EventType.SEARCH).order_by("pk"))


def test_search_returning_a_unit_of_the_norm_carries_the_notice(read_user, regime):
    """REQ-021, REQ-012: una búsqueda que devuelve una unidad de la norma lleva el aviso
    con la cantidad 2, en lo que devuelve y en el detalle del hecho `search`."""
    norm, article, _ = regime

    outcome = services.search(read_user, DATE, norm_id=norm.pk, article="5")

    assert [r.unit_id for r in outcome.results] == [article.pk]
    assert outcome.notices == [notice(norm, 2)]
    [event] = search_events()
    assert event.detail["notices"] == [notice(norm, 2)]


def test_search_returning_only_another_norm_has_no_notice(read_user, regime, dictamen):
    """REQ-021: una búsqueda que solo devuelve unidades de otra norma no lleva aviso."""
    norm, point = dictamen

    outcome = services.search(read_user, DATE, words="adjudicado")

    assert [r.unit_id for r in outcome.results] == [point.pk]
    assert outcome.notices == []
    [event] = search_events()
    assert event.detail["notices"] == []


def test_search_screen_shows_the_notice(client, read_user, regime, load_amendment):
    """REQ-021: la pantalla de búsqueda muestra el recuadro con la cantidad, debajo de
    la línea de régimen y arriba de los resultados; cargada una modificatoria muestra 1
    y con las dos no aparece."""
    norm, _, (first, second) = regime
    log_in(client)

    def search_page():
        response = client.post(reverse("queries:search"), {
            "search-norm": norm.pk, "search-article": "5", "search-words": "",
            "search-reference_date": DATE.isoformat(),
        })
        assert response.status_code == 200
        return response.content.decode()

    body = search_page()
    assert notice_boxes(body) == [notice_text(REGIME_NAME, 2)]
    box = body.index('class="pending-notice"')
    assert body.index('class="search-results"') < box < body.index('class="search-list"')
    assert body.index('class="regime-line"') < box

    load_amendment(norm, first)
    assert notice_boxes(search_page()) == [notice_text(REGIME_NAME, 1)]

    load_amendment(norm, second)
    assert notice_boxes(search_page()) == []


def test_notice_has_no_article_before_a_masculine_name(
    client, read_user, make_norm, make_document, make_reading, make_pending_amendment
):
    """REQ-021: el aviso no lleva artículo delante del nombre de la norma (decisión del
    Coordinador), así un nombre masculino como "Decreto 1023/2001" no queda "La Decreto
    1023/2001"; con una sola modificatoria, en singular."""
    decree = make_norm(category="marco_nacional", norm_type="decreto", number="1023",
                       year=2001, citation="Decreto 1023/2001")
    make_reading(make_document(decree), [
        ("art-24", "ARTICULO 24.- Selección sintética del cocontratante."),
    ])
    make_pending_amendment(decree)
    log_in(client)

    response = client.post(reverse("queries:search"), {
        "search-norm": decree.pk, "search-article": "24", "search-words": "",
        "search-reference_date": DATE.isoformat(),
    })
    assert response.status_code == 200
    body = response.content.decode()

    assert notice_boxes(body) == [
        "Decreto 1023/2001 tiene 1 modificatoria que todavía no está cargada en el "
        "sistema. Puede haber cambios en este texto que el sistema no conoce."]
    assert "La Decreto" not in body
