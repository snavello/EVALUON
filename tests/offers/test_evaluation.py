"""Medición de la ficha del caso chico (REQ-038, REQ-039, REQ-040, REQ-041, REQ-044; plan 008,
"Medición"; ADR-0025; T-130).

El caso es inventado y público (`tests/offers/data/caso-chico/`). El modelo se reemplaza por un
guion que elige pasajes por su texto: lo que se prueba acá es la cuenta, no la IA (la IA se
mide con `medir_fichas --caso-chico` y el modelo real)."""

import dataclasses
import json
import shutil

import pytest
from django.core.management import call_command

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import evaluation as ev
from evaluon.offers import models as om
from tests.offers.conftest import DATA, make_offer, pick

pytestmark = pytest.mark.django_db

# Qué pasaje elige el guion para cada requisito del caso chico (por su texto).
ANSWERS = (
    ("declaración jurada", "Declaro bajo juramento"),
    ("constancia de inscripción", "registro de proveedores con el número"),
    ("garantía", "garantiza, hasta la suma"),
    ("Cotizar en pesos", "precios se cotizan"),
    ("validez", "validez por sesenta"),
    ("RESMA", "1 Resma"),
    ("CARTUCHO", "2 Cartucho"),
)


def case_script(script, *, wrong=None, extra=None):
    """El modelo que acierta en todo, salvo lo que se le pida. `wrong` cambia el pasaje de
    un requisito (por su texto); `extra` hace que también "encuentre" algo en esos."""
    answers = dict(ANSWERS)
    answers.update(wrong or {})
    answers.update(extra or {})

    def function(requirement, blocks, number, messages):
        for key, needle in answers.items():
            if key in requirement:
                return pick(needle)(requirement, blocks, number, messages)
        return None

    script.choose(function)


@pytest.fixture
def chico(evaluator_user, db, operator_user, fake_ai, expected):
    """El caso chico armado en la base, con la lectura real de sus tres PDF."""
    procedure, offers = ev.build_case(evaluator_user, expected)
    # el reranker puntúa alto lo que el guion va a elegir (con 13 pasajes y 8 candidatos,
    # sin puntajes el azar de los vectores del doble dejaría afuera algún pasaje)
    fake_ai.reranker.scores = {needle: 0.9 for _, needle in ANSWERS}
    return procedure, offers


def run(operator_user, chico, expected, tmp_path, **kwargs):
    procedure, offers = chico
    return ev.measure(operator_user, procedure, expected, offers, tmp_path, commit="abc1234",
                      **kwargs)


# --- La lista ------------------------------------------------------------------------------


def test_the_list_of_the_small_case_loads(expected):
    """La lista del caso chico: una oferta de cuatro documentos, siete fragmentos, un
    requisito sin respuesta y una página no legible."""
    offer = expected.offers[0]
    assert len(offer.fragments) == 7 and offer.no_answer == ["M-009"]
    assert len(offer.documents) == 5 and len(offer.unreadable_pages) == 1
    assert offer.items == {1: "cotizado", 2: "cotizado", 3: "no_cotizado"}
    assert offer.technical_documents is True
    assert len(expected.requirements) == 9 and expected.approval


def test_a_list_without_approval_is_not_used(tmp_path):
    """Una lista sin visto bueno no se mide."""
    text = (DATA / "fichas-esperadas.yaml").read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("visto_bueno"))
    path = tmp_path / "fichas-esperadas.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_expected(path)
    assert ev.load_expected(path, require_approval=False).approval == ""


@pytest.mark.parametrize("old, new, message", [
    ("requisito: M-006", "requisito: M-099", "requisito desconocido"),
    ("documento: constancia-escaneada.pdf, pagina: 1", "documento: otro.pdf, pagina: 1",
     "documento desconocido"),
    ("sin_respuesta: [M-009]", "sin_respuesta: [M-099]", "requisitos desconocidos"),
    ("renglones: {1: cotizado,", "renglones: {1: quizas,", "cotizado"),
    ("clase: tecnico, renglon: 1", "clase: tecnico", "renglon"),
])
def test_a_badly_formed_list_is_refused(tmp_path, old, new, message):
    """La lista se valida antes de usarla."""
    text = (DATA / "fichas-esperadas.yaml").read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "fichas-esperadas.yaml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ev.ExpectedError, match=message):
        ev.load_expected(path)


