"""Esquema de la 014 en `norms` (T-193; plan 014, "Modelo de datos"; ADR-0051): la norma
subida que espera la confirmación de la Comisión. Textos inventados (P4)."""

import pytest
from django.db import IntegrityError, transaction

from evaluon.norms import models as nm
from tests.conftest import sha256_hex

pytestmark = pytest.mark.django_db


def make_upload(user, **fields):
    values = {"file_name": "norma.pdf", "file_format": "pdf", "file_size": 14,
              "file_sha256": sha256_hex("norma subida"), "content": b"%PDF-sintetico",
              "uploaded_by": user}
    values.update(fields)
    return nm.NormUpload.objects.create(**values)


def test_an_upload_starts_reading_and_keeps_the_original_bytes(read_write_user):
    """REQ-094: la norma espera en la subida, con sus bytes y su huella."""
    upload = make_upload(read_write_user)
    upload.refresh_from_db()
    assert upload.state == nm.ProposalState.LEYENDO and upload.proposal == {}
    assert bytes(upload.content) == b"%PDF-sintetico"
    assert upload.document is None


def test_an_upload_keeps_proposed_and_corrected_values(read_write_user):
    """REQ-094: cada dato lleva propuesto, corregido, motivo, quién y cuándo."""
    upload = make_upload(read_write_user)
    upload.proposal = {"number": {"propuesto": "297", "corregido": "298",
                                  "motivo": "error del encabezado", "quien": "evaluador",
                                  "cuando": "2026-10-07T10:00:00",
                                  "evidencia": {"pagina": 1, "texto": "Disposición 297"}}}
    upload.state = nm.ProposalState.PROPUESTO
    upload.save()
    upload.refresh_from_db()
    assert upload.proposal["number"]["propuesto"] == "297"
    assert upload.proposal["number"]["corregido"] == "298"


def test_an_approved_upload_names_the_document_it_created(
        read_write_user, make_norm, make_document):
    """REQ-094: aprobada dice qué documento de norma creó; ningún otro estado lo tiene."""
    document = make_document(make_norm())
    with pytest.raises(IntegrityError), transaction.atomic():
        make_upload(read_write_user, state=nm.ProposalState.APROBADO)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_upload(read_write_user, state=nm.ProposalState.PROPUESTO, document=document)
    ok = make_upload(read_write_user, state=nm.ProposalState.APROBADO, document=document)
    assert document.upload == ok


@pytest.mark.parametrize("fields", [{"state": "pendiente"}, {"file_sha256": "abc"},
                                    {"file_format": "docx"}])
def test_an_upload_rejects_invalid_values(read_write_user, fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_upload(read_write_user, **fields)


def test_the_same_file_may_be_uploaded_again_after_a_failure(read_write_user):
    """El rechazo del mismo archivo lo hace `load_norm` (REQ-011); la subida no lo impide,
    así un intento fallido no bloquea el siguiente."""
    make_upload(read_write_user, state=nm.ProposalState.FALLIDO)
    make_upload(read_write_user)
    assert nm.NormUpload.objects.count() == 2
