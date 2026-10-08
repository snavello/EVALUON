"""Esquema de la 014 en `tenders` (T-193; plan 014, "Modelo de datos"; ADR-0048 y ADR-0049).

Historial de documentos del pliego (solo inserción), tipo `dictamen`, borrador de
procedimiento y pedidos `propose_procedure` y `propose_offer`. Las restricciones las hace
valer la base: se prueban con el modelo y con SQL directo. Textos inventados (P4).
"""

import hashlib
import itertools
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.tenders import models as m

pytestmark = pytest.mark.django_db

_counter = itertools.count(1)


def sha(seed):
    return hashlib.sha256(str(seed).encode()).hexdigest()


@pytest.fixture
def procedure(read_write_user):
    return m.Procedure.objects.create(
        number=f"PROC-014-{next(_counter)}", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=read_write_user)


@pytest.fixture
def make_document(read_write_user, procedure):
    def make(**fields):
        values = {"kind": m.DocumentKind.PLIEGO, "title": "Pliego", "file_name": "p.pdf",
                  "file_format": "pdf", "file_size": 10, "file_sha256": sha(next(_counter)),
                  "loaded_by": read_write_user}
        values.update(fields)
        return m.Document.objects.create(procedure=procedure, **values)
    return make


@pytest.fixture
def event(read_write_user):
    return audit.record(EventType.DOCUMENT_CHANGE, outcome=Outcome.OK,
                        channel=Channel.SCREEN, user=read_write_user)


def change(document, event, user, action, **fields):
    return m.DocumentChange.objects.create(document=document, action=action, user=user,
                                           event=event, **fields)


# --- Historial de documentos (REQ-099, ADR-0048) ----------------------------------------


def test_the_document_change_table_exists_and_accepts_the_three_actions(
        make_document, event, read_write_user):
    """REQ-099: reemplazar (con el documento nuevo), retirar y restituir se insertan."""
    old, new = make_document(), make_document(file_name="p2.pdf")
    first = change(old, event, read_write_user, m.DocumentChangeAction.REEMPLAZAR,
                   new_document=new, note="versión corregida")
    change(new, event, read_write_user, m.DocumentChangeAction.RETIRAR)
    change(new, event, read_write_user, m.DocumentChangeAction.RESTITUIR)
    assert m.DocumentChange.objects.count() == 3
    assert first.new_document == new and old.changes.get() == first
    assert new.replaces.get() == first


@pytest.mark.parametrize("statement", ["UPDATE tenders_document_change SET note = 'x'",
                                       "DELETE FROM tenders_document_change"])
def test_the_document_change_table_is_insert_only(
        make_document, event, read_write_user, statement):
    """REQ-099 (P6): UPDATE y DELETE se rechazan, también por SQL."""
    change(make_document(), event, read_write_user, m.DocumentChangeAction.RETIRAR)
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(statement)


def test_a_change_cannot_be_modified_from_the_model(make_document, event, read_write_user):
    row = change(make_document(), event, read_write_user, m.DocumentChangeAction.RETIRAR)
    row.note = "otra"
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        row.save()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        row.delete()


def test_a_replacement_needs_the_new_document(make_document, event, read_write_user):
    """REQ-099: `reemplazar` sin documento nuevo, `retirar` con documento nuevo y un
    documento que se reemplaza a sí mismo, se rechazan."""
    doc = make_document()
    for action, extra in [(m.DocumentChangeAction.REEMPLAZAR, {}),
                          (m.DocumentChangeAction.RETIRAR, {"new_document": make_document()}),
                          (m.DocumentChangeAction.RESTITUIR, {"new_document": make_document()}),
                          (m.DocumentChangeAction.REEMPLAZAR, {"new_document": doc})]:
        with pytest.raises(IntegrityError), transaction.atomic():
            change(doc, event, read_write_user, action, **extra)


def test_an_unknown_action_is_rejected(make_document, event, read_write_user):
    with pytest.raises(IntegrityError), transaction.atomic():
        change(make_document(), event, read_write_user, "borrar")


