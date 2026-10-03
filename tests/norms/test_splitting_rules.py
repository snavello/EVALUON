"""Reglas de partición de normas (T-023; ADR-0004, "Cómo se parte" y "Encabezados y pies
que se descartan"; plan 001, "Identificación de unidades", "Texto normativo sin número de
artículo" y "Unidades base, incisos y pasajes").

Dos partes:

- **La tabla de encabezados.** Cada forma que reconoce la partición, con su variante y el
  resultado esperado. Cada regla nueva suma su fila (T-050 suma las de la 297/03 y del
  cuerpo de la 247/2022).
- **Las reglas sobre lecturas sintéticas.** Incisos de dos niveles, títulos y capítulos
  en la ruta, cláusula transitoria, anexos dentro de un cuerpo, visto y considerandos,
  cierre y firma, encabezados y pies de página, carátula, control de secuencia con margen,
  y los casos trampa: cita a un artículo en medio de un párrafo, artículo transcripto
  entre comillas, índice, artículos derogados seguidos que no son un índice, la línea
  "ANEXO (artículo 1°)" de la carátula, las palabras de la cláusula en medio de un párrafo
  y una frase en mayúsculas dentro de un artículo.

Decisión del responsable del 2026-10-03 (plan 001, "Texto normativo sin número de
artículo"): un párrafo propio que coincide con un encabezado reconocido (título,
capítulo, sección, cláusula, anexo) cierra el artículo abierto y lo que sigue hasta la
próxima unidad queda sin ubicar; un párrafo en mayúsculas que no es un encabezado
reconocido no corta: queda dentro del artículo y el informe lo señala.

Las lecturas son sintéticas y propias de cada prueba (P4).
"""

import pytest

from evaluon.norms.reading import (
    FORMAT_PDF,
    ORIGIN_PDF_TEXT,
    PAGE_READ,
    DocumentReading,
    Line,
    Page,
)
from evaluon.norms.splitting import split_document
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.norms.splitting.headings import (
    ANNEX,
    ARTICLE,
    CLAUSE,
    CONSIDERANDO_HEADING,
    FORMULA,
    INCISO,
    INDEX,
    QUE,
    SIGNATURE,
    TEXT,
    TITLE,
    UPPER,
    VISTO,
    classify_heading,
)
from evaluon.norms.splitting.partition import SEQUENCE_MARGIN

# --- Lecturas sintéticas ----------------------------------------------------------------

HEIGHT = 12.0
# Separación entre renglones de un mismo párrafo y entre párrafos, como en el anexo de la
# 247/2022.
SAME_PARAGRAPH = 13.5
NEW_PARAGRAPH = 25.5


def synthetic(*paragraph_pages):
    """Una lectura: cada argumento es una página, lista de párrafos de un renglón."""
    pages = []
    for number, paragraphs in enumerate(paragraph_pages, start=1):
        lines, top = [], 100.0
        for text in paragraphs:
            lines.append(_line(text, top))
            top += NEW_PARAGRAPH
        pages.append(_page(number, lines))
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions={"pdfplumber": "x"})


def glued(*lines):
    """Una página cuyos renglones están todos pegados, sin espacio de párrafo entre ellos:
    solo un encabezado reconocido puede empezar otro párrafo."""
    page_lines, top = [], 100.0
    for text in lines:
        page_lines.append(_line(text, top))
        top += SAME_PARAGRAPH
    return DocumentReading(file_format=FORMAT_PDF, pages=[_page(1, page_lines)], tool_versions={})


def _line(text, top, x1=300.0):
    return Line(text=text, x0=70.0, top=top, x1=x1, bottom=top + HEIGHT, origin=ORIGIN_PDF_TEXT)


def _page(number, lines):
    return Page(number=number, width=612.0, height=792.0, status=PAGE_READ, lines=lines)


def by_key(result):
    return {unit.key: unit for unit in result.units}


def keys(result):
    return [unit.key for unit in result.units]


def check_invariants(result):
    """Propiedades que se cumplen siempre (ADR-0004, "Cómo se prueba"): texto igual al
    recorte, orden creciente, claves únicas, el padre antes que el hijo, el inciso dentro
    de su padre y la cobertura completa, contando cada carácter una vez en su unidad
    base."""
    text = result.canonical_text
    seen = {}
    for unit in result.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
        if unit.parent_key is not None:
            parent = seen[unit.parent_key]
            if unit.unit_type == "inciso":
                assert parent.char_start <= unit.char_start <= unit.char_end <= parent.char_end
        seen[unit.key] = unit
    assert [unit.order for unit in result.units] == list(range(1, len(result.units) + 1))
    starts = [unit.char_start for unit in result.units if unit.char_end > unit.char_start]
    assert starts == sorted(starts)
    assert len(seen) == len(result.units)
    coverage = result.report["coverage"]
    assert coverage["total"] == len(text)
    assert (
        coverage["units"] + coverage["discarded"] + coverage["unlocated"] + coverage["separators"]
        == coverage["total"]
    )
    assert coverage["matches"] is True


# --- Tabla de encabezados (REQ-003) -----------------------------------------------------

