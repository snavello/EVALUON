"""Zonas de tabla de cada página de un PDF del pliego (plan 003, "Carga y lectura" y
"Tramos"; ADR-0019; T-070).

La lectura de la 001 (`evaluon/norms/reading/`) entrega líneas de texto, sin saber si
una línea está dentro de una tabla. Una tabla leída línea por línea mezcla las
condiciones de sus celdas (el detalle de renglones y cantidades, las multas), así que la
partición en tramos (`segmenting.py`) junta las líneas que caen dentro de una zona de
tabla en un tramo `tabla`, pendiente de revisión (REQ-028).

Las zonas se buscan con pdfplumber, con su estrategia por omisión (bordes dibujados), sin
tocar la lectura de la 001. Cada zona es un rectángulo en las unidades de la página, con
el origen arriba a la izquierda, como las posiciones de las líneas de la lectura:

    {"page": 5, "x0": 112.0, "top": 385.0, "x1": 519.0, "bottom": 705.0}

Se guardan en `tenders_reading.tables`. Una página web no tiene zonas. Todo corre en
CPU y sin conexión (P4).
"""

import io

from evaluon.norms.reading import FORMAT_PDF, UnsupportedFormatError, detect_format

# Decimales de las medidas, como en la lectura de la 001.
_DECIMALS = 2

_DAMAGED_MESSAGE = "El PDF está dañado o incompleto: no se pueden buscar sus tablas."


def table_zones(data: bytes) -> list[dict]:
    """Las zonas de tabla de un documento, página por página, en el orden del archivo.
    Un documento que no es PDF no tiene zonas; un PDF dañado levanta
    `UnsupportedFormatError`."""
    if detect_format(data) != FORMAT_PDF:
        return []

    import pdfplumber
    from pdfminer.psparser import PSException
    from pdfplumber.utils.exceptions import PdfminerException

    zones = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                for table in page.find_tables():
                    x0, top, x1, bottom = table.bbox
                    zones.append(
                        {
                            "page": number,
                            "x0": round(float(x0), _DECIMALS),
                            "top": round(float(top), _DECIMALS),
                            "x1": round(float(x1), _DECIMALS),
                            "bottom": round(float(bottom), _DECIMALS),
                        }
                    )
    except (PdfminerException, PSException) as error:
        raise UnsupportedFormatError(_DAMAGED_MESSAGE) from error
    return zones
