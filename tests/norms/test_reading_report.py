"""Informe de lectura completo (T-025; ADR-0004, "Qué contiene el informe de lectura";
plan 001, "Ingesta").

El informe tiene las diez partes del ADR-0004, en datos (`norms_reading.report`) y en
texto legible (`norms_reading.report_text`), y empieza por lo que requiere atención:

1. Requiere atención. 2. Documento. 3. Páginas. 4. Unidades reconocidas. 5. No ubicado.
6. Descartado. 7. Uniones de palabras cortadas. 8. Reconocimiento sobre imagen.
9. Control de cobertura. 10. Posibles duplicados (los completa la carga, T-026).

Las lecturas son sintéticas y propias de cada prueba (P4), salvo la del anexo real de la
Disp. AFIP 247/2022, que es pública y está en `corpus/normativa/`.
"""

import json
from pathlib import Path

import pytest

from evaluon.norms.reading import (
    FORMAT_HTML,
    FORMAT_PDF,
    ORIGIN_OCR,
    ORIGIN_PDF_TEXT,
    ORIGIN_WEB,
    PAGE_BLANK,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_NOT_READ,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
    Word,
    read_document,
)
from evaluon.norms.splitting import Unit, split_document
from evaluon.norms.splitting.report import attention_items, coverage, report_text

REPO = Path(__file__).resolve().parents[2]
ANNEX_247 = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"

HEIGHT = 12.0
NEW_PARAGRAPH = 25.5
TOOLS = {"pdfplumber": "0.11.10", "pypdfium2": "5.13.0"}


# --- Lecturas sintéticas ----------------------------------------------------------------


def line(text, top, origin=ORIGIN_PDF_TEXT, confidences=None, discarded=""):
    """Un renglón. Con `confidences`, es de reconocimiento: una confianza por palabra."""
    words = []
    confidence = None
    if confidences is not None:
        words = [Word(word, value) for word, value in zip(text.split(), confidences, strict=True)]
        confidence = round(sum(confidences) / len(confidences), 2)
    return Line(
        text=text,
        x0=70.0,
        top=top,
        x1=300.0,
        bottom=top + HEIGHT,
        origin=origin,
        confidence=confidence,
        words=words,
        discarded=discarded,
    )


def page(number, *texts, status=PAGE_READ, origin=None, confidence=None):
    """Una página de PDF con texto: un párrafo por renglón."""
    lines = [line(text, 100.0 + i * NEW_PARAGRAPH) for i, text in enumerate(texts)]
    return Page(
        number=number,
        width=612.0,
        height=792.0,
        status=status,
        lines=lines,
        origin=origin,
        confidence=confidence,
    )


def ocr_page(number, *rows, status=PAGE_READ):
    """Una página reconocida: cada fila es (texto, confianzas de sus palabras)."""
    lines = [
        line(text, 100.0 + i * NEW_PARAGRAPH, ORIGIN_OCR, confidences)
        for i, (text, confidences) in enumerate(rows)
    ]
    words = [value for _, confidences in rows for value in confidences]
    return Page(
        number=number,
        width=612.0,
        height=792.0,
        status=status,
        lines=lines,
        origin=ORIGIN_OCR,
        confidence=round(sum(words) / len(words), 2),
    )


def unreadable_ocr_page(number, confidence):
    """Una página reconocida que salió ilegible: no aporta líneas, pero conserva su
    origen y su confianza (T-025)."""
    return Page(
        number=number,
        width=612.0,
        height=792.0,
        status=PAGE_ILLEGIBLE,
        lines=[],
        origin=ORIGIN_OCR,
        confidence=confidence,
    )


def pdf(*pages):
    return DocumentReading(file_format=FORMAT_PDF, pages=list(pages), tool_versions=dict(TOOLS))


def kinds(report):
    return [item["kind"] for item in report["attention"]]


def attention_text(result):
    """El bloque "Requiere atención" del texto: desde su encabezado hasta la línea en
    blanco que lo cierra."""
    text = result.report_text
    start = text.index("Requiere atención:")
    return text[start : text.index("\n\n", start)]


def item(report, kind):
    [found] = [entry for entry in report["attention"] if entry["kind"] == kind]
    return found


# --- Páginas: ilegible, casi sin texto, sin texto, en blanco (REQ-004) ------------------


