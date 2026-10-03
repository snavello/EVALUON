"""Partición de dictámenes legales y recomendaciones de auditoría en puntos y párrafos
(T-024; ADR-0004, "Cómo se parte", fila "Dictamen o recomendación"; plan 001,
"Identificación de unidades").

Todavía no hay dictámenes ni recomendaciones en el corpus: todo se prueba con documentos
sintéticos, de contenido inventado (P4). El ajuste contra documentos reales es de T-043.

- `tests/fixtures/dictamen-sintetico.pdf`: un dictamen inventado de dos páginas, con
  puntos romanos (`I.`), arábigos (`1.`), decimales con punto final (`3.1.`) y sin él
  (`4.1`), un encabezado sin numerar, la firma y un pie de página repetido. Lo arma
  `build_synthetic_opinion_pdf()`, en este mismo archivo, sin bibliotecas: el archivo
  guardado tiene que ser igual, byte por byte, a lo que arma la función.
- Lecturas sintéticas armadas en cada prueba, con renglones como los del PDF.
- El anexo real de la Disp. AFIP 247/2022 (`corpus/`), para comprobar que una norma se
  sigue partiendo igual que con las reglas 3 de T-023.
"""

import hashlib
import json
from pathlib import Path

import pytest

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_PDF_TEXT,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
    read_document,
)
from evaluon.norms.splitting import RULES_VERSION, split_document

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "dictamen-sintetico.pdf"
ANNEX_247 = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"

DICTAMEN = "dictamen_legal"
RECOMENDACION = "recomendacion_auditoria"
NORM_CATEGORIES = ("regimen_especifico", "otra_normativa", "marco_nacional")


# --- El PDF sintético -------------------------------------------------------------------

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
FONT_SIZE = 11
LINE_STEP = 13  # entre renglones de un mismo párrafo
PARAGRAPH_STEP = 26  # entre párrafos
LEFT = 72
FIRST_BASELINE = 720
FOOTER_BASELINE = 40

# Cada página es una lista de párrafos; cada párrafo, una lista de renglones. Contenido
# inventado: no copia ningún dictamen real.
OPINION_PAGES = [
    [
        ["DICTAMEN JURÍDICO SINTÉTICO N° 99/2026"],
        ["Ref.: consulta de prueba sobre la garantía de mantenimiento de oferta."],
        ["I. ANTECEDENTES"],
        [
            "1. La dependencia consultante remitió un expediente de prueba para que este",
            "servicio jurídico opine sobre la garantía exigida en un pliego inventado.",
        ],
        ["2. Se acompañó una planilla con montos ficticios, que suman $ 1.000 en total."],
        ["II. ANÁLISIS"],
        ["3. Corresponde examinar el régimen aplicable al caso planteado."],
        ["3.1. La garantía se constituye en la forma prevista en el pliego."],
        [
            "3.2. El monto se calcula sobre el valor total de la oferta, según la planilla",
            "acompañada:",
        ],
    ],
    [
        ["1.000 unidades de medida figuran en la planilla adjunta, sin observaciones."],
        ["4. Sobre el plazo de mantenimiento de la oferta:"],
        ["4.1 La oferta se mantiene durante el plazo fijado en el pliego."],
        ["4.2 El plazo se prorroga en forma automática, salvo manifestación en contrario."],
        [
            "5. La consultante menciona, como antecedente, el punto",
            "2.3 de un dictamen anterior, que no se transcribe en este documento.",
        ],
        ["III. CONCLUSIÓN"],
        ["6. Por lo expuesto, este servicio jurídico no formula objeciones al proyecto."],
        ["Firmado digitalmente por Persona Sintética"],
    ],
]
FOOTER = "Dictamen sintético · Página {page} de {pages}"


def _pdf_string(text):
    """Una cadena literal de PDF en WinAnsiEncoding, con sus caracteres escapados."""
    raw = text.encode("cp1252")
    for char in (b"\\", b"(", b")"):
        raw = raw.replace(char, b"\\" + char)
    return b"(" + raw + b")"


