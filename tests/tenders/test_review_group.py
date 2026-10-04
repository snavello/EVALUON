"""Revisión por grupos: confirmar o quitar de una vez las filas propuestas de una cláusula
o de un tramo (REQ-034, REQ-026, REQ-035; plan 003, "Revisión por grupos"; T-104).

Pliego y datos sintéticos (P4).
"""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import review, validation
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
    requested, job = propose(operator_user, procedure, level="alta")
    assert job.status == "done", job.error
    return requested.run.version


def segment(version, key):
    ids = [d["reading"] for d in version.run.documents]
    return m.Segment.objects.get(reading_id__in=ids, key=key)


def make_row(version, key, *, state="propuesto", start=0, length=5):
    """Un formal con una cita literal de `length` caracteres del tramo `key`."""
    seg = segment(version, key)
    number = version.requirements.order_by("-number").first().number + 1
    requirement = m.Requirement.objects.create(
        version=version, number=number, category="formal", items=[],
        origin="propuesto", state=state, proposed={}, passes=[],
        doubt_reason="duda" if state == "sugerido" else "")
    begin = seg.char_start + start
    m.RequirementQuote.objects.create(
        requirement=requirement, order=1, segment=seg, char_start=begin,
        char_end=begin + length, text=seg.reading.canonical_text[begin:begin + length],
        scope="", quote_flag="")
    return requirement


def states(rows):
    return {r.number: m.Requirement.objects.get(pk=r.pk).state for r in rows}


# --- Confirmar por grupo -------------------------------------------------------------------------


def test_confirming_a_group_confirms_each_proposed_row_like_an_individual_confirmation(
        evaluator_user, case):
    """REQ-034/026: cinco filas propuestas de una cláusula quedan `confirmado`, cada una con
    su fila de historial (quién y cuándo) igual a la de una confirmación individual."""
    rows = [make_row(case, "sec-i/3.1", start=i * 6) for i in range(5)]
    single = make_row(case, "sec-i/4.1")
    review.confirm(evaluator_user, [single.pk])
    individual = single.changes.get()

    done = review.confirm_group(evaluator_user, case.pk, "sec-i/3.1")

    assert set(states(rows).values()) == {"confirmado"}
    assert len(done.changes) == 5 and len(done.events) == 5
    for row in rows:
        change = row.changes.get()
        assert change.action == "confirmar" and change.user == evaluator_user
        assert (change.before, change.after) == (individual.before, individual.after)
        assert change.event.detail["via_grupo"] == "sec-i/3.1"
        assert change.event.event_type == EventType.REQUIREMENT_CHANGE
    assert "via_grupo" not in individual.event.detail


def test_a_group_key_continues_only_with_a_level_separator(evaluator_user, case):
    """REQ-034: `sec-i/1` no alcanza a `sec-i/11`; `sec-i/11.3/v-1` es del grupo
    `sec-i/11.3` y de `sec-i/11`."""
    assert review.in_group("sec-i/11.3/v-1", "sec-i/11.3")
    assert review.in_group("sec-i/11.3/v-1", "sec-i/11")
    assert review.in_group("sec-i/11.3", "sec-i/11.3")
    assert review.in_group("sec-i/11#2", "sec-i/11")
    assert not review.in_group("sec-i/11", "sec-i/1")
    assert not review.in_group("sec-i/11.3", "sec-i/1")
    assert not review.in_group("sec-ii/1.1", "sec-i")

    clause = make_row(case, "sec-i/1.1")
    other = make_row(case, "sec-i/2.1")
    review.confirm_group(evaluator_user, case.pk, "sec-i/1")
    assert states([clause, other]) == {clause.number: "confirmado",
                                       other.number: "propuesto"}


def test_a_group_does_not_touch_confirmed_removed_or_suggested_rows(
        evaluator_user, operator_user, case):
    """REQ-034/035: solo las `propuesto`; una confirmada, una quitada y una sugerida no se
    tocan (las sugerencias se deciden aparte)."""
    proposed = make_row(case, "sec-i/3.1", start=0)
    confirmed = make_row(case, "sec-i/3.1", start=6)
    review.confirm(evaluator_user, [confirmed.pk])
    removed = make_row(case, "sec-i/3.1", start=12)
    review.remove(operator_user, removed.pk)
    suggested = make_row(case, "sec-i/3.1", start=18, state="sugerido")
    others = [confirmed, removed, suggested]
    before = m.RequirementChange.objects.filter(requirement__in=others).count()

    done = review.confirm_group(evaluator_user, case.pk, "sec-i/3.1")

    assert [r.pk for r in done.requirements] == [proposed.pk]
    assert states([proposed, *others]) == {
        proposed.number: "confirmado", confirmed.number: "confirmado",
        removed.number: "quitado", suggested.number: "sugerido"}
    assert m.RequirementChange.objects.filter(
        requirement__in=others).count() == before


