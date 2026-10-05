"""Registrar ofertas, cargar sus documentos, leerlos en segundo plano y entregar el original
(REQ-037, REQ-038; plan 008, "Carga y lectura", "Roles" y "Registro de auditoría"; T-130).

- `register_offer`: da de alta la oferta de un oferente en un procedimiento (REQ-037). Lo
  hacen el operador y el evaluador. El oferente es único dentro del procedimiento: repetirlo
  se rechaza con aviso. Deja el hecho `offer_register`, también si se rechaza.
- `load_document`: carga un archivo de la oferta, sin que la persona elija el tipo (lo
  clasifica el sistema al leer, por reglas, y queda vacío si no puede). Guarda el original
  byte por byte con su huella, encola su lectura (`read_offer_document`) y deja el hecho
  `offer_load`, todo en una transacción. El mismo archivo (misma huella) dos veces en la
  oferta se rechaza con aviso; toda carga rechazada deja el hecho `offer_load` con resultado
  `rejected`, su motivo y lo que se intentó cargar.
- `run_read_document`: el manejador del pedido `read_offer_document` (lo registra
  `tenders.jobs.HANDLERS`). Lee el documento con la lectura de la 001 (PDF con texto o
  escaneado, página por página, con el reconocimiento de texto existente), arma el texto
  canónico, lo parte en pasajes (`passages.py`) y calcula el vector de cada uno. Guarda la
  lectura, sus pasajes y su informe (páginas no leídas y de baja confianza, REQ-038) y deja
  el hecho `offer_read`, en una sola transacción. Si algo falla, deja el hecho `offer_read`
  con resultado `failed` y vuelve a lanzar el error para que la cola deje el pedido
  `failed`.
- `offers_page`, `offer_page`, `original_file`: lo que muestra la pantalla.

El rol se comprueba fuera de toda transacción, como en la 003, para que el hecho `rejected`
no se pierda si algo después se deshace. La lectura corre en CPU y los vectores con el
servicio local de embeddings, sin conexión a internet (P4).
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai import embeddings
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.reading import (
    PAGE_BLANK,
    PAGE_DOUBTFUL,
    PAGE_ILLEGIBLE,
    PAGE_NOT_READ,
)
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers import passages as passage_rules
from evaluon.offers import reading as reading_tools
from evaluon.offers.models import (
    Document,
    DocumentFile,
    DocumentKind,
    FileFormat,
    Offer,
    Passage,
    Reading,
)
from evaluon.tenders import jobs
from evaluon.tenders.models import Job, JobKind, JobStatus, Procedure

REGISTER_OPERATION = "evaluon.offers.services.offers.register_offer"
LOAD_OPERATION = "evaluon.offers.services.offers.load_document"
PAGE_OPERATION = "evaluon.offers.services.offers.offer_page"
LIST_OPERATION = "evaluon.offers.services.offers.offers_page"
ORIGINAL_OPERATION = "evaluon.offers.services.offers.original_file"

# Restricciones de la base que hacen únicos al oferente y a la huella.
_UNIQUE_BIDDER = "offers_offer_bidder_unique"
_UNIQUE_FILE = "offers_document_sha256_unique_in_offer"

# Estado de la lectura de un documento, para la pantalla (igual que en la 003).
STATE_QUEUED = "en_espera"
STATE_RUNNING = "leyendo"
STATE_READ = "leido"
STATE_FAILED = "fallido"

# Estados de página que van a la lista de "no leídas" y de "baja confianza" (REQ-038).
UNREAD_STATUSES = (PAGE_ILLEGIBLE, PAGE_NOT_READ)


class OfferRefused(ValueError):
    """No se hizo la operación. `field` es el dato que lo impidió y `reason`, el motivo
    que queda en el registro."""

    reason = "invalid_data"

    def __init__(self, message, field=None, reason=None):
        super().__init__(message)
        self.field = field
        if reason is not None:
            self.reason = reason


class DuplicateBidder(OfferRefused):
    reason = "duplicate_bidder"


class DuplicateFile(OfferRefused):
    """El mismo archivo ya está cargado en la oferta."""

    reason = "duplicate_file"

    def __init__(self, message, loaded_document):
        super().__init__(message, field="file")
        self.loaded_document = loaded_document


class OriginalChanged(RuntimeError):
    """El original guardado ya no tiene la huella con que se cargó."""


@dataclass(frozen=True)
class Loaded:
    """Lo que devuelve `load_document`: el documento, el pedido de lectura y el hecho."""

    document: Document
    job: Job
    event: object


@dataclass
class DocumentRow:
    """Un documento de la página de la oferta: su estado de lectura (`STATE_*`), el último
    pedido de lectura, la última lectura y sus páginas no leídas y de baja confianza."""

    document: Document
    state: str
    job: Job | None
    reading: Reading | None
    unread: list = field(default_factory=list)
    low_confidence: list = field(default_factory=list)


@dataclass
class OfferPage:
    """La oferta, sus documentos, las páginas que hay que revisar a mano y sus fichas."""

    offer: Offer
    documents: list
    unread: list
    low_confidence: list
    sheets: list
    sheet_job: Job | None
    validated_matrix: object

    @property
    def all_read(self):
        return bool(self.documents) and all(row.state == STATE_READ
                                            for row in self.documents)


@dataclass
class OfferRow:
    """Una oferta de la lista del procedimiento."""

    offer: Offer
    documents: int
    read: int
    failed: int
    sheet: object


# --- Alta de la oferta ----------------------------------------------------------------------


def register_offer(user, procedure, *, bidder, channel=Channel.SCREEN):
    """Da de alta la oferta de `bidder` en `procedure`. Lanza `RoleRejected` sin rol de la
    Comisión y `OfferRefused` si falta el oferente o ya tiene oferta en el procedimiento."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REGISTER_OPERATION,
                            channel=channel)
    bidder = " ".join((bidder or "").split())
    detail = {"procedure": procedure.pk}
    try:
        if not bidder:
            raise OfferRefused("Escriba el nombre del oferente.", "bidder", "missing_data")
        if procedure.offers.filter(bidder=bidder).exists():
            raise DuplicateBidder(
                "Ese oferente ya tiene una oferta en este procedimiento.", "bidder")
        with transaction.atomic():
            Procedure.objects.select_for_update().get(pk=procedure.pk)
            last = procedure.offers.aggregate(last=Max("number"))["last"] or 0
            offer = Offer.objects.create(procedure=procedure, number=last + 1,
                                         bidder=bidder, created_by=user)
            audit.record(EventType.OFFER_REGISTER, outcome=Outcome.OK, channel=channel,
                         user=user, detail={**detail, "offer": offer.pk,
                                            "number": offer.number})
    except IntegrityError as error:
        if _violated_constraint(error) != _UNIQUE_BIDDER:
            raise
        refusal = DuplicateBidder(
            "Ese oferente ya tiene una oferta en este procedimiento.", "bidder")
        _record_register_refusal(user, channel, detail, refusal)
        raise refusal from error
    except OfferRefused as error:
        _record_register_refusal(user, channel, detail, error)
        raise
    return offer


