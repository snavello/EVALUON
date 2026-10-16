"""T-258 · frente de la matriz de la ronda del comité (REQ-101, REQ-102; spec 015, decisiones del
2026-10-10 al 2026-10-12; ADR-0054 y ADR-0058).

Qué se prueba, sin GPU (el modelo es el doble con guion de `tests/tenders/scripted.py` o un doble
propio): las definiciones del 2026-10-12 en el bloque común v5 (presentación física, la oferta
económica por el formulario del Portal, la prórroga en la fila del plazo, el derecho posterior del
filtro), la extracción v8 y la completitud v6 (la prórroga y el cómputo en la fila del plazo, la
opción de la que una fila es condición), la pasada de unión de las filas del mismo asunto y de la
nota de una tabla con su cláusula, el párrafo que introduce los ítems de un anexo como encabezado,
el reintento de la extracción con memoria y los caracteres de área privada. La prueba con el modelo
real está en el informe de la tarea (pedidos guardados reenviados). Los textos son inventados y de
otro rubro (P4).
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import yaml
from django.conf import settings

from evaluon.ai import AIServiceError
from evaluon.tenders import models as m
from evaluon.tenders.proposal import extraction, joining, quotes, sentences
from evaluon.tenders.proposal import filter as row_filter
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.proposal.extraction import Found
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
)

PROMPTS = Path(extraction.PROMPTS_DIR)
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"
PUA = chr(0xF0A7)


def _read(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _examples(text, start):
    return [json.loads(line) for line in text.splitlines() if line.startswith(start)]


# --- Versiones vigentes ----------------------------------------------------------------------------


def test_the_active_versions_are_the_t258_ones_and_the_older_ones_stay_published():
    """REQ-106, P6: T-258 publica el bloque v5 y v6, la extracción v8 y v9, la completitud v6 y la
    unión v1, y registra como vigentes el bloque v6 y la extracción v9 (la fila del plazo sin el
    aviso de no renovar); las anteriores siguen publicadas (congeladas)."""
    versions = settings.MATRIX_PROMPT_VERSIONS
    assert versions["definiciones"] == "matriz-definiciones-v10"  # T-285
    assert versions["extraccion"] == "matriz-extraccion-v14"  # T-285
    assert versions["completitud"] == "matriz-completitud-v7"  # T-279
    assert versions["union"] == "matriz-union-v2"  # T-279
    for old in ("matriz-definiciones-v4", "matriz-extraccion-v7", "matriz-completitud-v5",
                "matriz-definiciones-v5", "matriz-extraccion-v8", "matriz-definiciones-v6",
                "matriz-extraccion-v9"):
        assert (PROMPTS / f"{old}.md").is_file()


# T-280: las circulares v8 no llevan el bloque (plan 016; ver `test_circulars`).
@pytest.mark.parametrize("name", ["extraccion", "completitud", "union", "filtro"])
def test_every_instruction_with_the_block_records_the_active_block(name):
    """REQ-106, P6: la versión y la huella del bloque vigente (v7) quedan en el registro de cada
    instrucción que lo usa, también la de la unión."""
    record = extraction.load_instruction(name).record
    assert record["definiciones"]["version"] == "matriz-definiciones-v10"  # T-285
    assert record["definiciones"]["sha256"] == extraction.text_sha256(_read("matriz-definiciones-v10"))


def test_the_v7_block_keeps_two_obligations_on_the_same_object_in_two_rows():
    """REQ-101 (Coordinador, verificación de T-258): la unidad de sentido une solo la misma
    obligación dicha en varias oraciones; dos obligaciones distintas sobre el mismo objeto (lo que
    cumple una forma de garantía y acompañar su copia) van en filas separadas. El resto del bloque v6
    sigue igual."""
    block = _read("matriz-definiciones-v7")
    rule = ("- La unidad de sentido une solo la misma obligación dicha en varias oraciones. Dos "
            "obligaciones distintas sobre el mismo objeto van en filas separadas, aunque estén seguidas")
    assert rule in block
    assert "acompañar su copia con la oferta, por otro" in block
    line = next(x for x in block.splitlines() if x.startswith(rule))
    assert block.replace("\n" + line, "") == _read("matriz-definiciones-v6")


def test_the_v10_extraction_returns_a_guarantee_limit_and_its_copy_as_two_requirements():
    """REQ-101 (Coordinador): la extracción v10 dice que dos obligaciones distintas sobre el mismo
    objeto son dos requisitos, y su ejemplo (una forma de garantía con su límite y la copia que se
    acompaña) devuelve dos filas; los ejemplos siguen balanceados."""
    text = _read("matriz-extraccion-v10")
    assert "dos obligaciones distintas sobre el mismo objeto, aunque estén seguidas, son dos requisitos" in text
    lines = text.splitlines()
    at = next(n for n, line in enumerate(lines) if line.startswith("Tramo") and "cheque de pago diferido" in line)
    answer = json.loads(lines[at + 1])
    assert [r["cita"].split(",")[0] for r in answer["requisitos"]] == [
        "Si la garantía se constituye con un cheque de pago diferido",
        "Será requisito adjuntar a la propuesta una copia del cheque."]
    examples = _examples(text, '{"requisitos"')
    with_requirements = sum(1 for e in examples if e["requisitos"] or e["tecnico"])
    discarded = sum(1 for e in examples if e["descarte"])
    assert abs(with_requirements - discarded) <= 1 and discarded >= 16


def test_the_v10_extraction_motive_of_the_organism_matches_the_block():
    """REQ-102 (O-258-2): el motivo `obligacion_organismo` de la extracción dice lo mismo que el
    bloque: lo que hace el organismo y los derechos que se reserva para después de la oferta; ya no
    trae la frase «que la oferta no puede contradecir ni condicionar», que el bloque sacó."""
    text = _read("matriz-extraccion-v10")
    line = next(x for x in text.splitlines() if x.startswith("- obligacion_organismo:"))
    assert "un derecho que se reserva para después de la oferta (ampliar o reducir lo adjudicado" in line
    assert "contradecir ni condicionar" not in line
    assert "No es la verificación que el organismo hace sobre el oferente o su oferta" in line
    assert "Los derechos que el organismo se reserva para después de la oferta" in _read("matriz-definiciones-v7")


# --- Bloque común v5: decisiones del 2026-10-12 ------------------------------------------------------


def test_the_v5_block_makes_the_paper_delivery_the_portal_asks_for_a_requirement():
    """REQ-102 (decisión del 2026-10-12, «presentación física»): entregar en papel, en la mesa de
    entradas, lo que el Portal marca para presentar así es requisito, aunque la oración empiece por
    la carga en el Portal; si no consta, no cumple."""
    block = _read("matriz-definiciones-v5")
    assert "Entra también entregar en papel, en la mesa de entradas del organismo" in block
    assert "si la oferta no lo entrega, no cumple" in block
    assert "aunque la oración empiece por la carga en el Portal" in block


def test_the_v5_block_says_completing_the_quote_in_the_portal_form_is_not_a_row():
    """REQ-102 (decisión del 2026-10-12): completar la oferta económica en el formulario del Portal
    no es fila propia: es forma de presentar por el Portal y su contenido lo cubren la cotización por
    renglón y las filas técnicas."""
    block = _read("matriz-definiciones-v5")
    assert "Tampoco es una fila propia completar la cotización en el formulario del Portal" in block
    assert "ya lo cubren la cotización de cada renglón y las filas técnicas" in block


def test_the_v5_block_puts_the_automatic_extension_in_the_row_of_the_term():
    """REQ-101 (decisión del 2026-10-12, «En la misma fila del plazo»): el mantenimiento de la oferta
    y su prórroga automática son una fila; la frase ambigua sobre «lo que la oferta no puede
    contradecir ni condicionar» (que dejaba afuera la prórroga) sale de las obligaciones del organismo."""
    block = _read("matriz-definiciones-v5")
    assert "El mantenimiento de la oferta y su prórroga automática van en la misma fila del plazo" in block
    assert "Un plazo y las oraciones que lo precisan son una sola fila" in block
    assert "el plazo durante el cual la oferta sigue vigente, y su renovación, sí son un compromiso" in block
    assert "y lo que la oferta no puede contradecir ni condicionar" not in block


def test_the_v5_block_defines_the_later_right_the_filter_uses_as_a_motive():
    """REQ-102 (H7 del comité): el motivo `derecho_posterior` del filtro tiene su definición en el
    bloque común, con las mismas palabras que el motivo («la oferta no puede condicionar»)."""
    block = _read("matriz-definiciones-v5")
    assert "Los derechos que el organismo se reserva para después de la oferta" in block
    assert "la oferta no puede condicionarlos" in block
    assert "derecho_posterior" in settings.FILTER_MOTIVES
    first, _ = row_filter.load_prompts()
    line = next(x for x in first.splitlines() if '"derecho_posterior"' in x)
    assert "posterior a la oferta" in line and "no puede condicionar" in line


def test_the_v5_block_keeps_every_decision_of_the_v4_block():
    """REQ-102: el bloque nuevo suma y precisa; lo que decidió el responsable y lo que corrigió
    T-254 sigue (la verificación del oferente, la opción, la forma elegida, la unidad de sentido)."""
    block = _read("matriz-definiciones-v5")
    for literal in ("El pago, la moneda de pago y la factura", "La forma de presentar la oferta por el Portal",
                    "la confirmación por el Administrador Legitimado", "Los compromisos que se cumplen al presentarse",
                    "la mera presentación implicará el conocimiento y aceptación del pliego", "Las consecuencias",
                    "la moneda en que se cotiza la oferta", "Es un requisito externo de la oferta",
                    "Lo que cuenta es de quién es lo que se verifica, no quién lo verifica",
                    "No lo es la verificación que el organismo hace sobre el oferente o su oferta",
                    "el texto de una norma que se transcribe",
                    "la condición de una opción entra, como condición de esa opción",
                    "únicamente la oración que no le exige nada ni a la oferta que usa la opción ni a la que no",
                    "mirá qué le exige la oración a quien usa la opción",
                    "el límite del pagaré o la póliza según la norma de la Superintendencia",
                    "se evalúan solo en la oferta que eligió esa forma", "Las excepciones y las dispensas",
                    "Una fila es una unidad de sentido", "cuatro patas", "dos ojos", "marrón"):
        assert literal in block, literal
    for forbidden in ("dividí", "fragmento más corto", "ante la duda", "mantené"):
        assert forbidden not in block.lower()


def test_the_v6_block_leaves_the_notice_of_not_renewing_out_of_the_row_of_the_term():
    """REQ-101, REQ-102 (Coordinador, 2026-10-12, tras T-229 y T-239): la fila del plazo lleva el
    plazo, su cómputo y la prórroga automática, y no las oraciones del aviso de no renovar, que son
    un trámite posterior y optativo del oferente (no son fila ni condición de una opción). El resto
    del bloque v5 sigue igual."""
    block = _read("matriz-definiciones-v6")
    assert "El mantenimiento de la oferta y su prórroga automática van en la misma fila del plazo" in block
    assert "Las oraciones que dicen cómo el oferente puede no renovarla" in block
    assert "no van en esa fila ni en otra: son un trámite posterior y optativo del oferente" in block
    assert "no son la condición de una opción de la oferta" in block
    previous = _read("matriz-definiciones-v5")
    assert block.replace(block[block.index(" Las oraciones que dicen cómo"):block.index(
        "de una opción de la oferta.") + len("de una opción de la oferta.")], "") == previous


def test_the_v9_extraction_copies_the_term_without_the_notice_of_not_renewing():
    """REQ-101 (Coordinador, 2026-10-12): el ejemplo del plazo trae después el aviso de no renovar y
    su firma, y la cita se queda con el plazo, el cómputo y la renovación; un tramo que solo trae la
    fecha del aviso se descarta como dato del procedimiento. Los ejemplos siguen balanceados."""
    text = _read("matriz-extraccion-v9")
    assert "no se copian en esa cita ni en otra: son un trámite posterior y optativo del oferente" in text
    lines = text.splitlines()
    at = next(n for n, line in enumerate(lines) if line.startswith("Tramo") and "renovada de pleno derecho" in line)
    assert "no quiera seguir con su propuesta" in lines[at] and "firma del representante" in lines[at]
    answer = json.loads(lines[at + 1])
    assert len(answer["requisitos"]) == 1
    quote = answer["requisitos"][0]["cita"]
    assert quote.endswith("y así sucesivamente.") and "no quiera seguir" not in quote
    notice = next(n for n, line in enumerate(lines) if line.startswith("Tramo") and "vale la fecha en que ingresa" in line)
    assert '"dato_procedimiento"' in lines[notice + 1]
    examples = _examples(text, '{"requisitos"')
    with_requirements = sum(1 for e in examples if e["requisitos"] or e["tecnico"])
    discarded = sum(1 for e in examples if e["descarte"])
    assert with_requirements == discarded == 16


# --- Extracción v8 -----------------------------------------------------------------------------------


def test_the_v8_extraction_keeps_the_term_its_count_and_its_extension_in_one_quote():
    """REQ-101 (decisión del 2026-10-12): la extracción pide copiar juntos el plazo, cómo se cuenta y
    su renovación automática, aunque esta se diga como efecto; el ejemplo empieza con la cita de una
    norma (para no enseñar a cortarla) y es una sola cita con las tres oraciones."""
    text = _read("matriz-extraccion-v8")
    assert "El mantenimiento de la oferta y su prórroga automática van en la misma cita" in text
    assert "aunque empiece con la cita de una norma" in text
    examples = _examples(text, '{"requisitos"')
    term = [e for e in examples if e["requisitos"] and "renovada de pleno derecho" in e["requisitos"][0]["cita"]]
    assert len(term) == 1 and len(term[0]["requisitos"]) == 1
    quote = term[0]["requisitos"][0]["cita"]
    assert quote.startswith("Conforme al artículo") and quote.count(". ") == 2


def test_the_v8_extraction_keeps_the_mixed_portal_and_paper_sentence_and_discards_the_portal_form():
    """REQ-102 (decisión del 2026-10-12): la oración que habla de la carga en la plataforma y pide
    además entregar en papel es un requisito entero; subir la propuesta económica a la plataforma
    sigue siendo forma de presentar por el Portal."""
    text = _read("matriz-extraccion-v8")
    examples = _examples(text, '{"requisitos"')
    mixed = [e for e in examples if e["requisitos"] and "van en papel" in e["requisitos"][0]["cita"]]
    assert len(mixed) == 1 and mixed[0]["descarte"] == ""
    lines = text.splitlines()
    at = next(n for n, line in enumerate(lines) if "subirá el archivo con la propuesta económica" in line)
    assert '"forma_presentacion_portal"' in lines[at + 1]


def test_the_v8_extraction_asks_for_the_option_of_each_requirement():
    """REQ-102 (interfaz con T-257): cada requisito trae `opcion`, vacío si vale para toda oferta o el
    nombre de la opción que el oferente puede no usar; la forma de la garantía no es una opción. Los
    ejemplos la llevan: la subcontratación y el plazo menor con su opción, el resto vacíos."""
    text = _read("matriz-extraccion-v8")
    assert '"opcion" va vacío ("") si el requisito vale para toda oferta' in text
    assert "la de la garantía) no es una opción" in text
    examples = _examples(text, '{"requisitos"')
    options = [(r["cita"], r["opcion"]) for e in examples for r in e["requisitos"]]
    assert all(set(r) == {"cita", "clase", "opcion"} for e in examples for r in e["requisitos"])

    def option_of(start):
        return next(option for quote, option in options if quote.startswith(start))

    assert option_of("Si la editorial subcontrata") == "subcontratacion"
    assert option_of("Las editoriales podrán ofrecer un plazo") == "otra"
    assert option_of("Si la garantía se constituye con cheque") == ""
    assert {option for _, option in options} <= {"", *extraction.OPTIONS}


def test_the_v8_extraction_examples_are_balanced_between_requirements_and_discards():
    """REQ-106 (ADR-0055, regla 4): tantos ejemplos con requisitos como descartados (a lo sumo uno de
    diferencia), con el derecho del organismo y los ítems de la ejecución bajo un encabezado."""
    examples = _examples(_read("matriz-extraccion-v8"), '{"requisitos"')
    with_requirements = sum(1 for e in examples if e["requisitos"] or e["tecnico"])
    discarded = sum(1 for e in examples if e["descarte"])
    assert abs(with_requirements - discarded) <= 1 and discarded >= 15


def test_the_schema_asks_for_the_option_and_the_shape_accepts_it():
    """REQ-102: el esquema pide `opcion` (vacío o un nombre de `OPTIONS`); la forma la acepta, acepta
    la salida sin ella (vacía) y rechaza un nombre desconocido."""
    schema = extraction.build_schema(["T1"], [])
    entry = schema["properties"]["T1"]["properties"]["requisitos"]["items"]
    assert entry["required"] == ["cita", "clase", "opcion"]
    assert entry["properties"]["opcion"]["enum"] == ["", *extraction.OPTIONS]
    assert {"mipyme", "oferta_alternativa", "descuento", "subcontratacion", "cotizacion_parcial"} <= set(
        extraction.OPTIONS)
    shaped = extraction.shape_item({"requisitos": [{"cita": "a", "clase": "formal", "opcion": "mipyme"},
                                                   {"cita": "b", "clase": "formal"}],
                                    "tecnico": [], "descarte": ""})
    assert shaped.options == ["mipyme", ""]
    with pytest.raises(extraction.InvalidItem):
        extraction.shape_item({"requisitos": [{"cita": "a", "clase": "formal", "opcion": "cupón"}],
                               "tecnico": [], "descarte": ""})


# --- Completitud v6 ----------------------------------------------------------------------------------


def test_the_v6_completeness_recovers_the_extension_of_a_term_already_found():
    """REQ-101 (decisión del 2026-10-12): si al plazo ya encontrado le falta su renovación
    automática, la completitud la devuelve como faltante y el sistema la une a la fila del plazo; los
    ejemplos siguen balanceados (5 y 5)."""
    text = _read("matriz-completitud-v6")
    assert "el sistema la une a la fila del plazo" in text
    answers = _examples(text, '{"faltantes"')
    assert sum(1 for a in answers if a["faltantes"]) == sum(1 for a in answers if not a["faltantes"]) == 5
    assert any("renovada de pleno derecho" in f["cita"] for a in answers for f in a["faltantes"])


# --- Generalidad: ninguna ancla de los casos ---------------------------------------------------------

NEW = {"matriz-definiciones-v5": "matriz-definiciones-v4", "matriz-extraccion-v8": "matriz-extraccion-v7",
       "matriz-completitud-v6": "matriz-completitud-v5", "matriz-union-v1": None,
       "matriz-definiciones-v6": "matriz-definiciones-v5", "matriz-extraccion-v9": "matriz-extraccion-v8",
       "matriz-definiciones-v7": "matriz-definiciones-v6", "matriz-extraccion-v10": "matriz-extraccion-v9"}


def _shingles(text, size=5):
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))
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
def test_what_the_t258_instructions_add_repeats_no_five_words_of_the_case_files(name):
    """REQ-106 (generalidad, P4): lo que agregan las instrucciones de T-258 no repite cinco palabras
    seguidas de las listas esperadas de los casos 00 a 06. Se saltea si `corpus/casos/` no está
    montado: la comprobación con huellas está en `test_definitions.py`."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno")
    known = set()
    for path in files:
        for anchor in _anchors(yaml.safe_load(path.read_text(encoding="utf-8"))):
            known |= _shingles(anchor)
    assert len(known) > 100
    before = _shingles(_read(NEW[name])) if NEW[name] else set()
    hits = sorted((_shingles(_read(name)) - before) & known)
    assert not hits, [hashlib.sha256(h.encode()).hexdigest()[:12] for h in hits]


