"""La ficha de la oferta marca los fragmentos que salen de una página leída por visión (REQ-086,
REQ-104; P3; dictamen de la 015, hallazgo 2; plan 015, T-264, barrido de las pantallas). Un
fragmento de la ficha es texto literal de la lectura de la oferta; si la página se leyó mirando su
imagen, es la transcripción del modelo y la Comisión lo compara con el original (ADR-0041). La ficha
se arma directo en la base, sin el modelo; todo el material es inventado (P4)."""

import hashlib

import pytest
from django.urls import reverse

from evaluon.offers import models as om
from tests.accounts.test_session import TEST_PASSWORD
from tests.conftest import unit_vector

pytestmark = pytest.mark.django_db

NOTICE = ("Proviene de una página con dificultades de lectura: el texto citado es la "
          "transcripción que hizo el sistema mirando su imagen y puede tener errores. "
          "Conviene que la Comisión lo vuelva a chequear.")
LINK = "Ver la imagen de la página"
MARK = "leída por visión"
SEEN = "Declaro bajo juramento (transcripción de la visión)."


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure, offer):
    return reverse("expedientes:ofertas", args=[procedure.pk]) + f"?ficha={offer.pk}"


def fragment_of(entry, order, passage, state="propuesto"):
    return om.Fragment.objects.create(
        entry=entry, order=order, passage=passage, char_start=passage.char_start,
        char_end=passage.char_end, text=passage.text, origin="sistema", state=state, proposed={})


@pytest.fixture
def card(offer, procedure, matrix, operator_user, client):
    """La ficha de la oferta: la fila 1 cita la declaración leída por visión (página 1 de una
    lectura nueva de `oferta.pdf`); la fila 2, la constancia, una página legible; y la fila 2
    tiene además un fragmento quitado que también salía de la página leída por visión."""
    document = offer.documents.get(file_name="oferta.pdf")
    other = offer.documents.get(file_name="constancia.pdf")
    seen = om.Reading.objects.create(
        document=document, sequence=2, pages={"pages": []}, canonical_text=SEEN,
        canonical_sha256=hashlib.sha256(SEEN.encode()).hexdigest(), tool_versions={},
        report={"vision": {"pages": [{"page": 1, "outcome": "read"}]}})
    by_vision = om.Passage.objects.create(
        reading=seen, order=1, key="p1/b1", page=1, char_start=0, char_end=len(SEEN), text=SEEN,
        text_origin="vision", embedding=unit_vector(7001))
    plain_reading = other.readings.get()
    plain = plain_reading.passages.get()
    sheet = om.Sheet.objects.create(
        offer=offer, matrix_version=matrix.version, number=1, channel=om.SheetChannel.SCREEN,
        readings=[{"document": document.pk, "reading": seen.pk, "sequence": 2},
                  {"document": other.pk, "reading": plain_reading.pk, "sequence": 1}],
        models_used={}, parameters={}, prompt_versions={}, requested_by=operator_user)
    first, second = list(matrix.version.requirements.order_by("number")[:2])
    one = om.SheetEntry.objects.create(sheet=sheet, requirement=first, outcome="encontrado",
                                       synthesis="Declara estar habilitado.")
    two = om.SheetEntry.objects.create(sheet=sheet, requirement=second, outcome="encontrado",
                                       synthesis="Presenta la constancia.")
    fragment_of(one, 1, by_vision)
    fragment_of(two, 1, plain)
    fragment_of(two, 2, by_vision, state="quitado")
    log_in(client, operator_user)
    return sheet, one, two, document


def block(html):
    return html[html.index('class="ficha"'):]


def row_of(html, entry, tag):
    """Desde la fila (`<tr class="fila-req" id="fila-N">`) o su detalle hasta la siguiente."""
    start = html.index(f'id="{tag}-{entry.pk}"')
    end = html.find("</tr>", start)
    return html[start:end]


