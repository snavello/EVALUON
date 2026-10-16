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
la instrucción con su fila. El informe no lleva texto de los casos. Desde T-282, toda instrucción vigente
está en `SIMPLIFIED` (salvo las de `NOT_SIMPLIFIED`, con su motivo) y cada definición derivada del
informe conserva su marca («pendiente» o «confirmada») y su origen, como dice la tabla de control
`DERIVED` (H-281-4).

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
    "matriz-definiciones-v10": {
        "Estas definiciones son decisiones del responsable y valen para toda la matriz."},
}
# T-281 (H-280-4, a): la fila de la salida puede sumar, después de la oración completa, el esqueleto de
# la salida con marcadores (las de T-279 y T-280). Es lo único que una fila puede agregar.
SKELETON_NOTE = ", y el esqueleto de la salida con marcadores"


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
    """Si la fila nombra la oración: la oración completa, igual, o seguida solo de la nota del
    esqueleto de la salida (`SKELETON_NOTE`). Desde T-281 (H-280-4, a) no alcanza el comienzo: una
    cláusula agregada al final de una oración que tenía fila, o una quitada, la deja sin fila."""
    return row == sentence or row.startswith(sentence + SKELETON_NOTE)


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


def test_a_clause_added_to_a_sentence_with_a_row_leaves_it_without_its_row():
    """REQ-119 (H-280-4, a, de la verificación de T-280): la fila compara la oración completa, no su
    comienzo. Agregar una cláusula al final de una oración que ya tenía fila, o quitarle una, la deja
    sin fila y la prueba la nombra (instrucción y tabla de prueba, inventadas)."""
    added = SAMPLE_INSTRUCTION.replace("Segunda oración de la prueba.",
                                       "Segunda oración de la prueba, y además otra cosa.")
    assert uncovered_sentences(SAMPLE_TABLE, "matriz-prueba-v5", added) == [
        "Segunda oración de la prueba, y además otra cosa."]

    cut = SAMPLE_INSTRUCTION.replace("Primera oración de la prueba, que es larga.",
                                     "Primera oración de la prueba.")
    assert uncovered_sentences(SAMPLE_TABLE, "matriz-prueba-v5", cut) == [
        "Primera oración de la prueba."]

    assert not _covers(_norm("Primera oración de la prueba"), _norm("Primera oración de la prueba, larga."))
    assert not _covers(_norm("Primera."), _norm("Primera oración de la prueba."))


def test_the_row_of_the_output_may_add_only_the_skeleton_note():
    """REQ-119 (H-280-4, a): la fila de la salida puede sumar, después de la oración completa, la nota
    del esqueleto de la salida; cualquier otro agregado de la fila no cubre la oración."""
    sentence = _norm("Salida, un objeto JSON con una propiedad por alias:")
    assert _covers(_norm("Salida, un objeto JSON con una propiedad por alias, y el esqueleto de la salida "
                         "con marcadores (campo de prueba)."), sentence)
    assert not _covers(_norm("Salida, un objeto JSON con una propiedad por alias y otra cosa."), sentence)


def test_every_sentence_of_the_real_instructions_fails_with_a_clause_added():
    """REQ-119 (H-280-4, a): sobre las instrucciones reales de `SIMPLIFIED`, agregar una cláusula al
    final de cualquier oración que tiene fila la deja sin fila (se prueba con la primera y la última
    oración de cada instrucción)."""
    report = read_report_016()
    for version, entry in SIMPLIFIED.items():
        text = _raw(entry)
        exempt = {_norm(sentence) for sentence in WITHOUT_ROW.get(version, ())}
        found = [sentence for sentence in instruction_sentences(text) if _norm(sentence) not in exempt]
        for sentence in {found[0], found[-1]}:
            core = sentence.rstrip(".:;")
            altered = text.replace(sentence, f"{core}, y además completás lo que falte.", 1)
            assert altered != text, (version, sentence)
            missing = [_norm(s) for s in uncovered_sentences(report, version, altered)]
            assert _norm(f"{core}, y además completás lo que falte.") in missing, (version, sentence)



