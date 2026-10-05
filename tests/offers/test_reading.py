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


# --- Foto de pantalla con una tabla (T-136) -------------------------------------------------

TABLE_HEADER = ["Renglon", "Alternativa", "Descripcion", "Cantidad", "Unidad", "Precio",
                "Precio"]
TABLE_ROWS = [("1", "1", "RESMA DE PAPEL", "2700,00", "kg", "7.390,00", "19.953.000,00"),
              ("2", "1", "RESMA DE PAPEL", "8760,00", "kg", "7.760,00", "67.977.600,00"),
              ("3", "1", "RESMA DE PAPEL", "250,00", "kg", "12.000,00", "3.000.000,00"),
              ("4", "1", "RESMA DE PAPEL", "360,00", "kg", "12.000,00", "4.320.000,00"),
              ("5", "1", "RESMA DE PAPEL", "200,00", "kg", "11.000,00", "2.200.000,00"),
              ("6", "1", "RESMA DE PAPEL", "300,00", "kg", "11.500,00", "3.450.000,00")]
TABLE_PRICES = [cell for row in TABLE_ROWS for cell in row[-2:]]


def screen_photo(width=1600, height=640, moire=30, shear=0.03, blur=0.8, noise=0.002, seed=3):
    """Una foto de la pantalla de un portal inventado: una tabla con rejilla, la columna del
    renglón con fondo verde, cantidades y precios; vista en perspectiva, con moiré (una trama
    de rayas finas) y un poco de desenfoque."""
    rng = random.Random(seed)
    image = Image.new("RGB", (width, height), (232, 232, 232))
    draw = ImageDraw.Draw(image)
    small = ImageFont.truetype(str(FONT), 17)
    big = ImageFont.truetype(str(FONT), 30)
    draw.text((20, 18), "Detalle de oferta por renglon", font=small, fill=(20, 20, 20))
    columns = [20, 150, 280, 620, 790, 900, 1130, 1380]
    top, row_h = 60, 58
    for i, title in enumerate(TABLE_HEADER):
        draw.rectangle([columns[i], top, columns[i + 1], top + 50], fill=(190, 190, 190))
        draw.text((columns[i] + 6, top + 14), title, font=small, fill=(30, 30, 30))
    for r, row in enumerate(TABLE_ROWS):
        y = top + 50 + r * row_h
        draw.rectangle([columns[0], y, columns[1], y + row_h], fill=(160, 210, 150))
        for c, cell in enumerate(row):
            font = big if c == 0 else small
            draw.text((columns[c] + 8, y + (6 if c == 0 else 18)), cell, font=font,
                      fill=(25, 25, 25))
    for x in columns:
        draw.line([x, top, x, top + 50 + len(TABLE_ROWS) * row_h], fill=(90, 90, 90), width=2)
    for r in range(len(TABLE_ROWS) + 2):
        y = top + (0 if r == 0 else 50 + (r - 1) * row_h)
        draw.line([columns[0], y, columns[-1], y], fill=(90, 90, 90), width=2)
    # perspectiva: un lado de la foto más alto que el otro
    coeffs = (1, shear, -shear * 40, 0.0, 1, 0, 0, shear / 400)
    image = image.transform(image.size, Image.PERSPECTIVE, coeffs, Image.BICUBIC,
                            fillcolor=(232, 232, 232))
    stripes = Image.new("L", image.size, 0)
    sd = ImageDraw.Draw(stripes)
    for x in range(0, width, 3):
        sd.line([x, 0, x + 40, height], fill=moire, width=1)
    image = ImageChops.subtract(image, Image.merge("RGB", (stripes, stripes, stripes)))
    image = image.filter(ImageFilter.GaussianBlur(blur))
    pixels = image.load()
    for _ in range(int(noise * width * height)):
        pixels[rng.randrange(width), rng.randrange(height)] = (rng.randrange(256),) * 3
    return image


def screen_pdf(**kwargs):
    out = io.BytesIO()
    screen_photo(**kwargs).save(out, format="JPEG", quality=60)
    return tools.photo_to_pdf(out.getvalue())


def amounts_in(reading):
    text = words(reading)
    return sum(1 for price in TABLE_PRICES if price in text)


def page_of(status, words_conf, origin="ocr", number=1):
    """Una página ya leída con las palabras dadas: `[(texto, confianza)]` en una línea."""
    from evaluon.norms.reading import Line, Page, Word

    cells = [Word(text=t, confidence=c) for t, c in words_conf]
    average = sum(c for _, c in words_conf) / len(words_conf) if words_conf else None
    lines = [Line(text=" ".join(t for t, _ in words_conf), x0=0.0, top=0.0, x1=1.0, bottom=1.0,
                  origin=origin, confidence=average, words=cells)] if cells else []
    return Page(number=number, width=100.0, height=100.0, status=status, lines=lines,
                origin=origin, confidence=average)


