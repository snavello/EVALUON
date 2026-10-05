"""Pantalla e impresión de lo que cambian las circulares (REQ-031, REQ-032; plan 003, "Pantalla
e impresión (T-116)"; ADR-0023).

Pliego y circulares sintéticos, con textos inventados (P4). Las fuentes se crean a mano en la
base, como las deja la propuesta; sin modelo real.
"""

import html
import io
import re
from datetime import date

import pdfplumber
import pytest
from django.test import Client
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import export
from evaluon.tenders import models as m
from evaluon.tenders.services import matrix_page
from tests.conftest import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    GARANTIA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db

LEGEND = "BORRADOR INCOMPLETO"
NEW_TEXT = "La bolsa tendrá cuarenta litros de capacidad."
NEW_CLAUSE = "Los oferentes deberán acreditar un seguro de caución vigente."
CIRCULAR_DATE = date(2025, 11, 20)


@pytest.fixture
def case(operator_user, script):  # noqa: F811
    """Un borrador propuesto de un pliego de tres renglones, más una circular fechada con un
    texto nuevo y otra con una cláusula nueva."""
    procedure = make_procedure(operator_user)
    pliego = load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when("Bolsa de diez kilogramos", item(technical=["2"]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    version = requested.run.version
    circular = load_and_read(
        operator_user, procedure,
        tender_pdf([[para("CIRCULAR MODIFICATORIA N° 1"),
                     para("1. Se modifica el renglón 2.", f"1.1. {NEW_TEXT}"),
                     para("2. Se agrega una condición.", f"2.1. {NEW_CLAUSE}")]]),
        kind=m.DocumentKind.CIRCULAR_MODIFICATORIA, title="Circular Uno",
        issued_on=CIRCULAR_DATE)
    return {"procedure": procedure, "pliego": pliego, "version": version,
            "circular": circular}


def segment_with(document, text):
    return m.Segment.objects.filter(reading__document=document, text__contains=text).first()


def span(segment, text):
    start = segment.char_start + segment.text.index(text)
    return start, start + len(text)


def add_source(requirement, quote, circular, text, *, original=None, effect="modifica"):
    """Una fuente de la circular sobre una cita; `original` es `(tramo, texto)` del anexo."""
    segment = segment_with(circular, text)
    start, end = span(segment, text)
    fields = {}
    if original is not None:
        o_segment, o_text = original
        o_start, o_end = span(o_segment, o_text)
        fields = {"original_segment": o_segment, "original_char_start": o_start,
                  "original_char_end": o_end}
    return m.RequirementSource.objects.create(
        requirement=requirement, quote=quote, effect=effect, segment=segment,
        char_start=start, char_end=end, text=text, issued_on=circular.issued_on, **fields)


def technical_row(version):
    return version.requirements.get(category="tecnico", items=[2])


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    return html.unescape(response.content.decode())


def squash(text):
    return " ".join(text.split())


def pdf_pages(data):
    with pdfplumber.open(io.BytesIO(data)) as document:
        return [" ".join((page.extract_text() or "").split()) for page in document.pages]


def annex_original(case):
    """Un tramo del pliego que hace de anexo sin requisitos, con su recorte."""
    segment = segment_with(case["pliego"], "Los bienes tienen vencimiento")
    return segment, "Los bienes tienen vencimiento mayor a once meses."


# --- El original en un anexo sin requisitos ------------------------------------------------------


def test_original_in_an_annex_is_shown_from_that_stretch(client, operator_user, case):
    """REQ-031: una fuente con original en un anexo sin requisitos muestra como "Texto
    original" el tramo del anexo (literal, con su documento y página) y como vigente el de la
    circular con su documento y fecha."""
    version = case["version"]
    row = version.requirements.filter(category="economico").first()
    quote = row.quotes.get()
    annex_segment, annex_text = annex_original(case)
    add_source(row, quote, case["circular"], NEW_TEXT, original=(annex_segment, annex_text))
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[version.pk])))

    assert "Texto vigente, según la circular del 20/11/2025" in page
    assert f'<blockquote class="literal">{NEW_TEXT}</blockquote>' in page
    assert "Circular Uno" in page
    assert f'<blockquote class="literal">{annex_text}</blockquote>' in page
    original_label = page.index("Texto original")
    assert page.index(annex_text) > original_label
    assert 'href="' + reverse("tenders:document_original", args=[case["pliego"].pk]) in page


