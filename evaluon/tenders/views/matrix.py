"""Páginas de la matriz: pedir la propuesta, ver la matriz y ver la cobertura (REQ-024,
REQ-025, REQ-028, REQ-030, REQ-032; plan 003, "Pantalla"; ADR-0005; T-074).

- `request_proposal`: el formulario "Proponer matriz" de la página del procedimiento. Pide
  no pide ningún nivel (hay un solo proceso) y llama a `services.matrix.request_matrix`. Un
  pedido correcto redirige a la página del procedimiento, para que recargar no vuelva a
  pedir; uno rechazado (documentos sin leer, borrador abierto, pedido en curso) vuelve a la
  página del procedimiento con el motivo.
- `matrix`: la versión de la matriz, con la franja "BORRADOR INCOMPLETO" si no está
  validada.
- `coverage`: la disposición de cada tramo de la propuesta.

Las funciones de negocio comprueban el rol de la Comisión: sin él, "acceso denegado" (403).
La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.journey.legacy import section_url, to_section
from evaluon.tenders.models import MatrixVersion, Procedure
from evaluon.tenders.services import documents as documents_service
from evaluon.tenders.services import matrix as matrix_service
from evaluon.tenders.services import matrix_page as pages
from evaluon.tenders.views.documents import TEMPLATE as PROCEDURE_TEMPLATE
from evaluon.tenders.views.documents import DocumentForm

MATRIX_TEMPLATE = "tenders/matrix.html"
COVERAGE_TEMPLATE = "tenders/coverage.html"

# Parámetro con que la redirección después de pedir la matriz nombra el pedido.
REQUESTED_PARAM = "pedido"


@require_POST
def request_proposal(request, procedure_id):
    """Pide la propuesta de la matriz: hay un solo proceso, no se elige nivel."""
    try:
        page = documents_service.procedure_page(request.user, procedure_id,
                                                channel=Channel.SCREEN)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    try:
        requested = matrix_service.request_matrix(request.user, page.procedure,
                                                  channel=Channel.SCREEN)
    except matrix_service.MatrixRefused as error:
        return render(request, PROCEDURE_TEMPLATE, {
            "page": page,
            "form": DocumentForm(),
            "loaded": None,
            "matrix_error": str(error),
        })
    return redirect(reverse("tenders:procedure", args=[page.procedure.pk])
                    + f"?{REQUESTED_PARAM}={requested.job.pk}")


def _version_procedure(request, version_id):
    procedure_id = MatrixVersion.objects.filter(pk=version_id).values_list(
        "procedure_id", flat=True).first()
    if procedure_id is None:
        raise Http404("No hay una versión de la matriz con ese número.")
    return section_url("pliego", procedure_id)


@to_section(_version_procedure)
@require_GET
def matrix(request, version_id):
    """La versión de la matriz."""
    try:
        page = pages.matrix_page(request.user, version_id, channel=Channel.SCREEN)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    return render(request, MATRIX_TEMPLATE, {"page": page})


@require_GET
def coverage(request, version_id):
    """La cobertura de la propuesta de la versión."""
    try:
        page = pages.coverage_page(request.user, version_id, channel=Channel.SCREEN)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    return render(request, COVERAGE_TEMPLATE, {"page": page})
