"""Búsqueda directa en la pantalla de consulta, con su registro (T-041; plan 001,
"Búsqueda directa (REQ-010)", "Fecha de autorización y régimen aplicado", "Pantalla,
acceso y comandos" y "Registro de auditoría").

La pantalla de consulta tiene, además del formulario de la pregunta, el de búsqueda:
por norma (de la lista) y número de artículo, o por palabras, con su propio campo de
fecha de autorización. Lo envía a la función de búsqueda de `queries/services.py`, que
comprueba el rol, valida la fecha, toma el régimen aplicado, busca con
`queries/search.py` y deja el hecho `search`. La página muestra los resultados con la
línea de fecha y régimen. Sin modelos de IA. Los datos son sintéticos (P4): los dos
regímenes de prueba de `two_regimes` y normas armadas con las fábricas de `conftest.py`.
"""

import html
import re
from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.queries import services
from evaluon.queries.forms import FUTURE_DATE_ERROR
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

NO_REGIME_TEXT = "Para esa fecha no hay un régimen específico cargado en el sistema"
NO_RESULTS_TEXT = "No se encontró ningún texto"
REPEALED_MARK = "Texto derogado"
INTERNAL_NAMES = ("regimen_especifico", "articulo", "outgoing", "incoming", "repealed",
                  "pdf_text", "consultable_units", "by_article", "by_words")


# --- Ayudas -----------------------------------------------------------------------------


def log_in(client, username="lectura"):
    assert client.login(username=username, password=TEST_PASSWORD)


def search_on_screen(client, *, norm=None, article="", words="", reference_date=""):
    """Envía el formulario de búsqueda desde la pantalla y devuelve la página."""
    data = {
        "search-norm": norm.pk if norm is not None else "",
        "search-article": article,
        "search-words": words,
        "search-reference_date": (reference_date.isoformat()
                                  if isinstance(reference_date, date)
                                  else reference_date),
    }
    response = client.post(reverse("queries:search"), data)
    assert response.status_code == 200
    return response.content.decode()


def results_block(body):
    """La sección de resultados de la búsqueda."""
    match = re.search(r'<section class="search-results".*?</section>', body, re.S)
    assert match, "la página no muestra resultados de búsqueda"
    return match.group(0)


def result_items(block):
    """Cada resultado, por `id` de unidad: `{id: marcado}`."""
    items = re.findall(
        r'<li class="search-result"[^>]*>\s*<details class="citation" '
        r'data-unit="(\d+)"[^>]*>(.*?)</details>\s*</li>',
        block, re.S,
    )
    return {int(unit_id): content for unit_id, content in items}


def summary(item):
    return re.search(r"<summary>(.*?)</summary>", item, re.S).group(1)


def literal(unit):
    return html.escape(unit.reading.canonical_text[unit.char_start:unit.char_end])


def date_value(body, name):
    match = re.search(rf'<input type="date" name="{name}" value="([^"]*)"', body)
    assert match, f"la página no tiene el campo de fecha {name}"
    return match.group(1)


def search_events():
    return list(AuditEvent.objects.filter(event_type=EventType.SEARCH).order_by("pk"))


# --- La pantalla con el formulario de búsqueda -------------------------------------------