def test_an_illegible_page_is_pointed_out_and_no_other():
    """REQ-004: dada una lectura con una página ilegible, el informe señala esa página y
    ninguna otra: en la lista de ilegibles, en "Requiere atención" y en las no leídas."""
    result = split_document(
        pdf(
            page(1, "ARTÍCULO 1°.- UNO. Texto del primero."),
            unreadable_ocr_page(2, confidence=23.4),
            page(3, "ARTÍCULO 2°.- DOS. Texto del segundo."),
        ),
        part="cuerpo",
    )
    report = result.report

    summary = report["page_summary"]
    assert summary["illegible"] == [2]
    assert summary["almost_empty"] == []
    assert summary["doubtful"] == []
    assert summary["without_text"] == []
    assert summary["blank"] == []
    assert report["pages"] == {"total": 3, "not_read": [2]}
    assert [p["state"] for p in report["page_list"]] == ["legible", "ilegible", "legible"]
    assert report["page_list"][1] == {
        "number": 2,
        "origin": ORIGIN_OCR,
        "status": PAGE_ILLEGIBLE,
        "state": "ilegible",
        "chars": 0,
        "confidence": 23.4,
    }
    page_items = [k for k in kinds(report) if k.endswith("pages") or k == "pages_without_text"]
    assert page_items == ["illegible_pages"]
    assert item(report, "illegible_pages")["pages"] == [2]
    block = attention_text(result)
    assert "Páginas ilegibles" in block and "página 2" in block
    assert "página 1" not in block and "página 3" not in block
    assert "Ilegibles: 2." in result.report_text


def test_almost_empty_is_told_apart_from_illegible():
    """REQ-004: una página reconocida con menos de tres palabras sale ilegible aunque su
    confianza sea alta (por ejemplo, una carátula que dice solo "ANEXO"). El informe la
    da como "casi sin texto", no como ilegible, y conserva su confianza; una página de
    confianza baja sigue siendo ilegible. Las dos van a "Requiere atención"."""
    result = split_document(
        pdf(
            unreadable_ocr_page(1, confidence=96.0),
            page(2, "ARTÍCULO 1°.- UNO. Texto."),
            unreadable_ocr_page(3, confidence=31.0),
            unreadable_ocr_page(4, confidence=None),
        ),
        part="cuerpo",
    )
    report = result.report

    assert report["page_summary"]["illegible"] == [3]
    assert report["page_summary"]["almost_empty"] == [1, 4]
    states = {p["number"]: p["state"] for p in report["page_list"]}
    assert states == {1: "casi_sin_texto", 2: "legible", 3: "ilegible", 4: "casi_sin_texto"}
    assert report["page_list"][0]["confidence"] == 96.0
    assert item(report, "illegible_pages")["pages"] == [3]
    assert item(report, "almost_empty_pages")["pages"] == [1, 4]
    assert "casi sin texto" in attention_text(result)
    assert "Página 1: reconocimiento sobre imagen, casi sin texto" in result.report_text
    assert "Página 3: reconocimiento sobre imagen, ilegible" in result.report_text


def test_a_page_without_text_is_not_confused_with_an_illegible_one():
    """REQ-004: una página de un PDF de la que no se obtuvo texto (como la 45 del anexo
    de la 247/2022, que trae solo la firma digital) se informa como "sin texto", no como
    ilegible: no se intentó reconocer, así que no es una página que no se pudo leer. Va a
    "Requiere atención" para que se compare con el original."""
    result = split_document(
        pdf(
            page(1, "ARTÍCULO 1°.- UNO. Texto."),
            Page(number=2, width=612.0, height=792.0, status=PAGE_NOT_READ, lines=[]),
        ),
        part="cuerpo",
    )
    report = result.report

    assert report["page_summary"]["without_text"] == [2]
    assert report["page_summary"]["illegible"] == []
    assert report["page_list"][1]["state"] == "sin_texto"
    assert report["page_list"][1]["origin"] is None
    assert "illegible_pages" not in kinds(report)
    assert item(report, "pages_without_text")["pages"] == [2]
    block = attention_text(result)
    assert "sin texto" in block and "página 2" in block
    assert "ilegible" not in block
    assert "Página 2: sin texto" in result.report_text


def test_a_blank_page_is_reported_without_counting_as_illegible():
    """REQ-004: una página en blanco se informa (en la lista de páginas y en "Requiere
    atención") y no cuenta como ilegible ni como no leída (ADR-0004, "Cómo se lee")."""
    result = split_document(
        pdf(
            page(1, "ARTÍCULO 1°.- UNO. Texto."),
            Page(number=2, width=612.0, height=792.0, status=PAGE_BLANK, lines=[]),
        ),
        part="cuerpo",
    )
    report = result.report

    assert report["page_summary"]["blank"] == [2]
    assert report["page_summary"]["illegible"] == []
    assert report["pages"]["not_read"] == []
    assert report["page_list"][1]["state"] == "en_blanco"
    assert item(report, "blank_pages")["pages"] == [2]
    assert "en blanco" in attention_text(result)


