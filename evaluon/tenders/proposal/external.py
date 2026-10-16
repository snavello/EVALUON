"""Etapa externa de la matriz: extracción, completitud y filtro con el modelo externo, que lee el
pliego completo (T-291; REQ-122, REQ-123; plan 016, «Paso 3 · Matriz con modelo externo»;
ADR-0065 a ADR-0068).

**Qué se manda.** El pliego completo es el prefijo común (el sistema) de todos los pedidos de la
propuesta: la instrucción `matriz-externa-v1` (con el bloque `matriz-definiciones-vN` de la matriz
local) y el texto canónico de todos los tramos de la lectura vigente, en el orden del documento,
con los mismos `[T1]…[/T1]` del extractor local (`extraction.render_block`: documento, ruta,
encabezado, renglones, clase de la sección y texto visible). Nunca el PDF. El prefijo lleva caché
de una hora; lo que cambia en cada pedido (qué tramos decide, qué filas controla) va al final, en
el mensaje del usuario. Cada pieza entra con su origen (O-290-3): el texto de un tramo, con
`guard.tender_document` de su documento; lo que escribe el código, con `guard.instruction`.

**Pedidos.** Todos se arman con `guard.build` y se mandan con `ledger.send` (registro, tope y
reuso por huella), en el modo de `EXTERNAL_MODE` (`lotes`; `directo` solo para la prueba de humo):

- (a) extracción (`matriz_extraccion`): los tramos que no decide una regla, en el orden del
  pliego, repartidos en pedidos de hasta `SEGMENTS_PER_REQUEST` tramos (al menos 1 y como mucho
  `MAX_EXTRACTION_REQUESTS`: un pliego de 300 tramos sale en 2, uno de 600 en 4), todos en un lote;
- (b) completitud y filtro (`matriz_completitud_filtro`): un pedido con las filas ya extraídas:
  qué oración obligatoria falta y, por fila, firme, sugerencia o descartada con su motivo.

Esfuerzo y pensamiento, los de la etapa (`EXTERNAL_EFFORT`, `EXTERNAL_THINKING`); `max_tokens`
`MAX_TOKENS`; salida con el esquema JSON del pedido. Los largos se validan acá, no en el esquema.

**Mismo contrato que lo local.** `Stage.extract` devuelve una `extraction.Extraction` (un
`extraction.Outcome` por tramo); `Stage.complete_and_filter` devuelve una
`completeness.Completion` y un `ExternalFilter` cuyo `filter_rows` devuelve un `filter.Result`
(firme, sugerencia o descartada por fila). Lo que viene después en `run.propose` no se entera de
quién decidió.

**Citas.** Como en lo local: el fragmento del modelo se ubica con `quotes.locate_unit` (que llama
a `quotes.locate`) y se amplía con `sentences.py`; lo guardado es el recorte del texto canónico.
Un fragmento que no se ubica se descarta con la anomalía `fragmento_externo_no_ubicado`; un tramo
cuyas citas no se ubicó ninguna, sin marca técnica, queda sin disposición (pendiente de revisión).
Un descarte sin motivo de la lista o sin indicio ubicado va a sugerencia (`descarte_sin_sustento`):
una duda nunca es un descarte silencioso.

**Si falla.** Un bloqueo de la puerta, un error, un vencimiento, el tope, una etapa frenada o una
salida que no es el JSON pedido lanzan `Unavailable` con sus anomalías: la propuesta sigue con la
cadena local y lo registra (`externo_no_disponible`, etapa `local`). Nada de lo externo se aplica a
medias.

Cada pedido externo deja su fila en `tenders_run_step` (la extracción como `extraccion`, la
completitud y el filtro como `completitud`) con la referencia al hecho `external_request`, que
guarda el texto enviado y la respuesta completos (P6).
"""

import json
import math
import time
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from evaluon.ai.external import client, guard, ledger
from evaluon.tenders.models import DiscardReason, PassName, RunStep
from evaluon.tenders.proposal import completeness, dedup, extraction, quotes
from evaluon.tenders.proposal import filter as row_filter

STAGE = "matriz"
STAGE_EXTRACTION = "matriz_extraccion"
STAGE_COMPLETION = "matriz_completitud_filtro"
RUN_KIND = "matriz"
INSTRUCTION_NAME = "matriz_externa"

MAX_TOKENS = 32000
SEGMENTS_PER_REQUEST = 150
MAX_EXTRACTION_REQUESTS = 4
CACHE_TTL = "1h"

