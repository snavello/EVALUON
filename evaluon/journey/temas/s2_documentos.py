"""Tema s2_documentos: los documentos del pliego, sus anexos y las especificaciones técnicas, en
la pestaña «Pliego y matriz» (REQ-080, REQ-097; plan 014, T-198).

Lista cada documento con su tipo, de dónde vino (el Portal o un archivo subido, con la fecha en
hora local) y el estado de su lectura, y muestra como «Falta» lo que el Portal lista y todavía no
se tomó. Las circulares y aclaraciones no van acá: van en la pestaña Ofertas (REQ-085).

«Subir archivo» sube varios archivos a la vez: cada uno con su tipo (y su fecha, que solo exigen
los tipos fechados) pasa por `load_document` por separado, así que cada uno deja su propio hecho
`tender_load` y su resultado; un repetido o ilegible se rechaza con su motivo sin frenar a los
otros. «Tomar del Portal» lleva a los documentos que el Portal propone. El tema no decide nada
(P3): cargar es una acción de una persona.

Historial (REQ-099, T-200): cada documento vigente tiene «Historial», «Reemplazar» y «Retirar»,
que llaman al servicio `tenders.services.document_history` (nada se borra). El historial de un
documento se abre dentro de la pestaña (`?historial=<documento>`), con la línea de tiempo de sus
versiones, quién, cuándo y el motivo; `?historial=retirados` muestra solo el bloque «Retirados»,
con «Restituir». La tabla principal muestra solo lo vigente. Si la matriz se armó con un
documento que después se retiró o se reemplazó, un aviso lo dice. El motivo es obligatorio en
los tres cambios (la pantalla lo exige; el servicio lo guarda). Solo el operador y el
evaluador cambian; sin rol, 403 con el rechazo registrado.

El resultado de la subida viaja firmado en la dirección (`?docs=`), sin guardar nada en la
sesión, y vale cinco minutos.
"""

from dataclasses import dataclass

from django.core import signing
from django.forms import DateField, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import Missing, TemaStatus
from evaluon.portal.models import ItemKind, ItemState, LoadedModel, PortalItem
from evaluon.queries.forms import DATE_INPUT_FORMATS
from evaluon.tenders.models import (
    DATED_DOCUMENT_KINDS,
    Document,
    DocumentKind,
    JobKind,
    Procedure,
)
from evaluon.tenders.services import document_history as history_service
from evaluon.tenders.services import documents as services

KEY = "s2_documentos"
SECTION = "pliego"
PARTIAL = "journey/temas/s2_documentos.html"

SALT = "journey.s2.documentos"
MAX_AGE = 300
ANCHOR = "#s2-documentos"
MAX_FILES = 30

# Los tipos de esta pestaña. Las circulares y las respuestas a consultas son de Ofertas.
KINDS = (DocumentKind.PLIEGO, DocumentKind.ANEXO, DocumentKind.ESPECIFICACIONES)
KIND_VALUES = tuple(k.value for k in KINDS)
KIND_CHOICES = tuple((k.value, k.label) for k in KINDS)
DATED_VALUES = tuple(k.value for k in DATED_DOCUMENT_KINDS)
# Lo que el Portal clasifica y no pertenece a esta pestaña.
NOT_HERE = ("circular", "dictamen")
TAKEABLE = (ItemState.PROPUESTO, ItemState.RECHAZADO, ItemState.FALLIDO)

STATE_ICONS = {
    services.STATE_READ: ("cumple", "Leído"),
    services.STATE_QUEUED: ("pend", "En espera de lectura"),
    services.STATE_RUNNING: ("pend", "Leyendo"),
    services.STATE_FAILED: ("nocumple", "No se pudo leer"),
}


@dataclass
class DocRow:
    document: Document
    kind_label: str
    icon: str
    icon_name: str
    reading_text: str
    pages: object
    origin: str  # «Portal» o «Archivo»
    origin_date: str
    origin_by: str
    note: str = ""


@dataclass
class MissingRow:
    name: str
    state: str