def test_a_doubtful_page_goes_to_attention_with_its_confidence():
    """REQ-004, REQ-015: una página reconocida con confianza media queda dudosa: aporta su
    texto y el informe la señala con su confianza."""
    result = split_document(
        pdf(ocr_page(1, ("ARTÍCULO 1°.- UNO. Texto dudoso.", [70, 60, 55, 65, 50]), status=PAGE_DOUBTFUL)),
        part="cuerpo",
    )
    report = result.report

    assert report["page_summary"]["doubtful"] == [1]
    assert report["page_list"][0]["state"] == "dudosa"
    assert report["page_list"][0]["confidence"] == 60.0
    assert item(report, "doubtful_pages")["pages"] == [1]
    assert "Página 1: reconocimiento sobre imagen, dudosa" in result.report_text
    assert "confianza promedio 60" in result.report_text


def test_a_web_page_without_text_is_shown_without_a_page_number():
    """REQ-004, REQ-015: una página web no tiene número. Si no se obtuvo texto de ella
    (`pages_not_read == [None]`), el informe la nombra como la página web, nunca como
    "None"."""
    reading = DocumentReading(
        file_format=FORMAT_HTML,
        pages=[
            Page(
                number=None,
                width=None,
                height=None,
                status=PAGE_NOT_READ,
                lines=[
                    Line("var x = 1;", None, None, None, None, ORIGIN_WEB, discarded="script de la página"),
                ],
            )
        ],
        tool_versions={"beautifulsoup4": "4.13.4"},
    )

    result = split_document(reading, part="cuerpo")

    assert result.report["pages"]["not_read"] == [None]
    assert result.report["page_summary"]["without_text"] == [None]
    assert "None" not in result.report_text
    assert "Páginas no leídas: la página web, sin número." in result.report_text
    assert "la página web" in attention_text(result)


def test_pages_show_origin_state_characters_and_confidence():
    """REQ-004, REQ-015: por cada página, el informe da su origen, su estado, la cantidad
    de caracteres que aportó al texto canónico y, si hubo reconocimiento, su confianza
    promedio."""
    result = split_document(
        pdf(
            page(1, "ARTÍCULO 1°.- UNO. Texto."),
            ocr_page(2, ("ARTÍCULO 2°.- DOS. Leído.", [90, 92, 96, 98])),
        ),
        part="cuerpo",
    )

    assert result.report["page_list"] == [
        {
            "number": 1,
            "origin": ORIGIN_PDF_TEXT,
            "status": PAGE_READ,
            "state": "legible",
            "chars": len("ARTÍCULO 1°.- UNO. Texto."),
            "confidence": None,
        },
        {
            "number": 2,
            "origin": ORIGIN_OCR,
            "status": PAGE_READ,
            "state": "legible",
            "chars": len("ARTÍCULO 2°.- DOS. Leído."),
            "confidence": 94.0,
        },
    ]
    assert "Página 1: texto del PDF, legible, 25 caracteres." in result.report_text
    assert (
        "Página 2: reconocimiento sobre imagen, legible, 25 caracteres, confianza promedio 94."
        in result.report_text
    )


# --- Documento vacío (REQ-004) -----------------------------------------------------------


@pytest.mark.parametrize("part", ["cuerpo", "anexo"])
def test_a_document_without_units_is_flagged_first(part):
    """REQ-004: un PDF con una sola página en blanco se incorpora sin unidades con texto
    (con la parte `anexo` queda solo su unidad raíz, vacía). El informe lo advierte en
    primer lugar en "Requiere atención", para que no se valide una norma vacía."""
    result = split_document(
        pdf(Page(number=1, width=612.0, height=792.0, status=PAGE_NOT_READ, lines=[])),
        part=part,
    )

    assert kinds(result.report)[0] == "empty_document"
    assert "ninguna unidad con texto" in attention_text(result)


def test_a_document_with_units_is_not_flagged_as_empty():
    """REQ-004: un documento con unidades no lleva el aviso de documento vacío."""
    result = split_document(pdf(page(1, "ARTÍCULO 1°.- UNO. Texto.")), part="cuerpo")

    assert "empty_document" not in kinds(result.report)


# --- Unidades: cláusula, cuenta esperada y secuencia (REQ-004) --------------------------