def _content_stream(paragraphs, page_number, page_count):
    commands = [b"BT", b"/F1 %d Tf" % FONT_SIZE]
    baseline = FIRST_BASELINE
    for paragraph in paragraphs:
        for line in paragraph:
            commands.append(b"1 0 0 1 %d %d Tm %s Tj" % (LEFT, baseline, _pdf_string(line)))
            baseline -= LINE_STEP
        baseline -= PARAGRAPH_STEP - LINE_STEP
    footer = FOOTER.format(page=page_number, pages=page_count)
    commands.append(b"1 0 0 1 %d %d Tm %s Tj" % (LEFT, FOOTER_BASELINE, _pdf_string(footer)))
    commands.append(b"ET")
    return b"\n".join(commands)


def build_synthetic_opinion_pdf(pages=OPINION_PAGES):
    """Arma un PDF con texto, sin bibliotecas y siempre igual: Helvetica de 11 puntos en
    WinAnsiEncoding, un renglón por línea y más espacio entre párrafos que entre
    renglones, como el anexo de la 247/2022."""
    count = len(pages)
    page_ids = [4 + 2 * index for index in range(count)]
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % page_id for page_id in page_ids), count),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    for index, paragraphs in enumerate(pages):
        page_id = page_ids[index]
        stream = _content_stream(paragraphs, index + 1, count)
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % (PAGE_WIDTH, PAGE_HEIGHT, page_id + 1)
        )
        objects[page_id + 1] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (number, objects[number])
    xref = len(out)
    size = max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for number in range(1, size):
        out += b"%010d 00000 n \n" % offsets[number]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)


# --- Ayudas -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def opinion():
    return split_document(read_document(FIXTURE), category=DICTAMEN)


def synthetic(*paragraph_pages):
    """Una lectura sintética: cada argumento es una página, lista de párrafos de un
    renglón cada uno, separados como en el PDF sintético."""
    pages = []
    for number, paragraphs in enumerate(paragraph_pages, start=1):
        lines, top = [], 72.0
        for text in paragraphs:
            lines.append(
                Line(text=text, x0=72.0, top=top, x1=300.0, bottom=top + 11.0, origin=ORIGIN_PDF_TEXT)
            )
            top += PARAGRAPH_STEP
        pages.append(Page(number=number, width=612.0, height=792.0, status=PAGE_READ, lines=lines))
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions={"pdfplumber": "x"})


def by_key(result):
    return {unit.key: unit for unit in result.units}


def check_invariants(result):
    """Propiedades que se cumplen siempre (ADR-0004, "Cómo se prueba"): cada texto es
    igual a su recorte, el orden es creciente y la cobertura suma el total."""
    text = result.canonical_text
    for unit in result.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
    orders = [unit.order for unit in result.units]
    assert orders == sorted(orders) == list(range(1, len(orders) + 1))
    assert len({unit.key for unit in result.units}) == len(result.units)
    cover = result.report["coverage"]
    assert cover["matches"], cover
    assert cover["units"] + cover["discarded"] + cover["unlocated"] + cover["separators"] == len(text)


# --- El dictamen sintético --------------------------------------------------------------


def test_fixture_is_the_generated_synthetic_opinion():
    """REQ-003: el dictamen de prueba es sintético y reproducible: el archivo guardado es
    igual, byte por byte, al que arma `build_synthetic_opinion_pdf()`, y es chico."""
    data = FIXTURE.read_bytes()
    assert data == build_synthetic_opinion_pdf()
    assert len(data) < 5000


