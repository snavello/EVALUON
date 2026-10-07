"""Pedir y armar la ficha de una oferta, y mostrarla (REQ-039, REQ-040, REQ-041, REQ-043,
REQ-044; plan 008, "Flujo de IA: armar la ficha", "Roles" y "Registro de auditoría"; ADR-0027;
T-130).

- `request_sheet`: pide la ficha de una oferta. Lo hacen el operador y el evaluador. Encola
  el pedido `build_sheet` y deja el hecho `sheet_request` (versión de la matriz y lecturas
  incluidas). Se rechaza, sin encolar nada y con el hecho en resultado `rejected` y su
  motivo, si no hay matriz validada (`no_matrix`, REQ-043), si la oferta no tiene documentos
  (`no_documents`), si algún documento está en lectura (`reading_in_progress`) o su lectura
  falló (`reading_failed`), o si ya hay un pedido de ficha de esa oferta en espera o en curso
  (`request_in_progress`).
- `run_build_sheet`: el manejador del pedido `build_sheet` (lo registra `tenders.jobs`).
- `build_sheet`: arma la ficha contra la última matriz validada. Para cada requisito firme
  (propuesto o confirmado; no los quitados ni las sugerencias) busca candidatos en todos los
  documentos de la oferta (`retrieval.py`) y le pide al modelo que elija cuáles responden y
  escriba una síntesis. **El fragmento es siempre el texto del pasaje, copiado de la base**:
  el modelo solo elige alias (P3, REQ-039). Sin alias válida, la fila queda "no se encontró
  en la oferta" (REQ-040), con el aviso de páginas sin leer si las hay: el sistema no supone
  que la respuesta estaba ahí. La síntesis se controla contra una lista de palabras de juicio
  (REQ-041): un reintento con el aviso y, si vuelve a fallar, la fila queda sin síntesis y la
  anomalía en el registro. En las filas técnicas por renglón se informa si el oferente lo
  cotizó (REQ-044); un renglón que no se puede descartar porque la oferta tiene páginas sin
  leer figura "no se pudo leer", nunca "no cotizado". Todo se guarda en una transacción al
  final: una ficha cortada no queda a medias. Cada pedido al modelo queda en
  `offers_sheet_step` y el armado deja el hecho `sheet_build` (P6).
- `sheet_page`: la ficha para la pantalla, en solo lectura.

El rol se comprueba fuera de toda transacción. Todo corre en el equipo, sin servicios
externos (P4).
"""

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai import generation
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers import retrieval
from evaluon.offers.models import (
    DocumentKind,
    Fragment,
    FragmentOrigin,
    FragmentState,
    Offer,
    Outcome as EntryOutcome,
    Passage,
    Quoted,
    Reading,
    Sheet,
    SheetChannel,
    SheetEntry,
    SheetStep,
)
from evaluon.offers.services import offers as offers_service
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    Job,
    JobKind,
    JobStatus,
    MatrixVersion,
    Requirement,
    RequirementClass,
    RequirementState,
)
from evaluon.tenders.services.validation import latest_validated

REQUEST_OPERATION = "evaluon.offers.services.sheets.request_sheet"
PAGE_OPERATION = "evaluon.offers.services.sheets.sheet_page"

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Filas de la ficha: los requisitos firmes de la matriz.
FIRM_STATES = (RequirementState.PROPUESTO, RequirementState.CONFIRMADO)

NOT_FOUND_TEXT = "no se encontró en la oferta"

# Anomalías (registro de la ficha y de cada pedido).
ANOMALY_INVALID_OUTPUT = "salida_invalida"
ANOMALY_UNKNOWN_ALIAS = "alias_inexistente"
ANOMALY_JUDGMENT = "sintesis_con_juicio"
ANOMALY_NO_QUOTE = "requisito_sin_cita"
ANOMALY_REWRITE = "reescritura_descartada"

MAX_PASSAGES_PER_ANSWER = 3

