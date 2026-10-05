"""Validar la matriz, descartar un borrador y abrir versiones nuevas (REQ-027; plan 003,
"Revisión, validación y versiones"; principio P3; T-082).

Pliegos y datos sintéticos (P4). El pliego es el de tres renglones de `scripted.py`: una
garantía y un pago como económicos, una fila técnica por renglón y un tramo pendiente.
"""

from django.utils import timezone
import html
from datetime import date

import pytest
from django.db import DatabaseError, transaction
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import consequences, matrix_page, review
from evaluon.tenders.services import validation as service
from tests.conftest import TEST_PASSWORD
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


def requirement_with(version, text):
    for row in m.Requirement.objects.filter(version=version).order_by("number"):
        if any(text in q.text for q in row.quotes.all()):
            return row
    raise AssertionError(text)


def finish_review(evaluator, version, *, skip=()):
    """Resuelve los pendientes y elige la consecuencia de cada requisito no quitado."""
    for pending in version.pending_items.filter(resolved_at__isnull=True):
        review.resolve_pending(evaluator, pending.pk)
    for requirement in version.requirements.exclude(state="quitado"):
        if requirement.pk not in skip:
            consequences.choose(evaluator, requirement.pk,
                                consequence_type="aprobar_igual", note="Motivo de prueba")


@pytest.fixture
def ready(case, evaluator_user):
    """La versión lista para validar, con una fuente de circular sobre una cita."""
    pago = requirement_with(case, PAGO)
    quote = pago.quotes.get()
    m.RequirementSource.objects.create(
        requirement=pago, quote=quote, effect="modifica", segment=quote.segment,
        char_start=quote.char_start, char_end=quote.char_end,
        text="El pago se efectuará a los 30 días corridos de la factura.",
        issued_on=date(2025, 12, 1))
    finish_review(evaluator_user, case)
    return case


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def page_text(response):
    return html.unescape(response.content.decode())


def rejected(reason, event_type=EventType.MATRIX_VALIDATION):
    return AuditEvent.objects.filter(event_type=event_type, outcome=Outcome.REJECTED,
                                     detail__reason=reason)


# --- Condiciones para validar -------------------------------------------------------------------


def test_a_pending_without_resolving_blocks_the_validation_and_says_why(
        evaluator_user, case):
    """REQ-027: con un tramo pendiente sin resolver no se valida; se dice por qué."""
    for requirement in case.requirements.all():
        consequences.choose(evaluator_user, requirement.pk,
                            consequence_type="aprobar_igual", note="Motivo")
    assert case.pending_items.filter(resolved_at__isnull=True).exists()

    with pytest.raises(service.ValidationRefused) as error:
        service.validate(evaluator_user, case.pk)

    assert "pendientes de revisión" in str(error.value)
    case.refresh_from_db()
    assert case.status == "draft" and case.validated_at is None
    assert rejected("pending_unresolved").count() == 1
    assert not AuditEvent.objects.filter(event_type=EventType.MATRIX_VALIDATION,
                                         outcome=Outcome.OK).exists()


def test_a_requirement_without_a_chosen_consequence_blocks_it_and_names_it(
        evaluator_user, case):
    """REQ-027, REQ-029: un requisito sin consecuencia elegida impide validar y se lo
    nombra por su número."""
    pago = requirement_with(case, PAGO)
    finish_review(evaluator_user, case, skip=[pago.pk])

    with pytest.raises(service.ValidationRefused) as error:
        service.validate(evaluator_user, case.pk)

    assert "consecuencia" in str(error.value) and str(pago.number) in str(error.value)
    case.refresh_from_db()
    assert case.status == "draft"
    assert rejected("consequence_missing").count() == 1
    assert not m.RequirementChange.objects.filter(action="confirmar").exists()


def test_a_removed_requirement_does_not_need_a_consequence(evaluator_user, case):
    """Un requisito quitado no exige consecuencia para validar."""
    pago = requirement_with(case, PAGO)
    review.remove(evaluator_user, pago.pk)
    finish_review(evaluator_user, case)

    service.validate(evaluator_user, case.pk)

    pago.refresh_from_db()
    assert pago.state == "quitado"


def test_only_an_evaluator_validates(operator_user, ready):
    """Roles: el operador no valida; el rechazo queda registrado y nada cambia."""
    with pytest.raises(RoleRejected):
        service.validate(operator_user, ready.pk)

    event = AuditEvent.objects.filter(event_type=EventType.REJECTED).latest("id")
    assert event.detail["required_commission_role"] == "evaluator"
    assert event.detail["operation"] == service.VALIDATE_OPERATION
    ready.refresh_from_db()
    assert ready.status == "draft"


