"""Texto canónico de una lectura (T-013; ADR-0004, "Texto literal"; plan 001, "Cita").

El texto canónico se obtiene de la lectura con cinco operaciones fijas y ninguna más:
NFC; ligaduras, espacios duros y guiones opcionales; saltos de línea dentro de un párrafo
por un espacio; unión de palabras cortadas por guion si la línea siguiente empieza en
minúscula, contada; y espacios repetidos reducidos a uno. Los párrafos quedan separados
por un salto de línea.

Las lecturas sintéticas se arman en cada prueba con el resultado común de T-012 (P4).
El extracto real es `tests/fixtures/disp-247-2022-anexo-extracto.pdf` (T-012).
"""

import unicodedata
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
from evaluon.norms.splitting.canonical import build_canonical_text

REPO = Path(__file__).resolve().parents[2]
EXTRACT = REPO / "tests" / "fixtures" / "disp-247-2022-anexo-extracto.pdf"

# Medidas de las páginas del anexo de la 247/2022: renglones de 12 puntos de alto, 1,5
# puntos entre renglones de un mismo párrafo y 13,5 entre párrafos; margen derecho
# cerca de 595.
HEIGHT = 12.0
LINE_GAP = 1.5
PARAGRAPH_GAP = 13.5
FULL = 595.0
SHORT = 300.0


def page(number, paragraphs, status=PAGE_READ, last_full=False):
    """Una página sintética. `paragraphs` es una lista de párrafos, cada uno una lista
    de renglones. Los renglones de un párrafo llegan al margen derecho salvo el último;
    con `last_full`, también el último renglón de la página llega al margen."""
    lines = []
    top = 30.0
    for p_index, paragraph in enumerate(paragraphs):
        if p_index:
            top += PARAGRAPH_GAP - LINE_GAP
        for l_index, text in enumerate(paragraph):
            last = l_index == len(paragraph) - 1
            last_of_page = last and p_index == len(paragraphs) - 1
            x1 = FULL if (not last or (last_of_page and last_full)) else SHORT
            lines.append(
                Line(text=text, x0=70.0, top=top, x1=x1, bottom=top + HEIGHT, origin=ORIGIN_PDF_TEXT)
            )
            top += HEIGHT + LINE_GAP
    return Page(number=number, width=612.0, height=792.0, status=status, lines=lines)


def reading(*pages):
    return DocumentReading(file_format=FORMAT_PDF, pages=list(pages), tool_versions={})


def canonical(*paragraphs):
    return build_canonical_text(reading(page(1, list(paragraphs))))


# --- Las cinco operaciones ------------------------------------------------------------


def test_operation_1_nfc_composes_accents_and_keeps_the_ordinal_sign():
    """REQ-003: operación 1, normalización NFC. Una tilde escrita como letra más acento
    combinante queda compuesta; `º` (ordinal) y `°` (grado) no se tocan, porque NFKC
    convertiría `º` en `o` y no se usa."""
    decomposed = "ARTI\u0301CULO 1º.- Contratacio\u0301n del 2°"
    assert not unicodedata.is_normalized("NFC", decomposed)

    result = canonical([decomposed])

    assert result.text == "ARTÍCULO 1º.- Contratación del 2°"
    assert "º" in result.text and "°" in result.text


def test_operation_2_ligatures_hard_spaces_and_soft_hyphens():
    """REQ-003: operación 2. Las ligaduras tipográficas se separan en sus letras, los
    espacios duros pasan a espacio común y los guiones opcionales invisibles se quitan."""
    result = canonical(["La \ufb01rma del o\ufb01cio \ufb02uye\u00a0con\u202fla\u2007contra\u00adtación \ufb00 \ufb03 \ufb04"])

    assert result.text == "La firma del oficio fluye con la contratación ff ffi ffl"


def test_operation_3_line_breaks_inside_a_paragraph_become_a_space():
    """REQ-003: operación 3. Los saltos de línea dentro de un párrafo se reemplazan por un
    espacio; los párrafos quedan separados por un salto de línea."""
    result = canonical(
        ["Primer renglón del párrafo", "y su segundo renglón."],
        ["Segundo párrafo."],
    )

    assert result.text == "Primer renglón del párrafo y su segundo renglón.\nSegundo párrafo."
    assert result.paragraphs == [(0, 48), (49, 65)]


