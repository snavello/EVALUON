"""Página de un procedimiento, carga de documentos del pliego y entrega del original
(REQ-023, REQ-028, REQ-031; plan 003, "Carga y lectura" y "Pantalla"; ADR-0005; T-072).

- `procedure`: los datos del procedimiento y su régimen; sus documentos con su tipo, su
  fecha, el estado de la lectura y el enlace al original; si ya se leyeron, sus tramos
  pendientes de revisión (páginas ilegibles o dudosas, tablas, tramos no ubicados); y el
  formulario de carga. Una carga correcta redirige a la misma página, para que recargar
  no vuelva a cargar; una rechazada (sin fecha en una circular, archivo repetido,
  formato que no se lee) vuelve al formulario marcado.
- `document_original`: el original byte por byte, como la vista de la 001: el PDF va
  para el visor del navegador; la página web guardada, aislada con la misma política
  (`norms.views.SAVED_PAGE_CSP`).

Las dos llaman a `services.documents`, que comprueba el rol de la Comisión: sin él,
"acceso denegado" (403) y el rechazo queda registrado. La sesión la exige
`LoginRequiredMiddleware`. La vista no guarda nada en la sesión.
"""

from django import forms
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.csp import CSP, build_policy
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_http_methods

from evaluon.audit.models import Channel
from evaluon.norms.models import FileFormat
from evaluon.norms.views import CONTENT_TYPES, SAVED_PAGE_CSP
from evaluon.queries.forms import DATE_INPUT_FORMATS, INVALID_DATE_ERROR
from evaluon.tenders.models import DocumentFile, DocumentKind, Procedure
from evaluon.tenders.services import documents as services

TEMPLATE = "tenders/procedure.html"

# Parámetro con que la redirección después de la carga nombra al documento cargado.
LOADED_PARAM = "cargado"


class DocumentForm(forms.Form):
    """El formulario de carga. Título y fecha los comprueba la función de carga, para
    que todo rechazo quede registrado."""

    file = forms.FileField(label="Archivo (PDF o página web guardada)")
    kind = forms.ChoiceField(label="Tipo", choices=DocumentKind.choices)
    title = forms.CharField(label="Título", required=False)
    issued_on = forms.DateField(
        label="Fecha del documento (obligatoria en circulares y respuestas)",
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": INVALID_DATE_ERROR},
    )


def _loaded_id(request):
    try:
        return int(request.GET.get(LOADED_PARAM, ""))
    except ValueError:
        return None


@require_http_methods(["GET", "POST"])
def procedure(request, procedure_id):
    """Página del procedimiento con sus documentos y el formulario de carga."""
    try:
        page = services.procedure_page(request.user, procedure_id, channel=Channel.SCREEN)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")

    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            upload = data["file"]
            try:
                loaded = services.load_document(
                    request.user,
                    page.procedure,
                    data=upload.read(),
                    file_name=upload.name,
                    kind=data["kind"],
                    title=data["title"],
                    issued_on=data["issued_on"],
                    channel=Channel.SCREEN,
                )
            except services.DocumentRefused as error:
                form.add_error(error.field if error.field in form.fields else None,
                               str(error))
            else:
                return redirect(
                    reverse("tenders:procedure", args=[page.procedure.pk])
                    + f"?{LOADED_PARAM}={loaded.document.pk}"
                )
    else:
        form = DocumentForm()

    loaded_id = _loaded_id(request) if request.method == "GET" else None
    loaded = next(
        (row.document for row in page.documents if row.document.pk == loaded_id), None
    )
    return render(request, TEMPLATE, {"page": page, "form": form, "loaded": loaded})


@require_GET
def document_original(request, document_id):
    """Entrega byte por byte el original de un documento del pliego."""
    try:
        stored = services.original_file(request.user, document_id, channel=Channel.SCREEN)
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
        response[str(CSP.HEADER_ENFORCE)] = build_policy(SAVED_PAGE_CSP)
    return response