# (párrafo, tipo, número, nombre en la ruta o etiqueta)
HEADING_TABLE = [
    # Artículo: formas del anexo de la 247/2022.
    ("ARTÍCULO 1°.- OBJETO. El presente régimen", ARTICLE, "1", "ARTÍCULO 1°.- OBJETO"),
    ("ARTÍCULO 1º.- OBJETO", ARTICLE, "1", "ARTÍCULO 1º.- OBJETO"),
    ("ARTÍCULO 10.- FORMALIDADES DE LAS ACTUACIONES. Las", ARTICLE, "10", "ARTÍCULO 10.- FORMALIDADES DE LAS ACTUACIONES"),
    ("ARTÍCULO 27.- PLIEGOS DE BASES Y CONDICIONES.", ARTICLE, "27", "ARTÍCULO 27.- PLIEGOS DE BASES Y CONDICIONES"),
    # Artículo: las demás formas de la tabla del ADR-0004.
    ("ARTICULO 1° — Apruébase el régimen", ARTICLE, "1", "ARTICULO 1° —"),
    ("ARTICULO 1.- OBJETO", ARTICLE, "1", "ARTICULO 1.- OBJETO"),
    ("ARTICULO 12.— Las ofertas", ARTICLE, "12", "ARTICULO 12.—"),
    ("ARTICULO 11. — Las ofertas", ARTICLE, "11", "ARTICULO 11. —"),
    ("ARTICULO 13 — Las ofertas", ARTICLE, "13", "ARTICULO 13 —"),
    ("Art. 2º.- Las ofertas", ARTICLE, "2", "Art. 2º.-"),
    ("Artículo 14 bis.- Texto agregado.", ARTICLE, "14 bis", "Artículo 14 bis.-"),
    ("ARTÍCULO 14 BIS.- GARANTÍAS. Texto.", ARTICLE, "14 bis", "ARTÍCULO 14 BIS.- GARANTÍAS"),
    ("ARTÍCULO 5°.- DEROGADO.", ARTICLE, "5", "ARTÍCULO 5°.- DEROGADO"),
    # Casos trampa de artículo: una cita, no un encabezado.
    ("Artículo 2° de la Ley N° 19.549, que se cita.", TEXT, "", ""),
    ("ARTÍCULO 2° DE LA LEY", UPPER, "", ""),
    ('"ARTÍCULO 3°.- TEXTO TRANSCRIPTO. Entre comillas."', TEXT, "", ""),
    # Inciso, en sus dos niveles y sus formas.
    ("a) Integridad en los procedimientos.", INCISO, "a", "a)"),
    ("ñ) Otro supuesto.", INCISO, "ñ", "ñ)"),
    ("1. Compra de bienes muebles.", INCISO, "1", "1."),
    ("12) Duodécimo supuesto.", INCISO, "12", "12)"),
    ("Inciso 1) Compras.", INCISO, "1", "Inciso 1)"),
    ("inc. a) Primero.", INCISO, "a", "inc. a)"),
    ("1.1. Invitaciones a proveedores: Para las que", TEXT, "", ""),
    ("1.000 pesos por cada día de demora.", TEXT, "", ""),
    # Título, capítulo y sección: pasan a la ruta.
    ("TÍTULO II - DE LA FORMACIÓN Y PERFECCIONAMIENTO DEL CONTRATO", TITLE, "II", "Título II"),
    ("TITULO III", TITLE, "III", "Título III"),
    ("CAPÍTULO VIII - GARANTÍAS", TITLE, "VIII", "Capítulo VIII"),
    ("SECCIÓN 1ª - REGLAS", TITLE, "1ª", "Sección 1ª"),
    ("Título II de la Ley N° 19.549.", TEXT, "", ""),
    # Cláusula: texto normativo sin número de artículo.
    ("CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES", CLAUSE, "", "Cláusula transitoria"),
    ("CLAUSULA TRANSITORIA", CLAUSE, "", "Clausula transitoria"),
    ("Cláusula transitoria: se aplica desde la publicación.", TEXT, "", ""),
    # Anexo.
    ("ANEXO", ANNEX, "", "Anexo"),
    ("ANEXO I", ANNEX, "I", "Anexo I"),
    ("ANEXO A", ANNEX, "A", "Anexo A"),
    ("ANEXO I - DISPOSICION N° 297/03 (AFIP)", ANNEX, "I", "Anexo I"),
    ("ANEXO (artículo 1°)", ANNEX, "", "Anexo"),
    ("ANEXOS DE LA PRESENTE", UPPER, "", ""),
    # Caso trampa: prosa que empieza con "ANEXO I" no es un encabezado.
    ("ANEXO I forma parte integrante de la presente disposición.", TEXT, "", ""),
    ("ANEXO II de la Resolución General citada.", TEXT, "", ""),
    # Visto, considerandos y fórmula.
    ("VISTO el Expediente Electrónico N° 1, y", VISTO, "", ""),
    ("CONSIDERANDO:", CONSIDERANDO_HEADING, "", ""),
    ("Que el artículo 2° dispone lo siguiente.", QUE, "", ""),
    ("Por ello, EL ADMINISTRADOR FEDERAL DISPONE:", FORMULA, "", ""),
    # Índice, firma y párrafos en mayúsculas sin forma reconocida.
    ("ÍNDICE:", INDEX, "", ""),
    ("Digitally signed by Gestion Documental Electronica", SIGNATURE, "", ""),
    ("Firmado digitalmente por: CASTAGNETO Carlos Daniel", SIGNATURE, "", ""),
    ("DE LAS GARANTÍAS EN GENERAL", UPPER, "", ""),
    ("Texto común de un párrafo.", TEXT, "", ""),
]


@pytest.mark.parametrize("text, kind, number, name", HEADING_TABLE)
def test_heading_table(text, kind, number, name):
    """REQ-003: cada forma de encabezado de la tabla da el tipo, el número y el nombre o
    la etiqueta esperados; las formas que solo se parecen (una cita, un texto entre
    comillas, un `1.1.`) no son encabezados."""
    heading = classify_heading(text)

    assert heading.kind == kind
    assert heading.number == number
    if kind in (ARTICLE, INCISO):
        assert heading.label == name
    elif kind in (TITLE, CLAUSE, ANNEX):
        assert heading.name == name


# --- Incisos (REQ-003) ------------------------------------------------------------------


def test_incisos_of_two_levels_are_child_units_cut_from_the_article():
    """REQ-003: los incisos de dos niveles son unidades hijas del artículo, cuyo texto es
    un recorte del texto del artículo. Un inciso va hasta el siguiente de su mismo nivel
    o de uno superior; el último de su lista no se lleva los párrafos que siguen, que son
    del inciso o del artículo que lo contiene."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- CLASES. Los procedimientos serán:",
                "a) Licitación pública.",
                "b) Subasta pública. Podrá aplicarse en los siguientes casos:",
                "1. Compra de bienes.",
                "Párrafo que sigue al punto 1.",
                "2. Venta de bienes.",
                "Párrafo final del inciso b.",
                "c) Contratación directa.",
                "Párrafo final del artículo.",
                "ARTÍCULO 2°.- OTRO. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == [
        "art-1",
        "art-1/inc-a",
        "art-1/inc-b",
        "art-1/inc-b/inc-1",
        "art-1/inc-b/inc-2",
        "art-1/inc-c",
        "art-2",
    ]
    units = by_key(result)
    assert units["art-1/inc-a"].text == "a) Licitación pública."
    assert units["art-1/inc-b"].text == (
        "b) Subasta pública. Podrá aplicarse en los siguientes casos:\n"
        "1. Compra de bienes.\nPárrafo que sigue al punto 1.\n2. Venta de bienes.\n"
        "Párrafo final del inciso b."
    )
    assert units["art-1/inc-b/inc-1"].text == "1. Compra de bienes.\nPárrafo que sigue al punto 1."
    assert units["art-1/inc-b/inc-2"].text == "2. Venta de bienes."
    assert units["art-1/inc-c"].text == "c) Contratación directa."
    assert units["art-1"].text.endswith("c) Contratación directa.\nPárrafo final del artículo.")

    second = units["art-1/inc-b/inc-1"]
    assert (second.unit_type, second.number, second.label) == ("inciso", "1", "1.")
    assert second.parent_key == "art-1/inc-b"
    assert second.path == "Artículo 1 › Inciso b › Inciso 1"
    assert units["art-1/inc-b"].parent_key == "art-1"
    assert units["art-1/inc-b"].label == "b)"
    check_invariants(result)


def test_inciso_forms_of_the_297_nest_with_letters():
    """REQ-003: `Inciso 1)` con letras `a)` adentro da las claves del plan
    (`art-14/inc-1/inc-a`)."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- MODALIDADES. Son:",
                "Inciso 1) Compras.",
                "a) Primera.",
                "b) Segunda.",
                "Inciso 2) Ventas.",
            ]
        ),
        part="anexo-i",
    )

    assert keys(result)[2:] == [
        "anexo-i/art-2",
        "anexo-i/art-2/inc-1",
        "anexo-i/art-2/inc-1/inc-a",
        "anexo-i/art-2/inc-1/inc-b",
        "anexo-i/art-2/inc-2",
    ]
    assert by_key(result)["anexo-i/art-2/inc-1/inc-a"].path == (
        "Anexo I › Artículo 2 › Inciso 1 › Inciso a"
    )
    check_invariants(result)


