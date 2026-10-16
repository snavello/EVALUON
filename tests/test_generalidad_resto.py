"""Generalidad del resto de las instrucciones (REQ-106; plan 015; T-248; P4, P7).

Los casos 00 a 06 son casos de medición: si una instrucción repite su texto, la medición enseña
justamente lo que mide. Como con la matriz (`tests/tenders/test_definitions.py`) y la evaluación
(`tests/assessment/test_generalidad_evaluacion.py`), ninguna secuencia de cinco palabras seguidas de
las anclas de los casos puede estar en las demás instrucciones vigentes: consecuencias, respaldo,
ficha, ficha por renglón, reescritura, visión, informe técnico, consulta, nombre del oferente y
datos del procedimiento.

Hay cuatro comprobaciones:

1. Con las huellas SHA-256 de las secuencias de cinco palabras (`case_anchor_hashes.txt`, la misma
   lista de la matriz): corre siempre, también donde `corpus/` no está.
2. Con las anclas de `corpus/casos/*/esperado/*.yaml` (fuera de git, P4): se saltea y lo avisa si
   `corpus/casos/` no está montado.
3. Con el cuerpo de los pliegos de `corpus/casos/*/pliego/` (la capa de texto de cada PDF, con sus
   anexos; fuera de git, P4), secuencias exactas: ninguna secuencia de seis palabras seguidas de
   un pliego está en una instrucción (verificación de T-248, H-248-1 y H-248-2: las cláusulas
   generales de los pliegos no son anclas y el test de las anclas no las veía). Seis y no cinco:
   con cinco, el cuerpo de un pliego comparte con cualquier texto de compras frases genéricas como
   «de la orden de compra», que no son el texto de un caso.
4. Con el mismo cuerpo, paráfrasis: ninguna oración de una instrucción comparte con una oración
   de un pliego `PARAPHRASE_MIN` palabras con contenido o más que sean, además, al menos el
   `PARAPHRASE_SHARE` de las suyas (palabras sin tildes ni mayúsculas, sin las vacías, cortadas en
   sus primeras seis letras, para que «presentar» y «presentación» cuenten como la misma).

Las comprobaciones 3 y 4 se saltean y lo avisan si los pliegos no están montados. Para correr las
tres que usan el corpus: `docker compose run --rm -v ./corpus/casos:/app/corpus/casos:ro app
pytest tests/test_generalidad_resto.py`. Los fallos muestran huellas o el texto de la instrucción,
nunca el de un caso (P4).
"""

import functools
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.assessment.services import technical_report
from evaluon.offers import proposal_fields
from evaluon.queries import answering
from evaluon.tenders.proposal import procedure_fields
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
    found[procedure_fields.PROMPT_VERSION] = TENDERS / f"{procedure_fields.PROMPT_VERSION}.md"
    return found


# Secuencias exactas contra el cuerpo de los pliegos: seis palabras (ver el comentario del módulo).
BODY_SIZE = 6
# Paráfrasis: palabras con contenido compartidas por una oración de la instrucción y una del
# pliego, como mínimo, y la parte de las de la instrucción que tienen que ser. Fijados antes de
# corregir los ejemplos, con las versiones que la verificación de T-248 encontró copiadas: las
# detectan (7 de 8, 6 de 7 y 5 de 5) y no detectan las oraciones propias de las instrucciones,
# que comparten con los pliegos el vocabulario de compras (4 de 5 como máximo).
PARAPHRASE_MIN = 5
PARAPHRASE_SHARE = 0.8
# Una oración del pliego más larga que esto se compara por ventanas de este largo, que avanzan
# de a la mitad: una oración de cien palabras compartiría por azar las de cualquier instrucción.
WINDOW = 40
STOPWORDS = frozenset("""
a al algo alguna algunas alguno algunos ante antes aquel aquella aquellas aquello aquellos asi
aun cada como con contra cual cuales cualquier cuando cuya cuyo de del desde dicha dicho donde dos
e el ella ellas ellos en entre era es esa esas ese eso esos esta estas este esto estos fue fueron
ha han hasta hay la las le les lo los mas me mediante mi muy ni no nos o otra otras otro otros para
pero por que quien se segun ser sera seran si sin sino sobre son su sus tal tambien tanto toda
todas todo todos tu un una unas uno unos y ya debera deberan podra podran
""".split())


def _words(text):
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", folded)


def content_words(text):
    """Las palabras con contenido del texto: sin tildes ni mayúsculas, sin las vacías ni los
    números, de más de tres letras y cortadas en sus primeras seis."""
    return {w[:6] for w in _words(text) if len(w) > 3 and w not in STOPWORDS and not w.isdigit()}


def sentences(text):
    """Las oraciones del texto: lo que queda entre puntos, comillas y signos de cierre."""
    flat = re.sub(r"\s+", " ", text)
    return [part.strip() for part in re.split(r"[.;:!?\"«»“”]", flat) if part.strip()]


