"""Pantalla de consulta con sus tres bloques (T-016; plan 001, "Pantalla, acceso y
comandos", "Forma de la respuesta" y "Fecha de autorización y régimen aplicado").

Una sola página en la raíz del sitio: el formulario de la pregunta con su fecha de
autorización y, para una consulta guardada, uno de tres bloques. Las consultas se guardan
a mano, sin la función de consulta (T-019), en los tres estados. Los datos son
sintéticos (P4).
"""

import html
import re
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path

import pytest
from django.conf import settings
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils import timezone

from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.queries.forms import FUTURE_DATE_ERROR, QueryForm
from evaluon.queries.models import Query, Reason, Status
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

GROUNDED_TITLE = "Respuesta con fundamento en la normativa"
UNDETERMINED_TITLE = "No determinado"
UNDETERMINED_TEXT = "La normativa cargada no permite responder esta pregunta"
ERROR_TITLE = "No se pudo completar la consulta"
NO_REGIME_TEXT = "Para esa fecha no hay un régimen específico cargado en el sistema"
WAITING_TEXT = "Buscando en la normativa. Puede tardar hasta medio minuto."

OLD_REGIME = {"name": "Disposición AFIP 297/03"}
NEW_REGIME = {"name": "Disposición AFIP 247/2022"}

STATIC_DIR = Path(settings.BASE_DIR) / "evaluon" / "static"
EXTERNAL_IN_HTML = re.compile(r"""(src|href|action)\s*=\s*["']?(https?:)?//""", re.I)
EXTERNAL_IN_STATIC = re.compile(r"https?://|url\(\s*[\"']?//|@import", re.I)


# --- Armado de consultas guardadas ----------------------------------------------------


def log_in(client, username="lectura"):
    assert client.login(username=username, password=TEST_PASSWORD)


def save_query(user, result, question="¿Qué garantía se exige al ofertar?"):
    """Guarda una consulta terminada con su hecho `query`, como lo hará T-019."""
    status = result["status"]
    reason = result["reason"] or ""
    event = audit_services.record(
        EventType.QUERY,
        outcome=Outcome.OK,
        channel=Channel.SCREEN,
        user=user,
        detail={"question": question, "result": result},
    )
    return Query.objects.create(
        event=event,
        user=user,
        question=question,
        reference_date=date.fromisoformat(result["reference_date"]),
        corpus_version=event.corpus_version,
        status=status,
        reason=reason,
        result=result,
    )


def regime_entry(norm, name):
    return {"norm": norm.pk, "name": name}


def unit_entry(unit, name):
    return {
        "norm": name,
        "category": unit.reading.document.norm.category,
        "unit_type": unit.unit_type,
        "path": unit.path,
        "text_origin": unit.text_origin,
        "document": unit.reading.document.pk,
        "page_start": unit.page_start,
        "changes": [],
    }


def grounded_result(two_regimes):
    """Respuesta con dos afirmaciones que citan dos artículos del régimen anterior."""
    art = two_regimes.old_units["anexo-i/art-1"]
    body_art = two_regimes.old_units["art-1"]
    name = OLD_REGIME["name"]
    return {
        "query_id": None,
        "status": "grounded",
        "reason": None,
        "reference_date": two_regimes.before_v.isoformat(),
        "regime": [regime_entry(two_regimes.old, name)],
        "notices": [],
        "statements": [
            {"text": "El objeto del régimen es el sintético anterior.",
             "regimes_differ": False, "citations": [art.pk]},
            {"text": "La disposición aprueba el régimen de licitaciones.",
             "regimes_differ": False, "citations": [body_art.pk]},
        ],
        "units": {
            str(art.pk): unit_entry(art, name),
            str(body_art.pk): unit_entry(body_art, name),
        },
    }


def undetermined_result(reference_date, regime, reason="below_threshold"):
    return {
        "query_id": None,
        "status": "undetermined",
        "reason": reason,
        "reference_date": reference_date.isoformat(),
        "regime": regime,
        "notices": [],
        "statements": [],
        "units": {},
    }


