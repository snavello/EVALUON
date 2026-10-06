"""Lectura con visión de las páginas de lectura dudosa de una oferta (REQ-052, REQ-053, REQ-054;
plan 004, enmienda 2026-10-06, "Lectura con visión"; ADR-0041; T-160).

Antes de evaluar una oferta, el sistema busca en la última lectura de cada documento las
páginas de lectura dudosa, por un criterio objetivo que ya está en el informe de la lectura
(`offers.services.offers.read_report`), sin criterio del modelo:

- las `dudosa` (`low_confidence`), las ilegibles y casi sin texto (`unread`) y las de
  `without_text_unlisted`;
- toda página de un documento en formato imagen (foto JPG o PNG): el reconocimiento de texto
  falla ahí.

Hasta `ASSESSMENT_VISION_MAX_PAGES` páginas por oferta (con las ya intentadas antes); las que
pasan del tope siguen como están y quedan contadas. Una página legible de un documento con
texto nunca se manda a visión.

Cada página va en un pedido aparte al motor de lotes (`generation_batch`, con su proyector de
imagen), con la imagen dibujada con pypdfium2 y la instrucción `vision-v1`: el modelo
transcribe, no decide. La transcripción se guarda como una **lectura nueva** del documento
(`sequence` siguiente; las lecturas son de solo inserción: la anterior no se toca) con las
páginas de la lectura anterior tal cual y, en las páginas que se leyeron por visión, las líneas
de la transcripción con origen `vision`; sus pasajes salen con las mismas reglas de partición y
su texto canónico y su huella son propios. Una transcripción vacía o con más de
`ASSESSMENT_VISION_MAX_ILLEGIBLE_SHARE` de `[ilegible]` no cuenta como lectura: la página sigue
como estaba ("no se pudo leer" si era ilegible).

La cita sobre una página leída por visión es igual a cualquier otra: el sistema la ubica en el
texto canónico de esta lectura (ADR-0038). Es literal respecto de la transcripción, no del
original: por eso la pantalla la rotula "leída por visión" y muestra la imagen de la página
(P3).

Registro (P6, P8): el informe de la lectura nueva (`report["vision"]`) guarda modelo y huella,
proyector y su huella, compilación, parámetros, versión de la instrucción y, por página, el
motivo, la huella de la imagen, el pedido (sin los bytes de la imagen), la salida cruda, los
tokens, los tiempos y el resultado. El hecho `offer_read` sale con la acción `vision`.

Idempotente: una página ya intentada por visión (leída o descartada) no se repite. Un error del
motor (sin proyector, caído, demora agotada) no rompe la evaluación: la página queda como
estaba, el error se registra en el resumen y no se siguen pidiendo páginas. Todo corre en el
equipo, sin servicios externos (P4).
"""

import base64
import copy
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
from django.conf import settings
from django.db import transaction
from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai import AIServiceError, generation
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.reading import PAGE_READ, Line, ocr
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers import passages as passage_rules
from evaluon.offers import reading as reading_tools
from evaluon.offers.models import Document, DocumentFile, Passage, Reading
from evaluon.offers.services import offers as offers_service

ORIGIN_VISION = "vision"
OPERATION = "evaluon.offers.vision.read_offer_for"

# Motivos por los que una página va a visión.
REASON_UNREAD = "unread"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_WITHOUT_TEXT = "without_text_unlisted"
REASON_IMAGE_FORMAT = "image_format"

# Resultado de una página.
OUTCOME_READ = "read"
OUTCOME_EMPTY = "empty"
OUTCOME_TOO_ILLEGIBLE = "too_illegible"
OUTCOME_INVALID = "invalid_output"
OUTCOME_ERROR = "error"
# Las páginas con estos resultados ya se intentaron y no se repiten; un error técnico sí.
ATTEMPTED = (OUTCOME_READ, OUTCOME_EMPTY, OUTCOME_TOO_ILLEGIBLE, OUTCOME_INVALID)

ILLEGIBLE = "[ilegible]"
IMAGE_FORMATS = ("jpg", "png")
# Resolución con que se muestra la página junto a la cita, en puntos por pulgada.
DISPLAY_DPI = 100

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "assessment" / "prompts"
SCHEMA = {
    "type": "object",
    "properties": {"transcripcion": {"type": "string"}},
    "required": ["transcripcion"],
    "additionalProperties": False,
}
USER_TEXT = "Transcribí el texto de esta página."


