"""Partición de un pliego en tramos (T-070; plan 003, "Tramos" y "Qué es un requisito y
su clase"; ADR-0019, decisión 1).

Los pliegos son sintéticos (`pdfs.py`, P4) e imitan la forma del caso de referencia:
carátula, índice con puntos guía, secciones que vuelven a numerar, cláusulas de hasta
cuatro niveles con y sin espacio después del número, renglones, viñetas, incisos, una
tabla, un anexo, una página sin texto y el encabezado repetido. La tabla de claves
esperadas está escrita a mano, sin correr la partición.
"""

import dataclasses
import re

import pytest

from evaluon.norms.reading import PAGE_DOUBTFUL, read_document
from evaluon.tenders.segmenting import RULES_VERSION, check_coverage, split_tender
from evaluon.tenders.tables import table_zones
from tests.tenders.pdfs import para, synthetic_tender_pdf, table, tender_pdf


@pytest.fixture(scope="module")
def tender():
    data = synthetic_tender_pdf()
    return read_document(data), table_zones(data)


@pytest.fixture(scope="module")
def result(tender):
    reading, zones = tender
    return split_tender(reading, zones)


def by_key(result):
    return {segment.key: segment for segment in result.segments}


def split_pdf(pages, **options):
    data = tender_pdf(pages, header=None)
    return split_tender(read_document(data), table_zones(data), **options)


# Todos los tramos del pliego sintético, en orden: clave, tipo, clase de la sección y
# renglones.
EXPECTED = [
    ("pre/p-1", "parrafo", "", []),
    ("pre/p-2", "parrafo", "", []),
    ("pre/p-3", "parrafo", "", []),
    ("sec-i", "titulo", "", []),
    ("sec-i/1", "titulo", "", []),
    ("sec-i/1.1", "clausula", "", []),
    ("sec-i/2", "titulo", "", []),
    ("sec-i/2.1", "clausula", "", []),
    ("sec-i/2.1/v-1", "vineta", "", []),
    ("sec-i/2.1/v-2", "vineta", "", []),
    ("sec-i/3", "titulo", "", []),
    ("sec-i/3/tabla-1", "tabla", "", []),
    ("sec-i/3/p-1", "parrafo", "", []),
    ("sec-i/4", "titulo", "", []),
    ("sec-i/4.1", "clausula", "", []),
    ("sec-i/5", "titulo", "", []),
    ("sec-i/5.1", "clausula", "", []),
    ("sec-i/6", "titulo", "", []),
    ("sec-i/6.1", "clausula", "", []),
    ("sec-i/7", "titulo", "", []),
    ("sec-i/7.1", "clausula", "", []),
    ("sec-i/7.2", "clausula", "", []),
    ("sec-i/7.3", "clausula", "", []),
    ("sec-i/7.4", "clausula", "", []),
    ("sec-i/7.5", "clausula", "", []),
    ("sec-i/7.5.1", "clausula", "", []),
    ("sec-i/7.5.2", "clausula", "", []),
    ("sec-i/7.5.2.1", "clausula", "", []),
    ("sec-i/7.5.2.2", "clausula", "", []),
    ("sec-i/7.5.3", "clausula", "", []),
    ("sec-i/7.5.3/inc-a", "vineta", "", []),
    ("sec-i/7.5.3/inc-b", "vineta", "", []),
    ("sec-i/8", "titulo", "", []),
    ("sec-i/8.1", "clausula", "", []),
    ("sec-i/9", "titulo", "", []),
    ("sec-i/9.1", "clausula", "", []),
    ("sec-i/10", "titulo", "", []),
    ("sec-i/10.1", "clausula", "", []),
    ("sec-i/10.2", "clausula", "", []),
    ("sec-i/10.2.1", "clausula", "", []),
    ("sec-i/10.2.2", "clausula", "", []),
    ("sec-ii", "titulo", "tecnico", []),
    ("sec-ii/1", "titulo", "tecnico", []),
    ("sec-ii/1.1", "clausula", "tecnico", []),
    ("sec-ii/1.2", "clausula", "tecnico", []),
    ("sec-ii/1.2/v-1", "vineta", "tecnico", []),
    ("sec-ii/1.2/v-2", "vineta", "tecnico", []),
    ("sec-iii", "titulo", "tecnico", []),
    ("sec-iii/1", "titulo", "tecnico", [1]),
    ("sec-iii/1.1", "clausula", "tecnico", [1]),
    ("sec-iii/1.2", "clausula", "tecnico", [1]),
    ("sec-iii/2", "titulo", "tecnico", [2, 3, 4]),
    ("sec-iii/2.1", "clausula", "tecnico", [2, 3, 4]),
    ("pagina-7", "pagina", "", []),
    ("sec-iv", "titulo", "", []),
    ("sec-iv/anexo-i", "titulo", "", []),
    ("sec-iv/anexo-i/p-1", "parrafo", "", []),
    ("sec-iv/anexo-i/p-2", "parrafo", "", []),
    ("sec-iv/anexo-i/p-3", "parrafo", "", []),
]


