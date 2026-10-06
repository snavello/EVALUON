"""La matriz de evaluación de todas las ofertas (REQ-057, REQ-058, REQ-059; plan 004, "Pantalla"
y "Decisiones del responsable"; T-152). Caso chico inventado (P4); los resultados se guardan
directo, sin el modelo: lo que se prueba es la grilla, el estado, el descarte y la pantalla."""

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate
from evaluon.assessment.services import matrix as service
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.offers.services import offers as offers_service
from evaluon.tenders import models as m
from tests.offers.conftest import make_offer
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db

DECLARATION = "Declaro bajo juramento que me encuentro habilitado para contratar"


def requirement(procedure, needle=None, *, item=None):
    """Un requisito de la matriz validada: el formal o económico cuya cita contiene `needle`, o
    la fila técnica del renglón `item`."""
    version = procedure.matrix_versions.get(number=1)
    for row in version.requirements.all():
        if item is not None and row.category == "tecnico" and row.items \
                and str(row.items[0]) == str(item):
            return row
        if needle and any(needle in q.text for q in row.quotes.all()):
            return row
    raise AssertionError((needle, item))


@pytest.fixture
def three(procedure, operator_user):
    """Tres ofertas con documentos."""
    return [make_offer(procedure, operator_user, f"Oferente {name}",
                       {"oferta.pdf": [f"{DECLARATION}. Oferente {name}. Texto de la oferta."]})
            for name in "ABC"]


def add_run(user, procedure, offer, outcomes, *, version=None):
    """Guarda una evaluación de `offer`: `outcomes` es `{requisito: resultado}` (un resultado o
    un par `(resultado, motivo de la duda)`); un "no cumple" y un "cumple" llevan su cita de la
    oferta. Devuelve `{id del requisito: resultado}`."""
    version = version or procedure.matrix_versions.get(number=1)
    number = am.Run.objects.filter(offer=offer).count() + 1
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[offer.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=user)
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=number,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    document = offer.documents.first()
    reading = document.readings.get()
    saved = {}
    for row, wanted in outcomes.items():
        outcome, doubt = wanted if isinstance(wanted, tuple) else (wanted, "")
        result = am.Result.objects.create(
            run=run, offer=offer, requirement=row, outcome=outcome, doubt=doubt,
            exigence=am.Exigence.CONDICION, explanation="Lo dice el texto.")
        order = 0
        if outcome in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE):
            order += 1
            am.Citation.objects.create(
                result=result, order=order, kind=am.CitationKind.OFERTA, document=document,
                reading=reading, page=1, char_start=0, char_end=10,
                text=reading.canonical_text[:10])
        quote = row.quotes.first()
        if quote is not None:
            order += 1
            am.Citation.objects.create(
                result=result, order=order, kind=am.CitationKind.PLIEGO,
                requirement_quote=quote, text=quote.text)
        saved[row.pk] = result
    return saved


def decide(user, result, action, *, outcome_after="", note=""):
    event = audit.record(EventType.EVAL_DECISION, outcome=AuditOutcome.OK,
                         channel=Channel.SCREEN, user=user)
    return am.Decision.objects.create(result=result, action=action, user=user, event=event,
                                      outcome_after=outcome_after, note=note)


def open_matrix():
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE tenders_consequence DISABLE TRIGGER USER")


def page_of(user, procedure):
    return service.matrix_page(user, procedure.pk)


def discard_of(page, offer):
    return next((d for d in page.discards if d.offer.pk == offer.pk), None)


# --- Grilla y descarte ----------------------------------------------------------------------


@pytest.fixture
def evaluated(three, procedure, operator_user):
    """Tres ofertas evaluadas: A cumple lo formal; B no cumple la declaración jurada (con la
    consecuencia prevista); C no encontró la constancia de inscripción y no determinó la
    garantía."""
    declaration = requirement(procedure, "declaración jurada")
    registry = requirement(procedure, "constancia de inscripción")
    guarantee = requirement(procedure, "garantía de mantenimiento")
    open_matrix()
    m.Consequence.objects.create(
        requirement=declaration, consequence_type="desestimacion", grounds=[],
        origin="persona", chosen=True, chosen_by=operator_user,
        chosen_at=timezone.now(), chosen_note="El pliego desestima sin subsanar.")
    a, b, c = three
    add_run(operator_user, procedure, a, {declaration: "cumple", registry: "cumple",
                                          guarantee: "cumple"})
    add_run(operator_user, procedure, b, {declaration: "no_cumple", registry: "cumple",
                                          guarantee: "cumple"})
    add_run(operator_user, procedure, c, {declaration: "cumple", registry: "sin_documento",
                                          guarantee: ("no_determinado", "duda")})
    return three