def test_an_inciso_out_of_sequence_is_not_a_unit():
    """REQ-003: los incisos también siguen su secuencia: un `c)` después de un `a)` (por
    ejemplo, un renglón que cita "el inciso c) del artículo") no abre una unidad y queda
    dentro del inciso anterior; un `1.1.` no es un inciso de tercer nivel."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Son:",
                "a) Primero, según:",
                "1. Punto uno.",
                "1.1. Subpunto que queda en el texto del punto.",
                "c) del artículo 5 se aplica igual.",
                "b) Segundo.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-1/inc-a", "art-1/inc-a/inc-1", "art-1/inc-b"]
    # El punto 1 es el último de su lista: lo que le sigue es del inciso a.
    assert by_key(result)["art-1/inc-a/inc-1"].text == "1. Punto uno."
    assert by_key(result)["art-1/inc-a"].text.endswith(
        "1. Punto uno.\n1.1. Subpunto que queda en el texto del punto.\n"
        "c) del artículo 5 se aplica igual."
    )
    check_invariants(result)


def test_coverage_counts_each_character_once_in_its_base_unit():
    """REQ-003, REQ-004: los incisos repiten texto de su artículo; el control de
    cobertura cuenta cada carácter una vez, en su unidad base."""
    result = split_document(
        synthetic(["ARTÍCULO 1°.- UNO. Son:", "a) Primero.", "b) Segundo."]), part="cuerpo"
    )

    coverage = result.report["coverage"]
    assert coverage["units"] == len(by_key(result)["art-1"].text)
    assert coverage["matches"] is True


# --- Títulos y capítulos en la ruta (REQ-003) -------------------------------------------


def test_titles_and_chapters_go_to_the_path_and_are_not_units():
    """REQ-003: títulos, capítulos y secciones no son unidades: pasan a la ruta de las
    unidades que contienen. Un título nuevo cierra el capítulo anterior. La clave no los
    lleva. El encabezado se informa como descartado, con su motivo."""
    result = split_document(
        synthetic(
            [
                "TÍTULO I - DISPOSICIONES GENERALES",
                "ARTÍCULO 1°.- UNO. Son:",
                "a) Primero.",
                "TÍTULO II - DE LA FORMACIÓN",
                "CAPÍTULO I - PROCEDIMIENTOS",
                "ARTÍCULO 2°.- DOS. Texto.",
                "CAPÍTULO II - PLIEGOS",
                "SECCIÓN 1ª - GENERALES",
                "ARTÍCULO 3°.- TRES. Texto.",
                "TÍTULO III - EJECUCIÓN",
                "ARTÍCULO 4°.- CUATRO. Texto.",
            ]
        ),
        part="anexo",
    )

    units = by_key(result)
    assert keys(result) == [
        "anexo",
        "anexo/art-1",
        "anexo/art-1/inc-a",
        "anexo/art-2",
        "anexo/art-3",
        "anexo/art-4",
    ]
    assert units["anexo/art-1"].path == "Anexo › Título I › Artículo 1"
    assert units["anexo/art-1/inc-a"].path == "Anexo › Título I › Artículo 1 › Inciso a"
    assert units["anexo/art-1"].text == "ARTÍCULO 1°.- UNO. Son:\na) Primero."
    assert units["anexo/art-2"].path == "Anexo › Título II › Capítulo I › Artículo 2"
    assert units["anexo/art-3"].path == "Anexo › Título II › Capítulo II › Sección 1ª › Artículo 3"
    assert units["anexo/art-4"].path == "Anexo › Título III › Artículo 4"
    reasons = [(item["reason"], item["first_words"]) for item in result.report["discarded"]]
    assert ("titulo", "TÍTULO II - DE LA FORMACIÓN") in reasons
    assert result.report["unlocated"] == []
    check_invariants(result)


def test_a_recognized_heading_closes_the_article_and_what_follows_is_unlocated():
    """REQ-003, REQ-004 (decisión del responsable del 2026-10-03): un párrafo propio que
    coincide con un encabezado reconocido cierra el artículo abierto, y lo que sigue
    hasta la próxima unidad queda sin ubicar, con su página y sus primeras palabras: un
    título nunca termina dentro de la cita de un artículo."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto del uno.",
                "CAPÍTULO II - PLIEGOS",
                "Texto suelto después del capítulo.",
                "ARTÍCULO 2°.- DOS. Texto del dos.",
            ]
        ),
        part="cuerpo",
    )

    units = by_key(result)
    assert units["art-1"].text == "ARTÍCULO 1°.- UNO. Texto del uno."
    assert units["art-2"].path == "Capítulo II › Artículo 2"
    assert [(item["page"], item["first_words"]) for item in result.report["unlocated"]] == [
        (1, "Texto suelto después del capítulo.")
    ]
    check_invariants(result)


def test_an_uppercase_phrase_inside_an_article_stays_inside_and_is_reported():
    """REQ-003, REQ-004 (caso trampa; decisión del responsable del 2026-10-03): un
    párrafo en mayúsculas que no es un encabezado reconocido no corta el artículo: queda
    dentro, nada queda sin ubicar, y el informe lo señala para que lo revise la persona
    que valida."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- GARANTÍAS. Los oferentes deberán constituir:",
                "DE LAS GARANTÍAS EN GENERAL",
                "Texto que sigue dentro del artículo.",
                "ARTÍCULO 2°.- DOS. Texto.",
            ]
        ),
        part="cuerpo",
    )

    units = by_key(result)
    assert units["art-1"].text == (
        "ARTÍCULO 1°.- GARANTÍAS. Los oferentes deberán constituir:\n"
        "DE LAS GARANTÍAS EN GENERAL\nTexto que sigue dentro del artículo."
    )
    assert result.report["unlocated"] == []
    assert result.report["uppercase_in_units"] == [
        {"key": "art-1", "page": 1, "first_words": "DE LAS GARANTÍAS EN GENERAL"}
    ]
    assert "DE LAS GARANTÍAS EN GENERAL" in result.report_text
    check_invariants(result)


# --- Cláusula: texto normativo sin número de artículo (REQ-003) -------------------------


def test_a_transitory_clause_is_a_unit_of_its_own():
    """REQ-003: la cláusula transitoria es una unidad `clausula`, sin número, con el
    encabezado completo como etiqueta, clave `anexo/clausula-transitoria` y ruta
    "Anexo › Cláusula transitoria", sin el título abierto. Su encabezado cierra el
    artículo anterior y los títulos; la unidad trae sus párrafos."""
    result = split_document(
        synthetic(
            [
                "TÍTULO VII - MÓDULO",
                "ARTÍCULO 1°.- VALOR DEL MÓDULO. Texto del módulo.",
                "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES",
                "Las unidades en las que aún no se hubiere implementado el registro.",
                "Ello con excepción del requisito de incorporación.",
            ]
        ),
        part="anexo",
    )

    units = by_key(result)
    article, clause = units["anexo/art-1"], units["anexo/clausula-transitoria"]
    assert keys(result)[-1] == "anexo/clausula-transitoria"
    assert (clause.unit_type, clause.number, clause.parent_key) == ("clausula", "", "anexo")
    assert clause.label == "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES"
    assert clause.path == "Anexo › Cláusula transitoria"
    assert clause.text == (
        "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES\n"
        "Las unidades en las que aún no se hubiere implementado el registro.\n"
        "Ello con excepción del requisito de incorporación."
    )
    assert article.text == "ARTÍCULO 1°.- VALOR DEL MÓDULO. Texto del módulo."
    assert article.char_end + 1 == clause.char_start
    assert result.report["unlocated"] == []
    check_invariants(result)


def test_a_clause_stays_out_of_the_article_sequence_and_repeats_with_its_order():
    """REQ-003: la cláusula no entra en el control de secuencia: si después viene un
    artículo, sigue la numeración de su contenedor. Una segunda cláusula con el mismo
    nombre lleva su número de orden en la clave."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "CLÁUSULA TRANSITORIA",
                "Primera cláusula.",
                "ARTÍCULO 2°.- DOS. Texto.",
                "CLAUSULA TRANSITORIA SEGUNDA",
                "Segunda cláusula.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "clausula-transitoria", "art-2", "clausula-transitoria-2"]
    assert by_key(result)["clausula-transitoria-2"].path == "Clausula transitoria"
    check_invariants(result)


