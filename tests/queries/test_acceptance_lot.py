"""Lote de aceptación y lote de ajuste (T-060; ADR-0014, punto 1; plan 001, "Evals",
campo `lote`, "Lote de aceptación" y "Qué usa cada lote").

Un caso tiene un campo optativo `lote`, `ajuste` o `aceptacion`, comparado sin tildes ni
mayúsculas; sin el campo es de ajuste y cualquier otro valor lo deja mal formado. La
respuesta correcta y la abstención exigidas salen del lote de aceptación; la cita
literal y el tiempo, de toda la corrida. El lote de ajuste va en una tabla aparte y es
el único que entra en la recuperación, las medidas por régimen, la calibración y la
comparación quitando piezas. La comparación con la corrida anterior va lote por lote, y
una corrida anterior sin el campo cuenta toda como lote de ajuste.

Los casos y la corrida guardada son sintéticos (P4), en `tests/fixtures/evals/t060/`, y
se responden con los dos regímenes de `two_regimes` y los dobles de los clientes de IA.

Con las marcas de `marks`: EV-881 (ajuste) acierta; EV-882 (ajuste, ajena) se abstiene
por el umbral; EV-883 (aceptación) acierta; EV-884 (aceptación, `lote: "Aceptación"`)
queda bajo el umbral y es incorrecta; EV-885 (aceptación, ajena, con puntaje alto) no se
abstiene.
"""

import json
import shutil
from io import StringIO

import pytest
from django.core.management import call_command

from evaluon.accounts import permissions
from evaluon.queries import evaluation

from tests.queries.test_evaluation import FIXTURES
from tests.queries.test_evaluation_diagnostics import (  # noqa: F401 (fixture)
    GUARANTEES, NEW_OBJECT, OLD_OBJECT, scripted, section,
)

T060 = FIXTURES / "t060"
CASES = T060 / "casos"
SAVED_NAME = "2000-01-01T120000_abc1234_modelo-sintetico"

pytestmark = pytest.mark.django_db

TEST_PASSWORD = "clave-sintetica-de-prueba"  # la de tests/conftest.py

Q881 = "¿Cuál es el objeto del régimen sintético?"
Q882 = "¿Cuántos días de licencia sintética corresponden?"
Q883 = "¿Cuál es el objeto del régimen sintético anterior?"
Q884 = "¿Qué garantías sintéticas se piden?"
Q885 = "¿Cuántos días de licencia sintética había?"


def marks(scripted):
    scripted.marks[Q881] = {NEW_OBJECT: 0.9}
    scripted.marks[Q882] = {NEW_OBJECT: 0.2}
    scripted.marks[Q883] = {OLD_OBJECT: 0.9}
    scripted.marks[Q884] = {GUARANTEES: 0.25}
    scripted.marks[Q885] = {OLD_OBJECT: 0.95}


def summary_of(report):
    return (report.folder / "resumen.md").read_text(encoding="utf-8")


# --- Lectura del campo `lote` ----------------------------------------------------------


def write_case(folder, lot_line):
    text = (CASES / "EV-881.yaml").read_text(encoding="utf-8")
    if lot_line is not None:
        text += lot_line + "\n"
    folder.mkdir(exist_ok=True)
    (folder / "EV-881.yaml").write_text(text, encoding="utf-8")
    return evaluation.load_cases(folder)


@pytest.mark.parametrize("lot_line, lot", [
    (None, "ajuste"),
    ("lote: ajuste", "ajuste"),
    ("lote: Ajuste", "ajuste"),
    ("lote: aceptacion", "aceptacion"),
    ('lote: "Aceptación"', "aceptacion"),
    ("lote: ACEPTACIÓN", "aceptacion"),
])
def test_lot_is_read_without_accents_or_case(tmp_path, lot_line, lot):
    """REQ-008, REQ-009: sin el campo el caso es de ajuste; `aceptacion` y `Aceptación`
    son del lote de aceptación."""
    cases, skipped = write_case(tmp_path / "casos", lot_line)

    assert skipped == []
    assert cases[0].lot == lot


@pytest.mark.parametrize("lot_line", ["lote: aceptado", 'lote: ""', "lote: 1",
                                      "lote: [aceptacion]"])
def test_any_other_lot_leaves_the_case_malformed(tmp_path, lot_line):
    """REQ-008, REQ-009: cualquier otro valor (`aceptado`, vacío, un número o una lista)
    deja el caso mal formado, con un mensaje en lenguaje llano que nombra los valores
    posibles."""
    cases, skipped = write_case(tmp_path / "casos", lot_line)

    assert cases == []
    assert skipped[0].kind == evaluation.MALFORMED
    assert "`lote`" in skipped[0].reason
    assert "ajuste" in skipped[0].reason and "aceptacion" in skipped[0].reason