def test_screen_has_search_form_with_its_own_date_field(client, read_user, two_regimes,
                                                        monkeypatch):
    """REQ-010, REQ-020: la pantalla de consulta tiene el formulario de búsqueda por
    norma y número de artículo o por palabras, con su propio campo "Fecha de
    autorización del procedimiento", que viene con la fecha del día en hora de Buenos
    Aires y no repite el nombre ni el `id` del campo de la pregunta."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)

    body = client.get("/").content.decode()

    assert f'<form method="post" action="{reverse("queries:search")}' in body
    assert '<select name="search-norm"' in body
    assert 'name="search-article"' in body
    assert 'name="search-words"' in body
    assert date_value(body, "search-reference_date") == "2026-10-03"
    assert date_value(body, "reference_date") == "2026-10-03"
    assert body.count("Fecha de autorización del procedimiento") == 2
    ids = re.findall(r'\sid="([^"]+)"', body)
    assert len(ids) == len(set(ids)), "hay identificadores repetidos en la página"


def test_norm_list_shows_only_norms_that_can_be_searched(client, read_user, two_regimes,
                                                         make_norm, make_document,
                                                         make_reading):
    """REQ-010: la norma se elige de la lista, que nombra cada norma por su nombre de
    cita; una norma cargada y todavía sin validar no está en la lista."""
    pending = make_norm(citation="Resolución sintética pendiente 9/99")
    make_reading(make_document(pending), [("art-1", "ARTICULO 1.- Pendiente.")],
                 status="pending")
    log_in(client)

    body = client.get("/").content.decode()
    select = re.search(r'<select name="search-norm".*?</select>', body, re.S).group(0)

    assert f'<option value="{two_regimes.old.pk}">{two_regimes.old.citation}</option>' \
        in select
    assert f'<option value="{two_regimes.new.pk}">{two_regimes.new.citation}</option>' \
        in select
    assert pending.citation not in select


# --- Por norma y número de artículo (REQ-010) --------------------------------------------


def test_reader_searches_norm_and_article_and_gets_unit_with_text(client, read_user,
                                                                  two_regimes):
    """REQ-010: una persona con rol de lectura busca norma y artículo en la pantalla de
    consulta y obtiene la unidad con su texto literal, su norma y ruta, su categoría y el
    enlace al documento original."""
    log_in(client)
    unit = two_regimes.old_units["art-2"]

    body = search_on_screen(client, norm=two_regimes.old, article="2",
                            reference_date=two_regimes.before_v)

    items = result_items(results_block(body))
    assert list(items) == [unit.pk]
    item = items[unit.pk]
    assert f'<blockquote class="literal">{literal(unit)}</blockquote>' in item
    assert two_regimes.old.citation in summary(item)
    assert html.escape(unit.path) in summary(item)
    assert "Régimen específico" in summary(item)
    original = reverse("norms:original", args=[two_regimes.old_body.pk])
    assert f'href="{original}' in item
    assert "Abrir el documento original" in item
    assert REPEALED_MARK not in item


def test_article_1_in_body_and_annex_shows_both_with_their_path(client, read_user,
                                                                two_regimes):
    """REQ-010: "artículo 1" de una norma con artículo 1 en el cuerpo y en el anexo
    muestra las dos unidades, cada una con su ruta y su texto, en archivos distintos."""
    log_in(client)

    body = search_on_screen(client, norm=two_regimes.new, article="1",
                            reference_date=two_regimes.after_v)

    items = result_items(results_block(body))
    body_art = two_regimes.new_units["art-1"]
    annex_art = two_regimes.new_units["anexo/art-1"]
    assert list(items) == [body_art.pk, annex_art.pk]
    for unit in (body_art, annex_art):
        assert html.escape(unit.path) in summary(items[unit.pk])
        assert literal(unit) in items[unit.pk]
    assert reverse("norms:original", args=[two_regimes.new_body.pk]) in items[body_art.pk]
    assert reverse("norms:original", args=[two_regimes.new_annex.pk]) \
        in items[annex_art.pk]


def test_pdf_original_link_goes_to_the_unit_page(client, read_user, make_norm,
                                                 make_document, make_reading):
    """REQ-010: en un PDF, el enlace al original lleva a la página de la unidad y se
    abre en otra pestaña."""
    norm = make_norm(citation="Resolución sintética 12/20")
    document = make_document(norm, file_format="pdf")
    unit = make_reading(document, [
        {"key": "art-3", "text": "ARTICULO 3.- Texto sintético.", "page_start": 7,
         "page_end": 7},
    ]).units_by_key["art-3"]
    log_in(client)

    body = search_on_screen(client, norm=norm, article="3",
                            reference_date=date(2024, 1, 1))

    item = result_items(results_block(body))[unit.pk]
    url = reverse("norms:original", args=[document.pk]) + "#page=7"
    assert f'<a href="{url}" target="_blank" rel="noopener">' in item


# --- Fecha de autorización y régimen (REQ-020) -------------------------------------------


def test_repealed_article_is_marked_after_repeal_and_not_before(client, read_user,
                                                                two_regimes):
    """REQ-010, REQ-020: el artículo 1 de un régimen derogado se muestra marcado como
    derogado, con la norma que lo derogó y desde cuándo, con una fecha posterior a la
    derogación, y sin la marca con una anterior; en los dos casos la página indica la
    fecha y el régimen aplicado."""
    log_in(client)

    after = results_block(search_on_screen(client, norm=two_regimes.old, article="1",
                                           reference_date=two_regimes.after_v))
    before = results_block(search_on_screen(client, norm=two_regimes.old, article="1",
                                            reference_date=two_regimes.before_v))

    expected = [two_regimes.old_units["art-1"].pk, two_regimes.old_units["anexo-i/art-1"].pk]
    after_items = result_items(after)
    before_items = result_items(before)
    assert list(after_items) == expected
    assert list(before_items) == expected
    for item in after_items.values():
        assert REPEALED_MARK in summary(item)
        assert (f"Texto derogado desde el 01/01/2023 por {two_regimes.new.citation}."
                in item)
    for item in before_items.values():
        assert REPEALED_MARK not in item
    assert ("Procedimiento autorizado el 20/05/2024 · "
            f"Régimen aplicado: {two_regimes.new.citation}") in after
    assert ("Procedimiento autorizado el 15/03/2021 · "
            f"Régimen aplicado: {two_regimes.old.citation}") in before


def test_search_runs_without_regime_and_says_there_are_no_results(client, read_user,
                                                                  two_regimes):
    """REQ-020: a diferencia de la consulta, la búsqueda se ejecuta aunque no haya
    régimen a la fecha; la línea lo dice y, si no hay resultados para esa fecha, la
    pantalla también lo dice. La búsqueda queda registrada."""
    log_in(client)

    block = results_block(search_on_screen(client, norm=two_regimes.old, article="1",
                                           reference_date=two_regimes.before_all))

    assert f"Procedimiento autorizado el 10/01/2001 · {NO_REGIME_TEXT}" in block
    assert NO_RESULTS_TEXT in block
    assert result_items(block) == {}
    [event] = search_events()
    assert event.detail["regime"] == []
    assert event.detail["units"] == []


def test_future_date_is_rejected_and_not_searched(client, read_user, two_regimes,
                                                  monkeypatch):
    """REQ-020: una fecha posterior al día se rechaza en el formulario de búsqueda con su
    texto; no se busca ni se registra."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)
    events_before = AuditEvent.objects.count()

    body = search_on_screen(client, norm=two_regimes.old, article="1",
                            reference_date="2026-10-04")

    assert FUTURE_DATE_ERROR in body
    assert date_value(body, "search-reference_date") == "2026-10-04"
    assert '<section class="search-results"' not in body
    assert AuditEvent.objects.count() == events_before