# --- Validar -------------------------------------------------------------------------------------


def test_validating_confirms_the_proposed_ones_with_history_and_records_it(
        evaluator_user, ready):
    """REQ-027: quien valida confirma los que seguían propuestos, cada uno con su fila de
    historial; la versión queda con quién y cuándo, y el hecho trae las cuentas."""
    proposed = list(ready.requirements.filter(state="propuesto").values_list(
        "pk", flat=True))
    assert proposed

    version = service.validate(evaluator_user, ready.pk)

    assert version.status == "validated"
    assert version.validated_by == evaluator_user and version.validated_at is not None
    assert not ready.requirements.exclude(state="confirmado").exists()
    for pk in proposed:
        change = m.RequirementChange.objects.get(requirement_id=pk, action="confirmar")
        assert change.user == evaluator_user
        assert change.before == {"state": "propuesto"}
        assert change.after == {"state": "confirmado"}
        assert change.event.detail["by_validation"] is True
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VALIDATION,
                                   outcome=Outcome.OK)
    assert event.user == evaluator_user
    assert event.detail["version"] == ready.pk
    assert sorted(event.detail["confirmed_by_validation"]) == sorted(proposed)
    assert event.detail["by_state"] == {"confirmado": len(proposed)}
    assert sum(event.detail["by_class"].values()) == len(proposed)


def test_a_requirement_already_confirmed_is_not_confirmed_twice(evaluator_user, ready):
    """Un requisito ya confirmado no recibe otra fila de historial al validar."""
    pago = requirement_with(ready, PAGO)
    review.confirm(evaluator_user, [pago.pk])

    service.validate(evaluator_user, ready.pk)

    assert m.RequirementChange.objects.filter(requirement=pago, action="confirmar").count() == 1


# --- Una validada no cambia ----------------------------------------------------------------------


def test_once_validated_every_change_is_refused_by_the_functions(evaluator_user, ready):
    """REQ-027: validada, las funciones de negocio rechazan cualquier cambio."""
    service.validate(evaluator_user, ready.pk)
    pago = requirement_with(ready, PAGO)
    pending = ready.pending_items.first()

    with pytest.raises(review.ReviewRefused) as error:
        review.correct(evaluator_user, pago.pk, category="formal")
    assert error.value.reason == "version_not_draft"
    with pytest.raises(review.ReviewRefused):
        review.remove(evaluator_user, pago.pk)
    with pytest.raises(review.ReviewRefused):
        review.confirm(evaluator_user, [pago.pk])
    with pytest.raises(review.ReviewRefused):
        review.resolve_pending(evaluator_user, pending.pk)
    with pytest.raises(consequences.ChoiceRefused):
        consequences.choose(evaluator_user, pago.pk, consequence_type="desestimacion",
                            note="otra")
    with pytest.raises(service.ValidationRefused) as again:
        service.validate(evaluator_user, ready.pk)
    assert again.value.reason == "version_not_draft"
    with pytest.raises(service.ValidationRefused):
        service.discard(evaluator_user, ready.pk)


