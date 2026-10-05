"""Preparar y leer lo que se carga en una oferta: fotos, segundo intento y Word (REQ-038;
plan 008, "Carga y lectura"; ADR-0028; T-131).

Todo corre en el equipo, en CPU y sin conexión (P4), con lo que la imagen ya trae: Pillow
(que instalan WeasyPrint y pdfplumber), pypdfium2, Tesseract y lxml. No suma dependencias.

- Fotos JPG y PNG: el original se guarda tal cual; para leerlas, `to_pdf` las convierte a un
  PDF de una página (la imagen entera, ya girada según su marca de orientación), que la
  lectura de la 001 reconoce como página escaneada.
- Segundo intento (`read_with_second_attempt`): la lectura normal de la 001 y, para cada página
  reconocida por OCR cuya confianza quedó por debajo del umbral de dudosa, una vez más con la
  imagen preparada (enderezada y con umbral adaptativo). Se conserva la lectura de mayor
  confianza y el informe dice cuál se usó. Las páginas buenas no se tocan: su texto es el de
  la lectura normal, sin cambios.
- Word (`docx_to_pdf`): el `.docx` se convierte a PDF dentro del equipo (texto y tablas, con
  WeasyPrint); no se usa ningún servicio externo. Las imágenes incrustadas no se copian: si
  el documento tiene solo imágenes, la página queda vacía y no se inventa texto.
"""

import io
import re
import zipfile
from dataclasses import replace
from xml.sax.saxutils import escape

import pypdfium2 as pdfium
from lxml import etree
from PIL import Image, ImageChops, ImageFilter, ImageOps

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_OCR,
    PAGE_ILLEGIBLE,
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

# Qué lectura se conservó de cada página reintentada.
KEPT_FIRST = "primera"
KEPT_SECOND = "segunda"


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


def _confidence(page):
    return -1.0 if page.confidence is None else page.confidence


def _needs_second_attempt(page):
    """Páginas reconocidas por OCR cuya confianza quedó por debajo del umbral de dudosa
    (ADR-0028): las ilegibles, con o sin palabras reconocidas."""
    if page.origin != ORIGIN_OCR:
        return False
    return page.status == PAGE_ILLEGIBLE or _confidence(page) < ocr.DOUBTFUL_FROM


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


def read_with_second_attempt(pdf_bytes):
    """Lee un PDF con la lectura de la 001 y vuelve a leer una vez las páginas de baja
    confianza con la imagen preparada. Devuelve `(lectura, intentos)`; `intentos` tiene una
    entrada por página reintentada, con las dos confianzas y la lectura que se conservó
    (`primera` o `segunda`, la de mayor confianza; si empatan, la primera)."""
    reading = read_document(pdf_bytes)
    retry = [i for i, page in enumerate(reading.pages) if _needs_second_attempt(page)]
    if not retry:
        return reading, []
    attempts = []
    pages = list(reading.pages)
    document = pdfium.PdfDocument(pdf_bytes)
    try:
        for index in retry:
            first = pages[index]
            second, angle = _second_read(document[index], first.number)
            kept = KEPT_SECOND if _confidence(second) > _confidence(first) else KEPT_FIRST
            attempts.append({
                "page": first.number,
                "first_confidence": first.confidence,
                "first_status": first.status,
                "second_confidence": second.confidence,
                "second_status": second.status,
                "rotation_degrees": angle,
                "kept": kept,
            })
            if kept == KEPT_SECOND:
                pages[index] = replace(second, classification=first.classification)
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
