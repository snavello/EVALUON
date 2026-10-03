"""Calibración del umbral del reranker con la regla del hueco (T-060; ADR-0014, punto 2;
plan 001, "Abstención", "Calibración del umbral").

Entran solo las preguntas del lote de ajuste: las con respuesta que llegaron a
puntuarse y las sin respuesta con la etiqueta "ajena a la normativa" que llegaron a
puntuarse; las de "tema cercano que la normativa no resuelve" no entran. `A` es la ajena
más alta y `B` la pregunta con respuesta más baja; cada puntaje se acota entre 10⁻⁹ y
1 − 10⁻⁹ y se pasa a `logit`. Hay hueco si `logit(B) > logit(A)`; el umbral es la
sigmoide del punto medio, redondeada hacia abajo a tres decimales, y el margen es la
mitad del hueco, con un mínimo de 0,5. El valor es provisorio y no cambia `settings.py`.

Los puntajes de la corrida de T-045 están copiados a mano de
`evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0/` (los más altos de
cada pregunta; los demás con respuesta, entre 0,984 y 1,000). Los otros puntajes son
sintéticos, o salen de casos sintéticos (P4) respondidos con los dobles de los clientes
de IA.
"""

import pytest
from django.conf import settings

from evaluon.ai import reranker as reranker_client
from evaluon.queries import evaluation

from tests.queries.test_evaluation import FIXTURES

FOREIGN = "ajena a la normativa"
NEAR = "tema cercano que la normativa no resuelve"

# Corrida de T-045: preguntas con respuesta (24) con su puntaje más alto.
T045_ANSWERED = {
    "EV-001": 0.9982, "EV-002": 0.9991, "EV-003": 0.9874, "EV-004": 0.508,
    "EV-005": 0.9963, "EV-006": 0.9995, "EV-007": 0.748, "EV-008": 0.9840,
    "EV-009": 0.9978, "EV-010": 1.0, "EV-011": 0.9952, "EV-012": 0.9989,
    "EV-013": 0.9931, "EV-014": 0.9997, "EV-015": 0.9906, "EV-016": 0.9985,
    "EV-017": 0.9944, "EV-018": 0.9971, "EV-019": 0.9999, "EV-020": 0.368022,
    "EV-021": 0.9958, "EV-022": 0.9993, "EV-023": 0.9887, "EV-024": 0.9969,
}
T045_FOREIGN = {"EV-025": 0.1195, "EV-026": 0.0218, "EV-030": 0.0032}
T045_NEAR = {"EV-027": 0.775, "EV-028": 0.988, "EV-029": 0.743}


def entry(case_id, score, *, has_answer=True, labels=(), lot=None):
    row = {"id": case_id, "has_answer": has_answer, "max_score": score,
           "labels": list(labels)}
    if lot is not None:
        row["lot"] = lot
    return row


def t045_entries(near_label=NEAR):
    rows = [entry(case_id, score) for case_id, score in T045_ANSWERED.items()]
    rows += [entry(case_id, score, has_answer=False, labels=[FOREIGN])
             for case_id, score in T045_FOREIGN.items()]
    rows += [entry(case_id, score, has_answer=False, labels=[near_label])
             for case_id, score in T045_NEAR.items()]
    # EV-031: sin régimen a la fecha, no llega al reranker.
    rows.append(entry("EV-031", None, has_answer=False, labels=[FOREIGN]))
    return sorted(rows, key=lambda row: row["id"])


def text_of(calibration, rows):
    lines = [{"id": row["id"], "has_answer": row["has_answer"], "expected_regime": ""}
             for row in rows]
    return "\n".join(evaluation._calibration_section(calibration, lines))


def test_t045_scores_give_0_219_with_a_margin_of_0_728():
    """REQ-009: con los puntajes de T-045, `A` es EV-025 (logit −1,9972) y `B` EV-020
    (logit −0,5407); el punto medio es −1,2689, el umbral propuesto 0,219 (la sigmoide,
    0,2194, redondeada hacia abajo) y el margen 0,728, que cumple el mínimo. Frena las
    tres ajenas y ninguna pregunta con respuesta; las tres de tema cercano quedan por
    encima."""
    calibration = evaluation.calibrate(t045_entries(), current=0.368)

    assert calibration["proposed"] == 0.219
    assert calibration["provisional"] is True
    assert calibration["gap"] is True
    high = calibration["high_foreign"]
    low = calibration["low_answered"]
    assert (high["id"], high["score"]) == ("EV-025", 0.1195)
    assert high["logit"] == pytest.approx(-1.9972, abs=1e-4)
    assert (low["id"], low["score"]) == ("EV-020", 0.368022)
    assert low["logit"] == pytest.approx(-0.5407, abs=1e-4)
    assert calibration["midpoint"] == pytest.approx(-1.2689, abs=1e-4)
    assert round(calibration["margin"], 3) == 0.728
    assert calibration["min_margin"] == 0.5
    assert calibration["meets_margin"] is True
    assert calibration["blocked"] == []
    assert calibration["unanswered_stopped"] == ["EV-025", "EV-026", "EV-030"]
    assert calibration["near_above"] == ["EV-027", "EV-028", "EV-029"]
    assert calibration["current"]["threshold"] == 0.368
    assert calibration["current"]["blocked"] == []
    assert calibration["current"]["unanswered_stopped"] == ["EV-025", "EV-026", "EV-030"]
    assert calibration["answered"] == 24
    assert calibration["without_score"] == []


