"""Validar la matriz, descartar un borrador y abrir una versión nueva desde la pantalla
(REQ-027; plan 003, "Pantalla"; ADR-0005; T-082).

Cada botón es un formulario por POST que llama a `services.validation` y vuelve a la
matriz. Un pedido rechazado (pendientes sin resolver, consecuencias sin elegir, versión ya
validada) vuelve a mostrar la matriz con el motivo, sin cambiar nada. Sin el rol que la
acción pide, "acceso denegado" (403) y el rechazo queda registrado. No guarda nada en la
sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from evaluon.audit.models import Channel
from evaluon.tenders.models import MatrixVersion, Procedure
from evaluon.tenders.services import matrix_page as pages
from evaluon.tenders.services import validation as service

MATRIX_TEMPLATE = "tenders/matrix.html"


def _version(version_id):
    try:
        return MatrixVersion.objects.get(pk=version_id)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")


def _refused(request, version, error):
    page = pages.matrix_page(request.user, version.pk, channel=Channel.SCREEN)
    return render(request, MATRIX_TEMPLATE, {
        "page": page, "review_error": str(error), "review_error_field": error.field,
    }, status=400)


@require_POST
def validate(request, version_id):
    version = _version(version_id)
    try:
        service.validate(request.user, version_id, channel=Channel.SCREEN)
    except service.ValidationRefused as error:
        return _refused(request, version, error)
    return redirect(reverse("tenders:matrix", args=[version_id]))


@require_POST
def discard(request, version_id):
    version = _version(version_id)
    try:
        service.discard(request.user, version_id, channel=Channel.SCREEN)
    except service.ValidationRefused as error:
        return _refused(request, version, error)
    return redirect(reverse("tenders:procedure", args=[version.procedure_id]))


@require_POST
def open_new(request, procedure_id):
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    try:
        new = service.open_new_version(request.user, procedure_id, channel=Channel.SCREEN)
    except service.ValidationRefused as error:
        latest = (service.latest_validated(procedure)
                  or procedure.matrix_versions.order_by("-number").first())
        if latest is None:
            return redirect(reverse("tenders:procedure", args=[procedure_id]))
        return _refused(request, latest, error)
    return redirect(reverse("tenders:matrix", args=[new.pk]))
