"""Partición de la Disposición AFIP 297/03 desde su página web (T-050; ADR-0004, "Cómo se
prueba"; plan 001, "Identificación de unidades").

Documento real: `corpus/normativa/disp-afip-297-2003-original.htm`, la página de Infoleg,
leída con `web.py` (T-022) y cargada como parte `cuerpo`. Se lee sin modificarla.

Las tablas esperadas están escritas a mano mirando la página: contenedor, número, título
y capítulo de cada artículo (una página web no tiene páginas). Lo que trae la página, en
orden:

- encabezado ("MINISTERIO DE ECONOMIA Y PRODUCCION" ... "Bs. As., 11/6/2003");
- visto y ocho párrafos que empiezan con "Que" (la tarea no da la cantidad);
- "Por ello", "EL ADMINISTRADOR FEDERAL ..." y "DISPONE:";
- los cinco artículos de la disposición (`ARTICULO 1° —`); el 5 es el de forma
  ("Comuníquese, publíquese, dése ... — Dr. ALBERTO R. ABAD, Administrador Federal.",
  firma incluida en el mismo párrafo);
- "REGIMEN GENERAL DE CONTRATACIONES" y "Régimen General para Contrataciones de Bienes,
  Servicios y Obras Públicas", el nombre del régimen, antes del encabezado del anexo;
- "ANEXO I - DISPOSICION Nº 297/03 (AFIP)", que vuelve a numerar;
- "INDICE:", con los títulos, capítulos, artículos (`ARTICULO 1.- OBJETO`, `ARTICULO 20
  -`, `ARTICULO 27.`, `ARTICULO 29-`) e incisos del anexo, hasta "ARTICULO 64.- VIGENCIA";
- el articulado del anexo, del 1 al 64, con los títulos y capítulos en líneas propias y
  su nombre en la línea siguiente ("TITULO II" / "DE LA FORMACION Y PERFECCIONAMIENTO
  DEL CONTRATO");
- la línea de edición del Boletín Oficial "e. 13/6 N° 417.913 v. 13/6/2003".
"""

from pathlib import Path

import pytest

from evaluon.norms.reading import ORIGIN_WEB
from evaluon.norms.reading.web import read_web
from evaluon.norms.splitting import split_document

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "corpus" / "normativa" / "disp-afip-297-2003-original.htm"

T1, T2, T3, T4, T5 = "Título I", "Título II", "Título III", "Título IV", "Título V"


def _rows(title, chapter, first, last):
    return [(number, title, chapter) for number in range(first, last + 1)]


# Anexo I: (número, título, capítulo), contra el articulado y el índice de la página.
EXPECTED_ANNEX = (
    _rows(T1, None, 1, 20)
    + _rows(T2, "Capítulo I", 21, 23)
    + _rows(T2, "Capítulo II", 24, 24)
    + _rows(T2, "Capítulo III", 25, 26)
    + _rows(T2, "Capítulo IV", 27, 30)
    + _rows(T2, "Capítulo V", 31, 44)
    + _rows(T2, "Capítulo VI", 45, 47)
    + _rows(T2, "Capítulo VII", 48, 54)
    + _rows(T2, "Capítulo VIII", 55, 55)
    + _rows(T2, "Capítulo IX", 56, 56)
    + _rows(T2, "Capítulo X", 57, 57)
    + _rows(T3, None, 58, 59)
    + _rows(T4, None, 60, 62)
    + _rows(T5, None, 63, 64)
)

# Cuerpo: los cinco artículos de la disposición, sin títulos.
EXPECTED_BODY = [1, 2, 3, 4, 5]

# Etiquetas de algunos artículos, copiadas de la página: una por cada forma del
# articulado que nombra la tarea.
EXPECTED_LABELS = {
    "art-1": "ARTICULO 1° —",
    "anexo-i/art-2": "ARTICULO 2° — AMBITO DE APLICACION",
    "anexo-i/art-11": "ARTICULO 11. — ANTICORRUPCION",
    "anexo-i/art-12": "ARTICULO 12.— FORMALIDADES DE LAS ACTUACIONES",
    "anexo-i/art-13": "ARTICULO 13 — FACULTADES Y OBLIGACIONES DE LA AFIP",
    "anexo-i/art-48": "ARTICULO 48. INTEGRACION Y FUNCIONAMIENTO DE LA COMISION EVALUADORA",
}


@pytest.fixture(scope="module")
def norm():
    return split_document(read_web(PAGE.read_bytes()), part="cuerpo")


