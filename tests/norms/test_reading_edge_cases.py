"""Casos de lectura que el aviso de T-028 dejó sin probar, sumados en T-043 (ADR-0004,
"Cómo se lee"; plan 001, "Ingesta"; `norms/reading/__init__.py`, `read_document`).

- Un PDF que pypdfium2 abre y pdfplumber no: se rechaza como PDF dañado, con
  `UnsupportedFormatError`, y no con el error de la biblioteca.
- Un PDF con una página cuya capa de texto es inservible: recorre `read_document` desde la
  clasificación de la página hasta el reconocimiento sobre imagen.
- La codificación de una página web queda también en el hecho `reread` (P6).

Documentos de prueba, públicos o sintéticos (P4): el extracto del anexo de la
Disposición AFIP 247/2022 (T-012), su página web armada en T-028 y un PDF sintético
armado en el test.
"""

import io
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import pytest

from evaluon.audit.models import AuditEvent
from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_OCR,
    PAGE_KIND_UNUSABLE_TEXT,
    UnsupportedFormatError,
    classify_page,
    read_document,
)
from evaluon.norms.services import loading
from evaluon.norms.splitting import split_document
from tests.norms.test_three_formats import DATA_247

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
EXTRACT = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
WEB_PAGE = FIXTURES / "disp-247-2022-anexo-extracto.html"

# Proporción del extracto que se conserva: pypdfium2 reconstruye lo que falta del final
# (la tabla de referencias cruzadas) y pdfplumber no.
CUT_SHARE = 0.999

# Texto sintético de la página con capa de texto inservible.
SYNTHETIC_LINES = [
    "ARTICULO 1. OBJETO. El presente regimen",
    "regula las contrataciones de bienes y",
    "servicios del Organismo.",
]


def pdf_with_private_use_text_layer(lines):
    """Un PDF de una página con texto dibujado en Helvetica cuya capa de texto
    (`ToUnicode`) da caracteres de uso privado: se ve el texto, pero la capa no sirve.
    Es la forma de un PDF con fuentes sin correspondencia de caracteres."""
    cmap = (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap "
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def "
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def "
        "1 begincodespacerange <00> <FF> endcodespacerange "
        "1 beginbfrange <20> <7E> <E020> endbfrange endcmap "
        "CMapName currentdict /CMap defineresource pop end end"
    )
    content = "BT /F1 16 Tf 72 720 Td 22 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        f"<< /Length {len(cmap)} >>\nstream\n{cmap}\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def test_a_pdf_that_pypdfium2_opens_and_pdfplumber_does_not_is_rejected_as_damaged():
    """REQ-015 (aviso de T-028): el extracto cortado al 0,999 lo abre pypdfium2, que
    clasifica sus páginas, pero no pdfplumber, que lee las de texto. La lectura lo rechaza
    como PDF dañado, en lenguaje llano, y no deja pasar el error de la biblioteca."""
    data = EXTRACT.read_bytes()
    damaged = data[: int(len(data) * CUT_SHARE)]

    document = pdfium.PdfDocument(damaged)
    try:
        assert len(document) == 6
    finally:
        document.close()
    with pytest.raises(Exception) as plumber_error:
        with pdfplumber.open(io.BytesIO(damaged)) as pdf:
            for page in pdf.pages:
                page.extract_text()
    assert not isinstance(plumber_error.value, UnsupportedFormatError)

    with pytest.raises(UnsupportedFormatError, match="El PDF está dañado o incompleto"):
        read_document(damaged)


def test_a_page_with_an_unusable_text_layer_is_recognized_through_read_document():
    """REQ-015 (aviso de T-028): una página cuya capa de texto son caracteres de uso
    privado se clasifica como texto inservible y `read_document` la reconoce sobre
    imagen: sus líneas traen origen `ocr`, con confianza, y el texto visible; la lectura
    registra las versiones del reconocimiento. Partida, la unidad sale con origen
    `ocr`."""
    data = pdf_with_private_use_text_layer(SYNTHETIC_LINES)
    document = pdfium.PdfDocument(data)
    try:
        assert classify_page(document[0]) == PAGE_KIND_UNUSABLE_TEXT
    finally:
        document.close()

    reading = read_document(data)

    assert reading.file_format == FORMAT_PDF
    page = reading.pages[0]
    assert page.classification == PAGE_KIND_UNUSABLE_TEXT
    assert page.origin == ORIGIN_OCR
    assert page.lines and all(line.origin == ORIGIN_OCR for line in page.lines)
    assert all(line.confidence is not None for line in page.lines)
    recognized = " ".join(line.text for line in page.lines)
    assert "ARTICULO 1. OBJETO." in recognized
    assert "contrataciones" in recognized
    assert "" not in recognized
    assert reading.tool_versions["tesseract_spa_sha256"]

    result = split_document(reading, part="cuerpo")
    units = {unit.key: unit for unit in result.units}
    assert units["art-1"].text_origin == ORIGIN_OCR


@pytest.mark.django_db
def test_reread_of_a_web_page_records_its_encoding(read_write_user):
    """REQ-012, REQ-015 (aviso de T-028): la relectura de una página web vuelve a detectar
    su codificación y la deja en la lectura nueva y en el hecho `reread`, como la carga en
    el hecho `load` (P6)."""
    first = loading.load_norm(
        read_write_user,
        data=WEB_PAGE.read_bytes(),
        file_name=WEB_PAGE.name,
        part="anexo",
        general_regime=True,
        **DATA_247,
    )

    result = loading.reread_document(read_write_user, first.document.pk)

    assert result.reading.pages["encoding"] == "cp1252"
    event = AuditEvent.objects.get(event_type="reread")
    assert event.detail["file"]["format"] == "html"
    assert event.detail["file"]["encoding"] == "cp1252"
    assert event.detail["tool_versions"]["beautifulsoup4"]