def test_confirming_a_suggested_row_is_rejected(evaluator_user, case):
    """REQ-035: confirmar una `sugerido` se rechaza; se decide con la sugerencia."""
    suggested = make_row(case, "sec-i/3.1", state="sugerido")

    with pytest.raises(review.ReviewRefused) as error:
        review.confirm(evaluator_user, [suggested.pk])

    assert error.value.reason == "requirement_suggested"
    assert m.Requirement.objects.get(pk=suggested.pk).state == "sugerido"
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED,
                                     detail__reason="requirement_suggested").count() == 1


def test_an_empty_group_does_nothing_and_says_so(evaluator_user, case):
    """REQ-034: un grupo sin filas propuestas no cambia nada y lo dice."""
    with pytest.raises(review.ReviewRefused) as error:
        review.confirm_group(evaluator_user, case.pk, "sec-i/9")
    assert error.value.reason == "empty_group"
    assert "no tiene filas propuestas" in str(error.value)
    assert m.RequirementChange.objects.count() == 0


def test_technical_rows_belong_to_a_group_by_their_own_segments(evaluator_user, case):
    """REQ-034: una fila técnica es del grupo si todos sus tramos propios lo son; los
    tramos comunes a todos los renglones no la sacan del grupo del renglón."""
    done = review.confirm_group(evaluator_user, case.pk, "sec-iii/2")

    assert [r.items for r in done.requirements] == [[2]]
    technical = m.Requirement.objects.filter(version=case, category="tecnico")
    assert {r.items[0]: r.state for r in technical} == {
        1: "propuesto", 2: "confirmado", 3: "propuesto"}


# --- Roles y versión -----------------------------------------------------------------------------


def test_the_operator_can_remove_a_group_but_cannot_confirm_it(operator_user, case):
    """REQ-034/026: quitar por grupo lo hace un operador; confirmar por grupo se rechaza."""
    rows = [make_row(case, "sec-i/3.1", start=i * 6) for i in range(3)]

    with pytest.raises(RoleRejected):
        review.confirm_group(operator_user, case.pk, "sec-i/3.1")
    assert set(states(rows).values()) == {"propuesto"}
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).exists()

    done = review.remove_group(operator_user, case.pk, "sec-i/3.1")

    assert set(states(rows).values()) == {"quitado"}
    assert len(done.changes) == 3
    for row in rows:
        change = row.changes.get()
        assert change.action == "quitar" and change.user == operator_user
        assert change.after == {"state": "quitado"}
        assert change.event.detail["via_grupo"] == "sec-i/3.1"


def test_a_group_in_a_version_that_is_not_a_draft_is_rejected(evaluator_user, case):
    """REQ-027: en una versión que no es borrador no se actúa; queda el hecho `rejected`."""
    make_row(case, "sec-i/3.1")
    validation.discard(evaluator_user, case.pk)

    with pytest.raises(review.ReviewRefused) as error:
        review.confirm_group(evaluator_user, case.pk, "sec-i/3.1")

    assert error.value.reason == "version_not_draft"
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED,
                                     detail__reason="version_not_draft").count() == 1


def test_a_group_is_all_or_nothing(evaluator_user, case, monkeypatch):
    """REQ-034: una sola transacción: si una fila falla, ninguna queda confirmada."""
    rows = [make_row(case, "sec-i/3.1", start=i * 6) for i in range(3)]
    original = review._record
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        if len(calls) == 3:
            raise review.ReviewRefused("falla de prueba", "boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(review, "_record", failing)
    with pytest.raises(review.ReviewRefused):
        review.confirm_group(evaluator_user, case.pk, "sec-i/3.1")
    monkeypatch.undo()

    assert set(states(rows).values()) == {"propuesto"}
    assert not m.RequirementChange.objects.filter(requirement__in=rows).exists()
