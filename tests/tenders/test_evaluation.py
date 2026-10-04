"""Pruebas de la medición de la propuesta de matriz (T-077; REQ-024, REQ-025).

Todo es sintético (P4): un pliego de tres renglones, una lista esperada de
`tests/tenders/fixtures/` y el doble del modelo con guion. La lista trae los campos extra de
las listas reales (anexos con `*`, circulares, `origen`, `rol`, `nota`).
"""

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from evaluon.tenders import evaluation as ev
from evaluon.tenders import models as m
from tests.tenders.scripted import (
    ENTREGA,
    GARANTIA,
    MULTA,
    item,
    load_and_read,
    make_procedure,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)
from evaluon.tenders.proposal.extraction import ALL_ITEMS

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "matriz-esperada-sintetica.yaml"
FILE = "Pliego sintético.pdf"


@pytest.fixture
def case(operator_user, script, tmp_path):
    """El pliego leído, el guion del modelo y la lista esperada sintética escrita en
    `tmp_path`. El modelo: la garantía como formal (la lista la espera económica), la multa
    en una sola fila que junta dos condiciones, la entrega como técnica para todos los
    renglones, y el resto descartado."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, three_items_pdf(), title="Pliego sintético")
    script.when(GARANTIA, item(requirements=[("garantía del 5 % del monto", "formal")]))
    script.when(MULTA, item(requirements=[
        ("En caso de atraso se aplicará una multa del 1 % diario", "economico")]))
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))
    text = FIXTURE.read_text(encoding="utf-8").replace("__SHA256__", document.file_sha256)
    path = tmp_path / "esperado" / "matriz-esperada.yaml"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")
    return procedure, document, path, text


def write(path, text):
    path.write_text(text, encoding="utf-8")


def by_id(report, level="media"):
    result = next(r for r in report.results if r["level"] == level)
    return {line["id"]: line for line in result["measures"]["lines"]
            if line["tipo"] == "esperado"}


def run_measure(user, procedure, path, tmp_path, levels=("media",)):
    expected = ev.load_expected(path)
    return ev.measure(user, procedure, expected, list(levels), tmp_path / "corridas",
                      commit="abc1234")


# --- Lectura y comprobación de la lista ------------------------------------------------------


def test_list_with_extra_fields_is_read_and_checked(case):
    """REQ-024: la lista con anexos `*`, circulares, `origen`, `rol` y `nota` se lee y se
    comprueba; lo tentativo de las circulares se informa y no bloquea."""
    procedure, _, path, _ = case

    expected = ev.load_expected(path)
    verification = ev.verify_expected(expected, procedure)

    assert verification.ok, verification.problems
    assert verification.counts["anchors"] == 5 and verification.counts["anchors_ok"] == 5
    assert verification.counts["circular_anchors"] == 2
    assert any("circular" in note for note in verification.notes)
    assert [i.id for i in expected.items if i.from_circular] == ["S-006"]
    assert expected.annexes[0].wildcard


def test_wildcard_matches_any_segment_of_the_document_or_prefix():
    """REQ-024: `*` empareja con cualquier tramo del documento y `a/b/*` con los de `a/b`."""
    whole = ev.Ref("D", "*")
    prefix = ev.Ref("D", "sec-iv/anexo-vii/*")

    assert whole.matches("D", "sec-i/1") and not whole.matches("E", "sec-i/1")
    assert prefix.matches("D", "sec-iv/anexo-vii/3")
    assert prefix.matches("D", "sec-iv/anexo-vii")
    assert not prefix.matches("D", "sec-iv/anexo-viii/3")


def test_anchor_that_is_not_there_blocks(case, operator_user, tmp_path):
    """REQ-024: un ancla que no está bloquea, en la comprobación y antes de medir."""
    procedure, _, path, text = case
    write(path, text.replace("garantía del 5 % del monto", "garantía del 9 % inexistente"))

    verification = ev.verify_expected(ev.load_expected(path), procedure)
    assert not verification.ok
    assert any("S-001" in problem for problem in verification.problems)
    with pytest.raises(ev.MeasurementRefused):
        run_measure(operator_user, procedure, path, tmp_path)
    assert not m.MatrixRun.objects.exists()


def test_missing_technical_segment_blocks(case, operator_user):
    """REQ-024: un tramo técnico que no existe bloquea; uno de circular, no."""
    procedure, _, path, text = case
    write(path, text.replace("tramos: [sec-iii/1, sec-iii/1.1]",
                             "tramos: [sec-iii/1, sec-iii/9.9]"))

    verification = ev.verify_expected(ev.load_expected(path), procedure)

    assert any("sec-iii/9.9" in problem for problem in verification.problems)


def test_different_sha256_blocks(case):
    """REQ-024: la huella del archivo tiene que coincidir con la del documento cargado."""
    procedure, document, path, text = case
    write(path, text.replace(document.file_sha256, "f" * 64))

    verification = ev.verify_expected(ev.load_expected(path), procedure)

    assert any("huella" in problem for problem in verification.problems)


def test_list_without_approval_is_not_measured(case, operator_user, tmp_path):
    """REQ-024: una lista sin visto bueno no se mide."""
    procedure, _, path, text = case
    write(path, text.replace('visto_bueno: "responsable sintético, 2026-10-03"',
                             'visto_bueno: ""'))

    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_expected(path)
    assert ev.load_expected(path, require_approval=False).approval == ""
    assert not m.MatrixRun.objects.exists()


# --- Emparejamiento y faltantes ----------------------------------------------------------------


def test_row_that_joins_two_conditions_counts_one_and_leaves_the_other_grouped(
        case, operator_user, tmp_path):
    """REQ-024: una fila formal/económica que junta dos condiciones cuenta una sola ancla
    (emparejamiento uno a uno) y deja la otra con causa `agrupado`."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    states = {lines["S-003"]["estado"], lines["S-004"]["estado"]}
    assert states == {"encontrado", "faltante"}
    missing = lines["S-003"] if lines["S-003"]["estado"] == "faltante" else lines["S-004"]
    assert missing["causa"] == ev.GROUPED


