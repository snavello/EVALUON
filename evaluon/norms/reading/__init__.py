"""Lectura de documentos (ADR-0004, "Cómo se lee"; plan 001, "Ingesta").

Define el resultado común a los tres formatos y la entrada única de lectura.

Resultado común: la *lectura* de un documento (`DocumentReading`) es una lista de
páginas (`Page`), cada una con sus líneas (`Line`). Cada línea lleva su texto, su
posición en la página, su origen y, si vino de reconocimiento sobre imagen, su confianza
y la de cada palabra. La lectura trae además las versiones de las herramientas con que
se obtuvo (P6). Se guarda en `norms_reading.pages` con `as_json()`.

- **Texto.** Tal como lo entrega la herramienta, sin normalizar: el texto canónico y sus
  cinco operaciones son de la partición (`norms/splitting/`).
- **Posición.** `x0`, `top`, `x1`, `bottom`, en las unidades de la página (`width`,
  `height`), con el origen arriba a la izquierda. En PDF son puntos. En una página web
  no hay posición: quedan vacías y la ubicación es el orden de la línea.
- **Origen.** `pdf_text`, `ocr` o `web` (REQ-015).
- **Confianza.** Solo en líneas `ocr`: `confidence` es la de la línea y `words` la de
  cada palabra (`Word`). Vacías en los demás orígenes.
- **Descartado.** `discarded` vacío si la línea es texto del documento; si no, el motivo
  por el que se excluye de las unidades (por ejemplo, navegación de un sitio). Lo
  descartado no se borra de la lectura: queda marcado para el informe.
- **Página.** `number` empieza en 1; una página web es una sola página sin número. Su
  estado (`status`) es uno de `PAGE_STATUSES`. Para el lector de PDF con texto, una
  página sin capa de texto es no leída; la entrada única la clasifica antes (en blanco,
  escaneada o solo campos, ver abajo) (REQ-004). `origin` y `confidence` son
  opcionales (T-025): el origen del texto de la página y, si vino de reconocimiento, la confianza promedio de todas sus
  palabras. El reconocimiento los completa también en una página ilegible, que no aporta
  líneas, para que el informe distinga una página ilegible de una casi sin texto. Vacíos
  si el lector no los informa.

Entrada única: `read_document(archivo)` (T-028). Todo corre en CPU, sin los servicios de
IA y sin conexión (P4).

1. **Formato.** Se reconoce por el contenido, no por el nombre (`detect_format`): un PDF
   trae la marca `%PDF-` en su primer kilobyte; una página web guardada empieza, después
   de espacios, comentarios o la declaración XML, con `<!DOCTYPE html`, `<html`, `<head`
   o `<body`, leída como ASCII o, si trae la marca de orden de bytes, como UTF-8 o UTF-16.
   Un archivo con bytes nulos y sin esa marca (un UTF-16 sin marca, una imagen) no es una
   página web: se leería como texto legible equivocado. Lo demás se rechaza con
   `UnsupportedFormatError`.
2. **Cada página de un PDF se clasifica antes de leerla** (ADR-0004, "Cómo se lee";
   `classify_page`), con pypdfium2:
   - *con texto* (`con_texto`): tiene capa de texto utilizable. Se lee con `pdf_text.py`.
   - *escaneada* (`escaneada`): no tiene capa de texto y tiene tinta, o una imagen la
     cubre casi entera (`FULL_PAGE_IMAGE`), aunque traiga una capa de texto oculta puesta
     por el escáner. Se reconoce con `ocr.py`.
   - *con texto inservible* (`texto_inservible`): la capa de texto trae caracteres sin
     letra (reemplazo, `(cid:N)`, uso privado, control) en una proporción de
     `UNUSABLE_TEXT_SHARE` o más. Se reconoce con `ocr.py`.
   - *en blanco* (`en_blanco`): sin texto y sin tinta. Estado `en_blanco`: se informa y
     no cuenta como no leída.
   - *solo campos* (`solo_campos`): sin texto ni tinta, pero con anotaciones o campos de
     formulario, como la página de la firma digital del anexo de la Disp. AFIP 247/2022
     (página 45). No se da por en blanco, porque trae algo que no es texto, ni se
     reconoce, porque no hay tinta que reconocer: queda `no_leida`, sin texto, y el
     informe la muestra como "sin texto".
   La tinta se busca dibujando la página a `INK_DPI` puntos por pulgada, sin anotaciones
   ni campos: hay tinta si algún punto es más oscuro que `INK_LEVEL`. La clasificación
   queda en `Page.classification`. Los umbrales son valores de partida, sin medición
   detrás, como los del reconocimiento: se calibran con el corpus real (T-043).
3. **Página web:** se lee con `web.py`. La codificación detectada queda en
   `DocumentReading.encoding` (P6).
4. **Versiones** (`tool_versions`, P6): las de la lectura de PDF con texto en todo PDF;
   si alguna página se reconoció, además las del reconocimiento con la huella del modelo
   de español (`ocr.tool_versions()`); en una página web, las de `web.py`. La versión de
   las reglas de partición la suma la carga.

Un PDF dañado o incompleto (pypdfium2 o pdfplumber no lo pueden abrir) levanta
`UnsupportedFormatError`, no el error de la biblioteca.
"""

