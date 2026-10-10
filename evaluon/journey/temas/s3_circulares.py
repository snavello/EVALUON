"""Tema s3_circulares: «Circulares y aclaraciones» dentro de la pestaña «Ofertas» (REQ-085,
REQ-097; plan 014, T-205).

Lista las circulares modificatorias, las aclaratorias y las respuestas a consultas, con su tipo,
su fecha, de dónde vinieron (el Portal o un archivo subido, con la fecha de carga en hora local)
y qué hicieron con la matriz. Una modificatoria abre una versión nueva de la matriz de «Pliego
y matriz», en borrador y con lo cambiado marcado, que la Comisión valida de nuevo con la acción
de siempre; una aclaratoria o una respuesta no abre versión (servicio
`tenders.services.circular_version`, que explica en su docstring cómo el sistema aplica una
circular). El tema no decide nada (P3): la versión queda en borrador y la valida una persona.

«Subir circular o aclaración» sube varios archivos a la vez, cada uno con su tipo y su fecha
(obligatoria: los tres tipos la llevan) y pasa por `load_document` por separado, como la subida
del pliego: uno rechazado no frena a los otros. Una circular subida se lee en segundo plano;
cuando termina, «Abrir la versión nueva de la matriz» la incorpora (el pedido necesita la
circular leída). «Tomar del Portal» lleva a los ítems de circulares que el Portal propone.

Las circulares y las respuestas a consultas se suben solo acá: en «Pliego y matriz» no. Las
acciones vuelven a esta pestaña con el aviso firmado en la dirección (`?aviso_circ=`), sin
guardar nada en la sesión, y llaman a los mismos servicios que el resto (cargar, pedir la
matriz); sin rol de la Comisión, 403 con el rechazo registrado.

Cuentas: una modificatoria sin una matriz nueva validada es un pendiente (si el procedimiento
todavía no tiene versiones de la matriz, no: la primera propuesta la incluye); lo que el Portal
lista y no se tomó es un faltante con su acción.
"""

from dataclasses import dataclass

from django.core import signing
from django.forms import DateField, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections.base import Item, Missing, TemaStatus
from evaluon.journey.temas import s2_documentos
from evaluon.portal.models import ItemKind, ItemState, LoadedModel, PortalItem
from evaluon.queries.forms import DATE_INPUT_FORMATS
from evaluon.tenders.models import Document, DocumentKind, Procedure, VersionStatus
from evaluon.tenders.services import circular_version
from evaluon.tenders.services import documents as services

KEY = "s3_circulares"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_circulares.html"

SALT = "journey.s3.circulares"
MAX_AGE = 300
PARAM = "aviso_circ"
ANCHOR = "#s3-circulares"
MAX_FILES = 30

# Los tipos de este tema: los que llevan fecha. Solo se suben acá.
KINDS = (DocumentKind.CIRCULAR_MODIFICATORIA, DocumentKind.CIRCULAR_ACLARATORIA,
         DocumentKind.RESPUESTA_CONSULTA)
KIND_VALUES = tuple(k.value for k in KINDS)
KIND_CHOICES = tuple((k.value, k.label) for k in KINDS)
TAKEABLE = s2_documentos.TAKEABLE


@dataclass
class Row:
    document: object
    kind_label: str
    day: str            # la fecha del documento
    origin: str         # «Portal» o «Archivo»
    origin_date: str
    origin_by: str
    reading_text: str
    effect_text: str    # qué hizo con la matriz
    version: object = None
    version_url: str = ""
    needs_validation: bool = False
    can_open: bool = False


@dataclass
class MissingRow:
    name: str
    state: str


def can_load(user):
    return user.commission_role in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR)


def tab_url(procedure_id):
    return reverse("expedientes:ofertas", args=[procedure_id])


def matrix_url(procedure_id):
    return reverse("expedientes:pliego", args=[procedure_id]) + "#s2-matriz"


def _states(procedure):
    """Los estados de las circulares, calculados una vez por carga (la barra y el contexto los
    piden los dos)."""
    return memo.once(("s3_circulares", procedure.pk),
                     lambda: circular_version.states(procedure))


def _link_id(procedure):
    return memo.once(("s3_circulares_link", procedure.pk), lambda: (
        procedure.portal_links.order_by("-pk").values_list("pk", flat=True).first()))


def portal_url(procedure):
    """A los ítems de documentos del Portal; sin proceso seguido, al bloque del Portal de la
    pestaña «Procedimiento», donde se da de alta (sin salir del expediente)."""
    link_id = _link_id(procedure)
    if link_id is not None:
        return reverse("portal:proposal", args=[link_id]) + "#group-documento"
    return reverse("expedientes:procedimiento", args=[procedure.pk]) + "#s1-portal"


def _plural(numbers, one="el requisito", many="los requisitos"):
    listed = ", ".join(str(n) for n in numbers)
    return f"{one} {listed}" if len(numbers) == 1 else f"{many} {listed}"


