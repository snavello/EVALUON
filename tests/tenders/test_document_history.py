"""Historial de los documentos del pliego: reemplazar, retirar y restituir sin borrar nada
(REQ-099; ADR-0048; plan 014, "Modelo de datos"; T-199).

Pliegos sintéticos (`tests/tenders/pdfs.py`); sin datos de personas (P4).
"""

import pytest
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import document_history as history
from evaluon.tenders.services import documents, matrix
from tests.offers.conftest import expected, matrix as validated_matrix  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import load_and_read, make_procedure, run_jobs

pytestmark = pytest.mark.django_db


def pdf(text):
    return tender_pdf([[para(f"PLIEGO SINTÉTICO {text}"), para("1. Objeto de prueba.")]])


@pytest.fixture
def procedure(operator_user):
    return make_procedure(operator_user)


@pytest.fixture
def document(operator_user, procedure):
    return load_and_read(operator_user, procedure, pdf("v1"), title="Pliego",
                         file_name="v1.pdf")


def events(outcome=Outcome.OK):
    return AuditEvent.objects.filter(event_type=EventType.DOCUMENT_CHANGE, outcome=outcome)


def test_replace_keeps_the_old_document_and_adds_the_new_one(
        operator_user, evaluator_user, procedure, document):
    """REQ-099: el reemplazo deja la versión anterior y la nueva, con quién y cuándo."""
    original = bytes(m.DocumentFile.objects.get(document=document).content)
    change, loaded = history.replace(evaluator_user, document, data=pdf("v2"),
                                     file_name="v2.pdf", note="versión corregida")
    new = loaded.document
    assert (change.document, change.new_document, change.user) == (document, new,
                                                                   evaluator_user)
    assert change.action == "reemplazar" and change.note == "versión corregida"
    assert change.at is not None and change.event.event_type == EventType.DOCUMENT_CHANGE
    assert (new.kind, new.title, new.procedure) == (document.kind, document.title, procedure)
    assert list(history.current_documents(procedure)) == [new]
    assert list(history.replaced_documents(procedure)) == [document]
    assert history.state(document) == "reemplazado" and history.state(new) == "vigente"
    assert bytes(m.DocumentFile.objects.get(document=document).content) == original
    assert m.Document.objects.filter(procedure=procedure).count() == 2
    assert m.Job.objects.filter(document=new, kind=m.JobKind.READ_DOCUMENT).exists()


def test_history_shows_every_version_in_order(operator_user, procedure, document):
    """REQ-099: la historia de cualquier versión muestra toda la cadena."""
    _, second = history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    _, third = history.replace(operator_user, second.document, data=pdf("v3"),
                               file_name="v3.pdf")
    history.withdraw(operator_user, third.document, "ya no rige")
    for version in (document, second.document, third.document):
        rows = history.history(version)
        assert [r.action for r in rows] == ["reemplazar", "reemplazar", "retirar"]
        assert all(r.user == operator_user and r.at for r in rows)


def test_withdrawn_leaves_current_and_appears_in_withdrawn_and_restore_returns_it(
        operator_user, procedure, document):
    """REQ-099: retirado sale de lo vigente y aparece en retirados; restituir lo devuelve."""
    row = history.withdraw(operator_user, document, "cargado por error")
    assert row.action == "retirar" and row.new_document is None
    assert list(history.current_documents(procedure)) == []
    assert list(history.withdrawn_documents(procedure)) == [document]
    back = history.restore(operator_user, document)
    assert back.action == "restituir"
    assert list(history.current_documents(procedure)) == [document]
    assert list(history.withdrawn_documents(procedure)) == []
    assert [r.action for r in history.history(document)] == ["retirar", "restituir"]
    assert m.Document.objects.filter(pk=document.pk).exists()


def test_each_operation_leaves_its_audit_event(operator_user, procedure, document):
    """P6: cada operación deja el hecho `document_change` con su detalle."""
    history.withdraw(operator_user, document, "nota")
    history.restore(operator_user, document)
    _, loaded = history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    rows = list(events().order_by("id"))
    assert [e.detail["action"] for e in rows] == ["retirar", "restituir", "reemplazar"]
    assert rows[2].detail["new_document"] == loaded.document.pk
    assert rows[2].detail["file_sha256"] == document.file_sha256
    assert all(e.user == operator_user for e in rows)
    assert m.DocumentChange.objects.filter(event__in=rows).count() == 3