def test_a_document_with_changes_cannot_be_deleted(make_document, event, read_write_user):
    """REQ-099: el documento y su historial no se borran (PROTECT)."""
    doc = make_document()
    change(doc, event, read_write_user, m.DocumentChangeAction.RETIRAR)
    with pytest.raises(Exception), transaction.atomic():
        doc.delete()


def test_a_change_cannot_exist_without_its_audit_event(make_document, read_write_user):
    """P6: cada cambio apunta a su hecho de auditoría."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.DocumentChange.objects.create(
            document=make_document(), action=m.DocumentChangeAction.RETIRAR,
            user=read_write_user, event_id=None)


# --- Tipo dictamen (REQ-092) -------------------------------------------------------------


def test_a_dictamen_can_be_loaded_as_a_tender_document(make_document):
    """REQ-092: el dictamen subido es un documento del pliego del tipo `dictamen`."""
    assert make_document(kind=m.DocumentKind.DICTAMEN).kind == "dictamen"


# --- Pedidos nuevos en la cola (REQ-077, REQ-083) ---------------------------------------


def test_propose_procedure_may_have_no_procedure(read_write_user):
    """REQ-077: el pedido que lee el pliego existe antes del procedimiento."""
    job = m.Job.objects.create(kind=m.JobKind.PROPOSE_PROCEDURE, target_id=1,
                               requested_by=read_write_user)
    assert job.procedure is None


def test_propose_offer_needs_a_procedure(read_write_user, procedure):
    """REQ-083: el borrador de una oferta cuelga de un procedimiento."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.Job.objects.create(kind=m.JobKind.PROPOSE_OFFER, target_id=1,
                             requested_by=read_write_user)
    assert m.Job.objects.create(kind=m.JobKind.PROPOSE_OFFER, target_id=1,
                                procedure=procedure,
                                requested_by=read_write_user).pk


@pytest.mark.parametrize("kind", [m.JobKind.PROPOSE_PROCEDURE, m.JobKind.PROPOSE_OFFER])
def test_a_proposal_job_names_its_draft(read_write_user, procedure, kind):
    """REQ-077, REQ-083: sin `target_id` (el borrador) el pedido se rechaza."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.Job.objects.create(kind=kind, procedure=procedure, requested_by=read_write_user)


@pytest.mark.parametrize("kind", [m.JobKind.READ_DOCUMENT, m.JobKind.PROPOSE_MATRIX,
                                  m.JobKind.EVALUATE_OFFERS])
def test_the_other_jobs_still_need_a_procedure(read_write_user, kind):
    """El ajuste de la restricción no abre el resto de los tipos."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.Job.objects.create(kind=kind, target_id=1, requested_by=read_write_user)


def test_the_job_kinds_are_the_existing_plus_two():
    assert {"propose_procedure", "propose_offer"} <= set(m.JobKind.values)
    assert len(m.JobKind.values) == 9


# --- Borrador de procedimiento (REQ-077, ADR-0049) ---------------------------------------


def make_draft(user, **fields):
    values = {"file_name": "pliego.pdf", "file_format": "pdf", "file_size": 14,
              "file_sha256": sha(next(_counter)), "content": b"%PDF-sintetico",
              "created_by": user}
    values.update(fields)
    return m.ProcedureDraft.objects.create(**values)


def test_a_draft_starts_reading_and_keeps_the_original_bytes(read_write_user):
    """REQ-077: el pliego espera en el borrador, con sus bytes y su huella."""
    draft = make_draft(read_write_user)
    draft.refresh_from_db()
    assert draft.state == ProposalState.LEYENDO and draft.proposal == {}
    assert bytes(draft.content) == b"%PDF-sintetico"
    assert len(draft.file_sha256) == 64


