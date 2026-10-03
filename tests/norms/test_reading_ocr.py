"""Lectura de un PDF escaneado con reconocimiento de texto (T-021; ADR-0004, "Cómo se
lee"; plan 001, bloque A).

Archivos de prueba, generados dentro de la imagen de la aplicación con pypdfium2 y Pillow,
sin descargar nada. Son material público o sintético (P4):

- `tests/fixtures/disp-247-2022-anexo-extracto-escaneado.pdf`: el extracto de T-012
  (`disp-247-2022-anexo-extracto.pdf`, páginas 1 a 6 del anexo de la Disp. AFIP
  247/2022) dibujado como imágenes. Cada página se dibujó con pypdfium2 en escala de
  grises a 200 puntos por pulgada, se guardó como JPEG con Pillow (calidad 75) y se pegó
  como única imagen de una página de 612 x 792 puntos. No tiene capa de texto. Es más
  limpio que un escaneo real: mide el caso fácil (ADR-0004, "Cómo se prueba").
- `tests/fixtures/pagina-ruido.pdf`: una página de 612 x 792 puntos que es solo una
  imagen de 637 x 825 celdas blancas y negras al azar (`random.Random(21).randbytes`,
  negra si el byte pasa de 127), pegada con `PdfImage.set_bitmap`. Tesseract encuentra en
  ella unas pocas "palabras" de confianza baja.

Las pruebas de los umbrales y de las páginas dudosas reemplazan la salida de Tesseract
por datos armados en la prueba.
"""

import difflib
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from evaluon.norms.reading import (
    ORIGIN_OCR,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_NOT_READ,
    PAGE_READ,
    Page,
    Word,
    read_document,
)
from evaluon.norms.reading import ocr

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
EXTRACT = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
SCANNED = FIXTURES / "disp-247-2022-anexo-extracto-escaneado.pdf"
NOISE = FIXTURES / "pagina-ruido.pdf"

# Huella de spa.traineddata de tessdata_best 4.1.0 que fija el Dockerfile (T-005).
SPA_BEST_SHA256 = "e2c1ffdad8b30f26c45d4017a9183d3a7f9aa69e59918be4f88b126fac99ab2c"


def read_pages(path):
    pdf = pdfium.PdfDocument(path)
    return [ocr.read_page_ocr(page, number) for number, page in enumerate(pdf, start=1)]


@pytest.fixture(scope="module")
def scanned():
    return read_pages(SCANNED)


@pytest.fixture(scope="module")
def text_pdf():
    return read_document(EXTRACT)


def words_of(page):
    return " ".join(line.text for line in page.lines).split()