def test_the_grid_has_a_cell_per_offer_and_requirement_with_the_current_result(
        evaluated, procedure, operator_user):
    """REQ-059: la matriz de evaluación es de ofertas por requisitos, con el resultado vigente
    de cada par; lo no evaluado figura como tal."""
    page = page_of(operator_user, procedure)
    a, b, c = evaluated
    declaration = requirement(procedure, "declaración jurada")
    registry = requirement(procedure, "constancia de inscripción")
    assert [o.pk for o in page.offers] == [a.pk, b.pk, c.pk]
    assert page.cells[(a.pk, declaration.pk)].effective_outcome == "cumple"
    assert page.cells[(b.pk, declaration.pk)].effective_outcome == "no_cumple"
    assert page.cells[(c.pk, registry.pk)].effective_outcome == "sin_documento"
    other = requirement(procedure, "libre deuda")
    assert page.cells[(a.pk, other.pk)].state == service.UNEVALUATED
    assert len(page.rows) == len(page.requirements)


def test_a_no_cumple_proposes_the_discard_with_requirement_foundation_and_consequence(
        evaluated, procedure, operator_user):
    """REQ-059: la oferta con un "no cumple" formal queda señalada como descartada, con el
    requisito, su fundamento (pliego y oferta) y la consecuencia prevista."""
    page = page_of(operator_user, procedure)
    discard = discard_of(page, evaluated[1])
    assert discard.is_whole and not discard.is_partial
    ground = discard.whole[0]
    assert ground.requirement.pk == requirement(procedure, "declaración jurada").pk
    assert "Presentar la declaración jurada" in ground.requirement_text
    assert ground.offer_quotes and ground.offer_quotes[0].page == 1
    assert ground.consequences == ["Desestimación sin posibilidad de subsanar"]
    assert discard_of(page, evaluated[0]) is None


def test_a_missing_document_and_an_undetermined_result_do_not_discard(
        evaluated, procedure, operator_user):
    """REQ-059 y REQ-060: "no se encontró el documento" y "no determinado" no descartan."""
    page = page_of(operator_user, procedure)
    assert discard_of(page, evaluated[2]) is None
    assert [d.offer.number for d in page.discards] == [evaluated[1].number]


def test_the_matrix_page_marks_everything_as_a_proposal_of_the_commission(
        evaluated, procedure, operator_user, client):
    """P3: la pantalla rotula descarte y orden como propuestas y deja la decisión a la
    Comisión; el motivo del descarte se ve."""
    log_in(client, operator_user)
    response = client.get(reverse("assessment:matrix", args=[procedure.pk]))
    assert response.status_code == 200
    text = text_of(response)
    assert "propuesta del sistema" in text and "Decide la Comisión" in text
    assert "se propone descartar la oferta entera" in text
    assert "Presentar la declaración jurada" in text
    assert "Desestimación sin posibilidad de subsanar" in text
    assert "Orden económico propuesto" in text


# --- Estado de un par ----------------------------------------------------------------------


def test_the_state_of_a_pair_follows_the_last_decision(
        evaluated, procedure, operator_user, evaluator_user):
    """REQ-058: el estado de un par sin decisión, confirmado, corregido y rechazado; pedir la
    subsanación no lo cambia; el resultado efectivo es el corregido, y uno rechazado no cuenta."""
    a, b, c = evaluated
    declaration = requirement(procedure, "declaración jurada")
    registry = requirement(procedure, "constancia de inscripción")
    guarantee = requirement(procedure, "garantía de mantenimiento")
    page = page_of(operator_user, procedure)
    assert page.cells[(a.pk, declaration.pk)].state == service.PENDING

    confirmed = evaluate.current_result(a, declaration)
    decide(evaluator_user, confirmed, am.Action.CONFIRMAR)
    corrected = evaluate.current_result(c, guarantee)
    decide(evaluator_user, corrected, am.Action.CORREGIR, outcome_after="no_cumple",
           note="La garantía no es la pedida.")
    rejected = evaluate.current_result(b, declaration)
    decide(evaluator_user, rejected, am.Action.RECHAZAR, note="Es una declaración válida.")
    asked = evaluate.current_result(c, registry)
    decide(evaluator_user, asked, am.Action.PEDIR_SUBSANACION, note="Que presente la constancia.")

    page = page_of(operator_user, procedure)
    assert page.cells[(a.pk, declaration.pk)].state == service.CONFIRMED
    corrected_cell = page.cells[(c.pk, guarantee.pk)]
    assert corrected_cell.state == service.CORRECTED
    assert corrected_cell.result.outcome == "no_determinado"  # la propuesta original queda
    assert corrected_cell.effective_outcome == "no_cumple"
    rejected_cell = page.cells[(b.pk, declaration.pk)]
    assert rejected_cell.state == service.REJECTED and rejected_cell.effective_outcome is None
    assert page.cells[(c.pk, registry.pk)].state == service.PENDING
    # El rechazo de B levanta su descarte; la corrección de C a "no cumple" lo crea.
    assert discard_of(page, b) is None
    assert discard_of(page, c).whole[0].requirement.pk == guarantee.pk


