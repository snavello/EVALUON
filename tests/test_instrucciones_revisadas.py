"""Instrucciones al modelo: revisadas y congeladas (T-236; REQ-106; ADR-0055, regla 8; P6, P7).

Dos garantías, como `scripts/models.sha256` con los modelos:

1. **Cobertura.** El informe de revisión (`specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`,
   un resumen sin texto de casos) nombra el 100 % de las instrucciones vigentes: las de la
   matriz, las de la evaluación, la visión, la ficha, el informe técnico, la consulta, el nombre
   del oferente y los datos del procedimiento (las dos últimas vivían en el código y son archivos
   desde T-248).
2. **Versiones congeladas.** Cada versión publicada de una instrucción (cada archivo de las
   carpetas `prompts/` y cada instrucción dentro del código) tiene su huella SHA-256 en
   `tests/fixtures/instrucciones.sha256`, y el archivo no cambió. Una instrucción nueva es una
   versión nueva (archivo nuevo, con su línea en la lista); una publicada no se edita. Si falta
   una línea, el fallo trae la que hay que agregar.

Desde la 016 (T-278; REQ-119; ADR-0070) hay una tercera garantía: el informe de revisión de la 016
(`specs/016-calidad-medible/revision-instrucciones.md`) trae la tabla de decisiones del responsable y,
por cada versión de `SIMPLIFIED` (`tests/test_instrucciones_largo.py`), su tabla «oración →
decisión», con cada oración atada a una decisión de la tabla y, desde T-280 (H-279-5), cada oración de
la instrucción con su fila. El informe no lleva texto de los casos.

Los textos de las instrucciones son inventados o propios del sistema (P4).
"""

import re
from pathlib import Path

import pytest
from django.conf import settings

from evaluon.assessment.services import technical_report
from evaluon.offers import proposal_fields
from evaluon.queries import answering
from evaluon.tenders.proposal import extraction, procedure_fields
from tests.test_instrucciones_largo import SIMPLIFIED
from tests.test_instrucciones_sin_casos import (SIZE, corpus_shingles, shingles,
                                                 small_case_shingles)

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "specs" / "015-uso-y-eleccion-del-modelo" / "revision-instrucciones.md"
REPORT_016 = ROOT / "specs" / "016-calidad-medible" / "revision-instrucciones.md"
FROZEN = Path(__file__).resolve().parent / "fixtures" / "instrucciones.sha256"
PROMPT_DIRS = [
    ROOT / "evaluon" / "tenders" / "prompts",
    ROOT / "evaluon" / "offers" / "prompts",
    ROOT / "evaluon" / "assessment" / "prompts",
    ROOT / "evaluon" / "queries" / "prompts",
]
# Las instrucciones que viven dentro del código: su nombre de versión y su texto. Hoy ninguna: la
# del nombre del oferente y la de los datos del procedimiento pasaron a ser archivos
# (`offers/prompts/oferente-nombre-v2.md` y `tenders/prompts/procedimiento-datos-v2.md`, T-248),
# y sus v1 quedaron publicadas como archivos con los mismos bytes y la misma huella.
INLINE = {}


def current_versions():
    """Los nombres de versión de todas las instrucciones vigentes, tal como las fijan la
    configuración y el código. `unificacion` no tiene archivo: la pasada es de código."""
    names = {version for name, version in settings.MATRIX_PROMPT_VERSIONS.items()
             if name != "unificacion"}
    names |= set(settings.OFFERS_PROMPT_VERSIONS.values())
    names |= set(settings.ASSESSMENT_PROMPT_VERSIONS.values())
    names.add(settings.ASSESSMENT_VISION_PROMPT_VERSION)
    names.add(technical_report.PROMPT_VERSION)
    names.add(proposal_fields.PROMPT_VERSION)
    names.add(procedure_fields.PROMPT_VERSION)
    names |= {answering.PROMPT_VERSION_WITH_DATE, answering.PROMPT_VERSION_WITHOUT_DATE}
    names |= set(INLINE)
    return sorted(names)