@pytest.mark.parametrize("name", ["matriz-extraccion-v8", "matriz-completitud-v6", "matriz-union-v1",
                                  "matriz-extraccion-v9", "matriz-extraccion-v10"])
@pytest.mark.parametrize("paraphrase", [
    "pesos argentinos", "incluirán el iva", "pagaré", "euros", "conocimiento y la aceptación",
    "documentación solicitada determinará", "durante 60 días", "sesenta", "presentación de la factura",
    "administrador", "habilidad para contratar", "certificado de visita", "oferta alternativa",
    "descuento", "prorrogada automáticamente", "lapso igual al inicial", "mesa de entrada",
    "requiere presentar", "detalle de renglones", "no renovar", "manifestar su voluntad", "antelación",
    "tal manifestación",
])
def test_the_t258_examples_do_not_paraphrase_the_clauses_of_the_measurement_cases(name, paraphrase):
    """REQ-106 (D-236-1, P7): los ejemplos nuevos son de otro rubro y de otra redacción: no repiten la
    prórroga, la presentación en papel ni la oferta económica de los casos de medición."""
    text = _read(name).lower()
    for example in [line for line in text.splitlines()
                    if line.startswith(("tramo", "fila", "requisitos ya", "{"))]:
        assert paraphrase not in example, (name, paraphrase)


