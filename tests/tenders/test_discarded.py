"""Listar y devolver las filas descartadas por el sistema (REQ-033, REQ-026; plan 003,
"La lista de descartadas y cómo se devuelve"; ADR-0021; T-104).

Pliego y datos sintéticos (P4). Las descartadas se insertan a mano: de producirlas se
ocupa el filtro (T-102).
"""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import discarded
from evaluon.tenders.services import validation as validation_service
from evaluon.tenders.services.review import ReviewRefused
from tests.tenders.scripted import (
    GARANTIA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)
from tests.tenders.test_validation import finish_review

pytestmark = pytest.mark.django_db


@pytest.fixture
def case(operator_user, script):
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when("Bolsa de diez kilogramos", item(technical=["2"]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return requested.run.version


def segment(version, key):
    ids = [d["reading"] for d in version.run.documents]
    return m.Segment.objects.get(reading_id__in=ids, key=key)


def add_row(version, key="sec-i/3.1", *, order=1, extra_key=None, **fields):
    """Una descartada de la propuesta de `version`, con la cita literal de un tramo."""
    seg = segment(version, key)
    step = m.RunStep.objects.create(run=version.run, pass_name="filtro", batch=order,
                                    request={"messages": []})
    extra = []
    if extra_key:
        other = segment(version, extra_key)
        extra = [{"segment": other.pk, "char_start": other.char_start,
                  "char_end": other.char_end, "text": other.text}]
    values = {
        "run": version.run, "version": version, "order": order, "segment": seg,
        "char_start": seg.char_start, "char_end": seg.char_end, "text": seg.text,
        "extra_quotes": extra, "category": "formal", "items": [],
        "reason": "consecuencia_sancion", "evidence_segment": seg,
        "evidence_start": seg.char_start, "evidence_end": seg.char_start + 10,
        "evidence_text": seg.text[:10], "vote_a": {"decision": "descartar"},
        "vote_b": {"puede_ofertar": "no"}, "step_a": step, "step_b": step,
        "source_pass": "extraccion", "passes": ["extraccion"],
    }
    values.update(fields)
    return m.DiscardedRow.objects.create(**values)


def rejected(reason):
    return AuditEvent.objects.filter(
        event_type=EventType.REQUIREMENT_CHANGE, outcome=Outcome.REJECTED,
        detail__reason=reason)


# --- Listar --------------------------------------------------------------------------------------


def test_the_list_shows_each_row_with_its_derived_state(evaluator_user, case):
    """REQ-033: la lista trae cada descartada y su estado, derivado de si hay un
    requisito devuelto en la versión."""
    first = add_row(case, "sec-i/3.1", order=1)
    second = add_row(case, "sec-i/4.1", order=2)

    before = discarded.list_discarded(case)
    assert [(v.row.pk, v.state, v.requirement) for v in before] == [
        (first.pk, "descartada", None), (second.pk, "descartada", None)]

    done = discarded.restore(evaluator_user, case.pk, [first.pk])

    after = discarded.list_discarded(case)
    assert [(v.row.pk, v.state) for v in after] == [
        (first.pk, "devuelta"), (second.pk, "descartada")]
    assert after[0].requirement == done.requirements[0]


# --- Devolver ------------------------------------------------------------------------------------


def test_restoring_creates_the_requirement_with_literal_quotes_and_the_record(
        evaluator_user, case):
    """REQ-033/026: devolver crea el requisito propuesto con las citas literales de la
    descartada (la principal y las repetidas), `devuelto`, `restored_from`, y deja la fila
    `devolver` con el motivo y el indicio, y el hecho `requirement_change`."""
    row = add_row(case, "sec-i/3.1", extra_key="sec-i/4.1", category="economico",
                  items=[1, 2])

    done = discarded.restore(evaluator_user, case.pk, [row.pk])

    requirement = done.requirements[0]
    requirement.refresh_from_db()
    assert requirement.version == case
    assert requirement.origin == "devuelto" and requirement.state == "propuesto"
    assert requirement.restored_from == row
    assert requirement.category == "economico" and requirement.items == [1, 2]
    assert requirement.number == case.requirements.order_by("-number").first().number
    quotes = list(requirement.quotes.order_by("order"))
    assert [(q.scope, q.text) for q in quotes] == [
        ("", row.text), ("repetida", row.extra_quotes[0]["text"])]
    canonical = quotes[0].segment.reading.canonical_text
    assert canonical[quotes[0].char_start:quotes[0].char_end] == quotes[0].text
    assert requirement.proposed["category"] == "economico"
    assert requirement.proposed["quotes"][0]["text"] == row.text

    change = requirement.changes.get()
    assert change.action == "devolver" and change.user == evaluator_user
    assert change.before["reason"] == "consecuencia_sancion"
    assert change.before["evidence"]["text"] == row.evidence_text
    assert change.after["state"] == "propuesto"
    event = change.event
    assert event.event_type == EventType.REQUIREMENT_CHANGE and event.outcome == Outcome.OK
    assert event.detail["action"] == "devolver" and event.detail["discarded"] == row.pk
    assert done.changes == [change] and done.events == [event]


def test_the_evaluator_can_restore_and_several_rows_go_together(evaluator_user, case):
    """REQ-026: devolver lo hace el operador o el evaluador; varias filas, en una vez."""
    rows = [add_row(case, "sec-i/3.1", order=1), add_row(case, "sec-i/4.1", order=2)]

    done = discarded.restore(evaluator_user, case.pk, [r.pk for r in rows])

    assert len(done.requirements) == 2
    assert [r.number for r in done.requirements] == sorted(
        r.number for r in done.requirements)
    assert m.RequirementChange.objects.filter(action="devolver").count() == 2


def test_a_second_restore_in_the_same_version_is_rejected(evaluator_user, case):
    """REQ-033: una descartada se devuelve una sola vez por versión."""
    row = add_row(case)
    discarded.restore(evaluator_user, case.pk, [row.pk])
    total = m.Requirement.objects.count()

    with pytest.raises(ReviewRefused) as error:
        discarded.restore(evaluator_user, case.pk, [row.pk])

    assert error.value.reason == "already_restored"
    assert m.Requirement.objects.count() == total
    assert rejected("already_restored").count() == 1


def test_a_refused_row_leaves_the_others_unrestored(evaluator_user, case):
    """Todo o nada: si una fila no se puede devolver, ninguna se devuelve."""
    row = add_row(case)
    discarded.restore(evaluator_user, case.pk, [row.pk])
    other = add_row(case, "sec-i/4.1", order=2)
    total = m.Requirement.objects.count()

    with pytest.raises(ReviewRefused):
        discarded.restore(evaluator_user, case.pk, [other.pk, row.pk])

    assert m.Requirement.objects.count() == total
    assert not other.restored_requirements.exists()


def test_an_unknown_row_or_an_empty_selection_is_rejected(evaluator_user, case):
    """Solo se devuelven las descartadas de la versión (o de su cadena) y al menos una."""
    with pytest.raises(ReviewRefused) as error:
        discarded.restore(evaluator_user, case.pk, [999999])
    assert error.value.reason == "discarded_not_found"
    with pytest.raises(ReviewRefused) as error:
        discarded.restore(evaluator_user, case.pk, [])
    assert error.value.reason == "nothing_selected"


def test_a_user_without_commission_role_cannot_restore(no_commission_user, case):
    """REQ-026: sin rol de la Comisión se rechaza y no se crea nada."""
    row = add_row(case)
    with pytest.raises(RoleRejected):
        discarded.restore(no_commission_user, case.pk, [row.pk])
    assert not row.restored_requirements.exists()


# --- Versión validada y versión nueva ------------------------------------------------------------


def validated(evaluator_user, version):
    finish_review(evaluator_user, version)
    return validation_service.validate(evaluator_user, version.pk)


def test_restoring_in_a_validated_version_is_rejected_but_the_list_can_be_seen(
        evaluator_user, case):
    """REQ-033: en una versión validada devolver se rechaza; la lista se puede ver."""
    row = add_row(case)
    version = validated(evaluator_user, case)

    with pytest.raises(ReviewRefused) as error:
        discarded.restore(evaluator_user, version.pk, [row.pk])

    assert error.value.reason == "version_not_draft"
    assert rejected("version_not_draft").count() == 1
    assert [(v.row.pk, v.state) for v in discarded.list_discarded(version)] == [
        (row.pk, "descartada")]


def test_a_new_version_copies_what_was_restored_and_shows_the_chain(
        evaluator_user, case):
    """REQ-033: la versión nueva copia lo devuelto con su `restored_from`, muestra las
    descartadas de la cadena y no deja devolver otra vez la ya devuelta."""
    returned = add_row(case, "sec-i/3.1", order=1)
    pending = add_row(case, "sec-i/4.1", order=2)
    discarded.restore(evaluator_user, case.pk, [returned.pk])
    version = validated(evaluator_user, case)

    new = validation_service.open_new_version(evaluator_user, version.procedure_id)

    copy = new.requirements.get(restored_from=returned)
    assert copy.origin == "devuelto" and copy.previous.version == version
    assert [(v.row.pk, v.state) for v in discarded.list_discarded(new)] == [
        (returned.pk, "devuelta"), (pending.pk, "descartada")]
    with pytest.raises(ReviewRefused) as error:
        discarded.restore(evaluator_user, new.pk, [returned.pk])
    assert error.value.reason == "already_restored"
    done = discarded.restore(evaluator_user, new.pk, [pending.pk])
    assert done.requirements[0].restored_from == pending


def test_the_validation_fact_counts_discarded_and_restored_rows(
        evaluator_user, case):
    """REQ-033: el hecho `matrix_validation` suma las descartadas totales y las devueltas."""
    first = add_row(case, "sec-i/3.1", order=1)
    add_row(case, "sec-i/4.1", order=2)
    add_row(case, "sec-ii/1.1", order=3)
    discarded.restore(evaluator_user, case.pk, [first.pk])

    validated(evaluator_user, case)

    fact = AuditEvent.objects.get(event_type=EventType.MATRIX_VALIDATION,
                                  outcome=Outcome.OK)
    assert fact.detail["discarded"] == 3 and fact.detail["restored"] == 1
