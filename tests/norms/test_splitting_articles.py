"""Partición en artículos e informe de lectura mínimo (T-013; ADR-0004, "Cómo se parte" y
"Qué contiene el informe de lectura"; plan 001, "Identificación de unidades" y "Una norma
en más de un archivo").

Documento de prueba: `tests/fixtures/disp-247-2022-anexo-extracto.pdf` (T-012), las
páginas 1 a 6 del anexo de la Disposición AFIP 247/2022. Trae la carátula, el índice de
las páginas 1 a 5 (que repite los encabezados como `ARTÍCULO 1º.- OBJETO`, sin texto) y
el articulado desde la página 5 (`ARTÍCULO 1°.- OBJETO.` con el texto a continuación).
El artículo 7 queda cortado al final de la página 6. Además, una prueba con el anexo
completo del corpus, que se lee sin modificarlo. Las lecturas sintéticas son propias de
cada prueba (P4).
"""

import dataclasses
import hashlib
from pathlib import Path

import pytest

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_PDF_TEXT,
    PAGE_NOT_READ,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
    read_document,
)
from evaluon.norms.splitting import RULES_VERSION, split_document

REPO = Path(__file__).resolve().parents[2]
EXTRACT = REPO / "tests" / "fixtures" / "disp-247-2022-anexo-extracto.pdf"
ORIGINAL = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"


@pytest.fixture(scope="module")
def extract_reading():
    return read_document(EXTRACT)


@pytest.fixture(scope="module")
def as_annex(extract_reading):
    return split_document(extract_reading, part="anexo")


@pytest.fixture(scope="module")
def as_body(extract_reading):
    return split_document(extract_reading, part="cuerpo")


def articles(result):
    return [unit for unit in result.units if unit.unit_type == "articulo"]


def by_key(result):
    return {unit.key: unit for unit in result.units}


def synthetic(*paragraph_pages):
    """Una lectura sintética: cada argumento es una página, lista de párrafos de un
    renglón cada uno, separados como en el anexo de la 247/2022."""
    pages = []
    for number, paragraphs in enumerate(paragraph_pages, start=1):
        lines, top = [], 30.0
        for text in paragraphs:
            lines.append(
                Line(text=text, x0=70.0, top=top, x1=300.0, bottom=top + 12.0, origin=ORIGIN_PDF_TEXT)
            )
            top += 25.5
        pages.append(Page(number=number, width=612.0, height=792.0, status=PAGE_READ, lines=lines))
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions={"pdfplumber": "x"})


def check_invariants(result):
    """Propiedades que se cumplen siempre (ADR-0004, "Cómo se prueba")."""
    text = result.canonical_text
    for unit in result.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
    orders = [unit.order for unit in result.units]
    assert orders == sorted(orders) and len(set(orders)) == len(orders)
    starts = [unit.char_start for unit in result.units]
    assert starts == sorted(starts)
    assert len({unit.key for unit in result.units}) == len(result.units)
    coverage = result.report["coverage"]
    assert coverage["total"] == len(text)
    assert (
        coverage["units"] + coverage["discarded"] + coverage["unlocated"] + coverage["separators"]
        == coverage["total"]
    )
    assert coverage["matches"] is True


# --- Cada artículo es una unidad separada con su ubicación (REQ-003) --------------------


def test_each_article_of_the_extract_is_a_unit_under_the_annex(as_annex):
    """REQ-003: cargado como parte `anexo`, cada artículo del extracto es una unidad
    separada con clave `anexo/art-N`, que cuelga de la unidad raíz `anexo`."""
    units = articles(as_annex)

    assert [unit.number for unit in units] == ["1", "2", "3", "4", "5", "6", "7"]
    assert [unit.key for unit in units] == [f"anexo/art-{n}" for n in range(1, 8)]
    assert all(unit.parent_key == "anexo" for unit in units)
    assert all(unit.text_origin == ORIGIN_PDF_TEXT for unit in units)