# --- Unión de las filas del mismo asunto: la instrucción ----------------------------------------------


def test_the_join_instruction_has_the_block_reasoning_first_and_balanced_examples():
    """REQ-101, REQ-106 (ADR-0055): la unión usa el bloque común, pide el razonamiento antes de la
    respuesta y sus ejemplos tienen tantos «una» como «dos», con una nota de tabla y dos condiciones
    de la misma forma de garantía que quedan separadas."""
    raw = _read("matriz-union-v1")
    assert extraction.DEFINITIONS_MARK in raw
    examples = _examples(raw, '{"razonamiento"')
    assert [list(e) for e in examples] == [["razonamiento", "filas"]] * len(examples)
    assert sum(e["filas"] == "una" for e in examples) == sum(e["filas"] == "dos" for e in examples) == 3
    assert "tabla" in raw and "misma forma de garantía" in raw
    schema = joining.build_schema(["P1"])
    assert list(schema["properties"]["P1"]["properties"]) == ["razonamiento", "filas"]


# --- Unión: pares candidatos ----------------------------------------------------------------------------


def _unit(text, key="sec-i/5.1", kind="parrafo", pk=1, reading=1, path="Sección I › 5.1"):
    segment = NS(pk=pk, key=key, text=text, segment_type=kind, reading_id=reading, path=path, label="",
                 items=[], section_class="")
    return extraction.Unit(segment, "Pliego", pk)


