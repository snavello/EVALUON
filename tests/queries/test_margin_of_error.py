"""Margen de error de las medidas que son proporciones (T-060; ADR-0014, punto 1; plan
001, "Evals", "Margen de error").

Cada medida que es una proporción (cita literal, respuesta correcta y abstención) se
informa con su intervalo de confianza al 95 % por el método de Wilson, con `z = 1,96`,
en la tabla de las exigencias, en la del lote de ajuste y en las medidas por régimen.
Formato: "90,0 % (9 de 10; IC 95 %: 59,6 % a 98,2 %)"; sin casos, "—". El tiempo no
lleva intervalo. Los renglones son sintéticos (P4).
"""

import math

import pytest

from evaluon.queries import evaluation


@pytest.mark.parametrize("ok, total, low, high", [
    (10, 10, 72.2, 100.0),
    (9, 10, 59.6, 98.2),
    (6, 6, 61.0, 100.0),
])
def test_wilson_interval_gives_the_values_of_the_plan(ok, total, low, high):
    """REQ-008, REQ-009: con el lote mínimo, 10 de 10 da de 72,2 % a 100 %; 9 de 10, de
    59,6 % a 98,2 %; 6 de 6, de 61,0 % a 100 %."""
    lower, upper = evaluation.wilson_interval(ok, total)

    assert round(lower * 100, 1) == low
    assert round(upper * 100, 1) == high
    assert 0.0 <= lower <= upper <= 1.0


def test_wilson_interval_follows_the_formula_with_z_1_96():
    """REQ-008, REQ-009: el intervalo es el de la fórmula del plan, con `z = 1,96`."""
    ok, n, z = 17, 23, 1.96
    p = ok / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z / (1 + z * z / n) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))

    lower, upper = evaluation.wilson_interval(ok, n)

    assert evaluation.WILSON_Z == 1.96
    assert lower == pytest.approx(center - radius)
    assert upper == pytest.approx(center + radius)


def test_without_cases_there_is_no_interval():
    """REQ-008, REQ-009: sin casos no hay intervalo, y la medida se muestra "—"."""
    assert evaluation.wilson_interval(0, 0) is None
    assert evaluation.proportion_text({"ok": 0, "total": 0, "rate": None}) == "—"
    assert evaluation.proportion_text(None) == "—"


def test_text_follows_the_format_of_the_plan():
    """REQ-008, REQ-009: "90,0 % (9 de 10; IC 95 %: 59,6 % a 98,2 %)"; un extremo que
    llega a 100 % o a 0 % se escribe sin decimales."""
    assert (evaluation.proportion_text({"ok": 9, "total": 10, "rate": 0.9})
            == "90,0 % (9 de 10; IC 95 %: 59,6 % a 98,2 %)")
    assert (evaluation.proportion_text({"ok": 10, "total": 10, "rate": 1.0})
            == "100,0 % (10 de 10; IC 95 %: 72,2 % a 100 %)")
    assert evaluation.proportion_text({"ok": 0, "total": 5, "rate": 0.0}).startswith(
        "0,0 % (0 de 5; IC 95 %: 0 % a ")


def line(case_id, *, has_answer=True, passed=True, lot=None, regime="Disposición AFIP "
         "247/2022", citations=1):
    row = {
        "id": case_id, "has_answer": has_answer, "expected_regime": regime,
        "time_seconds": 2.0,
        "measures": {"citations": citations, "literal_citations": citations,
                     "correct": passed if has_answer else None,
                     "abstained": None if has_answer else passed},
    }
    if lot is not None:
        row["lot"] = lot
    return row


def test_measures_carry_the_interval():
    """REQ-008, REQ-009: cada proporción de `measure` trae los extremos del intervalo;
    el tiempo no."""
    lines = [line(f"EV-{i:03d}", passed=i != 1) for i in range(1, 11)]

    measures = evaluation.measure(lines)

    correct = measures["correct_answer"]
    assert (correct["ok"], correct["total"]) == (9, 10)
    assert round(correct["low"] * 100, 1) == 59.6
    assert round(correct["high"] * 100, 1) == 98.2
    assert measures["abstention"]["low"] is None
    assert "low" not in measures["response_time"]


def test_required_table_shows_the_interval_and_time_has_none():
    """REQ-008, REQ-009: la tabla de las exigencias muestra cada proporción con su
    intervalo y el tiempo sin intervalo."""
    lines = ([line(f"EV-1{i:02d}", passed=i != 1, lot="aceptacion") for i in range(1, 11)]
             + [line(f"EV-2{i:02d}", has_answer=False, lot="aceptacion", citations=0)
                for i in range(1, 7)])

    rows = {name: result for name, result, _, _ in
            evaluation.measure_rows(evaluation.required_measures(lines))}

    correct = next(v for k, v in rows.items() if k.startswith("Respuesta correcta"))
    abstention = next(v for k, v in rows.items() if k.startswith("Abstención"))
    literal = next(v for k, v in rows.items() if k.startswith("Cita literal"))
    timing = next(v for k, v in rows.items() if k.startswith("Tiempo"))
    assert correct == "90,0 % (9 de 10; IC 95 %: 59,6 % a 98,2 %)"
    assert abstention == "100,0 % (6 de 6; IC 95 %: 61,0 % a 100 %)"
    assert literal == "100,0 % (10 de 10; IC 95 %: 72,2 % a 100 %)"
    assert "IC 95 %" not in timing


def test_by_regime_section_shows_the_interval_and_a_dash_without_cases():
    """REQ-008, REQ-009, REQ-020: las medidas por régimen llevan su intervalo; un régimen
    sin preguntas sin respuesta muestra "—" en la abstención."""
    lines = [line(f"EV-{i:03d}", passed=i != 1) for i in range(1, 11)]

    text = "\n".join(evaluation._by_regime_section(evaluation.measures_by_regime(lines)))

    assert ("| Disposición AFIP 247/2022 | 90,0 % (9 de 10; IC 95 %: 59,6 % a 98,2 %) | — |"
            in text)