def load_prompt():
    """El texto de la instrucción de la versión que fija `ASSESSMENT_VISION_PROMPT_VERSION`."""
    version = settings.ASSESSMENT_VISION_PROMPT_VERSION
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def enabled():
    """Hay visión si el tope es mayor que cero y el motor de lotes lleva proyector de imagen."""
    return settings.ASSESSMENT_VISION_MAX_PAGES > 0 and bool(
        settings.GENERATION_BATCH_MMPROJ_FILE)


# --- Qué páginas ------------------------------------------------------------------------------


def vision_entries(reading):
    """Los registros de visión que trae el informe de `reading` (uno por página intentada)."""
    return list((reading.report or {}).get("vision", {}).get("pages", []))


def attempted_pages(reading):
    """Páginas que ya se intentaron por visión (leídas o descartadas)."""
    return {e["page"] for e in vision_entries(reading) if e.get("outcome") in ATTEMPTED}


def vision_pages(reading):
    """Páginas de `reading` que se leyeron por visión (su texto es una transcripción)."""
    return {e["page"] for e in vision_entries(reading) if e.get("outcome") == OUTCOME_READ}


def candidate_pages(document, reading):
    """Las páginas de lectura dudosa de la última lectura de `document`, que todavía no se
    intentaron por visión: `[{"page", "reason", "reasons", "status", "confidence"}]` por
    número de página."""
    report = reading.report or {}
    found = {}

    def add(page, reason, status=None, confidence=None):
        entry = found.setdefault(page, {"page": page, "reasons": [], "status": status,
                                        "confidence": confidence})
        entry["reasons"].append(reason)
        if entry["status"] is None:
            entry["status"], entry["confidence"] = status, confidence

    for item in report.get("unread", []):
        add(item["page"], REASON_UNREAD, item.get("status"), item.get("confidence"))
    for item in report.get("low_confidence", []):
        add(item["page"], REASON_LOW_CONFIDENCE, item.get("status"), item.get("confidence"))
    for page in report.get("without_text_unlisted", []):
        add(page, REASON_WITHOUT_TEXT)
    if document.file_format in IMAGE_FORMATS:
        for page in range(1, report.get("pages", 0) + 1):
            add(page, REASON_IMAGE_FORMAT)
    done = attempted_pages(reading)
    chosen = [found[p] for p in sorted(found) if p not in done]
    for entry in chosen:
        entry["reason"] = entry["reasons"][0]
    return chosen


# --- Imagen y pedido --------------------------------------------------------------------------


def render_image(pdf_bytes, page, dpi=None, max_side=None, fmt="PNG"):
    """La página `page` (desde 1) del PDF dibujada con pypdfium2: `(bytes, ancho, alto)`. El
    lado mayor no pasa de `max_side` puntos."""
    dpi = dpi or settings.ASSESSMENT_VISION_DPI
    max_side = max_side or settings.ASSESSMENT_VISION_MAX_SIDE
    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        if not 1 <= page <= len(pdf):
            raise ValueError(f"El documento no tiene la página {page}.")
        image = pdf[page - 1].render(scale=dpi / 72).to_pil().convert("RGB")
    finally:
        pdf.close()
    if max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize((max(1, round(image.width * ratio)),
                              max(1, round(image.height * ratio))))
    out = io.BytesIO()
    image.save(out, format=fmt)
    return out.getvalue(), image.width, image.height


def build_messages(png, system=None):
    """Los mensajes del pedido de transcripción de una página: la instrucción y la imagen."""
    url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return [{"role": "system", "content": system or load_prompt()},
            {"role": "user", "content": [
                {"type": "text", "text": USER_TEXT},
                {"type": "image_url", "image_url": {"url": url}}]}]


def _without_image(request, sha256):
    """El pedido tal como se envió, con el lugar de la imagen en vez de sus bytes (la imagen se
    puede volver a dibujar del original; su huella queda al lado)."""
    recorded = copy.deepcopy(request)
    for message in recorded.get("messages", []):
        if isinstance(message.get("content"), list):
            for part in message["content"]:
                if part.get("type") == "image_url":
                    part["image_url"] = {"url": f"[imagen png sha256:{sha256}]"}
    return recorded