def test_t045_summary_reports_the_rule():
    """REQ-009: el resumen y el comando dicen el umbral, `A` y `B` con su caso, el margen
    y "cumple el margen mínimo: sí"; la sección agrega lo que frena cada umbral, las de
    tema cercano por encima y la tabla de puntajes."""
    rows = t045_entries()
    calibration = evaluation.calibrate(rows, current=0.368)

    line = evaluation.threshold_line(calibration)
    text = text_of(calibration, rows)

    assert line.startswith("Umbral propuesto (provisorio): 0,219")
    for piece in ("EV-025", "0,1195", "EV-020", "0,3680", "margen 0,728",
                  "cumple el margen mínimo: sí"):
        assert piece in line
    assert line in text
    assert "umbral actual: 0,368" in text
    assert "no cambia el umbral configurado" in text
    assert "−1,9972" in text and "−0,5407" in text and "−1,2689" in text
    assert "EV-027, EV-028, EV-029" in text
    assert "| EV-028 | tema cercano |" in text
    assert "EV-031" not in text.split("| Caso |")[1]  # sin puntaje, fuera de la tabla


def test_near_questions_labelled_as_foreign_leave_no_gap():
    """REQ-009: las mismas preguntas con la etiqueta "ajena a la normativa" en lugar de
    "tema cercano" dejan sin hueco: no hay umbral propuesto; EV-027, EV-028 y EV-029
    son ajenas con puntaje mayor o igual que `B` y EV-020, EV-004 y EV-007 están entre
    las preguntas con respuesta con puntaje menor o igual que `A`. Eso prueba que las de
    tema cercano no entran en la regla."""
    rows = t045_entries(near_label=FOREIGN)
    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["proposed"] is None
    assert calibration["gap"] is False
    assert calibration["high_foreign"]["id"] == "EV-028"
    assert set(calibration["foreign_at_or_above_low"]) == {"EV-027", "EV-028", "EV-029"}
    assert calibration["answered_at_or_below_high"][:3] == ["EV-020", "EV-004", "EV-007"]
    assert calibration["meets_margin"] is None
    assert calibration["near_above"] == []

    line = evaluation.threshold_line(calibration)
    text = text_of(calibration, rows)
    assert "No hay hueco" in line
    assert "decisión es del responsable" in line
    assert "EV-027" in text and "EV-004" in text


def test_equal_scores_leave_no_gap():
    """REQ-009: en el borde A = B (la ajena más alta con el mismo puntaje que la pregunta
    con respuesta más baja) no hay hueco: la regla lo informa y no propone umbral; la
    ajena figura entre las de puntaje mayor o igual que `B` y la pregunta, entre las de
    puntaje menor o igual que `A`."""
    rows = [entry("EV-001", 0.4), entry("EV-002", 0.95),
            entry("EV-003", 0.4, has_answer=False, labels=[FOREIGN])]

    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["high_foreign"]["logit"] == calibration["low_answered"]["logit"]
    assert calibration["gap"] is False
    assert calibration["proposed"] is None
    assert calibration["meets_margin"] is None
    assert calibration["foreign_at_or_above_low"] == ["EV-003"]
    assert calibration["answered_at_or_below_high"] == ["EV-001"]
    line = evaluation.threshold_line(calibration)
    assert line.startswith("Umbral propuesto (provisorio): ninguno")
    assert "No hay hueco" in line
    assert "decisión es del responsable" in line
    text_of(calibration, rows)


def test_insufficient_margin_is_reported_and_marked():
    """REQ-009: con la ajena más alta en 0,30 y la pregunta con respuesta más baja en
    0,368022 hay hueco, pero el margen es 0,153: "cumple el margen mínimo: no" y el
    valor queda marcado como sin margen, sin fijarse sin decisión del responsable."""
    rows = [entry("EV-001", 0.368022), entry("EV-002", 0.95),
            entry("EV-003", 0.30, has_answer=False, labels=[FOREIGN])]

    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["gap"] is True
    assert round(calibration["margin"], 3) == 0.153
    assert calibration["meets_margin"] is False
    assert calibration["proposed"] == 0.333
    line = evaluation.threshold_line(calibration)
    assert "margen 0,153" in line
    assert "cumple el margen mínimo: no" in line
    assert "sin margen" in line
    assert "decisión del responsable" in text_of(calibration, rows)