def clause_reading():
    return pdf(
        page(
            1,
            "ARTÍCULO 1°.- UNO. Texto.",
            "ARTÍCULO 2°.- DOS. Texto.",
            "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES",
            "Mientras tanto rige lo anterior.",
        )
    )


def test_a_clause_after_the_last_article_is_counted_listed_and_located():
    """REQ-004, REQ-003: una cláusula transitoria después del último artículo se cuenta
    entre las unidades reconocidas como un tipo más, se lista con su clave, no queda como
    no ubicada y no entra en el control de saltos de los artículos."""
    result = split_document(clause_reading(), part="anexo")
    report = result.report

    assert report["units"]["by_type"]["clausula"] == 1
    [container] = report["units"]["containers"]
    assert container["by_type"] == {"articulo": 2, "clausula": 1}
    assert container["missing"] == []
    assert report["sequence"][0]["gaps"] == []
    assert report["unlocated"] == []
    assert "anexo/clausula-transitoria" in [u["key"] for u in report["unit_list"]]
    assert "Anexo: 2 artículos y 1 cláusula; artículos del 1 al 2." in result.report_text
    assert "  anexo/clausula-transitoria · Anexo › Cláusula transitoria" in result.report_text
    assert "unlocated" not in kinds(report)
    assert "expected_count" not in kinds(report)


def test_the_expected_count_from_the_index_is_compared_with_the_recognized_one():
    """REQ-004: si el documento trae un índice, la cuenta esperada de artículos sale de
    él; si se reconocieron menos (por ejemplo, porque se perdió el último encabezado), el
    informe muestra las dos cuentas y los números que faltan en "Requiere atención"."""
    result = split_document(
        pdf(
            page(
                1,
                "ÍNDICE:",
                "ARTÍCULO 1º.- OBJETO",
                "ARTÍCULO 2º.- ÁMBITO",
                "ARTÍCULO 3º.- PRINCIPIOS",
                "ARTÍCULO 4º.- CONTRATOS",
                "ARTÍCULO 1°.- OBJETO. Texto.",
                "ARTÍCULO 2°.- ÁMBITO. Texto.",
                "ARTÍCULO 3°.- PRINCIPIOS. Texto.",
            )
        ),
        part="anexo",
    )
    report = result.report

    [container] = report["units"]["containers"]
    assert container["expected"] == 4
    assert container["expected_from"] == "indice"
    assert container["recognized"] == 3
    assert container["missing"] == ["4"]
    found = item(report, "expected_count")
    assert found["container"] == "Anexo"
    block = attention_text(result)
    assert "se esperaban 4 artículos según el índice y se reconocieron 3" in block
    assert "falta el 4" in block


def test_without_an_index_the_expected_count_follows_the_numbering():
    """REQ-004: sin índice, la cuenta esperada es la del último número reconocido; un
    salto en la numeración la deja por encima de la reconocida y va a "Requiere
    atención", junto con el salto."""
    result = split_document(
        pdf(
            page(
                1,
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- DOS. Texto.",
                "ARTÍCULO 4°.- CUATRO. Texto.",
            )
        ),
        part="cuerpo",
    )
    report = result.report

    [container] = report["units"]["containers"]
    assert (container["expected"], container["expected_from"], container["recognized"]) == (
        4,
        "numeracion",
        3,
    )
    assert container["missing"] == ["3"]
    assert "expected_count" in kinds(report)
    assert "sequence_gaps" in kinds(report)
    assert "se esperaban 4 artículos según la numeración y se reconocieron 3" in attention_text(result)


def test_a_repeated_heading_goes_to_attention():
    """REQ-004: un encabezado de artículo que se repite no se acepta: queda dentro de la
    unidad abierta y el informe lo señala en "Requiere atención"."""
    result = split_document(
        pdf(
            page(
                1,
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- DOS. Texto.",
                "ARTÍCULO 2°.- DOS. Otra vez.",
                "ARTÍCULO 3°.- TRES. Texto.",
            )
        ),
        part="cuerpo",
    )

    found = item(result.report, "not_accepted")
    assert "art-2" in found["text"]
    assert "fuera de secuencia" in attention_text(result)


# --- Avisos de la partición en "Requiere atención" (T-023, T-024) -----------------------


