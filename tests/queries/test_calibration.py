"""Calibración del umbral del reranker (T-042; plan 001, "Abstención", pasos 1 y 2;
decisión del Coordinador en la verificación de T-042).

El umbral propuesto es el más alto que, dejando cada vez una pregunta afuera, frena por
error a lo sumo el 5 % de las preguntas con respuesta: se elige la posición `k` más alta
de los puntajes ordenados cuya estimación dejando una afuera no pasa del 5 %, y el
umbral es el puntaje en esa posición del conjunto completo, redondeado hacia abajo. Se
informa también la regla anterior (`k = piso(5 % de n)` sin dejar ninguna afuera). El
valor es provisorio y no cambia `settings.py`; es uno solo para los dos regímenes y cada
pregunta se corre con su fecha.

Los puntajes son preparados a mano o salen de casos sintéticos (P4) respondidos con los
dobles de los clientes de IA.
"""

import pytest
from django.conf import settings

from evaluon.ai import reranker as reranker_client
from evaluon.queries import evaluation

from tests.queries.test_evaluation import FIXTURES

# Veinte preguntas con respuesta.
ANSWERED_20 = [0.31, 0.42, 0.55, 0.61, 0.66, 0.70, 0.72, 0.75, 0.78, 0.80,
               0.81, 0.83, 0.85, 0.87, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]
UNANSWERED = [0.05, 0.20, 0.45, 0.60]

# Conjunto del testeador de la verificación de T-042 (`calib_manual.py`): 25 con
# respuesta, 6 sin respuesta. Puntajes sintéticos.
TESTER_ANSWERED = [0.9123, 0.2871, 0.5555, 0.4419, 0.7766, 0.3302, 0.8888, 0.6011, 0.9501,
                   0.7012, 0.4419, 0.6634, 0.5021, 0.8150, 0.7300, 0.3998, 0.9900, 0.6200,
                   0.5876, 0.8432, 0.7745, 0.6873, 0.4567, 0.9210, 0.5302]
TESTER_UNANSWERED = [0.0512, 0.3300, 0.4419, 0.2009, 0.6500, 0.1234]


def entries(answered, unanswered=()):
    rows = [{"id": f"EV-{i:03d}", "has_answer": True, "max_score": score}
            for i, score in enumerate(answered, start=1)]
    rows += [{"id": f"EV-{i:03d}", "has_answer": False, "max_score": score}
             for i, score in enumerate(unanswered, start=len(answered) + 1)]
    return rows


def test_tester_set_of_25_gives_the_lowest_score_with_a_4_percent_estimate():
    """REQ-009: con las 25 preguntas del testeador, la posición más alta que cumple es
    k = 0: dejando cada vez una afuera frena solo la de puntaje más bajo, 1 de 25 (4 %);
    con k = 1 frenaría 2 de 25 (8 %). El umbral es 0,287 (0,2871 redondeado hacia
    abajo). La regla anterior daba 0,330."""
    calibration = evaluation.calibrate(entries(TESTER_ANSWERED, TESTER_UNANSWERED),
                                       current=0.5)

    assert calibration["position"] == 0
    assert calibration["proposed"] == 0.287
    assert calibration["meets"] is True
    loo = calibration["leave_one_out"]
    assert loo["blocked"] == ["EV-002"]
    assert (loo["total"], loo["rate"]) == (25, 0.04)
    assert calibration["blocked"] == []
    assert calibration["previous_rule"] == {
        "position": 1, "threshold": 0.33, "blocked": ["EV-002"],
        "leave_one_out_rate": 0.08,
    }
    assert calibration["unanswered_stopped"] == ["EV-026", "EV-029", "EV-031"]
    assert calibration["current"]["blocked"] == ["EV-002", "EV-004", "EV-006", "EV-011",
                                                 "EV-016", "EV-023"]


def test_with_40_questions_the_second_lowest_score_is_chosen():
    """REQ-009: con 40 preguntas, k = 1 frena dejando una afuera 2 de 40 (5 %), dentro
    del límite, y k = 2 frenaría 3 de 40 (7,5 %): el umbral es el segundo puntaje."""
    answered = [round(0.01 * i, 2) for i in range(1, 41)]

    calibration = evaluation.calibrate(entries(answered), current=0.5)

    assert calibration["position"] == 1
    assert calibration["proposed"] == 0.02
    assert calibration["blocked"] == ["EV-001"]
    assert (len(calibration["leave_one_out"]["blocked"]),
            calibration["leave_one_out"]["rate"]) == (2, 0.05)
    assert calibration["previous_rule"]["position"] == 2


def test_twenty_questions_meet_with_the_lowest_score():
    """REQ-009: con 20 preguntas, k = 0 frena dejando una afuera 1 de 20 (5 %) y cumple;
    k = 1 frenaría 2 de 20. La regla anterior proponía 0,42."""
    calibration = evaluation.calibrate(entries(ANSWERED_20, UNANSWERED), current=0.5)

    assert calibration["proposed"] == 0.31
    assert calibration["meets"] is True
    assert calibration["leave_one_out"]["blocked"] == ["EV-001"]
    assert calibration["leave_one_out"]["thresholds"]["EV-001"] == 0.42
    assert calibration["leave_one_out"]["thresholds"]["EV-002"] == 0.31
    assert calibration["previous_rule"]["threshold"] == 0.42
    assert calibration["unanswered_stopped"] == ["EV-021", "EV-022"]
    assert calibration["current"] == {"threshold": 0.5, "blocked": ["EV-001", "EV-002"]}


