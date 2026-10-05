"""Lectura de fotos, segundo intento y Word (REQ-038; plan 008, "Carga y lectura"; ADR-0028;
T-131). Las imágenes se arman acá con texto inventado: una página con texto, torcida, con
una sombra, ruido y desenfoque, como una foto de celular. Todo corre en el equipo."""

import io
import random
import zipfile
from dataclasses import replace

import pypdfium2 as pdfium
import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from evaluon.norms.reading import PAGE_DOUBTFUL, PAGE_ILLEGIBLE, PAGE_READ, read_document
from evaluon.offers import reading as tools
from tests.tenders.pdfs import FONT_CANDIDATES, para, tender_pdf

TEXT = ["CONSTANCIA DE INSCRIPCION EN EL REGISTRO",
        "Se deja constancia de que el Oferente Sintetico se",
        "encuentra inscripto en el registro de proveedores",
        "con el numero 000123 desde el 10 de marzo de 2025.",
        "La presente constancia se emite a pedido del",
        "interesado para ser presentada ante el organismo."]
FONT = next(path for path in FONT_CANDIDATES if path.exists())


def synthetic_page(width=1654, height=2339, size=44):
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), size)
    y = 200
    for line in TEXT * 3:
        draw.text((150, y), line, font=font, fill=20)
        y += size * 2
    return image


def synthetic_photo(angle, shadow, noise, blur, *, seed=5):
    """Una foto torcida `angle` grados, con una sombra de `shadow` niveles, `noise` por
    ciento de puntos al azar y desenfoque `blur`."""
    rng = random.Random(seed)
    image = synthetic_page().rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    gradient = Image.linear_gradient("L").resize(image.size).rotate(20)
    image = ImageChops.multiply(image, gradient.point(lambda v: int(255 - shadow * v / 255)))
    image = image.filter(ImageFilter.GaussianBlur(blur))
    pixels = image.load()
    for _ in range(int(noise * image.width * image.height / 100)):
        pixels[rng.randrange(image.width), rng.randrange(image.height)] = rng.randrange(256)
    return image.convert("RGB")


def jpeg(image, quality=60):
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def png(image):
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def words(reading):
    return " ".join(line.text for page in reading.pages for line in page.lines)


# --- Formatos -----------------------------------------------------------------------------


def test_the_upload_format_is_detected_by_content_not_by_name():
    """REQ-038: PDF, JPG y PNG se reconocen por su contenido."""
    image = synthetic_page().convert("RGB")
    assert tools.detect_upload_format(tender_pdf([[para("x")]], header=None)) == "pdf"
    assert tools.detect_upload_format(jpeg(image)) == "jpg"
    assert tools.detect_upload_format(png(image)) == "png"
    assert tools.detect_upload_format(b"texto cualquiera") is None
    assert tools.detect_upload_format(b"PK\x03\x04no es un zip") is None


def test_a_damaged_photo_is_refused():
    """REQ-038: una foto cortada no se acepta."""
    with pytest.raises(tools.UnreadableFile):
        tools.check_image(jpeg(synthetic_page().convert("RGB"))[:200])


@pytest.mark.parametrize("make, kind", [(jpeg, "jpg"), (png, "png")])
def test_a_clean_photo_becomes_a_one_page_pdf_and_is_read(make, kind):
    """REQ-038: la foto se convierte a un PDF de una página, dentro del equipo, y se lee."""
    pdf = tools.to_pdf(make(synthetic_page().convert("RGB")), kind)
    assert len(pdfium.PdfDocument(pdf)) == 1
    reading = read_document(pdf)
    assert reading.pages[0].status == PAGE_READ
    assert reading.pages[0].classification == "escaneada"
    assert "registro de proveedores" in words(reading)


def test_a_photo_with_an_orientation_mark_is_turned_upright():
    """REQ-038: las fotos de celular traen la orientación en una marca; la página sale derecha."""
    rotated = synthetic_page().convert("RGB").rotate(90, expand=True)
    exif = Image.Exif()
    exif[0x0112] = 6  # hay que girarla 90 grados a la derecha para verla derecha
    out = io.BytesIO()
    rotated.save(out, format="JPEG", quality=90, exif=exif)
    assert "registro de proveedores" in words(read_document(tools.photo_to_pdf(out.getvalue())))


# --- Segundo intento ----------------------------------------------------------------------


