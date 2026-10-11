"""Instrucciones al modelo: revisadas y congeladas (T-236; REQ-106; ADR-0055, regla 8; P6, P7).

Dos garantías, como `scripts/models.sha256` con los modelos:

1. **Cobertura.** El informe de revisión (`specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`,
   un resumen sin texto de casos) nombra el 100 % de las instrucciones vigentes: las de la
   matriz, las de la evaluación, la visión, la ficha, el informe técnico, la consulta y las dos
   que viven en el código (`oferente-nombre`, `procedimiento-datos`).
2. **Versiones congeladas.** Cada versión publicada de una instrucción (cada archivo de las
   carpetas `prompts/` y cada instrucción dentro del código) tiene su huella SHA-256 en
   `tests/fixtures/instrucciones.sha256`, y el archivo no cambió. Una instrucción nueva es una
   versión nueva (archivo nuevo, con su línea en la lista); una publicada no se edita. Si falta
   una línea, el fallo trae la que hay que agregar.

Los textos de las instrucciones son inventados o propios del sistema (P4).
"""

from pathlib import Path

import pytest
from django.conf import settings

from evaluon.assessment.services import technical_report
from evaluon.offers import proposal_fields
from evaluon.queries import answering
from evaluon.tenders.proposal import extraction, procedure_fields

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "specs" / "015-uso-y-eleccion-del-modelo" / "revision-instrucciones.md"
FROZEN = Path(__file__).resolve().parent / "fixtures" / "instrucciones.sha256"
PROMPT_DIRS = [
    ROOT / "evaluon" / "tenders" / "prompts",
    ROOT / "evaluon" / "offers" / "prompts",
    ROOT / "evaluon" / "assessment" / "prompts",
    ROOT / "evaluon" / "queries" / "prompts",
]
# Las instrucciones que viven dentro del código: su nombre de versión y su texto.
INLINE = {
    proposal_fields.PROMPT_VERSION: proposal_fields.MODEL_INSTRUCTIONS,
    procedure_fields.PROMPT_VERSION: procedure_fields.MODEL_INSTRUCTIONS,
}


def current_versions():
    """Los nombres de versión de todas las instrucciones vigentes, tal como las fijan la
    configuración y el código. `unificacion` no tiene archivo: la pasada es de código."""
    names = {version for name, version in settings.MATRIX_PROMPT_VERSIONS.items()
             if name != "unificacion"}
    names |= set(settings.OFFERS_PROMPT_VERSIONS.values())
    names |= set(settings.ASSESSMENT_PROMPT_VERSIONS.values())
    names.add(settings.ASSESSMENT_VISION_PROMPT_VERSION)
    names.add(technical_report.PROMPT_VERSION)
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