FIRME, SUGERENCIA, DESCARTADA = row_filter.FIRME, row_filter.SUGERENCIA, row_filter.DESCARTADA
DESTINATIONS = (FIRME, SUGERENCIA, DESCARTADA)
ADDED_DESTINATIONS = (FIRME, SUGERENCIA)

# Las pasadas locales que la etapa externa reemplaza (plan 016, «Dónde se enchufa»).
REPLACED_PASSES = ("extraccion", "completitud", "union_oraciones", "unificacion", "filtro")

ANOMALY_NOT_LOCATED = "fragmento_externo_no_ubicado"
ANOMALY_UNAVAILABLE = ledger.ANOMALY_UNAVAILABLE  # externo_no_disponible
ANOMALY_BLOCKED = guard.ANOMALY  # externo_bloqueado
ANOMALY_STOPPED = "externo_etapa_frenada"
ANOMALY_INVALID = "externo_salida_invalida"
ANOMALY_MISSING_SEGMENT = "externo_tramo_sin_respuesta"
ANOMALY_EXTRA_SEGMENT = "externo_tramo_no_pedido"
ANOMALY_REPEATED = "externo_respuesta_repetida"
ANOMALY_OUT_OF_SCOPE = "externo_faltante_fuera_de_alcance"
ANOMALY_NO_ROW_ANSWER = "externo_fila_sin_respuesta"

_CLASS_LABELS = {"formal": "formal", "economico": "económico"}


def enabled():
    """Si la matriz va por el modelo externo: el uso externo encendido y la etapa en `externo`."""
    return bool(settings.EXTERNAL_ENABLED) and settings.EXTERNAL_STAGES.get(STAGE) == "externo"


class Unavailable(Exception):
    """La etapa externa no puede terminar: la propuesta sigue por la cadena local. `anomalies`
    son las que la propuesta registra (con `type`, como las demás)."""

    def __init__(self, reason, anomalies=()):
        super().__init__(reason)
        self.reason = reason
        self.anomalies = [*anomalies, {"type": ANOMALY_UNAVAILABLE, "etapa": STAGE,
                                       "motivo": reason, "camino": "local"}]


# --- Instrucción ---------------------------------------------------------------------------------


