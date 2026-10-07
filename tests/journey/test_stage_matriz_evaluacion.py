"""Estado de la etapa Matriz de evaluación del recorrido (REQ-066, REQ-068, REQ-069, REQ-072;
T-182). Caso chico inventado (P4); los resultados se guardan directo, sin el modelo."""

import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.assessment.services import review, technical
from evaluon.journey.stages import base, matriz_evaluacion
from evaluon.tenders import models as m
from tests.assessment.test_matrix import DECLARATION, add_run, decide, open_matrix, requirement
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

PENDING_OK = ("no_determinado", "pendiente_informe_tecnico")


@pytest.fixture
def declaration(procedure):
    return requirement(procedure, "declaración jurada")


@pytest.fixture
def registry(procedure):
    return requirement(procedure, "constancia de inscripción")


def decided(user, results, action=am.Action.CONFIRMAR):
    for result in results.values():
        decide(user, result, action)


def ask(procedure, offer, requirement_, result):
    return am.Question.objects.create(
        procedure=procedure, requirement=requirement_, offer=offer, result=result,
        text="¿Está vigente?", reason="externo")


def test_without_any_evaluation_the_stage_is_pending(procedure, two_offers, operator_user):
    """REQ-066: sin ninguna evaluación la etapa está pendiente y no cuenta nada."""
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.state == base.PENDIENTE
    assert (stage.pending, stage.suggestions) == (0, 0)
    assert "evaluación" in stage.detail


def test_undecided_pairs_make_the_stage_to_decide_with_their_count(
        procedure, offer, operator_user, declaration, registry):
    """REQ-066: los pares `propuesto` ponen la etapa a decidir con su cuenta."""
    add_run(operator_user, procedure, offer, {declaration: "cumple", registry: "cumple"})
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert stage.pending == 2
    assert "2 pares" in stage.detail


def test_decided_pairs_are_not_counted(procedure, offer, operator_user, evaluator_user,
                                       declaration, registry):
    """REQ-066: un par confirmado ya no espera; el otro sigue contando."""
    saved = add_run(operator_user, procedure, offer,
                    {declaration: "cumple", registry: "cumple"})
    decide(evaluator_user, saved[declaration.pk], am.Action.CONFIRMAR)
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.pending == 1


