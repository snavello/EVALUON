"""Lectura de una página web guardada con BeautifulSoup y lxml (ADR-0004, parte 3; T-022).

Recibe los bytes de un archivo `.html` y devuelve su lectura en el resultado común de
`evaluon.norms.reading`: una sola página, sin número ni medidas, con una línea por bloque
de texto en el orden del documento, todas con origen `web` y sin posición (la ubicación
es el orden de la línea).

Tres pasos:

1. **Codificación.** Se detecta, no se supone (ADR-0004, "Sin verificar"): la marca de
   orden de bytes si la hay; si no, la que declara la página en su `<meta>`; si no declara
   ninguna, UTF-8 si el archivo lo es y, si no, windows-1252. Las etiquetas ISO-8859-1 y
   ASCII se leen como windows-1252, como hacen los navegadores: la página de la
   Disp. 247/2022 declara ISO-8859-1 y la de la 297/03, que declara windows-1252, usa los
   bytes 0x96 y 0x97 para el guion medio y la raya, que en ISO-8859-1 serían caracteres
   de control. Si los bytes no corresponden a la codificación, la lectura se rechaza:
   reemplazar caracteres sin avisar cambiaría el texto de la norma.
2. **Bloques.** Se recorre el documento en orden. Cada elemento de bloque (`<p>`, `<div>`,
   `<dir>`, `<br>`, celdas, títulos...) corta la línea; el texto de los elementos de
   línea (`<b>`, `<span>`, `<a>`...) se suma a la línea en curso. Las entidades quedan
   resueltas por el lector de HTML. Los espacios, tabulaciones y saltos de renglón del
   archivo se reducen a un espacio, como los muestra el navegador; el espacio duro se
   conserva (lo trata el texto canónico). Fuera de eso el texto no se normaliza. Los
   comentarios y la declaración de tipo de documento no son texto y no se leen.
3. **Descartes.** Con reglas explícitas, generales y por sitio de origen. Lo descartado
   no se borra: queda como líneas con el motivo en `Line.discarded`, en su lugar del
   documento, para el informe. Una página sin texto que no esté descartado se informa
   como no leída.

   - Generales: scripts, estilos y el encabezado HTML (`<head>`, cuyo texto es el título
     de la ventana). Ninguna otra cosa se descarta en un sitio sin regla propia: perder
     texto sin aviso es más grave que conservar ruido (ADR-0004).
   - Infoleg, escrita contra las dos páginas de `corpus/normativa/`: el encabezado del
     sitio (`<header id="branding">` y `<div id="cleaner">`) y la nota que Infoleg
     agrega al pie, un elemento cuyo texto empieza con "(Nota Infoleg:". La nota del
     Boletín Oficial sobre los anexos y la línea de publicación son del documento y se
     conservan.
"""

import codecs
import re
from importlib.metadata import version

from bs4 import BeautifulSoup
from bs4.element import Comment, Declaration, Doctype, NavigableString, ProcessingInstruction, Tag

from evaluon.norms.reading import (
    FORMAT_HTML,
    ORIGIN_WEB,
    PAGE_NOT_READ,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
    UnsupportedFormatError,
)

# Motivos de descarte (`Line.discarded`).
DISCARD_SCRIPT = "script de la página"
DISCARD_STYLE = "estilo de la página"
DISCARD_HEAD = "encabezado HTML de la página"
DISCARD_INFOLEG_NAVIGATION = "navegación de Infoleg"
DISCARD_INFOLEG_NOTE = "nota de Infoleg"

# Bibliotecas cuya versión se registra con la lectura (P6).
TOOLS = ("beautifulsoup4", "lxml")

# --- Codificación -----------------------------------------------------------------------

_BOMS = (
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)
# `<meta charset="...">` o `<meta http-equiv="Content-Type" content="...; charset=...">`.
_DECLARED_CHARSET = re.compile(
    rb"<meta[^>]*?charset\s*=\s*[\"']?\s*([a-z0-9_.:-]+)", re.IGNORECASE
)
# Etiquetas que los navegadores leen como windows-1252 (WHATWG, "Encoding").
_WINDOWS_1252_LABELS = frozenset(
    {
        "ansi_x3.4-1968",
        "ascii",
        "cp1252",
        "cp819",
        "csisolatin1",
        "ibm819",
        "iso-8859-1",
        "iso-ir-100",
        "iso8859-1",
        "iso88591",
        "iso_8859-1",
        "iso_8859-1:1987",
        "l1",
        "latin1",
        "us-ascii",
        "windows-1252",
        "x-cp1252",
    }
)
FALLBACK_ENCODING = "cp1252"

# --- Bloques ----------------------------------------------------------------------------