def load_instruction():
    """La `extraction.Instruction` de `EXTERNAL_PROMPT_VERSIONS["matriz"]`, con el bloque de
    definiciones de la matriz local donde tiene la marca (la fuente de las decisiones es una)."""
    version = settings.EXTERNAL_PROMPT_VERSIONS[STAGE]
    raw = (extraction.PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")
    block_version = settings.MATRIX_PROMPT_VERSIONS[extraction.DEFINITIONS_NAME]
    block = (extraction.PROMPTS_DIR / f"{block_version}.md").read_text(encoding="utf-8")
    return extraction.Instruction(
        INSTRUCTION_NAME, version, raw.replace(extraction.DEFINITIONS_MARK, block.strip()),
        extraction.text_sha256(raw), (block_version, extraction.text_sha256(block)))


# --- Esquemas ------------------------------------------------------------------------------------


def _object(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _enum(values):
    return {"type": "string", "enum": list(values)}


def extraction_schema(numbers):
    """Salida del pedido de extracción: un elemento de `tramos` por tramo pedido."""
    requirement = _object({"cita": {"type": "string"},
                           "clase": _enum(extraction.BODY_CLASSES),
                           "opcion": _enum(["", *extraction.OPTIONS])})
    item = _object({
        "tramo": {"type": "string"},
        "requisitos": {"type": "array", "items": requirement},
        "tecnico": {"type": "array",
                    "items": _enum([extraction.ALL_ITEMS, *[str(n) for n in numbers]])},
        "descarte": _enum(["", *DiscardReason.values]),
    })
    return _object({"tramos": {"type": "array", "items": item}})


def completion_schema():
    """Salida del pedido de completitud y filtro: los faltantes y un elemento por fila."""
    missing = _object({"tramo": {"type": "string"}, "cita": {"type": "string"},
                       "clase": _enum(extraction.BODY_CLASSES),
                       "opcion": _enum(["", *extraction.OPTIONS]),
                       "destino": _enum(ADDED_DESTINATIONS)})
    row = _object({"fila": {"type": "string"}, "destino": _enum(DESTINATIONS),
                   "motivo": _enum(["", *settings.FILTER_MOTIVES]),
                   "indicio": {"type": "string"}, "razonamiento": {"type": "string"}})
    return _object({"faltantes": {"type": "array", "items": missing},
                    "filas": {"type": "array", "items": row}})


# --- Reparto -------------------------------------------------------------------------------------


def split(units):
    """Los tramos de la extracción en pedidos consecutivos de tamaño parejo: `ceil(n / 150)`
    pedidos, entre 1 y `MAX_EXTRACTION_REQUESTS` (por encima de 600 tramos, cada pedido lleva
    más de 150)."""
    units = list(units)
    if not units:
        return []
    count = min(max(math.ceil(len(units) / SEGMENTS_PER_REQUEST), 1), MAX_EXTRACTION_REQUESTS)
    size = math.ceil(len(units) / count)
    return [units[at:at + size] for at in range(0, len(units), size)]


def alias_of(unit):
    """El alias de un tramo en el pliego completo: su lugar en el orden de la propuesta."""
    return f"T{unit.position}"


# --- Lectura de las respuestas -------------------------------------------------------------------


def _category(unit, kind):
    """La clase de un requisito: la de la sección si la nombra; si no, la del modelo."""
    section = unit.segment.section_class
    return section if section in extraction.BODY_CLASSES else kind


def _not_located(unit, category, step_kind):
    return {"type": ANOMALY_NOT_LOCATED, "segment": unit.segment.pk, "key": unit.segment.key,
            "clase": category, "pedido": step_kind}


def resolve(unit, item, anomalies):
    """Ubica las citas de `item` (`extraction.Item`) en el tramo y las amplía a su unidad de
    sentido, como la extracción local. Un fragmento que no se ubica se descarta con la anomalía
    `fragmento_externo_no_ubicado` (no queda como cita amplia). Devuelve los `Found`."""
    text = unit.segment.text
    seen, used, found = set(), set(), []
    for index, (quote, kind) in enumerate(item.quotes):
        key = quote.strip()
        if key in seen:
            anomalies.append({"type": extraction.ANOMALY_QUOTES_JOINED,
                              "segment": unit.segment.pk, "key": unit.segment.key})
            continue
        seen.add(key)
        category = _category(unit, kind)
        located = quotes.locate_unit(text, key, used, expand=extraction.expands(unit))
        if located is None:
            anomalies.append(_not_located(unit, category, "extraccion"))
            continue
        fragment, expansion = located
        used.add(fragment)
        if expansion.too_long:
            anomalies.append({"type": extraction.ANOMALY_UNIT_TOO_LONG,
                              "segment": unit.segment.pk, "key": unit.segment.key,
                              "clase": category})
        new = extraction.found_from(category, fragment, expansion, item.option_of(index))
        if extraction.merge_into(found, new) is not None:
            anomalies.append({"type": extraction.ANOMALY_QUOTES_JOINED,
                              "segment": unit.segment.pk, "key": unit.segment.key,
                              "unidad": True})
    return found


def _load(text, keys):
    """La respuesta como objeto JSON con exactamente `keys`, cada una una lista; si no, `None`."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) != set(keys):
        return None
    if not all(isinstance(data[key], list) for key in keys):
        return None
    return data


def _by_alias(entries, field_name, asked, anomalies, segment_of=None):
    """`{alias: entrada}` de una lista de la respuesta: solo los alias pedidos y una vez cada uno
    (un alias repetido no vale: ni la primera ni la segunda respuesta)."""
    found, repeated = {}, set()
    for entry in entries:
        alias = entry.get(field_name) if isinstance(entry, dict) else None
        if not isinstance(alias, str) or alias not in asked:
            anomalies.append({"type": ANOMALY_EXTRA_SEGMENT, "alias": str(alias)[:20]})
            continue
        if alias in found:
            repeated.add(alias)
        found[alias] = entry
    for alias in repeated:
        found.pop(alias)
        anomalies.append({"type": ANOMALY_REPEATED, "alias": alias,
                          **({"segment": segment_of(alias)} if segment_of else {})})
    return found


def _found_record(found, text):
    return extraction.found_record(found, text)


def same_requirement(new, old):
    """Si un faltante es una fila que ya está en el tramo: una de las dos citas queda contenida
    en la otra en al menos el 90 % de sus caracteres (la misma regla que la completitud local)."""
    if new.flag == quotes.WIDE or old.flag == quotes.WIDE:
        return new.flag == old.flag and new.category == old.category
    return max(completeness.containment(new.span, old.span),
               completeness.containment(old.span, new.span)) >= completeness.CONTAINED


# --- El filtro ya respondido ---------------------------------------------------------------------


class ExternalFilter:
    """El filtro con las respuestas del modelo externo: `filter_rows(rows)` devuelve un
    `filter.Result` como `filter.Filter`, con las mismas guardas de código (oración compartida con
    una firme, la opción descartada por `condicion_opcional`, sugerencias apagadas). `answers` es
    `{id(Found): respuesta}`; una fila sin respuesta queda firme con la anomalía, como una fila sin
    opinión del filtro local."""

    def __init__(self, answers, step):
        self.answers = answers
        self.steps = [step]
        self.step = step
        self.anomalies = []
        self.stats = {"requests": 1, "requests_a": 1, "requests_b": 0, "split_batches": 0,
                      "failed_requests": 0}

    def _verdict(self, row):
        answer = self.answers.get(id(row.found))
        verdict = row_filter.Verdict(row, FIRME, step_a=self.step, step_b=self.step)
        if answer is None:
            verdict.anomaly = row_filter.ANOMALY_NO_OPINION
            self.anomalies.append({"type": ANOMALY_NO_ROW_ANSWER, "segment": row.segment.pk,
                                   "key": row.segment.key})
            return verdict
        verdict.vote_a = answer
        verdict.vote_b = {"origen": "externo"}
        destination = answer["destino"]
        if destination == FIRME:
            return verdict
        if destination == SUGERENCIA:
            verdict.destination = SUGERENCIA
            verdict.doubt_reason = "duda"
            return verdict
        evidence = row_filter.find_evidence(row.segment, answer.get("indicio", ""))
        verdict.evidence = evidence
        supported = (answer.get("motivo") in settings.FILTER_MOTIVES and evidence is not None
                     and len(dedup.content_words(dedup.normalize(evidence["text"])))
                     >= row_filter.MIN_CLUE_WORDS)
        verdict.destination = SUGERENCIA
        if not supported:
            verdict.doubt_reason = "descarte_sin_sustento"
            verdict.anomaly = row_filter.ANOMALY_NOT_SUPPORTED
            return verdict
        if answer["motivo"] == row_filter.OPTIONAL_MOTIVE and getattr(row.found, "option", ""):
            verdict.doubt_reason = "no_coinciden"
            verdict.anomaly = row_filter.ANOMALY_OPTION_DISCARDED
            return verdict
        verdict.destination = DESCARTADA
        verdict.reason = answer["motivo"]
        return verdict

    def filter_rows(self, rows):
        verdicts = [self._verdict(row) for row in rows]
        row_filter.protect_shared_sentences(verdicts)
        for verdict in verdicts:
            if verdict.destination == SUGERENCIA and not settings.SUGGESTIONS_ENABLED:
                verdict.destination = FIRME
                verdict.anomaly = verdict.anomaly or "filtro_sugerencias_apagadas"
        # Las mismas cuentas que el filtro local (`filter.Filter._count` solo usa `stats` y
        # `steps`).
        row_filter.Filter._count(self, rows, verdicts)
        return row_filter.Result(verdicts=verdicts, steps=self.steps, anomalies=self.anomalies,
                                 stats=self.stats)


# --- La etapa ------------------------------------------------------------------------------------


@dataclass
class Row:
    """Una fila mandada al control: su alias (`F1`…), la unidad y el `Found`."""

    alias: str
    unit: object
    found: object


class Stage:
    """Los pedidos externos de una propuesta (`MatrixRun`). `loaded` es lo que cargó
    `run.load`; `numbers`, los renglones del pliego. `measurement` (la medición) delimita el reuso
    por huella y el freno de la etapa en el libro."""

    def __init__(self, run, loaded, numbers, *, measurement=None, user=None, channel=None):
        self.run = run
        self.loaded = loaded
        self.numbers = list(numbers)
        self.measurement = measurement
        self.user = user
        self.channel = channel
        self.instruction = load_instruction()
        self.mode = settings.EXTERNAL_MODE
        self.sent = []
        self.steps = []
        self.anomalies = []
        self.extraction_requests = 0
        self._batch = {PassName.EXTRACCION: 0, PassName.COMPLETITUD: 0}
        self._system = self._prefix()

    # --- armado

    def _prefix(self):
        """El sistema común: la instrucción y el pliego completo, tramo por tramo con su origen."""
        pieces = [guard.instruction(f"{self.instruction.text.rstrip()}\n\nPLIEGO COMPLETO\n\n")]
        for unit in self.loaded.units:
            document = self.loaded.reading_of[unit.segment.pk].document
            pieces.append(guard.tender_document(
                document, extraction.render_block(alias_of(unit), unit) + "\n\n"))
        return pieces

    def _document(self, unit):
        return self.loaded.reading_of[unit.segment.pk].document

    def _build(self, stage, custom_id, message, schema):
        instruction = self.instruction
        result = guard.build(
            stage=stage, custom_id=custom_id, procedure=self.run.procedure_id,
            system=self._system, messages=[("user", message)], max_tokens=MAX_TOKENS,
            output_schema=schema, cache_system_ttl=CACHE_TTL, run_kind=RUN_KIND,
            run_id=self.run.pk, instruction_name=instruction.name,
            instruction_version=instruction.version, instruction_sha256=instruction.sha256,
            definitions_version=instruction.definitions[0],
            definitions_sha256=instruction.definitions[1], measurement=self.measurement,
            channel=self.channel, user=self.user)
        if result.blocked:
            raise Unavailable("bloqueado", [{
                "type": ANOMALY_BLOCKED, "etapa": stage, "custom_id": custom_id,
                "motivo": result.reason, "motivos": list(result.reasons),
                "hecho": result.event_id}])
        return result

    def _send(self, admitted):
        sent = ledger.send(admitted, measurement=self.measurement, mode=self.mode,
                           channel=self.channel, user=self.user)
        self.sent.append(sent)
        problems = [{"type": entry.get("anomalia", ANOMALY_UNAVAILABLE),
                     **{k: v for k, v in entry.items() if k != "anomalia"}}
                    for entry in sent.anomalies]
        failed = [answer for answer in sent.answers.values() if not answer.ok]
        if sent.stage_stopped or failed or problems:
            reason = ("etapa_frenada" if sent.stage_stopped
                      else (failed[0].reason or failed[0].outcome) if failed else "anomalia")
            if sent.stage_stopped and not any(p["type"] == ANOMALY_STOPPED for p in problems):
                problems.append({"type": ANOMALY_STOPPED, "etapa": sent.stage,
                                 "gasto_usd": float(sent.spent_stage_usd)})
            raise Unavailable(reason, problems)
        return sent

    def _record(self, pass_name, answer, keys, *, request, parsed, anomalies, seconds):
        self._batch[pass_name] += 1
        result = answer.result
        usage = getattr(result, "usage", None)
        step = RunStep.objects.create(
            run=self.run, pass_name=pass_name, batch=self._batch[pass_name], segment_keys=keys,
            request={"externo": {**request, "custom_id": answer.custom_id,
                                 "hecho": answer.event_id, "resultado": answer.outcome,
                                 "modo": self.mode,
                                 "lote_id": getattr(result, "batch_id", None)}},
            raw_output=answer.text,
            parsed={**parsed, "hecho": answer.event_id,
                    "instruccion": self.instruction.record},
            anomalies=anomalies,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": getattr(usage, "input_tokens", None),
                     "completion_tokens": getattr(usage, "output_tokens", None)})
        self.steps.append(step)
        return step

    # --- (a) extracción

    def extract(self, units):
        """Los pedidos de extracción de `units` (los tramos que no decide una regla), en un solo
        envío. Devuelve una `extraction.Extraction`. Lanza `Unavailable`."""
        chunks = split(units)
        self.extraction_requests = len(chunks)
        outcomes, anomalies = {}, []
        if not chunks:
            return extraction.Extraction(outcomes={}, steps=[], anomalies=[],
                                         stats=self._extraction_stats(0))
        schema = extraction_schema(self.numbers)
        admitted = []
        for number, chunk in enumerate(chunks, start=1):
            aliases = ", ".join(alias_of(unit) for unit in chunk)
            message = guard.instruction(
                "PEDIDO DE EXTRACCIÓN\n\n"
                f"Tramos que decidís en este pedido: {aliases}.\n"
                'Devolvé el objeto JSON con un elemento de "tramos" por cada uno.')
            admitted.append(self._build(STAGE_EXTRACTION, f"matriz-{self.run.pk}-x{number}",
                                        message, schema))
        started = time.monotonic()
        sent = self._send(admitted)
        seconds = time.monotonic() - started
        parsed_chunks = []
        for item, chunk in zip(admitted, chunks):
            answer = sent.answers[item.custom_id]
            asked = {alias_of(unit): unit for unit in chunk}
            data = _load(answer.text, ("tramos",))
            if data is None:
                raise Unavailable("salida_invalida", [{
                    "type": ANOMALY_INVALID, "etapa": STAGE_EXTRACTION,
                    "custom_id": item.custom_id, "hecho": answer.event_id}])
            parsed_chunks.append((answer, chunk, asked, data))
        for answer, chunk, asked, data in parsed_chunks:
            step_anomalies = []
            by_alias = _by_alias(data["tramos"], "tramo", asked, step_anomalies,
                                 lambda alias: asked[alias].segment.pk)
            chunk_outcomes, parsed = [], {}
            for alias, unit in asked.items():
                outcome = self._outcome(unit, by_alias.get(alias), step_anomalies)
                chunk_outcomes.append(outcome)
                parsed[alias] = self._parsed(outcome)
            step = self._record(PassName.EXTRACCION, answer, [u.segment.key for u in chunk],
                                request={"etapa": STAGE_EXTRACTION,
                                         "tramos": list(asked)},
                                parsed={"tramos": parsed}, anomalies=step_anomalies,
                                seconds=seconds)
            for outcome in chunk_outcomes:
                outcome.step = step
                for found in outcome.found:
                    found.step = step
                outcomes[outcome.unit.segment.pk] = outcome
            anomalies.extend(step_anomalies)
        return extraction.Extraction(outcomes=outcomes, steps=list(self.steps),
                                     anomalies=anomalies,
                                     stats=self._extraction_stats(len(chunks)))

    def _extraction_stats(self, requests):
        return {"requests": requests, "split_batches": 0, "segments_retried": 0,
                "quotes_retried": 0, "wide_quotes": 0, "long_units": 0, "steps": requests}

    def _outcome(self, unit, raw, anomalies):
        """El `extraction.Outcome` de un tramo con lo que respondió el modelo (`None`: no
        respondió)."""
        outcome = extraction.Outcome(unit=unit)
        if raw is None:
            anomalies.append({"type": ANOMALY_MISSING_SEGMENT, "segment": unit.segment.pk,
                              "key": unit.segment.key})
            return outcome
        body = {key: value for key, value in raw.items() if key != "tramo"}
        outcome.raw = body
        try:
            item = extraction.shape_item(body)
        except extraction.InvalidItem as error:
            anomalies.append({"type": extraction.ANOMALY_INVALID_OUTPUT,
                              "segment": unit.segment.pk, "detail": str(error)})
            outcome.problem = str(error)
            return outcome
        item.technical = [mark for mark in item.technical
                          if mark == extraction.ALL_ITEMS or mark in self.numbers]
        outcome.item = item
        if not item.has_disposition:
            anomalies.append({"type": extraction.ANOMALY_NO_DISPOSITION,
                              "segment": unit.segment.pk})
            return outcome
        found = resolve(unit, item, anomalies)
        if item.quotes and not found and not item.technical:
            # Ninguna cita se ubicó: el tramo queda sin disposición (pendiente de revisión), no
            # descartado en silencio.
            anomalies.append({"type": extraction.ANOMALY_NO_DISPOSITION,
                              "segment": unit.segment.pk, "detail": "ninguna cita ubicada"})
            return outcome
        outcome.valid = True
        outcome.found = found
        outcome.technical = list(item.technical)
        outcome.discard = item.discard
        return outcome

    @staticmethod
    def _parsed(outcome):
        if outcome.item is None:
            return {"segmento": outcome.unit.segment.pk, "valida": False}
        text = outcome.unit.segment.text
        return {"segmento": outcome.unit.segment.pk, "valida": outcome.valid,
                extraction.KEY_REQUIREMENTS: [_found_record(f, text) for f in outcome.found],
                extraction.KEY_TECHNICAL: list(outcome.item.technical),
                extraction.KEY_DISCARD: outcome.item.discard}

    # --- (b) completitud y filtro

    def complete_and_filter(self, candidates, rows):
        """El pedido de completitud y filtro. `candidates` son los tramos donde puede faltar algo
        (`completeness.Candidate`: los que el modelo decidió con requisitos o descartó, con todas
        sus filas), `rows` los `(unidad, Found)` de las filas que pasan por el filtro. Devuelve
        `(completeness.Completion, ExternalFilter)`. Lanza `Unavailable`."""
        rows = [Row(f"F{n}", unit, found) for n, (unit, found) in enumerate(rows, start=1)]
        open_by_alias = {alias_of(c.unit): c for c in candidates}
        message = [guard.instruction(
            "PEDIDO DE COMPLETITUD Y FILTRO\n\n"
            f"Tramos decididos: {', '.join(open_by_alias) or 'ninguno'}.\n\n"
            "Filas ya extraídas:\n\n")]
        for row in rows:
            option = getattr(row.found, "option", "")
            label = _CLASS_LABELS.get(row.found.category, row.found.category)
            message.append(guard.instruction(
                f"[{row.alias}] Tramo: {alias_of(row.unit)} · Clase: {label}"
                + (f" · Opción: {option}" if option else "") + "\nCita: "))
            text = row.unit.segment.text[row.found.span[0]:row.found.span[1]]
            message.append(guard.tender_document(self._document(row.unit), quotes.visible(text)))
            message.append(guard.instruction(f"\n[/{row.alias}]\n\n"))
        if not rows:
            message.append(guard.instruction("(ninguna)\n\n"))
        message.append(guard.instruction(
            'Devolvé el objeto JSON con "faltantes" y un elemento de "filas" por cada fila.'))
        admitted = [self._build(STAGE_COMPLETION, f"matriz-{self.run.pk}-cf", message,
                                completion_schema())]
        started = time.monotonic()
        sent = self._send(admitted)
        seconds = time.monotonic() - started
        answer = sent.answers[admitted[0].custom_id]
        data = _load(answer.text, ("faltantes", "filas"))
        if data is None:
            raise Unavailable("salida_invalida", [{
                "type": ANOMALY_INVALID, "etapa": STAGE_COMPLETION,
                "custom_id": admitted[0].custom_id, "hecho": answer.event_id}])
        anomalies = []
        added = self._missing(data["faltantes"], open_by_alias, anomalies)
        row_answers = self._row_answers(data["filas"], rows, anomalies)
        keys = list(dict.fromkeys([c.unit.segment.key for c in candidates]
                                  + [r.unit.segment.key for r in rows]))
        step = self._record(
            PassName.COMPLETITUD, answer, keys,
            request={"etapa": STAGE_COMPLETION, "filas": len(rows),
                     "tramos": list(open_by_alias)},
            parsed={"faltantes": {
                        alias: [{**_found_record(f, open_by_alias[alias].unit.segment.text),
                                 "destino": destination} for f, destination in entries]
                        for alias, entries in added.items()},
                    "filas": {row.alias: {"segmento": row.unit.segment.pk,
                                          **(row_answers.get(id(row.found)) or {"valida": False})}
                              for row in rows}},
            anomalies=anomalies, seconds=seconds)
        results = {}
        answers = dict(row_answers)
        for alias, entries in added.items():
            candidate = open_by_alias[alias]
            for found, destination in entries:
                found.step = step
                answers[id(found)] = {"destino": destination, "motivo": "", "indicio": "",
                                      "razonamiento": "", "origen": "externo",
                                      "pasada": "completitud"}
            final = sorted([*candidate.found, *(found for found, _ in entries)],
                           key=lambda f: f.span[0])
            results[candidate.unit.segment.pk] = completeness.Result(
                unit=candidate.unit, found=final, valid=True, added=len(entries), step=step)
        completion = completeness.Completion(
            results=results, steps=[step], anomalies=anomalies,
            stats={"requests": 1, "segments": len(candidates),
                   "added": sum(len(entries) for entries in added.values()), "invalid": 0,
                   "split_batches": 0, "segments_retried": 0, "steps": 1})
        return completion, ExternalFilter(answers, step)

    def _missing(self, entries, open_by_alias, anomalies):
        """`{alias: [(Found, destino)]}`: los faltantes ubicados en un tramo decidido, sin repetir
        una fila que ya está."""
        added = {}
        for entry in entries:
            if (not isinstance(entry, dict)
                    or set(entry) != {"tramo", "cita", "clase", "opcion", "destino"}
                    or not isinstance(entry["cita"], str)
                    or entry["clase"] not in extraction.BODY_CLASSES
                    or entry["opcion"] not in ("", *extraction.OPTIONS)
                    or entry["destino"] not in ADDED_DESTINATIONS):
                anomalies.append({"type": ANOMALY_INVALID, "etapa": STAGE_COMPLETION,
                                  "detail": "un faltante no tiene la forma pedida"})
                continue
            candidate = open_by_alias.get(entry["tramo"])
            if candidate is None:
                anomalies.append({"type": ANOMALY_OUT_OF_SCOPE,
                                  "alias": str(entry["tramo"])[:20]})
                continue
            unit = candidate.unit
            category = _category(unit, entry["clase"])
            located = quotes.locate_unit(unit.segment.text, entry["cita"].strip(),
                                         expand=extraction.expands(unit))
            if located is None:
                anomalies.append(_not_located(unit, category, "completitud"))
                continue
            fragment, expansion = located
            new = extraction.found_from(category, fragment, expansion, entry["opcion"])
            existing = [*candidate.found, *(found for found, _ in added.get(entry["tramo"], []))]
            if any(same_requirement(new, old) for old in existing):
                continue
            if expansion.too_long:
                anomalies.append({"type": extraction.ANOMALY_UNIT_TOO_LONG,
                                  "segment": unit.segment.pk, "key": unit.segment.key,
                                  "clase": category})
            new.passes = [PassName.COMPLETITUD.value]
            added.setdefault(entry["tramo"], []).append((new, entry["destino"]))
        return added

    def _row_answers(self, entries, rows, anomalies):
        """`{id(Found): respuesta}` de las filas: la respuesta con la forma pedida, o nada."""
        by_alias = {row.alias: row for row in rows}
        found = _by_alias(entries, "fila", by_alias, anomalies,
                          lambda alias: by_alias[alias].unit.segment.pk)
        answers = {}
        for alias, entry in found.items():
            if (set(entry) != {"fila", "destino", "motivo", "indicio", "razonamiento"}
                    or entry["destino"] not in DESTINATIONS
                    or not all(isinstance(entry[k], str)
                               for k in ("motivo", "indicio", "razonamiento"))):
                anomalies.append({"type": ANOMALY_INVALID, "etapa": STAGE_COMPLETION,
                                  "alias": alias, "detail": "la fila no tiene la forma pedida"})
                continue
            answers[id(by_alias[alias].found)] = {
                "destino": entry["destino"], "motivo": entry["motivo"],
                "indicio": entry["indicio"], "razonamiento": entry["razonamiento"],
                "origen": "externo"}
        return answers

    # --- registro

    def record(self, ran):
        """Lo que la propuesta guarda en su clave `externo` (plan 016, «Modelo de datos»; contrato
        de T-300): `models` (etapas, proveedor y modelo), `parameters` (modo y parámetros),
        `prompt_versions` (instrucción y huellas) y `counts` (pedidos y gasto). `ran` dice si la
        matriz quedó hecha por el modelo externo (si volvió a lo local, la etapa es `local`)."""
        model = settings.EXTERNAL_MODELS[STAGE]
        by_stage = {sent.stage: sent.summary() for sent in self.sent}
        requests = sum(summary["pedidos"] for summary in by_stage.values())
        spent = sum((sent.cost_usd for sent in self.sent), Decimal(0))
        stages = {name: "local" for name in settings.EXTERNAL_STAGE_NAMES}
        stages[STAGE] = "externo" if ran else "local"
        own = {"proveedor": client.PROVIDER, "modelo": model}
        instruction = self.instruction
        return {
            "models": {"habilitado": True, "etapas": stages, **own, STAGE: dict(own)},
            "parameters": {"modo": self.mode, STAGE: {
                "modo": self.mode, "effort": settings.EXTERNAL_EFFORT.get(STAGE),
                "thinking": settings.EXTERNAL_THINKING.get(STAGE), "max_tokens": MAX_TOKENS,
                "cache_system_ttl": CACHE_TTL, "tramos_por_pedido": SEGMENTS_PER_REQUEST,
                "pedidos_extraccion": self.extraction_requests,
                "medicion": self.measurement,
                "reemplaza": list(REPLACED_PASSES) if ran else []}},
            "prompt_versions": {STAGE: instruction.version,
                                extraction.DEFINITIONS_NAME: instruction.definitions[0],
                                "huellas": {STAGE: instruction.sha256,
                                            extraction.DEFINITIONS_NAME:
                                                instruction.definitions[1]}},
            "counts": {STAGE: {"pedidos": requests, "gasto_usd": float(spent),
                               "volvio_a_local": not ran, "por_etapa": by_stage}},
        }