def test_the_clause_words_inside_a_paragraph_do_not_open_a_unit():
    """REQ-003 (caso trampa): las mismas palabras en medio de un párrafo, o al comienzo
    de un párrafo que no está en mayúsculas, no abren una unidad."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Lo dispuesto en la CLÁUSULA TRANSITORIA REGISTRO DE "
                "PROVEEDORES rige igual.",
                "Cláusula transitoria: se aplica desde la publicación.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1"]
    assert by_key(result)["art-1"].text.endswith("\nCláusula transitoria: se aplica desde la publicación.")


# --- Anexos (REQ-003) -------------------------------------------------------------------


def test_annexes_inside_a_body_with_and_without_articles():
    """REQ-003: en un documento cargado como cuerpo, un encabezado "ANEXO" después del
    articulado abre una unidad `anexo`, que vuelve a numerar sus artículos. Un anexo con
    artículos tiene como texto propio su encabezado y lo que hay antes del primer
    artículo; un anexo sin artículos tiene todo su texto."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- Apruébase el régimen.",
                "ARTÍCULO 2°.- Comuníquese.",
                "ANEXO I - RÉGIMEN",
                "Texto propio del anexo.",
                "ARTÍCULO 1°.- OBJETO. Texto del anexo.",
                "ARTÍCULO 2°.- ÁMBITO. Son:",
                "a) Primero.",
                "ANEXO II",
                "Tabla de valores sin artículos.",
                "Otra línea de la tabla.",
            ]
        ),
        part="cuerpo",
    )

    units = by_key(result)
    assert keys(result) == [
        "art-1",
        "art-2",
        "anexo-i",
        "anexo-i/art-1",
        "anexo-i/art-2",
        "anexo-i/art-2/inc-a",
        "anexo-ii",
    ]
    annex = units["anexo-i"]
    assert (annex.unit_type, annex.number, annex.path, annex.parent_key) == ("anexo", "I", "Anexo I", None)
    assert annex.label == "ANEXO I - RÉGIMEN"
    assert annex.text == "ANEXO I - RÉGIMEN\nTexto propio del anexo."
    assert units["anexo-i/art-1"].path == "Anexo I › Artículo 1"
    assert units["anexo-i/art-1"].parent_key == "anexo-i"
    assert units["art-2"].text == "ARTÍCULO 2°.- Comuníquese."
    assert units["anexo-ii"].text == "ANEXO II\nTabla de valores sin artículos.\nOtra línea de la tabla."
    containers = result.report["units"]["by_container"]
    assert [(c["container"], c["articulo"]) for c in containers] == [
        ("Cuerpo", 2),
        ("Anexo I", 2),
        ("Anexo II", 0),
    ]
    check_invariants(result)


def test_the_annex_line_of_the_cover_names_an_article_without_being_one():
    """REQ-003 (caso trampa): la línea "ANEXO (artículo 1°)" de la carátula nombra un
    artículo sin serlo: no produce un artículo ni abre otro contenedor; en un documento
    cargado como anexo es la etiqueta de la unidad raíz."""
    result = split_document(
        synthetic(["ANEXO (artículo 1°)", "RÉGIMEN GENERAL", "ARTÍCULO 1°.- OBJETO. Texto."]),
        part="anexo",
    )

    assert keys(result) == ["anexo", "anexo/art-1"]
    root = result.units[0]
    assert root.label == "ANEXO (artículo 1°)"
    assert root.text == "ANEXO (artículo 1°)\nRÉGIMEN GENERAL"
    check_invariants(result)