def test_discarded_segment_leaves_its_anchor_with_that_cause(case, operator_user, tmp_path):
    """REQ-028: un tramo descartado deja sus anclas faltantes con esa causa y el motivo."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-002"]
    assert line["estado"] == "faltante"
    assert line["causa"] == ev.DISCARDED
    assert line["detalle"] == "dato_procedimiento"
    result = report.results[0]["measures"]
    assert result["causes"][ev.DISCARDED] == 1


def test_technical_rows_match_by_item_and_report_missing_segments(case, operator_user,
                                                                 tmp_path):
    """REQ-024: la fila técnica del renglón 2 empareja con el esperado del renglón 2 aunque
    le falte un tramo, y el tramo faltante se informa; el renglón 4 no tiene fila."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    assert lines["S-T1"]["estado"] == "encontrado"
    assert lines["S-T1"]["tramos_faltantes"] == []
    assert lines["S-T2"]["estado"] == "encontrado"
    assert lines["S-T2"]["propuesto"] is not None
    assert "sec-iii/3" in lines["S-T2"]["tramos_faltantes"]
    assert lines["S-T4"]["estado"] == "faltante"
    assert lines["S-T4"]["causa"] == ev.ITEM_WITHOUT_ROW
    measures = report.results[0]["measures"]
    assert measures["technical_missing"]["sec-iii/3"] >= 1
    assert 0 < measures["technical_tramos"]["ok"] < measures["technical_tramos"]["total"]