def illegible_share(text):
    """Proporción de `[ilegible]` en la transcripción: marcas sobre marcas más palabras."""
    marks = text.count(ILLEGIBLE)
    words = len(text.replace(ILLEGIBLE, " ").split())
    return marks / (marks + words) if marks else 0.0


def parse_transcription(content):
    """El texto de la salida del modelo; `None` si no tiene la forma pedida."""
    try:
        data = json.loads(content)
        text = data["transcripcion"]
    except (ValueError, KeyError, TypeError):
        return None
    return text if isinstance(text, str) else None


def transcribe_page(pdf_bytes, page, *, dpi=None, clock=time.monotonic):
    """Pide la transcripción de la página `page` y devuelve su registro (ver el módulo): trae
    `outcome` y, si se leyó, `text`. Un error del motor lanza `AIServiceError`."""
    dpi = dpi or settings.ASSESSMENT_VISION_DPI
    png, width, height = render_image(pdf_bytes, page, dpi=dpi)
    sha256 = hashlib.sha256(png).hexdigest()
    started = clock()
    result = generation.generate(
        build_messages(png), SCHEMA, max_tokens=settings.ASSESSMENT_VISION_MAX_OUTPUT_TOKENS,
        base_url=settings.GENERATION_BATCH_URL,
        timeout=settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS)
    entry = {"page": page, "image_sha256": sha256, "image_size": [width, height], "dpi": dpi,
             "request": _without_image(result.request, sha256), "raw_output": result.content,
             "finish_reason": result.finish_reason, "prompt_tokens": result.prompt_tokens,
             "completion_tokens": result.completion_tokens,
             "seconds": round(clock() - started, 3)}
    text = parse_transcription(result.content)
    if text is None:
        entry["outcome"] = OUTCOME_INVALID
        return entry
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    share = illegible_share(text)
    entry.update(text=text, chars=len(text), illegible_share=round(share, 4))
    if not text.replace(ILLEGIBLE, "").strip():
        entry["outcome"] = OUTCOME_EMPTY if not text else OUTCOME_TOO_ILLEGIBLE
    elif share > settings.ASSESSMENT_VISION_MAX_ILLEGIBLE_SHARE:
        entry["outcome"] = OUTCOME_TOO_ILLEGIBLE
    else:
        entry["outcome"] = OUTCOME_READ
    return entry


# --- Lectura nueva ---------------------------------------------------------------------------


def _models_used():
    return {"model": settings.GENERATION_BATCH_MODEL,
            "file": settings.GENERATION_BATCH_MODEL_FILE,
            "sha256": settings.GENERATION_BATCH_MODEL_SHA256,
            "mmproj_file": settings.GENERATION_BATCH_MMPROJ_FILE,
            "mmproj_sha256": settings.GENERATION_BATCH_MMPROJ_SHA256,
            "engine_build": settings.GENERATION_ENGINE_BUILD,
            "context_tokens": settings.GENERATION_BATCH_CONTEXT_TOKENS}


def _parameters():
    return {"dpi": settings.ASSESSMENT_VISION_DPI,
            "max_side": settings.ASSESSMENT_VISION_MAX_SIDE,
            "image_tokens": settings.ASSESSMENT_VISION_IMAGE_TOKENS,
            "max_output_tokens": settings.ASSESSMENT_VISION_MAX_OUTPUT_TOKENS,
            "max_illegible_share": settings.ASSESSMENT_VISION_MAX_ILLEGIBLE_SHARE,
            "max_pages": settings.ASSESSMENT_VISION_MAX_PAGES,
            "temperature": settings.GENERATION_TEMPERATURE,
            "seed": settings.GENERATION_SEED,
            "thinking": settings.GENERATION_THINKING,
            "request_timeout_seconds": settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS}


def _transcribed_page(page, text):
    """La página con la transcripción en lugar de sus líneas: una línea del texto por línea,
    sin posición y con origen `vision`."""
    page.lines = [Line(text=line, x0=None, top=None, x1=None, bottom=None,
                       origin=ORIGIN_VISION)
                  for line in text.split("\n") if line.strip()]
    page.status = PAGE_READ
    page.origin = ORIGIN_VISION
    page.confidence = None


