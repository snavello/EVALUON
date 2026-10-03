"""Partición del anexo completo de la Disposición AFIP 247/2022 (T-023; ADR-0004, "Cómo
se prueba"; plan 001, "Texto normativo sin número de artículo").

Documento real: `corpus/normativa/disp-afip-247-2022-anexo.pdf`, el mismo de T-020, PDF
con texto de 45 páginas, cargado como parte `anexo`. Se lee sin modificarlo.

La tabla esperada (`EXPECTED`) está escrita a mano contra el PDF y su índice: por cada
artículo, su número, la página donde empieza y el título y capítulo que lo contienen.
Página 1: carátula GDE (membrete, "ANEXO", "Número:", "Referencia:"), la línea "ANEXO
(artículo 1°)" y el nombre del régimen; páginas 1 a 5: índice, que no lista la cláusula
transitoria; páginas 5 a 44: articulado del 1 al 99; página 44: "CLÁUSULA TRANSITORIA
REGISTRO DE PROVEEDORES", con dos párrafos; página 45: solo la firma digital, sin texto.
"""

from pathlib import Path

import pytest

from evaluon.norms.reading import ORIGIN_PDF_TEXT, read_document
from evaluon.norms.splitting import split_document

REPO = Path(__file__).resolve().parents[2]
ANNEX = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"

T1 = "Título I"
T2, T3, T4, T5, T6, T7 = "Título II", "Título III", "Título IV", "Título V", "Título VI", "Título VII"


def _rows(title, chapter, pages):
    return [(number, page, title, chapter) for number, page in pages]


# (número, página de inicio, título, capítulo), contra el PDF.
EXPECTED = (
    _rows(T1, None, [(1, 5), (2, 5), (3, 5), (4, 6), (5, 6), (6, 6), (7, 6), (8, 7), (9, 7),
                     (10, 7), (11, 8), (12, 8), (13, 9), (14, 9), (15, 9), (16, 10), (17, 11),
                     (18, 11), (19, 12)])
    + _rows(T2, "Capítulo I", [(20, 12), (21, 12), (22, 15), (23, 15), (24, 16), (25, 18), (26, 19)])
    + _rows(T2, "Capítulo II", [(27, 19), (28, 20), (29, 21), (30, 21), (31, 21), (32, 22)])
    + _rows(T2, "Capítulo III", [(33, 22), (34, 25), (35, 25), (36, 26), (37, 26)])
    + _rows(T2, "Capítulo IV", [(38, 27), (39, 28), (40, 28), (41, 28), (42, 28), (43, 28),
                                (44, 29), (45, 29), (46, 30), (47, 30)])
    + _rows(T2, "Capítulo V", [(48, 30), (49, 30), (50, 30), (51, 30), (52, 31), (53, 31),
                               (54, 32), (55, 32), (56, 33), (57, 33), (58, 33), (59, 33)])
    + _rows(T2, "Capítulo VI", [(60, 34), (61, 34)])
    + _rows(T2, "Capítulo VII", [(62, 35)])
    + _rows(T2, "Capítulo VIII", [(63, 35), (64, 35), (65, 35), (66, 36), (67, 37), (68, 37), (69, 37)])
    + _rows(T3, "Capítulo I", [(70, 38), (71, 38), (72, 38), (73, 38), (74, 38), (75, 38),
                               (76, 38), (77, 39), (78, 39)])
    + _rows(T3, "Capítulo II", [(79, 39), (80, 40), (81, 40), (82, 40), (83, 41), (84, 41),
                                (85, 41), (86, 41), (87, 41)])
    + _rows(T4, None, [(88, 42), (89, 43), (90, 43), (91, 43), (92, 43), (93, 43), (94, 43)])
    + _rows(T5, None, [(95, 44), (96, 44)])
    + _rows(T6, None, [(97, 44), (98, 44)])
    + _rows(T7, None, [(99, 44)])
)


@pytest.fixture(scope="module")
def annex():
    return split_document(read_document(ANNEX), part="anexo")


def of_type(result, unit_type):
    return [unit for unit in result.units if unit.unit_type == unit_type]


def by_key(result):
    return {unit.key: unit for unit in result.units}


def test_expected_table_is_complete():
    """REQ-003: la tabla esperada tiene los 99 artículos del índice, en orden."""
    assert [row[0] for row in EXPECTED] == list(range(1, 100))