def test_the_original_must_be_of_the_pliego_not_of_the_circular(client, operator_user, case):
    """REQ-031, T-114: un original que cae en la lectura de la propia circular no es del
    pliego: no se muestra como texto original (se sigue viendo la cita)."""
    version = case["version"]
    row = version.requirements.filter(category="economico").first()
    quote = row.quotes.get()
    bad = segment_with(case["circular"], NEW_CLAUSE)
    add_source(row, quote, case["circular"], NEW_TEXT, original=(bad, NEW_CLAUSE))
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[version.pk])))

    assert f'<blockquote class="literal">{NEW_CLAUSE}</blockquote>' not in page
    assert f'<blockquote class="literal">{quote.text}</blockquote>' in page
    assert "Texto original del pliego" in page


def test_a_source_without_original_fields_is_seen_as_before(client, operator_user, case):
    """REQ-031: una fuente sin los campos del original (versión de antes) muestra la cita
    como texto original, igual que siempre."""
    version = case["version"]
    row = version.requirements.filter(category="economico").first()
    quote = row.quotes.get()
    add_source(row, quote, case["circular"], NEW_TEXT)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[version.pk])))

    assert "Texto original del pliego:" in page
    assert f'<blockquote class="literal">{quote.text}</blockquote>' in page


# --- Un cambio sobre varias citas del mismo requisito ---------------------------------------------


def two_quote_technical(case):
    """La fila técnica del renglón 2 con dos citas, y una fuente por cada una."""
    row = technical_row(case["version"])
    quotes = list(row.quotes.order_by("order"))
    assert len(quotes) >= 2
    annex = annex_original(case)
    for quote in quotes:
        add_source(row, quote, case["circular"], NEW_TEXT, original=annex)
    return row, quotes


def test_a_change_over_several_quotes_of_a_requirement_is_shown_once(
        client, operator_user, case):
    """REQ-031: el cambio de una circular sobre varias citas del mismo requisito se muestra
    una vez; las otras citas indican que lo alcanza."""
    row, quotes = two_quote_technical(case)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[case["version"].pk])))

    assert page.count(f'<blockquote class="literal">{NEW_TEXT}</blockquote>') == 1
    assert page.count("Alcanza a") == 1 and f"Alcanza a {len(quotes)} citas" in page
    assert page.count("Alcanzada por el cambio mostrado") == len(quotes) - 1


def test_the_service_keeps_the_change_on_the_first_quote_only(operator_user, case):
    """REQ-031: en los datos de la página, la primera cita lleva el cambio con su alcance y
    las demás quedan marcadas."""
    row, quotes = two_quote_technical(case)

    page = matrix_page.matrix_page(operator_user, case["version"].pk)

    shown = next(r for r in page.technical if r.requirement == row)
    assert shown.quotes[0].current.reach == len(quotes)
    assert shown.quotes[0].current.original.text == annex_original(case)[1]
    assert all(q.current is None and q.covered for q in shown.quotes[1:])


# --- Un requisito agregado por una circular -------------------------------------------------------


def circular_requirement(case):
    """Una fila formal agregada por la circular, con su cita en el tramo de la circular."""
    version = case["version"]
    number = version.requirements.count() + 1
    segment = segment_with(case["circular"], NEW_CLAUSE)
    start, end = span(segment, NEW_CLAUSE)
    requirement = m.Requirement.objects.create(
        version=version, number=number, category="formal", items=[], origin="circular",
        state="propuesto", proposed={}, passes=[])
    m.RequirementQuote.objects.create(
        requirement=requirement, order=1, segment=segment, char_start=start, char_end=end,
        text=NEW_CLAUSE, scope="")
    return requirement


def test_a_requirement_added_by_a_circular_shows_its_document_and_date(
        client, operator_user, case):
    """REQ-031: un requisito de origen circular muestra "Agregado por <documento> del
    <fecha>", tomados del tramo de su cita."""
    circular_requirement(case)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[case["version"].pk])))

    assert "Agregado por Circular Uno del 20/11/2025" in page
    assert f'<blockquote class="literal">{NEW_CLAUSE}</blockquote>' in page


