"""Lectura de un PDF con texto (T-012; ADR-0004, "Cómo se lee"; plan 001, etapa 2).

El archivo de prueba es `tests/fixtures/disp-247-2022-anexo-extracto.pdf`: las páginas 1
a 6 del anexo de la Disposición AFIP 247/2022 (`corpus/normativa/disp-afip-247-2022-anexo.pdf`),
copiadas sin cambiar su contenido. Es material público (P4). Traen la carátula, el índice
completo (páginas 1 a 5) y los primeros artículos; el artículo 7 queda cortado al final de
la página 6.

Los PDF con páginas sin capa de texto se arman en cada prueba con pypdfium2, a partir
del mismo extracto: una página en blanco y una página que es solo una imagen.
"""

import io
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from evaluon.norms.reading import (
    ORIGIN_PDF_TEXT,
    PAGE_NOT_READ,
    PAGE_READ,
    UnsupportedFormatError,
    read_document,
)
from evaluon.norms.reading.pdf_text import read_pdf_text

REPO = Path(__file__).resolve().parents[2]
EXTRACT = REPO / "tests" / "fixtures" / "disp-247-2022-anexo-extracto.pdf"
ORIGINAL = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"


@pytest.fixture(scope="module")
def extract():
    return read_document(EXTRACT)


def texts(page):
    return [line.text for line in page.lines]


def pdf_bytes(document):
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def with_pages_without_text():
    """El extracto con dos páginas sin capa de texto insertadas: una en blanco después
    de la página 1 y otra que es solo la imagen de la página 2 después de la página 3.
    Orden resultante: extracto 1, blanco, extracto 2, extracto 3, imagen, extracto 4 a 6."""
    source = pdfium.PdfDocument(EXTRACT)
    pdf = pdfium.PdfDocument.new()
    pdf.import_pages(source, pages=[0])
    pdf.new_page(612, 792)
    pdf.import_pages(source, pages=[1, 2])

    picture = source[1].render(scale=1).to_pil()
    page = pdf.new_page(612, 792)
    image = pdfium.PdfImage.new(pdf)
    image.set_bitmap(pdfium.PdfBitmap.from_pil(picture))
    image.set_matrix(pdfium.PdfMatrix().scale(612, 792))
    page.insert_obj(image)
    page.gen_content()

    pdf.import_pages(source, pages=[3, 4, 5])
    return pdf_bytes(pdf)


# --- El extracto se lee completo, en orden y con su origen (REQ-015) ------------------


def test_extract_reads_all_six_pages_in_order(extract):
    """REQ-015, REQ-004: un PDF con texto se lee con todas sus páginas, numeradas desde 1
    en el orden del archivo, todas leídas y con líneas; ninguna figura como no leída."""
    assert extract.file_format == "pdf"
    assert [page.number for page in extract.pages] == [1, 2, 3, 4, 5, 6]
    assert all(page.status == PAGE_READ for page in extract.pages)
    assert all(page.lines for page in extract.pages)
    assert extract.pages_not_read == []


def test_every_line_has_pdf_text_origin_and_no_confidence(extract):
    """REQ-015: cada línea leída de la capa de texto lleva origen `pdf_text` y no lleva
    confianza ni palabras de reconocimiento, que son solo del texto reconocido."""
    lines = [line for page in extract.pages for line in page.lines]
    assert lines
    assert {line.origin for line in lines} == {ORIGIN_PDF_TEXT}
    assert all(line.confidence is None for line in lines)
    assert all(line.words == [] for line in lines)
    assert all(line.discarded == "" for line in lines)


def test_lines_follow_the_page_from_top_to_bottom_with_their_position(extract):
    """REQ-015: las líneas de cada página van de arriba hacia abajo, cada una con su
    posición dentro de la página (en puntos, origen arriba a la izquierda)."""
    for page in extract.pages:
        assert (page.width, page.height) == (612, 792)
        tops = [line.top for line in page.lines]
        assert tops == sorted(tops)
        for line in page.lines:
            assert 0 <= line.x0 < line.x1 <= page.width
            assert 0 <= line.top < line.bottom <= page.height