def test_wrong_class_is_found_and_reported(case, operator_user, tmp_path):
    """REQ-024: la garantía propuesta como formal cuenta como encontrada con clase
    equivocada; la condición cubierta por una fila técnica, también, y no bloquea."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    assert lines["S-001"]["estado"] == "encontrado"
    assert lines["S-001"]["clase_propuesta"] == "formal"
    assert lines["S-001"]["clase_correcta"] is False
    assert lines["S-005"]["estado"] == "encontrado"
    assert lines["S-005"]["clase_propuesta"] == "tecnico"
    assert lines["S-005"]["clase_correcta"] is False
    measures = report.results[0]["measures"]
    assert measures["class_wrong_found"] == 1
    assert measures["class"]["ok"] < measures["class"]["total"]


def test_circular_rows_are_reported_apart(case, operator_user, tmp_path):
    """REQ-031: una fila `origen: circular` no entra en los encontrados mientras la propuesta
    no use circulares (T-083): se informa aparte."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    assert by_id(report)["S-006"]["causa"] == ev.CIRCULAR_UNMEASURED
    measures = report.results[0]["measures"]
    assert measures["circular_unmeasured"] == 1
    assert measures["found"]["total"] == 8


def test_found_proportion_uses_wilson_of_the_first_feature(case, operator_user, tmp_path):
    """REQ-024: la proporción lleva su intervalo de Wilson al 95 %, el de la 001."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "IC 95 %" in summary
    assert "Requisitos encontrados" in summary


# --- Cita literal, cobertura, tiempos ----------------------------------------------------------


def test_every_proposed_quote_is_literal_and_every_segment_has_a_disposition(
        case, operator_user, tmp_path):
    """REQ-025: la cita propuesta es igual al recorte, cae en su tramo y tiene página;
    todo tramo tiene disposición."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    measures = report.results[0]["measures"]
    assert measures["literal"]["total"] > 0
    assert measures["literal"]["ok"] == measures["literal"]["total"]
    coverage = measures["coverage"]
    assert coverage["with_disposition"] == coverage["segments"] > 0
    assert set(coverage["by_source"]) <= {"modelo", "regla"}


def test_timings_are_per_pass_per_page_and_extrapolated(case, operator_user, tmp_path):
    """REQ-024: tiempos por pasada, por página y por tramo, y extrapolación a 50 páginas."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    timings = report.results[0]["timings"]
    assert "extraccion" in timings["passes"] and "total" in timings["passes"]
    assert timings["pages"] > 0
    assert timings["extrapolated_50_pages_seconds"] >= timings["seconds_per_page"]
    assert "provisorio" in (report.folder / "resumen.md").read_text(encoding="utf-8")


# --- Corrida -----------------------------------------------------------------------------------


def test_run_uses_eval_channel_and_discards_its_versions(case, operator_user, tmp_path):
    """REQ-024: cada nivel corre con el canal `eval`; las versiones quedan descartadas, con
    su hecho de registro, y se puede medir otra vez."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path, levels=("media", "alta"))

    runs = list(m.MatrixRun.objects.order_by("id"))
    assert [(r.level, r.channel, r.job_id) for r in runs] == [
        ("media", "eval", None), ("alta", "eval", None)]
    versions = m.MatrixVersion.objects.filter(procedure=procedure)
    assert versions.count() == 2
    assert set(versions.values_list("status", flat=True)) == {"discarded"}
    assert all(v.discarded_by_id == operator_user.pk for v in versions)
    assert [row["verdict"] for row in report.comparison] == ["base", "no mejora"]
    assert report.comparison[1]["against"] == "media"
    again = run_measure(operator_user, procedure, path, tmp_path)
    assert again.folder != report.folder


def test_open_draft_refuses_the_measurement(case, operator_user, tmp_path):
    """REQ-024: con un borrador abierto no se mide (la base admite uno por procedimiento)."""
    procedure, _, path, _ = case
    m.MatrixVersion.objects.create(procedure=procedure, number=1, level="media",
                                   created_by=operator_user)

    with pytest.raises(ev.MeasurementRefused, match="borrador"):
        run_measure(operator_user, procedure, path, tmp_path)


