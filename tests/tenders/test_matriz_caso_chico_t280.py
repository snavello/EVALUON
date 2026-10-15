"""La matriz completa del caso chico con las instrucciones de T-279 y T-280 y los dobles (REQ-119;
plan 016, «Paso 2» y «Corte vertical»; ADR-0070).

Extiende `test_matriz_caso_chico_t279.py` a las pasadas que T-280 reescribe: el filtro (las dos
preguntas), las consecuencias, las circulares (los efectos de un tramo y los cambios de una unidad)
y el respaldo normativo de una sugerencia. El caso chico (`tests/assessment/data/caso-chico/`) es
inventado y público; la circular de la prueba también. La prueba no mide la calidad (eso es de T-283,
con el modelo real): comprueba que la propuesta corre de punta a punta con las versiones vigentes, que
cada pedido de cada pasada lleva el texto vigente de su instrucción (con el bloque v9 donde tiene la
marca) y registra su versión y su huella (P6), y que las filas que salen citan el pliego letra por
letra.
"""

from datetime import date

import pytest
from django.conf import settings

from evaluon.tenders import models as m
from evaluon.tenders.proposal import extraction, norm_support
from evaluon.tenders.proposal import filter as row_filter
from tests.assessment.fakes import CASO_CHICO
from tests.tenders.scripted import item, load_and_read, make_procedure, propose
from tests.tenders.test_circulars import add_circular
from tests.tenders.test_consequences import marks, regimes  # noqa: F401  (fixtures)
from tests.tenders.test_filter import KEEP, filt, script  # noqa: F401  (fixtures y ayudas)
from tests.tenders.test_norm_support import corpus, support  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db

T280 = {"filtro": "matriz-filtro-v10", "consecuencias": "matriz-consecuencias-v3",
        "circulares": "matriz-circulares-v8", "circulares_cambios": "matriz-circulares-cambios-v7",
        "respaldo": "matriz-respaldo-v3"}
# La pasada de cada pedido y la instrucción que usa.
PASSES = {"filtro": "filtro", "filtro_2": "filtro", "consecuencias": "consecuencias",
          "circulares": "circulares", "circulares_cambios": "circulares_cambios",
          "respaldo_normativo": "respaldo"}
# Palabras de una oración del pliego del caso chico (inventado) que el filtro deja en duda
# (sugerencia, con su respaldo), y la cita que nombra la circular de la prueba (inventada).
DOUBT_WORDS = "documento de identidad"
CIRCULAR_TARGET = "Presentar la declaración jurada de habilidad para contratar"
CIRCULAR_SENTENCE = ("La declaración jurada de habilidad para contratar se presentará con la firma "
                     "del apoderado.")


def _first_line(text):
    return next(line.strip() for line in text.splitlines() if line.strip())


def _messages(step):
    request = step.request
    return request.get("messages") or request.get("request", {}).get("messages")


def test_the_small_case_proposes_its_whole_matrix_with_the_t280_instructions(
        operator_user, script, filt, support, regimes, marks, corpus,  # noqa: F811
        monkeypatch):
    """REQ-119: el caso chico, con una circular inventada, propone su matriz completa con los dobles;
    el filtro, las consecuencias, las circulares, los cambios de circulares y el respaldo corren con
    las versiones de T-280, y cada pedido lleva su instrucción vigente y su registro."""
    # Las normas de prueba de la 001 tienen artículos de dos palabras (como en test_norm_support).
    monkeypatch.setattr(norm_support, "MIN_CITE_WORDS", 1)
    procedure = make_procedure(operator_user, date(2023, 1, 2))
    document = load_and_read(operator_user, procedure, (CASO_CHICO / "pliego.pdf").read_bytes(),
                             title="Pliego del caso chico")
    add_circular(operator_user, procedure, "Circular N.º 1", date(2023, 2, 1),
                 f"1. {CIRCULAR_SENTENCE}")
    # El doble propone, de cada tramo, su primera línea como requisito formal; el filtro mantiene
    # todo salvo la fila del documento de identidad, que queda en duda (sugerencia con respaldo);
    # la circular aclara la cita de la declaración jurada.
    script.override(lambda blocks, number, answer: {
        alias: item([(_first_line(block["text"]), "formal")]) for alias, block in blocks.items()})
    filt.when(DOUBT_WORDS, KEEP, "duda")
    script.c_when("firma del apoderado", efectos=[(CIRCULAR_TARGET, "aclara", CIRCULAR_SENTENCE)])
    support.says("Garantías sintéticas")

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert {name: run.prompt_versions[name] for name in T280} == T280
    for name, version in settings.MATRIX_PROMPT_VERSIONS.items():
        if name in run.prompt_versions:
            assert run.prompt_versions[name] == version, name
    for name in T280:
        assert run.prompt_versions["huellas"][name] == extraction.load_instruction(name).sha256

    first, second = row_filter.load_prompts()
    expected = {pass_name: extraction.load_prompt(name) for pass_name, name in PASSES.items()}
    expected.update({"filtro": first, "filtro_2": second})
    for pass_name, name in PASSES.items():
        steps = [step for step in m.RunStep.objects.filter(run=run, pass_name=pass_name)
                 if not step.request.get("sin_modelo")]
        assert steps, f"ningún pedido de {pass_name}"
        record = extraction.load_instruction(name).record
        for step in steps:
            assert step.parsed["instruccion"] == record, pass_name
            assert _messages(step)[0]["content"] == expected[pass_name], pass_name
    assert extraction.load_instruction("filtro").record["definiciones"]["version"] == (
        "matriz-definiciones-v9")
    for name in ("consecuencias", "circulares", "circulares_cambios", "respaldo"):
        assert "definiciones" not in extraction.load_instruction(name).record, name

    suggested = list(m.Requirement.objects.filter(version=run.version, state="sugerido"))
    assert len(suggested) == 1
    assert all(DOUBT_WORDS in quote.text for quote in suggested[0].quotes.all())
    assert m.NormSupport.objects.filter(requirement__version=run.version).exists()
    assert m.RequirementSource.objects.filter(requirement__version=run.version).exists()
    rows = m.Requirement.objects.filter(version=run.version, category__in=["formal", "economico"])
    assert rows.count() > 1
    canonical = document.readings.get().canonical_text
    for row in rows:
        for quote in row.quotes.all():
            assert quote.text == canonical[quote.char_start:quote.char_end]
