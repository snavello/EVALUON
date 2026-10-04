"""Revisión de la matriz: confirmar, corregir, quitar, agregar y resolver pendientes
(REQ-026, REQ-027, REQ-028; plan 003, "Revisión, validación y versiones"; T-079).

Pliegos sintéticos y el doble del modelo con guion (`tests/tenders/scripted.py`); sin datos
de personas (P4).
"""

import html

import pytest
from django.db import ProgrammingError, transaction
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import review
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import (
    GARANTIA,
    PAGO,
    check_deferred,
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
    """Un pliego de tres renglones propuesto: una garantía y un pago como económicos y una
    fila técnica por renglón (con tramos solo la del 2). Pendiente: el renglón 3, sin
    especificaciones."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    script.when(GARANTIA, item([("constituir una garantía del 5 % del monto",
                                 "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when("Bolsa de diez kilogramos", item(technical=["2"]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return requested.run.version


def req(version, text=None, category=None):
    rows = m.Requirement.objects.filter(version=version).order_by("number")
    if category:
        rows = rows.filter(category=category)
    for row in rows:
        if text is None or any(text in q.text for q in row.quotes.all()):
            return row
    raise AssertionError(f"no hay requisito con {text!r}")


def tech(version, number):
    return m.Requirement.objects.get(version=version, category="tecnico", items=[number])


def segment_with(version, text):
    reading_ids = [d["reading"] for d in version.run.documents]
    return m.Segment.objects.filter(reading_id__in=reading_ids,
                                    text__contains=text).first()


def rejected(reason):
    return AuditEvent.objects.filter(
        event_type=EventType.REQUIREMENT_CHANGE, outcome=Outcome.REJECTED,
        detail__reason=reason)


def counts():
    return (m.RequirementChange.objects.count(),
            AuditEvent.objects.filter(event_type=EventType.REQUIREMENT_CHANGE,
                                      outcome=Outcome.OK).count())


# --- Corregir (REQ-026) ---------------------------------------------------------------------------


def test_a_correction_keeps_user_moment_before_after_and_the_proposal(operator_user, case):
    """REQ-026: una corrección queda con usuario, momento, antes y después, y lo propuesto
    se consulta en el historial."""
    requirement = req(case, PAGO)
    proposed = dict(requirement.proposed)
    started = timezone.now()

    done = review.correct(operator_user, requirement.pk, category="formal", items="1, 2")

    requirement.refresh_from_db()
    assert requirement.category == "formal" and requirement.items == [1, 2]
    change = m.RequirementChange.objects.get(requirement=requirement)
    assert change.action == "corregir" and change.user == operator_user
    assert change.at >= started
    assert change.before["category"] == "economico" and change.after["category"] == "formal"
    assert change.before["items"] != change.after["items"]
    assert done.events[0].event_type == EventType.REQUIREMENT_CHANGE
    assert change.event == done.events[0]
    assert requirement.proposed == proposed != {}
    page = review.history(operator_user, requirement.pk)
    assert page.proposed["category"] == "economico"
    assert page.proposed["quotes"][0]["text"] == PAGO


def test_a_corrected_quote_is_the_exact_cut_of_the_canonical_text(operator_user, case):
    """REQ-025/026: la cita corregida se verifica en el tramo (tolera espacios y saltos de
    línea) y se guarda el recorte exacto del texto canónico."""
    requirement = req(case, PAGO)
    segment = segment_with(case, PAGO)
    messy = "a los 90   días\ncorridos de la factura"

    review.correct(operator_user, requirement.pk, segment=segment.pk, quote=messy)

    quote = requirement.quotes.get()
    canonical = segment.reading.canonical_text
    assert quote.text == canonical[quote.char_start:quote.char_end]
    assert " ".join(quote.text.split()) == "a los 90 días corridos de la factura"
    assert quote.quote_flag == "" and quote.segment_id == segment.pk


def test_a_quote_not_in_the_segment_is_rejected_and_nothing_changes(operator_user, case):
    """REQ-026: una cita corregida que no está en el tramo se rechaza, con su hecho."""
    requirement = req(case, PAGO)
    segment = segment_with(case, PAGO)
    before = counts()

    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, requirement.pk, segment=segment.pk,
                       quote="un texto que el pliego no dice")

    assert error.value.reason == "quote_not_in_segment"
    assert counts() == before
    assert rejected("quote_not_in_segment").count() == 1
    assert requirement.quotes.get().text == PAGO


def test_a_quote_can_move_to_another_segment_of_the_tender_but_not_to_a_foreign_one(
        operator_user, case):
    """La cita se puede llevar a otro tramo del mismo pliego; uno de otro pliego no."""
    requirement = req(case, PAGO)
    other = segment_with(case, "vencimiento mayor")
    review.correct(operator_user, requirement.pk, segment=other.pk,
                   quote="vencimiento mayor a once meses")
    assert requirement.quotes.get().segment_id == other.pk

    other_procedure = make_procedure(operator_user)
    load_and_read(operator_user, other_procedure, three_items_pdf(), title="Otro pliego")
    foreign = m.Segment.objects.filter(
        reading__document__procedure=other_procedure, text__contains=PAGO).first()
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, requirement.pk, segment=foreign.pk, quote=PAGO)
    assert error.value.reason == "segment_not_in_tender"


def test_a_correction_that_changes_nothing_is_refused(operator_user, case):
    requirement = req(case, PAGO)
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, requirement.pk, category="economico")
    assert error.value.reason == "nothing_to_change"


def test_correcting_a_confirmed_requirement_makes_it_proposed_again(
        operator_user, evaluator_user, case):
    requirement = req(case, PAGO)
    review.confirm(evaluator_user, [requirement.pk])
    review.correct(operator_user, requirement.pk, category="formal")
    requirement.refresh_from_db()
    assert requirement.state == "propuesto"
    last = requirement.changes.order_by("-id").first()
    assert last.before["state"] == "confirmado" and last.after["state"] == "propuesto"


def test_a_formal_passed_to_technical_joins_the_row_of_its_item(operator_user, case):
    """Pasar un formal o económico a técnico lo une a la fila de su renglón."""
    row = tech(case, 2)
    assert row.items == [2]
    requirement = req(case, PAGO)
    segment = segment_with(case, PAGO)
    quotes_before = row.quotes.count()

    done = review.correct(operator_user, requirement.pk, category="tecnico", items="2")

    requirement.refresh_from_db()
    assert requirement.state == "quitado"
    assert row.quotes.count() == quotes_before + 1
    joined = row.quotes.get(segment=segment)
    assert joined.text == PAGO and joined.scope in ("propia", "general")
    assert {c.requirement_id for c in done.changes} == {requirement.pk, row.pk}
    assert row.changes.get().after["quotes"][-1]["text"] == PAGO
    check_deferred()


def test_passing_to_technical_without_a_row_for_the_item_is_refused(operator_user, case):
    requirement = req(case, PAGO)
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, requirement.pk, category="tecnico", items="9")
    assert error.value.reason == "no_technical_row"
    requirement.refresh_from_db()
    assert requirement.state == "propuesto" and requirement.quotes.count() == 1


def test_adding_a_segment_to_a_technical_row_is_recorded(operator_user, case):
    """Sumar un tramo a una fila técnica queda registrado."""
    row = tech(case, 2)
    extra = segment_with(case, "multa del 1 %")

    review.correct(operator_user, row.pk, add_segments=[extra.pk])

    quote = row.quotes.get(segment=extra)
    assert (quote.char_start, quote.char_end, quote.text) == (
        extra.char_start, extra.char_end, extra.text)
    change = row.changes.get()
    assert change.action == "corregir" and change.user == operator_user
    assert len(change.after["quotes"]) == len(change.before["quotes"]) + 1
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, row.pk, add_segments=[extra.pk])
    assert error.value.reason == "quote_duplicate"


def test_removing_a_segment_from_a_technical_row_but_never_the_last(operator_user, case):
    row = tech(case, 2)
    extra = segment_with(case, "multa del 1 %")
    review.correct(operator_user, row.pk, add_segments=[extra.pk])
    added = row.quotes.get(segment=extra)

    review.correct(operator_user, row.pk, remove_quotes=[added.pk])
    assert not row.quotes.filter(segment=extra).exists()

    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, row.pk,
                       remove_quotes=[q.pk for q in row.quotes.all()])
    assert error.value.reason == "last_quote"
    assert row.quotes.exists()


# --- Agregar --------------------------------------------------------------------------------------


def test_a_second_technical_row_for_the_same_item_is_rejected(operator_user, case):
    """Una segunda fila técnica para el mismo renglón se rechaza."""
    segment = segment_with(case, "vencimiento mayor")
    before = counts()
    with pytest.raises(review.ReviewRefused) as error:
        review.add_technical_row(operator_user, case.pk, item=2, segments=[segment.pk])
    assert error.value.reason == "technical_row_exists"
    assert counts() == before
    assert m.Requirement.objects.filter(version=case, category="tecnico",
                                        items=[2]).count() == 1
    assert rejected("technical_row_exists").count() == 1


def test_a_technical_row_is_added_for_an_item_that_has_none(operator_user, case):
    segment = segment_with(case, "multa del 1 %")
    tech(case, 3).quotes.all().delete()  # el renglón 3 queda sin fila: se arma de nuevo
    tech(case, 3).consequences.all().delete()
    tech(case, 3).delete()
    done = review.add_technical_row(operator_user, case.pk, item=3, segments=[segment.pk])
    row = done.requirements[0]
    assert row.category == "tecnico" and row.items == [3] and row.origin == "agregado"
    assert row.quotes.get().segment_id == segment.pk
    assert row.changes.get().action == "agregar"
    check_deferred()


def test_adding_a_requirement_from_a_segment_with_a_literal_fragment(operator_user, case):
    segment = segment_with(case, "multa del 1 %")
    done = review.add_requirement(operator_user, case.pk, segment=segment.pk,
                                  quote="una multa del 1 % diario", category="economico")
    added = done.requirements[0]
    assert added.origin == "agregado" and added.category == "economico"
    quote = added.quotes.get()
    assert quote.text == segment.reading.canonical_text[quote.char_start:quote.char_end]
    assert "multa del 1 % diario" in quote.text
    change = added.changes.get()
    assert change.action == "agregar" and change.before is None
    check_deferred()
    with pytest.raises(review.ReviewRefused) as error:
        review.add_requirement(operator_user, case.pk, segment=segment.pk,
                               quote="un texto inventado", category="economico")
    assert error.value.reason == "quote_not_in_segment"
    with pytest.raises(review.ReviewRefused) as error:
        review.add_requirement(operator_user, case.pk, segment=segment.pk,
                               quote="multa", category="tecnico")
    assert error.value.reason == "invalid_category"


# --- Quitar y restituir ---------------------------------------------------------------------------


def test_remove_and_restore_keep_the_history(operator_user, evaluator_user, case):
    requirement = req(case, PAGO)
    review.confirm(evaluator_user, [requirement.pk])
    review.remove(operator_user, requirement.pk)
    requirement.refresh_from_db()
    assert requirement.state == "quitado" and requirement.quotes.count() == 1
    with pytest.raises(review.ReviewRefused):
        review.remove(operator_user, requirement.pk)
    with pytest.raises(review.ReviewRefused) as error:
        review.correct(operator_user, requirement.pk, category="formal")
    assert error.value.reason == "requirement_removed"

    review.restore(operator_user, requirement.pk)
    requirement.refresh_from_db()
    assert requirement.state == "confirmado"
    actions = list(requirement.changes.order_by("id").values_list("action", flat=True))
    assert actions == ["confirmar", "quitar", "restituir"]


# --- Roles ----------------------------------------------------------------------------------------


def test_an_operator_cannot_confirm_and_it_is_recorded(operator_user, case):
    """Un operador no puede confirmar: queda `rejected` con el rol exigido."""
    requirement = req(case, PAGO)
    with pytest.raises(RoleRejected):
        review.confirm(operator_user, [requirement.pk])
    event = AuditEvent.objects.filter(event_type=EventType.REJECTED).latest("id")
    assert event.detail["required_commission_role"] == "evaluator"
    assert event.detail["operation"] == review.CONFIRM_OPERATION
    requirement.refresh_from_db()
    assert requirement.state == "propuesto" and not requirement.changes.exists()


def test_an_operator_cannot_resolve_a_pending_and_it_is_recorded(operator_user, case):
    pending = case.pending_items.first()
    with pytest.raises(RoleRejected):
        review.resolve_pending(operator_user, pending.pk)
    event = AuditEvent.objects.filter(event_type=EventType.REJECTED).latest("id")
    assert event.detail["required_commission_role"] == "evaluator"
    pending.refresh_from_db()
    assert pending.resolved_at is None


def test_a_user_without_commission_role_cannot_review(no_commission_user, case):
    requirement = req(case, PAGO)
    with pytest.raises(RoleRejected):
        review.correct(no_commission_user, requirement.pk, category="formal")
    with pytest.raises(RoleRejected):
        review.remove(no_commission_user, requirement.pk)
    with pytest.raises(RoleRejected):
        review.history(no_commission_user, requirement.pk)


def test_the_evaluator_confirms_several_requirements(evaluator_user, case):
    ids = list(m.Requirement.objects.filter(version=case).values_list("pk", flat=True))
    done = review.confirm(evaluator_user, ids)
    assert len(done.changes) == len(ids)
    assert set(m.Requirement.objects.filter(version=case).values_list(
        "state", flat=True)) == {"confirmado"}
    assert all(c.user == evaluator_user for c in done.changes)
    again = review.confirm(evaluator_user, ids)  # ya confirmados: nada cambia
    assert again.changes == []


# --- Pendientes (REQ-028) -------------------------------------------------------------------------


def test_the_evaluator_resolves_a_pending_without_requirements(evaluator_user, case):
    pending = case.pending_items.first()
    done = review.resolve_pending(evaluator_user, pending.pk)
    pending.refresh_from_db()
    assert pending.resolution == "sin_requisitos"
    assert pending.resolved_by == evaluator_user and pending.resolved_at is not None
    assert done.events[0].event_type == EventType.SEGMENT_REVIEW
    with pytest.raises(review.ReviewRefused) as error:
        review.resolve_pending(evaluator_user, pending.pk)
    assert error.value.reason == "pending_resolved"


def test_adding_a_requirement_from_a_pending_resolves_it(operator_user, case):
    segment = segment_with(case, "multa del 1 %")
    pending = m.PendingItem.objects.create(version=case, segment=segment,
                                           reason="sin_disposicion")
    done = review.add_requirement(operator_user, case.pk, segment=segment.pk,
                                  quote="multa del 1 % diario", category="economico",
                                  pending=pending.pk)
    pending.refresh_from_db()
    assert pending.resolution == "requisito_agregado"
    assert pending.resolved_by == operator_user
    assert [e.event_type for e in done.events] == [EventType.REQUIREMENT_CHANGE,
                                                   EventType.SEGMENT_REVIEW]
    other = segment_with(case, PAGO)
    again = m.PendingItem.objects.create(version=case, segment=other, reason="marcadores")
    with pytest.raises(review.ReviewRefused) as error:
        review.add_requirement(operator_user, case.pk, segment=segment.pk,
                               quote="multa", category="economico", pending=again.pk)
    assert error.value.reason == "pending_other_segment"


# --- Una versión validada no cambia (REQ-027) -----------------------------------------------------


def validate(version, user):
    version.status = m.VersionStatus.VALIDATED
    version.validated_at = timezone.now()
    version.validated_by = user
    version.save()


def test_nothing_changes_in_a_validated_version(operator_user, evaluator_user, case):
    """REQ-027: en una versión validada toda operación se rechaza antes de escribir."""
    requirement = req(case, PAGO)
    technical = tech(case, 2)
    pending = case.pending_items.first()
    segment = segment_with(case, "multa del 1 %")
    validate(case, evaluator_user)
    before = counts()
    sets_before = (m.Requirement.objects.count(), m.RequirementQuote.objects.count())

    calls = [
        lambda: review.confirm(evaluator_user, [requirement.pk]),
        lambda: review.correct(operator_user, requirement.pk, category="formal"),
        lambda: review.correct(operator_user, technical.pk, add_segments=[segment.pk]),
        lambda: review.remove(operator_user, requirement.pk),
        lambda: review.restore(operator_user, requirement.pk),
        lambda: review.add_requirement(operator_user, case.pk, segment=segment.pk,
                                       quote="multa", category="economico"),
        lambda: review.add_technical_row(operator_user, case.pk, item=3,
                                         segments=[segment.pk]),
        lambda: review.resolve_pending(evaluator_user, pending.pk),
    ]
    for call in calls:
        with pytest.raises(review.ReviewRefused) as error:
            call()
        assert error.value.reason == "version_not_draft"

    assert counts() == before
    assert (m.Requirement.objects.count(),
            m.RequirementQuote.objects.count()) == sets_before
    assert rejected("version_not_draft").count() == len(calls)
    requirement.refresh_from_db()
    assert requirement.state == "propuesto" and requirement.category == "economico"


def test_the_database_also_refuses_to_change_a_validated_requirement(
        evaluator_user, case):
    requirement = req(case, PAGO)
    validate(case, evaluator_user)
    with pytest.raises(ProgrammingError), transaction.atomic():
        m.Requirement.objects.filter(pk=requirement.pk).update(state="confirmado")


# --- Pantalla -------------------------------------------------------------------------------------


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def page_text(response):
    return html.unescape(response.content.decode())


def test_pending_come_first_unresolved_before_resolved(client, evaluator_user, case):
    """REQ-028: en la página, los pendientes sin resolver van antes que los resueltos."""
    first = case.pending_items.order_by("id").first()
    segment = segment_with(case, PAGO)
    second = m.PendingItem.objects.create(version=case, segment=segment,
                                          reason="sin_disposicion")
    review.resolve_pending(evaluator_user, first.pk)
    log_in(client, evaluator_user)
    response = client.get(reverse("tenders:matrix", args=[case.pk]))
    rows = response.context["page"].pending
    assert rows[0].item.pk == second.pk and rows[-1].item.pk == first.pk


def test_the_page_offers_actions_by_role(client, operator_user, evaluator_user, case):
    log_in(client, operator_user)
    page = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    assert "Guardar la corrección" in page and "Quitar el requisito" in page
    assert "Confirmar los requisitos marcados" not in page
    assert "Revisado, sin requisitos" not in page
    assert "Agregar la fila técnica" in page

    client.logout()
    log_in(client, evaluator_user)
    page = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    assert "Confirmar los requisitos marcados" in page
    assert "Revisado, sin requisitos" in page

    validate(case, evaluator_user)
    page = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    assert "Guardar la corrección" not in page
    assert "Confirmar los requisitos marcados" not in page


def test_posting_a_correction_and_reading_the_history(client, operator_user, case):
    requirement = req(case, PAGO)
    log_in(client, operator_user)
    response = client.post(
        reverse("tenders:review_correct", args=[requirement.pk]),
        {"category": "formal", "items": "", "segment": segment_with(case, PAGO).pk,
         "quote": PAGO})
    assert response.status_code == 302
    requirement.refresh_from_db()
    assert requirement.category == "formal"
    assert requirement.quotes.get().quote_flag == ""

    history = page_text(client.get(reverse("tenders:history", args=[requirement.pk])))
    assert "Propuesto originalmente" in history and "economico" in history
    assert "Corregir" in history and operator_user.username in history
    assert PAGO in history


def test_a_refused_post_shows_the_reason_and_changes_nothing(client, operator_user, case):
    requirement = req(case, PAGO)
    log_in(client, operator_user)
    response = client.post(
        reverse("tenders:review_correct", args=[requirement.pk]),
        {"category": "formal", "segment": segment_with(case, PAGO).pk,
         "quote": "texto que no está"})
    assert response.status_code == 400
    assert "El fragmento no está en el tramo" in page_text(response)
    requirement.refresh_from_db()
    assert requirement.category == "economico"


def test_an_operator_posting_a_confirmation_gets_403(client, operator_user, case):
    requirement = req(case, PAGO)
    log_in(client, operator_user)
    response = client.post(reverse("tenders:review_confirm", args=[case.pk]),
                           {"requirement": [requirement.pk]})
    assert response.status_code == 403
    requirement.refresh_from_db()
    assert requirement.state == "propuesto"


def test_the_evaluator_confirms_from_the_page(client, evaluator_user, case):
    ids = list(m.Requirement.objects.filter(version=case).values_list("pk", flat=True))
    log_in(client, evaluator_user)
    response = client.post(reverse("tenders:review_confirm", args=[case.pk]),
                           {"requirement": ids})
    assert response.status_code == 302
    assert m.Requirement.objects.filter(version=case,
                                        state="confirmado").count() == len(ids)


def test_removed_requirements_stay_visible_and_can_be_restored(
        client, operator_user, case):
    requirement = req(case, PAGO)
    log_in(client, operator_user)
    client.post(reverse("tenders:review_remove", args=[requirement.pk]))
    page = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    assert "Requisitos quitados" in page and PAGO in page and "Restituir" in page
    client.post(reverse("tenders:review_restore", args=[requirement.pk]))
    requirement.refresh_from_db()
    assert requirement.state == "propuesto"


def test_get_on_an_action_is_not_allowed(client, operator_user, case):
    requirement = req(case, PAGO)
    log_in(client, operator_user)
    assert client.get(reverse("tenders:review_remove", args=[requirement.pk])
                      ).status_code == 405


def test_a_technical_row_for_an_item_not_in_the_tender_is_rejected(operator_user, case):
    """Un renglón que la lectura del pliego no reconoce se rechaza, con su hecho."""
    segment = segment_with(case, "multa del 1 %")
    before = counts()
    with pytest.raises(review.ReviewRefused) as error:
        review.add_technical_row(operator_user, case.pk, item=9, segments=[segment.pk])
    assert error.value.reason == "item_unknown"
    assert counts() == before
    assert rejected("item_unknown").count() == 1
    assert not m.Requirement.objects.filter(version=case, items=[9]).exists()


def test_restoring_a_formal_passed_to_technical_takes_its_quote_out_of_the_row(
        operator_user, case):
    """O1: restituir deshace el pase a técnico: la cita sale de la fila y queda registrado
    en el historial de la fila; no queda en dos lugares."""
    row = tech(case, 2)
    requirement = req(case, PAGO)
    segment = segment_with(case, PAGO)
    quotes_before = row.quotes.count()
    review.correct(operator_user, requirement.pk, category="tecnico", items="2")
    assert row.quotes.filter(segment=segment).exists()

    done = review.restore(operator_user, requirement.pk)

    requirement.refresh_from_db()
    assert requirement.state == "propuesto" and requirement.category == "economico"
    assert requirement.quotes.count() == 1
    assert row.quotes.count() == quotes_before
    assert not row.quotes.filter(segment=segment, text=PAGO).exists()
    last = row.changes.order_by("-id").first()
    assert last.action == "corregir" and last.user == operator_user
    assert len(last.after["quotes"]) == len(last.before["quotes"]) - 1
    assert {c.requirement_id for c in done.changes} == {requirement.pk, row.pk}
    check_deferred()


def test_restoring_a_plain_removal_does_not_touch_technical_rows(operator_user, case):
    row = tech(case, 2)
    requirement = req(case, PAGO)
    review.remove(operator_user, requirement.pk)
    review.restore(operator_user, requirement.pk)
    assert not row.changes.exists()


def test_correcting_a_wide_quote_removes_the_wide_mark(operator_user, case):
    """O2: corregir una cita amplia le quita la marca `cita_amplia`."""
    requirement = req(case, PAGO)
    quote = requirement.quotes.get()
    quote.quote_flag = "cita_amplia"
    quote.save()
    segment = segment_with(case, PAGO)

    review.correct(operator_user, requirement.pk, segment=segment.pk,
                   quote="a los 90 días corridos de la factura")

    quote.refresh_from_db()
    assert quote.quote_flag == ""
    assert quote.text == "a los 90 días corridos de la factura"
    change = requirement.changes.get()
    assert change.before["quotes"][0]["flag"] == "cita_amplia"
    assert change.after["quotes"][0]["flag"] == ""