def test_run_folder_has_the_four_files(case, operator_user, tmp_path):
    """REQ-024: la carpeta de la corrida trae parametros.json, resultados.jsonl,
    resumen.md y resumen-publico.md."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    names = sorted(p.name for p in report.folder.iterdir())
    assert names == ["parametros.json", "resultados.jsonl", "resumen-publico.md",
                     "resumen.md"]
    parameters = json.loads((report.folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["niveles"] == ["media"] and parameters["commit"] == "abc1234"
    rows = [json.loads(line) for line in
            (report.folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["tipo"] for row in rows} >= {"esperado", "propuesto"}
    assert "abc1234" in report.folder.name


def test_public_summary_has_no_text_of_the_tender(case, operator_user, tmp_path):
    """P4: `resumen-publico.md` no contiene ningún texto del pliego: ni un ancla ni una cita
    propuesta (se busca cada una); el completo sí puede."""
    procedure, document, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    expected = ev.load_expected(path)
    for item_ in expected.items:
        if item_.anchor:
            assert item_.anchor not in public
    quotes = m.RequirementQuote.objects.filter(requirement__version__procedure=procedure)
    assert quotes.exists()
    for quote in quotes:
        assert quote.text not in public
        assert quote.text[:25] not in public
    assert "S-002" in public and ev.DISCARDED in public and "sec-i" in public
    assert "a los 90 días corridos" in (report.folder / "resumen.md").read_text(
        encoding="utf-8")


# --- Comando -----------------------------------------------------------------------------------


def test_command_verifies_the_list_without_the_model(case, operator_user, monkeypatch,
                                                    capsys, script):
    """REQ-024: `--verificar-esperada` informa las cuentas y no usa el modelo."""
    procedure, _, path, _ = case
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)
    calls_before = len(script.calls)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), verificar_esperada=True)

    out = capsys.readouterr().out
    assert "Anclas encontradas: 5 de 5" in out
    assert "La lista se puede usar." in out
    assert len(script.calls) == calls_before
    assert not m.MatrixRun.objects.exists()


def test_command_measures_and_prints_the_counts(case, operator_user, monkeypatch, capsys):
    """REQ-024: el comando mide, guarda la corrida y muestra las cuentas."""
    procedure, _, path, _ = case
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), niveles="media")

    out = capsys.readouterr().out
    assert "Corrida guardada en" in out and "media: encontrados" in out
    assert (path.parent.parent / "corridas").is_dir()


# --- Errores, umbral, rol, citas amplias, un renglón una fila (verificación de T-077) ---------


def test_failed_proposal_does_not_put_its_message_in_the_public_summary(
        case, operator_user, tmp_path, monkeypatch):
    """P4: si la propuesta falla, el resumen público trae solo la clase de la excepción;
    el mensaje, que puede traer texto del pliego, queda en `resumen.md`."""
    procedure, _, path, _ = case

    def boom(run, **kwargs):
        raise ValueError("salida inválida: " + GARANTIA)

    monkeypatch.setattr(ev.proposal, "propose", boom)

    report = run_measure(operator_user, procedure, path, tmp_path)

    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    full = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert GARANTIA not in public and "salida inválida" not in public
    assert "ValueError" in public
    assert GARANTIA in full
    assert any("falló" in reason for reason in report.blocking)


def test_found_line_carries_the_wilson_interval_of_the_first_feature(case, operator_user,
                                                                    tmp_path):
    """REQ-024: la línea de requisitos encontrados trae el intervalo de Wilson de la 001."""
    from evaluon.queries.evaluation import wilson_interval

    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    found = report.results[0]["measures"]["found"]
    low, high = wilson_interval(found["ok"], found["total"])
    line = next(row for row in (report.folder / "resumen.md").read_text(
        encoding="utf-8").splitlines() if row.startswith("- Requisitos encontrados"))
    assert f"{found['ok']} de {found['total']}" in line
    assert f"{low * 100:.1f}".replace(".", ",") in line
    assert f"{high * 100:.1f}".replace(".", ",") in line


def test_quote_must_cover_half_of_the_anchor_to_match():
    """REQ-024: la cita tiene que cubrir al menos la mitad del ancla; 5 % no alcanza."""
    from types import SimpleNamespace as NS

    reading = NS(pk=1)
    entry = NS(span=(100, 120), reading=reading)  # ancla de 20 caracteres

    def pairs(start, end):
        return ev._pairs([entry], [NS(span=(start, end), reading=reading, quotes=[NS(
            char_start=start, char_end=end)])])

    assert pairs(110, 130) == {0: 0}    # 10 de 20
    assert pairs(111, 131) == {}        # 9 de 20
    assert pairs(119, 139) == {}        # 1 de 20 (5 %)


def test_role_is_checked_before_measuring(case, operator_user, evaluator_user,
                                          no_commission_user, tmp_path):
    """Roles: sin rol de la Comisión se rechaza y no queda ninguna propuesta; el evaluador
    también mide."""
    from evaluon.accounts.permissions import RoleRejected

    procedure, _, path, _ = case

    with pytest.raises(RoleRejected):
        run_measure(no_commission_user, procedure, path, tmp_path)
    assert not m.MatrixRun.objects.exists()
    assert run_measure(evaluator_user, procedure, path, tmp_path).results[0]["level"] == "media"


def test_wide_quotes_are_counted_apart_from_the_literal_quote_measure(
        case, operator_user, tmp_path, script):
    """REQ-025: una cita amplia (el modelo copió algo que no está en el tramo) se cuenta
    aparte y no entra en el denominador de la cita literal."""
    from tests.tenders.scripted import PAGO

    procedure, _, path, _ = case
    script.when(PAGO, item(requirements=[("texto que no está en el tramo", "formal")]))

    report = run_measure(operator_user, procedure, path, tmp_path)

    measures = report.results[0]["measures"]
    all_quotes = m.RequirementQuote.objects.filter(requirement__version__procedure=procedure)
    wide = all_quotes.filter(quote_flag="cita_amplia").count()
    assert wide == 1 and measures["wide"]["total"] == 1
    assert measures["literal"]["total"] == all_quotes.count() - wide


def test_two_technical_entries_for_one_item_are_a_list_error(case):
    """REQ-024: la regla es una fila por renglón: dos entradas técnicas del mismo renglón
    son un error de la lista y la comprobación lo informa."""
    procedure, _, path, text = case
    write(path, text.replace("    renglon: 4\n", "    renglon: 1\n"))

    verification = ev.verify_expected(ev.load_expected(path), procedure)

    assert not verification.ok
    assert any("renglón 1" in problem and "S-T1" in problem and "S-T4" in problem
               for problem in verification.problems)


def test_extrapolation_counts_the_real_pages_of_the_reading(case, operator_user, tmp_path):
    """REQ-030 (T-089): con una lectura de 20 páginas y 100 s en total, el tiempo por página es
    5 s y la extrapolación a 50 páginas es el tiempo × 2,5; no se cuentan las claves del
    diccionario de la lectura."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    reading = m.Reading.objects.get(pk=run.documents[0]["reading"])
    reading.pages = {**reading.pages, "pages": [{"number": n} for n in range(1, 21)]}
    reading.save(update_fields=["pages"])
    run.timings = {"extraccion": 90.0, "total": 100.0}

    timings = ev.timing_summary(run)

    assert timings["pages"] == 20
    assert timings["seconds_per_page"] == 5.0
    assert timings["extrapolated_50_pages_seconds"] == 250.0