# (clave, número, etiqueta, ruta, unidad que la contiene, página de inicio y de fin),
# escrita a mano contra el contenido de `OPINION_PAGES`.
EXPECTED_POINTS = [
    ("punto-i", "I", "I. ANTECEDENTES", "Punto I", None, 1, 1),
    ("punto-i/punto-1", "1", "1.", "Punto I › Punto 1", "punto-i", 1, 1),
    ("punto-i/punto-2", "2", "2.", "Punto I › Punto 2", "punto-i", 1, 1),
    ("punto-ii", "II", "II. ANÁLISIS", "Punto II", None, 1, 1),
    ("punto-ii/punto-3", "3", "3.", "Punto II › Punto 3", "punto-ii", 1, 1),
    ("punto-ii/punto-3.1", "3.1", "3.1.", "Punto II › Punto 3.1", "punto-ii", 1, 1),
    ("punto-ii/punto-3.2", "3.2", "3.2.", "Punto II › Punto 3.2", "punto-ii", 1, 2),
    ("punto-ii/punto-4", "4", "4.", "Punto II › Punto 4", "punto-ii", 2, 2),
    ("punto-ii/punto-4.1", "4.1", "4.1", "Punto II › Punto 4.1", "punto-ii", 2, 2),
    ("punto-ii/punto-4.2", "4.2", "4.2", "Punto II › Punto 4.2", "punto-ii", 2, 2),
    ("punto-ii/punto-5", "5", "5.", "Punto II › Punto 5", "punto-ii", 2, 2),
    ("punto-iii", "III", "III. CONCLUSIÓN", "Punto III", None, 2, 2),
    ("punto-iii/punto-6", "6", "6.", "Punto III › Punto 6", "punto-iii", 2, 2),
]


def test_each_point_of_the_opinion_is_a_unit_located_as_in_the_document(opinion):
    """REQ-003: en un dictamen, cada punto numerado (`I.`, `1.`, `3.1.`, `4.1`) es una
    unidad `punto` con su ubicación: número, etiqueta, clave, ruta y páginas. Los puntos
    arábigos que siguen a un punto romano cuelgan de él, y su clave se arma con la
    cadena de unidades que los contienen."""
    assert {unit.unit_type for unit in opinion.units} == {"punto"}
    got = [
        (u.key, u.number, u.label, u.path, u.parent_key, u.page_start, u.page_end)
        for u in opinion.units
    ]
    assert got == EXPECTED_POINTS
    assert {unit.text_origin for unit in opinion.units} == {ORIGIN_PDF_TEXT}


def test_point_text_goes_from_its_heading_to_the_next_point(opinion):
    """REQ-003: el texto de un punto va desde su encabezado hasta el siguiente punto: un
    punto romano tiene solo su encabezado; un punto sigue en la página siguiente si no
    viene otro (3.2 se lleva el párrafo que empieza con "1.000", que no es un número de
    punto); y un número de punto en medio de un párrafo ("el punto 2.3 de un dictamen")
    no abre otro."""
    units = by_key(opinion)
    assert units["punto-i"].text == "I. ANTECEDENTES"
    assert units["punto-i/punto-1"].text == (
        "1. La dependencia consultante remitió un expediente de prueba para que este "
        "servicio jurídico opine sobre la garantía exigida en un pliego inventado."
    )
    assert units["punto-ii/punto-3.2"].text == (
        "3.2. El monto se calcula sobre el valor total de la oferta, según la planilla "
        "acompañada:\n1.000 unidades de medida figuran en la planilla adjunta, sin "
        "observaciones."
    )
    assert units["punto-ii/punto-5"].text == (
        "5. La consultante menciona, como antecedente, el punto 2.3 de un dictamen "
        "anterior, que no se transcribe en este documento."
    )
    assert units["punto-iii/punto-6"].text == (
        "6. Por lo expuesto, este servicio jurídico no formula objeciones al proyecto."
    )


def test_opinion_coverage_is_complete_and_each_text_is_its_cut(opinion):
    """REQ-003: cada texto es igual a su recorte del texto canónico y la cobertura suma
    el total: lo que está antes del primer punto (el encabezado sin numerar) y la firma
    quedan como no ubicados, a la vista; el pie de página repetido se descarta."""
    check_invariants(opinion)
    unlocated = [item["first_words"] for item in opinion.report["unlocated"]]
    assert unlocated == [
        "DICTAMEN JURÍDICO SINTÉTICO N° 99/2026 Ref.: consulta de",
        "Firmado digitalmente por Persona Sintética",
    ]
    assert [line["text"] for line in opinion.report["discarded_line_list"]] == [
        "Dictamen sintético · Página 1 de 2",
        "Dictamen sintético · Página 2 de 2",
    ]
    assert "Firmado" not in by_key(opinion)["punto-iii/punto-6"].text