def test_operation_4_joins_a_word_cut_by_a_hyphen_only_before_lowercase_and_counts_it():
    """REQ-003, REQ-004: operación 4. Una palabra cortada por guion al final del renglón
    se une solo si el renglón siguiente empieza en minúscula; cada unión se cuenta con su
    página y la palabra que resultó, para el informe."""
    result = canonical(
        [
            "el procedimiento de contra-",
            "tación y la ley Norte-",
            "Sur del Decreto N° 1.759/72 -",
            "texto ordenado y el año 2022-",
            "2023 en la sub-",
            "comisión.",
        ]
    )

    assert result.text == (
        "el procedimiento de contratación y la ley Norte- Sur del Decreto N° 1.759/72 - "
        "texto ordenado y el año 2022- 2023 en la subcomisión."
    )
    assert [(join.page, join.word) for join in result.hyphen_joins] == [
        (1, "contratación"),
        (1, "subcomisión"),
    ]


def test_operation_5_repeated_spaces_become_one():
    """REQ-003: operación 5. Los espacios repetidos se reducen a uno, también los que
    resultan de los espacios duros y de la unión de renglones."""
    result = canonical(["Dos   espacios\u00a0\u00a0 y", " otro renglón"])

    assert result.text == "Dos espacios y otro renglón"


def test_nothing_else_changes_case_accents_signs_or_spelling():
    """REQ-003: ninguna operación más. No se corrigen mayúsculas, tildes, signos ni
    ortografía: "palabra por palabra" es la misma secuencia de palabras y signos."""
    text = "INEGIBILIDAD -directa o indirectamente-, “web” (M) aun Nº 19.549; ¿qué? ¡sí!"
    assert canonical([text]).text == text


# --- Párrafos y páginas -----------------------------------------------------------------


def test_a_paragraph_continues_on_the_next_page_only_if_the_last_line_is_full():
    """REQ-003: un párrafo sigue en la página siguiente si el último renglón de la página
    llega al margen derecho y no termina en punto, dos puntos o punto y coma, aunque la
    página siguiente empiece con mayúscula ("todo el" / "Organismo.", anexo de la
    247/2022, páginas 18 y 19). Si no, empieza otro párrafo."""
    continued = build_canonical_text(
        reading(
            page(1, [["Primer párrafo que sigue", "de forma transversal a todo el"]], last_full=True),
            page(2, [["Organismo."], ["Otro párrafo."]]),
        )
    )
    assert continued.text == (
        "Primer párrafo que sigue de forma transversal a todo el Organismo.\nOtro párrafo."
    )

    ended = build_canonical_text(
        reading(
            page(1, [["a) Integridad en los procedimientos."]]),
            page(2, [["b) Razonabilidad del proyecto."]]),
        )
    )
    assert ended.text == "a) Integridad en los procedimientos.\nb) Razonabilidad del proyecto."

    full_with_period = build_canonical_text(
        reading(
            page(1, [["Un párrafo que termina justo en el margen."]], last_full=True),
            page(2, [["que no sigue."]]),
        )
    )
    assert full_with_period.text == "Un párrafo que termina justo en el margen.\nque no sigue."


def test_an_article_heading_always_starts_a_paragraph():
    """REQ-003: un renglón que empieza con un encabezado de artículo empieza siempre un
    párrafo, aunque esté pegado al renglón anterior: un encabezado solo se reconoce al
    comienzo de un renglón del texto canónico."""
    result = canonical(["Texto del artículo anterior.", "ARTÍCULO 2°.- OTRO. Texto."])

    assert result.text == "Texto del artículo anterior.\nARTÍCULO 2°.- OTRO. Texto."