# --- Impresión y PDF -----------------------------------------------------------------------------------


def with_everything(case):
    row = case["version"].requirements.filter(category="economico").first()
    add_source(row, row.quotes.get(), case["circular"], NEW_TEXT, original=annex_original(case))
    two_quote_technical(case)
    circular_requirement(case)
    # Copias de un requisito para que el PDF pase de una página.
    originals = list(case["version"].requirements.filter(category="economico",
                                                         origin="pliego")[:1]) or [row]
    number = case["version"].requirements.count()
    for _ in range(25):
        for original in originals:
            quotes = list(original.quotes.all())
            number += 1
            original.pk = None
            original.number = number
            original.save()
            for quote in quotes:
                quote.pk = None
                quote.requirement = original
                quote.save()


def test_the_print_view_shows_the_original_the_single_change_and_the_addition(
        client, operator_user, case):
    """REQ-031, REQ-032: la vista de impresión lleva el original del anexo, el cambio una
    sola vez y "Agregado por …", sin enlaces de edición, y la leyenda de borrador."""
    with_everything(case)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:print", args=[case["version"].pk])))

    assert LEGEND in page
    assert annex_original(case)[1] in page
    assert page.count(f'<blockquote class="literal">{NEW_TEXT}</blockquote>') == 2  # fila 1 y fila 2
    assert "Agregado por Circular Uno del 20/11/2025" in page
    assert "Alcanza a" in page
    assert "<form" not in page


def test_every_page_of_the_draft_pdf_has_the_legend_and_the_texts(operator_user, case):
    """REQ-032: cada página del PDF del borrador lleva "BORRADOR INCOMPLETO"; el PDF lleva el
    original del anexo, el cambio de la circular y "Agregado por …"."""
    with_everything(case)

    data, _ = export.export_pdf(operator_user, case["version"].pk)

    pages = pdf_pages(data)
    assert len(pages) >= 2
    for number, text in enumerate(pages, start=1):
        assert LEGEND in text, f"falta la leyenda en la página {number}"
    everything = " ".join(pages)
    assert annex_original(case)[1] in everything
    assert NEW_TEXT in everything
    assert "Agregado por Circular Uno del 20/11/2025" in everything


def test_the_export_of_this_matrix_is_recorded(client, operator_user, case):
    """P6: exportar la matriz con cambios de circulares deja `matrix_export` con la huella."""
    with_everything(case)
    log_in(client, operator_user)

    response = client.get(reverse("tenders:pdf", args=[case["version"].pk]))
    b"".join(response.streaming_content)

    event = AuditEvent.objects.get(event_type=EventType.MATRIX_EXPORT)
    assert event.outcome == Outcome.OK and event.detail["legend"] is True
    assert event.detail["version"] == case["version"].pk


# --- Sin recursos externos y con formularios protegidos --------------------------------------------


def test_the_pages_with_changes_refer_to_no_external_address(client, operator_user, case):
    """P4: las páginas con estos casos no referencian direcciones externas."""
    with_everything(case)
    log_in(client, operator_user)
    for name in ("matrix", "print"):
        body = client.get(reverse(f"tenders:{name}", args=[case["version"].pk])).content
        assert not re.search(r"(https?:)?//[a-z0-9]", body.decode(), re.IGNORECASE), name


def test_forms_of_the_matrix_with_changes_need_the_csrf_token(operator_user, case):
    """REQ-031: con la verificación de CSRF activa, el formulario de quitar un requisito de
    una fila con cambios falla sin la marca y funciona con la de la página."""
    with_everything(case)
    row = case["version"].requirements.filter(category="economico").first()
    client = Client(enforce_csrf_checks=True)
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("tenders:review_remove", args=[row.pk])

    assert client.post(url).status_code == 403
    page = client.get(reverse("tenders:matrix", args=[case["version"].pk]))
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"',
                      page.content.decode()).group(1)
    response = client.post(url, {"csrfmiddlewaretoken": token})
    assert response.status_code in (200, 302)


# --- Defensas de lo que se muestra como original y del agrupado -----------------------------------------