# --- Claves, tipos, clase y renglones (ADR-0019, decisión 1) ---------------------------


def test_segments_match_the_hand_written_table(result):
    """REQ-024, REQ-028: el pliego se parte en los tramos esperados, en el orden del
    documento, cada uno con su clave estable, su tipo, la clase de su sección y sus
    renglones."""
    got = [
        (segment.key, segment.segment_type, segment.section_class, segment.items)
        for segment in result.segments
    ]
    assert got == EXPECTED
    assert [segment.order for segment in result.segments] == list(
        range(1, len(EXPECTED) + 1)
    )


@pytest.mark.parametrize(
    "key, starts_with",
    [
        ("sec-i/7.5.2", "7.5.2. Presentar la declaración jurada"),
        ("sec-iii/1.1", "1.1. Composición del producto"),
        ("sec-ii/1.2/v-1", "• Vencimiento mayor a once meses."),
        ("sec-iv/anexo-i/p-1", "El que suscribe declara bajo juramento"),
        ("sec-i/7.5.3/inc-b", "b) falte la garantía."),
        ("sec-i/3/p-1", "Instrucciones para cotizar"),
        ("pre/p-1", "PLIEGO DE BASES Y CONDICIONES PARTICULARES"),
    ],
)
def test_key_points_to_its_text(result, key, starts_with):
    """REQ-025: cada clave de la tabla del plan señala el texto que le corresponde."""
    assert by_key(result)[key].text.startswith(starts_with)


def test_numbering_restarts_in_each_section(result):
    """REQ-024: la numeración vuelve a empezar en cada sección: hay una "1.1" en las
    secciones I, II y III, cada una con su clave."""
    segments = by_key(result)
    assert segments["sec-i/1.1"].text.startswith("1.1. El objeto")
    assert segments["sec-ii/1.1"].text.startswith("1.1. Los bienes se entregan")
    assert segments["sec-iii/1.1"].text.startswith("1.1. Composición")


def test_numbers_at_the_start_of_a_line_do_not_cut(result):
    """REQ-024: "3.972 kcal" y "1.300 mg" al comienzo de una línea no continúan la
    numeración de su sección: quedan dentro de la cláusula 1.1 y se informan."""
    segments = by_key(result)
    clause = segments["sec-iii/1.1"].text
    assert "3.972 kcal por kilogramo" in clause
    assert "1.300 mg por kilogramo" in clause
    assert not any("3.972" in key or "1.300" in key for key in segments)
    assert [heading["number"] for heading in result.report["rejected_headings"]] == [
        "3.972",
        "1.300",
    ]


def test_clause_without_space_after_its_number_cuts(result):
    """REQ-024: "10.2.1.Una vez" (sin espacio después del número) empieza la cláusula
    10.2.1, y "10.2.2.La" la siguiente."""
    segments = by_key(result)
    assert segments["sec-i/10.2.1"].text == (
        "10.2.1.Una vez entregados los bienes, se emite la conformidad provisoria."
    )
    assert segments["sec-i/10.2.2"].text.startswith("10.2.2.La conformidad")