def _span(text, sentence):
    start = text.index(sentence)
    return (start, start + len(sentence))


TERM = "Las editoriales mantendrán su propuesta por noventa días."
COUNT = "La fecha de apertura no se cuenta."
RENEWAL = "La propuesta quedará renovada por otro período igual."


def test_two_rows_of_a_segment_with_at_most_two_short_sentences_between_are_a_pair():
    """REQ-101: dos filas seguidas del mismo tramo, con hasta dos oraciones cortas en el medio, son un
    par candidato; con más texto en el medio, o en una tabla, no."""
    text = f"5.1. {TERM} {COUNT} {RENEWAL}"
    unit = _unit(text)
    first, second = Found("formal", _span(text, TERM)), Found("formal", _span(text, RENEWAL))
    pairs = joining.contiguous_pairs(unit, [second, first])
    assert len(pairs) == 1 and pairs[0].first is first and pairs[0].between == COUNT

    long_gap = f"5.1. {TERM} {'Otra oración del pliego que habla de otra cosa. ' * 9}{RENEWAL}"
    unit = _unit(long_gap)
    rows = [Found("formal", _span(long_gap, TERM)), Found("formal", _span(long_gap, RENEWAL))]
    assert joining.contiguous_pairs(unit, rows) == []
    table = _unit(text, kind="tabla")
    assert joining.contiguous_pairs(table, [first, second]) == []


