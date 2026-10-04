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