def test_each_article_is_a_unit_located_as_in_the_document(annex):
    """REQ-003: cada artículo del anexo es una unidad separada y su ubicación coincide
    con la tabla esperada: contenedor, número, página de inicio, y título y capítulo en
    la ruta."""
    articles = of_type(annex, "articulo")

    found = [
        (unit.key, unit.number, unit.page_start, unit.path, unit.parent_key) for unit in articles
    ]
    expected = [
        (
            f"anexo/art-{number}",
            str(number),
            page,
            " › ".join(["Anexo", title] + ([chapter] if chapter else []) + [f"Artículo {number}"]),
            "anexo",
        )
        for number, page, title, chapter in EXPECTED
    ]
    assert found == expected


def test_all_keys_hang_from_the_annex(annex):
    """REQ-003: todas las claves empiezan con `anexo/`, debajo de una única unidad raíz
    `anexo`, y ninguna se repite."""
    root = annex.units[0]
    assert (root.key, root.unit_type, root.parent_key) == ("anexo", "anexo", None)
    assert [unit.key for unit in annex.units if unit.unit_type == "anexo"] == ["anexo"]
    assert all(unit.key.startswith("anexo/") for unit in annex.units[1:])
    assert len({unit.key for unit in annex.units}) == len(annex.units)


def test_the_root_is_the_annex_heading_without_the_cover(annex):
    """REQ-003: la unidad raíz es "ANEXO (artículo 1°)" con el nombre del régimen; el
    membrete y los datos GDE de la carátula se descartan y se informan."""
    root = annex.units[0]
    assert root.label == "ANEXO (artículo 1°)"
    assert root.text == (
        "ANEXO (artículo 1°)\nRÉGIMEN GENERAL PARA CONTRATACIONES DE BIENES, SERVICIOS Y "
        "OBRAS PÚBLICAS DE LA ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS"
    )
    cover = [item for item in annex.report["discarded"] if item["reason"] == "caratula"]
    assert len(cover) == 1
    assert cover[0]["first_words"].startswith("Administración Federal de Ingresos Públicos 2022")


def test_the_index_produces_no_units(annex):
    """REQ-003: el índice de las páginas 1 a 5 no produce unidades: se descarta y se
    informa; ningún artículo empieza antes de la página 5."""
    index = [item for item in annex.report["discarded"] if item["reason"] == "indice"]
    assert [(item["page_start"], item["page_end"]) for item in index] == [(1, 5)]
    assert min(unit.page_start for unit in of_type(annex, "articulo")) == 5


def test_article_99_ends_where_the_transitory_clause_begins(annex):
    """REQ-003: el texto de `anexo/art-99` termina donde empieza la cláusula transitoria,
    y no se lleva su encabezado."""
    units = by_key(annex)
    article, clause = units["anexo/art-99"], units["anexo/clausula-transitoria"]

    assert article.text == (
        "ARTÍCULO 99.- VALOR DEL MÓDULO. A los efectos de lo dispuesto en el presente "
        "régimen, el valor del módulo (M) será el que fije la máxima autoridad del Organismo."
    )
    assert annex.canonical_text[article.char_end : clause.char_start] == "\n"


def test_the_transitory_clause_is_its_own_unit(annex):
    """REQ-003: la cláusula es la unidad `anexo/clausula-transitoria`, de tipo
    `clausula`, sin número, con su etiqueta y su ruta sin el título VII, ubicada después
    de `anexo/art-99`; su texto trae sus dos párrafos y nada de la firma."""
    clause = by_key(annex)["anexo/clausula-transitoria"]

    assert annex.units[-1] is clause
    assert (clause.unit_type, clause.number, clause.parent_key) == ("clausula", "", "anexo")
    assert clause.label == "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES"
    assert clause.path == "Anexo › Cláusula transitoria"
    assert (clause.page_start, clause.page_end) == (44, 44)
    paragraphs = clause.text.split("\n")
    assert len(paragraphs) == 3
    assert paragraphs[0] == "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES"
    assert paragraphs[1].startswith("Las unidades con capacidad de contratación en las que aún")
    assert paragraphs[2].startswith("Ello con excepción del requisito de incorporación")
    assert paragraphs[2].endswith("hasta tanto ello suceda.")
    assert clause.text_origin == ORIGIN_PDF_TEXT
    order = [unit.key for unit in annex.units if unit.unit_type != "inciso"]
    assert order[-2:] == ["anexo/art-99", "anexo/clausula-transitoria"]


