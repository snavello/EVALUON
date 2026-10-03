"""Calibración del umbral del reranker (T-042; plan 001, "Abstención", pasos 1 y 2).

Con el puntaje más alto de cada pregunta, se propone el umbral más alto que frena por
error a lo sumo el 5 % de las preguntas con respuesta; se mide además dejando cada vez
una pregunta afuera. El valor se informa como provisorio y no cambia `settings.py`. El
umbral es uno solo para los dos regímenes y cada pregunta se corre con su fecha.

Los puntajes son preparados a mano o salen de casos sintéticos (P4) respondidos con los
dobles de los clientes de IA.
"""

import pytest
from django.conf import settings

from evaluon.ai import reranker as reranker_client
from evaluon.queries import evaluation

from tests.queries.test_evaluation import FIXTURES

N247 = "Disposición AFIP 247/2022"
N297 = "Disposición AFIP 297/03"

# Veinte preguntas con respuesta: con el 5 % se puede frenar una.
ANSWERED = [0.31, 0.42, 0.55, 0.61, 0.66, 0.70, 0.72, 0.75, 0.78, 0.80,
            0.81, 0.83, 0.85, 0.87, 0.88, 0.90, 0.92, 0.94, 0.96, 0.98]
UNANSWERED = [0.05, 0.20, 0.45, 0.60]


def entries(answered, unanswered=()):
    rows = [{"id": f"EV-{i:03d}", "has_answer": True, "max_score": score}
            for i, score in enumerate(answered, start=1)]
    rows += [{"id": f"EV-{i:03d}", "has_answer": False, "max_score": score}
             for i, score in enumerate(unanswered, start=len(answered) + 1)]
    return rows


def test_proposes_the_highest_threshold_that_blocks_at_most_five_percent():
    """REQ-009: con veinte preguntas con respuesta se puede frenar a lo sumo una: el
    umbral propuesto es el segundo puntaje más bajo (0,42), que frena solo la de 0,31."""
    calibration = evaluation.calibrate(entries(ANSWERED, UNANSWERED), current=0.5)

    assert calibration["proposed"] == 0.42
    assert calibration["provisional"] is True
    assert calibration["answered"] == 20
    assert calibration["allowed_blocked"] == 1
    assert calibration["blocked"] == ["EV-001"]
    assert calibration["unanswered"] == 4
    assert calibration["unanswered_stopped"] == ["EV-021", "EV-022"]
    assert calibration["current"] == {"threshold": 0.5, "blocked": ["EV-001", "EV-002"]}


def test_leave_one_out_measures_each_question_with_the_others():
    """REQ-009: dejando cada vez una pregunta afuera, el umbral se calcula con las demás
    y se mide sobre la que quedó afuera: con estos puntajes solo la de 0,31 queda
    frenada, 1 de 20 (5 %), dentro de lo admitido."""
    loo = evaluation.calibrate(entries(ANSWERED), current=0.5)["leave_one_out"]

    assert loo["blocked"] == ["EV-001"]
    assert (loo["total"], loo["rate"], loo["meets"]) == (20, 0.05, True)
    assert loo["thresholds"]["EV-001"] == 0.42  # sin ella, las 19 restantes: la mínima
    assert loo["thresholds"]["EV-002"] == 0.31
    assert (loo["min"], loo["max"]) == (0.31, 0.42)


def test_a_small_set_proposes_the_lowest_score_and_leave_one_out_says_so():
    """REQ-009: con menos de veinte preguntas con respuesta no se puede frenar ninguna:
    el umbral es el puntaje más bajo. Dejando una afuera, la más baja queda frenada, y
    la medida lo muestra."""
    calibration = evaluation.calibrate(entries([0.9, 0.8, 0.3], [0.2, 0.0]), current=0.5)

    assert calibration["proposed"] == 0.3
    assert calibration["allowed_blocked"] == 0
    assert calibration["blocked"] == []
    assert calibration["unanswered_stopped"] == ["EV-004", "EV-005"]
    loo = calibration["leave_one_out"]
    assert loo["blocked"] == ["EV-003"]
    assert loo["meets"] is False


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
    assert calibration["leave_one_out"]["rate"] is None


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
    assert "settings.py" in text
    assert "EV-801" in text and "0,900" in text
