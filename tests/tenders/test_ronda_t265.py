"""T-265 · la nota de un anexo que obliga al oferente no es un formulario (REQ-101, REQ-102,
REQ-106; spec 015; D-263-1 de la medición T-263).

Con la extracción v11 (T-262), el tramo de la nota de un anexo que le dice al oferente cómo completar
una planilla, y qué tiene que cumplir lo que informa, salió descartado como `formulario`; con la v10,
el mismo lote daba requisitos. La v11 había sumado un contraste para la oferta económica por el
formulario del Portal («solo dice cómo se completa algo en el sistema»), y su motivo `formulario`
decía solo «un formulario o una planilla para completar»: una nota que dice cómo completar una
planilla quedaba de ese lado. La extracción v12 dice qué es un formulario (la planilla en blanco:
rótulos, columnas, campos, casillas, o el modelo que se firma) y que la nota o la instrucción de un
anexo que le exige algo al oferente es un requisito, con un par de ejemplos inventados de otro rubro
(la planilla en blanco y su nota). Conserva lo de T-262: la presentación física entra y completar la
cotización en el formulario del Portal sigue afuera (decisión del 2026-10-12).

Se prueba sin GPU; la prueba con el modelo real está en el informe de la tarea. Los textos son
inventados (P4).
"""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.tenders.proposal import extraction

PROMPTS = Path(extraction.PROMPTS_DIR)
CASES = Path(settings.BASE_DIR) / "corpus" / "casos"
NEW, PREVIOUS = "matriz-extraccion-v12", "matriz-extraccion-v11"
SECTION = "LAS PLANILLAS DE LOS ANEXOS Y SUS NOTAS"
# Lo que dice que algo se entrega en papel (como en `test_ronda_t262.py`).
PAPER = re.compile(r"papel|impres|físic", re.IGNORECASE)
# El rubro de los ejemplos de siempre.
BOOKS = re.compile(r"libro|biblioteca|editorial|ejemplar|título", re.IGNORECASE)


def _read(name):
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _question(line):
    """El texto del tramo de un ejemplo, sin las comillas ni la nota entre paréntesis que lo
    precede (que a veces trae comillas: «Tramo (con "Encabezado: …"): "…"»)."""
    start = line.index('): "') + 4 if line.startswith("Tramo (") else line.index('"') + 1
    return line[start:].removesuffix('"')


def _pairs(text):
    """`[(texto, respuesta)]` de los ejemplos: el texto del tramo de la línea que empieza con
    «Tramo» y la respuesta JSON de la línea siguiente."""
    lines = text.splitlines()
    return [(_question(line), json.loads(lines[n + 1])) for n, line in enumerate(lines[:-1])
            if line.startswith("Tramo") and lines[n + 1].startswith('{"requisitos"')]


def _section(text, title, following):
    return text.split(f"\n{title}\n")[1].split(f"\n{following}\n")[0]


def _motive(text, name):
    return next(line for line in text.splitlines() if line.startswith(f"- {name}:"))


# --- Versión vigente -------------------------------------------------------------------------------


def test_the_active_extraction_is_v12_and_v11_stays_published():
    """REQ-106, P6: T-265 publica la extracción v12 y la registra como vigente; la v11 sigue
    publicada (congelada). El bloque común sigue en la v8 de T-262 (el filtro pasa a la v9, abajo).
    Cada pedido de la extracción registra la versión v12, la huella de su archivo y la del bloque
    v8."""
    versions = settings.MATRIX_PROMPT_VERSIONS
    # T-279: la vigente pasa a la extracción v13 con el bloque v9; la v12 y la v11 siguen publicadas.
    assert versions["extraccion"] == "matriz-extraccion-v14"
    assert versions["definiciones"] == "matriz-definiciones-v10"
    assert (PROMPTS / f"{NEW}.md").is_file() and (PROMPTS / f"{PREVIOUS}.md").is_file()
    record = extraction.load_instruction("extraccion").record
    assert record["version"] == "matriz-extraccion-v14"
    assert record["sha256"] == extraction.text_sha256(_read("matriz-extraccion-v14"))
    assert record["definiciones"] == {
        "version": "matriz-definiciones-v10",
        "sha256": extraction.text_sha256(_read("matriz-definiciones-v10"))}