# --- T-282: toda instrucción vigente es de la 016 -------------------------------------------------------

# Las vigentes que quedan fuera de `SIMPLIFIED` a propósito, con su motivo. Hoy una sola: la
# `consulta-v1`, que usa solo el camino sin fecha de `answering.answer` (T-018); ningún pedido de la
# aplicación lo usa (`services.ask` siempre pasa la fecha) y una versión publicada no se edita.
NOT_SIMPLIFIED = {
    "consulta-v1": "camino sin fecha de `answering.answer` (T-018), que la aplicación no usa: "
                   "`services.ask` siempre pasa la fecha; versión publicada, no se edita",
}


def test_every_current_instruction_is_simplified():
    """REQ-119 (T-282; plan 016, «Paso 2»): toda instrucción vigente está en `SIMPLIFIED`, y por eso
    bajo las tres pruebas (largo, no calco y tabla «oración → decisión»), salvo las de
    `NOT_SIMPLIFIED`, cada una con su motivo; y `SIMPLIFIED` no lista una versión que ya no rige
    (salvo el bloque de definiciones, que rige por la matriz)."""
    current = set(current_versions())

    outside = sorted(current - set(SIMPLIFIED) - set(NOT_SIMPLIFIED))
    stale = sorted(set(SIMPLIFIED) - current)

    assert outside == [], f"instrucciones vigentes fuera de SIMPLIFIED: {outside}"
    assert stale == [], f"versiones de SIMPLIFIED que ya no rigen: {stale}"
    assert all(NOT_SIMPLIFIED.values())


def test_the_versions_outside_simplified_are_still_what_their_reason_says():
    """REQ-119 (T-282): la excepción sigue siendo cierta: la `consulta-v1` es la versión del camino
    sin fecha y no la de la consulta con fecha, que es la que usan la pantalla y `correr_evals`; y
    ninguna versión de `NOT_SIMPLIFIED` está también en `SIMPLIFIED`."""
    assert set(NOT_SIMPLIFIED) == {answering.PROMPT_VERSION_WITHOUT_DATE}
    assert answering.PROMPT_VERSION_WITH_DATE in SIMPLIFIED
    assert not set(NOT_SIMPLIFIED) & set(SIMPLIFIED)


def test_the_coverage_check_finds_a_current_instruction_outside_simplified(monkeypatch):
    """REQ-119 (T-282): si una instrucción vigente sale de `SIMPLIFIED` (o se vuelve a una versión
    anterior en la configuración), la comprobación de cobertura falla."""
    monkeypatch.setitem(settings.OFFERS_PROMPT_VERSIONS, "ficha", "ficha-v3")

    assert "ficha-v3" in set(current_versions()) - set(SIMPLIFIED) - set(NOT_SIMPLIFIED)
    with pytest.raises(AssertionError):
        test_every_current_instruction_is_simplified()


# --- T-282 (H-281-4): las derivadas y su tabla de control -----------------------------------------------

