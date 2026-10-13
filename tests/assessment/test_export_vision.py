"""La exportación avisa de los resultados que se apoyan en una página leída por visión (REQ-093,
REQ-104; P3; ADR-0041; decisión del responsable del 2026-10-13; plan 015, T-264).

«Mantengo la visión, siempre es preferible a no leída. Obviamente aclarando que proviene de un
documento con dificultades de lectura y que conviene re chequear por la comisión»: en la planilla,
el fundamento del resultado suma el aviso; en el cuadro comparativo, la celda lleva una marca y el
cuadro una nota al pie. Los archivos no citan texto de la oferta: el aviso es lo único que dice que
el resultado sale de una transcripción. Resultados guardados directo, sin el modelo; todo el
material es inventado (P4)."""

import hashlib
import io

import pdfplumber
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.assessment import models as am
from evaluon.assessment.services import export as service
from evaluon.offers import models as om
from tests.assessment.test_export import flat, read_xlsx
from tests.assessment.test_matrix import (  # noqa: F401 - fixtures y ayudas
    add_run,
    page_of,
    requirement,
    three,
)

pytestmark = pytest.mark.django_db

NOTE = ("Se apoya en una página con dificultades de lectura, leída por visión: conviene que la "
        "Comisión la vuelva a chequear con la imagen del original.")
MARK = "(*)"


def add_vision_citation(result):
    """Suma a `result` una cita de la oferta sobre la página 2 de una lectura nueva del documento,
    con esa página leída por visión (informe de la lectura: `report["vision"]`)."""
    document = result.offer.documents.first()
    text = "Texto inventado de una página leída por visión."
    reading = om.Reading.objects.create(
        document=document, sequence=document.readings.count() + 1, pages={"pages": []},
        canonical_text=text, canonical_sha256=hashlib.sha256(text.encode()).hexdigest(),
        tool_versions={}, report={"vision": {"pages": [{"page": 2, "outcome": "read"}]}})
    am.Citation.objects.create(
        result=result, order=10, kind=am.CitationKind.OFERTA, document=document, reading=reading,
        page=2, char_start=0, char_end=30, text=text[:30])


@pytest.fixture
def plain(three, procedure, operator_user):  # noqa: F811
    """Tres ofertas evaluadas sin ninguna página leída por visión: A y C cumplen la declaración
    jurada; B no la cumple."""
    a, b, c = three
    declaration = requirement(procedure, "declaración jurada")
    results = {}
    for offer, outcome in ((a, "cumple"), (b, "no_cumple"), (c, "cumple")):
        results[offer.pk] = add_run(operator_user, procedure, offer,
                                    {declaration: outcome})[declaration.pk]
    return three, declaration, results


@pytest.fixture
def seen(plain):
    """Lo mismo, pero el «no cumple» de B cita además una página leída por visión."""
    offers, declaration, results = plain
    add_vision_citation(results[offers[1].pk])
    return plain


def sheet_row(rows, number):
    """La fila de la planilla del requisito `number`."""
    return next(row for row in rows if row and row[0] == str(number))


