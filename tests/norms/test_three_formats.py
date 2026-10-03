"""La misma norma en tres formatos y la entrada única de lectura (T-028; ADR-0004, "Cómo
se lee" y "Cómo se prueba"; plan 001, "Ingesta" y "Cobertura de requisitos", REQ-015).

Documentos de prueba, públicos o sintéticos (P4):

- `tests/fixtures/disp-247-2022-anexo-extracto.pdf` (T-012): páginas 1 a 6 del anexo de
  la Disposición AFIP 247/2022, PDF con texto.
- `tests/fixtures/disp-247-2022-anexo-extracto-escaneado.pdf` (T-021): el mismo extracto
  dibujado como imágenes, sin capa de texto.
- `tests/fixtures/disp-247-2022-anexo-extracto.html` (esta tarea): una página web con el
  mismo texto del extracto y la estructura de las páginas de Infoleg, porque el anexo de
  la 247/2022 no está publicado como página web. Se armó una vez dentro de la imagen de
  la aplicación: cada párrafo del texto canónico del extracto en PDF es un bloque de la
  página, separado del siguiente por `<br><br>` y cortado en renglones de 70 caracteres
  como en Infoleg (los saltos de renglón del archivo son espacios para el navegador); los
  encabezados cortos van en negrita. Tiene el encabezado del sitio (`<header
  id="branding">`, `<div id="cleaner">`), un script de medición en `<head>`, declara
  ISO-8859-1 y termina con una "Nota Infoleg" que dice que la página se armó para esta
  prueba.
- Las dos páginas web del corpus (`corpus/normativa/`), que parte T-050.

Diferencia admitida entre el PDF con texto y el escaneado (decisión del Coordinador): el
reconocimiento lee el inciso "g)" del artículo 3 como "£)", y los incisos g y h de ese
artículo no se crean. No se agrega tolerancia de letra de inciso, porque el riesgo de
inventar cortes es mayor que el beneficio: el informe del escaneado lo avisa en "Requiere
atención" y el texto de los dos incisos queda dentro del artículo. Cualquier otra
diferencia hace fallar la prueba.
"""

import difflib
import io
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from evaluon.accounts import permissions
from evaluon.audit.models import AuditEvent
from evaluon.norms.management.commands.cargar_norma import Command
from evaluon.norms.models import Unit
from evaluon.norms.reading import (
    FORMAT_HTML,
    FORMAT_PDF,
    ORIGIN_OCR,
    ORIGIN_PDF_TEXT,
    ORIGIN_WEB,
    PAGE_BLANK,
    PAGE_KIND_BLANK,
    PAGE_KIND_FIELDS_ONLY,
    PAGE_KIND_SCANNED,
    PAGE_KIND_TEXT,
    PAGE_KIND_UNUSABLE_TEXT,
    PAGE_NOT_READ,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
    PageFacts,
    UnsupportedFormatError,
    Word,
    classify_page,
    detect_format,
    page_kind,
    read_document,
    unusable_text_share,
)
from evaluon.norms.reading.web import read_web
from evaluon.norms.services import loading
from evaluon.norms.splitting import split_document
from tests.conftest import TEST_PASSWORD
from tests.norms import test_splitting_disp_247_2022_cuerpo as t050_cuerpo
from tests.norms import test_splitting_disp_297_03 as t050_297
from tests.norms.test_loading import COMMAND_ARGS, run_cargar_norma

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
TEXT_PDF = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
SCANNED_PDF = FIXTURES / "disp-247-2022-anexo-extracto-escaneado.pdf"
WEB_PAGE = FIXTURES / "disp-247-2022-anexo-extracto.html"
NOISE_PDF = FIXTURES / "pagina-ruido.pdf"
ANNEX_247 = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"
BODY_247_PAGE = REPO / "corpus" / "normativa" / "disp-afip-247-2022-original.htm"
PAGE_297 = REPO / "corpus" / "normativa" / "disp-afip-297-2003-original.htm"

PART = "anexo"
CATEGORY = "regimen_especifico"

# Huella de spa.traineddata de tessdata_best 4.1.0 que fija el Dockerfile (T-005).
SPA_BEST_SHA256 = "e2c1ffdad8b30f26c45d4017a9183d3a7f9aa69e59918be4f88b126fac99ab2c"