def table_words(good=8):
    """Palabras de una tabla: `good` importes bien formados y cantidades."""
    return [(f"{n}.390,00", 80.0) for n in range(1, good + 1)] + [("kg", 80.0)] * 2


def stub_reading(monkeypatch, first, *, second=None, table=None):
    """Dobles de las tres lecturas de una página: la normal, la preparada y la de tabla."""
    from evaluon.norms.reading import DocumentReading

    pdf = tender_pdf([[para("x")]], header=None)
    monkeypatch.setattr(tools, "read_document", lambda source: DocumentReading(
        file_format="pdf", pages=[first], tool_versions={}))
    monkeypatch.setattr(tools, "_second_read",
                        lambda page, number: (second or page_of("ilegible", []), 0.0))
    monkeypatch.setattr(tools, "_table_read",
                        lambda page, number: table or page_of("ilegible", []))
    return pdf


def test_a_doubtful_page_gets_a_second_attempt_even_with_confidence_above_fifty(monkeypatch):
    """REQ-038 (T-136): toda página dudosa tiene segundo intento; antes solo lo tenían las de
    menos de 50 % de confianza."""
    first = page_of("dudosa", [("Detalle", 71.0)] * 4)
    assert first.status == PAGE_DOUBTFUL and tools._needs_second_attempt(first)
    pdf = stub_reading(monkeypatch, first)
    _, attempts = tools.read_with_second_attempt(pdf)
    assert len(attempts) == 1 and attempts[0]["first_status"] == "dudosa"
    assert attempts[0]["kept"] == tools.KEPT_FIRST
    legible = page_of("legible", [("Detalle", 90.0)] * 130)
    assert not tools._needs_second_attempt(legible) and not tools._is_sparse(legible)
    assert not tools._needs_second_attempt(page_of("dudosa", [("x", 71.0)], origin="pdf_text"))


def test_the_table_reading_wins_when_it_brings_more_well_formed_amounts(monkeypatch):
    """REQ-038 (T-136): en una página de tabla se conserva la lectura de tabla aunque su
    confianza promedio sea menor, si trae más importes bien formados; el informe lo dice."""
    first = page_of("dudosa", [("Detalle", 71.0)] * 6 + [("19953.000,00", 70.0)] * 6
                    + [("2700,00", 80.0)])
    table = page_of("dudosa", table_words(10))
    table = replace(table, confidence=60.0)
    pdf = stub_reading(monkeypatch, first, table=table)
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert attempts[0]["kept"] == tools.KEPT_TABLE
    assert attempts[0]["table_confidence"] == 60.0 and attempts[0]["first_confidence"] > 60.0
    assert reading.pages[0] is not first and "1.390,00" in words(reading)


def test_the_table_reading_is_not_kept_for_a_text_page_or_with_fewer_amounts(monkeypatch):
    """REQ-038 (T-136): una lectura de tabla sin cifras de sobra, o con menos importes que la
    mejor, no reemplaza la lectura anterior."""
    first = page_of("dudosa", table_words(8))
    pdf = stub_reading(monkeypatch, first, table=page_of("dudosa", table_words(3)))
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert attempts[0]["kept"] == tools.KEPT_FIRST and reading.pages[0] is first
    prose = page_of("dudosa", [("palabra", 90.0)] * 40 + [("1", 90.0)] * 2)
    assert not tools._looks_tabular(prose)
    pdf = stub_reading(monkeypatch, page_of("dudosa", [("a", 60.0)] * 3), table=prose)
    assert tools.read_with_second_attempt(pdf)[1][0]["kept"] == tools.KEPT_FIRST


def test_a_legible_page_with_almost_no_text_is_probed_and_changes_only_for_a_real_table(
        monkeypatch):
    """REQ-038 (T-136): una foto de pantalla puede quedar "legible" con unas pocas palabras y
    perder la tabla. Se prueba con la lectura de tabla y solo cambia si trae el doble de
    importes confiables; si no, la página no cambia y no queda en el informe."""
    first = page_of("legible", [("Precio", 87.0), ("Unitario", 87.0), ("6.749,27", 90.0)])
    assert tools._is_sparse(first) and not tools._needs_second_attempt(first)
    pdf = stub_reading(monkeypatch, first, table=page_of("dudosa", table_words(10)))
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert [a["kept"] for a in attempts] == [tools.KEPT_TABLE]
    assert attempts[0]["second_confidence"] is None
    assert len(reading.pages[0].lines[0].words) == 12
    pdf = stub_reading(monkeypatch, first, table=page_of("dudosa", table_words(1)))
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert attempts == [] and reading.pages[0] is first