def test_a_decision_on_a_replaced_result_does_not_count_for_the_new_one(
        evaluated, procedure, operator_user, evaluator_user):
    """El estado sale de las decisiones del resultado vigente: una nueva evaluación del par
    vuelve a "sin decidir"."""
    a = evaluated[0]
    declaration = requirement(procedure, "declaración jurada")
    decide(evaluator_user, evaluate.current_result(a, declaration), am.Action.CONFIRMAR)
    add_run(operator_user, procedure, a, {declaration: "no_cumple"})
    page = page_of(operator_user, procedure)
    cell = page.cells[(a.pk, declaration.pk)]
    assert cell.state == service.PENDING and cell.effective_outcome == "no_cumple"


# --- Estado por oferta ---------------------------------------------------------------------


def test_the_status_of_an_offer_counts_by_state_and_outcome_and_lists_open_questions(
        evaluated, procedure, operator_user, evaluator_user):
    """REQ-058: por oferta, requisitos por estado y por resultado, y las preguntas abiertas
    (una respondida ya no cuenta)."""
    c = evaluated[2]
    registry = requirement(procedure, "constancia de inscripción")
    guarantee = requirement(procedure, "garantía de mantenimiento")
    result = evaluate.current_result(c, guarantee)
    open_q = am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=c, result=result,
        text="¿Qué garantía es válida?", reason="duda")
    answered = am.Question.objects.create(
        procedure=procedure, requirement=registry, offer=c,
        result=evaluate.current_result(c, registry), text="¿Hay constancia?",
        reason="sin_dato")
    event = audit.record(EventType.EVAL_ANSWER, outcome=AuditOutcome.OK,
                         channel=Channel.SCREEN, user=evaluator_user)
    am.Answer.objects.create(question=answered, text="Sí.", answered_by=evaluator_user,
                             event=event)
    decide(evaluator_user, evaluate.current_result(c, requirement(procedure, "declaración jurada")),
           am.Action.CONFIRMAR)

    status = {s.offer.pk: s for s in page_of(operator_user, procedure).statuses}[c.pk]
    assert status.evaluated and status.run.number == 1
    assert status.by_state[service.CONFIRMED] == 1 and status.by_state[service.PENDING] == 2
    assert status.by_state[service.UNEVALUATED] == len(
        service.sheets.firm_requirements(status.run.matrix_version)) - 3
    assert status.by_outcome == {"cumple": 1, "sin_documento": 1, "no_determinado": 1}
    assert [q.pk for q in status.open_questions] == [open_q.pk]


def test_an_offer_never_evaluated_has_no_run_and_all_unevaluated(
        three, procedure, operator_user):
    """REQ-058: antes de evaluar, todo "sin evaluar" y la grilla muestra la versión vigente."""
    page = page_of(operator_user, procedure)
    assert page.version.number == 1
    status = page.statuses[0]
    assert not status.evaluated and status.run is None
    assert status.by_state[service.UNEVALUATED] == len(page.requirements)


# --- Versión de la matriz ------------------------------------------------------------------


def test_an_evaluation_built_with_version_1_is_flagged_when_version_2_is_validated(
        evaluated, procedure, operator_user, matrix, client):
    """REQ-057: la evaluación dice con qué versión se armó y la pantalla avisa que hay otra."""
    newer = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, status="draft", created_by=operator_user,
        based_on=matrix.version)
    m.MatrixVersion.objects.filter(pk=newer.pk).update(
        status="validated", validated_by=operator_user, validated_at=newer.created_at)
    page = page_of(operator_user, procedure)
    assert page.version.number == 1 and page.newer_version.number == 2
    assert all(s.newer_version.number == 2 for s in page.statuses if s.evaluated)
    log_in(client, operator_user)
    text = text_of(client.get(reverse("assessment:matrix", args=[procedure.pk])))
    assert "la versión vigente es la 2" in text
    assert "armada con la versión 1" in text


