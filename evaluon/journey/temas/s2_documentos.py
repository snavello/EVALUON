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
    """Los documentos de esta pestaña: pliego, anexos y especificaciones, en orden de carga."""
    return list(procedure.documents.filter(kind__in=KIND_VALUES)
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


urlpatterns = [path("documentos/subir/", upload, name="s2_documentos_subir")]


def context(user, procedure, request):
    rows = rows_of(procedure)
    absent = missing_from_portal(procedure)
    return {
        "rows": rows, "absent": absent, "pid": procedure.pk, "empty": not rows,
        "can_load": can_load(user), "kind_choices": KIND_CHOICES,
        "portal_url": portal_url(procedure),
        "results": unpack(request.GET.get("docs")),
        "loaded_count": len(rows), "missing_count": len(absent),
    }