def test_partition_warnings_go_to_attention():
    """REQ-004: los avisos de la partición van a "Requiere atención": párrafos en
    mayúsculas dentro de una unidad, párrafos después del último inciso, tramos no
    ubicados y líneas descartadas como encabezado o pie de página."""
    pages = []
    for number, texts in enumerate(
        (
            [
                "Texto suelto antes del primer artículo.",
                "ARTÍCULO 1°.- UNO. Son:",
                "a) Primero.",
                "b) Segundo.",
                "Párrafo que sigue al último inciso.",
            ],
            ["ARTÍCULO 2°.- DOS. Texto.", "DE LAS GARANTÍAS EN GENERAL", "Más texto."],
        ),
        start=1,
    ):
        p = page(number, *texts)
        p.lines.insert(0, line(f"Boletín Oficial N° 3500{number}", 20.0))
        pages.append(p)
    result = split_document(pdf(*pages), part="cuerpo")
    report = result.report

    assert set(kinds(report)) >= {
        "unlocated",
        "uppercase_in_units",
        "after_last_inciso",
        "discarded_lines",
    }
    block = attention_text(result)
    assert "art-1/inc-b" in block
    assert "art-2" in block
    assert "2 líneas descartadas" in block


def test_doubtful_ocr_headings_go_to_attention():
    """REQ-004, REQ-015: un encabezado leído por reconocimiento con el número dudoso y
    aceptado por la secuencia va a "Requiere atención", con su clave y su etiqueta."""
    result = split_document(
        pdf(
            ocr_page(
                1,
                ("ARTÍCULO 1”.- UNO. Texto.", [90] * 4),
                ("ARTÍCULO 2*.- DOS. Texto.", [90] * 4),
                ("ARTÍCULO $”.- TRES. Texto.", [40, 41, 90, 90]),
                ("ARTÍCULO 4.- CUATRO. Texto.", [90] * 4),
            )
        ),
        part="cuerpo",
    )

    found = item(result.report, "doubtful_headings")
    assert "art-3" in found["text"]
    assert "ARTÍCULO $”.- TRES" in attention_text(result)


def test_opinion_attention_does_not_speak_of_articles():
    """REQ-004: en un dictamen la secuencia es de puntos: los avisos de "Requiere
    atención" no hablan de artículos."""
    result = split_document(
        pdf(page(1, "Encabezado sin numerar.", "1. Uno.", "2. Dos.", "4. Cuatro.")),
        part="cuerpo",
        category="dictamen_legal",
    )

    assert "artículo" not in result.report_text
    assert result.report["units"]["containers"] == []


# --- Descartado: un ejemplo de cada forma (REQ-004) -------------------------------------


def test_discarded_lines_are_listed_with_one_example_of_each_form():
    """REQ-004: el informe dice cuántas líneas se descartaron y da un ejemplo de cada
    forma (ADR-0004, parte 6): el encabezado repetido, el pie con el número de página y
    la dirección que agrega el navegador, cada uno con su cantidad y su página."""
    pages = []
    for number in (1, 2, 3):
        p = page(number, f"ARTÍCULO {number}°.- TEXTO. Contenido.")
        p.lines.insert(0, line(f"Boletín Oficial N° 3500{number}", 20.0))
        p.lines.append(line(f"Página {number} de 3", 760.0))
        if number == 2:
            p.lines.append(line("https://www.boletinoficial.gob.ar/aviso/1", 775.0))
        pages.append(p)

    result = split_document(pdf(*pages), part="cuerpo")
    report = result.report

    assert report["discarded_lines"] == 7
    assert report["discarded_line_forms"] == [
        {
            "reason": "encabezado_o_pie",
            "form": "Boletín Oficial N° #",
            "count": 3,
            "page": 1,
            "example": "Boletín Oficial N° 35001",
        },
        {
            "reason": "encabezado_o_pie",
            "form": "Página # de #",
            "count": 3,
            "page": 1,
            "example": "Página 1 de 3",
        },
        {
            "reason": "forma_conocida",
            "form": "https://www.boletinoficial.gob.ar/aviso/#",
            "count": 1,
            "page": 2,
            "example": "https://www.boletinoficial.gob.ar/aviso/1",
        },
    ]
    text = result.report_text
    assert "Líneas descartadas en la lectura: 7." in text
    assert "Encabezado o pie de página repetido, 3 líneas, por ejemplo en la página 1: Boletín Oficial N° 35001" in text
    assert "Forma conocida de encabezado o pie, 1 línea, por ejemplo en la página 2: https://www.boletinoficial.gob.ar/aviso/1" in text


