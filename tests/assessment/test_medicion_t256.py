"""Medida honesta de la evaluación (T-256; REQ-103, REQ-104, REQ-105, REQ-107; mesa de comité
del 2026-10-12, `4-medicion.md` §2, §5 y §7). Datos inventados (P4): las pruebas comprueban el
contador, no al modelo."""

import json
import types
from io import StringIO

import pytest
import yaml
from django.core.management import call_command

from evaluon.accounts import permissions
from evaluon.assessment import evaluation as ev
from evaluon.assessment import models as am


class _Cite(types.SimpleNamespace):
    pass


def _result(outcome, doubt="", **fields):
    return am.Result(outcome=outcome, doubt=doubt, **fields)


def _technical(**fields):
    base = dict(requirement="M-008", result=am.Outcome.NO_DETERMINADO, base="tecnica",
                technical_document="hay", offered="si", dictamen="cumple")
    return ev.ExpectedPair(**{**base, **fields})


def _pair_on(rows, outcome, number=2, doubt=""):
    run = am.Run.objects.create(
        request=rows.request, offer=rows.run.offer, matrix_version=rows.version, number=number,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    return am.Result.objects.create(run=run, offer=run.offer, requirement=rows.requirement,
                                    outcome=outcome, doubt=doubt,
                                    exigence=am.Exigence.CONDICION)


def _yaml_file(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# --- D1, D2, D3 y D8 ---------------------------------------------------------------------------


def test_a_portal_pair_matches_only_when_the_result_is_the_expected_one(monkeypatch):
    """REQ-103 (T-256, D1): el par del Portal coincide solo si el resultado coincide; una cita
    del Portal con el valor no alcanza si el sistema no propuso «cumple»."""
    cites = [_Cite(portal_kind="cotizacion", text="Renglón 1: precio 7390.0000, cantidad 2700")]
    monkeypatch.setattr(ev, "_portal_cites", lambda r: cites)
    pair = ev.ExpectedPair(requirement="M-024", result=am.Outcome.CUMPLE, base="oferta",
                           portal={"tipo": "cotizacion", "valor": "7390.0000"})
    assert ev._match(pair, _result(am.Outcome.CUMPLE))
    assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.FALTA_COINCIDENCIA))


def test_missing_document_against_a_cumple_of_the_dictamen_is_a_wrong_conclusion():
    """REQ-104 (T-256, D2): «no se encontró el documento» contra un «cumple» del dictamen cuenta
    como conclusión errada; si la lista espera que falte (fila técnica sin documento), no."""
    pair = ev.ExpectedPair(requirement="M-008", result=am.Outcome.CUMPLE, base="externa")
    assert ev._contradiction(pair, _result(am.Outcome.SIN_DOCUMENTO))
    assert not ev._contradiction(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.SIN_DATO))
    missing = _technical(technical_document="no_se_encontro", offered="si")
    facts = {"documento_tecnico": "no_se_encontro", "renglon_ofertado": "si"}
    assert not ev._contradiction(missing, _result(am.Outcome.SIN_DOCUMENTO, facts=facts))
    assert "no se encontró el documento" in ev.LABELS["contradictions"]


def _external(rule, requirement_id=None):
    result = am.Result(outcome=am.Outcome.NO_DETERMINADO, doubt=am.Doubt.EXTERNO,
                       facts={"regla": rule})
    result.requirement_id = requirement_id
    return result


def _stub(results):
    return types.SimpleNamespace(results=types.SimpleNamespace(all=lambda: results))


def test_the_external_that_the_model_marks_is_not_discounted_and_both_figures_are_reported():
    """REQ-104 (T-256, D3): el «externo» del catálogo o de la lista espera la hoja de compliance
    y no cuenta; el que marca el modelo sí cuenta. Se informan las dos cifras: sobre todas las
    celdas y sobre las decidibles."""
    results = [_external("externo_catalogo"), _external("externo_modelo"),
               _external("externo_modelo", requirement_id=7),
               am.Result(outcome=am.Outcome.NO_DETERMINADO,
                         doubt=am.Doubt.PENDIENTE_INFORME_TECNICO),
               am.Result(outcome=am.Outcome.NO_DETERMINADO, doubt=am.Doubt.SIN_DATO),
               am.Result(outcome=am.Outcome.CUMPLE)]

    counts = ev.cell_counts(_stub(results), external={7})

    assert (counts["total"], counts["undetermined"], counts["waiting_document"]) == (6, 5, 3)
    assert counts["model_external"] == 1
    cells = ev.aggregate_015([{"cells": counts}])["cells"]
    assert cells["counted"] == 2
    assert cells["ratio"] == {"ok": 2, "total": 6, "rate": 2 / 6}
    assert cells["ratio_decidable"] == {"ok": 2, "total": 3, "rate": 2 / 3}