# Palabras de juicio de cumplimiento (REQ-041), con sus formas, sobre el texto sin tildes y en
# minúsculas. La síntesis describe lo que dice la oferta: no la juzga.
JUDGMENT_RULE_VERSION = "juicio-v1"
_JUDGMENT = re.compile(
    r"\b(?:cumpl\w*|incumpl\w*|satisf\w*|adecuad\w*|inadecuad\w*|conforme\w*|"
    r"aceptable\w*|inaceptable\w*)")


class SheetRefused(ValueError):
    """No se pidió la ficha. `reason` es el motivo que queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class Requested:
    """Lo que devuelve `request_sheet`: el pedido, la versión de la matriz y el hecho."""

    job: Job
    matrix_version: MatrixVersion
    event: object


def _plain(text):
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def judgment_words(text):
    """Las palabras de juicio de cumplimiento que tiene `text` (vacía si no tiene)."""
    return _JUDGMENT.findall(_plain(text))


# --- Pedido -------------------------------------------------------------------------------------


def _readings_summary(offer):
    return [{"document": r.document_id, "reading": r.pk, "sequence": r.sequence,
             "canonical_sha256": r.canonical_sha256}
            for r in offers_service.latest_readings(offer)]


def _check_request(offer):
    """Lanza `SheetRefused` si no se puede pedir la ficha; si no, devuelve la versión."""
    version = latest_validated(offer.procedure)
    if version is None:
        raise SheetRefused(
            "El procedimiento no tiene una matriz validada: la ficha se arma solo contra "
            "una matriz validada.", "no_matrix")
    rows = [offers_service.document_row(d) for d in offer.documents.order_by("loaded_at", "id")]
    if not rows:
        raise SheetRefused("La oferta no tiene documentos cargados: cargue sus documentos "
                           "antes de armar la ficha.", "no_documents")
    waiting = [r.document.title for r in rows
               if r.state in (offers_service.STATE_QUEUED, offers_service.STATE_RUNNING)]
    if waiting:
        raise SheetRefused(
            "Hay documentos que todavía se están leyendo: "
            + ", ".join(f"«{t}»" for t in waiting) + ". Espere a que terminen.",
            "reading_in_progress")
    failed = [r.document.title for r in rows
              if r.state == offers_service.STATE_FAILED or r.reading is None]
    if failed:
        raise SheetRefused(
            "No se pudo leer: " + ", ".join(f"«{t}»" for t in failed)
            + ". La ficha no se arma sin ese documento.", "reading_failed")
    if Job.objects.filter(kind=JobKind.BUILD_SHEET, target_id=offer.pk,
                          status__in=[JobStatus.QUEUED, JobStatus.RUNNING]).exists():
        raise SheetRefused("Ya hay un pedido de ficha de esta oferta en espera o en curso.",
                           "request_in_progress")
    return version


def request_sheet(user, offer, *, channel=Channel.SCREEN):
    """Pide la ficha de `offer`. Ver el módulo. Lanza `RoleRejected` sin rol de la Comisión
    y `SheetRefused` si no se puede pedir."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REQUEST_OPERATION,
                            channel=channel)
    detail = {"procedure": offer.procedure_id, "offer": offer.pk}
    try:
        version = _check_request(offer)
    except SheetRefused as error:
        audit.record(EventType.SHEET_REQUEST, outcome=Outcome.REJECTED, channel=channel,
                     user=user, detail={**detail, "reason": error.reason,
                                        "message": str(error)})
        raise
    with transaction.atomic():
        job = jobs.enqueue(JobKind.BUILD_SHEET, procedure=offer.procedure,
                           requested_by=user, target_id=offer.pk)
        event = audit.record(
            EventType.SHEET_REQUEST, outcome=Outcome.OK, channel=channel, user=user,
            detail={**detail, "job": job.pk, "matrix_version": version.pk,
                    "matrix_version_number": version.number,
                    "readings": _readings_summary(offer)})
    return Requested(job=job, matrix_version=version, event=event)


# --- Armado -------------------------------------------------------------------------------------


