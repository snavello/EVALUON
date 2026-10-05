"""El modelo extrae la lista de cambios de una unidad de circular (REQ-031, REQ-028; plan 003,
"Rediseño de la pasada de circulares", entrega 2; ADR-0023; T-115).

La entrega 1 (`circular_units`) resuelve por clave lo que la circular dice con precisión; lo
que no tiene clave ("la memoria RAM del equipo", respuestas a consultas sin número) llegaba
al flujo de respaldo, donde el modelo elegía la cita del pliego entre candidatas. Acá el
modelo hace otra cosa: lee **solo la unidad de la circular, sin ver el pliego**, y devuelve
una lista estructurada de cambios (`cambios`: tipo, objetivo, referencia, texto anterior y
texto nuevo). El código resuelve cada cambio contra el pliego con las mismas reglas de la
entrega 1; el modelo no elige citas del pliego.

**Citas literales.** `texto_anterior` y `texto_nuevo` se copian de la unidad y se buscan en
ella (`quotes.locate`). Si alguno no está, se vuelve a pedir una vez; si sigue sin estar, el
cambio no se aplica y queda registrado (`circular_cambio_cita_inexistente`).

**Estabilidad.** Con `CIRCULAR_EXTRACTION_REPEATS` mayor que 1 el pedido se repite y se
comparan las listas: el cambio que aparece igual (tipo, objetivo, referencia y textos) en
todas las repeticiones se acepta; el que difiere queda no estable, no se aplica en firme y va
al respaldo con la anomalía (`circular_cambio_no_estable`).

**Respaldo.** Un cambio sin objetivo resoluble, no estable o sin cita verificable pasa al
flujo de candidatas de `circulars.Processor`, restringido a los tramos de la unidad donde está
ese cambio. Si el modelo falla, devuelve algo inválido o no encuentra cambios, toda la unidad
va al respaldo: nada se pierde.

Este módulo no toca el pliego ni escribe requisitos: devuelve un `Extraction` y
`circulars.Processor` lo aplica. Todo pedido queda en `tenders_run_step`
(`circulares_cambios`) con el modelo, los parámetros, la versión de las instrucciones y la
unidad (P6).
"""

import json
import re
import time
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.models import PassName, RequirementClass, RunStep, SourceEffect
from evaluon.tenders.proposal import circular_units as units
from evaluon.tenders.proposal import circulars, extraction, quotes

TYPES = (units.CHANGE_REPLACES, units.CHANGE_SUPPRESSES, units.CHANGE_ADDS,
         units.CHANGE_CLARIFIES, units.CHANGE_DATA)
TARGETS = ("clausula", "anexo", "renglon", "ninguno")

ANOMALY_SERVICE = "servicio"
ANOMALY_INVALID = "circular_cambios_salida_invalida"
ANOMALY_QUOTE_NOT_FOUND = "circular_cambio_cita_inexistente"
ANOMALY_UNSTABLE = "circular_cambio_no_estable"
ANOMALY_NO_CHANGES = "circular_cambios_vacios"
ANOMALY_NO_FIT = "circular_unidad_no_entra"
ANOMALY_UNRESOLVED = "circular_cambio_sin_resolver"

REASON_NOT_VERIFIED = "cita_inexistente"
REASON_UNSTABLE = "no_estable"

_ANNEX_NUMBER = re.compile(r"^(?:[ivxlc]+|\d+)$")


class InvalidOutput(ValueError):
    """Lo que el modelo devolvió no tiene la forma del esquema."""


# --- Pedido ------------------------------------------------------------------------------------


def build_schema():
    """Esquema de la salida: `cambios`, cada uno con los cinco campos obligatorios."""
    return {
        "type": "object",
        "properties": {
            "cambios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string", "enum": list(TYPES)},
                        "objetivo": {"type": "string", "enum": list(TARGETS)},
                        "referencia": {"type": "string"},
                        "texto_anterior": {"type": "string"},
                        "texto_nuevo": {"type": "string"},
                    },
                    "required": ["tipo", "objetivo", "referencia", "texto_anterior",
                                 "texto_nuevo"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["cambios"],
        "additionalProperties": False,
    }