# Diferencia admitida entre el PDF con texto y el escaneado: unidades (tipo, número,
# contenedor) que el escaneado no tiene, con el motivo. Ver la cabecera del archivo.
MISREAD_G = (
    "el reconocimiento lee la letra del inciso g) del artículo 3 como \"£)\"; sin "
    "tolerancia de letra de inciso, g y h no se crean y su texto queda en el artículo"
)
ADMITTED_MISSING_IN_SCANNED = {
    ("inciso", "g", "anexo/art-3"): MISREAD_G,
    ("inciso", "h", "anexo/art-3"): MISREAD_G,
}

# Proporción mínima de palabras del escaneado que coincide con el PDF con texto (T-021
# midió 97,9 % por página sobre las líneas del extracto).
MIN_WORD_COINCIDENCE = 0.95

# Datos de las normas del corpus, según el manifiesto y el ADR-0006.
DATA_247 = {
    "category": CATEGORY,
    "norm_type": "Disposición",
    "number": "247",
    "year": 2022,
    "issuer": "AFIP",
    "title": "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas",
    "citation": "Disposición AFIP 247/2022",
    "publication_date": date(2022, 11, 30),
    "effective_from": date(2023, 1, 1),
    "source": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/"
    "375829/norma.htm",
}
DATA_297 = {
    "category": CATEGORY,
    "norm_type": "Disposición",
    "number": "297",
    "year": 2003,
    "issuer": "AFIP",
    "title": "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas",
    "citation": "Disposición AFIP 297/2003",
    "publication_date": date(2003, 6, 13),
    "effective_from": date(2003, 6, 14),
    "source": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/85000-89999/"
    "85434/texact.htm",
}


def split(reading, part=PART):
    return split_document(reading, part=part, category=CATEGORY)


@pytest.fixture(scope="module")
def text_reading():
    return read_document(TEXT_PDF)


@pytest.fixture(scope="module")
def scanned_reading():
    return read_document(SCANNED_PDF)


@pytest.fixture(scope="module")
def web_reading():
    return read_document(WEB_PAGE)


@pytest.fixture(scope="module")
def text_split(text_reading):
    return split(text_reading)


@pytest.fixture(scope="module")
def scanned_split(scanned_reading):
    return split(scanned_reading)


@pytest.fixture(scope="module")
def web_split(web_reading):
    return split(web_reading)


def unit_list(result):
    """La lista de unidades del criterio de REQ-015: tipo, número y contenedor."""
    return [(unit.unit_type, unit.number, unit.parent_key) for unit in result.units]


def kinds(report):
    return [item["kind"] for item in report["attention"]]