def test_the_annex_root_unit(as_annex):
    """REQ-003: con la parte `anexo` hay una sola unidad raíz de tipo `anexo`, cuya clave
    es la parte; su texto propio es lo que está antes del índice y del primer artículo,
    sin la carátula GDE. Los encabezados "ANEXO" de la carátula no abren otro
    contenedor.

    Ajuste de T-023: el membrete y los datos GDE ("ANEXO", "Número:", "Referencia:")
    pasan a descartarse como carátula (aviso de T-013 a T-023); la raíz empieza en
    "ANEXO (artículo 1°)", que es su etiqueta."""
    roots = [unit for unit in as_annex.units if unit.unit_type == "anexo"]

    assert len(roots) == 1
    root = roots[0]
    assert as_annex.units[0] is root
    assert (root.key, root.number, root.path, root.parent_key) == ("anexo", "", "Anexo", None)
    assert root.label == "ANEXO (artículo 1°)"
    assert root.text.startswith("ANEXO (artículo 1°)\n")
    cover = as_annex.report["discarded"][0]
    assert (cover["reason"], cover["char_start"]) == ("caratula", 0)
    # El membrete ocupa dos renglones pegados: es un solo párrafo.
    assert as_annex.canonical_text[: cover["char_end"]].startswith(
        'Administración Federal de Ingresos Públicos 2022 - "Las Malvinas son argentinas"\n'
        "ANEXO\nNúmero:\nReferencia:"
    )
    assert root.char_start == cover["char_end"] + 1
    assert root.text.endswith(
        "RÉGIMEN GENERAL PARA CONTRATACIONES DE BIENES, SERVICIOS Y OBRAS PÚBLICAS DE LA "
        "ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS"
    )
    assert "ÍNDICE" not in root.text
    assert (root.page_start, root.page_end) == (1, 1)


def test_article_location_matches_the_document(as_annex):
    """REQ-003: la ubicación de cada artículo coincide con la del documento: etiqueta
    como figura, ruta, páginas y texto desde su encabezado hasta el siguiente. Ajuste
    de T-023: la ruta lleva el título que contiene al artículo."""
    units = by_key(as_annex)
    first, third, fourth = units["anexo/art-1"], units["anexo/art-3"], units["anexo/art-4"]

    assert first.label == "ARTÍCULO 1°.- OBJETO"
    assert first.path == "Anexo › Título I › Artículo 1"
    assert (first.page_start, first.page_end) == (5, 5)
    assert first.text == (
        "ARTÍCULO 1°.- OBJETO. El presente régimen tendrá por objeto establecer los "
        "lineamientos y principios básicos que deberán ser observados en todos los "
        "procedimientos de contrataciones de bienes, servicios y obras, de modo que se "
        "realicen en forma oportuna y al menor costo posible, como así también que la venta "
        "de bienes sea efectuada al mejor postor, coadyuvando al desempeño eficiente de la "
        "Administración Federal de Ingresos Públicos y al logro de los resultados requeridos "
        "por la sociedad.\n"
        "Toda contratación de la AFIP se presumirá de índole administrativa, salvo que por "
        "sus características esté sometida a normas de derecho privado."
    )

    assert third.label == "ARTÍCULO 3°.- PRINCIPIOS GENERALES"
    assert (third.page_start, third.page_end) == (5, 6)
    assert third.text.startswith("ARTÍCULO 3°.- PRINCIPIOS GENERALES. Los principios")
    assert "\na) Integridad en los procedimientos.\nb) Razonabilidad del proyecto" in third.text
    assert third.text.endswith("observancia de los principios que anteceden.")

    assert fourth.label == "ARTÍCULO 4°.- CONTRATOS COMPRENDIDOS"
    assert (fourth.page_start, fourth.page_end) == (6, 6)
    assert units["anexo/art-6"].label == (
        "ARTÍCULO 6°.- EXCEPCIONES A LAS CLÁUSULAS GENERALES DE CONTRATACIÓN"
    )


def test_the_index_produces_no_units(as_annex):
    """REQ-003: el índice de las páginas 1 a 5, que repite los encabezados con otra
    grafía (`ARTÍCULO 1º.- OBJETO`) y sin texto, no produce unidades: se descarta y se
    informa. Ningún artículo empieza antes de la página 5. Ajuste de T-023: lo descartado
    trae además la carátula y los títulos que pasan a la ruta; el índice sigue siendo un
    solo tramo."""
    assert all(unit.page_start == 5 or unit.page_start == 6 for unit in articles(as_annex))
    assert not any("º.-" in unit.label for unit in articles(as_annex))

    discarded = [item for item in as_annex.report["discarded"] if item["reason"] == "indice"]
    assert len(discarded) == 1
    index = discarded[0]
    assert (index["page_start"], index["page_end"]) == (1, 5)
    text = as_annex.canonical_text[index["char_start"] : index["char_end"]]
    assert text.startswith("ÍNDICE:\nTÍTULO I - DISPOSICIONES GENERALES\nARTÍCULO 1º.- OBJETO\n")
    assert text.endswith("ARTÍCULO 99.- VALOR DEL MÓDULO")