def _day(moment):
    """La fecha en hora local, no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y}"


def can_load(user):
    return user.commission_role in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR)


def documents_of(procedure):
    """Los documentos vigentes de esta pestaña: pliego, anexos y especificaciones, en orden de
    carga. Lo retirado y lo reemplazado no figura (está en el historial)."""
    return list(history_service.current_documents(procedure).filter(kind__in=KIND_VALUES)
                .select_related("loaded_by").order_by("loaded_at", "pk"))


def _portal_origin(procedure, documents):
    """`{id del documento: ítem del Portal}` de los documentos que se tomaron del Portal."""
    items = PortalItem.objects.filter(
        proposal__link__procedure=procedure, kind=ItemKind.DOCUMENTO,
        loaded_model=LoadedModel.DOCUMENT,
        loaded_id__in=[d.pk for d in documents]).order_by("pk")
    return {item.loaded_id: item for item in items}


def _reading(document):
    job = (document.jobs.filter(kind=JobKind.READ_DOCUMENT)
           .order_by("-requested_at", "-id").first())
    reading = document.readings.order_by("-sequence").first()
    state = services._state(job, reading)
    icon, name = STATE_ICONS[state]
    text, pages = name, None
    if reading is not None and state == services.STATE_READ:
        data = reading.pages
        listed = data.get("pages", []) if isinstance(data, dict) else data
        pages = len(listed) if isinstance(listed, list) else None
        review = reading.segments.exclude(review_reason="").count()
        if review:
            icon, name = "nodet", "Leído, con tramos a revisar"
            text = f"Leído; {review} {'tramo' if review == 1 else 'tramos'} a revisar"
    return icon, name, text, pages


def rows_of(procedure):
    documents = documents_of(procedure)
    from_portal = _portal_origin(procedure, documents)
    rows = []
    for document in documents:
        icon, name, text, pages = _reading(document)
        portal = from_portal.get(document.pk)
        rows.append(DocRow(
            document=document, kind_label=DocumentKind(document.kind).label, icon=icon,
            icon_name=name, reading_text=text, pages=pages,
            origin="Portal" if portal else "Archivo", origin_date=_day(document.loaded_at),
            origin_by="" if portal or document.loaded_by is None
            else document.loaded_by.username))
    return rows


def missing_from_portal(procedure):
    """Los documentos que el Portal lista para el procedimiento y todavía no se tomaron."""
    items = (PortalItem.objects.filter(proposal__link__procedure=procedure,
                                       kind=ItemKind.DOCUMENTO).order_by("pk"))
    taken, listed = set(), {}
    for item in items:
        if item.payload.get("clase") in NOT_HERE:
            continue
        if item.state == ItemState.CARGADO:
            taken.add(item.key)
        elif item.state in TAKEABLE:
            listed[item.key] = item
    return [MissingRow(item.payload.get("nombre") or item.key, ItemState(item.state).label)
            for key, item in listed.items() if key not in taken]


def portal_url(procedure):
    """A los ítems de documentos del Portal; sin proceso seguido, a donde se da de alta."""
    link = procedure.portal_links.order_by("-pk").first()
    if link is None:
        return reverse("portal:links")
    return reverse("portal:proposal", args=[link.pk]) + "#group-documento"


def status(user, procedure):
    documents = documents_of(procedure)
    sources, missing = [], []
    if documents:
        from_portal = len(_portal_origin(procedure, documents))
        by_hand = len(documents) - from_portal
        parts = []
        if from_portal:
            parts.append(f"{from_portal} del Portal")
        if by_hand:
            parts.append(f"{by_hand} {'subido' if by_hand == 1 else 'subidos'} como archivo")
        sources.append(f"Documentos del pliego: {', '.join(parts)}.")
    absent = missing_from_portal(procedure)
    if absent:
        count = len(absent)
        missing.append(Missing(
            f"El Portal lista {count} {'documento' if count == 1 else 'documentos'} "
            "del pliego que no se tomaron", portal_url(procedure), "Tomar del Portal"))
    return TemaStatus(missing=tuple(missing), sources=tuple(sources))


# --- Historial, reemplazo, retiro y restitución (T-200) --------------------------------------


@dataclass
class Entry:
    """Un renglón de la línea de tiempo de un documento."""
    at: object
    when: str
    who: str
    title: str
    text: str
    css: str = ""
    document: object = None


def _moment(moment):
    """Fecha y hora locales (la base guarda UTC)."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


def _who(user):
    return user.username if user is not None else "sistema"