def _record_register_refusal(user, channel, detail, error):
    audit.record(EventType.OFFER_REGISTER, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason,
                                    "message": str(error)})


def _violated_constraint(error):
    cause = error.__cause__
    return getattr(getattr(cause, "diag", None), "constraint_name", None) or ""


# --- Carga del documento ----------------------------------------------------------------------


# Formatos que se cargan, con el valor que se guarda en `Document.file_format`. El original
# se guarda tal cual; fotos y Word se convierten a PDF solo para leerlos (`reading.py`).
LOADABLE_FORMATS = {reading_tools.FORMAT_PDF: FileFormat.PDF,
                    reading_tools.FORMAT_JPG: FileFormat.JPG,
                    reading_tools.FORMAT_PNG: FileFormat.PNG,
                    reading_tools.FORMAT_DOCX: FileFormat.DOCX}


def _check(file_name, data):
    """Comprueba los datos y devuelve el formato del archivo (por su contenido, no por el
    nombre): PDF, Word, o foto JPG o PNG que se abre."""
    if not data or not (file_name or "").strip():
        raise OfferRefused("Elija el archivo del documento.", "file", "missing_data")
    detected = reading_tools.detect_upload_format(data)
    if detected not in LOADABLE_FORMATS:
        raise OfferRefused("El archivo no es un PDF, un documento de Word (.docx) ni una foto JPG o PNG: no se cargó.",
                           "file", "unsupported_format")
    if detected in (reading_tools.FORMAT_JPG, reading_tools.FORMAT_PNG):
        try:
            detected = reading_tools.check_image(data)
        except reading_tools.UnreadableFile as error:
            raise OfferRefused(f"{error} No se cargó.", "file", "unreadable_file") from error
    return LOADABLE_FORMATS[detected].value