def test_four_levels_with_and_without_space(result):
    """REQ-024: la numeración llega a cuatro niveles, con espacio ("7.5.2.1. Firmada")
    y sin espacio ("7.5.2.2.Con"), y después vuelve a un nivel superior (7.5.3)."""
    segments = by_key(result)
    assert segments["sec-i/7.5.2.1"].text == (
        "7.5.2.1. Firmada por el representante legal sintético."
    )
    assert segments["sec-i/7.5.2.2"].text == "7.5.2.2.Con la fecha de la presentación."
    assert segments["sec-i/7.5.2.2"].path.endswith("› 7.5 › 7.5.2 › 7.5.2.2")
    assert segments["sec-i/7.5.3"].text.startswith("7.5.3. Las ofertas")


def test_title_without_text_is_a_title(result):
    """REQ-024: una cláusula que es solo su título, seguida de sus subcláusulas, es un
    tramo `titulo`; con su texto, es una `clausula`."""
    segments = by_key(result)
    assert segments["sec-i/8"].segment_type == "titulo"
    assert segments["sec-i/8"].text == "8. VIGENCIA DE LA ORDEN DE COMPRA"
    assert segments["sec-i/8.1"].segment_type == "clausula"


def test_items_pass_to_the_segments_that_hang_from_them(result):
    """REQ-024: el renglón de una cláusula pasa a los tramos que cuelgan de ella;
    "RENGLONES NROS. 2 A 4" da los renglones 2, 3 y 4; los demás tramos no tienen
    renglón, aunque una tabla de la Sección I nombre renglones."""
    segments = by_key(result)
    assert segments["sec-iii/1"].items == [1]
    assert segments["sec-iii/1.2"].items == [1]
    assert segments["sec-iii/2"].items == [2, 3, 4]
    assert segments["sec-iii/2.1"].items == [2, 3, 4]
    assert segments["sec-i/3/tabla-1"].items == []


def test_reading_lists_its_items_with_the_heading_key(result):
    """REQ-024: la lista de renglones de la lectura trae cada renglón con la clave del
    tramo de su encabezado."""
    assert result.items == [
        {"number": 1, "key": "sec-iii/1"},
        {"number": 2, "key": "sec-iii/2"},
        {"number": 3, "key": "sec-iii/2"},
        {"number": 4, "key": "sec-iii/2"},
    ]


def test_a_range_for_all_items_does_not_take_the_key_of_each_item():
    """REQ-024: una cláusula de condiciones para todos los renglones ("RENGLONES NROS. 1
    A 3", como en la entrega) da sus renglones a sus tramos, pero la lista de la lectura
    lleva, para cada renglón, el encabezado que lo nombra solo; el rango, solo para el
    renglón que no tiene uno propio."""
    result = split_pdf(
        [
            [
                para("SECCIÓN I - CONDICIONES PARTICULARES"),
                para("1. ENTREGA", "1.1. RENGLONES NROS. 1 A 3: entrega en diez días."),
                para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS"),
                para("1. RENGLÓN N° 1 - PRODUCTO A", "1.1. Envase de un kilogramo."),
                para("2. RENGLÓN N° 2 - PRODUCTO B", "2.1. Envase de dos kilogramos."),
            ]
        ]
    )
    assert by_key(result)["sec-i/1.1"].items == [1, 2, 3]
    assert by_key(result)["sec-ii/2.1"].items == [2]
    assert result.items == [
        {"number": 1, "key": "sec-ii/1"},
        {"number": 2, "key": "sec-ii/2"},
        {"number": 3, "key": "sec-i/1.1"},
    ]


def test_section_class_comes_from_the_section_title(result):
    """REQ-024: los tramos de una sección titulada "Especificaciones técnicas" tienen
    clase técnica; los de "Condiciones particulares" y los de los anexos, ninguna."""
    for segment in result.segments:
        if segment.key.startswith(("sec-ii", "sec-iii")):
            assert segment.section_class == "tecnico", segment.key
        else:
            assert segment.section_class == "", segment.key