def shown_quote(operator_user, case, row):
    page = matrix_page.matrix_page(operator_user, case["version"].pk)
    rows = [x for g in page.groups for x in g.rows] + page.technical
    return next(r for r in rows if r.requirement == row).quotes[0]


def test_an_original_from_another_procedure_is_not_shown(operator_user, case):
    """REQ-031, T-114: un original que es un tramo del pliego de otro procedimiento no se
    muestra como texto original."""
    other = make_procedure(operator_user)
    foreign = load_and_read(operator_user, other, three_items_pdf(), title="Pliego ajeno")
    segment = segment_with(foreign, "Los bienes tienen vencimiento")
    row = case["version"].requirements.filter(category="economico").first()
    add_source(row, row.quotes.get(), case["circular"], NEW_TEXT,
               original=(segment, "Los bienes tienen vencimiento mayor a once meses."))

    quote = shown_quote(operator_user, case, row)

    assert quote.current is not None and quote.current.original is None


def test_an_original_with_a_range_outside_its_stretch_is_not_shown(operator_user, case):
    """REQ-031, T-114: un rango que se pasa del texto de la lectura, o que empieza fuera del
    tramo, no es un recorte válido: no se muestra como original."""
    row = case["version"].requirements.filter(category="economico").first()
    segment, text = annex_original(case)
    source = add_source(row, row.quotes.get(), case["circular"], NEW_TEXT,
                        original=(segment, text))
    reading = segment.reading
    assert shown_quote(operator_user, case, row).current.original is not None

    source.original_char_end = len(reading.canonical_text) + 10
    source.save()
    assert shown_quote(operator_user, case, row).current.original is None

    source.original_char_start = segment.char_end
    source.original_char_end = segment.char_end + 5
    source.save()
    assert shown_quote(operator_user, case, row).current.original is None


def test_sources_with_a_different_effect_are_not_grouped(operator_user, case):
    """REQ-031: dos fuentes del mismo tramo con efectos distintos sobre el mismo requisito
    se ven las dos: el agrupado exige el mismo efecto."""
    row = technical_row(case["version"])
    first, second = list(row.quotes.order_by("order"))[:2]
    add_source(row, first, case["circular"], NEW_TEXT, effect="modifica")
    add_source(row, second, case["circular"], NEW_TEXT, effect="aclara")

    page = matrix_page.matrix_page(operator_user, case["version"].pk)

    shown = next(r for r in page.technical if r.requirement == row)
    assert shown.quotes[0].current.effect == "modifica" and shown.quotes[0].current.reach == 1
    assert [n.effect for n in shown.quotes[1].notes] == ["aclara"]
    assert not shown.quotes[1].covered


# --- La cadena completa de circulares sobre una misma condición (T-126) ---------------------------

FIRST_TEXT = "La bolsa tendrá treinta litros de capacidad."
SECOND_TEXT = "La bolsa tendrá treinta y cinco litros de capacidad."
THIRD_TEXT = "La bolsa tendrá cuarenta litros de capacidad."


def chain_case(operator_user, case):
    """Tres circulares inventadas sobre la misma cita del renglón 2, con fechas distintas;
    se crean fuera de orden para comprobar que la pantalla ordena por fecha."""
    row = technical_row(case["version"])
    quote = row.quotes.order_by("order").first()
    circulars = []
    for number, (text, day) in enumerate(
            [(THIRD_TEXT, date(2025, 12, 10)), (FIRST_TEXT, date(2025, 11, 20)),
             (SECOND_TEXT, date(2025, 12, 1))], start=1):
        circulars.append(load_and_read(
            operator_user, case["procedure"],
            tender_pdf([[para(f"CIRCULAR MODIFICATORIA N° {number + 1}"),
                         para("1. Se modifica el renglón 2.", f"1.1. {text}")]]),
            kind=m.DocumentKind.CIRCULAR_MODIFICATORIA, title=f"Circular {number + 1}",
            issued_on=day))
    for circular, text in zip(circulars, (THIRD_TEXT, FIRST_TEXT, SECOND_TEXT)):
        add_source(row, quote, circular, text)
    return row, quote


def positions(page, texts):
    return [page.index(f'<blockquote class="literal">{t}</blockquote>') for t in texts]