def load_prompt(name):
    """Texto de las instrucciones de la versión que fija `OFFERS_PROMPT_VERSIONS`."""
    version = settings.OFFERS_PROMPT_VERSIONS[name]
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def _models():
    return {
        "generation_batch": {
            "model": settings.GENERATION_BATCH_MODEL,
            "file": settings.GENERATION_BATCH_MODEL_FILE,
            "sha256": settings.GENERATION_BATCH_MODEL_SHA256,
            "mmproj_file": settings.GENERATION_BATCH_MMPROJ_FILE,
            "mmproj_sha256": settings.GENERATION_BATCH_MMPROJ_SHA256,
            "engine_build": settings.GENERATION_ENGINE_BUILD,
            "context_tokens": settings.GENERATION_BATCH_CONTEXT_TOKENS},
        "embeddings": {
            "model": settings.EMBEDDINGS_MODEL, "file": settings.EMBEDDINGS_MODEL_FILE,
            "sha256": settings.EMBEDDINGS_MODEL_SHA256},
        "reranker": {
            "model": settings.RERANKER_MODEL, "file": settings.RERANKER_MODEL_FILE,
            "sha256": settings.RERANKER_MODEL_SHA256},
    }


def _parameters():
    return {
        "passage_max_chars": settings.OFFERS_PASSAGE_MAX_CHARS,
        "passage_min_chars": settings.OFFERS_PASSAGE_MIN_CHARS,
        "candidates_embeddings": settings.OFFERS_CANDIDATES_EMBEDDINGS,
        "candidates_words": settings.OFFERS_CANDIDATES_WORDS,
        "candidates_to_model": settings.OFFERS_CANDIDATES_TO_MODEL,
        "item_candidates_to_model": settings.OFFERS_ITEM_CANDIDATES_TO_MODEL,
        "min_rerank_score": settings.OFFERS_MIN_RERANK_SCORE,
        "item_neighbor_seeds": settings.OFFERS_ITEM_NEIGHBOR_SEEDS,
        "item_neighbors": settings.OFFERS_ITEM_NEIGHBORS,
        "max_output_tokens": settings.OFFERS_MAX_OUTPUT_TOKENS,
        "request_timeout_seconds": settings.OFFERS_REQUEST_TIMEOUT_SECONDS,
        "query_max_chars": settings.OFFERS_QUERY_MAX_CHARS,
        "temperature": settings.GENERATION_TEMPERATURE,
        "seed": settings.GENERATION_SEED,
        "thinking": settings.GENERATION_THINKING,
        "generation_batch_url": settings.GENERATION_BATCH_URL,
        "max_passages_per_answer": MAX_PASSAGES_PER_ANSWER,
        "judgment_rule_version": JUDGMENT_RULE_VERSION,
    }


def firm_requirements(version):
    """Los requisitos que son filas de la ficha, en el orden de la matriz."""
    return list(version.requirements.filter(state__in=FIRM_STATES).order_by("number"))


def _quotes(requirement):
    return list(requirement.quotes.order_by("order"))


def is_item_row(requirement):
    """Una fila técnica por renglón (REQ-044)."""
    return requirement.category == RequirementClass.TECNICO and bool(requirement.items)


def requirement_text(requirement):
    """El texto del requisito que se busca y se le muestra al modelo: la cita del pliego
    (de una fila por renglón, la del renglón con su encabezado). Vacío si no tiene cita."""
    quotes = _quotes(requirement)
    if not quotes:
        return ""
    if is_item_row(requirement):
        own = [q for q in quotes if q.scope == "propia"]
        return " ".join(q.text for q in (own or quotes[:1]))
    return quotes[0].text


def retrieval_query(requirement, text):
    """La consulta de la recuperación: la cita del requisito; la de una fila por renglón
    empieza con "Renglón N", porque las tablas de las ofertas traen solo el número y la
    descripción (T-135)."""
    if text and is_item_row(requirement):
        return f"Renglón {requirement.items[0]}: {text}"
    return text


