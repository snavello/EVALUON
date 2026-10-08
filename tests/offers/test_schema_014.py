"""Esquema de la 014 en `offers` (T-193; plan 014, "Modelo de datos"; ADR-0048 y ADR-0049).

Historial de documentos de la oferta (solo inserción), tipo `anexo_tecnico` y borrador de
oferta con sus archivos. Las restricciones las hace valer la base. Textos inventados (P4).
"""

import hashlib
import itertools
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.offers import models as om
from evaluon.tenders import models as tm

pytestmark = pytest.mark.django_db

_counter = itertools.count(1)


def sha(seed):
    return hashlib.sha256(str(seed).encode()).hexdigest()


@pytest.fixture
def procedure(read_write_user):
    return tm.Procedure.objects.create(
        number=f"PROC-014-O-{next(_counter)}", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=read_write_user)


@pytest.fixture
def offer(procedure, read_write_user):
    return om.Offer.objects.create(procedure=procedure, number=1, bidder="Oferente SA",
                                   created_by=read_write_user)


@pytest.fixture
def make_document(offer, read_write_user):
    def make(**fields):
        values = {"title": "Oferta", "file_name": "o.pdf", "file_format": "pdf",
                  "file_size": 10, "file_sha256": sha(next(_counter)),
                  "loaded_by": read_write_user}
        values.update(fields)
        return om.Document.objects.create(offer=offer, **values)
    return make


@pytest.fixture
def event(read_write_user):
    return audit.record(EventType.DOCUMENT_CHANGE, outcome=Outcome.OK,
                        channel=Channel.SCREEN, user=read_write_user)


def change(document, event, user, action, **fields):
    return om.DocumentChange.objects.create(document=document, action=action, user=user,
                                            event=event, **fields)


# --- Historial de documentos (REQ-099, ADR-0048) ----------------------------------------


def test_the_three_actions_are_inserted(make_document, event, read_write_user):
    """REQ-099: reemplazar (con el documento nuevo), retirar y restituir."""
    old, new = make_document(), make_document(file_name="o2.pdf")
    first = change(old, event, read_write_user, tm.DocumentChangeAction.REEMPLAZAR,
                   new_document=new, note="versión firmada")
    change(new, event, read_write_user, tm.DocumentChangeAction.RETIRAR)
    change(new, event, read_write_user, tm.DocumentChangeAction.RESTITUIR)
    assert om.DocumentChange.objects.count() == 3
    assert old.changes.get() == first and new.replaces.get() == first


@pytest.mark.parametrize("statement", ["UPDATE offers_document_change SET note = 'x'",
                                       "DELETE FROM offers_document_change"])
def test_the_change_table_is_insert_only(make_document, event, read_write_user, statement):
    """REQ-099 (P6): UPDATE y DELETE se rechazan, también por SQL."""
    change(make_document(), event, read_write_user, tm.DocumentChangeAction.RETIRAR)
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(statement)


def test_a_change_cannot_be_modified_from_the_model(make_document, event, read_write_user):
    row = change(make_document(), event, read_write_user, tm.DocumentChangeAction.RETIRAR)
    row.note = "otra"
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        row.save()


def test_a_replacement_needs_the_new_document_and_only_it(make_document, event,
                                                          read_write_user):
    doc = make_document()
    for action, extra in [(tm.DocumentChangeAction.REEMPLAZAR, {}),
                          (tm.DocumentChangeAction.RETIRAR,
                           {"new_document": make_document()}),
                          (tm.DocumentChangeAction.REEMPLAZAR, {"new_document": doc}),
                          ("borrar", {})]:
        with pytest.raises(IntegrityError), transaction.atomic():
            change(doc, event, read_write_user, action, **extra)


def test_a_document_with_changes_cannot_be_deleted(make_document, event, read_write_user):
    doc = make_document()
    change(doc, event, read_write_user, tm.DocumentChangeAction.RETIRAR)
    with pytest.raises(Exception), transaction.atomic():
        doc.delete()


# --- Anexo técnico (REQ-087) -------------------------------------------------------------


def test_a_technical_annex_is_a_document_kind(make_document):
    """REQ-087: la ficha técnica subida figura como anexo técnico de la oferta."""
    assert make_document(kind=om.DocumentKind.ANEXO_TECNICO).kind == "anexo_tecnico"


def test_the_document_kinds_are_the_existing_plus_the_annex():
    assert set(om.DocumentKind.values) == {"economica", "tecnica", "garantia", "compliance",
                                           "informe_tecnico", "anexo_tecnico", "otro"}


def test_an_invalid_kind_is_still_rejected(make_document):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_document(kind="inventado")


# --- Borrador de oferta (REQ-083, ADR-0049) ---------------------------------------------


def make_draft(procedure, user, **fields):
    return om.OfferDraft.objects.create(procedure=procedure, created_by=user, **fields)


def add_file(draft, name="oferta.pdf", **fields):
    values = {"file_name": name, "file_format": "pdf", "file_size": 14,
              "file_sha256": sha(next(_counter)), "content": b"%PDF-sintetico"}
    values.update(fields)
    return om.OfferDraftFile.objects.create(draft=draft, **values)


def test_a_draft_holds_several_files_with_their_bytes(procedure, read_write_user):
    """REQ-083: los archivos esperan en el borrador, con bytes y huella."""
    draft = make_draft(procedure, read_write_user)
    add_file(draft, "a.pdf")
    add_file(draft, "b.pdf")
    draft.refresh_from_db()
    assert draft.state == ProposalState.LEYENDO and draft.proposal == {}
    assert draft.files.count() == 2
    assert bytes(draft.files.first().content) == b"%PDF-sintetico"


def test_the_same_file_twice_in_a_draft_is_rejected(procedure, read_write_user):
    draft = make_draft(procedure, read_write_user)
    add_file(draft, "a.pdf", file_sha256=sha("igual"))
    with pytest.raises(IntegrityError), transaction.atomic():
        add_file(draft, "b.pdf", file_sha256=sha("igual"))


@pytest.mark.parametrize("fields", [{"file_sha256": "abc"}, {"file_format": "html"}])
def test_a_draft_file_rejects_invalid_values(procedure, read_write_user, fields):
    draft = make_draft(procedure, read_write_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        add_file(draft, **fields)


def test_a_draft_moves_through_its_states(procedure, read_write_user):
    draft = make_draft(procedure, read_write_user)
    job = tm.Job.objects.create(kind=tm.JobKind.PROPOSE_OFFER, procedure=procedure,
                                target_id=draft.pk, requested_by=read_write_user)
    draft.job, draft.state = job, ProposalState.PROPUESTO
    draft.proposal = {"cuit": {"propuesto": "30-00000000-0"}}
    draft.save()
    draft.refresh_from_db()
    assert (draft.state, draft.job) == (ProposalState.PROPUESTO, job)


def test_an_approved_draft_names_the_offer_it_created(procedure, read_write_user, offer):
    """REQ-083: aprobado dice qué oferta creó; ningún otro estado lo tiene."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(procedure, read_write_user, state=ProposalState.APROBADO)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(procedure, read_write_user, state=ProposalState.RECHAZADO, offer=offer)
    ok = make_draft(procedure, read_write_user, state=ProposalState.APROBADO, offer=offer)
    assert offer.draft == ok


def test_a_draft_rejects_an_invalid_state(procedure, read_write_user):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(procedure, read_write_user, state="pendiente")
