"""Verdad ampliada celda por celda: formato, cargador y `--verificar-verdad` (REQ-118; plan 016,
«Paso 1»; ADR-0069; T-271). Caso chico inventado y público (P4); no se usa el modelo salvo para
medir con la verdad."""

import copy
import hashlib
import re
from dataclasses import replace
from datetime import date
from io import StringIO

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluon.accounts import permissions
from evaluon.assessment import evaluation as ev
from evaluon.assessment import models as am
from evaluon.tenders.services.validation import latest_validated
from tests.assessment.fakes import CASO_CHICO, model  # noqa: F401 - `model` es fixture
from tests.assessment.test_evaluation import LIST, load_small_case_portal, oracle_for

pytestmark = pytest.mark.django_db

TRUTH = CASO_CHICO / "verdad-celdas.yaml"
REVIEWER = "Coordinador (caso chico inventado)"


def raw_truth():
    return yaml.safe_load(TRUTH.read_text(encoding="utf-8"))


def write_truth(tmp_path, change=None, *, name="verdad-celdas.yaml", refresh=True):
    """La verdad del caso chico, con `change(raw)` aplicado, en `tmp_path`. Recalcula la huella
    salvo `refresh=False`."""
    raw = raw_truth()
    if change is not None:
        change(raw)
    if refresh:
        raw["huella"] = ev.truth_fingerprint(raw["celdas"])
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def cell_of(raw, offer, requirement):
    return next(c for c in raw["celdas"] if c["oferta"] == offer and c["requisito"] == requirement)


def variant(truth, offer, requirement, **changes):
    """La misma verdad con una celda cambiada, en memoria (la base ya está armada)."""
    cells = [replace(c, **changes) if (c.offer, c.requirement) == (offer, requirement) else c
             for c in truth.truth]
    return replace(truth, truth=cells)


def with_basis(truth, offer, requirement, **changes):
    cell = next(c for c in truth.truth if (c.offer, c.requirement) == (offer, requirement))
    return variant(truth, offer, requirement, basis=dict(cell.basis, **changes))


def problems_of(truth, expected, procedure):
    return ev.verify_truth(truth, expected, procedure).problems


@pytest.fixture
def small(evaluator_user, fake_ai):
    """El caso chico armado en la base: `(lista, procedimiento, ofertas)`."""
    expected = ev.load_expected(LIST)
    procedure, offers = ev.build_case(evaluator_user, expected)
    return expected, procedure, offers


# --- El formato y el cargador (sin base) -------------------------------------------------------


def test_the_small_case_truth_loads_by_requirement_and_keeps_the_old_format_working(tmp_path):
    """REQ-118: `verdad-celdas.yaml` carga con lote, huella, quién armó y las 9 celdas por
    oferta y M-NNN; `no_determinado` es un resultado admitido; el formato de `celdas-comision`
    (por fila) sigue cargando igual."""
    truth = ev.load_commission_cells(TRUTH)
    assert truth.kind == "verdad" and truth.batch == "ajuste"
    assert truth.case == "caso-chico-evaluacion" and truth.procedure == "CASO-CHICO-EVALUACION"
    assert truth.approval and truth.armed_by["agente"]
    assert len(truth.truth) == 9 and truth.cells == {}
    assert truth.fingerprint == ev.truth_fingerprint(raw_truth()["celdas"])
    assert ev.COMMISSION_RESULTS["no_determinado"] == am.Outcome.NO_DETERMINADO
    first = truth.truth[0]
    assert (first.offer, first.requirement, first.result) == (1, "M-001", "cumple")
    assert first.reviewed and first.review["por"] == REVIEWER
    corrected = next(c for c in truth.truth if c.review["estado"] == "corregida")
    assert corrected.review["resultado_anterior"] == "no_se_encontro_documento"

    old = {"procedimiento": "X", "visto_bueno": "Coordinador, 2026-10-15",
           "celdas": [{"oferta": 1, "fila": 1, "resultado": "cumple", "nota": "ok"},
                      {"oferta": 1, "fila": 2, "resultado": "no_determinado"}]}
    old["huella"] = ev.cells_fingerprint(old["celdas"])
    path = tmp_path / "celdas-comision-x.yaml"
    path.write_text(yaml.safe_dump(old, allow_unicode=True), encoding="utf-8")
    loaded = ev.load_commission_cells(path)
    assert loaded.kind == "comision" and loaded.truth == []
    assert loaded.cells == {(1, 1): am.Outcome.CUMPLE, (1, 2): am.Outcome.NO_DETERMINADO}
    assert loaded.resolved({}) is loaded