def test_opinion_report_names_the_rule_and_lists_the_points(opinion):
    """REQ-003: el informe dice con qué regla se partió el documento, cuenta los puntos y
    lista cada uno con su clave."""
    assert opinion.report["rule"] == "dictamenes"
    assert opinion.report["rules_version"] == RULES_VERSION
    assert opinion.report["units"]["by_type"] == {"punto": 13}
    assert "dictámenes y recomendaciones" in opinion.report_text
    assert "13 puntos" in opinion.report_text
    assert "  punto-ii/punto-3.2 · Punto II › Punto 3.2 · 3.2. · páginas 1 a 2" in opinion.report_text
    assert "artículo" not in opinion.report_text


def test_a_recommendation_is_split_by_the_same_rule(opinion):
    """REQ-003: una recomendación de auditoría se parte con la misma regla que un
    dictamen."""
    recommendation = split_document(read_document(FIXTURE), category=RECOMENDACION)
    assert [(u.key, u.char_start, u.char_end) for u in recommendation.units] == [
        (u.key, u.char_start, u.char_end) for u in opinion.units
    ]


# --- Formas de numeración ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("I. ANTECEDENTES", "I"),
        ("IV. Conclusión del análisis.", "IV"),
        ("XII. Otro punto", "XII"),
        ("1. Texto del punto.", "1"),
        ("12. Texto del punto.", "12"),
        ("1.1. Texto del punto.", "1.1"),
        ("2.3 Texto del punto.", "2.3"),
        ("2.3. Texto del punto.", "2.3"),
        ("1.2.4. Tercer nivel.", "1.2.4"),
        ("3.", "3"),
        # No son encabezados de punto.
        ("1.000 unidades de medida.", None),
        ("12.5% del monto.", None),
        ("2 de mayo de 2026.", None),
        ("1) Primer inciso.", None),
        ("a) Primer inciso.", None),
        ("IIII. No es un número romano.", None),
        ("V.E. solicita opinión.", None),
        ("Imagen. Texto.", None),
        ("En el punto 2.3 se dijo.", None),
    ],
)
def test_point_heading_table(text, number):
    """REQ-003: tabla de encabezados de punto: romanos (`I.`), arábigos con punto
    (`1.`), decimales con y sin punto final (`1.1.`, `2.3`), y casos que no son punto
    (montos, porcentajes, fechas, incisos, abreviaturas como "V.E.")."""
    from evaluon.norms.splitting.opinions import point_heading

    heading = point_heading(text)
    assert (heading.number if heading else None) == number


def test_flat_numbering_gives_point_keys_without_container():
    """REQ-003: sin puntos romanos, los puntos cuelgan de la norma: `1.`, `2.`, `2.1.`,
    `2.2` y `2.3` dan las claves `punto-1` a `punto-2.3`, con su ruta."""
    result = split_document(
        synthetic(
            [
                "1. Primer punto.",
                "2. Segundo punto, con subpuntos:",
                "2.1. Primer subpunto.",
                "2.2 Segundo subpunto.",
                "2.3 Tercer subpunto.",
            ]
        ),
        category=DICTAMEN,
    )

    assert [(u.key, u.number, u.path, u.parent_key) for u in result.units] == [
        ("punto-1", "1", "Punto 1", None),
        ("punto-2", "2", "Punto 2", None),
        ("punto-2.1", "2.1", "Punto 2.1", None),
        ("punto-2.2", "2.2", "Punto 2.2", None),
        ("punto-2.3", "2.3", "Punto 2.3", None),
    ]
    assert by_key(result)["punto-2"].text == "2. Segundo punto, con subpuntos:"
    check_invariants(result)