def test_a_document_that_does_not_match_its_fingerprint_is_refused(evaluator_user, operator_user, expected,
                                                                   tmp_path):
    """P6: el archivo debe ser el que la lista nombra, con su huella."""
    for name in ("pliego.pdf", "oferta-propuesta.pdf", "constancia-escaneada.pdf",
                 "poliza-caucion.pdf", "documento-firmado-mixto.pdf"):
        shutil.copy(DATA / name, tmp_path / name)
    (tmp_path / "oferta-propuesta.pdf").write_bytes(b"%PDF-1.4 cambiado")
    with pytest.raises(ev.MeasurementRefused, match="huella"):
        ev.build_case(evaluator_user, expected, tmp_path)


# --- Armado y comprobación ---------------------------------------------------------------------


def test_the_case_is_built_with_a_validated_matrix_and_a_read_offer(chico, expected):
    """El corte vertical: procedimiento, matriz validada, oferta con sus cuatro documentos
    leídos (dos con escaneo)."""
    procedure, offers = chico
    version = procedure.matrix_versions.get()
    assert version.status == "validated" and version.requirements.count() == 9
    offer = offers["Oferente A Sintético"]
    assert offer.documents.count() == 5
    assert all(d.readings.count() == 1 for d in offer.documents.all())
    assert offer.documents.get(file_name="constancia-escaneada.pdf").readings.get()\
        .passages.first().text_origin == "ocr"


def test_building_the_case_twice_does_not_duplicate_anything(evaluator_user, chico, operator_user, expected):
    """El armado es idempotente: lo que existe no se vuelve a crear."""
    procedure, offers = ev.build_case(evaluator_user, expected)
    assert procedure.offers.count() == 1 and procedure.matrix_versions.count() == 1
    assert om.Reading.objects.count() == 5


def test_the_list_is_verified_against_the_readings_without_the_model(chico, expected,
                                                                      script):
    """REQ-039: huellas, páginas y anclas ubicadas en las lecturas, sin usar el modelo."""
    _, offers = chico
    verification = ev.verify_expected(expected, offers)
    assert verification.ok, verification.lines
    assert verification.counts == {"documents": 5, "anchors": 7, "unreadable_pages": 1}
    assert script.calls == []


def test_an_anchor_that_is_not_on_its_page_fails_the_verification(chico, expected):
    """Un ancla que no está en su página bloquea la lista."""
    _, offers = chico
    fragment = dataclasses.replace(expected.offers[0].fragments[0], page=2)
    changed = dataclasses.replace(
        expected, offers=[dataclasses.replace(expected.offers[0],
                                              fragments=[fragment])])
    verification = ev.verify_expected(changed, offers)
    assert not verification.ok and "F-001" in " ".join(verification.lines)


def test_the_anchor_match_does_not_need_the_same_words():
    """REQ-039: se ubica por similitud (0,8), tolerando diferencias de lectura."""
    assert ev._best_ratio("Se deja constancia de que el Oferente A Sintético está inscripto",
                          "Se deja constancia de que el Oferente A Sintetico esta inscripto"
                          ) >= ev.ANCHOR_SIMILARITY
    assert ev._best_ratio("otro texto sin relación alguna", "Se deja constancia de que") < 0.8


# --- Medición -----------------------------------------------------------------------------------


