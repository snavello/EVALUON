"""Subsanación de un resultado "no se encontró el documento" o "falta la hoja de compliance"
(REQ-060, REQ-056; plan 004, "Subsanación"; T-154). Caso chico inventado (P4); el modelo es un
guion."""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, remedy, review
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.tenders import jobs
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import DECLARATION, requirement_of, run_all
from tests.offers.conftest import DATA

pytestmark = pytest.mark.django_db

GUARANTEE = "garantía de mantenimiento"
POLICY = "garantiza, hasta la suma de $ 21.750, el cumplimiento de la obligación"
DEBT = "libre deuda"


def script(call):
    """Sin póliza en la oferta, el modelo no encuentra la garantía; con ella, la cita. El
    libre deuda es externo; lo demás, "no consta"."""
    if GUARANTEE in call.requirement:
        return says("cumple", call.quote(POLICY), exigence="documento") \
            if call.alias_with(POLICY) else says("no_consta", exigence="documento")
    if "declaración jurada" in call.requirement:
        return says("cumple", call.quote(DECLARATION))
    if DEBT in call.requirement:
        return says("cumple", call.quote(DECLARATION), external=True)


@pytest.fixture
def missing(offer, operator_user, procedure, model):
    """El resultado vigente "no se encontró el documento" de la garantía."""
    model.evaluates(script)
    run_all(operator_user, procedure)
    result = evaluate.current_result(offer, requirement_of(procedure, GUARANTEE))
    assert result.outcome == "sin_documento"
    return result


@pytest.fixture
def external(offer, procedure, missing):
    """El resultado vigente "falta la hoja de compliance" del libre deuda."""
    result = evaluate.current_result(offer, requirement_of(procedure, DEBT))
    assert (result.outcome, result.doubt) == ("no_determinado", "externo")
    return result


def policy():
    return (DATA / "poliza-caucion.pdf").read_bytes()


def read_documents():
    while jobs.run_next() is not None:
        pass


def test_only_the_evaluator_asks_adds_and_evaluates_again(missing, operator_user,
                                                          no_commission_user):
    """P3, REQ-060: el operador y quien no es de la Comisión no piden la subsanación, no agregan
    el documento ni piden evaluar de nuevo; no queda ninguna decisión."""
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            remedy.request_remedy(user, missing.pk, "Se pide el documento.")
        with pytest.raises(RoleRejected):
            remedy.add_document(user, missing.pk, data=policy(), file_name="poliza.pdf")
        with pytest.raises(RoleRejected):
            remedy.reevaluate(user, missing.pk)
    assert not am.Decision.objects.exists()
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() >= 6


def test_requesting_the_remedy_needs_a_note_and_keeps_the_state(missing, evaluator_user):
    """REQ-060, REQ-056: el pedido exige nota, deja autor, fecha y hecho, y no cambia el estado
    del par."""
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.request_remedy(evaluator_user, missing.pk, "  ")
    assert caught.value.reason == "note_required" and not am.Decision.objects.exists()
    decision = remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza.").decision
    assert decision.action == "pedir_subsanacion" and decision.user == evaluator_user
    assert decision.note == "Se pide la póliza." and decision.at is not None
    event = AuditEvent.objects.get(pk=decision.event_id)
    assert event.event_type == EventType.EVAL_DECISION and event.outcome == EventOutcome.OK
    assert review.state_of(missing) == "propuesto"
    assert review.effective_outcome(missing) == "sin_documento"
    assert remedy.state(missing).requested == decision


def test_only_a_missing_document_or_a_missing_sheet_can_be_remedied(
        offer, procedure, missing, evaluator_user):
    """REQ-060: un resultado que no es "no se encontró el documento" ni "falta la hoja" no se
    subsana."""
    declaration = evaluate.current_result(offer, requirement_of(procedure, "declaración jurada"))
    assert declaration.outcome != "sin_documento"
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.request_remedy(evaluator_user, declaration.pk, "Motivo.")
    assert caught.value.reason == "not_remediable"
    assert remedy.state(declaration).applicable is False


def test_a_rejected_result_has_no_effective_outcome_and_cannot_be_remedied(
        missing, evaluator_user):
    """Aviso de T-153: un resultado rechazado deja `effective_outcome` en `None` y no rige: no se
    subsana."""
    review.reject(evaluator_user, missing.pk, "No corresponde.")
    assert review.effective_outcome(missing) is None
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.request_remedy(evaluator_user, missing.pk, "Motivo.")
    assert caught.value.reason == "not_remediable"
    assert remedy.state(missing).applicable is False


def test_the_document_is_added_only_after_the_request_and_is_linked_with_its_hash(
        missing, offer, evaluator_user):
    """REQ-060: se agrega el documento con la carga de la 008 y queda vinculado al resultado,
    con su huella, quién lo cargó y cuándo."""
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.add_document(evaluator_user, missing.pk, data=policy(), file_name="poliza.pdf")
    assert caught.value.reason == "remedy_not_requested"
    assert not offer.documents.filter(file_name="poliza.pdf").exists()
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza.")
    decision = remedy.add_document(evaluator_user, missing.pk, data=policy(),
                                   file_name="poliza.pdf").decision
    document = decision.document
    assert decision.action == "subsanar" and document.offer == offer
    assert document.loaded_by == evaluator_user and len(document.file_sha256) == 64
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_LOAD,
                                     detail__document=document.pk).exists()
    assert review.state_of(missing) == "propuesto"  # sigue siendo recorrido, no estado


def test_reevaluating_waits_for_the_reading_of_the_added_document(
        missing, evaluator_user, model):
    """REQ-060: mientras el documento agregado se está leyendo no se evalúa de nuevo."""
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza.")
    remedy.add_document(evaluator_user, missing.pk, data=policy(), file_name="poliza.pdf")
    assert remedy.state(missing).can_reevaluate is False
    with pytest.raises(evaluate.EvaluationRefused) as caught:
        remedy.reevaluate(evaluator_user, missing.pk)
    assert caught.value.reason == "reading_in_progress"
    read_documents()
    assert remedy.state(missing).can_reevaluate is True


def test_reevaluating_needs_the_added_document(missing, evaluator_user):
    """REQ-060: sin documento agregado no hay nada que evaluar de nuevo."""
    remedy.request_remedy(evaluator_user, missing.pk, "Se pide la póliza.")
    with pytest.raises(remedy.RemedyRefused) as caught:
        remedy.reevaluate(evaluator_user, missing.pk)
    assert caught.value.reason == "document_not_added"


def test_a_missing_compliance_sheet_follows_the_same_circuit(
        external, offer, procedure, evaluator_user, operator_user, model):
    """Decisiones del responsable, punto 1: "falta la hoja de compliance" se subsana igual: la
    Comisión sube la hoja (aunque diga "no cumple") y el requisito se evalúa de nuevo."""
    state = remedy.state(external)
    assert state.applicable
    remedy.request_remedy(evaluator_user, external.pk, "Se pide la hoja de compliance.")
    remedy.add_document(evaluator_user, external.pk, data=policy(), file_name="compliance.pdf")
    read_documents()
    model.evaluates(lambda call: says("no_cumple", call.quote(POLICY), exigence="documento")
                    if DEBT in call.requirement and call.alias_with(POLICY) else script(call))
    requested = remedy.reevaluate(evaluator_user, external.pk)
    assert requested.request.cause == "subsanacion"
    assert requested.request.requirements == [external.requirement_id]
    assert requested.request.offers == [offer.pk]
    assert requested.request.decision.action == "subsanar"