def word_coincidence(expected, recognized):
    """Proporción de las palabras de `expected` que aparecen, en el mismo orden, en
    `recognized` (bloques coincidentes de `difflib.SequenceMatcher`)."""
    matcher = difflib.SequenceMatcher(a=expected, b=recognized, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(expected)


# --- Entrada única: el formato sale del contenido -------------------------------------


def test_each_format_is_detected_by_its_content():
    """REQ-015: el formato se determina por el contenido del archivo: un PDF (con texto
    o escaneado) es `pdf` y una página web guardada es `html`."""
    assert detect_format(TEXT_PDF.read_bytes()) == FORMAT_PDF
    assert detect_format(SCANNED_PDF.read_bytes()) == FORMAT_PDF
    assert detect_format(WEB_PAGE.read_bytes()) == FORMAT_HTML
    assert detect_format(BODY_247_PAGE.read_bytes()) == FORMAT_HTML
    assert detect_format(PAGE_297.read_bytes()) == FORMAT_HTML


def test_the_file_name_does_not_decide_the_format(tmp_path):
    """REQ-015: el nombre del archivo no decide: una página web llamada `.pdf` se lee como
    página web y un PDF llamado `.html`, como PDF."""
    web_as_pdf = tmp_path / "pagina.pdf"
    web_as_pdf.write_bytes(WEB_PAGE.read_bytes())
    pdf_as_web = tmp_path / "extracto.html"
    pdf_as_web.write_bytes(TEXT_PDF.read_bytes())

    assert read_document(web_as_pdf).file_format == FORMAT_HTML
    assert read_document(pdf_as_web).file_format == FORMAT_PDF


@pytest.mark.parametrize(
    "data",
    [
        b"Esto no es un PDF ni una pagina web.",
        "<html><body><p>ARTICULO 1.- Texto.</p></body></html>".encode("utf-16-le"),
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        b"",
    ],
    ids=["texto", "utf16-sin-marca", "imagen-png", "vacio"],
)
def test_other_contents_are_rejected(data):
    """REQ-015: lo que no es un PDF ni una página web se rechaza antes de leerlo, con un
    mensaje llano. Una página en UTF-16 sin marca de orden de bytes no se reconoce como
    página web (se leería como texto legible equivocado)."""
    assert detect_format(data) is None
    with pytest.raises(UnsupportedFormatError, match="no es un PDF ni una página web"):
        read_document(data)


def test_a_utf16_page_with_byte_order_mark_is_a_web_page():
    """REQ-015: una página web en UTF-16 con su marca de orden de bytes se reconoce y se
    lee."""
    data = "﻿<html><body><p>ARTÍCULO 1°.- Texto.</p></body></html>".encode("utf-16-le")
    reading = read_document(data)
    assert reading.file_format == FORMAT_HTML
    assert [line.text for line in reading.pages[0].lines] == ["ARTÍCULO 1°.- Texto."]


@pytest.mark.parametrize("cut", [0.5, 0.9], ids=["mitad", "casi-entero"])
def test_a_truncated_pdf_is_rejected_as_unreadable(cut):
    """REQ-004, REQ-015: un PDF cortado no levanta un error de la biblioteca sino el de
    archivo que no se puede leer, con un mensaje llano."""
    data = TEXT_PDF.read_bytes()
    with pytest.raises(UnsupportedFormatError, match="dañado o incompleto"):
        read_document(data[: int(len(data) * cut)])


# --- Clasificación de cada página de un PDF --------------------------------------------


@pytest.mark.parametrize(
    ("facts", "kind"),
    [
        (PageFacts(chars=900, unusable=0, image_cover=0.05, objects=True, ink=True,
                   annotations=3), PAGE_KIND_TEXT),
        (PageFacts(chars=0, unusable=0, image_cover=1.0, objects=True, ink=True,
                   annotations=0), PAGE_KIND_SCANNED),
        # Un escaneo con capa de texto oculta puesta por el escáner: se vuelve a reconocer.
        (PageFacts(chars=900, unusable=0, image_cover=0.98, objects=True, ink=True,
                   annotations=0), PAGE_KIND_SCANNED),
        (PageFacts(chars=900, unusable=300, image_cover=0.0, objects=True, ink=True,
                   annotations=0), PAGE_KIND_UNUSABLE_TEXT),
        (PageFacts(chars=900, unusable=5, image_cover=0.0, objects=True, ink=True,
                   annotations=0), PAGE_KIND_TEXT),
        (PageFacts(chars=0, unusable=0, image_cover=0.0, objects=False, ink=False,
                   annotations=0), PAGE_KIND_BLANK),
        (PageFacts(chars=0, unusable=0, image_cover=0.3, objects=True, ink=False,
                   annotations=0), PAGE_KIND_BLANK),
        # Solo dibujos o una imagen chica con tinta y sin texto: se reconoce.
        (PageFacts(chars=0, unusable=0, image_cover=0.3, objects=True, ink=True,
                   annotations=0), PAGE_KIND_SCANNED),
        # Sin texto ni tinta, pero con campos (la firma digital de la página 45 del anexo).
        (PageFacts(chars=0, unusable=0, image_cover=0.0, objects=False, ink=False,
                   annotations=5), PAGE_KIND_FIELDS_ONLY),
    ],
    ids=[
        "con-texto", "escaneada", "escaneo-con-capa-oculta", "texto-inservible",
        "pocos-caracteres-raros", "en-blanco", "objetos-sin-tinta", "dibujo-con-tinta",
        "solo-campos",
    ],
)
def test_page_kind_follows_the_adr_rules(facts, kind):
    """REQ-015, REQ-004: cada página se clasifica antes de leerla (ADR-0004, "Cómo se
    lee"): con texto; escaneada, si no tiene capa de texto o una imagen la cubre casi
    entera; con texto inservible, si su capa trae caracteres sin letra por encima del
    umbral; en blanco, sin texto y sin tinta. Una página sin texto ni tinta que trae
    campos (como la firma digital) no se da por en blanco."""
    assert page_kind(facts) == kind


@pytest.mark.parametrize(
    ("text", "unusable"),
    [
        ("ARTÍCULO 1°.- OBJETO. El presente régimen", 0),
        ("��� abc", 3),
        ("(cid:12)(cid:7) abc", 2),
        (" abc\x01", 3),
    ],
    ids=["normal", "reemplazo", "cid", "uso-privado-y-control"],
)
def test_unusable_characters_are_counted(text, unusable):
    """REQ-015: los caracteres de reemplazo, los códigos sin letra (`(cid:N)`), los de uso
    privado y los de control cuentan como texto inservible; el texto normal no."""
    assert unusable_text_share(text)[1] == unusable


def test_pages_of_the_corpus_are_classified_by_their_content():
    """REQ-015, REQ-004: las páginas del extracto son con texto, aunque la primera trae un
    logo; las del escaneado y la de ruido son escaneadas; una página nueva sin nada es en
    blanco; la página 45 del anexo, que trae solo los campos de la firma digital, no es en
    blanco ni se reconoce."""
    assert [classify_page(page) for page in pdfium.PdfDocument(TEXT_PDF)] == [PAGE_KIND_TEXT] * 6
    assert [classify_page(page) for page in pdfium.PdfDocument(SCANNED_PDF)] == [
        PAGE_KIND_SCANNED
    ] * 6
    assert classify_page(pdfium.PdfDocument(NOISE_PDF)[0]) == PAGE_KIND_SCANNED
    blank = pdfium.PdfDocument.new()
    assert classify_page(blank.new_page(612, 792)) == PAGE_KIND_BLANK
    assert classify_page(pdfium.PdfDocument(ANNEX_247)[44]) == PAGE_KIND_FIELDS_ONLY


def test_a_blank_page_is_reported_blank_and_not_as_not_read():
    """REQ-004: una página en blanco insertada en un PDF se informa en blanco: no cuenta
    entre las no leídas ni se reconoce; las demás se leen como texto."""
    source = pdfium.PdfDocument(TEXT_PDF)
    pdf = pdfium.PdfDocument.new()
    pdf.import_pages(source, pages=[0])
    pdf.new_page(612, 792)
    pdf.import_pages(source, pages=[1])

    buffer = io.BytesIO()
    pdf.save(buffer)
    reading = read_document(buffer.getvalue())

    assert [page.status for page in reading.pages] == [PAGE_READ, PAGE_BLANK, PAGE_READ]
    assert [page.classification for page in reading.pages] == [
        PAGE_KIND_TEXT, PAGE_KIND_BLANK, PAGE_KIND_TEXT
    ]
    assert reading.pages_not_read == []
    assert reading.pages[1].lines == []
    report = split(reading).report
    assert report["page_summary"]["blank"] == [2]
    assert report["page_summary"]["without_text"] == []


# --- Lectura de cada formato -----------------------------------------------------------


def test_text_pdf_is_read_from_its_text_layer(text_reading):
    """REQ-015: el PDF con texto se lee de su capa de texto, sin reconocimiento: todas
    sus páginas legibles, con origen `pdf_text`, y sin las versiones del reconocimiento."""
    assert text_reading.file_format == FORMAT_PDF
    assert [page.classification for page in text_reading.pages] == [PAGE_KIND_TEXT] * 6
    assert all(page.status == PAGE_READ for page in text_reading.pages)
    assert {line.origin for page in text_reading.pages for line in page.lines} == {
        ORIGIN_PDF_TEXT
    }
    assert "tesseract" not in text_reading.tool_versions
    assert text_reading.tool_versions["pdfplumber"]


def test_scanned_pdf_is_recognized_and_records_the_spanish_model(scanned_reading):
    """REQ-015, REQ-004: el PDF escaneado se reconoce página por página: origen `ocr`,
    confianza de cada página, y las versiones de las herramientas con la huella del
    modelo de español (P6)."""
    assert scanned_reading.file_format == FORMAT_PDF
    assert [page.classification for page in scanned_reading.pages] == [PAGE_KIND_SCANNED] * 6
    assert all(page.status == PAGE_READ for page in scanned_reading.pages)
    assert all(page.origin == ORIGIN_OCR and page.confidence for page in scanned_reading.pages)
    assert {line.origin for page in scanned_reading.pages for line in page.lines} == {ORIGIN_OCR}
    versions = scanned_reading.tool_versions
    assert versions["tesseract_spa_sha256"] == SPA_BEST_SHA256
    assert versions["tesseract"] and versions["pytesseract"] and versions["pypdfium2"]


def test_web_page_is_read_with_its_detected_encoding(web_reading):
    """REQ-015: la página web se lee con `web.py`, con origen `web`; la codificación
    detectada queda con la lectura (P6) y la nota de Infoleg sale descartada."""
    assert web_reading.file_format == FORMAT_HTML
    assert web_reading.encoding == "cp1252"
    assert web_reading.tool_versions["beautifulsoup4"]
    lines = web_reading.pages[0].lines
    assert {line.origin for line in lines} == {ORIGIN_WEB}
    assert any(line.discarded == "nota de Infoleg" for line in lines)
    assert web_reading.as_json()["encoding"] == "cp1252"


def test_reading_through_the_single_entry_equals_the_web_reader():
    """REQ-015: la entrada única lee una página web igual que `web.py`, la lectura que
    usan las pruebas de T-050."""
    for path in (BODY_247_PAGE, PAGE_297, WEB_PAGE):
        single = read_document(path)
        direct = read_web(path.read_bytes())
        assert single.pages == direct.pages
        assert single.tool_versions == direct.tool_versions


# --- La misma norma en tres formatos (criterio de REQ-015) -----------------------------


def test_text_pdf_and_web_page_give_the_same_units(text_split, web_split):
    """REQ-015: el PDF con texto y la página web dan la misma lista de unidades (tipo,
    número y contenedor), en el mismo orden."""
    assert unit_list(web_split) == unit_list(text_split)
    assert len(text_split.units) == 21


def test_text_pdf_and_web_page_give_the_same_words_in_each_unit(text_split, web_split):
    """REQ-015: entre el PDF con texto y la página web, cada artículo (y cada unidad)
    tiene la misma secuencia de palabras."""
    articles = 0
    for pdf_unit, web_unit in zip(text_split.units, web_split.units, strict=True):
        assert web_unit.text.split() == pdf_unit.text.split(), pdf_unit.key
        articles += pdf_unit.unit_type == "articulo"
    assert articles == 7


def test_scanned_pdf_gives_the_same_units_except_the_admitted_difference(
    text_split, scanned_split
):
    """REQ-015: el escaneado da la misma lista de unidades que el PDF con texto, en el
    mismo orden, salvo la diferencia admitida y declarada: los incisos g y h del artículo
    3, por la "g)" leída como "£)". Una unidad de más o cualquier otra que falte hace
    fallar la prueba."""
    expected = unit_list(text_split)
    found = unit_list(scanned_split)
    missing = [unit for unit in expected if unit not in found]
    extra = [unit for unit in found if unit not in expected]

    assert extra == []
    assert set(missing) == set(ADMITTED_MISSING_IN_SCANNED)
    assert len(missing) == len(ADMITTED_MISSING_IN_SCANNED)
    assert found == [unit for unit in expected if unit not in ADMITTED_MISSING_IN_SCANNED]


def test_every_scanned_unit_says_it_comes_from_recognition(scanned_split):
    """REQ-015: en el escaneado, todas las unidades tienen origen `ocr` y su confianza
    mínima y promedio; el informe lo dice en "Requiere atención" y en su parte de
    reconocimiento sobre imagen."""
    assert scanned_split.units
    for unit in scanned_split.units:
        assert unit.text_origin == ORIGIN_OCR, unit.key
        assert unit.ocr_confidence_min is not None and unit.ocr_confidence_avg is not None
    report = scanned_split.report
    assert report["ocr"]["units"] == len(scanned_split.units)
    assert "ocr" in kinds(report)
    assert f"{len(scanned_split.units)} unidades tienen texto reconocido sobre imagen" in (
        scanned_split.report_text
    )
    assert "Reconocimiento sobre imagen" in scanned_split.report_text


def test_text_and_web_units_do_not_say_recognition(text_split, web_split):
    """REQ-015: en el PDF con texto y en la página web ninguna unidad viene de
    reconocimiento: origen `pdf_text` y `web`, sin confianza."""
    assert {unit.text_origin for unit in text_split.units} == {ORIGIN_PDF_TEXT}
    assert {unit.text_origin for unit in web_split.units} == {ORIGIN_WEB}
    for result in (text_split, web_split):
        assert all(unit.ocr_confidence_min is None for unit in result.units)
        assert result.report["ocr"]["units"] == 0
        assert "ocr" not in kinds(result.report)


def test_share_of_scanned_words_that_coincide_with_the_text_pdf(text_split, scanned_split):
    """REQ-015: se mide y se informa qué proporción de las palabras del PDF con texto
    coincide, en el mismo orden, con las del escaneado (sobre el texto extraído
    completo)."""
    share = word_coincidence(text_split.canonical_text.split(), scanned_split.canonical_text.split())
    print(f"\nProporción de palabras del escaneado que coincide con el PDF con texto: {share:.4f}")
    assert share >= MIN_WORD_COINCIDENCE


def test_scanned_report_warns_about_the_skipped_inciso_letters(scanned_split, text_split, web_split):
    """REQ-004, REQ-015: el informe del escaneado avisa en "Requiere atención" que la
    lista de incisos del artículo 3 salta de f) a h) y que hay un párrafo que empieza como
    un inciso mal leído ("£)"); el PDF con texto y la página web no traen ese aviso. Las
    unidades no cambian por el aviso."""
    gaps = scanned_split.report["ocr_inciso_gaps"]
    assert [(gap["key"], gap["after"], gap["found"], gap["missing"]) for gap in gaps] == [
        ("anexo/art-3", "f", "£)", []),
        ("anexo/art-3", "f", "h)", ["g"]),
    ]
    assert all(gap["page"] == 6 for gap in gaps)
    item = next(i for i in scanned_split.report["attention"] if i["kind"] == "ocr_inciso_gaps")
    assert "anexo/art-3" in item["text"] and "falta g)" in item["text"]
    assert item["text"] in scanned_split.report_text
    for result in (text_split, web_split):
        assert result.report["ocr_inciso_gaps"] == []
        assert "ocr_inciso_gaps" not in kinds(result.report)


# --- Carga de los tres formatos ---------------------------------------------------------


def load(user, path, part=PART, data=DATA_247, **options):
    return loading.load_norm(
        user,
        data=path.read_bytes(),
        file_name=path.name,
        part=part,
        general_regime=True,
        **data,
        **options,
    )


def stored_units(reading):
    return list(
        Unit.objects.filter(reading=reading)
        .order_by("order")
        .values_list("unit_type", "number", "parent__key")
    )


@pytest.mark.django_db
def test_the_three_formats_load_with_their_detected_format(read_write_user):
    """REQ-015, REQ-004: la misma norma se carga en los tres formatos (la segunda y la
    tercera con la confirmación de "misma norma", como otro archivo de lo mismo): cada
    documento guarda su formato detectado, sus unidades quedan citables con su origen y la
    lectura guarda las versiones de sus herramientas."""
    text = load(read_write_user, TEXT_PDF)
    web = load(read_write_user, WEB_PAGE, same_norm_confirmation="other_file")
    scanned = load(read_write_user, SCANNED_PDF, same_norm_confirmation="other_file")

    assert [r.document.file_format for r in (text, web, scanned)] == ["pdf", "html", "pdf"]
    assert stored_units(web.reading) == stored_units(text.reading)
    expected = [unit for unit in stored_units(text.reading)
                if unit not in ADMITTED_MISSING_IN_SCANNED]
    assert stored_units(scanned.reading) == expected
    origins = {
        result.document.file_name: set(result.reading.units.values_list("text_origin", flat=True))
        for result in (text, web, scanned)
    }
    assert origins == {
        TEXT_PDF.name: {ORIGIN_PDF_TEXT},
        WEB_PAGE.name: {ORIGIN_WEB},
        SCANNED_PDF.name: {ORIGIN_OCR},
    }
    assert scanned.reading.tool_versions["tesseract_spa_sha256"] == SPA_BEST_SHA256
    assert "tesseract" not in text.reading.tool_versions
    assert web.reading.pages["encoding"] == "cp1252"
    assert "ocr_inciso_gaps" in [i["kind"] for i in scanned.reading.report["attention"]]
    assert "Reconocimiento sobre imagen" in scanned.reading.report_text


@pytest.mark.django_db
def test_load_event_records_format_encoding_and_tool_versions(read_write_user):
    """REQ-012, REQ-015: el hecho `load` registra el formato detectado, la codificación de
    la página web y las versiones de las herramientas, con la huella del modelo de
    español cuando hubo reconocimiento (P6)."""
    web = load(read_write_user, WEB_PAGE)
    scanned = load(read_write_user, SCANNED_PDF, same_norm_confirmation="other_file")

    web_event = AuditEvent.objects.get(pk=web.event.pk)
    assert web_event.detail["file"]["format"] == "html"
    assert web_event.detail["file"]["encoding"] == "cp1252"
    assert web_event.detail["tool_versions"]["beautifulsoup4"]
    scanned_event = AuditEvent.objects.get(pk=scanned.event.pk)
    assert scanned_event.detail["file"]["format"] == "pdf"
    assert "encoding" not in scanned_event.detail["file"]
    assert scanned_event.detail["tool_versions"]["tesseract_spa_sha256"] == SPA_BEST_SHA256


@pytest.mark.django_db
def test_the_corpus_web_pages_load_with_the_units_of_t050(read_write_user):
    """REQ-015, REQ-003: las dos páginas web del corpus, cargadas por la entrada única, dan
    las mismas unidades que las pruebas de T-050 (que las leen con `web.py`): misma clave,
    tipo, número, etiqueta, ruta y texto, y los artículos de sus tablas esperadas."""
    body_247 = load(read_write_user, BODY_247_PAGE, part="cuerpo")
    norm_297 = load(read_write_user, PAGE_297, part="cuerpo", data=DATA_297)

    for result, path in ((body_247, BODY_247_PAGE), (norm_297, PAGE_297)):
        assert result.document.file_format == "html"
        expected = split_document(read_web(path.read_bytes()), part="cuerpo")
        stored = list(
            Unit.objects.filter(reading=result.reading)
            .order_by("order")
            .values_list("key", "unit_type", "number", "label", "path", "text", "text_origin")
        )
        assert stored == [
            (u.key, u.unit_type, u.number, u.label, u.path, u.text, u.text_origin)
            for u in expected.units
        ]
        assert result.reading.canonical_text == expected.canonical_text

    keys_247 = [key for key in body_247.reading.units.order_by("order").values_list("key", flat=True)]
    assert keys_247 == [row[0] for row in t050_cuerpo.EXPECTED]
    articles_297 = list(
        norm_297.reading.units.filter(unit_type="articulo")
        .order_by("order")
        .values_list("key", flat=True)
    )
    assert articles_297 == [f"art-{n}" for n in t050_297.EXPECTED_BODY] + [
        f"anexo-i/art-{row[0]}" for row in t050_297.EXPECTED_ANNEX
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("path", [WEB_PAGE, SCANNED_PDF], ids=["web", "escaneado"])
def test_reread_accepts_web_and_scanned_documents(read_write_user, path):
    """REQ-004, REQ-015: `releer_norma` vuelve a leer una página web y un PDF escaneado
    desde el original guardado, comprobando su huella, y da las mismas unidades."""
    first = load(read_write_user, path)
    result = loading.reread_document(read_write_user, first.document.pk)

    assert result.reading.sequence == 2
    assert stored_units(result.reading) == stored_units(first.reading)
    assert result.reading.canonical_sha256 == first.reading.canonical_sha256
    detail = AuditEvent.objects.get(pk=result.event.pk).detail
    assert detail["file"]["sha256"] == first.document.file_sha256
    assert detail["file"]["format"] == first.document.file_format


@pytest.mark.django_db
def test_reread_of_an_altered_web_original_is_refused(read_write_user):
    """REQ-004, REQ-002: si el original guardado de una página web no coincide con la
    huella registrada, la relectura no se hace."""
    first = load(read_write_user, WEB_PAGE)
    stored = first.document.file
    stored.content = bytes(stored.content).replace(b"Integridad", b"Integridaz")
    stored.save()

    with pytest.raises(loading.StoredFileAltered):
        loading.reread_document(read_write_user, first.document.pk)


@pytest.mark.django_db
def test_a_file_that_is_neither_pdf_nor_web_is_refused_with_a_plain_message(read_write_user):
    """REQ-015, REQ-004: un archivo que no es PDF ni página web no se incorpora; el
    mensaje nombra los formatos que se aceptan."""
    with pytest.raises(loading.UnreadableFile, match="no es un PDF ni una página web"):
        loading.load_norm(
            read_write_user, data=b"Texto suelto.", file_name="norma.txt", part=PART,
            general_regime=True, **DATA_247,
        )


# --- Aviso de incisos salteados en el reconocimiento (decisión del Coordinador) --------


def synthetic_reading(texts, origin):
    """Una página con un párrafo por línea, con el origen indicado; en `ocr`, cada
    palabra con confianza 95."""
    lines = []
    for index, text in enumerate(texts):
        top = 100.0 + 30 * index
        words = [Word(text=word, confidence=95.0) for word in text.split()] if origin == ORIGIN_OCR else []
        lines.append(
            Line(
                text=text, x0=72.0, top=top, x1=300.0, bottom=top + 12, origin=origin,
                confidence=95.0 if origin == ORIGIN_OCR else None, words=words,
            )
        )
    page = Page(number=1, width=612.0, height=792.0, status=PAGE_READ, lines=lines,
                origin=origin)
    return DocumentReading(file_format=FORMAT_PDF, pages=[page], tool_versions={})


SKIPPED_LIST = [
    "ARTÍCULO 1°.- PRINCIPIOS. Son principios:",
    "a) Uno.",
    "b) Dos.",
    "c) Tres.",
    "f) Seis.",
    "g) Siete.",
    "ARTÍCULO 2°.- OTRO. Son casos:",
    "a) Primero.",
    "£) Segundo mal leído.",
]


def test_skipped_inciso_letters_in_recognition_are_reported_without_changing_units():
    """REQ-004, REQ-015: en una lectura de reconocimiento, una lista que salta de c) a f)
    y un párrafo que empieza con "£)" después de a) se señalan en "Requiere atención",
    una vez por lista; las unidades son las mismas que da el mismo texto en un PDF con
    texto, que no trae el aviso."""
    ocr_result = split_document(synthetic_reading(SKIPPED_LIST, ORIGIN_OCR), part="cuerpo")
    text_result = split_document(synthetic_reading(SKIPPED_LIST, ORIGIN_PDF_TEXT), part="cuerpo")

    assert [u.key for u in ocr_result.units] == [u.key for u in text_result.units] == [
        "art-1", "art-1/inc-a", "art-1/inc-b", "art-1/inc-c", "art-2", "art-2/inc-a",
    ]
    assert [u.text for u in ocr_result.units] == [u.text for u in text_result.units]
    gaps = ocr_result.report["ocr_inciso_gaps"]
    assert [(g["key"], g["after"], g["found"], g["missing"], g["page"]) for g in gaps] == [
        ("art-1", "c", "f)", ["d", "e"], 1),
        ("art-2", "a", "£)", [], 1),
    ]
    assert gaps[1]["first_words"] == "£) Segundo mal leído."
    item = next(i for i in ocr_result.report["attention"] if i["kind"] == "ocr_inciso_gaps")
    assert "art-1 (página 1): después de c) sigue f), faltan d), e)" in item["text"]
    assert 'art-2 (página 1): después de a) sigue "£) Segundo mal leído.…"' in item["text"]
    assert "Listas de incisos leídas por reconocimiento sobre imagen con letras salteadas" in (
        ocr_result.report_text
    )
    assert text_result.report["ocr_inciso_gaps"] == []
    assert "ocr_inciso_gaps" not in kinds(text_result.report)


def test_a_complete_recognized_list_has_no_warning():
    """REQ-004: una lista de incisos completa, leída por reconocimiento, no trae el
    aviso; tampoco la eñe que se saltea (de n) a o))."""
    texts = ["ARTÍCULO 1°.- LISTA. Son:"] + [f"{letter}) Texto." for letter in "abcdefghijklmnop"]
    result = split_document(synthetic_reading(texts, ORIGIN_OCR), part="cuerpo")

    assert result.report["ocr_inciso_gaps"] == []
    assert len([u for u in result.units if u.unit_type == "inciso"]) == 16


# --- Comando cargar_norma ---------------------------------------------------------------


@pytest.mark.django_db
def test_command_names_the_recognized_format(read_write_user, monkeypatch):
    """REQ-015, REQ-004: `cargar_norma` acepta los tres formatos, dice cuál reconoció y,
    en el escaneado, cuántas unidades tienen texto reconocido sobre imagen."""
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    common = [*COMMAND_ARGS, "--parte", "anexo", "--regimen-general",
              "--confirmar-misma-norma", "otro-archivo"]
    outputs = {
        path.name: run_cargar_norma(str(path), *common, usuario=read_write_user.username)
        for path in (TEXT_PDF, WEB_PAGE, SCANNED_PDF)
    }

    assert "Formato reconocido: PDF con texto." in outputs[TEXT_PDF.name]
    assert "Formato reconocido: página web." in outputs[WEB_PAGE.name]
    assert "Formato reconocido: PDF escaneado." in outputs[SCANNED_PDF.name]
    assert "19 unidades tienen texto reconocido sobre imagen" in outputs[SCANNED_PDF.name]
    assert "reconocido sobre imagen" not in outputs[TEXT_PDF.name]


def test_command_help_names_the_three_formats():
    """REQ-015: la ayuda de `cargar_norma` ya no dice solo "(PDF)": nombra los tres
    formatos."""
    parser = Command().create_parser("manage.py", "cargar_norma")
    help_text = " ".join(parser.format_help().split())
    assert "(PDF)" not in help_text
    assert "PDF escaneado" in help_text and "página web" in help_text