def test_nothing_normative_is_left_unlocated(annex):
    """REQ-003, REQ-004: ningún tramo queda como no ubicado; lo descartado es la
    carátula, el índice y los títulos y capítulos que pasan a la ruta. No faltan números
    ni hay encabezados fuera de secuencia, ni párrafos en mayúsculas dentro de una
    unidad."""
    assert annex.report["unlocated"] == []
    reasons = {item["reason"] for item in annex.report["discarded"]}
    assert reasons == {"caratula", "indice", "titulo"}
    titles = [item for item in annex.report["discarded"] if item["reason"] == "titulo"]
    assert len(titles) == 7 + 10  # siete títulos y diez capítulos
    assert annex.report["sequence"] == [
        {"container": "Anexo", "key": "anexo", "gaps": [], "not_accepted": []}
    ]
    assert annex.report["uppercase_in_units"] == []
    assert annex.report["doubtful_headings"] == []
    assert annex.report["discarded_lines"] == 0
    assert annex.report["pages"] == {"total": 45, "not_read": [45]}


def test_incisos_match_the_pdf(annex):
    """REQ-003: una muestra de artículos con incisos, revisada contra el PDF: el
    artículo 3 (a a h, con su párrafo final fuera del inciso h), el 21 (a a d; b con
    puntos 1 y 2, d con puntos 1 a 9), el 67 (dos incisos con puntos, y un párrafo que
    sigue al punto 1) y el 88 (a a d, con párrafos propios del inciso c)."""
    units = by_key(annex)
    keys = [unit.key for unit in annex.units]

    def children(parent):
        return [key for key in keys if key.startswith(parent + "/inc-") and key.count("/") == parent.count("/") + 1]

    assert children("anexo/art-3") == [f"anexo/art-3/inc-{c}" for c in "abcdefgh"]
    assert units["anexo/art-3/inc-h"].text == "h) Igualdad de trato."
    assert units["anexo/art-3"].text.endswith(
        "h) Igualdad de trato.\nDesde el inicio de las actuaciones hasta la finalización de "
        "la ejecución del contrato, toda cuestión vinculada con la contratación deberá "
        "interpretarse sobre la base de una rigurosa observancia de los principios que "
        "anteceden."
    )
    assert (units["anexo/art-3/inc-b"].page_start, units["anexo/art-3/inc-a"].page_start) == (6, 5)

    assert children("anexo/art-21") == [f"anexo/art-21/inc-{c}" for c in "abcd"]
    assert children("anexo/art-21/inc-b") == ["anexo/art-21/inc-b/inc-1", "anexo/art-21/inc-b/inc-2"]
    assert children("anexo/art-21/inc-d") == [f"anexo/art-21/inc-d/inc-{n}" for n in range(1, 10)]
    # El párrafo que sigue al último punto de b) es del inciso b, no del punto 2.
    last_of_b = units["anexo/art-21/inc-b"].text.split("\n")[-1]
    assert last_of_b.startswith("El Organismo podrá realizar el acto público de la subasta")
    assert units["anexo/art-21/inc-b/inc-2"].text == "2. Venta de bienes de propiedad de la AFIP."
    assert units["anexo/art-21/inc-d/inc-2"].text.startswith(
        "2. La realización o adquisición de obras científicas, técnicas o artísticas"
    )
    assert "\nSe considerará satisfecha la condición de único" in units["anexo/art-21/inc-d/inc-2"].text
    assert units["anexo/art-21/inc-d/inc-2"].path == (
        "Anexo › Título II › Capítulo I › Artículo 21 › Inciso d › Inciso 2"
    )

    assert children("anexo/art-67") == ["anexo/art-67/inc-a", "anexo/art-67/inc-b"]
    assert children("anexo/art-67/inc-a") == [f"anexo/art-67/inc-a/inc-{n}" for n in (1, 2, 3)]
    assert children("anexo/art-67/inc-b") == [f"anexo/art-67/inc-b/inc-{n}" for n in (1, 2)]
    assert units["anexo/art-67"].label == "ARTÍCULO 67.- DEVOLUCIÓN DE GARANTÍAS"
    assert units["anexo/art-67/inc-a/inc-1"].text.endswith(
        "\nEn los procedimientos de etapa múltiple, se pondrá a disposición la garantía a los "
        "oferentes que no resultaren preseleccionados en oportunidad de la apertura del sobre "
        "que contiene la oferta económica."
    )
    assert units["anexo/art-67/inc-b/inc-2"].page_start == 37

    assert children("anexo/art-88") == [f"anexo/art-88/inc-{c}" for c in "abcd"]
    assert units["anexo/art-88/inc-c"].text.startswith("c) Multas:\nEl pliego de bases")
    assert children("anexo/art-88/inc-c") == []
    assert units["anexo/art-88/inc-d/inc-3"].page_start == 42


