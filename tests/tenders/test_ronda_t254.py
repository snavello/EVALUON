"""T-254 · ronda extra: las verificaciones sobre el oferente y las condiciones de una opción
(REQ-102, REQ-106; spec 015, decisión del 2026-10-12; REQ-063 de la 004).

En T-244 el Qwen3.8-27B descartó dos verificaciones que la Comisión conserva (la consulta de
sanciones y la de deuda del oferente) como «obligación del organismo», y las condiciones de la
cotización parcial como «condición opcional». Las instrucciones nuevas (`matriz-definiciones-v4`,
`matriz-extraccion-v7`, `matriz-filtro-v7`) lo corrigen. Estas pruebas comprueban lo que las
instrucciones dicen y sus ejemplos, sin modelo ni GPU; la prueba con el modelo real está en
`verificacion/T-254.md` de la rama (pedidos reenviados). Los textos son inventados y de otro rubro
(P4): ninguna secuencia de cinco palabras de las anclas de los casos.
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
from evaluon.tenders.proposal import filter as row_filter

PROMPTS = Path(extraction.PROMPTS_DIR)
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"


def _read(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _examples(text, start):
    """Las líneas de respuesta (JSON) de los ejemplos de `text` que empiezan con `start`."""
    return [json.loads(line) for line in text.splitlines() if line.startswith(start)]


# --- Las versiones vigentes ---------------------------------------------------------------------


def test_the_active_versions_are_the_t254_ones_and_the_older_ones_stay_published():
    """REQ-106, P6: la ronda extra publica `matriz-definiciones-v4`, `matriz-extraccion-v7` y
    `matriz-filtro-v7`; las anteriores (con la `matriz-filtro-v6`, que la verificación observó:
    O-254-1) siguen publicadas (congeladas). T-258 publica después el bloque v5 y v6 y la extracción
    v8 a v10 (las vigentes, v7 y v10); el filtro sigue en la v7."""
    versions = settings.MATRIX_PROMPT_VERSIONS
    assert versions["definiciones"] == "matriz-definiciones-v7"
    assert versions["extraccion"] == "matriz-extraccion-v10"
    assert versions["filtro"] == "matriz-filtro-v7"
    for published in ("matriz-definiciones-v4", "matriz-extraccion-v7"):
        assert (PROMPTS / f"{published}.md").is_file()
    for old in ("matriz-definiciones-v3", "matriz-extraccion-v6", "matriz-filtro-v5", "matriz-filtro-v6"):
        assert (PROMPTS / f"{old}.md").is_file()


@pytest.mark.parametrize("name", ["extraccion", "completitud", "filtro", "circulares",
                                  "circulares_cambios"])
def test_every_instruction_that_uses_the_common_block_records_the_v4_block(name):
    """REQ-106, P6: la versión y la huella del bloque común nuevo quedan en el registro de cada
    instrucción que lo usa (extracción, completitud, filtro y las dos de circulares)."""
    record = extraction.load_instruction(name).record

    active = settings.MATRIX_PROMPT_VERSIONS["definiciones"]   # el vigente (v5 desde T-258)
    assert record["definiciones"]["version"] == active
    assert record["definiciones"]["sha256"] == extraction.text_sha256(_read(active))


# --- El bloque común ----------------------------------------------------------------------------


@pytest.mark.parametrize("literal", [
    # Lo que el organismo verifica del oferente es un requisito externo de la oferta.
    "lo que el organismo verifica del oferente o de su oferta",
    "aunque el sujeto de la oración sea el organismo, la Comisión o la Agencia",
    "que el oferente no tenga deudas",
    "que no figure con sanciones en un registro",
    "que esté inscripto como proveedor",
    "que esté habilitado para contratar",
    "Es un requisito externo de la oferta",
    "Lo que cuenta es de quién es lo que se verifica, no quién lo verifica",
    "esa parte es una consecuencia y no entra; la verificación sí",
    # No es una obligación del organismo.
    "No lo es la verificación que el organismo hace sobre el oferente o su oferta",
    # El texto de una norma que se transcribe no es la verificación del procedimiento.
    "el texto de una norma que se transcribe",
])
def test_the_v4_block_makes_the_verification_of_the_offeror_a_requirement(literal):
    """REQ-102 (REQ-063 de la 004): una verificación que la Comisión o la Agencia hace sobre el
    oferente (sanciones, deuda, registro de proveedores, habilidad) es un requisito externo de la
    oferta y no una obligación del organismo."""
    assert literal in _read("matriz-definiciones-v4")


@pytest.mark.parametrize("literal", [
    # La condición de la opción se mantiene; se descarta solo lo que no exige nada a nadie.
    "la condición de una opción entra, como condición de esa opción",
    "Que la opción sea voluntaria, o que la oración no alcance a las demás ofertas, no es un motivo "
    "para descartarla",
    "únicamente la oración que no le exige nada ni a la oferta que usa la opción ni a la que no",
    "mirá qué le exige la oración a quien usa la opción",
    "cotizar solo una parte",
])
def test_the_v4_block_keeps_the_condition_of_an_option_as_a_condition_of_that_option(literal):
    """REQ-102: las condiciones de una opción que el oferente puede usar (cotizar una parte, una
    oferta alternativa, un descuento) se mantienen como condición de esa opción; se descartan solo
    si no le exigen nada a ninguna oferta."""
    assert literal in _read("matriz-definiciones-v4")


def test_the_v4_block_keeps_every_decision_of_the_v3_block():
    """REQ-102: el bloque nuevo agrega y precisa; las decisiones del responsable siguen donde
    estaban (pago, Portal, compromisos, consecuencias, excepciones, formularios, forma elegida,
    unidad de sentido)."""
    new = _read("matriz-definiciones-v4")
    for sentence in ("El pago, la moneda de pago y la factura", "La forma de presentar la oferta por el Portal",
                     "Los compromisos que se cumplen al presentarse", "Las consecuencias",
                     "Las excepciones y las dispensas", "El texto de un formulario o de una declaración jurada",
                     "Una forma que el oferente tiene que elegir entre varias",
                     "Una fila es una unidad de sentido", "cuatro patas"):
        assert sentence in new, sentence


# --- La extracción ------------------------------------------------------------------------------


def test_the_v7_extraction_proposes_the_verification_of_the_offeror_and_leaves_the_consequence():
    """REQ-102: la extracción pide proponer lo que el organismo verifica del oferente, no lo cuenta
    como obligación del organismo, y tiene un ejemplo donde la verificación es el requisito y la
    frase que sigue (qué pasa con el defecto) queda afuera de la cita."""
    text = _read("matriz-extraccion-v7")
    assert "LO QUE EL ORGANISMO VERIFICA DEL OFERENTE" in text
    assert "No es una obligación del organismo ni se descarta por eso" in text
    assert "No es la verificación que el organismo hace sobre el oferente o su oferta" in text
    examples = _examples(text, '{"requisitos"')
    kept = [e for e in examples if e["requisitos"] and "consultará el padrón" in e["requisitos"][0]["cita"]]
    assert len(kept) == 1 and len(kept[0]["requisitos"]) == 1
    assert "podrá adjudicarse igual" not in kept[0]["requisitos"][0]["cita"]
    # el organismo que controla su propio trabajo sigue siendo una obligación del organismo
    own = [e for e in examples if e["descarte"] == "obligacion_organismo"]
    assert len(own) == 2


def test_the_v7_extraction_keeps_the_condition_of_an_option_with_both_sentences():
    """REQ-102, REQ-101: hay un ejemplo de una opción que el oferente puede no usar donde las dos
    oraciones del mismo asunto, la que permite y la que le exige algo a quien la usa, van en una
    sola cita; el descarte por condición opcional queda para lo que no exige nada."""
    text = _read("matriz-extraccion-v7")
    examples = _examples(text, '{"requisitos"')
    option = [e for e in examples if e["requisitos"] and "plazo de entrega menor" in e["requisitos"][0]["cita"]]
    assert len(option) == 1 and len(option[0]["requisitos"]) == 1
    assert option[0]["requisitos"][0]["cita"].count(". ") == 1   # dos oraciones, una cita
    assert "Que la opción sea voluntaria no es un motivo para descartar" in text
    assert [e for e in examples if e["descarte"] == "condicion_opcional"]


def test_the_v7_extraction_examples_are_balanced_between_requirements_and_discards():
    """REQ-106 (ADR-0055, regla 4): tantos ejemplos con requisitos como descartados (a lo sumo uno
    de diferencia)."""
    examples = _examples(_read("matriz-extraccion-v7"), '{"requisitos"')
    with_requirements = sum(1 for e in examples if e["requisitos"] or e["tecnico"])
    discarded = sum(1 for e in examples if e["descarte"])
    assert abs(with_requirements - discarded) <= 1 and discarded >= 13


# --- El filtro ----------------------------------------------------------------------------------


def test_the_v7_filter_asks_what_the_sentence_demands_of_who_uses_the_option():
    """REQ-102 (v7): A y B reciben la regla de la opción: antes de descartar por condición opcional se
    mira qué le exige la oración a quien usa la opción; si le exige algo, se mantiene aunque la
    opción sea voluntaria. Y la de lo verificado del oferente, que ya traían."""
    for prompt in row_filter.load_prompts():
        assert "Cuatro cuidados" in prompt
        assert "entra como condición de esa opción" in prompt
        assert "qué le exige la oración a quien usa la opción" in prompt
        assert "no quién lo verifica" in prompt
        assert "Solo se descarta la oración que no le exige nada ni a quien usa la opción ni a quien no" in prompt


def test_the_v7_filter_no_longer_answers_no_to_the_condition_of_an_option():
    """REQ-102 (T-244): la lista de «no» de B decía «condición de una opción que el oferente puede
    no usar» y el 27B contestaba «no» a las tres condiciones de la cotización parcial. Ahora el «no»
    es de la oración que solo permite o describe la opción, y el «si» incluye la condición de la
    opción cuando le exige algo a quien la usa."""
    _, second = row_filter.load_prompts()
    assert "condición de una opción que el oferente puede no usar." not in second
    assert "la oración que solo permite o describe una opción que el oferente puede no usar y no le exige nada a nadie" in second
    assert "la condición de una opción que el oferente puede usar, cuando le exige algo a quien la usa" in second


def test_the_v7_filter_motives_do_not_discard_a_verification_of_the_offeror_or_an_option():
    """REQ-102: en A, `obligacion_organismo` aclara que no es la verificación sobre el oferente y
    `condicion_opcional` que no es la condición de una opción que le exige algo a quien la usa."""
    first, _ = row_filter.load_prompts()
    organism = next(line for line in first.splitlines() if line.startswith('  - "obligacion_organismo"'))
    optional = next(line for line in first.splitlines() if line.startswith('  - "condicion_opcional"'))
    assert "No es la verificación que el organismo hace sobre el oferente o su oferta" in organism
    assert "no le exige nada ni a quien usa la opción ni a quien no" in optional
    assert "mantenela, aunque la opción sea voluntaria" in optional


def test_the_v7_filter_examples_keep_the_options_and_the_verification_of_the_offeror():
    """REQ-102, REQ-106: A tiene ejemplos que mantienen una opción con lo que exige y la
    verificación del oferente, y uno de obligación del organismo que se descarta; B suma el «si» de
    la opción y el «no» de la que solo permite. Balanceados: 11 y 11 en A, 5 y 5 en B."""
    first, second = row_filter.load_prompts()
    a = _examples(first, '{"razonamiento"')
    kept = [e for e in a if e["decision"] == "mantener"]
    dropped = [e for e in a if e["decision"] == "descartar"]
    assert len(kept) == len(dropped) == 11 and sum(e["decision"] == "duda" for e in a) == 1
    assert any("cronograma" in e["razonamiento"] for e in kept)
    assert any("verifica" in e["razonamiento"] for e in kept)
    assert any(e["motivo"] == "obligacion_organismo" for e in dropped)
    b = _examples(second, '{"razonamiento"')
    assert sum(e["respuesta"] == "si" for e in b) == sum(e["respuesta"] == "no" for e in b) == 5
    assert any("cronograma" in e["razonamiento"] and e["respuesta"] == "si" for e in b)


def test_the_v7_filter_examples_of_an_option_have_no_percentage_and_no_partial_quote():
    """REQ-106 (O-254-1, generalidad): los ejemplos de opciones del filtro no tienen la forma de la
    cláusula que se mide (la cotización parcial con un porcentaje mínimo): ninguna línea de
    ejemplo de A o de B habla de porcentajes, de por ciento ni de cotizar una parte, y hay un
    ejemplo de una opción de otra forma (entrega escalonada con su cronograma) mantenida como
    condición de esa opción, en A y en B."""
    first, second = row_filter.load_prompts()
    for prompt in (first, second):
        lines = [line for line in prompt.splitlines()
                 if line.startswith(("Fila:", '{"razonamiento"'))]
        assert len(lines) >= 20
        for line in lines:
            lowered = line.lower()
            for forbidden in ("porcentaje", "por ciento", "cotizar solo una parte", "cotización parcial",
                              "lote parcial", "cooperativa"):
                assert forbidden not in lowered, (forbidden, line[:80])
    a = _examples(first, '{"razonamiento"')
    b = _examples(second, '{"razonamiento"')
    assert any("entrega escalonada" in e["razonamiento"] and e["decision"] == "mantener" for e in a)
    assert any("entrega escalonada" in e["razonamiento"] and e["respuesta"] == "si" for e in b)


# --- Generalidad: ejemplos inventados, de otro rubro, sin anclas de los casos -------------------

INSTRUCTIONS = {"matriz-definiciones-v4": "matriz-definiciones-v3",
                "matriz-extraccion-v7": "matriz-extraccion-v6", "matriz-filtro-v7": "matriz-filtro-v5"}


def _shingles(text, size=5):
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", folded)
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def _anchors(node):
    """Los textos de las listas esperadas de los casos (anclas, citas y fragmentos)."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [text for value in node.values() for text in _anchors(value)]
    if isinstance(node, list):
        return [text for value in node for text in _anchors(value)]
    return []


@pytest.mark.parametrize("name", INSTRUCTIONS)
def test_what_the_new_instructions_add_repeats_no_five_words_of_the_case_files(name):
    """REQ-106 (generalidad, P4): lo que agregan el bloque, la extracción y el filtro nuevos no
    repite cinco palabras seguidas de las listas esperadas de los casos 00 a 06
    (`corpus/casos/*/esperado/`). Las secuencias que ya traía la versión anterior son de
    estructura («pliego de bases y condiciones») o decisiones del responsable copiadas literal
    (T-240). Se saltea si `corpus/casos/` no está montado: la comprobación con huellas está en
    `test_definitions.py`."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno: montarlo para comprobar la "
                    "generalidad contra las anclas de los casos")
    known = set()
    for path in files:
        for anchor in _anchors(yaml.safe_load(path.read_text(encoding="utf-8"))):
            known |= _shingles(anchor)
    assert len(known) > 100
    added = _shingles(_read(name)) - _shingles(_read(INSTRUCTIONS[name]))
    hits = sorted(added & known)
    assert not hits, [hashlib.sha256(h.encode()).hexdigest()[:12] for h in hits]
