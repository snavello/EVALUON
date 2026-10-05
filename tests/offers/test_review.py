"""Corregir la ficha (REQ-042, REQ-043; plan 008, "Revisión (REQ-042)" y "Roles"; T-132).
El caso es el chico, inventado; el modelo es un guion."""

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import review, sheets
from evaluon.tenders import models as m
from tests.offers.conftest import make_offer, pick

pytestmark = pytest.mark.django_db

JURADA = "Declaro bajo juramento"


@pytest.fixture
def sheet(offer, operator_user, script):
    script.choose(pick(JURADA, when="declaración jurada"))
    return sheets.build_sheet(offer, operator_user)


def found_entry(sheet):
    return sheet.entries.filter(outcome="encontrado").first()


def missing_entry(sheet):
    return sheet.entries.filter(outcome="no_encontrado").first()


def test_correcting_keeps_the_previous_fragment_with_author_and_date(
        sheet, offer, operator_user, evaluator_user):
    """REQ-042: el cambio queda con su autor y su fecha y el fragmento anterior sigue
    visible en el historial."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    original = fragment.text
    other = om.Passage.objects.get(text__startswith="Constancia de inscripción")
    review.correct(evaluator_user, fragment.pk, passage_id=other.pk)
    fragment.refresh_from_db()
    assert fragment.text == other.text and fragment.state == "propuesto"
    assert fragment.proposed["text"] == original  # lo propuesto no cambia
    change = entry.changes.get()
    assert (change.action, change.user, change.fragment) == ("corregir", evaluator_user,
                                                             fragment)
    assert change.before["text"] == original and change.after["text"] == other.text
    assert change.at is not None
    page = review.history(operator_user, entry.pk)
    assert [c.before["text"] for c in page.changes] == [original]
    event = AuditEvent.objects.get(event_type=EventType.SHEET_CHANGE)
    assert change.event == event and event.user == evaluator_user
    assert event.detail["before"]["text"] == original and event.detail["entry"] == entry.pk


def test_a_cut_must_be_literal_text_of_the_passage(sheet, operator_user):
    """REQ-042, P3: el recorte se comprueba contra el texto canónico; lo guardado es el del
    texto canónico y uno que no está en el pasaje se rechaza."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    review.correct(operator_user, fragment.pk, text="  habilitado   para\ncontratar ")
    fragment.refresh_from_db()
    canonical = fragment.passage.reading.canonical_text
    assert fragment.text == "habilitado para contratar" == canonical[
        fragment.char_start:fragment.char_end]
    before = om.Change.objects.count()
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, fragment.pk, text="habilitado para licitar")
    assert error.value.reason == "quote_not_in_passage"
    assert om.Change.objects.count() == before
    rejected = AuditEvent.objects.get(event_type=EventType.SHEET_CHANGE,
                                      outcome=Outcome.REJECTED)
    assert rejected.detail["reason"] == "quote_not_in_passage"
    fragment.refresh_from_db()
    assert fragment.text == "habilitado para contratar"


def test_a_passage_of_another_offer_is_refused(sheet, procedure, operator_user, fake_ai):
    """REQ-042: solo se eligen pasajes de las lecturas con que se armó la ficha."""
    foreign = make_offer(procedure, operator_user, "Otro oferente",
                         {"x.pdf": ["Texto ajeno."]})
    passage = om.Passage.objects.get(reading__document__offer=foreign)
    with pytest.raises(review.ReviewRefused) as error:
        review.add(operator_user, found_entry(sheet).pk, passage_id=passage.pk)
    assert error.value.reason == "passage_not_in_offer"