def test_the_truth_is_rejected_when_its_shape_or_fingerprint_is_wrong(tmp_path):
    """REQ-118: una huella que no es la de las celdas, un lote o un requisito inválido, una celda
    repetida o una revisión a medias no cargan; sin visto bueno no se usa (pero se puede
    verificar)."""
    def bad_fingerprint(raw):
        cell_of(raw, 1, "M-001")["resultado"] = "no_cumple"      # sin recalcular la huella

    def no_batch(raw):
        del raw["lote"]

    def bad_requirement(raw):
        cell_of(raw, 1, "M-001")["requisito"] = "R1"

    def repeated(raw):
        raw["celdas"].append(copy.deepcopy(cell_of(raw, 1, "M-001")))

    def bad_result(raw):
        cell_of(raw, 1, "M-001")["resultado"] = "quizas"

    def half_review(raw):
        del cell_of(raw, 1, "M-001")["revision"]["fecha"]

    def corrected_without_previous(raw):
        del cell_of(raw, 2, "M-003")["revision"]["resultado_anterior"]

    def bad_basis(raw):
        cell_of(raw, 1, "M-001")["fundamento"]["tipo"] = "intuicion"

    for change, message, refresh in (
            (bad_fingerprint, "huella", False), (no_batch, "lote", True),
            (bad_requirement, "requisito", True), (repeated, "repetida", True),
            (bad_result, "resultado", True), (half_review, "revisión", True),
            (corrected_without_previous, "resultado_anterior", True),
            (bad_basis, "fundamento", True)):
        path = write_truth(tmp_path, change, refresh=refresh)
        with pytest.raises(ev.ExpectedError, match=message):
            ev.load_commission_cells(path)

    def unsigned(raw):
        raw["visto_bueno"] = "pendiente"
    path = write_truth(tmp_path, unsigned)
    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_commission_cells(path)
    assert ev.load_commission_cells(path, require_approval=False).approval == ""


def test_resolving_the_truth_keeps_only_reviewed_cells_with_their_matrix_row(tmp_path):
    """REQ-118: `resolved` traduce M-NNN a la fila de la matriz y deja solo las celdas con
    revisión; una celda sin revisión no se cuenta, un requisito fuera de la matriz se rechaza y
    una verdad sin ninguna revisada no se mide."""
    rows = {f"M-{n:03d}": n for n in range(1, 11)}
    full = ev.load_commission_cells(TRUTH).resolved(rows)
    assert len(full.cells) == 9
    assert full.cells[(1, 1)] == am.Outcome.CUMPLE and full.cells[(3, 3)] == am.Outcome.SIN_DOCUMENTO
    assert full.cells[(2, 3)] == am.Outcome.NO_DETERMINADO
    assert full.cells[(3, 1)] == am.Outcome.NO_CUMPLE

    def one_unreviewed(raw):
        del cell_of(raw, 1, "M-003")["revision"]
    partial = ev.load_commission_cells(write_truth(tmp_path, one_unreviewed)).resolved(rows)
    assert len(partial.cells) == 8 and (1, 3) not in partial.cells

    def none_reviewed(raw):
        for cell in raw["celdas"]:
            cell.pop("revision")
    nothing = ev.load_commission_cells(write_truth(tmp_path, none_reviewed, name="n.yaml"))
    with pytest.raises(ev.ExpectedError, match="ninguna celda con revisión"):
        nothing.resolved(rows)
    with pytest.raises(ev.MeasurementRefused, match="M-004"):
        ev.load_commission_cells(TRUTH).resolved({k: v for k, v in rows.items() if k != "M-004"})