def test_the_skew_is_estimated_from_the_text_lines():
    """REQ-038: el enderezado encuentra los grados que torció la foto."""
    crooked = synthetic_photo(7, 0, 0, 0).convert("L")
    assert tools.estimate_skew(crooked) == pytest.approx(-7, abs=0.5)
    assert tools.estimate_skew(synthetic_page()) == 0.0


def test_a_good_page_is_not_read_again_and_keeps_its_text():
    """REQ-038: las páginas buenas no cambian de texto ni se releen."""
    text_pdf = tender_pdf([[para("Texto con capa de texto.")]], header=None)
    scan = tools.photo_to_pdf(jpeg(synthetic_page().convert("RGB")))
    for source in (text_pdf, scan):
        plain = read_document(source)
        reading, attempts = tools.read_with_second_attempt(source)
        assert attempts == []
        assert reading.pages == plain.pages


def test_a_crooked_noisy_photo_is_read_the_second_time_and_the_report_says_which():
    """REQ-038: una página que la primera lectura no pudo leer se vuelve a leer enderezada y con
    umbral adaptativo; se conserva la de mayor confianza y se informa cuál."""
    pdf = tools.photo_to_pdf(jpeg(synthetic_photo(7, 200, 5, 3)))
    assert read_document(pdf).pages[0].status == PAGE_ILLEGIBLE
    reading, attempts = tools.read_with_second_attempt(pdf)
    page = reading.pages[0]
    assert len(attempts) == 1 and attempts[0]["page"] == 1
    assert attempts[0]["kept"] == tools.KEPT_SECOND
    assert attempts[0]["second_confidence"] > (attempts[0]["first_confidence"] or -1)
    assert page.status in (PAGE_READ, PAGE_DOUBTFUL) and page.lines
    assert "registro de proveedores" in words(reading)


def test_a_page_that_stays_unreadable_keeps_the_first_reading_and_stays_listed():
    """REQ-038: si el segundo intento no mejora, la página sigue sin leer (va a la lista) y el
    informe dice que se conservó la primera."""
    pdf = tools.photo_to_pdf(jpeg(synthetic_photo(6, 120, 8, 4.5)))
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert reading.pages[0].status == PAGE_ILLEGIBLE and not reading.pages[0].lines
    assert attempts[0]["kept"] == tools.KEPT_FIRST


def test_the_reading_with_more_confidence_is_the_one_kept(monkeypatch):
    """REQ-038: se conserva la lectura de mayor confianza; sin palabras vale menos que
    cualquier confianza."""
    pdf = tools.photo_to_pdf(jpeg(synthetic_photo(6, 120, 8, 4.5)))
    base = read_document(pdf).pages[0]
    poor = replace(base, status=PAGE_ILLEGIBLE, confidence=10.0)
    monkeypatch.setattr(tools, "_second_read", lambda *args: (poor, 0.0))
    _, attempts = tools.read_with_second_attempt(pdf)
    assert attempts[0]["kept"] == tools.KEPT_SECOND  # la primera no tenía palabras
    assert tools._confidence(base) < tools._confidence(poor)
    better = replace(base, confidence=30.0)
    assert tools._confidence(better) > tools._confidence(poor)


# --- Word ---------------------------------------------------------------------------------


def make_docx(paragraphs, rows=()):
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    if rows:
        body += "<w:tbl>" + "".join(
            "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>"
                               for c in row) + "</w:tr>" for row in rows) + "</w:tbl>"
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.'
           f'openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", xml)
    return out.getvalue()


def test_a_word_document_is_converted_to_a_pdf_with_text_and_tables_inside_the_equipment():
    """REQ-038: un .docx se convierte a un PDF con su texto y sus tablas, sin servicios
    externos."""
    data = make_docx(["HOJA TÉCNICA", "Resma de papel A4 de 75 gramos."],
                     rows=[("Renglón", "Cantidad"), ("1", "100")])
    assert tools.detect_upload_format(data) == "docx"
    reading = read_document(tools.to_pdf(data, "docx"))
    text = words(reading)
    assert "HOJA TÉCNICA" in text and "Resma de papel A4" in text
    assert "Renglón" in text and "100" in text
    assert reading.pages[0].classification == "con_texto"


def test_a_damaged_or_empty_word_document_is_refused():
    """REQ-038: un Word dañado o sin texto no se convierte."""
    with pytest.raises(tools.UnreadableFile):
        tools.docx_to_pdf(b"PK\x03\x04roto")
    with pytest.raises(tools.UnreadableFile):
        tools.docx_to_pdf(make_docx([]))