def test_a_row_of_a_table_is_paired_with_the_last_row_of_the_clause_it_hangs_from():
    """REQ-101 (H4): la fila de un tramo `tabla` se pregunta con la última fila del tramo del que
    cuelga la tabla (su padre por la clave, en la misma lectura)."""
    clause_text = "7.3. Los oferentes declararán sus vínculos. Deberán usar el formulario del anexo."
    note_text = "Nombre Cargo\nSe informará además todo vínculo con el personal de la biblioteca."
    clause = _unit(clause_text, key="sec-i/7.3", pk=1)
    note = _unit(note_text, key="sec-i/7.3/tabla-1", kind="tabla", pk=2)
    other = _unit(note_text, key="sec-i/7.3/tabla-1", kind="tabla", pk=3, reading=2)
    rows = [Found("formal", (5, 43)), Found("formal", (44, len(clause_text)))]
    noted = Found("formal", _span(note_text, "Se informará además todo vínculo con el personal de la biblioteca."))
    decisions = {1: NS(found=rows), 2: NS(found=[noted]), 3: NS(found=[Found("formal", (0, 5))])}

    pairs = joining.table_pairs([clause, note, other], decisions)

    assert len(pairs) == 1
    assert pairs[0].kind == joining.TABLE_NOTE and pairs[0].first is rows[1] and pairs[0].second is noted


# --- Unión: lo que hace con la respuesta ------------------------------------------------------------------


class _Output:
    def __init__(self, content, messages=()):
        self.content = content
        self.request = {"messages": list(messages)}
        self.prompt_tokens = 10
        self.completion_tokens = 5
        self.finish_reason = "stop"


