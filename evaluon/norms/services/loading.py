"""Carga de una norma (REQ-001, REQ-002, REQ-004, REQ-012, REQ-017, REQ-020; plan 001,
"Ingesta", "Una norma en más de un archivo", "Dónde se guarda el archivo original" y
"Registro de auditoría").

`load_norm` incorpora un documento con los datos de su norma, en este orden:

1. Comprueba el rol de lectura y escritura. El registro del rechazo por rol es de T-038.
2. Comprueba los datos: los de REQ-001 (tipo, número, año, organismo emisor, título,
   fecha de publicación, fecha de vigencia y fuente) y la categoría (REQ-017); la parte
   (`cuerpo` o la clave de un anexo); la marca de régimen general, que solo se acepta
   con categoría `regimen_especifico` (REQ-020); y el nombre de cita, obligatorio al dar
   de alta una norma nueva (T-055). Tipo, número y organismo se normalizan con
   `normalize_identity`.
3. El mismo archivo no se carga dos veces: se comprueba primero, por su huella (plan
   001, "Ingesta", punto 2). Si la norma ya existe (mismos tipo, número, año y
   organismo), el documento se suma a ella como otra parte, siempre que los datos de la
   norma indicados coincidan con los registrados y que la norma todavía no tenga esa
   parte. El aviso de "misma norma" con confirmación expresa y los mensajes
   informativos son de T-026.
4. Lee el documento (`norms/reading/`) y lo parte (`norms/splitting/`) con su parte, en
   CPU y sin los servicios de IA.
5. En una sola transacción guarda la norma si es nueva, el documento (sin versión y fuera
   de uso), el original byte por byte, la lectura `pending` con su texto canónico, su
   huella, las versiones de las herramientas y de las reglas, el informe y las unidades,
   y al final registra el hecho `load`.

La fecha de vigencia es la que escribe la persona: la carga no la calcula ni la
completa. La carga no valida la lectura ni crea una versión de la normativa: eso pasa al
validar (T-015).

Una carga rechazada por los datos, por el archivo o por estar ya cargado también queda
registrada como hecho `load` con resultado `rejected` y el motivo, sin nada incorporado.
Los mensajes de los errores son para la persona que carga: en español llano.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from pdfminer.psparser import PSException
from pdfplumber.utils.exceptions import PdfminerException

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import (
    ANNEX_PART_REGEX,
    BODY_PART,
    Category,
    Document,
    DocumentFile,
    Norm,
    Reading,
    ReadingStatus,
    Unit,
)
from evaluon.norms.reading import UnsupportedFormatError, read_document
from evaluon.norms.splitting import RULES_VERSION, split_document

# Datos de la norma y del documento, con el nombre que ve la persona y la opción del
# comando que los recibe.
FIELDS = {
    "category": ("categoría", "--categoria"),
    "norm_type": ("tipo", "--tipo"),
    "number": ("número", "--numero"),
    "year": ("año", "--anio"),
    "issuer": ("organismo emisor", "--organismo"),
    "title": ("título", "--titulo"),
    "citation": ("nombre de cita", "--nombre"),
    "publication_date": ("fecha de publicación", "--fecha-publicacion"),
    "effective_from": ("fecha de vigencia", "--fecha-vigencia"),
    "source": ("fuente", "--fuente"),
}

# Obligatorios en toda carga. El nombre de cita, solo al dar de alta una norma nueva.
REQUIRED = (
    "category",
    "norm_type",
    "number",
    "year",
    "issuer",
    "title",
    "publication_date",
    "effective_from",
    "source",
)

# Datos de la norma que se escriben una vez, con la primera parte (plan 001, "Una norma
# en más de un archivo"). El nombre de cita se compara solo si se indica.
NORM_DATA = ("category", "title", "general_regime", "citation")

_PART = re.compile(rf"{re.escape(BODY_PART)}|{ANNEX_PART_REGEX.strip('^$')}")

# Vocales con tilde o diéresis y su forma sin marca. La eñe se conserva, como en la
# búsqueda por palabras (ADR-0007, adenda "La eñe").
_ACCENTS = str.maketrans("áéíóúàèìòùäëïöü", "aeiouaeiouaeiou")

# Errores de lectura de un archivo que no se puede leer: no es un PDF, o es un PDF
# truncado o dañado (pdfplumber los entrega como `PdfminerException`; pdfminer puede
# lanzar los suyos al leer una página).
_UNREADABLE_ERRORS = (UnsupportedFormatError, PdfminerException, PSException)


class LoadRefused(Exception):
    """No se incorporó el documento. El mensaje dice por qué, en lenguaje llano."""

    reason = "refused"


class MissingData(LoadRefused):
    """Faltan datos obligatorios. `missing` son los nombres de los campos."""

    reason = "missing_data"

    def __init__(self, message, missing):
        super().__init__(message)
        self.missing = missing


class InvalidData(LoadRefused):
    reason = "invalid_data"


class NormDataMismatch(LoadRefused):
    """La norma ya existe con otros datos. `registered` son los datos registrados."""

    reason = "norm_data_mismatch"

    def __init__(self, message, registered, differing):
        super().__init__(message)
        self.registered = registered
        self.differing = differing


class PartAlreadyLoaded(LoadRefused):
    reason = "part_already_loaded"


class FileAlreadyLoaded(LoadRefused):
    reason = "file_already_loaded"


class UnreadableFile(LoadRefused):
    reason = "unreadable_file"


@dataclass(frozen=True)
class LoadResult:
    norm: Norm
    document: Document
    reading: Reading
    units: int
    created_norm: bool
    event: object


def normalize_identity(value):
    """Forma normalizada de tipo, número y organismo emisor (plan 001, `norms_norm`):
    sin espacios de más, en minúsculas y sin tildes (la eñe se conserva).
    "Disposición" → "disposicion"; "AFIP" → "afip"."""
    return " ".join(str(value).split()).lower().translate(_ACCENTS)


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _clean(fields):
    """Los datos tal como se guardan: textos sin espacios de más; tipo, número y
    organismo normalizados."""
    cleaned = dict(fields)
    for name in ("category", "title", "citation", "source"):
        if isinstance(cleaned.get(name), str):
            cleaned[name] = cleaned[name].strip()
    for name in ("norm_type", "number", "issuer"):
        if not _blank(cleaned.get(name)):
            cleaned[name] = normalize_identity(cleaned[name])
    if _blank(cleaned.get("part")):
        cleaned["part"] = BODY_PART
    else:
        cleaned["part"] = cleaned["part"].strip().lower()
    cleaned["general_regime"] = bool(cleaned.get("general_regime"))
    return cleaned


def _names(fields):
    return ", ".join(f"{FIELDS[name][0]} ({FIELDS[name][1]})" for name in fields)


def _check_data(data):
    missing = [name for name in REQUIRED if _blank(data.get(name))]
    if missing:
        message = f"No se incorporó el documento: falta indicar {_names(missing)}."
        if "category" in missing:
            message += (
                " Indique la categoría con --categoria, una de: "
                f"{', '.join(Category.values)}."
            )
        raise MissingData(message, missing)

    if data["category"] not in Category.values:
        raise InvalidData(
            f"No se incorporó el documento: la categoría {data['category']!r} no es "
            f"válida. Use una de: {', '.join(Category.values)}."
        )
    if data["general_regime"] and data["category"] != Category.REGIMEN_ESPECIFICO:
        raise InvalidData(
            "No se incorporó el documento: la marca de régimen general (--regimen-general) "
            "solo se acepta con la categoría regimen_especifico."
        )
    if not _PART.fullmatch(data["part"]):
        raise InvalidData(
            f"No se incorporó el documento: la parte {data['part']!r} no es válida. "
            "Use cuerpo o la clave de un anexo, como anexo o anexo-i."
        )
    if not isinstance(data["year"], int) or data["year"] <= 0:
        raise InvalidData("No se incorporó el documento: el año tiene que ser un número.")
    for name in ("publication_date", "effective_from"):
        if not isinstance(data[name], date):
            raise InvalidData(
                f"No se incorporó el documento: la {FIELDS[name][0]} no es una fecha."
            )


def _registered_data(norm):
    return {
        "category": norm.category,
        "title": norm.title,
        "general_regime": norm.general_regime,
        "citation": norm.citation,
    }


def _describe(values):
    return (
        f"Categoría: {values['category']}. Título: {values['title']}. "
        f"Régimen general: {'sí' if values['general_regime'] else 'no'}. "
        f"Nombre de cita: {values['citation']}."
    )


def _check_existing_norm(norm, data):
    registered = _registered_data(norm)
    differing = [
        name
        for name in NORM_DATA
        if not (name == "citation" and _blank(data.get("citation")))
        and data[name] != registered[name]
    ]
    if differing:
        indicated = {**registered, **{name: data[name] for name in differing}}
        raise NormDataMismatch(
            f"No se incorporó el documento: la norma {norm.citation} ya está cargada con "
            "otros datos. Para sumarle una parte, indique los datos registrados.\n"
            f"Registrados: {_describe(registered)}\n"
            f"Indicados: {_describe(indicated)}",
            registered,
            differing,
        )
    loaded = norm.documents.filter(part=data["part"]).first()
    if loaded is not None:
        raise PartAlreadyLoaded(
            f"No se incorporó el documento: la norma {norm.citation} ya tiene cargado un "
            f"documento como parte {data['part']} ({loaded.file_name}). Esta versión del "
            "sistema todavía no permite cargar otro archivo de la misma parte."
        )


def _check_file(sha256):
    loaded = Document.objects.select_related("norm").filter(file_sha256=sha256).first()
    if loaded is not None:
        raise FileAlreadyLoaded(
            f"No se incorporó el documento: ese archivo ya está cargado, como parte "
            f"{loaded.part} de la norma {loaded.norm.citation} ({loaded.file_name})."
        )


def _read(data):
    try:
        return read_document(data)
    except _UNREADABLE_ERRORS as error:
        raise UnreadableFile(
            "No se pudo leer el archivo: no es un PDF o está dañado o incompleto. "
            "No se incorporó nada."
        ) from error


def _data_detail(data):
    return {name: data.get(name) for name in (*FIELDS, "part", "general_regime")}


def _file_detail(file_name, file_format, data, sha256):
    return {"name": file_name, "format": file_format, "size": len(data), "sha256": sha256}


def _record_refusal(user, channel, data, file_detail, error):
    detail = {"reason": error.reason, "message": str(error), "data": _data_detail(data),
              "file": file_detail}
    if isinstance(error, MissingData):
        detail["missing"] = error.missing
    if isinstance(error, NormDataMismatch):
        detail["registered"] = error.registered
        detail["differing"] = error.differing
    if isinstance(error, UnreadableFile) and error.__cause__ is not None:
        detail["error"] = f"{type(error.__cause__).__name__}: {error.__cause__}"
    audit.record(EventType.LOAD, outcome=Outcome.REJECTED, channel=channel, user=user,
                 detail=detail)


def _save_units(reading, drafts):
    """Guarda las unidades en el orden del documento. `parent` sale de `parent_key`: la
    unidad que contiene a otra viene antes en la lista."""
    saved = {}
    for draft in drafts:
        saved[draft.key] = Unit.objects.create(
            reading=reading,
            parent=saved[draft.parent_key] if draft.parent_key else None,
            unit_type=draft.unit_type,
            number=draft.number,
            label=draft.label,
            key=draft.key,
            path=draft.path,
            order=draft.order,
            page_start=draft.page_start,
            page_end=draft.page_end,
            char_start=draft.char_start,
            char_end=draft.char_end,
            text=draft.text,
            text_origin=draft.text_origin,
            ocr_confidence_min=draft.ocr_confidence_min,
            ocr_confidence_avg=draft.ocr_confidence_avg,
        )
    return len(saved)


def _report_summary(report):
    return {
        "units_by_type": report["units"]["by_type"],
        "pages_not_read": report["pages"]["not_read"],
        "unlocated": len(report["unlocated"]),
    }


def load_norm(user, *, data, file_name, part=None, general_regime=False,
              channel=Channel.COMMAND, **fields):
    """Incorpora el documento `data` (los bytes del archivo, con su nombre `file_name`)
    como parte `part` de su norma y devuelve un `LoadResult`.

    `fields` son los datos de `FIELDS`: `category`, `norm_type`, `number`, `year`,
    `issuer`, `title`, `citation`, `publication_date`, `effective_from` y `source`. Las
    fechas son `date` y el año, un entero; un dato que falta va como `None`.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `LoadRefused` si no se incorporó: datos que faltan o no son válidos,
    norma registrada con otros datos, parte o archivo ya cargados, o archivo que no se
    puede leer. En todos esos casos no se guarda nada salvo el hecho que lo registra.
    """
    require_role(user, Role.READ_WRITE)
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise TypeError(f"Datos desconocidos: {', '.join(sorted(unknown))}.")

    values = _clean({**dict.fromkeys(FIELDS), **fields, "part": part,
                     "general_regime": general_regime})
    sha256 = hashlib.sha256(data).hexdigest()
    file_detail = _file_detail(file_name, None, data, sha256)

    try:
        _check_data(values)
        # Primero el mismo archivo, por su huella (plan 001, "Ingesta", punto 2): se
        # reconoce antes que la parte o los datos de la norma.
        _check_file(sha256)
        identity ={name: values[name] for name in ("norm_type", "number", "year", "issuer")}
        norm = Norm.objects.filter(**identity).first()
        if norm is None:
            if _blank(values["citation"]):
                raise MissingData(
                    "No se incorporó el documento: la norma es nueva y falta indicar su "
                    f"{_names(['citation'])}, por ejemplo \"Disposición AFIP 247/2022\".",
                    ["citation"],
                )
        else:
            _check_existing_norm(norm, values)
        reading_data = _read(data)
    except LoadRefused as error:
        _record_refusal(user, channel, values, file_detail, error)
        raise

    file_detail["format"] = reading_data.file_format
    split = split_document(reading_data, part=values["part"])
    tool_versions = {**reading_data.tool_versions, "rules_version": RULES_VERSION}

    with transaction.atomic():
        created_norm = norm is None
        if created_norm:
            norm = Norm.objects.create(
                **identity,
                category=values["category"],
                title=values["title"],
                citation=values["citation"],
                general_regime=values["general_regime"],
                created_by=user,
            )
        document = Document.objects.create(
            norm=norm,
            part=values["part"],
            publication_date=values["publication_date"],
            effective_from=values["effective_from"],
            source=values["source"],
            in_use=False,
            version_number=None,
            file_name=file_name,
            file_format=reading_data.file_format,
            file_size=len(data),
            file_sha256=sha256,
            loaded_by=user,
        )
        DocumentFile.objects.create(document=document, content=data)
        reading = Reading.objects.create(
            document=document,
            sequence=1,
            status=ReadingStatus.PENDING,
            pages=reading_data.as_json(),
            canonical_text=split.canonical_text,
            canonical_sha256=split.canonical_sha256,
            tool_versions=tool_versions,
            report=split.report,
            report_text=split.report_text,
            created_by=user,
        )
        units = _save_units(reading, split.units)
        event = audit.record(
            EventType.LOAD,
            outcome=Outcome.OK,
            channel=channel,
            user=user,
            detail={
                "norm": norm.pk,
                "norm_created": created_norm,
                "document": document.pk,
                "reading": reading.pk,
                "data": _data_detail(values),
                "file": file_detail,
                "canonical_sha256": split.canonical_sha256,
                "tool_versions": tool_versions,
                "units": units,
                "report": _report_summary(split.report),
            },
        )

    return LoadResult(
        norm=norm,
        document=document,
        reading=reading,
        units=units,
        created_norm=created_norm,
        event=event,
    )