def of_type(result, unit_type):
    return [unit for unit in result.units if unit.unit_type == unit_type]


def by_key(result):
    return {unit.key: unit for unit in result.units}


def test_expected_tables_are_complete():
    """REQ-003: la tabla del Anexo I tiene los 64 artículos de su índice, en orden, y la
    del cuerpo los cinco de la disposición."""
    assert [row[0] for row in EXPECTED_ANNEX] == list(range(1, 65))
    assert EXPECTED_BODY == list(range(1, 6))


def test_each_article_is_a_unit_located_as_in_the_document(norm):
    """REQ-003: cada artículo es una unidad separada y su ubicación coincide con la tabla
    esperada: contenedor, número, y título y capítulo en la ruta; primero los cinco del
    cuerpo y después los 64 del Anexo I. Una página web no tiene páginas."""
    found = [
        (unit.key, unit.number, unit.path, unit.parent_key, unit.page_start, unit.page_end)
        for unit in of_type(norm, "articulo")
    ]
    expected = [(f"art-{n}", str(n), f"Artículo {n}", None, None, None) for n in EXPECTED_BODY] + [
        (
            f"anexo-i/art-{number}",
            str(number),
            " › ".join(["Anexo I", title] + ([chapter] if chapter else []) + [f"Artículo {number}"]),
            "anexo-i",
            None,
            None,
        )
        for number, title, chapter in EXPECTED_ANNEX
    ]
    assert found == expected


def test_article_1_of_the_body_and_of_the_annex_are_two_units(norm):
    """REQ-003: `art-1` y `anexo-i/art-1` son dos unidades distintas, cada una con su
    texto; el anexo es una unidad propia que vuelve a numerar."""
    units = by_key(norm)
    body, annex = units["art-1"], units["anexo-i/art-1"]

    assert body is not annex
    assert body.text.startswith('ARTICULO 1° — Aprobar el "REGIMEN GENERAL PARA CONTRATACIONES')
    assert annex.text.startswith("ARTICULO 1° — OBJETO. El Régimen de Contrataciones")
    root = units["anexo-i"]
    assert (root.unit_type, root.number, root.path, root.parent_key) == ("anexo", "I", "Anexo I", None)
    assert root.text == "ANEXO I - DISPOSICION Nº 297/03 (AFIP)"
    assert [unit.key for unit in norm.units if unit.unit_type == "anexo"] == ["anexo-i"]
    assert len({unit.key for unit in norm.units}) == len(norm.units)


def test_article_forms_keep_their_label(norm):
    """REQ-003: las formas del articulado (`ARTICULO 2° —`, `ARTICULO 11. —`, `ARTICULO
    12.—`, `ARTICULO 13 —`, `ARTICULO 48.` sin raya) dan la etiqueta como figura en la
    página, con su epígrafe."""
    units = by_key(norm)
    assert {key: units[key].label for key in EXPECTED_LABELS} == EXPECTED_LABELS


def test_the_index_produces_no_units_and_is_discarded_whole(norm):
    """REQ-003: el índice del Anexo I, con sus títulos, artículos e incisos, se descarta
    entero, de "INDICE:" a "ARTICULO 64.- VIGENCIA", y ninguna unidad toma texto de él."""
    text = norm.canonical_text
    index = [item for item in norm.report["discarded"] if item["reason"] == "indice"]

    assert len(index) == 1
    start, end = index[0]["char_start"], index[0]["char_end"]
    assert text[start:end].startswith("INDICE:\nTITULO I - DISPOSICIONES GENERALES\nARTICULO 1.- OBJETO")
    assert text[start:end].endswith("ARTICULO 63.- REGLAMENTACION\nARTICULO 64.- VIGENCIA")
    assert all(unit.char_end <= start or unit.char_start >= end for unit in norm.units)


def test_visto_and_considerandos_are_units_of_the_body(norm):
    """REQ-003: el visto y los ocho considerandos de la página son unidades del cuerpo,
    antes del artículo 1."""
    considerandos = of_type(norm, "considerando")

    assert [unit.key for unit in considerandos] == ["visto"] + [f"considerando-{n}" for n in range(1, 9)]
    assert considerandos[0].text.startswith("VISTO el Expediente N° 251.581/03")
    assert considerandos[1].text.startswith("CONSIDERANDO:\nQue en el Artículo 3°, segunda parte")
    assert considerandos[-1].text.startswith("Que en ejercicio de las facultades conferidas")
    assert norm.units.index(considerandos[-1]) < norm.units.index(by_key(norm)["art-1"])
    # El informe cuenta el visto aparte (decisión del Coordinador).
    assert "  Cuerpo: visto, 8 considerandos y 5 artículos; artículos del 1 al 5." in norm.report_text


