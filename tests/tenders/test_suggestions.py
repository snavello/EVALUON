"""Decidir las sugerencias: pasar a requisito o quitar, una por una o por grupo, y la
validación que no admite sugerencias sin decidir (REQ-035, REQ-034, REQ-026; plan 003,
"Qué hace la Comisión con una sugerencia"; ADR-0022; T-110).

Pliego y datos sintéticos (P4).
"""

import pytest
from django.db import DatabaseError, transaction

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import consequences, review, suggestions
from evaluon.tenders.services import validation as validation
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


def make_suggestion(version, key, *, state="sugerido", start=0, length=5,
                    reason="no_coinciden"):
    """Una fila `sugerido` (formal) con una cita literal del tramo `key`."""
    seg = segment(version, key)
    number = version.requirements.order_by("-number").first().number + 1
    requirement = m.Requirement.objects.create(
        version=version, number=number, category="formal", items=[], origin="propuesto",
        state=state, proposed={}, passes=[], doubt_reason=reason,
        doubt={"answers": ["a", "b"], "evidence": "indicio"})
    begin = seg.char_start + start
    m.RequirementQuote.objects.create(
        requirement=requirement, order=1, segment=seg, char_start=begin,
        char_end=begin + length, text=seg.reading.canonical_text[begin:begin + length],
        scope="", quote_flag="")
    return requirement


@pytest.fixture
def norm_unit(make_norm, make_document, make_reading):
    reading = make_reading(
        make_document(make_norm()), [("art-1", "Artículo 1. Texto sintético de la norma.")]
    )
    return reading.units_by_key["art-1"]


def add_support(requirement, unit, step_run):
    step = m.RunStep.objects.create(run=step_run, pass_name="filtro", batch=1,
                                    request={"messages": []})
    return m.NormSupport.objects.create(
        requirement=requirement, unit=unit, unit_label="Norma sintética, art. 1",
        char_start=0, char_end=10, text="Artículo 1.", score=0.5,
        regime="Régimen sintético", corpus_version=1, step=step)


def state_of(requirement):
    return m.Requirement.objects.get(pk=requirement.pk).state


def refused(reason, event_type=EventType.REQUIREMENT_CHANGE):
    return AuditEvent.objects.filter(event_type=event_type, outcome=Outcome.REJECTED,
                                     detail__reason=reason)


# --- Pasar a requisito ---------------------------------------------------------------------------


def test_accepting_a_suggestion_leaves_it_proposed_with_who_when_reason_and_support(
        operator_user, case, norm_unit):
    """REQ-035/026: pasa de `sugerido` a `propuesto`; la fila de historial dice quién,
    cuándo, el motivo de la duda y el respaldo como estaban; hay hecho de auditoría."""
    row = make_suggestion(case, "sec-i/3.1")
    add_support(row, norm_unit, case.run)

    done = suggestions.accept_suggestion(operator_user, row.pk)

    assert state_of(row) == "propuesto"
    change = row.changes.get()
    assert done.changes == [change] and len(done.events) == 1
    assert change.action == "aceptar_sugerencia" and change.user == operator_user
    assert change.at is not None and change.event == done.events[0]
    assert change.before["state"] == "sugerido"
    assert change.before["doubt_reason"] == "no_coinciden"
    assert change.before["norm_support"][0]["unit_label"] == "Norma sintética, art. 1"
    assert change.before["norm_support"][0]["text"] == "Artículo 1."
    assert change.after["state"] == "propuesto"
    assert done.events[0].event_type == EventType.REQUIREMENT_CHANGE
    assert done.events[0].detail["action"] == "aceptar_sugerencia"
    # El motivo y el respaldo se conservan en el requisito.
    row.refresh_from_db()
    assert row.doubt_reason == "no_coinciden" and row.norm_supports.count() == 1


def test_an_evaluator_can_accept_and_remove_too(evaluator_user, operator_user, case):
    """REQ-035: el operador y el evaluador deciden."""
    first = make_suggestion(case, "sec-i/3.1")
    second = make_suggestion(case, "sec-i/4.1")

    suggestions.accept_suggestion(evaluator_user, first.pk)
    review.remove(operator_user, second.pk)

    assert state_of(first) == "propuesto" and state_of(second) == "quitado"