# --- La regla nueva: la planilla en blanco es formulario; la nota que obliga, no -------------------


def test_the_formulario_motive_is_the_blank_form_and_not_the_note_that_obliges():
    """REQ-102 (D-263-1): el motivo `formulario` dice que es la planilla en blanco (sus rótulos,
    columnas, campos y casillas, o el modelo que se firma) y que no lo es la nota o la instrucción de
    un anexo que le exige algo al oferente; la v11 decía solo «un formulario o una planilla para
    completar»."""
    motive = _motive(_read(NEW), "formulario")
    for phrase in ("en blanco", "rótulos", "columnas", "campos", "casillas",
                   "el modelo de nota o de declaración que firma",
                   "No es la nota ni la instrucción del pliego que, en un anexo, le exige algo al "
                   "oferente", "esa nota es un requisito"):
        assert phrase in motive, phrase
    assert _motive(_read(PREVIOUS), "formulario") == (
        "- formulario: un formulario o una planilla para completar.")


def test_the_annex_section_says_the_note_that_obliges_is_a_requirement():
    """REQ-102, REQ-101 (D-263-1): una sección propia, entre la de la presentación física y los
    motivos de descarte, dice que la planilla en blanco de un anexo es formulario y que la nota o la
    instrucción que le exige algo al oferente sobre lo que informa es un requisito, aunque hable de
    cómo completar la planilla o empiece con «Nota:», y que se copia cada oración que exige algo."""
    text = _read(NEW)
    assert text.index("LA PRESENTACIÓN FÍSICA") < text.index(SECTION) < text.index(
        "MOTIVOS DE DESCARTE")
    section = _section(text, SECTION, "MOTIVOS DE DESCARTE")
    for phrase in ("La planilla en blanco es un formulario: su motivo es formulario.",
                   "no es el formulario: es un requisito de la oferta, aunque hable de cómo "
                   "completar la planilla y aunque empiece con \"Nota:\"",
                   "Copiá cada oración que exige algo",
                   "no la instrucción del pliego que le dice qué tiene que cumplir lo que informa"):
        assert phrase in section, phrase


def test_the_text_of_a_form_still_is_not_a_requirement_and_the_block_says_it_the_same_way():
    """REQ-106 (entre sí): la sección no contradice al bloque común, que sigue diciendo que el texto
    de un formulario no es un requisito: lo precisa (es lo que el oferente completa o firma tal como
    está, no la instrucción del pliego)."""
    block = _read("matriz-definiciones-v8")
    assert "El texto de un formulario o de una declaración jurada modelo tampoco es un requisito" in (
        block)
    section = _section(_read(NEW), SECTION, "MOTIVOS DE DESCARTE")
    assert ("El texto de un formulario que no es un requisito es el que el oferente completa o firma "
            "tal como está") in section


def test_the_examples_discard_the_blank_form_and_keep_the_note_of_its_annex():
    """REQ-102, REQ-101 (D-263-1): hay un ejemplo de la planilla en blanco de un anexo, que se
    descarta como `formulario`, y enseguida el de su nota, que le exige algo al oferente y da un
    requisito por oración (tres obligaciones distintas, tres filas), con las citas letra por letra.
    Ningún ejemplo descarta una nota, y los que se descartan como `formulario` son un modelo o una
    planilla en blanco."""
    pairs = _pairs(_read(NEW))
    notes = [(q, a) for q, a in pairs if q.startswith("Nota:")]
    assert len(notes) == 1
    question, answer = notes[0]
    assert answer["descarte"] == "" and answer["tecnico"] == []
    assert len(answer["requisitos"]) == 3
    assert all(r["cita"] in question and r["opcion"] == "" for r in answer["requisitos"])
    assert answer["requisitos"][0]["cita"].startswith("Nota:")
    assert BOOKS.search(question)
    forms = [q for q, a in pairs if a["descarte"] == "formulario"]
    assert len(forms) == 2
    assert all(q.startswith("Modelo de") or " | " in q for q in forms)
    at = pairs.index(notes[0])
    assert pairs[at - 1][1]["descarte"] == "formulario" and " | " in pairs[at - 1][0]
    assert pairs[at - 2][1]["descarte"] == "forma_presentacion_portal"
    for q, a in pairs:
        if a["descarte"]:
            assert not q.startswith("Nota:"), q