def error_result(reference_date, regime, reason="timeout"):
    result = undetermined_result(reference_date, regime)
    result.update(status="error", reason=reason)
    return result


def query_page(client, query):
    response = client.get(reverse("queries:query", args=[query.pk]))
    assert response.status_code == 200
    return response.content.decode()


def result_block(body):
    """El bloque del resultado, desde su apertura hasta el cierre de la sección."""
    match = re.search(r'<section class="result [^"]*".*?</section>', body, re.S)
    assert match, "la página no muestra ningún bloque de resultado"
    return match.group(0)


def date_field_value(body):
    match = re.search(r'<input type="date" name="reference_date" value="([^"]*)"', body)
    assert match, "la página no tiene el campo de fecha del navegador"
    return match.group(1)


# --- Acceso y página sin consulta ----------------------------------------------------


def test_root_without_session_redirects_to_login(client):
    """REQ-013, REQ-016: la pantalla de consulta ocupa la raíz y, sin sesión, redirige
    al ingreso."""
    response = client.get("/")

    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL) + "?next=")


def test_saved_query_without_session_redirects_to_login(client, read_user):
    """REQ-013, REQ-016: la página de una consulta guardada también exige sesión."""
    query = save_query(read_user, undetermined_result(date(2021, 3, 15), []))

    response = client.get(reverse("queries:query", args=[query.pk]))

    assert response.status_code == 302
    assert response["Location"].startswith(resolve_url(settings.LOGIN_URL))


def test_screen_is_root_with_header_and_question_form(client, read_user):
    """REQ-013: en la raíz, una sola página con el nombre del sistema, el usuario, el
    botón "Salir" y el formulario de la pregunta; sin consulta, ningún bloque."""
    log_in(client)

    response = client.get("/")

    assert response.status_code == 200
    body = response.content.decode()
    assert reverse("queries:screen") == "/"
    assert "EVALUON" in body
    assert read_user.username in body
    assert ">Salir</button>" in body
    assert '<textarea name="question"' in body
    assert "Fecha de autorización del procedimiento" in body
    assert '<form method="post" action="/"' in body
    assert '<section class="result ' not in body


def test_date_field_defaults_to_today_in_buenos_aires(client, read_user, monkeypatch):
    """REQ-020: sin consulta, el campo de fecha es el control de fecha del navegador y
    viene con la fecha del día en hora de Buenos Aires, no en hora universal."""
    # 02:30 en hora universal del 4 de octubre son las 23:30 del 3 en Buenos Aires.
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)

    body = client.get("/").content.decode()

    assert date_field_value(body) == "2026-10-03"


def test_screen_does_not_write_the_session(client, read_user):
    """REQ-013, REQ-016: mirar la pantalla no guarda nada en la sesión, así el tope de 8
    horas desde el ingreso no se renueva con el uso."""
    log_in(client)
    before = dict(client.session.items())
    query = save_query(read_user, undetermined_result(date(2021, 3, 15), []))

    client.get("/")
    client.get(reverse("queries:query", args=[query.pk]))
    client.post("/", {"question": "¿Algo?", "reference_date": "2999-01-01"})

    assert dict(client.session.items()) == before


# --- Validación de la fecha ------------------------------------------------------------