def test_once_validated_the_database_refuses_every_change(evaluator_user, ready):
    """REQ-027: validada, la base rechaza UPDATE, DELETE e INSERT sobre sus filas, aun
    por fuera de las funciones de negocio."""
    service.validate(evaluator_user, ready.pk)
    pago = requirement_with(ready, PAGO)
    quote = pago.quotes.first()

    for change in (
        lambda: m.Requirement.objects.filter(pk=pago.pk).update(category="formal"),
        lambda: m.RequirementQuote.objects.filter(pk=quote.pk).update(text="otro"),
        lambda: m.RequirementSource.objects.filter(requirement=pago).update(text="otro"),
        lambda: m.Consequence.objects.filter(requirement=pago).update(chosen_note="otro"),
        lambda: m.PendingItem.objects.filter(version=ready).update(reason="tabla"),
        lambda: m.Requirement.objects.filter(pk=pago.pk).delete(),
        lambda: m.MatrixVersion.objects.filter(pk=ready.pk).update(level="media"),
        lambda: m.Requirement.objects.create(
            version=ready, number=99, category="formal", origin="agregado"),
        lambda: m.Consequence.objects.create(
            requirement=pago, consequence_type="desestimacion", origin="persona"),
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            change()


# --- La página de una validada -------------------------------------------------------------------


def test_the_page_of_a_validated_version_has_no_draft_banner_and_shows_who_and_when(
        client, evaluator_user, ready):
    """REQ-032: la validada no muestra «BORRADOR INCOMPLETO» y sí su número, la fecha y el
    evaluador; el borrador sí lo muestra."""
    log_in(client, evaluator_user)
    draft_text = page_text(client.get(reverse("tenders:matrix", args=[ready.pk])))
    assert "BORRADOR INCOMPLETO" in draft_text
    assert "Consecuencias sin elegir: 0" in draft_text

    service.validate(evaluator_user, ready.pk)
    ready.refresh_from_db()
    text = page_text(client.get(reverse("tenders:matrix", args=[ready.pk])))

    assert "BORRADOR INCOMPLETO" not in text
    assert f"versión {ready.number}" in text
    assert timezone.localtime(ready.validated_at).strftime("%d/%m/%Y") in text
    assert evaluator_user.username in text


def test_the_summary_counts_the_consequences_not_yet_chosen(client, evaluator_user, case):
    """La página resume cuántos requisitos no quitados siguen sin consecuencia elegida."""
    total = case.requirements.count()
    pago = requirement_with(case, PAGO)
    consequences.choose(evaluator_user, pago.pk, consequence_type="aprobar_igual",
                        note="Motivo")
    log_in(client, evaluator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))

    assert f"Consecuencias sin elegir: {total - 1}" in text


# --- Descartar -----------------------------------------------------------------------------------


def test_discarding_a_draft_leaves_it_fixed_visible_and_allows_a_new_proposal(
        operator_user, evaluator_user, case):
    """Descartar deja la versión `discarded`, con quién y cuándo, fija en la base, y se
    puede pedir otra propuesta."""
    version = service.discard(evaluator_user, case.pk)

    assert version.status == "discarded"
    assert version.discarded_by == evaluator_user and version.discarded_at is not None
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VERSION)
    assert event.detail["action"] == "discarded" and event.detail["version"] == case.pk
    with pytest.raises(DatabaseError), transaction.atomic():
        m.Requirement.objects.filter(version=case).update(category="formal")
    assert matrix_page.panel(operator_user, case.procedure).can_request is True
    assert case.procedure.matrix_versions.filter(pk=case.pk).exists()


def test_an_operator_cannot_discard(operator_user, case):
    """Roles: descartar un borrador es del evaluador."""
    with pytest.raises(RoleRejected):
        service.discard(operator_user, case.pk)
    case.refresh_from_db()
    assert case.status == "draft"


# --- Versión nueva -------------------------------------------------------------------------------


def snapshot(version):
    """Todo el contenido de una versión, para comparar antes y después."""
    rows = []
    for r in version.requirements.order_by("number"):
        rows.append((
            r.number, r.category, r.items, r.state, r.origin, r.proposed,
            [(q.order, q.segment_id, q.char_start, q.char_end, q.text, q.scope,
              q.quote_flag) for q in r.quotes.order_by("order")],
            [(s.effect, s.segment_id, s.text, s.issued_on, s.quote_id)
             for s in r.sources.order_by("id")],
            [(c.consequence_type, c.grounds, c.chosen, c.chosen_by_id, c.chosen_note)
             for c in r.consequences.order_by("id")],
        ))
    pending = [(p.segment_id, p.reason, p.resolution, p.resolved_by_id)
               for p in version.pending_items.order_by("id")]
    return rows, pending, version.status, version.validated_at


