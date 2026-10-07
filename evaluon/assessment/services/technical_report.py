"""Informe técnico del área requirente: subirlo y proponer apto o no apto por renglón (REQ-074 de
la 013; REQ-061 de la 004; ADR-0043; T-190).

Decisiones literales del responsable: «creo que pasa algo similar con el informe tecnico del area
requirente lo mismo para el informe tecnico» (sobre la hoja de compliance); «La parte tecnica ya
te dije que venia del area correspondiente»; «la comision debiera dar el ok de que tiene el
informe tecnico aprobado».

1. `upload_report`: el evaluador sube el informe técnico aprobado del área, por oferta o por
   procedimiento (en ese caso se carga en cada oferta del procedimiento y cada una lo lee y lo
   cruza con su oferente). Queda como documento de la oferta, de tipo `informe_tecnico`, con la
   carga de la 008 (huella, original y lectura en la cola) y un hecho `eval_decision` (P6). El
   informe no es un documento de la oferta para evaluarla: `documents.py` no lo lee en la
   evaluación.
2. Cuando la lectura del informe termina, `after_read` (lo llama la cola, ya cerrado el pedido de
   lectura) **propone** por renglón de la oferta: `apto` o `no_apto` con la cita literal del
   informe, o nada si el informe no trata a ese oferente en ese renglón. El sistema no juzga lo
   técnico: copia lo que el informe dice (P3). Una cita que no se encuentra letra por letra en el
   informe descarta la propuesta de ese renglón. La propuesta queda como hecho `eval_build` con
   `kind = technical_proposal` (P6): modelo, versión de la instrucción, tramos leídos, y por
   renglón el dictamen y la cita ubicada (página, posiciones) o el motivo por el que no se propone.
3. La matriz muestra la propuesta junto al ok técnico y la precarga; **la Comisión confirma o
   corrige** dando el ok (`technical.give_ok`, sin cambios en su regla). La propuesta nunca cambia
   un resultado por sí sola.
4. `request_proposal`: lo mismo a mano, si el modelo no estaba disponible cuando terminó la
   lectura.

Solo el evaluador sube el informe y pide proponer de nuevo (P3). El rol se comprueba antes de todo.
"""

import json
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai import AIServiceError, generation
from evaluon.assessment import citations as citing
from evaluon.assessment import documents, prompting, sizing
from evaluon.assessment.services import technical
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.models import Document, DocumentKind, Offer
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets
from evaluon.tenders.models import Procedure

UPLOAD_OPERATION = "evaluon.assessment.services.technical_report.upload_report"
PROPOSE_OPERATION = "evaluon.assessment.services.technical_report.request_proposal"

PROMPT_VERSION = "informe-tecnico-v1"
SCHEMA_NAME = "informe_tecnico"

APTO = "apto"
NO_APTO = "no_apto"
NO_TRATA = technical.NOT_TREATED
VERDICTS = (APTO, NO_APTO, NO_TRATA)

ITEM_TEXT_CHARS = 300


class ReportRefused(ValueError):
    """No se hizo. `reason` es el motivo que queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


@dataclass
class Uploaded:
    """Lo que dejó subir el informe: un documento por oferta alcanzada y las ofertas que ya lo
    tenían."""

    documents: list
    events: list
    already: list = field(default_factory=list)


def reports_of(offer):
    """Los informes técnicos del área cargados en la oferta, del más viejo al más nuevo."""
    return list(offer.documents.filter(kind=DocumentKind.INFORME_TECNICO)
                .order_by("loaded_at", "id"))


def reading_reports(offer):
    """Los informes de la oferta que todavía se están leyendo (o no se pudieron leer)."""
    return [d for d in reports_of(offer)
            if offers_service.document_row(d).state != offers_service.STATE_READ]


def _offer(offer_id):
    try:
        return Offer.objects.select_related("procedure").get(pk=int(offer_id))
    except (Offer.DoesNotExist, TypeError, ValueError):
        raise ReportRefused("No hay una oferta con ese número.", "offer_not_found")


# --- Subir el informe ------------------------------------------------------------------------


def upload_report(user, *, offer_id=None, procedure_id=None, data, file_name, title="",
                  note="", channel=Channel.SCREEN):
    """El evaluador sube el informe técnico aprobado (`data`, con su nombre `file_name`) de una
    oferta (`offer_id`) o de todo el procedimiento (`procedure_id`: se carga en cada oferta).
    Lanza `ReportRefused` si falta la oferta o el procedimiento no tiene ofertas, y lo de la
    carga de la 008 (`OfferRefused`, `DuplicateFile`) si el archivo no se acepta."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=UPLOAD_OPERATION,
                            channel=channel)
    if offer_id is not None:
        targets = [_offer(offer_id)]
    else:
        try:
            procedure = Procedure.objects.get(pk=int(procedure_id))
        except (Procedure.DoesNotExist, TypeError, ValueError):
            raise ReportRefused("No hay un procedimiento con ese número.",
                                "procedure_not_found")
        targets = list(procedure.offers.order_by("number"))
        if not targets:
            raise ReportRefused("El procedimiento todavía no tiene ofertas donde cargar el "
                                "informe.", "no_offers")
    title = (title or "").strip() or (
        f"Informe técnico · {offers_service._title_from(file_name)}")
    done, events, already = [], [], []
    for offer in targets:
        try:
            loaded = offers_service.load_document(
                user, offer, data=data, file_name=file_name, title=title,
                kind=DocumentKind.INFORME_TECNICO, channel=channel)
        except offers_service.DuplicateFile:
            if len(targets) == 1:
                raise
            already.append(offer)
            continue
        with transaction.atomic():
            event = audit.record(
                EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
                detail={"action": "informe_tecnico", "offer": offer.pk,
                        "procedure": offer.procedure_id, "document": loaded.document.pk,
                        "file_sha256": loaded.document.file_sha256,
                        "load_event": loaded.event.pk,
                        "scope": "oferta" if offer_id is not None else "procedimiento",
                        "note": (note or "").strip()})
        done.append(loaded.document)
        events.append(event)
    if not done:
        raise ReportRefused("Todas las ofertas ya tienen este informe.", "already_loaded")
    return Uploaded(documents=done, events=events, already=already)