@pytest.mark.parametrize(
    "part, expected",
    [("cuerpo", ["art-1", "art-2"]), ("anexo", ["anexo", "anexo/art-1", "anexo/art-2"])],
)
def test_a_paragraph_that_starts_with_annex_in_prose_does_not_open_an_annex(part, expected):
    """REQ-003 (caso trampa): un párrafo en prosa que empieza con "ANEXO I" ("ANEXO I
    forma parte integrante...") no es un encabezado de anexo, igual que las palabras de
    un título o de una cláusula fuera de un párrafo en mayúsculas: queda dentro del
    artículo, no abre un anexo ni queda sin ubicar, como cuerpo y como anexo."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- Apruébase el régimen que se detalla a continuación:",
                "ANEXO I forma parte integrante de la presente disposición.",
                "ARTÍCULO 2°.- Comuníquese.",
            ]
        ),
        part=part,
    )

    assert keys(result) == expected
    first = by_key(result)[expected[-2]]
    assert first.text.endswith("\nANEXO I forma parte integrante de la presente disposición.")
    assert result.report["unlocated"] == []
    containers = [c["container"] for c in result.report["units"]["by_container"]]
    assert containers == (["Cuerpo"] if part == "cuerpo" else ["Anexo"])
    check_invariants(result)


def test_considerandos_are_only_of_the_body():
    """REQ-003: el visto y los considerandos son solo del cuerpo, antes del primer
    artículo. En un documento cargado como anexo, un párrafo que empieza con "Que"
    después de un artículo es texto del artículo, no un considerando."""
    result = split_document(
        synthetic(
            [
                "ANEXO (artículo 1°)",
                "ARTÍCULO 1°.- REQUISITOS. Serán requisitos de la oferta:",
                "Que el oferente esté inscripto en el registro.",
                "ARTÍCULO 2°.- DOS. Texto.",
            ]
        ),
        part="anexo",
    )

    assert keys(result) == ["anexo", "anexo/art-1", "anexo/art-2"]
    assert by_key(result)["anexo/art-1"].text.endswith(
        "\nQue el oferente esté inscripto en el registro."
    )
    assert "considerando" not in result.report["units"]["by_type"]
    check_invariants(result)


# --- Carátula, encabezados y pies de página (REQ-003, REQ-004) --------------------------


def test_the_letterhead_and_the_gde_data_of_the_cover_are_discarded():
    """REQ-003, REQ-004: el membrete y los datos GDE de la carátula ("Número:",
    "Referencia:") son una forma conocida: se descartan, se informan con su motivo y no
    quedan en el texto de la unidad raíz."""
    result = split_document(
        synthetic(
            [
                'Administración Federal de Ingresos Públicos 2022 - "Las Malvinas son argentinas"',
                "ANEXO",
                "Número:",
                "Referencia: Régimen general para contrataciones. ANEXO.",
                "ANEXO (artículo 1°)",
                "RÉGIMEN GENERAL",
                "ARTÍCULO 1°.- OBJETO. Texto.",
            ]
        ),
        part="anexo",
    )

    root = result.units[0]
    assert root.text == "ANEXO (artículo 1°)\nRÉGIMEN GENERAL"
    cover = result.report["discarded"][0]
    assert cover["reason"] == "caratula"
    assert cover["char_start"] == 0
    assert result.canonical_text[cover["char_start"] : cover["char_end"]].endswith(
        "Referencia: Régimen general para contrataciones. ANEXO."
    )
    assert "Carátula" in result.report_text
    check_invariants(result)


def test_repeated_page_headers_and_footers_are_discarded():
    """REQ-003, REQ-004: en PDF, los renglones de la franja superior o inferior que se
    repiten en la mayoría de las páginas (ignorando los números) y las formas conocidas
    (número de página, dirección web que agrega el navegador) no entran en el texto
    canónico: el artículo que cruza la página queda entero y las líneas se cuentan."""
    pages = []
    for number, body in enumerate(
        (
            ["ARTÍCULO 1°.- UNO. Texto que sigue en la", "página siguiente"],
            ["sin cortarse.", "ARTÍCULO 2°.- DOS. Texto."],
            ["ARTÍCULO 3°.- TRES. Texto."],
        ),
        start=1,
    ):
        lines = [_line(f"IF-2022-0012345{number}-APN-DI#AFIP", 20.0)]
        top = 100.0
        for text in body:
            lines.append(_line(text, top, x1=595.0))
            top += SAME_PARAGRAPH
        lines.append(_line(f"Página {number} de 3", 760.0))
        if number == 2:
            lines.append(_line("https://www.boletinoficial.gob.ar/detalleAviso/primera/1", 775.0))
        pages.append(_page(number, lines))
    reading = DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions={})

    canonical = build_canonical_text(reading)
    result = split_document(reading, part="cuerpo")

    assert "IF-2022" not in canonical.text and "Página" not in canonical.text
    assert "https://" not in canonical.text
    assert canonical.discarded_lines == 7
    assert by_key(result)["art-1"].text == (
        "ARTÍCULO 1°.- UNO. Texto que sigue en la página siguiente sin cortarse."
    )
    assert result.report["discarded_lines"] == 7
    check_invariants(result)


def test_a_line_in_the_band_that_does_not_repeat_is_kept():
    """REQ-003: un renglón de la franja superior que no se repite y no tiene una forma
    conocida es texto del documento (el anexo de la 247/2022 empieza sus páginas con
    artículos)."""
    reading = DocumentReading(
        file_format=FORMAT_PDF,
        pages=[
            _page(1, [_line("ARTÍCULO 1°.- UNO. Texto.", 20.0)]),
            _page(2, [_line("ARTÍCULO 2°.- DOS. Texto.", 20.0)]),
        ],
        tool_versions={},
    )

    assert keys(split_document(reading, part="cuerpo")) == ["art-1", "art-2"]


def _three_pages(extra):
    """Tres páginas con un artículo cada una, más los renglones `extra(número)`: pares
    (texto, altura del renglón)."""
    pages = []
    for number, name in enumerate(("UNO", "DOS", "TRES"), start=1):
        lines = [_line(f"ARTÍCULO {number}°.- {name}. Texto del artículo.", 100.0)]
        lines += [_line(text, top) for text, top in extra(number)]
        lines.sort(key=lambda line: line.top)
        pages.append(_page(number, lines))
    return DocumentReading(file_format=FORMAT_PDF, pages=pages, tool_versions={})


def test_repeated_lines_in_the_band_without_a_known_form_are_discarded():
    """REQ-003, REQ-004: un renglón de la franja superior o inferior que se repite en la
    mayoría de las páginas (ignorando los números) se descarta aunque no tenga una forma
    conocida: un membrete arriba, el nombre de la norma con su número de hoja al pie. Se
    informa con su motivo."""
    reading = _three_pages(
        lambda number: [
            ("Administración Federal de Ingresos Públicos", 20.0),
            (f"Disposición de prueba - hoja {number}", 770.0),
        ]
    )

    canonical = build_canonical_text(reading)
    result = split_document(reading, part="cuerpo")

    assert "Administración Federal" not in canonical.text
    assert "hoja" not in canonical.text
    assert by_key(result)["art-2"].text == "ARTÍCULO 2°.- DOS. Texto del artículo."
    reasons = [(line["reason"], line["page"]) for line in result.report["discarded_line_list"]]
    assert sorted(reasons) == [("encabezado_o_pie", n) for n in (1, 1, 2, 2, 3, 3)]
    check_invariants(result)


def test_a_repeated_line_outside_the_band_is_kept():
    """REQ-003: un renglón que se repite en todas las páginas pero está fuera de la
    franja superior e inferior es texto del documento y se conserva."""
    reading = _three_pages(lambda number: [("Sin modificaciones en este punto.", 400.0)])

    canonical = build_canonical_text(reading)
    result = split_document(reading, part="cuerpo")

    assert canonical.text.count("Sin modificaciones en este punto.") == 3
    assert by_key(result)["art-2"].text == (
        "ARTÍCULO 2°.- DOS. Texto del artículo.\nSin modificaciones en este punto."
    )
    assert canonical.discarded_lines == 0
    check_invariants(result)


# --- Forzar párrafo en los encabezados (REQ-003) ----------------------------------------


def test_inciso_title_and_clause_headings_start_a_paragraph_even_without_spacing():
    """REQ-003: un renglón que empieza con un encabezado de inciso (después de un renglón
    que cierra con punto, dos puntos o punto y coma), de título o de cláusula empieza un
    párrafo aunque esté pegado al anterior. Un `b)` que sigue a "del inciso" es una cita
    partida por el renglón: no empieza un párrafo."""
    canonical = build_canonical_text(
        glued(
            "ARTÍCULO 1°.- UNO. Son los siguientes:",
            "a) Primero, conforme lo previsto en el inciso",
            "b) del presente artículo;",
            "b) Segundo.",
            "TÍTULO II - DE LA FORMACIÓN",
            "ARTÍCULO 2°.- DOS. Texto.",
            "CLÁUSULA TRANSITORIA",
            "Texto de la cláusula.",
        )
    )

    assert canonical.text.split("\n") == [
        "ARTÍCULO 1°.- UNO. Son los siguientes:",
        "a) Primero, conforme lo previsto en el inciso b) del presente artículo;",
        "b) Segundo.",
        "TÍTULO II - DE LA FORMACIÓN",
        "ARTÍCULO 2°.- DOS. Texto.",
        "CLÁUSULA TRANSITORIA",
        "Texto de la cláusula.",
    ]


# --- Visto, considerandos, cierre y firma (REQ-003) -------------------------------------


def test_visto_and_each_considerando_paragraph_are_units():
    """REQ-003: el visto es una unidad `considerando` con clave `visto`; cada párrafo que
    empieza con "Que" es una unidad `considerando`, numerada por orden
    (`considerando-1`); un párrafo que no empieza con "Que" sigue al considerando
    anterior. La fórmula "Por ello" no es un considerando y queda a la vista como no
    ubicada."""
    result = split_document(
        synthetic(
            [
                "VISTO el Expediente Electrónico N° 1, y",
                "CONSIDERANDO:",
                "Que el primer fundamento.",
                "Que el segundo fundamento:",
                "Continuación del segundo.",
                "Por ello, EL ADMINISTRADOR FEDERAL DISPONE:",
                "ARTÍCULO 1°.- Apruébase el régimen.",
                "ARTÍCULO 2°.- Comuníquese.",
            ]
        ),
        part="cuerpo",
    )

    units = by_key(result)
    assert keys(result) == ["visto", "considerando-1", "considerando-2", "art-1", "art-2"]
    visto = units["visto"]
    assert (visto.unit_type, visto.number, visto.label, visto.path) == (
        "considerando",
        "",
        "VISTO",
        "Visto",
    )
    first = units["considerando-1"]
    assert (first.unit_type, first.number, first.label, first.path) == (
        "considerando",
        "1",
        "Considerando 1",
        "Considerando 1",
    )
    assert first.text == "CONSIDERANDO:\nQue el primer fundamento."
    assert units["considerando-2"].text == "Que el segundo fundamento:\nContinuación del segundo."
    assert [item["first_words"] for item in result.report["unlocated"]] == [
        "Por ello, EL ADMINISTRADOR FEDERAL DISPONE:"
    ]
    check_invariants(result)


def test_closing_and_signature_are_not_added_to_the_last_unit():
    """REQ-003: el cierre y la firma no se suman a la última unidad: la firma digital
    cierra la unidad abierta y queda a la vista como no ubicada."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "CLÁUSULA TRANSITORIA",
                "Texto de la cláusula.",
                "Digitally signed by Gestion Documental Electronica",
                "Date: 2022.11.29 10:00:00 -03:00",
            ]
        ),
        part="cuerpo",
    )

    assert by_key(result)["clausula-transitoria"].text == "CLÁUSULA TRANSITORIA\nTexto de la cláusula."
    assert [item["first_words"] for item in result.report["unlocated"]] == [
        "Digitally signed by Gestion Documental Electronica Date: 2022.11.29"
    ]
    check_invariants(result)


