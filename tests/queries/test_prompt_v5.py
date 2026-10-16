"""Instrucciones `consulta-v5`: la consulta con solo las definiciones y decisiones vigentes (T-282;
REQ-119 de la 016; REQ-008, REQ-009, REQ-018 a REQ-020 de la 001; ADR-0002, ADR-0015, ADR-0070).

La v5 reemplaza a la v4 con una instrucción corta y sin ejemplos: conserva lo que piden el ADR-0002
y la 001 (señalar la unidad y no copiar su texto, que inserta el sistema; abstenerse cuando ninguna
unidad trata el punto; responder la remisión sin dar el contenido de la norma remitida; el papel de
cada categoría; el texto vigente a la fecha; los regímenes que difieren) y el esqueleto de la salida
con las afirmaciones antes que el estado. El aviso de modificatorias sin cargar (REQ-021) no es de la
instrucción: lo arma `services.py` y el modelo no lo recibe ni lo redacta. Las versiones publicadas,
también la `consulta-v1` del camino sin fecha, no cambian.

P6: cada consulta registra, junto a `prompt_version`, el nombre, la versión y la huella de la
instrucción (`parameters["instruccion"]`, también en el hecho `query`).

Con los dobles de `tests/conftest.py`; los textos son sintéticos (P4). Lo que hace el modelo con la
v5 lo mide el conjunto dorado de la 001 en T-283 (P7).
"""

import json
import re
from datetime import date

import pytest

from evaluon.audit.models import AuditEvent
from evaluon.queries import answering, services
from evaluon.tenders.proposal import extraction

QUESTION = "¿Cuál es el plazo sintético para presentar la muestra?"
DATE = date(2024, 5, 20)
MARK = "[articulo-v5]"
UNIT_TEXT = f"ARTICULO 4.- {MARK} La muestra sintética se presenta dentro de los cinco días."


def v5():
    return answering.load_instructions("consulta-v5")


def test_v5_is_the_active_version_with_date_and_v1_stays_without_date():
    """REQ-119, REQ-008: con fecha, la versión activa es `consulta-v5`; el camino sin fecha sigue
    con la `consulta-v1` publicada."""
    assert answering.PROMPT_VERSION_WITH_DATE == "consulta-v5"
    assert answering.PROMPT_VERSION_WITHOUT_DATE == "consulta-v1"
    assert answering.load_instructions() == v5()


def test_v5_keeps_what_adr_0002_and_the_001_ask_for():
    """REQ-008, REQ-009, REQ-018, REQ-019, REQ-020 (ADR-0002, ADR-0015): la v5 dice que se cita la
    unidad sin copiar su texto, que no se agrega nada que no esté en las unidades, el papel de cada
    categoría, el texto vigente a la fecha con la unidad que lo modifica, la marca de regímenes que
    difieren, la remisión sin el contenido de la norma remitida y la abstención."""
    text = v5()
    for phrase in ("No copies el texto de la norma",
                   "el sistema muestra el texto literal de cada unidad citada",
                   "No agregues nada que no esté en las unidades",
                   "Régimen específico: es lo que se aplica",
                   "Marco nacional: marco de referencia",
                   "criterio que acompaña",
                   "Considerando: contexto",
                   "con el cambio aplicado, y citá también la unidad que la modifica",
                   '"regimes_differ" en true',
                   "remite su contenido a otra norma",
                   "No des el contenido de la norma remitida",
                   'esa respuesta es "grounded"',
                   "ni siquiera para remitirlo a otra norma",
                   "es preferible no responder a responder sin sustento"):
        assert phrase in text, phrase


def test_v5_has_no_examples_and_its_skeleton_follows_the_schema():
    """REQ-119 (ADR-0070, punto 2): sin ejemplos; una sola línea JSON, el esqueleto, con las
    afirmaciones antes que el estado, que es el orden del esquema de la v5 (el mismo de la v4)."""
    text = v5()
    assert not re.search(r"(?im)^[\s#>*\-\d.)]*ejemplos?\b", text)
    [skeleton] = [line for line in text.splitlines() if line.startswith("{")]
    assert list(json.loads(skeleton.replace("grounded|undetermined", "grounded"))) == [
        "statements", "status"]
    schema = answering.build_schema(["U1"], version="consulta-v5")
    assert list(schema["properties"]) == ["statements", "status"]
    assert schema == answering.build_schema(["U1"], version="consulta-v4")
    assert "REQ-021" not in text and "modificatorias sin cargar" not in text


def test_the_prompt_record_is_the_name_version_and_sha256_of_the_file():
    """REQ-119, P6: `prompt_record` da el nombre, la versión y la huella (fines de línea LF) de la
    instrucción de esa versión; por omisión, la vigente con fecha."""
    record = answering.prompt_record()

    assert record == {"nombre": "consulta", "version": "consulta-v5",
                      "sha256": extraction.text_sha256(v5())}
    assert answering.prompt_record("consulta-v1")["sha256"] == extraction.text_sha256(
        answering.load_instructions("consulta-v1"))


@pytest.mark.django_db
def test_every_query_records_the_version_and_the_sha256_of_its_instruction(
        read_user, make_norm, make_document, make_reading, fake_ai, settings):
    """REQ-119, P6 (T-282): la consulta que llama al modelo guarda, junto a `prompt_version`, el
    nombre, la versión y la huella de la instrucción que lleva su pedido, en la fila y en el hecho
    `query`."""
    norm = make_norm(category="regimen_especifico", general_regime=True)
    make_reading(make_document(norm), [("art-4", UNIT_TEXT)])
    settings.RERANK_THRESHOLD = 0.219
    fake_ai.reranker.scores = {MARK: 0.9}

    query = services.ask(read_user, QUESTION, DATE)

    [(messages, _)] = fake_ai.generation.calls
    assert messages[0]["content"] == v5()
    assert query.prompt_version == "consulta-v5"
    assert query.parameters["instruccion"] == answering.prompt_record("consulta-v5")
    event = AuditEvent.objects.get(pk=query.event_id)
    assert event.detail["parameters"]["instruccion"] == query.parameters["instruccion"]