@pytest.mark.parametrize(
    "title, section_class",
    [
        ("SECCIÓN I - REQUISITOS FORMALES", "formal"),
        ("SECCIÓN I - REQUISITOS ECONÓMICOS", "economico"),
        ("SECCIÓN I - ESPECIFICACIONES TECNICAS", "tecnico"),
        ("SECCIÓN I - CONDICIONES GENERALES", ""),
    ],
)
def test_each_class_named_by_a_section_title(title, section_class):
    """REQ-024: la clase que nombra el título de la sección pasa a todos sus tramos."""
    result = split_pdf([[para(title), para("1. TEMA", "1.1. Texto sintético.")]])
    assert {segment.section_class for segment in result.segments} == {section_class}


def test_labels_and_paths(result):
    """REQ-025: cada tramo lleva su encabezado tal como figura y una ruta legible."""
    segments = by_key(result)
    assert segments["sec-i/8"].label == "8. VIGENCIA DE LA ORDEN DE COMPRA"
    assert segments["sec-i/8"].path == "Sección I › 8. Vigencia de la orden de compra"
    assert segments["sec-i/7.5.2"].label == "7.5.2."
    assert segments["sec-i/7.5.2"].path == (
        "Sección I › 7. Requisitos de la presentación › 7.5 › 7.5.2"
    )
    assert segments["sec-ii/1.2/v-1"].path == (
        "Sección II › 1. Cláusulas generales › 1.2 › viñeta 1"
    )
    assert segments["sec-i/7.5.3/inc-a"].path.endswith("› 7.5.3 › inciso a)")
    assert segments["sec-iv/anexo-i/p-1"].path == "Sección IV › Anexo I › párrafo 1"
    assert segments["sec-i/3/tabla-1"].path == "Sección I › 3. Detalle de los bienes › tabla 1"
    assert segments["sec-i"].label == "SECCIÓN I - CONDICIONES PARTICULARES"
    assert segments["pagina-7"].path == "Página 7"


# --- Lo que la lectura no puede ubicar queda pendiente (REQ-028) ----------------------


def test_table_is_one_pending_segment(result):
    """REQ-028: las líneas de la zona de tabla forman un tramo `tabla`, pendiente de
    revisión, con todas sus celdas."""
    segment = by_key(result)["sec-i/3/tabla-1"]
    assert segment.review_reason == "tabla"
    assert segment.text.startswith("RENGLÓN DESCRIPCIÓN CANTIDAD")
    assert segment.text.endswith("2 PRODUCTO SINTÉTICO B 50 UNIDADES")
    assert segment.page_start == segment.page_end == 3


def test_page_without_text_is_a_pending_segment(result):
    """REQ-028: la página sin texto legible es un tramo `pagina` sin texto, pendiente de
    revisión, con su número de página."""
    segment = by_key(result)["pagina-7"]
    assert segment.text == ""
    assert segment.char_start == segment.char_end
    assert (segment.page_start, segment.page_end) == (7, 7)
    assert segment.review_reason == "pagina_ilegible"


def test_doubtful_page_marks_its_segments(tender):
    """REQ-028: los tramos de una página dudosa quedan pendientes con ese motivo."""
    reading, zones = tender
    pages = list(reading.pages)
    pages[4] = dataclasses.replace(pages[4], status=PAGE_DOUBTFUL)
    result = split_tender(dataclasses.replace(reading, pages=pages), zones)
    reasons = {s.key: s.review_reason for s in result.segments}
    assert reasons["sec-ii/1.1"] == "pagina_dudosa"
    assert reasons["sec-ii/1.2/v-2"] == "pagina_dudosa"
    assert reasons["sec-iii/1.1"] == ""


def test_text_outside_every_rule_is_unlocated():
    """REQ-028: un texto que no encaja en ninguna regla (entre el título de una sección
    y su primera cláusula) queda `no_ubicado`, pendiente de revisión, nunca afuera."""
    result = split_pdf(
        [
            [
                para("SECCIÓN I - CONDICIONES PARTICULARES"),
                para("Texto sintético sin número antes de la primera cláusula."),
                para("1. OBJETO", "1.1. Texto sintético."),
            ]
        ]
    )
    segment = by_key(result)["sec-i/no-ubicado-1"]
    assert segment.segment_type == "no_ubicado"
    assert segment.review_reason == "no_ubicado"
    assert segment.text == "Texto sintético sin número antes de la primera cláusula."


