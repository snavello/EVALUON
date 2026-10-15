"""Las instrucciones simplificadas no copian casos (T-278; REQ-119; plan 016, umbral 6; P4, P7).

Los casos 00 a 06 y el caso chico son casos de medición: si una instrucción repite su texto, la
medición enseña justo lo que mide. Para cada versión de `SIMPLIFIED` (la tabla de
`test_instrucciones_largo.py`, con el bloque de definiciones incluido):

1. **Ninguna secuencia de 6 palabras seguidas** (sin tildes ni mayúsculas) aparece en el cuerpo
   de los pliegos, las circulares, las ofertas y los dictámenes de los casos 00 a 06
   (`corpus/casos/caso-0N/{pliego,circulares,ofertas,evaluacion,otros}/`; fuera de git, P4) ni
   del caso chico (`tests/*/data/caso-chico/`, inventado y público). Contra `corpus/casos/` la
   prueba se salta y lo avisa si no está montado; el caso chico se comprueba siempre. Para
   correr la prueba completa:
   `docker compose run --rm -v ./corpus/casos:/app/corpus/casos:ro app pytest
   tests/test_instrucciones_sin_casos.py`.
2. **Sin ejemplos con contenido de licitación**: ninguna sección ni línea que arme un ejemplo
   («Ejemplo», «Ejemplos»). Lo que se admite es el esqueleto de la salida con marcadores.

El texto de los casos no se copia a ningún test ni fixture: se lee desde `corpus/` en el momento
y los fallos muestran la oración de la instrucción, nunca la del caso. Los textos de prueba
son inventados.
"""

import functools
import io
import re
import sys
import zipfile
from pathlib import Path

import pytest
from django.conf import settings

from tests.assessment.test_generalidad_evaluacion import shingles
from tests.test_instrucciones_largo import SIMPLIFIED, effective_text

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"
SMALL_CASES = sorted((ROOT / "tests").glob("*/data/caso-chico"))
SIZE = 6
CASE_NAME = re.compile(r"^caso-0[0-6]$")
CASE_FOLDERS = ("pliego", "circulares", "ofertas", "evaluacion", "otros")
TEXT_SUFFIXES = {".txt", ".md", ".html", ".htm", ".csv", ".yaml", ".yml"}
# Un título o una línea de ejemplo: «Ejemplo», «Ejemplos», «### Ejemplo 3», «- Ejemplo:».
EXAMPLE_LINE = re.compile(r"(?im)^[\s#>*\-\d.)]*ejemplos?\b")


# --- Lectura de los casos ---------------------------------------------------------------------


def _pdf_text(data):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()


def _docx_text(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", "replace")
    return re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml))


def text_of(name, data):
    """El texto de un archivo de un caso: PDF (capa de texto), DOCX, ZIP (sus miembros) o
    texto plano. Una imagen o un formato que no se lee da vacío."""
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".pdf":
            return _pdf_text(data)
        if suffix == ".docx":
            return _docx_text(data)
        if suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return "\n".join(text_of(member, archive.read(member))
                                 for member in archive.namelist() if not member.endswith("/"))
        if suffix in TEXT_SUFFIXES:
            return data.decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, RuntimeError, ValueError):
        return ""
    return ""


def folder_shingles(files):
    known = set()
    for path in files:
        known |= shingles(text_of(path.name, path.read_bytes()), SIZE)
    return known


@functools.lru_cache(maxsize=1)
def corpus_shingles():
    """Las secuencias de 6 palabras de los casos 00 a 06 de `corpus/casos/`; vacío si no
    está montado."""
    if not CASES.is_dir():
        return frozenset()
    files = [path for case in sorted(CASES.iterdir()) if CASE_NAME.match(case.name)
             for folder in CASE_FOLDERS for path in sorted((case / folder).rglob("*"))
             if path.is_file()]
    return frozenset(folder_shingles(files))