def test_closing_and_publication_data_are_not_added_to_articles(norm):
    """REQ-003: el artículo de forma termina en su párrafo (con la firma que trae en la
    misma línea); el nombre del régimen que sigue no se le suma y queda no ubicado; la
    línea de edición del Boletín Oficial no se suma al artículo 64 del anexo y se
    descarta como dato de publicación."""
    units = by_key(norm)

    assert units["art-5"].text == (
        "ARTICULO 5° — Comuníquese, publíquese, dése a la Dirección Nacional del Registro "
        "Oficial y archívese. — Dr. ALBERTO R. ABAD, Administrador Federal."
    )
    assert units["anexo-i/art-64"].text.startswith("ARTICULO 64. — VIGENCIA.")
    assert "e. 13/6" not in units["anexo-i/art-64"].text
    publication = [item for item in norm.report["discarded"] if item["reason"] == "publicacion"]
    assert [item["first_words"] for item in publication] == ["e. 13/6 N° 417.913 v. 13/6/2003"]


def test_only_the_heading_formula_and_regime_name_are_unlocated(norm):
    """REQ-003: no queda texto normativo sin ubicar: solo el encabezado de la página, la
    fórmula "Por ello ... DISPONE:" y el nombre del régimen antes del anexo. Los nombres
    de los títulos y capítulos se descartan con su título."""
    assert [item["first_words"] for item in norm.report["unlocated"]] == [
        "MINISTERIO DE ECONOMIA Y PRODUCCION ADMINISTRACION FEDERAL DE",
        "Por ello EL ADMINISTRADOR FEDERAL DE LA ADMINISTRACION",
        "REGIMEN GENERAL DE CONTRATACIONES Régimen General para Contrataciones",
    ]
    titles = [item["first_words"] for item in norm.report["discarded"] if item["reason"] == "titulo"]
    assert "TITULO II DE LA FORMACION Y PERFECCIONAMIENTO DEL" in titles
    assert "CAPITULO X PERFECCIONAMIENTO" in titles
    assert norm.report["uppercase_in_units"] == []


def test_incisos_of_the_annex(norm):
    """REQ-003: los incisos de los artículos que la página arma con las formas de la
    297/03, revisados a mano: `Inciso N)` siempre en el primer nivel (artículos 25 y 47),
    la lista de pautas del artículo 21, la `c)` sin espacio del artículo 41 y el `Inciso
    1).` del artículo 52; el último `Inciso N)` lleva sus párrafos (artículo 17)."""
    keys = {unit.key for unit in norm.units if unit.unit_type == "inciso"}

    art_21 = ["inc-1", "inc-2", "inc-2/inc-1", "inc-2/inc-2", "inc-3", "inc-3/inc-1", "inc-3/inc-2", "inc-4"]
    art_21 += [f"inc-4/inc-{n}" for n in range(1, 10)] + [f"inc-{x}" for x in "abcdefg"]
    art_25 = [f"inc-{x}" for x in "abcdefg"] + [f"inc-{n}" for n in range(1, 9)]
    art_25 += ["inc-1/inc-a", "inc-1/inc-b", "inc-1/inc-c", "inc-2/inc-a", "inc-2/inc-b"]
    art_25 += ["inc-3/inc-a", "inc-3/inc-b", "inc-3/inc-c", "inc-3/inc-d", "inc-4/inc-a", "inc-4/inc-b"]
    art_25 += [f"inc-8/inc-{x}" for x in "abcdefg"]
    art_47 = ["inc-a", "inc-b"] + [f"inc-a/inc-{n}" for n in range(1, 6)] + ["inc-b/inc-1", "inc-b/inc-2"]
    art_47 += [f"inc-{n}" for n in range(1, 9)] + [f"inc-2/inc-{x}" for x in "abcde"]
    art_41 = [f"inc-{x}" for x in "abcdefgh"]
    for article, expected in (("21", art_21), ("25", art_25), ("47", art_47), ("41", art_41)):
        prefix = f"anexo-i/art-{article}/"
        assert {key[len(prefix):] for key in keys if key.startswith(prefix)} == set(expected), article
    assert "anexo-i/art-52/inc-1" in keys

    units = by_key(norm)
    assert units["anexo-i/art-17/inc-2"].text.endswith(
        "La toma de vista en ningún caso dará derecho al particular a efectuar presentaciones "
        "en el expediente por el que tramita la contratación, ni dará lugar a la suspensión "
        "de los trámites o a demoras en el procedimiento de contratación."
    )
    assert units["anexo-i/art-41/inc-c"].text == "c)Nombre de los oferentes."