# --- Leer el informe y proponer ---------------------------------------------------------------


def _schema(items):
    return {
        "type": "object",
        "properties": {"renglones": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "renglon": {"type": "integer", "enum": sorted(items)},
                "dictamen": {"type": "string", "enum": list(VERDICTS)},
                "cita": {"type": "string"},
                "motivo": {"type": "string"}},
            "required": ["renglon", "dictamen", "cita", "motivo"],
            "additionalProperties": False}}},
        "required": ["renglones"], "additionalProperties": False}


def _item_lines(rows):
    lines = []
    for item, requirement in sorted(rows.items()):
        text = " ".join(sheets.requirement_text(requirement).split())[:ITEM_TEXT_CHARS]
        lines.append(f"Renglón {item}: {text}" if text else f"Renglón {item}")
    return "\n".join(lines)


def _messages(system, offer, rows, text):
    user = "\n\n".join([
        f"[INFORME]\n{text}\n[/INFORME]",
        f"Oferente: {offer.bidder} (oferta {offer.number})",
        f"Renglones del pliego:\n{_item_lines(rows)}",
        "Devolvé un objeto JSON con los campos pedidos."])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _windows(entry):
    """Los tramos del informe que caben en un pedido: `[(texto, primera, última)]`."""
    budget = settings.ASSESSMENT_GROUP_TOKENS
    if entry.tokens <= budget:
        return [(entry.render(), None, None)]
    return [(entry.render(part[0] + 1, part[-1] + 1), part[0] + 1, part[-1] + 1)
            for part in sizing.windows(entry.page_tokens, budget)]


def _parse(content, items):
    """`{renglón: (dictamen, cita, motivo)}` de la salida del modelo, o `None` si no es válida.
    Solo cuentan los renglones pedidos, el primero que aparece de cada uno."""
    try:
        data = json.loads(content)
        entries = data["renglones"]
        parsed = {}
        for entry in entries:
            item, verdict = int(entry["renglon"]), entry["dictamen"]
            if item in items and item not in parsed and verdict in VERDICTS:
                parsed[item] = (verdict, str(entry.get("cita") or ""),
                                str(entry.get("motivo") or ""))
        return parsed
    except (ValueError, KeyError, TypeError):
        return None


def _locate(entry, quote, finder, anomalies):
    """La cita ubicada letra por letra en el informe, o `None`."""
    if not quote.strip():
        anomalies.append({"type": "cita_vacia"})
        return None
    return citing.locate_quote(entry, quote, finder, (), anomalies)