@functools.lru_cache(maxsize=1)
def small_case_shingles():
    """Las del caso chico (inventado, en el repositorio): pliego, ofertas y dictamen esperado."""
    files = [path for case in SMALL_CASES for path in sorted(case.rglob("*"))
             if path.is_file() and path.suffix.lower() in {".pdf", ".yaml", ".yml"}]
    return frozenset(folder_shingles(files))


# --- Comprobaciones ---------------------------------------------------------------------------


def copied_sequences(text, known):
    """Las secuencias de 6 palabras del `text` de una instrucción que están en `known`."""
    return sorted(shingles(text, SIZE) & known)


def copy_problems(table, known):
    """`[texto]` por cada versión de `table` que repite 6 palabras seguidas de `known`. El texto
    dice la versión, cuántas secuencias y en qué líneas de la instrucción: nunca la secuencia,
    que es texto de un caso (P4)."""
    problems = []
    for version, entry in table.items():
        text = effective_text(version, entry)
        hits = copied_sequences(text, known)
        if hits:
            lines = [number for number, line in enumerate(text.splitlines(), 1)
                     if shingles(line, SIZE) & set(hits)]
            problems.append(f"{version}: {len(hits)} secuencias de {SIZE} palabras copiadas de un "
                            f"caso, en las líneas {lines or 'entre dos líneas'} de la instrucción")
    return problems


def example_problems(table):
    """`[texto]` por cada versión de `table` con una sección o una línea de ejemplos."""
    return [f"{version}: línea de ejemplo «{match.group(0).strip()[:40]}…»"
            for version, entry in table.items()
            for match in EXAMPLE_LINE.finditer(effective_text(version, entry))]


# --- Pruebas sobre las versiones listadas ---------------------------------------------------------


def test_no_simplified_instruction_repeats_six_words_of_the_small_case():
    """REQ-119 (umbral 6, P4): ninguna instrucción de `SIMPLIFIED` repite 6 palabras seguidas
    del pliego, las ofertas ni el dictamen del caso chico. Corre siempre (el caso chico está en
    el repositorio)."""
    if SIMPLIFIED:
        assert len(small_case_shingles()) > 100
    assert copy_problems(SIMPLIFIED, small_case_shingles()) == []


def test_no_simplified_instruction_repeats_six_words_of_the_cases():
    """REQ-119 (umbral 6, P4): ninguna instrucción de `SIMPLIFIED` repite 6 palabras seguidas del
    cuerpo de los pliegos, circulares, ofertas y dictámenes de los casos 00 a 06. Se salta si
    `corpus/casos/` no está montado."""
    known = corpus_shingles()
    if not known:
        pytest.skip("corpus/casos/ no está montado en este entorno: montarlo para comprobar que "
                    "ninguna instrucción copia el texto de los casos (docker compose run --rm "
                    "-v ./corpus/casos:/app/corpus/casos:ro app pytest "
                    "tests/test_instrucciones_sin_casos.py)")
    assert len(known) > 10000

    assert copy_problems(SIMPLIFIED, known) == []


def test_no_simplified_instruction_has_examples():
    """REQ-119 (umbral 6): ninguna instrucción de `SIMPLIFIED` trae una sección ni una línea de
    «Ejemplo»: solo el esqueleto de la salida con marcadores. Corre siempre."""
    assert example_problems(SIMPLIFIED) == []


# --- Las pruebas detectan lo que dicen detectar (casos y versiones inventados) ----------------------


# Un tramo inventado de un «caso» y dos instrucciones de prueba: una que lo copia con otras
# mayúsculas y tildes, otra que dice lo mismo con otras palabras.
INVENTED_CASE = ("La firma oferente deberá constituir una garantía de mantenimiento de oferta "
                 "equivalente al cinco por ciento del monto cotizado para cada renglón.")
COPYING = "Regla: la FIRMA oferente deberá constituir una garantía de mantenimiento de oferta."
CLEAN = "Regla: se pide una garantía de la oferta, calculada sobre lo cotizado por renglón."


