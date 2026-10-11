"""Generalidad de las instrucciones de la evaluación (REQ-106; plan 015; T-237, D-237-1; P4, P7).

Los casos 00 a 06 son casos de medición: si una instrucción repite su texto, la medición enseña
justamente lo que mide. Como con la matriz (`tests/tenders/test_definitions.py`), ninguna secuencia de
cinco palabras seguidas de las anclas de los casos puede estar en las instrucciones de la
evaluación (evaluación, contraste y cláusulas, en su versión vigente).

Hay dos comprobaciones:

1. Con las huellas SHA-256 de las secuencias de cinco palabras (`case_anchor_hashes.txt`, la misma
   lista que usa la matriz): corre siempre, también donde `corpus/` no está.
2. Con las anclas de `corpus/casos/*/esperado/*.yaml` (fuera de git, P4): se saltea y lo avisa si
   `corpus/casos/` no está montado en el contenedor. Para correrla: `docker compose run --rm -v
   ./corpus/casos:/app/corpus/casos:ro app pytest tests/assessment/test_generalidad_evaluacion.py`.
"""

import hashlib
import re
import unicodedata
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.assessment import prompting

HASHES = Path(__file__).resolve().parent.parent / "tenders" / "fixtures" / "case_anchor_hashes.txt"
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"
SIZE = 5


def shingles(text, size=SIZE):
    """Las secuencias de `size` palabras seguidas del texto, sin acentos ni mayúsculas."""
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def instructions():
    """`{nombre: texto}` de las instrucciones vigentes de la evaluación."""
    return {name: prompting.load_prompt(name) for name in settings.ASSESSMENT_PROMPT_VERSIONS}


def anchors_of(node):
    """Los textos de las claves `ancla` y `anclas` de un documento YAML, a cualquier profundidad."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("ancla", "anclas"):
                found.extend([value] if isinstance(value, str) else
                             [v for v in value or [] if isinstance(v, str)])
            else:
                found.extend(anchors_of(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(anchors_of(item))
    return found


@pytest.mark.parametrize("name", sorted(settings.ASSESSMENT_PROMPT_VERSIONS))
def test_the_evaluation_instructions_repeat_no_five_words_of_a_case_anchor(name):
    """REQ-106 (generalidad, P4): la instrucción vigente no repite cinco palabras seguidas de las
    anclas de los casos (se comparan huellas, sin texto de los casos)."""
    known = set(HASHES.read_text(encoding="utf-8").split())
    assert len(known) > 100
    hits = [hashlib.sha256(s.encode()).hexdigest()[:12] for s in shingles(instructions()[name])
            if hashlib.sha256(s.encode()).hexdigest() in known]
    assert not hits, f"{settings.ASSESSMENT_PROMPT_VERSIONS[name]}: {hits}"


def test_the_evaluation_instructions_repeat_no_five_words_of_the_case_files():
    """REQ-106 (generalidad, P4): lo mismo, contra las anclas de los casos 00 a 06 tal como están
    en `corpus/casos/*/esperado/`. Se saltea si `corpus/casos/` no está montado."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno: la generalidad se comprobó "
                    "solo con las huellas; montarlo para comprobar contra las anclas de los casos")
    anchors = []
    for path in files:
        anchors.extend(anchors_of(yaml.safe_load(path.read_text(encoding="utf-8"))))
    known = set()
    for anchor in anchors:
        known |= shingles(anchor)
    assert len(anchors) > 50 and len(known) > 100
    hits = {settings.ASSESSMENT_PROMPT_VERSIONS[name]: sorted(shingles(text) & known)
            for name, text in instructions().items()}
    hits = {version: found for version, found in hits.items() if found}
    assert not hits, {version: [hashlib.sha256(h.encode()).hexdigest()[:12] for h in found]
                      for version, found in hits.items()}
