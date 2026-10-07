"""Verificacion T-168 (REQ-061): casos adicionales del testeador."""
import pytest
from django.db import IntegrityError, InternalError, ProgrammingError, transaction
from django.test import Client
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import technical
from evaluon.audit.models import AuditEvent, EventType
from tests.assessment.test_matrix import add_run, discard_of, page_of, requirement
from tests.assessment.test_technical_ok import pending, current, PENDING  # noqa: F401
from tests.offers.test_screens import log_in

pytestmark = [pytest.mark.django_db]


def n_ok():
    return am.TechnicalOk.objects.count()


@pytest.mark.parametrize("bad", ["cumple", "APTO", "no cumple", "x", 1, None, ""])
def test_verdict_other_than_apto_no_apto_refused(pending, evaluator_user, bad):
    offer, rows = pending
    with pytest.raises(technical.TechnicalRefused):
        technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: bad})
    assert n_ok() == 0
    assert current(offer, rows[1]).doubt == "pendiente_informe_tecnico"
    assert AuditEvent.objects.filter(outcome="rejected", detail__kind="technical_ok").count() == 1


def test_verdict_for_unnamed_item_refused(pending, evaluator_user):
    offer, rows = pending
    with pytest.raises(technical.TechnicalRefused) as e:
        technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "apto", 2: "no_apto"})
    assert e.value.reason == "verdict_out_of_scope"
    assert n_ok() == 0


@pytest.mark.parametrize("items", [[99], ["abc"], [], [1, 99]])
def test_unknown_or_empty_items_refused(pending, evaluator_user, items):
    offer, rows = pending
    with pytest.raises(technical.TechnicalRefused):
        technical.give_ok(evaluator_user, offer, items=items, verdicts={i: "apto" for i in items})
    assert n_ok() == 0


@pytest.mark.parametrize("who", ["operator_user", "no_commission_user"])
def test_only_evaluator(pending, request, who, evaluator_user):
    user = request.getfixturevalue(who)
    offer, rows = pending
    before_events = AuditEvent.objects.count()
    with pytest.raises(RoleRejected):
        technical.give_ok(user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    with pytest.raises(RoleRejected):
        technical.withdraw_ok(user, offer, note="n")
    assert n_ok() == 1
    assert AuditEvent.objects.filter(outcome="rejected").count() == 2
    assert technical.has_ok(offer, 1)


def test_every_ok_has_event_with_kind_and_row_links_it(pending, evaluator_user):
    offer, rows = pending
    a = technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "no_apto"}, note="x")
    b = technical.withdraw_ok(evaluator_user, offer, items=[1], note="y")
    for applied in (a, b):
        assert applied.ok.event_id == applied.event.pk
        assert applied.event.detail["kind"] == "technical_ok"
        assert applied.event.event_type == EventType.EVAL_DECISION
        assert applied.event.outcome == "ok"
        assert applied.event.user_id == evaluator_user.pk


def test_opinion_never_discards(pending, evaluator_user, procedure, operator_user):
    offer, rows = pending
    old = {i: current(offer, r) for i, r in rows.items()}
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=old[1].run.matrix_version, offers=[offer.pk],
        requirements=None, cause=am.Cause.MATRIZ, requested_by=operator_user)
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=old[1].run.matrix_version, number=9,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    for i, r in rows.items():
        am.Result.objects.create(
            run=run, offer=offer, requirement=r, outcome="no_determinado",
            doubt="pendiente_informe_tecnico", exigence=old[i].exigence, explanation="op",
            opinion="no_cumple", previous=old[i])
    assert discard_of(page_of(evaluator_user, procedure), offer) is None
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    assert discard_of(page_of(evaluator_user, procedure), offer) is None
    assert current(offer, rows[1]).opinion == "no_cumple"


def test_ok_rows_are_insert_only(pending, evaluator_user):
    offer, rows = pending
    a = technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "apto"})
    for op in (lambda: am.TechnicalOk.objects.filter(pk=a.ok.pk).update(note="z"),
               lambda: am.TechnicalOk.objects.filter(pk=a.ok.pk).delete(),
               lambda: am.Result.objects.filter(pk=a.results[0].pk).update(outcome="no_cumple"),
               lambda: am.Result.objects.filter(pk=a.results[0].previous_id).delete()):
        with pytest.raises(Exception):
            with transaction.atomic():
                op()


def test_withdraw_reverts_discard_and_regive_changes_verdict(pending, evaluator_user, procedure):
    offer, rows = pending
    technical.give_ok(evaluator_user, offer, verdicts={1: "no_apto", 2: "apto", 3: "apto"})
    assert discard_of(page_of(evaluator_user, procedure), offer).items == [1]
    # dar de nuevo cambiando el dictamen
    technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "apto"})
    assert current(offer, rows[1]).outcome == "cumple"
    assert discard_of(page_of(evaluator_user, procedure), offer) is None
    technical.withdraw_ok(evaluator_user, offer, items=[1], note="n")
    assert current(offer, rows[1]).doubt == "pendiente_informe_tecnico"
    assert not technical.has_ok(offer, 1) and technical.has_ok(offer, 2)
    chain, r = [], current(offer, rows[1])
    while r:
        chain.append(r.outcome)
        r = r.previous
    assert chain == ["no_determinado", "cumple", "no_cumple", "no_determinado"]


def test_non_pending_row_not_touched(pending, evaluator_user, operator_user, procedure):
    offer, rows = pending
    decl = requirement(procedure, "declaración jurada")
    before = current(offer, decl)
    # un renglón nuevo cumple ya resuelto
    r4 = requirement(procedure, item=1)
    ap = technical.give_ok(evaluator_user, offer, items=[1], verdicts={1: "apto"})
    again = technical.withdraw_ok(evaluator_user, offer, items=[1, 2], note="n")
    assert 2 in again.skipped and 1 not in again.skipped
    assert current(offer, decl).pk == before.pk


def test_csrf_and_anonymous(pending, evaluator_user, operator_user):
    offer, rows = pending
    give = reverse("assessment:technical_give", args=[offer.pk])
    withdraw = reverse("assessment:technical_withdraw", args=[offer.pk])
    c = Client(enforce_csrf_checks=True)
    log_in(c, evaluator_user)
    assert c.post(give, {"all": "1", "verdict_1": "apto"}).status_code == 403
    assert c.post(withdraw, {"all": "1", "note": "n"}).status_code == 403
    assert n_ok() == 0
    anon = Client()
    r = anon.post(give, {"all": "1"})
    assert r.status_code in (302, 401, 403) and n_ok() == 0
    c2 = Client()
    log_in(c2, operator_user)
    assert c2.post(withdraw, {"all": "1", "note": "n"}).status_code == 403
    assert c2.get(give).status_code in (405, 403)
    log_in(c2, evaluator_user)
    assert c2.get(give).status_code == 405
    assert c2.post(reverse("assessment:technical_give", args=[999999]), {}).status_code == 404


def test_view_all_with_missing_verdicts_422(pending, evaluator_user):
    offer, rows = pending
    c = Client()
    log_in(c, evaluator_user)
    give = reverse("assessment:technical_give", args=[offer.pk])
    r = c.post(give, {"all": "1", "verdict_1": "apto", "verdict_2": "apto"})
    assert r.status_code == 422 and n_ok() == 0
    r = c.post(give, {"all": "1", "verdict_1": "cumple", "verdict_2": "apto", "verdict_3": "apto"})
    assert r.status_code == 422 and n_ok() == 0