# --- Control de secuencia, saltos y repeticiones (REQ-003, REQ-004) ---------------------


def test_a_forward_jump_within_the_margin_is_accepted_and_reported():
    """REQ-003, REQ-004: si se pierde un encabezado, el artículo siguiente se acepta
    igual cuando el salto está dentro del margen, y el informe dice qué números faltan;
    así no se manda todo el resto al artículo anterior."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- DOS. Texto.",
                "ARTÍCULO 4°.- CUATRO. Texto.",
                "ARTÍCULO 5°.- CINCO. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-4", "art-5"]
    sequence = result.report["sequence"]
    assert sequence == [{"container": "Cuerpo", "key": "", "gaps": ["3"], "not_accepted": []}]
    assert "faltan los números 3" in result.report_text
    check_invariants(result)


def test_a_jump_beyond_the_margin_stays_inside_and_is_reported():
    """REQ-003, REQ-004: un encabezado que salta más allá del margen o repite un número
    ya aceptado no abre una unidad: queda dentro del artículo abierto, y el informe lo
    señala con su número y su página."""
    far = 3 + SEQUENCE_MARGIN + 1
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- DOS. Texto.",
                f"ARTÍCULO {far}.- LEJANO. Texto.",
                "ARTÍCULO 2°.- REPETIDO. Texto.",
                "ARTÍCULO 3°.- TRES. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3"]
    assert by_key(result)["art-2"].text.endswith("\nARTÍCULO 2°.- REPETIDO. Texto.")
    assert result.report["sequence"][0]["not_accepted"] == [
        {"number": str(far), "page": 1, "inside": "art-2"},
        {"number": "2", "page": 1, "inside": "art-2"},
    ]
    check_invariants(result)


def test_bis_articles_follow_their_base_number():
    """REQ-003: `14 bis` se acepta después del 14 sin mover la secuencia; su clave es
    `art-14-bis` y su ruta "Artículo 14 bis"."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 1° BIS.- UNO BIS. Texto.",
                "ARTÍCULO 2°.- DOS. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-1-bis", "art-2"]
    bis = by_key(result)["art-1-bis"]
    assert (bis.number, bis.path) == ("1 bis", "Artículo 1 bis")
    check_invariants(result)


# --- Casos trampa del ADR-0004 (REQ-003) ------------------------------------------------


def test_a_transcribed_article_between_quotes_stays_inside():
    """REQ-003 (caso trampa): el artículo que una norma transcribe entre comillas queda
    dentro de la unidad que lo transcribe, aunque su número sea el siguiente de la
    secuencia."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Texto.",
                "ARTÍCULO 2°.- Sustitúyese el artículo 3° por el siguiente:",
                '"ARTÍCULO 3°.- NUEVO. Texto transcripto."',
                "ARTÍCULO 3°.- Comuníquese.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3"]
    assert by_key(result)["art-2"].text.endswith('\n"ARTÍCULO 3°.- NUEVO. Texto transcripto."')
    assert by_key(result)["art-3"].text == "ARTÍCULO 3°.- Comuníquese."


def test_a_citation_in_the_middle_of_a_paragraph_does_not_open_a_unit():
    """REQ-003 (caso trampa): la mención de un artículo en medio de un párrafo, o un
    párrafo que empieza con "Artículo 5° de la Ley", no abre una unidad."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Según el ARTÍCULO 2°.- de la ley citada.",
                "Artículo 5° de la Ley N° 24.156, que se cita.",
                "ARTÍCULO 2°.- DOS. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2"]


