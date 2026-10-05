"""El esquema de ofertas y fichas y sus triggers de inmutabilidad (REQ-037, REQ-038, REQ-039,
REQ-042; plan 008, "Modelo de datos" e "Inmutabilidad"; ADR-0026; T-130)."""

import pytest
from django.db import IntegrityError, connection, transaction

from evaluon.audit.models import EventType
from evaluon.offers import models as om
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


@pytest.fixture
def sheet(procedure, matrix, offer, operator_user):
    return om.Sheet.objects.create(
        offer=offer, matrix_version=matrix.version, number=1, channel="screen",
        readings=[], models_used={}, parameters={}, prompt_versions={}, requested_by=operator_user)


@pytest.fixture
def entry(sheet, matrix):
    return om.SheetEntry.objects.create(
        sheet=sheet, requirement=matrix.version.requirements.first(), outcome="no_encontrado")


def test_an_offer_bidder_is_unique_in_the_procedure(procedure, offer, operator_user):
    """REQ-037: un oferente tiene una oferta por procedimiento."""
    with pytest.raises(IntegrityError), transaction.atomic():
        om.Offer.objects.create(procedure=procedure, number=99, bidder=offer.bidder,
                                created_by=operator_user)


def test_the_same_file_twice_in_an_offer_is_refused_by_the_database(offer, operator_user):
    """REQ-037: la huella es única dentro de la oferta."""
    document = offer.documents.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        om.Document.objects.create(
            offer=offer, title="otra", file_name="otra.pdf", file_format="pdf", file_size=1,
            file_sha256=document.file_sha256, loaded_by=operator_user)


def test_a_passage_has_its_words_computed_by_the_database(offer):
    """REQ-039: `tsv` lo calcula la base con la normalización de la 001 (sin tildes)."""
    passage = offer.documents.get(file_name="oferta.pdf").readings.get().passages.first()
    with connection.cursor() as cursor:
        cursor.execute("SELECT tsv @@ search_query('habilitado juramento') "
                       "FROM offers_passage WHERE id = %s", [passage.pk])
        assert cursor.fetchone()[0] is True


@pytest.mark.parametrize("table", ["offers_reading", "offers_passage"])
def test_readings_and_passages_are_insert_only(offer, table):
    """REQ-038: una lectura y sus pasajes no se modifican ni se borran."""
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {table} SET id = id")
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table}")


def test_a_model_request_is_insert_only(sheet, entry):
    """REQ-039 (P6): el pedido al modelo no se modifica ni se borra."""
    step = om.SheetStep.objects.create(sheet=sheet, entry=entry, candidates={})
    step.raw_output = "otra cosa"
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        step.save()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        step.delete()
    assert om.SheetStep.objects.get(pk=step.pk).raw_output == ""


def test_a_change_is_insert_only(sheet, entry, operator_user):
    """REQ-042 (P6): el historial de la ficha no se modifica ni se borra."""
    from evaluon.audit import services as audit
    from evaluon.audit.models import Channel, Outcome

    event = audit.record(EventType.SHEET_CHANGE, outcome=Outcome.OK, channel=Channel.SCREEN,
                         user=operator_user)
    change = om.Change.objects.create(entry=entry, action="confirmar", user=operator_user,
                                      event=event)
    change.action = "quitar"
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        change.save()
    with pytest.raises(Exception, match="solo admite agregar filas"), transaction.atomic():
        change.delete()


def test_the_database_refuses_an_entry_for_the_same_requirement_twice(sheet, entry):
    with pytest.raises(IntegrityError), transaction.atomic():
        om.SheetEntry.objects.create(sheet=sheet, requirement=entry.requirement,
                                     outcome="no_encontrado")


def test_the_six_audit_event_types_of_the_feature_exist():
    """P6: los seis tipos de hecho de la 008."""
    for name in ("offer_register", "offer_load", "offer_read", "sheet_request",
                 "sheet_build", "sheet_change"):
        assert name in EventType.values
        assert len(name) <= 20


def test_a_job_of_offers_needs_its_target(procedure, operator_user):
    """ADR-0026: `target_id` sin clave foránea, pero un pedido de ofertas lo trae siempre."""
    for kind in (m.JobKind.READ_OFFER_DOCUMENT, m.JobKind.BUILD_SHEET):
        with pytest.raises(IntegrityError), transaction.atomic():
            jobs.enqueue(kind, procedure=procedure, requested_by=operator_user)
        job = jobs.enqueue(kind, procedure=procedure, requested_by=operator_user, target_id=1)
        assert job.target_id == 1


def test_the_two_job_kinds_have_a_handler():
    """ADR-0026: la cola compartida atiende los dos pedidos nuevos."""
    assert callable(jobs._handler(m.JobKind.READ_OFFER_DOCUMENT))
    assert callable(jobs._handler(m.JobKind.BUILD_SHEET))
    assert len(m.JobKind.READ_OFFER_DOCUMENT.value) <= 20


def test_make_offer_builds_readable_passages(procedure, operator_user):
    offer = make_offer(procedure, operator_user, "Otro", {"a.pdf": ["uno", "dos"]})
    reading = offer.documents.get().readings.get()
    assert [p.text for p in reading.passages.order_by("order")] == ["uno", "dos"]
    assert all(reading.canonical_text[p.char_start:p.char_end] == p.text
               for p in reading.passages.all())
