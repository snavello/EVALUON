"""Tema s5_normas: subir una norma, leerla y validarla, sin comandos (sección «Normativas»;
REQ-094, REQ-097; ADR-0051; plan 014, T-214).

Una norma se carga «solo subiendo el archivo». Todo sale de los servicios de `norms`, que son los
mismos que usan los comandos (`cargar_norma`, `validar_informe`): el resultado es el mismo.

1. «Subir una norma» (`upload.stage`): el sistema lee el archivo y propone los diez datos con su
   evidencia (página y texto). Lo que no reconoce queda marcado.
2. Cada dato se corrige o completa escribiendo el valor y el motivo (`upload.correct`).
3. «Cargar la norma» (`upload.confirm` -> `load_norm`): queda cargada, con su lectura pendiente.
4. El informe de lectura se ve dentro de la pestaña (`reading_report`, `reading_summary`), y el
   evaluador lo valida con «Validar la norma» (`validation.validate_reading`).

Roles. Las operaciones de normas exigen el rol de normativa de lectura y escritura; la pantalla
exige además un rol de la Comisión (operador o evaluador) y, para validar, el de evaluador. No se
cambia el modelo de permisos: los evaluadores se crean con los dos roles (runbook de la tarea).
La pantalla dice cuál de los dos le falta a quien no puede una acción. Sin el rol, el servicio o
`require_commission_role` rechazan con 403 y dejan el hecho (P6).

La biblioteca de normas es común a todos los procedimientos: la lista no depende del que se abra.
Las acciones vuelven a la pestaña con el aviso de lo hecho (firmado en la dirección, sin sesión).

Fuera de alcance de esta tarea: descartar una subida equivocada (el servicio `upload` no tiene
`reject`; mientras espera, el mismo archivo no puede volver a subirse) y «Devolver para releer».
"""

import datetime

from django.core import signing
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole, Role
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import Item, Missing, TemaStatus
from evaluon.norms.models import (
    Category,
    Document,
    NormUpload,
    PendingAmendment,
    ProposalState,
    Reading,
    ReadingStatus,
)
from evaluon.norms.services import listing, loading, upload, validation
from evaluon.tenders.models import Procedure

KEY = "s5_normas"
SECTION = "normativas"
PARTIAL = "journey/temas/s5_normas.html"

CHANNEL = Channel.SCREEN
SALT = "journey.s5.aviso"
AVISO_MAX_AGE = 300
EXCERPT = 280

# Estado de una lectura -> (símbolo del ícono, nombre).
READING_STATES = {
    ReadingStatus.PENDING: ("nodet", "Cargada, sin validar"),
    ReadingStatus.VALIDATED: ("cumple", "Validada"),
    ReadingStatus.SUPERSEDED: ("pend", "Reemplazada por otra lectura"),
    None: ("nocumple", "Sin lectura"),
}

# Cómo se escribe cada dato al corregirlo.
INPUT_KINDS = {"category": "select", "year": "number", "publication_date": "date",
               "effective_from": "date"}
HINTS = {
    "publication_date": "Fecha en que se publicó la norma.",
    "effective_from": "Desde cuándo rige. Si la norma lo dice en plazos («a los 30 días»), se "
                      "escribe la fecha que resulta y, en el motivo, cómo se calculó.",
    "citation": "Cómo se nombra la norma al citarla, por ejemplo «Disposición AFIP 247/2022».",
}


# --- Mensajes y regreso a la pestaña -------------------------------------------------------------


def pack(text, ok=True):
    return signing.dumps({"ok": ok, "m": text}, salt=SALT, compress=True)


def unpack(value):
    """El aviso firmado de la dirección, o `None` si falta, está alterado o venció."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=AVISO_MAX_AGE)
    except signing.BadSignature:
        return None
    return {"ok": bool(data.get("ok")), "text": str(data.get("m", ""))}


def tab_url(procedure_id):
    return reverse("expedientes:normativas", args=[procedure_id])


def _back(procedure, text, ok=True, anchor="s5-aviso", reading=None):
    query = f"?aviso={pack(text, ok)}"
    if reading is not None:
        query += f"&lectura={reading}"
    return redirect(f"{tab_url(procedure.pk)}{query}#{anchor}")


def local(moment):
    """Fecha y hora locales (America/Argentina/Buenos_Aires), no las de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}" if moment else ""


