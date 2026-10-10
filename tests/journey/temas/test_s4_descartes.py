"""Tema «descartes y orden económico» de la sección Evaluación y dictamen (REQ-091, REQ-097; plan
014, T-210). Los resultados se guardan directo, sin el modelo (la GPU no se comparte); todo el
material es inventado (P4)."""

import re
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import matriz_evaluacion
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    open_matrix,
    requirement,
    three,
)
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401  (fixtures y ayudas)
from tests.journey.temas.test_s4_propuesta import log_in, notice, page, tab

pytestmark = pytest.mark.django_db


@pytest.fixture
def proposed(three, portal, procedure, operator_user):  # noqa: F811
    """B con un motivo que la descarta entera; C con uno que descarta solo el renglón 2; A sin
    motivos. Con cotizaciones del Portal."""
    a, b, c = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    add_run(operator_user, procedure, b, {declaration: "no_cumple"})
    add_run(operator_user, procedure, c, {requirement(procedure, item=2): "no_cumple",
                                          requirement(procedure, item=1): "cumple"})
    quote_data(portal, procedure, a, total=Decimal("900"), prices={1: (Decimal("10"), 1),
                                                                 2: (Decimal("10"), 1)})
    quote_data(portal, procedure, b, total=Decimal("100"), prices={1: (Decimal("5"), 1),
                                                                 2: (Decimal("5"), 1)})
    quote_data(portal, procedure, c, total=Decimal("500"), prices={1: (Decimal("7"), 1),
                                                                 2: (Decimal("7"), 1)})
    return three


def url(procedure):
    return reverse("expedientes:s4_decidir_descarte", args=[procedure.pk])


def post(client, procedure, offer, line="", action="confirmar", note=""):
    return client.post(url(procedure), {"offer": offer.pk, "line": line, "action": action,
                                        "note": note})


def block(html, anchor, until):
    """Solo el bloque de `anchor`, hasta el siguiente."""
    return html.split(f'id="{anchor}"', 1)[1].split(f'id="{until}"', 1)[0]


def rows_of(html):
    return re.findall(r'<tr id="(desc-[\d-]+)"', html)


# --- Qué muestra ----------------------------------------------------------------------------------


def test_the_blocks_follow_the_order_of_the_approved_mockup(
        client, proposed, procedure, operator_user):
    """REQ-091: resultado y orden económico, descartes, propuesta, preguntas e informe, en ese
    orden, con las anclas."""
    log_in(client, operator_user)
    html = page(client, procedure)
    anchors = ["s4-resultado", "s4-descartes", "s4-propuesta", "s4-preguntas", "s4-informe"]
    places = [html.index(f'id="{anchor}"') for anchor in anchors]
    assert places == sorted(places)


def test_the_tab_lists_each_discard_with_its_grounds_and_state(
        client, proposed, procedure, operator_user):
    """REQ-091: cada descarte propuesto con su motivo, la cita de la oferta y la consecuencia;
    sin decidir; sin textos de la maqueta."""
    a, b, c = proposed
    log_in(client, operator_user)
    html = page(client, procedure)
    assert rows_of(html) == [f"desc-{b.number}", f"desc-{c.number}-2"]
    descartes = block(html, "s4-descartes", "s4-propuesta")
    assert "Descartes propuestos" in descartes and "2 por decidir · 0 decididos" in descartes
    assert f"Oferta {b.number} completa" in descartes
    assert f"Oferta {c.number} · renglón 2" in descartes
    assert "Presentar la declaración jurada" in descartes  # el requisito del pliego
    assert "La oferta dice:" in descartes and "Propuesto, sin decidir" in descartes
    for sample in ("Mascotas del Litoral", "evaluador de muestra", "Nutrición Canina"):
        assert sample not in html


def test_the_economic_order_has_the_total_and_one_row_per_line(
        client, proposed, procedure, operator_user):
    """REQ-091: orden total y por renglón; lo propuesto sin decidir sigue en el orden, marcado."""
    a, b, c = proposed
    log_in(client, operator_user)
    html = page(client, procedure)
    resultado = block(html, "s4-resultado", "s4-descartes")
    total = resultado.split('id="t-orden-total"', 1)[1].split("</table>", 1)[0]
    assert re.findall(r'<td class="pos">(\d+)</td><th scope="row">(\d+) ·', total) == [
        ("1", str(b.number)), ("2", str(c.number)), ("3", str(a.number))]
    assert '<tr class="tachada">' in total and "Descarte propuesto, sin decidir" in total
    assert "$ 100" in total and "$ 900" in total and "2 de 2" in total
    per_line = resultado.split('id="t-orden-renglon"', 1)[1].split("</table>", 1)[0]
    assert "Renglón 1" in per_line and "Renglón 2" in per_line
    assert f"Of. {b.number} · $ 5" in per_line
    assert "(descartada)" not in per_line
    assert "Resultado propuesto por oferta" in resultado and "Confirmados" in resultado