def test_the_chain_of_three_circulars_is_shown_in_date_order(client, operator_user, case):
    """REQ-031: tres circulares sobre la misma cita se muestran en orden de fecha: el
    original del pliego, los dos textos intermedios con su fecha y al final el vigente."""
    row, quote = chain_case(operator_user, case)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[case["version"].pk])))

    order = positions(page, [quote.text, FIRST_TEXT, SECOND_TEXT, THIRD_TEXT])
    assert order == sorted(order)
    assert "Modifica (20/11/2025)" in page and "Modifica (01/12/2025)" in page
    assert page.count("Texto vigente, según la circular del 10/12/2025") == 1
    assert page.count("Texto vigente") == 1
    assert page.index("Texto vigente") > order[2]


def test_the_service_gives_the_earlier_changes_and_the_current_one(operator_user, case):
    """REQ-031: en los datos de la página, la cita lleva las modificaciones anteriores por
    fecha y la última como vigente."""
    row, quote = chain_case(operator_user, case)

    page = matrix_page.matrix_page(operator_user, case["version"].pk)

    shown = next(r for r in page.technical if r.requirement == row).quotes[0]
    assert [s.text for s in shown.earlier] == [FIRST_TEXT, SECOND_TEXT]
    assert shown.current.text == THIRD_TEXT


def test_the_print_view_and_the_pdf_show_the_whole_chain(client, operator_user, case):
    """REQ-031, REQ-032: la impresión y el PDF llevan la cadena completa en orden, el texto
    literal y la leyenda de borrador en cada página."""
    row, quote = chain_case(operator_user, case)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:print", args=[case["version"].pk])))

    order = positions(page, [quote.text, FIRST_TEXT, SECOND_TEXT, THIRD_TEXT])
    assert order == sorted(order) and LEGEND in page
    data, _ = export.export_pdf(operator_user, case["version"].pk)
    pages = pdf_pages(data)
    everything = " ".join(pages)
    assert all(LEGEND in text for text in pages)
    found = [everything.index(squash(t)) for t in (FIRST_TEXT, SECOND_TEXT, THIRD_TEXT)]
    assert found == sorted(found)


def test_a_circular_that_annuls_another_is_shown_as_such(client, operator_user, case):
    """REQ-031: una circular que suprime lo que cambió otra se muestra como "Suprime" con su
    fecha, junto a la cadena, y no se confunde con un texto vigente."""
    row, quote = chain_case(operator_user, case)
    annulling = load_and_read(
        operator_user, case["procedure"],
        tender_pdf([[para("CIRCULAR MODIFICATORIA N° 5"),
                     para("1. Se deja sin efecto.", "1.1. Queda sin efecto el cambio anterior.")]]),
        kind=m.DocumentKind.CIRCULAR_MODIFICATORIA, title="Circular 5",
        issued_on=date(2025, 12, 20))
    add_source(row, quote, annulling, "Queda sin efecto el cambio anterior.",
               effect="suprime")
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:matrix", args=[case["version"].pk])))

    assert "Suprime (20/12/2025)" in page
    assert '<blockquote class="literal">Queda sin efecto el cambio anterior.</blockquote>' in page
    assert page.count("Texto vigente") == 1


def test_a_single_change_keeps_the_previous_layout(operator_user, case):
    """REQ-031: con una sola circular no hay modificaciones anteriores."""
    row = technical_row(case["version"])
    add_source(row, row.quotes.order_by("order").first(), case["circular"], NEW_TEXT)

    page = matrix_page.matrix_page(operator_user, case["version"].pk)

    shown = next(r for r in page.technical if r.requirement == row).quotes[0]
    assert shown.earlier == [] and shown.current.text == NEW_TEXT


def test_the_chain_text_is_shown_literally(client, operator_user, case):
    """REQ-031: el texto de cada paso de la cadena sale tal cual, sin interpretarse como
    marcas."""
    row, quote = chain_case(operator_user, case)
    m.RequirementSource.objects.filter(text=FIRST_TEXT).update(text="<b>treinta</b> & litros")
    log_in(client, operator_user)

    raw = client.get(reverse("tenders:matrix", args=[case["version"].pk])).content.decode()

    assert "&lt;b&gt;treinta&lt;/b&gt; &amp; litros" in raw
    assert "<b>treinta</b>" not in raw