def test_web_discarded_lines_have_their_reason_and_no_page():
    """REQ-004, REQ-015: en una página web lo descartado (scripts, navegación del sitio)
    se lista con su motivo y un ejemplo, sin número de página."""
    reading = DocumentReading(
        file_format=FORMAT_HTML,
        pages=[
            Page(
                number=None,
                width=None,
                height=None,
                status=PAGE_READ,
                lines=[
                    Line("Inicio", None, None, None, None, ORIGIN_WEB, discarded="navegación de Infoleg"),
                    Line("ARTÍCULO 1°.- Texto.", None, None, None, None, ORIGIN_WEB),
                ],
            )
        ],
        tool_versions={},
    )

    result = split_document(reading, part="cuerpo")

    assert result.report["discarded_line_forms"] == [
        {"reason": "navegación de Infoleg", "form": "Inicio", "count": 1, "page": None, "example": "Inicio"}
    ]
    assert "Navegación de Infoleg, 1 línea, por ejemplo en la página web: Inicio" in result.report_text


# --- Reconocimiento sobre imagen (REQ-015) ----------------------------------------------


def mixed_reading():
    return pdf(
        page(1, "ARTÍCULO 1°.- UNO. Texto del PDF."),
        ocr_page(
            2,
            ("ARTÍCULO 2°.- DOS. Son:", [90, 60, 95, 99]),
            ("a) primero leído.", [88, 41.5, 97]),
        ),
    )


def test_ocr_units_carry_their_origin_and_confidence():
    """REQ-015: una unidad con alguna línea de reconocimiento tiene origen `ocr` y su
    confianza mínima y promedio, calculadas sobre las palabras de sus líneas; una unidad
    del texto del PDF no tiene confianza."""
    result = split_document(mixed_reading(), part="cuerpo")
    units = {unit.key: unit for unit in result.units}

    assert units["art-1"].text_origin == ORIGIN_PDF_TEXT
    assert (units["art-1"].ocr_confidence_min, units["art-1"].ocr_confidence_avg) == (None, None)
    assert units["art-2"].text_origin == ORIGIN_OCR
    assert units["art-2"].ocr_confidence_min == 41.5
    assert units["art-2"].ocr_confidence_avg == round((90 + 60 + 95 + 99 + 88 + 41.5 + 97) / 7, 2)
    assert units["art-2/inc-a"].text_origin == ORIGIN_OCR
    assert (units["art-2/inc-a"].ocr_confidence_min, units["art-2/inc-a"].ocr_confidence_avg) == (
        41.5,
        round((88 + 41.5 + 97) / 3, 2),
    )


def test_the_report_says_which_units_come_from_recognition():
    """REQ-015: el informe dice cuántas unidades tienen texto reconocido sobre imagen, lo
    señala en "Requiere atención" y da las palabras de menor confianza con su página, para
    compararlas con el original."""
    result = split_document(mixed_reading(), part="cuerpo")
    report = result.report

    assert report["ocr"]["units"] == 2
    assert report["ocr"]["lowest_words"][:3] == [
        {"page": 2, "word": "primero", "confidence": 41.5},
        {"page": 2, "word": "2°.-", "confidence": 60.0},
        {"page": 2, "word": "a)", "confidence": 88.0},
    ]
    assert "ocr" in kinds(report)
    assert "2 unidades" in item(report, "ocr")["text"]
    text = result.report_text
    assert "Reconocimiento sobre imagen: 2 unidades de 3 tienen texto reconocido sobre imagen." in text
    assert "  - página 2: primero (confianza 41,5)" in text


def test_lowest_confidence_words_come_only_from_units():
    """REQ-015: las palabras de menor confianza son las del texto que entra en las
    unidades, que es el que se cita. Las del índice, la carátula o un tramo sin ubicar,
    que no se citan, no las tapan (esos tramos ya se listan en su parte)."""
    result = split_document(
        pdf(
            ocr_page(
                1,
                ("Logo ilegible arriba.", [5, 10, 15]),
                ("ARTÍCULO 1°.- UNO. Texto claro.", [90, 91, 92, 93, 94]),
            )
        ),
        part="cuerpo",
    )
    report = result.report

    assert [u["first_words"] for u in report["unlocated"]] == ["Logo ilegible arriba."]
    assert [w["word"] for w in report["ocr"]["lowest_words"]] == [
        "ARTÍCULO",
        "1°.-",
        "UNO.",
        "Texto",
        "claro.",
    ]
    assert report["ocr"]["words"] == 5


def test_a_reading_without_recognition_says_so():
    """REQ-015: sin reconocimiento, el informe lo dice y no lleva el aviso."""
    result = split_document(pdf(page(1, "ARTÍCULO 1°.- UNO. Texto.")), part="cuerpo")

    assert result.report["ocr"] == {"units": 0, "words": 0, "lowest_words": []}
    assert "ocr" not in kinds(result.report)
    assert "Reconocimiento sobre imagen: ninguna unidad." in result.report_text


