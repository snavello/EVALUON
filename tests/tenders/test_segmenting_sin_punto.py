"""Tramos de un pliego con cláusulas sin punto y cuadros de texto (T-178; REQ-028 y
REQ-024; plan 003, "Tramos").

Reproduce, con un pliego inventado, la forma que dejó sin ubicar todo el cuerpo de un
pliego real (prueba AABN5): los títulos de primer nivel van sin punto ("5 DEFINICIÓN DEL
SERVICIO.") y varias cláusulas están dentro de un recuadro de una sola columna que la
búsqueda de tablas tomaba por tabla.
"""

from evaluon.norms.reading import read_document
from evaluon.tenders.segmenting import split_tender
from evaluon.tenders.tables import table_zones
from tests.tenders.pdfs import para, table, tender_pdf


def split_pdf(pages):
    data = tender_pdf(pages, header=None)
    return split_tender(read_document(data), table_zones(data)), data


PAGES = [
    [
        para("PLIEGO INVENTADO DE PRUEBA"),
        para("SECCIÓN I – DESCRIPCIÓN PARTICULAR"),
        para("1 OBJETO.", "1.1 El objeto es un servicio inventado."),
        para("2 DEFINICIONES.", "2.1 Los términos se interpretan en plural."),
    ],
    [
        para("SECCIÓN II. CONDICIONES DEL CONTRATO."),
        para("3 DEFINICIÓN DEL SERVICIO.", "3.1 Se contrata un servicio.", "3.1.1 Renglón 1: sede norte."),
        para("3.1.2 Renglón 2: sede sur."),
        para("4 VISITA OBLIGATORIA", "4.1 Los oferentes deberán visitar las sedes."),
        para("3 UNIDADES POR CADA VISITA."),
        para("5 REQUISITOS ADMINISTRATIVOS.", "5.1 Constituir domicilio especial."),
    ],
]


def test_unnumbered_dot_titles_open_clauses():
    """REQ-028: un título de primer nivel en mayúsculas sin punto ("5 VISITA OBLIGATORIA")
    abre su cláusula; nada de la sección queda como tramo no ubicado."""
    result, _ = split_pdf(PAGES)
    keys = [segment.key for segment in result.segments]
    for key in (
        "sec-i/1", "sec-i/1.1", "sec-i/2", "sec-ii/3", "sec-ii/3.1", "sec-ii/3.1.2",
        "sec-ii/4", "sec-ii/4.1", "sec-ii/5", "sec-ii/5.1",
    ):
        assert key in keys, key
    assert not [s for s in result.segments if s.segment_type == "no_ubicado"]
    assert result.report["coverage"]["matches"]


def test_a_number_inside_a_sentence_is_not_a_clause():
    """REQ-028: "3 UNIDADES" no abre una cláusula si no continúa la numeración: queda
    dentro del tramo abierto, sin crear un tramo no ubicado."""
    result, _ = split_pdf(PAGES)
    keys = [segment.key for segment in result.segments]
    assert "sec-ii/3~2" not in keys
    assert not [s for s in result.segments if s.segment_type == "no_ubicado"]
    clause = next(s for s in result.segments if s.key == "sec-ii/4.1")
    assert "3 UNIDADES" in clause.text


def test_boxed_text_in_one_column_is_not_a_table():
    """REQ-028: un recuadro de una sola columna con cláusulas es texto, no tabla: sus
    cláusulas se ubican y no quedan pendientes como tabla."""
    pages = [
        [para("SECCIÓN I – CONDICIONES"), para("1. PERSONAL.")],
        [table(("1.1 El personal debe estar registrado.",), ("1.2 El personal debe usar uniforme.",))],
    ]
    result, data = split_pdf(pages)
    assert table_zones(data) == []
    keys = [segment.key for segment in result.segments]
    assert "sec-i/1.1" in keys and "sec-i/1.2" in keys
    assert not [s for s in result.segments if s.segment_type == "tabla"]


def test_real_tables_are_still_tables():
    """REQ-028: una tabla de dos o más columnas sigue siendo tabla pendiente."""
    pages = [[para("SECCIÓN I – CONDICIONES"), para("1. TABLA."), table(("A", "B"), ("1", "2"))]]
    result, data = split_pdf(pages)
    assert len(table_zones(data)) == 1
    assert [s for s in result.segments if s.segment_type == "tabla"]