def published():
    """`{clave: huella}` de cada versión publicada: la ruta relativa de cada archivo de
    instrucción y el nombre de cada instrucción dentro del código."""
    result = {}
    for folder in PROMPT_DIRS:
        for path in sorted(folder.iterdir()):
            if path.suffix in (".md", ".txt"):
                text = path.read_text(encoding="utf-8")
                result[path.relative_to(ROOT).as_posix()] = extraction.text_sha256(text)
    for name, text in INLINE.items():
        result[name] = extraction.text_sha256(text)
    return result


def frozen():
    result = {}
    for line in FROZEN.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, key = line.split(None, 1)
            result[key.strip()] = digest
    return result


def read_report():
    """El informe de revisión. `docker-compose.yml` no monta `specs/` en la aplicación: dentro del
    contenedor la prueba se salta, salvo que se monte (`docker compose run --rm -v
    ./specs:/app/specs:ro app pytest tests/test_instrucciones_revisadas.py`)."""
    if not REPORT.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el informe")
    return REPORT.read_text(encoding="utf-8")


def test_the_review_report_names_every_current_instruction():
    """REQ-106, REQ-119: el informe de revisión cubre el 100 % de las instrucciones vigentes: nombra
    la versión de cada una. Desde la 016 (T-279), una versión vigente de `SIMPLIFIED` la cubre su
    sección del informe de la 016 (su tabla la comprueba
    `test_every_simplified_version_has_its_table_in_the_016_report`)."""
    report = read_report()
    report_016 = read_report_016()

    missing = [version for version in current_versions() if version not in report
               and not (version in SIMPLIFIED
                        and re.search(rf"(?m)^### {re.escape(version)}[ \t]*$", report_016))]

    assert not missing, f"el informe no nombra: {missing}"
    assert len(current_versions()) >= 20


def test_the_review_report_has_no_case_text():
    """P4 (REQ-106): el informe del repositorio es un resumen: instrucción, hallazgo, gravedad
    y estado; sin fragmentos de los casos ni cifras de filas de un pliego."""
    report = read_report()

    assert "Estado" in report and "Gravedad" in report
    for forbidden in ("LPU25", "procedimiento 10", "Administrador Legitimado"):
        assert forbidden not in report


def test_every_current_instruction_has_a_published_file_or_is_inline():
    """REQ-106: cada versión vigente existe como archivo de instrucción o como instrucción del
    código, y está en la lista de las congeladas."""
    keys = {Path(key).stem: key for key in published() if "/" in key}
    keys.update({name: name for name in INLINE})
    frozen_keys = frozen()

    for version in current_versions():
        assert version in keys, f"no hay archivo ni instrucción con la versión {version}"
        assert keys[version] in frozen_keys, f"falta la huella de {version}"


def test_the_published_versions_are_frozen():
    """REQ-106 (P6, P7): ninguna versión publicada cambió, y toda versión nueva tiene su huella en
    `tests/fixtures/instrucciones.sha256`. Una instrucción publicada no se edita: se crea la
    versión siguiente."""
    expected = frozen()
    actual = published()

    changed = sorted(key for key in expected if key in actual and actual[key] != expected[key])
    assert not changed, f"cambió una versión publicada (crear una versión nueva): {changed}"
    gone = sorted(key for key in expected if key not in actual)
    assert not gone, f"se borró una versión publicada: {gone}"
    new = sorted(key for key in actual if key not in expected)
    assert not new, "falta la huella de una versión nueva; agregar a instrucciones.sha256:\n" + (
        "\n".join(f"{actual[key]}  {key}" for key in new))


@pytest.mark.parametrize("key", sorted(published()))
def test_the_hash_of_a_published_version_is_a_sha256(key):
    """REQ-106: cada huella congelada es un SHA-256 de 64 dígitos hexadecimales."""
    digest = frozen().get(key)

    assert digest is not None and len(digest) == 64
    int(digest, 16)


# --- Informe de la 016: decisiones y oraciones por instrucción (T-278, REQ-119) ------------------------

DECISION_ID = re.compile(r"\bD-\d{2}\b")
SOURCES = ("Spec 003", "Spec 004", "Spec 014", "Spec 015",
           "ADR-0043", "ADR-0053", "ADR-0054", "ADR-0058")


def read_report_016():
    """El informe de la 016. Se salta si `specs/` no está montada, como el de la 015."""
    if not REPORT_016.is_file():
        pytest.skip("specs/ no está montada en este entorno: montarla para comprobar el informe")
    return REPORT_016.read_text(encoding="utf-8")


