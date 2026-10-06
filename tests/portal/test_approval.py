"""Aprobar o rechazar lo propuesto y cargarlo (REQ-048, REQ-049; T-141; plan 012, "Flujo, paso 4")."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    PortalItem,
    PortalLine,
    PortalProcedureData,
)
from evaluon.portal.services import approval
from evaluon.tenders.models import Procedure
from tests.portal.fakeportal import (  # noqa: F401
    EXPECTED,
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db

DATE = date(2025, 11, 14)


@pytest.fixture
def proposed(operator_user, explore_link):
    link, _ = explore_link(operator_user)
    return (link, PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO),
            PortalItem.objects.get(kind=ItemKind.RENGLONES))


def confirm(item, when=DATE):
    return {item.pk: {"authorization_date": when}}


def decisions():
    return AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION)


def test_approved_procedure_is_loaded_with_register_procedure(evaluator_user, proposed):
    """REQ-048, REQ-049: aprobar crea el procedimiento por register_procedure y guarda lo
    que esa tabla no tiene, con el ítem de origen."""
    link, procedure_item, _ = proposed
    (result,) = approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                                confirmations=confirm(procedure_item))
    assert result.result == approval.LOADED, result.reason
    want = EXPECTED["procedimiento"]
    procedure = Procedure.objects.get()
    assert (procedure.number, procedure.procedure_type) == (want["numero"], "Licitacion Pública")
    assert procedure.authorization_date == DATE
    assert procedure.created_by == evaluator_user
    data = PortalProcedureData.objects.get()
    assert data.procedure == procedure and data.item == procedure_item
    assert data.file_number and data.legal_framework and data.schedule and data.guarantees
    link.refresh_from_db()
    assert link.procedure == procedure
    procedure_item.refresh_from_db()
    assert procedure_item.state == ItemState.CARGADO
    assert (procedure_item.loaded_model, procedure_item.loaded_id) == (
        "tenders_procedure", procedure.pk)
    assert AuditEvent.objects.filter(event_type=EventType.PROCEDURE).count() == 1


def test_decision_has_author_date_and_fact(evaluator_user, proposed):
    """REQ-048, P6: cada decisión queda con autor y fecha, en el ítem y en el hecho."""
    _, procedure_item, lines_item = proposed
    before = timezone.now()
    approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                    confirmations=confirm(procedure_item))
    approval.decide(evaluator_user, [lines_item.pk], approval.REJECT)
    for item in (procedure_item, lines_item):
        item.refresh_from_db()
        assert item.decided_by == evaluator_user
        assert before <= item.decided_at <= timezone.now()
    assert decisions().count() == 2
    by_decision = {e.detail["decision"]: e for e in decisions()}
    assert by_decision["aprobar"].detail["item"] == procedure_item.pk
    assert by_decision["aprobar"].detail["loaded_id"] == Procedure.objects.get().pk
    assert by_decision["rechazar"].detail["item"] == lines_item.pk
    assert all(e.user == evaluator_user and e.outcome == Outcome.OK for e in decisions())


def test_approve_one_part_and_reject_the_other_loads_only_what_was_approved(evaluator_user, proposed):
    """REQ-048: lo rechazado no se carga y queda rechazado con su autor."""
    link, procedure_item, lines_item = proposed
    approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                    confirmations=confirm(procedure_item))
    (result,) = approval.decide(evaluator_user, [lines_item.pk], approval.REJECT)
    assert result.result == approval.REJECTED
    assert Procedure.objects.count() == 1
    assert not PortalLine.objects.exists()
    lines_item.refresh_from_db()
    assert lines_item.state == ItemState.RECHAZADO and lines_item.decided_by == evaluator_user


def test_lines_are_loaded_with_their_quantity(evaluator_user, proposed):
    """REQ-046: 6 de 6 renglones cargados con su cantidad y su ítem de origen."""
    _, procedure_item, lines_item = proposed
    approval.decide(evaluator_user, [lines_item.pk, procedure_item.pk], approval.APPROVE,
                    confirmations=confirm(procedure_item))
    lines = list(PortalLine.objects.order_by("number"))
    assert [(l.number, int(l.quantity), l.unit) for l in lines] == [
        (w["numero"], w["cantidad"], w["unidad"]) for w in EXPECTED["renglones"]]
    assert all(l.item == lines_item and l.procedure == Procedure.objects.get() for l in lines)


def test_lines_without_the_procedure_wait(evaluator_user, proposed):
    """Plan 012: un ítem que depende del procedimiento no cargado queda propuesto, con motivo."""
    _, _, lines_item = proposed
    (result,) = approval.decide(evaluator_user, [lines_item.pk], approval.APPROVE)
    assert result.result == approval.PENDING and "procedimiento" in result.reason
    lines_item.refresh_from_db()
    assert lines_item.state == ItemState.PROPUESTO and lines_item.decided_by is None
    assert not PortalLine.objects.exists()


def test_procedure_without_confirmed_date_is_not_approved(evaluator_user, proposed):
    """REQ-046, P3: sin la fecha de autorización confirmada el procedimiento no se carga."""
    _, procedure_item, _ = proposed
    (result,) = approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE)
    assert result.result == approval.PENDING and "fecha de autorización" in result.reason
    assert not Procedure.objects.exists()
    procedure_item.refresh_from_db()
    assert procedure_item.state == ItemState.PROPUESTO


def test_failed_load_leaves_the_item_failed_and_the_rest_goes_on(evaluator_user, proposed):
    """Plan 012: si la carga falla, el ítem queda fallido con el motivo y nada de él se carga."""
    _, procedure_item, lines_item = proposed
    tomorrow = timezone.localdate() + timedelta(days=1)
    results = approval.decide(evaluator_user, [procedure_item.pk, lines_item.pk],
                              approval.APPROVE, confirmations=confirm(procedure_item, tomorrow))
    assert [r.result for r in results] == [approval.FAILED, approval.PENDING]
    procedure_item.refresh_from_db()
    assert procedure_item.state == ItemState.FALLIDO and "posterior" in procedure_item.failure
    assert not Procedure.objects.exists() and not PortalProcedureData.objects.exists()
    event = decisions().get(detail__item=procedure_item.pk)
    assert event.outcome == Outcome.FAILED and event.detail["reason"]


def test_partial_load_of_an_item_is_rolled_back(evaluator_user, proposed, monkeypatch):
    """Plan 012: la carga de un ítem y su decisión van en una sola transacción."""
    _, procedure_item, lines_item = proposed
    approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                    confirmations=confirm(procedure_item))
    real = PortalLine.objects.create
    calls = []

    def flaky(**kwargs):
        calls.append(kwargs["number"])
        if len(calls) == 4:
            raise RuntimeError("falla a mitad de camino")
        return real(**kwargs)

    monkeypatch.setattr(PortalLine.objects, "create", flaky)
    (result,) = approval.decide(evaluator_user, [lines_item.pk], approval.APPROVE)
    assert result.result == approval.FAILED and "a mitad de camino" in result.reason
    assert not PortalLine.objects.exists()


def test_already_associated_procedure_is_associated(operator_user, evaluator_user, explore_link):
    """Plan 012: con el número ya registrado se asocia al existente, sin duplicarlo."""
    existing = Procedure.objects.create(
        number=EXPECTED["procedimiento"]["numero"], procedure_type="Licitación pública",
        subject="Cargado a mano", authorization_date=DATE, created_by=operator_user)
    link, _ = explore_link(operator_user)
    item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    (result,) = approval.decide(evaluator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.LOADED, result.reason
    link.refresh_from_db()
    assert link.procedure == existing
    assert Procedure.objects.count() == 1
    assert PortalProcedureData.objects.get().procedure == existing
    assert not AuditEvent.objects.filter(event_type=EventType.PROCEDURE).exists()


def test_operator_cannot_approve_the_procedure(operator_user, proposed):
    """REQ-048: el operador no aprueba el procedimiento; no se decide ni se carga nada."""
    _, procedure_item, lines_item = proposed
    with pytest.raises(RoleRejected):
        approval.decide(operator_user, [procedure_item.pk, lines_item.pk], approval.APPROVE,
                        confirmations=confirm(procedure_item))
    assert not Procedure.objects.exists()
    assert not PortalItem.objects.exclude(state=ItemState.PROPUESTO).exists()
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 1
    assert not decisions().exists()


def test_operator_cannot_reject_nor_approve_all(operator_user, proposed):
    """REQ-048: el operador tampoco rechaza esos ítems ni aprueba todo."""
    link, procedure_item, _ = proposed
    with pytest.raises(RoleRejected):
        approval.decide(operator_user, [procedure_item.pk], approval.REJECT)
    with pytest.raises(RoleRejected):
        approval.approve_all(operator_user, link.pk)
    assert not PortalItem.objects.exclude(state=ItemState.PROPUESTO).exists()


def test_user_without_commission_role_cannot_decide(no_commission_user, proposed):
    """REQ-048: sin rol de la Comisión no se decide."""
    _, procedure_item, _ = proposed
    with pytest.raises(RoleRejected):
        approval.decide(no_commission_user, [procedure_item.pk], approval.REJECT)


def test_approve_all_loads_everything_in_dependency_order(evaluator_user, proposed):
    """REQ-048: aprobar todo respeta el orden: procedimiento y después renglones."""
    link, _, _ = proposed
    results = approval.approve_all(evaluator_user, link.pk,
                                   confirmations=confirm(proposed[1]))
    assert [r.item.kind for r in results] == [ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES]
    assert all(r.result == approval.LOADED for r in results)
    assert PortalLine.objects.count() == 6


def test_decided_item_is_not_decided_twice(evaluator_user, proposed):
    """Un ítem ya decidido no se vuelve a decidir."""
    _, procedure_item, _ = proposed
    approval.decide(evaluator_user, [procedure_item.pk], approval.REJECT)
    (result,) = approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                                confirmations=confirm(procedure_item))
    assert result.result == approval.ALREADY
    assert not Procedure.objects.exists()
    assert decisions().count() == 1


def test_proposal_page_marks_damaged_text_and_what_the_user_can_decide(
        operator_user, evaluator_user, proposed):
    """REQ-046: la página trae el ítem con su marca; el operador no puede decidir estos ítems."""
    link, _, _ = proposed
    as_operator = approval.proposal_page(operator_user, link.pk)
    as_evaluator = approval.proposal_page(evaluator_user, link.pk)
    assert not any(r.can_decide for g in as_operator.rows.values() for r in g)
    assert all(r.can_decide for g in as_evaluator.rows.values() for r in g)
    assert not as_operator.can_approve_all and as_evaluator.can_approve_all
    (row,) = as_evaluator.rows[ItemKind.PROCEDIMIENTO]
    assert row.action == "crear" and row.item.damaged_fields


def test_changed_item_is_marked_as_changed_from_what_was_approved(
        client, operator_user, evaluator_user, proposed, fake_portal_calco):
    """REQ-050: un ítem con otra huella que el ya cargado se muestra "cambiado respecto de lo
    aprobado"; el que no cambió no lleva la marca."""
    from evaluon.portal.models import Origin
    from evaluon.tenders import jobs
    from tests.conftest import TEST_PASSWORD
    from tests.portal.conftest import reply
    from tests.portal.fakeportal import DATA, LINK_URL

    link, procedure_item, lines_item = proposed
    approval.approve_all(evaluator_user, link.pk, confirmations=confirm(procedure_item))
    page = (DATA / "proceso.html").read_bytes().replace(b"2700 kg", b"2800 kg")
    fake_portal_calco.routes[("GET", LINK_URL)] = reply(LINK_URL, page)
    review = jobs.enqueue("portal_review", procedure=None, requested_by=operator_user,
                          target_id=link.pk)
    jobs.run(review)
    new = PortalItem.objects.get(proposal__origin=Origin.REVISION)
    rows = approval.proposal_page(evaluator_user, link.pk).rows[ItemKind.RENGLONES]
    marks = {row.item.pk: row.changed for row in rows}
    assert marks[new.pk] is True
    assert sum(marks.values()) == 1
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    html = client.get(f"/importar/{link.pk}/").content.decode()
    assert html.count("Cambiado respecto de lo aprobado") == 1