import codecs
import re
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from os import PathLike

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

# Origen del texto de una línea (REQ-015).
ORIGIN_PDF_TEXT = "pdf_text"
ORIGIN_OCR = "ocr"
ORIGIN_WEB = "web"

# Estado de lectura de una página (ADR-0004, "Cómo se lee"). `legible`, `dudosa` e
# `ilegible` resultan de la confianza del reconocimiento (T-021); `en_blanco` es una
# página sin texto y sin tinta (T-028); `no_leida`, una página de la que no se obtuvo
# texto. Una página `pdf_text` con texto es `legible`.
PAGE_READ = "legible"
PAGE_DOUBTFUL = "dudosa"
PAGE_ILLEGIBLE = "ilegible"
PAGE_BLANK = "en_blanco"
PAGE_NOT_READ = "no_leida"
PAGE_STATUSES = (PAGE_READ, PAGE_DOUBTFUL, PAGE_ILLEGIBLE, PAGE_BLANK, PAGE_NOT_READ)

# Estados de las páginas que no aportan texto y van al informe como no leídas (REQ-004).
_NOT_READ_STATUSES = (PAGE_ILLEGIBLE, PAGE_NOT_READ)

FORMAT_PDF = "pdf"
FORMAT_HTML = "html"

# Un PDF empieza con `%PDF-`; la norma admite que la marca aparezca dentro del primer
# kilobyte, después de algunos bytes previos.
_PDF_SIGNATURE = b"%PDF-"
_PDF_SIGNATURE_WINDOW = 1024

