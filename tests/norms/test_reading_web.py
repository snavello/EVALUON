"""Lectura de una página web guardada (T-022; ADR-0004, "Cómo se lee"; plan 001, bloque B).

Archivos de prueba, todos públicos (P4):

- `tests/fixtures/disp-297-03-extracto.html`: extracto de la página de Infoleg de la
  Disposición AFIP 297/03 (`corpus/normativa/disp-afip-297-2003-original.htm`), armado
  copiando renglones del original sin cambiar sus bytes, así que conserva su codificación
  (windows-1252, con el signo de grado, la raya y el ordinal como bytes sueltos y las
  letras acentuadas como entidades). Trae el encabezado con los scripts de medición, la
  navegación del sitio, la disposición con sus cinco artículos, el comienzo del Anexo I
  con su índice hasta el artículo 21 (con sus bloques `<DIR>`), el título I del
  articulado con los artículos 1 a 5 y la línea final del Boletín Oficial.
- `corpus/normativa/disp-afip-247-2022-original.htm`: la página del cuerpo de la
  Disposición AFIP 247/2022, que es corta y se lee directamente del corpus.
- `corpus/normativa/disp-afip-297-2003-original.htm`: la página completa de la 297/03.

Las páginas sintéticas de las pruebas de codificación se arman en cada prueba.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from evaluon.norms.reading import (
    FORMAT_HTML,
    ORIGIN_WEB,
    PAGE_NOT_READ,
    PAGE_READ,
    UnsupportedFormatError,
)
from evaluon.norms.reading.web import (
    DISCARD_HEAD,
    DISCARD_INFOLEG_NOTE,
    DISCARD_SCRIPT,
    DISCARD_STYLE,
    detect_encoding,
    read_web,
)

REPO = Path(__file__).resolve().parents[2]
EXTRACT_297 = REPO / "tests" / "fixtures" / "disp-297-03-extracto.html"
PAGE_297 = REPO / "corpus" / "normativa" / "disp-afip-297-2003-original.htm"
PAGE_247 = REPO / "corpus" / "normativa" / "disp-afip-247-2022-original.htm"

# Caracteres de control C1 (U+0080 a U+009F): aparecen si un archivo windows-1252 se lee
# como ISO-8859-1 (la raya `—`, byte 0x97, quedaría como U+0097).
C1_CONTROLS = re.compile("[\u0080-\u009f]")
# Una entidad HTML sin resolver (`&oacute;`, `&#8220;`).
ENTITY = re.compile(r"&#?\w+;")


def read(path):
    return read_web(path.read_bytes())


@pytest.fixture(scope="module")
def extract_297():
    return read(EXTRACT_297)


@pytest.fixture(scope="module")
def page_247():
    return read(PAGE_247)


@pytest.fixture(scope="module")
def page_297():
    return read(PAGE_297)


def kept(reading):
    """Textos de las líneas que son texto del documento (no descartadas), en orden."""
    return [line.text for page in reading.pages for line in page.lines if not line.discarded]


def discarded(reading):
    """Pares (motivo, texto) de las líneas descartadas, en orden."""
    return [
        (line.discarded, line.text)
        for page in reading.pages
        for line in page.lines
        if line.discarded
    ]


def all_lines(reading):
    return [line for page in reading.pages for line in page.lines]


class _BodyText(HTMLParser):
    """Extracción independiente (biblioteca estándar, no lxml) del texto visible del
    cuerpo: todo el texto fuera de `<head>`, `<script>` y `<style>`. Cualquier elemento
    que no sea de línea separa palabras."""

    SKIPPED = {"head", "script", "style", "title"}
    INLINE = {"a", "b", "big", "em", "font", "i", "small", "span", "strong", "sub", "sup", "u"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self.depth += 1
        if tag not in self.INLINE:
            self.chunks.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIPPED and self.depth:
            self.depth -= 1
        if tag not in self.INLINE:
            self.chunks.append(" ")

    def handle_data(self, data):
        if not self.depth:
            self.chunks.append(data)


def body_words(path, encoding):
    parser = _BodyText()
    parser.feed(path.read_bytes().decode(encoding))
    parser.close()
    return "".join(parser.chunks).split()


# --- Resultado común: origen `web`, una sola página sin número (REQ-015) ---------------


@pytest.mark.parametrize("path", [EXTRACT_297, PAGE_247, PAGE_297], ids=lambda p: p.name)
def test_a_web_page_is_one_page_without_number_and_web_origin(path):
    """REQ-015: una página web se lee como una sola página, sin número ni medidas, leída,
    con todas sus líneas de origen `web`, sin posición y sin confianza."""
    reading = read(path)

    assert reading.file_format == FORMAT_HTML
    assert len(reading.pages) == 1
    page = reading.pages[0]
    assert (page.number, page.width, page.height) == (None, None, None)
    assert page.status == PAGE_READ
    assert reading.pages_not_read == []
    assert page.lines
    for line in page.lines:
        assert line.origin == ORIGIN_WEB
        assert (line.x0, line.top, line.x1, line.bottom) == (None, None, None, None)
        assert line.confidence is None
        assert line.words == []


def test_the_reading_records_the_tool_versions(extract_297):
    """REQ-015 (P6): la lectura registra las versiones de las bibliotecas con que se hizo."""
    assert set(extract_297.tool_versions) == {"beautifulsoup4", "lxml"}
    assert all(extract_297.tool_versions.values())


def test_the_same_page_gives_the_same_reading(extract_297):
    """REQ-015: la lectura es determinista: el mismo archivo da el mismo resultado."""
    assert read(EXTRACT_297).as_json() == extract_297.as_json()


# --- Codificación (REQ-015) ----------------------------------------------------------


def test_encoding_of_the_infoleg_pages_is_windows_1252():
    """REQ-015: la página de la 297/03 declara windows-1252 y la de la 247/2022 declara
    ISO-8859-1; las dos se leen como windows-1252, que es como los navegadores tratan la
    etiqueta ISO-8859-1. Así la raya (byte 0x97) de la 297/03 no queda como un control."""
    assert detect_encoding(EXTRACT_297.read_bytes()) == "cp1252"
    assert detect_encoding(PAGE_297.read_bytes()) == "cp1252"
    assert detect_encoding(PAGE_247.read_bytes()) == "cp1252"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ('<meta charset="utf-8"><p>Disposición N° 1</p>'.encode("utf-8"), "utf-8"),
        (
            '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
            "<p>Disposición N° 1</p>".encode("utf-8"),
            "utf-8",
        ),
        ("﻿<p>Disposición N° 1</p>".encode("utf-8"), "utf-8"),
        ("<p>Disposición N° 1</p>".encode("utf-8"), "utf-8"),
        ("<p>Disposición N° 1</p>".encode("cp1252"), "cp1252"),
        ('<meta charset="latin1"><p>Disposición N° 1</p>'.encode("cp1252"), "cp1252"),
    ],
    ids=["meta-charset", "meta-http-equiv", "bom", "utf8-sin-declarar", "sin-declarar", "latin1"],
)
def test_encoding_is_detected_from_the_file(data, expected):
    """REQ-015: la codificación se toma de la marca de orden de bytes o de la que declara
    la página; si no declara ninguna, UTF-8 si el archivo lo es y, si no, windows-1252.
    En todos los casos el texto se lee con su tilde y su signo de grado."""
    assert detect_encoding(data) == expected
    assert kept(read_web(data)) == ["Disposición N° 1"]


def test_a_page_that_does_not_match_its_declared_encoding_is_rejected():
    """REQ-015: si los bytes no corresponden a la codificación declarada, la lectura se
    rechaza con un error en lugar de reemplazar caracteres sin avisar."""
    data = '<meta charset="utf-8"><p>Disposición</p>'.encode("cp1252")
    with pytest.raises(UnsupportedFormatError):
        read_web(data)


# --- Extracto de la 297/03: texto, orden y descartes (REQ-015) -------------------------


def test_extract_297_has_its_accents_degree_signs_dashes_and_quotes(extract_297):
    """REQ-015: el extracto de la 297/03 se lee con sus letras acentuadas (escritas como
    entidades), el signo de grado y el ordinal, la raya y el guion medio (bytes de
    windows-1252) y sus comillas, sin entidades sin resolver ni caracteres de control."""
    texts = kept(extract_297)

    assert "Disposición N° 297/2003" in texts
    assert "ANEXO I - DISPOSICION Nº 297/03 (AFIP)" in texts
    assert (
        'ARTICULO 1° — Aprobar el "REGIMEN GENERAL PARA CONTRATACIONES DE BIENES, '
        'SERVICIOS Y OBRAS PUBLICAS de la AFIP – "ADMINISTRACION FEDERAL DE INGRESOS '
        'PUBLICOS" que como ANEXO integra la presente Disposición.'
    ) in texts
    assert (
        "ARTICULO 5° — Comuníquese, publíquese, dése a la Dirección Nacional del Registro "
        "Oficial y archívese. — Dr. ALBERTO R. ABAD, Administrador Federal."
    ) in texts
    for text in texts:
        assert not C1_CONTROLS.search(text), text
        assert "�" not in text, text
        assert not ENTITY.search(text), text


def test_extract_297_blocks_are_in_document_order(extract_297):
    """REQ-015: los bloques del extracto quedan en el orden del documento, uno por
    párrafo, incluidos los que están dentro de bloques `<DIR>` del índice: encabezado de
    la disposición, visto y considerandos, los cinco artículos, el Anexo I con su índice,
    el título I del articulado con sus artículos y la línea del Boletín Oficial."""
    texts = kept(extract_297)

    assert texts[:6] == [
        "MINISTERIO DE ECONOMIA Y PRODUCCION",
        "ADMINISTRACION FEDERAL DE INGRESOS PUBLICOS",
        "Disposición N° 297/2003",
        "Régimen Geeneral para Contrataciones de Bienes, Servicios y Obras Públicas de "
        "la AFIP.",
        "Bs. As., 11/6/2003",
        "VISTO el Expediente N° 251.581/03 del Registro de la ADMINISTRACION FEDERAL DE "
        "INGRESOS PUBLICOS y el Decreto N° 1399 del 4 de noviembre de 2001, y",
    ]
    assert texts[-1] == "e. 13/6 N° 417.913 v. 13/6/2003"

    def position(prefix, start=0):
        return next(i for i, text in enumerate(texts) if i >= start and text.startswith(prefix))

    order = [
        "CONSIDERANDO:",
        "DISPONE:",
        "ARTICULO 1° — Aprobar",
        "ARTICULO 2° — Delegar",
        "ARTICULO 3° — El nuevo",
        "ARTICULO 4° — Derogar",
        "ARTICULO 5° — Comuníquese",
        "ANEXO I - DISPOSICION Nº 297/03 (AFIP)",
        "INDICE:",
        "TITULO I - DISPOSICIONES GENERALES",
        "ARTICULO 1.- OBJETO",
        "ARTICULO 7.- NORMATIVA APLICABLE",
        "Inciso 1) Orden de prelación",
        "ARTICULO 8.- COMPUTO DE PLAZOS",
        "ARTICULO 20 - PERSONAS NO HABILITADAS",
        "ARTICULO 21.- PROCEDIMIENTOS DE SELECCION",
        "Inciso 4) CONTRATACION DIRECTA",
        "g) Trámites no obligatorios en las Contrataciones Directas",
        "TITULO I",
        "DISPOSICIONES GENERALES",
        "ARTICULO 1° — OBJETO.",
        "ARTICULO 2° — AMBITO DE APLICACION.",
        "ARTICULO 3° — PRINCIPIOS GENERALES.",
        "h) Igualdad de trato.",
        "ARTICULO 4° — CONTRATOS COMPRENDIDOS.",
        "ARTICULO 5° — CONTRATOS EXCLUIDOS.",
        "d) Los comprendidos en operaciones de crédito público.",
        "e. 13/6 N° 417.913 v. 13/6/2003",
    ]
    positions = []
    for prefix in order:
        positions.append(position(prefix, positions[-1] + 1 if positions else 0))
    assert positions == sorted(positions)
    assert texts.count("TITULO I") == 1
    assert sum(text.startswith("Que ") for text in texts) == 8


def test_extract_297_drops_scripts_and_site_navigation(extract_297):
    """REQ-015: el texto del documento no trae nada de los scripts de medición ni del
    encabezado del sitio; los scripts y el título de la página quedan en la lectura como
    líneas descartadas, con su motivo, antes del texto."""
    texts = kept(extract_297)
    joined = "\n".join(texts)
    for noise in ("gtag", "GoogleAnalytics", "dataLayer", "function", "86154", "infoleg"):
        assert noise not in joined

    reasons = [reason for reason, _ in discarded(extract_297)]
    assert reasons == [DISCARD_SCRIPT, DISCARD_SCRIPT, DISCARD_HEAD]
    assert "GoogleAnalyticsObject" in discarded(extract_297)[0][1]
    assert discarded(extract_297)[2][1] == "86154"
    lines = all_lines(extract_297)
    assert all(line.discarded for line in lines[:3])
    assert not any(line.discarded for line in lines[3:])


def test_extract_297_is_a_copy_of_the_original_page(extract_297, page_297):
    """REQ-015: el extracto no cambió el texto de la página real: cada uno de sus bloques
    es, en el mismo orden, un bloque de la página completa."""
    full = kept(page_297)
    position = -1
    for text in kept(extract_297):
        position = full.index(text, position + 1)


# --- Página de la 247/2022 (REQ-015) ---------------------------------------------------


def test_page_247_has_its_accents_degree_signs_and_curly_quotes(page_247):
    """REQ-015: la página de la 247/2022 (ISO-8859-1 declarado) se lee con sus tildes en
    mayúsculas y minúsculas, el signo de grado y las comillas tipográficas que trae como
    entidades numéricas; los saltos de renglón del archivo dentro de un párrafo quedan
    como un espacio, como los muestra el navegador."""
    texts = kept(page_247)

    assert texts[:5] == [
        "ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS",
        "Disposición 247/2022",
        "DI-2022-247-E-AFIP-AFIP",
        "Ciudad de Buenos Aires, 28/11/2022",
        "VISTO el Expediente Electrónico N° EX-2022-02052228- -AFIP-SGDADVCOAD#SDGCTI, y",
    ]
    assert (
        "ARTÍCULO 1°.- Aprobar el “RÉGIMEN GENERAL PARA CONTRATACIONES DE BIENES, "
        "SERVICIOS Y OBRAS PÚBLICAS DE LA ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS”, "
        "que como Anexo (IF-2022-02210546-AFIP-SGDADVCOAD#SDGCTI) forma parte de la "
        "presente disposición."
    ) in texts
    for text in texts:
        assert not C1_CONTROLS.search(text), text
        assert "�" not in text, text
        assert not ENTITY.search(text), text
        assert "\n" not in text and "  " not in text and text == text.strip(), text


def test_page_247_blocks_are_in_document_order(page_247):
    """REQ-015: la página de la 247/2022, que trae todo el texto en un bloque separado
    por `<br>`, da un bloque por párrafo en el orden del documento: visto, siete
    considerandos, los cinco artículos, la firma, la nota del Boletín Oficial y la línea
    de publicación."""
    texts = kept(page_247)

    considerations = [text for text in texts if text.startswith("Que ")]
    assert len(considerations) == 7
    articles = [text for text in texts if text.startswith("ARTÍCULO ")]
    assert [text[:13] for text in articles] == [f"ARTÍCULO {n}°.-" for n in range(1, 6)]
    assert texts[-4:] == [
        "ARTÍCULO 5°.- Comuníquese, dese a la Dirección Nacional del Registro Oficial "
        "para su publicación en el Boletín Oficial y archívese.",
        "Carlos Daniel Castagneto",
        "NOTA: El/los Anexo/s que integra/n este(a) Disposición se publican en la edición "
        "web del BORA -www.boletinoficial.gob.ar-",
        "e. 30/11/2022 N° 97811/22 v. 30/11/2022",
    ]
    order = ["VISTO", "CONSIDERANDO:", "Que en el artículo 3º", "Por ello,", "DISPONE:"]
    positions = [next(i for i, t in enumerate(texts) if t.startswith(p)) for p in order]
    assert positions == sorted(positions)


def test_page_247_drops_scripts_and_marks_the_infoleg_note(page_247):
    """REQ-015: los scripts de medición del encabezado y la nota que Infoleg agrega al
    pie no son texto de la norma: quedan en la lectura como líneas descartadas, con su
    motivo, y no aparecen en el texto del documento."""
    joined = "\n".join(kept(page_247))
    for noise in ("gtag", "GoogleAnalytics", "InfoLEG", "Nota Infoleg", "Anexos)"):
        assert noise not in joined

    lines = discarded(page_247)
    assert [reason for reason, _ in lines] == [
        DISCARD_SCRIPT,
        DISCARD_SCRIPT,
        DISCARD_HEAD,
        DISCARD_INFOLEG_NOTE,
    ]
    assert lines[2][1] == "InfoLEG - Ministerio de Justicia y Derechos Humanos - Argentina"
    assert lines[3][1] == (
        "(Nota Infoleg: Los anexos referenciados en la presente norma han sido extraídos "
        "de la edición web de Boletín Oficial. Los mismos pueden consultarse en el "
        "siguiente link: Anexos)"
    )
    assert all_lines(page_247)[-1].discarded == DISCARD_INFOLEG_NOTE


# --- Página completa de la 297/03 (REQ-015) --------------------------------------------


def test_page_297_is_read_whole(page_297):
    """REQ-015: la página completa de la 297/03 se lee de la primera a la última línea,
    con el índice y el articulado del anexo hasta el artículo 64, el signo por mil y sin
    entidades ni caracteres de control."""
    texts = kept(page_297)

    assert texts[0] == "MINISTERIO DE ECONOMIA Y PRODUCCION"
    assert texts[-1] == "e. 13/6 N° 417.913 v. 13/6/2003"
    # Un bloque por cada uno de los 716 párrafos `<P>` del archivo, todos con texto, y
    # 133 que empiezan con "ARTICULO": 5 de la disposición, 64 del índice y 64 del
    # articulado del anexo.
    assert len(texts) == 716
    assert sum(text.startswith("ARTICULO") for text in texts) == 5 + 64 + 64
    # Las 71 rayas (byte 0x97) del archivo.
    assert sum(text.count("—") for text in texts) == 71
    assert "ARTICULO 64.- VIGENCIA" in texts
    assert texts[-2].startswith("ARTICULO 64. — VIGENCIA. Este Régimen entrará en vigencia")
    assert any("UNO POR MIL (1 ‰)" in text for text in texts)
    for text in texts:
        assert not C1_CONTROLS.search(text), text
        assert "�" not in text, text
        assert not ENTITY.search(text), text
        assert "\n" not in text and "  " not in text and text == text.strip(), text
    assert [reason for reason, _ in discarded(page_297)] == [
        DISCARD_SCRIPT,
        DISCARD_SCRIPT,
        DISCARD_HEAD,
    ]


@pytest.mark.parametrize("path", [EXTRACT_297, PAGE_247, PAGE_297], ids=lambda p: p.name)
def test_no_word_of_the_body_is_lost(path):
    """REQ-015: las palabras del cuerpo de la página, sacadas con un lector independiente
    (el de la biblioteca estándar), son las mismas y en el mismo orden que las de las
    líneas leídas que no vienen del encabezado ni de scripts. Lo descartado del cuerpo,
    como la nota de Infoleg, sigue en la lectura."""
    reading = read(path)
    words = " ".join(
        line.text
        for line in all_lines(reading)
        if line.discarded not in (DISCARD_SCRIPT, DISCARD_STYLE, DISCARD_HEAD)
    ).split()
    assert words == body_words(path, detect_encoding(path.read_bytes()))


# --- Reglas generales, para cualquier sitio (REQ-015) ----------------------------------


def test_generic_rules_drop_scripts_and_styles_and_keep_unknown_text():
    """REQ-015: en una página de un sitio sin regla propia se descartan solo los scripts,
    los estilos y el encabezado HTML; el resto del texto se conserva, aunque sea un menú,
    porque perder texto sin aviso es peor que conservar ruido (ADR-0004)."""
    data = (
        "<html><head><title>Sitio</title><style>p { color: red; }</style></head><body>"
        "<nav>Inicio | Normas</nav>"
        "<script>var x = 1;</script>"
        "<p>ARTÍCULO 1°.- Texto <b>de la</b> norma.</p><div>Firma<br>Cargo</div>"
        "</body></html>"
    ).encode("utf-8")
    reading = read_web(data)

    assert kept(reading) == [
        "Inicio | Normas",
        "ARTÍCULO 1°.- Texto de la norma.",
        "Firma",
        "Cargo",
    ]
    assert discarded(reading) == [
        (DISCARD_HEAD, "Sitio"),
        (DISCARD_STYLE, "p { color: red; }"),
        (DISCARD_SCRIPT, "var x = 1;"),
    ]


@pytest.mark.parametrize(
    "data",
    [
        b'<meta charset="utf-8"><p>N&nbsp;297</p>',
        b"<p>N\xa0297</p>",
    ],
    ids=["entidad-nbsp", "byte-a0-windows-1252"],
)
def test_a_hard_space_is_kept(data):
    """REQ-015: el espacio duro, escrito como entidad `&nbsp;` o como el byte 0xA0 de
    windows-1252, se conserva en la línea: no es espacio en blanco de HTML. Lo pasa a
    espacio común el texto canónico, no la lectura."""
    assert kept(read_web(data)) == ["N\xa0297"]


def test_a_page_without_text_is_not_read():
    """REQ-015, REQ-004: una página que no trae texto del documento (solo scripts) figura
    como no leída."""
    reading = read_web(b"<html><head><script>var x = 1;</script></head><body></body></html>")

    assert reading.pages[0].status == PAGE_NOT_READ
    assert kept(reading) == []
