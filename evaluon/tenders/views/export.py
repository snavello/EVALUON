"""Vista de impresión y descarga del PDF de la matriz (REQ-032; plan 003, "Salidas";
ADR-0020; T-086). Sin el rol de la Comisión, "acceso denegado" (403) con el rechazo
registrado. Un PDF que no se pudo generar responde 500 con el motivo dicho en llano."""

import io

from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET

from evaluon.audit.models import Channel
from evaluon.tenders import export as service
from evaluon.tenders.models import MatrixVersion


@require_GET
def print_view(request, version_id):
    """La matriz para imprimir desde el navegador."""
    try:
        html, _page = service.render_html(request.user, version_id, pdf=False,
                                          channel=Channel.SCREEN)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    return HttpResponse(html)


@require_GET
def pdf(request, version_id):
    """Descarga el PDF de la matriz."""
    try:
        data, name = service.export_pdf(request.user, version_id, channel=Channel.SCREEN)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    except service.ExportFailed:
        return HttpResponse("No se pudo generar el PDF de la matriz. El error quedó "
                            "registrado.", status=500, content_type="text/plain; charset=utf-8")
    return FileResponse(io.BytesIO(data), as_attachment=True, filename=name,
                        content_type="application/pdf")