def test_an_open_question_counts_by_itself(procedure, offer, operator_user, evaluator_user,
                                           declaration):
    """REQ-066: una pregunta sin respuesta cuenta aunque todos los pares estén decididos, y
    lleva al evaluador a las preguntas."""
    saved = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    result = saved[declaration.pk]
    decide(evaluator_user, result, am.Action.CONFIRMAR)
    ask(procedure, offer, declaration, result)
    stage = matriz_evaluacion.compute(evaluator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert stage.pending == 1
    assert "1 pregunta" in stage.detail
    assert stage.decide_url == reverse("assessment:questions", args=[procedure.pk])


def test_an_answered_question_does_not_count(procedure, offer, operator_user, evaluator_user,
                                             declaration):
    """REQ-066: con respuesta la pregunta ya no espera."""
    saved = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    result = saved[declaration.pk]
    decide(evaluator_user, result, am.Action.CONFIRMAR)
    question = ask(procedure, offer, declaration, result)
    am.Answer.objects.create(question=question, text="Sí.", answered_by=evaluator_user,
                             event=result.decisions.get().event)
    assert matriz_evaluacion.compute(operator_user, procedure).state == base.LISTA


@pytest.fixture
def technical_offer(procedure, operator_user, declaration):
    """Una oferta con la declaración cumplida y los renglones 1 a 3 pendientes del ok."""
    offer = make_offer(procedure, operator_user, "Oferente Z",
                       {"oferta.pdf": [f"{DECLARATION}. Texto de la oferta."]})
    rows = {i: requirement(procedure, item=i) for i in (1, 2, 3)}
    saved = add_run(operator_user, procedure, offer,
                    {declaration: "cumple", **{r: PENDING_OK for r in rows.values()}})
    return offer, saved


def test_pending_technical_ok_counts_once_per_offer_and_not_as_pairs(
        procedure, technical_offer, declaration, operator_user, evaluator_user):
    """REQ-066/REQ-068: las filas técnicas sin ok cuentan una vez por oferta y sus pares no se
    suman otra vez como pares por decidir."""
    _, saved = technical_offer
    decide(evaluator_user, saved[declaration.pk], am.Action.CONFIRMAR)
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR
    assert stage.pending == 1
    assert "informe técnico" in stage.detail


def test_after_the_technical_ok_the_stage_is_ready(procedure, technical_offer, declaration,
                                                   operator_user, evaluator_user):
    """REQ-066: con el ok dado y todo decidido la etapa queda lista."""
    offer, saved = technical_offer
    decide(evaluator_user, saved[declaration.pk], am.Action.CONFIRMAR)
    technical.give_ok(evaluator_user, offer, verdicts={1: "apto", 2: "apto", 3: "apto"})
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert (stage.state, stage.pending) == (base.LISTA, 0)


def test_the_three_kinds_add_up_and_are_detailed(procedure, technical_offer, offer,
                                                 declaration, operator_user, evaluator_user):
    """REQ-066: los tres tipos juntos suman y el detalle los nombra por separado."""
    other = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    ask(procedure, offer, declaration, other[declaration.pk])
    stage = matriz_evaluacion.compute(evaluator_user, procedure)
    # Pares: la declaración de cada oferta (2); preguntas: 1; ok técnico: 1 oferta.
    assert stage.pending == 4
    assert "2 pares" in stage.detail and "1 pregunta" in stage.detail
    assert "1 oferta" in stage.detail and "informe técnico" in stage.detail
    assert stage.decide_url == reverse("assessment:matrix", args=[procedure.pk])


def test_all_decided_is_ready(procedure, offer, operator_user, evaluator_user, declaration):
    """REQ-066: sin pendientes la etapa está lista."""
    saved = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    decided(evaluator_user, saved)
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert (stage.state, stage.pending) == (base.LISTA, 0)


def test_suggestions_are_counted_apart_from_pending(procedure, offer, operator_user,
                                                    evaluator_user, declaration):
    """REQ-072: el descarte propuesto es una sugerencia, se cuenta aparte y no suma a lo
    pendiente (que sigue siendo el par por decidir)."""
    open_matrix()
    m.Consequence.objects.create(
        requirement=declaration, consequence_type="desestimacion", grounds=[],
        origin="persona", chosen=True, chosen_by=operator_user, chosen_at=timezone.now(),
        chosen_note="El pliego desestima sin subsanar.")
    add_run(operator_user, procedure, offer, {declaration: "no_cumple"})
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.suggestions == 1
    assert stage.pending == 1
    assert "Sugerencias del sistema: 1 descarte" in stage.detail


def test_computing_the_stage_changes_no_pair_state(procedure, offer, operator_user,
                                                   declaration, registry):
    """REQ-066: la etapa solo lee: el estado de cada par y la cantidad de filas no cambian."""
    saved = add_run(operator_user, procedure, offer,
                    {declaration: "cumple", registry: "cumple"})
    before = {pk: review.state_of(r) for pk, r in saved.items()}
    counts = (am.Decision.objects.count(), am.Result.objects.count(),
              am.Question.objects.count())
    matriz_evaluacion.compute(operator_user, procedure)
    assert {pk: review.state_of(r) for pk, r in saved.items()} == before
    assert (am.Decision.objects.count(), am.Result.objects.count(),
            am.Question.objects.count()) == counts


def test_links_and_roles(procedure, offer, operator_user, evaluator_user, declaration):
    """REQ-068/REQ-069: el enlace de ver resuelve a la matriz y solo el evaluador recibe el
    de decidir."""
    add_run(operator_user, procedure, offer, {declaration: "cumple"})
    as_operator = matriz_evaluacion.compute(operator_user, procedure)
    as_evaluator = matriz_evaluacion.compute(evaluator_user, procedure)
    assert as_operator.view_url == reverse("assessment:matrix", args=[procedure.pk])
    assert as_operator.decide_url is None
    assert as_evaluator.decide_url == as_evaluator.view_url
    assert as_evaluator.key == "matriz_evaluacion"


def test_the_queries_stay_bounded(procedure, offer, operator_user, declaration, registry):
    """Rendimiento: se mide el costo de la etapa con el caso chico (se anota en la
    verificación)."""
    add_run(operator_user, procedure, offer, {declaration: "cumple", registry: "cumple"})
    started = time.perf_counter()
    with CaptureQueriesContext(connection) as queries:
        matriz_evaluacion.compute(operator_user, procedure)
    print(f"matriz_evaluacion: {len(queries)} consultas, "
          f"{time.perf_counter() - started:.3f} s")
    assert len(queries) < 80