def test_the_same_text_as_body_gives_keys_without_the_annex(as_body):
    """REQ-003: el mismo texto partido como `cuerpo` no tiene unidad raíz: los artículos
    tienen claves `art-N`, sin contenedor, y la ruta empieza en el artículo. Ajuste de
    T-023: la ruta empieza en el título; además de los artículos solo hay incisos, que
    cuelgan de ellos."""
    units = articles(as_body)

    assert [unit.key for unit in units] == [f"art-{n}" for n in range(1, 8)]
    assert all(unit.parent_key is None for unit in units)
    assert units[0].path == "Título I › Artículo 1"
    assert not [unit for unit in as_body.units if unit.unit_type == "anexo"]
    others = [unit for unit in as_body.units if unit.unit_type != "articulo"]
    assert {unit.unit_type for unit in others} == {"inciso"}
    assert all(unit.key.startswith("art-") for unit in others)


def test_annex_and_body_cut_the_articles_at_the_same_places(as_annex, as_body):
    """REQ-003: la parte cambia la clave y la ruta, no el recorte: cada artículo tiene el
    mismo texto y las mismas posiciones como `anexo` y como `cuerpo`."""
    assert as_annex.canonical_text == as_body.canonical_text
    pairs = zip(articles(as_annex), articles(as_body), strict=True)
    for annex_unit, body_unit in pairs:
        assert (annex_unit.char_start, annex_unit.char_end) == (
            body_unit.char_start,
            body_unit.char_end,
        )
        assert annex_unit.label == body_unit.label


def test_text_is_always_the_canonical_slice_and_coverage_adds_up(as_annex, as_body):
    """REQ-003, REQ-004: en todas las unidades, el texto es igual, carácter por carácter,
    a `canonical_text[char_start:char_end]`; el orden es creciente y la cobertura suma el
    total del texto canónico."""
    check_invariants(as_annex)
    check_invariants(as_body)


def test_canonical_text_and_its_fingerprint_come_with_the_result(as_annex):
    """REQ-003: la partición entrega el texto canónico, su huella y la versión de las
    reglas, que se guardan con la lectura."""
    assert as_annex.canonical_sha256 == hashlib.sha256(
        as_annex.canonical_text.encode("utf-8")
    ).hexdigest()
    assert as_annex.rules_version == RULES_VERSION
    assert as_annex.report["rules_version"] == RULES_VERSION


# --- Reglas de encabezado y control de secuencia (REQ-003) ------------------------------


