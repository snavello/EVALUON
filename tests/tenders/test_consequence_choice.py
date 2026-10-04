"""Elegir la consecuencia en la pantalla (REQ-029; plan 003, "Consecuencias"; principio P3;
T-081).

Pliegos y normas sintéticos (P4). Las opciones sugeridas se crean directamente, como las
deja la pasada de consecuencias de T-080 (sus tests están en `test_consequences.py`).
"""

import html

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import consequences as service
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
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    return requested.run.version


def requirement_with(version, text):
    for row in m.Requirement.objects.filter(version=version).order_by("number"):
        if any(text in q.text for q in row.quotes.all()):
            return row
    raise AssertionError(text)


def segment_with(version, text):
    reading_ids = [d["reading"] for d in version.run.documents]
    return m.Segment.objects.filter(reading_id__in=reading_ids,
                                    text__contains=text).first()


def suggest(requirement, kind, grounds):
    return m.Consequence.objects.create(
        requirement=requirement, consequence_type=kind, grounds=grounds,
        origin="sistema")


def pliego_ground(segment):
    return {"source": "pliego", "reading": segment.reading_id, "segment": segment.pk,
            "key": segment.key, "char_start": segment.char_start,
            "char_end": segment.char_end}


@pytest.fixture
def garantia(case, two_regimes):
    """El requisito de la garantía con una sugerencia fundada en el pliego y otra fundada
    en una unidad de la norma."""
    requirement = requirement_with(case, "garantía")
    unit = two_regimes.new_units["anexo/art-2"]
    desest = suggest(requirement, "desestimacion",
                     [pliego_ground(segment_with(case, GARANTIA))])
    intim = suggest(requirement, "intimacion_subsanar",
                    [{"source": "norma", "unit": unit.pk}])
    return requirement, desest, intim, unit


def rejected(reason):
    return AuditEvent.objects.filter(
        event_type=EventType.CONSEQUENCE_CHOICE, outcome=Outcome.REJECTED,
        detail__reason=reason)


def page_text(response):
    return html.unescape(response.content.decode())


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


# --- La pantalla muestra cada opción con su fundamento literal ----------------------------------


def test_the_page_shows_each_option_with_the_literal_text_of_its_ground(
        client, evaluator_user, case, garantia):
    """REQ-029, P3: cada opción se ve con el texto literal de su fundamento: el tramo del
    pliego con su ubicación y la unidad de la norma con su cita."""
    requirement, desest, intim, unit = garantia
    segment = segment_with(case, GARANTIA)
    log_in(client, evaluator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))

    assert "Desestimación sin posibilidad de subsanar" in text
    assert "Intimación a subsanar" in text
    assert segment.reading.canonical_text[segment.char_start:segment.char_end] in text
    assert unit.text in text
    assert unit.reading.document.norm.citation in text
    assert "Sugerida por el sistema" in text
    assert reverse("tenders:consequence_choose", args=[requirement.pk]) in text


def test_undetermined_is_shown_as_such_and_cannot_be_picked(
        client, evaluator_user, case):
    """REQ-029: un requisito sin sugerencia con fundamento muestra «No determinada», sin
    casilla para elegirla."""
    requirement = requirement_with(case, PAGO)
    undetermined = requirement.consequences.get(consequence_type="no_determinada")
    log_in(client, evaluator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))

    assert "No determinada" in text
    assert f'name="option" value="{undetermined.pk}"' not in text


def test_the_operator_sees_the_options_but_not_the_choice_form(
        client, operator_user, case, garantia):
    """REQ-029: elegir es del evaluador; el operador ve las opciones sin formulario."""
    requirement = garantia[0]
    log_in(client, operator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))

    assert "Desestimación sin posibilidad de subsanar" in text
    assert reverse("tenders:consequence_choose", args=[requirement.pk]) not in text


# --- Elegir una sugerencia: su fundamento es el motivo ------------------------------------------


def test_accepting_a_suggestion_needs_no_note_and_records_who_when(
        evaluator_user, garantia):
    """REQ-029: aceptar una sugerencia del sistema no pide escribir nada; queda con quién,
    cuándo y el hecho `consequence_choice` con el fundamento."""
    requirement, desest, _, _ = garantia

    chosen = service.choose(evaluator_user, requirement.pk, option=desest.pk)

    chosen.refresh_from_db()
    assert chosen.pk == desest.pk and chosen.chosen
    assert chosen.chosen_by == evaluator_user and chosen.chosen_at is not None
    event = AuditEvent.objects.get(event_type=EventType.CONSEQUENCE_CHOICE)
    assert event.outcome == Outcome.OK and event.user == evaluator_user
    assert event.detail["type"] == "desestimacion"
    assert event.detail["suggested_by_system"] is True
    assert event.detail["grounds"] == desest.grounds
    change = m.RequirementChange.objects.get(requirement=requirement,
                                             action="elegir_consecuencia")
    assert change.user == evaluator_user and change.event == event


