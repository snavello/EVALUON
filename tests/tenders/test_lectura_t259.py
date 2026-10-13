"""Lectura del pliego de la ronda del comité (REQ-104; T-259; informe del comité, H1 y H3,
acciones A1).

- **Texto «(cid:N)».** Un PDF cuya fuente no trae la correspondencia de caracteres (los
  croquis del caso-01): pypdfium2 da los códigos crudos como si fueran letras y la página
  pasaba por legible; pdfplumber da `(cid:39)(cid:44)…`. La página tiene que leerse con
  reconocimiento, como una escaneada.
- **Tablas con sus celdas.** Una tabla de marcas como la 17.1 del caso-00 («Total», «Por
  Renglón» con una «X», «Por grupo de Renglones»): la «X» queda con su fila.

Los PDF se arman en el test con texto inventado (P4): `tests/tenders/pdfs.py`, y para el
primero se le quita a la fuente su `ToUnicode` y se le cambia el orden de caracteres, que es
la forma de una fuente subconjunto sin correspondencia.
"""

import hashlib
import io
import re
from datetime import date

import pdfplumber
import pypdfium2 as pdfium
import pytest

from evaluon.norms.reading import (
    ORIGIN_OCR,
    ORIGIN_PDF_TEXT,
    PAGE_KIND_TEXT,
    PAGE_KIND_UNUSABLE_TEXT,
    Line,
    Page,
    classify_page,
    extracted_kind,
    read_document,
)
from evaluon.tenders import jobs
from evaluon.tenders.models import DocumentKind, Procedure, Reading, Segment
from evaluon.tenders.proposal import quotes
from evaluon.tenders.segmenting import TABLA, split_tender
from evaluon.tenders.services import documents
from evaluon.tenders.tables import CELLS_VERSION, read_tables, table_zones, with_cells
from tests.tenders.pdfs import para, table, tender_pdf

CROQUIS_LINES = (
    "LA CONTRATISTA SERA RESPONSABLE DE VERIFICAR",
    "EN EL LUGAR TODAS LAS MEDIDAS Y CANTIDADES.",
)

MARKS_TABLE = (
    ("Total", ""),
    ("Por Renglón", "X"),
    ("Por grupo de Renglones", ""),
)


def without_unicode_map(data):
    """El PDF con su fuente sin `ToUnicode` (los bytes se reemplazan por espacios, así las
    posiciones de la tabla de referencias siguen valiendo) y con un orden de caracteres que
    pdfminer no conoce: pdfplumber ya no puede pasar los glifos a letras y escribe
    `(cid:N)`; pypdfium2 sigue dibujándolos bien."""
    data = re.sub(rb"/ToUnicode \d+ 0 R", lambda m: b" " * len(m.group(0)), data)
    return data.replace(b"(Identity)", b"(Identitx)")


@pytest.fixture(scope="module")
def croquis_pdf():
    return without_unicode_map(tender_pdf([[para(*CROQUIS_LINES)]], header=None))


@pytest.fixture(scope="module")
def marks_pdf():
    return tender_pdf([[
        para("17.1. Tipo de Cotización:"),
        table(*MARKS_TABLE),
        para("17.2. La oferta se presenta por el Portal."),
    ]], header=None)


# --- Texto «(cid:N)» -------------------------------------------------------------------------


def test_the_invented_croquis_reproduces_the_failure(croquis_pdf):
    """REQ-104 (T-259, H3): el PDF inventado tiene la forma de los croquis: pypdfium2 da su
    capa por buena (con texto, casi sin caracteres sin letra) y pdfplumber la lee como
    `(cid:N)`."""
    document = pdfium.PdfDocument(croquis_pdf)
    try:
        assert classify_page(document[0]) == PAGE_KIND_TEXT
    finally:
        document.close()
    with pdfplumber.open(io.BytesIO(croquis_pdf)) as pdf:
        assert "(cid:" in pdf.pages[0].extract_text()


