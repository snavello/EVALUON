"""Subir el archivo de una norma (T-213; REQ-094, ADR-0051, plan 014, "Modelo de datos").

Una norma se carga «solo subiendo el archivo». Tres pasos, sin pantalla y sin IA:

1. `stage(user, data, file_name)`: guarda el archivo en `norms_upload` (estado `leyendo`),
   lo lee con la lectura existente y propone los diez datos de la norma con su evidencia
   (página y texto), por reglas sobre el encabezado y el pie (`splitting/header_fields.py`).
   Lo que no reconoce queda marcado (`reconocido: false`). Termina en `propuesto`. Un
   archivo ya cargado se rechaza como lo hace la carga (`FileAlreadyLoaded`); también uno
   que ya espera confirmación.
2. `correct(user, upload_id, field, value, reason)`: corrige o completa un dato. El motivo
   es obligatorio. Cada dato guarda `{propuesto, corregido, motivo, quien, cuando}` y la
   lista de correcciones: el valor propuesto original no se pierde.
3. `confirm(user, upload_id)`: llama a `load_norm` con los datos confirmados (el corregido
   si lo hay, si no el propuesto) y, en la misma transacción, marca la subida `aprobado`
   con el documento resultante y registra el hecho. Si `load_norm` rechaza la carga, no
   queda nada aprobado y la subida sigue `propuesto`.

Cada paso deja un hecho `norm_upload` (P6). Mantiene el rol de lectura y escritura de la
carga. `load_norm` se llama sin cambios: sus reglas (duplicados, versionado) siguen siendo
las del comando.

Forma de `NormUpload.proposal`:

    {"fields": {"<dato>": {"propuesto": ..., "reconocido": true|false,
                           "evidencia": {"pagina": 1|null, "texto": "..."} | null,
                           "corregido": null, "motivo": null, "quien": null,
                           "cuando": null, "correcciones": []}},
     "format": "pdf", "pages": 45}

Las fechas van como `AAAA-MM-DD`.
"""

import hashlib
from datetime import date

from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Category, NormUpload, ProposalState
from evaluon.norms.reading import read_document
from evaluon.norms.services import loading
from evaluon.norms.splitting.header_fields import propose_fields

DATE_FIELDS = ("publication_date", "effective_from")
FIELD_NAMES = tuple(loading.FIELDS)


class UploadRefused(Exception):
    """No se pudo hacer el paso. El mensaje dice por qué, en lenguaje llano."""

    reason = "refused"


class UploadNotFound(UploadRefused):
    reason = "upload_not_found"


class UploadNotPending(UploadRefused):
    """La subida no está esperando confirmación (ya se aprobó, falló o se rechazó)."""

    reason = "upload_not_pending"


class AlreadyStaged(UploadRefused):
    """Ese archivo ya espera confirmación."""

    reason = "already_staged"

    def __init__(self, message, upload):
        super().__init__(message)
        self.upload = upload


class InvalidCorrection(UploadRefused):
    reason = "invalid_correction"


class MissingConfirmedData(UploadRefused):
    """Faltan datos para confirmar. `missing` son los nombres de los datos."""

    reason = "missing_data"

    def __init__(self, message, missing):
        super().__init__(message)
        self.missing = missing


def _serialize(value):
    return value.isoformat() if isinstance(value, date) else value


def _field_entry(proposed):
    if proposed is None:
        return {"propuesto": None, "reconocido": False, "evidencia": None,
                "corregido": None, "motivo": None, "quien": None, "cuando": None,
                "correcciones": []}
    return {"propuesto": _serialize(proposed.value), "reconocido": True,
            "evidencia": {"pagina": proposed.page, "texto": proposed.text},
            "corregido": None, "motivo": None, "quien": None, "cuando": None,
            "correcciones": []}


def current_value(entry):
    """El valor que vale de un dato: el corregido si lo hay, si no el propuesto."""
    return entry["corregido"] if entry["corregido"] is not None else entry["propuesto"]


def _get(upload_id, *, lock=False):
    query = NormUpload.objects.select_for_update() if lock else NormUpload.objects
    upload = query.filter(pk=upload_id).first()
    if upload is None:
        raise UploadNotFound("No existe esa norma subida.")
    return upload


def _require_pending(upload):
    if upload.state != ProposalState.PROPUESTO:
        raise UploadNotPending(
            "Esta subida ya no espera confirmación "
            f"(estado: {upload.get_state_display().lower()})."
        )