# --- Comparar niveles medidos en corridas separadas (T-091) ----------------------------------


def _fake_run(folder, expected, procedure, level, found, leftovers):
    """Una corrida guardada sintética: solo `parametros.json` y `resultados.jsonl`."""
    folder.mkdir(parents=True)
    (folder / "parametros.json").write_text(json.dumps(
        {"procedimiento": procedure.number, "lista": {"sha256": expected.sha256}}),
        encoding="utf-8")
    rows = [{"nivel": level, "tipo": "esperado", "id": f"M-{n}", "estado": "encontrado"}
            for n in range(found)]
    rows += [{"nivel": level, "tipo": "propuesto", "numero": n, "estado": "sobrante"}
             for n in range(leftovers)]
    (folder / "resultados.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_levels_measured_in_separate_runs_are_compared(case, operator_user, tmp_path):
    """REQ-030: media, alta y exigente en carpetas separadas: el resumen compara con la última
    corrida de cada nivel y aplica la regla (mejora si encuentra más, o lo mismo con menos
    sobrantes); no lleva texto del pliego."""
    procedure, _, path, _ = case
    expected = ev.load_expected(path)
    runs = tmp_path / "corridas"
    _fake_run(runs / "20260101-000000-aaa", expected, procedure, "media", 1, 3)
    _fake_run(runs / "20260102-000000-bbb", expected, procedure, "media", 2, 3)  # más reciente
    _fake_run(tmp_path / "otra" / "20260103-000000-ccc", expected, procedure,
              "exigente", 2, 1)

    report = ev.measure(operator_user, procedure, expected, ["alta"], runs, commit="abc1234",
                        compare_with=[tmp_path / "otra"])

    row = report.comparison[0]
    found = report.results[0]["measures"]["found"]["ok"]
    leftovers = report.results[0]["measures"]["leftovers"]
    assert row["against"] == "media" and row["against_run"] == "20260102-000000-bbb"
    expected_verdict = "mejora" if (found, -leftovers) > (2, -3) else "no mejora"
    assert row["verdict"] == expected_verdict
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "respecto de media (corrida 20260102-000000-bbb)" in public
    quotes = m.RequirementQuote.objects.filter(requirement__version__procedure=procedure)
    for quote in quotes:
        assert quote.text[:25] not in public


def test_comparison_rule_with_earlier_runs():
    """REQ-030: un nivel se ofrece solo si mejora al anterior; el anterior puede venir de una
    corrida guardada; sin corridas previas el nivel es la base."""
    def result(level, found, leftovers):
        return {"level": level, "measures": {"found": {"ok": found}, "leftovers": leftovers}}

    order = ["media", "alta", "exigente"]
    earlier = {"media": {"found": 40, "leftovers": 5, "run": "r1"},
               "alta": {"found": 45, "leftovers": 6, "run": "r2"}}

    exigente = ev.compare_levels([result("exigente", 45, 6)], earlier, order)[0]
    assert (exigente["verdict"], exigente["against"]) == ("no mejora", "alta")
    exigente = ev.compare_levels([result("exigente", 45, 4)], earlier, order)[0]
    assert exigente["verdict"] == "mejora" and exigente["against_run"] == "r2"
    alta = ev.compare_levels([result("alta", 46, 9)], earlier, order)[0]
    assert (alta["verdict"], alta["against"]) == ("mejora", "media")
    assert ev.compare_levels([result("alta", 46, 9)], {}, order)[0]["verdict"] == "base"


def test_runs_of_another_list_or_procedure_are_not_used(case, operator_user, tmp_path):
    """REQ-030: no se compara contra corridas de otra lista (otra huella) ni con una corrida
    que falló."""
    procedure, _, path, _ = case
    expected = ev.load_expected(path)
    runs = tmp_path / "corridas"
    _fake_run(runs / "20260101-000000-aaa", expected, procedure, "media", 2, 0)
    other = runs / "20260102-000000-bbb"
    _fake_run(other, expected, procedure, "media", 2, 0)
    (other / "parametros.json").write_text(json.dumps(
        {"procedimiento": procedure.number, "lista": {"sha256": "otra"}}), encoding="utf-8")
    failed = runs / "20260103-000000-ccc"
    _fake_run(failed, expected, procedure, "media", 0, 0)
    (failed / "resultados.jsonl").write_text(
        json.dumps({"nivel": "media", "tipo": "error", "error": "x"}) + "\n", encoding="utf-8")

    earlier = ev.previous_levels([runs], expected, procedure.number)

    assert earlier["media"]["run"] == "20260101-000000-aaa"
