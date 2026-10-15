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
decisión», con cada oración atada a una decisión de la tabla. El informe no lleva texto de los casos.

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
    """REQ-106: el informe de revisión cubre el 100 % de las instrucciones vigentes: nombra la
    versión de cada una."""
    report = read_report()

    missing = [version for version in current_versions() if version not in report]

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

    assert len(decisions) >= 20
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