def test_extract_lines_match_the_document(extract):
    """REQ-015: el texto de las líneas es el del documento, carácter por carácter: la
    carátula, el índice con `º` (ordinal) y el articulado con `°` (grado) sin
    normalizar, y el corte del artículo 7 al final de la página 6."""
    page_1, page_5, page_6 = extract.pages[0], extract.pages[4], extract.pages[5]

    assert texts(page_1)[:3] == [
        "Administración Federal de Ingresos Públicos",
        '2022 - "Las Malvinas son argentinas"',
        "ANEXO",
    ]
    assert "ANEXO (artículo 1°)" in texts(page_1)
    assert "ÍNDICE:" in texts(page_1)
    assert "ARTÍCULO 1º.- OBJETO" in texts(page_1)
    assert texts(page_1)[-1] == "ARTÍCULO 13.- VISTA DE LAS ACTUACIONES"

    assert "ARTÍCULO 99.- VALOR DEL MÓDULO" in texts(page_5)
    assert (
        "ARTÍCULO 1°.- OBJETO. El presente régimen tendrá por objeto establecer los "
        "lineamientos y principios"
    ) in texts(page_5)
    assert texts(page_5)[-1] == "a) Integridad en los procedimientos."

    assert texts(page_6)[0] == (
        "b) Razonabilidad del proyecto y eficiencia de la contratación a fin de cumplir "
        "con el interés público"
    )
    assert texts(page_6)[-1] == "a) El presente régimen."
    assert all(text == text.strip() and text for text in texts(page_6))


def test_extract_is_the_same_as_the_first_six_pages_of_the_original(extract):
    """REQ-015: el archivo de prueba no cambió el contenido del anexo real: sus seis
    páginas se leen igual que las seis primeras del archivo del corpus."""
    original = read_document(ORIGINAL)

    assert len(original.pages) == 45
    assert original.pages[:6] == extract.pages


# --- El anexo completo, palabra por palabra (REQ-015, REQ-004) ------------------------


@pytest.fixture(scope="module")
def original():
    return read_document(ORIGINAL)


def test_every_page_of_the_original_has_the_same_words_as_pdfium(original):
    """REQ-015, REQ-004: en las 45 páginas del anexo real, la secuencia de palabras de
    las líneas leídas es la misma que da una extracción independiente con pypdfium2
    (`get_text_range().split()`). Detecta espacios mal ubicados dentro de una palabra y
    líneas perdidas en el medio de una página."""
    pdf = pdfium.PdfDocument(ORIGINAL)
    assert len(original.pages) == len(pdf) == 45

    for page, pdfium_page in zip(original.pages, pdf):
        expected = pdfium_page.get_textpage().get_text_range().split()
        words = " ".join(texts(page)).split()
        assert words == expected, f"la página {page.number} no coincide con pypdfium2"
        tops = [line.top for line in page.lines]
        assert tops == sorted(tops), f"la página {page.number} no va de arriba abajo"


@pytest.mark.parametrize(
    ("page_number", "line"),
    [
        (14, "y 9. del presente"),
        (18, "la necesidad del área"),
        (39, "a efectos de conformar la"),
        (44, "un banco, repartición"),
    ],
)
def test_spaces_drawn_inside_a_word_do_not_split_it(original, page_number, line):
    """REQ-015, REQ-004: el PDF dibuja algunos espacios en posiciones que caen dentro de
    una palabra (artículos 21, 24, 76 y 95). La lectura sigue el orden en que el PDF
    escribe los caracteres y no los reordena por posición, así que esas palabras quedan
    enteras, como en el documento."""
    page = original.pages[page_number - 1]
    assert any(line in text for text in texts(page)), (
        f"la página {page_number} no trae {line!r}"
    )