def test_a_system_abstention_against_an_undetermined_truth_is_exact():
    """REQ-118: «no determinado» del sistema contra «no determinado» de la verdad es exacto; el
    «no determinado» contra una celda decidida es abstención y una celda decidida contra un
    «no determinado» de la verdad es errada."""
    truth = ev.load_commission_cells(TRUTH).resolved({f"M-{n:03d}": n for n in range(1, 11)})
    outcomes = {(1, 1): am.Outcome.CUMPLE, (2, 3): am.Outcome.NO_DETERMINADO,
                (2, 4): am.Outcome.CUMPLE, (3, 1): am.Outcome.NO_DETERMINADO}
    cells = [ev.observed_cell(offer, row, outcome) for (offer, row), outcome in outcomes.items()]
    accuracy = ev.cell_accuracy(cells, truth)
    assert accuracy["exact_cells"] == [(1, 1), (2, 3)]
    assert accuracy["wrong_cells"] == [(2, 4, am.Outcome.NO_DETERMINADO, am.Outcome.CUMPLE)]
    assert accuracy["abstained_cells"] == [(3, 1)]
    assert accuracy["total"] == 4 and len(accuracy["without_result"]) == 5


# --- Las comprobaciones contra la lectura (con base) -------------------------------------------


def test_verify_truth_counts_the_small_case_and_rejects_what_is_not_in_the_reading(small):
    """REQ-118: el caso chico da los conteos esperados (9 celdas, 7 decididas, 9 revisadas, 6 citas
    ubicadas de 6, 2 «no determinado» con pregunta, 0 corridas); una cita que no está palabra por
    palabra en la lectura, en otra página o de un documento que no está se rechaza; una celda sin
    revisión no se cuenta."""
    expected, procedure, _ = small
    truth = ev.load_commission_cells(TRUTH)
    check = ev.verify_truth(truth, expected, procedure)
    assert check.problems == [] and check.ok
    assert (check.cells, check.decided, check.decided_reviewed, check.reviewed) == (9, 7, 7, 9)
    assert check.by_result == {"cumple": 5, "no_cumple": 1, "no_se_encontro_documento": 1,
                               "no_determinado": 2}
    assert (check.cites_needed, check.cites_located) == (6, 6)
    assert (check.undetermined, check.undetermined_named) == (2, 2)
    assert check.reviewers == {REVIEWER: 9} and check.dates == ("2026-10-15", "2026-10-15")
    assert check.runs == 0 and check.frozen.startswith("no se exige")
    text = "\n".join(check.lines())
    assert "Decididas: 7; decididas con revisión (las que cuentan): 7" in text
    assert "Citas ubicadas en la lectura o ítem del Portal: 6 de 6" in text
    assert "Verdad: sin fallas" in text
    total = ev.truth_total([check])
    assert (total["cases"], total["cells"], total["decided_reviewed"]) == (1, 9, 7)

    invented = "Declaro bajo juramento que me encuentro habilitado y además tengo 10 empleados"
    altered = with_basis(truth, 1, "M-001", texto=invented)
    problems = problems_of(altered, expected, procedure)
    assert len(problems) == 1 and "oferta 1, M-001" in problems[0]
    assert "palabra por palabra" in problems[0]
    assert invented not in problems[0]          # la verdad real no se repite en el informe
    in_page_2 = with_basis(truth, 1, "M-001", pagina=2)
    assert "no está palabra por palabra en la página 2" in problems_of(
        in_page_2, expected, procedure)[0]
    no_page = with_basis(truth, 1, "M-001", pagina=9)
    assert "la página 9 no está en la lectura" in problems_of(no_page, expected, procedure)[0]
    other = with_basis(truth, 1, "M-001", documento="ofertas/oferente-a/inexistente.pdf")
    assert "no está cargado" in problems_of(other, expected, procedure)[0]
    by_name = with_basis(truth, 1, "M-001", documento="oferta-propuesta.pdf")
    assert problems_of(by_name, expected, procedure) == []        # el nombre sin carpetas vale

    unreviewed = variant(truth, 1, "M-003", review=None)
    check = ev.verify_truth(unreviewed, expected, procedure)
    assert (check.decided, check.decided_reviewed, check.reviewed, check.unreviewed) == (7, 6, 8, 1)
    assert check.ok and "sin revisión: 1 (no se cuentan)" in "\n".join(check.lines())