def coincidence(expected, recognized):
    """Proporción de palabras del PDF con texto que aparecen, en el mismo orden, en lo
    reconocido (bloques coincidentes de `difflib.SequenceMatcher`)."""
    matcher = difflib.SequenceMatcher(a=expected, b=recognized, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(expected)


# --- El archivo de prueba es un escaneo -----------------------------------------------


def test_scanned_fixture_is_the_extract_without_text_layer():
    """REQ-015: el extracto escaneado tiene las seis páginas del extracto, del mismo
    tamaño, y ninguna capa de texto: leído como PDF con texto, todas sus páginas quedan
    no leídas. Lo que se lea de él sale del reconocimiento sobre la imagen."""
    pdf = pdfium.PdfDocument(SCANNED)
    assert len(pdf) == 6
    for page in pdf:
        assert page.get_size() == (612, 792)
        assert page.get_textpage().get_text_range().strip() == ""

    as_text = read_document(SCANNED)
    assert [page.status for page in as_text.pages] == [PAGE_NOT_READ] * 6


# --- Lectura del extracto escaneado (REQ-015) -----------------------------------------


def test_scanned_pages_are_legible_with_their_number_and_size(scanned):
    """REQ-015, REQ-004: cada página escaneada se lee con el número que recibe, su tamaño
    en puntos (el mismo que da la lectura de PDF con texto) y estado legible; ninguna
    queda sin líneas."""
    assert [page.number for page in scanned] == [1, 2, 3, 4, 5, 6]
    for page in scanned:
        assert isinstance(page, Page)
        assert (page.width, page.height) == (612, 792)
        assert page.status == PAGE_READ
        assert page.lines


def test_every_recognized_line_has_ocr_origin_and_word_confidence(scanned):
    """REQ-015: cada línea reconocida lleva origen `ocr`, la confianza de cada palabra
    (0 a 100) y la de la línea, que es el promedio de sus palabras. El texto de la línea
    son sus palabras separadas por un espacio. No se descarta nada."""
    lines = [line for page in scanned for line in page.lines]
    assert lines
    for line in lines:
        assert line.origin == ORIGIN_OCR
        assert line.discarded == ""
        assert line.words and all(isinstance(word, Word) for word in line.words)
        assert all(0 <= word.confidence <= 100 for word in line.words)
        assert line.text == " ".join(word.text for word in line.words)
        average = sum(word.confidence for word in line.words) / len(line.words)
        assert line.confidence == pytest.approx(average, abs=0.01)


def test_recognized_lines_go_top_to_bottom_in_page_points(scanned):
    """REQ-015: las líneas van de arriba hacia abajo, con su posición en puntos de la
    página (origen arriba a la izquierda), como en la lectura de PDF con texto: así la
    partición separa párrafos con la misma medida en los dos orígenes."""
    for page in scanned:
        tops = [line.top for line in page.lines]
        assert tops == sorted(tops)
        for line in page.lines:
            assert 0 <= line.x0 < line.x1 <= page.width
            assert 0 <= line.top < line.bottom <= page.height


def test_line_positions_agree_with_the_text_pdf(scanned, text_pdf):
    """REQ-015: la misma línea queda en el mismo lugar en los dos orígenes. La primera
    línea de la página 6 empieza y termina a menos de dos puntos de donde la ubica la
    capa de texto del PDF original."""
    recognized = scanned[5].lines[0]
    original = text_pdf.pages[5].lines[0]
    for edge in ("x0", "top", "x1", "bottom"):
        assert getattr(recognized, edge) == pytest.approx(getattr(original, edge), abs=2)


def test_recognized_words_coincide_with_the_text_pdf(scanned, text_pdf):
    """REQ-015: el reconocimiento transcribe el documento. Frente al PDF con texto, cada
    página coincide en al menos el 85 % de sus palabras y el extracto en al menos el
    95 % (medido: 97,9 %; lo que falla son sobre todo los signos `°` y `º`)."""
    matched = total = 0
    for recognized, original in zip(scanned, text_pdf.pages):
        expected = words_of(original)
        share = coincidence(expected, words_of(recognized))
        assert share >= 0.85, f"página {original.number}: {share:.3f}"
        matched += share * len(expected)
        total += len(expected)
    assert matched / total >= 0.95


def test_some_recognized_lines_are_literal(scanned, text_pdf):
    """REQ-015: líneas de texto corrido salen carácter por carácter iguales al documento,
    con tildes y signos de puntuación."""
    for number, index in ((2, 0), (6, 0), (6, -1)):
        assert scanned[number - 1].lines[index].text == text_pdf.pages[number - 1].lines[index].text


def test_same_page_gives_the_same_reading(scanned):
    """REQ-015, REQ-004: el reconocimiento es determinista: la misma página da la misma
    lectura, con las mismas palabras, posiciones y confianzas."""
    page = pdfium.PdfDocument(SCANNED)[1]
    assert ocr.read_page_ocr(page, 2) == scanned[1]


# --- Página de ruido (REQ-004) --------------------------------------------------------


def test_noise_page_is_illegible_and_gives_no_text():
    """REQ-004: una página que es solo ruido queda ilegible y sin líneas: no aporta texto
    a las unidades y la lectura la cuenta entre las no leídas."""
    [page] = read_pages(NOISE)

    assert page.number == 1
    assert (page.width, page.height) == (612, 792)
    assert page.status == PAGE_ILLEGIBLE
    assert page.lines == []


# --- Estado de la página según la confianza (REQ-004) ---------------------------------


def words(*confidences, text="palabra"):
    return [Word(text=text, confidence=value) for value in confidences]


@pytest.mark.parametrize(
    ("page_words", "status"),
    [
        (words(95, 90, 85, 92), PAGE_READ),
        (words(80, 80, 80), PAGE_READ),
        (words(79.99, 80, 80), PAGE_DOUBTFUL),
        (words(60, 70, 55, 65), PAGE_DOUBTFUL),
        (words(50, 50, 50), PAGE_DOUBTFUL),
        (words(49.99, 50, 50), PAGE_ILLEGIBLE),
        (words(20, 30, 10, 40), PAGE_ILLEGIBLE),
        (words(), PAGE_ILLEGIBLE),
        (words(96, 96), PAGE_ILLEGIBLE),
        (words(96, 96) + words(96, 96, text="-."), PAGE_ILLEGIBLE),
    ],
    ids=[
        "alta",
        "80-legible",
        "apenas-bajo-80",
        "media",
        "50-dudosa",
        "apenas-bajo-50",
        "baja",
        "sin-palabras",
        "dos-palabras",
        "signos-no-cuentan",
    ],
)
def test_page_status_by_average_confidence(page_words, status):
    """REQ-004: el estado de una página reconocida sale de la confianza promedio de sus
    palabras: legible desde 80, dudosa desde 50 y por debajo de 80, ilegible por debajo de
    50. Con casi ninguna palabra (menos de tres con alguna letra o cifra) es ilegible,
    aunque su confianza sea alta."""
    assert ocr.page_status(page_words) == status


def test_thresholds_are_the_starting_values():
    """REQ-004: los umbrales son los valores de partida del plan, a calibrar con escaneos
    reales: 80, 50 y tres palabras."""
    assert (ocr.LEGIBLE_FROM, ocr.DOUBTFUL_FROM, ocr.MIN_WORDS) == (80, 50, 3)


def tesseract_output(rows):
    """Salida de `pytesseract.image_to_data` armada a mano: una fila por palabra, con
    (bloque, línea, izquierda, arriba, ancho, alto, confianza, texto), en píxeles a 300
    puntos por pulgada."""
    data = {key: [] for key in (
        "level", "page_num", "block_num", "par_num", "line_num", "word_num",
        "left", "top", "width", "height", "conf", "text",
    )}
    for block, line, left, top, width, height, conf, text in rows:
        for key, value in zip(
            ("level", "page_num", "block_num", "par_num", "line_num", "word_num",
             "left", "top", "width", "height", "conf", "text"),
            (5, 1, block, 1, line, 1, left, top, width, height, conf, text),
        ):
            data[key].append(value)
    return data


def fake_tesseract(monkeypatch, rows):
    def image_to_data(image, **kwargs):
        return tesseract_output(rows)

    monkeypatch.setattr(ocr.pytesseract, "image_to_data", image_to_data)


def test_doubtful_page_keeps_its_text_with_confidence(monkeypatch):
    """REQ-004, REQ-015: una página de confianza media queda dudosa y conserva su texto,
    con origen `ocr` y la confianza de cada palabra, para que el informe la señale. Las
    líneas se ordenan de arriba hacia abajo y la posición pasa de píxeles a puntos."""
    fake_tesseract(
        monkeypatch,
        [
            (2, 1, 300, 1250, 250, 50, 61.5, "segunda"),
            (2, 1, 600, 1250, 200, 50, 58.5, "línea."),
            (1, 1, 300, 1000, 500, 50, 70, "ARTÍCULO"),
            (1, 1, 850, 1000, 100, 50, 50, "1°.-"),
        ],
    )
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 7)

    assert page.number == 7
    assert page.status == PAGE_DOUBTFUL
    assert [line.text for line in page.lines] == ["ARTÍCULO 1°.-", "segunda línea."]
    first, second = page.lines
    assert first.words == [Word("ARTÍCULO", 70.0), Word("1°.-", 50.0)]
    assert first.confidence == 60.0
    assert second.confidence == 60.0
    assert {line.origin for line in page.lines} == {ORIGIN_OCR}
    assert (first.x0, first.top, first.x1, first.bottom) == (72.0, 240.0, 228.0, 252.0)