# --- Evaluar todas -------------------------------------------------------------------------


def test_evaluate_all_requests_every_offer_in_one_job(three, procedure, operator_user):
    """REQ-059: un solo pedido con todas las ofertas."""
    requested, left_out = service.request_all(operator_user, procedure)
    assert left_out == []
    assert sorted(requested.request.offers) == sorted(o.pk for o in three)
    assert m.Job.objects.filter(kind=m.JobKind.EVALUATE_OFFERS).count() == 1


def test_evaluate_all_warns_about_an_offer_without_documents_and_evaluates_the_rest(
        three, procedure, operator_user, client):
    """REQ-059 y aviso de T-150: antes de pedir se avisa que una oferta no tiene documentos; el
    pedido no se rechaza entero: evalúa las otras y dice cuál quedó afuera."""
    empty = offers_service.register_offer(operator_user, procedure, bidder="Sin documentos",
                                          channel=Channel.COMMAND)
    log_in(client, operator_user)
    url = reverse("assessment:matrix", args=[procedure.pk])
    assert "no tiene documentos y no se va a evaluar" in text_of(client.get(url))
    response = client.post(reverse("assessment:evaluate_all", args=[procedure.pk]))
    text = text_of(response)
    assert "Se pidió la evaluación de 3 ofertas" in text
    assert f"la oferta {empty.number} (Sin documentos)" in text
    request = am.Request.objects.get()
    assert empty.pk not in request.offers and len(request.offers) == 3
    # un segundo pedido mientras hay uno en curso se rechaza con su motivo
    again = text_of(client.post(reverse("assessment:evaluate_all", args=[procedure.pk])))
    assert "Ya hay un pedido de evaluación" in again


def test_evaluate_all_with_no_offer_having_documents_is_refused_and_registered(
        matrix, procedure, operator_user):
    """REQ-059: si ninguna oferta tiene documentos, se rechaza con su motivo y queda
    registrado."""
    offers_service.register_offer(operator_user, procedure, bidder="Sin documentos",
                                  channel=Channel.COMMAND)
    with pytest.raises(evaluate.EvaluationRefused) as error:
        service.request_all(operator_user, procedure)
    assert error.value.reason == "no_documents"
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_REQUEST,
                                     outcome="rejected").exists()


def test_the_matrix_page_and_the_request_need_a_commission_role(
        three, procedure, no_commission_user, client):
    """Roles: sin rol de la Comisión, 403 y rechazo registrado."""
    with pytest.raises(RoleRejected):
        service.matrix_page(no_commission_user, procedure.pk)
    with pytest.raises(RoleRejected):
        service.request_all(no_commission_user, procedure)
    log_in(client, no_commission_user)
    assert client.get(reverse("assessment:matrix", args=[procedure.pk])).status_code == 403
    assert not m.Job.objects.filter(kind=m.JobKind.EVALUATE_OFFERS).exists()


def test_the_finished_notice_of_an_evaluation_links_to_the_matrix(
        three, procedure, operator_user, client):
    """El aviso de fin de la 003 nombra la evaluación y lleva a la matriz."""
    requested, _ = service.request_all(operator_user, procedure)
    from evaluon.tenders import jobs

    job = jobs.claim([m.JobKind.EVALUATE_OFFERS])
    jobs.finish(job)
    log_in(client, operator_user)
    response = client.get(reverse("assessment:matrix", args=[procedure.pk]))
    text = text_of(response)
    assert "La evaluación de las ofertas del procedimiento" in text and "terminó" in text
    assert reverse("assessment:matrix", args=[procedure.pk]) in response.content.decode()


def test_a_rejected_proposal_is_in_the_state_count_but_not_in_the_outcome_count(
        evaluated, procedure, operator_user, evaluator_user, client):
    """REQ-058: la propuesta rechazada cuenta como "rechazado" y no tiene resultado efectivo;
    la grilla lo dice y el estado sin decisión se rotula "propuesto" (el de la revisión)."""
    b = evaluated[1]
    declaration = requirement(procedure, "declaración jurada")
    decide(evaluator_user, evaluate.current_result(b, declaration), am.Action.RECHAZAR,
           note="No es así.")
    page = page_of(operator_user, procedure)
    status = {s.offer.pk: s for s in page.statuses}[b.pk]
    assert status.by_state[service.REJECTED] == 1
    assert "no_cumple" not in status.by_outcome and sum(status.by_outcome.values()) == 2
    log_in(client, operator_user)
    text = text_of(client.get(reverse("assessment:matrix", args=[procedure.pk])))
    assert "Propuesta rechazada" in text and "Propuesto" in text