def table_rows(block):
    """Las filas de datos de las tablas Markdown de `block`: `[[celda, ...]]` (sin el encabezado
    ni la línea de separación)."""
    rows, header_seen = [], False
    for line in block.splitlines():
        if not line.startswith("|"):
            header_seen = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not header_seen:
            header_seen = True
        elif not set("".join(cells)) <= set("-: "):
            rows.append(cells)
    return rows


def decisions_of(report):
    """`{id: fila}` de la tabla de decisiones (filas cuya primera celda es `D-NN`)."""
    return {row[0]: row for row in table_rows(report) if DECISION_ID.fullmatch(row[0])}


def sentence_problems(report, version):
    """Lo que le falta a la tabla «oración → decisión» de `version` en `report`: lista de
    textos (vacía si la tabla está completa y cada fila nombra una decisión que existe)."""
    match = re.search(rf"(?m)^### {re.escape(version)}[ \t]*$(.*?)(?=^#{{1,3}} |\Z)", report,
                      re.S)
    if not match:
        return [f"{version}: el informe no tiene la sección «### {version}»"]
    known = set(decisions_of(report))
    rows = [row for row in table_rows(match.group(1)) if len(row) >= 2]
    if not rows:
        return [f"{version}: la sección no tiene filas de oración y decisión"]
    problems = []
    for sentence, decision, *_ in rows:
        cited = set(DECISION_ID.findall(decision))
        if not sentence or sentence.startswith("(pendiente"):
            problems.append(f"{version}: fila sin completar")
        elif not cited or not cited <= known:
            problems.append(f"{version}: una oración nombra una decisión que no está en la tabla "
                            f"({decision!r})")
    return problems


def test_the_016_report_has_the_table_of_decisions_with_its_sources():
    """REQ-119 (plan 016, «Paso 2»): el informe de la 016 trae la tabla de decisiones con una fuente
    de cada spec (003, 004, 014, 015) y de cada ADR (0043, 0053, 0054, 0058), y cada fila tiene su
    decisión y su fuente."""
    report = read_report_016()
    decisions = decisions_of(report)

    assert len(decisions) >= 31
    # D-278-3: las decisiones van de D-01 en adelante, sin saltos (quitar una fila se nota).
    assert sorted(decisions) == [f"D-{n:02d}" for n in range(1, len(decisions) + 1)]
    for row in decisions.values():
        assert len(row) == 4 and all(row), row
    sources = " ".join(row[2] for row in decisions.values())
    missing = [source for source in SOURCES if source not in sources]
    assert not missing, f"ninguna decisión cita: {missing}"


def test_every_simplified_version_has_its_table_in_the_016_report():
    """REQ-119: toda versión de `SIMPLIFIED` tiene en el informe de la 016 su tabla «oración →
    decisión» completa, con cada oración atada a una decisión de la tabla."""
    report = read_report_016()

    problems = [problem for version in SIMPLIFIED for problem in sentence_problems(report, version)]

    assert problems == []


SAMPLE_REPORT = """
| Id | Decisión | Fuente | Aplica a |
|---|---|---|---|
| D-01 | Una decisión inventada | Spec 099 | todas |

### matriz-prueba-v1

| Oración | Decisión |
|---|---|
| Se pide lo primero. | D-01 |
| Se pide lo segundo. | D-01, D-01 |

### matriz-prueba-v2

| Oración | Decisión |
|---|---|
| (pendiente: T-999) | (pendiente) |

### matriz-prueba-v3

| Oración | Decisión |
|---|---|
| Se pide algo que ninguna decisión pide. | D-77 |
"""


def test_the_table_check_finds_a_missing_pending_or_unattached_table():
    """REQ-119: la comprobación pasa con una tabla completa (informe de prueba inventado) y falla
    con la sección que falta, la que sigue pendiente y la oración atada a una decisión que no
    existe."""
    assert sentence_problems(SAMPLE_REPORT, "matriz-prueba-v1") == []
    assert sentence_problems(SAMPLE_REPORT, "matriz-prueba-v0")[0].endswith(
        "no tiene la sección «### matriz-prueba-v0»")
    assert sentence_problems(SAMPLE_REPORT, "matriz-prueba-v2") == [
        "matriz-prueba-v2: fila sin completar"]
    assert "no está en la tabla" in sentence_problems(SAMPLE_REPORT, "matriz-prueba-v3")[0]