def render_unit(document, change, text):
    """La unidad tal como la ve el modelo: el documento y su texto; nada del pliego."""
    doc = document.document
    first = change.members[0].segment
    return "\n".join([
        f"Documento: {doc.title} ({doc.get_kind_display()}), del "
        f"{doc.issued_on.strftime('%d/%m/%Y')}",
        f"Ruta: {first.path or first.label or first.key}",
        "Texto:", text,
    ])


def build_messages(prompt, block):
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": block + "\n\nDevolvé un objeto JSON con cambios."}]


# --- Salida ----------------------------------------------------------------------------------


@dataclass
class Change:
    """Un cambio que el modelo extrajo de la unidad. `old_span` y `new_span` son las posiciones
    absolutas de sus textos en la lectura de la circular (`None` si no se dieron o no se
    encontraron)."""

    type: str
    target: str
    reference: str
    old_text: str
    new_text: str
    old_span: tuple | None = None
    new_span: tuple | None = None
    unfound: bool = False
    reason: str = ""

    @property
    def signature(self):
        return (self.type, self.target, circulars.fold(" ".join(self.reference.split())),
                _norm(self.old_text), _norm(self.new_text))

    def spans(self):
        return [s for s in (self.old_span, self.new_span) if s is not None]

    def record(self):
        return {"tipo": self.type, "objetivo": self.target, "referencia": self.reference,
                "texto_anterior": self.old_text, "texto_nuevo": self.new_text,
                "ubicado": not self.unfound, "motivo": self.reason}


def _norm(text):
    return " ".join(circulars.fold(text).split())


def shape(raw):
    """Comprueba la forma de lo devuelto y lo pasa a `Change`. Lanza `InvalidOutput`."""
    if not isinstance(raw, dict) or set(raw) != {"cambios"} or not isinstance(raw["cambios"],
                                                                              list):
        raise InvalidOutput("no es un objeto con la lista cambios")
    fields = {"tipo", "objetivo", "referencia", "texto_anterior", "texto_nuevo"}
    out = []
    for entry in raw["cambios"]:
        if (not isinstance(entry, dict) or set(entry) != fields
                or not all(isinstance(v, str) for v in entry.values())
                or entry["tipo"] not in TYPES or entry["objetivo"] not in TARGETS):
            raise InvalidOutput("un cambio no tiene los cinco campos con tipo y objetivo "
                                "válidos")
        out.append(Change(entry["tipo"], entry["objetivo"], entry["referencia"].strip(),
                          entry["texto_anterior"].strip(), entry["texto_nuevo"].strip()))
    return out


def _locate(change, text, base, anomalies, key):
    """Ubica los dos textos del cambio dentro de la unidad; marca `unfound` si alguno dado
    no está."""
    for name in ("old", "new"):
        value = getattr(change, f"{name}_text")
        if not value:
            continue
        span = quotes.locate(text, value)
        if span is None:
            change.unfound = True
            anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND, "segmento": key,
                              "texto": name})
        else:
            setattr(change, f"{name}_span", (base + span[0], base + span[1]))


def _dedupe(changes):
    seen, out = set(), []
    for change in changes:
        if change.signature not in seen:
            seen.add(change.signature)
            out.append(change)
    return out


# --- Resultado -----------------------------------------------------------------------------------


@dataclass
class Extraction:
    """Lo que la extracción hizo con una unidad: la resolución por clave de los cambios
    estables (`resolution`, con `effects` y `additions`), los tramos que quedan para el
    respaldo y los de datos del trámite, y el pedido que los respalda."""

    resolution: object
    changes: list
    step: object
    fallback_members: list = field(default_factory=list)
    data_members: list = field(default_factory=list)
    applied: int = 0


# --- Resolución de un cambio contra el pliego, por clave -----------------------------------------


