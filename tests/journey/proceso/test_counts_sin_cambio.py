"""`matriz_evaluacion.counts` es público y `compute` da el mismo estado y los mismos textos
(REQ-145; T-342). Caso chico inventado (P4)."""

import pytest

from evaluon.assessment import models as am
from evaluon.journey import memo
from evaluon.journey.stages import base, matriz_evaluacion
from tests.assessment.test_matrix import add_run, decide, requirement

pytestmark = pytest.mark.django_db


def test_counts_sin_evaluacion(procedure, two_offers, operator_user):
    """REQ-145: sin evaluación todas las cuentas son cero."""
    page = memo.matrix_page(operator_user, procedure.pk)
    assert tuple(matriz_evaluacion.counts(page)) == (0, 0, 0, 0)


def test_counts_y_compute_coinciden(procedure, offer, operator_user, evaluator_user):
    """REQ-145: las cuentas públicas suman lo que `compute` informa y el texto no cambia."""
    declaration = requirement(procedure, "declaración jurada")
    registry = requirement(procedure, "constancia de inscripción")
    saved = add_run(operator_user, procedure, offer,
                    {declaration: "cumple", registry: "cumple"})
    found = matriz_evaluacion.counts(memo.matrix_page(operator_user, procedure.pk))
    assert found.pairs == 2 and found.pending == 2
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert stage.state == base.A_DECIDIR and stage.pending == found.pending
    assert stage.detail == "Falta decidir: 2 pares por decidir."

    decide(evaluator_user, saved[declaration.pk], am.Action.CONFIRMAR)
    found = matriz_evaluacion.counts(memo.matrix_page(operator_user, procedure.pk))
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert found.pending == stage.pending == 1
    assert stage.detail == "Falta decidir: 1 par por decidir."


# --- Los otros tres tipos de cuenta (hallazgo 2 del testeador) -------------------------------
# Los textos son los que `compute` ya daba en main; se corrieron contra main antes de fijarlos.

from django.utils import timezone  # noqa: E402

from evaluon.assessment.services import technical  # noqa: E402
from evaluon.tenders import models as m  # noqa: E402
from tests.assessment.test_matrix import open_matrix  # noqa: E402
from tests.journey.test_stage_matriz_evaluacion import (  # noqa: E402,F401
    ask,
    declaration,
    registry,
    technical_offer,
)


def _page(user, procedure):
    return memo.matrix_page(user, procedure.pk)


def test_preguntas_abiertas(procedure, offer, operator_user, evaluator_user, declaration):  # noqa: F811
    """REQ-145: una pregunta sin respuesta suma a `questions` y a `pending`."""
    saved = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    result = saved[declaration.pk]
    decide(evaluator_user, result, am.Action.CONFIRMAR)
    ask(procedure, offer, declaration, result)
    found = matriz_evaluacion.counts(_page(operator_user, procedure))
    assert tuple(found) == (0, 1, 0, 0) and found.pending == 1
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert (stage.state, stage.pending) == (base.A_DECIDIR, 1)
    assert stage.detail == "Falta decidir: 1 pregunta abierta."


def test_ok_tecnico_pendiente(procedure, technical_offer, declaration,  # noqa: F811
                              operator_user, evaluator_user):
    """REQ-145: las filas técnicas sin ok cuentan una vez por oferta en `reports`."""
    _, saved = technical_offer
    decide(evaluator_user, saved[declaration.pk], am.Action.CONFIRMAR)
    found = matriz_evaluacion.counts(_page(operator_user, procedure))
    assert tuple(found) == (0, 0, 1, 0) and found.pending == 1
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert (stage.state, stage.pending) == (base.A_DECIDIR, 1)
    assert stage.detail == "Falta decidir: 1 oferta sin informe técnico."


def test_descarte_propuesto(procedure, offer, operator_user, declaration):  # noqa: F811
    """REQ-145: un descarte propuesto sin decidir suma a `discards`, junto con su par."""
    open_matrix()
    m.Consequence.objects.create(
        requirement=declaration, consequence_type="desestimacion", grounds=[],
        origin="persona", chosen=True, chosen_by=operator_user, chosen_at=timezone.now(),
        chosen_note="El pliego desestima sin subsanar.")
    add_run(operator_user, procedure, offer, {declaration: "no_cumple"})
    found = matriz_evaluacion.counts(_page(operator_user, procedure))
    assert tuple(found) == (1, 0, 0, 1) and found.pending == 2
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert (stage.state, stage.pending) == (base.A_DECIDIR, 2)
    assert stage.detail == "Falta decidir: 1 par por decidir; 1 descarte propuesto."


def test_los_cuatro_tipos_juntos(procedure, technical_offer, offer, declaration,  # noqa: F811
                                 operator_user, evaluator_user):
    """REQ-145: la suma de `pending` es la de las cuatro cuentas."""
    other = add_run(operator_user, procedure, offer, {declaration: "cumple"})
    ask(procedure, offer, declaration, other[declaration.pk])
    found = matriz_evaluacion.counts(_page(evaluator_user, procedure))
    assert tuple(found) == (2, 1, 1, 0) and found.pending == 4
    assert matriz_evaluacion.compute(evaluator_user, procedure).pending == 4