def test_the_examples_stay_balanced():
    """REQ-106 (ejemplos representativos): siguen siendo tantos tramos con requisitos (o marca
    técnica) como descartados, con uno de diferencia como mucho, y ninguno tiene a la vez un descarte
    y requisitos."""
    pairs = _pairs(_read(NEW))
    kept = sum(1 for _, a in pairs if a["requisitos"] or a["tecnico"])
    discarded = sum(1 for _, a in pairs if a["descarte"])
    assert kept + discarded == len(pairs) == len(_pairs(_read(PREVIOUS))) + 2
    assert abs(kept - discarded) <= 1


# --- Lo que T-262 dejó y sigue igual -----------------------------------------------------------------


def test_v12_keeps_the_physical_presentation_of_t262():
    """REQ-102 (decisión del 2026-10-12): la sección de la presentación física, la salvedad del
    motivo `forma_presentacion_portal` (que sigue igual, al principio del motivo) y la regla de la
    oración que pide algo en papel siguen como en la v11; ningún ejemplo descarta una oración que
    pide algo en papel y siguen los dos que la mantienen, uno de otro rubro."""
    new, old = _read(NEW), _read(PREVIOUS)
    assert (_section(new, "LA PRESENTACIÓN FÍSICA", SECTION)
            == _section(old, "LA PRESENTACIÓN FÍSICA", "MOTIVOS DE DESCARTE"))
    assert _motive(new, "forma_presentacion_portal").startswith(
        _motive(old, "forma_presentacion_portal"))
    rule = next(line for line in old.splitlines()
                if line.startswith("Una oración que habla de la carga en el Portal"))
    assert rule in new.splitlines()
    pairs = _pairs(new)
    for question, answer in pairs:
        if answer["descarte"]:
            assert not PAPER.search(question), question
    kept = [(q, a) for q, a in pairs if PAPER.search(q) and a["requisitos"]]
    assert len(kept) == 2
    assert any(q.startswith("Toda la documentación que pide este capítulo") and not BOOKS.search(q)
               for q, _ in kept)


def test_v12_still_discards_completing_the_quote_in_the_portal_form():
    """REQ-102 (decisión del 2026-10-12): completar la cotización en el formulario del Portal sigue
    siendo la forma de presentar por el Portal: la sección nueva lo dice, el ejemplo del sistema de
    compras se sigue descartando con ese motivo (su nota dice ahora que es la forma de presentar por
    el Portal) y el bloque común v8 lo sigue diciendo."""
    text = _read(NEW)
    section = _section(text, SECTION, "MOTIVOS DE DESCARTE")
    assert ("completar la cotización en el formulario del Portal, renglón por renglón, sigue siendo "
            "forma_presentacion_portal") in section
    assert "La nota de una planilla de un anexo del pliego no es esa cláusula." in section
    portal = [q for q, a in _pairs(text) if a["descarte"] == "forma_presentacion_portal"]
    assert len(portal) == 2
    assert any("sistema de compras electrónicas" in q and "renglón por renglón" in q for q in portal)
    note = next(line for line in text.splitlines()
                if line.startswith("Tramo (") and "sistema de compras electrónicas" in line
                and "renglón por renglón" in line)
    assert "solo dice dónde se cargan los precios, y eso es forma_presentacion_portal" in note
    assert "no fija la moneda ni lo que se informa" in note
    block = _read("matriz-definiciones-v8")
    assert "Tampoco es una fila propia completar la cotización en el formulario del Portal" in block