def test_the_sheet_marks_the_fragment_read_by_vision_in_the_table_and_the_detail(
        client, procedure, offer, card):
    """REQ-086, REQ-104, P3: el fragmento de la página leída por visión lleva, en la fila de la
    ficha, la marca «leída por visión» junto al documento y la página, y en su detalle el aviso de
    comparar con el original y el enlace al original; el de una página legible no."""
    _, one, two, document = card
    html = block(client.get(tab(procedure, offer)).content.decode())
    original = f"{reverse('offers:document_original', args=[document.pk])}#page=1"
    row = row_of(html, one, "fila")
    assert MARK in row and f'<a href="{original}"' in row
    detail = row_of(html, one, "detalle-ficha")
    assert detail.count(NOTICE) == 1
    assert f'<a href="{original}">{LINK}</a>' in detail
    plain_row = row_of(html, two, "fila")
    assert MARK not in plain_row


def test_the_sheet_marks_a_removed_fragment_read_by_vision_and_only_that_one(
        client, procedure, offer, card):
    """REQ-086, REQ-104, P3: en «Fragmentos quitados», el que salía de una página leída por visión
    lleva el aviso; el fragmento vigente de una página legible, en la misma fila, no."""
    _, one, two, _ = card
    html = block(client.get(tab(procedure, offer)).content.decode())
    detail = row_of(html, two, "detalle-ficha")
    kept, removed = detail.split("Fragmentos quitados")
    assert NOTICE not in kept and MARK not in kept
    assert removed.count(NOTICE) == 1
    assert html.count(NOTICE) == 2  # el vigente de la fila 1 y el quitado de la fila 2


@pytest.fixture
def mixed_card(offer, procedure, matrix, operator_user, client):
    """La ficha de una lectura mixta de `oferta.pdf`: la página 1 se leyó por visión, la 2 es legible
    y la 3 la visión la descartó (la página sigue como estaba). Una fila cita cada página."""
    document = offer.documents.get(file_name="oferta.pdf")
    texts = [(1, "Página uno, transcripta por el sistema.", "vision"),
             (2, "Página dos, legible.", "pdf_text"),
             (3, "Página tres, que la visión descartó.", "ocr")]
    canonical = chr(10).join(text for _, text, _ in texts)
    reading = om.Reading.objects.create(
        document=document, sequence=2, pages={"pages": []}, canonical_text=canonical,
        canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(), tool_versions={},
        report={"vision": {"pages": [{"page": 1, "outcome": "read"},
                                     {"page": 3, "outcome": "too_illegible"}]}})
    passages, start = [], 0
    for number, text, origin in texts:
        passages.append(om.Passage.objects.create(
            reading=reading, order=number, key=f"p{number}/b1", page=number, char_start=start,
            char_end=start + len(text), text=text, text_origin=origin,
            embedding=unit_vector(7200 + number)))
        start += len(text) + 1
    sheet = om.Sheet.objects.create(
        offer=offer, matrix_version=matrix.version, number=1, channel=om.SheetChannel.SCREEN,
        readings=[{"document": document.pk, "reading": reading.pk, "sequence": 2}],
        models_used={}, parameters={}, prompt_versions={}, requested_by=operator_user)
    requirements = list(matrix.version.requirements.order_by("number")[:3])
    entries = [om.SheetEntry.objects.create(sheet=sheet, requirement=row, outcome="encontrado",
                                            synthesis=f"Página {n}.")
               for n, row in enumerate(requirements, start=1)]
    for entry, passage in zip(entries, passages, strict=True):
        fragment_of(entry, 1, passage)
    log_in(client, operator_user)
    return entries


def test_a_mixed_reading_marks_only_the_fragment_on_the_page_the_vision_read(
        client, procedure, offer, mixed_card):  # noqa: F811
    """REQ-086, REQ-104, P3: de una lectura mixta, solo el fragmento de la página 1 (leída por
    visión) lleva la marca y el aviso; los de la página 2 (legible) y la 3 (que la visión descartó),
    no."""
    first, second, third = mixed_card
    html = block(client.get(tab(procedure, offer)).content.decode())
    assert html.count(NOTICE) == 1 and html.count(MARK) == 2  # la marca de la fila y la del aviso
    for entry in (second, third):
        assert MARK not in row_of(html, entry, "fila")
        assert NOTICE not in row_of(html, entry, "detalle-ficha")
    assert NOTICE in row_of(html, first, "detalle-ficha")