def _duplicate(offer, sha256):
    loaded = offer.documents.filter(file_sha256=sha256).order_by("id").first()
    if loaded is None:
        return None
    return DuplicateFile(
        f"Ese archivo ya está cargado en esta oferta, como «{loaded.title}» "
        f"({loaded.file_name}). No se cargó de nuevo.", loaded.pk)


def _record_load_refusal(user, channel, detail, error):
    detail = {**detail, "reason": error.reason, "message": str(error)}
    if isinstance(error, DuplicateFile):
        detail["loaded_document"] = error.loaded_document
    audit.record(EventType.OFFER_LOAD, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail=detail)


def load_document(user, offer, *, data, file_name, title="", channel=Channel.SCREEN):
    """Carga el archivo `data` (sus bytes, con su nombre `file_name`) como documento de
    `offer` y encola su lectura. Ver el módulo.

    Lanza `RoleRejected` sin rol de la Comisión, `DuplicateFile` si el archivo ya está
    cargado en la oferta y `OfferRefused` con un dato que falta o un formato que no se
    lee. En esos casos no se guarda nada salvo el hecho que lo registra."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=LOAD_OPERATION,
                            channel=channel)
    data = bytes(data or b"")
    sha256 = hashlib.sha256(data).hexdigest()
    title = (title or "").strip() or _title_from(file_name)
    detail = {"procedure": offer.procedure_id, "offer": offer.pk, "title": title,
              "file": {"name": file_name, "format": None, "size": len(data),
                       "sha256": sha256}}
    try:
        file_format = _check(file_name, data)
        detail["file"]["format"] = file_format
        duplicate = _duplicate(offer, sha256)
        if duplicate is not None:
            raise duplicate
        with transaction.atomic():
            document = Document.objects.create(
                offer=offer, title=title, file_name=file_name, file_format=file_format,
                file_size=len(data), file_sha256=sha256, loaded_by=user)
            DocumentFile.objects.create(document=document, content=data)
            job = jobs.enqueue(JobKind.READ_OFFER_DOCUMENT, procedure=offer.procedure,
                               requested_by=user, target_id=document.pk)
            event = audit.record(
                EventType.OFFER_LOAD, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "document": document.pk, "job": job.pk})
    except IntegrityError as error:
        # Otra carga del mismo archivo se confirmó entre el control y el alta.
        if _violated_constraint(error) != _UNIQUE_FILE:
            raise
        refusal = _duplicate(offer, sha256)
        if refusal is None:
            raise
        _record_load_refusal(user, channel, detail, refusal)
        raise refusal from error
    except OfferRefused as error:
        _record_load_refusal(user, channel, detail, error)
        raise
    return Loaded(document=document, job=job, event=event)


def _title_from(file_name):
    name = (file_name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return name.rsplit(".", 1)[0] if "." in name else name


# --- Clasificación del tipo de documento ---------------------------------------------------------

# Reglas por palabras del nombre del archivo y del comienzo del texto, en este orden. Solo
# sirven para clasificar (dato); nunca excluyen un documento de la búsqueda (plan 008).
KIND_RULES = (
    (DocumentKind.GARANTIA, ("poliza", "seguro de caucion", "garantia de mantenimiento",
                             "garantia de oferta", "garantia de cumplimiento", "pagare")),
    (DocumentKind.ECONOMICA, ("propuesta economica", "oferta economica", "planilla de cotizacion",
                              "planilla de precios", "cotizacion", "precio unitario")),
    # Un documento técnico de verdad (especificaciones firmadas, folletos, hojas técnicas),
    # no una tabla de renglones con precios (T-130, decisión del Coordinador).
    (DocumentKind.TECNICA, ("especificaciones tecnicas", "especificacion tecnica",
                            "documentacion tecnica", "ficha tecnica", "fichas tecnicas",
                            "hoja tecnica", "hojas tecnicas", "hoja de datos", "datasheet",
                            "memoria tecnica", "folleto", "brochure", "catalogo")),
)
_HEAD_CHARS = 1500


def _plain(text):
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return re.sub(r"[\s_\-]+", " ",
                  "".join(c for c in decomposed if unicodedata.category(c) != "Mn"))


# Raíces del encabezado de un documento técnico (T-135): una hoja técnica no siempre trae una
# frase de la lista, y el OCR cambia letras ("espec1ficaciones"). Una palabra del nombre o
# del encabezado (primeros `_TITLE_CHARS` caracteres) que empieza como la raíz, con una
# letra de diferencia como máximo, la cuenta.
_TECHNICAL_ROOTS = ("tecnic", "especif")
_TITLE_CHARS = 400


def _close(prefix, root):
    """Las dos cadenas (del mismo largo) difieren en una letra a lo sumo."""
    return len(prefix) == len(root) and sum(a != b for a, b in zip(prefix, root)) <= 1


def _has_technical_root(source):
    for word in re.findall(r"\w+", source):
        for root in _TECHNICAL_ROOTS:
            if len(word) >= len(root) and _close(word[:len(root)], root):
                return True
    return False


def classify_kind(file_name, text):
    """El tipo del documento por reglas sobre su nombre y el comienzo de su texto; vacío
    si ninguna regla alcanza."""
    for source in (_plain(file_name), _plain((text or "")[:_HEAD_CHARS])):
        for kind, words in KIND_RULES:
            if any(word in source for word in words):
                return kind.value
    for source in (_plain(file_name), _plain((text or "")[:_TITLE_CHARS])):
        if _has_technical_root(source):
            return DocumentKind.TECNICA.value
    return ""


# --- Lectura en segundo plano -------------------------------------------------------------------


def _page_entries(document, pages, statuses):
    return [{"document": document.pk, "title": document.title, "page": page.number,
             "status": page.status,
             "confidence": None if page.confidence is None else round(page.confidence, 2)}
            for page in pages if page.status in statuses]


def read_report(document, reading, specs, second_attempt=()):
    """El informe de una lectura: páginas por estado y origen, páginas no leídas y de baja
    confianza (REQ-038), páginas en blanco y páginas sin texto que no están en ninguna
    lista (que no debería haber)."""
    pages = reading.pages
    with_passages = {spec.page for spec in specs}
    by_status, by_origin = {}, {}
    for page in pages:
        by_status[page.status] = by_status.get(page.status, 0) + 1
        origin = page.origin or "sin_texto"
        by_origin[origin] = by_origin.get(origin, 0) + 1
    unlisted = [page.number for page in pages
                if page.number not in with_passages
                and page.status not in UNREAD_STATUSES + (PAGE_BLANK,)]
    return {
        "pages": len(pages),
        "pages_by_status": by_status,
        "pages_by_origin": by_origin,
        "unread": _page_entries(document, pages, UNREAD_STATUSES),
        "low_confidence": _page_entries(document, pages, (PAGE_DOUBTFUL,)),
        "blank": [page.number for page in pages if page.status == PAGE_BLANK],
        "without_text_unlisted": unlisted,
        "passages": len(specs),
        # Páginas que se leyeron por segunda vez con la imagen preparada (ADR-0028), con la
        # lectura que se conservó (`primera` o `segunda`).
        "second_attempt": list(second_attempt),
    }


def _embedding_info():
    return {"model": settings.EMBEDDINGS_MODEL, "file": settings.EMBEDDINGS_MODEL_FILE,
            "sha256": settings.EMBEDDINGS_MODEL_SHA256}


def _vectors(specs):
    batch = settings.OFFERS_EMBED_BATCH
    vectors = []
    for index in range(0, len(specs), batch):
        vectors.extend(embeddings.embed([spec.text for spec in specs[index:index + batch]]))
    return vectors


def run_read_document(job):
    """Lee el documento del pedido `job` y guarda su lectura, sus pasajes y su informe.
    Ver el módulo. Cualquier falla deja el hecho `offer_read` fallido y se vuelve a
    lanzar."""
    detail = {"procedure": job.procedure_id, "job": job.pk, "document": job.target_id}
    try:
        document = Document.objects.select_related("offer").get(pk=job.target_id)
        if document.offer.procedure_id != job.procedure_id:
            raise ValueError("El documento del pedido no es de una oferta del procedimiento "
                             "del pedido.")
        detail["offer"] = document.offer_id
        detail["file_sha256"] = document.file_sha256
        data = bytes(DocumentFile.objects.get(document=document).content)
        if hashlib.sha256(data).hexdigest() != document.file_sha256:
            raise OriginalChanged(
                "El original guardado no coincide con la huella con que se cargó: no se "
                "leyó.")
        pdf = reading_tools.to_pdf(data, document.file_format)
        reading, attempts = reading_tools.read_with_second_attempt(pdf)
        canonical = build_canonical_text(reading)
        specs = passage_rules.build_passages(canonical)
        vectors = _vectors(specs)
        canonical_sha256 = hashlib.sha256(canonical.text.encode("utf-8")).hexdigest()
        tool_versions = {**reading.tool_versions, "embeddings": _embedding_info()}
        report = read_report(document, reading, specs, attempts)
        kind = classify_kind(document.file_name, canonical.text)

        with transaction.atomic():
            Document.objects.select_for_update().get(pk=document.pk)
            last = document.readings.aggregate(last=Max("sequence"))["last"] or 0
            saved = Reading.objects.create(
                document=document, sequence=last + 1, pages=reading.as_json(),
                canonical_text=canonical.text, canonical_sha256=canonical_sha256,
                tool_versions=tool_versions, report=report, job=job)
            Passage.objects.bulk_create(
                Passage(reading=saved, order=spec.order, key=spec.key, page=spec.page,
                        char_start=spec.char_start, char_end=spec.char_end, text=spec.text,
                        text_origin=spec.text_origin,
                        ocr_confidence_min=spec.ocr_confidence_min,
                        ocr_confidence_avg=spec.ocr_confidence_avg, embedding=vector)
                for spec, vector in zip(specs, vectors, strict=True))
            if kind and document.kind != kind:
                document.kind = kind
                document.save(update_fields=["kind"])
            audit.record(
                EventType.OFFER_READ, outcome=Outcome.OK, channel=Channel.COMMAND,
                user=job.requested_by,
                detail={**detail, "reading": saved.pk, "sequence": saved.sequence,
                        "canonical_sha256": canonical_sha256, "tool_versions": tool_versions,
                        "kind": kind, **report})
    except Exception as error:
        audit.record(EventType.OFFER_READ, outcome=Outcome.FAILED, channel=Channel.COMMAND,
                     user=job.requested_by,
                     detail={**detail, "error": f"{type(error).__name__}: {error}"})
        raise
    return saved


# --- Páginas --------------------------------------------------------------------------------------


def _state(job, reading):
    if job is None or job.status == JobStatus.DONE:
        return STATE_READ if reading is not None else STATE_QUEUED
    return {JobStatus.QUEUED: STATE_QUEUED, JobStatus.RUNNING: STATE_RUNNING,
            JobStatus.FAILED: STATE_FAILED}[job.status]


def _read_job(document):
    return (Job.objects.filter(kind=JobKind.READ_OFFER_DOCUMENT, target_id=document.pk)
            .order_by("-requested_at", "-id").first())


def document_row(document):
    """El estado de lectura de un documento y sus páginas a revisar."""
    job = _read_job(document)
    reading = document.readings.order_by("-sequence").first()
    unread = reading.report.get("unread", []) if reading is not None else []
    low = reading.report.get("low_confidence", []) if reading is not None else []
    return DocumentRow(document=document, state=_state(job, reading), job=job,
                       reading=reading, unread=unread, low_confidence=low)


def latest_readings(offer):
    """La última lectura de cada documento de la oferta que ya se leyó."""
    readings = []
    for document in offer.documents.order_by("loaded_at", "id"):
        reading = document.readings.order_by("-sequence").first()
        if reading is not None:
            readings.append(reading)
    return readings


def offers_page(user, procedure_id, *, channel=Channel.SCREEN):
    """El procedimiento y sus ofertas con el estado de lectura y de ficha. Lanza
    `RoleRejected` sin rol de la Comisión y `Procedure.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=LIST_OPERATION,
                            channel=channel)
    procedure = Procedure.objects.get(pk=procedure_id)
    rows = []
    for offer in procedure.offers.order_by("number"):
        doc_rows = [document_row(d) for d in offer.documents.order_by("loaded_at", "id")]
        rows.append(OfferRow(
            offer=offer, documents=len(doc_rows),
            read=sum(1 for r in doc_rows if r.state == STATE_READ),
            failed=sum(1 for r in doc_rows if r.state == STATE_FAILED),
            sheet=offer.sheets.order_by("-number").first()))
    return procedure, rows


def offer_page(user, offer_id, *, channel=Channel.SCREEN):
    """La oferta con sus documentos, las páginas que hay que revisar a mano y sus fichas.
    Lanza `RoleRejected` sin rol de la Comisión y `Offer.DoesNotExist` si no existe."""
    from evaluon.tenders.services.validation import latest_validated

    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    offer = Offer.objects.select_related("procedure").get(pk=offer_id)
    rows = [document_row(d) for d in offer.documents.order_by("loaded_at", "id")]
    sheet_job = (Job.objects.filter(kind=JobKind.BUILD_SHEET, target_id=offer.pk)
                 .order_by("-requested_at", "-id").first())
    return OfferPage(
        offer=offer, documents=rows,
        unread=[e for r in rows for e in r.unread],
        low_confidence=[e for r in rows for e in r.low_confidence],
        sheets=list(offer.sheets.order_by("-number")),
        sheet_job=sheet_job, validated_matrix=latest_validated(offer.procedure))


def original_file(user, document_id, *, channel=Channel.SCREEN):
    """El original guardado de un documento (`DocumentFile`, con su documento). Lanza
    `RoleRejected` sin rol de la Comisión y `DocumentFile.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=ORIGINAL_OPERATION,
                            channel=channel)
    return DocumentFile.objects.select_related("document").get(document_id=document_id)