def test_words_are_grouped_into_rows_by_height_and_ordered_from_left_to_right():
    """REQ-038 (T-136): el texto disperso devuelve cada celda por separado; se vuelven a juntar
    en filas para que el precio quede junto a su renglón."""
    cells = [("7.390,00", 80.0, 500, 102, 90, 20), ("RESMA", 80.0, 100, 100, 80, 20),
             ("1", 80.0, 10, 104, 12, 20), ("3.000,00", 80.0, 500, 200, 90, 20),
             ("RESMA", 80.0, 100, 198, 80, 20)]
    rows = tools._rows(cells)
    assert [[w[0] for w in row] for row in rows] == [["1", "RESMA", "7.390,00"],
                                                     ["RESMA", "3.000,00"]]


def test_a_screen_photo_of_a_table_is_read_with_the_table_configuration():
    """REQ-038 (T-136): la foto de una pantalla con tabla, en perspectiva y con moiré, sale
    "dudosa" con la lectura normal y desordenada; el segundo intento usa la configuración de
    tablas, conserva esa lectura y recupera más precios, que quedan en la fila de su renglón."""
    pdf = screen_pdf(moire=45, blur=1.1, shear=0.05)
    first = read_document(pdf)
    assert first.pages[0].status == PAGE_DOUBTFUL
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert len(attempts) == 1 and attempts[0]["kept"] == tools.KEPT_TABLE
    assert amounts_in(reading) > amounts_in(first)
    assert amounts_in(reading) >= 5
    page = reading.pages[0]
    assert page.origin == "ocr" and page.lines and page.classification == \
        first.pages[0].classification
    row = next(line.text for line in page.lines if "8760" in line.text or "7.760,00" in line.text)
    assert "7.760,00" in row or "67.977.600,00" in row


def test_a_page_that_keeps_the_table_reading_is_never_legible(monkeypatch):
    """REQ-038, P3 (T-136): aunque la lectura de tabla dé 85 de confianza y estado legible, la
    página queda "dudosa" y sigue en la lista de baja confianza."""
    first = page_of("dudosa", [("Detalle", 71.0)] * 6 + [("2700,00", 80.0)])
    table = page_of("legible", [(f"{n}.390,00", 85.0) for n in range(1, 9)] + [("kg", 85.0)] * 2)
    assert table.status == PAGE_READ and table.confidence >= 80
    pdf = stub_reading(monkeypatch, first, table=table)
    reading, attempts = tools.read_with_second_attempt(pdf)
    assert attempts[0]["kept"] == tools.KEPT_TABLE
    assert reading.pages[0].status == PAGE_DOUBTFUL and reading.pages[0].confidence == 85.0


def test_a_table_reading_that_is_tabular_but_has_no_more_reliable_amounts_loses(monkeypatch):
    """REQ-038 (T-136): una lectura de tabla con cifras de sobra pero con menos importes
    confiables que la primera (o con los mismos) no la reemplaza: la lectura de tabla no gana
    siempre."""
    first = page_of("dudosa", table_words(5))
    digits = [(str(n * 111), 90.0) for n in range(1, 9)]
    for table in (page_of("dudosa", digits + table_words(2)),   # solo 2 importes
                  page_of("dudosa", digits + table_words(5))):  # los mismos 5
        assert tools._looks_tabular(table)
        pdf = stub_reading(monkeypatch, first, table=table)
        reading, attempts = tools.read_with_second_attempt(pdf)
        assert attempts[0]["kept"] == tools.KEPT_FIRST and reading.pages[0] is first


def test_only_complete_amounts_with_enough_confidence_count_as_reliable():
    """REQ-038 (T-136): cuentan los importes con miles y decimales coherentes y confianza de 65
    o más; no los de separadores incoherentes ni los de confianza media."""
    words = [("7.390,00", 80.0), ("2700,00", 70.0), ("19953.000,00", 90.0),
             ("12,000,00", 90.0), ("7.39,00", 90.0), ("3.000.000,00", 64.0),
             ("11.500,00", 66.0), ("1.000", 90.0), ("27000,00", 90.0)]
    assert tools._reliable_numbers(page_of("dudosa", words)) == 3