def test_sequence_control_keeps_an_out_of_sequence_heading_inside_the_article():
    """REQ-003: dentro de un contenedor, un encabezado de artículo se acepta solo si
    continúa la numeración. Un "ARTÍCULO 14.-" que aparece después del 2 (por ejemplo,
    un artículo transcripto) queda dentro del artículo 2; el 3 se acepta después."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- OBJETO. Texto del uno.",
                "ARTÍCULO 2°.- MODIFICACIÓN. Sustitúyese el artículo 14 por el siguiente:",
                "ARTÍCULO 14.- GARANTÍAS. Texto transcripto.",
                "ARTÍCULO 3°.- VIGENCIA. Texto del tres.",
                "ARTÍCULO 3°.- REPETIDO. Texto repetido.",
            ]
        ),
        part="cuerpo",
    )

    units = by_key(result)
    assert list(units) == ["art-1", "art-2", "art-3"]
    assert units["art-2"].text.endswith("\nARTÍCULO 14.- GARANTÍAS. Texto transcripto.")
    assert units["art-3"].text.endswith("\nARTÍCULO 3°.- REPETIDO. Texto repetido.")
    check_invariants(result)


def test_article_heading_forms_of_the_annex():
    """REQ-003: las formas de encabezado del anexo de la 247/2022: con signo de grado o
    con ordinal, sin signo desde el 10, con epígrafe seguido de texto, y con epígrafe
    solo, terminado en punto, cuando el texto sigue en otro párrafo (artículos 27 y 67).
    La etiqueta es el encabezado con su epígrafe, sin el punto ni el texto. Ajuste de
    T-023: el `a)` es además un inciso del artículo 4, por eso se miran solo los
    artículos."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- OBJETO. Texto.",
                "ARTÍCULO 2º.- ÁMBITO. Texto.",
                "ARTÍCULO 3.- SIN SIGNO. Texto.",
                "ARTÍCULO 4°.- PLIEGOS DE BASES Y CONDICIONES.",
                "a) Los pliegos que rigen la contratación serán:",
                "ARTÍCULO 5°.- Texto sin epígrafe.",
            ]
        ),
        part="cuerpo",
    )

    assert [(unit.number, unit.label) for unit in articles(result)] == [
        ("1", "ARTÍCULO 1°.- OBJETO"),
        ("2", "ARTÍCULO 2º.- ÁMBITO"),
        ("3", "ARTÍCULO 3.- SIN SIGNO"),
        ("4", "ARTÍCULO 4°.- PLIEGOS DE BASES Y CONDICIONES"),
        ("5", "ARTÍCULO 5°.-"),
    ]
    assert articles(result)[3].text == (
        "ARTÍCULO 4°.- PLIEGOS DE BASES Y CONDICIONES.\n"
        "a) Los pliegos que rigen la contratación serán:"
    )
    check_invariants(result)


def test_a_citation_in_the_middle_of_a_paragraph_is_not_a_heading():
    """REQ-003: una mención a un artículo que no está al comienzo de un renglón, o que no
    tiene la forma de encabezado, no abre una unidad."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- OBJETO. Conforme el ARTÍCULO 2°.- del decreto.",
                "Artículo 2° de la Ley N° 19.549, que se cita.",
                "ARTÍCULO 2°.- SEGUNDO. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert [unit.key for unit in result.units] == ["art-1", "art-2"]
    assert result.units[0].text.endswith("\nArtículo 2° de la Ley N° 19.549, que se cita.")


def test_an_uppercase_heading_closes_the_article_and_is_reported_as_unlocated():
    """REQ-003, REQ-004: un párrafo propio que es un encabezado reconocido (un título, un
    capítulo, una cláusula transitoria) cierra el artículo abierto: su texto no se suma
    al artículo. Lo que sigue hasta la próxima unidad queda como no ubicado, con su
    página y sus primeras ocho palabras.

    Ajuste de T-023 (decisión del responsable del 2026-10-03): el corte se limita a los
    encabezados reconocidos. El título y el capítulo pasan a la ruta y se descartan con
    su motivo, y la cláusula transitoria es una unidad propia, en lugar de quedar como no
    ubicados; un párrafo suelto después del capítulo sigue quedando sin ubicar. Una frase
    en mayúsculas que no es un encabezado reconocido no corta (lo prueba
    `test_splitting_rules.py`)."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- OBJETO. Texto del uno.",
                "TÍTULO II - DE LA FORMACIÓN DEL CONTRATO",
                "CAPÍTULO I - PROCEDIMIENTOS",
                "Texto suelto que no es de ningún artículo, después del capítulo.",
                "ARTÍCULO 2°.- REGLA. Texto del dos.",
            ],
            [
                "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES",
                "Las unidades en las que aún no se hubiere implementado el registro.",
            ],
        ),
        part="anexo",
    )

    units = by_key(result)
    assert units["anexo/art-1"].text == "ARTÍCULO 1°.- OBJETO. Texto del uno."
    assert units["anexo/art-2"].text == "ARTÍCULO 2°.- REGLA. Texto del dos."
    assert units["anexo/art-2"].path == "Anexo › Título II › Capítulo I › Artículo 2"
    unlocated = result.report["unlocated"]
    assert [(item["page"], item["first_words"]) for item in unlocated] == [
        (1, "Texto suelto que no es de ningún artículo,"),
    ]
    titles = [item["first_words"] for item in result.report["discarded"] if item["reason"] == "titulo"]
    assert titles == ["TÍTULO II - DE LA FORMACIÓN DEL CONTRATO", "CAPÍTULO I - PROCEDIMIENTOS"]
    assert units["anexo/clausula-transitoria"].text == (
        "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES\n"
        "Las unidades en las que aún no se hubiere implementado el registro."
    )
    check_invariants(result)