def effect_text(effect):
    """Lo que la circular hizo en la versión, en una línea."""
    parts = []
    if effect.changed:
        parts.append("cambió " + _plural(effect.changed))
    if effect.removed:
        parts.append("dejó sin efecto " + _plural(effect.removed))
    if effect.added:
        parts.append("agregó " + _plural(effect.added))
    if effect.clarified:
        parts.append("aclara " + _plural(effect.clarified))
    return "; ".join(parts) if parts else "no cambió ningún requisito"


def _validated_day(version):
    if version.status != VersionStatus.VALIDATED or version.validated_at is None:
        return ""
    who = f" por {version.validated_by.username}" if version.validated_by_id else ""
    return f" Validada el {s2_documentos._day(version.validated_at)}{who}."


def _what_it_did(state, has_validated, has_versions, user_can):
    """El texto de «Qué hizo con la matriz», si falta validar y si se puede abrir la versión
    nueva ahora."""
    if state.state == circular_version.NO_APLICA:
        return "No cambia la matriz.", False, False
    if state.state in (circular_version.VALIDADA, circular_version.EN_BORRADOR):
        version, what = state.version, effect_text(state.effect)
        if state.state == circular_version.VALIDADA:
            return (f"Entró en la versión {version.number}: {what}."
                    + _validated_day(version)), False, False
        return f"Entró en la versión {version.number} (en revisión): {what}.", True, False
    if state.state == circular_version.DESCARTADA:
        head = (f"La versión {state.version.number}, donde entró, se descartó. "
                "Falta abrir una versión nueva.")
    elif state.building:
        return "Se está armando la versión nueva de la matriz.", False, False
    elif state.failed:
        head = f"No se pudo armar la versión nueva ({state.failed}). Se puede pedir de nuevo."
    elif not has_versions:
        return ("La matriz todavía no se propuso: cuando se proponga, ya incluirá esta "
                "circular."), False, False
    elif not has_validated:
        return ("La matriz está en borrador sin esta circular: valídela o descártela y "
                "después abra la versión nueva."), False, False
    else:
        head = "Todavía no abrió una versión nueva de la matriz."
    if state.reading in (services.STATE_QUEUED, services.STATE_RUNNING):
        return "Se está leyendo; cuando termine se puede abrir la versión nueva.", False, False
    if state.reading == services.STATE_FAILED:
        return "No se pudo leer: no se puede abrir la versión nueva.", False, False
    return head, False, user_can


def _portal_items(procedure):
    """Los ítems de documentos del Portal, en una consulta por carga."""
    return memo.once(("s3_circulares_items", procedure.pk), lambda: list(
        PortalItem.objects.filter(proposal__link__procedure=procedure,
                                  kind=ItemKind.DOCUMENTO).order_by("pk")))


def _from_portal(procedure, documents):
    """`{id del documento: ítem del Portal}` de las circulares que se tomaron del Portal."""
    ids = {d.pk for d in documents}
    return {item.loaded_id: item for item in _portal_items(procedure)
            if item.loaded_model == LoadedModel.DOCUMENT and item.loaded_id in ids}


def missing_from_portal(procedure):
    """Las circulares y aclaraciones que el Portal lista y todavía no se tomaron."""
    taken, listed = set(), {}
    for item in _portal_items(procedure):
        if item.payload.get("clase") != "circular":
            continue
        if item.state == ItemState.CARGADO:
            taken.add(item.key)
        elif item.state in TAKEABLE:
            listed[item.key] = item
    return [MissingRow(item.payload.get("nombre") or item.key, ItemState(item.state).label)
            for key, item in listed.items() if key not in taken]


def rows_of(user, procedure):
    states = _states(procedure)
    if not states:
        return []
    from_portal = _from_portal(procedure, [s.document for s in states])
    versions = procedure.matrix_versions.exclude(status=VersionStatus.DISCARDED)
    has_versions = versions.exists()
    has_validated = versions.filter(status=VersionStatus.VALIDATED).exists()
    rows = []
    for state in states:
        document = state.document
        text, needs_validation, can_open = _what_it_did(
            state, has_validated, has_versions, can_load(user))
        portal = from_portal.get(document.pk)
        rows.append(Row(
            document=document, kind_label=DocumentKind(document.kind).label,
            day=f"{document.issued_on:%d/%m/%Y}" if document.issued_on else "—",
            origin="Portal" if portal else "Archivo",
            origin_date=s2_documentos._day(document.loaded_at),
            origin_by="" if portal or document.loaded_by is None
            else document.loaded_by.username,
            reading_text=s2_documentos._reading(document)[2], effect_text=text,
            version=state.version,
            version_url=matrix_url(procedure.pk) if state.version else "",
            needs_validation=needs_validation, can_open=can_open))
    return rows