def test_page_illegible_by_confidence_gives_no_text(monkeypatch):
    """REQ-004: una página con palabras de confianza baja queda ilegible y no aporta
    líneas, aunque Tesseract haya devuelto palabras."""
    fake_tesseract(
        monkeypatch,
        [
            (1, 1, 300, 1000, 100, 50, 30, "Ea"),
            (1, 1, 450, 1000, 100, 50, 20, "rn"),
            (1, 2, 300, 1100, 100, 50, 45, "lli"),
            (1, 2, 450, 1100, 100, 50, 10, "2"),
        ],
    )
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 3)

    assert page.status == PAGE_ILLEGIBLE
    assert page.lines == []


def test_word_with_confidence_minus_one_counts_as_zero(monkeypatch):
    """REQ-004, REQ-015: Tesseract marca con -1 lo que no reconoce como palabra. Si una
    palabra con texto trae -1, se guarda con confianza 0 y así cuenta para el promedio de
    la línea y de la página: no sube la confianza ni se pierde su texto."""
    fake_tesseract(
        monkeypatch,
        [
            (1, 1, 300, 1000, 200, 50, -1, "Texto"),
            (1, 1, 550, 1000, 100, 50, 90, "con"),
            (1, 1, 700, 1000, 300, 50, 90, "confianza"),
            (1, 1, 1050, 1000, 150, 50, 90, "alta."),
        ],
    )
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 1)

    [line] = page.lines
    assert line.words[0] == Word("Texto", 0.0)
    assert line.text == "Texto con confianza alta."
    assert line.confidence == 67.5
    assert page.status == PAGE_DOUBTFUL