def _compact(entries):
    """Los registros sin el pedido ni la salida cruda ni el texto (van en el informe de la
    lectura; el hecho de auditoría lleva lo demás)."""
    return [{k: v for k, v in e.items() if k not in ("request", "raw_output", "text")}
            for e in entries]


def save_reading(document, previous, entries, *, user, channel, job=None, over_limit=0):
    """Guarda la lectura nueva de `document` con las páginas de visión de `entries` (registros
    de `transcribe_page` con su motivo) sobre `previous`. Devuelve la lectura, o `None` si no
    hay ninguna página intentada que registrar."""
    entries = [e for e in entries if e["outcome"] in ATTEMPTED]
    if not entries:
        return None
    detail = {"action": "vision", "procedure": document.offer.procedure_id,
              "offer": document.offer_id, "document": document.pk,
              "from_reading": previous.pk}
    try:
        reading = reading_tools.rebuild_reading(previous.pages)
        by_number = {p.number: p for p in reading.pages}
        for entry in entries:
            if entry["outcome"] == OUTCOME_READ:
                _transcribed_page(by_number[entry["page"]], entry["text"])
        canonical = build_canonical_text(reading)
        specs = passage_rules.build_passages(canonical)
        vectors = offers_service._vectors(specs)
        canonical_sha256 = hashlib.sha256(canonical.text.encode("utf-8")).hexdigest()
        report = offers_service.read_report(document, reading, specs,
                                            previous.report.get("second_attempt", []))
        with transaction.atomic():
            Document.objects.select_for_update().get(pk=document.pk)
            last = document.readings.aggregate(last=Max("sequence"))["last"] or 0
            sequence = last + 1
            new = [{**{k: v for k, v in e.items() if k != "text"}, "sequence": sequence}
                   for e in entries]
            report["vision"] = {
                "models": _models_used(), "parameters": _parameters(),
                "prompt_version": settings.ASSESSMENT_VISION_PROMPT_VERSION,
                "from_reading": previous.pk, "over_limit": over_limit,
                "pages": [*vision_entries(previous), *new]}
            tool_versions = {**previous.tool_versions, "vision": _models_used()}
            saved = Reading.objects.create(
                document=document, sequence=sequence, pages=reading.as_json(),
                canonical_text=canonical.text, canonical_sha256=canonical_sha256,
                tool_versions=tool_versions, report=report, job=job)
            Passage.objects.bulk_create(
                Passage(reading=saved, order=spec.order, key=spec.key, page=spec.page,
                        char_start=spec.char_start, char_end=spec.char_end, text=spec.text,
                        text_origin=spec.text_origin,
                        ocr_confidence_min=spec.ocr_confidence_min,
                        ocr_confidence_avg=spec.ocr_confidence_avg, embedding=vector)
                for spec, vector in zip(specs, vectors, strict=True))
            audit.record(
                EventType.OFFER_READ, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "reading": saved.pk, "sequence": sequence,
                        "canonical_sha256": canonical_sha256, "tool_versions": tool_versions,
                        "vision": {**{k: v for k, v in report["vision"].items()
                                      if k != "pages"}, "pages": _compact(new)},
                        "pages_read": [e["page"] for e in entries
                                       if e["outcome"] == OUTCOME_READ],
                        "passages": len(specs)})
    except Exception as error:
        audit.record(EventType.OFFER_READ, outcome=Outcome.FAILED, channel=channel, user=user,
                     detail={**detail, "error": f"{type(error).__name__}: {error}"})
        raise
    return saved


@dataclass
class VisionSummary:
    """Lo que hizo la lectura con visión de una oferta, para el registro de la evaluación."""

    disabled: bool = False
    candidates: int = 0
    attempted: int = 0
    read: int = 0
    discarded: int = 0
    errors: list = field(default_factory=list)
    over_limit: int = 0
    seconds: float = 0.0
    readings: list = field(default_factory=list)

    def record(self):
        return {"disabled": self.disabled, "candidates": self.candidates,
                "attempted": self.attempted, "read": self.read, "discarded": self.discarded,
                "errors": list(self.errors), "over_limit": self.over_limit,
                "seconds": round(self.seconds, 3), "readings": [r.pk for r in self.readings]}