# --- Página sin capa de texto (REQ-004) -----------------------------------------------


def test_pages_without_text_layer_are_reported_as_not_read():
    """REQ-004: para la lectura de PDF con texto, una página sin capa de texto (en
    blanco, o que es solo una imagen) figura como no leída, sin líneas, con su número;
    las demás se leen y conservan el suyo. (Desde T-028 la entrada única clasifica esas
    páginas antes de leerlas: la en blanco queda en blanco y la imagen se reconoce; ver
    `test_three_formats.py`.)"""
    reading = read_pdf_text(with_pages_without_text())

    assert [page.number for page in reading.pages] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert reading.pages_not_read == [2, 5]
    for number in (2, 5):
        page = reading.pages[number - 1]
        assert page.status == PAGE_NOT_READ
        assert page.lines == []

    extract = read_document(EXTRACT)
    read = [page for page in reading.pages if page.status == PAGE_READ]
    assert [page.number for page in read] == [1, 3, 4, 6, 7, 8]
    assert [page.lines for page in read] == [page.lines for page in extract.pages]


# --- Misma entrada, misma salida; versiones; formato ----------------------------------


def test_same_input_gives_same_output():
    """REQ-004, REQ-015: la lectura es determinista: el mismo archivo da siempre la misma
    lectura, se lea desde su ruta o desde sus bytes."""
    first = read_document(EXTRACT)
    second = read_document(EXTRACT)
    from_bytes = read_document(EXTRACT.read_bytes())

    assert first == second == from_bytes
    assert first.as_json() == from_bytes.as_json()


def test_reading_records_tool_versions(extract):
    """REQ-004: la lectura trae las versiones de las herramientas con que se leyó, que
    van al informe de lectura."""
    assert set(extract.tool_versions) == {"pdfplumber", "pdfminer.six", "pypdfium2"}
    assert extract.tool_versions["pdfplumber"] == "0.11.10"
    assert extract.tool_versions["pypdfium2"] == "5.13.0"
    assert all(extract.tool_versions.values())


def test_as_json_keeps_pages_lines_and_versions(extract):
    """REQ-004, REQ-015: la lectura se puede guardar como JSON (campo `pages` de la
    lectura) con sus páginas, sus líneas con texto, posición y origen, y las versiones."""
    data = extract.as_json()

    assert data["file_format"] == "pdf"
    assert data["tool_versions"] == extract.tool_versions
    assert len(data["pages"]) == 6
    first_line = data["pages"][0]["lines"][0]
    assert first_line == {
        "text": "Administración Federal de Ingresos Públicos",
        "x0": extract.pages[0].lines[0].x0,
        "top": extract.pages[0].lines[0].top,
        "x1": extract.pages[0].lines[0].x1,
        "bottom": extract.pages[0].lines[0].bottom,
        "origin": "pdf_text",
        "confidence": None,
        "words": [],
        "discarded": "",
    }
    assert data["pages"][0]["status"] == PAGE_READ


def test_a_file_that_is_not_a_pdf_is_rejected(tmp_path):
    """REQ-015: el formato se reconoce por el contenido y no por el nombre. Una página
    web, aunque se llame `.pdf`, no se lee como PDF (desde T-028 se lee como página web);
    un archivo que no es PDF ni página web, aunque se llame `.pdf`, se rechaza."""
    html = b"<!DOCTYPE html><html><body><p>ARTICULO 1.- Texto.</p></body></html>"
    disguised = tmp_path / "pagina-sintetica.pdf"
    disguised.write_bytes(html)
    text = b"ARTICULO 1.- Texto suelto, sin formato."
    other = tmp_path / "texto-sintetico.pdf"
    other.write_bytes(text)

    assert read_document(disguised).file_format == "html"
    assert read_document(html).file_format == "html"
    with pytest.raises(UnsupportedFormatError):
        read_document(other)
    with pytest.raises(UnsupportedFormatError):
        read_document(text)