# `{id: (estado, fuente)}` de cada definición derivada de la tabla de decisiones: «pendiente» (de
# confirmación del responsable) o «confirmada» (por el responsable, con la fecha y la cita), y la
# celda «Fuente» completa, con su origen. Confirmar una derivada o cambiar su origen pide cambiar esta
# tabla en el mismo commit (H-281-4: quitar la marca o cambiar el origen no hacía fallar nada).
DERIVED = {
    "D-32": ("confirmada", (
        'Derivada de D-01 (spec 003, «Qué es un requisito», 2026-10-03); origen: D-266-1 de la '
        'lista de revisión de la 015 y H-279-1; confirmación: spec 016, 2026-10-15, «Garantía '
        'de cumplimiento de contrato (REQ-102)»')),
    "D-33": ("pendiente", (
        'Derivada de D-01 («aunque la cumpla el organismo»); spec 004, REQ-063; spec 015, '
        '2026-10-12, «1 y luego 3 para no dejarlo sin probar» (la ronda que corrige las '
        'definiciones de lo externo); H-279-3')),
    "D-34": ("pendiente", (
        'Derivada de D-01 y D-04; origen: T-236 de la 015 (definición del Planificador para '
        'aplicar REQ-102); H-279-3')),
    "D-35": ("pendiente", (
        'Derivada de D-04 (spec 003, «Consecuencia del incumplimiento», 2026-10-03: el sistema '
        'sugiere las consecuencias posibles «con su fundamento»); origen: T-248 de la 015 '
        '(`matriz-consecuencias-v2`: «la v1 no decía que una cláusula general alcanza a todos '
        'los requisitos de su punto»); H-280-1')),
    "D-36": ("pendiente", (
        'Derivada de D-05 (spec 003, REQ-031: la matriz aplica el cambio y cita el documento '
        'que lo produjo); origen: T-098 de la 003 (`matriz-circulares-v2`, «sin citas ajenas») '
        'y T-236 de la 015 (`matriz-circulares-v7`: «nunca se elige una cita ajena»); H-280-1')),
    "D-37": ("pendiente", (
        'Derivada de D-02 (spec 003: una fila por renglón del pliego); origen: T-236 de la 015 '
        '(`matriz-circulares-v6`: «"Ítem" vale como renglón»); H-280-2')),
    "D-38": ("pendiente", (
        'Derivada de D-01, D-12 y del ADR-0023, decisión 1; origen: T-236 de la 015 '
        '(`matriz-circulares-v6`: «no es un "agrega", sino un "dato_del_tramite"»); H-280-2')),
    "D-43": ("pendiente", (
        'Derivada de D-41 (ADR-0038: el contraste contesta si el texto citado demuestra la '
        'conclusión); origen: T-151 de la 004 (`contraste-v2`, «no exige más detalle que el '
        'requisito»), conservada en `contraste-v3` y `contraste-v4` (T-237 de la 015); H-281-1')),
    "D-44": ("pendiente", (
        'Derivada de D-14 (spec 015, «Unidad de la fila»: la unidad de sentido no se parte); '
        'origen: T-164 de la 004 (`clausulas-v2`), conservada hasta `clausulas-v5` (T-237 de '
        'la 015); H-281-1')),
    "D-45": ("pendiente", (
        'Derivada de D-26 (spec 014, «Lo que presentó cada oferta») y de la spec 008, REQ-039 '
        '(los fragmentos que responden al requisito); origen: T-146 de la 008 '
        '(`reescritura-v1`) y T-248 de la 015 (`reescritura-v2`); H-281-1')),
    "D-55": ("pendiente", (
        'Derivada de D-51 (ADR-0041, decisión 3: transcribir el texto visible); origen: T-160 '
        'de la 004 (`vision-v1`: la firma que es solo un trazo) y T-177 de la 004 '
        '(`vision-v3`, hallazgo V-1 de T-161: las líneas para escribir encima); H-282-1')),
    "D-56": ("pendiente", (
        'Derivada de D-53 (spec 014, REQ-077: el sistema propone el tipo del procedimiento); '
        'origen: T-248 de la 015 (`procedimiento-datos-v2`; la v1 no la tenía); H-282-1')),
    "D-57": ("pendiente", (
        'Derivada de D-50 (spec 008, REQ-044 y respuesta 2 de las preguntas abiertas: si cada '
        'renglón tiene o no oferta; sostén parcial, no fija los cuatro valores); origen: T-135 '
        'de la 008 (`ficha-renglon-v3`: cotizado solo con precio o cantidad), T-136 de la 008 '
        '(`ficha-renglon-v4`: «sin_precio») y T-248 de la 015 (`ficha-renglon-v5`: '
        '«no_aparece»); H-282-1')),
    "D-58": ("pendiente", (
        'Derivada de D-52 (spec 013, REQ-074: el sistema solo toma lo que dice el informe); '
        'origen: T-190 de la 013 (`informe-tecnico-v1`), conservada en `informe-tecnico-v2` '
        '(T-248 de la 015); H-282-1')),
    "D-59": ("pendiente", (
        'Derivada de D-49 (spec 008, REQ-039 y REQ-040: los fragmentos que responden al '
        'requisito, sin suponer); origen: T-135 de la 008 (`ficha-v2`: el dato concreto) y '
        'T-248 de la 015 (`ficha-v3`: todas las citas); H-282-1')),
    "D-60": ("pendiente", (
        'Derivada de D-27 (spec 014, «El sistema lo propone»: el nombre del oferente con su '
        'cita); origen: T-220 de la 014 (`oferente-nombre-v1` y las reglas del nombre: '
        'terceros en la ronda 1, rótulo explícito en la ronda 2) y T-248 de la 015 '
        '(`oferente-nombre-v2`); H-282-1')),
}
PENDING_MARK = "pendiente de confirmación del responsable"
CONFIRMED_MARK = re.compile(r"confirmada por el responsable el (\d{4}-\d{2}-\d{2})\b[^«“]*[«“][^»”]+[»”]")