def _original_pdf(document):
    data = bytes(DocumentFile.objects.get(document=document).content)
    if hashlib.sha256(data).hexdigest() != document.file_sha256:
        raise offers_service.OriginalChanged(
            "El original guardado no coincide con la huella con que se cargó.")
    return reading_tools.to_pdf(data, document.file_format)


def read_offer(offer, *, user, channel=Channel.COMMAND, job=None, clock=time.monotonic):
    """Pide la lectura con visión de las páginas dudosas de `offer` y guarda una lectura nueva de
    cada documento que la necesite. Ver el módulo. No lanza por errores del motor: los deja en
    `errors` del resumen."""
    summary = VisionSummary()
    if not enabled():
        summary.disabled = True
        return summary
    started = clock()
    plan, used = [], 0
    for document in offer.documents.select_related("offer").order_by("loaded_at", "id"):
        previous = document.readings.order_by("-sequence").first()
        if previous is None:
            continue
        used += len(attempted_pages(previous))
        plan.append((document, previous, candidate_pages(document, previous)))
    summary.candidates = sum(len(c) for _, _, c in plan)
    room = max(settings.ASSESSMENT_VISION_MAX_PAGES - used, 0)
    stopped = False
    for document, previous, candidates in plan:
        chosen, over = candidates[:room], candidates[room:]
        room -= len(chosen)
        summary.over_limit += len(over)
        if not chosen or stopped:
            continue
        entries = []
        # Una foto se convierte en un PDF a la resolución de la lectura (300 puntos por
        # pulgada, 1 a 1 con sus píxeles): se dibuja a esa misma, hasta el lado máximo, para no
        # perder la mitad de los píxeles de la foto.
        dpi = ocr.RENDER_DPI if document.file_format in IMAGE_FORMATS else None
        try:
            pdf = _original_pdf(document)
        except Exception as error:  # noqa: BLE001 - el original no se pudo preparar
            summary.errors.append(f"documento {document.pk}: {type(error).__name__}: {error}")
            continue
        for candidate in chosen:
            try:
                entry = transcribe_page(pdf, candidate["page"], dpi=dpi, clock=clock)
            except AIServiceError as error:
                summary.errors.append(
                    f"documento {document.pk}, página {candidate['page']}: "
                    f"{type(error).__name__}: {error}")
                stopped = True
                break
            except Exception as error:  # noqa: BLE001 - la página no se pudo dibujar
                summary.errors.append(
                    f"documento {document.pk}, página {candidate['page']}: "
                    f"{type(error).__name__}: {error}")
                continue
            entry.update(reason=candidate["reason"], reasons=candidate["reasons"],
                         status=candidate["status"], confidence=candidate["confidence"])
            entries.append(entry)
        summary.attempted += len(entries)
        summary.read += sum(1 for e in entries if e["outcome"] == OUTCOME_READ)
        summary.discarded += sum(1 for e in entries if e["outcome"] != OUTCOME_READ)
        try:
            saved = save_reading(document, previous, entries, user=user, channel=channel,
                                 job=job, over_limit=len(over))
        except Exception as error:  # noqa: BLE001 - ya quedó el hecho fallido
            summary.errors.append(f"documento {document.pk}: {type(error).__name__}: {error}")
            summary.read -= sum(1 for e in entries if e["outcome"] == OUTCOME_READ)
            continue
        if saved is not None:
            summary.readings.append(saved)
    summary.seconds = clock() - started
    return summary


def read_offer_for(user, offer, *, channel=Channel.COMMAND):
    """`read_offer` pedida a mano por una persona (comando `leer_con_vision`). Lo hacen el
    operador y el evaluador; sin rol de la Comisión lanza `RoleRejected`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=channel)
    return read_offer(offer, user=user, channel=channel)


def page_image(document, page):
    """La imagen de la página `page` del original de `document`, lista para mostrar en la
    pantalla (bytes JPEG), o `None` si no se puede dibujar."""
    try:
        data, _, _ = render_image(_original_pdf(document), page, dpi=DISPLAY_DPI, fmt="JPEG")
    except Exception:  # noqa: BLE001 - la pantalla sigue sin la imagen; el enlace al original queda
        return None
    return data