def test_a_new_version_copies_everything_and_the_previous_stays_the_same(
        operator_user, evaluator_user, ready):
    """REQ-027: la versión nueva copia requisitos, citas (también las técnicas), fuentes,
    consecuencias elegidas y pendientes resueltos; la anterior no cambia."""
    validated = service.validate(evaluator_user, ready.pk)
    before = snapshot(validated)
    technical = validated.requirements.filter(category="tecnico")
    assert technical.exists() and any(r.quotes.count() >= 1 for r in technical)

    new = service.open_new_version(operator_user, validated.procedure_id)

    assert new.status == "draft" and new.number == validated.number + 1
    assert new.based_on == validated and new.level == validated.level
    assert new.created_by == operator_user and new.run_id is None
    assert snapshot(validated) == before
    assert new.requirements.count() == validated.requirements.count()
    for old in validated.requirements.all():
        copy = new.requirements.get(number=old.number)
        assert copy.previous == old
        assert copy.category == old.category and copy.items == old.items
        assert copy.state == old.state == "confirmado"
        assert [q.text for q in copy.quotes.order_by("order")] == [
            q.text for q in old.quotes.order_by("order")]
        assert [q.scope for q in copy.quotes.order_by("order")] == [
            q.scope for q in old.quotes.order_by("order")]
        chosen = copy.consequences.get()
        assert chosen.chosen and chosen.chosen_by == evaluator_user
        assert chosen.consequence_type == "aprobar_igual"
        assert chosen.chosen_note == "Motivo de prueba"
    pago = new.requirements.get(number=requirement_with(validated, PAGO).number)
    source = pago.sources.get()
    assert source.quote == pago.quotes.get() and source.effect == "modifica"
    assert new.pending_items.count() == validated.pending_items.count() > 0
    assert not new.pending_items.filter(resolved_at__isnull=True).exists()
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VERSION,
                                   detail__action="opened")
    assert event.detail["based_on"] == validated.pk and event.detail["version"] == new.pk
    assert event.detail["copied"]["requirements"] == new.requirements.count()


def test_the_new_version_is_a_working_draft_and_can_be_validated_again(
        client, operator_user, evaluator_user, ready):
    """La versión nueva es un borrador editable; se la corrige, se valida y la anterior
    sigue como estaba."""
    validated = service.validate(evaluator_user, ready.pk)
    before = snapshot(validated)
    new = service.open_new_version(evaluator_user, validated.procedure_id)
    pago = new.requirements.get(number=requirement_with(validated, PAGO).number)

    review.correct(operator_user, pago.pk, category="formal")
    pago.refresh_from_db()
    assert pago.state == "propuesto" and pago.category == "formal"
    log_in(client, evaluator_user)
    text = page_text(client.get(reverse("tenders:matrix", args=[new.pk])))
    assert "BORRADOR INCOMPLETO" in text
    assert "<option" in text  # los tramos del pliego de origen se pueden elegir
    second = service.validate(evaluator_user, new.pk)

    assert second.status == "validated"
    assert snapshot(validated) == before
    assert requirement_with(validated, PAGO).category == "economico"
    assert m.RequirementChange.objects.filter(requirement=pago, action="confirmar").exists()


def test_a_new_version_needs_a_validated_one_and_no_open_draft(
        operator_user, evaluator_user, case):
    """Sin validada no hay sobre qué abrir; con un borrador abierto, tampoco."""
    with pytest.raises(service.ValidationRefused) as error:
        service.open_new_version(operator_user, case.procedure_id)
    assert error.value.reason == "no_validated_version"

    finish_review(evaluator_user, case)
    service.validate(evaluator_user, case.pk)
    service.open_new_version(operator_user, case.procedure_id)
    with pytest.raises(service.ValidationRefused) as again:
        service.open_new_version(operator_user, case.procedure_id)
    assert again.value.reason == "draft_open"
    assert rejected("draft_open", EventType.MATRIX_VERSION).count() == 1
    assert case.procedure.matrix_versions.count() == 2


def test_the_new_version_opens_over_the_last_validated(operator_user, evaluator_user, ready):
    """Se abre sobre la última validada, aunque haya descartadas después de otras."""
    first = service.validate(evaluator_user, ready.pk)
    second = service.open_new_version(operator_user, first.procedure_id)
    service.discard(evaluator_user, second.pk)

    third = service.open_new_version(operator_user, first.procedure_id)

    assert third.based_on == first and third.number == 3


def test_a_user_without_a_commission_role_cannot_open_one(no_commission_user, ready,
                                                          evaluator_user):
    """Un usuario sin rol de la Comisión no abre versiones."""
    service.validate(evaluator_user, ready.pk)
    with pytest.raises(RoleRejected):
        service.open_new_version(no_commission_user, ready.procedure_id)
    assert ready.procedure.matrix_versions.count() == 1


# --- Pantalla ------------------------------------------------------------------------------------