def test_numbering_restarts_after_a_roman_point_without_repeating_keys():
    """REQ-003: si la numeración arábiga vuelve a empezar en cada punto romano, las
    claves no se repiten porque llevan la del punto romano que las contiene; también se
    acepta que la numeración siga de un punto romano al siguiente, y que los decimales
    salten de nivel (`1.2` a `2.1`)."""
    result = split_document(
        synthetic(
            [
                "I. PRIMERA PARTE",
                "1. Uno.",
                "1.1 Uno punto uno.",
                "1.2 Uno punto dos.",
                "2.1 Dos punto uno.",
                "II. SEGUNDA PARTE",
                "1. Uno de nuevo.",
                "2. Dos de nuevo.",
                "III. TERCERA PARTE",
                "3. Sigue la numeración.",
            ]
        ),
        category=DICTAMEN,
    )

    assert [u.key for u in result.units] == [
        "punto-i",
        "punto-i/punto-1",
        "punto-i/punto-1.1",
        "punto-i/punto-1.2",
        "punto-i/punto-2.1",
        "punto-ii",
        "punto-ii/punto-1",
        "punto-ii/punto-2",
        "punto-iii",
        "punto-iii/punto-3",
    ]
    check_invariants(result)


def test_out_of_sequence_point_stays_inside_and_is_reported():
    """REQ-003: control de secuencia, como en los artículos. Una enumeración propia
    dentro de un punto (un "1." después del punto 2) no abre un punto: queda dentro y el
    informe lo señala. Un salto hacia adelante dentro del margen se acepta y se informa
    el número que falta."""
    result = split_document(
        synthetic(
            [
                "1. Primer punto.",
                "2. Segundo punto, que enumera:",
                "1. una condición;",
                "2. otra condición.",
                "4. Cuarto punto, sin tercero.",
                "V. E. ha solicitado opinión sobre este punto.",
            ]
        ),
        category=DICTAMEN,
    )

    units = by_key(result)
    assert list(units) == ["punto-1", "punto-2", "punto-4"]
    assert units["punto-2"].text == (
        "2. Segundo punto, que enumera:\n1. una condición;\n2. otra condición."
    )
    assert units["punto-4"].text.endswith("\nV. E. ha solicitado opinión sobre este punto.")
    [sequence] = result.report["sequence"]
    assert sequence["gaps"] == ["3"]
    assert [(item["number"], item["inside"]) for item in sequence["not_accepted"]] == [
        ("1", "punto-2"),
        ("2", "punto-2"),
        ("V", "punto-4"),
    ]
    assert "encabezado del punto 1 fuera de secuencia" in result.report_text
    check_invariants(result)


def test_arabic_jump_beyond_the_margin_does_not_open_a_point():
    """REQ-003: un salto arábigo mayor que el margen ("10." después de "2.") no abre un
    punto: queda dentro del punto abierto y se informa; el "3." que sigue se acepta."""
    result = split_document(
        synthetic(["1. Uno.", "2. Dos.", "10. Diez, fuera de secuencia.", "3. Tres."]),
        category=DICTAMEN,
    )

    units = by_key(result)
    assert list(units) == ["punto-1", "punto-2", "punto-3"]
    assert units["punto-2"].text == "2. Dos.\n10. Diez, fuera de secuencia."
    [sequence] = result.report["sequence"]
    assert sequence["gaps"] == []
    assert [(item["number"], item["inside"]) for item in sequence["not_accepted"]] == [
        ("10", "punto-2")
    ]
    check_invariants(result)


# Carátula GDE sintética: membrete, "Número:" y "Referencia:" (`partition._cover_end`).
GDE_COVER = [
    "Organismo Sintético de Prueba",
    "Número: IF-2026-00000001-APN-SINTETICO",
    "Referencia: Documento sintético de prueba",
]


def test_numbered_opinion_with_gde_cover_discards_the_cover():
    """REQ-003: en un dictamen numerado, la carátula GDE se descarta, como en las
    normas, y no queda como no ubicada."""
    result = split_document(synthetic(GDE_COVER + ["1. Uno.", "2. Dos."]), category=DICTAMEN)

    assert [u.key for u in result.units] == ["punto-1", "punto-2"]
    assert result.report["unlocated"] == []
    assert [(item["reason"], item["first_words"]) for item in result.report["discarded"]] == [
        ("caratula", "Organismo Sintético de Prueba Número: IF-2026-00000001-APN-SINTETICO Referencia: Documento")
    ]
    check_invariants(result)


