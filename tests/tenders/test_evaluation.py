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
    PAGO,
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


def by_id(report):
    result = report.results[0]
    return {line["id"]: line for line in result["measures"]["lines"]
            if line["tipo"] == "esperado"}


def run_measure(user, procedure, path, tmp_path):
    expected = ev.load_expected(path)
    return ev.measure(user, procedure, expected, tmp_path / "corridas",
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


def test_run_uses_eval_channel_and_discards_its_version(case, operator_user, tmp_path):
    """REQ-024: la medición corre el proceso único con el canal `eval`; la versión queda
    descartada, con su hecho de registro, y se puede medir otra vez."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    runs = list(m.MatrixRun.objects.order_by("id"))
    assert [(r.process, r.level, r.channel, r.job_id) for r in runs] == [
        ("completo", "", "eval", None)]
    versions = m.MatrixVersion.objects.filter(procedure=procedure)
    assert versions.count() == 1 and versions.get().process == "completo"
    assert set(versions.values_list("status", flat=True)) == {"discarded"}
    assert all(v.discarded_by_id == operator_user.pk for v in versions)
    assert [r["process"] for r in report.results] == ["completo"]
    assert not hasattr(report, "comparison")
    again = run_measure(operator_user, procedure, path, tmp_path)
    assert again.folder != report.folder


def test_open_draft_refuses_the_measurement(case, operator_user, tmp_path):
    """REQ-024: con un borrador abierto no se mide (la base admite uno por procedimiento)."""
    procedure, _, path, _ = case
    m.MatrixVersion.objects.create(procedure=procedure, number=1, process="completo",
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
    assert parameters["proceso"] == "completo" and parameters["commit"] == "abc1234"
    assert "niveles" not in parameters
    assert [p["process"] for p in parameters["propuestas"]] == ["completo"]
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
                 esperada=str(path))

    out = capsys.readouterr().out
    assert "Corrida guardada en" in out and "completo: encontrados" in out
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
        return ev._pairs([entry], [NS(spans=[(reading.pk, start, end, False)], quotes=[NS(
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
    assert run_measure(evaluator_user, procedure, path, tmp_path).results[0]["process"] == "completo"


def test_technical_row_citing_two_documents_is_measured_against_each_own_reading(
        case, operator_user, tmp_path, monkeypatch):
    """REQ-025: una fila técnica que cita tramos de dos documentos mide cada cita contra la
    lectura de su propio tramo, no contra la de la primera cita de la fila."""
    from tests.tenders.pdfs import para, tender_pdf

    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    base = report.results[0]["measures"]["literal"]
    annex = load_and_read(
        operator_user, procedure,
        tender_pdf([[para("ANEXO SINTÉTICO", "1. Los planos se entregan en papel.",
                          "2. La señalética es de chapa.")]], header=None),
        kind=m.DocumentKind.ANEXO, title="Anexo sintético")
    segment = annex.readings.get().segments.order_by("order").first()
    # La versión medida ya está descartada y no se modifica: la cita del anexo se agrega en
    # memoria, como primera cita de la fila técnica.
    foreign = m.RequirementQuote(
        order=0, segment=segment, char_start=segment.char_start, char_end=segment.char_end,
        text=segment.reading.canonical_text[segment.char_start:segment.char_end],
        scope=m.QuoteScope.PROPIA)
    original = ev._proposed

    def with_annex_quote(version):
        rows = original(version)
        technical = next(r for r in rows if r.category == ev.TECHNICAL)
        technical.quotes.insert(0, foreign)
        technical.reading, technical.segment = segment.reading, segment
        return rows

    monkeypatch.setattr(ev, "_proposed", with_annex_quote)

    expected = ev.load_expected(path)
    verification = ev.verify_expected(expected, procedure)
    measures = ev.measure_version(run, expected, verification)

    assert measures["literal"]["total"] == base["total"] + 1
    assert measures["literal"]["ok"] == measures["literal"]["total"]
    assert not [line for line in measures["lines"] if line["tipo"] == "cita"]


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


# --- A revisión obligatoria (T-095) -------------------------------------------------------------


def test_expected_in_a_pending_segment_is_mandatory_review_and_counts_in_acceptance(
        case, operator_user, script, tmp_path):
    """REQ-024: un esperado en un tramo pendiente no es faltante: cuenta como "a revisión
    obligatoria", entra en el numerador de los encontrados y se informa aparte."""
    procedure, _, path, _ = case
    base = run_measure(operator_user, procedure, path, tmp_path / "base")
    base_found = base.results[0]["measures"]["found"]["ok"]
    script.when(PAGO, item())

    report = run_measure(operator_user, procedure, path, tmp_path / "pendiente")

    line = by_id(report)["S-002"]
    assert line["estado"] == ev.MANDATORY_REVIEW
    assert line["causa"] == ev.PENDING
    measures = report.results[0]["measures"]
    assert measures["review"] == {"count": 1, "ids": ["S-002"], "keys": ["sec-i/2.1"]}
    assert ev.PENDING not in measures["causes"]
    assert measures["found"]["ok"] == base_found + 1
    assert measures["found_without_review"]["ok"] == base_found
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "A revisión obligatoria (tramos pendientes): 1" in summary
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "S-002" in public and "sec-i/2.1" in public
    assert "a los 90 días corridos" not in public
    assert PAGO not in public


def test_discarded_or_with_requirements_segments_stay_missing_not_review(
        case, operator_user, tmp_path):
    """REQ-024: un esperado en un tramo descartado o con otros requisitos sigue siendo
    faltante; sin pendientes no hay revisión obligatoria."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    assert lines["S-002"]["estado"] == "faltante"
    assert lines["S-002"]["causa"] == ev.DISCARDED
    measures = report.results[0]["measures"]
    assert measures["review"]["count"] == 0
    assert measures["found"] == measures["found_without_review"]
    assert all(line["estado"] != ev.MANDATORY_REVIEW for line in lines.values())


def test_expected_in_a_segment_with_requirements_stays_missing_not_review(
        case, operator_user, script, tmp_path):
    """REQ-024: un esperado en un tramo con requisitos, sin esta fila, sigue siendo faltante
    (`tramo_con_requisitos_sin_este`); no pasa a revisión obligatoria."""
    procedure, _, path, _ = case
    script.when(PAGO, item(requirements=[("El pago se efectuará", "economico")]))

    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-002"]
    assert line["estado"] == "faltante"
    assert line["causa"] == ev.SEGMENT_WITH_OTHERS
    measures = report.results[0]["measures"]
    assert measures["review"]["count"] == 0
    assert measures["found"] == measures["found_without_review"]
    assert all(row["estado"] != ev.MANDATORY_REVIEW for row in by_id(report).values())


# --- Cobertura con circulares y resumen que no se pierde (T-096) -------------------------------


def _with_circular_dispositions(user, procedure, run):
    """Agrega al procedimiento una circular (no es documento base) y le da a sus tramos una
    disposición en `run`, como hace la propuesta."""
    from datetime import date

    from tests.tenders.pdfs import para, tender_pdf

    pdf = tender_pdf([[para("CIRCULAR SINTÉTICA", "1. Prorrógase la apertura.",
                            "2. Aclárase el lugar de entrega.")]], header=None)
    document = load_and_read(user, procedure, pdf, kind=m.DocumentKind.CIRCULAR_MODIFICATORIA,
                             title="Circular sintética", issued_on=date(2025, 12, 1))
    segments = list(document.readings.get().segments.all())
    assert segments
    for segment in segments:
        m.Disposition.objects.create(
            run=run, segment=segment, outcome=m.DispositionOutcome.DESCARTADO,
            discard_reason=m.DiscardReason.DATO_PROCEDIMIENTO, source=m.DispositionSource.REGLA)
    return len(segments)


def test_coverage_counts_the_same_set_when_there_are_circulars(case, operator_user, tmp_path):
    """REQ-030: los tramos de circulares reciben disposición pero no son tramos de los
    documentos de la corrida: la cobertura se mide sobre los mismos tramos (nunca pasa del
    100 %) y los de circulares se informan aparte."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    base = report.results[0]["measures"]["coverage"]
    extra = _with_circular_dispositions(operator_user, procedure, run)

    dispositions = {d.segment_id: d for d in m.Disposition.objects.filter(run=run)}
    coverage = ev._coverage(run, dispositions)

    assert coverage["segments"] == base["segments"]
    assert coverage["with_disposition"] == base["with_disposition"] <= coverage["segments"]
    assert coverage["circular_with_disposition"] == extra
    assert sum(coverage["by_source"].values()) == base["with_disposition"] + extra


def test_summary_is_written_even_if_a_proportion_is_out_of_range(case, operator_user, tmp_path,
                                                                 monkeypatch):
    """REQ-030: si una cuenta queda fuera de 0 a 100 %, el resumen se escribe e informa la
    anomalía en vez de perderse."""
    procedure, _, path, _ = case
    real = ev._coverage

    def broken(run, dispositions):
        data = real(run, dispositions)
        return {**data, "with_disposition": data["segments"] + 5}

    monkeypatch.setattr(ev, "_coverage", broken)

    report = run_measure(operator_user, procedure, path, tmp_path)

    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "anomalía" in summary


def test_summaries_are_regenerated_from_a_finished_run_without_the_model(
        case, operator_user, tmp_path, script, monkeypatch):
    """REQ-030: `--regenerar-resumen` reescribe los dos resúmenes de una corrida hecha, con
    las mismas cuentas, sin llamar al modelo ni tocar parametros.json ni resultados.jsonl."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    folder = report.folder
    before = {n: (folder / n).read_text(encoding="utf-8")
              for n in ("resumen.md", "resumen-publico.md", "parametros.json",
                        "resultados.jsonl")}
    (folder / "resumen.md").unlink()
    (folder / "resumen-publico.md").unlink()
    runs_before = m.MatrixRun.objects.count()
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)
    calls_before = len(script.calls)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), regenerar_resumen=str(folder))

    for name, text in before.items():
        assert (folder / name).read_text(encoding="utf-8") == text
    assert m.MatrixRun.objects.count() == runs_before
    assert len(script.calls) == calls_before


def test_command_no_longer_accepts_levels_or_comparison(case, operator_user, monkeypatch):
    """REQ-030: `medir_matriz` mide el proceso único: `--niveles` y `--comparar-con` ya no
    existen, y no se corre nada."""
    from django.core.management.base import CommandError

    procedure, _, path, _ = case
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)

    for option in ("--niveles", "--comparar-con"):
        with pytest.raises(CommandError):
            call_command("medir_matriz", "--usuario", "operador", "--procedimiento",
                         procedure.number, "--esperada", str(path), option, "alta")
    assert not m.MatrixRun.objects.exists()


def test_a_run_folder_made_with_levels_is_still_regenerated(
        case, operator_user, tmp_path, monkeypatch):
    """REQ-030: una carpeta de corrida hecha antes del proceso único (claves `niveles`,
    `level` y `nivel`, con la propuesta guardada con su nivel) se sigue leyendo y sus
    resúmenes se reescriben, con el nivel mostrado como el proceso de la propuesta."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    folder = report.folder
    parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
    parameters.pop("proceso")
    parameters["niveles"] = ["media"]
    for entry in parameters["propuestas"]:
        entry["level"] = entry.pop("process")
    (folder / "parametros.json").write_text(json.dumps(parameters), encoding="utf-8")
    m.MatrixRun.objects.update(process="", level="media")
    expected = ev.load_expected(path)

    again = ev.regenerate_summaries(procedure, expected, folder)

    assert [r["process"] for r in again.results] == ["media"]
    summary = (folder / "resumen.md").read_text(encoding="utf-8")
    assert "## Proceso " in summary


# --- Sobrantes sobre las filas firmes, con tope e informe de descartadas (T-103) ----------------
#
# Las descartadas y las sugerencias se insertan a mano después de la propuesta del doble: de
# producirlas se ocupan el filtro y las sugerencias (T-102, T-109).


def after_propose(monkeypatch, hook):
    """Llama a `hook(version)` apenas termina la propuesta, antes de medirla."""
    real = ev.proposal.propose

    def wrapped(run, **kwargs):
        version = real(run, **kwargs)
        hook(version)
        return version

    monkeypatch.setattr(ev.proposal, "propose", wrapped)


def seg_of(version, key):
    from tests.tenders.test_discarded import segment
    return segment(version, key)


def add_requirement(version, key, *, state="propuesto", category="formal", repeated=(),
                    doubt=""):
    """Una fila con su cita principal en el tramo `key` y citas `repetida` en `repeated`
    (pares tramo, frase)."""
    number = max([r.number for r in version.requirements.all()] or [0]) + 1
    row = m.Requirement.objects.create(
        version=version, number=number, category=category, items=[],
        origin=m.RequirementOrigin.PROPUESTO, state=state, proposed={},
        doubt_reason=doubt)
    for order, (where, phrase, scope) in enumerate(
            [(key, None, "")] + [(k, p, "repetida") for k, p in repeated], start=1):
        seg = seg_of(version, where)
        span = ev.find_anchor(seg, phrase, 1) if phrase else (seg.char_start, seg.char_end)
        m.RequirementQuote.objects.create(
            requirement=row, order=order, segment=seg, char_start=span[0], char_end=span[1],
            text=seg.reading.canonical_text[span[0]:span[1]], scope=scope)
    return row


def add_discarded(version, key, **fields):
    from tests.tenders.test_discarded import add_row
    order = version.discarded_rows.count() + 1
    return add_row(version, key, order=order, **fields)


def measures_of(report):
    return report.results[0]["measures"]


def test_discarded_rows_and_suggestions_are_not_leftovers_nor_in_the_denominator(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: las descartadas por el sistema y las filas `sugerido` no cuentan como
    sobrantes ni en el denominador del tope; una firme sin pareja sí."""
    procedure, _, path, _ = case
    base = measures_of(run_measure(operator_user, procedure, path, tmp_path / "base"))

    def hook(version):
        add_discarded(version, "sec-ii/1.1")
        add_requirement(version, "sec-ii/1.1", state="sugerido", doubt="duda")

    after_propose(monkeypatch, hook)
    with_extras = measures_of(run_measure(operator_user, procedure, path, tmp_path / "x"))

    assert with_extras["leftovers"] == base["leftovers"] == 1  # el renglón 3, sin esperado
    assert with_extras["leftover_ratio"] == base["leftover_ratio"]
    assert with_extras["leftover_ratio"]["total"] == base["proposed_total"] == 5

    def one_more(version):
        hook(version)
        add_requirement(version, "sec-ii/1.1")

    after_propose(monkeypatch, one_more)
    firm = measures_of(run_measure(operator_user, procedure, path, tmp_path / "y"))
    assert firm["leftovers"] == 2
    assert firm["leftover_ratio"] == {"ok": 2, "total": 6, "rate": 2 / 6}
    assert firm["leftover_ratio_formal_economic"] == {"ok": 1, "total": 3, "rate": 1 / 3}


def test_expected_inside_a_discarded_row_is_a_missing_with_its_own_cause(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: un esperado cuya cita está en una descartada es faltante con la causa
    `descartado_por_el_sistema`, el motivo y la clave del tramo."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_discarded(v, "sec-i/2.1", reason="formulario"))

    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-002"]
    assert line["estado"] == "faltante"
    assert line["causa"] == ev.DISCARDED_BY_SYSTEM == "descartado_por_el_sistema"
    assert "formulario" in line["detalle"] and "sec-i/2.1" in line["detalle"]
    measures = measures_of(report)
    assert measures["causes"][ev.DISCARDED_BY_SYSTEM] == 1
    assert any("found" in reason for reason in report.blocking)
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "S-002" in public and "descartado_por_el_sistema" in public
    assert "formulario" in public


def test_expected_in_a_repeated_quote_counts_as_unified_not_missing(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: un esperado cuya ancla está en una cita `repetida` de una fila ya emparejada
    es encontrado "unificado", informado aparte; no es faltante."""
    procedure, _, path, _ = case
    base = measures_of(run_measure(operator_user, procedure, path, tmp_path / "base"))

    def hook(version):
        row = version.requirements.get(quotes__text__contains="garantía del 5 %")
        seg = seg_of(version, "sec-i/2.1")
        span = ev.find_anchor(seg, "a los 90 días corridos", 1)
        m.RequirementQuote.objects.create(
            requirement=row, order=row.quotes.count() + 1, segment=seg, char_start=span[0],
            char_end=span[1], text=seg.reading.canonical_text[span[0]:span[1]],
            scope="repetida")

    after_propose(monkeypatch, hook)
    report = run_measure(operator_user, procedure, path, tmp_path / "x")

    line = by_id(report)["S-002"]
    assert line["estado"] == "encontrado" and "unificado" in line["detalle"]
    measures = measures_of(report)
    assert measures["unified"] == {"count": 1, "ids": ["S-002"]}
    assert measures["found"]["ok"] == base["found"]["ok"] + 1
    assert ev.DISCARDED not in measures["causes"]
    assert measures["leftovers"] == 1
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Unificados" in summary and "S-002" in summary


def test_a_row_matches_an_expected_through_any_of_its_quotes(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: una fila empareja con un esperado si cualquiera de sus citas cubre la mitad
    del ancla; esa fila deja de ser sobrante."""
    procedure, _, path, _ = case
    holder = {}

    def hook(version):
        holder["row"] = add_requirement(
            version, "sec-ii/1.1", category="economico",
            repeated=[("sec-i/2.1", "a los 90 días corridos")])

    after_propose(monkeypatch, hook)
    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-002"]
    assert line["estado"] == "encontrado" and line.get("detalle", "") == ""
    assert line["propuesto"] == holder["row"].number
    assert measures_of(report)["leftovers"] == 1
    assert measures_of(report)["unified"]["count"] == 0


@pytest.mark.parametrize("leftovers,total,meets", [(8, 40, True), (9, 40, False),
                                                   (0, 3, True), (1, 4, False)])
def test_cap_is_twenty_percent_of_the_firm_rows(leftovers, total, meets):
    """REQ-024, REQ-033: con 8 sobrantes sobre 40 filas (20 %) el tope cumple y con 9 no."""
    verdict = ev.cap_verdict(ev.ratio(leftovers, total), ev.ratio(10, 10))

    assert verdict["leftovers_ok"] is meets
    assert verdict["met"] is meets
    assert verdict["limit"] == 0.20


def test_cap_fails_with_a_missing_even_if_the_proportion_meets_it(
        case, operator_user, tmp_path):
    """REQ-024: con un faltante el tope no cumple aunque la proporción de sobrantes sí."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    cap = measures_of(report)["cap"]
    assert measures_of(report)["leftovers"] == 1
    assert cap["leftovers_ok"] is True and cap["found_ok"] is False and cap["met"] is False
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Tope de sobrantes" in summary and "no cumple" in summary


def test_cap_over_the_limit_blocks_the_acceptance(case, operator_user, monkeypatch, tmp_path):
    """REQ-024: una proporción de sobrantes mayor que el tope se informa entre los bloqueos."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_requirement(v, "sec-ii/1.1"))

    report = run_measure(operator_user, procedure, path, tmp_path)

    assert any("sobrantes" in reason and "tope" in reason for reason in report.blocking)
    assert not measures_of(report)["cap"]["leftovers_ok"]


def test_discarded_report_counts_by_reason_segment_and_pass_and_the_leftovers_without_filter(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: el informe de descartadas da la cantidad, el reparto por motivo, tramo y
    pasada, y los sobrantes que habría sin el filtro (sobrantes más descartadas sin
    pareja en la lista)."""
    procedure, _, path, _ = case

    def hook(version):
        add_requirement(version, "sec-ii/1.1")
        add_discarded(version, "sec-ii/1.1", reason="titulo", source_pass="extraccion")
        add_discarded(version, "sec-i/3.1", reason="titulo", source_pass="completitud")
        add_discarded(version, "sec-i/2.1", reason="formulario", source_pass="extraccion")

    after_propose(monkeypatch, hook)
    report = run_measure(operator_user, procedure, path, tmp_path)

    info = measures_of(report)["discarded"]
    assert info["count"] == 3
    assert info["by_reason"] == {"titulo": 2, "formulario": 1}
    assert info["by_segment"] == {"sec-ii/1.1": 1, "sec-i/3.1": 1, "sec-i/2.1": 1}
    assert info["by_pass"] == {"extraccion": 2, "completitud": 1}
    assert info["with_pair"] == 2  # las de sec-i/3.1 y sec-i/2.1 cubren anclas esperadas
    assert info["leftovers_without_filter"] == measures_of(report)["leftovers"] + 1 == 3
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Descartadas por el sistema: 3" in summary
    assert "Sobrantes que habría sin el filtro: 3" in summary


def test_sample_of_discarded_has_the_planned_size_and_order():
    """REQ-033: una de cada tres, con un mínimo de 20, en el orden de la corrida; con menos
    del mínimo, todas."""
    def sample(n):
        return ev.sample_indexes(n, {"every": 3, "minimum": 20})

    assert sample(90) == list(range(0, 90, 3))
    assert len(sample(30)) == 20 and sample(30) == sorted(set(sample(30)))
    assert sample(12) == list(range(12))
    assert sample(0) == []
    assert len(sample(100)) == 34 and sample(100) == sorted(set(sample(100)))


def test_sample_is_written_with_text_and_a_template_for_the_verifier(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: la muestra sale en `resumen.md` y en la plantilla local
    `muestra-descartadas.md` con una columna para el verificador; `resumen-publico.md` no
    lleva texto de ninguna cita ni indicio."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: (add_discarded(v, "sec-ii/1.1", reason="titulo"),
                                          add_discarded(v, "sec-i/3.1", reason="formulario")))

    report = run_measure(operator_user, procedure, path, tmp_path)

    rows = list(m.DiscardedRow.objects.filter(run_id=report.results[0]["run"]).order_by("order"))
    assert len(rows) == 2
    private = (report.folder / "resumen.md").read_text(encoding="utf-8")
    template = (report.folder / "muestra-descartadas.md").read_text(encoding="utf-8")
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "Muestra de descartadas (2 de 2)" in private
    assert "¿Descarte correcto?" in template
    for row in rows:
        assert row.text[:30] in private and row.text[:30] in template
        assert row.evidence_text in private
        assert row.text[:30] not in public and row.evidence_text not in public
    assert "titulo" in public and "sec-ii/1.1" in public
    assert template.index(rows[0].text[:30]) < template.index(rows[1].text[:30])


def test_run_without_discarded_gives_the_usual_measures(case, operator_user, tmp_path):
    """REQ-033: una corrida sin descartadas da las medidas de siempre y lo dice."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    measures = measures_of(report)
    assert measures["discarded"]["count"] == 0 and measures["discarded"]["sample"] == []
    assert measures["leftovers"] == 1 and measures["proposed_total"] == 5
    assert not (report.folder / "muestra-descartadas.md").exists()
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Descartadas por el sistema: 0" in summary


def test_regenerating_keeps_the_verifiers_sample(case, operator_user, monkeypatch, tmp_path):
    """REQ-033: `--regenerar-resumen` con descartadas reescribe los resúmenes iguales y no
    pisa la muestra que el verificador ya completó."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_discarded(v, "sec-ii/1.1"))
    report = run_measure(operator_user, procedure, path, tmp_path)
    folder = report.folder
    before = {n: (folder / n).read_text(encoding="utf-8")
              for n in ("resumen.md", "resumen-publico.md")}
    (folder / "muestra-descartadas.md").write_text("completada por el verificador",
                                                   encoding="utf-8")
    (folder / "resumen.md").unlink()
    (folder / "resumen-publico.md").unlink()
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), regenerar_resumen=str(folder))

    for name, text in before.items():
        assert (folder / name).read_text(encoding="utf-8") == text
    assert (folder / "muestra-descartadas.md").read_text(
        encoding="utf-8") == "completada por el verificador"