def test_report_lists_the_pending_segments(result):
    """REQ-028: el informe de la lectura trae los tramos pendientes con su motivo, los
    tramos por tipo, las páginas por estado y la versión de las reglas."""
    report = result.report
    assert report["pending"] == [
        {"key": "sec-i/3/tabla-1", "reason": "tabla", "detail": ""},
        {"key": "pagina-7", "reason": "pagina_ilegible", "detail": ""},
    ]
    assert report["segments_by_type"]["clausula"] == 26
    assert report["segments_by_type"]["pagina"] == 1
    assert report["pages_by_status"] == {"legible": 7, "no_leida": 1}
    assert report["rules_version"] == RULES_VERSION
    assert report["items"] == result.items


# --- Índice, texto literal y cobertura -------------------------------------------------


def test_index_produces_no_segments(result):
    """REQ-024: el índice no produce tramos: se descarta, y se cuenta aparte."""
    for segment in result.segments:
        assert "ÍNDICE" not in segment.text
        assert "....." not in segment.text
    assert [reason for _, _, reason in result.discarded] == ["indice"]
    start, end, _ = result.discarded[0]
    index_text = result.canonical.text[start:end]
    assert index_text.startswith("ÍNDICE")
    assert index_text.endswith("SECCIÓN IV - ANEXOS ........................................ 8")


def test_each_text_equals_its_slice_of_the_canonical_text(result):
    """REQ-025: el texto de cada tramo es igual a su recorte del texto canónico, sin
    espacios en los bordes, y lleva sus páginas."""
    text = result.canonical.text
    for segment in result.segments:
        assert segment.text == text[segment.char_start : segment.char_end]
        assert segment.text == segment.text.strip()
    segments = by_key(result)
    assert (segments["sec-i/7.5.2"].page_start, segments["sec-i/7.5.2"].page_end) == (4, 4)
    assert segments["sec-i/7.5.2"].text_origin == "pdf_text"


def test_coverage_adds_up_to_the_total(result):
    """REQ-028: cada carácter del texto canónico está en un solo tramo, en el índice
    descartado o es un separador entre tramos; la suma da el total. Las líneas que la
    lectura descartó (encabezado y pie) se cuentan aparte."""
    coverage = result.coverage
    assert coverage["matches"] is True
    assert coverage["problems"] == []
    assert coverage["total"] == len(result.canonical.text)
    assert (
        coverage["segments"] + coverage["discarded"] + coverage["separators"]
        == coverage["total"]
    )
    assert coverage["segments"] == sum(len(s.text) for s in result.segments)
    assert coverage["discarded_lines"] == 14  # encabezado y pie de las 7 páginas con texto


def test_header_and_footer_are_not_in_any_segment(result):
    """REQ-024: el encabezado repetido y el número de página no entran en los tramos."""
    for segment in result.segments:
        assert "Año sintético" not in segment.text
        assert not re.search(r"Página \d+ de \d+", segment.text)


# --- Tramos largos, pliego sin secciones y claves repetidas ----------------------------


def test_long_segment_is_split_at_sentence_boundaries(tender):
    """REQ-025: un tramo más largo que el máximo se parte en límites de oración: la
    primera parte conserva la clave y las siguientes suman `#2`, `#3`; cada parte es un
    recorte del texto canónico y ninguna se pierde."""
    reading, zones = tender
    result = split_tender(reading, zones, max_chars=40)
    parts = [s for s in result.segments if s.key.split("#")[0] == "sec-i/7.5.3"]
    assert [s.key for s in parts][:2] == ["sec-i/7.5.3", "sec-i/7.5.3#2"]
    for part in parts:
        assert len(part.text) <= 40 or " " not in part.text
    joined = result.canonical.text[parts[0].char_start : parts[-1].char_end]
    assert joined == " ".join(part.text for part in parts)
    assert result.coverage["matches"] is True


