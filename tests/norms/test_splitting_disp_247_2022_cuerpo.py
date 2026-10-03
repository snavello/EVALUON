"""Partición del cuerpo de la Disposición AFIP 247/2022 desde su página web (T-050;
ADR-0004, "Cómo se prueba"; plan 001, "Una norma en más de un archivo").

Documento real: `corpus/normativa/disp-afip-247-2022-original.htm`, la página de Infoleg,
leída con `web.py` (T-022) y cargada como parte `cuerpo`. Se lee sin modificarla. Su
anexo es otro archivo (`disp-afip-247-2022-anexo.pdf`, T-023), cargado como parte
`anexo`, cuyas claves son `anexo/art-N`.

La tabla esperada está escrita a mano mirando la página (una página web no tiene
páginas). Lo que trae, en orden:

- encabezado ("ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS", "Disposición 247/2022",
  "DI-2022-247-E-AFIP-AFIP", "Ciudad de Buenos Aires, 28/11/2022");
- el visto y siete párrafos que empiezan con "Que", después de "CONSIDERANDO:". El visto
  es una unidad de tipo `considerando` con clave `visto` (ADR-0004, "Visto y
  considerandos"): los considerandos son `considerando-1` a `considerando-7`, como dice
  la tarea, y las unidades de tipo `considerando` son ocho;
- "Por ello,", "EL ADMINISTRADOR FEDERAL ..." y "DISPONE:";
- cinco artículos (`ARTÍCULO 1°.-`); el 5 es el de forma ("Comuníquese, ...");
- la firma "Carlos Daniel Castagneto";
- la nota del Boletín Oficial sobre los anexos ("NOTA: El/los Anexo/s ...") y la línea de
  edición "e. 30/11/2022 N° 97811/22 v. 30/11/2022";
- la nota de Infoleg del pie, que ya descarta la lectura.
"""

from pathlib import Path

import pytest

from evaluon.norms.reading import ORIGIN_WEB
from evaluon.norms.reading.web import read_web
from evaluon.norms.splitting import split_document

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "corpus" / "normativa" / "disp-afip-247-2022-original.htm"

# (clave, tipo, número, etiqueta, ruta), en el orden de la página.
EXPECTED = (
    [("visto", "considerando", "", "VISTO", "Visto")]
    + [
        (f"considerando-{n}", "considerando", str(n), f"Considerando {n}", f"Considerando {n}")
        for n in range(1, 8)
    ]
    + [(f"art-{n}", "articulo", str(n), f"ARTÍCULO {n}°.-", f"Artículo {n}") for n in range(1, 6)]
)


@pytest.fixture(scope="module")
def body():
    return split_document(read_web(PAGE.read_bytes()), part="cuerpo")


def by_key(result):
    return {unit.key: unit for unit in result.units}


def test_expected_table_has_visto_seven_considerandos_and_five_articles():
    """REQ-003: la tabla esperada tiene el visto, siete considerandos y cinco artículos."""
    assert [row[1] for row in EXPECTED].count("articulo") == 5
    assert [row[0] for row in EXPECTED if row[0].startswith("considerando-")] == [
        f"considerando-{n}" for n in range(1, 8)
    ]


def test_each_unit_is_located_as_in_the_document(body):
    """REQ-003: el visto, cada considerando y cada artículo son unidades separadas, en el
    orden de la página, con su clave, tipo, número, etiqueta y ruta; cuelgan de la norma
    (sin unidad raíz) y no tienen páginas."""
    found = [
        (unit.key, unit.unit_type, unit.number, unit.label, unit.path) for unit in body.units
    ]
    assert found == EXPECTED
    assert all(unit.parent_key is None for unit in body.units)
    assert all(unit.page_start is None and unit.page_end is None for unit in body.units)


def test_body_keys_do_not_clash_with_the_annex_keys(body):
    """REQ-003: las claves del cuerpo (`art-1` a `art-5`) no chocan con las del anexo,
    cargado aparte como parte `anexo` (`anexo/art-1` a `anexo/art-99`)."""
    keys = {unit.key for unit in body.units}
    annex_keys = {"anexo"} | {f"anexo/art-{n}" for n in range(1, 100)} | {"anexo/clausula-transitoria"}

    assert not keys & annex_keys
    assert not any(key.startswith("anexo") for key in keys)
    assert len(keys) == len(body.units)


def test_texts_of_visto_considerandos_and_articles(body):
    """REQ-003: el texto de cada unidad empieza y termina donde la página: el
    "CONSIDERANDO:" va con el primero, y el artículo 5 termina en su párrafo, sin la
    firma ni las notas que le siguen."""
    units = by_key(body)

    assert units["visto"].text == (
        "VISTO el Expediente Electrónico N° EX-2022-02052228- -AFIP-SGDADVCOAD#SDGCTI, y"
    )
    assert units["considerando-1"].text.startswith(
        "CONSIDERANDO:\nQue en el artículo 3º del Decreto N° 1.399 del 4 de noviembre de 2001"
    )
    assert units["considerando-7"].text.startswith("Que la presente de dicta en ejercicio")
    assert units["considerando-7"].text.endswith("sus modificatorios y sus complementarios.")
    assert units["art-2"].text.startswith("ARTÍCULO 2°.- Abrogar las Disposiciones Nros. 297 (AFIP)")
    assert units["art-5"].text.startswith("ARTÍCULO 5°.- Comuníquese, dese a la Dirección Nacional")
    assert units["art-5"].text.endswith("Boletín Oficial y archívese.")


def test_signature_and_notes_are_not_units(body):
    """REQ-003: la firma queda a la vista como no ubicada, junto con el encabezado y la
    fórmula "Por ello ... DISPONE:"; la nota del Boletín Oficial sobre los anexos y la
    línea de edición se descartan como datos de publicación; la nota de Infoleg del pie
    la descarta la lectura. Ninguna es una unidad."""
    assert [item["first_words"] for item in body.report["unlocated"]] == [
        "ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS Disposición 247/2022 DI-2022-247-E-AFIP-AFIP",
        "Por ello, EL ADMINISTRADOR FEDERAL DE LA ADMINISTRACIÓN",
        "Carlos Daniel Castagneto",
    ]
    publication = [item for item in body.report["discarded"] if item["reason"] == "publicacion"]
    assert len(publication) == 1
    start, end = publication[0]["char_start"], publication[0]["char_end"]
    assert body.canonical_text[start:end] == (
        "NOTA: El/los Anexo/s que integra/n este(a) Disposición se publican en la edición web "
        "del BORA -www.boletinoficial.gob.ar-\ne. 30/11/2022 N° 97811/22 v. 30/11/2022"
    )
    assert "Nota Infoleg" not in body.canonical_text
    assert all("Castagneto" not in unit.text and "NOTA:" not in unit.text for unit in body.units)


def test_texts_are_their_cut_and_coverage_adds_up(body):
    """REQ-003: el texto de cada unidad es igual a su recorte del texto canónico, viene de
    la página web, y la cobertura suma el total."""
    text = body.canonical_text
    for unit in body.units:
        assert unit.text == text[unit.char_start : unit.char_end], unit.key
        assert unit.text_origin == ORIGIN_WEB
    assert [unit.order for unit in body.units] == list(range(1, len(body.units) + 1))
    coverage = body.report["coverage"]
    assert coverage["total"] == len(text)
    assert (
        coverage["units"] + coverage["discarded"] + coverage["unlocated"] + coverage["separators"]
        == coverage["total"]
    )
    assert coverage["matches"] is True
    assert body.report["uppercase_in_units"] == []