@pytest.mark.django_db
def test_a_cumple_cited_to_the_portal_is_not_without_citation(rows, monkeypatch):
    """REQ-053, REQ-103 (T-256, D8): el «cumple» citado al Portal no cuenta como «sin cita»; sin
    ninguna cita, sí."""
    result = _pair_on(rows, am.Outcome.CUMPLE)
    pair = ev.ExpectedPair(requirement="M-001", result=am.Outcome.CUMPLE, base="oferta")
    monkeypatch.setattr(ev, "_portal_cites", lambda r: [
        _Cite(portal_kind="total", text="Total de la oferta: 535000.00 ARS", portal_item=None)])
    record = ev.measure_pair(pair, result, rows.requirement, result.offer, ev.PageFinder(),
                             [], {})
    assert record["sin_cita"] is False
    monkeypatch.setattr(ev, "_portal_cites", lambda r: [])
    record = ev.measure_pair(pair, result, rows.requirement, result.offer, ev.PageFinder(),
                             [], {})
    assert record["sin_cita"] is True


# --- Exactitud por celda contra la Comisión de prueba ---------------------------------------------


COMMISSION = [
    {"oferta": 1, "fila": 10, "resultado": "cumple", "nota": "Cotiza en pesos (inventado)."},
    {"oferta": 1, "fila": 16, "resultado": "cumple"},
    {"oferta": 1, "fila": 22, "resultado": "cumple"},
    {"oferta": 1, "fila": 80, "resultado": "no_aplica"},
    {"oferta": 2, "fila": 24, "resultado": "no_se_encontro_documento"},
    {"oferta": 2, "fila": 123, "resultado": "cumple"},
]


def _commission_file(tmp_path, cells, **fields):
    data = {"caso": "caso-00", "procedimiento": "P-1", "huella": ev.cells_fingerprint(cells),
            "visto_bueno": "", "celdas": cells, **fields}
    return _yaml_file(tmp_path / "celdas-comision.yaml", data)


def test_the_commission_cells_need_their_fingerprint_and_approval(tmp_path):
    """REQ-104, REQ-107 (T-256): las decisiones de la Comisión de prueba se leen con su huella;
    sin visto bueno no se usan en una medición, y una huella que no es la de las celdas se
    rechaza."""
    path = _commission_file(tmp_path, COMMISSION)
    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_commission_cells(path)
    loaded = ev.load_commission_cells(path, require_approval=False)
    assert loaded.cells[(1, 80)] == "no_aplica"
    assert loaded.cells[(2, 24)] == am.Outcome.SIN_DOCUMENTO
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["celdas"][0]["resultado"] = "no_cumple"
    _yaml_file(path, data)
    with pytest.raises(ev.ExpectedError, match="huella"):
        ev.load_commission_cells(path, require_approval=False)


def test_cell_accuracy_counts_exact_abstained_and_wrong_and_lists_the_exact_to_read(tmp_path):
    """REQ-104, REQ-107 (T-256): exacta si el resultado es el de la Comisión (con cita o sin
    cita, y todas listadas para leer si la cita sostiene lo afirmado); abstención si es «no
    determinado»; errada en otro caso, también «no se encontró el documento» contra «no
    aplica». Las filas excluidas no cuentan y se informan aparte."""
    commission = ev.load_commission_cells(_commission_file(tmp_path, COMMISSION),
                                          require_approval=False)
    cells = [
        ev.observed_cell(1, 10, am.Outcome.CUMPLE, offer_cites=["Cotiza en pesos."]),
        ev.observed_cell(1, 16, am.Outcome.CUMPLE),
        ev.observed_cell(1, 22, am.Outcome.NO_DETERMINADO, doubt=am.Doubt.SIN_DATO),
        ev.observed_cell(1, 80, am.Outcome.SIN_DOCUMENTO),
        ev.observed_cell(2, 24, am.Outcome.SIN_DOCUMENTO),
        ev.observed_cell(2, 123, am.Outcome.CUMPLE, portal_cites=["Garantía: monto 1"]),
    ]

    accuracy = ev.cell_accuracy(cells, commission, excluded_rows={123})

    assert accuracy["total"] == 5
    assert (accuracy["exact"]["ok"], accuracy["abstained"]["ok"], accuracy["wrong"]["ok"]) == (
        3, 1, 1)
    assert accuracy["exact_cells"] == [(1, 10), (1, 16), (2, 24)]
    assert accuracy["abstained_cells"] == [(1, 22)]
    assert accuracy["wrong_cells"] == [(1, 80, "no_aplica", am.Outcome.SIN_DOCUMENTO)]
    assert (accuracy["exact_with_citation"], accuracy["exact_without_citation"]) == (1, 2)
    assert accuracy["excluded"] == [(2, 123)]
    sample = ev.write_exact_sample(tmp_path, accuracy).read_text(encoding="utf-8")
    assert "¿La cita sostiene lo afirmado?" in sample and "Cotiza en pesos (inventado)." in sample
    assert sample.count("\n| 1 |") + sample.count("\n| 2 |") == 3
    assert "exactas 60,0 %" in ev.accuracy_lines(accuracy)[0]