def test_a_user_without_a_commission_role_cannot_decide(no_commission_user, case):
    """REQ-035 (P6): sin rol de la Comisión se rechaza y queda el hecho `rejected`."""
    row = make_suggestion(case, "sec-i/3.1")
    before = AuditEvent.objects.filter(outcome=Outcome.REJECTED).count()

    with pytest.raises(RoleRejected):
        suggestions.accept_suggestion(no_commission_user, row.pk)
    with pytest.raises(RoleRejected):
        suggestions.accept_suggestions_group(no_commission_user, case.pk, "sec-i/3.1")
    with pytest.raises(RoleRejected):
        suggestions.remove_suggestions_group(no_commission_user, case.pk, "sec-i/3.1")

    assert state_of(row) == "sugerido"
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() == before + 3


def test_only_a_suggestion_can_be_accepted(operator_user, case):
    """REQ-035: una fila que no es `sugerido` no se pasa a requisito."""
    row = make_suggestion(case, "sec-i/3.1", state="propuesto")

    with pytest.raises(review.ReviewRefused) as error:
        suggestions.accept_suggestion(operator_user, row.pk)

    assert error.value.reason == "not_a_suggestion"
    assert refused("not_a_suggestion").count() == 1
    assert not row.changes.exists()


# --- Por grupo -----------------------------------------------------------------------------------


def test_accepting_a_group_equals_five_individual_decisions(operator_user, case):
    """REQ-034/035: cinco sugerencias de una cláusula pasan a requisito con cinco filas de
    historial iguales a las de la decisión individual; `sec-i/1` no alcanza a `sec-i/11`;
    las filas ya decididas no se tocan."""
    rows = [make_suggestion(case, "sec-i/3.1", start=i * 6) for i in range(5)]
    other = make_suggestion(case, "sec-i/4.1")
    removed = make_suggestion(case, "sec-i/3.1", start=40)
    review.remove(operator_user, removed.pk)
    proposed = make_suggestion(case, "sec-i/3.1", state="propuesto", start=50)
    single = make_suggestion(case, "sec-i/4.1", start=20)
    suggestions.accept_suggestion(operator_user, single.pk)
    individual = single.changes.get()

    done = suggestions.accept_suggestions_group(operator_user, case.pk, "sec-i/3")

    assert {state_of(r) for r in rows} == {"propuesto"}
    assert len(done.changes) == 5 and len(done.events) == 5
    assert state_of(other) == "sugerido"          # otra cláusula
    assert state_of(removed) == "quitado"         # ya decidida
    assert state_of(proposed) == "propuesto" and not proposed.changes.exists()
    for row in rows:
        change = row.changes.get()
        assert change.action == individual.action == "aceptar_sugerencia"
        assert change.user == operator_user
        assert change.before == individual.before and change.after == individual.after
        assert change.event.detail["via_grupo"] == "sec-i/3"
    assert "via_grupo" not in individual.event.detail


def test_a_group_key_does_not_reach_a_longer_key(operator_user, case):
    """REQ-034: `sec-i/3` no alcanza a una sugerencia de `sec-i/30.1`; `sec-i/4` sí a
    `sec-i/4.1`."""
    assert not review.in_group("sec-i/30.1", "sec-i/3")
    near = make_suggestion(case, "sec-i/3.1")
    far = make_suggestion(case, "sec-i/4.1")

    suggestions.accept_suggestions_group(operator_user, case.pk, "sec-i/3")

    assert state_of(near) == "propuesto" and state_of(far) == "sugerido"


def test_a_group_without_suggestions_is_refused_and_nothing_changes(operator_user, case):
    """REQ-035: un grupo sin sugerencias no hace nada y deja el hecho `rejected`."""
    make_suggestion(case, "sec-i/3.1", state="propuesto")

    with pytest.raises(review.ReviewRefused) as error:
        suggestions.accept_suggestions_group(operator_user, case.pk, "sec-i/3.1")

    assert error.value.reason == "empty_group"
    assert refused("empty_group").count() == 1