@pytest.fixture
def a_run(operator_user, script):
    """Una propuesta ya hecha, para colgarle los pedidos de la unión."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[para("SECCIÓN I - CONDICIONES"),
                                                         para("1. OBJETO", "1.1. Compra de libros.")]],
                                                       header=None))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return requested.run


def _answering(monkeypatch, answer):
    calls = []

    def fake(messages, schema, **options):
        calls.append((messages, schema, options))
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return _Output(answer(schema), messages)
        return _Output(json.dumps({alias: {"razonamiento": "prueba", "filas": answer}
                                   for alias in schema["properties"]}), messages)

    monkeypatch.setattr(joining.generation, "generate_batch", fake)
    return calls


def _case():
    text = f"5.1. {TERM} {COUNT} {RENEWAL}"
    unit = _unit(text)
    first = Found("formal", _span(text, TERM), fragments=[_span(text, TERM)], unit=_span(text, TERM))
    second = Found("formal", _span(text, RENEWAL), fragments=[_span(text, RENEWAL)], option="")
    second.passes = [m.PassName.COMPLETITUD.value]
    return text, unit, first, second, {1: NS(found=[first, second])}


@pytest.mark.django_db
def test_two_rows_the_model_says_are_one_become_one_row_with_the_contiguous_quote(a_run, monkeypatch):
    """REQ-101 (H3; decisión del 2026-10-12): si el modelo responde «una», las dos filas quedan en una
    cuya cita va de la primera a la última oración (el recorte contiguo del tramo, con el cómputo del
    medio), con los fragmentos y las pasadas de las dos; el pedido queda guardado (P6)."""
    text, unit, first, second, decisions = _case()
    calls = _answering(monkeypatch, joining.ONE)

    result = joining.Joiner(a_run).join([unit], decisions)

    assert decisions[1].found == [first]
    assert text[first.span[0]:first.span[1]] == f"{TERM} {COUNT} {RENEWAL}"
    assert len(first.fragments) == 2 and first.passes == ["extraccion", "completitud"]
    assert result.stats["joined"] == 1 and len(calls) == 1
    assert calls[0][2]["max_tokens"] == joining.MAX_OUTPUT_TOKENS
    user = calls[0][0][1]["content"]
    assert f"Fila A: «{TERM}»" in user and f"Entre las dos, el pliego dice: «{COUNT}»" in user
    step = m.RunStep.objects.filter(run=a_run, pass_name="unificacion").order_by("-id").first()
    assert step.parsed["pasada"] == "union_oraciones"
    assert step.parsed["instruccion"]["version"] == "matriz-union-v2"  # T-279
    assert step.parsed["pares"]["P1"]["filas"] == "una"
    assert step.parsed["pares"]["P1"]["razonamiento"] == "prueba"


@pytest.mark.django_db
@pytest.mark.parametrize("answer, anomaly", [
    (joining.TWO, None),
    (lambda schema: "no es json", joining.ANOMALY_INVALID),
    (lambda schema: json.dumps({"P9": {"razonamiento": "", "filas": "una"}}), joining.ANOMALY_MISSING_ALIAS),
    (lambda schema: json.dumps({"P1": {"filas": "una"}}), joining.ANOMALY_INVALID),
    (AIServiceError("se cortó", service="generation_batch"), joining.ANOMALY_SERVICE),
])
def test_rows_stay_as_they_were_unless_the_model_says_one(a_run, monkeypatch, answer, anomaly):
    """REQ-101, P6 (O-258-1): con «dos», una salida que no es JSON, un alias que falta, una respuesta
    sin la forma o una falla del servicio, las dos filas quedan como estaban (nada se pierde), y el
    pedido queda guardado con su instrucción y, si falló, con su anomalía."""
    text, unit, first, second, decisions = _case()
    span = first.span
    before = m.RunStep.objects.filter(run=a_run, pass_name="unificacion").count()
    _answering(monkeypatch, answer)

    result = joining.Joiner(a_run).join([unit], decisions)

    assert decisions[1].found == [first, second] and first.span == span
    steps = m.RunStep.objects.filter(run=a_run, pass_name="unificacion").order_by("id")
    assert steps.count() == before + 1
    step = steps.last()
    assert step.parsed["pasada"] == "union_oraciones"
    assert step.parsed["instruccion"]["version"] == "matriz-union-v2"  # T-279
    assert step.request["messages"][1]["content"].startswith("Pares de filas propuestas")
    types = [a["type"] for a in step.anomalies]
    assert types == ([anomaly] if anomaly else [])
    if anomaly == joining.ANOMALY_SERVICE:
        assert result.stats["failed_requests"] == 1 and step.raw_output == ""


@pytest.mark.django_db
def test_rows_with_a_different_option_are_never_joined(a_run, monkeypatch):
    """REQ-101, REQ-102 (H-258-2): una fila de toda oferta y una fila de una opción (o de dos
    opciones distintas) no son un par y no se unen aunque el modelo diga «una»: la fila general no
    pasa a ser de la opción y se sigue evaluando en todas las ofertas."""
    text, unit, first, second, decisions = _case()
    second.option = "cotizacion_parcial"
    calls = _answering(monkeypatch, joining.ONE)

    assert joining.contiguous_pairs(unit, [first, second]) == []
    joining.Joiner(a_run).join([unit], decisions)

    assert decisions[1].found == [first, second]
    assert first.option == "" and second.option == "cotizacion_parcial"
    assert calls == []
    first.option = "mipyme"
    assert joining.contiguous_pairs(unit, [first, second]) == []
    second.option = "mipyme"
    assert len(joining.contiguous_pairs(unit, [first, second])) == 1


def test_a_table_note_with_another_option_is_not_paired_with_the_clause():
    """REQ-101, REQ-102 (H-258-2): la nota de una tabla con una opción distinta de la fila de su
    cláusula no se pregunta como par."""
    clause_text = "7.3. Los oferentes declararán sus vínculos con el comité."
    note_text = "Nombre Cargo\nQuien use la opción informará además su participación."
    clause = _unit(clause_text, key="sec-i/7.3", pk=1)
    note = _unit(note_text, key="sec-i/7.3/tabla-1", kind="tabla", pk=2)
    row = Found("formal", (5, len(clause_text)))
    noted = Found("formal", _span(note_text, "Quien use la opción informará además su participación."),
                  option="otra")
    assert joining.table_pairs([clause, note], {1: NS(found=[row]), 2: NS(found=[noted])}) == []


def test_two_quotes_of_the_same_unit_with_a_different_option_stay_two_rows():
    """REQ-101, REQ-102 (H-258-2): en la extracción, dos citas de la misma unidad de sentido con
    distinta opción no se unen en una fila (`merge_into`); con la misma opción, sí."""
    general = Found("formal", (0, 40), fragments=[(0, 20)], unit=(0, 40))
    option = Found("formal", (0, 40), fragments=[(21, 40)], unit=(0, 40), option="mipyme")
    found = [general]
    assert extraction.merge_into(found, option) is None
    assert found == [general, option] and general.option == "" and option.option == "mipyme"
    same = Found("formal", (10, 40), fragments=[(25, 40)], unit=(10, 40), option="mipyme")
    assert extraction.merge_into(found, same) is option
    assert len(found) == 2 and option.fragments == [(21, 40), (25, 40)]


def test_the_rule_unification_does_not_merge_rows_with_a_different_option():
    """REQ-102 (H-258-2): la unificación por regla (`dedup`) no junta como repetidas dos filas con el
    mismo texto y distinta opción."""
    from evaluon.tenders.proposal import dedup

    text = "Los oferentes adjuntarán la constancia del registro de editoriales vigente."
    a = (NS(segment=NS(pk=1, key="a/1", text=text)), Found("formal", (0, len(text))))
    b = (NS(segment=NS(pk=2, key="b/1", text=text)), Found("formal", (0, len(text)), option="mipyme"))
    assert len(dedup.unify([a, b], 0.9, containment=True).body) == 2
    b[1].option = ""
    assert len(dedup.unify([a, b], 0.9, containment=True).body) == 1


@pytest.mark.django_db
def test_a_table_note_the_model_says_is_one_becomes_a_quote_of_the_clause_row(a_run, monkeypatch):
    """REQ-101 (H4): la nota de la tabla que complementa la declaración de la cláusula deja de ser una
    fila propia y pasa a ser una cita más de esa fila (`extra_quotes`, alcance `repetida`)."""
    clause_text = "7.3. Los oferentes declararán sus vínculos con el comité."
    note_text = "Nombre Cargo\nSe informará además todo vínculo con el personal de la biblioteca."
    clause = _unit(clause_text, key="sec-i/7.3", pk=1)
    note = _unit(note_text, key="sec-i/7.3/tabla-1", kind="tabla", pk=2)
    row = Found("formal", (5, len(clause_text)))
    noted = Found("formal", _span(note_text, "Se informará además todo vínculo con el personal de la biblioteca."))
    decisions = {1: NS(found=[row]), 2: NS(found=[noted])}
    _answering(monkeypatch, joining.ONE)

    result = joining.Joiner(a_run).join([clause, note], decisions)

    assert decisions[2].found == [] and decisions[1].found == [row]
    assert result.attached == {id(row): [(note, noted)]}
    unification = NS(repeated={}, merged=[], attached=result.attached)
    assert proposal.extra_quotes(unification) == {id(row): [(note, noted)]}


@pytest.mark.django_db
def test_the_proposal_joins_two_rows_of_the_same_matter_and_saves_one_requirement(operator_user, script):
    """REQ-101, REQ-025: en la propuesta, dos filas seguidas del mismo tramo que el modelo dice que son
    una quedan en un requisito cuya cita es el recorte del texto canónico con las tres oraciones; la
    pasada queda en los parámetros y la instrucción en `prompt_versions` (P6)."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("5. MANTENIMIENTO", f"5.1. {TERM} {COUNT} {RENEWAL}"),
    ]], header=None))
    script.when(TERM, item([(TERM, "formal"), (RENEWAL, "formal")]))
    script.join_answer = joining.ONE

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    rows = m.Requirement.objects.filter(version=run.version, category__in=["formal", "economico"])
    assert rows.count() == 1
    quote = rows.get().quotes.get()
    canonical = document.readings.get().canonical_text
    assert quote.text == canonical[quote.char_start:quote.char_end]
    assert TERM in quote.text and COUNT in quote.text and RENEWAL in quote.text
    assert "union_oraciones" in run.parameters["passes"]
    assert run.prompt_versions["union"] == "matriz-union-v2"  # T-279
    assert len(script.join_calls) == 1