def test_the_index_produces_no_units_and_its_titles_do_not_enter_the_path():
    """REQ-003 (caso trampa): el índice repite los encabezados sin texto, con los
    títulos intercalados: se descarta y se informa; sus títulos no pasan a la ruta."""
    result = split_document(
        synthetic(
            [
                "ÍNDICE:",
                "TÍTULO I - GENERALES",
                "ARTÍCULO 1º.- OBJETO",
                "CAPÍTULO IX - INDICE",
                "ARTÍCULO 2º.- ÁMBITO",
                "TÍTULO I - GENERALES",
                "ARTÍCULO 1°.- OBJETO. Texto.",
                "ARTÍCULO 2°.- ÁMBITO. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2"]
    assert by_key(result)["art-2"].path == "Título I › Artículo 2"
    index = [item for item in result.report["discarded"] if item["reason"] == "indice"]
    assert len(index) == 1
    assert result.canonical_text[index[0]["char_start"] : index[0]["char_end"]].endswith(
        "ARTÍCULO 2º.- ÁMBITO"
    )
    check_invariants(result)


def test_derogated_articles_in_a_row_are_not_an_index():
    """REQ-003 (caso trampa): dos artículos seguidos que solo tienen su encabezado (por
    ejemplo, "DEROGADO") no son un índice si sus números no se repiten después: son
    artículos, al comienzo o en medio del articulado."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- DEROGADO.",
                "ARTÍCULO 2°.- DEROGADO.",
                "ARTÍCULO 3°.- TRES. Texto.",
                "ARTÍCULO 4°.- DEROGADO.",
                "ARTÍCULO 5°.- DEROGADO.",
                "ARTÍCULO 6°.- SEIS. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == [f"art-{n}" for n in range(1, 7)]
    assert by_key(result)["art-4"].text == "ARTÍCULO 4°.- DEROGADO."
    assert result.report["discarded"] == []
    check_invariants(result)


def test_derogated_articles_are_not_an_index_because_an_annex_renumbers():
    """REQ-003 (caso trampa): la repetición de números que delata un índice tiene que
    darse dentro del mismo contenedor. Dos artículos "DEROGADO" seguidos en el cuerpo no
    son un índice porque un anexo que viene después vuelva a numerar desde 1."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- Apruébase el régimen.",
                "ARTÍCULO 2°.- DEROGADO.",
                "ARTÍCULO 3°.- DEROGADO.",
                "ARTÍCULO 4°.- Comuníquese.",
                "ANEXO I",
                "ARTÍCULO 1°.- OBJETO. Texto.",
                "ARTÍCULO 2°.- ÁMBITO. Texto.",
                "ARTÍCULO 3°.- PLAZOS. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == [
        "art-1",
        "art-2",
        "art-3",
        "art-4",
        "anexo-i",
        "anexo-i/art-1",
        "anexo-i/art-2",
        "anexo-i/art-3",
    ]
    assert by_key(result)["art-2"].text == "ARTÍCULO 2°.- DEROGADO."
    assert result.report["discarded"] == []
    assert result.report["unlocated"] == []
    check_invariants(result)


def test_an_index_inside_an_annex_of_the_body_is_still_an_index():
    """REQ-003: el índice de un anexo dentro del cuerpo se reconoce, porque sus números
    se repiten dentro del mismo anexo."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- Apruébase el régimen.",
                "ARTÍCULO 2°.- Comuníquese.",
                "ANEXO I",
                "ÍNDICE:",
                "ARTÍCULO 1°.- OBJETO",
                "ARTÍCULO 2°.- ÁMBITO",
                "ARTÍCULO 1°.- OBJETO. Texto.",
                "ARTÍCULO 2°.- ÁMBITO. Texto.",
            ]
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "anexo-i", "anexo-i/art-1", "anexo-i/art-2"]
    assert [item["reason"] for item in result.report["discarded"]] == ["indice"]
    check_invariants(result)


# --- Párrafos después del último inciso (REQ-003, REQ-004) ------------------------------


def test_paragraphs_after_the_last_inciso_are_reported():
    """REQ-003, REQ-004: el PDF no distingue sangrías, así que los párrafos sin
    encabezado que siguen al último inciso de una lista pueden ser del inciso o del
    artículo. Quedan en el artículo, y el informe señala el inciso y cuántos párrafos
    quedaron en el artículo, para que lo revise quien valida."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Son:",
                "a) Primero.",
                "b) Segundo.",
                "Primer párrafo que sigue.",
                "Segundo párrafo que sigue.",
                "ARTÍCULO 2°.- DOS. Son:",
                "a) Primero.",
                "b) Segundo.",
            ]
        ),
        part="cuerpo",
    )

    assert by_key(result)["art-1/inc-b"].text == "b) Segundo."
    assert by_key(result)["art-1"].text.endswith("\nSegundo párrafo que sigue.")
    assert result.report["after_last_inciso"] == [
        {"key": "art-1/inc-b", "inside": "art-1", "paragraphs": 2, "page": 1}
    ]
    assert "Párrafos después del último inciso de una lista" in result.report_text
    assert "art-1/inc-b, página 1: 2 párrafos quedaron en art-1" in result.report_text
    check_invariants(result)


def test_paragraphs_after_the_last_point_of_an_inciso_are_reported_inside_the_inciso():
    """REQ-003, REQ-004: lo mismo en el segundo nivel: los párrafos que siguen al último
    punto de un inciso quedan en el inciso, y el informe los señala con la clave del
    punto."""
    result = split_document(
        synthetic(
            [
                "ARTÍCULO 1°.- UNO. Son:",
                "a) Primero, según:",
                "1. Punto uno.",
                "2. Punto dos.",
                "Párrafo que sigue al punto dos.",
                "b) Segundo.",
            ]
        ),
        part="cuerpo",
    )

    assert result.report["after_last_inciso"] == [
        {"key": "art-1/inc-a/inc-2", "inside": "art-1/inc-a", "paragraphs": 1, "page": 1}
    ]
    assert "art-1/inc-a/inc-2, página 1: 1 párrafo quedó en art-1/inc-a" in result.report_text


def test_a_list_without_paragraphs_after_its_last_inciso_is_not_reported():
    """REQ-004: si el último inciso no tiene párrafos después, no hay nada que revisar."""
    result = split_document(
        synthetic(["ARTÍCULO 1°.- UNO. Son:", "a) Primero.", "b) Segundo.", "ARTÍCULO 2°.- DOS."]),
        part="cuerpo",
    )

    assert result.report["after_last_inciso"] == []
    assert "Párrafos después del último inciso" not in result.report_text


# --- Encabezados leídos por reconocimiento sobre imagen (REQ-003, REQ-015) --------------

OCR_SUBSTITUTES = ["”", "*", "%", "'", '"', "?", "”%", "O", "", " "]


def ocr_synthetic(*paragraphs, origin="ocr"):
    """Una lectura de una página cuyos renglones vienen de reconocimiento (`ocr`, con su
    confianza) o, para comparar, de texto del PDF."""
    lines, top = [], 100.0
    for text in paragraphs:
        line = _line(text, top)
        line.origin = origin
        if origin == "ocr":
            line.confidence = 88.0
        lines.append(line)
        top += NEW_PARAGRAPH
    return DocumentReading(file_format=FORMAT_PDF, pages=[_page(1, lines)], tool_versions={})


@pytest.mark.parametrize("substitute", OCR_SUBSTITUTES)
def test_ocr_article_headings_accept_the_substitutes_of_the_degree_sign(substitute):
    """REQ-003, REQ-015: Tesseract no reconoce `°` ni `º`. En un párrafo de origen `ocr`,
    el encabezado se reconoce con cualquiera de `” * % ' " O` en su lugar, sin signo, o
    con un espacio antes del `.-`."""
    text = f"ARTÍCULO 1{substitute}.- OBJETO. El presente régimen."

    heading = classify_heading(text, ocr=True)

    assert (heading.kind, heading.number, heading.article_number) == (ARTICLE, "1", 1)


@pytest.mark.parametrize("substitute", ["”", "*", "%", "'", '"', "O"])
def test_pdf_text_and_web_keep_the_strict_article_rule(substitute):
    """REQ-003: en texto de PDF o de página web la regla queda estricta: los signos
    sustitutos del reconocimiento no forman un encabezado."""
    text = f"ARTÍCULO 1{substitute}.- OBJETO. El presente régimen."

    assert classify_heading(text).kind != ARTICLE
    assert classify_heading(text, ocr=False).kind != ARTICLE