def test_choosing_the_type_of_a_suggestion_is_accepting_it(evaluator_user, garantia):
    """REQ-029: elegir por tipo uno que el sistema ya sugirió es aceptar esa sugerencia."""
    requirement, desest, _, _ = garantia

    chosen = service.choose(evaluator_user, requirement.pk,
                            consequence_type="desestimacion")

    assert chosen.pk == desest.pk
    assert not m.Consequence.objects.filter(requirement=requirement,
                                            origin="persona").exists()


def test_choosing_again_replaces_the_choice_and_keeps_the_history(
        evaluator_user, garantia):
    """REQ-029: una elección nueva reemplaza a la anterior; la anterior queda en el
    historial."""
    requirement, desest, intim, _ = garantia
    service.choose(evaluator_user, requirement.pk, option=desest.pk)

    service.choose(evaluator_user, requirement.pk, option=intim.pk)

    desest.refresh_from_db()
    intim.refresh_from_db()
    assert not desest.chosen and intim.chosen
    last = m.RequirementChange.objects.filter(
        requirement=requirement, action="elegir_consecuencia").order_by("-id").first()
    assert last.before["type"] == "desestimacion"
    assert last.after["type"] == "intimacion_subsanar"


# --- Elegir otra: motivo obligatorio ------------------------------------------------------------


def test_another_type_without_a_note_is_rejected(evaluator_user, garantia):
    """REQ-029: elegir un tipo que el sistema no sugirió sin escribir el motivo se rechaza."""
    requirement = garantia[0]

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, consequence_type="aprobar_igual")

    assert error.value.reason == "note_required"
    assert rejected("note_required").count() == 1
    assert not m.Consequence.objects.filter(requirement=requirement, chosen=True).exists()
    assert not m.Consequence.objects.filter(requirement=requirement,
                                            origin="persona").exists()


def test_another_type_with_a_note_is_chosen_and_keeps_the_note(evaluator_user, garantia):
    """REQ-029: la elección de otro tipo queda con quién, cuándo y el motivo."""
    requirement = garantia[0]

    chosen = service.choose(evaluator_user, requirement.pk,
                            consequence_type="aprobar_igual",
                            note="  La diferencia no afecta la comparación.  ")

    assert chosen.origin == "persona" and chosen.chosen_by == evaluator_user
    assert chosen.chosen_note == "La diferencia no afecta la comparación."
    event = AuditEvent.objects.get(event_type=EventType.CONSEQUENCE_CHOICE)
    assert event.detail["suggested_by_system"] is False
    assert event.detail["note"] == chosen.chosen_note


def test_a_conditional_approval_without_a_condition_is_rejected(
        evaluator_user, garantia):
    """REQ-029: la aprobación condicionada exige escribir la condición."""
    requirement = garantia[0]

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk,
                       consequence_type="aprobacion_condicionada")

    assert error.value.reason == "condition_required"
    assert rejected("condition_required").count() == 1

    chosen = service.choose(evaluator_user, requirement.pk,
                            consequence_type="aprobacion_condicionada",
                            note="Presentar la constancia antes de la adjudicación.")
    assert chosen.chosen_note == "Presentar la constancia antes de la adjudicación."


def test_undetermined_cannot_be_chosen_by_type_or_by_option(evaluator_user, case):
    """REQ-029: «no determinada» no se puede elegir."""
    requirement = requirement_with(case, PAGO)
    undetermined = requirement.consequences.get(consequence_type="no_determinada")

    with pytest.raises(service.ChoiceRefused) as by_type:
        service.choose(evaluator_user, requirement.pk,
                       consequence_type="no_determinada", note="motivo")
    with pytest.raises(service.ChoiceRefused) as by_option:
        service.choose(evaluator_user, requirement.pk, option=undetermined.pk)

    assert by_type.value.reason == by_option.value.reason == "undetermined_not_choosable"
    undetermined.refresh_from_db()
    assert not undetermined.chosen


def test_an_option_of_another_requirement_is_rejected(evaluator_user, garantia, case):
    """REQ-029: una opción de otro requisito no se puede elegir."""
    other = requirement_with(case, PAGO)

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, other.pk, option=garantia[1].pk)

    assert error.value.reason == "option_not_found"


# --- Tramo del pliego con cita verificada -------------------------------------------------------