def test_verify_truth_requires_citation_question_and_documents_by_result(small):
    """REQ-118: un «cumple» o «no cumple» sin cita ni dato del Portal, un «no determinado» sin
    pregunta ni documento nombrado, un «no se encontró el documento» sin los documentos leídos, un
    «no aplica» sin fundamento, un requisito fuera de la lista o una oferta que no está, se
    señalan."""
    expected, procedure, _ = small
    truth = ev.load_commission_cells(TRUTH)
    by_absence = with_basis(truth, 1, "M-001", tipo="ausencia")
    assert "sin cita de la oferta ni dato del Portal" in problems_of(
        by_absence, expected, procedure)[0]
    check = ev.verify_truth(by_absence, expected, procedure)
    assert (check.cites_needed, check.cites_located) == (6, 5)
    no_basis = variant(truth, 3, "M-001", basis={})
    assert "sin cita" in problems_of(no_basis, expected, procedure)[0]
    no_question = variant(truth, 2, "M-003", question="")
    assert "sin pregunta ni documento nombrado" in problems_of(
        no_question, expected, procedure)[0]
    named_document = variant(truth, 2, "M-003", question="", basis={
        "tipo": "documento_faltante", "documento": "certificado de vigencia"})
    assert problems_of(named_document, expected, procedure) == []
    no_documents = with_basis(truth, 3, "M-003", nota="")
    assert "documentos leídos" in problems_of(no_documents, expected, procedure)[0]
    not_applicable = variant(truth, 3, "M-003", result="no_aplica", basis={})
    assert "«no aplica» sin fundamento" in problems_of(not_applicable, expected, procedure)[0]
    unknown_requirement = replace(truth, truth=truth.truth + [
        replace(truth.truth[0], requirement="M-099")])
    assert "no está en la lista esperada" in "\n".join(
        problems_of(unknown_requirement, expected, procedure))
    unknown_offer = replace(truth, truth=truth.truth + [replace(truth.truth[0], offer=7)])
    assert "la oferta no está en el procedimiento" in "\n".join(
        problems_of(unknown_offer, expected, procedure))
    other_case = replace(truth, procedure="OTRO-PROCEDIMIENTO")
    assert "no es el del caso" in problems_of(other_case, expected, procedure)[0]
    with pytest.raises(ev.ExpectedError, match="no es una verdad"):
        ev.verify_truth(replace(truth, kind="comision"), expected, procedure)


def test_verify_truth_checks_the_portal_item(small, evaluator_user):
    """REQ-118: un dato del Portal vale como fundamento si el Portal trae ese dato de esa oferta
    (garantía, total, CUIT o cotización); si no lo trae, o falta el tipo o el valor, se señala."""
    expected, procedure, offers = small
    truth = ev.load_commission_cells(TRUTH)
    portal = {"tipo": "dato_portal", "portal": "garantia", "valor": "26.750"}
    cell = variant(truth, 1, "M-001", basis=portal)
    assert "el Portal no trae ese dato" in problems_of(cell, expected, procedure)[0]
    load_small_case_portal(evaluator_user, procedure, offers)
    assert problems_of(cell, expected, procedure) == []
    total = variant(truth, 1, "M-001", basis=dict(portal, portal="total", valor="535000"))
    assert problems_of(total, expected, procedure) == []
    wrong = variant(truth, 1, "M-001", basis=dict(portal, valor="99.999"))
    assert "el Portal no trae ese dato" in problems_of(wrong, expected, procedure)[0]
    other_offer = variant(truth, 2, "M-001", basis=portal)
    assert "el Portal no trae ese dato" in problems_of(other_offer, expected, procedure)[0]
    incomplete = variant(truth, 1, "M-001", basis={"tipo": "dato_portal"})
    assert "lleva `portal`" in problems_of(incomplete, expected, procedure)[0]