def _entry(tmp_path, name, text):
    path = tmp_path / f"{name}.md"
    path.write_text(text + "\n", encoding="utf-8")
    return {"path": path}


def test_a_sentence_copied_from_an_invented_case_fails(tmp_path):
    """REQ-119 (umbral 6): una oración copiada de un caso inventado (aunque cambien las
    mayúsculas) hace fallar la comprobación; una instrucción que dice lo mismo con otras palabras
    pasa. El fallo muestra la oración de la instrucción."""
    known = shingles(INVENTED_CASE, SIZE)
    table = {"matriz-extraccion-v99": _entry(tmp_path, "matriz-extraccion-v99", COPYING),
             "matriz-union-v99": _entry(tmp_path, "matriz-union-v99", CLEAN)}

    problems = copy_problems(table, known)

    assert len(problems) == 1 and problems[0].startswith("matriz-extraccion-v99:")
    assert copy_problems({"matriz-union-v99": table["matriz-union-v99"]}, known) == []


def test_five_words_in_common_are_not_a_copy(tmp_path):
    """REQ-119 (umbral 6): el umbral son 6 palabras seguidas: cinco en común no cuentan."""
    known = shingles("deberá constituir una garantía de mantenimiento", SIZE)
    entry = {"x-v1": _entry(tmp_path, "x-v1", "Se debe constituir una garantía de mantenimiento")}

    assert copy_problems(entry, known) == []


def test_six_words_in_common_are_a_copy(tmp_path):
    """REQ-119 (umbral 6; D-278-1 de la verificación de T-278): el tamaño es 6 palabras: una
    instrucción que comparte exactamente 6 palabras seguidas con un caso falla, y con 5 pasa."""
    assert SIZE == 6
    known = shingles("Nube verde salta sobre el puente rojo.", SIZE)
    six = {"x-v1": _entry(tmp_path, "x-v1", "Regla: verde salta sobre el puente rojo, y nada más.")}
    five = {"x-v2": _entry(tmp_path, "x-v2", "Regla: salta sobre el puente rojo, y nada más.")}

    assert len(copy_problems(six, known)) == 1
    assert copy_problems(five, known) == []


def test_the_comparison_ignores_upper_case(tmp_path):
    """REQ-119 (umbral 6; D-278-2): un caso escrito todo en mayúsculas y una instrucción en
    minúsculas con las mismas 6 palabras seguidas son una copia (la comparación pasa todo a
    minúsculas antes de cortar en palabras)."""
    known = shingles("NUBE VERDE SALTA SOBRE EL PUENTE ROJO", SIZE)
    entry = {"x-v1": _entry(tmp_path, "x-v1", "Regla: nube verde salta sobre el puente rojo.")}

    assert known
    assert len(copy_problems(entry, known)) == 1


# Las cinco carpetas que el umbral 6 del plan manda leer, escritas aparte de `CASE_FOLDERS` para que
# la prueba note si el lector deja de leer alguna.
THE_FIVE_FOLDERS = ("pliego", "circulares", "ofertas", "evaluacion", "otros")


@pytest.fixture
def invented_corpus(tmp_path, monkeypatch):
    """Un árbol de casos inventado: una oración propia en cada carpeta de cada caso 00 a 06, y
    otras en lo que no se lee (un caso 07 y la carpeta `esperado`)."""
    root = tmp_path / "casos"

    def sentence(case, folder):
        return f"marca {case} {folder} alfa beta gama delta"

    for case in range(7):
        for folder in THE_FIVE_FOLDERS:
            target = root / f"caso-0{case}" / folder / "sub"
            target.mkdir(parents=True)
            (target / "texto.txt").write_text(sentence(case, folder), encoding="utf-8")
        (root / f"caso-0{case}" / "esperado").mkdir()
        (root / f"caso-0{case}" / "esperado" / "lista.txt").write_text(
            sentence(case, "esperado"), encoding="utf-8")
    (root / "caso-07" / "pliego").mkdir(parents=True)
    (root / "caso-07" / "pliego" / "texto.txt").write_text(sentence(7, "pliego"), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "CASES", root)
    corpus_shingles.cache_clear()
    yield sentence
    corpus_shingles.cache_clear()