def test_split_prefers_the_end_of_a_sentence():
    """REQ-025: el corte cae después del punto de una oración, no en medio de ella."""
    result = split_pdf(
        [
            [
                para(
                    "1. TEMA",
                    "1.1. Primera oración sintética. Segunda oración sintética más larga.",
                )
            ]
        ],
        max_chars=50,
    )
    segments = by_key(result)
    assert segments["1.1"].text == "1.1. Primera oración sintética."
    assert segments["1.1#2"].text == "Segunda oración sintética más larga."


def test_tender_without_sections_uses_keys_without_prefix():
    """REQ-024: un pliego sin secciones usa las claves sin prefijo; lo que va antes de
    la primera cláusula es la carátula."""
    result = split_pdf(
        [
            [
                para("PLIEGO SINTÉTICO"),
                para("7. REQUISITOS", "7.1. Presentar la oferta sintética."),
                para("8. ENTREGA", "8.1. Entregar en diez días."),
            ]
        ]
    )
    assert [s.key for s in result.segments] == ["pre/p-1", "7", "7.1", "8", "8.1"]
    assert result.coverage["matches"] is True


def test_repeated_key_gets_a_suffix():
    """REQ-024: una clave repetida suma `~2`."""
    result = split_pdf(
        [
            [
                para("1. TEMA", "1.1. Texto sintético."),
                para("ANEXO I - FORMULARIO SINTÉTICO"),
                para("Primer párrafo sintético."),
                para("ANEXO I - FORMULARIO SINTÉTICO"),
                para("Segundo párrafo sintético."),
            ]
        ]
    )
    assert [s.key for s in result.segments] == [
        "1",
        "1.1",
        "anexo-i",
        "anexo-i/p-1",
        "anexo-i~2",
        "anexo-i~2/p-1",
    ]


def test_table_in_an_annex_hangs_from_the_annex():
    """REQ-028: una tabla dentro de un anexo cuelga del anexo y queda pendiente."""
    result = split_pdf(
        [
            [
                para("ANEXO II - PLANILLA SINTÉTICA"),
                table(("CONCEPTO", "VALOR"), ("Uno", "10"), ("Dos", "20")),
                para("Firma: ______________"),
            ]
        ]
    )
    segments = by_key(result)
    assert segments["anexo-ii/tabla-1"].review_reason == "tabla"
    assert segments["anexo-ii/p-1"].text == "Firma: ______________"


# --- Saltos de numeración (verificación de T-070, F1) ----------------------------------