def test_an_acceptance_case_needs_a_matching_freeze_and_no_saved_evaluation(
        small, evaluator_user, tmp_path):
    """REQ-118: en un caso de aceptación, el congelado falta (pendiente mientras la verdad no está
    firmada), coincide o no coincide; y un caso de aceptación con una corrida de evaluación
    guardada se señala (en uno de ajuste solo se informa)."""
    expected, procedure, _ = small

    def acceptance(raw):
        raw["lote"] = "aceptacion"

    def unsigned(raw):
        acceptance(raw)
        raw["visto_bueno"] = "pendiente"

    folder = tmp_path / "aceptacion"
    folder.mkdir()
    path = write_truth(folder, acceptance)
    truth = ev.load_commission_cells(path)
    check = ev.verify_truth(truth, expected, procedure)
    assert check.problems == ["la verdad tiene visto bueno y no hay congelado-016.txt"]
    assert check.frozen == "falta"
    draft = ev.load_commission_cells(write_truth(tmp_path, unsigned, name="borrador.yaml"),
                                     require_approval=False)
    check = ev.verify_truth(draft, expected, procedure)
    assert check.ok and check.frozen.startswith("pendiente")

    frozen = folder / ev.FROZEN_FILE
    frozen.write_text(f"huella-verdad: {truth.fingerprint}\nhuella-lista: {expected.sha256}\n"
                      "commit: 0123456789abcdef\nfecha: 2026-10-15\n", encoding="utf-8")
    check = ev.verify_truth(truth, expected, procedure)
    assert check.ok and check.frozen == "coincide (commit 0123456789ab, 2026-10-15)"

    frozen.write_text(f"huella-verdad: {'0' * 64}\nhuella-lista: {expected.sha256}\n"
                      "commit: 0123456789abcdef\nfecha: 2026-10-15\n", encoding="utf-8")
    assert "la huella de la verdad cambió" in ev.verify_truth(truth, expected, procedure).problems[0]
    frozen.write_text(f"huella-verdad: {truth.fingerprint}\nhuella-lista: {'1' * 64}\n"
                      "commit: 0123456789abcdef\nfecha: 2026-10-15\n", encoding="utf-8")
    assert "la lista esperada cambió" in ev.verify_truth(truth, expected, procedure).problems[0]
    frozen.write_text(f"huella-verdad: {truth.fingerprint}\n", encoding="utf-8")
    assert "no trae huella-lista, commit, fecha" in ev.verify_truth(
        truth, expected, procedure).problems[0]

    frozen.write_text(f"huella-verdad: {truth.fingerprint}\nhuella-lista: {expected.sha256}\n"
                      "commit: 0123456789abcdef\nfecha: 2026-10-15\n", encoding="utf-8")
    version = latest_validated(procedure)
    offer = procedure.offers.first()
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[offer.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=evaluator_user)
    am.Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=1, channel=am.Channel.EVAL,
        documents=[], norms={}, models_used={}, parameters={}, prompt_versions={})
    check = ev.verify_truth(truth, expected, procedure)
    assert check.runs == 1 and not check.ok
    assert "1 corridas de evaluación guardadas" in check.problems[0]
    adjustment = ev.load_commission_cells(TRUTH)
    check = ev.verify_truth(adjustment, expected, procedure)
    assert check.ok and check.runs == 1


# --- La medida con la verdad y el comando ------------------------------------------------------