# --- Filas agregadas solo para la medida ------------------------------------------------------------


def test_the_cell_exclusions_file_carries_rows_with_their_motive(tmp_path):
    """REQ-103 a REQ-105 (T-256): el archivo de exclusión de celdas nombra las filas agregadas
    solo para la medida, cada una con su motivo; sin motivo o sin visto bueno, no se usa."""
    data = {"visto_bueno": "Coordinador sintético", "filas": [
        {"fila": 123, "requisito": "M-020", "motivo": "agregada solo para la medida"},
        {"fila": 124, "requisito": "M-039", "motivo": "encabezado de tabla"}]}
    path = _yaml_file(tmp_path / "exclusiones-celdas.yaml", data)
    loaded = ev.load_cell_exclusions(path)
    assert loaded.rows == {123: "agregada solo para la medida", 124: "encabezado de tabla"}
    assert loaded.ids == {"M-020", "M-039"}
    data["filas"][0]["motivo"] = ""
    _yaml_file(path, data)
    with pytest.raises(ev.ExpectedError, match="motivo"):
        ev.load_cell_exclusions(path)
    data["filas"][0]["motivo"] = "x"
    data["visto_bueno"] = "pendiente"
    _yaml_file(path, data)
    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_cell_exclusions(path)


def test_an_excluded_row_leaves_the_cells_counts():
    """REQ-104 (T-256): una celda de una fila excluida no entra en el «no determinado» y se
    cuenta aparte."""
    kept = am.Result(outcome=am.Outcome.NO_DETERMINADO, doubt=am.Doubt.SIN_DATO)
    kept.requirement_id = 1
    left = am.Result(outcome=am.Outcome.NO_DETERMINADO, doubt=am.Doubt.SIN_DATO)
    left.requirement_id = 2
    counts = ev.cell_counts(_stub([kept, left]), excluded={2})
    assert (counts["total"], counts["undetermined"], counts["excluded"]) == (1, 1, 1)


# --- Recálculo de una corrida guardada, sin GPU ------------------------------------------------------


CELLS_TXT = """O1 R10 no_determinado sin_dato regla=
   expl: Falta el dato (inventado).
   cita pliego : Las cotizaciones se deberán realizar en pesos.
   cita portal : Total de la oferta: 1000.00 ARS
O1 R22 sin_documento  regla=
   expl: No se encontró (inventado).
O1 R29 cumple  regla=portal_cumple
   cita portal : Garantía: tipo Mantenimiento oferta, forma Seguros, monto 50.00
O1 R33 no_determinado externo regla=externo_modelo
O1 R34 cumple  regla=forma_garantia_no_elegida
O1 R47 no_determinado falta_coincidencia regla=portal_falta_coincidencia
   cita portal : Renglón 1: precio 10.0000, cantidad 100.0000
O1 R90 no_determinado pendiente_informe_tecnico regla=tecnico_hechos
O1 R123 cumple  regla=portal_cumple
   cita portal : Garantía: tipo Mantenimiento oferta, forma Seguros, monto 50.00

TOTAL 8 {}
"""


