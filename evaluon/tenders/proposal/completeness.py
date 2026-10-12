"""Pasada de completitud del proceso único (REQ-024, REQ-030; plan 003, "Pasadas";
ADR-0019, decisión 5).

Esta pasada solo cambia cómo se buscan los requisitos formales y económicos; lo técnico lo
arma una regla. Solo trabaja con tramos que pasan por el modelo: los de una sección técnica
se disponen por regla y no llegan acá. La segunda extracción y la unión de las dos
extracciones (nivel "exigente") dejaron de ser parte del proceso (T-100).

Cada requisito que la completitud suma se ubica y se amplía a su unidad de sentido como los de
la extracción (`quotes.locate_unit`; T-234, REQ-101): la oración completa y las oraciones
cortas contiguas del mismo asunto. El fragmento que señaló el modelo y la unidad quedan en el
`parsed` del pedido (P6).

Un requisito de la completitud es el mismo que uno ya encontrado en el tramo solo si una de
las dos citas queda contenida en la otra en al menos el 90 % de sus propios caracteres
(`_same_requirement`); una cita amplia (tramo entero) nunca se reemplaza por un fragmento ni
al revés: solo es la misma que otra cita amplia de su clase. Cada requisito lleva en
`passes` las pasadas que lo encontraron.

**Completitud.** `Completer.complete` recibe, solo para tramos formales y
económicos, cada tramo con sus requisitos ya encontrados (o ninguno, si el modelo lo
descartó y tiene marcadores de obligación) y devuelve los que faltan
(`prompts/matriz-completitud-v4.md`). Ya no divide los requisitos que juntan dos condiciones
(T-236, ADR-0054, regla 3): una fila es una unidad de sentido y las condiciones de una oración
se evalúan juntas. El sistema ubica cada cita
con `quotes.locate`, que tolera espacios y saltos de línea distintos y devuelve posiciones
relativas al tramo; un faltante que es el mismo que un requisito ya encontrado (misma regla de
`_same_requirement`) no se suma; una cita que no se ubica queda con el tramo entero como cita
(`cita_amplia`), porque un requisito nunca se pierde por una cita mal copiada. Un tramo cuya
salida es inválida se vuelve a pedir una vez, solo; si sigue inválido no cambia y quien llama
decide (un descartado con marcadores queda pendiente).
"""

import json
import time
from dataclasses import dataclass

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.models import PassName, RunStep
from evaluon.tenders.proposal import extraction, quotes
from evaluon.tenders.proposal.extraction import BODY_CLASSES, Found

KEY_MISSING = "faltantes"

ANOMALY_CUT = "completitud_salida_cortada"
ANOMALY_INVALID = "completitud_salida_invalida"
ANOMALY_MISSING_ALIAS = "completitud_tramo_sin_propiedad"
ANOMALY_QUOTE_NOT_FOUND = "completitud_cita_no_encontrada"
ANOMALY_NO_RESULT = "completitud_sin_resultado"
ANOMALY_SERVICE = "servicio"
# El paso cuyo razonamiento propio del modelo se enciende en `settings.GENERATION_BATCH_REASONING` (T-253).
REASONING_STEP = "completeness"

CONTAINED = 0.9  # fracción de una cita que tiene que estar dentro de la otra para ser la misma


class InvalidItem(ValueError):
    """La salida de un tramo no tiene la forma del esquema de la completitud."""


# --- Superposición y pasadas de un requisito -------------------------------------------------


def containment(inner, outer):
    """Qué fracción de los caracteres de `inner` (inicio, fin) está dentro de `outer`."""
    shared = min(inner[1], outer[1]) - max(inner[0], outer[0])
    length = inner[1] - inner[0]
    if shared <= 0 or length <= 0:
        return 0.0
    return shared / length


def passes_of(found):
    return list(getattr(found, "passes", None) or [PassName.EXTRACCION.value])



def _same_requirement(new, old):
    """Si `new` es el mismo requisito que `old` del mismo tramo: una de las dos citas queda
    contenida en la otra en al menos el 90 % de sus propios caracteres. Una cita amplia
    (el tramo entero) solo es la misma que otra cita amplia de su clase."""
    if new.flag == quotes.WIDE or old.flag == quotes.WIDE:
        return new.flag == old.flag and new.category == old.category
    return max(containment(new.span, old.span),
               containment(old.span, new.span)) >= CONTAINED


# --- Completitud -----------------------------------------------------------------------------


@dataclass
class Candidate:
    """Un tramo para la completitud con los requisitos ya encontrados (`Found`)."""

    unit: object
    found: list


@dataclass
class Result:
    """Lo que la completitud dijo de un tramo. `valid` es falso si la salida no sirvió
    ni después del reintento: `found` queda como estaba."""

    unit: object
    found: list
    valid: bool = False
    added: int = 0
    step: object = None


@dataclass
class Completion:
    results: dict
    steps: list
    anomalies: list
    stats: dict