def _annex_filters(reference):
    """`(números, títulos)` del anexo que nombra la referencia: "VI", "Anexo 2" o un título."""
    folded = circulars.fold(reference).strip()
    folded = re.sub(r"^anexo\s*", "", folded).strip(" .")
    if _ANNEX_NUMBER.match(folded):
        return {folded}, set()
    if len(folded.split()) >= 2:
        return set(), {folded}
    return set(), set()


def _from_old_text(change, pool, fallback_reason):
    """Las citas de `pool` que el texto anterior designa; `(citas, motivo)`."""
    if not change.old_text:
        return [], fallback_reason
    return units.match_old_text(units._without_names(change.old_text), pool)


def _pool_for(ctx, change):
    """Las citas que alcanza el cambio según su objetivo y referencia; `(citas, motivo)`."""
    candidates = ctx.candidates
    kind, reference = change.target, change.reference
    if kind == "clausula":
        numbers = set(re.findall(circulars._NUMBER, reference))
        if not numbers:
            return [], units.FALLBACK_NO_TARGET
        found, reason = units._resolve_clauses(ctx, numbers)
        if reason:
            return [], reason
        if change.old_text:
            matched, reason = units.match_old_text(units._without_names(change.old_text), found)
            if not reason:
                return matched, ""
            if len(found) == 1:
                return found, ""
            return [], reason
        # T-128: una aclaración sin texto anterior se aplica a todas las citas de la cláusula
        # (decisión del responsable, 2026-10-05).
        return found, ""
    if kind == "renglon":
        items = {int(n) for n in re.findall(r"\d+", reference)}
        if not items:
            return [], units.FALLBACK_NO_TARGET
        pool = units._item_candidates(candidates, items)
        if not pool:
            return [], units.FALLBACK_MISSING_KEY
        if change.old_text:
            return units.match_old_text(units._without_names(change.old_text), pool)
        # T-129: una aclaración de renglón sin texto anterior alcanza las citas del renglón,
        # con el mismo criterio que la cláusula y el anexo (T-128).
        if change.type in (units.CHANGE_SUPPRESSES, units.CHANGE_CLARIFIES):
            return pool, ""
        return [], units.FALLBACK_NO_OLD_TEXT
    if kind == "anexo":
        annexes, titles = _annex_filters(reference)
        if not annexes and not titles:
            return [], units.FALLBACK_NO_TARGET
        pool = [c for c in candidates
                if units._in_annex(c, annexes) or units._asks_for_annex(c, annexes, titles)]
        if not pool:
            return [], units.FALLBACK_ZERO
        if (change.type in (units.CHANGE_SUPPRESSES, units.CHANGE_CLARIFIES)
                and not change.old_text):
            return pool, ""
        return _from_old_text(change, pool, units.FALLBACK_NO_OLD_TEXT)
    pool = [c for c in candidates if not units._is_shared(c)]
    # T-137: bajo el encabezado de un renglón, el texto anterior se busca en ese renglón.
    pool = units.restrict_to_scope(ctx, pool)
    return _from_old_text(change, pool, units.FALLBACK_NO_TARGET)


