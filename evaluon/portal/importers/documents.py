"""Ítems `documento` (T-142; REQ-046, REQ-048, REQ-049, REQ-051).

Explorar: por cada documento de la página (pliego, cláusulas, anexos, circulares, actos,
acta y dictamen) lo baja con el cliente acotado (GET de la URL directa, o envío de formulario
de ASP.NET con los campos ocultos de la página), lo guarda tal cual en `portal_file` con su
huella y propone un ítem con el nombre, la clase, la fecha y su origen. Lo que no se puede
bajar (por ejemplo, la pantalla de error que da el Portal en lugar del Pliego de Bases y
Condiciones Generales) o no es PDF ni página web guardada se informa como anomalía y no frena
el resto: queda la carga manual (REQ-051).

Cargar: pliego, anexo y circular van por `load_document` de la 003 (queda encolada su
lectura); acto, acta y dictamen no son pliego y la 003 no los lee: quedan como archivo del
Portal con su origen y su huella, descargables desde la pantalla de lo importado (el ítem
queda `aprobado`).

Una circular pide su tipo (modificatoria o aclaratoria) y su fecha: si el Portal no los dice,
los elige quien aprueba y el ítem no se aprueba sin ellos (plan 012, punto 5).
"""

import hashlib
import re
from datetime import date
from urllib.parse import unquote

from evaluon.audit.models import Channel
from evaluon.norms.reading import detect_format
from evaluon.portal.client import PortalError
from evaluon.portal.importers import Draft, jsonable
from evaluon.portal.models import ItemKind, LoadedModel, PortalFile
from evaluon.portal.parsing import documentos, texto
from evaluon.tenders.models import DocumentKind
from evaluon.tenders.services.documents import load_document

KIND = ItemKind.DOCUMENTO

CIRCULAR_KINDS = (DocumentKind.CIRCULAR_MODIFICATORIA, DocumentKind.CIRCULAR_ACLARATORIA)
_LOAD_KIND = {"pliego": DocumentKind.PLIEGO, "anexo": DocumentKind.ANEXO}
_ERROR_MARKERS = (b"PantallaError.aspx", b"lblMensajeErrorGenerico")
_FILENAME = re.compile(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", re.IGNORECASE)


def explore(context):
    drafts = []
    for ref in documentos.list_documents(context.parsed):
        result = _download(context, ref)
        if isinstance(result, str):
            _anomaly(context, ref, result)
            continue
        url, response = result
        body = bytes(response.body)
        file_format = detect_format(body)
        if file_format != "pdf" and any(m in body for m in _ERROR_MARKERS):
            _anomaly(context, ref, "El Portal respondió su pantalla de error en lugar del "
                                   "documento.")
        elif file_format is None:
            _anomaly(context, ref, "Lo que bajó no es un PDF ni una página web guardada.")
        else:
            drafts.append(_draft(context, ref, url, response, body, file_format))
    return drafts


def _anomaly(context, ref, reason):
    context.anomalies.append({"parte": f"documento «{ref.name}»",
                              "motivo": f"{reason} Queda la carga manual."})


def _download(context, ref):
    """`(url, respuesta)` o el motivo (texto) de por qué no se pudo bajar."""
    page = context.page
    if ref.how == "url" and ref.url:
        url = documentos.absolute_url(page.url, ref.url)
        call = lambda: context.client.get(url)  # noqa: E731
    elif ref.how == "formulario" and ref.target:
        url = f"{page.url}#envio={ref.target}"
        fields = {"__EVENTTARGET": ref.target, "__EVENTARGUMENT": ref.argument or ""}
        call = lambda: context.client.submit_form(  # noqa: E731
            page.url, bytes(page.content), fields)
    else:
        return "El Portal no trae la forma de abrirlo."
    try:
        return url, call()
    except PortalError as error:
        return f"No se pudo bajar: {error}."


def _file_name(ref, response, file_format):
    found = _FILENAME.search(response.headers.get("content-disposition", ""))
    name = re.sub(r"[\\/]", "_", unquote(found.group(1)).strip()) if found else ""
    if not name:
        base = re.sub(r"[^\w.-]+", "_", ref.name).strip("_") or "documento"
        name = base + (".pdf" if file_format == "pdf" else ".html")
    return name[:300]


def _draft(context, ref, url, response, body, file_format):
    digest = hashlib.sha256(body).hexdigest()
    stored = (PortalFile.objects.filter(link=context.link, url=url, sha256=digest)
              .order_by("id").first())
    if stored is None:
        stored = PortalFile.objects.create(
            link=context.link, exploration=context.exploration, url=url,
            file_name=_file_name(ref, response, file_format), file_format=file_format,
            sha256=digest, content=body, page=context.page,
        )
    context.files.append({"url": url, "sha256": digest, "file_name": stored.file_name,
                          "fetched_at": stored.fetched_at.isoformat(),
                          "page": context.page.pk})
    payload = {
        "nombre": ref.name,
        "clase": ref.document_class,
        "seccion": ref.section,
        "numero_gde": ref.gde_number,
        "fecha": ref.issued_on,
        "se_carga_como": "documento" if ref.document_class in documentos.LOADABLE else "archivo",
        "archivo": {"nombre": stored.file_name, "formato": file_format, "sha256": digest,
                    "tamano": len(body), "url": url},
    }
    if ref.document_class == documentos.CIRCULAR:
        payload.update(numero=ref.circular_number, tipo_portal=ref.portal_type,
                       tipo_circular=ref.circular_kind)
    damaged = [ref.name] if texto.is_damaged(ref.name) else []
    return Draft(KIND, ref.key, jsonable(payload), damaged, file=stored)


# --- Carga --------------------------------------------------------------------------------


def blocker(item, confirmation):
    """Por qué el ítem no se puede aprobar todavía, o `""`. Una circular pide tipo y fecha."""
    payload = item.payload
    if payload["clase"] != documentos.CIRCULAR:
        return ""
    if _circular_kind(payload, confirmation) is None:
        return "Elija si la circular es modificatoria o aclaratoria."
    if _issued_on(payload, confirmation) is None:
        return "Escriba la fecha de la circular."
    return ""


def _circular_kind(payload, confirmation):
    kind = payload.get("tipo_circular") or (confirmation or {}).get("circular_kind")
    return kind if kind in CIRCULAR_KINDS else None


def _issued_on(payload, confirmation):
    value = payload.get("fecha") or (confirmation or {}).get("issued_on")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def load(user, item, confirmation=None, channel=Channel.SCREEN):
    """Carga el ítem aprobado. Devuelve `(modelo, id)` si creó un documento del pliego, o
    `None` si el documento queda como archivo del Portal. Levanta la excepción de
    `load_document` (por ejemplo, un duplicado) con su motivo."""
    payload = item.payload
    if payload["clase"] not in documentos.LOADABLE:
        return None
    procedure = item.proposal.link.procedure
    if payload["clase"] == documentos.CIRCULAR:
        kind = _circular_kind(payload, confirmation)
    else:
        kind = _LOAD_KIND[payload["clase"]]
    loaded = load_document(
        user, procedure, data=bytes(item.file.content), file_name=item.file.file_name,
        kind=kind, title=payload["nombre"], issued_on=_issued_on(payload, confirmation),
        channel=channel,
    )
    return LoadedModel.DOCUMENT, loaded.document.pk