def test_the_buttons_by_state_and_role(client, operator_user, evaluator_user, ready):
    """Botones: el evaluador ve «Validar» y «Descartar» en el borrador; el operador no;
    la validada ofrece la versión nueva a ambos."""
    url = reverse("tenders:matrix", args=[ready.pk])
    validate_url = reverse("tenders:validate", args=[ready.pk])
    log_in(client, operator_user)
    assert validate_url not in page_text(client.get(url))
    log_in(client, evaluator_user)
    text = page_text(client.get(url))
    assert validate_url in text and reverse("tenders:discard", args=[ready.pk]) in text

    service.validate(evaluator_user, ready.pk)
    new_url = reverse("tenders:open_new_version", args=[ready.procedure_id])
    assert new_url in page_text(client.get(url))
    assert new_url in page_text(client.get(
        reverse("tenders:procedure", args=[ready.procedure_id])))
    log_in(client, operator_user)
    assert new_url in page_text(client.get(url))


def test_validating_from_the_screen_and_the_refusal_with_its_reason(
        client, operator_user, evaluator_user, case):
    """La pantalla valida y, si no se puede, vuelve a la matriz diciendo por qué."""
    url = reverse("tenders:validate", args=[case.pk])
    log_in(client, operator_user)
    assert client.post(url).status_code == 403

    log_in(client, evaluator_user)
    refused = client.post(url)
    assert refused.status_code == 400
    assert "No se puede validar" in page_text(refused)
    case.refresh_from_db()
    assert case.status == "draft"

    finish_review(evaluator_user, case)
    done = client.post(url)
    assert done.status_code == 302
    case.refresh_from_db()
    assert case.status == "validated"


def test_opening_and_discarding_from_the_screen(client, operator_user, evaluator_user,
                                                ready):
    """La pantalla abre la versión nueva (el operador también) y el evaluador descarta."""
    service.validate(evaluator_user, ready.pk)
    log_in(client, operator_user)
    response = client.post(reverse("tenders:open_new_version", args=[ready.procedure_id]))
    new = ready.procedure.matrix_versions.get(number=2)
    assert response.status_code == 302
    assert response.url == reverse("tenders:matrix", args=[new.pk])

    assert client.post(reverse("tenders:discard", args=[new.pk])).status_code == 403
    log_in(client, evaluator_user)
    response = client.post(reverse("tenders:discard", args=[new.pk]))
    assert response.status_code == 302
    new.refresh_from_db()
    assert new.status == "discarded"


# --- Ajustes de la verificación (O1 a O4) -----------------------------------------------------


def test_a_request_in_progress_blocks_opening_a_new_version(
        operator_user, evaluator_user, ready):
    """O3: con una propuesta en espera o en curso no se abre una versión nueva; queda
    registrado como rechazado, igual que `request_matrix`."""
    from evaluon.tenders.services import matrix

    validated = service.validate(evaluator_user, ready.pk)
    matrix.request_matrix(operator_user, validated.procedure)

    with pytest.raises(service.ValidationRefused) as error:
        service.open_new_version(operator_user, validated.procedure_id)

    assert error.value.reason == "request_in_progress"
    assert rejected("request_in_progress", EventType.MATRIX_VERSION).count() == 1
    assert validated.procedure.matrix_versions.count() == 1


def test_a_matrix_with_no_current_requirement_is_not_validated(evaluator_user, case):
    """O4: con todos los requisitos quitados no se valida (`empty_matrix`)."""
    for requirement in case.requirements.all():
        review.remove(evaluator_user, requirement.pk)
    finish_review(evaluator_user, case)

    with pytest.raises(service.ValidationRefused) as error:
        service.validate(evaluator_user, case.pk)

    assert error.value.reason == "empty_matrix"
    assert "ningún requisito" in str(error.value)
    assert rejected("empty_matrix").count() == 1
    case.refresh_from_db()
    assert case.status == "draft"


def test_the_validated_page_says_when_and_by_whom_as_another_user_sees_it(
        client, operator_user, evaluator_user, ready):
    """O1, REQ-032: la página de la validada dice «validada el DD/MM/AAAA por <usuario>»,
    también para quien no la validó."""
    version = service.validate(evaluator_user, ready.pk)
    version.refresh_from_db()
    day = timezone.localtime(version.validated_at).strftime("%d/%m/%Y")
    expected = (f"versión {version.number} · validada el {day} por "
                f"{evaluator_user.username}")
    log_in(client, operator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[version.pk])))

    assert expected in text
    header = text.split("Encabezado")[1].split("Resumen")[0]
    assert f"el {day} por {evaluator_user.username}" in header


