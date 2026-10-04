"""Vista de impresión y PDF de una versión de la matriz (REQ-032; plan 003, "Salidas:
impresión y PDF"; ADR-0020; principio P4; T-086).

- Una sola plantilla (`tenders/matrix_print.html`) para la vista de impresión del navegador
  y para el PDF. Toda versión que no esté validada (borrador o descartada) lleva la leyenda
  "BORRADOR INCOMPLETO"; la validada lleva su versión, la fecha y quién la validó.
- El PDF se genera dentro del equipo con WeasyPrint, en el mismo pedido de la pantalla.
  WeasyPrint por omisión busca los recursos de la página por red; acá un `URLFetcher`
  propio solo entrega la hoja de estilos de impresión desde el disco y rechaza todo lo demás
  con un error que corta la generación (nada de buscar afuera).
- Cada exportación deja el hecho `matrix_export` con la versión, su estado, si llevó la
  leyenda, la cantidad de páginas y la huella del PDF entregado. Una exportación que falla
  deja el hecho en resultado `failed`. La vista de impresión no se registra: no produce un
  archivo.

Los datos salen de `matrix_page`, que comprueba el rol de la Comisión (el operador y el
evaluador pueden ver, imprimir y exportar).
"""

import dataclasses
import hashlib
import re
from pathlib import Path

from django.template.loader import render_to_string
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher, URLFetcherResponse

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.services import matrix_page as pages

PRINT_TEMPLATE = "tenders/matrix_print.html"
EXPORT_OPERATION = "evaluon.tenders.export.export_pdf"

LEGEND = "BORRADOR INCOMPLETO"

# La hoja de estilos de impresión: la única dirección que el generador entrega. Es una
# dirección interna; el contenido sale de este archivo del disco.
PRINT_CSS_URL = "file:///evaluon-print/print.css"
PRINT_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "tenders" / "print.css"
BASE_URL = "file:///evaluon-print/"


class ExportFailed(Exception):
    """No se pudo generar el PDF. `reason` queda en el registro."""

    def __init__(self, message, reason="render_failed"):
        super().__init__(message)
        self.reason = reason


class LocalOnlyFetcher(URLFetcher):
    """Entrega `print.css` desde el disco y rechaza cualquier otra dirección, sea de red o
    de archivo. El error es fatal para WeasyPrint: la generación se corta en lugar de
    seguir sin el recurso."""

    def __init__(self):
        super().__init__(allowed_protocols=("file",))
        self.requested = []

    def fetch(self, url, headers=None):
        self.requested.append(url)
        if url != PRINT_CSS_URL:
            raise FatalURLFetchingError(
                f"El PDF de la matriz no admite recursos externos: {url}")
        return URLFetcherResponse(
            url, body=PRINT_CSS_PATH.read_bytes(), headers={"Content-Type": "text/css"})


def _print_page(page):
    """La página sin acciones de edición, para que las consecuencias salgan de solo
    lectura."""
    return dataclasses.replace(page, can_edit=False, can_confirm=False,
                               can_validate=False, can_open_new=False,
                               segment_options=[])


def render_html(user, version_id, *, pdf, channel=Channel.SCREEN):
    """El HTML de la matriz. Devuelve `(html, page)`. Lanza `RoleRejected` sin rol de la
    Comisión y `MatrixVersion.DoesNotExist` si no existe."""
    page = pages.matrix_page(user, version_id, channel=channel)
    html = render_to_string(PRINT_TEMPLATE, {
        "page": _print_page(page),
        "pdf": pdf,
        "css_href": PRINT_CSS_URL if pdf else _static_css(),
        "legend": page.draft,
    })
    return html, page


def _static_css():
    from django.templatetags.static import static
    return static("tenders/print.css")


def html_to_pdf(html):
    """Convierte el HTML en PDF con WeasyPrint. Devuelve `(bytes, páginas)`. Cualquier fallo
    (también un recurso externo) lanza `ExportFailed`."""
    fetcher = LocalOnlyFetcher()
    try:
        document = HTML(string=html, base_url=BASE_URL, url_fetcher=fetcher).render()
        data = document.write_pdf()
    except FatalURLFetchingError as error:
        raise ExportFailed(str(error), "external_resource") from error
    except Exception as error:  # noqa: BLE001 - toda falla del generador se informa igual
        raise ExportFailed(f"No se pudo generar el PDF: {error}") from error
    return data, len(document.pages)


def file_name(page):
    """`matriz-<procedimiento>-v<N>[-borrador].pdf`."""
    number = re.sub(r"[^A-Za-z0-9._-]+", "-", page.procedure.number).strip("-") or "sin-numero"
    suffix = "-borrador" if page.draft else ""
    return f"matriz-{number}-v{page.version.number}{suffix}.pdf"


def export_pdf(user, version_id, *, channel=Channel.SCREEN):
    """Genera el PDF de la versión y deja el hecho `matrix_export`. Devuelve
    `(bytes, nombre del archivo)`."""
    html, page = render_html(user, version_id, pdf=True, channel=channel)
    detail = {"procedure": page.procedure.pk, "version": page.version.pk,
              "version_number": page.version.number, "status": page.version.status,
              "legend": page.draft}
    try:
        data, page_count = html_to_pdf(html)
    except ExportFailed as error:
        audit.record(EventType.MATRIX_EXPORT, outcome=Outcome.FAILED, channel=channel,
                     user=user, detail={**detail, "reason": error.reason,
                                        "message": str(error)})
        raise
    name = file_name(page)
    audit.record(EventType.MATRIX_EXPORT, outcome=Outcome.OK, channel=channel, user=user,
                 detail={**detail, "pages": page_count, "file_name": name,
                         "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return data, name