def test_without_foreign_scores_the_rule_cannot_be_applied():
    """REQ-009: sin preguntas ajenas a la normativa con puntaje no hay umbral propuesto
    y se dice por qué; lo mismo sin preguntas con respuesta con puntaje."""
    rows = [entry("EV-001", 0.9), entry("EV-002", 0.4, has_answer=False, labels=[NEAR]),
            entry("EV-003", None, has_answer=False, labels=[FOREIGN])]

    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["proposed"] is None
    assert calibration["gap"] is None
    assert "ajenas a la normativa" in calibration["reason"]
    assert "no se puede aplicar" in evaluation.threshold_line(calibration)
    assert "ajenas a la normativa" in evaluation.threshold_line(calibration)

    only_foreign = evaluation.calibrate(
        [entry("EV-001", 0.2, has_answer=False, labels=[FOREIGN])], current=0.368)
    assert only_foreign["proposed"] is None
    assert "con respuesta" in only_foreign["reason"]


def test_acceptance_lot_does_not_move_the_threshold():
    """REQ-009 (ADR-0014, punto 1): un caso del lote de aceptación con puntaje menor que
    el de EV-020, o una ajena de ese lote con puntaje mayor que el de EV-025, no cambia
    el umbral, y no figura en la tabla de puntajes."""
    rows = t045_entries() + [
        entry("EV-040", 0.30, lot="aceptacion"),
        entry("EV-041", 0.35, has_answer=False, labels=[FOREIGN], lot="aceptacion"),
    ]

    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["proposed"] == 0.219
    assert calibration["high_foreign"]["id"] == "EV-025"
    assert calibration["low_answered"]["id"] == "EV-020"
    assert "EV-040" not in calibration["scores"]
    assert "EV-041" not in calibration["scores"]
    assert "EV-041" not in calibration["unanswered_stopped"]
    assert calibration["answered"] == 24


def test_saved_scores_of_zero_or_one_give_no_error():
    """REQ-009: un puntaje guardado de 0,0 o de 1,0 se acota antes de pasar a `logit` y
    no da error."""
    rows = [entry("EV-001", 1.0), entry("EV-002", 0.0, has_answer=False, labels=[FOREIGN])]

    calibration = evaluation.calibrate(rows, current=0.368)

    assert calibration["proposed"] == 0.5
    assert calibration["meets_margin"] is True
    assert calibration["high_foreign"]["logit"] == pytest.approx(-20.723, abs=1e-3)
    text_of(calibration, rows)


def test_answered_questions_without_a_score_are_listed_apart():
    """REQ-009: una pregunta con respuesta sin puntaje (no llegó a puntuarse) no cambia
    con ningún umbral: se lista aparte y no entra en la cuenta."""
    rows = [entry("EV-001", 0.9), entry("EV-002", 0.7),
            entry("EV-003", 0.1, has_answer=False, labels=[FOREIGN]),
            entry("EV-099", None)]

    calibration = evaluation.calibrate(rows, current=0.5)

    assert calibration["without_score"] == ["EV-099"]
    assert calibration["answered"] == 2
    assert calibration["low_answered"]["id"] == "EV-002"
    assert "EV-099" in text_of(calibration, rows)


def test_leave_one_out_rule_is_gone():
    """REQ-009 (ADR-0014, punto 2): la regla de T-042 (dejar una afuera y frenar a lo
    sumo el 5 %) ya no está."""
    assert not hasattr(evaluation, "leave_one_out")
    assert not hasattr(evaluation, "CALIBRATION_MAX_BLOCKED")
    assert evaluation.CALIBRATION_MIN_MARGIN == 0.5


@pytest.mark.django_db
def test_run_proposes_the_threshold_without_changing_settings(
    read_user, two_regimes, fake_ai, monkeypatch, tmp_path
):
    """REQ-009, REQ-020: la corrida calibra con el puntaje más alto de cada pregunta,
    corrida con su `fecha_autorizacion`; el umbral es uno solo para los dos regímenes,
    se informa como provisorio en `resumen.md` y `settings.py` no cambia. Con 0,3 la
    pregunta con respuesta más baja y 0,2 la ajena más alta (la otra puntúa 0), el
    umbral es 0,246 y el margen, 0,270, no llega al mínimo."""
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
    assert calibration["high_foreign"]["id"] == "EV-803"
    assert calibration["low_answered"]["id"] == "EV-805"
    assert calibration["proposed"] == 0.246
    assert calibration["meets_margin"] is False
    assert calibration["current"]["threshold"] == before
    assert settings.RERANK_THRESHOLD == before
    lines = {line["id"]: line for line in report.results}
    assert lines["EV-801"]["reference_date"] == "2021-03-15"
    assert lines["EV-801"]["diagnostics"]["max_score"] == pytest.approx(0.9)
    assert lines["EV-804"]["diagnostics"]["max_score"] == 0.0

    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    text = summary.split("## Calibración del umbral (provisoria)\n", 1)[1].split("\n## ")[0]
    assert "Umbral propuesto (provisorio): 0,246" in text
    assert "cumple el margen mínimo: no" in text
    assert f"umbral actual: {before:.3f}".replace(".", ",") in text
    assert "no cambia el umbral configurado" in text
    assert "EV-801" in text and "0,9000" in text