def test_a_small_set_proposes_the_lowest_score_and_says_it_does_not_meet():
    """REQ-009: con menos de veinte preguntas ninguna posición cumple (frenar una ya es
    más del 5 %): se propone el puntaje más bajo y se informa que no cumple."""
    calibration = evaluation.calibrate(entries([0.9, 0.8, 0.3], [0.2, 0.0]), current=0.5)

    assert calibration["proposed"] == 0.3
    assert calibration["position"] == 0
    assert calibration["meets"] is False
    assert calibration["blocked"] == []
    assert calibration["leave_one_out"]["blocked"] == ["EV-003"]
    assert calibration["unanswered_stopped"] == ["EV-004", "EV-005"]


def test_threshold_is_rounded_down_to_three_decimals():
    """REQ-009: el umbral propuesto se redondea hacia abajo a tres decimales, para que la
    pregunta que lo fija siga pasando (puntaje igual o mayor)."""
    calibration = evaluation.calibrate(entries([0.98765, 0.4267]), current=0.5)

    assert calibration["proposed"] == 0.426
    assert calibration["blocked"] == []


def test_answered_questions_without_a_score_are_listed_apart():
    """REQ-009: una pregunta con respuesta sin puntaje (no llegó a puntuarse) no cambia
    con ningún umbral: se lista aparte y no entra en la cuenta."""
    rows = entries([0.9, 0.7]) + [{"id": "EV-099", "has_answer": True, "max_score": None}]

    calibration = evaluation.calibrate(rows, current=0.5)

    assert calibration["without_score"] == ["EV-099"]
    assert calibration["answered"] == 2
    assert calibration["proposed"] == 0.7


def test_without_answered_questions_there_is_no_proposal():
    """REQ-009: sin preguntas con respuesta y puntaje no hay umbral para proponer."""
    calibration = evaluation.calibrate(entries([], [0.2]), current=0.5)

    assert calibration["proposed"] is None
    assert calibration["position"] is None
    assert calibration["leave_one_out"]["rate"] is None


def test_summary_explains_the_choice_and_the_previous_rule():
    """REQ-009: el resumen dice qué posición se eligió y por qué, la estimación dejando
    una afuera y el valor de la regla anterior, en lenguaje llano y con coma decimal."""
    calibration = evaluation.calibrate(entries(TESTER_ANSWERED, TESTER_UNANSWERED),
                                       current=0.5)
    lines = [{"id": row["id"], "has_answer": row["has_answer"], "expected_regime": ""}
             for row in entries(TESTER_ANSWERED, TESTER_UNANSWERED)]

    text = "\n".join(evaluation._calibration_section(calibration, lines))

    assert "Umbral propuesto (provisorio): 0,287" in text
    assert "puntaje número 1 de 25" in text
    assert "frena 1 de 25 (4,0 %)" in text
    assert "regla anterior" in text and "daría 0,330" in text
    assert "se admite frenar" not in text


@pytest.mark.django_db
def test_run_proposes_the_threshold_without_changing_settings(
    read_user, two_regimes, fake_ai, monkeypatch, tmp_path
):
    """REQ-009, REQ-020: la corrida calibra con el puntaje más alto de cada pregunta,
    corrida con su `fecha_autorizacion`; el umbral es uno solo para los dos regímenes,
    se informa como provisorio en `resumen.md` y `settings.py` no cambia."""
    marks = {
        "¿Cuál es el objeto del régimen sintético anterior?": 0.9,  # 297/03, 2021
        "¿Cuál es el objeto del régimen sintético?": 0.8,  # 247/2022, 2024
        "¿Qué garantías sintéticas se piden?": 0.3,
        "¿Cuántos días de licencia sintética corresponden?": 0.2,
    }
    monkeypatch.setattr(reranker_client, "rerank",
                        lambda query, documents: [marks.get(query, 0.0)] * len(documents))
    before = settings.RERANK_THRESHOLD

    report = evaluation.run(read_user, FIXTURES / "t042-diagnostico", tmp_path,
                            commit="abc1234")

    calibration = report.calibration
    assert calibration["answered"] == 3  # dos de la 247/2022 y una de la 297/03
    assert calibration["proposed"] == 0.3
    assert calibration["current"]["threshold"] == before
    assert settings.RERANK_THRESHOLD == before
    lines = {line["id"]: line for line in report.results}
    assert lines["EV-801"]["reference_date"] == "2021-03-15"
    assert lines["EV-801"]["diagnostics"]["max_score"] == pytest.approx(0.9)

    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    text = summary.split("## Calibración del umbral (provisoria)\n", 1)[1].split("\n## ")[0]
    assert "Umbral propuesto (provisorio): 0,300" in text
    assert "umbral actual: 0,500" in text
    assert "no cambia el umbral configurado" in text
    assert "EV-801" in text and "0,900" in text