def _read_report(document, offer, rows):
    """Lee el informe para la oferta: `({renglón: entrada}, pasos, anomalías)`. La entrada trae
    `verdict`, `quote`, `page`, posiciones y `motive`, o el `reason` por el que no se propone."""
    entry = documents.read_document(document, generation.count_tokens)
    anomalies = []
    if entry.reading is None:
        return ({i: {"reason": "sin_lectura"} for i in rows}, [], anomalies)
    system = (prompting.PROMPTS_DIR / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
    finder = citing.PageFinder()
    schema = _schema(set(rows))
    candidates = {i: [] for i in rows}  # dictámenes con cita ubicada, por tramo
    misses = {i: set() for i in rows}
    steps = []
    for text, first, last in _windows(entry):
        result = generation.generate(
            _messages(system, offer, rows, text), schema,
            max_tokens=settings.ASSESSMENT_MAX_OUTPUT_TOKENS,
            base_url=settings.GENERATION_BATCH_URL,
            timeout=settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS)
        parsed = _parse(result.content, set(rows))
        steps.append({"pages": [first, last], "prompt_tokens": result.prompt_tokens,
                      "completion_tokens": result.completion_tokens,
                      "valid": parsed is not None})
        if parsed is None:
            anomalies.append({"type": prompting.ANOMALY_INVALID_OUTPUT, "pages": [first, last]})
            continue
        for item, (verdict, quote, motive) in parsed.items():
            if verdict == NO_TRATA:
                continue
            found = _locate(entry, quote, finder, anomalies)
            if found is None:
                misses[item].add("cita_no_ubicada")
                continue
            candidates[item].append({
                "verdict": verdict, "quote": found.text, "page": found.page,
                "char_start": found.char_start, "char_end": found.char_end,
                "reading": found.reading.pk, "motive": motive})
    unread = bool(entry.unread_pages)
    out = {}
    for item in rows:
        found = candidates[item]
        if len({c["verdict"] for c in found}) > 1:
            out[item] = {"reason": "contradictorio"}
        elif found:
            out[item] = found[0]
        elif misses[item]:
            out[item] = {"reason": "cita_no_ubicada"}
        elif unread:
            # El informe tiene páginas que no se pudieron leer: no se afirma que no lo trata.
            out[item] = {"reason": "paginas_sin_leer"}
        else:
            out[item] = {"reason": NO_TRATA}
    return out, steps, anomalies


def _model_record():
    return {"model": settings.GENERATION_BATCH_MODEL,
            "file": settings.GENERATION_BATCH_MODEL_FILE,
            "sha256": settings.GENERATION_BATCH_MODEL_SHA256,
            "prompt": PROMPT_VERSION, "temperature": settings.GENERATION_TEMPERATURE,
            "seed": settings.GENERATION_SEED}


def propose(document, user, *, channel=Channel.COMMAND):
    """Lee el informe `document` y deja la propuesta de su oferta como hecho registrado (P6).
    Devuelve el hecho, o `None` si la oferta no tiene filas técnicas por renglón. Si el modelo
    falla, deja el hecho `failed` y relanza el error."""
    offer = document.offer
    rows = technical.item_rows(offer)
    if not rows:
        return None
    detail = {"kind": technical.PROPOSAL_KIND, "offer": offer.pk,
              "procedure": offer.procedure_id, "document": document.pk,
              "document_title": document.title, "file_sha256": document.file_sha256,
              "models": _model_record()}
    try:
        items, steps, anomalies = _read_report(document, offer, rows)
    except AIServiceError as error:
        audit.record(EventType.EVAL_BUILD, outcome=EventOutcome.FAILED, channel=channel,
                     user=user, detail={**detail, "reason": "falla",
                                        "message": str(error)[:300]})
        raise
    detail.update({"steps": steps, "anomalies": anomalies,
                   "items": {str(i): _entry(entry) for i, entry in items.items()}})
    return audit.record(EventType.EVAL_BUILD, outcome=EventOutcome.OK, channel=channel,
                        user=user, detail=detail)


def _entry(found):
    if "verdict" in found:
        return found
    return {"verdict": "", "reason": found["reason"]}


def request_proposal(user, offer_id, *, channel=Channel.SCREEN):
    """El evaluador pide proponer de nuevo, con los informes ya leídos de la oferta. Lanza
    `ReportRefused` si no hay informe o todavía se lee, y deja el hecho rechazado."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=PROPOSE_OPERATION,
                            channel=channel)
    offer = _offer(offer_id)
    reports = reports_of(offer)
    refusal = None
    if not reports:
        refusal = ReportRefused("La oferta todavía no tiene informe técnico del área.",
                                "report_not_uploaded")
    elif reading_reports(offer):
        refusal = ReportRefused("El informe se está leyendo: espere a que termine.",
                                "reading_in_progress")
    if refusal is not None:
        audit.record(EventType.EVAL_BUILD, outcome=EventOutcome.REJECTED, channel=channel,
                     user=user, detail={"kind": technical.PROPOSAL_KIND, "offer": offer.pk,
                                        "reason": refusal.reason, "message": str(refusal)})
        raise refusal
    try:
        return [propose(d, user, channel=channel) for d in reports]
    except AIServiceError as error:
        raise ReportRefused("No se pudo leer el informe con el modelo; reintente.",
                            "model_failed") from error


def after_read(job):
    """Paso posterior de la lectura de un documento (lo llama la cola con el pedido ya
    cerrado): si era un informe técnico del área, propone para su oferta. Si el modelo falla,
    queda el hecho `failed` (P6) y la Comisión lo pide a mano desde la matriz."""
    document = Document.objects.select_related("offer__procedure", "loaded_by").filter(
        pk=job.target_id, kind=DocumentKind.INFORME_TECNICO).first()
    if document is None or document.loaded_by is None:
        return None
    try:
        return propose(document, document.loaded_by, channel=Channel.COMMAND)
    except AIServiceError:
        return None  # `propose` ya dejó el hecho de la falla