def test_body_text_before_the_first_article_is_unlocated():
    """REQ-003, REQ-004: con la parte `cuerpo` no hay unidad raíz: lo que está antes del
    primer artículo y no tiene una forma reconocida queda como no ubicado.

    Ajuste de T-023: el visto y los considerandos ya son unidades (los prueba
    `test_splitting_rules.py`); este caso usa un texto previo sin forma reconocida."""
    result = split_document(
        synthetic(["Texto previo sin forma.", "Otro párrafo previo.", "ARTÍCULO 1°.- Apruébase."]),
        part="cuerpo",
    )

    assert [unit.key for unit in result.units] == ["art-1"]
    assert result.report["unlocated"][0]["first_words"] == "Texto previo sin forma. Otro párrafo previo."
    check_invariants(result)


def test_annex_parts_with_numbers_get_their_own_root():
    """REQ-003: la clave de la unidad raíz es la parte; `anexo-i` da la ruta "Anexo I" y
    el número `I`, y sus artículos quedan como `anexo-i/art-N`."""
    result = split_document(synthetic(["ANEXO I", "ARTÍCULO 1°.- OBJETO. Texto."]), part="anexo-i")

    root, first = result.units
    assert (root.key, root.number, root.path, root.label) == ("anexo-i", "I", "Anexo I", "ANEXO I")
    assert (first.key, first.path, first.parent_key) == ("anexo-i/art-1", "Anexo I › Artículo 1", "anexo-i")


def test_an_invalid_part_is_rejected():
    """REQ-003: la parte es `cuerpo` o la clave de un anexo (`anexo`, `anexo-i`); otro
    valor no se acepta, porque armaría claves que no se pueden comparar."""
    for part in ("Anexo", "anexo i", "apéndice", ""):
        with pytest.raises(ValueError):
            split_document(synthetic(["ARTÍCULO 1°.- Texto."]), part=part)


def test_same_reading_gives_the_same_partition(extract_reading, as_annex):
    """REQ-003: la partición es determinista: la misma lectura da las mismas unidades y
    el mismo informe."""
    again = split_document(extract_reading, part="anexo")

    assert again.units == as_annex.units
    assert again.report == as_annex.report
    assert again.report_text == as_annex.report_text


# --- Informe de lectura mínimo (REQ-004) ------------------------------------------------


def test_report_counts_units_by_type_and_container(as_annex):
    """REQ-004: el informe dice cuántas unidades reconoció, por tipo y por contenedor,
    con el primer y el último número. Ajuste de T-023: suma los incisos de los artículos 3
    (a a h), 5 (a a d) y 7 (a)."""
    units = as_annex.report["units"]

    assert units["total"] == 21
    assert units["by_type"] == {"anexo": 1, "articulo": 7, "inciso": 13}
    assert units["by_container"] == [
        {"container": "Anexo", "key": "anexo", "articulo": 7, "first": "1", "last": "7"}
    ]


def test_report_lists_every_unit_with_its_key(as_annex):
    """REQ-004: el informe lista las unidades con su clave, su tipo, su etiqueta y sus
    páginas, en el orden del documento; el texto legible las muestra con su clave. Ajuste
    de T-023: la ruta lleva el título."""
    listed = as_annex.report["unit_list"]

    assert [item["key"] for item in listed] == [unit.key for unit in as_annex.units]
    assert listed[1] == {
        "key": "anexo/art-1",
        "unit_type": "articulo",
        "label": "ARTÍCULO 1°.- OBJETO",
        "path": "Anexo › Título I › Artículo 1",
        "page_start": 5,
        "page_end": 5,
    }
    for unit in as_annex.units:
        assert unit.key in as_annex.report_text


def test_report_shows_what_could_not_be_located(as_annex):
    """REQ-004: el informe señala cada tramo que no entró en ninguna unidad, con su página
    y sus primeras palabras.

    Ajuste de T-023: en el extracto el título I que precede al artículo 1 ya no queda sin
    ubicar (decisión del responsable del 2026-10-03): pasa a la ruta y se informa como
    descartado, con su página. Nada queda sin ubicar en el extracto; el señalamiento de
    lo no ubicado lo prueban `test_body_text_before_the_first_article_is_unlocated` y
    `test_splitting_rules.py`."""
    assert as_annex.report["unlocated"] == []
    assert "No ubicado: 0 tramos." in as_annex.report_text
    titles = [item for item in as_annex.report["discarded"] if item["reason"] == "titulo"]
    assert [(item["page_start"], item["first_words"]) for item in titles] == [
        (5, "TÍTULO I - DISPOSICIONES GENERALES")
    ]
    assert "TÍTULO I - DISPOSICIONES GENERALES" in as_annex.report_text