def test_timings_add_the_unification_and_filter_passes(case, operator_user, tmp_path):
    """REQ-033: `timing_summary` suma las pasadas `unificacion` y `filtro` y el resumen las
    informa."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    run.timings = {**run.timings, "unificacion": 1.5, "filtro": 2.25}

    timings = ev.timing_summary(run)

    assert timings["filter_seconds"] == 3.75
    shown = "\n".join(ev._timing_lines(timings))
    assert "Unificación y filtro" in shown and "unificacion 1,5 s" in shown


def test_verify_warns_of_two_expected_with_the_same_normalized_anchor(case):
    """REQ-033: `--verificar-esperada` avisa de dos esperados con el mismo ancla normalizado
    (se unificarían); no bloquea."""
    procedure, _, path, text = case
    write(path, text.replace(
        "  - id: S-T1",
        '  - id: S-007\n    documento: Pliego sintético.pdf\n    tramo: sec-i/1.1\n'
        '    ancla: "garantía  del 5 % del  monto"\n    clase: formal\n    renglones: []\n'
        "  - id: S-T1"))

    verification = ev.verify_expected(ev.load_expected(path), procedure)

    assert verification.ok, verification.problems
    assert any("S-001" in n and "S-007" in n and "mismo ancla" in n
               for n in verification.notes)


def test_row_with_repeated_quotes_covers_the_expected_of_its_main_quote_too(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-033: una fila con citas `repetida` cubre como unificado a cada esperado que cubra
    cualquiera de sus citas, la principal incluida, aunque el emparejamiento uno a uno haya
    dado la fila al otro; una fila sin repetidas no cuenta para dos esperados."""
    procedure, _, path, _ = case

    def hook(version):
        # Sin la fila de la garantía del doble: la fila nueva es la única que las cubre.
        version.requirements.filter(quotes__text__contains="garantía del 5 %").update(
            state="quitado")
        # Principal en el pago (S-002, ancla más corta); repetida en la garantía (S-001).
        add_requirement(version, "sec-i/2.1", category="economico",
                        repeated=[("sec-i/1.1", "garantía del 5 % del monto")])

    after_propose(monkeypatch, hook)
    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    assert lines["S-001"]["estado"] == "encontrado"
    assert lines["S-002"]["estado"] == "encontrado"
    assert measures_of(report)["unified"]["count"] == 1