# --- Control de cobertura (REQ-004) -----------------------------------------------------


def unit(start, end, unit_type="articulo"):
    return Unit(
        unit_type=unit_type,
        number="1",
        label="",
        key=f"u-{start}",
        path="",
        order=0,
        page_start=None,
        page_end=None,
        char_start=start,
        char_end=end,
        text="",
        text_origin=ORIGIN_PDF_TEXT,
    )


def test_coverage_detects_a_hole():
    """REQ-004 (test negativo del control de cobertura): texto que no quedó en ninguna
    unidad ni tramo es un hueco: la suma no coincide y se dice dónde está."""
    text = "x" * 20

    result = coverage(text, [unit(0, 8)], [("unlocated", 12, 20, "")])

    assert result["matches"] is False
    assert result["problems"] == [{"kind": "hole", "char_start": 8, "char_end": 12}]


def test_coverage_detects_a_hole_at_the_end():
    """REQ-004 (test negativo): un hueco al final del texto también se detecta."""
    result = coverage("x" * 20, [unit(0, 15)], [])

    assert result["matches"] is False
    assert result["problems"] == [{"kind": "hole", "char_start": 15, "char_end": 20}]


def test_coverage_detects_an_overlap():
    """REQ-004 (test negativo del control de cobertura): dos tramos que se pisan cuentan
    dos veces los mismos caracteres: la suma no coincide y se dice dónde se pisan."""
    text = "x" * 20

    result = coverage(text, [unit(0, 12)], [("unlocated", 10, 20, "")])

    assert result["matches"] is False
    assert result["problems"] == [{"kind": "overlap", "char_start": 10, "char_end": 12}]
    assert result["units"] + result["unlocated"] == 22


def test_coverage_counts_separators_and_ignores_incisos():
    """REQ-004: el salto de línea entre dos tramos es la cuarta categoría (separadores) y
    un inciso no se cuenta, porque es un recorte de su artículo."""
    text = "aaaa\nbbbb"

    result = coverage(text, [unit(0, 4), unit(2, 4, "inciso")], [("unlocated", 5, 9, "")])

    assert result == {
        "total": 9,
        "units": 4,
        "discarded": 0,
        "unlocated": 4,
        "separators": 1,
        "matches": True,
        "problems": [],
    }


def test_a_failed_coverage_goes_first_to_attention():
    """REQ-004: si la cobertura no cierra, el texto lo dice y "Requiere atención" lo pone
    en primer lugar."""
    result = split_document(pdf(page(1, "ARTÍCULO 1°.- UNO. Texto.")), part="cuerpo")
    report = json.loads(json.dumps(result.report))
    report["coverage"] = coverage("x" * 20, [unit(0, 8)], [("unlocated", 12, 20, "")])
    report["attention"] = attention_items(report)

    text = report_text(report)

    assert kinds(report)[0] == "coverage"
    assert "la suma NO coincide con el total" in text
    assert "hueco" in report["attention"][0]["text"]


def test_coverage_of_a_real_split_adds_up():
    """REQ-004: la cobertura suma el total leído, con las cuatro categorías nombradas en
    el texto."""
    result = split_document(clause_reading(), part="anexo")
    cover = result.report["coverage"]

    assert cover["matches"] is True and cover["problems"] == []
    assert cover["units"] + cover["discarded"] + cover["unlocated"] + cover["separators"] == cover["total"]
    assert "saltos de línea entre tramos" in result.report_text


# --- Documento, duplicados y forma del informe (REQ-004) ---------------------------------


def test_the_document_part_has_format_pages_versions_and_hashes():
    """REQ-004: la parte "Documento" trae el formato detectado, la cantidad de páginas,
    las versiones de las herramientas, la versión y la regla de partición, la huella del
    texto canónico y, si la carga los pasa, el nombre, la huella del archivo y la fecha."""
    reading = pdf(page(1, "ARTÍCULO 1°.- UNO. Texto."))
    info = {"file_name": "norma.pdf", "file_sha256": "ab" * 32, "read_at": "2026-10-03 10:00"}

    result = split_document(reading, part="cuerpo", document_info=info)
    bare = split_document(reading, part="cuerpo")

    document = result.report["document"]
    assert document == {
        "file_name": "norma.pdf",
        "file_sha256": "ab" * 32,
        "read_at": "2026-10-03 10:00",
        "file_format": FORMAT_PDF,
        "pages": 1,
        "canonical_sha256": result.canonical_sha256,
        "tool_versions": TOOLS,
        "rules_version": result.rules_version,
        "rule": "normas",
        "part": "cuerpo",
    }
    text = result.report_text
    assert "Archivo: norma.pdf." in text
    assert f"Huella del archivo: {'ab' * 32}." in text
    assert "Formato: PDF. Cantidad de páginas: 1." in text
    assert "Herramientas: pdfplumber 0.11.10, pypdfium2 5.13.0." in text
    assert f"Huella del texto canónico: {result.canonical_sha256}." in text
    assert bare.report["document"]["file_name"] is None
    assert "Archivo:" not in bare.report_text


