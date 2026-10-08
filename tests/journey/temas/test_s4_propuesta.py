"""Tema «propuesta de evaluación» de la sección Evaluación y dictamen (REQ-089, REQ-097; plan 014,
T-207). Los resultados se guardan directo, sin el modelo (la GPU no se comparte); todo el material
es inventado (P4)."""

import datetime
import html as htmllib
import re
import time

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.assessment.services import review
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import matriz_evaluacion
from evaluon.journey.temas import s4_propuesta
from evaluon.tenders.models import JobStatus, Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    evaluated,
    requirement,
    three,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

PENDING_OK = ("no_determinado", "pendiente_informe_tecnico")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def page(client, procedure, query=""):
    response = client.get(tab(procedure) + query)
    assert response.status_code == 200
    return response.content.decode()


def result_of(offer, requirement_):
    return am.Result.objects.filter(offer=offer, requirement=requirement_).get()


def notice(client, response):
    """La pestaña a la que vuelve la acción y el mensaje que muestra."""
    assert response.status_code == 302
    page_ = client.get(response["Location"])
    assert page_.status_code == 200
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)" id="s4-aviso"[^>]*>(.*?)</p>',
                      page_.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


# --- La tabla --------------------------------------------------------------------------------------


def test_the_tab_shows_each_requirement_by_offer_with_its_grounds(
        client, evaluated, procedure, operator_user):
    """REQ-089: con el caso evaluado se ve la propuesta por oferta y requisito, con su
    fundamento (la explicación del sistema y el texto de la oferta que lo respalda)."""
    log_in(client, operator_user)
    html = page(client, procedure)
    version = procedure.matrix_versions.get(number=1)
    shown = {int(n) for n in re.findall(r'<tr class="fila-req" data-numero="(\d+)"', html)}
    assert shown == {r.number for r in version.requirements.exclude(
        state__in=("quitado", "sugerido"))}
    for offer in evaluated:
        assert f"Oferta {offer.number}" in html and offer.bidder in html
    # Los tres resultados y el motivo del «no determinado».
    for name in ("Cumple", "No cumple", "No determinado: Duda",
                 "No se encontró el documento"):
        assert f'aria-label="{name}"' in html
    assert "Lo dice el texto." in html  # la explicación del sistema, rotulada
    assert "Explicación del sistema (no es texto de la oferta ni del pliego)" in html
    assert "Declaro ba" in html and "página 1" in html  # la cita de la oferta
    assert "Presentar la declaración jurada" in html  # la cita del pliego
    declaration = requirement(procedure, "declaración jurada")
    assert f'id="ev-det-{declaration.number}"' in html


