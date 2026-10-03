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
  estado (`status`) es uno de `PAGE_STATUSES`. Una página sin capa de texto se informa
  como no leída (REQ-004). `origin` y `confidence` son opcionales (T-025): el origen del
  texto de la página y, si vino de reconocimiento, la confianza promedio de todas sus
  palabras. El reconocimiento los completa también en una página ilegible, que no aporta
  líneas, para que el informe distinga una página ilegible de una casi sin texto. Vacíos
  si el lector no los informa.

Entrada única: `read_document(archivo)`. El formato se reconoce por el contenido, no por
el nombre. En esta tarea (T-012) solo acepta PDF con texto; la lectura de PDF escaneados
(`ocr.py`, T-021), de páginas web (`web.py`, T-022) y la clasificación de cada página
se suman en T-028. Todo corre en CPU, sin los servicios de IA.
"""

from dataclasses import asdict, dataclass, field
from os import PathLike

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


@dataclass
class DocumentReading:
    """La lectura de un documento: sus páginas y las versiones de las herramientas."""

    file_format: str
    pages: list[Page]
    tool_versions: dict[str, str]

    @property
    def pages_not_read(self):
        """Números de las páginas que no aportaron texto (REQ-004)."""
        return [page.number for page in self.pages if page.status in _NOT_READ_STATUSES]

    def as_json(self):
        """La lectura como datos JSON, para `norms_reading.pages` y el informe."""
        return asdict(self)


def read_document(source: str | PathLike | bytes) -> DocumentReading:
    """Lee un documento desde su ruta o desde sus bytes y devuelve su lectura.

    En esta etapa solo acepta PDF con texto: cualquier otro contenido levanta
    `UnsupportedFormatError`.
    """
    data = source if isinstance(source, bytes) else _read_bytes(source)
    if _PDF_SIGNATURE not in data[:_PDF_SIGNATURE_WINDOW]:
        raise UnsupportedFormatError(
            "La lectura acepta por ahora solo PDF con texto; el archivo no es un PDF."
        )

    from evaluon.norms.reading.pdf_text import read_pdf_text

    return read_pdf_text(data)


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()