def test_a_model_that_answers_well_meets_every_threshold(chico, operator_user, expected,
                                                         script, tmp_path):
    """REQ-039, REQ-040, REQ-041, REQ-044: con el caso chico y un modelo que acierta, todas
    las medidas cumplen el umbral."""
    case_script(script)
    report = run(operator_user, chico, expected, tmp_path)
    total = report.total
    assert report.blocking == []
    assert total["found"] == {"ok": 7, "total": 7, "rate": 1.0}
    assert (total["literal"]["ok"], total["literal"]["total"]) == (7, 7)
    assert total["no_answer"] == {"ok": 1, "total": 1, "rate": 1.0}
    # el renglón sin oferta no se puede dar por "no cotizado": la oferta tiene una página
    # ilegible, así que figura "no se pudo leer" y se informa aparte
    assert total["items"] == {"ok": 2, "total": 2, "rate": 1.0}
    assert total["items_unreadable"] == [3]
    assert total["technical_documents"]["rate"] == 1.0
    assert total["pages_unlisted"] == [] and total["false_findings"] == []
    assert total["extra_fragments"] == 0 and total["pages"] == 9


def test_the_run_leaves_its_folder_with_a_public_summary(chico, operator_user, expected,
                                                         script, tmp_path):
    """La corrida guarda parámetros, resultados y los dos resúmenes; el público no lleva
    el nombre del oferente ni textos de la oferta."""
    case_script(script)
    report = run(operator_user, chico, expected, tmp_path)
    folder = report.folder
    assert folder.name.endswith("abc1234")
    for name in ev.RUN_FILE_NAMES:
        assert (folder / name).exists()
    parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["umbrales"]["found"] == 0.9 and parameters["commit"] == "abc1234"
    assert parameters["fichas"][0]["modelos"]["generation_batch"]["sha256"]
    lines = [json.loads(line) for line in
             (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {line["tipo"] for line in lines} == {"fragmento", "sin_respuesta", "renglon"}
    public = (folder / "resumen-publico.md").read_text(encoding="utf-8")
    private = (folder / "resumen.md").read_text(encoding="utf-8")
    assert "Cumple el umbral." in public and "Oferente A" not in public
    assert "Oferente A" in private and "Declaro bajo juramento" not in public


def test_the_measure_leaves_the_sheet_with_the_eval_channel(chico, operator_user, expected,
                                                            script, tmp_path):
    """P6: la ficha medida queda con canal `eval` y su hecho `sheet_build`."""
    case_script(script)
    run(operator_user, chico, expected, tmp_path)
    sheet = om.Sheet.objects.get()
    assert sheet.channel == "eval"
    event = AuditEvent.objects.get(event_type=EventType.SHEET_BUILD, outcome=Outcome.OK)
    assert event.channel == "eval"


def test_a_missed_fragment_lowers_the_found_rate_and_blocks(chico, operator_user, expected,
                                                            script, tmp_path):
    """REQ-039: un fragmento esperado en otro lugar no cuenta como encontrado; 6 de 7 es
    85,7 %, menos del 90 %, y bloquea."""
    case_script(script, wrong={"validez": "2 Cartucho"})
    report = run(operator_user, chico, expected, tmp_path)
    assert report.total["found"]["ok"] == 6
    assert any("Fragmentos esperados encontrados" in line for line in report.blocking)
    causes = [line["causa"] for r in report.results for line in r["measures"]["lines"]
              if line["tipo"] == "fragmento" and not line["encontrado"]]
    assert causes == ["otro_pasaje"]
    assert "No cumple" in (report.folder / "resumen-publico.md").read_text(encoding="utf-8")


def test_a_fragment_in_a_requirement_without_an_answer_is_a_false_finding(
        chico, operator_user, expected, script, tmp_path):
    """REQ-040: un fragmento propuesto donde no hay respuesta se informa como falso hallazgo
    y la medida del requisito sin respuesta baja a 0 de 1."""
    case_script(script, extra={"certificado fiscal": "validez por sesenta"})
    report = run(operator_user, chico, expected, tmp_path)
    assert report.total["false_findings"] == ["M-009"]
    assert report.total["no_answer"]["ok"] == 0
    assert any("sin respuesta" in line for line in report.blocking)


def test_a_wrong_item_state_blocks(chico, operator_user, expected, script, tmp_path):
    """REQ-044: un renglón con otro estado que el esperado baja la medida de renglones."""
    case_script(script, extra={"ARCHIVADOR": "1 Resma"})
    report = run(operator_user, chico, expected, tmp_path)
    assert report.total["items"] == {"ok": 2, "total": 3, "rate": 2 / 3}
    assert any("Renglones" in line for line in report.blocking)


def test_a_fragment_that_is_not_a_literal_cut_is_not_literal(chico, operator_user, expected,
                                                             script, tmp_path):
    """REQ-039: la medida del texto literal detecta un fragmento distinto del recorte."""
    case_script(script)
    run(operator_user, chico, expected, tmp_path)
    fragment = om.Fragment.objects.first()
    assert ev._literal(fragment)
    fragment.text = fragment.text + " agregado"
    assert not ev._literal(fragment)


def test_an_item_that_could_not_be_read_is_reported_apart(procedure, matrix, operator_user,
                                                          fake_ai, script):
    """REQ-044: un renglón "no se pudo leer" no es acierto ni "no cotizado": se informa
    aparte y no entra en la cuenta de renglones."""
    offer = make_offer(procedure, operator_user, "Con hoja ilegible",
                       {"a.pdf": ["Renglón 1: resma de papel A4, 100 unidades.", ""]},
                       unread=[("a.pdf", 2)])
    script.choose(pick("Renglón 1", when="RESMA"))
    from evaluon.offers.services import sheets

    sheet = sheets.build_sheet(offer, operator_user)
    entry = ev.ExpectedOffer(bidder="x", documents=[], fragments=[], no_answer=[],
                             items={1: "cotizado", 3: "no_cotizado"},
                             technical_documents=None,
                             unreadable_pages=[{"documento": "a.pdf", "pagina": 2}])
    mapping = ev._requirement_map(matrix.version, matrix.expected.requirements)
    measures = ev.measure_sheet(sheet, entry, offer, mapping)
    assert measures["items"] == {"ok": 1, "total": 1, "rate": 1.0}
    assert measures["items_unreadable"] == [3]
    assert measures["expected_pages"] == {"ok": 1, "total": 1, "rate": 1.0}
    assert measures["unread_pages"] == 1


def test_a_page_without_text_and_without_a_list_blocks(chico):
    """REQ-038: toda página sin texto ni figura en la lista cuenta como falla."""
    total = {name: {"ok": 1, "total": 1, "rate": 1.0} for name in
             ("found", "literal", "no_answer", "synthesis", "items", "technical_documents",
              "expected_pages")}
    total["pages_unlisted"] = [{"documento": "a.pdf", "pagina": 2}]
    assert ev.blocking(total) == ["Páginas sin texto ni lista: 1, máximo 0"]


# --- Comandos --------------------------------------------------------------------------------------


@pytest.fixture
def as_operator(monkeypatch, operator_user):
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)


def test_the_command_builds_verifies_and_measures_the_small_case(
        as_operator, fake_ai, script, tmp_path, capsys):
    """El corte vertical de punta a punta con el comando: arma el caso, comprueba la lista y
    mide con el modelo."""
    call_command("medir_fichas", usuario="operador", caso_chico=True, verificar_esperada=True)
    out = capsys.readouterr().out
    assert "anclas 7" in out and "sin fallas" in out
    fake_ai.reranker.scores = {needle: 0.9 for _, needle in ANSWERS}
    case_script(script)
    call_command("medir_fichas", usuario="operador", caso_chico=True, corridas=str(tmp_path),
                 commit="abc1234")
    out = capsys.readouterr().out
    assert "Corrida guardada en" in out and "Bloquea la aceptación: nada" in out
    assert "7 de 7" in out


def test_the_command_needs_a_list(as_operator):
    """Sin `--esperada` ni `--caso-chico`, el comando lo dice."""
    from django.core.management import CommandError

    with pytest.raises(CommandError, match="--esperada"):
        call_command("medir_fichas", usuario="operador")


def test_the_loading_command_registers_the_offer_and_queues_the_readings(
        as_operator, matrix, capsys):
    """REQ-037: `cargar_oferta` registra el oferente y encola la lectura de cada archivo."""
    from evaluon.tenders import models as m

    call_command("cargar_oferta", str(DATA / "oferta-propuesta.pdf"),
                 str(DATA / "constancia-escaneada.pdf"), usuario="operador",
                 procedimiento=matrix.procedure.number, oferente="Oferente por comando")
    out = capsys.readouterr().out
    offer = matrix.procedure.offers.get(bidder="Oferente por comando")
    assert offer.documents.count() == 2 and "cargado" in out
    assert m.Job.objects.filter(kind=m.JobKind.READ_OFFER_DOCUMENT).count() == 2
    call_command("cargar_oferta", str(DATA / "oferta-propuesta.pdf"), usuario="operador",
                 procedimiento=matrix.procedure.number, oferente="Oferente por comando")
    assert "ya está cargado" in capsys.readouterr().out
    assert offer.documents.count() == 2


def _total(**changes):
    total = {name: {"ok": 1, "total": 1, "rate": 1.0} for name in
             ("found", "literal", "no_answer", "synthesis", "items", "technical_documents",
              "expected_pages")}
    total["pages_unlisted"] = []
    total.update(changes)
    return total


def test_case_00_has_its_own_thresholds():
    """REQ-040, REQ-044 (T-135, H-0): en el caso-00 "sin respuesta" se informa sin tope y los
    renglones piden 90 %; el caso chico sigue con 100 %."""
    total = _total(no_answer={"ok": 0, "total": 5, "rate": 0.0},
                   items={"ok": 17, "total": 18, "rate": 17 / 18})
    assert ev.blocking(total, "caso-00") == []
    assert len(ev.blocking(total, "caso-chico")) == 2
    assert len(ev.blocking(total)) == 2


def test_case_00_items_below_ninety_percent_block():
    """REQ-044: 16 de 18 (88,9 %) no llega al 90 % del caso-00."""
    total = _total(items={"ok": 16, "total": 18, "rate": 16 / 18})
    failed = ev.blocking(total, "caso-00")
    assert len(failed) == 1 and "Renglones" in failed[0]


def test_the_summary_of_case_00_says_no_cap_for_no_answer(chico, operator_user, expected,
                                                          script, tmp_path):
    """REQ-040: la tabla del resumen del caso-00 dice "informado, sin tope"."""
    import dataclasses

    case_script(script)
    as_case_00 = dataclasses.replace(expected, case="caso-00")
    report = run(operator_user, chico, as_case_00, tmp_path)
    summary = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert "informado, sin tope" in summary
    assert report.expected.case == "caso-00"


def test_an_identical_copy_in_another_document_counts_as_the_same_place(
        procedure, operator_user, fake_ai):
    """REQ-039 (T-135, decisión del responsable): el mismo pasaje literal en otro documento de
    la oferta, o el mismo lugar de una página de texto igual, es el mismo lugar; un pasaje
    distinto o del mismo documento no."""
    from tests.offers.conftest import make_offer

    offer = make_offer(procedure, operator_user, "Copias", {
        "a.pdf": ["Constancia de inscripción número 000123.", "Texto distinto uno."],
        "b.pdf": ["CONSTANCIA de inscripción  número 000123.", "Texto distinto dos."]})
    a, b = (om.Passage.objects.filter(reading__document__file_name=n).order_by("order")
            for n in ("a.pdf", "b.pdf"))
    cache = {}
    assert ev.is_identical_copy(b[0], a[0], cache)
    assert not ev.is_identical_copy(b[1], a[0], cache)
    assert not ev.is_identical_copy(a[1], a[0], cache)
    assert not ev.is_identical_copy(b[1], a[1], cache)