def test_an_ocr_heading_with_a_misread_number_is_accepted_by_sequence_and_marked():
    """REQ-003, REQ-015: en un párrafo `ocr`, un encabezado cuyo número no se puede leer
    (`$0` por `80`) o no es el esperado, pero está donde corresponde por la secuencia
    (el siguiente encabezado sigue la numeración), se acepta como el siguiente y queda
    marcado como encabezado dudoso en el informe, para que lo revise la persona que
    valida."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1”.- UNO. Texto.",
            "ARTÍCULO 2*.- DOS. Texto.",
            "ARTÍCULO $”.- TRES. Texto.",
            "ARTÍCULO 9%.- CUATRO. Texto.",
            "ARTÍCULO 5.- CINCO. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3", "art-4", "art-5"]
    units = by_key(result)
    assert units["art-3"].label == "ARTÍCULO $”.- TRES"
    assert units["art-3"].text_origin == "ocr"
    assert result.report["doubtful_headings"] == [
        {"key": "art-3", "label": "ARTÍCULO $”.- TRES", "page": 1},
        {"key": "art-4", "label": "ARTÍCULO 9%.- CUATRO", "page": 1},
    ]
    assert "Requiere atención" in result.report_text
    assert "ARTÍCULO $”.- TRES" in result.report_text
    assert result.report["sequence"][0]["gaps"] == []
    check_invariants(result)


@pytest.mark.parametrize("origin", ["pdf_text", "web"])
def test_the_same_misread_text_from_pdf_text_has_no_tolerance(origin):
    """REQ-003: el mismo texto con origen `pdf_text` o `web` no se tolera: los
    encabezados con signos sustitutos no son encabezados (tampoco fuera de secuencia),
    no abren unidades y nada queda marcado como dudoso."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1°.- UNO. Texto.",
            "ARTÍCULO 2°.- DOS. Texto.",
            "ARTÍCULO $”.- TRES. Texto.",
            "ARTÍCULO 9%.- CUATRO. Texto.",
            origin=origin,
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2"]
    assert by_key(result)["art-2"].text.endswith("ARTÍCULO 9%.- CUATRO. Texto.")
    assert result.report["doubtful_headings"] == []
    assert result.report["sequence"][0]["not_accepted"] == []


def test_an_ocr_heading_out_of_place_is_not_accepted():
    """REQ-003: la tolerancia del reconocimiento no acepta cualquier número: si el
    encabezado no está donde corresponde por la secuencia (el siguiente no continúa la
    numeración), queda dentro del artículo abierto."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1”.- UNO. Texto.",
            "ARTÍCULO 2”.- DOS. Texto.",
            "ARTÍCULO 40”.- CITA. Texto.",
            "ARTÍCULO 3”.- TRES. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3"]
    assert result.report["doubtful_headings"] == []


def test_an_ocr_sign_read_as_a_digit_is_resolved_by_the_sequence():
    """REQ-003, REQ-015: en un escaneo real del anexo, Tesseract lee el signo `°` como
    cifra (`4°` → `47`, `7°` → `77`), el 8 como `$` (`8°` → `$”`) y el signo como
    `9”%`. Donde se espera el 4, `ARTÍCULO 47.-` se acepta como el 4; donde se espera
    el 7, `ARTÍCULO 77.-` como el 7; `$”` como el 8 y `99”%` como el 9. Cada uno queda
    marcado como encabezado dudoso en el informe, y no se informan saltos."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1%.- UNO. Texto.",
            "ARTÍCULO 2?.- DOS. Texto.",
            "ARTÍCULO 3.- TRES. Texto.",
            "ARTÍCULO 47.- CUATRO. Texto.",
            "ARTÍCULO 5”.- CINCO. Texto.",
            "ARTÍCULO 6*.- SEIS. Texto.",
            "ARTÍCULO 77.- SIETE. Texto.",
            "ARTÍCULO $”.- OCHO. Texto.",
            "ARTÍCULO 99”%.- NUEVE. Texto.",
            "ARTÍCULO 10.- DIEZ. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == [f"art-{n}" for n in range(1, 11)]
    units = by_key(result)
    assert units["art-4"].text == "ARTÍCULO 47.- CUATRO. Texto."
    assert units["art-7"].label == "ARTÍCULO 77.- SIETE"
    assert [item["key"] for item in result.report["doubtful_headings"]] == [
        "art-4",
        "art-7",
        "art-8",
        "art-9",
    ]
    assert result.report["sequence"][0]["gaps"] == []
    assert result.report["sequence"][0]["not_accepted"] == []
    check_invariants(result)


def test_an_ocr_sign_read_as_a_digit_as_the_last_article_is_accepted():
    """REQ-003, REQ-015: el número imposible para la secuencia se resuelve también sin
    encabezados después: `ARTÍCULO 47.-` donde se espera el 4, como último artículo, es
    el 4, dudoso; `$6` se lee como 86 (sin signo `°`)."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1.- UNO. Texto.",
            "ARTÍCULO 2.- DOS. Texto.",
            "ARTÍCULO 3.- TRES. Texto.",
            "ARTÍCULO 47.- CUATRO. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3", "art-4"]
    assert result.report["doubtful_headings"] == [
        {"key": "art-4", "label": "ARTÍCULO 47.- CUATRO", "page": 1}
    ]
    heading = classify_heading("ARTÍCULO $6.- PLAZO. Texto.", ocr=True)
    assert (heading.kind, heading.raw, heading.article_number) == (ARTICLE, "$6", None)


def test_an_ocr_47_followed_by_the_real_4_is_not_taken_as_the_4():
    """REQ-003: si después de un `ARTÍCULO 47.-` leído por reconocimiento viene el
    encabezado del 4, el 47 no es el 4 (por ejemplo, una cita al comienzo de un
    párrafo): queda dentro del artículo abierto y el 4 se acepta."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1.- UNO. Texto.",
            "ARTÍCULO 2.- DOS. Texto.",
            "ARTÍCULO 3.- TRES. Texto.",
            "ARTÍCULO 47.- CITADO. Texto.",
            "ARTÍCULO 4.- CUATRO. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3", "art-4"]
    assert by_key(result)["art-3"].text.endswith("\nARTÍCULO 47.- CITADO. Texto.")
    assert result.report["doubtful_headings"] == []


def test_the_sign_read_as_a_digit_is_not_tolerated_in_pdf_text():
    """REQ-003: con origen `pdf_text` la regla queda estricta: `ARTÍCULO 47.-` donde se
    espera el 4 no se acepta como el 4, queda dentro del artículo 3 y se informa como
    encabezado fuera de secuencia; nada se marca como dudoso."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1°.- UNO. Texto.",
            "ARTÍCULO 2°.- DOS. Texto.",
            "ARTÍCULO 3°.- TRES. Texto.",
            "ARTÍCULO 47.- CUATRO. Texto.",
            origin="pdf_text",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3"]
    assert result.report["doubtful_headings"] == []
    assert result.report["sequence"][0]["not_accepted"] == [
        {"number": "47", "page": 1, "inside": "art-3"}
    ]


def test_an_ocr_number_whose_last_digit_is_not_a_sign_is_not_taken_as_the_next():
    """REQ-003: el signo `°` leído como cifra es un 7 o un 9. `ARTÍCULO 43.-` donde se
    espera el 4 no es el 4 si la secuencia no lo justifica (los encabezados que le siguen
    no continúan desde el 4): queda dentro del artículo abierto y se informa fuera de
    secuencia; nada se marca como dudoso."""
    result = split_document(
        ocr_synthetic(
            "ARTÍCULO 1.- UNO. Texto.",
            "ARTÍCULO 2.- DOS. Texto.",
            "ARTÍCULO 3.- TRES. Texto.",
            "ARTÍCULO 43.- CITADO. Texto.",
            "ARTÍCULO 6.- SEIS. Texto.",
            "ARTÍCULO 7.- SIETE. Texto.",
        ),
        part="cuerpo",
    )

    assert keys(result) == ["art-1", "art-2", "art-3", "art-6", "art-7"]
    assert by_key(result)["art-3"].text.endswith("\nARTÍCULO 43.- CITADO. Texto.")
    assert result.report["doubtful_headings"] == []
    assert result.report["sequence"][0]["not_accepted"] == [
        {"number": "43", "page": 1, "inside": "art-3"}
    ]
