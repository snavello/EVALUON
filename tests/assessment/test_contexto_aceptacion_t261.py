"""Pruebas de aceptación de T-261 (D-260-1; REQ-104, P3, P6), escritas por el testeador
evaluador desde la fila de la tarea y el encargo, antes de leer los tests del desarrollador.

Textos inventados (P4). El motor es el doble de `tests/assessment/fakes.py` (una palabra, un
token) envuelto por el fixture `engine` de `test_contexto_t261.py`, que rechaza como
`llama-server` un pedido cuyos mensajes pasan del contexto.
"""

import pytest

from evaluon.assessment import prompting, sizing
from evaluon.assessment.services import evaluate
from evaluon.audit.models import AuditEvent, EventType
from tests.assessment.fakes import model, says  # noqa: F401
from tests.assessment.test_contexto_t261 import context_for, engine  # noqa: F401
from tests.assessment.test_evaluate import number_of, results_of, run_all, sheets_firm, words
from tests.offers.conftest import (  # noqa: F401 - fixtures de la 008 y la 003
    evaluator_user,
    expected,
    make_offer,
    matrix,
    offer,
    operator_user,
    procedure,
)

pytestmark = pytest.mark.django_db

VALIDITY = "La oferta mantiene su validez por sesenta días corridos."


def _readings_for(model, needle):
    return [c for c in model.calls if needle in c.requirement]


def test_aceptacion_tres_particiones_como_maximo_y_la_oferta_sigue(
        procedure, operator_user, model, engine, settings):
    """REQ-104 (T-261), caso extremo inventado: un grupo cuyo pedido el motor rechaza siempre se
    parte en dos hasta 3 veces (1 + 2 + 4 + 8 = 15 pedidos rechazados, ninguno más); las 8 partes
    finales quedan «no determinado» por lectura incompleta con `pedido_fuera_de_contexto`, la
    evaluación termina (`eval_build` ok) y los demás requisitos se evalúan (P6: anomalías con el
    tope, el contexto y la salida)."""
    pages = {f"anexo-{n:02d}.pdf": [f"Anexo {n}. {words(20, f'z{n}-')}"] for n in range(1, 17)}
    pages["validez.pdf"] = [VALIDITY]
    offer = make_offer(procedure, operator_user, "Oferente de dieciocho piezas", pages)
    engine.reject = lambda messages, schema: ("condiciones" in schema["properties"]
                                              and "declaración jurada" in messages[1]["content"])
    model.evaluates(lambda call: says("cumple", call.quote(VALIDITY))
                    if "validez" in call.requirement and call.alias_with("sesenta días")
                    else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    number = number_of(procedure, "declaración jurada")
    assert engine.rejected == 15
    splits = [a for a in run.anomalies
              if a["type"] == evaluate.ANOMALY_SPLIT and a["requirement"] == number]
    assert sorted(a["splits"] for a in splits) == [0, 1, 1, 2, 2, 2, 2]
    final = [a for a in run.anomalies if a["type"] == evaluate.ANOMALY_TOO_LONG
             and a["requirement"] == number and "splits" in a]
    assert len(final) == 8 and all(a["splits"] == sizing.MAX_SPLITS for a in final)
    assert all({"budget", "context", "output", "documents"} <= set(a) for a in final)
    results = results_of(run)
    assert len(results) == len(sheets_firm(procedure))
    assert results[number].outcome == "no_determinado"
    assert results[number].doubt == "lectura_incompleta"
    assert evaluate.TOO_LONG_NOTE in results[number].explanation
    validity = results[number_of(procedure, "sesenta días")]
    assert validity.outcome == "cumple"
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_BUILD, outcome="ok").count() == 1
    assert str(number) in run.counts["group_budgets"]
    assert run.parameters["max_splits"] == sizing.MAX_SPLITS


def test_aceptacion_el_reintento_que_no_entra_no_se_manda(
        offer, operator_user, procedure, model, engine, settings):
    """REQ-104, P6 (T-261): el primer pedido entra, pero su salida trae una cita que no se ubica y
    el reintento (que suma la salida anterior y la corrección) no entra en el contexto: el
    reintento no se manda, queda la anomalía `reintento_fuera_de_contexto` y el requisito queda
    con lo del primer pedido («no determinado», sin «cumple» sin cita: P3)."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = context_for(1_500)
    long_explanation = words(3_000, "e")
    model.evaluates(lambda call: says(
        "cumple", ("D1", "Esta oración no figura en ningún documento de la oferta"),
        explanation=long_explanation) if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    number = number_of(procedure, "declaración jurada")
    assert len(_readings_for(model, "declaración jurada")) == 1
    assert engine.rejected == 0
    retry = [a for a in run.anomalies
             if a["type"] == evaluate.ANOMALY_RETRY_TOO_LONG and a["requirement"] == number]
    assert len(retry) == 1
    assert retry[0]["tokens"] + retry[0]["output"] > retry[0]["context"]
    result = results_of(run)[number]
    assert result.outcome == "no_determinado"
    assert run.steps.filter(requirement__number=number, purpose="grupo").count() == 1
    assert len(results_of(run)) == len(sheets_firm(procedure))


def test_aceptacion_parte_sin_leer_por_contexto_no_afirma_que_falta_el_documento(
        procedure, operator_user, model, engine, settings):
    """P3, REQ-104 (T-261): con una parte de la oferta que no entra ni partida, el «no consta» de
    las partes leídas no se convierte en «no se encontró el documento» ni en «no cumple»: el
    sistema no afirma la ausencia sin la lectura completa."""
    settings.GENERATION_BATCH_CONTEXT_TOKENS = context_for(3_000)
    offer = make_offer(procedure, operator_user, "Oferente con planilla enorme", {
        "nota.pdf": [f"Nota de presentación. {words(40, 'n')}"],
        "planilla.pdf": [f"Planilla. {words(7_000, 'p')}"]})
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    assert engine.rejected == 0
    results = results_of(run)
    assert len(results) == len(sheets_firm(procedure))
    assert all(r.outcome == "no_determinado" for r in results.values())
    # Las filas técnicas esperan el informe del área (regla técnica); las demás, la lectura.
    assert all(r.doubt in ("lectura_incompleta", "pendiente_informe_tecnico")
               for r in results.values())
    assert any(r.doubt == "lectura_incompleta" for r in results.values())
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_BUILD, outcome="ok").count() == 1


def test_aceptacion_contraste_rechazado_queda_sin_corroborar_y_registrado(
        offer, operator_user, procedure, model, engine):
    """REQ-104, P6 (T-261): un contraste que el motor rechaza por el contexto deja el «cumple»
    sin corroborar (nunca «cumple»), registra el pedido que no salió con su anomalía y la oferta
    termina con todos sus requisitos."""
    engine.reject = lambda messages, schema: "respuesta" in schema["properties"]
    model.evaluates(lambda call: says("cumple", call.quote(VALIDITY))
                    if "validez" in call.requirement and call.alias_with("sesenta días")
                    else None)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    run = runs[0]
    number = number_of(procedure, "sesenta días")
    result = results_of(run)[number]
    assert result.outcome == "no_determinado" and result.doubt == "sin_corroborar"
    contrast = run.steps.filter(requirement__number=number, purpose="contraste")
    assert contrast.count() == 1
    step = contrast.get()
    assert step.request and not step.raw_output
    assert step.anomalies[0]["type"] == evaluate.ANOMALY_TOO_LONG
    assert len(results_of(run)) == len(sheets_firm(procedure))
    assert prompting  # el módulo de instrucciones queda importado para el registro
