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