def test_each_line_keeps_its_page_and_its_position_in_the_canonical_text():
    """REQ-003, REQ-004: cada renglón leído queda ubicado en el texto canónico con su
    página y su origen, para calcular las páginas y el origen de cada unidad. Una página
    no leída no aporta texto."""
    result = build_canonical_text(
        reading(
            page(1, [["Uno."]]),
            Page(number=2, width=612.0, height=792.0, status=PAGE_NOT_READ, lines=[]),
            page(3, [["Tres", "y más."]]),
        )
    )

    assert result.text == "Uno.\nTres y más."
    assert [(line.page, result.text[line.start : line.end]) for line in result.lines] == [
        (1, "Uno."),
        (3, "Tres"),
        (3, "y más."),
    ]
    assert {line.origin for line in result.lines} == {ORIGIN_PDF_TEXT}
    assert result.pages_at(5, 15) == (3, 3)
    assert result.pages_at(0, 15) == (1, 3)


def test_lines_discarded_by_the_reading_do_not_enter_the_canonical_text():
    """REQ-004: una línea que la lectura marcó como descartada (por ejemplo, navegación
    de un sitio) no entra en el texto canónico; se cuenta aparte para el informe."""
    source = page(1, [["Inicio | Buscar"], ["ARTÍCULO 1°.- Texto."]])
    source.lines[0].discarded = "navegacion"

    result = build_canonical_text(reading(source))

    assert result.text == "ARTÍCULO 1°.- Texto."
    assert result.discarded_lines == 1


def test_web_lines_without_position_are_one_paragraph_each():
    """REQ-003: una línea sin posición (página web) es un párrafo propio."""
    lines = [
        Line(text=text, x0=None, top=None, x1=None, bottom=None, origin="web")
        for text in ("Primer bloque.", "Segundo bloque.")
    ]
    web = DocumentReading(
        file_format="html",
        pages=[Page(number=None, width=None, height=None, status=PAGE_READ, lines=lines)],
        tool_versions={},
    )

    result = build_canonical_text(web)

    assert result.text == "Primer bloque.\nSegundo bloque."
    assert result.pages_at(0, 5) == (None, None)


# --- El extracto real -------------------------------------------------------------------


@pytest.fixture(scope="module")
def extract_canonical():
    return build_canonical_text(read_document(EXTRACT))


def test_extract_paragraphs_are_the_document_paragraphs(extract_canonical):
    """REQ-003: en el extracto del anexo de la 247/2022, el artículo 1 queda en dos
    párrafos, con sus renglones unidos por un espacio y el texto tal como el documento,
    y cada entrada del índice queda en un párrafo propio, aunque ocupe dos renglones."""
    paragraphs = extract_canonical.text.split("\n")

    assert (
        "ARTÍCULO 1°.- OBJETO. El presente régimen tendrá por objeto establecer los "
        "lineamientos y principios básicos que deberán ser observados en todos los "
        "procedimientos de contrataciones de bienes, servicios y obras, de modo que se "
        "realicen en forma oportuna y al menor costo posible, como así también que la venta "
        "de bienes sea efectuada al mejor postor, coadyuvando al desempeño eficiente de la "
        "Administración Federal de Ingresos Públicos y al logro de los resultados requeridos "
        "por la sociedad."
    ) in paragraphs
    assert (
        "Toda contratación de la AFIP se presumirá de índole administrativa, salvo que por "
        "sus características esté sometida a normas de derecho privado."
    ) in paragraphs
    assert "ARTÍCULO 1º.- OBJETO" in paragraphs
    assert (
        "ARTÍCULO 30.- OBSERVACIONES AL PROYECTO DE PLIEGO DE BASES Y CONDICIONES PARTICULARES"
    ) in paragraphs
    assert "a) Integridad en los procedimientos." in paragraphs
    assert paragraphs[-1] == "a) El presente régimen."
    assert extract_canonical.hyphen_joins == []


def test_canonical_text_keeps_every_word_of_the_reading(extract_canonical):
    """REQ-003: el texto canónico del extracto trae las mismas palabras que la lectura,
    en el mismo orden: las operaciones no agregan ni quitan nada."""
    source = read_document(EXTRACT)
    words = [w for p in source.pages for line in p.lines for w in line.text.split()]

    assert extract_canonical.text.split() == words


def test_same_reading_gives_the_same_canonical_text(extract_canonical):
    """REQ-003: el texto canónico es determinista: la misma lectura da el mismo texto."""
    again = build_canonical_text(read_document(EXTRACT))

    assert again.text == extract_canonical.text
    assert again.lines == extract_canonical.lines