def test_a_section_without_rows_fails_the_table_check():
    """REQ-119 (D-278-3 de la verificación de T-278): una sección con el encabezado de la tabla y sin
    filas no cuenta como tabla completa (informe de prueba inventado)."""
    report = SAMPLE_REPORT + """
### matriz-prueba-v4

| Oración | Decisión |
|---|---|
"""

    assert sentence_problems(report, "matriz-prueba-v4") == [
        "matriz-prueba-v4: la sección no tiene filas de oración y decisión"]


def test_a_simplified_version_without_a_table_fails_the_report_check(monkeypatch):
    """REQ-119: con una versión de prueba en `SIMPLIFIED` que el informe no tiene, la comprobación
    de las tablas devuelve el fallo."""
    monkeypatch.setitem(SIMPLIFIED, "matriz-prueba-v0", {"path": "no-importa"})
    report = read_report_016()

    problems = [problem for version in SIMPLIFIED for problem in sentence_problems(report, version)]

    assert problems != []


def test_the_016_report_has_no_case_text():
    """P4 (REQ-119): el informe de la 016 no lleva texto de los casos: ni las marcas que el informe
    de la 015 ya prohíbe, ni 6 palabras seguidas del caso chico y, si `corpus/casos/` está montado,
    de los pliegos, circulares, ofertas y dictámenes de los casos 00 a 06. El fallo cuenta
    secuencias, nunca muestra texto de un caso."""
    report = read_report_016()
    for forbidden in ("LPU25", "procedimiento 10", "Administrador Legitimado"):
        assert forbidden not in report

    assert len(shingles(report, SIZE) & small_case_shingles()) == 0
    known = corpus_shingles()
    if not known:
        pytest.skip("corpus/casos/ no está montado en este entorno: el informe se comprobó solo "
                    "contra el caso chico; montarlo para comprobar contra los casos 00 a 06")
    hits = len(shingles(report, SIZE) & known)
    assert hits == 0, f"{hits} secuencias de {SIZE} palabras del informe están en los casos"


# --- T-280 (H-279-5): cada oración de una instrucción tiene su fila ------------------------------------

# Un punto que cierra una oración: lo sigue un espacio y una mayúscula, una comilla o un signo de apertura.
SENTENCE_END = re.compile(r'(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ¿¡«"])')
# Las oraciones que no llevan fila a propósito, con su motivo (el informe de la 016 lo dice).
WITHOUT_ROW = {
    # Procedencia, no regla (H-279-3; el Coordinador, en el encargo de T-280).
    "matriz-definiciones-v9": {
        "Estas definiciones son decisiones del responsable y valen para toda la matriz."},
}
# Lo más corto que puede ser una fila que nombra una oración larga por su primera frase.
MIN_PREFIX = 20


def _is_label(line):
    """Un rótulo que ordena el texto: hasta cuatro palabras y dos puntos («Unidad de la fila:»)."""
    return line.endswith(":") and len(line.split()) <= 4


def instruction_sentences(text):
    """Las oraciones de una instrucción (el archivo, sin el bloque de definiciones): cada línea sin
    su viñeta, partida donde un punto cierra una oración. No son oraciones los títulos en
    mayúsculas, la marca del bloque, las marcas de parte del filtro («# COMÚN»), los rótulos y las
    líneas del esqueleto JSON."""
    found = []
    for line in text.replace("\r\n", "\n").splitlines():
        line = line.strip()
        if not line or line.startswith(("{", "#")) or line == "{{DEFINICIONES}}":
            continue
        line = re.sub(r"^-\s+", "", line)
        if line.upper() == line or _is_label(line):
            continue
        found.extend(part.strip() for part in SENTENCE_END.split(line) if part.strip())
    return found


def _norm(text):
    return " ".join(text.replace("`", "").split()).rstrip(".:;").strip()


def _covers(row, sentence):
    """Si la fila nombra la oración: igual, por su primera frase o con lo que agrega la fila (el
    esqueleto de la salida)."""
    if row == sentence:
        return True
    shorter = min(len(row), len(sentence))
    return shorter >= MIN_PREFIX and (sentence.startswith(row) or row.startswith(sentence))