def test_the_corpus_reader_reads_every_folder_of_every_case(invented_corpus):
    """REQ-119 (umbral 6; D-278-2): el lector del corpus lee las cinco carpetas (pliego,
    circulares, ofertas, evaluación y otros, también en subcarpetas) de los siete casos 00 a 06,
    y nada más (ni un caso 07 ni la lista esperada)."""
    known = corpus_shingles()

    for case in range(7):
        for folder in THE_FIVE_FOLDERS:
            assert shingles(invented_corpus(case, folder), SIZE) <= known, (case, folder)
        assert not shingles(invented_corpus(case, "esperado"), SIZE) & known
    assert not shingles(invented_corpus(7, "pliego"), SIZE) & known


def test_a_copy_inside_the_definitions_block_is_detected(tmp_path):
    """REQ-119 (umbral 6; D-278-2): la comparación mide lo que lee el modelo, con el bloque de
    definiciones adentro: una copia que está en el bloque, y no en el archivo de la instrucción,
    falla."""
    (tmp_path / "matriz-definiciones-v98.md").write_text(COPYING + "\n", encoding="utf-8")
    body = _entry(tmp_path, "matriz-extraccion-v98", "Regla propia.\n\n{{DEFINICIONES}}")
    entry = {"matriz-extraccion-v98": {**body, "definitions": "matriz-definiciones-v98"}}

    raw = Path(body["path"]).read_text(encoding="utf-8")
    assert not shingles(raw, SIZE) & shingles(INVENTED_CASE, SIZE)
    assert len(copy_problems(entry, shingles(INVENTED_CASE, SIZE))) == 1


def test_the_listed_versions_test_fails_with_a_copied_sentence(tmp_path, monkeypatch):
    """REQ-119 (umbral 6): con la oración copiada en `SIMPLIFIED`, la comprobación sobre una
    fuente de casos inventada devuelve el fallo."""
    monkeypatch.setitem(SIMPLIFIED, "matriz-extraccion-v99",
                        _entry(tmp_path, "matriz-extraccion-v99", COPYING))

    assert copy_problems(SIMPLIFIED, shingles(INVENTED_CASE, SIZE)) != []


def test_an_instruction_with_examples_fails(tmp_path):
    """REQ-119 (umbral 6): una sección «Ejemplos» o una línea «Ejemplo 3:» hacen fallar la
    comprobación; la palabra dentro de una oración («por ejemplo») no."""
    with_examples = _entry(tmp_path, "matriz-extraccion-v98",
                           "Regla.\n\n### Ejemplos\n\nEntrada: algo.\n- Ejemplo 3: otra cosa.")
    inline = _entry(tmp_path, "matriz-union-v98", "Se une, por ejemplo, lo que sigue igual.")

    assert len(example_problems({"matriz-extraccion-v98": with_examples})) == 2
    assert example_problems({"matriz-union-v98": inline}) == []


def test_the_text_reader_reads_pdf_docx_zip_and_plain_text(tmp_path):
    """REQ-119: el lector de casos lee DOCX, ZIP y texto plano (y da vacío con una imagen); el
    PDF se prueba con el caso chico del repositorio."""
    docx = io.BytesIO()
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml",
                         "<w:document><w:p><w:t>uno dos tres</w:t></w:p></w:document>")
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("a.txt", "cuatro cinco")
        archive.writestr("b.docx", docx.getvalue())

    assert "uno dos tres" in text_of("x.docx", docx.getvalue())
    assert "cuatro cinco" in text_of("x.zip", packed.getvalue())
    assert "uno dos tres" in text_of("x.zip", packed.getvalue())
    assert text_of("x.jpg", b"\xff\xd8") == ""
    assert text_of("x.docx", b"no es un zip") == ""
    assert len(small_case_shingles()) > 100