@pytest.mark.django_db
def test_the_proposal_keeps_two_rows_when_the_model_says_two(operator_user, script):
    """REQ-101: con «dos» las filas quedan separadas (por ejemplo, dos condiciones de la misma forma
    de garantía, que la Comisión conserva separadas)."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("5. MANTENIMIENTO", f"5.1. {TERM} {COUNT} {RENEWAL}"),
    ]], header=None))
    script.when(TERM, item([(TERM, "formal"), (RENEWAL, "formal")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    rows = m.Requirement.objects.filter(version=requested.run.version, category__in=["formal", "economico"])
    assert rows.count() == 2


# --- La opción de la que una fila es condición ------------------------------------------------------------


@pytest.mark.django_db
def test_the_option_the_extraction_names_is_saved_in_the_proposed_requirement(operator_user, script):
    """REQ-102 (interfaz con T-257): la opción que la extracción nombra para un requisito queda en
    `Requirement.proposed["opcion"]` y en el `parsed` del pedido; un requisito de toda oferta no la
    lleva."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("5. TALLERES", "5.1. Si la editorial subcontrata la encuadernación, informará el taller."),
        para("6. CATÁLOGO", "6.1. Cada editorial adjuntará su catálogo vigente."),
    ]], header=None))
    sub = "Si la editorial subcontrata la encuadernación, informará el taller."
    script.when("subcontrata", {"requisitos": [{"cita": sub, "clase": "formal", "opcion": "subcontratacion"}],
                                "tecnico": [], "descarte": ""})
    script.when("catálogo", item([("Cada editorial adjuntará su catálogo vigente.", "formal")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    rows = {r.quotes.get().text: r for r in m.Requirement.objects.filter(
        version=requested.run.version, category__in=["formal", "economico"])}
    assert rows[sub].proposed["opcion"] == "subcontratacion"
    assert "opcion" not in rows["Cada editorial adjuntará su catálogo vigente."].proposed
    step = m.RunStep.objects.filter(run=requested.run, pass_name="extraccion").first()
    recorded = [r for t in step.parsed["tramos"].values() for r in t.get("requisitos", [])]
    assert {"opcion": "subcontratacion"}.items() <= next(r for r in recorded if r.get("opcion")).items()


# --- Reintento de la extracción con memoria ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_retry_of_a_quote_not_found_carries_the_previous_answer_and_the_quote(operator_user, script):
    """REQ-101 (H5 del comité; como la evaluación, ADR-0055, regla 7): el reintento de un tramo con
    una cita que no está en el texto lleva la respuesta anterior del modelo como turno del asistente y
    la cita que no se encontró; lo que vuelve se ubica como siempre."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("5. CATÁLOGO", "5.1. Cada editorial adjuntará el catálogo aprobado por la comisión."),
    ]], header=None))
    good = "Cada editorial adjuntará el catálogo aprobado por la comisión."
    bad = "Cada editorial adjuntará el catálogo aprobado por comisión."

    def answer(blocks, number, default):
        quote = bad if number == 0 else good
        return {alias: item([(quote, "formal")]) if "catálogo" in block["text"] else default[alias]
                for alias, block in blocks.items()}

    script.override(answer)
    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    retry = m.RunStep.objects.filter(run=requested.run, pass_name="extraccion",
                                     retry_of__isnull=False).get()
    messages = retry.request["messages"]
    assert [x["role"] for x in messages] == ["system", "user", "assistant", "user"]
    assert json.loads(messages[2]["content"])["T1"]["requisitos"][0]["cita"] == bad
    assert f"- «{bad}»" in messages[3]["content"]
    assert "letra por letra" in messages[3]["content"]
    row = m.Requirement.objects.get(version=requested.run.version, category="formal")
    assert row.quotes.get().text == good and row.quotes.get().quote_flag == ""


def test_a_retry_without_a_previous_answer_for_the_segment_has_no_memory():
    """REQ-101: si el modelo no devolvió nada para el tramo, el reintento es el pedido de siempre."""
    outcome = extraction.Outcome(unit=None)
    assert extraction.retry_memory(outcome) is None
    outcome.raw = {"requisitos": [], "tecnico": [], "descarte": ""}
    outcome.problem = "sin disposición"
    previous, correction = extraction.retry_memory(outcome)
    assert json.loads(previous) == {"T1": outcome.raw} and "no tiene la forma pedida" in correction


# --- Caracteres de área privada -----------------------------------------------------------------------------


def test_private_use_characters_do_not_count_when_locating_a_quote():
    """REQ-025 (H5 del comité): en la propuesta de la matriz, una viñeta de área privada del texto
    (U+F000 a U+F8FF) no cuenta al ubicar la cita, en el texto ni en la cita; lo que se guarda es el
    recorte del texto canónico."""
    text = f"Documentación: {PUA} Listado del personal afectado. {PUA} Constancia de la aseguradora."
    located = quotes.locate_unit(text, "Listado del personal afectado. Constancia de la aseguradora.",
                                 expand=False)
    assert located is not None
    span = located[0]
    assert text[span[0]:span[1]] == f"Listado del personal afectado. {PUA} Constancia de la aseguradora."
    assert quotes.locate(text, f"{PUA} Constancia de la aseguradora.", ignore_private=True) == quotes.locate(
        text, "Constancia de la aseguradora.", ignore_private=True)
    # Los demás usos (la evaluación, la medición) comparan como antes.
    assert quotes.locate(text, "Listado del personal afectado. Constancia de la aseguradora.") is None
    assert quotes.visible(text) == "Documentación:  Listado del personal afectado.  Constancia de la aseguradora."


def test_the_model_does_not_see_private_use_characters():
    """REQ-101 (H5 del comité): el texto del tramo que ve el modelo, en la extracción y en la
    completitud, no trae los caracteres de área privada."""
    from evaluon.tenders.proposal import completeness

    text = f"{PUA} Listado del personal afectado."
    unit = _unit(text)
    assert PUA not in extraction.render_block("T1", unit)
    candidate = completeness.Candidate(unit, [Found("formal", (2, len(text)))])
    assert PUA not in completeness.render_block("T1", candidate)


# --- El párrafo que introduce los ítems de un anexo -----------------------------------------------------------


def _segments(*texts, prefix="sec-iv/anexo-v/p-"):
    by_key = {}
    for number, text in enumerate(texts, start=1):
        by_key[f"{prefix}{number}"] = NS(key=f"{prefix}{number}", text=text, segment_type="parrafo")
    return by_key


INTRO = "La adjudicataria entregará al área usuaria, antes de empezar los trabajos:"


@pytest.mark.parametrize("texts, target, expected", [
    # Los ítems con viñeta (de área privada o «•») toman el párrafo que termina en «:».
    ((INTRO, f"{PUA} Certificado de cobertura. {PUA} Listado del personal."), 2, INTRO),
    ((INTRO, f"{PUA} Certificado.", f"Documentación del personal: {PUA} Listado."), 3, INTRO),
    ((INTRO, "• Planilla de reposiciones."), 2, INTRO),
    ((INTRO, "1. Planilla de reposiciones.", "2. Constancia de capacitación."), 3, INTRO),
    # El que abre la serie no termina en «:»: sin encabezado.
    (("La adjudicataria entregará lo que sigue.", f"{PUA} Certificado de cobertura."), 2, ""),
    # Un párrafo que no es de ítems: sin encabezado.
    ((INTRO, "El oferente no podrá alegar ignorancia de las condiciones."), 2, ""),
])
def test_the_items_of_an_annex_list_carry_the_paragraph_that_introduces_them(texts, target, expected):
    """REQ-101 (H5 del comité): los párrafos de ítems de una lista de un anexo llevan como encabezado
    el párrafo que los introduce, si termina en «:» (dice quién los entrega y cuándo); es contexto y
    no se cita."""
    by_key = _segments(*texts)
    segment = by_key[f"sec-iv/anexo-v/p-{target}"]
    assert sentences.heading_of(segment, by_key.get) == expected


def test_an_inciso_still_takes_the_paragraph_that_opens_its_list():
    """REQ-101 (T-240): el inciso de un párrafo hermano sigue tomando el párrafo que abre la lista de
    incisos, como antes."""
    by_key = _segments("No podrán presentarse:", "a) Quienes tengan deudas.", "b) Quienes estén sancionados.")
    assert sentences.heading_of(by_key["sec-iv/anexo-v/p-3"], by_key.get) == "No podrán presentarse:"