def test_row_without_repeated_quotes_does_not_count_for_two_expected(
        case, operator_user, tmp_path):
    """REQ-033: sin citas `repetida`, una fila sigue contando para un solo esperado (la otra
    condición queda `agrupado`)."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    assert ev.GROUPED in measures_of(report)["causes"]
    assert measures_of(report)["unified"]["count"] == 0


# --- Sugerencias y respaldo normativo (T-111; REQ-035, REQ-036, REQ-024) ------------------------
#
# Las sugerencias y sus respaldos se insertan a mano después de la propuesta del doble: de
# producirlos se ocupan el filtro y la consulta normativa (T-102, T-109).


@pytest.fixture
def norm_unit(make_norm, make_document, make_reading):
    reading = make_reading(
        make_document(make_norm()), [("art-1", "Artículo 1. Texto sintético de la norma.")])
    return reading.units_by_key["art-1"]


def add_suggestion(version, key, *, doubt="duda", category="formal", repeated=()):
    return add_requirement(version, key, state="sugerido", category=category,
                           repeated=repeated, doubt=doubt)


def add_support(row, norm_unit, *, label="Norma sintética, art. 1"):
    step = m.RunStep.objects.create(run=row.version.run, pass_name="respaldo_normativo",
                                    batch=row.number, request={"messages": []})
    return m.NormSupport.objects.create(
        requirement=row, unit=norm_unit, unit_label=label, char_start=0, char_end=11,
        text="Artículo 1.", score=0.5, regime="Régimen sintético", corpus_version=1, step=step)


def test_expected_in_a_suggestion_is_mandatory_review_and_counts_in_the_acceptance(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: un esperado cuya cita está en una sugerencia cuenta "a revisión obligatoria"
    con causa `sugerencia`: suma a los encontrados, se informa aparte con su clave y no es
    sobrante ni faltante; la sugerencia no entra en el tope."""
    procedure, _, path, _ = case
    base = measures_of(run_measure(operator_user, procedure, path, tmp_path / "base"))
    after_propose(monkeypatch, lambda v: add_suggestion(v, "sec-i/2.1"))

    report = run_measure(operator_user, procedure, path, tmp_path / "x")

    line = by_id(report)["S-002"]
    assert line["estado"] == ev.MANDATORY_REVIEW and line["causa"] == "sugerencia"
    measures = measures_of(report)
    assert measures["suggestion_review"] == {"count": 1, "ids": ["S-002"]}
    assert measures["review"]["count"] == 0
    assert measures["found"]["ok"] == base["found"]["ok"] + 1
    assert measures["found_without_review"]["ok"] == base["found"]["ok"]
    assert "sugerencia" not in measures["causes"]
    assert measures["leftovers"] == base["leftovers"]
    assert measures["leftover_ratio"] == base["leftover_ratio"]
    assert measures["proposed_total"] == base["proposed_total"]
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "A revisión obligatoria (sugerencias): 1" in summary and "S-002" in summary
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "S-002" in public