def test_other_from_the_tender_without_a_segment_is_rejected(evaluator_user, case):
    """REQ-029: `otra_pliego` elegida por una persona sin sugerencia del sistema necesita
    el tramo del pliego."""
    requirement = requirement_with(case, PAGO)

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, consequence_type="otra_pliego",
                       note="Lo prevé el pliego.")

    assert error.value.reason == "segment_not_found"
    assert not m.Consequence.objects.filter(requirement=requirement,
                                            origin="persona").exists()


def test_a_quote_that_is_not_in_the_segment_is_rejected(evaluator_user, case):
    """REQ-029, REQ-025: el fragmento del pliego se verifica palabra por palabra."""
    requirement = requirement_with(case, PAGO)
    segment = segment_with(case, PAGO)

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk,
                       consequence_type="consultar_oferente",
                       note="Se puede consultar.", segment=segment.pk,
                       quote="un texto que el pliego no dice")

    assert error.value.reason == "quote_not_in_segment"
    assert rejected("quote_not_in_segment").count() == 1


def test_a_verified_quote_becomes_the_ground_of_the_option(client, evaluator_user, case):
    """REQ-029: con tramo y fragmento verificados la opción queda con ese fundamento, y la
    pantalla muestra su texto literal."""
    requirement = requirement_with(case, PAGO)
    segment = segment_with(case, PAGO)

    chosen = service.choose(evaluator_user, requirement.pk,
                            consequence_type="otra_pliego", note="Lo prevé el pliego.",
                            segment=segment.pk, quote="a los 90   días\ncorridos")

    [ground] = chosen.grounds
    canonical = segment.reading.canonical_text
    assert ground["source"] == "pliego" and ground["segment"] == segment.pk
    assert " ".join(canonical[ground["char_start"]:ground["char_end"]].split()) == (
        "a los 90 días corridos")
    log_in(client, evaluator_user)
    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    assert canonical[ground["char_start"]:ground["char_end"]] in text
    assert "Propuesta por una persona" in text


def test_a_suggested_consult_is_accepted_without_choosing_a_segment(
        evaluator_user, case):
    """REQ-029: si el sistema sugirió `consultar_oferente`, su cita ya está."""
    requirement = requirement_with(case, PAGO)
    suggested = suggest(requirement, "consultar_oferente",
                        [pliego_ground(segment_with(case, PAGO))])

    chosen = service.choose(evaluator_user, requirement.pk, option=suggested.pk)

    assert chosen.pk == suggested.pk and chosen.chosen


# --- Roles y pantalla ---------------------------------------------------------------------------


def test_an_operator_cannot_choose(operator_user, garantia):
    """REQ-029, P3: elegir la consecuencia es del evaluador; el rechazo queda registrado."""
    requirement, desest, _, _ = garantia

    with pytest.raises(RoleRejected):
        service.choose(operator_user, requirement.pk, option=desest.pk)

    desest.refresh_from_db()
    assert not desest.chosen
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()
    assert not AuditEvent.objects.filter(event_type=EventType.CONSEQUENCE_CHOICE).exists()


def test_an_operator_posting_a_choice_gets_403(client, operator_user, garantia):
    """REQ-029: por la pantalla, el operador recibe «acceso denegado»."""
    requirement, desest, _, _ = garantia
    log_in(client, operator_user)

    response = client.post(reverse("tenders:consequence_choose", args=[requirement.pk]),
                           {"option": desest.pk})

    assert response.status_code == 403
    desest.refresh_from_db()
    assert not desest.chosen


def test_the_evaluator_chooses_from_the_page(client, evaluator_user, case, garantia):
    """REQ-029: el evaluador elige desde la página y la ve elegida, con su nombre."""
    requirement, desest, _, _ = garantia
    log_in(client, evaluator_user)

    response = client.post(reverse("tenders:consequence_choose", args=[requirement.pk]),
                           {"option": desest.pk, "note": ""})

    assert response.status_code == 302
    assert response["Location"].endswith(f"#requisito-{requirement.number}")
    text = page_text(client.get(response["Location"]))
    assert f"Elegida por {evaluator_user.username}" in text


def test_a_refused_post_shows_the_reason_and_changes_nothing(
        client, evaluator_user, case, garantia):
    """REQ-029: una elección rechazada vuelve a la matriz con el motivo."""
    requirement = garantia[0]
    log_in(client, evaluator_user)

    response = client.post(reverse("tenders:consequence_choose", args=[requirement.pk]),
                           {"consequence_type": "aprobar_igual", "note": ""})

    assert response.status_code == 400
    assert "Escriba el motivo de la elección" in page_text(response)
    assert not m.Consequence.objects.filter(requirement=requirement, chosen=True).exists()


