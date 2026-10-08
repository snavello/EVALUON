"""Historial de los documentos de una oferta: reemplazar, retirar y restituir sin borrar nada
(REQ-099; ADR-0048; plan 014, "Modelo de datos"; T-199).

Ofertas e ingresos inventados (P4); los archivos nuevos son PDF sintéticos.
"""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.documents import build_offer_text
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import document_history as history
from evaluon.offers.services import offers as offers_service
from tests.offers.conftest import make_offer
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db


def pdf(text):
    return tender_pdf([[para(f"OFERTA SINTÉTICA {text}"), para("Cotizo el renglón 1.")]])


@pytest.fixture
def document(offer):
    return offer.documents.get(file_name="oferta.pdf")


def events(outcome=Outcome.OK):
    return AuditEvent.objects.filter(event_type=EventType.DOCUMENT_CHANGE, outcome=outcome)


def count_tokens(text):
    return len(text.split())


def test_replace_keeps_the_old_document_and_adds_the_new_one(
        evaluator_user, offer, document):
    """REQ-099: el reemplazo deja la versión anterior y la nueva, con quién y cuándo."""
    original = bytes(om.DocumentFile.objects.get(document=document).content)
    change, loaded = history.replace(evaluator_user, document, data=pdf("v2"),
                                     file_name="oferta-v2.pdf", note="trae la firma")
    new = loaded.document
    assert (change.document, change.new_document, change.user) == (document, new,
                                                                   evaluator_user)
    assert change.action == "reemplazar" and change.note == "trae la firma" and change.at
    assert (new.offer, new.title, new.kind) == (offer, document.title, document.kind)
    assert new in history.current_documents(offer) and document not in history.current_documents(offer)
    assert list(history.replaced_documents(offer)) == [document]
    assert bytes(om.DocumentFile.objects.get(document=document).content) == original
    assert offer.documents.count() == 3
    assert om.Document.objects.filter(pk=document.pk).exists()
    assert [r.action for r in history.history(new)] == ["reemplazar"]
    assert history.history(document) == history.history(new)


def test_withdrawn_leaves_current_and_appears_in_withdrawn_and_restore_returns_it(
        operator_user, offer, document):
    """REQ-099: retirado sale de lo vigente y aparece en retirados; restituir lo devuelve."""
    other = offer.documents.exclude(pk=document.pk).get()
    history.withdraw(operator_user, document, "no es de este oferente")
    assert list(history.current_documents(offer)) == [other]
    assert list(history.withdrawn_documents(offer)) == [document]
    history.restore(operator_user, document)
    assert set(history.current_documents(offer)) == {document, other}
    assert list(history.withdrawn_documents(offer)) == []
    assert [r.action for r in history.history(document)] == ["retirar", "restituir"]
    rows = list(events().order_by("id"))
    assert [e.detail["action"] for e in rows] == ["retirar", "restituir"]
    assert all(e.user == operator_user and e.detail["offer"] == offer.pk for e in rows)
    assert om.DocumentChange.objects.filter(event__in=rows).count() == 2


@pytest.mark.parametrize("prepare, operation, reason", [
    ("withdraw", "withdraw", "not_vigente"),
    ("withdraw", "replace", "not_vigente"),
    ("none", "restore", "not_retirado"),
    ("replace", "restore", "not_retirado"),
    ("replace", "withdraw", "not_vigente"),
])
def test_a_change_that_does_not_apply_is_refused_and_recorded(
        operator_user, offer, document, prepare, operation, reason):
    """REQ-099: solo se retira o reemplaza lo vigente y solo se restituye lo retirado."""
    if prepare == "withdraw":
        history.withdraw(operator_user, document)
    elif prepare == "replace":
        history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    before = om.DocumentChange.objects.count()
    with pytest.raises(history.HistoryRefused) as refusal:
        if operation == "replace":
            history.replace(operator_user, document, data=pdf("v3"), file_name="v3.pdf")
        else:
            getattr(history, operation)(operator_user, document)
    assert refusal.value.reason == reason
    assert om.DocumentChange.objects.count() == before
    assert events(Outcome.REJECTED).get().detail["reason"] == reason