# Últimos incisos seguidos de párrafos que el informe sigue señalando, revisados a mano
# contra la página. Ninguno pierde texto: el párrafo queda en la unidad que contiene la
# lista. Los cinco que están dentro de un `Inciso N)` quedaron donde corresponden (en ese
# inciso); los de los artículos 11 y 12 son del artículo; en los artículos 23 y 56 el
# párrafo puede ser del último inciso, y lo decide quien valida. De los 19 que señalaban
# las reglas anteriores, los demás se resolvieron con las reglas de `Inciso N)`, de la
# lista presentada por un párrafo y de `c)Nombre`. El del artículo 14 (`f) OTRAS
# OBLIGACIONES DEL CO-CONTRATANTE:`) se resolvió en T-043 con la regla del último inciso
# que termina en dos puntos (`test_the_last_inciso_of_article_14_keeps_what_it_presents`).
REVIEWED_AFTER_LAST_INCISO = [
    ("anexo-i/art-11/inc-c", "anexo-i/art-11", 2),
    ("anexo-i/art-12/inc-i", "anexo-i/art-12", 1),
    ("anexo-i/art-23/inc-a", "anexo-i/art-23", 2),
    ("anexo-i/art-28/inc-2/inc-d", "anexo-i/art-28/inc-2", 1),
    ("anexo-i/art-55/inc-2/inc-g", "anexo-i/art-55/inc-2", 2),
    ("anexo-i/art-55/inc-4/inc-b", "anexo-i/art-55/inc-4", 2),
    ("anexo-i/art-56/inc-b", "anexo-i/art-56", 1),
    ("anexo-i/art-58/inc-3/inc-b", "anexo-i/art-58/inc-3", 3),
    ("anexo-i/art-58/inc-16/inc-c", "anexo-i/art-58/inc-16", 1),
]


def test_paragraphs_after_the_last_inciso_are_the_reviewed_ones(norm):
    """REQ-003, REQ-004: el informe señala para revisar solo los últimos incisos
    seguidos de párrafos que quedaron después de revisar los 19 de las reglas
    anteriores."""
    found = [
        (item["key"], item["inside"], item["paragraphs"]) for item in norm.report["after_last_inciso"]
    ]
    assert found == REVIEWED_AFTER_LAST_INCISO


def test_the_last_inciso_of_article_14_keeps_what_it_presents(norm):
    """REQ-003 (T-043): "f) OTRAS OBLIGACIONES DEL CO-CONTRATANTE:" termina en dos puntos
    y presenta el párrafo de confidencialidad que le sigue, que es suyo y no del
    artículo. El artículo, que lo contiene, no cambia."""
    units = by_key(norm)
    inciso = units["anexo-i/art-14/inc-f"]
    assert inciso.text.startswith(
        "f) OTRAS OBLIGACIONES DEL CO-CONTRATANTE:\nEl co-contratante deberá respetar la "
        "confidencialidad de la información"
    )
    assert inciso.char_end == units["anexo-i/art-14"].char_end


def test_texts_are_their_cut_and_coverage_adds_up(norm):
    """REQ-003: el texto de cada unidad es igual a su recorte del texto canónico, viene de
    la página web, las claves no se repiten, el orden es creciente y la cobertura suma el
    total."""
    text = norm.canonical_text
    for unit in norm.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
        assert unit.text_origin == ORIGIN_WEB
    assert [unit.order for unit in norm.units] == list(range(1, len(norm.units) + 1))
    coverage = norm.report["coverage"]
    assert coverage["total"] == len(text)
    assert (
        coverage["units"] + coverage["discarded"] + coverage["unlocated"] + coverage["separators"]
        == coverage["total"]
    )
    assert coverage["matches"] is True
    counts = {item: sum(1 for unit in norm.units if unit.unit_type == item) for item in ("articulo", "considerando", "anexo")}
    assert counts == {"articulo": 69, "considerando": 9, "anexo": 1}
