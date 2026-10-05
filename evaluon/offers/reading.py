"""Preparar y leer lo que se carga en una oferta: fotos, segundo intento y Word (REQ-038;
plan 008, "Carga y lectura"; ADR-0028; T-131).

Todo corre en el equipo, en CPU y sin conexión (P4), con lo que la imagen ya trae: Pillow
(que instalan WeasyPrint y pdfplumber), pypdfium2, Tesseract y lxml. No suma dependencias.

- Fotos JPG y PNG: el original se guarda tal cual; para leerlas, `to_pdf` las convierte a un
  PDF de una página (la imagen entera, ya girada según su marca de orientación), que la
  lectura de la 001 reconoce como página escaneada.
- Segundo intento (`read_with_second_attempt`): la lectura normal de la 001 y, para cada página
  reconocida por OCR que no quedó legible (dudosa o ilegible, T-136), dos veces más: con la
  imagen preparada (enderezada y con umbral adaptativo) y con la configuración para tablas
  (ampliada, sin ruido de puntos, segmentación de texto disperso y filas rearmadas; solo vale
  si salió una tabla de cifras). Se conserva la lectura de mayor confianza y el informe dice
  cuál se usó. Las páginas buenas no se tocan: su texto es el de la lectura normal, sin
  cambios.
- Word (`docx_to_pdf`): el `.docx` se convierte a PDF dentro del equipo (texto y tablas, con
  WeasyPrint); no se usa ningún servicio externo. Las imágenes incrustadas no se copian: si
  el documento tiene solo imágenes, la página queda vacía y no se inventa texto.
"""

import io
import re
import statistics
import zipfile
from dataclasses import replace
from xml.sax.saxutils import escape

import pypdfium2 as pdfium
import pytesseract
from lxml import etree
from PIL import Image, ImageChops, ImageFilter, ImageOps

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_OCR,
    PAGE_BLANK,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    Line,
    Page,
    Word,
    detect_format,
    ocr,
    read_document,
)

FORMAT_JPG = "jpg"
FORMAT_PNG = "png"
FORMAT_DOCX = "docx"

_JPG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ZIP_SIGNATURE = b"PK\x03\x04"

# La imagen se pone en una página a la resolución con que el OCR dibuja las páginas: se lee
# punto por punto, sin ampliarla ni reducirla.
_PHOTO_DPI = 300


# Preparación de la imagen del segundo intento (valores de partida, sin medición: se ajustan
# con las ofertas reales dentro de las rondas de la medición, ADR-0028).
DESKEW_MAX_DEGREES = 10.0
DESKEW_COARSE_STEP = 1.0
DESKEW_FINE_STEP = 0.25
DESKEW_PROBE_WIDTH = 800
DESKEW_MIN_GAIN = 1.05
THRESHOLD_BLUR_FRACTION = 0.02
THRESHOLD_MARGIN = 14

# Lectura de tablas (T-136): la página se dibuja ampliada hasta `TABLE_TARGET_WIDTH` puntos de
# ancho (sin achicarla ni pasar de `TABLE_MAX_SCALE` veces), se pasa a un solo canal (el rojo
# y el gris, las dos variantes de `TABLE_CHANNELS`: el rojo borra el fondo verde de las celdas
# de las pantallas del Portal), se le quita el ruido de puntos de una foto de pantalla (el
# moiré) con un filtro de mediana y se reconoce con la segmentación de texto disperso
# (`--psm 11`: cada celda es su propio bloque) en vez de la de página (`--psm 3`), que mezcla
# las columnas. Las palabras se vuelven a juntar en filas por su altura. Se conserva la
# variante de mayor confianza. Valores medidos con las fotos de pantalla del Portal del
# caso-00 (informe de T-136, ADR-0028).
TABLE_TARGET_WIDTH = 3200
TABLE_MAX_SCALE = 3.0
TABLE_MEDIAN_SIZE = 3
TABLE_PSM = 11
TABLE_CHANNELS = ("R", "L")
TABLE_ROW_TOLERANCE = 0.6  # fracción de la altura mediana de palabra
# Una lectura "de tabla" solo se conserva si tiene cifras: al menos `TABLE_MIN_NUMBERS`
# palabras con un dígito y `TABLE_MIN_SHARE` de las palabras.
TABLE_MIN_NUMBERS = 6
TABLE_MIN_SHARE = 0.15
# Una página legible con menos de estas palabras se prueba con la lectura de tabla; se conserva
# si trae `TABLE_SPARSE_GAIN` veces los importes bien formados de la primera. En una página
# dudosa o ilegible, la lectura de tabla se conserva si trae más importes bien formados que la
# mejor de las otras (la confianza promedio sola no sirve: una lectura que pierde las cifras
# puede tenerla más alta).
TABLE_SPARSE_WORDS = 120
TABLE_SPARSE_GAIN = 2.0