# Comienzo de una página web guardada: espacios, comentarios o la declaración XML, y
# después el tipo de documento o el primer elemento.
_HTML_WINDOW = 4096
_HTML_START = re.compile(
    r"(?:\s|<!--.*?-->|<\?xml[^>]*>)*<(?:!doctype\s+html|html|head|body)\b",
    re.IGNORECASE | re.DOTALL,
)
_HTML_BOMS = (
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

# Clasificación de las páginas de un PDF (ADR-0004, "Cómo se lee"; T-028).
PAGE_KIND_TEXT = "con_texto"
PAGE_KIND_SCANNED = "escaneada"
PAGE_KIND_UNUSABLE_TEXT = "texto_inservible"
PAGE_KIND_BLANK = "en_blanco"
PAGE_KIND_FIELDS_ONLY = "solo_campos"
PAGE_KINDS = (
    PAGE_KIND_TEXT,
    PAGE_KIND_SCANNED,
    PAGE_KIND_UNUSABLE_TEXT,
    PAGE_KIND_BLANK,
    PAGE_KIND_FIELDS_ONLY,
)
_RECOGNIZED_KINDS = (PAGE_KIND_SCANNED, PAGE_KIND_UNUSABLE_TEXT)

# Valores de partida, sin medición detrás (se calibran en T-043):
# - proporción del área de la página que tiene que cubrir una sola imagen para tratarla
#   como escaneada aunque tenga capa de texto;
FULL_PAGE_IMAGE = 0.85
# - proporción de caracteres sin letra en la capa de texto a partir de la cual el texto
#   es inservible;
UNUSABLE_TEXT_SHARE = 0.1
# - resolución a la que se dibuja la página para buscar tinta, y nivel de gris (0 negro,
#   255 blanco) por debajo del cual un punto es tinta.
INK_DPI = 36
INK_LEVEL = 200

# Caracteres sin letra de una capa de texto: `(cid:N)` (glifo sin correspondencia, como
# lo escribe pdfminer), caracteres de reemplazo y no caracteres, y las categorías de uso
# privado, sin asignar, sustitutos y control.
_CID = re.compile(r"\(cid:\d+\)")
_UNUSABLE_CHARS = frozenset("�￾￿")
_UNUSABLE_CATEGORIES = frozenset({"Co", "Cn", "Cs", "Cc"})

# Decimales de las medidas de una página, como en `pdf_text.py` y `ocr.py`.
_DECIMALS = 2

_UNSUPPORTED_MESSAGE = (
    "El archivo no es un PDF ni una página web guardada (.html): la lectura acepta PDF con "
    "texto, PDF escaneado y página web."
)
_DAMAGED_MESSAGE = "El PDF está dañado o incompleto: no se puede leer."


class UnsupportedFormatError(ValueError):
    """El archivo no está en un formato que la lectura acepte."""


@dataclass
class Word:
    """Palabra reconocida sobre una imagen, con su confianza (0 a 100)."""

    text: str
    confidence: float


@dataclass
class Line:
    """Una línea de texto de una página, en el orden del documento."""

    text: str
    x0: float | None
    top: float | None
    x1: float | None
    bottom: float | None
    origin: str
    confidence: float | None = None
    words: list[Word] = field(default_factory=list)
    discarded: str = ""


@dataclass
class Page:
    """Una página con sus líneas, de arriba hacia abajo."""

    number: int | None
    width: float | None
    height: float | None
    status: str
    lines: list[Line] = field(default_factory=list)
    origin: str | None = None
    confidence: float | None = None
    # Clasificación de la página de un PDF antes de leerla (`PAGE_KINDS`, T-028); vacía
    # en una página web o si el lector no la informa.
    classification: str | None = None


@dataclass
class DocumentReading:
    """La lectura de un documento: sus páginas, las versiones de las herramientas y, en
    una página web, la codificación detectada."""

    file_format: str
    pages: list[Page]
    tool_versions: dict[str, str]
    encoding: str | None = None

    @property
    def pages_not_read(self):
        """Números de las páginas que no aportaron texto (REQ-004)."""
        return [page.number for page in self.pages if page.status in _NOT_READ_STATUSES]

    def as_json(self):
        """La lectura como datos JSON, para `norms_reading.pages` y el informe."""
        return asdict(self)


@dataclass(frozen=True)
class PageFacts:
    """Lo que se mira de una página de PDF para clasificarla: caracteres visibles de su
    capa de texto y cuántos de ellos no tienen letra; la mayor proporción de la página
    que cubre una sola imagen; si tiene objetos; si tiene tinta (`None` si no hizo falta
    mirarlo); y cuántas anotaciones o campos trae."""

    chars: int
    unusable: int
    image_cover: float
    objects: bool
    ink: bool | None
    annotations: int


def read_document(source: str | PathLike | bytes) -> DocumentReading:
    """Lee un documento desde su ruta o desde sus bytes y devuelve su lectura.

    Acepta PDF (con texto, escaneado o mezclado, página por página) y página web
    guardada. Cualquier otro contenido, o un PDF dañado, levanta
    `UnsupportedFormatError`.
    """
    data = source if isinstance(source, bytes) else _read_bytes(source)
    file_format = detect_format(data)
    if file_format == FORMAT_PDF:
        return _read_pdf(data)
    if file_format == FORMAT_HTML:
        return _read_html(data)
    raise UnsupportedFormatError(_UNSUPPORTED_MESSAGE)


def detect_format(data: bytes) -> str | None:
    """El formato del archivo según su contenido: `pdf`, `html` o `None`."""
    if _PDF_SIGNATURE in data[:_PDF_SIGNATURE_WINDOW]:
        return FORMAT_PDF
    start = _html_start(data[:_HTML_WINDOW])
    if start is not None and _HTML_START.match(start):
        return FORMAT_HTML
    return None


def _html_start(head):
    """El comienzo del archivo como texto, para reconocer una página web: con la marca de
    orden de bytes, en su codificación; sin ella, byte por byte. `None` si trae bytes
    nulos sin marca."""
    for bom, encoding in _HTML_BOMS:
        if head.startswith(bom):
            return head[len(bom):].decode(encoding, errors="ignore")
    if b"\x00" in head:
        return None
    return head.decode("latin-1")


def unusable_text_share(text: str) -> tuple[int, int]:
    """Caracteres visibles de una capa de texto y cuántos no tienen letra. Cada `(cid:N)`
    cuenta como un carácter."""
    cids = len(_CID.findall(text))
    rest = _CID.sub("", text)
    visible = [char for char in rest if not char.isspace()]
    unusable = sum(
        1
        for char in visible
        if char in _UNUSABLE_CHARS or unicodedata.category(char) in _UNUSABLE_CATEGORIES
    )
    return cids + len(visible), cids + unusable


def page_kind(facts: PageFacts) -> str:
    """La clasificación de una página según lo que se miró de ella (`PAGE_KINDS`)."""
    if facts.image_cover >= FULL_PAGE_IMAGE:
        return PAGE_KIND_SCANNED
    if facts.chars:
        if facts.unusable / facts.chars >= UNUSABLE_TEXT_SHARE:
            return PAGE_KIND_UNUSABLE_TEXT
        return PAGE_KIND_TEXT
    if facts.ink:
        return PAGE_KIND_SCANNED
    if facts.annotations:
        return PAGE_KIND_FIELDS_ONLY
    return PAGE_KIND_BLANK


def classify_page(page) -> str:
    """Clasifica una página de PDF (`pypdfium2.PdfPage`) antes de leerla."""
    return page_kind(page_facts(page))


def page_facts(page) -> PageFacts:
    """Lo que se mira de una página de PDF para clasificarla. La tinta solo se busca si
    la página no tiene texto ni una imagen que la cubra."""
    textpage = page.get_textpage()
    try:
        chars, unusable = unusable_text_share(textpage.get_text_range())
    finally:
        textpage.close()
    width, height = page.get_size()
    area = width * height
    cover = 0.0
    for image in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = image.get_bounds()
        covered = max(0.0, min(right, width) - max(left, 0.0)) * max(
            0.0, min(top, height) - max(bottom, 0.0)
        )
        cover = max(cover, covered / area if area else 0.0)
    objects = pdfium_c.FPDFPage_CountObjects(page) > 0
    annotations = pdfium_c.FPDFPage_GetAnnotCount(page)
    ink = None
    if not chars and cover < FULL_PAGE_IMAGE:
        ink = objects and _has_ink(page)
    return PageFacts(chars, unusable, cover, objects, ink, annotations)


def _has_ink(page):
    """Si la página dibujada, sin anotaciones ni campos, tiene algún punto oscuro."""
    bitmap = page.render(
        scale=INK_DPI / 72, grayscale=True, draw_annots=False, may_draw_forms=False
    )
    darkest, _ = bitmap.to_pil().getextrema()
    return darkest < INK_LEVEL


def _read_pdf(data):
    """Lee un PDF página por página, según su clasificación."""
    from pdfminer.psparser import PSException
    from pdfplumber.utils.exceptions import PdfminerException

    from evaluon.norms.reading import ocr, pdf_text

    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise UnsupportedFormatError(_DAMAGED_MESSAGE) from error
    try:
        kinds = [classify_page(pdf[index]) for index in range(len(pdf))]
        text_pages = None
        if PAGE_KIND_TEXT in kinds:
            try:
                text_pages = pdf_text.read_pdf_text(data).pages
            except (PdfminerException, PSException) as error:
                raise UnsupportedFormatError(_DAMAGED_MESSAGE) from error
            if len(text_pages) != len(kinds):
                raise UnsupportedFormatError(_DAMAGED_MESSAGE)

        pages = []
        for index, kind in enumerate(kinds):
            number = index + 1
            if kind == PAGE_KIND_TEXT:
                page = text_pages[index]
            elif kind in _RECOGNIZED_KINDS:
                page = ocr.read_page_ocr(pdf[index], number)
            else:
                width, height = pdf[index].get_size()
                page = Page(
                    number=number,
                    width=round(float(width), _DECIMALS),
                    height=round(float(height), _DECIMALS),
                    status=PAGE_BLANK if kind == PAGE_KIND_BLANK else PAGE_NOT_READ,
                )
            pages.append(replace(page, classification=kind))
    finally:
        pdf.close()

    versions = pdf_text.tool_versions()
    if any(kind in _RECOGNIZED_KINDS for kind in kinds):
        versions.update(ocr.tool_versions())
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions=versions)


def _read_html(data):
    from evaluon.norms.reading import web

    reading = web.read_web(data)
    reading.encoding = web.detect_encoding(data)
    return reading


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()