def test_removing_a_group_of_suggestions_removes_only_the_suggested(
        operator_user, case):
    """REQ-034/035: quitar un grupo de sugerencias deja `quitado` solo las `sugerido`,
    cada una con su historial `quitar` y `via_grupo`."""
    rows = [make_suggestion(case, "sec-i/3.1", start=i * 6) for i in range(3)]
    proposed = make_suggestion(case, "sec-i/3.1", state="propuesto", start=30)

    done = suggestions.remove_suggestions_group(operator_user, case.pk, "sec-i/3.1")

    assert {state_of(r) for r in rows} == {"quitado"}
    assert state_of(proposed) == "propuesto"
    assert len(done.changes) == 3
    assert {c.action for c in done.changes} == {"quitar"}
    assert all(e.detail["via_grupo"] == "sec-i/3.1" for e in done.events)


def test_the_group_of_proposed_rows_still_ignores_suggestions(operator_user, case):
    """REQ-034: quitar un grupo sin pedir sugerencias sigue quitando solo propuestas."""
    suggested = make_suggestion(case, "sec-i/3.1")
    proposed = make_suggestion(case, "sec-i/3.1", state="propuesto", start=10)

    review.remove_group(operator_user, case.pk, "sec-i/3.1")

    assert state_of(suggested) == "sugerido" and state_of(proposed) == "quitado"


# --- Quitar y restituir --------------------------------------------------------------------------


def test_removing_a_suggestion_and_restoring_it_leaves_it_proposed(operator_user, case):
    """REQ-035: quitar una sugerencia la deja `quitado`; restituirla la deja `propuesto`
    (la persona la quiere como requisito)."""
    row = make_suggestion(case, "sec-i/3.1")

    review.remove(operator_user, row.pk)
    assert state_of(row) == "quitado"
    review.restore(operator_user, row.pk)

    assert state_of(row) == "propuesto"
    assert [c.action for c in row.changes.order_by("id")] == ["quitar", "restituir"]


def test_confirming_a_suggestion_is_refused_even_for_an_evaluator(evaluator_user, case):
    """REQ-035: confirmar una sugerencia sin pasarla antes a requisito se rechaza."""
    row = make_suggestion(case, "sec-i/3.1")

    with pytest.raises(review.ReviewRefused) as error:
        review.confirm(evaluator_user, [row.pk])

    assert error.value.reason == "requirement_suggested"
    assert "primero a requisito" in str(error.value)
    assert state_of(row) == "sugerido"


def test_in_a_validated_version_nothing_about_suggestions_can_be_done(
        operator_user, evaluator_user, case):
    """REQ-035/027: en una versión validada las funciones rechazan, y la base también."""
    row = make_suggestion(case, "sec-i/3.1")
    other = make_suggestion(case, "sec-i/4.1")
    suggestions.accept_suggestion(operator_user, row.pk)
    suggestions.accept_suggestion(operator_user, other.pk)
    finish(evaluator_user, case)
    validation.validate(evaluator_user, case.pk)

    for call in (lambda: suggestions.accept_suggestion(operator_user, row.pk),
                 lambda: suggestions.accept_suggestions_group(
                     operator_user, case.pk, "sec-i/3.1"),
                 lambda: suggestions.remove_suggestions_group(
                     operator_user, case.pk, "sec-i/3.1")):
        with pytest.raises(review.ReviewRefused) as error:
            call()
        assert error.value.reason == "version_not_draft"
    assert state_of(row) == "confirmado"
    with pytest.raises(DatabaseError), transaction.atomic():
        m.Requirement.objects.filter(pk=row.pk).update(state="sugerido")


# --- Validar -------------------------------------------------------------------------------------


def finish(evaluator, version):
    for pending in version.pending_items.filter(resolved_at__isnull=True):
        review.resolve_pending(evaluator, pending.pk)
    for requirement in version.requirements.exclude(state__in=("quitado", "sugerido")):
        consequences.choose(evaluator, requirement.pk, consequence_type="aprobar_igual",
                            note="Motivo de prueba")


def test_validating_with_one_undecided_suggestion_is_refused_saying_how_many_and_where(
        evaluator_user, case):
    """REQ-035: una sola sugerencia sin decidir bloquea la validación; el mensaje dice
    cuántas quedan y en qué grupos; la versión sigue en borrador."""
    make_suggestion(case, "sec-i/3.1")
    make_suggestion(case, "sec-i/3.1", start=8)
    make_suggestion(case, "sec-i/4.1")
    finish(evaluator_user, case)

    with pytest.raises(validation.ValidationRefused) as error:
        validation.validate(evaluator_user, case.pk)

    assert error.value.reason == "suggestions_undecided"
    assert "3" in str(error.value)
    assert "sec-i/3.1" in str(error.value) and "sec-i/4.1" in str(error.value)
    case.refresh_from_db()
    assert case.status == "draft"
    assert refused("suggestions_undecided", EventType.MATRIX_VALIDATION).count() == 1


