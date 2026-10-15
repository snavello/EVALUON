"""La matriz del caso chico con las instrucciones de T-279 y el doble de generación (REQ-119; plan
016, «Paso 2» y «Corte vertical»; ADR-0070).

El caso chico (`tests/assessment/data/caso-chico/`) es inventado y público. La prueba no mide la
calidad (eso es de T-283, con el modelo real): comprueba que la propuesta corre de punta a punta
con el bloque de definiciones v9, la extracción v13, la completitud v7 y la unión v2, que cada
pedido lleva el texto vigente con el bloque adentro y registra su versión y su huella (P6), y que
las filas que salen citan el pliego letra por letra.
"""

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import extraction
from tests.assessment.fakes import CASO_CHICO
from tests.tenders.scripted import item, load_and_read, make_procedure, propose, script  # noqa: F401

pytestmark = pytest.mark.django_db

T279 = {"definiciones": "matriz-definiciones-v9", "extraccion": "matriz-extraccion-v13",
        "completitud": "matriz-completitud-v7", "union": "matriz-union-v2"}


def _first_line(text):
    return next(line.strip() for line in text.splitlines() if line.strip())


def test_the_small_case_proposes_its_matrix_with_the_t279_instructions(operator_user, script):
    """REQ-119: el caso chico propone su matriz con el doble de generación y las instrucciones de
    T-279; cada pedido de la extracción, la completitud y la unión lleva la instrucción vigente
    (con el bloque v9 donde tiene la marca) y su registro; las filas citan el pliego."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, (CASO_CHICO / "pliego.pdf").read_bytes(),
                             title="Pliego del caso chico")
    # El doble propone, de cada tramo, su primera línea como requisito formal; dos filas seguidas
    # del mismo tramo, si las hay, quedan en dos (la respuesta por omisión de la unión).
    script.override(lambda blocks, number, answer: {
        alias: item([(_first_line(block["text"]), "formal")]) for alias, block in blocks.items()})

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert {name: run.prompt_versions[name] for name in T279} == T279
    for name in ("extraccion", "completitud", "union"):
        instruction = extraction.load_instruction(name)
        assert extraction.DEFINITIONS_MARK not in instruction.text
        assert instruction.definitions[0] == T279["definiciones"]
        assert run.prompt_versions["huellas"][name] == instruction.sha256

    steps = list(m.RunStep.objects.filter(run=run, pass_name="extraccion"))
    assert steps
    for step in steps:
        assert step.request["messages"][0]["content"] == extraction.load_prompt("extraccion")
        assert step.parsed["instruccion"] == extraction.load_instruction("extraccion").record
    for messages in script.completeness_default_calls:
        assert messages[0]["content"] == extraction.load_prompt("completitud")
    for messages in script.join_calls:
        assert messages[0]["content"] == extraction.load_prompt("union")

    rows = m.Requirement.objects.filter(version=run.version, category__in=["formal", "economico"])
    assert rows.exists()
    canonical = document.readings.get().canonical_text
    for row in rows:
        for quote in row.quotes.all():
            assert quote.text == canonical[quote.char_start:quote.char_end]