def build_messages(prompt, requirement, text, aliased, correction=""):
    """Mensajes del pedido: las instrucciones como sistema; el requisito y los candidatos
    como usuario. `correction` suma el aviso del reintento."""
    label = (f"Renglón {requirement.items[0]} del pliego" if is_item_row(requirement)
             else "Requisito del pliego")
    blocks = "\n\n".join(
        f"[{alias}]\nDocumento: {title}\nPágina: {page}\nTexto:\n{body}\n[/{alias}]"
        for alias, title, page, body in aliased)
    user = (f"{label}:\n«{text}»\n\nPasajes de la oferta:\n\n{blocks}\n\n"
            "Devolvé un objeto JSON con los campos pedidos.")
    if correction:
        user += "\n\n" + correction
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


def build_schema(aliases, item_row):
    properties = {
        "pasajes": {"type": "array", "items": {"type": "string", "enum": list(aliases)},
                    "maxItems": MAX_PASSAGES_PER_ANSWER},
        "sintesis": {"type": "string"},
    }
    required = ["pasajes", "sintesis"]
    if item_row:
        properties = {"cotizado": {"type": "string", "enum": ["si", "sin_precio", "no"]},
                      **properties}
        required = ["cotizado", *required]
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


class InvalidAnswer(ValueError):
    """La salida del modelo no tiene la forma pedida."""

    def __init__(self, message, kind=ANOMALY_INVALID_OUTPUT):
        super().__init__(message)
        self.kind = kind


