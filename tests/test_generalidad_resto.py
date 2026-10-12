"""Generalidad del resto de las instrucciones (REQ-106; plan 015; T-248; P4, P7).

Los casos 00 a 06 son casos de medición: si una instrucción repite su texto, la medición enseña
justamente lo que mide. Como con la matriz (`tests/tenders/test_definitions.py`) y la evaluación
(`tests/assessment/test_generalidad_evaluacion.py`), ninguna secuencia de cinco palabras seguidas de
las anclas de los casos puede estar en las demás instrucciones vigentes: consecuencias, respaldo,
ficha, ficha por renglón, reescritura, visión, informe técnico, consulta y nombre del oferente.

Hay dos comprobaciones:

1. Con las huellas SHA-256 de las secuencias de cinco palabras (`case_anchor_hashes.txt`, la misma
   lista de la matriz): corre siempre, también donde `corpus/` no está.
2. Con las anclas de `corpus/casos/*/esperado/*.yaml` (fuera de git, P4): se saltea y lo avisa si
   `corpus/casos/` no está montado. Para correrla: `docker compose run --rm -v
   ./corpus/casos:/app/corpus/casos:ro app pytest tests/test_generalidad_resto.py`.
"""

import hashlib
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.assessment.services import technical_report
from evaluon.offers import proposal_fields
from evaluon.queries import answering
from tests.assessment.test_generalidad_evaluacion import CASES, HASHES, anchors_of, shingles

ROOT = Path(__file__).resolve().parent.parent
TENDERS = ROOT / "evaluon" / "tenders" / "prompts"
OFFERS = ROOT / "evaluon" / "offers" / "prompts"
ASSESSMENT = ROOT / "evaluon" / "assessment" / "prompts"
QUERIES = ROOT / "evaluon" / "queries" / "prompts"


def current():
    """`{versión: ruta}` de las instrucciones vigentes que revisó T-248."""
    found = {}
    for name in ("consecuencias", "respaldo"):
        version = settings.MATRIX_PROMPT_VERSIONS[name]
        found[version] = TENDERS / f"{version}.md"
    for version in settings.OFFERS_PROMPT_VERSIONS.values():
        found[version] = OFFERS / f"{version}.md"
    for version in (settings.ASSESSMENT_VISION_PROMPT_VERSION, technical_report.PROMPT_VERSION):
        found[version] = ASSESSMENT / f"{version}.md"
    found[answering.PROMPT_VERSION_WITH_DATE] = QUERIES / f"{answering.PROMPT_VERSION_WITH_DATE}.txt"
    found[proposal_fields.PROMPT_VERSION] = OFFERS / f"{proposal_fields.PROMPT_VERSION}.md"
    return found


def test_the_remaining_instructions_are_the_ones_that_t248_reviewed():
    """REQ-106: la comprobación cubre las nueve instrucciones vigentes que revisó T-248, cada una
    en su versión nueva."""
    versions = set(current())

    assert versions == {
        "matriz-consecuencias-v2", "matriz-respaldo-v2", "ficha-v3", "ficha-renglon-v5",
        "reescritura-v2", "vision-v4", "informe-tecnico-v2", "consulta-v4",
        "oferente-nombre-v2"}
    assert all(path.is_file() for path in current().values())


@pytest.mark.parametrize("version", sorted(current()))
def test_no_remaining_instruction_repeats_five_words_of_a_case_anchor(version):
    """REQ-106 (generalidad, P4): la instrucción vigente no repite cinco palabras seguidas de las
    anclas de los casos (se comparan huellas, sin texto de los casos)."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    text = current()[version].read_text(encoding="utf-8")

    hits = [hashlib.sha256(s.encode()).hexdigest()[:12] for s in shingles(text)
            if hashlib.sha256(s.encode()).hexdigest() in known]

    assert not hits, f"{version}: {hits}"


def test_no_remaining_instruction_repeats_five_words_of_the_case_files():
    """REQ-106 (generalidad, P4): lo mismo, contra las anclas de los casos 00 a 06 tal como están
    en `corpus/casos/*/esperado/`. Se saltea si `corpus/casos/` no está montado."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno: la generalidad se comprobó "
                    "solo con las huellas; montarlo para comprobar contra las anclas de los casos")
    known = set()
    anchors = []
    for path in files:
        anchors.extend(anchors_of(yaml.safe_load(path.read_text(encoding="utf-8"))))
    for anchor in anchors:
        known |= shingles(anchor)
    assert len(anchors) > 50 and len(known) > 100

    hits = {version: sorted(shingles(path.read_text(encoding="utf-8")) & known)
            for version, path in current().items()}
    hits = {version: found for version, found in hits.items() if found}

    assert not hits, {version: [hashlib.sha256(h.encode()).hexdigest()[:12] for h in found]
                      for version, found in hits.items()}