def timeline(document):
    """La línea de tiempo del documento: cada versión (con quién la subió, cuándo y el motivo del
    reemplazo) y cada retiro o restitución, de lo más nuevo a lo más viejo."""
    changes = history_service.history(document)
    versions = {document.pk: document}
    for change in changes:
        versions[change.document_id] = change.document
        if change.new_document is not None:
            versions[change.new_document_id] = change.new_document
    ordered = sorted(versions.values(), key=lambda d: (d.loaded_at, d.pk))
    replaced_by = {c.new_document_id: c for c in changes
                   if c.action == "reemplazar" and c.new_document_id}
    entries = []
    for number, version in enumerate(ordered, start=1):
        state = history_service.state(version)
        change = replaced_by.get(version.pk)
        if change is not None:
            how, at, who = "reemplazo", change.at, change.user
            text = f"Motivo: «{change.note}»." if change.note else "Sin motivo escrito."
        else:
            portal = PortalItem.objects.filter(
                kind=ItemKind.DOCUMENTO, loaded_model=LoadedModel.DOCUMENT,
                loaded_id=version.pk).exists()
            how = "tomado del Portal" if portal else "subido como archivo"
            at, who = version.loaded_at, version.loaded_by
            text = ""
        entries.append(Entry(
            at=at, when=_moment(at), who=_who(who), title=f"Versión {number} · {state}",
            text=f"{how} · {version.file_name}" + (f" · {text}" if text else ""),
            document=version))
    for change in changes:
        if change.action in ("retirar", "restituir"):
            retired = change.action == "retirar"
            entries.append(Entry(
                at=change.at, when=_moment(change.at), who=_who(change.user),
                title="Retirado" if retired else "Restituido",
                text=f"Motivo: «{change.note}»." if change.note else "Sin motivo escrito.",
                css="retiro" if retired else ""))
    entries.sort(key=lambda e: e.at, reverse=True)
    return entries


def withdrawn_rows(procedure):
    """Los documentos retirados de esta pestaña, con quién, cuándo y el motivo del retiro."""
    rows = []
    for document in (history_service.withdrawn_documents(procedure).filter(kind__in=KIND_VALUES)
                     .select_related("loaded_by")):
        change = document.changes.filter(action="retirar").order_by("-id").first()
        rows.append(DocRow(
            document=document, kind_label=DocumentKind(document.kind).label, icon="",
            icon_name="", reading_text="", pages=None, origin="",
            origin_date=_moment(change.at), origin_by=_who(change.user), note=change.note))
    return rows


def stale_matrix_warnings(procedure):
    """Un aviso por cada versión de la matriz armada con un documento que hoy está retirado o
    reemplazado."""
    warnings = []
    for version, gone in history_service.versions_with_withdrawn(procedure):
        names = ", ".join(f"«{d.title}» ({history_service.state(d)})" for d in gone)
        warnings.append(f"La versión {version.number} de la matriz se armó con {names}. "
                        "La matriz no cambia sola: revísela y, si hace falta, abra una versión "
                        "nueva.")
    return warnings


def _document(procedure, document_id):
    try:
        document = Document.objects.get(pk=document_id, procedure=procedure)
    except Document.DoesNotExist:
        raise Http404("No hay un documento con ese número en este procedimiento.")
    if document.kind not in KIND_VALUES:
        raise Http404("Ese documento no es del pliego.")
    return document


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _change(request, procedure_id, document_id, operation, done, call, needs_file=False):
    """Valida rol, motivo (y archivo) y llama al servicio; con rechazo vuelve con el motivo."""
    procedure = _procedure(procedure_id)
    document = _document(procedure, document_id)
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=operation,
                            channel=Channel.SCREEN)
    note = " ".join(request.POST.get("note", "").split())
    if not note:
        return _back(procedure, [_result(document.title, False, "Escriba el motivo: es "
                                         "obligatorio y queda registrado.")])
    upload_file = request.FILES.get("file")
    if needs_file and upload_file is None:
        return _back(procedure, [_result(document.title, False,
                                         "Elija el archivo que reemplaza al documento.")])
    try:
        call(request.user, document, note, upload_file)
    except (history_service.HistoryRefused, services.DocumentRefused) as error:
        return _back(procedure, [_result(document.title, False, str(error))])
    return _back(procedure, [_result(document.title, True, done)])


@require_POST
def withdraw(request, procedure_id, document_id):
    return _change(
        request, procedure_id, document_id, history_service.WITHDRAW_OPERATION,
        "Retirado: no se borra, queda en «Retirados» y se puede restituir.",
        lambda user, doc, note, f: history_service.withdraw(user, doc, note,
                                                            channel=Channel.SCREEN))


@require_POST
def restore(request, procedure_id, document_id):
    return _change(
        request, procedure_id, document_id, history_service.RESTORE_OPERATION,
        "Restituido: vuelve a estar vigente.",
        lambda user, doc, note, f: history_service.restore(user, doc, note=note,
                                                           channel=Channel.SCREEN))


@require_POST
def replace(request, procedure_id, document_id):
    return _change(
        request, procedure_id, document_id, history_service.REPLACE_OPERATION,
        "Reemplazado: la versión anterior queda en el historial y la nueva queda en espera de "
        "lectura.",
        lambda user, doc, note, f: history_service.replace(
            user, doc, data=f.read(), file_name=f.name, note=note, channel=Channel.SCREEN),
        needs_file=True)