def build_schema(aliases):
    """Esquema de la salida: una propiedad obligatoria por alias, con la lista de faltantes."""
    requirement = {
        "type": "object",
        "properties": {
            "cita": {"type": "string", "minLength": 1},
            "clase": {"type": "string", "enum": list(BODY_CLASSES)},
        },
        "required": ["cita", "clase"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {KEY_MISSING: {"type": "array", "items": requirement}},
        "required": [KEY_MISSING],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {alias: item for alias in aliases},
        "required": list(aliases),
        "additionalProperties": False,
    }


def _shape_requirement(entry):
    if (
        not isinstance(entry, dict)
        or set(entry) != {"cita", "clase"}
        or not isinstance(entry["cita"], str)
        or entry["clase"] not in BODY_CLASSES
    ):
        raise InvalidItem("un requisito no es {cita, clase} con clase válida")
    return entry["cita"], entry["clase"]


def shape_item(raw):
    """Comprueba la forma de lo que el modelo devolvió para un tramo y devuelve los
    faltantes, pares `(cita, clase)`. Lanza `InvalidItem`."""
    if not isinstance(raw, dict) or set(raw) != {KEY_MISSING}:
        raise InvalidItem("no es un objeto con faltantes")
    if not isinstance(raw[KEY_MISSING], list):
        raise InvalidItem("faltantes tiene que ser una lista")
    return [_shape_requirement(entry) for entry in raw[KEY_MISSING]]


def _category(unit, kind):
    section = unit.segment.section_class
    return section if section in BODY_CLASSES else kind


def render_block(alias, candidate):
    """El tramo tal como lo ve el modelo: lo del extractor más los requisitos ya
    encontrados, antes del texto."""
    unit, text = candidate.unit, candidate.unit.segment.text
    lines = extraction.render_block(alias, unit).split("\n")
    at = lines.index("Texto:")
    if candidate.found:
        listed = ["Requisitos ya encontrados:"]
        for number, found in enumerate(candidate.found, start=1):
            if found.flag == quotes.WIDE:
                shown = "(el tramo entero)"
            else:
                shown = " ".join(text[found.span[0]:found.span[1]].split())
            listed.append(f"{number}. {shown} ({found.category})")
    else:
        listed = ["Requisitos ya encontrados: ninguno"]
    return "\n".join(lines[:at] + listed + lines[at:])


def build_messages(prompt, aliased):
    blocks = "\n\n".join(render_block(alias, candidate) for alias, candidate in aliased)
    names = ", ".join(alias for alias, _ in aliased)
    user = (
        "Tramos del pliego con los requisitos ya encontrados:\n\n"
        f"{blocks}\n\n"
        f"Devolvé un objeto JSON con una propiedad por cada alias: {names}."
    )
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


def batches(candidates):
    """Lotes de tramos consecutivos de hasta `MATRIX_BATCH_INPUT_TOKENS` tokens."""
    limit = settings.MATRIX_BATCH_INPUT_TOKENS
    result, current, total = [], [], 0
    for candidate in candidates:
        tokens = generation.count_tokens_batch(render_block("T00", candidate))
        if current and total + tokens > limit:
            result.append(current)
            current, total = [], 0
        current.append(candidate)
        total += tokens
    if current:
        result.append(current)
    return result


def apply(unit, found_list, missing, anomalies):
    """Aplica la salida validada de un tramo a sus requisitos ya encontrados. Devuelve
    `(requisitos finales, agregados)`. No modifica `found_list`."""
    segment = unit.segment
    text = segment.text
    final = list(found_list)
    added = 0

    unlocated = []
    for quote, kind in missing:
        category = _category(unit, kind)
        located = quotes.locate_unit(text, quote, expand=extraction.expands(unit))
        if located is None:
            unlocated.append(category)
            anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND, "segment": segment.pk,
                              "key": segment.key, "clase": category})
            continue
        fragment, expansion = located
        new = extraction.found_from(category, fragment, expansion)
        if any(_same_requirement(new, old) for old in final):
            continue
        if expansion.too_long:
            anomalies.append({"type": extraction.ANOMALY_UNIT_TOO_LONG,
                              "segment": segment.pk, "key": segment.key, "clase": category})
        new.passes = [PassName.COMPLETITUD.value]
        final.append(new)
        added += 1
    for wide in extraction.wide_quotes(unit, unlocated, final):
        wide.passes = [PassName.COMPLETITUD.value]
        final.append(wide)
        added += 1
    final.sort(key=lambda f: f.span[0])
    return final, added