def test_an_evaluator_sees_the_buttons_and_an_operator_only_the_state(
        client, proposed, procedure, evaluator_user, operator_user):
    """REQ-091: «Confirmar el descarte» y «Rechazar el descarte» para el evaluador; el operador
    ve el estado y ningún botón ni formulario de descartes."""
    log_in(client, evaluator_user)
    html = block(page(client, procedure), "s4-descartes", "s4-propuesta")
    assert html.count("Confirmar el descarte") == 2 and html.count("Rechazar el descarte") == 2
    assert url(procedure) in html
    client.logout()
    log_in(client, operator_user)
    html = block(page(client, procedure), "s4-descartes", "s4-propuesta")
    assert "Confirmar el descarte" not in html and "Rechazar el descarte" not in html
    assert url(procedure) not in html and "Lo decide un evaluador" in html
    assert "Propuesto, sin decidir" in html


# --- Decidir --------------------------------------------------------------------------------------


def test_confirming_returns_to_the_tab_with_the_notice_and_shows_who_and_when(
        client, proposed, procedure, evaluator_user, operator_user):
    """REQ-091: confirmar vuelve a la pestaña con el aviso; la fila dice quién y cuándo, en hora
    local; el operador también lo ve, sin botones."""
    b = proposed[1]
    log_in(client, evaluator_user)
    response = post(client, procedure, b, note="Falta la DJ.")
    ok, text = notice(client, response)
    assert ok and f"Se confirmó el descarte de la oferta {b.number}" in text
    assert "quién y cuándo" in text
    decision = am.DiscardDecision.objects.get()
    moment = f"{timezone.localtime(decision.at):%d/%m/%Y %H:%M}"
    html = block(page(client, procedure), "s4-descartes", "s4-propuesta")
    assert f"Confirmado por {evaluator_user.username} el {moment} · nota: Falta la DJ." in html
    assert "1 por decidir · 1 decidido" in html
    client.logout()
    log_in(client, operator_user)
    html = block(page(client, procedure), "s4-descartes", "s4-propuesta")
    assert f"Confirmado por {evaluator_user.username} el {moment}" in html
    assert "Confirmar el descarte" not in html


def test_rejecting_a_line_discard_is_recorded(client, proposed, procedure, evaluator_user):
    """REQ-091: rechazar el descarte de un renglón queda registrado, con la nota opcional vacía."""
    c = proposed[2]
    log_in(client, evaluator_user)
    ok, text = notice(client, post(client, procedure, c, line="2", action="rechazar"))
    assert ok and "Se rechazó el descarte" in text and "renglón 2" in text
    row = am.DiscardDecision.objects.get()
    assert (row.line, row.action, row.note, row.user) == (2, "rechazar", "", evaluator_user)
    html = page(client, procedure)
    assert f"Rechazado por {evaluator_user.username} el " in html


def test_an_operator_post_is_denied_with_the_attempt_recorded(
        client, proposed, procedure, operator_user):
    """REQ-091: sin el rol de evaluador la ruta responde 403, no cambia nada y deja el registro."""
    log_in(client, operator_user)
    response = post(client, procedure, proposed[1])
    assert response.status_code == 403
    assert am.DiscardDecision.objects.count() == 0
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED, user=operator_user).exists()


def test_a_decision_that_does_not_apply_returns_an_error_notice_and_saves_nothing(
        client, proposed, procedure, evaluator_user):
    """REQ-091: un descarte que no está propuesto, o datos mal formados, vuelven con un aviso de
    error y sin cambios; el rechazo queda en el registro."""
    a = proposed[0]
    log_in(client, evaluator_user)
    ok, text = notice(client, post(client, procedure, a))
    assert not ok and "ya no está propuesto" in text
    ok, _ = notice(client, client.post(url(procedure), {"offer": "x", "line": "y",
                                                       "action": "confirmar"}))
    assert not ok
    assert am.DiscardDecision.objects.count() == 0
    assert AuditEvent.objects.filter(event_type=EventType.DISCARD_DECISION,
                                     outcome=AuditOutcome.REJECTED).count() == 2
    assert client.get(url(procedure)).status_code == 405


def test_a_new_evaluation_brings_the_discard_back_to_undecided(
        client, proposed, procedure, evaluator_user, operator_user):
    """REQ-091: tras una evaluación nueva de la oferta, el descarte vuelve a quedar por decidir."""
    b = proposed[1]
    log_in(client, evaluator_user)
    post(client, procedure, b)
    assert "1 por decidir · 1 decidido" in page(client, procedure)
    add_run(operator_user, procedure, b, {requirement(procedure, "declaración jurada"):
                                          "no_cumple"})
    html = page(client, procedure)
    assert "2 por decidir · 0 decididos" in html
    assert am.DiscardDecision.objects.count() == 1


