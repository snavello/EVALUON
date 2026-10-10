"""Errores gruesos de la revisión C en Evaluación y dictamen (REQ-090, REQ-089, REQ-097; plan 014,
T-231): evaluar de nuevo los pares respondidos desde la pestaña, con aviso claro si ya hay un
pedido, y la situación del orden económico. Material inventado (P4); sin el modelo."""

import html as htmllib
import re

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import questions
from evaluon.tenders.models import JobStatus
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    evaluated,
    requirement,
    three,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def notice(client, response):
    assert response.status_code == 302
    page_ = client.get(response["Location"])
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)" id="s4-aviso"[^>]*>(.*?)</p>',
                      page_.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


@pytest.fixture
def answered(evaluated, procedure, evaluator_user):
    """Una pregunta sobre la declaración jurada, respondida con alcance «requisito»: alcanza a
    las tres ofertas, que siguen con el resultado de antes de la respuesta."""
    a, b, c = evaluated
    declaration = requirement(procedure, "declaración jurada")
    question = am.Question.objects.create(
        procedure=procedure, requirement=declaration, offer=b,
        result=am.Result.objects.get(offer=b, requirement=declaration),
        text="¿La firma es del apoderado?")
    given = questions.answer(evaluator_user, question.pk, "Sí, figura en el poder.").answer
    return evaluated, declaration, given


def evaluate_again_url(procedure):
    return reverse("expedientes:s4_evaluar_respondidas", args=[procedure.pk])