class Completer:
    """Hace los pedidos de la completitud de una propuesta (`MatrixRun`) y guarda cada uno
    en `tenders_run_step`."""

    pass_name = PassName.COMPLETITUD

    def __init__(self, run):
        self.run = run
        self.instruction = extraction.load_instruction("completitud")
        self.prompt = self.instruction.text
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "split_batches": 0, "segments_retried": 0,
                      "segments": 0, "added": 0, "invalid": 0}
        self._batch = 0

    def _record(self, result, *, parsed, anomalies, retry_of, seconds, keys):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch, segment_keys=keys,
            request=result["request"], raw_output=result["content"],
            parsed=extraction.with_instruction(parsed, self.instruction,
                                               result.get("reasoning")),
            anomalies=anomalies, retry_of=retry_of,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": result["prompt_tokens"],
                     "completion_tokens": result["completion_tokens"]},
        )
        self.steps.append(step)
        return step

    def ask(self, candidates, retry_of=None):
        """Un pedido con `candidates` (o dos, si la salida se corta). Devuelve un `Result`
        por tramo, en orden."""
        aliased = [(f"T{n}", c) for n, c in enumerate(candidates, start=1)]
        keys = [c.unit.segment.key for c in candidates]
        messages = build_messages(self.prompt, aliased)
        schema = build_schema([alias for alias, _ in aliased])
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens,
                                               step=REASONING_STEP)
        except AIServiceError as error:
            self._record(
                {"request": generation.build_batch_request(messages, schema, max_tokens,
                                                           step=REASONING_STEP),
                 "content": "", "prompt_tokens": None, "completion_tokens": None},
                parsed=None, retry_of=retry_of, seconds=time.monotonic() - started,
                keys=keys,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error)}],
            )
            raise
        seconds = time.monotonic() - started
        result = {"request": output.request, "content": output.content,
                  "prompt_tokens": output.prompt_tokens,
                  "completion_tokens": output.completion_tokens,
                  "reasoning": output.reasoning_record()}
        self.stats["requests"] += 1

        if output.finish_reason == "length" and len(candidates) > 1:
            step = self._record(result, parsed=None, retry_of=retry_of, seconds=seconds,
                                keys=keys,
                                anomalies=[{"type": ANOMALY_CUT, "tramos": len(candidates)}])
            self.stats["split_batches"] += 1
            middle = len(candidates) // 2
            return self.ask(candidates[:middle], retry_of=step) + self.ask(
                candidates[middle:], retry_of=step)

        anomalies = []
        data = None
        try:
            data = json.loads(output.content)
            if not isinstance(data, dict):
                raise ValueError("no es un objeto")
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID, "detail": f"no es JSON: {error}",
                              "finish_reason": output.finish_reason})
            data = {}
        results, parsed = [], {}
        for alias, candidate in aliased:
            unit = candidate.unit
            outcome = Result(unit=unit, found=list(candidate.found))
            results.append(outcome)
            parsed[alias] = {"segmento": unit.segment.pk, "valida": False}
            if alias not in data:
                if data:
                    anomalies.append({"type": ANOMALY_MISSING_ALIAS, "alias": alias,
                                      "segment": unit.segment.pk})
                continue
            try:
                missing = shape_item(data[alias])
            except InvalidItem as error:
                anomalies.append({"type": ANOMALY_INVALID, "alias": alias,
                                  "segment": unit.segment.pk, "detail": str(error)})
                continue
            outcome.valid = True
            outcome.found, outcome.added = apply(unit, candidate.found, missing, anomalies)
            parsed[alias] = {"segmento": unit.segment.pk, "valida": True,
                             KEY_MISSING: len(missing), "agregados": outcome.added,
                             "requisitos_agregados": [
                                 extraction.found_record(found, unit.segment.text)
                                 for found in outcome.found
                                 if found.fragments
                                 and passes_of(found) == [PassName.COMPLETITUD.value]]}
        step = self._record(
            result, retry_of=retry_of, seconds=seconds, keys=keys, anomalies=anomalies,
            parsed={"tramos": parsed, "finish_reason": output.finish_reason})
        for outcome in results:
            outcome.step = step
            for found in outcome.found:
                if passes_of(found) == [PassName.COMPLETITUD.value]:
                    found.step = step
        return results

    def complete(self, candidates):
        """Pide la completitud de `candidates` (lista de `Candidate`, en el orden del
        pliego), reintenta una vez los tramos de salida inválida y devuelve la
        `Completion`."""
        results = {}
        for batch in batches(candidates):
            for result in self.ask(batch):
                results[result.unit.segment.pk] = result
        by_pk = {c.unit.segment.pk: c for c in candidates}
        for pk, result in list(results.items()):
            if result.valid:
                continue
            self.stats["segments_retried"] += 1
            again = self.ask([by_pk[pk]], retry_of=result.step)[0]
            results[pk] = again
            if not again.valid:
                self.stats["invalid"] += 1
                self.anomalies.append({
                    "type": ANOMALY_NO_RESULT, "segment": pk,
                    "key": again.unit.segment.key,
                    "detail": "sin resultado de la completitud después del reintento"})
        self.stats["segments"] = len(candidates)
        self.stats["added"] = sum(r.added for r in results.values())
        self.stats["steps"] = len(self.steps)
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        return Completion(results=results, steps=self.steps,
                          anomalies=self.anomalies + step_anomalies, stats=self.stats)