def parse_answer(content, aliases, item_row):
    """Interpreta la salida del modelo: `(alias elegidas, síntesis, cotizado o None)`.
    Lanza `InvalidAnswer` si no es el objeto pedido o si cita una alias inexistente."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidAnswer("la salida no es JSON") from error
    expected = {"cotizado", "pasajes", "sintesis"} if item_row else {"pasajes", "sintesis"}
    if not isinstance(data, dict) or set(data) != expected:
        raise InvalidAnswer("la salida no tiene los campos pedidos")
    chosen, synthesis = data["pasajes"], data["sintesis"]
    if not isinstance(chosen, list) or not all(isinstance(a, str) for a in chosen):
        raise InvalidAnswer("pasajes no es una lista de alias")
    if not isinstance(synthesis, str):
        raise InvalidAnswer("sintesis no es texto")
    unknown = [a for a in chosen if a not in aliases]
    if unknown:
        raise InvalidAnswer(f"alias inexistente: {', '.join(unknown)}", ANOMALY_UNKNOWN_ALIAS)
    quoted = None
    if item_row:
        quoted = data["cotizado"]
        if quoted not in ("si", "sin_precio", "no"):
            raise InvalidAnswer("cotizado no es si ni no")
    unique = list(dict.fromkeys(chosen))
    return unique, synthesis.strip(), quoted


@dataclass
class StepData:
    """Un pedido al modelo, todavía sin guardar."""

    candidates: list
    request: dict | None = None
    raw_output: str = ""
    parsed: dict | None = None
    anomalies: list = field(default_factory=list)
    retry_of: int | None = None  # posición del pedido anterior en la lista de la fila
    timings: dict = field(default_factory=dict)


@dataclass
class EntryData:
    """Una fila de la ficha, todavía sin guardar."""

    requirement: Requirement
    outcome: str = EntryOutcome.NO_ENCONTRADO
    synthesis: str = ""
    quoted: str = ""
    passages: list = field(default_factory=list)
    unread_warning: bool = False
    steps: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)


def _candidate_json(candidate, passage):
    return {**candidate.as_json(), "key": passage.key, "page": passage.page,
            "document": passage.reading.document_id}


def _correction(problem):
    if problem[0] == "judgment":
        return ("Tu respuesta anterior usó " + ", ".join(f"«{w}»" for w in problem[1])
                + ", que expresa un juicio de cumplimiento. Volvé a responder describiendo "
                "solo lo que dice la oferta, sin juzgarla.")
    return ("Tu respuesta anterior no tuvo la forma pedida (" + problem[1]
            + "). Respondé solo con el objeto JSON pedido y usá solo los alias de la lista.")


def _only_technical(passages):
    return all(p.reading.document.kind == DocumentKind.TECNICA for p in passages)


def neutral_synthesis(passages):
    """Síntesis de una fila cuyo texto del modelo sigue con juicio después del reintento: solo
    dice dónde está la respuesta (documento y página de los pasajes), sin datos del modelo
    (T-135)."""
    places = "; ".join(f"{p.reading.document.title}, página {p.page}" for p in passages)
    text = f"El oferente responde en: {places}."
    return text if not judgment_words(text) else "El oferente responde en los pasajes mostrados."


REWRITE_SCHEMA = {"type": "object", "properties": {"consulta": {"type": "string"}},
                  "required": ["consulta"], "additionalProperties": False}


def rewrite_requirement(text, clock=time.monotonic):
    """El requisito escrito como lo diría una oferta (T-146), para buscar. Devuelve el
    registro de la reescritura (P6): `query` es el texto, vacío si se descartó (salida sin la
    forma pedida, o vacía); en ese caso la búsqueda sigue solo con la
    consulta del pliego y `anomaly` dice por qué."""
    messages = [
        {"role": "system", "content": load_prompt("reescritura")},
        {"role": "user", "content": f"Requisito del pliego:\n«{text}»\n\n"
                                    "Devolvé un objeto JSON con el campo pedido."}]
    started = clock()
    result = generation.generate(
        messages, REWRITE_SCHEMA, max_tokens=settings.OFFERS_MAX_OUTPUT_TOKENS,
        base_url=settings.GENERATION_BATCH_URL, timeout=settings.OFFERS_REQUEST_TIMEOUT_SECONDS)
    record = {"prompt_version": settings.OFFERS_PROMPT_VERSIONS["reescritura"],
              "request": result.request, "raw_output": result.content, "query": "",
              "seconds": round(clock() - started, 3)}
    try:
        data = json.loads(result.content)
        query = data["consulta"].strip()
        if set(data) != {"consulta"}:
            raise ValueError("campos de más")
    except (ValueError, KeyError, TypeError, AttributeError):
        record["anomaly"] = "salida sin la forma pedida"
        return record
    if not query:
        record["anomaly"] = "consulta vacía"
    else:
        record["query"] = query
    return record


def _answer_entry(offer, requirement, unread, clock):
    """Arma una fila: recupera candidatos, pide al modelo y valida su respuesta."""
    entry = EntryData(requirement=requirement, unread_warning=bool(unread))
    item_row = is_item_row(requirement)
    text = requirement_text(requirement)
    if not text:
        entry.anomalies.append({"type": ANOMALY_NO_QUOTE, "requirement": requirement.number})
    # Las filas comunes buscan también con el requisito reescrito como lo diría una oferta
    # (T-146); las de renglón no (T-135: su consulta ya es la tabla).
    rewrite = rewrite_requirement(text, clock) if text and not item_row else None
    started = clock()
    found = retrieval.retrieve(offer, retrieval_query(requirement, text), neighbors=item_row,
                               rewrite=rewrite["query"] if rewrite else "")
    retrieval_seconds = clock() - started
    passages = {p.pk: p for p in Passage.objects.filter(
        pk__in=[c.passage_id for c in found.pool]).select_related("reading__document")}
    pool_json = [_candidate_json(c, passages[c.passage_id]) for c in found.pool]
    sent = [c.passage_id for c in found.chosen]
    extra = {"rewrite": rewrite} if rewrite else {}
    if rewrite and rewrite.get("anomaly"):
        entry.anomalies.append({"type": ANOMALY_REWRITE, "requirement": requirement.number,
                                "reason": rewrite["anomaly"]})
    if not found.chosen:
        entry.steps.append(StepData(
            candidates={"pool": pool_json, "sent": sent, "query": found.query, **extra},
            timings={"retrieval_seconds": round(retrieval_seconds, 3)}))
        if item_row:
            entry.quoted = item_state("sin_precio", [], unread)
        return entry

    aliased = [(f"P{i}", passages[c.passage_id].reading.document.title,
                passages[c.passage_id].page, passages[c.passage_id].text)
               for i, c in enumerate(found.chosen, start=1)]
    alias_to_passage = {f"P{i}": passages[c.passage_id]
                        for i, c in enumerate(found.chosen, start=1)}
    aliases = list(alias_to_passage)
    prompt = load_prompt("ficha_renglon" if item_row else "ficha")
    schema = build_schema(aliases, item_row)
    candidates = {"pool": pool_json, "sent": sent, "query": found.query, **extra,
                  "aliases": {alias: p.pk for alias, p in alias_to_passage.items()}}

    answer, correction, previous = None, "", None
    first = None  # la primera respuesta con forma válida pero con juicio
    for attempt in range(2):
        step = StepData(candidates=candidates, retry_of=previous,
                        timings={"retrieval_seconds": round(retrieval_seconds, 3)})
        entry.steps.append(step)
        messages = build_messages(prompt, requirement, text, aliased, correction)
        started = clock()
        result = generation.generate(
            messages, schema, max_tokens=settings.OFFERS_MAX_OUTPUT_TOKENS,
            base_url=settings.GENERATION_BATCH_URL,
            timeout=settings.OFFERS_REQUEST_TIMEOUT_SECONDS)
        step.timings["generation_seconds"] = round(clock() - started, 3)
        step.request = result.request
        step.raw_output = result.content
        problem = None
        try:
            chosen, synthesis, quoted = parse_answer(result.content, aliases, item_row)
        except InvalidAnswer as error:
            step.anomalies.append({"type": error.kind, "message": str(error)})
            problem = ("invalid", str(error), error.kind)
        else:
            step.parsed = {"pasajes": chosen, "sintesis": synthesis, "cotizado": quoted}
            words = judgment_words(synthesis)
            if words:
                step.anomalies.append({"type": ANOMALY_JUDGMENT, "words": words})
                problem = ("judgment", words, ANOMALY_JUDGMENT)
                first = first or (chosen, "", quoted)
            answer = (chosen, "" if words else synthesis, quoted)
        if problem is None:
            break
        if attempt == 0:
            correction = _correction(problem)
            previous = len(entry.steps) - 1
        else:
            # Sigue mal después del reintento: la fila queda con lo que se pueda usar y la
            # anomalía registrada (REQ-041).
            entry.anomalies.append({"type": problem[2], "requirement": requirement.number})
            if problem[0] == "invalid":
                answer = first
    if answer is None:
        return entry
    chosen, synthesis, quoted = answer
    entry.passages = [alias_to_passage[a] for a in chosen]
    if entry.passages:
        entry.outcome = EntryOutcome.ENCONTRADO
        entry.synthesis = synthesis or neutral_synthesis(entry.passages)
    if item_row:
        entry.quoted = item_state(quoted, entry.passages, unread)
    return entry


def item_state(quoted, passages, unread):
    """El estado de cotización de una fila por renglón (REQ-044), separado de los pasajes que
    la fila muestra (T-136). `quoted` es lo que contestó el modelo (`si`, `sin_precio` o
    `no`), `passages` los pasajes de la fila y `unread` las páginas sin leer de la oferta.

    - "cotizado": solo si algún pasaje trae el precio o la cantidad ofrecida. Una hoja técnica
      o las especificaciones solas no alcanzan, aunque el modelo diga `si`: la fila las sigue
      mostrando, pero el renglón queda sin cotización a la vista.
    - "no cotizado": la oferta dice expresamente que no lo cotiza, o su tabla de precios no lo
      trae (el modelo contestó `no`). Sin pasajes y con páginas sin leer, "no se pudo leer".
    - sin cotización a la vista (`Quoted` en blanco): hay pasajes que describen lo ofrecido, o
      ninguno, pero ni precio ni cantidad ni una negativa expresa. Con páginas sin leer y sin
      pasajes, "no se pudo leer": no se afirma lo que quizás está en una página ilegible."""
    if quoted == "si" and passages and not _only_technical(passages):
        return Quoted.COTIZADO
    if quoted == "no":
        return Quoted.NO_SE_PUDO_LEER if unread and not passages else Quoted.NO_COTIZADO
    if unread and not passages:
        return Quoted.NO_SE_PUDO_LEER
    return ""


def _unread_pages(readings):
    """Las páginas no leídas de las lecturas dadas (REQ-038), de todos los documentos."""
    return [page for reading in readings for page in reading.report.get("unread", [])]


def _technical_documents(offer, entries):
    docs = list(offer.documents.filter(kind=DocumentKind.TECNICA)
                .order_by("id").values_list("pk", flat=True))
    # Cuenta solo un documento técnico (especificaciones firmadas, folletos, hojas técnicas,
    # T-131); una tabla de renglones con fragmentos no alcanza.
    return {"present": bool(docs), "documents": docs}


def _counts(entries, steps_count):
    counts = {"entries": len(entries), "model_requests": steps_count,
              "retries": sum(1 for e in entries for s in e.steps if s.retry_of is not None),
              "found": sum(1 for e in entries if e.outcome == EntryOutcome.ENCONTRADO),
              "not_found": sum(1 for e in entries if e.outcome == EntryOutcome.NO_ENCONTRADO),
              "fragments": sum(len(e.passages) for e in entries)}
    for kind in Quoted:
        counts[kind.value] = sum(1 for e in entries if e.quoted == kind)
    counts["sin_cotizacion_a_la_vista"] = sum(
        1 for e in entries if is_item_row(e.requirement) and e.quoted == "")
    return counts


def build_sheet(offer, user, *, channel=SheetChannel.SCREEN, job=None,
                audit_channel=Channel.COMMAND, clock=time.monotonic):
    """Arma la ficha de `offer` contra la última matriz validada y la guarda. Ver el módulo.
    Lanza `SheetRefused` si no hay matriz validada o ninguna lectura. Cualquier falla deja
    el hecho `sheet_build` fallido y se vuelve a lanzar."""
    detail = {"procedure": offer.procedure_id, "offer": offer.pk,
              "job": job.pk if job else None}
    try:
        version = latest_validated(offer.procedure)
        if version is None:
            raise SheetRefused("El procedimiento no tiene una matriz validada.", "no_matrix")
        readings = offers_service.latest_readings(offer)
        if not readings:
            raise SheetRefused("La oferta no tiene ningún documento leído.", "no_documents")
        detail.update(matrix_version=version.pk, matrix_version_number=version.number)
        unread = _unread_pages(readings)
        started = clock()
        requirements = list(firm_requirements(version))
        entries = []
        for index, requirement in enumerate(requirements):
            if job is not None:
                jobs.report(job, f"Buscando en la oferta el requisito {requirement.number}",
                            index, len(requirements), f"Ficha de la oferta {offer.number}")
            entries.append(_answer_entry(offer, requirement, unread, clock))
        if job is not None:
            jobs.report(job, "Guardando la ficha", len(requirements), len(requirements),
                        f"Ficha de la oferta {offer.number}")
        steps_count = sum(len(e.steps) for e in entries)
        counts = _counts(entries, steps_count)
        anomalies = [a for e in entries for a in e.anomalies]
        timings = {"total_seconds": round(clock() - started, 3), "entries": len(entries),
                   "model_requests": steps_count}
        technical = _technical_documents(offer, entries)

        with transaction.atomic():
            Offer.objects.select_for_update().get(pk=offer.pk)
            last = offer.sheets.aggregate(last=Max("number"))["last"] or 0
            sheet = Sheet.objects.create(
                offer=offer, matrix_version=version, number=last + 1, channel=channel,
                readings=_readings_summary(offer), models_used=_models(),
                parameters=_parameters(), prompt_versions=dict(settings.OFFERS_PROMPT_VERSIONS),
                counts=counts, timings=timings, anomalies=anomalies,
                technical_documents=technical, requested_by=user, job=job)
            for data in entries:
                _save_entry(sheet, data)
            audit.record(
                EventType.SHEET_BUILD, outcome=Outcome.OK, channel=audit_channel, user=user,
                detail={**detail, "sheet": sheet.pk, "number": sheet.number,
                        "models": sheet.models_used, "parameters": sheet.parameters,
                        "prompt_versions": sheet.prompt_versions, "readings": sheet.readings,
                        "counts": counts, "anomalies": anomalies, "timings": timings,
                        "technical_documents": technical, "unread_pages": len(unread)})
    except Exception as error:
        audit.record(EventType.SHEET_BUILD, outcome=Outcome.FAILED, channel=audit_channel,
                     user=user, detail={**detail,
                                        "error": f"{type(error).__name__}: {error}"})
        raise
    return sheet


def _save_entry(sheet, data):
    entry = SheetEntry.objects.create(
        sheet=sheet, requirement=data.requirement, outcome=data.outcome,
        synthesis=data.synthesis, quoted=data.quoted,
        unread_pages_warning=data.unread_warning)
    for order, passage in enumerate(data.passages, start=1):
        # El texto del fragmento es el del pasaje, copiado de la base (P3).
        Fragment.objects.create(
            entry=entry, order=order, passage=passage, char_start=passage.char_start,
            char_end=passage.char_end, text=passage.text, origin=FragmentOrigin.SISTEMA,
            state=FragmentState.PROPUESTO,
            proposed={"passage": passage.pk, "char_start": passage.char_start,
                      "char_end": passage.char_end, "text": passage.text})
    saved = []
    for step in data.steps:
        saved.append(SheetStep.objects.create(
            sheet=sheet, entry=entry, candidates=step.candidates, request=step.request,
            raw_output=step.raw_output, parsed=step.parsed, anomalies=step.anomalies,
            retry_of=None if step.retry_of is None else saved[step.retry_of],
            timings=step.timings))
    return entry


def run_build_sheet(job):
    """Manejador del pedido `build_sheet`: arma la ficha de la oferta del pedido. No marca
    el estado del pedido: eso es de `jobs.run`."""
    offer = Offer.objects.select_related("procedure").get(pk=job.target_id)
    if offer.procedure_id != job.procedure_id:
        raise ValueError("La oferta del pedido no es del procedimiento del pedido.")
    return build_sheet(offer, job.requested_by, channel=SheetChannel.SCREEN, job=job)


# --- Página de la ficha -------------------------------------------------------------------------


@dataclass
class FragmentView:
    fragment: Fragment
    document: object
    page: int


@dataclass
class EntryRow:
    entry: SheetEntry
    requirement: Requirement
    text: str
    fragments: list
    item: int | None


@dataclass
class SheetPage:
    """La ficha para la pantalla: sus filas, lo que no se encontró, las páginas sin leer y
    el aviso de versión de la matriz (REQ-043)."""

    sheet: Sheet
    offer: Offer
    rows: list
    missing: list
    unread: list
    newer_version: MatrixVersion | None
    technical_documents: dict
    item_rows: list


def sheet_page(user, sheet_id, *, channel=Channel.SCREEN):
    """La ficha en solo lectura. Lanza `RoleRejected` sin rol de la Comisión y
    `Sheet.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    sheet = Sheet.objects.select_related("offer__procedure", "matrix_version").get(pk=sheet_id)
    entries = list(sheet.entries.select_related("requirement")
                   .order_by("requirement__number"))
    rows = []
    for entry in entries:
        fragments = [FragmentView(f, f.passage.reading.document, f.passage.page)
                     for f in entry.fragments.exclude(state=FragmentState.QUITADO)
                     .select_related("passage__reading__document").order_by("order")]
        item = entry.requirement.items[0] if is_item_row(entry.requirement) else None
        rows.append(EntryRow(entry=entry, requirement=entry.requirement,
                             text=requirement_text(entry.requirement), fragments=fragments,
                             item=item))
    reading_ids = [r["reading"] for r in sheet.readings]
    unread = [page for reading in Reading.objects.filter(pk__in=reading_ids)
              .order_by("document_id") for page in reading.report.get("unread", [])]
    latest = latest_validated(sheet.offer.procedure)
    newer = latest if latest is not None and latest.number > sheet.matrix_version.number \
        else None
    return SheetPage(
        sheet=sheet, offer=sheet.offer, rows=rows,
        missing=[r for r in rows if r.entry.outcome == EntryOutcome.NO_ENCONTRADO],
        unread=unread, newer_version=newer,
        technical_documents=sheet.technical_documents,
        item_rows=[r for r in rows if r.item is not None])