@pytest.mark.parametrize("category", [DICTAMEN, RECOMENDACION])
def test_unnumbered_document_with_gde_cover_starts_at_paragraph_one(category):
    """REQ-003: en un documento sin numeración con carátula GDE, la carátula se descarta
    y la numeración de los párrafos empieza en `parrafo-1` con el primer párrafo que la
    sigue."""
    result = split_document(
        synthetic(GDE_COVER + ["Primer párrafo sintético.", "Segundo párrafo sintético."]),
        category=category,
    )

    assert [(u.key, u.text) for u in result.units] == [
        ("parrafo-1", "Primer párrafo sintético."),
        ("parrafo-2", "Segundo párrafo sintético."),
    ]
    assert result.report["unlocated"] == []
    assert [item["reason"] for item in result.report["discarded"]] == ["caratula"]
    check_invariants(result)


# --- Documentos sin numeración ----------------------------------------------------------


def test_unnumbered_document_is_split_into_numbered_paragraphs():
    """REQ-003: un documento sin numeración se parte en párrafos, unidades `parrafo`
    numeradas por orden (`parrafo-1`, `parrafo-2`...), con su ubicación; la firma no es
    un párrafo y queda como no ubicada. La cobertura suma el total."""
    result = split_document(
        synthetic(
            [
                "Observación sintética sobre el registro de garantías.",
                "Se verificó que las garantías no se registran en tiempo.",
            ],
            [
                "Se recomienda registrar cada garantía al recibirla.",
                "Firmado digitalmente por Auditor Sintético",
            ],
        ),
        category=RECOMENDACION,
    )

    assert [
        (u.unit_type, u.key, u.number, u.label, u.path, u.parent_key, u.page_start)
        for u in result.units
    ] == [
        ("parrafo", "parrafo-1", "1", "Párrafo 1", "Párrafo 1", None, 1),
        ("parrafo", "parrafo-2", "2", "Párrafo 2", "Párrafo 2", None, 1),
        ("parrafo", "parrafo-3", "3", "Párrafo 3", "Párrafo 3", None, 2),
    ]
    assert by_key(result)["parrafo-3"].text == "Se recomienda registrar cada garantía al recibirla."
    assert [item["first_words"] for item in result.report["unlocated"]] == [
        "Firmado digitalmente por Auditor Sintético"
    ]
    assert result.report["units"]["by_type"] == {"parrafo": 3}
    assert result.report["sequence"] == []
    check_invariants(result)


def test_a_single_numbered_paragraph_does_not_make_a_numbered_document():
    """REQ-003: un solo párrafo que empieza con un número no alcanza para tomar el
    documento como numerado: se parte en párrafos, y el párrafo número 12 es
    `parrafo-12`."""
    paragraphs = [f"Párrafo sintético número {n}." for n in range(1, 12)]
    paragraphs.append("1. Un párrafo que empieza con un número.")
    result = split_document(synthetic(paragraphs), category=DICTAMEN)

    assert [u.key for u in result.units] == [f"parrafo-{n}" for n in range(1, 13)]
    assert by_key(result)["parrafo-12"].text == "1. Un párrafo que empieza con un número."
    check_invariants(result)


# --- La regla se elige por la categoría -------------------------------------------------

NORM_PARAGRAPHS = [
    "ARTÍCULO 1°.- OBJETO. Texto del uno.",
    "1. Primer punto del artículo.",
    "2. Segundo punto del artículo.",
    "ARTÍCULO 2°.- VIGENCIA. Texto del dos.",
]