def test_a_draft_moves_through_its_states_and_may_link_a_job(read_write_user):
    """REQ-077: el borrador cambia de estado (no es un registro de hechos) y nombra su
    pedido."""
    draft = make_draft(read_write_user)
    job = m.Job.objects.create(kind=m.JobKind.PROPOSE_PROCEDURE, target_id=draft.pk,
                               requested_by=read_write_user)
    draft.job, draft.state = job, ProposalState.PROPUESTO
    draft.proposal = {"numero": {"propuesto": "X-1", "cita": {"pagina": 1, "texto": "X-1"}}}
    draft.save()
    draft.refresh_from_db()
    assert (draft.state, draft.job) == (ProposalState.PROPUESTO, job)


def test_an_approved_draft_names_the_procedure_it_created(read_write_user, procedure):
    """REQ-077: aprobado dice qué procedimiento creó; ningún otro estado lo tiene."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(read_write_user, state=ProposalState.APROBADO)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(read_write_user, state=ProposalState.PROPUESTO, procedure=procedure)
    ok = make_draft(read_write_user, state=ProposalState.APROBADO, procedure=procedure)
    assert procedure.draft == ok


@pytest.mark.parametrize("fields", [{"state": "pendiente"}, {"file_sha256": "abc"},
                                    {"file_format": "docx"}])
def test_a_draft_rejects_invalid_values(read_write_user, fields):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_draft(read_write_user, **fields)


def test_the_proposal_states_are_the_plans():
    assert set(ProposalState.values) == {"leyendo", "propuesto", "aprobado", "rechazado",
                                         "fallido"}


# --- Migraciones sobre datos existentes (REQ-077, REQ-099) --------------------------------

PREVIOUS = [("tenders", "0008_job_progress"), ("offers", "0006_informe_tecnico_del_area"),
            ("portal", "0003_garantias"), ("assessment", "0004_triggers"),
            ("norms", "0007_norm_citation"), ("audit", "0007_evaluacion")]


@pytest.mark.django_db(transaction=True)
def test_the_014_migrations_apply_over_existing_data_and_are_reversible(
        make_document, read_write_user, procedure):
    """REQ-077, REQ-099: con un procedimiento, un documento, un pedido, un hecho y un
    renglón del Portal ya guardados, las migraciones de la 014 se revierten y se vuelven a
    aplicar sin perder nada, y el renglón sigue con su ítem de origen."""
    from django.db.migrations.executor import MigrationExecutor

    from evaluon.portal import models as p

    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/x?qs=1",
                                       created_by=read_write_user)
    page = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                       url=link.url, sha256=sha("pg"), content=b"<html/>")
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    item = p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.RENGLONES,
                                       key="renglones", payload={}, content_sha256=sha("it"),
                                       page=page)
    p.PortalProcedureData.objects.create(procedure=procedure, file_number="EX-1", item=item)
    line = p.PortalLine.objects.create(procedure=procedure, number=1, description="Resma",
                                       item=item)
    document = make_document()
    job = m.Job.objects.create(kind=m.JobKind.READ_DOCUMENT, procedure=procedure,
                               document=document, requested_by=read_write_user)
    audit.record(EventType.PROCEDURE, outcome=Outcome.OK, channel=Channel.SCREEN,
                 user=read_write_user)

    def migrate(targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)

    latest = [(app, MigrationExecutor(connection).loader.graph.leaf_nodes(app)[0][1])
              for app, _ in PREVIOUS]
    try:
        migrate(PREVIOUS)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('tenders_document_change'), "
                           "to_regclass('offers_offer_draft'), to_regclass('norms_upload'), "
                           "to_regclass('assessment_discard_decision')")
            assert cursor.fetchone() == (None, None, None, None)
            cursor.execute("SELECT count(*) FROM tenders_document WHERE id = %s",
                           [document.pk])
            assert cursor.fetchone()[0] == 1
        migrate(latest)
        assert m.Document.objects.get(pk=document.pk).file_sha256 == document.file_sha256
        assert m.Job.objects.get(pk=job.pk).kind == m.JobKind.READ_DOCUMENT
        migrated = p.PortalLine.objects.get(pk=line.pk)
        assert (migrated.item_id, migrated.document_id) == (item.pk, None)
        assert p.PortalProcedureData.objects.get(procedure=procedure).item_id == item.pk
    finally:
        migrate(latest)