def test_only_the_evaluator_confirms(sheet, operator_user, evaluator_user,
                                     no_commission_user):
    """REQ-042: el operador no confirma; el evaluador sí, y la fila y sus fragmentos quedan
    confirmados."""
    entry = found_entry(sheet)
    with pytest.raises(RoleRejected):
        review.confirm(operator_user, [entry.pk])
    with pytest.raises(RoleRejected):
        review.confirm(no_commission_user, [entry.pk])
    entry.refresh_from_db()
    assert entry.state == "propuesto"
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 2
    done = review.confirm(evaluator_user, [entry.pk, missing_entry(sheet).pk])
    entry.refresh_from_db()
    assert entry.state == "confirmado" and entry.fragments.get().state == "confirmado"
    assert len(done.changes) == 2 and all(c.user == evaluator_user for c in done.changes)
    assert AuditEvent.objects.filter(event_type=EventType.SHEET_CHANGE).count() == 2
    assert review.confirm(evaluator_user, [entry.pk]).changes == []  # ya confirmada


def test_a_change_to_a_confirmed_row_makes_it_proposed_again(sheet, operator_user,
                                                             evaluator_user):
    """REQ-042: la confirmación valía para lo de antes."""
    entry = found_entry(sheet)
    review.confirm(evaluator_user, [entry.pk])
    review.add(operator_user, entry.pk, passage_id=om.Passage.objects.first().pk)
    entry.refresh_from_db()
    assert entry.state == "propuesto"


def test_remove_and_restore_keep_the_fragment_visible_in_the_history(sheet, operator_user):
    """REQ-042: quitar deja la fila "no se encontró"; restituir la devuelve; todo queda en el
    historial."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    review.remove(operator_user, fragment.pk)
    entry.refresh_from_db()
    assert entry.outcome == "no_encontrado"
    page = review.history(operator_user, entry.pk)
    assert page.removed == [fragment] and page.current == []
    with pytest.raises(review.ReviewRefused):
        review.remove(operator_user, fragment.pk)
    with pytest.raises(review.ReviewRefused):
        review.correct(operator_user, fragment.pk, text="x")
    review.restore(operator_user, fragment.pk)
    entry.refresh_from_db()
    assert entry.outcome == "encontrado"
    assert [c.action for c in entry.changes.order_by("id")] == ["quitar", "restituir"]
    with pytest.raises(review.ReviewRefused):
        review.restore(operator_user, fragment.pk)


def test_adding_a_fragment_to_a_not_found_row(sheet, operator_user):
    """REQ-042: agregar a una fila sin respuesta la pasa a "encontrado", con origen
    persona y el recorte literal."""
    entry = missing_entry(sheet)
    passage = om.Passage.objects.get(text__startswith="Constancia de inscripción")
    review.add(operator_user, entry.pk, passage_id=passage.pk,
               text="registro de proveedores")
    entry.refresh_from_db()
    fragment = entry.fragments.get()
    assert entry.outcome == "encontrado" and fragment.origin == "persona"
    assert fragment.text == "registro de proveedores" == passage.reading.canonical_text[
        fragment.char_start:fragment.char_end]
    assert fragment.proposed == {}
    assert entry.changes.get().action == "agregar" and entry.changes.get().before is None


def test_history_is_append_only(sheet, operator_user):
    """REQ-042, P6: el historial no se modifica ni se borra."""
    review.remove(operator_user, found_entry(sheet).fragments.get().pk)
    with pytest.raises(DatabaseError), transaction.atomic():
        om.Change.objects.update(action="confirmar")


def test_matrix_version_of_the_sheet_is_kept_when_a_new_one_is_validated(
        sheet, matrix, operator_user):
    """REQ-043: la ficha guarda la versión con que se armó, aunque haya una vigente nueva."""
    second = m.MatrixVersion.objects.create(procedure=matrix.procedure, number=2,
                                            created_by=operator_user)
    second.status = m.VersionStatus.VALIDATED
    second.validated_at, second.validated_by = timezone.now(), operator_user
    second.save()
    page = sheets.sheet_page(operator_user, sheet.pk)
    assert page.sheet.matrix_version.number == 1 and page.newer_version.number == 2