# --- Subida de varios archivos --------------------------------------------------------------


def pack(results):
    return signing.dumps(results, salt=SALT, compress=True)


def unpack(value):
    """Los resultados firmados de la dirección, o `None` si faltan, están alterados o vencieron."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return [{"name": str(r.get("n", "")), "ok": bool(r.get("ok")), "text": str(r.get("t", ""))}
            for r in data if isinstance(r, dict)]


def _back(procedure, results):
    url = reverse("expedientes:pliego", args=[procedure.pk])
    return redirect(f"{url}?docs={pack(results)}{ANCHOR}")


def _title(name):
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.replace("_", " ").strip() or name


def _result(name, ok, text):
    return {"n": name, "ok": ok, "t": text}


_date_field = DateField(input_formats=DATE_INPUT_FORMATS, required=False)


@require_POST
def upload(request, procedure_id):
    """Sube cada archivo elegido con `load_document`; el resultado de cada uno vuelve a la
    pestaña. Sin rol de la Comisión, `load_document` lo rechaza y deja el hecho."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    uploads = request.FILES.getlist("files")[:MAX_FILES]
    if not uploads:
        return _back(procedure, [_result("", False, "Elija al menos un archivo para subir.")])
    default_kind = request.POST.get("kind", "")
    results = []
    for index, upload_file in enumerate(uploads):
        name = upload_file.name
        kind = request.POST.get(f"kind_{index}") or default_kind
        if kind not in KIND_VALUES:
            results.append(_result(name, False, "El tipo de documento no corresponde a esta "
                                   "pestaña (pliego, anexo o especificaciones técnicas): no "
                                   "se cargó."))
            continue
        title = (request.POST.get(f"title_{index}") or "").strip() or _title(name)
        text_date = (request.POST.get(f"issued_on_{index}") or "").strip()
        content = upload_file.read()
        try:
            issued_on = _date_field.clean(text_date) if text_date else None
        except ValidationError:
            refusal = services.refuse_invalid_date(
                request.user, procedure, data=content, file_name=name, kind=kind, title=title,
                issued_on_text=text_date, channel=Channel.SCREEN)
            results.append(_result(name, False, str(refusal)))
            continue
        try:
            services.load_document(request.user, procedure, data=content, file_name=name,
                                   kind=kind, title=title, issued_on=issued_on,
                                   channel=Channel.SCREEN)
        except services.DocumentRefused as error:
            results.append(_result(name, False, str(error)))
        else:
            results.append(_result(name, True, "Cargado; queda en espera de lectura."))
    return _back(procedure, results)


urlpatterns = [
    path("documentos/subir/", upload, name="s2_documentos_subir"),
    path("documentos/<int:document_id>/reemplazar/", replace, name="s2_documentos_reemplazar"),
    path("documentos/<int:document_id>/retirar/", withdraw, name="s2_documentos_retirar"),
    path("documentos/<int:document_id>/restituir/", restore, name="s2_documentos_restituir"),
]


def _open_history(procedure, request):
    """Lo que pide `?historial=`: `("retirados", None)`, `("documento", doc)` o `None`."""
    value = request.GET.get("historial", "")
    if value == "retirados":
        return "retirados", None
    if value.isdigit():
        try:
            return "documento", _document(procedure, int(value))
        except Http404:
            return None
    return None


def context(user, procedure, request):
    rows = rows_of(procedure)
    absent = missing_from_portal(procedure)
    opened = _open_history(procedure, request)
    tab_url = reverse("expedientes:pliego", args=[procedure.pk])
    entries = timeline(opened[1]) if opened and opened[0] == "documento" else []
    return {
        "withdrawn": withdrawn_rows(procedure), "history_mode": opened[0] if opened else "",
        "history_document": opened[1] if opened else None,
        "timeline": entries,
        "history_current": bool(opened and opened[1] is not None
                                and history_service.state(opened[1]) == "vigente"),
        "versions_count": sum(1 for e in entries if e.document is not None),
        "tab_url": tab_url, "retired_url": f"{tab_url}?historial=retirados#s2-retirados",
        "stale": stale_matrix_warnings(procedure),
        "rows": rows, "absent": absent, "pid": procedure.pk, "empty": not rows,
        "can_load": can_load(user), "kind_choices": KIND_CHOICES,
        "portal_url": portal_url(procedure),
        "results": unpack(request.GET.get("docs")),
        "loaded_count": len(rows), "missing_count": len(absent),
    }
