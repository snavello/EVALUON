"""Entrega del documento original (REQ-002; plan 001, "Documento original"; ADR-0005).

La sesión la exige `LoginRequiredMiddleware` (settings.py) para toda página salvo la de
ingreso: sin sesión, esta vista no se ejecuta y se redirige al ingreso.
"""

from django.http import Http404, HttpResponse
from django.utils.csp import CSP, build_policy
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET

from evaluon.norms.models import DocumentFile, FileFormat

# Una página web guardada (las de Infoleg traen scripts de medición) se aísla con la
# cabecera, sin modificar el archivo. `sandbox` sin permisos impide ejecutar scripts,
# enviar formularios y abrir ventanas, y le da a la página un origen propio, sin acceso
# a la sesión. `default-src 'none'` impide cargar recursos, de internet o del propio
# servidor; solo se admite el estilo escrito dentro de la página, que no carga nada.
SAVED_PAGE_CSP = {
    "default-src": [CSP.NONE],
    "style-src": [CSP.UNSAFE_INLINE],
    "base-uri": [CSP.NONE],
    "form-action": [CSP.NONE],
    "frame-ancestors": [CSP.NONE],
    "sandbox": True,
}

# Sin `charset`: el archivo sale tal cual y el navegador usa la codificación que declara
# la propia página (windows-1252 o ISO-8859-1 en las de Infoleg).
CONTENT_TYPES = {
    FileFormat.PDF: "application/pdf",
    FileFormat.HTML: "text/html",
}


@require_GET
def original(request, document_id):
    """Entrega byte por byte el archivo original de un documento (una parte de una
    norma). El PDF va para el visor del navegador; la página web guardada, aislada."""
    try:
        stored = DocumentFile.objects.select_related("document").get(
            document_id=document_id
        )
    except DocumentFile.DoesNotExist:
        raise Http404("No hay un documento original con ese número.")
    document = stored.document

    response = HttpResponse(
        bytes(stored.content), content_type=CONTENT_TYPES[document.file_format]
    )
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=False, filename=document.file_name
    )
    if document.file_format == FileFormat.HTML:
        # Con la cabecera ya puesta, el middleware no agrega la política general.
        response[str(CSP.HEADER_ENFORCE)] = build_policy(SAVED_PAGE_CSP)
    return response