@pytest.mark.parametrize("prepare, operation, reason", [
    ("withdraw", "withdraw", "not_vigente"),
    ("withdraw", "replace", "not_vigente"),
    ("none", "restore", "not_retirado"),
    ("replace", "restore", "not_retirado"),
    ("replace", "withdraw", "not_vigente"),
])
def test_a_change_that_does_not_apply_is_refused_and_recorded(
        operator_user, procedure, document, prepare, operation, reason):
    """REQ-099: solo se retira o reemplaza lo vigente y solo se restituye lo retirado; el
    rechazo queda en el registro y no agrega ningún cambio."""
    if prepare == "withdraw":
        history.withdraw(operator_user, document)
    elif prepare == "replace":
        history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    before = m.DocumentChange.objects.count()
    with pytest.raises(history.HistoryRefused) as refusal:
        if operation == "replace":
            history.replace(operator_user, document, data=pdf("v3"), file_name="v3.pdf")
        else:
            getattr(history, operation)(operator_user, document)
    assert refusal.value.reason == reason
    assert m.DocumentChange.objects.count() == before
    assert events(Outcome.REJECTED).get().detail["reason"] == reason


def test_a_user_without_commission_role_cannot_change_documents(
        no_commission_user, procedure, document):
    """Roles: sin rol de la Comisión no se reemplaza, retira ni restituye."""
    for call in (lambda: history.withdraw(no_commission_user, document),
                 lambda: history.restore(no_commission_user, document),
                 lambda: history.replace(no_commission_user, document, data=pdf("x"),
                                         file_name="x.pdf")):
        with pytest.raises(RoleRejected):
            call()
    assert m.DocumentChange.objects.count() == 0


def test_replacing_with_the_same_file_is_refused_without_a_change(
        operator_user, procedure, document):
    """Un archivo repetido se rechaza por su huella, como en la carga."""
    with pytest.raises(documents.DuplicateFile):
        history.replace(operator_user, document, file_name="otra.pdf",
                        data=bytes(m.DocumentFile.objects.get(document=document).content))
    assert m.DocumentChange.objects.count() == 0
    assert m.Document.objects.count() == 1


def test_the_new_document_must_belong_to_the_same_procedure(
        operator_user, procedure, document):
    """Aviso de T-193: el esquema no lo comprueba; el servicio sí."""
    elsewhere = load_and_read(operator_user, make_procedure(operator_user), pdf("zzz"),
                              title="Otro", file_name="z.pdf")
    with pytest.raises(history.HistoryRefused) as refusal:
        history.link_replacement(operator_user, document, elsewhere)
    assert refusal.value.reason == "other_procedure"
    with pytest.raises(history.HistoryRefused):
        history.link_replacement(operator_user, document, document)
    assert m.DocumentChange.objects.count() == 0


def test_withdrawn_documents_are_not_used_to_propose_the_matrix(
        operator_user, procedure, document):
    """REQ-099: lo retirado o reemplazado deja de usarse en la propuesta de la matriz."""
    annex = load_and_read(operator_user, procedure, pdf("anexo"), title="Anexo",
                          file_name="a.pdf", kind=m.DocumentKind.ANEXO)
    assert list(matrix.base_documents(procedure)) == [document, annex]
    history.withdraw(operator_user, annex)
    assert list(matrix.base_documents(procedure)) == [document]
    _, loaded = history.replace(operator_user, document, data=pdf("v2"), file_name="v2.pdf")
    assert list(matrix.base_documents(procedure)) == [loaded.document]
    run_jobs()
    history.withdraw(operator_user, loaded.document)
    with pytest.raises(matrix.MatrixRefused) as refusal:
        matrix.request_matrix(operator_user, procedure)
    assert refusal.value.reason == "no_documents"


def test_a_validated_matrix_does_not_change_and_is_marked(operator_user, validated_matrix):
    """REQ-099: la versión validada no cambia; queda marcada como armada con un documento
    retirado."""
    procedure, version = validated_matrix.procedure, validated_matrix.version
    assert history.versions_with_withdrawn(procedure) == []
    # La versión del caso chico se arma sin propuesta: se agrega una versión validada con
    # una propuesta que usó los documentos base.
    run = m.MatrixRun.objects.create(
        procedure=procedure, channel=m.RunChannel.EVAL,
        documents=matrix._documents_snapshot(procedure),
        authorization_date=procedure.authorization_date)
    version = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, status=m.VersionStatus.VALIDATED, run=run,
        created_by=operator_user, validated_at=timezone.now(), validated_by=operator_user)
    used = version.run.documents[0]["document"]
    document = m.Document.objects.get(pk=used)

    def snapshot():
        version.refresh_from_db()
        version.run.refresh_from_db()
        return (version.status, list(version.requirements.values_list("pk", flat=True)),
                list(version.run.documents))

    before = snapshot()
    history.withdraw(operator_user, document, "documento equivocado")
    assert snapshot() == before
    assert version.status == m.VersionStatus.VALIDATED
    marked = history.versions_with_withdrawn(procedure)
    assert [(v.pk, [d.pk for d in docs]) for v, docs in marked] == [(version.pk, [used])]
    history.restore(operator_user, document)
    assert history.versions_with_withdrawn(procedure) == []
