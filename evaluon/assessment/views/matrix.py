"""Pantalla de la matriz de evaluación y "Evaluar todas las ofertas" (REQ-057, REQ-058,
REQ-059; plan 004, "Pantalla"; T-152).

- `matrix`: ofertas por requisitos con el resultado vigente y el estado de cada par, el estado
  por oferta, los descartes propuestos con su motivo, el orden económico, las preguntas abiertas
  y el aviso de versión. Todo rotulado como propuesta: decide la Comisión.
- `evaluate_all`: el botón "Evaluar todas las ofertas". Un pedido correcto vuelve a la matriz con
  el aviso de las ofertas que quedaron afuera por no tener documentos; uno rechazado (sin matriz
  validada, documentos en lectura, pedido en curso) la muestra con el motivo.

Las funciones de negocio comprueban el rol de la Comisión. La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from evaluon.assessment.services import evaluate
from evaluon.assessment.services import matrix as service
from evaluon.audit.models import Channel
from evaluon.tenders.models import Procedure
from evaluon.journey.legacy import section_url, to_section

MATRIX_TEMPLATE = "assessment/matrix.html"


def _render(request, procedure_id, status=200, **extra):
    try:
        page = service.matrix_page(request.user, procedure_id, channel=Channel.SCREEN)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    return render(request, MATRIX_TEMPLATE, {"page": page, **extra}, status=status)


@to_section(lambda request, procedure_id: section_url("evaluacion", procedure_id))
@require_GET
def matrix(request, procedure_id):
    """La matriz de evaluación del procedimiento."""
    return _render(request, procedure_id)


@require_POST
def evaluate_all(request, procedure_id):
    """Pide la evaluación de todas las ofertas del procedimiento."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    try:
        requested, left_out = service.request_all(request.user, procedure,
                                                  channel=Channel.SCREEN)
    except evaluate.EvaluationRefused as error:
        return _render(request, procedure_id, request_error=str(error))
    return _render(request, procedure_id, requested=requested, left_out=left_out)
