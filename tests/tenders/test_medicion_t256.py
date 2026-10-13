"""Medida honesta de la matriz (T-256; REQ-101, REQ-102, REQ-107; mesa de comité del 2026-10-12,
`4-medicion.md` §2 H6 y §7: D5, D7, D9 y la fila que agrega una circular). Todo sintético (P4)."""

import json

import pytest

from evaluon.tenders import evaluation as ev
from evaluon.tenders import models as m
from tests.tenders.scripted import PAGO, item, script  # noqa: F401  (fixture)
from tests.tenders.test_evaluation import (  # noqa: F401  (fixtures)
    case,
    circular_case,
    measures_of,
    run_measure,
)

pytestmark = pytest.mark.django_db


def test_what_is_in_mandatory_review_is_not_found_and_is_reported_apart(
        case, operator_user, script, tmp_path):
    """REQ-101, REQ-102 (T-256, D5): lo que está a revisión obligatoria no cuenta como
    encontrado en la cifra principal (la del umbral); la cifra con la revisión se informa al
    lado."""
    procedure, _, path, _ = case
    base = measures_of(run_measure(operator_user, procedure, path, tmp_path / "base"))
    script.when(PAGO, item())

    report = run_measure(operator_user, procedure, path, tmp_path / "pendiente")

    measures = measures_of(report)
    assert measures["review"]["count"] == 1
    assert measures["recall"] == measures["found_without_review"]
    # S-002 no estaba en la base: a revisión suma a la cifra informada, no a la principal.
    assert measures["recall"]["ok"] == base["recall"]["ok"]
    assert measures["found"]["ok"] == base["recall"]["ok"] + 1
    [(name, value, _)] = [row for row in ev.thresholds_015(measures) if "lista" in row[0]]
    assert "ni lo que está a revisión" in name and value == measures["recall"]
    summary = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "recall contando lo que está a revisión (informado)" in summary


