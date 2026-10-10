"""Descartar una norma subida por error (T-225; REQ-094, ADR-0051).

La norma de prueba es una página de Infoleg sintética, con contenido inventado (P4)."""

import pytest
from django.contrib.auth import get_user_model

from evaluon.accounts.models import CommissionRole, Role
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.models import Norm, NormUpload, ProposalState
from evaluon.norms.services import upload
from tests.accounts.test_session import TEST_PASSWORD
from tests.norms.test_upload_proposal import RESOLUTION, stage_resolution

pytestmark = pytest.mark.django_db


def make_user(name, commission, role=Role.READ_WRITE):
    return get_user_model().objects.create_user(
        username=name, password=TEST_PASSWORD, role=role, commission_role=commission)


@pytest.fixture
def operator(db):
    return make_user("operador-que-sube", CommissionRole.OPERATOR)


@pytest.fixture
def other_operator(db):
    return make_user("otro-operador", CommissionRole.OPERATOR)


@pytest.fixture
def evaluator(db):
    return make_user("evaluador-que-descarta", CommissionRole.EVALUATOR)


def reject_events(outcome):
    return AuditEvent.objects.filter(event_type=EventType.NORM_UPLOAD, outcome=outcome,
                                     detail__action="reject")


def test_reject_needs_a_reason_and_keeps_the_file_who_when_and_the_fact(operator):
    """REQ-094, P6: descartar exige motivo; la subida queda «rechazado» con el archivo, el motivo,
    quién y cuándo, y deja el hecho `norm_upload`. No se carga ninguna norma."""
    staged = stage_resolution(operator)
    with pytest.raises(upload.InvalidCorrection):
        upload.reject(operator, staged.pk, "  ")
    staged.refresh_from_db()
    assert staged.state == ProposalState.PROPUESTO
    assert reject_events(Outcome.REJECTED).count() == 1

    rejected = upload.reject(operator, staged.pk, "Subí el archivo equivocado.")
    rejected.refresh_from_db()
    assert rejected.state == ProposalState.RECHAZADO and rejected.document is None
    assert bytes(rejected.content) == RESOLUTION
    assert rejected.proposal["rechazo"]["motivo"] == "Subí el archivo equivocado."
    assert rejected.proposal["rechazo"]["quien"] == operator.username
    assert rejected.proposal["rechazo"]["cuando"]
    assert rejected.proposal["fields"]["number"]["propuesto"] == "9999"
    event = reject_events(Outcome.OK).get()
    assert event.user == operator and event.detail["upload"] == staged.pk
    assert event.detail["motivo"] == "Subí el archivo equivocado."
    assert event.detail["file"]["sha256"] == staged.file_sha256
    assert not Norm.objects.exists()


def test_a_rejected_upload_does_not_block_uploading_the_same_file_again(operator):
    """REQ-094: el archivo de una subida descartada se puede volver a subir."""
    first = stage_resolution(operator)
    with pytest.raises(upload.AlreadyStaged):
        stage_resolution(operator)
    upload.reject(operator, first.pk, "Datos equivocados: la vuelvo a subir.")
    second = stage_resolution(operator)
    assert second.pk != first.pk and second.state == ProposalState.PROPUESTO
    assert NormUpload.objects.count() == 2


def test_the_evaluator_or_the_operator_who_uploaded_it_rejects_it_and_nobody_else(
        operator, other_operator, evaluator, read_write_user):
    """REQ-094, P3: descarta el evaluador o el operador que la subió; otro operador o alguien sin
    rol de la Comisión no, y el rechazo queda registrado."""
    staged = stage_resolution(operator)
    for user in (other_operator, read_write_user):
        with pytest.raises(upload.RejectNotAllowed):
            upload.reject(user, staged.pk, "No es mía.")
    assert reject_events(Outcome.REJECTED).count() == 2
    staged.refresh_from_db()
    assert staged.state == ProposalState.PROPUESTO
    upload.reject(evaluator, staged.pk, "Archivo equivocado.")
    staged.refresh_from_db()
    assert staged.state == ProposalState.RECHAZADO


def test_reject_needs_the_read_write_role(operator):
    """El rol de normativa de lectura y escritura sigue siendo el de toda la carga."""
    staged = stage_resolution(operator)
    reader = make_user("solo-lectura", CommissionRole.EVALUATOR, role=Role.READ)
    with pytest.raises(RoleRejected):
        upload.reject(reader, staged.pk, "Motivo.")


def test_only_a_waiting_upload_is_rejected(operator):
    """REQ-094: una subida ya descartada (o aprobada) no se descarta de nuevo ni se confirma."""
    staged = stage_resolution(operator)
    upload.reject(operator, staged.pk, "Archivo equivocado.")
    with pytest.raises(upload.UploadNotPending):
        upload.reject(operator, staged.pk, "Otra vez.")
    with pytest.raises(upload.UploadNotPending):
        upload.confirm(operator, staged.pk)
    with pytest.raises(upload.UploadNotFound):
        upload.reject(operator, staged.pk + 999, "No existe.")