def jumped_numbering():
    """Pliego de la reproducción de F1: la numeración salta de la 1 a la 3."""
    return split_pdf(
        [
            [
                para("SECCIÓN III - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
                para("1. RENGLÓN N° 1 - PRODUCTO UNO", "1.1. Envase de un kilogramo."),
                para("3. RENGLÓN N° 3 - PRODUCTO TRES", "3.1. Envase de tres kilogramos."),
                para("4. RENGLÓN N° 4 - PRODUCTO CUATRO", "4.1. Envase de cuatro kilogramos."),
            ]
        ],
        max_chars=4000,
    )


def test_rejected_heading_opens_a_pending_unlocated_segment():
    """REQ-028: un encabezado que el control de secuencia rechaza no queda en silencio
    dentro de la cláusula anterior: abre un tramo `no_ubicado`, pendiente de revisión por
    numeración inesperada, que llega hasta el próximo encabezado aceptado."""
    result = jumped_numbering()
    segments = by_key(result)
    assert segments["sec-iii/1.1"].text == "1.1. Envase de un kilogramo."
    first = segments["sec-iii/no-ubicado-1"]
    assert first.segment_type == "no_ubicado"
    assert first.review_reason == "no_ubicado"
    assert first.review_detail == "numeracion_inesperada"
    assert first.text == "3. RENGLÓN N° 3 - PRODUCTO TRES 3.1. Envase de tres kilogramos."
    assert first.label == "3. RENGLÓN N° 3 - PRODUCTO TRES"
    assert segments["sec-iii/no-ubicado-2"].text.startswith("4. RENGLÓN N° 4")
    assert result.report["pending"] == [
        {"key": "sec-iii/no-ubicado-1", "reason": "no_ubicado", "detail": "numeracion_inesperada"},
        {"key": "sec-iii/no-ubicado-2", "reason": "no_ubicado", "detail": "numeracion_inesperada"},
    ]
    assert result.coverage["matches"] is True


def test_items_are_found_even_with_broken_numbering():
    """REQ-024: los renglones se reconocen por su encabezado aunque la numeración de
    cláusulas esté rota: entran en la lista de la lectura con la clave de su tramo
    `no_ubicado`, y sus especificaciones no quedan con el renglón anterior."""
    result = jumped_numbering()
    segments = by_key(result)
    assert segments["sec-iii/1.1"].items == [1]
    assert segments["sec-iii/no-ubicado-1"].items == [3]
    assert segments["sec-iii/no-ubicado-2"].items == [4]
    assert result.items == [
        {"number": 1, "key": "sec-iii/1"},
        {"number": 3, "key": "sec-iii/no-ubicado-1"},
        {"number": 4, "key": "sec-iii/no-ubicado-2"},
    ]
    assert {s.section_class for s in result.segments} == {"tecnico"}


def test_numbering_resumes_after_an_unlocated_segment():
    """REQ-028: el tramo `no_ubicado` termina en el próximo encabezado que continúa la
    numeración, que vuelve a ser una cláusula."""
    result = split_pdf(
        [
            [
                para("1. TEMA", "1.1. Texto uno."),
                para("1.3. Texto con un número que salta."),
                para("1.4. Otro texto rechazado."),
                para("2. OTRO TEMA", "2.1. Texto dos."),
            ]
        ]
    )
    assert [s.key for s in result.segments] == ["1", "1.1", "no-ubicado-1", "2", "2.1"]
    assert by_key(result)["no-ubicado-1"].text == (
        "1.3. Texto con un número que salta.\n1.4. Otro texto rechazado."
    )


# --- Controles sin test en la verificación (M9, M10, M13) ------------------------------


def test_coverage_reports_holes_and_overlaps(result):
    """REQ-028: el control de cobertura informa un hueco (un tramo que falta) y un
    solapamiento (un tramo repetido), y entonces no cierra."""
    segments = list(result.segments)
    missing = segments[:10] + segments[11:]
    holed = check_coverage(result.canonical, missing, result.discarded)
    assert holed["matches"] is False
    assert [p["kind"] for p in holed["problems"]] == ["hole"]
    assert holed["problems"][0]["char_start"] <= segments[10].char_start

    doubled = check_coverage(result.canonical, segments + [segments[10]], result.discarded)
    assert doubled["matches"] is False
    assert [p["kind"] for p in doubled["problems"]] == ["overlap"]


def test_inciso_mark_in_the_middle_of_a_sentence_does_not_cut():
    """REQ-024: una línea que empieza con "a)" sin que el texto anterior cierre con
    punto, dos puntos o punto y coma no es un inciso: sigue en su cláusula."""
    result = split_pdf(
        [[para("1. TEMA", "1.1. Rige lo previsto en el inciso", "a) del régimen sintético.")]]
    )
    assert [s.key for s in result.segments] == ["1", "1.1"]
    assert by_key(result)["1.1"].text.endswith("inciso a) del régimen sintético.")


def test_two_lists_in_one_clause_get_unique_keys():
    """REQ-024: dos listas de incisos en una misma cláusula repiten `inc-a`: la segunda
    suma `~2`, y todas las claves de la lectura son únicas."""
    result = split_pdf(
        [
            [
                para(
                    "1. TEMA",
                    "1.1. Primera lista:",
                    "a) uno;",
                    "b) dos.",
                    "Segunda lista:",
                    "a) tres.",
                )
            ]
        ]
    )
    keys = [s.key for s in result.segments]
    assert keys == ["1", "1.1", "1.1/inc-a", "1.1/inc-b", "1.1/inc-a~2"]
    assert len(set(keys)) == len(keys)