# --- Mantenimiento de lo ya cargado (T-136) ----------------------------------------------------

RECLASSIFY_OPERATION = "evaluon.offers.services.offers.reclassify_documents"
REBUILD_OPERATION = "evaluon.offers.services.offers.rebuild_passages"


def reclassify_documents(user, procedure, *, channel=Channel.COMMAND):
    """Vuelve a aplicar `classify_kind` a los documentos ya cargados del procedimiento, sobre
    su nombre y el texto canónico de su última lectura. No lee ni usa OCR ni GPU. Si ninguna
    regla alcanza, el tipo que ya tenía no se toca (igual que al leer). Cada documento cuyo
    tipo cambia deja el hecho `offer_read` con `action: reclassify`, el tipo anterior y el
    nuevo (P6). Devuelve la lista `(documento, tipo anterior, tipo nuevo)` de los que
    cambiaron."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=RECLASSIFY_OPERATION,
                            channel=channel)
    changed = []
    documents = Document.objects.filter(offer__procedure=procedure).select_related("offer")
    for document in documents.order_by("offer__number", "loaded_at", "id"):
        reading = document.readings.order_by("-sequence").first()
        if reading is None:
            continue
        kind = classify_kind(document.file_name, reading.canonical_text)
        if not kind or kind == document.kind:
            continue
        with transaction.atomic():
            before = document.kind
            document.kind = kind
            document.save(update_fields=["kind"])
            audit.record(
                EventType.OFFER_READ, outcome=Outcome.OK, channel=channel, user=user,
                detail={"action": "reclassify", "procedure": procedure.pk,
                        "offer": document.offer_id, "document": document.pk,
                        "reading": reading.pk, "kind_before": before, "kind": kind})
        changed.append((document, before, kind))
    return changed


def _passage_shape(items):
    return [(i.key, i.page, i.char_start, i.char_end, i.text) for i in items]


def rebuild_passages(user, document, *, channel=Channel.COMMAND):
    """Arma de nuevo los pasajes de `document` desde las páginas de su última lectura, con
    las reglas de partición de hoy, sin OCR. Si salen otros pasajes, guarda una lectura nueva
    (la anterior queda: las lecturas son de solo agregado) con las mismas páginas, su texto
    canónico, sus pasajes con vectores y su informe, y deja el hecho `offer_read` con
    `action: rebuild_passages`. Devuelve la lectura nueva, o `None` si el particionado no
    cambia nada."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REBUILD_OPERATION,
                            channel=channel)
    detail = {"action": "rebuild_passages", "procedure": document.offer.procedure_id,
              "offer": document.offer_id, "document": document.pk}
    try:
        previous = document.readings.order_by("-sequence").first()
        if previous is None:
            raise ValueError("El documento todavía no tiene una lectura.")
        detail["from_reading"] = previous.pk
        reading = reading_tools.rebuild_reading(previous.pages)
        canonical = build_canonical_text(reading)
        specs = passage_rules.build_passages(canonical)
        if (canonical.text == previous.canonical_text
                and _passage_shape(specs) == _passage_shape(previous.passages.order_by("order"))):
            return None
        vectors = _vectors(specs)
        canonical_sha256 = hashlib.sha256(canonical.text.encode("utf-8")).hexdigest()
        tool_versions = {**previous.tool_versions, "embeddings": _embedding_info(),
                         "rebuilt_from_reading": previous.pk}
        report = read_report(document, reading, specs,
                             previous.report.get("second_attempt", []))
        with transaction.atomic():
            Document.objects.select_for_update().get(pk=document.pk)
            last = document.readings.aggregate(last=Max("sequence"))["last"] or 0
            saved = Reading.objects.create(
                document=document, sequence=last + 1, pages=previous.pages,
                canonical_text=canonical.text, canonical_sha256=canonical_sha256,
                tool_versions=tool_versions, report=report, job=None)
            Passage.objects.bulk_create(
                Passage(reading=saved, order=spec.order, key=spec.key, page=spec.page,
                        char_start=spec.char_start, char_end=spec.char_end, text=spec.text,
                        text_origin=spec.text_origin,
                        ocr_confidence_min=spec.ocr_confidence_min,
                        ocr_confidence_avg=spec.ocr_confidence_avg, embedding=vector)
                for spec, vector in zip(specs, vectors, strict=True))
            audit.record(
                EventType.OFFER_READ, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "reading": saved.pk, "sequence": saved.sequence,
                        "canonical_sha256": canonical_sha256, "tool_versions": tool_versions,
                        "passages_before": previous.passages.count(),
                        "passages": len(specs)})
    except Exception as error:
        audit.record(EventType.OFFER_READ, outcome=Outcome.FAILED, channel=channel,
                     user=user, detail={**detail,
                                        "error": f"{type(error).__name__}: {error}"})
        raise
    return saved
