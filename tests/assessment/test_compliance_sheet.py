"""Hoja de compliance por oferta (REQ-073 de la 013; REQ-063 de la 004; ADR-0043; T-189).

La Comisión sube una hoja por oferta (también una que diga que no cumple) y todos los requisitos
externos de esa oferta se evalúan de nuevo solos, citando la hoja. Caso chico inventado (P4); el
modelo es un guion. Las hojas son PDF inventados que se arman en la prueba.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import compliance, evaluate
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers import models as om
from evaluon.tenders import jobs
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import DECLARATION, requirement_of, run_all
from tests.offers.conftest import make_offer
from tests.offers.test_screens import log_in, text_of
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db

REGISTRY = "Registro de Proveedores: el oferente figura inscripto y habilitado."
HABILITY = "Habilidad para contratar: el oferente no figura en el REPSAL ni tiene sanciones."
DEBT_OK = "Deuda exigible: el oferente no registra deuda exigible ante el organismo."
DEBT_BAD = "Deuda exigible: el oferente registra deuda exigible, no cumple."
POLICY_OK = "Póliza de caución: validada ante la Superintendencia de Seguros de la Nación."

# Qué requisito del caso chico se verifica con cada línea de la hoja.
CHECKS = {
    "registro de proveedores": "registro",
    "declaración jurada": "habilidad",
    "libre deuda": "deuda",
    "garantía de mantenimiento": "poliza",
}


def sheet_pdf(*lines):
    return tender_pdf([[para("HOJA DE COMPLIANCE", *lines)]], header=None)


@pytest.fixture
def full_sheet():
    """Una hoja que cubre registro, habilidad (sanciones), deuda y póliza."""
    return sheet_pdf(REGISTRY, HABILITY, DEBT_OK, POLICY_OK)


def scripted(lines_by_check):
    """Guion: sin hoja, los cuatro requisitos externos cumplen según la oferta pero el modelo los
    marca externos; con hoja, cada uno cita su línea (cumple, o no cumple si la línea lo dice) y,
    si la hoja no trae su línea, el modelo dice que no consta."""
    def script(call):
        check = next((c for key, c in CHECKS.items() if key in call.requirement), None)
        if check is None:
            return None
        if call.alias_with("HOJA DE COMPLIANCE") is None:
            return says("cumple", call.quote(DECLARATION), external=True)
        line = lines_by_check.get(check)
        if line is None or call.quote(line) is None:
            return says("no_consta", exigence="documento", external=True)
        verdict = "no_cumple" if "no cumple" in line else "cumple"
        return says(verdict, call.quote(line), exigence="documento", external=True)
    return script


def read_and_evaluate():
    """Corre la cola como el worker: la lectura de la hoja y, encadenada, la evaluación."""
    ran = []
    while True:
        job = jobs.run_next()
        if job is None:
            return ran
        ran.append(job)


@pytest.fixture
def evaluated(offer, procedure, operator_user, model):
    """La oferta evaluada sin hoja: los cuatro requisitos quedan «falta la hoja de compliance»."""
    model.evaluates(scripted({}))
    run_all(operator_user, procedure)
    for needle in CHECKS:
        result = evaluate.current_result(offer, requirement_of(procedure, needle))
        assert (result.outcome, result.doubt) == ("no_determinado", "externo"), needle
    return offer


def current(offer, procedure, needle):
    return evaluate.current_result(offer, requirement_of(procedure, needle))


def test_one_sheet_reevaluates_every_external_requirement_of_the_offer(
        evaluated, procedure, evaluator_user, model, full_sheet):
    """REQ-073: una hoja por oferta queda como documento de tipo compliance, se registra (P6) y,
    leída, todos los requisitos externos se evalúan de nuevo solos, citando la hoja."""
    model.evaluates(scripted({"registro": REGISTRY, "habilidad": HABILITY, "deuda": DEBT_OK,
                              "poliza": POLICY_OK}))
    before = am.Request.objects.count()
    uploaded = compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                                       file_name="compliance.pdf")
    document = uploaded.document
    assert document.kind == om.DocumentKind.COMPLIANCE and document.offer == evaluated
    assert uploaded.external_pending == 4
    event = AuditEvent.objects.get(pk=uploaded.event.pk)
    assert event.event_type == EventType.EVAL_DECISION and event.outcome == EventOutcome.OK
    assert event.detail["action"] == "hoja_compliance"
    assert event.detail["file_sha256"] == document.file_sha256
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_LOAD,
                                     detail__document=document.pk).exists()

    read_and_evaluate()

    document.refresh_from_db()
    assert document.kind == om.DocumentKind.COMPLIANCE  # la lectura no lo reclasifica
    assert am.Request.objects.count() == before + 1  # un solo pedido para los cuatro
    request = am.Request.objects.order_by("-pk").first()
    assert request.cause == "subsanacion" and request.offers == [evaluated.pk]
    assert len(request.requirements) == 4
    for needle, line in (("registro de proveedores", REGISTRY), ("declaración jurada", HABILITY),
                         ("libre deuda", DEBT_OK), ("garantía de mantenimiento", POLICY_OK)):
        result = current(evaluated, procedure, needle)
        assert result.outcome == "cumple", needle
        cited = result.citations.get(kind="oferta")
        assert cited.document == document and line in cited.text
        assert result.previous is not None and result.previous.doubt == "externo"
    # El requisito que no era externo no se tocó.
    assert current(evaluated, procedure, "validez").run.number == 1


def test_a_sheet_that_says_it_does_not_comply_is_a_valid_sheet(
        evaluated, procedure, evaluator_user, model):
    """REQ-073: una hoja que dice que no cumple también se sube; el requisito queda «no cumple»
    con la cita literal de la hoja."""
    sheet = sheet_pdf(REGISTRY, HABILITY, DEBT_BAD, POLICY_OK)
    model.evaluates(scripted({"registro": REGISTRY, "habilidad": HABILITY, "deuda": DEBT_BAD,
                              "poliza": POLICY_OK}))
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=sheet, file_name="hoja.pdf")
    read_and_evaluate()
    debt = current(evaluated, procedure, "libre deuda")
    assert debt.outcome == "no_cumple" and debt.doubt == ""
    assert DEBT_BAD in debt.citations.get(kind="oferta").text
    assert current(evaluated, procedure, "registro de proveedores").outcome == "cumple"


def test_a_check_the_sheet_does_not_cover_is_not_determined(
        evaluated, procedure, evaluator_user, model):
    """REQ-073: si la hoja no trata un chequeo, el resultado es «no determinado» (no «no se
    encontró el documento») y dice que la hoja no lo trata."""
    sheet = sheet_pdf(REGISTRY, DEBT_OK)  # sin habilidad ni póliza
    model.evaluates(scripted({"registro": REGISTRY, "deuda": DEBT_OK}))
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=sheet, file_name="hoja.pdf")
    read_and_evaluate()
    for needle in ("declaración jurada", "garantía de mantenimiento"):
        result = current(evaluated, procedure, needle)
        assert result.outcome == "no_determinado" and result.doubt == "duda", needle
        assert "no trata este chequeo" in result.explanation
        assert result.facts["regla"] == "externo_hoja_sin_chequeo"
    assert current(evaluated, procedure, "libre deuda").outcome == "cumple"


def test_the_sheet_of_one_offer_does_not_rule_over_another(
        evaluated, procedure, operator_user, evaluator_user, model, full_sheet):
    """REQ-073: la hoja es de una oferta; los externos de otra oferta siguen pidiéndola."""
    other = make_offer(procedure, operator_user, "Otro oferente", {
        "oferta.pdf": [DECLARATION + ". Texto de la otra oferta."]})
    model.evaluates(scripted({}))
    run_all(operator_user, procedure, offers=[other.pk])
    assert current(other, procedure, "libre deuda").doubt == "externo"
    model.evaluates(scripted({"deuda": DEBT_OK, "registro": REGISTRY, "habilidad": HABILITY,
                              "poliza": POLICY_OK}))
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                            file_name="compliance.pdf")
    read_and_evaluate()
    assert current(evaluated, procedure, "libre deuda").outcome == "cumple"
    assert current(other, procedure, "libre deuda").doubt == "externo"
    assert compliance.sheets_of(other) == []


def test_the_name_of_the_file_does_not_change_the_kind(
        evaluated, evaluator_user, model, full_sheet):
    """REQ-073: un archivo que se llama «póliza» y es la hoja sigue siendo la hoja (la
    clasificación por reglas no la pisa)."""
    model.evaluates(scripted({}))
    document = compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                                       file_name="poliza-seguro-de-caucion.pdf").document
    read_and_evaluate()
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.COMPLIANCE


def test_only_the_evaluator_uploads_the_sheet(evaluated, operator_user, no_commission_user,
                                              full_sheet):
    """P3, REQ-073: el operador y quien no es de la Comisión no suben la hoja ni piden evaluar de
    nuevo; no queda ningún documento y sí el hecho rechazado."""
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            compliance.upload_sheet(user, evaluated.pk, data=full_sheet, file_name="h.pdf")
        with pytest.raises(RoleRejected):
            compliance.reevaluate_externals(user, evaluated.pk)
    assert compliance.sheets_of(evaluated) == []
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() >= 4


def test_reevaluating_by_hand_needs_a_sheet_that_is_already_read(
        evaluated, evaluator_user, model, full_sheet):
    """REQ-073: sin hoja no hay nada que evaluar de nuevo; mientras la hoja se lee, el pedido se
    rechaza."""
    with pytest.raises(compliance.ComplianceRefused) as caught:
        compliance.reevaluate_externals(evaluator_user, evaluated.pk)
    assert caught.value.reason == "sheet_not_uploaded"
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                            file_name="compliance.pdf")
    with pytest.raises(evaluate.EvaluationRefused) as caught:
        compliance.reevaluate_externals(evaluator_user, evaluated.pk)
    assert caught.value.reason == "reading_in_progress"


def test_if_the_queue_is_busy_the_automatic_request_is_recorded_and_it_can_be_asked_by_hand(
        evaluated, procedure, evaluator_user, model, full_sheet):
    """REQ-073, P6: si otra evaluación está en curso cuando termina la lectura de la hoja, el
    pedido automático no se encola y queda el hecho rechazado; la Comisión lo pide a mano."""
    model.evaluates(scripted({"registro": REGISTRY, "habilidad": HABILITY, "deuda": DEBT_OK,
                              "poliza": POLICY_OK}))
    other = evaluate.request_evaluation(evaluator_user, procedure,
                                        requirements=[requirement_of(procedure, "validez").pk])
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                            file_name="compliance.pdf")
    jobs.run_next(kinds=[jobs.JobKind.READ_OFFER_DOCUMENT])
    assert compliance.external_results(evaluated)  # sigue sin resolverse
    assert AuditEvent.objects.filter(
        event_type=EventType.EVAL_REQUEST, outcome=EventOutcome.REJECTED,
        detail__reason="request_in_progress").exists()
    jobs.finish(other.job)
    requested = compliance.reevaluate_externals(evaluator_user, evaluated.pk)
    assert requested.request.cause == "subsanacion" and len(requested.request.requirements) == 4
    with pytest.raises(evaluate.EvaluationRefused):  # ya hay un pedido en espera
        compliance.reevaluate_externals(evaluator_user, evaluated.pk)


def test_a_failing_follow_up_does_not_change_the_reading_job(
        evaluated, evaluator_user, full_sheet, monkeypatch):
    """REQ-073: si el paso encadenado falla, el pedido de lectura queda terminado."""
    def broken(job):
        raise RuntimeError("falla de prueba")
    monkeypatch.setitem(jobs.AFTER_DONE, jobs.JobKind.READ_OFFER_DOCUMENT, broken)
    document = compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                                       file_name="compliance.pdf").document
    job = jobs.run_next()
    assert job.status == "done" and job.target_id == document.pk


# --- Pantalla ----------------------------------------------------------------------------------


def test_the_matrix_offers_the_upload_only_to_the_evaluator(
        client, evaluated, procedure, evaluator_user, operator_user):
    """REQ-073: «Subir hoja de compliance» está por oferta en la matriz y solo lo ve el
    evaluador; la oferta sin hoja lo dice."""
    url = reverse("assessment:matrix", args=[procedure.pk])
    log_in(client, evaluator_user)
    page = text_of(client.get(url))
    assert "Subir hoja de compliance" in page
    assert "Falta la hoja de compliance de esta oferta" in page
    assert "Requisitos «falta la hoja de compliance» por resolver: 4" in page
    client.logout()
    log_in(client, operator_user)
    page = text_of(client.get(url))
    assert "Subir hoja de compliance" not in page
    assert "Solo el evaluador de la Comisión sube la hoja de compliance" in page


def test_the_upload_from_the_matrix_loads_the_sheet_and_shows_it(
        client, evaluated, procedure, evaluator_user, operator_user, full_sheet):
    """REQ-073: la hoja se sube desde la matriz; vuelve a la matriz con la hoja y su huella; un
    archivo que no se lee vuelve con el motivo (422); el operador recibe 403."""
    upload = reverse("assessment:compliance_upload", args=[evaluated.pk])
    log_in(client, operator_user)
    assert client.post(upload, {"file": SimpleUploadedFile("h.pdf", full_sheet)}).status_code \
        == 403
    client.logout()
    log_in(client, evaluator_user)
    bad = client.post(upload, {"file": SimpleUploadedFile("h.txt", b"nada")})
    assert bad.status_code == 422
    good = client.post(upload, {"file": SimpleUploadedFile("compliance.pdf", full_sheet)})
    assert good.status_code == 302 and good["Location"].endswith(f"#oferta-{evaluated.number}")
    document = compliance.sheets_of(evaluated)[0]
    page = text_of(client.get(reverse("assessment:matrix", args=[procedure.pk])))
    assert document.file_sha256 in page and "La hoja se está leyendo" in page
    assert "Falta la hoja de compliance de esta oferta" not in page


def test_the_manual_reevaluation_button_appears_when_the_sheet_is_read(
        client, evaluated, procedure, evaluator_user, model, full_sheet):
    """REQ-073: leída la hoja y con externos por resolver, la matriz da «Evaluar de nuevo los
    requisitos externos»; con la cola ocupada vuelve con el motivo (422) y libre, a la matriz."""
    other = evaluate.request_evaluation(evaluator_user, procedure,
                                        requirements=[requirement_of(procedure, "validez").pk])
    compliance.upload_sheet(evaluator_user, evaluated.pk, data=full_sheet,
                            file_name="compliance.pdf")
    jobs.run_next(kinds=[jobs.JobKind.READ_OFFER_DOCUMENT])
    log_in(client, evaluator_user)
    url = reverse("assessment:matrix", args=[procedure.pk])
    assert "Evaluar de nuevo los requisitos externos" in text_of(client.get(url))
    again = reverse("assessment:compliance_reevaluate", args=[evaluated.pk])
    assert client.post(again).status_code == 422
    jobs.finish(other.job)
    assert client.post(again).status_code == 302
