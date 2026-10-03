"""Instrucciones `consulta-v3`: remisión a una norma no cargada (T-063; plan 001,
"Generación", "Abstención", "Remisión a una norma no cargada"; ADR-0015).

La v3 suma a la v2 la regla de la remisión (responder lo que dice la unidad y a qué norma
remite, con su cita, sin dar el contenido de la norma remitida) y reescribe la de
abstención ("undetermined" solo si ninguna unidad trata el punto, ni siquiera para
remitirlo). El esquema y la validación no cambian.

Con los dobles de `tests/conftest.py`; los textos son sintéticos (P4). Estas pruebas no
comprueban qué hace el modelo con la v3: eso lo mide la corrida del conjunto dorado (P7).
"""

import hashlib
import json
from datetime import date

import pytest

from evaluon.queries import answering, services

pytestmark = pytest.mark.django_db

QUESTION = "¿Cuál es el plazo sintético para presentar la muestra?"
DATE = date(2024, 5, 20)

# Marca de texto que puntúa el doble del reranker.
REMISSION = "[articulo-remision]"
REMISSION_TEXT = (f"ARTICULO 9.- {REMISSION} La muestra sintética se presenta dentro del "
                  "plazo que fije la reglamentación sintética vigente.")

# Huellas SHA-256 de las versiones publicadas, con finales de línea LF, tal como están
# guardadas en el repositorio (`git show HEAD:evaluon/queries/prompts/<archivo> |
# sha256sum`). Una versión publicada no se modifica: un cambio es un archivo nuevo (P7).
PUBLISHED_SHA256 = {
    "consulta-v1": "ba732859c34958d2c95bdecbb9554c9b8c8e4b53b6149f05464b58a94df35131",
    "consulta-v2": "1fbb042027214abce2ff71bdf259eee94ccf74812b923095c78bb419fb33d734",
}


@pytest.fixture
def remission(make_norm, make_document, make_reading):
    """Un régimen específico con marca de régimen general y un artículo que remite su
    contenido a otra norma, no cargada."""
    norm = make_norm(category="regimen_especifico", general_regime=True)
    reading = make_reading(make_document(norm), [("art-9", REMISSION_TEXT)])
    return reading.units_by_key["art-9"]


@pytest.fixture
def scored(fake_ai, settings):
    """El artículo que remite queda muy por encima del umbral, que se fija acá para no
    depender del calibrado."""
    settings.RERANK_THRESHOLD = 0.219
    fake_ai.reranker.scores = {REMISSION: 0.9}
    return fake_ai


def literal(unit):
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def ask(user):
    return services.ask(user, QUESTION, DATE)


def test_v3_is_the_active_version_with_date():
    """REQ-008, REQ-009: con fecha, la versión activa de las instrucciones es
    `consulta-v3`; el camino sin fecha sigue con `consulta-v1`."""
    assert answering.PROMPT_VERSION_WITH_DATE == "consulta-v3"
    assert answering.PROMPT_VERSION_WITHOUT_DATE == "consulta-v1"
    assert answering.load_instructions() == answering.load_instructions("consulta-v3")


def test_request_carries_v3_as_system_message_and_query_records_it(read_user, remission,
                                                                    scored):
    """REQ-008, REQ-009, REQ-012: con fecha, el pedido al modelo lleva la v3 como mensaje
    de sistema y la consulta registra `prompt_version` "consulta-v3"."""
    query = ask(read_user)

    [(messages, _)] = scored.generation.calls
    assert messages[0] == {"role": "system",
                           "content": answering.load_instructions("consulta-v3")}
    assert query.prompt_version == "consulta-v3"
    assert query.request["messages"][0]["content"] == \
        answering.load_instructions("consulta-v3")


def test_v3_has_the_remission_rule_and_the_rewritten_abstention_rule():
    """REQ-009: la v3 trae la regla de la remisión (responder lo que dice la unidad y a
    qué norma remite, citándola, sin dar el contenido de la norma remitida aunque el
    modelo crea conocerlo) antes de la regla de abstención, y la abstención reescrita:
    "undetermined" solo si ninguna unidad trata el punto, ni siquiera para remitirlo. La
    regla vieja de la v2 ya no está."""
    v3 = answering.load_instructions("consulta-v3")

    remission_rule = v3.index("remite su contenido a otra norma")
    abstention_rule = v3.index("ninguna unidad trata el punto de la pregunta")
    assert remission_rule < abstention_rule
    for phrase in ("respondé lo que dice la unidad y a qué norma remite",
                   "No des el contenido de la norma remitida",
                   "aunque creas conocerlo",
                   "ni siquiera para remitirlo a otra norma"):
        assert phrase in v3, phrase
    assert "Si las unidades no permiten responder la pregunta, no respondas" not in v3


