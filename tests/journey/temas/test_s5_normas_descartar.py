"""«Descartar esta subida» en la pestaña Normativas (REQ-094; T-225). Normas de prueba sintéticas,
con contenido inventado (P4)."""

import pytest

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.models import NormUpload, ProposalState
from tests.journey.conftest import procedure  # noqa: F401  (fixture)
from tests.journey.temas.test_s5_normas import (  # noqa: F401  (fixtures y ayudas)
    embeddings,
    evaluator,
    log_in,
    make_user,
    notice,
    operator,
    page,
    send,
    url,
)
from evaluon.accounts.models import CommissionRole

pytestmark = pytest.mark.django_db


def discard(client, procedure, upload_id, reason="Subí el archivo equivocado."):
    return client.post(url("s5_descartar", procedure, upload_id), {"reason": reason})


def test_the_uploader_sees_discard_and_discarding_returns_with_notice(
        client, procedure, operator):
    """REQ-094: quien subió la norma ve «Descartar esta subida» con motivo obligatorio; al
    descartarla vuelve a la pestaña con el aviso, la subida deja de esperar y queda el hecho."""
    log_in(client, operator)
    send(client, procedure)
    staged = NormUpload.objects.get()
    html = page(client, procedure)
    assert "Descartar esta subida" in html and url("s5_descartar", procedure, staged.pk) in html
    assert "Motivo para descartarla (obligatorio)" in html
    ok, text = notice(client, discard(client, procedure, staged.pk, " "))
    assert not ok and "motivo" in text
    ok, text = notice(client, discard(client, procedure, staged.pk))
    assert ok and "Se descartó la subida «rg-9999-2024.htm»" in text
    staged.refresh_from_db()
    assert staged.state == ProposalState.RECHAZADO
    html = page(client, procedure)
    assert f'id="s5-subida-{staged.pk}"' not in html
    assert AuditEvent.objects.filter(event_type=EventType.NORM_UPLOAD, outcome=Outcome.OK,
                                     detail__action="reject").count() == 1


def test_after_discarding_the_same_file_can_be_uploaded_again(client, procedure, operator):
    """REQ-094: descartada la subida equivocada, el mismo archivo se vuelve a subir."""
    log_in(client, operator)
    send(client, procedure)
    first = NormUpload.objects.get()
    discard(client, procedure, first.pk)
    ok, _ = notice(client, send(client, procedure))
    assert ok
    assert NormUpload.objects.filter(state=ProposalState.PROPUESTO).exclude(pk=first.pk).exists()


def test_another_operator_does_not_see_discard_and_cannot_discard(
        client, procedure, operator, evaluator):
    """REQ-094, P3: otro operador no ve el botón y, si lo intenta, no cambia nada; el evaluador
    sí descarta la subida de otro."""
    log_in(client, operator)
    send(client, procedure)
    staged = NormUpload.objects.get()
    client.logout()
    other = make_user("otro-operador-normas", commission=CommissionRole.OPERATOR)
    log_in(client, other)
    html = page(client, procedure)
    assert url("s5_descartar", procedure, staged.pk) not in html
    ok, text = notice(client, discard(client, procedure, staged.pk))
    assert not ok and "quien la subió" in text
    staged.refresh_from_db()
    assert staged.state == ProposalState.PROPUESTO
    client.logout()
    log_in(client, evaluator)
    assert url("s5_descartar", procedure, staged.pk) in page(client, procedure)
    ok, _ = notice(client, discard(client, procedure, staged.pk))
    assert ok