def local_date(moment):
    return f"{timezone.localtime(moment):%d/%m/%Y}" if moment else ""


def _show(field, value):
    """Un dato como lo lee la persona: fechas día/mes/año y categoría con su nombre."""
    if value is None or value == "":
        return ""
    if field in upload.DATE_FIELDS:
        return datetime.date.fromisoformat(value).strftime("%d/%m/%Y")
    if field == "category":
        return Category(value).label if value in Category.values else str(value)
    return str(value)


# --- Roles ---------------------------------------------------------------------------------------


def _can_write(user):
    return getattr(user, "role", "") == Role.READ_WRITE


def _missing_roles(user, *, evaluator):
    """Qué rol le falta al usuario para la acción, en lenguaje llano. Vacío si puede."""
    missing = []
    if not _can_write(user):
        missing.append("el rol de normativa de lectura y escritura")
    commission = getattr(user, "commission_role", "")
    if evaluator and commission != CommissionRole.EVALUATOR:
        missing.append("el rol de evaluador de la Comisión")
    elif not evaluator and commission not in (CommissionRole.OPERATOR,
                                              CommissionRole.EVALUATOR):
        missing.append("un rol de la Comisión (operador o evaluador)")
    return " y ".join(missing)


# --- Estado del tema -----------------------------------------------------------------------------


def _pending_readings():
    """Las lecturas sin validar que son la última de su documento."""
    later = Reading.objects.filter(document_id=OuterRef("document_id"),
                                   sequence__gt=OuterRef("sequence"))
    return (Reading.objects.filter(status=ReadingStatus.PENDING)
            .filter(~Exists(later)).select_related("document__norm").order_by("pk"))


def status(user, procedure):
    """Cuentas del tema: lecturas por validar y subidas que esperan confirmación (pendientes) y
    modificatorias registradas sin cargar (faltantes, cada una con «Subir norma»)."""
    url = tab_url(procedure.pk)
    items = [Item(f"Norma {reading.document.norm.citation or reading.document.norm.title}: "
                  "su lectura espera la validación del evaluador",
                  f"{url}?lectura={reading.pk}#s5-lectura", 1, "Ver el informe")
             for reading in _pending_readings()]
    waiting = NormUpload.objects.filter(state=ProposalState.PROPUESTO).order_by("pk")
    items += [Item(f"Norma subida «{one.file_name}»: faltan confirmar sus datos",
                   f"{url}#s5-subida-{one.pk}", 1, "Revisar") for one in waiting]
    missing = tuple(
        Missing(f"Modificatoria sin cargar: {entry.norm_type} {entry.number}/{entry.year} "
                f"({entry.issuer}), de {entry.target_norm.citation or entry.target_norm.title}",
                f"{url}#s5-subir", "Subir norma")
        for entry in PendingAmendment.objects.filter(loaded_norm__isnull=True)
        .select_related("target_norm").order_by("pk"))
    return TemaStatus(pending=len(items), pending_items=tuple(items), missing=missing)


# --- Contexto del parcial ------------------------------------------------------------------------