def test_v3_keeps_rules_1_to_9_and_the_output_format_of_v2():
    """REQ-008, REQ-018, REQ-019: fuera de la remisión y la abstención, la v3 conserva
    las reglas 1 a 9 de la v2, palabra por palabra, y el formato de la salida."""
    v2 = answering.load_instructions("consulta-v2")
    v3 = answering.load_instructions("consulta-v3")
    rules_v2 = v2.split("QUÉ TENÉS QUE HACER", 1)[1].split("\n10. ", 1)[0]
    assert rules_v2 in v3
    for line in ('- "text": la afirmación.',
                 '- "regimes_differ": true solo si la afirmación dice que el régimen '
                 'específico y el marco nacional tratan el punto de manera distinta y '
                 'cita a los dos; si no, false.'):
        assert line in v3


def test_v3_example_of_a_remission_is_not_a_question_of_the_set():
    """REQ-009: la v3 trae un ejemplo de la forma con una remisión, con un texto
    ilustrativo que no repite una pregunta del conjunto (ni montos, ni la Comisión
    Evaluadora) y que cumple la forma de la salida."""
    v3 = answering.load_instructions("consulta-v3")
    examples = [json.loads(line) for line in v3.splitlines() if line.startswith("{")]
    remissions = [e for e in examples
                  if e["status"] == "grounded"
                  and any("reglamentación" in s["text"] for s in e["statements"])]
    assert len(remissions) == 1
    text = remissions[0]["statements"][0]["text"].lower()
    for word in ("monto", "comisión", "jurisdiccional", "contratación directa",
                 "licitación privada"):
        assert word not in text, word


def test_v3_schema_asks_for_regimes_differ():
    """REQ-019: el esquema de la v3 pide `regimes_differ` en cada afirmación, como el de
    la v2."""
    schema = answering.build_schema(["U1"], version="consulta-v3")

    item = schema["properties"]["statements"]["items"]
    assert "regimes_differ" in item["required"]
    assert item["properties"]["regimes_differ"] == {"type": "boolean"}
    assert schema == answering.build_schema(["U1"], version="consulta-v2")


def test_remission_with_its_citation_is_grounded_with_the_literal_text(read_user,
                                                                       remission,
                                                                       scored):
    """REQ-009, REQ-008: un doble que devuelve una remisión con su cita da `grounded`; la
    cita es la unidad que remite y su texto literal lo inserta el sistema desde la base,
    no la salida del modelo."""
    scored.generation.answer([
        {"text": "La muestra se presenta en el plazo que fije la reglamentación vigente.",
         "citations": ["U1"], "regimes_differ": False},
    ])

    query = ask(read_user)

    result = query.result
    assert result["status"] == "grounded"
    assert result["reason"] is None
    assert result["statements"] == [
        {"text": "La muestra se presenta en el plazo que fije la reglamentación vigente.",
         "regimes_differ": False, "citations": [remission.pk]},
    ]
    assert answering.citation_texts(result) == {remission.pk: literal(remission)}
    assert literal(remission) == REMISSION_TEXT
    assert REMISSION_TEXT not in json.dumps(result, ensure_ascii=False)


def test_undetermined_from_the_model_is_still_model_abstained(read_user, remission,
                                                              scored):
    """REQ-009: con la v3, un doble que devuelve `undetermined` sigue dando "no
    determinado" con el motivo `model_abstained`, sin afirmaciones."""
    scored.generation.abstain()

    query = ask(read_user)

    assert query.prompt_version == "consulta-v3"
    assert query.result["status"] == "undetermined"
    assert query.result["reason"] == "model_abstained"
    assert query.result["statements"] == []


@pytest.mark.parametrize("version", sorted(PUBLISHED_SHA256))
def test_published_versions_do_not_change(version):
    """REQ-008: la v3 se creó sin modificar las versiones publicadas: la huella de
    `consulta-v1.txt` y la de `consulta-v2.txt` quedan fijas (P7). Se calcula sobre los
    bytes con `\\r\\n` normalizado a `\\n`, como lee `load_instructions`."""
    raw = (answering.PROMPTS_DIR / f"{version}.txt").read_bytes()

    normalized = raw.replace(b"\r\n", b"\n")

    assert hashlib.sha256(normalized).hexdigest() == PUBLISHED_SHA256[version]