def test_v12_keeps_the_currency_of_the_quote_even_if_the_sentence_mentions_the_portal():
    """REQ-102 (decisión del 2026-10-10: «la moneda de la oferta si es un requisito»): la oración que
    fija la moneda en que se cotiza o el tipo de cambio con que se convierte un precio es un
    requisito aunque diga que es para completar o cargar la cotización en el Portal; lo dicen la
    sección y el motivo `forma_presentacion_portal`, que también deja afuera de ese motivo la nota de
    una planilla de un anexo. La cláusula del formulario del Portal solo dice dónde y cómo se carga."""
    text = _read(NEW)
    section = _section(text, SECTION, "MOTIVOS DE DESCARTE")
    assert "Esa cláusula solo dice dónde y cómo se carga la cotización." in section
    assert ("Tampoco lo es la oración que fija la moneda en que se cotiza o el tipo de cambio con que "
            "se convierte un precio, aunque diga que es para completar o cargar la cotización en el "
            "Portal: la moneda de la cotización es un requisito") in section
    motive = _motive(text, "forma_presentacion_portal")
    assert ("Tampoco es la oración que fija la moneda en que se cotiza o el tipo de cambio con que se "
            "convierte un precio") in motive
    assert "ni la nota de una planilla de un anexo que le exige algo al oferente" in motive
    assert "La moneda en que se cotiza" not in _section(_read(PREVIOUS), "LA PRESENTACIÓN FÍSICA",
                                                       "MOTIVOS DE DESCARTE")


def test_v12_changes_only_what_t265_says():
    """REQ-106 (versiones congeladas, P7): de la v11 a la v12 cambian solo los motivos `formulario` y
    `forma_presentacion_portal` y la nota del ejemplo del sistema de compras; se suman la sección de
    los anexos y los dos ejemplos. Nada más se toca."""
    new = Counter(line for line in _read(NEW).splitlines() if line)
    old = Counter(line for line in _read(PREVIOUS).splitlines() if line)
    removed, added = list((old - new).elements()), list((new - old).elements())
    assert len(removed) == 3
    assert sum(line.startswith("- formulario:") for line in removed) == 1
    assert sum(line.startswith("- forma_presentacion_portal:") for line in removed) == 1
    assert sum(line.startswith("Tramo (solo dice cómo se completa algo en el sistema")
               for line in removed) == 1
    # La sección (título y dos párrafos), los dos motivos, la nota del ejemplo del sistema de compras
    # y los dos ejemplos nuevos (tramo y respuesta de cada uno).
    assert len(added) == 10
    assert SECTION in added
    assert sum(line.startswith("- formulario:") for line in added) == 1
    assert sum(line.startswith("- forma_presentacion_portal:") for line in added) == 1
    assert sum(line.startswith("Tramo (") for line in added) == 3
    assert sum(line.startswith('{"requisitos"') for line in added) == 2


# --- Generalidad: los ejemplos nuevos son inventados -------------------------------------------------


def _added(name, previous):
    old = set(_read(previous).splitlines())
    return [line for line in _read(name).splitlines() if line and line not in old]


@pytest.mark.parametrize("term", [
    r"sueldo", r"salari", r"operari", r"viátic", r"mano de obra", r"impuesto", r"porcentaje",
    r"precio unitario", r"costo directo", r"gastos generales", r"previsi", r"iva", r"iibb",
    r"componente", r"estructura de costos",
    # Los de T-262 (`test_ronda_t262.py`): la presentación física, la oferta económica por el
    # formulario del Portal y la póliza de los casos.
    r"mesa de entrada", r"requiere presentar", r"presentarse físicamente",
    r"adjuntar electrónicamente", r"portal de compras", r"detalle de renglones",
    r"a través del formulario", r"póliza", r"pagaré", r"pesos argentinos", r"administrador",
])
def test_what_v12_adds_does_not_paraphrase_the_cost_breakdown_of_a_measurement_case(term):
    """REQ-106 (ADR-0059, conjunto de validación; P4, P7): lo que suma la v12 (la sección, el motivo
    y los dos ejemplos) es de otro rubro y de otra redacción: no usa el vocabulario de una planilla de
    costos de servicios de los casos de medición (sueldos, operarios, cargas, impuestos) ni repite
    los términos que T-262 ya sacó de sus ejemplos."""
    pattern = re.compile(rf"\b{term}", re.IGNORECASE)
    for line in _added(NEW, PREVIOUS):
        assert not pattern.search(line), (term, line[:60])


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