def uncovered_sentences(report, version, text):
    """Las oraciones de `text` (la instrucción `version`) que su tabla del informe no nombra."""
    match = re.search(rf"(?m)^### {re.escape(version)}[ \t]*$(.*?)(?=^#{{1,3}} |\Z)", report, re.S)
    rows = [_norm(row[0]) for row in table_rows(match.group(1))] if match else []
    exempt = {_norm(sentence) for sentence in WITHOUT_ROW.get(version, ())}
    return [sentence for sentence in instruction_sentences(text)
            if _norm(sentence) not in exempt
            and not any(_covers(row, _norm(sentence)) for row in rows)]


def _raw(entry):
    return (ROOT / entry["path"]).read_text(encoding="utf-8")


def test_every_sentence_of_a_simplified_instruction_has_its_row():
    """REQ-119 (H-279-5 de la verificación de T-279): cada oración de cada instrucción de
    `SIMPLIFIED` tiene su fila en la tabla «oración → decisión» del informe de la 016; borrar una
    fila, o agregar una oración sin su fila, hace fallar la prueba."""
    report = read_report_016()

    missing = {version: uncovered_sentences(report, version, _raw(entry))
               for version, entry in SIMPLIFIED.items()}

    assert {version: rows for version, rows in missing.items() if rows} == {}


def test_the_sentences_without_a_row_are_in_their_instruction():
    """REQ-119: las oraciones que no llevan fila a propósito están en su instrucción (la excepción no
    queda vieja ni tapa otra cosa) y el informe dice por qué."""
    report = read_report_016()
    for version, sentences in WITHOUT_ROW.items():
        text = _raw(SIMPLIFIED[version])
        for sentence in sentences:
            assert sentence in text, (version, sentence)
            assert sentence.split("…")[0][:40] in report, (version, sentence)


SAMPLE_INSTRUCTION = """TÍTULO DE PRUEBA

Primera oración de la prueba, que es larga. Segunda oración de la prueba.

Por cada fila:
- "campo": lo que lleva el campo de prueba.
{"F1": {"campo": "<marcador>"}}
"""

SAMPLE_TABLE = """
### matriz-prueba-v5

| Oración | Decisión |
|---|---|
| Primera oración de la prueba, que es larga. | D-01 |
| Segunda oración de la prueba. | D-01 |
| "campo": lo que lleva el campo de prueba. | D-01 |
"""


def test_the_sentence_check_finds_a_deleted_row_and_a_new_sentence():
    """REQ-119 (H-279-5): con una instrucción y una tabla de prueba (inventadas) la comprobación pasa;
    al borrar una fila o al sumar una oración, falla y nombra la oración. Los títulos, los rótulos y
    el esqueleto no cuentan."""
    assert instruction_sentences(SAMPLE_INSTRUCTION) == [
        "Primera oración de la prueba, que es larga.", "Segunda oración de la prueba.",
        '"campo": lo que lleva el campo de prueba.']
    assert uncovered_sentences(SAMPLE_TABLE, "matriz-prueba-v5", SAMPLE_INSTRUCTION) == []

    without_row = SAMPLE_TABLE.replace("| Segunda oración de la prueba. | D-01 |\n", "")
    assert uncovered_sentences(without_row, "matriz-prueba-v5", SAMPLE_INSTRUCTION) == [
        "Segunda oración de la prueba."]

    longer = SAMPLE_INSTRUCTION.replace("Segunda oración de la prueba.",
                                        "Segunda oración de la prueba. Una regla nueva sin fila.")
    assert uncovered_sentences(SAMPLE_TABLE, "matriz-prueba-v5", longer) == [
        "Una regla nueva sin fila."]
    assert uncovered_sentences(SAMPLE_TABLE, "matriz-prueba-v0", SAMPLE_INSTRUCTION) != []


def test_a_row_named_by_its_first_phrase_covers_its_sentence_but_a_short_one_does_not():
    """REQ-119 (H-279-5): una fila que nombra una oración larga por su primera frase la cubre; una
    fila de menos de 20 caracteres no cubre a otra oración que empieza igual."""
    assert _covers(_norm("Primera oración de la prueba"), _norm("Primera oración de la prueba, larga."))
    assert not _covers(_norm("Primera."), _norm("Primera oración de la prueba."))