def test_report_points_out_the_page_that_could_not_be_read_and_no_other(extract_reading):
    """REQ-004: dada una lectura con una página que no se pudo leer, el informe señala
    esa página y ninguna otra, en datos y en el texto legible."""
    pages = [dataclasses.replace(page) for page in extract_reading.pages]
    pages[2] = dataclasses.replace(pages[2], status=PAGE_NOT_READ, lines=[])
    damaged = dataclasses.replace(extract_reading, pages=pages)

    result = split_document(damaged, part="anexo")

    assert result.report["pages"] == {"total": 6, "not_read": [3]}
    assert "Páginas no leídas: 3." in result.report_text
    clean = split_document(extract_reading, part="anexo")
    assert clean.report["pages"] == {"total": 6, "not_read": []}
    assert "Páginas no leídas: ninguna." in clean.report_text
    check_invariants(result)


def test_report_text_has_the_minimum_parts(as_annex):
    """REQ-004: el informe en texto trae las partes mínimas: páginas, unidades por tipo y
    contenedor, no ubicado, descartado, uniones de palabras cortadas, cobertura y la lista
    de unidades. Ajuste de T-023: suma los incisos; lo descartado trae la carátula, el
    índice y el título I; nada queda sin ubicar."""
    text = as_annex.report_text

    assert "Unidades reconocidas: 21 (1 anexo, 7 artículos, 13 incisos)." in text
    assert "Anexo: 7 artículos, del 1 al 7." in text
    assert "No ubicado: 0 tramos." in text
    assert "Descartado: 3 tramos." in text
    assert "Carátula (membrete y datos GDE), página 1" in text
    assert "Índice, páginas 1 a 5" in text
    assert "Uniones de palabras cortadas: 0." in text
    total = as_annex.report["coverage"]["total"]
    assert f"Cobertura: {total} caracteres" in text
    assert "la suma coincide con el total" in text


def test_report_counts_hyphen_joins():
    """REQ-004: las uniones de palabras cortadas se cuentan y se listan en el informe con
    su página, porque pueden equivocarse con palabras compuestas."""
    reading = synthetic([])
    top = 30.0
    for text in ("ARTÍCULO 1°.- OBJETO. El procedimiento de contra-", "tación directa."):
        reading.pages[0].lines.append(
            Line(text=text, x0=70.0, top=top, x1=595.0, bottom=top + 12.0, origin=ORIGIN_PDF_TEXT)
        )
        top += 13.5

    result = split_document(reading, part="cuerpo")

    assert result.units[0].text == "ARTÍCULO 1°.- OBJETO. El procedimiento de contratación directa."
    assert result.report["hyphen_joins"] == [{"page": 1, "word": "contratación"}]
    assert "Uniones de palabras cortadas: 1." in result.report_text
    assert "página 1: contratación" in result.report_text


# --- El anexo completo del corpus (REQ-003) ---------------------------------------------


@pytest.fixture(scope="module")
def full_annex():
    return split_document(read_document(ORIGINAL), part="anexo")


def test_full_annex_has_its_99_articles(full_annex):
    """REQ-003: el anexo completo de la 247/2022 da sus 99 artículos, de `anexo/art-1` a
    `anexo/art-99`, en orden, todos con texto, sin que el índice produzca unidades."""
    units = articles(full_annex)

    assert [unit.key for unit in units] == [f"anexo/art-{n}" for n in range(1, 100)]
    assert units[0].page_start == 5
    assert units[-1].label == "ARTÍCULO 99.- VALOR DEL MÓDULO"
    assert (units[-1].page_start, units[-1].page_end) == (44, 44)
    assert units[-1].text.endswith("será el que fije la máxima autoridad del Organismo.")
    assert full_annex.report["pages"] == {"total": 45, "not_read": [45]}
    check_invariants(full_annex)
