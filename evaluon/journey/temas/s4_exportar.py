"""Tema s4_exportar: exportar la evaluación (sección «Evaluación y dictamen»; REQ-093; plan 014,
T-212; ADR-0050).

Bloque «Exportar», al pie de la pestaña: la planilla por oferta y el cuadro comparativo, cada uno
en Excel y en PDF, como en la maqueta aprobada. Cada botón es un enlace de descarga a
`evaluacion/exportar/<documento>/<formato>/`; el archivo y el hecho de auditoría `eval_export`
los hace `assessment.services.export` (con los mismos números de la pantalla; todo rotulado como
propuesta de evaluación). Sin el rol de la Comisión, «acceso denegado» (403). No tiene pendientes
ni sugerencias: es una salida, no una tarea.
"""

import io

from django.http import FileResponse, Http404, HttpResponse
from django.urls import path, reverse
from django.views.decorators.http import require_GET

from evaluon.assessment.services import export as service
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import TemaStatus
from evaluon.tenders.models import Procedure

KEY = "s4_exportar"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_exportar.html"
CHANNEL = Channel.SCREEN

DOCUMENTS = (
    (service.PLANILLA, "Planilla por oferta"),
    (service.CUADRO, "Cuadro comparativo"),
)
FORMATS = ((service.XLSX, "Excel"), (service.PDF, "PDF"))


def status(user, procedure):
    """Una salida: no suma pendientes, sugerencias ni faltantes."""
    return TemaStatus()


def context(user, procedure, request):
    rows = [{
        "label": label,
        "links": [(fmt_label, reverse("expedientes:s4_exportar_archivo",
                                      args=[procedure.pk, document, fmt]))
                  for fmt, fmt_label in FORMATS],
    } for document, label in DOCUMENTS]
    return {"pid": procedure.pk, "rows": rows,
            "has_offers": procedure.offers.exists()}


@require_GET
def download(request, procedure_id, document, fmt):
    """Baja el archivo. 404 si el documento o el formato no existen; 403 sin rol; 500 con el
    motivo en llano si el generador falla (queda registrado)."""
    try:
        content, name, content_type = service.export(
            request.user, procedure_id, document, fmt, channel=CHANNEL)
    except (service.ExportRefused, Procedure.DoesNotExist):
        raise Http404("No hay nada para exportar con ese pedido.")
    except service.ExportFailed:
        return HttpResponse("No se pudo generar el archivo. El error quedó registrado.",
                            status=500, content_type="text/plain; charset=utf-8")
    return FileResponse(io.BytesIO(content), as_attachment=True, filename=name,
                        content_type=content_type)


urlpatterns = [
    path("evaluacion/exportar/<str:document>/<str:fmt>/", download,
         name="s4_exportar_archivo"),
]
