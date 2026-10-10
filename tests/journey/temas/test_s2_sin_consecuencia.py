"""Pestaña «Pliego y matriz»: requisitos cuyo pliego no indica consecuencia y aviso de validación
(REQ-081, REQ-029 de la 003; plan 014, T-232, puntos P-3 y P-7 de la revisión C). Todo el material
es inventado (P4)."""

import html as htmllib
import re

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.journey.temas import s2_matriz_acciones as acciones
from evaluon.tenders import models as m
from evaluon.tenders.services import consequences as service
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s2_matriz_actions import (  # noqa: F401  (fixtures y ayudas)
    board,
    decide_everything,
    follow,
    log_in,
    tab,
    url,
)
from tests.journey.temas.test_s2_matriz import two_versions  # noqa: F401

pytestmark = pytest.mark.django_db

SIN = "sin_consecuencia"


def undetermined_only(requirement):
    """Lo que deja el sistema cuando no halla consecuencia: solo «No determinada»."""
    return m.Consequence.objects.create(requirement=requirement, consequence_type="no_determinada",
                                        origin="sistema", grounds=[])


def suggested(requirement, kind="desestimacion"):
    segment = requirement.quotes.order_by("order").first().segment
    return m.Consequence.objects.create(
        requirement=requirement, consequence_type=kind, origin="sistema",
        grounds=[{"source": "pliego", "reading": segment.reading_id, "segment": segment.pk,
                  "key": segment.key, "char_start": segment.char_start,
                  "char_end": segment.char_start + 5}])


def form_of(html, requirement):
    """El formulario «Elegir la consecuencia» de la fila del requisito."""
    action = url("s2_consecuencia", requirement.version.procedure, requirement.pk)
    start = html.index(f'action="{action}"')
    return html[start:html.index("</form>", start)]


# --- P-3: «El pliego no indica consecuencia» como opción válida ----------------------------------


def test_the_commission_can_choose_that_the_pliego_indicates_no_consequence(
        evaluator_user, board):
    """REQ-081: «El pliego no indica consecuencia» se elige sin motivo y sin inventar otro tipo; queda
    quién y cuándo (P3)."""
    row = board.rows[0]
    undetermined_only(row)

    picked = service.choose(evaluator_user, row.pk, consequence_type=SIN)

    assert picked.consequence_type == SIN and picked.chosen
    assert picked.chosen_by == evaluator_user and picked.chosen_at and picked.chosen_note == ""
    assert picked.get_consequence_type_display() == "El pliego no indica consecuencia"
    assert row.consequences.get(consequence_type="no_determinada").chosen is False
    event = AuditEvent.objects.filter(event_type=EventType.CONSEQUENCE_CHOICE).last()
    assert event.detail["type"] == SIN and event.user == evaluator_user


def test_the_only_proposal_undetermined_comes_preselected_as_the_pliego_indicating_none(
        client, procedure, board, evaluator_user):
    """REQ-081: si la única propuesta del sistema es «No determinada», la fila ofrece «El pliego no
    indica consecuencia» ya marcada, como propuesta; la Comisión la confirma y la matriz queda
    con consecuencia elegida."""
    row = board.rows[0]
    undetermined_only(row)
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    form = form_of(html, row)
    radio = re.search(r'<input type="radio" name="option" value="sin_consecuencia"([^>]*)>', form)
    assert radio and "checked" in radio.group(1)
    assert "El pliego no indica consecuencia" in form
    assert "propuesta del sistema" in htmllib.unescape(form)

    ok, text = follow(client, client.post(url("s2_consecuencia", procedure, row.pk),
                                          {"option": SIN}))

    assert ok and "El pliego no indica consecuencia" in text
    chosen = row.consequences.get(chosen=True)
    assert chosen.consequence_type == SIN and chosen.chosen_by == evaluator_user
    html = client.get(tab(procedure)).content.decode()
    assert re.search(r'<input type="radio" name="option" value="sin_consecuencia"[^>]*checked',
                     form_of(html, row))
    assert "elegida" in htmllib.unescape(form_of(html, row))


def test_with_a_real_proposal_the_option_is_offered_but_not_preselected(
        client, procedure, board, evaluator_user):
    """REQ-081: si el sistema propuso una consecuencia del pliego, «El pliego no indica
    consecuencia» sigue disponible, sin marcar."""
    row = board.rows[1]
    suggested(row)
    undetermined_only(row)
    log_in(client, evaluator_user)
    form = form_of(client.get(tab(procedure)).content.decode(), row)
    radio = re.search(r'<input type="radio" name="option" value="sin_consecuencia"([^>]*)>', form)
    assert radio and "checked" not in radio.group(1)