def test_future_date_is_marked_in_form_and_not_queried(client, read_user, monkeypatch):
    """REQ-020: una fecha posterior al día (en hora de Buenos Aires) se marca en el
    formulario con su texto y no se consulta ni deja registro."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)
    events_before = AuditEvent.objects.count()

    response = client.post(
        "/", {"question": "¿Qué garantía se exige?", "reference_date": "2026-10-04"}
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert FUTURE_DATE_ERROR == "La fecha de autorización no puede ser posterior a hoy"
    assert FUTURE_DATE_ERROR in body
    # El campo conserva lo que escribió la persona, para corregirlo.
    assert date_field_value(body) == "2026-10-04"
    assert Query.objects.count() == 0
    assert AuditEvent.objects.count() == events_before


def test_invalid_date_is_marked_in_form_and_not_queried(client, read_user):
    """REQ-020: algo que no es una fecha se marca en el formulario y no se consulta."""
    log_in(client)

    response = client.post(
        "/", {"question": "¿Qué garantía se exige?", "reference_date": "2021-02-31"}
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert 'class="form-error"' in body
    assert Query.objects.count() == 0


def test_form_accepts_today_and_empty_date_and_rejects_tomorrow(monkeypatch):
    """REQ-020: el formulario acepta la fecha del día y el campo vacío (la función de
    consulta usa entonces la del día) y rechaza el día siguiente."""
    instant = datetime(2026, 10, 4, 2, 30, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)

    today = QueryForm({"question": "¿Algo?", "reference_date": "2026-10-03"})
    empty = QueryForm({"question": "¿Algo?", "reference_date": ""})
    tomorrow = QueryForm({"question": "¿Algo?", "reference_date": "2026-10-04"})

    assert today.is_valid()
    assert today.cleaned_data["reference_date"] == date(2026, 10, 3)
    assert empty.is_valid()
    assert empty.cleaned_data["reference_date"] is None
    assert not tomorrow.is_valid()
    assert tomorrow.errors["reference_date"] == [FUTURE_DATE_ERROR]


# --- Los tres bloques ----------------------------------------------------------------


def test_grounded_query_shows_answer_with_citations_and_literal_text(
    client, read_user, two_regimes
):
    """REQ-013: una consulta con fundamento muestra su bloque con la respuesta y sus
    citas; cada cita muestra norma y ruta y despliega el texto literal de la unidad,
    igual carácter por carácter a `canonical_text[char_start:char_end]`."""
    log_in(client)
    query = save_query(read_user, grounded_result(two_regimes))

    body = query_page(client, query)
    block = result_block(body)

    assert 'class="result result-answer"' in block
    assert GROUNDED_TITLE in block
    assert html.escape(query.question) in block
    assert "El objeto del régimen es el sintético anterior." in block
    assert "La disposición aprueba el régimen de licitaciones." in block
    for key in ("anexo-i/art-1", "art-1"):
        unit = two_regimes.old_units[key]
        canonical = unit.reading.canonical_text[unit.char_start:unit.char_end]
        citation = re.search(
            rf'<details class="citation" data-unit="{unit.pk}">(.*?)</details>',
            block, re.S,
        )
        assert citation, f"falta la cita de {key}"
        assert "Disposición AFIP 297/03" in citation.group(1)
        assert html.escape(unit.path) in citation.group(1)
        literal = re.search(
            r'<blockquote class="literal">(.*?)</blockquote>', citation.group(1), re.S
        )
        assert literal.group(1) == html.escape(canonical)
    # Ni nombres internos ni textos de los otros dos bloques.
    assert "grounded" not in body
    assert UNDETERMINED_TITLE not in body
    assert ERROR_TITLE not in body


def test_undetermined_query_shows_own_notice_without_citations(client, read_user):
    """REQ-014: con `undetermined`, la página muestra un aviso propio, distinto del de
    una respuesta (título, ícono y color), y ninguna cita."""
    log_in(client)
    query = save_query(read_user, undetermined_result(date(2021, 3, 15), []))

    body = query_page(client, query)
    block = result_block(body)

    assert 'class="result result-no-answer"' in block
    assert UNDETERMINED_TITLE in block
    assert UNDETERMINED_TEXT in block
    assert "<details" not in body
    assert GROUNDED_TITLE not in body
    assert ERROR_TITLE not in body


@pytest.mark.parametrize(
    "reason", ["no_regime_at_date", "below_threshold", "model_abstained",
               "invalid_citation"],
)
def test_every_undetermined_reason_shows_the_same_notice(client, read_user, reason):
    """REQ-014: los cuatro motivos de "no determinado" se muestran igual, sin
    afirmaciones ni citas, y sin el nombre interno del motivo."""
    log_in(client)
    query = save_query(read_user, undetermined_result(date(2021, 3, 15), [], reason))

    body = query_page(client, query)

    assert UNDETERMINED_TEXT in result_block(body)
    assert "<details" not in body
    assert reason not in body
    assert "undetermined" not in body


def test_error_query_shows_failure_block(client, read_user, two_regimes):
    """REQ-014: una falla técnica no se muestra como "no determinado" ni como
    respuesta: tiene su propio bloque, sin citas."""
    log_in(client)
    regime = [regime_entry(two_regimes.old, OLD_REGIME["name"])]
    query = save_query(read_user, error_result(two_regimes.before_v, regime))

    body = query_page(client, query)
    block = result_block(body)

    assert 'class="result result-failure"' in block
    assert ERROR_TITLE in block
    assert UNDETERMINED_TEXT not in body
    assert GROUNDED_TITLE not in body
    assert "<details" not in body


def test_three_blocks_differ_in_title_icon_and_colour(client, read_user, two_regimes):
    """REQ-014: los tres bloques se distinguen a simple vista: cada uno tiene su título,
    su ícono y su clase, que la hoja de estilos pinta con un color propio."""
    log_in(client)
    regime = [regime_entry(two_regimes.old, OLD_REGIME["name"])]
    pages = {
        "answer": query_page(client, save_query(read_user, grounded_result(two_regimes))),
        "no-answer": query_page(
            client, save_query(read_user, undetermined_result(two_regimes.before_v, regime))
        ),
        "failure": query_page(
            client, save_query(read_user, error_result(two_regimes.before_v, regime))
        ),
    }

    titles, icons, colours = set(), set(), set()
    stylesheet = (STATIC_DIR / "css" / "evaluon.css").read_text(encoding="utf-8")
    for state, body in pages.items():
        block = result_block(body)
        assert f'class="result result-{state}"' in block
        title = re.search(r"<h2[^>]*>(.*?)</h2>", block, re.S).group(1)
        icon = re.search(r'<span class="result-icon" aria-hidden="true">(.*?)</span>',
                         title).group(1)
        titles.add(re.sub(r"<[^>]+>", "", title).strip())
        icons.add(icon)
        rule = re.search(rf"\.result-{state}\s*\{{(.*?)\}}", stylesheet, re.S)
        assert rule, f"la hoja de estilos no pinta el bloque {state}"
        colours.add(re.search(r"border-color:\s*([^;]+);", rule.group(1)).group(1))

    assert len(titles) == 3
    assert len(icons) == 3
    assert len(colours) == 3


# --- Fecha y régimen aplicado ----------------------------------------------------------


@pytest.mark.parametrize("state", ["grounded", "undetermined", "error"])
def test_every_block_shows_date_and_applied_regime(client, read_user, two_regimes, state):
    """REQ-020: los tres bloques llevan la línea de fecha de autorización, en
    día/mes/año, y del régimen aplicado, armada con lo guardado."""
    log_in(client)
    regime = [regime_entry(two_regimes.old, OLD_REGIME["name"])]
    result = {
        "grounded": grounded_result(two_regimes),
        "undetermined": undetermined_result(two_regimes.before_v, regime),
        "error": error_result(two_regimes.before_v, regime),
    }[state]

    block = result_block(query_page(client, save_query(read_user, result)))

    assert (
        "Procedimiento autorizado el 15/03/2021 · "
        "Régimen aplicado: Disposición AFIP 297/03"
    ) in block


def test_line_says_when_there_is_no_regime(client, read_user):
    """REQ-020: si no había régimen a la fecha, la línea lo dice."""
    log_in(client)
    query = save_query(
        read_user,
        undetermined_result(date(2001, 1, 10), [], reason="no_regime_at_date"),
    )

    block = result_block(query_page(client, query))

    assert f"Procedimiento autorizado el 10/01/2001 · {NO_REGIME_TEXT}" in block
    assert "Régimen aplicado" not in block


def test_line_names_every_regime_when_there_are_several(client, read_user, two_regimes):
    """REQ-020: si lo guardado trae más de un régimen, la línea los nombra a todos."""
    log_in(client)
    regime = [
        regime_entry(two_regimes.old, OLD_REGIME["name"]),
        regime_entry(two_regimes.new, NEW_REGIME["name"]),
    ]
    query = save_query(read_user, undetermined_result(two_regimes.after_v, regime))

    block = result_block(query_page(client, query))

    assert (
        "Procedimiento autorizado el 20/05/2024 · Regímenes aplicados: "
        "Disposición AFIP 297/03 y Disposición AFIP 247/2022"
    ) in block


def test_saved_query_brings_its_date_in_the_field(client, read_user, monkeypatch):
    """REQ-020: en la página de una consulta guardada, el campo de fecha trae la fecha
    de esa consulta y no la del día."""
    instant = datetime(2026, 10, 4, 15, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr(timezone, "now", lambda: instant)
    log_in(client)
    query = save_query(read_user, undetermined_result(date(2021, 3, 15), []))

    body = query_page(client, query)

    assert date_field_value(body) == "2021-03-15"


# --- Quién ve qué, recursos propios y espera --------------------------------------------


def test_other_user_does_not_see_the_query(client, read_user, read_write_user):
    """REQ-013, REQ-016: solo ve el resultado quien hizo la consulta; para otro usuario
    la consulta no existe."""
    query = save_query(
        read_user,
        undetermined_result(date(2021, 3, 15), []),
        question="Pregunta sintética privada de lectura",
    )
    log_in(client, "escritura")

    response = client.get(reverse("queries:query", args=[query.pk]))

    assert response.status_code == 404
    assert "Pregunta sintética privada de lectura" not in response.content.decode()


def test_missing_query_is_not_found(client, read_user):
    """REQ-013: una consulta que no existe da "no encontrada"."""
    log_in(client)

    response = client.get(reverse("queries:query", args=[999999]))

    assert response.status_code == 404


def test_pages_and_static_files_have_no_external_references(
    client, read_user, two_regimes
):
    """REQ-013: la pantalla funciona sin conexión: ninguna página ni archivo estático
    referencia direcciones externas, no hay scripts ni estilos en línea, y la cabecera
    de política de contenido está presente y solo admite el propio servidor."""
    log_in(client)
    regime = [regime_entry(two_regimes.old, OLD_REGIME["name"])]
    queries = [
        save_query(read_user, grounded_result(two_regimes)),
        save_query(read_user, undetermined_result(two_regimes.before_v, regime)),
        save_query(read_user, error_result(two_regimes.before_v, regime)),
    ]
    responses = [client.get("/"), client.post("/", {"question": ""})] + [
        client.get(reverse("queries:query", args=[q.pk])) for q in queries
    ]

    for response in responses:
        assert response.status_code == 200
        assert response["Content-Security-Policy"] == "default-src 'self'"
        body = response.content.decode()
        assert not EXTERNAL_IN_HTML.search(body)
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", body), "script en línea"
        assert "<style" not in body
        assert not re.search(r"\sstyle\s*=", body)
        assert not re.search(r"\son[a-z]+\s*=", body), "manejador de evento en línea"

    static_files = [p for p in STATIC_DIR.rglob("*") if p.is_file()]
    assert static_files
    for path in static_files:
        assert not EXTERNAL_IN_STATIC.search(path.read_text(encoding="utf-8")), path


def test_waiting_script_is_an_own_file_and_form_works_without_it(client, read_user):
    """REQ-013: la espera la maneja un script propio, servido por la aplicación, que
    desactiva el botón y muestra el aviso; sin el script el formulario es un envío
    común."""
    log_in(client)

    body = client.get("/").content.decode()

    script_src = settings.STATIC_URL + "js/consulta.js"
    assert script_src == "/static/js/consulta.js"
    assert f'<script src="{script_src}" defer></script>' in body
    # El aviso está en la página, oculto hasta que el script lo muestra.
    assert re.search(rf'<p class="waiting" id="query-waiting" hidden>\s*{WAITING_TEXT}',
                     body)
    assert '<button type="submit" id="query-submit">' in body
    script = (STATIC_DIR / "js" / "consulta.js").read_text(encoding="utf-8")
    assert "query-submit" in script and "query-waiting" in script
    assert "disabled" in script