def test_the_lot_is_saved_in_each_line(read_user, two_regimes, scripted, tmp_path):
    """REQ-008, REQ-009: el renglón de `resultados.jsonl` guarda el lote del caso."""
    marks(scripted)

    report = evaluation.run(read_user, CASES, tmp_path, commit="abc1234")

    rows = {json.loads(row)["id"]: json.loads(row) for row in
            (report.folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()}
    assert {case_id: row["lot"] for case_id, row in rows.items()} == {
        "EV-881": "ajuste", "EV-882": "ajuste", "EV-883": "aceptacion",
        "EV-884": "aceptacion", "EV-885": "aceptacion",
    }


# --- Qué usa cada lote -----------------------------------------------------------------


def test_required_measures_use_the_acceptance_lot(read_user, two_regimes, scripted,
                                                  tmp_path):
    """REQ-008, REQ-009 (ADR-0014): la respuesta correcta y la abstención exigidas se
    miden solo con el lote de aceptación; la cita literal y el tiempo, con toda la
    corrida. El lote de ajuste va aparte."""
    marks(scripted)

    report = evaluation.run(read_user, CASES, tmp_path, commit="abc1234")

    required = report.measures
    assert (required["correct_answer"]["ok"], required["correct_answer"]["total"]) == (1, 2)
    assert (required["abstention"]["ok"], required["abstention"]["total"]) == (0, 1)
    # Citas de EV-881, EV-883 y EV-885: toda la corrida.
    assert required["literal_citation"]["total"] == sum(
        line["measures"]["citations"] for line in report.results)
    assert {line["id"] for line in report.results if line["measures"]["citations"]} == {
        "EV-881", "EV-883", "EV-885"}
    assert required["response_time"]["max"] is not None
    adjustment = report.adjustment_measures
    assert (adjustment["correct_answer"]["ok"], adjustment["correct_answer"]["total"]) == (1, 1)
    assert (adjustment["abstention"]["ok"], adjustment["abstention"]["total"]) == (1, 1)

    summary = summary_of(report)
    table = section(summary, "Medidas exigidas")
    assert "| Respuesta correcta que cita la unidad correcta (lote de aceptación) | 50,0 % (1 de 2;" in table
    assert "| Abstención (lote de aceptación) | 0,0 % (0 de 1;" in table
    assert "| Cita literal (toda la corrida) | 100,0 % (" in table
    assert "no tiene casos del lote de aceptación" not in table
    adjustment_text = section(summary, "Lote de ajuste (diagnóstico)")
    assert "| Respuesta correcta que cita la unidad correcta | 100,0 % (1 de 1;" in adjustment_text
    assert "| Abstención | 100,0 % (1 de 1;" in adjustment_text


def test_diagnosis_and_calibration_leave_the_acceptance_lot_out(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-009 (ADR-0014): la recuperación, las medidas por régimen, la calibración y la
    comparación quitando piezas usan solo el lote de ajuste: EV-884 (aceptación, 0,25)
    no es la pregunta con respuesta más baja y EV-885 (aceptación, ajena, 0,95) no
    cierra el hueco."""
    marks(scripted)

    report = evaluation.run(read_user, CASES, tmp_path, commit="abc1234", ablation=True)

    assert list(report.by_regime) == ["Disposición AFIP 247/2022"]
    assert report.retrieval["selected"]["total"] == 1
    assert report.retrieval["unanswered_stopped"]["total"] == 1
    calibration = report.calibration
    assert calibration["low_answered"]["id"] == "EV-881"
    assert calibration["high_foreign"]["id"] == "EV-882"
    assert calibration["proposed"] == 0.6
    assert set(calibration["scores"]) == {"EV-881", "EV-882"}
    assert [config["selected"]["total"] for config in report.ablation] == [1, 1, 1, 1]
    lines = {line["id"]: line for line in report.results}
    assert lines["EV-883"]["ablation"] is None
    assert lines["EV-881"]["ablation"] is not None

    summary = summary_of(report)
    assert "Disposición AFIP 297/03" not in section(summary,
                                                    "Medidas por régimen (diagnóstico)")
    assert "EV-885" not in section(summary, "Calibración del umbral (provisoria)")


def test_pairs_notices_and_failures_use_the_whole_run(read_user, two_regimes, scripted,
                                                      tmp_path):
    """REQ-008, REQ-021 (plan, "Qué usa cada lote"): el aviso de REQ-021 y las salidas
    con falla se miran en toda la corrida."""
    marks(scripted)

    report = evaluation.run(read_user, CASES, tmp_path, commit="abc1234")

    assert report.notices["total"] == 5
    text = section(summary_of(report), "Aviso de REQ-021")
    assert "5 de 5" in text


def test_failed_cases_of_the_acceptance_lot_are_listed_apart(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008, REQ-009 (plan, "Lote de aceptación"): los casos fallados del lote de
    aceptación van aparte, con el aviso de que no se usan para ajustar."""
    marks(scripted)

    report = evaluation.run(read_user, CASES, tmp_path, commit="abc1234")

    summary = summary_of(report)
    adjustment = section(summary, "Casos fallados")
    acceptance = section(summary, "Casos fallados del lote de aceptación")
    assert "EV-884" not in adjustment and "EV-885" not in adjustment
    assert "Ninguno." in adjustment
    assert "EV-884" in acceptance and "EV-885" in acceptance
    assert "no se usan para ajustar" in acceptance


def test_without_acceptance_cases_the_requirements_cannot_be_met(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-008, REQ-009 (plan, "Qué usa cada lote"): si la corrida no tiene casos del
    lote de aceptación, la tabla de las exigencias lo dice: no se pueden dar por
    cumplidas con ella. El comando también lo dice."""
    marks(scripted)
    cases = tmp_path / "casos"
    cases.mkdir()
    for name in ("EV-881.yaml", "EV-882.yaml"):
        shutil.copy(CASES / name, cases / name)

    report = evaluation.run(read_user, cases, tmp_path / "corridas", commit="abc1234")

    assert report.measures["correct_answer"]["total"] == 0
    assert report.measures["correct_answer"]["meets"] is None
    table = section(summary_of(report), "Medidas exigidas")
    assert "no tiene casos del lote de aceptación" in table
    assert "no se pueden dar por cumplidas" in table
    assert "| Respuesta correcta que cita la unidad correcta (lote de aceptación) | — |" in table

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()
    call_command("correr_evals", "--usuario", read_user.username, "--casos", str(cases),
                 "--corridas", str(tmp_path / "otras"), "--commit", "abc1234",
                 stdout=out, stderr=StringIO())
    assert "no tiene casos del lote de aceptación" in out.getvalue()


# --- Comparación con la corrida anterior y recalificación ------------------------------


@pytest.fixture
def runs_with_saved(tmp_path):
    """Carpeta de corridas con la corrida sintética guardada sin lotes."""
    runs = tmp_path / "corridas"
    shutil.copytree(T060 / "corridas" / SAVED_NAME, runs / SAVED_NAME)
    return runs


def test_previous_run_without_lots_is_compared_as_the_adjustment_lot(
    read_user, two_regimes, scripted, runs_with_saved
):
    """REQ-008 (P7; plan, "Qué usa cada lote"): la comparación va lote por lote; una
    corrida anterior sin el campo cuenta toda como lote de ajuste. EV-881 deja de
    acertar: baja la respuesta correcta del lote de ajuste (de 2 de 2 a 0 de 1); el
    lote de aceptación no tiene con qué compararse."""
    marks(scripted)
    del scripted.marks[Q881]

    report = evaluation.run(read_user, CASES, runs_with_saved, commit="abc1234")

    comparison = report.comparison
    assert comparison["previous"] == SAVED_NAME
    rows = {(row["lot"], row["name"]): row for row in comparison["measures"]}
    assert rows[("ajuste", "correct_answer")]["previous"] == 1.0
    assert rows[("ajuste", "correct_answer")]["current"] == 0.0
    assert rows[("aceptacion", "correct_answer")]["previous"] is None
    assert rows[("aceptacion", "correct_answer")]["current"] == 0.5
    assert {"name": "correct_answer", "lot": "ajuste"} in comparison["drops"]
    assert all(drop["lot"] != "aceptacion" for drop in comparison["drops"])

    text = section(summary_of(report), "Comparación con la corrida anterior")
    adjustment = text.split("### Lote de ajuste", 1)[1].split("###", 1)[0]
    assert "| Respuesta correcta que cita la unidad correcta | 100,0 % | 0,0 % | baja |" \
        in adjustment
    acceptance = text.split("### Lote de aceptación", 1)[1].split("###", 1)[0]
    assert "| Respuesta correcta que cita la unidad correcta | — | 50,0 % | — |" in acceptance
    assert "lote de ajuste" in text.split("**Hay bajas", 1)[1]


def test_rescore_takes_the_lot_of_the_current_case(read_user, runs_with_saved):
    """REQ-008, REQ-009 (plan, "Recalificar"; aviso de T-058): la recalificación toma el
    lote del caso vigente: EV-883, guardado sin lote, pasa a ser del lote de aceptación
    y sale de la calibración (su puntaje guardado, 0,1, cerraría el hueco). Los casos
    que no están en la corrida quedan como no recalificables."""
    source = runs_with_saved / SAVED_NAME

    report = evaluation.rescore(read_user, source, CASES, runs_with_saved,
                                commit="def5678")

    lines = {line["id"]: line for line in report.results}
    assert {case_id: line["lot"] for case_id, line in lines.items()} == {
        "EV-881": "ajuste", "EV-882": "ajuste", "EV-883": "aceptacion"}
    assert {s.case_id for s in report.skipped
            if s.kind == evaluation.NOT_RESCORABLE} == {"EV-884", "EV-885"}
    assert report.calibration["low_answered"]["id"] == "EV-881"
    assert report.calibration["proposed"] == 0.6
    assert (report.measures["correct_answer"]["ok"],
            report.measures["correct_answer"]["total"]) == (1, 1)
    rows = {(row["lot"], row["name"]): row for row in report.comparison["measures"]}
    assert rows[("ajuste", "correct_answer")]["previous"] == 1.0
    assert rows[("ajuste", "correct_answer")]["current"] == 1.0