def test_empty_date_searches_with_today(client, read_user, two_regimes, monkeypatch):
    """REQ-020: con el campo de fecha vacío, la búsqueda se hace con la fecha del día en
    hora de Buenos Aires."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)

    block = results_block(search_on_screen(client, norm=two_regimes.new, article="1"))

    assert "Procedimiento autorizado el 03/10/2026" in block
    [event] = search_events()
    assert event.detail["reference_date"] == "2026-10-03"


def test_result_page_brings_the_search_date_in_both_fields(client, read_user,
                                                           two_regimes):
    """REQ-020: la página que muestra los resultados trae la fecha de esa búsqueda en el
    campo de la búsqueda y en el de la pregunta."""
    log_in(client)

    body = search_on_screen(client, norm=two_regimes.old, article="1",
                            reference_date=two_regimes.before_v)

    assert date_value(body, "search-reference_date") == "2021-03-15"
    assert date_value(body, "reference_date") == "2021-03-15"


def test_saved_query_page_brings_its_date_in_the_search_field(client, read_user,
                                                              two_regimes, fake_ai):
    """REQ-020: la página de una consulta guardada trae la fecha de esa consulta también
    en el campo de fecha de la búsqueda."""
    log_in(client)
    response = client.post("/", {"question": "¿Algo?",
                                 "reference_date": two_regimes.before_v.isoformat()})

    body = client.get(response["Location"]).content.decode()

    assert date_value(body, "search-reference_date") == "2021-03-15"


# --- Por palabras (REQ-010) -------------------------------------------------------------


def test_words_without_accents_find_text_with_accents(client, read_user, two_regimes):
    """REQ-010: una búsqueda por palabras sin tildes encuentra el texto con tildes, en
    cualquier norma o solo en la elegida."""
    log_in(client)
    annex_art = two_regimes.new_units["anexo/art-2"]

    anywhere = result_items(results_block(search_on_screen(
        client, words="garantia", reference_date=two_regimes.after_v)))
    in_norm = result_items(results_block(search_on_screen(
        client, norm=two_regimes.old, words="garantia",
        reference_date=two_regimes.after_v)))

    assert list(anywhere) == [annex_art.pk]
    assert literal(annex_art) in anywhere[annex_art.pk]
    assert in_norm == {}


# --- Vínculos y cambios (REQ-006) -------------------------------------------------------


def test_link_is_shown_from_either_norm(client, read_user, two_regimes):
    """REQ-006: al ver una unidad de cualquiera de las dos normas vinculadas se muestra
    el vínculo, en el sentido que corresponde y con su fecha."""
    log_in(client)

    old_item = result_items(results_block(search_on_screen(
        client, norm=two_regimes.old, article="2", reference_date=two_regimes.after_v)))
    new_item = result_items(results_block(search_on_screen(
        client, norm=two_regimes.new, article="2", reference_date=two_regimes.after_v)))

    [old_markup] = old_item.values()
    assert (f"Es derogada por {two_regimes.new.citation}, desde el 01/01/2023."
            in old_markup)
    for markup in new_item.values():
        assert (f"Deroga {two_regimes.old.citation}, desde el 01/01/2023."
                in markup)


def test_change_in_force_is_shown_with_the_text_that_brings_it(
    client, read_user, make_norm, make_document, make_reading, make_relation
):
    """REQ-006, REQ-010: una unidad modificada a la fecha muestra el cambio, desde
    cuándo y el texto literal de la unidad que lo trae; antes de la fecha del cambio no
    lo muestra."""
    target = make_norm(citation="Resolución sintética 1/10")
    target_unit = make_reading(make_document(target), [
        ("art-5", "ARTICULO 5.- El plazo sintético es de diez días."),
        ("art-5/inc-a", "a) inciso sintético del plazo."),
    ]).units_by_key["art-5"]
    source = make_norm(citation="Resolución sintética 2/15")
    source_unit = make_reading(make_document(source), [
        ("art-1", "ARTICULO 1.- Sustitúyese el inciso a) sintético."),
    ]).units_by_key["art-1"]
    make_relation(source, target, "modifica", source_unit_key="art-1",
                  target_unit_key="art-5/inc-a", effective_date=date(2015, 3, 1))
    log_in(client)

    after = result_items(results_block(search_on_screen(
        client, norm=target, article="5", reference_date=date(2016, 1, 1))))
    before = result_items(results_block(search_on_screen(
        client, norm=target, article="5", reference_date=date(2014, 1, 1))))

    item = after[target_unit.pk]
    assert ("Modificación de «Artículo 5 › Inciso a» desde el 01/03/2015, por "
            f"{source.citation} · Artículo 1.") in item
    assert f'<blockquote class="literal">{literal(source_unit)}</blockquote>' in item
    assert "Modificación" not in before[target_unit.pk]
    assert literal(source_unit) not in before[target_unit.pk]


def test_each_text_is_shown_once_with_its_own_anchor(
    client, read_user, make_norm, make_document, make_reading, make_relation
):
    """REQ-010: un texto se muestra una sola vez por página: si la unidad que trae un
    cambio también es un resultado, el cambio lleva a ella. Las anclas `texto-N` no se
    repiten."""
    target = make_norm(citation="Resolución sintética 3/12")
    target_unit = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Plazo sintético original."),
    ]).units_by_key["art-1"]
    source = make_norm(citation="Resolución sintética 4/13")
    source_unit = make_reading(make_document(source), [
        ("art-2", "ARTICULO 2.- Sustitúyese el plazo sintético del artículo 1."),
    ]).units_by_key["art-2"]
    make_relation(source, target, "modifica", source_unit_key="art-2",
                  target_unit_key="art-1", effective_date=date(2012, 6, 1))
    log_in(client)

    body = search_on_screen(client, words="plazo", reference_date=date(2020, 1, 1))

    block = results_block(body)
    assert list(result_items(block)) == [target_unit.pk, source_unit.pk]
    assert block.count(literal(source_unit)) == 1
    assert f'href="#texto-{source_unit.pk}"' in block
    anchors = re.findall(r'id="(texto-\d+)"', body)
    assert len(anchors) == len(set(anchors))
    assert set(anchors) == {f"texto-{target_unit.pk}", f"texto-{source_unit.pk}"}


# --- Formulario --------------------------------------------------------------------------


@pytest.mark.parametrize("data", [
    {"article": "1"},
    {},
    {"article": "1", "words": "garantía", "with_norm": True},
])
def test_incomplete_or_mixed_search_is_marked_and_not_run(client, read_user, two_regimes,
                                                          data):
    """REQ-010: un número de artículo sin norma, un formulario vacío o artículo y
    palabras a la vez se marcan en el formulario en lenguaje llano, y no se busca ni se
    registra."""
    log_in(client)
    events_before = AuditEvent.objects.count()

    body = search_on_screen(
        client, norm=two_regimes.old if data.get("with_norm") else None,
        article=data.get("article", ""), words=data.get("words", ""),
        reference_date=two_regimes.after_v,
    )

    assert 'class="form-error"' in body
    assert '<section class="search-results"' not in body
    assert AuditEvent.objects.count() == events_before


def test_search_page_requires_session(client, two_regimes):
    """REQ-016, REQ-010: buscar exige sesión iniciada."""
    response = client.post(reverse("queries:search"),
                           {"search-words": "sintético"})

    assert response.status_code == 302
    assert search_events() == []


# --- Registro de la búsqueda (REQ-012) ---------------------------------------------------


def test_search_is_recorded_with_terms_date_regime_and_results(client, read_user,
                                                               two_regimes):
    """REQ-012: la búsqueda queda en el registro con el usuario, el canal, el tipo, sus
    términos, su fecha de autorización, su régimen y sus resultados con la marca de
    derogada, y la versión de la normativa."""
    log_in(client)

    search_on_screen(client, norm=two_regimes.old, article="1",
                     reference_date=two_regimes.after_v)

    [event] = search_events()
    assert event.user == read_user
    assert event.channel == Channel.SCREEN
    assert event.outcome == Outcome.OK
    detail = event.detail
    assert detail["kind"] == "article"
    assert detail["terms"] == {"norm": two_regimes.old.pk,
                               "norm_name": two_regimes.old.citation,
                               "article": "1", "words": ""}
    assert detail["reference_date"] == "2024-05-20"
    assert detail["regime"] == [{"norm": two_regimes.new.pk,
                                 "name": two_regimes.new.citation}]
    assert detail["units"] == [
        {"unit": two_regimes.old_units[key].pk, "repealed": True,
         "repealed_by": {"relation": two_regimes.repeal.pk,
                         "norm": two_regimes.new.pk, "since": "2023-01-01"}}
        for key in ("art-1", "anexo-i/art-1")
    ]
    assert detail["notices"] == []


def test_words_search_is_recorded_with_its_words(client, read_user, two_regimes):
    """REQ-012: una búsqueda por palabras registra sus palabras, la norma elegida (o
    ninguna) y las unidades devueltas sin la marca cuando no están derogadas."""
    log_in(client)

    search_on_screen(client, words="garantia", reference_date=two_regimes.after_v)

    [event] = search_events()
    assert event.detail["kind"] == "words"
    assert event.detail["terms"] == {"norm": None, "norm_name": None, "article": "",
                                     "words": "garantia"}
    assert event.detail["units"] == [
        {"unit": two_regimes.new_units["anexo/art-2"].pk, "repealed": False,
         "repealed_by": None}]


# --- Función de búsqueda -----------------------------------------------------------------


def test_service_returns_results_and_records_with_given_channel(read_write_user,
                                                                two_regimes):
    """REQ-010, REQ-012: los dos roles pueden buscar; la función devuelve los resultados
    con el régimen aplicado y registra el canal recibido."""
    outcome = services.search(read_write_user, two_regimes.before_v,
                              norm_id=two_regimes.old.pk, article="2",
                              channel=Channel.COMMAND)

    assert [r.unit_id for r in outcome.results] == [two_regimes.old_units["art-2"].pk]
    assert outcome.reference_date == two_regimes.before_v
    assert outcome.regime == [{"norm": two_regimes.old.pk,
                               "name": two_regimes.old.citation}]
    [event] = search_events()
    assert event.channel == Channel.COMMAND
    assert event.user == read_write_user


def test_service_rejects_without_role_and_records_rejection(two_regimes):
    """REQ-016, REQ-012: sin un usuario con rol, la función no busca; queda el hecho
    `rejected` y ningún hecho `search`."""
    with pytest.raises(RoleRejected):
        services.search(AnonymousUser(), two_regimes.after_v, words="sintético")

    assert search_events() == []
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 1


def test_service_validates_date_and_terms(read_user, two_regimes, monkeypatch):
    """REQ-020, REQ-010: la función valida la fecha igual que la consulta y no busca sin
    términos; en los dos casos no registra la búsqueda."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)

    with pytest.raises(services.FutureDate):
        services.search(read_user, date(2026, 10, 4), words="sintético")
    with pytest.raises(services.QueryRefused):
        services.search(read_user, two_regimes.after_v, words="   ")
    with pytest.raises(services.QueryRefused):
        services.search(read_user, two_regimes.after_v, article="1")

    assert search_events() == []


# --- Lenguaje y recursos propios ---------------------------------------------------------


def test_search_page_has_no_internal_names_or_external_references(client, read_user,
                                                                  two_regimes):
    """REQ-010: la página de resultados no muestra nombres internos y funciona sin
    conexión: sin direcciones externas ni scripts o estilos en línea, con la política de
    contenido propia."""
    log_in(client)

    response = client.post(reverse("queries:search"), {
        "search-norm": two_regimes.old.pk, "search-article": "1",
        "search-reference_date": two_regimes.after_v.isoformat()})

    body = response.content.decode()
    assert response["Content-Security-Policy"] == "default-src 'self'"
    text = re.sub(r"<[^>]+>", " ", body)
    for name in INTERNAL_NAMES:
        assert name not in text, name
    assert not re.search(r"""(src|href|action)\s*=\s*["']?(https?:)?//""", body, re.I)
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body)
    assert "<style" not in body
    assert not re.search(r"\sstyle\s*=", body)