def test_duplicates_are_left_for_the_load_to_fill():
    """REQ-004: la parte de posibles duplicados queda sin comprobar en la partición (la
    completa la carga, T-026); cuando la carga la completa, el aviso pasa a "Requiere
    atención"."""
    result = split_document(pdf(page(1, "ARTÍCULO 1°.- UNO. Texto.")), part="cuerpo")
    report = json.loads(json.dumps(result.report))

    assert report["duplicates"] is None
    assert "Posibles duplicados: sin comprobar" in result.report_text

    report["duplicates"] = [{"check": "same_norm", "detail": "Misma norma que el documento 3."}]
    report["attention"] = attention_items(report)
    text = report_text(report)

    assert "duplicates" in kinds(report)
    assert "  - Misma norma que el documento 3." in text


def test_the_ten_parts_come_in_order_starting_with_attention():
    """REQ-004: el texto trae las diez partes del ADR-0004 en su orden, empezando por
    "Requiere atención", y al final la lista de unidades con su clave."""
    result = split_document(mixed_reading(), part="cuerpo")
    starts = [
        "Requiere atención:",
        "Documento:",
        "Páginas:",
        "Unidades reconocidas:",
        "No ubicado:",
        "Descartado:",
        "Uniones de palabras cortadas:",
        "Reconocimiento sobre imagen:",
        "Cobertura:",
        "Posibles duplicados:",
        "Unidades:",
    ]
    lines = result.report_text.splitlines()
    positions = [next(i for i, text in enumerate(lines) if text.startswith(start)) for start in starts]

    assert positions == sorted(positions)
    assert lines[0] == "Informe de lectura"


def test_nothing_to_attend_says_so():
    """REQ-004: si no hay nada que requiera atención, el informe lo dice."""
    result = split_document(pdf(page(1, "ARTÍCULO 1°.- UNO. Texto.")), part="cuerpo")

    assert result.report["attention"] == []
    assert "Requiere atención: nada." in result.report_text


def test_the_report_survives_being_stored_as_json():
    """REQ-004: el informe se guarda como JSON (`norms_reading.report`): vuelve igual, y
    el texto armado desde lo guardado es el mismo que se mostró."""
    result = split_document(mixed_reading(), part="cuerpo")

    stored = json.loads(json.dumps(result.report))

    assert stored == result.report
    assert report_text(stored) == result.report_text


# --- El anexo real de la Disp. AFIP 247/2022 (REQ-004) ----------------------------------


@pytest.fixture(scope="module")
def annex():
    return split_document(read_document(ANNEX_247), part="anexo", category="regimen_especifico")


def test_real_annex_report_makes_sense(annex):
    """REQ-004: el informe del anexo de la 247/2022 dice lo que hay: 99 artículos y 1
    cláusula, los 99 que lista su índice; la página 45 (solo la firma digital) sin texto,
    no ilegible; ningún tramo sin ubicar; la cobertura completa. "Requiere atención"
    trae la página 45 y los párrafos después del último inciso, y nada más."""
    report = annex.report

    [container] = report["units"]["containers"]
    assert container["by_type"] == {"articulo": 99, "clausula": 1}
    assert (container["expected"], container["expected_from"], container["recognized"]) == (
        99,
        "indice",
        99,
    )
    assert container["missing"] == []
    assert report["page_summary"] == {
        "illegible": [],
        "almost_empty": [],
        "doubtful": [],
        "without_text": [45],
        "blank": [],
    }
    assert kinds(report) == ["pages_without_text", "after_last_inciso"]
    assert report["ocr"]["units"] == 0
    assert report["coverage"]["matches"] is True
    text = annex.report_text
    assert "Anexo: 99 artículos y 1 cláusula; artículos del 1 al 99." in text
    assert "Según el índice se esperaban 99 artículos; se reconocieron 99." in text
    assert "ilegible" not in attention_text(annex)
