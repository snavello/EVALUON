"""Zonas de tabla de un PDF del pliego (T-070; plan 003, "Carga y lectura" y "Tramos").

El PDF es el pliego sintético de `pdfs.py` (P4): una sola tabla con bordes, en la
página 3, y el encabezado repetido en todas las páginas.
"""

import json

import pytest

from evaluon.norms.reading import UnsupportedFormatError, read_document
from evaluon.tenders.tables import table_zones
from tests.tenders.pdfs import para, synthetic_tender_pdf, table, tender_pdf


@pytest.fixture(scope="module")
def tender():
    return synthetic_tender_pdf()


def test_finds_the_table_zone_on_its_page(tender):
    """REQ-028: la tabla del pliego se encuentra como una zona de su página, y las
    líneas de sus celdas caen dentro de la zona; las demás líneas de esa página no."""
    zones = table_zones(tender)
    assert [zone["page"] for zone in zones] == [3]
    zone = zones[0]

    page = read_document(tender).pages[2]
    inside = [
        line.text
        for line in page.lines
        if zone["top"] <= (line.top + line.bottom) / 2 <= zone["bottom"]
    ]
    assert inside == [
        "RENGLÓN DESCRIPCIÓN CANTIDAD",
        "1 PRODUCTO SINTÉTICO A 100 UNIDADES",
        "2 PRODUCTO SINTÉTICO B 50 UNIDADES",
    ]
    assert zone["x0"] < zone["x1"] and zone["top"] < zone["bottom"]


def test_zones_are_json_with_page_and_position(tender):
    """REQ-028: las zonas se guardan con la lectura (`tenders_reading.tables`): son datos
    JSON con la página y la posición, en puntos y con el origen arriba a la izquierda."""
    zones = table_zones(tender)
    assert json.loads(json.dumps(zones)) == zones
    assert set(zones[0]) == {"page", "x0", "top", "x1", "bottom"}


def test_pages_without_tables_have_no_zones():
    """REQ-028: un PDF sin tablas no tiene zonas."""
    data = tender_pdf([[para("1. OBJETO", "1.1. Texto sintético sin tablas.")]])
    assert table_zones(data) == []


def test_two_tables_on_different_pages():
    """REQ-028: cada tabla es una zona, con su página."""
    data = tender_pdf(
        [
            [para("1. PRIMERA"), table(("A", "B"), ("1", "2"))],
            [para("2. SEGUNDA"), table(("C", "D"), ("3", "4"), ("5", "6"))],
        ]
    )
    assert [zone["page"] for zone in table_zones(data)] == [1, 2]


def test_a_web_page_has_no_zones():
    """REQ-028: una página web guardada no tiene zonas de tabla."""
    assert table_zones(b"<!DOCTYPE html><html><body><p>Texto</p></body></html>") == []


def test_a_damaged_pdf_is_rejected(tender):
    """REQ-028: un PDF dañado se rechaza con el error de formato de la lectura, no con
    el de la biblioteca."""
    with pytest.raises(UnsupportedFormatError):
        table_zones(b"%PDF-1.7\n" + b"\x00" * 64)