def resolve_change(ctx, change, anomalies=None):
    """Aplica un cambio por clave: `(efectos, nuevos, motivo)`. Con motivo, el cambio no se
    resolvió y va al respaldo."""
    document = ctx.document
    unit = ctx.unit
    canonical = document.reading.canonical_text

    if change.type == units.CHANGE_DATA:
        # T-137: fecha, hora y lugar que el pliego fija en una cláusula (la visita) precisan esa
        # condición; con dos cláusulas posibles, el respaldo.
        found, ambiguous = units.data_clause_candidates(ctx)
        if ambiguous:
            return [], [], units.FALLBACK_AMBIGUOUS
        span = units.data_clause_span(ctx)
        return [units._effect(unit, document, candidate, SourceEffect.MODIFICA.value, *span)
                for candidate in found], [], ""
    if (change.type == units.CHANGE_CLARIFIES and change.new_text
            and units.is_title_text(change.new_text)):
        # T-137: el título de una carátula no es una aclaración.
        # Ante la duda no se descarta en silencio: las filas que nombra quedan a revisión.
        if anomalies is not None:
            pool, reason = _pool_for(ctx, change)
            anomalies.append({
                "type": circulars.ANOMALY_TITLE_NOT_CLARIFICATION, "review_required": True,
                "tramos": unit.keys, "referencia": change.reference,
                "circular": f"{document.document.title} "
                            f"({document.document.issued_on.strftime('%d/%m/%Y')})",
                "requirements": [] if reason else sorted(
                    {t.number for c in pool for t in c.targets
                     if circulars.shares_topic(change.new_text, c.text)})})
        return [], [], ""
    if change.type == units.CHANGE_ADDS:
        if change.target != "clausula":
            return [], [], units.FALLBACK_NO_TARGET
        numbers = set(re.findall(circulars._NUMBER, change.reference))
        if not numbers:
            return [], [], units.FALLBACK_NO_TARGET
        existing = ctx.pliego.numbers
        if any(n in existing or any(p.startswith(n + ".") for p in existing)
               for n in numbers):
            return [], [], units.FALLBACK_EXISTING_KEY
        if change.new_span is None:
            return [], [], units.FALLBACK_NO_NEW_TEXT
        start, end = change.new_span
        return [], [units.Addition(RequirementClass.FORMAL.value,
                                   units._segment_at(unit, start), start, end,
                                   canonical[start:end])], ""

    targets, reason = _pool_for(ctx, change)
    if reason:
        return [], [], reason
    if not targets:
        return [], [], units.FALLBACK_ZERO
    if change.type == units.CHANGE_REPLACES:
        if change.new_span is None:
            return [], [], units.FALLBACK_NO_NEW_TEXT
        effect, span = SourceEffect.MODIFICA.value, change.new_span
    else:
        effect = (SourceEffect.SUPRIME if change.type == units.CHANGE_SUPPRESSES
                  else SourceEffect.ACLARA).value
        span = change.new_span or units._span_of_head(ctx)
        if (effect == SourceEffect.SUPRIME.value
                and not circulars.has_suppression_phrase(canonical[span[0]:span[1]])):
            # T-127/T-128: sin frase explícita no hay supresión firme: queda `aclara`, con
            # revisión obligatoria (P3).
            effect = SourceEffect.ACLARA.value
            if anomalies is not None:
                anomalies.append({
                    "type": circulars.ANOMALY_SUPPRESSION_WITHOUT_PHRASE,
                    "tramos": unit.keys, "tipo": change.type, "objetivo": change.target,
                    "referencia": change.reference, "returned": SourceEffect.SUPRIME.value,
                    "result": effect, "text": canonical[span[0]:span[1]],
                    "review_required": True,
                    "circular": f"{document.document.title} "
                                f"({document.document.issued_on.strftime('%d/%m/%Y')})",
                    "requirements": sorted({t.number for c in targets for t in c.targets})})
    return [units._effect(unit, document, candidate, effect, *span)
            for candidate in targets], [], ""


# --- La extracción de una unidad -----------------------------------------------------------------------