def pdf_text(data):
    """El texto del PDF entregado, con los espacios colapsados."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return " ".join(" ".join(page.extract_text() or "" for page in pdf.pages).split())


# --- Planilla --------------------------------------------------------------------------------


def test_the_planilla_adds_the_note_to_the_basis_of_the_result_that_rests_on_a_vision_page(
        seen, procedure, operator_user):
    """REQ-093, REQ-104, P3: en la planilla en Excel, el fundamento del resultado que cita una
    página leída por visión suma el aviso; el de las otras ofertas, que no citan ninguna, no."""
    (a, b, c), declaration, _ = seen
    sheets = read_xlsx(service.export(operator_user, procedure.pk, "planilla", "xlsx")[0])
    mine = sheet_row(sheets[f"Oferta {b.number}"], declaration.number)
    assert mine[6] == f"Lo dice el texto. {NOTE}"
    for other in (a, c):
        texts = flat(sheets[f"Oferta {other.number}"])
        assert not any("dificultades de lectura" in text for text in texts)
        assert sheet_row(sheets[f"Oferta {other.number}"], declaration.number)[6] == \
            "Lo dice el texto."


def test_without_vision_pages_the_planilla_and_the_cuadro_add_nothing(
        plain, procedure, operator_user):
    """REQ-093, P3: si ningún resultado se apoya en una página leída por visión, ni la planilla ni
    el cuadro (Excel y PDF) traen aviso, marca ni nota al pie."""
    for document, fmt in (("planilla", "xlsx"), ("cuadro", "xlsx")):
        sheets = read_xlsx(service.export(operator_user, procedure.pk, document, fmt)[0])
        texts = [text for rows in sheets.values() for text in flat(rows)]
        assert not any("dificultades de lectura" in text or MARK in text for text in texts)
    for document in ("planilla", "cuadro"):
        html = service.build_html(service.collect(operator_user, procedure.pk), document)
        assert "dificultades de lectura" not in html and MARK not in html
        data = service.export(operator_user, procedure.pk, document, "pdf")[0]
        assert "dificultades de lectura" not in pdf_text(data)


# --- Cuadro comparativo ----------------------------------------------------------------------


def test_the_cuadro_marks_the_cell_and_explains_the_mark_in_a_footnote(
        seen, procedure, operator_user):
    """REQ-093, REQ-104, P3: en el cuadro en Excel, la celda de B lleva la marca corta y el cuadro
    trae la nota al pie una sola vez; las celdas de A y C, no."""
    (a, b, c), declaration, _ = seen
    sheets = read_xlsx(service.export(operator_user, procedure.pk, "cuadro", "xlsx")[0])
    rows = sheets["Cuadro comparativo"]
    row = sheet_row(rows, declaration.number)
    page = page_of(operator_user, procedure)
    cells = dict(zip((o.pk for o in page.offers), row[3:], strict=True))
    assert cells[b.pk] == f"No cumple (propuesto) {MARK}"
    assert cells[a.pk] == "Cumple (propuesto)" and cells[c.pk] == "Cumple (propuesto)"
    assert flat(rows).count(f"{MARK} {NOTE}") == 1
    marked = [text for text in flat(rows) if text.endswith(f" {MARK}")]
    assert marked == [f"No cumple (propuesto) {MARK}"]


# --- PDF -------------------------------------------------------------------------------------


def test_the_pdf_of_the_planilla_and_of_the_cuadro_say_it_too(seen, procedure, operator_user):
    """REQ-093, REQ-104, P3: el PDF (el HTML con que se arma y el texto del archivo entregado)
    trae el aviso en el fundamento de la planilla y la marca con su nota al pie en el cuadro."""
    (a, b, c), declaration, _ = seen
    data = service.collect(operator_user, procedure.pk)
    planilla = service.build_html(data, "planilla")
    assert planilla.count(NOTE) == 1 and MARK not in planilla
    cuadro = service.build_html(data, "cuadro")
    assert f"<td>No cumple (propuesto) {MARK}</td>" in cuadro
    assert cuadro.count(f"{MARK} {NOTE}") == 1
    # El texto del archivo: las frases se parten en las celdas, pero las palabras salen todas.
    words = pdf_text(service.export(operator_user, procedure.pk, "planilla", "pdf")[0])
    assert "dificultades" in words and "lectura," in words and "chequear" in words
    words = pdf_text(service.export(operator_user, procedure.pk, "cuadro", "pdf")[0])
    assert f"{MARK} Se apoya en una página con dificultades de lectura" in words


# --- Una consulta para todos los resultados --------------------------------------------------


def test_the_vision_pages_of_every_result_are_looked_up_with_one_query(
        seen, procedure, operator_user):
    """REQ-100, T-223: las lecturas con visión de todos los resultados se piden con una sola
    consulta, no una por fila de la planilla ni por celda del cuadro."""
    with CaptureQueriesContext(connection) as queries:
        service.collect(operator_user, procedure.pk)
    readings = [q["sql"] for q in queries
                if 'FROM "offers_reading"' in q["sql"] and "? 'vision'" in q["sql"]]
    assert len(readings) == 1