def _evidence(entry):
    evidence = entry["evidencia"]
    if not evidence:
        return None
    text = evidence["texto"] or ""
    return {"page": evidence["pagina"],
            "text": text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"}


def _field_rows(proposal):
    rows = []
    for name in upload.FIELD_NAMES:
        entry = proposal["fields"][name]
        current = upload.current_value(entry)
        rows.append({
            "name": name, "label": loading.FIELDS[name][0], "value": _show(name, current),
            "raw": "" if current is None else current,
            "proposed": _show(name, entry["propuesto"]),
            "recognized": entry["reconocido"], "evidence": _evidence(entry),
            "corrected": entry["corregido"] is not None,
            "reason": entry["motivo"] or "", "who": entry["quien"] or "",
            "when": local(datetime.datetime.fromisoformat(entry["cuando"]))
            if entry["cuando"] else "",
            "required": name in loading.REQUIRED,
            "empty": current in (None, ""),
            "kind": INPUT_KINDS.get(name, "text"), "hint": HINTS.get(name, ""),
        })
    return rows


def _waiting_uploads():
    waiting = []
    for one in NormUpload.objects.filter(state=ProposalState.PROPUESTO).select_related(
            "uploaded_by").order_by("pk"):
        fields = _field_rows(one.proposal)
        waiting.append({
            "id": one.pk, "file_name": one.file_name, "pages": one.proposal.get("pages"),
            "format": one.get_file_format_display(), "when": local(one.uploaded_at),
            "who": one.uploaded_by.username if one.uploaded_by_id else "",
            "fields": fields,
            "to_check": sum(1 for f in fields if f["required"] and f["empty"]),
        })
    return waiting


def _norm_rows(user):
    items = listing.list_norms(user)
    document_ids = [d.id for item in items for d in item.documents]
    uploads = {u.document_id: u for u in NormUpload.objects.filter(document_id__in=document_ids)
               .select_related("uploaded_by")}
    validated = {r.pk: r for r in Reading.objects.filter(
        document_id__in=document_ids, status=ReadingStatus.VALIDATED)}
    loaded = {d.pk: d.loaded_at for d in Document.objects.filter(pk__in=document_ids)}
    rows = []
    for item in items:
        for position, document in enumerate(item.documents):
            icon, name = READING_STATES[document.reading_status]
            reading = validated.get(document.reading_id)
            if reading is not None and reading.validated_at:
                name = f"Validada el {local_date(reading.validated_at)}"
            origin = uploads.get(document.id)
            if origin is not None and origin.uploaded_by_id:
                where = (f"Archivo subido por {origin.uploaded_by.username} el "
                         f"{local_date(origin.uploaded_at)}")
            else:
                where = f"Archivo cargado el {local_date(loaded[document.id])}"
            rows.append({
                "citation": item.citation or item.title,
                "category": Category(item.category).label,
                "part": document.part,
                "version": (f"versión {document.version_number}" if document.version_number
                            else "sin versión"),
                "in_use": document.in_use, "icon": icon, "state": name,
                "file_name": document.file_name, "origin": where,
                "reading_id": document.reading_id,
                "general": item.general_regime,
                "amendments": [f"{a.norm_type} {a.number}/{a.year} ({a.issuer})"
                               for a in item.pending_amendments] if position == 0 else [],
            })
    return rows, items


def _report(user, reading_id):
    """El informe de lectura pedido en la dirección, con lo que pasa al validar."""
    try:
        reading_id = int(reading_id)
    except (TypeError, ValueError):
        return None
    try:
        report = listing.reading_report(user, reading_id)
    except listing.ReadingNotFound as error:
        return {"error": str(error)}
    icon, name = READING_STATES[report.status]
    data = {"id": report.reading_id, "citation": report.citation or report.title,
            "title": report.title, "part": report.part, "file_name": report.file_name,
            "sequence": report.sequence, "icon": icon, "state": name, "text": report.report_text,
            "pending": report.status == ReadingStatus.PENDING, "summary": None, "note": "",
            "error": ""}
    if data["pending"] and _can_write(user):
        try:
            summary = validation.reading_summary(user, reading_id, channel=CHANNEL)
        except validation.ValidationRefused as error:
            data["note"] = str(error)
        else:
            if not summary["in_use"]:
                effect = ("Al validar, este documento no entra en las consultas hasta "
                          "registrarlo como versión.")
            elif summary["replaces"]:
                effect = "Al validar, esta lectura reemplaza en las consultas a la anterior."
            else:
                effect = "Al validar, la norma queda disponible para consultas."
            data["summary"] = {"units": summary["units"], "effect": effect,
                               "relations": [w["text"] for w in summary["relations_without_unit"]]}
    return data


def context(user, procedure, request):
    base = {"pid": procedure.pk if procedure is not None else None,
            "aviso": unpack(request.GET.get("aviso")) if request else None}
    rows, items = _norm_rows(user)
    upload_blocked = _missing_roles(user, evaluator=False)
    validate_blocked = _missing_roles(user, evaluator=True)
    return {
        **base, "rows": rows, "norm_count": len(items),
        "unvalidated": _pending_readings().count(), "waiting": _waiting_uploads(),
        "categories": Category.choices,
        "upload_blocked": upload_blocked, "can_upload": not upload_blocked,
        "validate_blocked": validate_blocked, "can_validate": not validate_blocked,
        "report": _report(user, request.GET.get("lectura")) if request else None,
    }


# --- Acciones ------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _require(request, role, name):
    require_commission_role(request.user, role,
                            operation=f"evaluon.journey.temas.s5_normas.{name}", channel=CHANNEL)


@require_POST
def upload_file(request, procedure_id):
    """Sube el archivo de una norma: el sistema la lee y propone sus datos (`upload.stage`)."""
    procedure = _procedure(procedure_id)
    _require(request, CommissionRole.OPERATOR, "upload_file")
    file = request.FILES.get("file")
    if file is None:
        return _back(procedure, "Elija el archivo de la norma (un PDF o una página web "
                                "guardada).", ok=False)
    try:
        staged = upload.stage(request.user, file.read(), file.name, channel=CHANNEL)
    except (loading.LoadRefused, upload.UploadRefused) as error:
        return _back(procedure, str(error), ok=False)
    unknown = sum(1 for e in staged.proposal["fields"].values() if not e["reconocido"])
    tail = (f" {unknown} dato(s) no se reconocieron: complételos escribiendo el valor y el "
            "motivo." if unknown else " Revise los datos y cargue la norma.")
    return _back(procedure, f"Se subió «{staged.file_name}» y el sistema la leyó "
                            f"({staged.proposal['pages']} página(s)).{tail}",
                 anchor=f"s5-subida-{staged.pk}")


@require_POST
def correct(request, procedure_id, upload_id):
    """Corrige o completa un dato propuesto, con valor y motivo (`upload.correct`)."""
    procedure = _procedure(procedure_id)
    _require(request, CommissionRole.OPERATOR, "correct")
    field = request.POST.get("field", "")
    anchor = f"s5-subida-{upload_id}"
    try:
        upload.correct(request.user, upload_id, field, request.POST.get("value", ""),
                       request.POST.get("reason", ""), channel=CHANNEL)
    except upload.UploadRefused as error:
        return _back(procedure, str(error), ok=False, anchor=anchor)
    return _back(procedure, f"Se guardó el dato «{loading.FIELDS[field][0]}» con su motivo, "
                            "quién y cuándo. El valor que propuso el sistema se conserva en el "
                            "registro.", anchor=anchor)


@require_POST
def load(request, procedure_id, upload_id):
    """Carga la norma con los datos confirmados (`upload.confirm`); deja su lectura pendiente."""
    procedure = _procedure(procedure_id)
    _require(request, CommissionRole.OPERATOR, "load")
    anchor = f"s5-subida-{upload_id}"
    try:
        result = upload.confirm(
            request.user, upload_id, part=(request.POST.get("part", "").strip() or None),
            general_regime=request.POST.get("general_regime") == "on",
            same_norm_confirmation=request.POST.get("same_norm") or None, channel=CHANNEL)
    except (upload.UploadRefused, loading.LoadRefused) as error:
        return _back(procedure, str(error), ok=False, anchor=anchor)
    name = result.norm.citation or result.norm.title
    return _back(procedure, f"Se cargó la norma {name} (parte {result.document.part}). Quedó su "
                            "informe de lectura: falta que lo valide un evaluador.",
                 anchor="s5-lectura", reading=result.reading.pk)


@require_POST
def validate(request, procedure_id, reading_id):
    """Valida la lectura de una norma (`validation.validate_reading`): solo el evaluador."""
    procedure = _procedure(procedure_id)
    _require(request, CommissionRole.EVALUATOR, "validate")
    try:
        result = validation.validate_reading(request.user, reading_id, channel=CHANNEL)
    except validation.ValidationRefused as error:
        return _back(procedure, str(error), ok=False, anchor="s5-lectura", reading=reading_id)
    norm = result.reading.document.norm
    if result.in_use:
        done = (f"Se validó la lectura {result.reading.pk} de {norm.citation or norm.title}, con "
                f"{result.passages} pasajes. Quedó en uso como versión {result.version_number} "
                f"de su parte. Se creó la versión {result.corpus_version} de la normativa.")
    else:
        done = (f"Se validó la lectura {result.reading.pk}; el documento no entra en las "
                "consultas hasta registrarlo como versión.")
    if result.relations_without_unit:
        done += " Atención: " + " ".join(w["text"] for w in result.relations_without_unit)
    return _back(procedure, done, anchor="s5-normas")


urlpatterns = [
    path("normativas/norma/subir/", upload_file, name="s5_subir"),
    path("normativas/subida/<int:upload_id>/corregir/", correct, name="s5_corregir"),
    path("normativas/subida/<int:upload_id>/cargar/", load, name="s5_cargar"),
    path("normativas/lectura/<int:reading_id>/validar/", validate, name="s5_validar"),
]