class Extractor:
    """Los pedidos de extracción de una propuesta: usa el `Processor` de las circulares para
    numerar los pasos, guardarlos y contar."""

    pass_name = PassName.CIRCULARES_CAMBIOS

    def __init__(self, processor):
        self.processor = processor
        self.prompt = extraction.load_prompt("circulares_cambios")
        self.version = settings.MATRIX_PROMPT_VERSIONS["circulares_cambios"]
        # T-137: por qué la unidad que se acaba de extraer pudo perder un cambio.
        self.loss = []

    # -- Pedidos --------------------------------------------------------------------------

    def _record(self, change_unit, messages, schema, max_tokens, output, parsed, anomalies,
                retry_of, seconds, repetition):
        processor = self.processor
        processor._batch += 1
        if output is None:
            request = generation.build_request(messages, schema, max_tokens)
            content, prompt_tokens, completion_tokens = "", None, None
        else:
            request, content = output.request, output.content
            prompt_tokens, completion_tokens = output.prompt_tokens, output.completion_tokens
        request = dict(request, instrucciones=self.version, repeticion=repetition,
                       unidad={"tipo": change_unit.kind, "tramos": change_unit.keys})
        step = RunStep.objects.create(
            run=processor.run, pass_name=self.pass_name, batch=processor._batch,
            segment_keys=change_unit.keys, request=request, raw_output=content,
            parsed=parsed, anomalies=anomalies, retry_of=retry_of,
            timings={"seconds": round(seconds, 3), "prompt_tokens": prompt_tokens,
                     "completion_tokens": completion_tokens})
        processor.steps.append(step)
        return step

    def _ask(self, document, change_unit, text, messages, retry_of, repetition):
        """Un pedido. Devuelve `(cambios, paso, no_ubicados)` o `None` si el servicio falló o
        la salida es inválida (queda registrado)."""
        schema = build_schema()
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens)
        except AIServiceError as error:
            step = self._record(
                change_unit, messages, schema, max_tokens, None, None,
                [{"type": ANOMALY_SERVICE, "reason": error.reason, "service": error.service,
                  "message": str(error)}], retry_of, time.monotonic() - started, repetition)
            return None, step, 0
        seconds = time.monotonic() - started
        self.processor.stats["extraction_requests"] += 1
        anomalies, changes = [], None
        try:
            changes = _dedupe(shape(json.loads(output.content)))
        except ValueError as error:   # `InvalidOutput` es un `ValueError`
            anomalies.append({"type": ANOMALY_INVALID, "detail": str(error),
                              "finish_reason": output.finish_reason})
        unfound = 0
        parsed = {"valida": changes is not None, "finish_reason": output.finish_reason}
        if changes is not None:
            for change in changes:
                _locate(change, text, change_unit.start, anomalies, change_unit.keys[0])
            unfound = sum(1 for c in changes if c.unfound)
            parsed["cambios"] = [c.record() for c in changes]
        step = self._record(change_unit, messages, schema, max_tokens, output, parsed,
                            anomalies, retry_of, seconds, repetition)
        return changes, step, unfound

    def _repetition(self, document, change_unit, text, messages, repetition):
        """Un pedido con un reintento si no tiene la forma o una cita no está. Devuelve
        `(cambios, paso)`; `cambios` es `None` si no hay una salida válida."""
        first, first_step, first_unfound = self._ask(document, change_unit, text, messages,
                                                     None, repetition)
        if first is not None and not first_unfound:
            return first, first_step
        self.processor.stats["retried"] += 1
        second, second_step, second_unfound = self._ask(document, change_unit, text,
                                                        messages, first_step, repetition)
        if second is not None and (first is None or len(second) < len(first)):
            # T-137: la salida del primer pedido no sirvió o traía más cambios: el reintento
            # pudo perder alguno.
            if circulars.REVIEW_RETRY_LOST not in self.loss:
                self.loss.append(circulars.REVIEW_RETRY_LOST)
        if second is not None and (first is None or second_unfound <= first_unfound):
            return second, second_step
        return (first, first_step) if first is not None else (second, second_step)

    # -- Una unidad ------------------------------------------------------------------------

    def run(self, document, change_unit, candidates, pliego, fallback_resolution):
        """Extrae y resuelve los cambios de la unidad. Devuelve un `Extraction` o `None` si
        la unidad entera va al respaldo (falla del modelo, salida inválida o sin cambios)."""
        processor = self.processor
        self.loss = []
        text = units.unit_text(change_unit, document)
        messages = build_messages(self.prompt, render_unit(document, change_unit, text))
        space = (processor._space()
                 - generation.count_tokens(messages[-1]["content"]))
        if space < 0:
            processor.anomalies.append({"type": ANOMALY_NO_FIT, "tramos": change_unit.keys})
            self.loss.append(circulars.REVIEW_NO_FIT)
            return None

        repeats = max(1, int(settings.CIRCULAR_EXTRACTION_REPEATS))
        runs, steps = [], []
        for number in range(1, repeats + 1):
            changes, step = self._repetition(document, change_unit, text, messages, number)
            if changes is None:
                served = not any(a.get("type") == ANOMALY_SERVICE for a in step.anomalies)
                self.loss.append(circulars.REVIEW_INVALID if served
                                 else circulars.REVIEW_SERVICE)
                return None
            runs.append(changes)
            steps.append(step)
        first = runs[0]
        if not first:
            processor.anomalies.append({"type": ANOMALY_NO_CHANGES, "tramos": change_unit.keys})
            return None

        stable = set.intersection(*({c.signature for c in run} for run in runs))
        for change in first:
            if change.unfound:
                change.reason = REASON_NOT_VERIFIED
            elif change.signature not in stable:
                change.reason = REASON_UNSTABLE
                processor.stats["changes_unstable"] += 1
                processor.anomalies.append({"type": ANOMALY_UNSTABLE, "tramos": change_unit.keys,
                                            "tipo": change.type, "objetivo": change.target,
                                            "referencia": change.reference})
        for change in (c for run in runs[1:] for c in run if c.signature not in stable):
            processor.anomalies.append({"type": ANOMALY_UNSTABLE, "tramos": change_unit.keys,
                                        "tipo": change.type, "objetivo": change.target,
                                        "referencia": change.reference})
        return self._resolve(document, change_unit, candidates, pliego, first, steps[0],
                             fallback_resolution)

    def _resolve(self, document, change_unit, candidates, pliego, changes, step, base):
        processor = self.processor
        ctx = units._Ctx(change_unit, document, candidates, pliego)
        resolution = units.Resolution(change_unit, units.OUTCOME_APPLIED,
                                      change=",".join(sorted({c.type for c in changes})))
        applied, spans_applied, spans_data, unresolved = 0, [], [], []
        for change in changes:
            if change.reason:
                unresolved.append(change)
                continue
            effects, additions, reason = resolve_change(ctx, change, processor.anomalies)
            if reason:
                change.reason = reason
                unresolved.append(change)
                continue
            if change.type == units.CHANGE_DATA and not effects:
                spans_data.extend(change.spans())
                continue
            resolution.effects.extend(effects)
            resolution.additions.extend(additions)
            spans_applied.extend(change.spans())
            applied += 1
        for change in unresolved:
            processor.stats["changes_unresolved"] += 1
            processor.anomalies.append({"type": ANOMALY_UNRESOLVED, "tramos": change_unit.keys,
                                        "tipo": change.type, "objetivo": change.target,
                                        "referencia": change.reference,
                                        "motivo": change.reason})
        processor.stats["changes_applied"] += applied
        resolution.reason = ",".join(sorted({c.reason for c in unresolved}))
        resolution.record = False
        resolution.target = {"cambios": [c.record() for c in changes], "paso": step.pk}

        def touching(spans):
            return [m for m in change_unit.members
                    if any(s < m.segment.char_end and e > m.segment.char_start
                           for s, e in spans)]

        members = change_unit.members
        fallback = touching([s for c in unresolved for s in c.spans()])
        if unresolved and not fallback:
            # Cambios sin texto ubicado: no se sabe qué tramo es; van los que ningún otro
            # cambio reclamó.
            claimed = touching(spans_applied + spans_data)
            fallback = [m for m in members if m not in claimed]
        data = [m for m in touching(spans_data) if m not in touching(spans_applied)
                and m not in fallback]
        if not applied and not unresolved:
            data = list(members)
        elif not applied:
            # Sin efectos aplicados no hay nada que afirmar de los tramos que sobran.
            fallback = [m for m in members if m not in data]
        return Extraction(resolution, changes, step, fallback, data, applied)