def test_paragraphs_after_the_last_inciso_are_reported(annex):
    """REQ-004: el informe señala las listas cuyo último inciso tiene párrafos después,
    que quedaron en el artículo o en el inciso que la contiene: diecinueve en el anexo,
    entre ellos el inciso h del artículo 24. Ninguno cambia el texto de las unidades: es
    un aviso para quien valida. El punto 4 del inciso e del artículo 33, que se señalaba
    hasta T-043, termina en dos puntos y ya se lleva sus puntos 4.1 y 4.2
    (`test_point_4_of_article_33_e_keeps_its_subpoints`)."""
    after = annex.report["after_last_inciso"]
    found = {item["key"]: item for item in after}

    assert len(after) == 19
    assert found["anexo/art-24/inc-h"]["inside"] == "anexo/art-24"
    assert "anexo/art-33/inc-e/inc-4" not in found
    assert found["anexo/art-3/inc-h"]["paragraphs"] == 1
    assert all(item["paragraphs"] >= 1 for item in after)
    units = by_key(annex)
    starts = [units[item["key"]].char_start for item in after]
    assert starts == sorted(starts)


def test_point_4_of_article_33_e_keeps_its_subpoints(annex):
    """REQ-003 (T-043): el punto 4 del inciso e del artículo 33 (página 24) termina en
    "...a través de los siguientes medios:" y lo siguen 4.1 (invitaciones) y 4.2
    (difusión), que son suyos: quedan en el punto 4 y no en el inciso e. El punto 4 llega
    hasta el final del inciso e, que no cambia; termina en la página 25. El informe lo
    señala para que quien valida lo revise (REQ-004)."""
    assert annex.report["presenting_inciso"] == [
        {"key": "anexo/art-33/inc-e/inc-4", "paragraphs": 2, "page": 24}
    ]
    units = by_key(annex)
    point = units["anexo/art-33/inc-e/inc-4"]
    paragraphs = point.text.split("\n")
    assert paragraphs[0].endswith("deberá efectuarse a través de los siguientes medios:")
    assert paragraphs[1].startswith("4.1. Invitaciones a por lo menos TRES (3) proveedores")
    assert paragraphs[2].startswith("4.2. Difusión: Se difundirán en el sitio")
    assert len(paragraphs) == 3
    assert point.char_end == units["anexo/art-33/inc-e"].char_end
    assert (point.page_start, point.page_end) == (24, 25)


def test_every_inciso_is_a_slice_of_its_article(annex):
    """REQ-003: el texto de cada inciso es un recorte del texto de su artículo; la
    unidad que lo contiene viene antes en la lista."""
    units = by_key(annex)
    seen = set()
    for unit in annex.units:
        if unit.unit_type == "inciso":
            parent = units[unit.parent_key]
            assert unit.parent_key in seen
            assert parent.char_start <= unit.char_start <= unit.char_end <= parent.char_end
            assert unit.text in parent.text
        seen.add(unit.key)


def test_every_text_is_its_slice_and_coverage_adds_up(annex):
    """REQ-003, REQ-004: cada texto es igual a su recorte del texto canónico, el orden es
    creciente y la cobertura suma el total."""
    text = annex.canonical_text
    for unit in annex.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
    assert [unit.order for unit in annex.units] == list(range(1, len(annex.units) + 1))
    coverage = annex.report["coverage"]
    assert coverage["matches"] is True
    assert coverage["unlocated"] == 0
    assert (
        coverage["units"] + coverage["discarded"] + coverage["separators"] == coverage["total"]
    )


def test_report_counts(annex):
    """REQ-004: el informe cuenta las unidades por tipo y por contenedor."""
    units = annex.report["units"]
    assert units["by_container"] == [
        {"container": "Anexo", "key": "anexo", "articulo": 99, "first": "1", "last": "99"}
    ]
    assert units["by_type"]["anexo"] == 1
    assert units["by_type"]["articulo"] == 99
    assert units["by_type"]["clausula"] == 1
    assert units["by_type"]["inciso"] == len(of_type(annex, "inciso"))