def test_the_new_version_copies_the_removed_requirements_too(
        operator_user, evaluator_user, case):
    """A13: la copia conserva los requisitos quitados, con su estado."""
    pago = requirement_with(case, PAGO)
    review.remove(evaluator_user, pago.pk)
    finish_review(evaluator_user, case)
    validated = service.validate(evaluator_user, case.pk)

    new = service.open_new_version(operator_user, validated.procedure_id)

    copy = new.requirements.get(number=pago.number)
    assert copy.state == "quitado" and copy.previous.pk == pago.pk
    assert new.requirements.count() == validated.requirements.count()


def test_the_new_version_opens_over_the_last_of_several_validated_ones(
        operator_user, evaluator_user, ready):
    """A16: con dos validadas, la versión nueva sale de la segunda."""
    first = service.validate(evaluator_user, ready.pk)
    second = service.open_new_version(operator_user, first.procedure_id)
    second = service.validate(evaluator_user, second.pk)

    third = service.open_new_version(operator_user, first.procedure_id)

    assert third.based_on == second and third.number == 3
    assert third.requirements.first().previous.version_id == second.pk


def test_the_new_version_inherits_a_level_other_than_the_default(
        operator_user, evaluator_user, ready):
    """A17: el nivel de la versión nueva es el de su origen."""
    m.MatrixVersion.objects.filter(pk=ready.pk).update(level="exigente")
    validated = service.validate(evaluator_user, ready.pk)

    new = service.open_new_version(operator_user, validated.procedure_id)

    assert validated.level == "exigente" and new.level == "exigente"


def test_a_failure_in_the_middle_of_validating_leaves_nothing_changed(
        evaluator_user, ready, monkeypatch):
    """A21: validar es atómico: si falla a la mitad, ningún requisito queda confirmado,
    no hay historial y la versión sigue en borrador."""
    original = review._record
    calls = []

    def failing(*args, **kwargs):
        if calls:
            raise RuntimeError("falla de prueba")
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(review, "_record", failing)

    with pytest.raises(RuntimeError):
        service.validate(evaluator_user, ready.pk)

    assert calls
    ready.refresh_from_db()
    assert ready.status == "draft" and ready.validated_by is None
    assert not ready.requirements.exclude(state="propuesto").exists()
    assert not m.RequirementChange.objects.filter(action="confirmar").exists()
    assert not AuditEvent.objects.filter(event_type=EventType.MATRIX_VALIDATION,
                                         outcome=Outcome.OK).exists()


def test_the_new_version_offers_the_tender_segments_to_choose(
        operator_user, evaluator_user, ready):
    """A27: el borrador abierto sobre otro ofrece los mismos tramos que el original."""
    options = matrix_page.matrix_page(evaluator_user, ready.pk).segment_options
    assert options
    validated = service.validate(evaluator_user, ready.pk)
    new = service.open_new_version(operator_user, validated.procedure_id)

    assert matrix_page.matrix_page(operator_user, new.pk).segment_options == options
    second = service.validate(evaluator_user, new.pk)
    newer = service.open_new_version(operator_user, second.procedure_id)
    assert matrix_page.matrix_page(operator_user, newer.pk).segment_options == options


def test_the_new_version_button_is_only_on_the_last_validated(
        client, operator_user, evaluator_user, ready):
    """A29: el botón de versión nueva aparece solo en la última validada y sin borrador."""
    first = service.validate(evaluator_user, ready.pk)
    second = service.open_new_version(operator_user, first.procedure_id)
    url = reverse("tenders:open_new_version", args=[first.procedure_id])
    log_in(client, operator_user)
    assert url not in page_text(client.get(reverse("tenders:matrix", args=[first.pk])))
    assert not matrix_page.matrix_page(operator_user, first.pk).can_open_new

    second = service.validate(evaluator_user, second.pk)

    assert url not in page_text(client.get(reverse("tenders:matrix", args=[first.pk])))
    assert url in page_text(client.get(reverse("tenders:matrix", args=[second.pk])))


def test_the_new_version_copies_the_reference_to_the_original(
        operator_user, evaluator_user, ready):
    """REQ-031: una versión nueva copia el original en un anexo de cada fuente."""
    annex = ready.requirements.get(sources__isnull=False).quotes.get().segment
    m.RequirementSource.objects.filter(requirement__version=ready).update(
        original_segment=annex, original_char_start=2, original_char_end=6)
    validated = service.validate(evaluator_user, ready.pk)

    new = service.open_new_version(operator_user, validated.procedure_id)

    copied = m.RequirementSource.objects.get(requirement__version=new)
    assert (copied.original_segment_id, copied.original_char_start,
            copied.original_char_end) == (annex.pk, 2, 6)