def test_rule_is_chosen_by_the_category_of_the_document():
    """REQ-003, REQ-017: la regla se elige por la categoría. Las tres categorías de
    normas, y la omisión de la categoría, parten en artículos; dictamen legal y
    recomendación de auditoría, en puntos."""
    for category in (None,) + NORM_CATEGORIES:
        result = split_document(synthetic(NORM_PARAGRAPHS), category=category)
        assert [u.key for u in result.units] == ["art-1", "art-1/inc-1", "art-1/inc-2", "art-2"]
        assert result.report["rule"] == "normas"
    for category in (DICTAMEN, RECOMENDACION):
        result = split_document(synthetic(NORM_PARAGRAPHS), category=category)
        assert [u.key for u in result.units] == ["punto-1", "punto-2"]
        assert result.report["rule"] == "dictamenes"
        check_invariants(result)


def test_a_norm_is_split_the_same_with_or_without_its_category():
    """REQ-003: elegir la regla por la categoría no cambia la partición de una norma:
    la misma lectura da las mismas unidades sin categoría (como antes de T-024) y con
    cualquiera de las tres categorías de normas, también con el dictamen sintético."""
    reading = read_document(FIXTURE)
    before = split_document(reading)
    assert not [u for u in before.units if u.unit_type in ("punto", "parrafo")]
    for category in NORM_CATEGORIES:
        result = split_document(reading, category=category)
        assert result.canonical_text == before.canonical_text
        assert [vars(u) for u in result.units] == [vars(u) for u in before.units]


def test_unknown_category_is_rejected():
    """REQ-003, REQ-017: una categoría que no es ninguna de las cinco no elige regla:
    se rechaza."""
    with pytest.raises(ValueError, match="categoría"):
        split_document(synthetic(NORM_PARAGRAPHS), category="dictamen")


def test_opinion_with_an_annex_part_is_rejected():
    """REQ-003: dictámenes y recomendaciones se parten como documento único (`cuerpo`):
    no hay todavía reglas para un dictamen en más de un archivo."""
    with pytest.raises(ValueError, match="parte"):
        split_document(synthetic(NORM_PARAGRAPHS), part="anexo", category=DICTAMEN)


def test_categories_of_the_rule_are_those_of_the_model():
    """REQ-003, REQ-017: las categorías que eligen regla son las cinco del modelo, sin
    que falte ni sobre ninguna."""
    from evaluon.norms.models import Category
    from evaluon.norms.splitting import NORM_RULE_CATEGORIES, OPINION_RULE_CATEGORIES

    assert set(OPINION_RULE_CATEGORIES) == {DICTAMEN, RECOMENDACION}
    assert set(NORM_RULE_CATEGORIES) | set(OPINION_RULE_CATEGORIES) == set(Category.values)


# --- El anexo real de la 247/2022 no cambia ---------------------------------------------

# Con las reglas 3 de T-023, antes de T-024: 335 unidades, la huella del texto canónico
# y la huella de la lista de unidades (clave, tipo, posición, página, etiqueta y ruta).
ANNEX_UNITS = 335
ANNEX_CANONICAL_SHA256 = "e0c272ac7496021324244f552e5e0dfd7cda45cffe99be61263e4d2be6f7addb"
ANNEX_UNITS_SHA256 = "495f7b631d0112bcd8dc1f76c61928af1555d9cf76642386816b1ef8b48842ce"


def test_real_annex_of_247_2022_is_split_as_before():
    """REQ-003: el anexo real de la Disp. AFIP 247/2022, como régimen específico, da las
    mismas 335 unidades, el mismo texto canónico y las mismas claves, posiciones,
    páginas, etiquetas y rutas que con las reglas de T-023."""
    reading = read_document(ANNEX_247)
    for category in (None, "regimen_especifico"):
        result = split_document(reading, part="anexo", category=category)
        assert len(result.units) == ANNEX_UNITS
        assert result.canonical_sha256 == ANNEX_CANONICAL_SHA256
        units = [
            (u.key, u.unit_type, u.char_start, u.char_end, u.page_start, u.label, u.path)
            for u in result.units
        ]
        assert hashlib.sha256(json.dumps(units).encode()).hexdigest() == ANNEX_UNITS_SHA256
        assert result.report["coverage"]["matches"]