def derived_problems(report, expected=None):
    """Lo que no coincide entre las derivadas del informe y la tabla de control: lista de textos,
    vacía si cada derivada tiene su marca y su fuente, y si están todas y solo ellas."""
    expected = DERIVED if expected is None else expected
    found = {row[0]: row for row in decisions_of(report).values()
             if row[1].startswith("Definición derivada")}
    problems = [f"{key}: es derivada y no está en la tabla de control" for key in found
                if key not in expected]
    problems += [f"{key}: la tabla de control la tiene y el informe no" for key in expected
                 if key not in found]
    for key, (state, source) in expected.items():
        if key not in found:
            continue
        decision, cited = found[key][1], found[key][2]
        pending = PENDING_MARK in decision
        confirmed = bool(CONFIRMED_MARK.search(decision))
        if state == "pendiente" and not (pending and not confirmed):
            problems.append(f"{key}: perdió «{PENDING_MARK}»")
        if state == "confirmada" and not (confirmed and not pending):
            problems.append(f"{key}: perdió «confirmada por el responsable el AAAA-MM-DD» con la cita")
        if cited != source:
            problems.append(f"{key}: la fuente o el origen cambió sin cambiar la tabla de control")
    return problems


def test_every_derived_definition_keeps_its_mark_and_its_origin():
    """REQ-119 (H-281-4 de la verificación de T-281): cada definición derivada del informe dice si
    está pendiente de confirmación o confirmada por el responsable (con la fecha y la cita) y nombra
    su origen, tal como la tabla de control `DERIVED`."""
    assert derived_problems(read_report_016()) == []


def test_the_derived_check_finds_a_lost_mark_or_a_changed_origin():
    """REQ-119 (H-281-4; alteraciones C9 a C11 de la verificación de T-281): quitar «pendiente de
    confirmación del responsable» de D-35, quitar «confirmada por el responsable» de D-32, volver el
    origen de D-36 a T-236 sin T-098 o cambiar el de D-43 hace fallar la comprobación."""
    report = read_report_016()
    rows = decisions_of(report)

    def altered(key, old, new):
        line = "| " + " | ".join(rows[key]) + " |"
        assert line in report and old in line, (key, old)
        return report.replace(line, line.replace(old, new, 1))

    cases = [
        ("D-35", altered("D-35", ", pendiente de confirmación del responsable", "")),
        ("D-32", altered("D-32", "confirmada por el responsable", "propuesta")),
        ("D-36", altered("D-36", "origen: T-098 de la 003 (`matriz-circulares-v2`, «sin citas "
                                 "ajenas») y T-236", "origen: T-236")),
        ("D-43", altered("D-43", "origen: T-151 de la 004", "origen: T-240 de la 015")),
        ("D-45", altered("D-45", "pendiente de confirmación del responsable",
                         "confirmada por el responsable el 2026-10-16: «Sí»")),
    ]
    for key, text in cases:
        assert [p for p in derived_problems(text) if p.startswith(f"{key}:")], key
