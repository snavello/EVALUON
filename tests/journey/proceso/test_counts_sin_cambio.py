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