# Elementos que cortan la línea. El resto se trata como texto de línea.
BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "body", "br", "caption", "center",
        "dd", "dir", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
        "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hr", "html", "li",
        "main", "menu", "nav", "ol", "p", "pre", "section", "table", "tbody", "td",
        "tfoot", "th", "thead", "title", "tr", "ul",
    }
)
# Nodos que no son texto del documento.
_NOT_TEXT = (Comment, Declaration, Doctype, ProcessingInstruction)
# Espacio en blanco de HTML: no incluye el espacio duro.
_HTML_WHITESPACE = re.compile(r"[ \t\n\r\f]+")

# --- Reglas de descarte -----------------------------------------------------------------

_GENERIC_RULES = {"script": DISCARD_SCRIPT, "style": DISCARD_STYLE, "head": DISCARD_HEAD}

_INFOLEG_NAVIGATION_IDS = {("header", "branding"), ("div", "cleaner")}
_INFOLEG_NOTE = re.compile(r"^\(\s*Nota\s+Infoleg:")


def tool_versions():
    """Versiones instaladas de las herramientas de lectura de páginas web."""
    return {tool: version(tool) for tool in TOOLS}


def detect_encoding(data: bytes) -> str:
    """Codificación de una página web guardada, con el nombre del códec de Python."""
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            return encoding
    declared = _DECLARED_CHARSET.search(data)
    if declared:
        label = declared.group(1).decode("ascii").lower()
        if label in _WINDOWS_1252_LABELS:
            return FALLBACK_ENCODING
        try:
            return codecs.lookup(label).name
        except LookupError:
            pass  # Etiqueta desconocida: se sigue como si no declarara ninguna.
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return FALLBACK_ENCODING
    return "utf-8"


def read_web(data: bytes) -> DocumentReading:
    """Lee una página web guardada y devuelve su lectura, como una sola página."""
    text = _decode(data)
    soup = BeautifulSoup(text, "lxml")
    reader = _BlockReader(_site_rules(soup))
    reader.read(soup)
    lines = reader.lines
    status = PAGE_READ if any(not line.discarded for line in lines) else PAGE_NOT_READ
    page = Page(number=None, width=None, height=None, status=status, lines=lines)
    return DocumentReading(file_format=FORMAT_HTML, pages=[page], tool_versions=tool_versions())


def _decode(data):
    encoding = detect_encoding(data)
    for bom, bom_encoding in _BOMS:
        if encoding == bom_encoding and data.startswith(bom):
            data = data[len(bom):]
            break
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as error:
        raise UnsupportedFormatError(
            f"La página no se puede leer con la codificación {encoding}: "
            f"byte {data[error.start]:#04x} en la posición {error.start}."
        ) from error


def _site_rules(soup):
    """Reglas del sitio de origen de la página, o ninguna si no se reconoce el sitio."""
    if _is_infoleg(soup):
        return _infoleg_reason
    return None


def _is_infoleg(soup):
    if soup.find("div", id="encabezado_norma"):
        return True
    return any("/infolegInternet/" in link.get("href", "") for link in soup.find_all("link"))


def _infoleg_reason(tag):
    if (tag.name, tag.get("id")) in _INFOLEG_NAVIGATION_IDS:
        return DISCARD_INFOLEG_NAVIGATION
    if _INFOLEG_NOTE.match(_collapse(tag.get_text())):
        return DISCARD_INFOLEG_NOTE
    return ""


def _collapse(text):
    return _HTML_WHITESPACE.sub(" ", text).strip(" ")


class _BlockReader:
    """Recorre el documento y arma una línea por bloque de texto."""

    def __init__(self, site_reason):
        self.site_reason = site_reason
        self.lines = []
        self.buffer = []

    def read(self, soup):
        self._visit(soup, "")
        self._flush("")

    def _reason(self, tag, current):
        reason = _GENERIC_RULES.get(tag.name, "")
        if not reason and not current and self.site_reason:
            reason = self.site_reason(tag)
        return reason or current

    def _visit(self, node, current):
        for child in node.children:
            if isinstance(child, Tag):
                reason = self._reason(child, current)
                boundary = reason != current or child.name in BLOCK_TAGS
                if boundary:
                    self._flush(current)
                self._visit(child, reason)
                if boundary:
                    self._flush(reason)
            elif isinstance(child, NavigableString) and not isinstance(child, _NOT_TEXT):
                self.buffer.append(str(child))

    def _flush(self, reason):
        text = _collapse("".join(self.buffer))
        self.buffer.clear()
        if text.strip():
            self.lines.append(
                Line(
                    text=text,
                    x0=None,
                    top=None,
                    x1=None,
                    bottom=None,
                    origin=ORIGIN_WEB,
                    discarded=reason,
                )
            )