def test_a_user_without_commission_role_cannot_change_documents(
        no_commission_user, offer, document):
    """Roles: sin rol de la Comisión no se reemplaza, retira ni restituye."""
    for call in (lambda: history.withdraw(no_commission_user, document),
                 lambda: history.restore(no_commission_user, document),
                 lambda: history.replace(no_commission_user, document, data=pdf("x"),
                                         file_name="x.pdf")):
        with pytest.raises(RoleRejected):
            call()
    assert om.DocumentChange.objects.count() == 0


def test_replacing_with_the_same_file_is_refused_without_a_change(
        operator_user, offer):
    """Un archivo repetido se rechaza por su huella, como en la carga."""
    data = pdf("igual")
    loaded = offers_service.load_document(operator_user, offer, data=data, file_name="a.pdf")
    with pytest.raises(offers_service.DuplicateFile):
        history.replace(operator_user, loaded.document, data=data, file_name="b.pdf")
    assert om.DocumentChange.objects.count() == 0


def test_the_new_document_must_belong_to_the_same_offer(
        operator_user, procedure, offer, document):
    """Aviso de T-193: el esquema no lo comprueba; el servicio sí."""
    other = make_offer(procedure, operator_user, "Otro oferente", {"x.pdf": ["Texto."]})
    foreign = other.documents.get()
    with pytest.raises(history.HistoryRefused) as refusal:
        history.link_replacement(operator_user, document, foreign)
    assert refusal.value.reason == "other_offer"
    with pytest.raises(history.HistoryRefused):
        history.link_replacement(operator_user, document, document)
    assert om.DocumentChange.objects.count() == 0


def test_withdrawn_documents_are_not_read_to_assess_the_offer(operator_user, offer, document):
    """REQ-099: lo retirado o reemplazado deja de usarse en la evaluación."""
    assert {d.document.pk for d in build_offer_text(offer, count_tokens).documents} == {
        d.pk for d in offer.documents.all()}
    history.withdraw(operator_user, document)
    names = [d.document.file_name for d in build_offer_text(offer, count_tokens).documents]
    assert names == ["constancia.pdf"]
    history.restore(operator_user, document)
    assert len(build_offer_text(offer, count_tokens).documents) == 2
    _, loaded = history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    used = {d.document.pk for d in build_offer_text(offer, count_tokens).documents}
    assert document.pk not in used and loaded.document.pk in used


def test_an_assessment_made_with_a_withdrawn_document_is_marked_and_not_changed(
        operator_user, evaluator_user, matrix, offer, document):
    """REQ-099: la evaluación hecha no cambia; queda marcada para evaluar de nuevo."""
    request = am.Request.objects.create(
        procedure=matrix.procedure, matrix_version=matrix.version, offers=[offer.pk],
        requirements=None, cause=am.Cause.MATRIZ, requested_by=evaluator_user)
    used = [{"document": d.pk} for d in offer.documents.order_by("id")]
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=matrix.version, number=1,
        channel=am.Channel.SCREEN, documents=used, norms={}, models_used={},
        parameters={}, prompt_versions={})
    assert history.runs_with_withdrawn(offer) == []
    history.withdraw(operator_user, document)
    marked = history.runs_with_withdrawn(offer)
    assert [(r.pk, [d.pk for d in docs]) for r, docs in marked] == [(run.pk, [document.pk])]
    run.refresh_from_db()
    assert run.documents == used
    history.restore(operator_user, document)
    assert history.runs_with_withdrawn(offer) == []


def test_a_failure_linking_the_replacement_leaves_no_new_document(
        operator_user, offer, document, monkeypatch):
    """REQ-099: reemplazo en una sola transacción; si falla el vínculo no queda nada."""
    def broken(*args, **kwargs):
        raise RuntimeError("falla el vínculo")

    monkeypatch.setattr(history, "_add_change", broken)
    events_before = AuditEvent.objects.count()
    with pytest.raises(RuntimeError):
        history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    assert offer.documents.count() == 2
    assert AuditEvent.objects.count() == events_before
    assert document in history.current_documents(offer)


def test_a_refused_load_in_a_replacement_keeps_its_rejection_event(operator_user, offer):
    """P6: el rechazo de la carga queda registrado aunque el reemplazo no se haga."""
    data = pdf("igual")
    loaded = offers_service.load_document(operator_user, offer, data=data, file_name="a.pdf")
    with pytest.raises(offers_service.DuplicateFile):
        history.replace(operator_user, loaded.document, data=data, file_name="b.pdf")
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_LOAD,
                                     outcome=Outcome.REJECTED).count() == 1
