"""T-262 · la presentación física en la matriz (REQ-102, REQ-106; spec 015, decisión del 2026-10-12).

La decisión: «si requiere presentacion fisica y no la hace (...) la oferta no cumple»; presentar en
Mesa de Entrada lo que el Portal marca para entregar así es requisito, aunque la oración empiece
hablando de la carga en el Portal. La medición T-260 la vio descartada como
`forma_presentacion_portal` en los siete casos (en uno por la extracción y en seis por el filtro).
Se prueban, sin GPU, las instrucciones nuevas: el bloque común v8, la extracción v11 y el filtro v8
dicen la salvedad donde definen la forma de presentar por el Portal, ningún ejemplo descarta una
oración que pide algo en papel, y hay ejemplos de otro rubro que la mantienen. La prueba con el
modelo real está en el informe de la tarea. Los textos son inventados (P4).
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.tenders.proposal import extraction

PROMPTS = Path(extraction.PROMPTS_DIR)
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"
NEW = {"matriz-definiciones-v8": "matriz-definiciones-v7",
       "matriz-extraccion-v11": "matriz-extraccion-v10",
       "matriz-filtro-v8": "matriz-filtro-v7"}
# Lo que dice que algo se entrega en papel.
PAPER = re.compile(r"papel|impres|físic", re.IGNORECASE)
# El rubro de los ejemplos de siempre: el ejemplo nuevo es de otro.
BOOKS = re.compile(r"libro|biblioteca|editorial|ejemplar|título", re.IGNORECASE)


def _read(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _pairs(text, question, answer):
    """`[(texto, respuesta)]` de los ejemplos: el texto entre comillas de la línea que empieza con
    `question` (sin la nota entre paréntesis que la precede) y la respuesta JSON de la línea
    siguiente."""
    lines = text.splitlines()
    return [(line[line.index('"'):], json.loads(lines[n + 1])) for n, line in enumerate(lines[:-1])
            if line.startswith(question) and lines[n + 1].startswith(answer)]


def test_the_active_versions_are_the_t262_ones_and_the_older_ones_stay_published():
    """REQ-106, P6: T-262 publica el bloque v8, la extracción v11 y el filtro v8 y los registra como
    vigentes; las versiones anteriores siguen publicadas (congeladas)."""
    versions = settings.MATRIX_PROMPT_VERSIONS
    assert versions["definiciones"] == "matriz-definiciones-v10"  # T-285: la v8 y la siguiente siguen publicadas
    assert versions["extraccion"] == "matriz-extraccion-v14"  # T-285: la v11, la v12 y la siguiente siguen publicadas
    assert versions["filtro"] == "matriz-filtro-v11"  # T-285: la v8, la v9 y la siguiente siguen publicadas
    for name, previous in NEW.items():
        assert (PROMPTS / f"{name}.md").is_file() and (PROMPTS / f"{previous}.md").is_file()


def test_the_block_says_the_paper_delivery_is_not_the_portal_form_where_it_defines_it():
    """REQ-102 (decisión del 2026-10-12): el ítem de lo que no entra por ser la forma de presentar
    por el Portal dice, en el mismo lugar, que no incluye entregar en papel lo que el Portal marca,
    aunque la oración empiece por la carga; el resto del bloque v7 sigue igual."""
    block = _read("matriz-definiciones-v8")
    item = next(line for line in block.splitlines()
                if line.startswith("- La forma de presentar la oferta por el Portal"))
    assert "No incluye entregar en papel lo que el Portal marca para presentar así" in item
    assert "aunque la misma oración empiece por la carga en el Portal" in item
    assert "si la oferta no la hace, no cumple" in item
    assert "Entra también entregar en papel, en la mesa de entradas del organismo" in block
    previous = _read("matriz-definiciones-v7").splitlines()
    assert [line for line in block.splitlines() if line not in previous] == [item]


def test_no_extraction_example_discards_a_sentence_that_asks_for_paper():
    """REQ-102: en la extracción v11 ningún ejemplo descarta un tramo que pide entregar algo en
    papel, hay uno de otro rubro que empieza por la carga en el sistema y se mantiene entero, y el
    motivo `forma_presentacion_portal` trae la salvedad; los ejemplos siguen balanceados."""
    text = _read("matriz-extraccion-v11")
    pairs = _pairs(text, "Tramo", '{"requisitos"')
    assert pairs
    for question, answer in pairs:
        if answer["descarte"]:
            assert not PAPER.search(question), question
    kept = [(q, a) for q, a in pairs if PAPER.search(q) and a["requisitos"]]
    assert len(kept) >= 2
    other = [(q, a) for q, a in kept if not BOOKS.search(q)]
    assert other, "falta un ejemplo de otro rubro que mantenga la presentación física"
    question, answer = other[0]
    [requirement] = answer["requisitos"]
    assert requirement["cita"] in question and requirement["opcion"] == ""
    assert requirement["cita"].index("se subirá al sistema") < requirement["cita"].index("papel")
    assert requirement["cita"].startswith("Toda la documentación que pide este capítulo")
    motive = next(line for line in text.splitlines()
                  if line.startswith("- forma_presentacion_portal:"))
    assert "No es la oración que, además de la carga, pide entregar en papel" in motive
    assert "nunca la descartes como forma_presentacion_portal" in text
    section = text.split("LA PRESENTACIÓN FÍSICA")[1].split("MOTIVOS DE DESCARTE")[0]
    assert "aunque hable en general de la documentación de un punto o de un capítulo" in section
    assert "nunca la descartes con forma_presentacion_portal" in section
    with_requirements = sum(1 for _, a in pairs if a["requisitos"] or a["tecnico"])
    discarded = sum(1 for _, a in pairs if a["descarte"])
    assert abs(with_requirements - discarded) <= 1


def test_the_extraction_still_discards_what_only_says_how_to_fill_in_the_portal():
    """REQ-102 (decisión del 2026-10-10): la salvedad no devuelve la forma de presentar por el
    Portal: completar algo en el sistema, sin nada en papel, se sigue descartando, con un ejemplo
    del mismo rubro que el de la presentación física."""
    pairs = _pairs(_read("matriz-extraccion-v11"), "Tramo", '{"requisitos"')
    portal = [q for q, a in pairs if a["descarte"] == "forma_presentacion_portal"]
    assert len(portal) == 2
    assert any("sistema de compras electrónicas" in q for q in portal)


def test_no_filter_example_discards_a_row_that_asks_for_paper_and_both_questions_keep_one():
    """REQ-102: en el filtro v8 ningún ejemplo de A descarta una fila que pide algo en papel; A la
    mantiene y B responde «si» en un ejemplo de otro rubro, y un contraste del mismo rubro que solo
    completa algo en el sistema se descarta en A y es «no» en B. Los ejemplos siguen balanceados."""
    text = _read("matriz-filtro-v8")
    first, second = text.split("# PREGUNTA B")
    a_pairs = _pairs(first, "Fila", '{"razonamiento"')
    b_pairs = _pairs(second, "Fila", '{"razonamiento"')
    for question, answer in a_pairs:
        if answer["decision"] == "descartar":
            assert not PAPER.search(question), question
    for question, answer in b_pairs:
        if answer["respuesta"] == "no":
            assert not PAPER.search(question), question
    assert any(PAPER.search(q) and not BOOKS.search(q) and a["decision"] == "mantener"
               for q, a in a_pairs)
    assert any(PAPER.search(q) and not BOOKS.search(q) and a["respuesta"] == "si"
               for q, a in b_pairs)
    assert any("sistema de compras electrónicas" in q and a["motivo"] == "forma_presentacion_portal"
               for q, a in a_pairs)
    assert any("sistema de compras electrónicas" in q and a["respuesta"] == "no" for q, a in b_pairs)
    decisions = [a["decision"] for _, a in a_pairs]
    assert decisions.count("descartar") == decisions.count("mantener")
    answers = [a["respuesta"] for _, a in b_pairs]
    assert answers.count("si") == answers.count("no")


def test_the_filter_says_the_exception_in_its_cautions_its_motive_and_the_no_list_of_b():
    """REQ-102: el filtro v8 lo dice en un quinto cuidado (el encabezado cuenta cinco), en el motivo
    de A y en la lista de «no» de B."""
    text = _read("matriz-filtro-v8")
    common = text.split("CÓMO VIENEN LOS DATOS")[0]
    assert "Cinco cuidados:" in common
    cautions = [line for line in common.split("Cinco cuidados:")[1].splitlines()
                if line.startswith("- ")]
    assert len(cautions) == 5
    assert "no es la forma de presentar por el Portal y no se descarta por ese motivo" in cautions[-1]
    motive = next(line for line in text.splitlines()
                  if line.startswith('  - "forma_presentacion_portal":'))
    assert "No lo es la fila que además pide entregar en papel lo que el Portal marca" in motive
    no_list = next(line for line in text.splitlines() if line.startswith('  - "no":'))
    assert "no la entrega en papel de lo que el Portal marca, que es un requisito" in no_list


@pytest.mark.parametrize("name", sorted(NEW))
@pytest.mark.parametrize("paraphrase", [
    "mesa de entrada", "requiere presentar", "presentarse físicamente", "adjuntar electrónicamente",
    "portal de compras", "detalle de renglones", "a través del formulario", "pólizas", "póliza",
    "pagaré", "pesos argentinos", "administrador",
])
def test_the_new_examples_do_not_paraphrase_the_clauses_of_the_measurement_cases(name, paraphrase):
    """REQ-106 (D-236-1, P7): los ejemplos nuevos son de otro rubro y de otra redacción: no repiten
    la presentación física, la oferta económica por el formulario ni la póliza de los casos."""
    text = _read(name).lower()
    for example in [line for line in text.splitlines()
                    if line.startswith(("tramo", "fila", "{"))]:
        assert paraphrase not in example, (name, paraphrase)


def _shingles(text, size=5):
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def _anchors(node):
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [text for value in node.values() for text in _anchors(value)]
    if isinstance(node, list):
        return [text for value in node for text in _anchors(value)]
    return []


@pytest.mark.parametrize("name", sorted(NEW))
def test_what_the_t262_instructions_add_repeats_no_five_words_of_the_case_files(name):
    """REQ-106 (generalidad, P4): lo que agregan las instrucciones de T-262 no repite cinco palabras
    seguidas de las listas esperadas de los casos 00 a 06 (incluidas las re-ancladas). Se saltea si
    `corpus/casos/` no está montado: la comprobación con huellas está en `test_definitions.py`."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno")
    known = set()
    for path in files:
        for anchor in _anchors(yaml.safe_load(path.read_text(encoding="utf-8"))):
            known |= _shingles(anchor)
    assert len(known) > 100
    hits = sorted((_shingles(_read(name)) - _shingles(_read(NEW[name]))) & known)
    assert not hits, [hashlib.sha256(h.encode()).hexdigest()[:12] for h in hits]