def test_a_page_whose_text_comes_out_as_cid_is_read_by_recognition(croquis_pdf):
    """REQ-104 (T-259, H3): la página cuya capa de texto pdfplumber lee como `(cid:N)` no se
    toma por legible: se clasifica con texto inservible y se reconoce sobre la imagen, como
    una escaneada. Sus líneas traen origen `ocr`, con confianza, y el texto que se ve."""
    reading = read_document(croquis_pdf)

    page = reading.pages[0]
    assert page.classification == PAGE_KIND_UNUSABLE_TEXT
    assert page.origin == ORIGIN_OCR
    assert page.lines and all(line.origin == ORIGIN_OCR for line in page.lines)
    text = " ".join(line.text for line in page.lines)
    assert "(cid:" not in text
    assert "CONTRATISTA" in text and "MEDIDAS" in text
    assert reading.tool_versions["tesseract_spa_sha256"]


def test_no_segment_of_the_croquis_keeps_cid_text(croquis_pdf):
    """REQ-104 (T-259, H3): partido en tramos, ningún tramo del croquis trae `(cid:`."""
    reading, zones = with_cells(read_document(croquis_pdf), read_tables(croquis_pdf))
    split = split_tender(reading, zones, max_chars=4000)
    assert split.segments
    assert not any("(cid:" in segment.text for segment in split.segments)


def test_a_few_cid_marks_in_a_long_text_do_not_send_the_page_to_recognition():
    """REQ-104 (T-259): unos pocos `(cid:13)(cid:10)` en un texto largo (el ruido de las
    pólizas del caso-00) no mandan la página al reconocimiento: la proporción de caracteres
    sin letra queda por debajo del umbral y la capa de texto se usa."""
    words = "La póliza de caución garantiza el mantenimiento de la oferta presentada " * 6
    page = Page(number=1, width=595, height=842, status="legible", lines=[
        Line(text=words + "(cid:13)(cid:10)", x0=50, top=100, x1=500, bottom=110,
             origin=ORIGIN_PDF_TEXT)])
    assert extracted_kind(PAGE_KIND_TEXT, page) == PAGE_KIND_TEXT

    noisy = Page(number=1, width=595, height=842, status="legible", lines=[
        Line(text="DEPENDENCIA: (cid:39)(cid:44)(cid:53)(cid:40)(cid:38)", x0=50, top=100,
             x1=500, bottom=110, origin=ORIGIN_PDF_TEXT)])
    assert extracted_kind(PAGE_KIND_TEXT, noisy) == PAGE_KIND_UNUSABLE_TEXT


# --- Tablas con sus celdas ---------------------------------------------------------------------


def _table_segment(pdf):
    reading, zones = with_cells(read_document(pdf), read_tables(pdf))
    split = split_tender(reading, zones, max_chars=4000)
    tables = [segment for segment in split.segments if segment.segment_type == TABLA]
    assert len(tables) == 1
    return tables[0], zones


def test_a_marks_table_keeps_each_mark_in_its_row(marks_pdf):
    """REQ-104 (T-259, H1): la tabla de marcas sale fila por fila y con sus celdas separadas
    por una tabulación: la «X» queda en la fila «Por Renglón», no entre dos filas, y las
    celdas vacías quedan vacías entre sus separadores."""
    segment, zones = _table_segment(marks_pdf)

    assert segment.text.split("\n") == ["Total\t", "Por Renglón\tX",
                                        "Por grupo de Renglones\t"]
    assert zones[0]["cells"] is True
    assert zones[0]["rows"] == [["Total", ""], ["Por Renglón", "X"],
                                ["Por grupo de Renglones", ""]]