def test_measuring_with_the_truth_counts_only_reviewed_cells_by_matrix_row(
        small, model, evaluator_user, tmp_path):
    """REQ-118: `measure` con el archivo de verdad traduce M-NNN a la fila de la matriz validada y
    mide la exactitud por celda solo con las celdas revisadas (una sin revisión no se cuenta)."""
    expected, procedure, offers = small
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    model.evaluates(oracle_for(raw))

    def one_unreviewed(raw_truth_):
        del cell_of(raw_truth_, 3, "M-004")["revision"]
    truth = ev.load_commission_cells(write_truth(tmp_path, one_unreviewed))
    report = ev.measure(evaluator_user, procedure, expected, offers, tmp_path / "corridas",
                        commit="abc1234", commission_cells=truth)
    accuracy = report.total["accuracy"]
    assert accuracy["total"] == 8
    assert (3, 4) not in accuracy["exact_cells"] + accuracy["abstained_cells"]
    assert (2, 4) in accuracy["exact_cells"]        # «no determinado» contra «no determinado»
    assert report.commission_cells.kind == "verdad" and len(report.commission_cells.cells) == 8
    summary = (report.folder / "parametros.json").read_text(encoding="utf-8")
    assert truth.fingerprint in summary


def _command(user, monkeypatch, *args):
    from tests.tenders.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", user.username, *args, stdout=out)
    return out.getvalue()


def test_the_command_verifies_the_small_case_truth_without_the_model(
        db, operator_user, fake_ai, model, monkeypatch, tmp_path):
    """REQ-118: `medir_evaluacion --caso-chico --verificar-verdad` da los conteos del caso chico
    sin usar el modelo; con una cita inventada o una celda sin revisión lo dice y, en el primer
    caso, termina con error."""
    text = _command(operator_user, monkeypatch, "--caso-chico", "--verificar-verdad")
    assert not model.calls
    for line in ("Celdas: 9 (cumple 5, no cumple 1, no aplica 0, no se encontró el documento 1, "
                 "no determinado 2)",
                 "Decididas: 7; decididas con revisión (las que cuentan): 7",
                 f"Con revisión (quién y cuándo): 9 ({REVIEWER}: 9; del 2026-10-15 al "
                 "2026-10-15); sin revisión: 0 (no se cuentan)",
                 "Citas ubicadas en la lectura o ítem del Portal: 6 de 6",
                 "«No determinado» con pregunta o documento nombrado: 2 de 2",
                 "Congelado (congelado-016.txt): no se exige en el lote de ajuste",
                 "Corridas de evaluación guardadas del procedimiento: 0",
                 "Verdad: sin fallas", "Total de 1 casos: 9 celdas, 7 decididas"):
        assert line in text, line

    def invented(raw):
        cell_of(raw, 3, "M-001")["fundamento"]["texto"] = "El oferente jura no deber nada."
    path = write_truth(tmp_path, invented)
    with pytest.raises(CommandError, match="fallas"):
        _command(operator_user, monkeypatch, "--caso-chico", "--verificar-verdad",
                 "--celdas-comision", str(path))

    def unreviewed(raw):
        del cell_of(raw, 1, "M-001")["revision"]
    path = write_truth(tmp_path, unreviewed, name="sin-revision.yaml")
    text = _command(operator_user, monkeypatch, "--caso-chico", "--verificar-verdad",
                    "--celdas-comision", str(path))
    assert "decididas con revisión (las que cuentan): 6" in text and "sin revisión: 1" in text

    with pytest.raises(CommandError, match="no es una verdad"):
        old = tmp_path / "vieja.yaml"
        cells = [{"oferta": 1, "fila": 1, "resultado": "cumple"}]
        old.write_text(yaml.safe_dump({"huella": ev.cells_fingerprint(cells), "celdas": cells}),
                       encoding="utf-8")
        _command(operator_user, monkeypatch, "--caso-chico", "--verificar-verdad",
                 "--celdas-comision", str(old))


def test_the_truth_file_has_its_fingerprint_and_only_synthetic_content():
    """REQ-118: la verdad del caso chico declara la huella de sus celdas y no nombra nada que no sea
    del caso inventado (P4)."""
    text = TRUTH.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    assert raw["huella"] == ev.truth_fingerprint(raw["celdas"])
    assert raw["huella"] == hashlib.sha256("\n".join(
        f"{c['oferta']}|{c['requisito']}|{c['resultado']}" for c in raw["celdas"]
    ).encode("utf-8")).hexdigest()
    assert isinstance(raw["armada_por"]["fecha"], date)
    assert not re.search(r"\b\d{2}-\d{8}-\d\b", text)      # ningún CUIT