def test_what_v12_adds_repeats_no_five_words_of_the_case_files():
    """REQ-106 (generalidad, P4): lo que agrega la v12 no repite cinco palabras seguidas de las
    listas esperadas de los casos 00 a 06 (incluidas las re-ancladas). Se saltea si `corpus/casos/`
    no está montado: la comprobación con huellas está en `test_definitions.py`."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno")
    known = set()
    for path in files:
        for anchor in _anchors(yaml.safe_load(path.read_text(encoding="utf-8"))):
            known |= _shingles(anchor)
    assert len(known) > 100
    hits = sorted((_shingles(_read(NEW)) - _shingles(_read(PREVIOUS))) & known)
    assert not hits, [hashlib.sha256(h.encode()).hexdigest()[:12] for h in hits]


# --- El filtro v9: el mismo criterio en las dos preguntas --------------------------------------------
#
# La comprobación con el modelo de T-265 mostró que, con las filas de la nota, la pregunta B del
# filtro v8 respondía «no» donde la v7 respondía «sí» (y la A descartaba la primera como
# `formulario`): el mismo contraste del formulario del Portal. Sin ese ejemplo, B volvía a «sí».

FILTER, FILTER_PREVIOUS = "matriz-filtro-v9", "matriz-filtro-v8"


def _filter_pairs(text, answer):
    """`[(fila, respuesta)]` de los ejemplos del filtro: el texto entre comillas que sigue a
    «Fila: » y la respuesta JSON de la línea siguiente."""
    lines = text.splitlines()
    return [(line[len('Fila: "'):].split('"')[0], json.loads(lines[n + 1]))
            for n, line in enumerate(lines[:-1])
            if line.startswith('Fila: "') and lines[n + 1].startswith(answer)]


def _questions(name):
    first, second = _read(name).split("# PREGUNTA B")
    return (_filter_pairs(first, '{"razonamiento"'), _filter_pairs(second, '{"razonamiento"'))


def test_the_active_filter_is_v9_and_v8_stays_published():
    """REQ-106, P6: T-265 publica el filtro v9 y lo registra como vigente; la v8 sigue publicada
    (congelada). Cada pedido del filtro registra la versión v9, la huella de su archivo y la del
    bloque v8."""
    # T-280: la vigente pasa a la v10; la v9 y la v8 siguen publicadas (congeladas).
    assert settings.MATRIX_PROMPT_VERSIONS["filtro"] == "matriz-filtro-v11"
    assert (PROMPTS / f"{FILTER}.md").is_file() and (PROMPTS / f"{FILTER_PREVIOUS}.md").is_file()
    record = extraction.load_instruction("filtro").record
    assert record["version"] == "matriz-filtro-v11"
    assert record["sha256"] == extraction.text_sha256(_read("matriz-filtro-v11"))
    assert record["definiciones"]["version"] == "matriz-definiciones-v10"  # T-285


def test_the_filter_v9_says_the_note_that_obliges_is_not_a_form_nor_the_portal_form():
    """REQ-102 (D-263-1): un sexto cuidado, común a las dos preguntas, dice que la nota o la
    instrucción de un anexo que obliga es un requisito; que el formulario es solo la planilla en
    blanco o el texto modelo; que la forma de presentar por el Portal es solo dónde y cómo se carga
    algo en el sistema; y que la moneda o el tipo de cambio de la cotización es un requisito. Lo
    repiten los motivos de A y las listas de «si» y «no» de B; los cinco cuidados de antes (el
    quinto es la presentación física de T-262) siguen igual."""
    text, old = _read(FILTER), _read(FILTER_PREVIOUS)
    common = text.split("CÓMO VIENEN LOS DATOS")[0]
    assert "Seis cuidados:" in common
    cautions = [line for line in common.split("Seis cuidados:")[1].splitlines()
                if line.startswith("- ")]
    old_common = old.split("CÓMO VIENEN LOS DATOS")[0]
    old_cautions = [line for line in old_common.split("Cinco cuidados:")[1].splitlines()
                    if line.startswith("- ")]
    assert len(cautions) == 6 and cautions[:5] == old_cautions
    for phrase in ("La nota o la instrucción de un anexo que le exige algo al oferente",
                   "no es el texto de un formulario ni la forma de presentar la oferta por el Portal",
                   "El formulario es solo la planilla en blanco o el texto modelo",
                   "es solo dónde y cómo se carga algo en el sistema",
                   "fija la moneda en que se cotiza o el tipo de cambio"):
        assert phrase in cautions[-1], phrase
    form = next(line for line in text.splitlines() if line.startswith('  - "formulario":'))
    assert "la planilla en blanco o el texto modelo" in form
    assert "ni la nota o la instrucción que le exige algo sobre lo que informa" in form
    portal = next(line for line in text.splitlines()
                  if line.startswith('  - "forma_presentacion_portal":'))
    assert "la que fija la moneda o el tipo de cambio de la cotización" in portal
    assert "ni la nota de una planilla que le exige algo al oferente" in portal
    yes = next(line for line in text.splitlines() if line.startswith('  - "si":'))
    no = next(line for line in text.splitlines() if line.startswith('  - "no":'))
    assert "la nota o la instrucción de un anexo que le exige algo al oferente" in yes
    assert "ni la moneda o el tipo de cambio de la cotización, que son requisitos" in no
    assert "texto modelo de un formulario (no la nota que le exige algo al oferente" in no


def test_the_filter_v9_examples_keep_the_note_and_discard_the_blank_form_in_both_questions():
    """REQ-102, REQ-106: en A, la nota de la planilla de un anexo se mantiene y la planilla en
    blanco se descarta como `formulario`, después del contraste del Portal; en B, «si» y «no». Los
    ejemplos siguen balanceados (A 13 y 13 más una duda, B 7 y 7 más una duda), ningún «descartar» ni
    «no» es una nota, y el contraste del Portal sigue descartándose con su motivo."""
    a, b = _questions(FILTER)
    note_a = [(q, r) for q, r in a if q.startswith("Nota:")]
    form_a = [(q, r) for q, r in a if " | " in q]
    assert [r["decision"] for _, r in note_a] == ["mantener"]
    assert [(r["decision"], r["motivo"]) for _, r in form_a] == [("descartar", "formulario")]
    assert form_a[0][1]["indicio"] in form_a[0][0]
    note_b = [r["respuesta"] for q, r in b if q.startswith("Nota:")]
    form_b = [r["respuesta"] for q, r in b if " | " in q]
    assert note_b == ["si"] and form_b == ["no"]
    for question, answer in a:
        if answer["decision"] == "descartar":
            assert not question.startswith("Nota:"), question
    for question, answer in b:
        if answer["respuesta"] == "no":
            assert not question.startswith("Nota:"), question
    at = [q for q, _ in a].index(note_a[0][0])
    assert a[at - 1][0] == form_a[0][0] and a[at - 2][1]["motivo"] == "forma_presentacion_portal"
    assert "Solo dice dónde se cargan los precios" in a[at - 2][1]["razonamiento"]
    decisions = [r["decision"] for _, r in a]
    assert decisions.count("mantener") == decisions.count("descartar") == 13
    assert decisions.count("duda") == 1
    answers = [r["respuesta"] for _, r in b]
    assert answers.count("si") == answers.count("no") == 7 and answers.count("duda") == 1


def test_the_filter_v9_keeps_the_physical_presentation_of_t262():
    """REQ-102 (decisión del 2026-10-12): la entrega en papel sigue manteniéndose en A y siendo
    «si» en B, ningún «descartar» ni «no» pide algo en papel, y la cotización que solo se carga en
    el sistema sigue descartándose."""
    a, b = _questions(FILTER)
    for question, answer in a:
        if answer["decision"] == "descartar":
            assert not PAPER.search(question), question
    for question, answer in b:
        if answer["respuesta"] == "no":
            assert not PAPER.search(question), question
    assert any(PAPER.search(q) and r["decision"] == "mantener" for q, r in a)
    assert any(PAPER.search(q) and r["respuesta"] == "si" for q, r in b)
    assert any("sistema de compras electrónicas" in q and r["motivo"] == "forma_presentacion_portal"
               for q, r in a)
    assert any("sistema de compras electrónicas" in q and r["respuesta"] == "no" for q, r in b)


def test_the_filter_v9_changes_only_what_t265_says():
    """REQ-106 (versiones congeladas, P7): de la v8 a la v9 cambian el título de los cuidados, los
    motivos `formulario` y `forma_presentacion_portal`, las listas de «si» y «no» y el razonamiento
    de los dos contrastes del Portal; se suman el sexto cuidado y dos ejemplos en cada pregunta."""
    new = Counter(line for line in _read(FILTER).splitlines() if line)
    old = Counter(line for line in _read(FILTER_PREVIOUS).splitlines() if line)
    removed, added = list((old - new).elements()), list((new - old).elements())
    assert len(removed) == 7 and len(added) == 16
    assert "Cinco cuidados:" in removed and "Seis cuidados:" in added
    assert sum(line.startswith("Fila: ") for line in added) == 4
    assert sum(line.startswith('{"razonamiento"') for line in added) == 6


@pytest.mark.parametrize("term", [
    r"sueldo", r"salari", r"operari", r"viátic", r"mano de obra", r"impuesto", r"porcentaje",
    r"precio unitario", r"costo directo", r"gastos generales", r"previsi", r"iva", r"iibb",
    r"componente", r"estructura de costos", r"mesa de entrada", r"requiere presentar",
    r"presentarse físicamente", r"adjuntar electrónicamente", r"portal de compras",
    r"detalle de renglones", r"a través del formulario", r"póliza", r"pagaré", r"pesos argentinos",
    r"administrador",
])
def test_what_the_filter_v9_adds_does_not_paraphrase_a_measurement_case(term):
    """REQ-106 (ADR-0059, conjunto de validación; P4, P7): lo que suma el filtro v9 es de otro
    rubro y de otra redacción, con el mismo control que la extracción v12."""
    pattern = re.compile(rf"\b{term}", re.IGNORECASE)
    for line in _added(FILTER, FILTER_PREVIOUS):
        assert not pattern.search(line), (term, line[:60])


def test_what_the_filter_v9_adds_repeats_no_five_words_of_the_case_files():
    """REQ-106 (generalidad, P4): lo que agrega el filtro v9 no repite cinco palabras seguidas de
    las listas esperadas de los casos 00 a 06. Se saltea si `corpus/casos/` no está montado."""
    files = sorted(CASES.glob("*/esperado/*.yaml")) if CASES.is_dir() else []
    if not files:
        pytest.skip("corpus/casos/ no está montado en este entorno")
    known = set()
    for path in files:
        for anchor in _anchors(yaml.safe_load(path.read_text(encoding="utf-8"))):
            known |= _shingles(anchor)
    assert len(known) > 100
    hits = sorted((_shingles(_read(FILTER)) - _shingles(_read(FILTER_PREVIOUS))) & known)
    assert not hits, [hashlib.sha256(h.encode()).hexdigest()[:12] for h in hits]