def test_a_quote_copied_with_spaces_between_cells_is_still_found(marks_pdf):
    """REQ-104 (T-259; REQ-025): la tabulación entre celdas es un espacio en blanco: la cita
    que el modelo copia con un espacio («Por Renglón X») se ubica en el tramo, y su recorte
    literal trae la tabulación."""
    segment, _ = _table_segment(marks_pdf)
    span = quotes.locate(segment.text, "Por Renglón X")
    assert span is not None
    assert segment.text[span[0]:span[1]] == "Por Renglón\tX"


def test_the_text_around_the_table_does_not_change(marks_pdf):
    """REQ-104 (T-259): lo que está antes y después de la tabla se lee igual que sin las
    celdas, y ningún carácter de la tabla se pierde ni se agrega (solo los separadores)."""
    plain = read_document(marks_pdf)
    reading, _ = with_cells(plain, read_tables(marks_pdf))
    before = split_tender(plain, table_zones(marks_pdf), max_chars=4000)
    after = split_tender(reading, read_tables(marks_pdf), max_chars=4000)

    def others(split):
        return [s.text for s in split.segments if s.segment_type != TABLA]

    assert others(after) == others(before)
    [old] = [s.text for s in before.segments if s.segment_type == TABLA]
    [new] = [s.text for s in after.segments if s.segment_type == TABLA]
    assert sorted(new.split()) == sorted(old.split())
    assert "\t" in new and "\t" not in old


def test_a_table_whose_cells_do_not_match_its_lines_is_left_as_it_was(marks_pdf):
    """REQ-104 (T-259): si las celdas no traen los mismos caracteres que las líneas de la zona
    (algo quedaría afuera o de más), la tabla no se escribe: quedan sus líneas, sin
    separadores, y la zona lo dice."""
    zones = read_tables(marks_pdf)
    zones[0]["rows"][1][1] = "Y"
    reading, marked = with_cells(read_document(marks_pdf), zones)
    split = split_tender(reading, marked, max_chars=4000)
    [segment] = [s for s in split.segments if s.segment_type == TABLA]
    assert "\t" not in segment.text
    assert marked[0]["cells"] is False


def test_a_one_row_frame_is_not_rewritten():
    """REQ-104 (T-259): un recuadro de una sola fila (el lema del año, una nota con borde) no
    se escribe celda por celda: queda como lo leyó la capa de texto."""
    pdf = tender_pdf([[para("Texto previo."), table(("Nota", "Ver anexo")),
                       para("Texto posterior.")]], header=None)
    reading, zones = with_cells(read_document(pdf), read_tables(pdf))
    assert zones and zones[0]["cells"] is False
    assert all("\t" not in line.text for page in reading.pages for line in page.lines)


@pytest.mark.django_db
def test_the_reading_job_keeps_the_cells_and_registers_how(operator_user, marks_pdf):
    """REQ-104 (T-259, H1; P6): la lectura del pliego en segundo plano guarda la tabla con sus
    celdas en `tenders_reading.tables`, su tramo `tabla` con la «X» en su fila, y la versión
    de la forma de escribir las celdas en `tool_versions`."""
    procedure = Procedure.objects.create(
        number="SINT-T259", procedure_type="Licitación pública",
        subject="Adquisición sintética de insumos de prueba",
        authorization_date=date(2025, 11, 14), created_by=operator_user)
    loaded = documents.load_document(
        operator_user, procedure, data=marks_pdf, file_name="pliego-t259.pdf",
        kind=DocumentKind.PLIEGO, title="Pliego sintético")
    while jobs.run_next() is not None:
        pass

    reading = Reading.objects.get(document=loaded.document)
    assert reading.tool_versions["table_cells"] == CELLS_VERSION
    assert reading.tables[0]["rows"][1] == ["Por Renglón", "X"]
    assert reading.tables[0]["cells"] is True
    table_segment = Segment.objects.get(reading=reading, segment_type=TABLA)
    assert "Por Renglón\tX" in table_segment.text
    assert reading.canonical_sha256 == hashlib.sha256(
        reading.canonical_text.encode("utf-8")).hexdigest()