def test_an_explicit_other_type_wins_over_the_preselected_option(
        client, procedure, board, evaluator_user):
    """REQ-081: la opción marcada de antemano es solo un valor por omisión; si la Comisión elige
    otro tipo y escribe su motivo, vale lo que eligió."""
    row = board.rows[0]
    undetermined_only(row)
    log_in(client, evaluator_user)
    ok, text = follow(client, client.post(url("s2_consecuencia", procedure, row.pk), {
        "option": SIN, "consequence_type": "desestimacion", "note": "Lo dice la cláusula 9."}))
    assert ok, text
    assert row.consequences.get(chosen=True).consequence_type == "desestimacion"


def test_the_matrix_validates_when_requirements_have_no_consequence_in_the_pliego(
        client, procedure, board, evaluator_user):
    """REQ-081: con todo decidido y algunos requisitos sin consecuencia en el pliego, la matriz se
    valida igual."""
    log_in(client, evaluator_user)
    rows = list(board.draft.requirements.exclude(state__in=("quitado", "sugerido")))
    for row in rows[:4]:
        undetermined_only(row)
        client.post(url("s2_consecuencia", procedure, row.pk), {"option": SIN})
    for row in rows[4:]:
        client.post(url("s2_consecuencia", procedure, row.pk), {
            "consequence_type": "desestimacion", "note": "Lo dice el pliego."})
    client.post(url("s2_confirmar", procedure), {"requirement": [r.pk for r in board.rows]})
    client.post(url("s2_sugerencia_quitar", procedure, board.suggestion.pk))
    client.post(url("s2_tramo_revisado", procedure, board.pending.pk))

    ok, text = follow(client, client.post(url("s2_validar", procedure, board.draft.pk)))

    board.draft.refresh_from_db()
    assert ok and board.draft.status == "validated", text


def test_a_system_cannot_have_chosen_undetermined_but_a_person_chooses_the_new_type():
    """REQ-081: «No determinada» sigue sin elegirse (decisión de la 003); lo que se elige es
    «El pliego no indica consecuencia», que es otro tipo."""
    assert "no_determinada" not in service.CHOOSABLE_TYPES
    assert SIN in service.CHOOSABLE_TYPES


# --- P-7: el aviso de validación dice lo que hace el servicio -------------------------------------


def test_requirements_without_confirming_do_not_block_the_validation(
        client, procedure, board, evaluator_user):
    """REQ-081: el servicio de validación confirma solo los requisitos propuestos; el aviso no
    los cuenta como lo que traba y el botón de validar queda encendido."""
    log_in(client, evaluator_user)
    for row in board.draft.requirements.exclude(state__in=("quitado", "sugerido")):
        client.post(url("s2_consecuencia", procedure, row.pk), {
            "consequence_type": "desestimacion", "note": "Lo dice el pliego."})
    client.post(url("s2_sugerencia_quitar", procedure, board.suggestion.pk))
    client.post(url("s2_tramo_revisado", procedure, board.pending.pk))
    assert board.draft.requirements.filter(state="propuesto").count() == 3

    html = client.get(tab(procedure)).content.decode()

    assert not re.search(r'id="validar"[^>]*\bdisabled\b', html)
    condition = htmllib.unescape(re.search(r'id="cond-validar">(.*?)</p>', html, re.S).group(1))
    assert "3 requisitos sin confirmar" in condition
    assert "No se valida mientras" not in condition
    assert "Ya puede validar la versión" in condition and "confirma esos requisitos" in condition

    ok, text = follow(client, client.post(url("s2_validar", procedure, board.draft.pk)))
    board.draft.refresh_from_db()
    assert ok and board.draft.status == "validated"
    assert not board.draft.requirements.filter(state="propuesto").exists()


def test_the_notice_names_only_what_really_blocks(client, procedure, board, evaluator_user):
    """REQ-081: mientras haya sugerencias, tramos o consecuencias sin resolver, el aviso lo dice y
    aclara que los requisitos sin confirmar los confirma la validación."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    condition = htmllib.unescape(re.search(r'id="cond-validar">(.*?)</p>', html, re.S).group(1))
    assert condition.startswith("Quedan 14 sin decidir: 3 requisitos sin confirmar, "
                                "1 sugerencia, 1 tramo, 9 consecuencias sin elegir.")
    assert "No se valida mientras quede alguna sugerencia, tramo o consecuencia" in condition
    assert "Los requisitos sin confirmar se confirman al validar" in condition
    assert re.search(r'<button class="btn primario" id="validar"[^>]*\bdisabled\b', html)


def test_blockers_separate_what_blocks_from_what_the_validation_confirms(board):
    """REQ-081: las cuentas distinguen lo que traba (`blocking`) de lo que confirma la validación."""
    counts = acciones.blockers(board.draft)
    assert counts["unconfirmed"] == 3
    assert counts["blocking"] == counts["total"] - 3 == 11