def windows(text):
    """Las oraciones del texto y, de las que pasan de `WINDOW` palabras, sus ventanas."""
    found = []
    for sentence in sentences(text):
        words = _words(sentence)
        if len(words) <= WINDOW:
            found.append(" ".join(words))
        else:
            found.extend(" ".join(words[i:i + WINDOW])
                         for i in range(0, len(words) - WINDOW // 2, WINDOW // 2))
    return found


def paraphrases(instruction, body_windows):
    """Las oraciones de `instruction` que parafrasean una de `body_windows`: `[(compartidas,
    propias, oración)]`, con la oración de la instrucción (nunca la del pliego, P4)."""
    index = {}
    for number, window in enumerate(body_windows):
        for word in content_words(window):
            index.setdefault(word, []).append(number)
    found = []
    for sentence in sentences(instruction):
        own = content_words(sentence)
        if len(own) < PARAPHRASE_MIN:
            continue
        counts = Counter(number for word in own for number in index.get(word, ()))
        shared = max(counts.values(), default=0)
        if shared >= PARAPHRASE_MIN and shared / len(own) >= PARAPHRASE_SHARE:
            found.append((shared, len(own), sentence[:120]))
    return found


@functools.lru_cache(maxsize=1)
def pliego_bodies():
    """`{ruta: texto}` de la capa de texto de cada PDF de `corpus/casos/*/pliego/` (con sus
    anexos). Vacío si `corpus/casos/` no está montado."""
    if not CASES.is_dir():
        return {}
    import pypdfium2 as pdfium

    bodies = {}
    for path in sorted(CASES.glob("*/pliego/**/*.pdf")):
        pdf = pdfium.PdfDocument(str(path))
        try:
            bodies[path] = "\n".join(page.get_textpage().get_text_range() for page in pdf)
        finally:
            pdf.close()
    return bodies


def bodies_or_skip():
    bodies = pliego_bodies()
    if not bodies:
        pytest.skip("corpus/casos/*/pliego/ no está montado en este entorno: la generalidad no se "
                    "comprobó contra el cuerpo de los pliegos; montar corpus/casos/ para hacerlo")
    return bodies


def test_the_remaining_instructions_are_the_ones_that_t248_reviewed():
    """REQ-106: la comprobación cubre las diez instrucciones vigentes que revisó T-248, cada una
    en su versión nueva."""
    versions = set(current())

    assert versions == {
        "matriz-consecuencias-v3", "matriz-respaldo-v3",  # T-280
        "reescritura-v3",  # T-281
        "ficha-v4", "ficha-renglon-v6", "vision-v5", "informe-tecnico-v3", "consulta-v5",  # T-282
        "oferente-nombre-v3", "procedimiento-datos-v3"}
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


def test_the_paraphrase_check_finds_a_reworded_sentence_and_not_one_that_only_shares_vocabulary():
    """REQ-106 (generalidad): la comprobación de paráfrasis encuentra una oración dicha con otras
    palabras de las mismas raíces y no una que solo comparte el vocabulario de compras. Textos
    inventados (P4); corre siempre."""
    body = windows("Las firmas proponentes deberán conservar vigentes sus propuestas durante "
                   "noventa jornadas corridas, contadas desde la fecha de la convocatoria. Otra "
                   "cosa distinta sobre el depósito del organismo.")
    reworded = "La propuesta deberá conservarse vigente durante noventa jornadas corridas."
    vocabulary = "Las propuestas de las firmas se leen enteras antes de responder."

    assert paraphrases(reworded, body)
    assert not paraphrases(vocabulary, body)


def test_no_remaining_instruction_repeats_six_words_of_the_body_of_a_pliego():
    """REQ-106 (generalidad, P4; verificación de T-248, H-248-1 y H-248-2): ninguna instrucción
    vigente del resto repite seis palabras seguidas del cuerpo de un pliego de los casos 00 a 06,
    con las cláusulas generales que no son anclas. Se saltea si los pliegos no están montados."""
    bodies = bodies_or_skip()
    known = set()
    for body in bodies.values():
        known |= shingles(body, BODY_SIZE)
    assert len(bodies) >= 7 and len(known) > 10000

    hits = {version: sorted(shingles(path.read_text(encoding="utf-8"), BODY_SIZE) & known)
            for version, path in current().items()}
    hits = {version: found for version, found in hits.items() if found}

    assert not hits, {version: [hashlib.sha256(h.encode()).hexdigest()[:12] for h in found]
                      for version, found in hits.items()}


def test_no_remaining_instruction_paraphrases_a_sentence_of_a_pliego():
    """REQ-106 (generalidad, P4; verificación de T-248, H-248-1 y H-248-2): ninguna oración de las
    instrucciones vigentes del resto es una paráfrasis de una oración de un pliego de los casos
    (comparte `PARAPHRASE_MIN` palabras con contenido o más, y al menos el `PARAPHRASE_SHARE` de
    las suyas). El fallo muestra la oración de la instrucción, no la del pliego. Se saltea si los
    pliegos no están montados."""
    bodies = bodies_or_skip()
    body_windows = [window for body in bodies.values() for window in windows(body)]
    assert len(body_windows) > 1000

    hits = {version: paraphrases(path.read_text(encoding="utf-8"), body_windows)
            for version, path in current().items()}
    hits = {version: found for version, found in hits.items() if found}

    assert not hits, hits