# --- Origen y confianza de la página (REQ-004, REQ-015; T-025) -------------------------


def test_a_recognized_page_keeps_its_origin_and_average_confidence(monkeypatch):
    """REQ-015, REQ-004: una página reconocida lleva su origen `ocr` y su confianza, que
    es el promedio de todas sus palabras, para que el informe la muestre."""
    fake_tesseract(
        monkeypatch,
        [
            (1, 1, 300, 1000, 500, 50, 70, "ARTÍCULO"),
            (1, 1, 850, 1000, 100, 50, 50, "1°.-"),
            (2, 1, 300, 1250, 250, 50, 61.5, "segunda"),
            (2, 1, 600, 1250, 200, 50, 58.5, "línea."),
        ],
    )
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 1)

    assert page.status == PAGE_DOUBTFUL
    assert page.origin == ORIGIN_OCR
    assert page.confidence == 60.0


def test_an_illegible_page_keeps_its_origin_and_confidence(monkeypatch):
    """REQ-004, REQ-015: una página ilegible no aporta líneas, pero conserva su origen y su
    confianza: el informe la puede mostrar como ilegible por confianza baja."""
    fake_tesseract(
        monkeypatch,
        [
            (1, 1, 300, 1000, 100, 50, 30, "Ea"),
            (1, 1, 450, 1000, 100, 50, 20, "rn"),
            (1, 2, 300, 1100, 100, 50, 45, "lli"),
            (1, 2, 450, 1100, 100, 50, 10, "2"),
        ],
    )
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 3)

    assert page.status == PAGE_ILLEGIBLE
    assert page.lines == []
    assert page.origin == ORIGIN_OCR
    assert page.confidence == 26.25


def test_an_almost_empty_page_keeps_its_high_confidence(monkeypatch):
    """REQ-004: una página que dice solo "ANEXO" sale ilegible por tener casi ninguna
    palabra, aunque se lea bien; su confianza alta queda en la página, y así el informe
    la distingue ("casi sin texto") de una página ilegible."""
    fake_tesseract(monkeypatch, [(1, 1, 300, 1000, 300, 50, 96, "ANEXO")])
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 1)

    assert page.status == PAGE_ILLEGIBLE
    assert page.lines == []
    assert page.origin == ORIGIN_OCR
    assert page.confidence == 96.0


def test_a_page_without_words_has_origin_and_no_confidence(monkeypatch):
    """REQ-004: si el reconocimiento no encuentra ninguna palabra, la página es `ocr` y no
    tiene confianza (no hay de qué promediar)."""
    fake_tesseract(monkeypatch, [])
    page = ocr.read_page_ocr(pdfium.PdfDocument(NOISE)[0], 1)

    assert page.status == PAGE_ILLEGIBLE
    assert page.origin == ORIGIN_OCR
    assert page.confidence is None


def test_the_noise_page_keeps_its_origin():
    """REQ-004, REQ-015: la página de ruido real queda ilegible, con origen `ocr`."""
    [page] = read_pages(NOISE)

    assert page.status == PAGE_ILLEGIBLE
    assert page.origin == ORIGIN_OCR


def test_origin_and_confidence_are_optional_in_a_page():
    """REQ-015: `origin` y `confidence` son opcionales: las páginas de los otros lectores
    los dejan vacíos y siguen siendo válidas."""
    page = Page(number=1, width=612.0, height=792.0, status=PAGE_NOT_READ)

    assert (page.origin, page.confidence) == (None, None)


# --- Versiones (P6) --------------------------------------------------------------------


def test_tool_versions_include_tesseract_and_the_spanish_model():
    """REQ-004, REQ-015: el reconocimiento informa las versiones con que se hizo, para
    registrarlas con la lectura: Tesseract, pytesseract, pypdfium2 y la huella del modelo
    de español, que es el de tessdata_best que fija la imagen."""
    versions = ocr.tool_versions()

    assert versions["tesseract"] == "5.5.0"
    assert versions["pytesseract"] == "0.3.13"
    assert versions["pypdfium2"] == "5.13.0"
    assert versions["tesseract_spa_sha256"] == SPA_BEST_SHA256