def test_expected_with_a_firm_match_and_a_suggestion_matches_the_firm_row(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: el orden de emparejamiento es firmes, sugerencias, descartadas: un esperado
    con pareja firme y otra en una sugerencia empareja con la firme."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_suggestion(v, "sec-i/1.1"))

    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-001"]
    assert line["estado"] == "encontrado" and "causa" not in line
    assert measures_of(report)["suggestion_review"]["count"] == 0


def test_expected_in_a_discarded_row_and_a_suggestion_goes_to_the_suggestion(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: un esperado con pareja en una descartada y en una sugerencia es "a revisión
    obligatoria"."""
    procedure, _, path, _ = case

    def hook(version):
        add_discarded(version, "sec-i/2.1", reason="formulario")
        add_suggestion(version, "sec-i/2.1")

    after_propose(monkeypatch, hook)
    lines = by_id(run_measure(operator_user, procedure, path, tmp_path))

    assert lines["S-002"]["estado"] == ev.MANDATORY_REVIEW
    assert lines["S-002"]["causa"] == "sugerencia"


def test_expected_only_in_a_discarded_row_stays_missing_with_a_suggestion_elsewhere(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035, REQ-033: la sugerencia de otro tramo no toca al faltante descartado."""
    procedure, _, path, _ = case

    def hook(version):
        add_discarded(version, "sec-i/2.1", reason="formulario")
        add_suggestion(version, "sec-ii/1.1")

    after_propose(monkeypatch, hook)
    line = by_id(run_measure(operator_user, procedure, path, tmp_path))["S-002"]

    assert line["estado"] == "faltante" and line["causa"] == ev.DISCARDED_BY_SYSTEM


def three_suggestions(version, norm_unit):
    """A (sec-i/2.1, con respaldo), B (sin esperado) y C (sec-i/4.1, sin la fila firme de la
    multa); dos de las tres cubren esperados."""
    version.requirements.filter(quotes__text__contains="multa del 1 %").update(
        state="quitado")
    a = add_suggestion(version, "sec-i/2.1", doubt="no_coinciden")
    add_suggestion(version, "sec-ii/1.1", doubt="duda")
    add_suggestion(version, "sec-i/4.1", doubt="duda")
    add_support(a, norm_unit)


def test_suggestion_report_counts_the_suggestions_the_expected_and_the_support(
        case, operator_user, monkeypatch, tmp_path, norm_unit):
    """REQ-035, REQ-036: con 3 sugerencias, 2 con pareja esperada, 1 con respaldo y esa
    esperada, el informe da 3, 2 de 3, 1 con respaldo y 1 de 1; por motivo y por tramo; los
    sobrantes "si fueran firmes" suman las sugerencias sin pareja."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: three_suggestions(v, norm_unit))

    report = run_measure(operator_user, procedure, path, tmp_path)

    info = measures_of(report)["suggestions"]
    assert info["count"] == 3
    assert info["by_reason"] == {"no_coinciden": 1, "duda": 2}
    assert info["by_segment"] == {"sec-i/2.1": 1, "sec-ii/1.1": 1, "sec-i/4.1": 1}
    assert info["expected"] == {"ok": 2, "total": 3, "rate": 2 / 3}
    assert info["with_support"] == 1
    assert info["with_support_expected"] == {"ok": 1, "total": 1, "rate": 1.0}
    assert info["expected_as_suggestion"]["ok"] == 2  # S-002 y uno de S-003, S-004
    leftovers = measures_of(report)["leftovers"]
    assert info["leftovers_if_firm"] == leftovers + 1
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Sugerencias de condición: 3" in summary
    assert "con respaldo normativo: 1" in summary
    assert "si las sugerencias fueran firmes" in summary


def test_suggestions_do_not_count_in_the_cap_but_the_informative_cap_adds_them(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-024, REQ-035: ocho sugerencias sin pareja no mueven el tope firme; el informativo
    "con sugerencias como firmes" sí las suma."""
    procedure, _, path, _ = case
    base = measures_of(run_measure(operator_user, procedure, path, tmp_path / "base"))

    def hook(version):
        for _ in range(8):
            add_suggestion(version, "sec-ii/1.1")

    after_propose(monkeypatch, hook)
    measures = measures_of(run_measure(operator_user, procedure, path, tmp_path / "x"))

    assert measures["leftover_ratio"] == base["leftover_ratio"]
    assert measures["cap"] == base["cap"]
    info = measures["suggestions"]
    assert info["leftovers_if_firm"] == base["leftovers"] + 8
    assert info["cap_if_firm"]["leftovers_ok"] is False
    assert info["cap_if_firm"]["limit"] == 0.20


def test_public_summary_has_no_text_of_the_suggestions_nor_of_the_norm(
        case, operator_user, monkeypatch, tmp_path, norm_unit):
    """REQ-035, REQ-036 (P4): `resumen-publico.md` lleva cuentas, claves, motivos y la
    identificación de la norma, sin el texto de ninguna cita ni de la norma; el resumen
    local y `muestra-sugerencias.md` sí llevan el texto, con una columna para el
    verificador."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: three_suggestions(v, norm_unit))

    report = run_measure(operator_user, procedure, path, tmp_path)

    rows = list(m.Requirement.objects.filter(
        version__run_id=report.results[0]["run"], state="sugerido").order_by("number"))
    assert len(rows) == 3
    private = (report.folder / "resumen.md").read_text(encoding="utf-8")
    template = (report.folder / "muestra-sugerencias.md").read_text(encoding="utf-8")
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "Muestra de sugerencias (3 de 3)" in private
    assert "¿Sugerencia y respaldo correctos?" in template
    for row in rows:
        text = row.quotes.get().text
        assert text[:30] in private and text[:30] in template
        assert text[:30] not in public
    assert "Texto sintético de la norma" not in public
    assert "Artículo 1." not in public
    assert "Artículo 1." in private and "Artículo 1." in template
    assert "no_coinciden" in public and "sec-i/2.1" in public
    assert "Norma sintética, art. 1" in public
    assert template.index(rows[0].quotes.get().text[:30]) < template.index(
        rows[1].quotes.get().text[:30])


def test_run_without_suggestions_gives_the_usual_measures(case, operator_user, tmp_path):
    """REQ-035: una corrida sin sugerencias da las medidas de siempre y no escribe la
    muestra de sugerencias."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    measures = measures_of(report)
    assert measures["suggestions"]["count"] == 0
    assert measures["suggestions"]["sample"] == []
    assert measures["suggestion_review"] == {"count": 0, "ids": []}
    assert measures["leftovers"] == 1 and measures["proposed_total"] == 5
    assert not (report.folder / "muestra-sugerencias.md").exists()
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Sugerencias de condición: 0" in summary


def test_timings_add_the_normative_support_pass(case, operator_user, tmp_path):
    """REQ-036: `timing_summary` suma la pasada `respaldo_normativo` y el resumen la
    informa."""
    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    run.timings = {**run.timings, "respaldo_normativo": 4.5}

    timings = ev.timing_summary(run)

    assert timings["support_seconds"] == 4.5
    assert "Respaldo normativo: 4,5 s" in "\n".join(ev._timing_lines(timings))


def test_regenerating_keeps_the_suggestions_sample_of_the_verifier(
        case, operator_user, monkeypatch, tmp_path, norm_unit):
    """REQ-035: `--regenerar-resumen` reescribe los resúmenes con sugerencias iguales y no
    pisa la muestra de sugerencias ya completada."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: three_suggestions(v, norm_unit))
    report = run_measure(operator_user, procedure, path, tmp_path)
    folder = report.folder
    before = {n: (folder / n).read_text(encoding="utf-8")
              for n in ("resumen.md", "resumen-publico.md")}
    (folder / "muestra-sugerencias.md").write_text("completada", encoding="utf-8")
    (folder / "resumen.md").unlink()
    (folder / "resumen-publico.md").unlink()
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), regenerar_resumen=str(folder))

    for name, text in before.items():
        assert (folder / name).read_text(encoding="utf-8") == text
    assert (folder / "muestra-sugerencias.md").read_text(encoding="utf-8") == "completada"


def test_the_measurement_never_changes_the_state_of_a_suggestion(
        case, operator_user, monkeypatch, tmp_path, norm_unit):
    """REQ-036: medir no cambia el estado de las sugerencias ni agrega respaldos."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: three_suggestions(v, norm_unit))

    report = run_measure(operator_user, procedure, path, tmp_path)

    run_id = report.results[0]["run"]
    assert m.Requirement.objects.filter(version__run_id=run_id, state="sugerido").count() == 3
    assert m.NormSupport.objects.filter(requirement__version__run_id=run_id).count() == 1


def test_a_suggestion_counts_for_one_expected_only(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: el emparejamiento de sugerencias es uno a uno: una sugerencia que cubre dos
    esperados da uno "a revisión obligatoria" y el otro queda faltante."""
    procedure, _, path, _ = case

    def hook(version):
        version.requirements.filter(quotes__text__contains="multa del 1 %").update(
            state="quitado")
        add_suggestion(version, "sec-i/4.1")

    after_propose(monkeypatch, hook)
    report = run_measure(operator_user, procedure, path, tmp_path)

    lines = by_id(report)
    states = sorted(lines[i]["estado"] for i in ("S-003", "S-004"))
    assert states == ["a_revision_obligatoria", "faltante"]
    measures = measures_of(report)
    assert measures["suggestion_review"]["count"] == 1
    assert measures["suggestions"]["expected_as_suggestion"]["ok"] == 1


def test_a_suggestion_over_an_expected_already_matched_by_a_firm_row_is_not_an_expected_one(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: la proporción de sugerencias esperadas no cuenta los esperados que ya
    empareja una fila firme."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_suggestion(v, "sec-i/1.1"))  # S-001 es firme

    info = measures_of(run_measure(operator_user, procedure, path, tmp_path))["suggestions"]

    assert info["count"] == 1
    assert info["expected"] == {"ok": 0, "total": 1, "rate": 0.0}


def test_a_suggestion_must_cover_half_of_the_anchor_to_match(
        case, operator_user, monkeypatch, tmp_path):
    """REQ-035: como para una fila firme, la cita de la sugerencia debe cubrir al menos la
    mitad del ancla; con menos, el esperado no queda a revisión."""
    procedure, _, path, _ = case
    after_propose(monkeypatch, lambda v: add_suggestion(
        v, "sec-ii/1.1", repeated=[("sec-i/2.1", "a los")]))  # 5 de 22 caracteres
    short = by_id(run_measure(operator_user, procedure, path, tmp_path / "a"))["S-002"]

    after_propose(monkeypatch, lambda v: add_suggestion(
        v, "sec-ii/1.1", repeated=[("sec-i/2.1", "a los 90 días")]))  # 13 de 22
    long = by_id(run_measure(operator_user, procedure, path, tmp_path / "b"))["S-002"]

    assert short["estado"] == "faltante"
    assert long["estado"] == ev.MANDATORY_REVIEW


# --- REQ-031 por fila (T-117) -----------------------------------------------------------------

CIRCULAR_FILE = "Circular sintética.pdf"
CIRCULAR_DATE = "2025-12-01"
VIGENTE = "garantía del 3 % del monto"
FIXTURE_BLOCK = """    circulares:
      - documento: Circular sintética.pdf
        fecha: 2099-01-10
        efecto: modifica
        tramo: circ/1
        pagina: 1
        ancla: "garantía del 3 %"
        texto_original: "garantía del 5 %"
        texto_vigente: "garantía del 3 %"
"""


def block_yaml(*, fecha=CIRCULAR_DATE, efecto="modifica", original="garantía del 5 %",
               vigente=VIGENTE, ancla=VIGENTE, tramo="circ/1", document=CIRCULAR_FILE):
    """Un bloque `circulares:` con el formato real de las listas: `texto_original` con
    `{documento, pagina, cita}`."""
    lines = ["    circulares:",
             f"      - documento: {document}",
             f'        fecha: "{fecha}"',
             f"        efecto: {efecto}",
             f'        tramo: "{tramo}"',
             "        pagina: 1",
             f'        ancla: "{ancla}"',
             f'        texto_original: {{documento: {FILE}, pagina: 1, cita: "{original}"}}']
    if vigente:
        lines.append(f'        texto_vigente: "{vigente}"')
    return "\n".join(lines) + "\n"


@pytest.fixture
def circular_case(case, operator_user, tmp_path, monkeypatch):
    """El caso con la propuesta ya medida y una circular sintética cargada en el
    procedimiento. Devuelve un objeto con la corrida, la circular, el tramo y ayudas para
    escribir la lista, agregar fuentes y medir REQ-031."""
    from datetime import date

    from tests.tenders.pdfs import para, tender_pdf

    procedure, _, path, text = case
    # La versión queda abierta para agregarle fuentes sintéticas (la medición la descartaría).
    monkeypatch.setattr(ev, "_discard", lambda *args, **kwargs: None)
    report = run_measure(operator_user, procedure, path, tmp_path)
    run = m.MatrixRun.objects.get(pk=report.results[0]["run"])
    pdf = tender_pdf([[para("CIRCULAR SINTÉTICA N° 1", "1. Se modifica la cláusula 1.1.",
                            f"1.1. Los oferentes deberán constituir una {VIGENTE}.",
                            "2. El plazo de entrega será de 10 días corridos.")]],
                     header=None)
    circular = load_and_read(operator_user, procedure, pdf,
                             kind=m.DocumentKind.CIRCULAR_MODIFICATORIA,
                             title="Circular sintética", issued_on=date(2025, 12, 1))
    segment = m.Segment.objects.get(reading__document=circular, text__contains=VIGENTE)

    class Case:
        pass

    c = Case()
    c.procedure, c.path, c.text, c.run, c.segment = procedure, path, text, run, segment
    c.version, c.circular, c.report = run.version, circular, report

    def write_list(block=None, **options):
        options.setdefault("tramo", segment.key)
        block = block or block_yaml(**options)
        assert FIXTURE_BLOCK in text
        listed = text.replace(FIXTURE_BLOCK, block).replace("0" * 64, circular.file_sha256)
        write(path, listed)
        return ev.load_expected(path)

    def row_with(phrase):
        return m.RequirementQuote.objects.get(requirement__version=c.version,
                                              text__contains=phrase).requirement

    def add_source(requirement, *, effect="modifica", phrase=VIGENTE, issued=date(2025, 12, 1),
                   original=None):
        start = segment.char_start + segment.text.index(phrase)
        extra = {}
        if original:
            where, phrase_o = original
            seg = m.Segment.objects.get(reading__document=where, text__contains=phrase_o)
            offset = seg.char_start + seg.text.index(phrase_o)
            extra = {"original_segment": seg, "original_char_start": offset,
                     "original_char_end": offset + len(phrase_o)}
        return m.RequirementSource.objects.create(
            requirement=requirement, quote=requirement.quotes.order_by("order").first(),
            effect=effect, segment=segment, char_start=start, char_end=start + len(phrase),
            text=phrase, issued_on=issued, **extra)

    def measure():
        expected = ev.load_expected(path)
        check = ev.verify_expected(expected, procedure)
        return expected, check, ev.measure_version(c.run, expected, check)

    c.write_list, c.row_with, c.add_source, c.measure = write_list, row_with, add_source, measure
    return c


def test_circular_row_with_the_four_points_meets(circular_case):
    """REQ-031: una fila de circular con efecto, original, vigente, documento y fecha cumple
    los cuatro puntos; el bloque se lee en el formato real de las listas."""
    c = circular_case
    expected = c.write_list()
    block = next(i for i in expected.items if i.id == "S-001").blocks[0]
    assert block.original_anchor == "garantía del 5 %" and block.original_document == FILE
    c.add_source(c.row_with("garantía del 5 %"))

    _, check, measures = c.measure()

    assert check.ok, check.problems
    info = measures["circulars"]
    assert info["met"]["ok"] == info["met"]["total"] == 1
    assert all(info["points"][name]["ok"] == 1 for name in ev.POINTS)
    assert info["noise"]["sources"] == 0 and info["failing"] == []
    assert [r for r in measures["lines"] if r["tipo"] == "circular"][0]["estado"] == "cumple"


def test_wrong_original_text_fails_only_point_two(circular_case):
    """REQ-031: con el texto original equivocado falla solo el punto 2."""
    c = circular_case
    c.write_list(original="multa del 1 % diario")
    c.add_source(c.row_with("garantía del 5 %"))

    info = c.measure()[2]["circulars"]

    assert info["failing"] == [{"id": "S-001", "documento": CIRCULAR_FILE, "puntos": [2]}]
    assert info["met"]["ok"] == 0


def test_different_date_fails_only_point_four(circular_case):
    """REQ-031: con una fecha distinta de la de la fuente falla solo el punto 4."""
    c = circular_case
    c.write_list(fecha="2025-12-02")
    c.add_source(c.row_with("garantía del 5 %"))

    info = c.measure()[2]["circulars"]

    assert info["failing"][0]["puntos"] == [4]


def test_wrong_effect_fails_only_point_one(circular_case):
    """REQ-031: una fuente con otro efecto que el esperado falla solo el punto 1."""
    c = circular_case
    c.write_list()
    c.add_source(c.row_with("garantía del 5 %"), effect="aclara")

    assert c.measure()[2]["circulars"]["failing"][0]["puntos"] == [1]


def test_row_without_source_fails_point_one(circular_case):
    """REQ-031: una fila sin fuente falla el punto 1 (y no cumple)."""
    c = circular_case
    c.write_list()

    info = c.measure()[2]["circulars"]

    assert info["points"]["effect"]["ok"] == 0
    assert 1 in info["failing"][0]["puntos"] and info["met"]["ok"] == 0


def test_precisa_in_the_list_is_an_aclara_source(circular_case):
    """REQ-031: `precisa` (efecto de las listas reales) se mide contra la fuente `aclara`; en
    `suprime` no se exige texto vigente."""
    c = circular_case
    c.write_list(efecto="precisa")
    row = c.row_with("garantía del 5 %")
    c.add_source(row, effect="aclara")
    assert c.measure()[2]["circulars"]["met"]["ok"] == 1

    c.write_list(efecto="suprime", vigente="")
    row.sources.all().delete()
    c.add_source(row, effect="suprime")
    assert c.measure()[2]["circulars"]["met"]["ok"] == 1


def test_original_is_read_from_the_annex_when_the_source_references_it(circular_case):
    """REQ-031: con el original en un tramo aparte (anexo), el original mostrado es ese
    tramo, no la cita alcanzada."""
    c = circular_case
    c.write_list(original="multa del 1 % diario")
    c.add_source(c.row_with("garantía del 5 %"),
                 original=(c.procedure.documents.get(file_name=FILE), "multa del 1 % diario"))

    assert c.measure()[2]["circulars"]["met"]["ok"] == 1


def test_source_in_a_row_without_expected_circular_is_noise_by_document(circular_case):
    """REQ-031: una fuente en una fila sin esperado de circular cuenta como ruido, por
    documento y por fila."""
    c = circular_case
    c.write_list()
    c.add_source(c.row_with("garantía del 5 %"))
    other = c.row_with("multa del 1 % diario")
    c.add_source(other, effect="aclara")

    noise = c.measure()[2]["circulars"]["noise"]

    assert noise["sources"] == 1 and noise["rows"] == 1
    assert noise["by_document"] == {CIRCULAR_FILE: 1}
    assert noise["by_row"] == {str(other.number): 1}


def test_circular_origin_row_without_expected_is_noise(circular_case):
    """REQ-031: un requisito de origen `circular` que ninguna fila esperada pide se cuenta."""
    c = circular_case
    c.write_list()
    c.add_source(c.row_with("garantía del 5 %"))
    row = add_requirement(c.version, "sec-i/3.1")
    m.Requirement.objects.filter(pk=row.pk).update(origin="circular")

    noise = c.measure()[2]["circulars"]["noise"]

    assert noise["unexpected_requirements"] == [row.number]


def test_agrega_measures_the_circular_origin_row_with_its_document_and_date(circular_case):
    """REQ-031: `agrega`: vale la fila de origen `circular` con cita en el documento y la
    fecha esperados; con otra fecha falla el punto 4."""
    c = circular_case
    c.write_list()
    block = block_yaml(efecto="agrega", tramo=c.segment.key, ancla="plazo de entrega",
                       original="", vigente="plazo de entrega será de 10 días")
    old = "    origen: circular\n    renglones: []\n"
    text = c.path.read_text(encoding="utf-8")
    assert old in text
    text = text.replace(old, "    origen: circular\n    renglones: []\n" + block, 1)
    write(c.path, text)
    c.add_source(c.row_with("garantía del 5 %"))
    segment = m.Segment.objects.get(reading__document=c.circular,
                                    text__contains="plazo de entrega")
    row = m.Requirement.objects.create(
        version=c.version, number=99, category="formal", items=[],
        origin=m.RequirementOrigin.CIRCULAR, state="propuesto", proposed={})
    m.RequirementQuote.objects.create(
        requirement=row, order=1, segment=segment, char_start=segment.char_start,
        char_end=segment.char_end, text=segment.text, scope="")

    measures = c.measure()[2]
    line = next(r for r in measures["lines"] if r.get("id") == "S-006" and r["tipo"] == "circular")

    assert line["estado"] == "cumple" and line["fila"] == 99
    assert measures["circulars"]["noise"]["unexpected_requirements"] == []

    head, _, tail = text.rpartition(f'fecha: "{CIRCULAR_DATE}"')  # el bloque de S-006
    write(c.path, head + 'fecha: "2025-12-09"' + tail)
    failing = c.measure()[2]["circulars"]["failing"]
    assert [f["id"] for f in failing] == ["S-006"] and failing[0]["puntos"] == [4]


def test_list_scope_circulars_measures_only_req_031(circular_case):
    """REQ-031: una lista con `alcance: circulares` no calcula encontrados, sobrantes ni
    tope del resto, y el bloqueo es solo el de las filas de circular."""
    c = circular_case
    row = c.row_with("garantía del 5 %")
    c.add_source(row)
    head = c.text.split("requisitos:")[0].replace(
        "uso: primera_corrida", "uso: ajuste\nalcance: circulares")
    body = ("requisitos:\n  - id: S-001\n    documento: Pliego sintético.pdf\n"
            "    tramo: sec-i/1.1\n    pagina: 1\n    ancla: \"garantía del 5 % del monto\"\n"
            "    clase: economico\n    renglones: []\n" + block_yaml(tramo=c.segment.key))
    write(c.path, head + body)
    expected, check, _ = c.measure()
    assert expected.circulars_only

    result = ev._result_of_run(c.run, c.version, c.procedure, expected, check.readings)
    measures = result["measures"]

    assert measures["scope"] == "circulares"
    assert "found" not in measures and "leftover_ratio" not in measures
    assert measures["circulars"]["met"]["ok"] == 1
    report = ev.Report(c.path.parent, expected, check, [result])
    assert report.blocking == []
    private = ev._summary(report, public=False)
    assert "solo circulares" in private and "Sobrantes" not in private

    row.sources.all().delete()
    result = ev._result_of_run(c.run, c.version, c.procedure, expected, check.readings)
    assert any("REQ-031" in r for r in ev.Report(c.path.parent, expected, check,
                                                  [result]).blocking)


def test_verify_expected_rejects_a_block_whose_anchor_is_not_in_the_reading(circular_case):
    """REQ-031: `--verificar-esperada` rechaza un bloque cuyo ancla (de la circular, original
    o vigente) no está en la lectura, y una fecha que no es la del documento."""
    c = circular_case
    for options in ({"ancla": "texto que la circular no tiene"},
                    {"vigente": "texto vigente inventado que no está"},
                    {"original": "texto original inventado que no está"},
                    {"fecha": "2025-12-02"}):
        c.write_list(**options)
        check = ev.verify_expected(ev.load_expected(c.path), c.procedure)
        assert not check.ok and any("S-001" in p for p in check.problems), options
    c.write_list()
    assert ev.verify_expected(ev.load_expected(c.path), c.procedure).ok


def test_list_block_with_a_bad_effect_or_date_is_refused(circular_case):
    """REQ-031: un bloque con efecto o fecha inválidos no se lee."""
    c = circular_case
    for options in ({"efecto": "borra"}, {"fecha": "ayer"}):
        with pytest.raises(ev.ExpectedError, match="circulares"):
            c.write_list(**options)


def test_public_summary_has_no_text_of_the_circular_rows(circular_case):
    """P4, REQ-031: `resumen-publico.md` no contiene el texto de ninguna ancla ni cita de las
    filas de circular (se busca cada una) y sí lleva cuentas, claves y documentos."""
    c = circular_case
    expected = c.write_list()
    c.add_source(c.row_with("garantía del 5 %"))
    c.add_source(c.row_with("multa del 1 % diario"), effect="aclara")
    _, check, _ = c.measure()
    result = ev._result_of_run(c.run, c.version, c.procedure, expected, check.readings)
    report = ev.Report(c.path.parent, expected, check, [result])

    public = ev._summary(report, public=True)

    block = next(i for i in expected.items if i.id == "S-001").blocks[0]
    for text in (block.anchor, block.original_anchor, block.current_anchor,
                 *(q.text for q in m.RequirementQuote.objects.filter(
                     requirement__version=c.version))):
        assert text not in public
    assert "REQ-031, cumplen los cuatro puntos: " in public
    assert "ruido" in public and CIRCULAR_FILE in public


def test_old_list_without_blocks_gives_the_usual_measures(case, operator_user, tmp_path):
    """REQ-031: una lista sin bloques `circulares` da las medidas de siempre y no agrega
    líneas de circulares; las corridas viejas se regeneran."""
    procedure, _, path, text = case
    write(path, text.replace(FIXTURE_BLOCK, ""))
    report = run_measure(operator_user, procedure, path, tmp_path)
    expected = ev.load_expected(path)

    assert report.results[0]["measures"]["circulars"] is None
    assert not [r for r in report.results[0]["measures"]["lines"] if r["tipo"] == "circular"]
    assert "la lista no tiene bloques" in (report.folder / "resumen.md").read_text(
        encoding="utf-8")
    again = ev.regenerate_summaries(procedure, expected, report.folder)
    assert again.results[0]["measures"]["circulars"] is None


# --- Correcciones de la verificación de T-117 --------------------------------------------------


def test_block_document_not_in_the_list_blocks(circular_case):
    """REQ-031: un bloque cuyo `documento` no figura en los documentos de la lista bloquea (un
    nombre mal escrito no puede quedar "sin medir")."""
    c = circular_case
    c.write_list(document="Circular mal escrita.pdf")

    check = ev.verify_expected(ev.load_expected(c.path), c.procedure)

    assert not check.ok and any("S-001" in p and "lista" in p for p in check.problems)


def test_block_document_not_loaded_blocks_unless_declared_so(case):
    """REQ-031: un bloque cuya circular está en la lista pero no cargada bloquea; solo se
    informa (sin medir) si la lista declara `cargado: false` para ese documento."""
    procedure, _, path, text = case
    assert "    cargado: false\n" in text
    declared = ev.verify_expected(ev.load_expected(path), procedure)
    assert declared.ok and any("no está cargada" in n for n in declared.notes)

    write(path, text.replace("    cargado: false\n", ""))
    undeclared = ev.verify_expected(ev.load_expected(path), procedure)

    assert not undeclared.ok
    assert any("S-001" in p and "no está cargada" in p for p in undeclared.problems)


def test_unmeasured_declared_circular_is_reported_in_the_summary(case, operator_user, tmp_path):
    """REQ-031: la circular declarada sin cargar queda "sin medir" y el resumen público lo
    informa con la clave de la fila."""
    procedure, _, path, _ = case

    report = run_measure(operator_user, procedure, path, tmp_path)

    assert report.results[0]["measures"]["circulars"]["unmeasured"] == ["S-001"]
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "sin medir porque la circular no está cargada: S-001" in public


def test_the_four_points_must_be_met_by_one_same_source(circular_case):
    """REQ-031: los cuatro puntos los cumple una misma fuente; puntos repartidos entre dos
    fuentes de la fila no cuentan."""
    from datetime import date

    c = circular_case
    c.write_list()
    row = c.row_with("garantía del 5 %")
    c.add_source(row, effect="modifica", issued=date(2025, 12, 2))  # falla el punto 4
    c.add_source(row, effect="aclara", issued=date(2025, 12, 1))  # falla el punto 1

    info = c.measure()[2]["circulars"]

    assert info["met"]["ok"] == 0
    assert info["failing"] and len(info["failing"][0]["puntos"]) == 1
    # los puntos sueltos no se suman entre fuentes
    assert sum(info["points"][name]["ok"] for name in ev.POINTS) == 3


def test_public_summary_failing_row_line_has_no_text(circular_case):
    """P4, REQ-031: con una fila que no cumple, la línea "no cumple" del resumen público lleva
    la clave, el documento y los puntos, y ningún texto de ancla ni de cita."""
    c = circular_case
    expected = c.write_list(original="multa del 1 % diario")
    c.add_source(c.row_with("garantía del 5 %"))
    _, check, _ = c.measure()
    result = ev._result_of_run(c.run, c.version, c.procedure, expected, check.readings)
    report = ev.Report(c.path.parent, expected, check, [result])

    public = ev._summary(report, public=True)

    line = next(row for row in public.splitlines() if "no cumple S-001" in row)
    assert "puntos 2" in line and CIRCULAR_FILE in line
    block = next(i for i in expected.items if i.id == "S-001").blocks[0]
    for text in (block.anchor, block.original_anchor, block.current_anchor,
                 *(q.text for q in m.RequirementQuote.objects.filter(
                     requirement__version=c.version))):
        assert text not in public


# --- Memoria de la medición (T-121) ---------------------------------------------------------


def test_the_rows_share_one_reading_instead_of_loading_one_per_quote(
        case, operator_user, tmp_path):
    """REQ-024: la medición no carga la lectura (texto canónico y páginas, de varios MB en un
    pliego real) una vez por cita: con ~300 filas y ~1.600 citas el contenedor pasaba de 14 GB
    y el kernel lo mató. Todas las citas de una misma lectura comparten una sola instancia, y
    las consultas de lecturas no crecen con las filas."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    procedure, _, path, _ = case
    report = run_measure(operator_user, procedure, path, tmp_path)
    version = m.MatrixRun.objects.get(pk=report.results[0]["run"]).version

    with CaptureQueriesContext(connection) as queries:
        rows = ev._proposed(version) + ev._suggestions(version)

    quotes = [q for row in rows for q in row.quotes]
    assert len(quotes) >= 2
    readings = {}
    for quote in quotes:
        readings.setdefault(quote.segment.reading_id, set()).add(id(quote.segment.reading))
    assert all(len(ids) == 1 for ids in readings.values())
    for row in rows:
        assert row.reading is row.quotes[0].segment.reading
    reading_queries = [q for q in queries.captured_queries if 'FROM "tenders_reading"' in q["sql"]]
    assert len(reading_queries) <= 2


# --- Correcciones de la medición (T-123) --------------------------------------------------------


def test_technical_row_quote_in_another_reading_does_not_match_an_expected(
        case, operator_user, tmp_path, monkeypatch):
    """REQ-024: una cita de una fila técnica en otra lectura (un anexo) cuyas posiciones
    contienen numéricamente las del ancla del pliego no empareja al esperado: la cita tiene
    que ser de la misma lectura que el esperado."""
    from tests.tenders.pdfs import para, tender_pdf

    procedure, _, path, _ = case
    annex = load_and_read(
        operator_user, procedure,
        tender_pdf([[para("ANEXO SINTÉTICO", "1. Los planos se entregan en papel.")]],
                   header=None),
        kind=m.DocumentKind.ANEXO, title="Anexo sintético")
    segment = annex.readings.get().segments.order_by("order").first()
    # Una cita del anexo que abarca todo el rango numérico del pliego.
    foreign = m.RequirementQuote(order=9, segment=segment, char_start=0, char_end=10**6,
                                 text="x", scope=m.QuoteScope.PROPIA)
    original = ev._proposed

    def rows_without_the_guarantee(version):
        rows = [r for r in original(version)
                if "garantía" not in " ".join(q.text for q in r.quotes)]
        technical = next(r for r in rows if r.category == ev.TECHNICAL)
        technical.quotes.append(foreign)
        return rows

    monkeypatch.setattr(ev, "_proposed", rows_without_the_guarantee)

    report = run_measure(operator_user, procedure, path, tmp_path)

    line = by_id(report)["S-001"]
    assert line["estado"] == "faltante"
    assert "clase_propuesta" not in line


def _suppress(c, phrase):
    """Deja la fila de `phrase` quitada por una circular, con una fuente `suprime`."""
    row = c.row_with(phrase)
    c.add_source(row, effect="suprime")
    m.Requirement.objects.filter(pk=row.pk).update(state=m.RequirementState.QUITADO)
    return row


def _line(measures, item_id):
    return next(r for r in measures["lines"] if r.get("id") == item_id and r["tipo"] == "esperado")


def test_row_suppressed_by_a_circular_matches_an_expected_with_a_suprime_block(circular_case):
    """REQ-031: un esperado con bloque `circulares` de efecto `suprime` empareja con la fila
    quitada por la circular y cuenta como encontrado; la fila no es sobrante."""
    c = circular_case
    c.write_list(efecto="suprime", vigente=None)
    row = _suppress(c, "garantía del 5 %")

    _, _, measures = c.measure()

    line = _line(measures, "S-001")
    assert line["estado"] == "encontrado" and line["detalle"] == "suprimido por circular"
    assert measures["suppressed"]["ids"] == ["S-001"]
    assert not measures["causes"].get(ev.SUPPRESSED)
    assert not [r for r in measures["lines"]
                if r["tipo"] == "propuesto" and r.get("numero") == row.number]
    info = measures["circulars"]
    assert info["met"]["ok"] == info["met"]["total"] == 1


def test_expected_without_suprime_block_with_only_a_suppressed_match_has_its_cause(
        circular_case):
    """REQ-031: un esperado sin bloque `suprime` cuya única pareja es una fila quitada por una
    circular es un faltante con causa `suprimido_por_circular`."""
    c = circular_case
    c.write_list()  # el bloque de S-001 es `modifica`
    _suppress(c, "garantía del 5 %")

    _, _, measures = c.measure()

    line = _line(measures, "S-001")
    assert line["estado"] == "faltante" and line["causa"] == ev.SUPPRESSED
    assert measures["causes"][ev.SUPPRESSED] == 1


def test_suppressed_row_is_matched_one_to_one(circular_case):
    """REQ-031: la regla uno a uno vale también para las filas quitadas: una fila suprimida no
    es pareja de dos esperados."""
    c = circular_case
    c.write_list(efecto="suprime", vigente=None)
    _suppress(c, "garantía del 5 %")
    _, check, _ = c.measure()
    located = [check.located["S-001"], check.located["S-001"]]

    assert len(ev._pairs(located, ev._suppressed(c.version))) == 1