# Qué lectura se conservó de cada página reintentada.
KEPT_FIRST = "primera"
KEPT_SECOND = "segunda"
KEPT_TABLE = "tabla"


class UnreadableFile(ValueError):
    """El archivo no se puede abrir como lo que dice ser."""


# --- Formato de lo que se carga -----------------------------------------------------------------


def detect_upload_format(data):
    """El formato de lo que se carga, por su contenido: `pdf`, `jpg`, `png`, `docx` o `None`."""
    if detect_format(data) == FORMAT_PDF:
        return FORMAT_PDF
    if data.startswith(_JPG_SIGNATURE):
        return FORMAT_JPG
    if data.startswith(_PNG_SIGNATURE):
        return FORMAT_PNG
    if data.startswith(_ZIP_SIGNATURE) and _is_docx(data):
        return FORMAT_DOCX
    return None


def _is_docx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def check_image(data):
    """Comprueba que la foto se abre y devuelve su formato real (`jpg` o `png`). Lanza
    `UnreadableFile` si está dañada."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            kind = image.format
    except Exception as error:
        raise UnreadableFile("La foto está dañada o no se puede abrir.") from error
    if kind == "JPEG":
        return FORMAT_JPG
    if kind == "PNG":
        return FORMAT_PNG
    raise UnreadableFile("La foto no es JPG ni PNG.")


# --- Foto a PDF ---------------------------------------------------------------------------------


def _open_upright(data):
    """La imagen en RGB, girada según su marca de orientación (las fotos de celular la usan)."""
    with Image.open(io.BytesIO(data)) as image:
        upright = ImageOps.exif_transpose(image)
        return upright.convert("RGB")


def _image_pdf(image):
    """Un PDF de una página con `image` ocupando toda la página, a `_PHOTO_DPI` puntos por
    pulgada."""
    dpi = _PHOTO_DPI
    out = io.BytesIO()
    image.save(out, format="PDF", resolution=float(dpi))
    return out.getvalue()


def photo_to_pdf(data):
    """Convierte una foto JPG o PNG en un PDF de una página, dentro del equipo."""
    try:
        return _image_pdf(_open_upright(data))
    except Exception as error:
        raise UnreadableFile("La foto está dañada o no se puede abrir.") from error


def to_pdf(data, file_format):
    """Los bytes de PDF con que se lee un documento: él mismo si ya es PDF; una foto o un
    Word, convertidos."""
    if file_format == FORMAT_PDF:
        return data
    if file_format in (FORMAT_JPG, FORMAT_PNG):
        return photo_to_pdf(data)
    if file_format == FORMAT_DOCX:
        return docx_to_pdf(data)
    raise UnreadableFile(f"Formato sin lectura: {file_format}.")


# --- Preparación de la imagen y segundo intento ---------------------------------------------------


def _binary_probe(gray):
    """Una copia chica en blanco y negro, para medir la inclinación."""
    scale = DESKEW_PROBE_WIDTH / gray.width if gray.width > DESKEW_PROBE_WIDTH else 1.0
    probe = gray.resize((max(1, round(gray.width * scale)), max(1, round(gray.height * scale))),
                        Image.BOX)
    cut = _otsu(probe)
    return probe.point(lambda v: 255 if v < cut else 0)


def _otsu(gray):
    histogram = gray.histogram()
    total = sum(histogram)
    weighted = sum(i * n for i, n in enumerate(histogram))
    below_n = below_sum = 0
    best, cut = -1.0, 128
    for level in range(256):
        below_n += histogram[level]
        if not below_n or below_n == total:
            continue
        below_sum += level * histogram[level]
        mean_below = below_sum / below_n
        mean_above = (weighted - below_sum) / (total - below_n)
        between = below_n * (total - below_n) * (mean_below - mean_above) ** 2
        if between > best:
            best, cut = between, level
    return cut


def _row_sharpness(ink, angle):
    """Cuánto se concentran las filas de tinta al girar la imagen `angle` grados: con el
    texto horizontal, las líneas de texto y los blancos entre ellas dan la mayor variación."""
    rotated = ink.rotate(angle, resample=Image.BILINEAR, fillcolor=0)
    rows = list(rotated.resize((1, rotated.height), Image.BOX).tobytes())
    mean = sum(rows) / len(rows)
    return sum((r - mean) ** 2 for r in rows)


def estimate_skew(gray):
    """Los grados que hay que girar la imagen (en el sentido de `Image.rotate`) para dejar
    el texto horizontal; 0 si no se encuentra una inclinación clara."""
    ink = _binary_probe(gray)
    if not ink.getbbox():
        return 0.0
    steps = int(DESKEW_MAX_DEGREES / DESKEW_COARSE_STEP)
    coarse = [i * DESKEW_COARSE_STEP for i in range(-steps, steps + 1)]
    scores = {angle: _row_sharpness(ink, angle) for angle in coarse}
    best = max(scores, key=scores.get)
    fine = {best + i * DESKEW_FINE_STEP: None
            for i in range(-int(DESKEW_COARSE_STEP / DESKEW_FINE_STEP),
                           int(DESKEW_COARSE_STEP / DESKEW_FINE_STEP) + 1)}
    for angle in fine:
        fine[angle] = scores.get(angle) or _row_sharpness(ink, angle)
    best = max(fine, key=fine.get)
    # Solo se gira si mejora de forma clara respecto de no girar.
    if fine[best] < _row_sharpness(ink, 0.0) * DESKEW_MIN_GAIN:
        return 0.0
    return round(best, 2)


def prepare_image(image):
    """La imagen preparada para el segundo intento: en escala de grises, enderezada y con
    quitar el ruido de puntos, umbral adaptativo (cada punto se compara con el promedio de su vecindad, así una sombra
    o un degradado de luz no tapan el texto). Devuelve la imagen y los grados girados."""
    denoised = image.convert("L").filter(ImageFilter.MedianFilter(3))
    gray = ImageOps.autocontrast(denoised, cutoff=1)
    angle = estimate_skew(gray)
    if angle:
        gray = gray.rotate(angle, resample=Image.BICUBIC, fillcolor=255)
    radius = max(8, round(max(gray.size) * THRESHOLD_BLUR_FRACTION))
    local_mean = gray.filter(ImageFilter.GaussianBlur(radius))
    darker = ImageChops.subtract(local_mean, gray)
    return darker.point(lambda v: 0 if v > THRESHOLD_MARGIN else 255), angle


_AMOUNT = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$|^\d+,\d{2}$")


def _confidence(page):
    return -1.0 if page.confidence is None else page.confidence


def _needs_second_attempt(page):
    """Páginas reconocidas por OCR que no quedaron legibles (ADR-0028, T-136): las dudosas y
    las ilegibles, con o sin palabras reconocidas."""
    if page.origin != ORIGIN_OCR:
        return False
    return page.status in (PAGE_DOUBTFUL, PAGE_ILLEGIBLE)


def _page_words(page):
    return [word for line in page.lines for word in line.words]


def _reliable_numbers(page):
    """Los importes bien formados (`7.390,00`, `2700,00`) reconocidos con confianza de dudosa o
    más: cuántos datos de una tabla (cantidades, precios) se pudieron leer de verdad. La
    confianza promedio sola no lo dice: una lectura que pierde las cifras puede tenerla más
    alta."""
    return sum(1 for word in _page_words(page)
               if word.confidence >= ocr.DOUBTFUL_FROM and _AMOUNT.match(word.text))


def _looks_tabular(page):
    """La lectura tiene cifras de sobra: una tabla de renglones, cantidades y precios."""
    words = _page_words(page)
    numbers = sum(1 for word in words if any(c.isdigit() for c in word.text))
    return numbers >= TABLE_MIN_NUMBERS and numbers >= TABLE_MIN_SHARE * len(words)


def _rows(words):
    """Agrupa las palabras `(texto, confianza, izquierda, arriba, ancho, alto)` en filas por la
    altura de su centro; devuelve las filas de arriba hacia abajo, cada una de izquierda a
    derecha."""
    typical = statistics.median(w[5] for w in words)
    groups = []
    for word in sorted(words, key=lambda w: w[3] + w[5] / 2):
        center = word[3] + word[5] / 2
        if groups and abs(center - groups[-1]["center"]) <= TABLE_ROW_TOLERANCE * typical:
            group = groups[-1]
            group["words"].append(word)
            group["center"] = sum(w[3] + w[5] / 2 for w in group["words"]) / len(group["words"])
        else:
            groups.append({"center": center, "words": [word]})
    return [sorted(group["words"], key=lambda w: w[2]) for group in groups]


def _channel(image, name):
    rgb = image.convert("RGB")
    return rgb.split()[0] if name == "R" else rgb.convert("L")


def _table_variant(image, number, width, height, scale, channel):
    """Una lectura de tabla de la imagen (ver `TABLE_CHANNELS`): una línea por fila de la
    tabla, con sus palabras de izquierda a derecha. `scale` es cuánto está ampliada la imagen
    respecto de la página a `ocr.RENDER_DPI`; `width` y `height` son los de la página en
    puntos."""
    gray = _channel(image, channel).filter(ImageFilter.MedianFilter(TABLE_MEDIAN_SIZE))
    gray = ImageOps.autocontrast(gray, cutoff=1)
    data = pytesseract.image_to_data(
        gray, lang=ocr.LANGUAGE,
        config=f"--oem 1 --psm {TABLE_PSM} --dpi {ocr.RENDER_DPI}",
        output_type=pytesseract.Output.DICT)
    words = []
    for index, level in enumerate(data["level"]):
        text = data["text"][index].strip()
        if level == 5 and text:
            words.append((text, ocr._round(max(float(data["conf"][index]), 0)),
                          data["left"][index], data["top"][index], data["width"][index],
                          data["height"][index]))
    lines = []
    for row in _rows(words) if words else []:
        row_words = [Word(text=w[0], confidence=w[1]) for w in row]
        lines.append(Line(
            text=" ".join(w.text for w in row_words),
            x0=ocr._points(min(w[2] for w in row) / scale),
            top=ocr._points(min(w[3] for w in row) / scale),
            x1=ocr._points(max(w[2] + w[4] for w in row) / scale),
            bottom=ocr._points(max(w[3] + w[5] for w in row) / scale),
            origin=ORIGIN_OCR,
            confidence=ocr._round(sum(w.confidence for w in row_words) / len(row_words)),
            words=row_words))
    every = [word for line in lines for word in line.words]
    status = ocr.page_status(every)
    confidence = (ocr._round(sum(w.confidence for w in every) / len(every))
                  if every else None)
    return Page(number=number, width=width, height=height, status=status,
                lines=lines if status != PAGE_ILLEGIBLE else [], origin=ORIGIN_OCR,
                confidence=confidence)


def read_table_image(image, number, width, height, scale=1.0):
    """Reconoce la imagen de una página con la configuración para tablas (ver
    `TABLE_TARGET_WIDTH`) y devuelve la variante de mayor confianza."""
    pages = [_table_variant(image, number, width, height, scale, channel)
             for channel in TABLE_CHANNELS]
    return max(pages, key=_confidence)


def _table_read(pdf_page, number):
    """Vuelve a leer una página de PDF con la configuración para tablas."""
    width, height = pdf_page.get_size()
    scale = min(TABLE_MAX_SCALE, max(1.0, TABLE_TARGET_WIDTH / (width * ocr.RENDER_DPI / 72)))
    image = pdf_page.render(scale=ocr.RENDER_DPI / 72 * scale).to_pil()
    return read_table_image(image, number, ocr._round(width), ocr._round(height), scale)


def _second_read(pdf_page, number):
    """Vuelve a leer una página de PDF con la imagen preparada. Devuelve la página leída y
    los grados que se la giró."""
    image = pdf_page.render(scale=ocr.RENDER_DPI / 72, grayscale=True).to_pil()
    prepared, angle = prepare_image(image)
    document = pdfium.PdfDocument(_image_pdf(prepared.convert("RGB")))
    try:
        reread = ocr.read_page_ocr(document[0], number)
    finally:
        document.close()
    return reread, angle


def _is_sparse(page):
    """Una página reconocida por OCR y legible, pero con tan pocas palabras que puede haber
    perdido una tabla entera (una foto de pantalla: la confianza se calcula solo sobre lo que
    se reconoció)."""
    return (page.origin == ORIGIN_OCR and page.status not in (PAGE_DOUBTFUL, PAGE_ILLEGIBLE)
            and page.status != PAGE_BLANK and len(_page_words(page)) < TABLE_SPARSE_WORDS)


def _attempt_entry(first, second, table, angle, kept):
    return {
        "page": first.number,
        "first_confidence": first.confidence,
        "first_status": first.status,
        "second_confidence": None if second is None else second.confidence,
        "second_status": None if second is None else second.status,
        "table_confidence": table.confidence,
        "table_status": table.status,
        "rotation_degrees": angle,
        "kept": kept,
    }


def read_with_second_attempt(pdf_bytes):
    """Lee un PDF con la lectura de la 001 y vuelve a leer las páginas reconocidas por OCR
    que no quedaron legibles (dudosas o ilegibles): una vez con la imagen preparada y una con
    la configuración para tablas. Devuelve `(lectura, intentos)`; `intentos` tiene una entrada
    por página reintentada, con las confianzas y la lectura que se conservó (`primera`,
    `segunda` o `tabla`: entre la primera y la segunda, la de mayor confianza (si empatan, la
    primera); la de tabla gana si trae más importes bien formados, ver `_reliable_numbers`).

    Una página legible con muy pocas palabras (menos de `TABLE_SPARSE_WORDS`) se prueba solo
    con la configuración para tablas, y la lectura de tabla se conserva solo si trae
    `TABLE_SPARSE_GAIN` veces las importes bien formados de la primera; si no, la página no cambia y no queda
    en `intentos`."""
    reading = read_document(pdf_bytes)
    retry = [i for i, page in enumerate(reading.pages)
             if _needs_second_attempt(page) or _is_sparse(page)]
    if not retry:
        return reading, []
    attempts = []
    pages = list(reading.pages)
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        for index in retry:
            first = pages[index]
            sparse = not _needs_second_attempt(first)
            second, angle = (None, 0.0) if sparse else _second_read(document[index],
                                                                    first.number)
            table = _table_read(document[index], first.number)
            kept, best = KEPT_FIRST, first
            if second is not None and _confidence(second) > _confidence(best):
                kept, best = KEPT_SECOND, second
            # La lectura de tabla solo cuenta si salió una tabla de cifras y con texto.
            if table.lines and _looks_tabular(table):
                needed = TABLE_SPARSE_GAIN if sparse else 1.0
                if _reliable_numbers(table) > needed * _reliable_numbers(best):
                    kept, best = KEPT_TABLE, table
            if sparse and kept == KEPT_FIRST:
                continue
            attempts.append(_attempt_entry(first, second, table, angle, kept))
            if kept != KEPT_FIRST:
                pages[index] = replace(best, classification=first.classification)
    finally:
        document.close()
    return replace(reading, pages=pages), attempts


# --- Word a PDF ---------------------------------------------------------------------------------

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W}
_STYLE = ("body{font-family:'DejaVu Sans',sans-serif;font-size:10pt}"
          "table{border-collapse:collapse;width:100%}"
          "td,th{border:1px solid #444;padding:2px 4px;vertical-align:top}"
          "p{margin:0 0 6px 0}")


def _runs_text(paragraph):
    parts = []
    for node in paragraph.iter():
        tag = etree.QName(node).localname
        if tag == "t":
            parts.append(node.text or "")
        elif tag in ("tab",):
            parts.append("\t")
        elif tag in ("br", "cr"):
            parts.append("\n")
    return "".join(parts)


def _paragraph_html(paragraph):
    text = escape(_runs_text(paragraph)).replace("\n", "<br>")
    return f"<p>{text}</p>" if text.strip() else ""


def _table_html(table):
    rows = []
    for row in table.findall("w:tr", _NS):
        cells = []
        for cell in row.findall("w:tc", _NS):
            inner = "".join(_paragraph_html(p) for p in cell.findall("w:p", _NS))
            cells.append(f"<td>{inner}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table>{''.join(rows)}</table>"


def docx_to_html(data):
    """El texto y las tablas de un `.docx`, en el orden del documento, como HTML simple."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = etree.fromstring(archive.read("word/document.xml"),
                                    etree.XMLParser(resolve_entities=False, no_network=True))
    except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError) as error:
        raise UnreadableFile("El documento de Word está dañado o no se puede abrir.") from error
    body = root.find("w:body", _NS)
    parts = []
    for child in body if body is not None else []:
        tag = etree.QName(child).localname
        if tag == "p":
            parts.append(_paragraph_html(child))
        elif tag == "tbl":
            parts.append(_table_html(child))
    return f"<html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>" \
           f"{''.join(parts)}</body></html>"


def docx_to_pdf(data):
    """Convierte un `.docx` en un PDF con texto, dentro del equipo y sin servicios externos."""
    from weasyprint import HTML

    html = docx_to_html(data)
    if not re.search(r"<(p|table)", html):
        raise UnreadableFile("El documento de Word no tiene texto.")
    return HTML(string=html).write_pdf()


# --- Lectura guardada a objetos ----------------------------------------------------------------


def rebuild_reading(data):
    """La lectura guardada (`Reading.pages`, el JSON de `DocumentReading.as_json`) como
    objetos, para volver a armar su texto canónico y sus pasajes sin leer de nuevo el
    archivo (T-136)."""
    from evaluon.norms.reading import DocumentReading, Line, Page, Word

    pages = [
        Page(**{**page, "lines": [
            Line(**{**line, "words": [Word(**word) for word in line["words"]]})
            for line in page["lines"]]})
        for page in data["pages"]
    ]
    return DocumentReading(file_format=data["file_format"], pages=pages,
                           tool_versions=data["tool_versions"], encoding=data.get("encoding"))