def test_technical_rows_built_by_a_rule_are_reported_apart(case, operator_user, tmp_path):
    """REQ-101, REQ-102 (T-256, D9): las filas técnicas que arma una regla se informan aparte:
    la lista presente y las conservadas sin ellas, al lado de las cifras con ellas."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    measures = measures_of(report)
    lines = [line for line in measures["lines"] if line["tipo"] == "esperado"
             and line.get("estado") != "sin_medir"]
    fe = [line for line in lines if line["clase"] != ev.TECHNICAL]
    technical = [line for line in lines if line["clase"] == ev.TECHNICAL]
    assert technical and fe
    assert measures["found_without_technical"]["total"] == len(fe)
    assert measures["found_without_technical"]["ok"] == sum(
        1 for line in fe if line["estado"] == "encontrado")
    assert measures["technical"]["items"] == len(technical)
    proposed = [line for line in measures["lines"] if line["tipo"] == "propuesto"]
    fe_rows = [line for line in proposed if line["clase"] != ev.TECHNICAL]
    assert measures["technical"]["rows"] == len(proposed) - len(fe_rows)
    assert measures["kept_without_technical"]["total"] == len(fe_rows)
    assert measures["kept_without_technical"]["ok"] == sum(
        1 for line in fe_rows if line["estado"] != "sobrante")
    summary = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "sin las filas técnicas que arma una regla (informado)" in summary


def test_a_row_added_by_a_circular_is_not_a_leftover(circular_case):
    """REQ-102 (T-256): una fila de la matriz agregada por una circular no cuenta como sobrante;
    se informa aparte. La misma fila de origen propuesto sí es sobrante."""
    c = circular_case
    c.write_list()
    before = c.measure()[2]
    leftover = next(line["numero"] for line in before["lines"]
                    if line["tipo"] == "propuesto" and line["estado"] == "sobrante")
    m.Requirement.objects.filter(version=c.version, number=leftover).update(
        origin=m.RequirementOrigin.CIRCULAR)

    measures = c.measure()[2]

    assert before["leftovers"] >= 1 and before["added_by_circular"]["count"] == 0
    assert measures["leftovers"] == before["leftovers"] - 1
    assert measures["proposed_total"] == before["proposed_total"]
    assert measures["added_by_circular"] == {"count": 1, "rows": [leftover]}
    line = next(line for line in measures["lines"]
                if line["tipo"] == "propuesto" and line["numero"] == leftover)
    assert line["estado"] == ev.ADDED_BY_CIRCULAR


def _saved_lines(tmp_path, lines):
    folder = tmp_path / "20261012-000000-abc1234"
    folder.mkdir()
    (folder / "resultados.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
        encoding="utf-8")
    return folder


class _Block:
    def __init__(self, effect):
        self.effect = effect


class _Item:
    def __init__(self, ident, effects=()):
        self.id = ident
        self.blocks = [_Block(e) for e in effects]


class _Expected:
    def __init__(self, items):
        self.items = items


class _Exclusions:
    def __init__(self, ids):
        self.motives = {i: "pago" for i in ids}


def test_a_saved_matrix_run_is_recomputed_without_the_model_before_and_after(tmp_path):
    """REQ-101, REQ-102, REQ-107 (T-256): una corrida guardada de la matriz se recalcula sin
    modelo ni base: antes, con sus cifras; después, sin lo que está a revisión (D5), con la
    suprimida en otra fila como encontrada (D7), sin las técnicas aparte (D9) y con el archivo
    de exclusiones corregido (la fila que solo cubría una excluida pasa a sobrante)."""
    esperado = {"tipo": "esperado", "proceso": "completo"}
    lines = [
        dict(esperado, id="S-001", clase="formal", estado="encontrado", propuesto=1),
        dict(esperado, id="S-002", clase="formal", estado="encontrado", propuesto=2),
        dict(esperado, id="S-003", clase="formal", estado=ev.MANDATORY_REVIEW,
             causa=ev.PENDING),
        dict(esperado, id="S-004", clase="formal", estado="faltante", causa=ev.SUPPRESSED),
        dict(esperado, id="S-005", clase="formal", estado="faltante", causa=ev.SUPPRESSED),
        dict(esperado, id="S-T1", clase="tecnico", estado="encontrado", propuesto=3),
        {"tipo": "excluida", "id": "S-009", "motivo": "pago"},
        {"tipo": "propuesto", "numero": 1, "clase": "formal", "estado": "emparejado",
         "esperado": "S-001"},
        {"tipo": "propuesto", "numero": 2, "clase": "formal", "estado": "emparejado",
         "esperado": "S-002"},
        {"tipo": "propuesto", "numero": 3, "clase": "tecnico", "estado": "emparejado",
         "esperado": "S-T1"},
        {"tipo": "propuesto", "numero": 4, "clase": "formal", "estado": "sobrante"},
    ]
    folder = _saved_lines(tmp_path, lines)
    expected = _Expected([_Item("S-001"), _Item("S-002"), _Item("S-003"),
                          _Item("S-004", ["suprime"]), _Item("S-005"), _Item("S-T1"),
                          _Item("S-009")])

    result = ev.recompute_matrix_run(folder, expected, _Exclusions({"S-002", "S-009"}))

    before, after = result["before"], result["after"]
    assert before["recall"] == {"ok": 4, "total": 6, "rate": 4 / 6}     # con la revisión
    assert before["kept"] == {"ok": 3, "total": 4, "rate": 3 / 4}
    # Después: S-002 excluida (su fila 2 queda sobrante), S-003 a revisión no cuenta y S-004,
    # con bloque `suprime`, está en una fila suprimida; S-005 no tiene el bloque.
    assert after["recall"] == {"ok": 3, "total": 5, "rate": 3 / 5}
    assert after["found_with_review"] == {"ok": 4, "total": 5, "rate": 4 / 5}
    assert after["suppressed_elsewhere"] == 1
    assert after["kept"] == {"ok": 2, "total": 4, "rate": 2 / 4}
    assert after["found_without_technical"] == {"ok": 2, "total": 4, "rate": 2 / 4}
    assert after["kept_without_technical"] == {"ok": 1, "total": 3, "rate": 1 / 3}
    assert (before["excluded"], after["excluded"]) == (1, 2)
    assert after["without_line"] == []
    shrunk = ev.recompute_matrix_run(folder, expected, _Exclusions(set()))
    assert shrunk["after"]["without_line"] == ["S-009"]


def test_the_command_recomputes_a_saved_matrix_run_without_the_model(
        case, operator_user, tmp_path, monkeypatch):
    """REQ-107 (T-256): `medir_matriz --recalcular` no pide el procedimiento ni corre la
    propuesta: lee la corrida guardada y escribe las cifras de antes y de después."""
    from io import StringIO

    from django.core.management import call_command

    _, _, path, _ = case
    expected = ev.load_expected(path)
    first = expected.items[0].id
    folder = _saved_lines(tmp_path, [
        {"tipo": "esperado", "id": first, "clase": "formal", "estado": "encontrado",
         "propuesto": 1},
        {"tipo": "propuesto", "numero": 1, "clase": "formal", "estado": "emparejado",
         "esperado": first},
        {"tipo": "propuesto", "numero": 2, "clase": "formal", "estado": "sobrante"}])
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)
    monkeypatch.setattr(ev, "measure", lambda *a, **k: pytest.fail("corrió la propuesta"))
    out = StringIO()
    call_command("medir_matriz", "--usuario", "operador", "--esperada", str(path),
                 "--recalcular", str(folder), stdout=out)
    text = out.getvalue()
    assert "[antes] lista presente 100,0 % (1 de 1" in text
    assert "[después]" in text and "filas conservadas 50,0 % (1 de 2" in text
    assert not m.MatrixRun.objects.exists()



def test_the_matrix_recompute_asks_for_the_user_and_the_password_like_every_command(
        tmp_path, monkeypatch):
    """REQ-016 (de la 001), REQ-107 (T-256): `medir_matriz --recalcular` exige `--usuario` y pide
    la clave como todo comando, aunque solo lea archivos."""
    from io import StringIO
    from pathlib import Path

    from django.core.management import call_command
    from django.core.management.base import CommandError

    from evaluon.accounts import permissions

    fixture = Path(__file__).parent / "fixtures" / "matriz-esperada-sintetica.yaml"
    path = tmp_path / "matriz-esperada.yaml"
    path.write_text(fixture.read_text(encoding="utf-8").replace("__SHA256__", "a" * 64),
                    encoding="utf-8")
    first = ev.load_expected(path).items[0].id
    folder = _saved_lines(tmp_path, [
        {"tipo": "esperado", "id": first, "clase": "formal", "estado": "encontrado",
         "propuesto": 1},
        {"tipo": "propuesto", "numero": 1, "clase": "formal", "estado": "emparejado",
         "esperado": first}])
    with pytest.raises(CommandError, match="--usuario"):
        call_command("medir_matriz", "--esperada", str(path), "--recalcular", str(folder))
    asked = []
    monkeypatch.setattr(permissions, "authenticate_command",
                        lambda username: asked.append(username) or object())
    out = StringIO()
    call_command("medir_matriz", "--usuario", "operador", "--esperada", str(path),
                 "--recalcular", str(folder), stdout=out)
    assert asked == ["operador"]
    assert "[después] lista presente 100,0 % (1 de 1" in out.getvalue()