def _record_refusal(user, channel, action, error, **detail):
    audit.record(EventType.NORM_UPLOAD, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail={"action": action, "reason": error.reason,
                                    "message": str(error), **detail})


def stage(user, data, file_name, *, channel=Channel.SCREEN):
    """Guarda el archivo de una norma, lo lee y propone sus datos. Devuelve la
    `NormUpload` en estado `propuesto`.

    Lanza `RoleRejected` sin el rol de lectura y escritura; `loading.FileAlreadyLoaded` si
    el archivo ya está cargado; `AlreadyStaged` si ya espera confirmación, y
    `loading.UnreadableFile` si no es un PDF ni una página web legible.
    """
    require_role(user, Role.READ_WRITE)
    sha256 = hashlib.sha256(data).hexdigest()
    file_detail = {"name": file_name, "size": len(data), "sha256": sha256}
    try:
        loading._check_file(sha256)
        waiting = NormUpload.objects.filter(
            file_sha256=sha256,
            state__in=(ProposalState.LEYENDO, ProposalState.PROPUESTO),
        ).first()
        if waiting is not None:
            raise AlreadyStaged(
                "Ese archivo ya se subió y espera confirmación "
                f"({waiting.file_name}, subida {waiting.pk}).", waiting.pk,
            )
        try:
            reading = read_document(data)
        except loading._UNREADABLE_ERRORS as error:
            raise loading.UnreadableFile(
                "No se pudo leer el archivo: no es un PDF ni una página web guardada "
                "(.html), o está dañado o incompleto. No se subió nada."
            ) from error
    except (loading.LoadRefused, UploadRefused) as error:
        _record_refusal(user, channel, "stage", error, file=file_detail)
        raise

    found = propose_fields(reading, file_name)
    proposal = {
        "fields": {name: _field_entry(found[name]) for name in FIELD_NAMES},
        "format": reading.file_format,
        "pages": len(reading.pages),
    }
    with transaction.atomic():
        upload = NormUpload.objects.create(
            file_name=file_name,
            file_format=reading.file_format,
            file_size=len(data),
            file_sha256=sha256,
            content=data,
            proposal=proposal,
            state=ProposalState.PROPUESTO,
            uploaded_by=user,
        )
        recognized = [n for n in FIELD_NAMES if proposal["fields"][n]["reconocido"]]
        audit.record(
            EventType.NORM_UPLOAD, outcome=Outcome.OK, channel=channel, user=user,
            detail={
                "action": "stage",
                "upload": upload.pk,
                "file": {**file_detail, "format": reading.file_format,
                         "pages": len(reading.pages)},
                "recognized": recognized,
                "not_recognized": [n for n in FIELD_NAMES if n not in recognized],
                "fields": {n: proposal["fields"][n]["propuesto"] for n in FIELD_NAMES},
                "tool_versions": reading.tool_versions,
            },
        )
    return upload


def _valid_value(field, value):
    """El valor de `field` como se guarda en el JSON, o `InvalidCorrection`."""
    if field not in FIELD_NAMES:
        raise InvalidCorrection(f"No existe el dato «{field}».")
    label = loading.FIELDS[field][0]
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        raise InvalidCorrection(f"Escriba el valor de {label}.")
    if field == "category":
        if value not in Category.values:
            raise InvalidCorrection(
                f"La categoría no es válida; use una de: {', '.join(Category.values)}."
            )
    elif field == "year":
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise InvalidCorrection(
                f"El año ({value}) no es válido: escríbalo con cuatro cifras."
            ) from None
        if not 1800 <= value <= 2200:
            raise InvalidCorrection(
                f"El año ({value}) no es válido: escríbalo con cuatro cifras."
            )
    elif field in DATE_FIELDS:
        if isinstance(value, date):
            value = value.isoformat()
        else:
            try:
                value = date.fromisoformat(value).isoformat()
            except (TypeError, ValueError):
                raise InvalidCorrection(
                    f"La fecha de {label} ({value}) no es válida: escríbala como "
                    "AAAA-MM-DD, por ejemplo 2023-01-01."
                ) from None
    else:
        value = str(value)
    return value