def test_validating_with_every_suggestion_decided_works_and_counts_them(
        operator_user, evaluator_user, case):
    """REQ-035: con todas decididas se valida; el hecho `matrix_validation` suma las
    aceptadas y las quitadas."""
    accepted = [make_suggestion(case, "sec-i/3.1", start=i * 6) for i in range(2)]
    removed = make_suggestion(case, "sec-i/4.1")
    for row in accepted:
        suggestions.accept_suggestion(operator_user, row.pk)
    review.remove(operator_user, removed.pk)
    finish(evaluator_user, case)

    version = validation.validate(evaluator_user, case.pk)

    assert version.status == "validated"
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VALIDATION,
                                   outcome=Outcome.OK)
    assert event.detail["suggestions_accepted"] == 2
    assert event.detail["suggestions_removed"] == 1


def test_a_validation_without_suggestions_counts_zero(evaluator_user, case):
    """REQ-035: sin sugerencias las cuentas son cero y todo sigue igual."""
    finish(evaluator_user, case)

    validation.validate(evaluator_user, case.pk)

    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VALIDATION,
                                   outcome=Outcome.OK)
    assert event.detail["suggestions_accepted"] == 0
    assert event.detail["suggestions_removed"] == 0


def test_discarding_a_draft_with_undecided_suggestions_is_allowed(evaluator_user, case):
    """REQ-035: descartar un borrador con sugerencias sin decidir se permite."""
    make_suggestion(case, "sec-i/3.1")

    version = validation.discard(evaluator_user, case.pk)

    assert version.status == "discarded"


# --- Versión nueva -------------------------------------------------------------------------------


def test_the_new_version_copies_the_suggestion_origin_reason_support_and_process(
        operator_user, evaluator_user, case, norm_unit):
    """REQ-035/036/027: la versión nueva copia el requisito venido de una sugerencia con su
    motivo, su duda y su respaldo; también `doubt_reason`, `doubt` y `restored_from` de
    cualquier fila, y el proceso de la versión (aviso de T-104 y T-100)."""
    row = make_suggestion(case, "sec-i/3.1")
    add_support(row, norm_unit, case.run)
    suggestions.accept_suggestion(operator_user, row.pk)
    restored = m.DiscardedRow.objects.create(
        run=case.run, version=case, order=1, segment=row.quotes.get().segment,
        char_start=0, char_end=3, text="abc", category="formal", items=[],
        reason="titulo", evidence_segment=row.quotes.get().segment, evidence_start=0,
        evidence_end=3, evidence_text="abc", vote_a={}, vote_b={},
        step_a=row.norm_supports.get().step, step_b=row.norm_supports.get().step,
        source_pass="extraccion")
    m.Requirement.objects.filter(pk=row.pk).update(restored_from=restored)
    case.process = "completo"
    case.save(update_fields=["process"])
    finish(evaluator_user, case)
    validated = validation.validate(evaluator_user, case.pk)
    assert validated.process == "completo"

    new = validation.open_new_version(operator_user, validated.procedure_id)

    copy = new.requirements.get(number=row.number)
    assert copy.state == "confirmado"
    assert copy.doubt_reason == "no_coinciden"
    assert copy.doubt == {"answers": ["a", "b"], "evidence": "indicio"}
    assert copy.restored_from_id == restored.pk
    support = copy.norm_supports.get()
    assert (support.unit_id, support.unit_label, support.text, support.score,
            support.regime, support.corpus_version, support.char_start,
            support.char_end, support.step_id) == (
        norm_unit.pk, "Norma sintética, art. 1", "Artículo 1.", 0.5,
        "Régimen sintético", 1, 0, 10, row.norm_supports.get().step_id)
    assert new.process == "completo"
    assert row.norm_supports.count() == 1  # el de la versión de origen no cambia