def test_the_tab_offers_to_evaluate_again_the_answered_pairs(client, answered, procedure,
                                                             evaluator_user, operator_user):
    """REQ-090, E-3: después de responder, la pestaña ofrece «Evaluar de nuevo los N pares
    respondidos» (un solo pedido) al evaluador; el operador no ve el botón."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert "Evaluar de nuevo los 3 pares respondidos" in html
    assert evaluate_again_url(procedure) in html
    client.logout()
    log_in(client, operator_user)
    assert "pares respondidos" not in client.get(tab(procedure)).content.decode()


def test_the_button_makes_one_request_with_the_answer_as_origin(client, answered, procedure,
                                                                evaluator_user):
    """REQ-090, REQ-056, E-3: un solo pedido para todos los pares respondidos, con la causa
    «respuesta» y la respuesta de origen; el aviso dice cuántos."""
    (a, b, c), declaration, given = answered
    log_in(client, evaluator_user)
    before = am.Request.objects.count()
    ok, text = notice(client, client.post(evaluate_again_url(procedure)))
    assert ok and "3 pares respondidos" in text
    assert am.Request.objects.count() == before + 1
    request = am.Request.objects.latest("pk")
    assert request.cause == am.Cause.RESPUESTA and request.answer_id == given.pk
    assert sorted(request.offers) == sorted([a.pk, b.pk, c.pk])
    assert request.requirements == [declaration.pk]


def test_a_second_request_while_one_is_waiting_gives_a_clear_notice_not_a_422(
        client, answered, procedure, evaluator_user, simulate):
    """REQ-090, E-3: con un pedido en espera que cubre los pares, el aviso dice que los pares
    respondidos se suman cuando termine; no hay un 422 mudo ni un pedido nuevo."""
    offers, _, _ = answered
    simulate(list(offers), JobStatus.QUEUED)
    log_in(client, evaluator_user)
    before = am.Request.objects.count()
    ok, text = notice(client, client.post(evaluate_again_url(procedure)))
    assert not ok
    assert "Ya hay una evaluación en espera; los pares respondidos se suman cuando termine" in text
    assert am.Request.objects.count() == before
    # D-2: con el pedido en espera no se ofrece el botón; el texto remite al avance de la pestaña.
    html = client.get(tab(procedure)).content.decode()
    assert "pares respondidos</button>" not in html and evaluate_again_url(procedure) not in html
    assert 'id="preg-reevaluar-motivo"' in html and 'href="#s4-avance"' in html
    assert 'id="s4-avance"' in html  # el enlace existe en la pestaña


def test_with_a_request_running_the_notice_says_to_evaluate_again_when_it_ends(
        client, answered, procedure, evaluator_user, simulate):
    """REQ-090, E-3: con el pedido en curso los pares respondidos no se pueden sumar: el aviso
    dice que se evalúe de nuevo cuando termine."""
    offers, _, _ = answered
    simulate(list(offers), JobStatus.RUNNING, done=1)
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(evaluate_again_url(procedure)))
    assert not ok and "evaluá de nuevo los pares respondidos cuando termine" in text


def test_once_evaluated_again_the_pair_is_no_longer_offered(answered, procedure, operator_user):
    """REQ-090, E-3: un par con una evaluación posterior a la respuesta ya no figura entre los
    pares respondidos por evaluar de nuevo."""
    (a, b, c), declaration, _ = answered
    assert len(questions.answered_pairs(procedure)) == 3
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    pairs = questions.answered_pairs(procedure)
    assert [offer.pk for offer, _, _ in pairs.pairs] == [b.pk, c.pk]


def test_a_pair_the_commission_already_decided_is_not_offered(answered, procedure,
                                                              evaluator_user):
    """P3, E-3: un par que la Comisión decidió no se vuelve a evaluar sin que lo pida."""
    from evaluon.assessment.services import review

    (a, b, c), declaration, _ = answered
    result = am.Result.objects.get(offer=a, requirement=declaration)
    review.confirm(evaluator_user, result.pk)
    assert [offer.pk for offer, _, _ in questions.answered_pairs(procedure).pairs] == [
        b.pk, c.pk]


# --- E-9: la situación del orden económico es la verdadera ---------------------------------------

from decimal import Decimal  # noqa: E402

from evaluon.assessment.services import discards, export, remedy  # noqa: E402,F401
from tests.assessment.test_ordering import portal, quote_data  # noqa: E402,F401,F811


def situations(client, procedure):
    html = client.get(tab(procedure)).content.decode()
    block = html.split('id="s4-resultado"', 1)[1]
    return re.findall(r"<tr[^>]*>\s*<td[^>]*>.*?</tr>", block, re.S)


@pytest.fixture
def ordered(evaluated, portal, procedure):  # noqa: F811
    """Las tres ofertas del caso chico con total en el Portal (entran al orden)."""
    a, b, c = evaluated
    for offer, total in ((a, 900), (b, 100), (c, 500)):
        quote_data(portal, procedure, offer, total=Decimal(total))
    return evaluated


def situation_of(client, procedure, offer):
    html = client.get(tab(procedure)).content.decode()
    block = html.split('id="s4-resultado"', 1)[1].split('id="s4-descartes"', 1)[0]
    rows = [r for r in re.findall(r"<tr.*?</tr>", block, re.S)
            if f"{offer.number} · {offer.bidder}" in r]
    row = rows[-1]  # la tabla del orden económico (la primera es la de resultados)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", row))


def test_an_offer_with_a_missing_document_and_no_decision_is_not_without_observations(
        client, ordered, procedure, operator_user):
    """REQ-091, E-9: la oferta C no encontró la constancia de inscripción y la subsanación está
    por decidir: la situación lo dice, no «Sin observaciones»; A y B, sin nada, sí."""
    a, b, c = ordered
    log_in(client, operator_user)
    text = situation_of(client, procedure, c)
    assert "Sin observaciones" not in text
    assert "No se encontró el documento (requisito" in text
    assert "Subsanación por decidir" in text
    assert "Sin observaciones" in situation_of(client, procedure, a)


def test_a_requested_remedy_is_in_the_situation(client, ordered, procedure, evaluator_user):
    """REQ-091, E-9: con la subsanación pedida, la situación dice «Subsanación pedida»."""
    a, b, c = ordered
    registry = requirement(procedure, "constancia de inscripción")
    result = am.Result.objects.get(offer=c, requirement=registry)
    remedy.request_remedy(evaluator_user, result.pk, "Falta la constancia del registro.")
    log_in(client, evaluator_user)
    text = situation_of(client, procedure, c)
    assert "Subsanación pedida" in text and "Subsanación por decidir" not in text
    assert "Sin observaciones" not in text


def test_an_offer_not_evaluated_is_without_evaluating_not_without_observations(
        client, ordered, procedure, operator_user, portal):  # noqa: F811
    """REQ-091, E-9: una oferta que no se evaluó figura «Sin evaluar»."""
    from tests.offers.conftest import make_offer

    fourth = make_offer(procedure, operator_user, "Oferente D",
                        {"oferta.pdf": ["Texto de la oferta D."]})
    quote_data(portal, procedure, fourth, total=Decimal(700))
    log_in(client, operator_user)
    text = situation_of(client, procedure, fourth)
    assert "Sin evaluar" in text and "Sin observaciones" not in text


def test_the_export_says_the_same_situation(ordered, procedure, operator_user):
    """REQ-091, E-9: la exportación del orden usa la misma situación que la pantalla."""
    a, b, c = ordered
    data = export.collect(operator_user, procedure.pk)
    by_offer = {t.offer: t.situation for t in data.totals}
    assert "Sin observaciones" not in by_offer[f"{c.number} · {c.bidder}"]
    assert "No se encontró el documento" in by_offer[f"{c.number} · {c.bidder}"]
    assert by_offer[f"{a.number} · {a.bidder}"] == "Sin observaciones"


# --- D-2: el botón solo se ofrece si el pedido se puede hacer -----------------------------------------


@pytest.fixture
def answered_with_a_decided_pair(answered, procedure, evaluator_user):
    """Además de la respuesta sobre la declaración (tres ofertas), una respuesta por par sobre la
    garantía de la oferta C, y la Comisión ya decidió el par de la oferta A en la declaración."""
    from evaluon.assessment.services import review

    (a, b, c), declaration, _ = answered
    guarantee = requirement(procedure, "garantía de mantenimiento")
    question = am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=c,
        result=am.Result.objects.get(offer=c, requirement=guarantee),
        text="¿La garantía está vigente?")
    questions.answer(evaluator_user, question.pk, "Está vigente.", am.AnswerScope.PAR)
    review.confirm(evaluator_user, am.Result.objects.get(offer=a, requirement=declaration).pk)
    return (a, b, c), declaration, guarantee


def test_the_request_never_includes_a_decided_pair_and_the_button_says_what_it_asks(
        client, answered_with_a_decided_pair, procedure, evaluator_user):
    """REQ-090, D-2: con un par decidido entre los respondidos, el botón ofrece el grupo que se
    puede pedir sin un par de más (los 2 pares sin decidir de la declaración) y avisa lo que
    queda; al apretarlo, el pedido se hace y no se rechaza."""
    (a, b, c), declaration, guarantee = answered_with_a_decided_pair
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert "Evaluar de nuevo los 2 pares respondidos" in html
    assert "Quedan 1 par respondido que se piden después" in html
    before = am.Request.objects.count()
    ok, text = notice(client, client.post(evaluate_again_url(procedure)))
    assert ok and "2 pares respondidos" in text and "Quedan 1 par respondido" in text
    assert am.Request.objects.count() == before + 1
    request = am.Request.objects.latest("pk")
    assert sorted(request.offers) == sorted([b.pk, c.pk])
    assert request.requirements == [declaration.pk]


def test_the_answered_pairs_are_grouped_in_exact_rectangles(answered_with_a_decided_pair,
                                                            procedure):
    """REQ-090, D-2: los requisitos que alcanzan las mismas ofertas van juntos; ningún grupo
    evalúa un par de más."""
    (a, b, c), declaration, guarantee = answered_with_a_decided_pair
    groups = questions.answered_pairs(procedure).groups
    assert [len(g) for g in groups] == [2, 1]
    for group in groups:
        assert len(group) == len(group.offers) * len(group.requirements)