# --- Cierre de la verificación (F1, O1, O2, O3, A24) -------------------------------------------


def test_option_and_a_different_type_together_are_rejected(evaluator_user, garantia):
    """REQ-029, P3: una opción y un tipo distintos juntos se rechazan; no se descarta uno
    en silencio."""
    requirement, desest, _, _ = garantia

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, option=desest.pk,
                       consequence_type="aprobar_igual", note="Otro motivo.")

    assert error.value.reason == "ambiguous_choice"
    assert rejected("ambiguous_choice").count() == 1
    assert not m.Consequence.objects.filter(requirement=requirement, chosen=True).exists()


def _forms_of(requirement, text):
    marker = f"/requisitos/{requirement.pk}/consecuencia/"
    return [chunk for chunk in text.split("<form")[1:] if marker in chunk.split(">")[0]]


def test_after_a_choice_the_form_can_pick_another_type_with_its_note(
        client, evaluator_user, case, garantia):
    """REQ-029, P3: con el POST de los formularios reales, después de una elección, elegir
    otro tipo con motivo deja elegido el tipo nuevo con ese motivo."""
    requirement, desest, _, _ = garantia
    log_in(client, evaluator_user)
    url = reverse("tenders:consequence_choose", args=[requirement.pk])
    client.post(url, {"option": desest.pk})

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))
    forms = _forms_of(requirement, text)
    assert forms
    for form in forms:  # ningún formulario junta las dos vías
        assert not ('name="option"' in form and 'name="consequence_type"' in form)
    other = next(f for f in forms if 'name="consequence_type"' in f)
    assert 'name="option"' not in other
    response = client.post(url, {"consequence_type": "aprobar_igual",
                                 "note": "No afecta la comparación."})

    assert response.status_code == 302
    chosen = m.Consequence.objects.get(requirement=requirement, chosen=True)
    assert chosen.consequence_type == "aprobar_igual"
    assert chosen.chosen_note == "No afecta la comparación."
    desest.refresh_from_db()
    assert not desest.chosen and desest.chosen_note == ""


def test_a_ground_from_another_clause_shows_its_exact_partial_cut(
        client, evaluator_user, case, garantia):
    """REQ-029, P3: un fundamento de otra cláusula, con recorte parcial, se muestra con el
    texto literal exacto."""
    requirement = garantia[0]
    segment = segment_with(case, PAGO)
    start, end = segment.char_start + 3, segment.char_end - 4
    suggest(requirement, "otra_pliego", [{**pliego_ground(segment), "char_start": start,
                                          "char_end": end}])
    cut = segment.reading.canonical_text[start:end]
    log_in(client, evaluator_user)

    text = page_text(client.get(reverse("tenders:matrix", args=[case.pk])))

    assert f'<blockquote class="literal">{cut}</blockquote>' in text


@pytest.mark.parametrize("status", ["discarded", "validated"])
def test_a_version_that_is_not_a_draft_cannot_be_chosen_on(
        evaluator_user, case, garantia, status):
    """REQ-029, REQ-027: en una versión descartada o validada no se elige."""
    from django.utils import timezone

    requirement, desest, _, _ = garantia
    when = {"discarded": ("discarded_at", "discarded_by"),
            "validated": ("validated_at", "validated_by")}[status]
    m.MatrixVersion.objects.filter(pk=case.pk).update(
        status=status, **{when[0]: timezone.now(), when[1]: evaluator_user})

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, option=desest.pk)

    assert error.value.reason == "version_not_draft"
    assert rejected("version_not_draft").count() == 1
    desest.refresh_from_db()
    assert not desest.chosen


def test_a_removed_requirement_cannot_be_chosen_on(evaluator_user, garantia):
    """REQ-029: un requisito quitado no se elige."""
    from evaluon.tenders.services import review

    requirement, desest, _, _ = garantia
    review.remove(evaluator_user, requirement.pk)

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, option=desest.pk)

    assert error.value.reason == "requirement_removed"


@pytest.mark.parametrize("kind", ["consultar_oferente", "otra_pliego"])
def test_a_system_option_without_grounds_asks_for_the_quote(evaluator_user, case, kind):
    """REQ-029: defensa en profundidad: una sugerencia del sistema que exige la cita del
    pliego y no la trae se rechaza."""
    requirement = requirement_with(case, PAGO)
    bare = suggest(requirement, kind, [])

    with pytest.raises(service.ChoiceRefused) as error:
        service.choose(evaluator_user, requirement.pk, option=bare.pk)

    assert error.value.reason == "pliego_ground_required"
    bare.refresh_from_db()
    assert not bare.chosen