def test_the_tab_has_the_texts_of_the_approved_mockup_and_none_of_its_samples(
        client, evaluated, procedure, operator_user):
    """REQ-089/REQ-100: los títulos de la maqueta aprobada y ningún texto de ejemplo."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "Propuesta por oferta y requisito" in html
    assert "Haga clic en una fila para ver el fundamento de cada oferta" in html
    assert "Evaluar todas las ofertas" in html
    assert "Solo lo abierto" in html and "Técnicos por renglón" in html
    assert "[texto de ejemplo]" not in html and "Nutrición Canina" not in html


def test_the_filters_by_type_and_by_what_is_open(client, evaluated, procedure, operator_user):
    """REQ-089: el filtro por tipo y «solo lo abierto» dejan las filas que corresponden."""
    log_in(client, operator_user)
    everything = page(client, procedure)
    all_rows = re.findall(r'<tr class="fila-req" data-numero="(\d+)"', everything)
    formal = page(client, procedure, "?tipo=formal")
    formal_rows = re.findall(r'<tr class="fila-req" data-numero="(\d+)"', formal)
    assert 0 < len(formal_rows) <= len(all_rows)
    assert 'data-tipo="economico"' not in formal and 'data-tipo="tecnico"' not in formal
    open_rows = re.findall(r'<tr class="fila-req" data-numero="(\d+)"',
                           page(client, procedure, "?ver=abiertas"))
    # Todo par evaluado y sin decidir es abierto: quedan las filas con algún resultado.
    evaluated_rows = {r.requirement.number for r in am.Result.objects.select_related(
        "requirement")}
    assert set(open_rows) == {str(n) for n in evaluated_rows}
    bad = page(client, procedure, "?ver=nocumple")
    bad_rows = re.findall(r'<tr class="fila-req" data-numero="(\d+)"', bad)
    declaration = requirement(procedure, "declaración jurada")
    registry = requirement(procedure, "constancia de inscripción")
    assert set(bad_rows) == {str(declaration.number), str(registry.number)}
    mask = lambda text: re.sub(r'value="[A-Za-z0-9]{64}"', "", text)  # noqa: E731  (el token)
    assert mask(page(client, procedure, "?ver=inventado")) == mask(page(client, procedure))


def test_without_evaluation_the_tab_says_so_and_offers_to_evaluate(
        client, procedure, matrix, offer, operator_user):
    """REQ-089/REQ-097: sin evaluación, la pestaña dice qué falta y deja «Evaluar todas las
    ofertas» a la vista."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "Todavía no se evaluó ninguna oferta" in html
    assert 'id="evaluar-todas"' in html
    assert 'id="evaluar-todas" type="submit" disabled' not in html


def test_without_a_validated_matrix_the_button_is_off_and_says_why(client, operator_user):
    """REQ-097: sin matriz validada no se puede evaluar y la pestaña dice por qué."""
    bare = Procedure.objects.create(
        number="SIN-MATRIZ-1", procedure_type="Contratación directa", subject="Inventado",
        authorization_date=datetime.date(2024, 5, 6), created_by=operator_user)
    make_offer(bare, operator_user, "Oferente sin matriz",
               {"oferta.pdf": ["Texto de la oferta."]})
    log_in(client, operator_user)
    html = page(client, bare)
    assert 'id="evaluar-todas" type="submit" disabled' in html
    assert "Falta una matriz de cumplimiento validada." in html
    assert "Todavía no se evaluó ninguna oferta" in html