def status(user, procedure):
    rows = _states(procedure)
    documents = [row.document for row in rows]
    sources, missing, pending = [], [], []
    if documents:
        portal = len(_from_portal(procedure, documents))
        by_hand = len(documents) - portal
        parts = []
        if portal:
            parts.append(f"{portal} del Portal")
        if by_hand:
            parts.append(f"{by_hand} {'subida' if by_hand == 1 else 'subidas'} como archivo")
        sources.append(f"Circulares y aclaraciones: {', '.join(parts)}.")
    absent = missing_from_portal(procedure)
    if absent:
        count = len(absent)
        what = "circular o aclaración" if count == 1 else "circulares o aclaraciones"
        missing.append(Missing(f"El Portal lista {count} {what} que no se tomaron",
                               portal_url(procedure), "Tomar del Portal"))
    for state in circular_version.pending(procedure, rows):
        title = state.document.title
        if state.state == circular_version.EN_BORRADOR:
            pending.append(Item(
                f"{title}: la versión {state.version.number} de la matriz, con lo que cambió, "
                "falta validarla", matrix_url(procedure.pk), 1, "Validar"))
        else:
            pending.append(Item(f"{title}: falta abrir la versión nueva de la matriz",
                                tab_url(procedure.pk) + ANCHOR, 1, "Abrir"))
    return TemaStatus(pending=len(pending), missing=tuple(missing), sources=tuple(sources),
                      pending_items=tuple(pending))


# --- Avisos y regreso a la pestaña ------------------------------------------------------------


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


def _result(name, ok, text):
    return {"n": name, "ok": ok, "t": text}


def back(procedure, results):
    return redirect(f"{tab_url(procedure.pk)}?{PARAM}={pack(results)}{ANCHOR}")


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _title(name):
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.replace("_", " ").strip() or name


_date_field = DateField(input_formats=DATE_INPUT_FORMATS, required=False)

LOADED = {
    DocumentKind.CIRCULAR_MODIFICATORIA: (
        "Cargada; queda en espera de lectura. Cuando se lea, abra la versión nueva de la "
        "matriz."),
    DocumentKind.CIRCULAR_ACLARATORIA: "Cargada; queda en espera de lectura. No cambia la matriz.",
    DocumentKind.RESPUESTA_CONSULTA: "Cargada; queda en espera de lectura. No cambia la matriz.",
}


@require_POST
def upload(request, procedure_id):
    """Sube cada archivo elegido con `load_document`; el resultado de cada uno vuelve a la
    pestaña. Sin rol de la Comisión, `load_document` lo rechaza y deja el hecho."""
    procedure = _procedure(procedure_id)
    uploads = request.FILES.getlist("files")[:MAX_FILES]
    if not uploads:
        return back(procedure, [_result("", False, "Elija al menos un archivo para subir.")])
    default_kind = request.POST.get("kind", "")
    default_date = (request.POST.get("issued_on") or "").strip()
    results = []
    for index, upload_file in enumerate(uploads):
        name = upload_file.name
        kind = request.POST.get(f"kind_{index}") or default_kind
        if kind not in KIND_VALUES:
            results.append(_result(name, False, "El tipo no corresponde a esta pestaña "
                                   "(circular modificatoria, circular aclaratoria o respuesta "
                                   "a consulta): no se cargó."))
            continue
        title = (request.POST.get(f"title_{index}") or "").strip() or _title(name)
        text_date = (request.POST.get(f"issued_on_{index}") or default_date).strip()
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
            results.append(_result(name, True, LOADED[DocumentKind(kind)]))
    return back(procedure, results)


@require_POST
def open_version(request, procedure_id):
    """Pide la versión nueva de la matriz con la circular elegida (el mismo servicio de pedido
    de la matriz) y vuelve a la pestaña con el aviso."""
    procedure = _procedure(procedure_id)
    try:
        document = Document.objects.get(pk=request.POST.get("document") or 0,
                                        procedure=procedure, kind__in=KIND_VALUES)
    except (Document.DoesNotExist, ValueError):
        raise Http404("No hay una circular con ese número en este procedimiento.")
    try:
        circular_version.open_for_circular(request.user, procedure, document,
                                           channel=Channel.SCREEN)
    except circular_version.CircularRefused as error:
        return back(procedure, [_result(document.title, False, str(error))])
    return back(procedure, [_result(
        document.title, True,
        "Se pidió la versión nueva de la matriz con esta circular. El sistema la arma en "
        "segundo plano y queda en borrador, con lo cambiado marcado, para que la Comisión la "
        "valide.")])


urlpatterns = [
    path("circulares/subir/", upload, name="s3_circulares_subir"),
    path("circulares/abrir-version/", open_version, name="s3_circulares_abrir"),
]


def context(user, procedure, request):
    rows = rows_of(user, procedure)
    absent = missing_from_portal(procedure)
    return {
        "rows": rows, "absent": absent, "pid": procedure.pk, "empty": not rows,
        "can_load": can_load(user), "kind_choices": KIND_CHOICES,
        "portal_url": portal_url(procedure),
        "results": unpack(request.GET.get(PARAM)),
        "loaded_count": len(rows), "missing_count": len(absent),
        "matrix_url": matrix_url(procedure.pk),
        # Un solo botón: abre una sola versión con todas las modificatorias leídas.
        "open_document": next((row.document for row in rows if row.can_open), None),
    }