def correct(user, upload_id, field, value, reason, *, channel=Channel.SCREEN):
    """Corrige o completa un dato propuesto. El motivo es obligatorio. Guarda el valor
    propuesto, el corregido, el motivo, quién y cuándo, y deja el hecho. Devuelve la
    `NormUpload`."""
    require_role(user, Role.READ_WRITE)
    try:
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidCorrection("Escriba el motivo de la corrección.")
        new_value = _valid_value(field, value)
        with transaction.atomic():
            upload = _get(upload_id, lock=True)
            _require_pending(upload)
            entry = upload.proposal["fields"][field]
            now = timezone.now().isoformat(timespec="seconds")
            before = current_value(entry)
            entry["correcciones"].append(
                {"valor": new_value, "motivo": reason.strip(),
                 "quien": user.get_username(), "cuando": now}
            )
            entry.update(corregido=new_value, motivo=reason.strip(),
                         quien=user.get_username(), cuando=now)
            upload.save(update_fields=["proposal"])
            audit.record(
                EventType.NORM_UPLOAD, outcome=Outcome.OK, channel=channel, user=user,
                detail={"action": "correct", "upload": upload.pk, "field": field,
                        "propuesto": entry["propuesto"], "anterior": before,
                        "corregido": new_value, "motivo": reason.strip()},
            )
    except UploadRefused as error:
        _record_refusal(user, channel, "correct", error, upload=upload_id, field=field)
        raise
    return upload


def confirmed_fields(upload):
    """Los datos confirmados de la subida, listos para `load_norm`: fechas como `date`.
    Los que faltan van como `None`."""
    values = {}
    for name in FIELD_NAMES:
        value = current_value(upload.proposal["fields"][name])
        if value is not None and name in DATE_FIELDS:
            value = date.fromisoformat(value)
        values[name] = value
    return values


def confirm(user, upload_id, *, part=None, general_regime=False,
            same_norm_confirmation=None, confirm_same_norm=None, channel=Channel.SCREEN):
    """Carga la norma con los datos confirmados y deja la subida `aprobado`.

    `part`, `general_regime`, `same_norm_confirmation` y `confirm_same_norm` son los de
    `load_norm`. Devuelve el `LoadResult`. Lanza `MissingConfirmedData` si falta algún
    dato (no se llama a la carga), `UploadNotPending` si la subida ya no espera, y las
    excepciones de `load_norm` (`RoleRejected`, `LoadRefused`): en ese caso la subida
    sigue `propuesto`, para corregir los datos y volver a confirmar.
    """
    require_role(user, Role.READ_WRITE)
    refusal = None
    try:
        with transaction.atomic():
            upload = _get(upload_id, lock=True)
            _require_pending(upload)
            fields = confirmed_fields(upload)
            # El nombre de cita lo exige `load_norm` solo al dar de alta una norma nueva.
            blank = [n for n in loading.REQUIRED if fields[n] is None]
            if blank:
                raise MissingConfirmedData(
                    "Faltan datos para cargar la norma: "
                    + ", ".join(loading.FIELDS[n][0] for n in blank) + ".",
                    blank,
                )
            # Se atrapa el rechazo de la carga dentro del bloque para que el hecho que ella
            # registra no se deshaga con esta transacción.
            try:
                result = loading.load_norm(
                    user, data=bytes(upload.content), file_name=upload.file_name,
                    part=part, general_regime=general_regime,
                    same_norm_confirmation=same_norm_confirmation,
                    confirm_same_norm=confirm_same_norm, channel=channel, **fields,
                )
            except loading.LoadRefused as error:
                refusal = error
            else:
                upload.state = ProposalState.APROBADO
                upload.document = result.document
                upload.save(update_fields=["state", "document"])
                audit.record(
                    EventType.NORM_UPLOAD, outcome=Outcome.OK, channel=channel, user=user,
                    detail={"action": "confirm", "upload": upload.pk,
                            "document": result.document.pk, "norm": result.norm.pk,
                            "norm_created": result.created_norm,
                            "load_event": result.event.pk,
                            "fields": upload.proposal["fields"],
                            "part": part, "general_regime": general_regime},
                )
    except UploadRefused as error:
        _record_refusal(user, channel, "confirm", error, upload=upload_id)
        raise
    if refusal is not None:
        _record_refusal(user, channel, "confirm", UploadRefused(str(refusal)),
                        upload=upload_id, load_reason=refusal.reason)
        raise refusal
    return result


__all__ = [
    "AlreadyStaged", "InvalidCorrection", "MissingConfirmedData", "UploadNotFound",
    "UploadNotPending", "UploadRefused", "confirm", "confirmed_fields", "correct",
    "current_value", "stage",
]