def test_a_confirmed_discard_is_shown_as_discarded_in_the_order(
        client, proposed, procedure, evaluator_user):
    """REQ-091: la oferta con descarte confirmado figura como «descartada», sin posición ni
    marca de «propuesto»; el renglón confirmado figura descartado en su renglón; los demás
    siguen ordenados."""
    a, b, c = proposed
    log_in(client, evaluator_user)
    post(client, procedure, b)
    post(client, procedure, c, line="2")
    resultado = block(page(client, procedure), "s4-resultado", "s4-descartes")
    total = resultado.split('id="t-orden-total"', 1)[1].split("</table>", 1)[0]
    rows = re.findall(r'<tr[^>]*>.*?</tr>', total, re.S)[1:]
    ordered = [re.search(r'<td class="pos">(.*?)</td><th scope="row">(\d+)', r).groups()
               for r in rows]
    assert ordered == [("1", str(c.number)), ("2", str(a.number)), ("—", str(b.number))]
    assert "Descartada. Confirmado por" in rows[2] and 'class="tachada"' in rows[2]
    assert "Descarte propuesto, sin decidir" not in total
    assert "Renglón 2 descartado" in rows[0]
    per_line = resultado.split('id="t-orden-renglon"', 1)[1].split("</table>", 1)[0]
    line_two = re.findall(r"<tr>.*?</tr>", per_line, re.S)[2]
    assert line_two.count("(descartada)") == 2  # B (oferta completa) y C (el renglón)
    assert re.findall(r"Of\. (\d+)", line_two)[0] == str(a.number)


# --- Pendientes -----------------------------------------------------------------------------------


def test_undecided_discards_are_pending_with_resolve_and_not_suggestions(
        client, proposed, procedure, operator_user, evaluator_user):
    """REQ-097/REQ-091: cada descarte sin decidir es un pendiente con «Resolver» a su fila; no
    figura entre las sugerencias; al decidir deja de contar."""
    a, b, c = proposed
    stage = matriz_evaluacion.compute(operator_user, procedure)
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert section.pending == stage.pending and stage.suggestions == 0
    assert "2 descartes propuestos" in stage.detail and "Sugerencias" not in stage.detail
    assert section.suggestions == 0 and section.suggestion_items == ()
    items = [i for i in section.pending_items if "Descarte propuesto" in i.text]
    assert len(items) == 2 and all(i.action == "Resolver" for i in items)
    assert len(section.pending_items) == section.pending
    log_in(client, operator_user)
    html = page(client, procedure)
    for item in items:
        anchor = item.url.split("#")[1]
        assert f'id="{anchor}"' in html
    panel = re.search(r'<section class="panel" id="pendientes".*?</section>', html, re.S).group(0)
    assert panel.count("Resolver") == section.pending
    assert "Descarte propuesto por decidir: oferta" in panel
    sugg = re.search(r'<section class="panel" id="sugerencias".*?</section>', html, re.S)
    assert sugg is None or "Descarte propuesto" not in sugg.group(0)
    client.logout()
    log_in(client, evaluator_user)
    post(client, procedure, b)
    after = sections_for(evaluator_user, procedure).get("evaluacion")
    assert after.pending == section.pending - 1
    assert len(after.pending_items) == after.pending and after.suggestions == 0


def test_without_evaluation_the_blocks_are_there_and_say_so(
        client, procedure, matrix, offer, operator_user):
    """REQ-091: sin evaluación, las anclas existen y dicen que todavía no hay nada."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert 'id="s4-resultado"' in html and 'id="s4-descartes"' in html
    assert "no hay descartes que proponer" in html
    assert rows_of(html) == []


def test_the_order_row_does_not_repeat_the_line_name(client, proposed, procedure, operator_user):
    """REQ-091: «Renglón 1 · <descripción>», o solo «Renglón 1» si la descripción repite el nombre."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "Renglón 1 · Renglón 1" not in html
    assert '<th scope="row">Renglón 1</th>' in html


def test_the_missing_report_and_the_pending_list_name_the_same_offers(
        client, proposed, procedure, operator_user):
    """REQ-097: cada oferta sin informe técnico figura igual en «Falta» y en los pendientes (las
    dos con filas técnicas ya evaluadas); el resumen no habla de sugerencias de descartes."""
    a, b, c = proposed
    section = sections_for(operator_user, procedure).get("evaluacion")
    waiting = [i.text for i in section.pending_items if "informe técnico" in i.text]
    missing = [m.text for m in section.tema_missing if "informe técnico" in m.text]
    assert waiting == [f"Oferta {c.number}: falta subir el informe técnico"]
    assert missing == [f"Falta el informe técnico del área (oferta {c.number})"]
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "Sugerencias del sistema:" not in html
    assert "2 descartes propuestos" in html
