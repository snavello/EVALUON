"""Lectura de PDF con texto con pdfplumber (ADR-0004, alternativa B; T-012).

Toma la capa de texto de cada página y la entrega en líneas, de arriba hacia abajo, con
su posición en puntos y origen `pdf_text`. No normaliza el texto: lo deja como lo arma
pdfplumber a partir de los caracteres del PDF. Una página sin capa de texto (en blanco o
que es solo una imagen) se informa como no leída y no aporta líneas (REQ-004).

Los parámetros de agrupación de caracteres quedan fijos acá, no librados a los valores
por omisión de la biblioteca, para que la misma entrada dé siempre la misma salida.
"""

import io
from importlib.metadata import version

import pdfplumber

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_PDF_TEXT,
    PAGE_NOT_READ,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
)

# Distancia máxima, en puntos, entre caracteres de una misma palabra (horizontal) y de
# una misma línea (vertical). Son los valores por omisión de pdfplumber 0.11.
X_TOLERANCE = 3
Y_TOLERANCE = 3

# Decimales con que se guardan las posiciones.
POSITION_DECIMALS = 2

# Bibliotecas cuya versión se registra con la lectura (P6).
TOOLS = ("pdfplumber", "pdfminer.six", "pypdfium2")


def tool_versions():
    """Versiones instaladas de las herramientas de lectura de PDF con texto."""
    return {tool: version(tool) for tool in TOOLS}


def read_pdf_text(data: bytes) -> DocumentReading:
    """Lee todas las páginas de un PDF con texto, en el orden del archivo."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [_read_page(page) for page in pdf.pages]
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions=tool_versions())


def _read_page(page):
    lines = [
        Line(
            text=line["text"],
            x0=_position(line["x0"]),
            top=_position(line["top"]),
            x1=_position(line["x1"]),
            bottom=_position(line["bottom"]),
            origin=ORIGIN_PDF_TEXT,
        )
        for line in page.extract_text_lines(
            x_tolerance=X_TOLERANCE, y_tolerance=Y_TOLERANCE, strip=True, return_chars=False
        )
        if line["text"].strip()
    ]
    return Page(
        number=page.page_number,
        width=_position(page.width),
        height=_position(page.height),
        status=PAGE_READ if lines else PAGE_NOT_READ,
        lines=lines,
    )


def _position(value):
    return round(float(value), POSITION_DECIMALS)