def test_the_operator_sees_no_decision_buttons_and_the_evaluator_does(
        client, evaluated, procedure, operator_user, evaluator_user):
    """P3, REQ-089: el operador ve el estado y que lo decide un evaluador; el evaluador ve
    confirmar, corregir y rechazar."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "decidir/" not in html
    assert "Lo decide un evaluador" in html
    client.logout()
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert "decidir/" in html
    for text in ("Confirmar", "Corregir", "Rechazar", "Motivo (obligatorio)"):
        assert text in html


# --- Decidir -------------------------------------------------------------------------------------


def decide_url(procedure, result):
    return reverse("expedientes:s4_decidir", args=[procedure.pk, result.pk])


def test_confirming_leaves_the_same_decision_and_fact_as_the_old_route(
        client, evaluated, procedure, evaluator_user):
    """REQ-089: confirmar desde la pestaña deja la misma decisión y el mismo hecho de
    auditoría que `assessment:decide`, y vuelve a la pestaña con su aviso."""
    a, b, _ = evaluated
    declaration = requirement(procedure, "constancia de inscripción")  # las dos cumplen
    log_in(client, evaluator_user)
    old = client.post(reverse("assessment:decide", args=[result_of(a, declaration).pk]),
                      {"action": "confirmar"})
    assert old.status_code == 302
    new = client.post(decide_url(procedure, result_of(b, declaration)), {"action": "confirmar"})
    assert new["Location"].startswith(tab(procedure))
    ok, text = notice(client, new)
    assert ok and "Se confirmó" in text and f"oferta {b.number}" in text
    first = am.Decision.objects.get(result=result_of(a, declaration))
    second = am.Decision.objects.get(result=result_of(b, declaration))
    for field in ("action", "outcome_after", "note", "user_id"):
        assert getattr(first, field) == getattr(second, field)
    drop = ("result", "offer")
    detail_a = {k: v for k, v in first.event.detail.items() if k not in drop}
    detail_b = {k: v for k, v in second.event.detail.items() if k not in drop}
    assert detail_a == detail_b
    assert (first.event.event_type, first.event.outcome, first.event.channel) == (
        second.event.event_type, second.event.outcome, second.event.channel)
    assert second.event.event_type == EventType.EVAL_DECISION


def test_correcting_needs_the_motive_and_shows_who_and_when_in_the_row(
        client, evaluated, procedure, evaluator_user):
    """REQ-089: corregir sin motivo no cambia nada y lo dice; con motivo queda la corrección y la
    fila muestra quién, cuándo (hora local) y el motivo."""
    a = evaluated[0]
    declaration = requirement(procedure, "declaración jurada")
    result = result_of(a, declaration)
    log_in(client, evaluator_user)
    refused = client.post(decide_url(procedure, result),
                          {"action": "corregir", "outcome_after": "no_cumple", "note": "  "})
    ok, text = notice(client, refused)
    assert not ok and "motivo" in text.lower()
    assert not am.Decision.objects.filter(result=result).exists()
    done = client.post(decide_url(procedure, result), {
        "action": "corregir", "outcome_after": "no_cumple", "note": "La firma no es válida."})
    ok, text = notice(client, done)
    assert ok and "Se corrigió" in text
    decision = am.Decision.objects.get(result=result)
    assert decision.outcome_after == "no_cumple" and decision.note == "La firma no es válida."
    assert decision.user == evaluator_user
    # Hora local: 01:30 UTC del 8 de octubre (de un año futuro, para ser la última) son las 22:30 del 7 en Buenos Aires. Las
    # decisiones son de solo inserción: se vuelve a decidir con esa hora en lugar de cambiarla.
    am.Decision.objects.create(
        result=result, action=am.Action.CORREGIR, outcome_after="no_cumple",
        note="La firma no es válida.", user=evaluator_user, event=decision.event,
        at=datetime.datetime(2099, 10, 8, 1, 30, tzinfo=datetime.timezone.utc))
    html = page(client, procedure)
    assert (f"Corregido por {evaluator_user.username} el 07/10/2099 22:30 · resultado: "
            "No cumple · motivo: La firma no es válida.") in html
    assert 'aria-label="No cumple"' in html


def test_rejecting_needs_the_motive_and_keeps_the_proposal(
        client, evaluated, procedure, evaluator_user):
    """REQ-089: rechazar exige el motivo; la propuesta queda y el par pasa a rechazado."""
    b = evaluated[1]
    declaration = requirement(procedure, "declaración jurada")
    result = result_of(b, declaration)
    log_in(client, evaluator_user)
    ok, _ = notice(client, client.post(decide_url(procedure, result), {"action": "rechazar"}))
    assert not ok and not am.Decision.objects.exists()
    ok, text = notice(client, client.post(decide_url(procedure, result), {
        "action": "rechazar", "note": "No corresponde al requisito."}))
    assert ok and "Se rechazó" in text
    result.refresh_from_db()
    assert result.outcome == "no_cumple"  # la propuesta no se toca
    assert review.state_of(result) == "rechazado"
    html = page(client, procedure)
    assert "Rechazado por" in html and "No corresponde al requisito." in html


def test_the_operator_cannot_decide_and_the_refusal_is_recorded(
        client, evaluated, procedure, operator_user):
    """P3: sin el rol de evaluador la acción da «acceso denegado» (403), no cambia nada y deja el
    hecho `rejected`, como la ruta vieja."""
    declaration = requirement(procedure, "declaración jurada")
    result = result_of(evaluated[0], declaration)
    log_in(client, operator_user)
    before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    response = client.post(decide_url(procedure, result), {"action": "confirmar"})
    assert response.status_code == 403
    assert not am.Decision.objects.exists()
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == before + 1


def test_a_result_of_another_procedure_is_not_found(
        client, evaluated, procedure, evaluator_user):
    """El resultado debe ser del procedimiento de la dirección."""
    other = Procedure.objects.create(
        number="OTRO-1", procedure_type="Contratación directa", subject="Inventado",
        authorization_date=datetime.date(2024, 5, 6), created_by=evaluator_user)
    log_in(client, evaluator_user)
    declaration = requirement(procedure, "declaración jurada")
    result = result_of(evaluated[0], declaration)
    url = reverse("expedientes:s4_decidir", args=[other.pk, result.pk])
    assert client.post(url, {"action": "confirmar"}).status_code == 404
    assert not am.Decision.objects.exists()


# --- Evaluar todas las ofertas ---------------------------------------------------------------------


def test_evaluating_all_leaves_the_same_request_and_fact_as_the_old_route(
        client, procedure, matrix, two_offers, evaluator_user):
    """REQ-089: el botón de la pestaña pide lo mismo que `assessment:evaluate_all` (un pedido
    con las ofertas, el mismo hecho) y vuelve a la pestaña con su aviso; no corre el modelo."""
    log_in(client, evaluator_user)
    new = client.post(reverse("expedientes:s4_evaluar", args=[procedure.pk]))
    assert new["Location"].startswith(tab(procedure))
    ok, text = notice(client, new)
    assert ok and "Se pidió la evaluación de 2 ofertas" in text
    request = am.Request.objects.get(procedure=procedure)
    assert request.offers == [o.pk for o in two_offers] and request.requested_by == evaluator_user
    event_new = AuditEvent.objects.filter(event_type=EventType.EVAL_REQUEST).get()
    # La misma pantalla vieja, con el pedido anterior terminado, deja la misma forma.
    request.job.status = "done"
    request.job.save(update_fields=["status"])
    old = client.post(reverse("assessment:evaluate_all", args=[procedure.pk]))
    assert old.status_code == 200
    events = list(AuditEvent.objects.filter(event_type=EventType.EVAL_REQUEST).order_by("pk"))
    assert len(events) == 2 and events[0].pk == event_new.pk
    keep = ("procedure", "cause", "matrix_version", "offers", "requirements")
    assert {k: events[0].detail[k] for k in keep} == {k: events[1].detail[k] for k in keep}
    assert (events[0].outcome, events[0].channel) == (events[1].outcome, events[1].channel)


def test_evaluating_with_a_pending_request_is_refused_with_the_reason(
        client, procedure, matrix, two_offers, simulate, evaluator_user):
    """REQ-089: con un pedido en curso el botón figura apagado con el motivo; si igual se
    pide, el servicio lo rechaza, no crea otro pedido y la pestaña dice por qué."""
    simulate(two_offers, JobStatus.RUNNING, done=1)
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert 'id="evaluar-todas" type="submit" disabled' in html
    assert "Ya hay una evaluación en espera o en curso." in html
    before = am.Request.objects.count()
    refused = client.post(reverse("expedientes:s4_evaluar", args=[procedure.pk]))
    ok, text = notice(client, refused)
    assert not ok and text
    assert am.Request.objects.count() == before
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_REQUEST,
                                     outcome=AuditOutcome.REJECTED).exists()


def test_the_progress_of_a_running_request_is_shown(
        client, procedure, matrix, two_offers, simulate, operator_user):
    """REQ-089: el avance del pedido en curso («1 de 2 ofertas evaluadas»)."""
    simulate(two_offers, JobStatus.RUNNING, done=1)
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "1 de 2 ofertas evaluadas" in html
    assert 'id="s4-avance"' in html


def test_a_failed_request_shows_its_reason(
        client, procedure, matrix, two_offers, simulate, operator_user):
    """REQ-089: la última evaluación fallida se dice, con su motivo."""
    simulate(two_offers, JobStatus.FAILED, done=0, error="el servicio de generación no respondió")
    log_in(client, operator_user)
    html = page(client, procedure)
    assert "La última evaluación falló" in html


# --- El detalle de un par dentro de la pestaña -------------------------------------------------------


def test_the_pair_opens_inside_the_tab_with_its_history(
        client, evaluated, procedure, evaluator_user):
    """REQ-089: el detalle del par se abre dentro de la pestaña, con «← Volver a Evaluación», el
    historial con las decisiones (quién y cuándo) y las acciones que vuelven al detalle."""
    b = evaluated[1]
    declaration = requirement(procedure, "declaración jurada")
    result = result_of(b, declaration)
    log_in(client, evaluator_user)
    review.reject(evaluator_user, result.pk, "Primero se rechaza.")
    url = reverse("expedientes:s4_par", args=[procedure.pk, b.pk, declaration.pk])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "← Volver a Evaluación" in html and f'href="{tab(procedure)}#ev-' in html
    assert "Historial del par" in html and "Evaluación 1 (vigente)" in html
    assert f"Rechazado por {evaluator_user.username}" in html and "Primero se rechaza." in html
    assert 'class="tab' in html or "pestaña" in html.lower() or "Evaluación y dictamen" in html
    # Corregir desde el detalle vuelve al detalle, con el aviso.
    done = client.post(decide_url(procedure, result), {
        "action": "corregir", "outcome_after": "cumple", "note": "Sí la presentó.",
        "desde": "par"})
    assert done["Location"].startswith(url)
    ok, text = notice(client, done)
    assert ok and "Se corrigió" in text
    html = client.get(url).content.decode()
    assert "Sí la presentó." in html


def test_the_pair_of_an_unevaluated_requirement_is_not_found(
        client, evaluated, procedure, operator_user):
    log_in(client, operator_user)
    other = requirement(procedure, "libre deuda")
    url = reverse("expedientes:s4_par", args=[procedure.pk, evaluated[0].pk, other.pk])
    assert client.get(url).status_code == 404


# --- Pendientes de la pestaña --------------------------------------------------------------------


def test_the_pending_are_listed_one_by_one_and_match_the_bar(
        client, evaluated, procedure, operator_user):
    """REQ-097/REQ-098: cada par por decidir es un pendiente con «Resolver» al ancla de su fila;
    la cuenta de la sección es la de la etapa y los renglones suman lo mismo. Las sugerencias
    (descartes propuestos) también."""
    log_in(client, operator_user)
    stage = matriz_evaluacion.compute(operator_user, procedure)
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert stage.pending > 0 and section.pending == stage.pending
    assert len(section.pending_items) == stage.pending
    assert section.suggestions == stage.suggestions == len(section.suggestion_items) == 1
    html = page(client, procedure)
    panel = re.search(r'<section class="panel" id="pendientes".*?</section>', html, re.S).group(0)
    assert f'<span class="cta">{stage.pending}</span>' in panel
    assert panel.count("Resolver") == stage.pending
    for item in section.pending_items:
        anchor = item.url.split("#")[1]
        assert f'id="{anchor}"' in html and f'href="{item.url}"' in panel
        assert item.action == "Resolver"
    sugg = re.search(r'<section class="panel" id="sugerencias".*?</section>', html, re.S).group(0)
    assert "Descarte propuesto: oferta" in sugg
    # La barra de pestañas muestra las mismas cuentas.
    bar = client.get(reverse("expedientes:barra", args=[procedure.pk])).content.decode()
    mine = re.search(r'data-seccion="evaluacion".*?</a>', bar, re.S).group(0)
    assert f"<b>{section.pending}</b> pend. · <b>{section.suggestions}</b> sug." in mine


def test_a_decided_pair_stops_being_pending(client, evaluated, procedure, evaluator_user):
    """REQ-097: al confirmar, el pendiente de ese par desaparece de la lista y de la cuenta."""
    declaration = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    before = sections_for(evaluator_user, procedure).get("evaluacion")
    client.post(decide_url(procedure, result_of(evaluated[0], declaration)),
                {"action": "confirmar"})
    after = sections_for(evaluator_user, procedure).get("evaluacion")
    assert after.pending == before.pending - 1
    assert len(after.pending_items) == after.pending
    assert not any(f"Oferta {evaluated[0].number} · requisito {declaration.number}:" in i.text
                   for i in after.pending_items)


def test_open_questions_and_technical_ok_are_listed_and_counted_like_the_stage(
        client, procedure, offer, operator_user, evaluator_user):
    """REQ-097: una pregunta abierta y un ok técnico pendiente son pendientes de la pestaña,
    sin duplicar los pares de las filas técnicas, y la suma es la de la etapa."""
    declaration = requirement(procedure, "declaración jurada")
    rows = {i: requirement(procedure, item=i) for i in (1, 2, 3)}
    saved = add_run(operator_user, procedure, offer,
                    {declaration: "cumple", **{r: PENDING_OK for r in rows.values()}})
    am.Question.objects.create(
        procedure=procedure, requirement=declaration, offer=offer, result=saved[declaration.pk],
        text="¿Está vigente?", reason="externo")
    stage = matriz_evaluacion.compute(operator_user, procedure)
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert stage.pending == 3  # 1 par + 1 pregunta + 1 oferta con ok técnico pendiente
    assert section.pending == len(section.pending_items) == 3
    texts = " | ".join(i.text for i in section.pending_items)
    assert "pregunta abierta" in texts and "falta subir el informe técnico" in texts
    question = am.Question.objects.get()
    link = next(i.url for i in section.pending_items if "pregunta abierta" in i.text)
    assert link == f"{tab(procedure)}#preg-{question.pk}"  # el ancla del bloque de preguntas
    log_in(client, evaluator_user)
    html = page(client, procedure)
    first = rows[1]
    technical = result_of(offer, first)
    assert decide_url(procedure, technical) not in html
    assert "se decide con el ok del informe técnico del área" in html


def test_no_decision_link_goes_to_the_old_screens(client, evaluated, procedure, evaluator_user):
    """REQ-089: ningún enlace ni formulario de decisión de la pestaña ni del detalle apunta a
    `/evaluacion/` de la pantalla vieja."""
    declaration = requirement(procedure, "declaración jurada")
    log_in(client, evaluator_user)
    html = page(client, procedure)
    old = reverse("assessment:matrix", args=[procedure.pk])
    old_pair = reverse("assessment:pair", args=[evaluated[0].pk, declaration.pk])
    body = html.split('id="s4-propuesta"', 1)[1]
    assert old not in body
    old_decide = reverse("assessment:decide", args=[result_of(evaluated[0], declaration).pk])
    # Las rutas de la pestaña terminan igual que las viejas: se compara la dirección entera.
    assert f'"{old_decide}"' not in body and f'"{old_pair}"' not in body
    pair = client.get(reverse("expedientes:s4_par", args=[procedure.pk, evaluated[0].pk,
                                                         declaration.pk])).content.decode()
    assert f'"{old_decide}"' not in pair and f'"{old}"' not in pair


# --- Tiempo --------------------------------------------------------------------------------------


def test_the_tab_loads_in_under_two_seconds_with_the_small_case(
        client, evaluated, procedure, evaluator_user):
    """REQ-100 (no funcional): la pestaña carga en menos de 2 segundos con el caso chico."""
    log_in(client, evaluator_user)
    client.get(tab(procedure))  # calienta
    started = time.perf_counter()
    response = client.get(tab(procedure))
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    print(f"\npestaña Evaluación y dictamen, caso chico: {elapsed:.3f} s")
    assert elapsed < 2.0


def test_the_module_keys_are_the_registered_ones():
    """Plan 014: el tema es el de la sección «evaluacion»."""
    assert (s4_propuesta.KEY, s4_propuesta.SECTION) == ("s4_propuesta", "evaluacion")
    assert s4_propuesta.PARTIAL == "journey/temas/s4_propuesta.html"
