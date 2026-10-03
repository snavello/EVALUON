"""Carga de una norma (REQ-001, REQ-002, REQ-004, REQ-011, REQ-012, REQ-017, REQ-020;
plan 001, "Ingesta", "Una norma en más de un archivo", "Dónde se guarda el archivo
original" y "Registro de auditoría").

`load_norm` incorpora un documento con los datos de su norma, en este orden:

1. Comprueba el rol de lectura y escritura. El registro del rechazo por rol es de T-038.
2. Comprueba los datos: los de REQ-001 (tipo, número, año, organismo emisor, título,
   fecha de publicación, fecha de vigencia y fuente) y la categoría (REQ-017); la parte
   (`cuerpo` o la clave de un anexo; un dictamen o una recomendación, solo `cuerpo`); la
   marca de régimen general, que solo se acepta con categoría `regimen_especifico`
   (REQ-020); el nombre de cita, obligatorio al dar de alta una norma nueva (T-055); y
   la confirmación de misma norma, si se indica (`other_file` o `new_version`). Tipo,
   número y organismo se normalizan con `normalize_identity`.
3. Duplicados (REQ-011; plan 001, "Ingesta", punto 2), en este orden:
   - Misma huella de archivo: no se incorpora (`FileAlreadyLoaded`), aun con
     confirmación.
   - Si la norma ya existe (mismos tipo, número, año y organismo), los datos de la
     norma indicados tienen que coincidir con los registrados (`NormDataMismatch`).
   - Lee el documento (`norms/reading/`) y lo parte (`norms/splitting/`) con su parte y
     su categoría, en CPU y sin los servicios de IA.
   - Mismo texto canónico que otro documento (de cualquier norma y parte), o misma norma
     y misma parte que un documento ya cargado: "misma norma". Solo se incorpora con
     confirmación expresa, en la que la persona indica si es otro archivo de lo mismo o
     una versión nueva (`same_norm_confirmation`, o la respuesta de `confirm_same_norm`
     al aviso). Sin ella, `SameNormNotConfirmed`. El documento así incorporado queda,
     como todo documento cargado, sin versión y fuera de uso, y guarda la confirmación.
   - Misma norma con una parte que todavía no tiene: no es un duplicado. Se incorpora
     como otra parte y se informa en `LoadResult.notices`, junto con el aviso si la
     fecha de vigencia indicada difiere de la de otra parte en uso de la misma norma.
4. Completa en el informe los posibles duplicados (cada uno con su `detail`), vuelve a
   armar "Requiere atención" y el texto del informe, cuya huella firma la validación.
5. En una sola transacción guarda la norma si es nueva, el documento, el original byte
   por byte, la lectura `pending` con su texto canónico, su huella, las versiones de las
   herramientas y de las reglas, el informe y las unidades, y al final registra el hecho
   `load` con el resultado de las comprobaciones de duplicado, la confirmación y los
   avisos.

La fecha de vigencia es la que escribe la persona: la carga no la calcula ni la
completa. La carga no valida la lectura ni crea una versión de la normativa: eso pasa al
validar (T-015).

Una carga rechazada por los datos, por el archivo, por duplicado o por otra carga
simultánea también queda registrada como hecho `load` con resultado `rejected`, el motivo
y el resultado de las comprobaciones hechas, sin nada incorporado. Los mensajes de los
errores son para la persona que carga: en español llano.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
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
    SameNormConfirmation,
    Unit,
)
from evaluon.norms.reading import UnsupportedFormatError, read_document
from evaluon.norms.splitting import OPINION_RULE, RULES_VERSION, rule_for, split_document
from evaluon.norms.splitting.report import attention_items, report_text

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

# Clases de coincidencia de "misma norma" (REQ-011).
SAME_TEXT = "same_text"
SAME_NORM_PART = "same_norm_part"

# Cómo se nombra cada confirmación en los mensajes.
CONFIRMATION_NAMES = {
    SameNormConfirmation.OTHER_FILE: "otro archivo de lo mismo",
    SameNormConfirmation.NEW_VERSION: "versión nueva",
}

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


class FileAlreadyLoaded(LoadRefused):
    reason = "file_already_loaded"

    def __init__(self, message, document):
        super().__init__(message)
        self.document = document


class SameNormNotConfirmed(LoadRefused):
    """"Misma norma" sin confirmación expresa. `matches` son las coincidencias."""

    reason = "same_norm_not_confirmed"

    def __init__(self, message, matches):
        super().__init__(message)
        self.matches = matches


class ConcurrentLoad(LoadRefused):
    """Otra carga guardó al mismo tiempo el mismo archivo o la misma norma."""

    reason = "concurrent_load"


class UnreadableFile(LoadRefused):
    reason = "unreadable_file"


@dataclass(frozen=True)
class SameNormWarning:
    """El aviso de "misma norma" que se muestra antes de pedir la confirmación:
    `message` en lenguaje llano y `matches`, las coincidencias."""

    message: str
    matches: list


@dataclass(frozen=True)
class LoadResult:
    norm: Norm
    document: Document
    reading: Reading
    units: int
    created_norm: bool
    event: object
    # Mensajes informativos para la persona: otra parte de una norma ya cargada y fecha
    # de vigencia distinta de la de otra parte en uso.
    notices: tuple = ()
    # El aviso de "misma norma" que se confirmó, si lo hubo.
    same_norm_warning: SameNormWarning | None = None


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


def _check_data(data, confirmation):
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
    if rule_for(data["category"]) == OPINION_RULE and data["part"] != BODY_PART:
        raise InvalidData(
            f"No se incorporó el documento: un dictamen o una recomendación se carga como "
            f"documento único, con la parte {BODY_PART}, y no como parte {data['part']}."
        )
    if not isinstance(data["year"], int) or data["year"] <= 0:
        raise InvalidData("No se incorporó el documento: el año tiene que ser un número.")
    for name in ("publication_date", "effective_from"):
        if not isinstance(data[name], date):
            raise InvalidData(
                f"No se incorporó el documento: la {FIELDS[name][0]} no es una fecha."
            )
    if confirmation is not None and confirmation not in SameNormConfirmation.values:
        raise InvalidData(
            f"No se incorporó el documento: la confirmación de misma norma {confirmation!r} "
            "no es válida. Indique otro archivo de lo mismo o una versión nueva."
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


def _check_file(sha256):
    loaded = Document.objects.select_related("norm").filter(file_sha256=sha256).first()
    if loaded is not None:
        raise FileAlreadyLoaded(
            f"No se incorporó el documento: ese archivo ya está cargado, como parte "
            f"{loaded.part} de la norma {loaded.norm.citation} ({loaded.file_name}).",
            loaded.pk,
        )


def _read(data):
    try:
        return read_document(data)
    except _UNREADABLE_ERRORS as error:
        raise UnreadableFile(
            "No se pudo leer el archivo: no es un PDF o está dañado o incompleto. "
            "No se incorporó nada."
        ) from error


def _match(kind, document):
    if kind == SAME_TEXT:
        text = (
            f"El texto extraído es el mismo texto del documento {document.pk} "
            f"({document.file_name}), parte {document.part} de la {document.norm.citation}."
        )
    else:
        text = (
            f"La {document.norm.citation} ya tiene cargado un documento como parte "
            f"{document.part}: el documento {document.pk} ({document.file_name})."
        )
    return {
        "kind": kind,
        "document": document.pk,
        "file_name": document.file_name,
        "part": document.part,
        "norm": document.norm.citation,
        "text": text,
    }


def _same_norm_matches(norm, part, canonical_sha256):
    """Coincidencias de "misma norma": documentos con el mismo texto canónico (de
    cualquier norma y parte; en cualquiera de sus lecturas) y documentos de la misma
    norma y la misma parte."""
    same_text = list(
        Document.objects.select_related("norm")
        .filter(readings__canonical_sha256=canonical_sha256)
        .distinct()
        .order_by("pk")
    )
    same_part = (
        list(norm.documents.select_related("norm").filter(part=part).order_by("pk"))
        if norm is not None
        else []
    )
    matches = [_match(SAME_TEXT, d) for d in same_text]
    matches += [_match(SAME_NORM_PART, d) for d in same_part]
    return matches, same_text, same_part


def _same_norm_message(matches):
    lines = "\n".join(f"  - {match['text']}" for match in matches)
    return (
        "Atención, misma norma: el documento parece ser una norma ya incorporada.\n"
        f"{lines}\n"
        "Solo se incorpora con confirmación expresa: indique si es otro archivo de lo "
        "mismo (por ejemplo, otro formato) o una versión nueva. El documento incorporado "
        "así no se usa en las consultas hasta registrarlo con registrar_version."
    )


def _part_name(part):
    return f"el {part}"


def _join(parts):
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def _existing_parts(norm):
    parts = set(norm.documents.values_list("part", flat=True))
    return sorted(parts, key=lambda part: (part != BODY_PART, part))


def _notices(norm, data, existing_parts):
    """Mensajes informativos al sumar una parte a una norma ya cargada (plan 001, "Una
    norma en más de un archivo")."""
    notices = []
    if existing_parts and data["part"] not in existing_parts:
        loaded = "cargados" if len(existing_parts) > 1 else "cargado"
        notices.append(
            f"Se suma como parte {data['part']} de la {norm.citation}, que ya tiene "
            f"{loaded} {_join([_part_name(p) for p in existing_parts])}."
        )
    differing = []
    if norm is not None:
        differing = list(
            norm.documents.filter(in_use=True)
            .exclude(part=data["part"])
            .exclude(effective_from=data["effective_from"])
            .order_by("part", "pk")
        )
    for document in differing:
        notices.append(
            f"Atención: la fecha de vigencia indicada ({data['effective_from'].isoformat()}) "
            f"difiere de la de la parte {document.part} en uso "
            f"({document.effective_from.isoformat()}). Revísela antes de validar: las "
            "fechas de carga no se pueden corregir por comando."
        )
    return notices, differing


def _duplicates(matches, confirmation):
    """Los posibles duplicados del informe, cada uno con su `detail` en texto."""
    name = CONFIRMATION_NAMES.get(confirmation)
    items = []
    for match in matches:
        detail = match["text"]
        if name:
            detail += f" Se confirmó como {name}."
        items.append({**{k: v for k, v in match.items() if k != "text"},
                      "confirmation": confirmation, "detail": detail})
    return items


def _data_detail(data):
    return {name: data.get(name) for name in (*FIELDS, "part", "general_regime")}


def _file_detail(file_name, file_format, data, sha256):
    return {"name": file_name, "format": file_format, "size": len(data), "sha256": sha256}


def _record_refusal(user, channel, data, file_detail, error, checks, confirmation):
    detail = {"reason": error.reason, "message": str(error), "data": _data_detail(data),
              "file": file_detail, "duplicate_checks": checks,
              "same_norm_confirmation": confirmation}
    if isinstance(error, MissingData):
        detail["missing"] = error.missing
    if isinstance(error, NormDataMismatch):
        detail["registered"] = error.registered
        detail["differing"] = error.differing
    if isinstance(error, SameNormNotConfirmed):
        detail["matches"] = [
            {k: v for k, v in match.items() if k != "text"} for match in error.matches
        ]
    if isinstance(error, (UnreadableFile, ConcurrentLoad)) and error.__cause__ is not None:
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
              same_norm_confirmation=None, confirm_same_norm=None,
              channel=Channel.COMMAND, **fields):
    """Incorpora el documento `data` (los bytes del archivo, con su nombre `file_name`)
    como parte `part` de su norma y devuelve un `LoadResult`.

    `fields` son los datos de `FIELDS`: `category`, `norm_type`, `number`, `year`,
    `issuer`, `title`, `citation`, `publication_date`, `effective_from` y `source`. Las
    fechas son `date` y el año, un entero; un dato que falta va como `None`.

    Confirmación de "misma norma" (REQ-011): `same_norm_confirmation` la da de antemano
    (`other_file` o `new_version`); si no se da y hay aviso, se llama a
    `confirm_same_norm(aviso)` con un `SameNormWarning`, que devuelve uno de esos dos
    valores o `None` si la persona no confirma. Fuera del caso de "misma norma", la
    confirmación indicada no se guarda.

    Lanza `RoleRejected` si el usuario no tiene rol de lectura y escritura, y una
    subclase de `LoadRefused` si no se incorporó: datos que faltan o no son válidos,
    norma registrada con otros datos, archivo ya cargado, misma norma sin confirmar,
    archivo que no se puede leer u otra carga simultánea. En todos esos casos no se
    guarda nada salvo el hecho que lo registra.
    """
    require_role(user, Role.READ_WRITE)
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise TypeError(f"Datos desconocidos: {', '.join(sorted(unknown))}.")

    values = _clean({**dict.fromkeys(FIELDS), **fields, "part": part,
                     "general_regime": general_regime})
    sha256 = hashlib.sha256(data).hexdigest()
    file_detail = _file_detail(file_name, None, data, sha256)
    checks = {"same_file": None, "same_text": None, "same_norm_part": None,
              "new_part_of_norm": None, "existing_parts": None}
    confirmation = same_norm_confirmation
    warning = None

    try:
        _check_data(values, confirmation)
        # Primero el mismo archivo, por su huella (plan 001, "Ingesta", punto 2): se
        # reconoce antes que la parte o los datos de la norma.
        try:
            _check_file(sha256)
        except FileAlreadyLoaded as error:
            checks["same_file"] = error.document
            raise
        identity = {name: values[name] for name in ("norm_type", "number", "year", "issuer")}
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
        file_detail["format"] = reading_data.file_format
        read_at = timezone.localtime().isoformat(timespec="seconds")
        split = split_document(
            reading_data,
            part=values["part"],
            category=values["category"],
            document_info={"file_name": file_name, "file_sha256": sha256,
                           "read_at": read_at},
        )

        matches, same_text, same_part = _same_norm_matches(
            norm, values["part"], split.canonical_sha256
        )
        checks["same_text"] = [d.pk for d in same_text]
        checks["same_norm_part"] = [d.pk for d in same_part]
        if matches:
            warning = SameNormWarning(message=_same_norm_message(matches), matches=matches)
            if confirmation is None and confirm_same_norm is not None:
                confirmation = confirm_same_norm(warning)
                if confirmation is not None and confirmation not in SameNormConfirmation.values:
                    confirmation = None
            if confirmation is None:
                raise SameNormNotConfirmed(
                    "No se incorporó el documento: es la misma norma que un documento ya "
                    "cargado y no se confirmó si es otro archivo de lo mismo o una "
                    "versión nueva.\n"
                    + "\n".join(f"  - {match['text']}" for match in matches),
                    matches,
                )
        else:
            confirmation = None
        existing_parts = _existing_parts(norm) if norm is not None else []
        if existing_parts and not same_part:
            checks["new_part_of_norm"] = norm.pk
        checks["existing_parts"] = existing_parts
        notices, differing_dates = _notices(norm, values, existing_parts)
    except LoadRefused as error:
        _record_refusal(user, channel, values, file_detail, error, checks, confirmation)
        raise

    report = split.report
    report["duplicates"] = _duplicates(matches, confirmation)
    report["attention"] = attention_items(report)
    text = report_text(report)
    tool_versions = {**reading_data.tool_versions, "rules_version": RULES_VERSION}

    try:
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
                same_norm_confirmation=confirmation or "",
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
                report=report,
                report_text=text,
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
                    "report": _report_summary(report),
                    "duplicate_checks": checks,
                    "same_norm_confirmation": confirmation,
                    "notices": notices,
                    "effective_from_differs": [
                        {"document": d.pk, "part": d.part,
                         "effective_from": d.effective_from.isoformat()}
                        for d in differing_dates
                    ],
                },
            )
    except IntegrityError as error:
        # Dos cargas simultáneas del mismo archivo o de la misma norma nueva: la base
        # deja pasar una sola (huella única; tipo, número, año y organismo únicos).
        refusal = ConcurrentLoad(
            "No se incorporó el documento: otra carga guardó al mismo tiempo el mismo "
            "archivo o la misma norma. Vuelva a intentarlo: el sistema le dirá si ya está "
            "cargado."
        )
        refusal.__cause__ = error
        _record_refusal(user, channel, values, file_detail, refusal, checks, confirmation)
        raise refusal from error

    return LoadResult(
        norm=norm,
        document=document,
        reading=reading,
        units=units,
        created_norm=created_norm,
        event=event,
        notices=tuple(notices),
        same_norm_warning=warning,
    )