def _saved_run(tmp_path):
    """Una corrida guardada inventada: ocho celdas (las filas 10 a 123 de la oferta 1, con los
    resultados 101 a 108 en orden de fila) y cuatro pares de la lista."""
    folder = tmp_path / "20261012-000000-abc1234"
    folder.mkdir()
    (folder / ev.CELLS_FILE).write_text(CELLS_TXT, encoding="utf-8")
    base = {"base": "oferta", "via": "expreso", "motivo_esperado": "", "no_aplica": False,
            "contradicciones_hecho": [], "hechos": {}, "opinion": "", "dictamen": "cumple",
            "citas_portal": 0, "citas_oferta": 0, "sin_cita": False, "contradiccion": False,
            "portal_celda": None}
    records = [
        dict(base, oferta=1, requisito="M-024", tipo="portal", esperado="cumple",
             obtenido="no_determinado", motivo="falta_coincidencia", coincide=True,
             resultado_pk=106, citas_portal=1),
        dict(base, oferta=1, requisito="M-008", tipo="externo", base="externa",
             esperado="cumple", obtenido="sin_documento", motivo="", coincide=False,
             resultado_pk=102),
        dict(base, oferta=1, requisito="M-012", tipo="oferta", esperado="cumple",
             obtenido="cumple", motivo="", coincide=True, resultado_pk=103, citas_portal=1,
             sin_cita=True),
        dict(base, oferta=1, requisito="M-020", tipo="oferta", esperado="cumple",
             obtenido="cumple", motivo="", coincide=True, resultado_pk=108, citas_portal=1),
    ]
    (folder / "resultados.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    return folder


def _recompute_inputs(tmp_path):
    exclusions = _yaml_file(tmp_path / "exclusiones-celdas.yaml", {
        "visto_bueno": "Coordinador sintético",
        "filas": [{"fila": 123, "requisito": "M-020", "motivo": "agregada solo para la medida"}]})
    portal = _yaml_file(tmp_path / "celdas-portal.yaml", {
        "procedimiento": "P-1", "visto_bueno": "Coordinador sintético", "celdas": [
            {"oferta": 1, "fila": 29, "tipo": "garantia", "valor": "50.00", "coincide": True},
            {"oferta": 1, "fila": 47, "tipo": "cotizacion", "valor": "10.0000",
             "coincide": True},
            {"oferta": 1, "fila": 123, "tipo": "garantia", "valor": "50.00",
             "coincide": True}]})
    commission = _commission_file(tmp_path, [
        {"oferta": 1, "fila": 22, "resultado": "cumple"},
        {"oferta": 1, "fila": 29, "resultado": "cumple"},
        {"oferta": 1, "fila": 33, "resultado": "no_aplica"},
        {"oferta": 1, "fila": 34, "resultado": "no_aplica"}])
    return exclusions, portal, commission


def test_a_saved_run_is_recomputed_without_the_model_before_and_after(tmp_path):
    """REQ-103, REQ-104, REQ-107 (T-256): una corrida guardada se recalcula sin GPU ni base desde
    `resultados.jsonl` y `celdas-todas.txt`: con las reglas de antes da sus cifras y con las
    corregidas aplica D1, D2, D3, D8 y la exclusión de filas; con la lista de la Comisión, la
    exactitud por celda."""
    folder = _saved_run(tmp_path)
    exclusions, portal, commission = _recompute_inputs(tmp_path)

    result = ev.recompute_run(
        folder, portal_cells=ev.load_portal_cells(portal),
        commission=ev.load_commission_cells(commission, require_approval=False),
        cell_exclusions=ev.load_cell_exclusions(exclusions))

    assert result["pairs_mapped"] is True
    before, after = result["before"], result["after"]
    assert (before["match"]["ok"], after["match"]["ok"]) == (3, 1)          # D1 y R123 fuera
    assert (before["contradictions"], after["contradictions"]) == (0, 1)    # D2
    assert (before["no_citation"], after["no_citation"]) == (1, 0)          # D8
    assert before["cells"]["ratio"] == {"ok": 2, "total": 7, "rate": 2 / 7}
    assert after["cells"]["ratio"] == {"ok": 3, "total": 6, "rate": 3 / 6}  # D3 y R123 fuera
    assert after["cells"]["ratio_decidable"] == {"ok": 3, "total": 5, "rate": 3 / 5}
    assert before["portal_cumple"] == {"ok": 2, "total": 3, "rate": 2 / 3}
    assert after["portal_cumple"] == {"ok": 1, "total": 2, "rate": 0.5}
    assert (after["excluded_cells"], after["excluded_pairs"]) == (1, 1)
    accuracy = result["accuracy_after"]
    assert accuracy["exact_cells"] == [(1, 29), (1, 34)]
    assert accuracy["abstained_cells"] == [(1, 33)]
    assert accuracy["wrong_cells"] == [(1, 22, am.Outcome.CUMPLE, am.Outcome.SIN_DOCUMENTO)]


@pytest.mark.django_db
def test_the_command_recomputes_a_saved_run_without_the_model(
        tmp_path, operator_user, monkeypatch):
    """REQ-107 (T-256): `medir_evaluacion --recalcular` lee la corrida guardada y escribe las
    cifras de antes y de después sin pedir la evaluación ni usar la GPU."""
    from tests.tenders.conftest import TEST_PASSWORD

    folder = _saved_run(tmp_path)
    exclusions, portal, commission = _recompute_inputs(tmp_path)
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    monkeypatch.setattr(ev, "run_evaluation", lambda *a, **k: pytest.fail("usó el modelo"))
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--recalcular",
                 str(folder), "--celdas-portal", str(portal), "--celdas-comision",
                 str(commission), "--exclusiones-celdas", str(exclusions), stdout=out)
    text = out.getvalue()
    assert "antes" in text and "después" in text
    assert "«No determinado» sobre las decidibles: 3 de 5" in text
    assert "Exactitud por celda" in text and "visto bueno pendiente" in text
