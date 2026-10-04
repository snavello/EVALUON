"""Segunda extracción, unión y pasada de completitud de los niveles alta y exigente
(REQ-024, REQ-030; plan 003, "Pasadas"; ADR-0019, decisión 5).

Estas pasadas solo cambian cómo se buscan los requisitos formales y económicos; lo técnico
es igual en los tres niveles. Solo trabajan con tramos que pasan por el modelo: los de una
sección técnica se disponen por regla y no llegan acá.

**Segunda extracción** (exigente). `second_extraction` repite la extracción sobre los mismos
tramos con los lotes desplazados medio lote: el primer lote se corta a la mitad, así que los
límites caen en otros tramos. Usa su propio `Extractor` con `PassName.EXTRACCION_2`.

**Unión** (`union`). Por tramo: un requisito de la segunda extracción entra si su cita no se
superpone en más de la mitad con la de otro del mismo tramo; si se superpone, es el mismo y
queda el primero (si el primero era una cita amplia y el segundo un fragmento, queda el
fragmento). Un tramo descartado en una extracción y con requisitos o marca técnica en la otra
queda con lo encontrado; la marca técnica es la unión de las dos. Si una sola extracción
dejó el tramo sin disposición, vale la otra. Cada requisito lleva en `passes` las pasadas
que lo encontraron.

**Completitud** (alta y exigente). `Completer.complete` recibe, solo para tramos formales y
económicos, cada tramo con sus requisitos ya encontrados (o ninguno, si el modelo lo
descartó y tiene marcadores de obligación) y devuelve los que faltan y las divisiones de los
que juntan dos condiciones (`prompts/matriz-completitud-v1.md`). El sistema ubica cada cita
con `quotes.locate`, que tolera espacios y saltos de línea distintos y devuelve posiciones
relativas al tramo; un faltante que se superpone en más de la mitad con un requisito ya
encontrado no se suma; una cita que no se ubica queda con el tramo entero como cita
(`cita_amplia`), porque un requisito nunca se pierde por una cita mal copiada; una división
cuyas partes no se ubican todas deja el requisito como estaba. Un tramo cuya salida es
inválida se vuelve a pedir una vez, solo; si sigue inválido no cambia y quien llama decide
(un descartado con marcadores queda pendiente).
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
KEY_SPLITS = "divisiones"

ANOMALY_CUT = "completitud_salida_cortada"
ANOMALY_INVALID = "completitud_salida_invalida"
ANOMALY_MISSING_ALIAS = "completitud_tramo_sin_propiedad"
ANOMALY_QUOTE_NOT_FOUND = "completitud_cita_no_encontrada"
ANOMALY_SPLIT_NOT_APPLIED = "completitud_division_no_aplicada"
ANOMALY_NO_RESULT = "completitud_sin_resultado"
ANOMALY_SERVICE = "servicio"

MORE_THAN_HALF = 0.5


class InvalidItem(ValueError):
    """La salida de un tramo no tiene la forma del esquema de la completitud."""


# --- Superposición y pasadas de un requisito -------------------------------------------------


def overlap(a, b):
    """Cuánto se superponen dos posiciones `(inicio, fin)`, como fracción de la más corta."""
    shared = min(a[1], b[1]) - max(a[0], b[0])
    shortest = min(a[1] - a[0], b[1] - b[0])
    if shared <= 0 or shortest <= 0:
        return 0.0
    return shared / shortest


def passes_of(found):
    """Las pasadas que encontraron el requisito; sin marca, solo la extracción."""
    return list(getattr(found, "passes", None) or [PassName.EXTRACCION.value])


def tag(found, *names):
    """Suma `names` a las pasadas del requisito y lo devuelve."""
    found.passes = list(dict.fromkeys([*(getattr(found, "passes", None) or []), *names]))
    return found


def _same_requirement(new, old):
    """Si `new` es el mismo requisito que `old` del mismo tramo: se superponen en más de la
    mitad. Una cita amplia cubre todo el tramo, así que solo se compara con la de su
    clase."""
    if (new.flag == quotes.WIDE or old.flag == quotes.WIDE) and new.category != old.category:
        return False
    return overlap(new.span, old.span) > MORE_THAN_HALF


# --- Segunda extracción y unión --------------------------------------------------------------


def second_extraction(extractor, units):
    """Repite la extracción de `units` con los lotes desplazados medio lote. `extractor` es
    el `Extractor` de la segunda extracción. Devuelve una `extraction.Extraction`."""
    lots = extraction.batches(units)
    shift = len(lots[0]) // 2 if lots else 0
    outcomes = {}
    result = None
    for part in (units[:shift], units[shift:]):
        if part:
            result = extractor.extract(part)
            outcomes.update(result.outcomes)
    if result is None:
        return extraction.Extraction(outcomes={}, steps=extractor.steps, anomalies=[],
                                     stats=extractor.stats)
    # Las anomalías y las cuentas del extractor son acumuladas: valen las de la última.
    return extraction.Extraction(outcomes=outcomes, steps=extractor.steps,
                                 anomalies=result.anomalies, stats=result.stats)


def union(first, second):
    """El `extraction.Outcome` que une el de la primera y el de la segunda extracción del
    mismo tramo. Ver el módulo."""
    for found in first.found:
        tag(found, PassName.EXTRACCION.value)
    for found in second.found:
        tag(found, PassName.EXTRACCION_2.value)
    if not first.valid:
        return second if second.valid else first
    if not second.valid:
        return first

    merged = list(first.found)
    for new in second.found:
        for index, old in enumerate(merged):
            if _same_requirement(new, old):
                if old.flag == quotes.WIDE and new.flag != quotes.WIDE:
                    tag(new, *passes_of(old))
                    merged[index] = new
                else:
                    tag(old, PassName.EXTRACCION_2.value)
                break
        else:
            merged.append(new)
    technical = extraction._union(first.technical, second.technical)
    discard = "" if merged or technical else (first.discard or second.discard)
    return extraction.Outcome(
        unit=first.unit, valid=True, found=merged, technical=technical, discard=discard,
        step=first.step if (first.found or first.technical or not second.found)
        else second.step,
        retried=first.retried or second.retried, item=first.item,
    )


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
    split: int = 0
    step: object = None


@dataclass
class Completion:
    results: dict
    steps: list
    anomalies: list
    stats: dict


def build_schema(aliases):
    """Esquema de la salida: una propiedad obligatoria por alias."""
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
        "properties": {
            KEY_MISSING: {"type": "array", "items": requirement},
            KEY_SPLITS: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "original": {"type": "string", "minLength": 1},
                        "partes": {"type": "array", "items": requirement, "minItems": 2},
                    },
                    "required": ["original", "partes"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [KEY_MISSING, KEY_SPLITS],
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
    """Comprueba la forma de lo que el modelo devolvió para un tramo y devuelve
    `(faltantes, divisiones)`: pares `(cita, clase)` y pares `(original, [(cita, clase)])`.
    Lanza `InvalidItem`."""
    if not isinstance(raw, dict) or set(raw) != {KEY_MISSING, KEY_SPLITS}:
        raise InvalidItem("no es un objeto con faltantes y divisiones")
    if not isinstance(raw[KEY_MISSING], list) or not isinstance(raw[KEY_SPLITS], list):
        raise InvalidItem("faltantes y divisiones tienen que ser listas")
    missing = [_shape_requirement(entry) for entry in raw[KEY_MISSING]]
    splits = []
    for entry in raw[KEY_SPLITS]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"original", "partes"}
            or not isinstance(entry["original"], str)
            or not isinstance(entry["partes"], list)
        ):
            raise InvalidItem("una división no es {original, partes}")
        splits.append((entry["original"], [_shape_requirement(p) for p in entry["partes"]]))
    return missing, splits


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
        tokens = generation.count_tokens(render_block("T00", candidate))
        if current and total + tokens > limit:
            result.append(current)
            current, total = [], 0
        current.append(candidate)
        total += tokens
    if current:
        result.append(current)
    return result


def _split_target(final, span):
    """El requisito de `final` que `span` (el original de una división) reemplaza: el que
    más se le parece entre los que cubre en más de la mitad."""
    target, best = None, 0.0
    for candidate in final:
        shared = min(span[1], candidate.span[1]) - max(span[0], candidate.span[0])
        length = candidate.span[1] - candidate.span[0]
        if shared <= 0 or length <= 0 or shared / length < MORE_THAN_HALF:
            continue
        score = shared / (max(span[1], candidate.span[1]) - min(span[0], candidate.span[0]))
        if score > best:
            target, best = candidate, score
    return target


def apply(unit, found_list, missing, splits, anomalies):
    """Aplica la salida validada de un tramo a sus requisitos ya encontrados. Devuelve
    `(requisitos finales, agregados, divididos)`. No modifica `found_list`."""
    segment = unit.segment
    text = segment.text
    final = list(found_list)
    added = divided = 0

    def refuse(detail):
        anomalies.append({"type": ANOMALY_SPLIT_NOT_APPLIED, "segment": segment.pk,
                          "key": segment.key, "detail": detail})

    for original, parts in splits:
        span = quotes.locate(text, original)
        if span is None:
            refuse("el original no está en el tramo")
            continue
        target = _split_target(final, span)
        if target is None:
            refuse("el original no coincide con un requisito")
            continue
        used = {f.span for f in final if f is not target}
        located = []
        for quote, kind in parts:
            part_span = quotes.locate(text, quote, used | {s for s, _ in located})
            if part_span is None:
                located = None
                break
            located.append((part_span, _category(unit, kind)))
        if located is None or len(located) < 2:
            refuse("las partes no se ubican todas en el tramo")
            continue
        pieces = []
        for part_span, category in located:
            piece = Found(category=category, span=part_span)
            piece.passes = [PassName.COMPLETITUD.value]
            pieces.append(piece)
        at = final.index(target)
        final[at:at + 1] = pieces
        divided += 1

    unlocated = []
    for quote, kind in missing:
        category = _category(unit, kind)
        span = quotes.locate(text, quote)
        if span is None:
            unlocated.append(category)
            anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND, "segment": segment.pk,
                              "key": segment.key, "clase": category})
            continue
        new = Found(category=category, span=span)
        if any(_same_requirement(new, old) for old in final):
            continue
        new.passes = [PassName.COMPLETITUD.value]
        final.append(new)
        added += 1
    for wide in extraction.wide_quotes(unit, unlocated, final):
        wide.passes = [PassName.COMPLETITUD.value]
        final.append(wide)
        added += 1
    final.sort(key=lambda f: f.span[0])
    return final, added, divided


class Completer:
    """Hace los pedidos de la completitud de una propuesta (`MatrixRun`) y guarda cada uno
    en `tenders_run_step`."""

    pass_name = PassName.COMPLETITUD

    def __init__(self, run):
        self.run = run
        self.prompt = extraction.load_prompt("completitud")
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "split_batches": 0, "segments_retried": 0,
                      "segments": 0, "added": 0, "split": 0, "invalid": 0}
        self._batch = 0

    def _record(self, result, *, parsed, anomalies, retry_of, seconds, keys):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch, segment_keys=keys,
            request=result["request"], raw_output=result["content"], parsed=parsed,
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
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens)
        except AIServiceError as error:
            self._record(
                {"request": generation.build_request(messages, schema, max_tokens),
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
                  "completion_tokens": output.completion_tokens}
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
                missing, splits = shape_item(data[alias])
            except InvalidItem as error:
                anomalies.append({"type": ANOMALY_INVALID, "alias": alias,
                                  "segment": unit.segment.pk, "detail": str(error)})
                continue
            outcome.valid = True
            outcome.found, outcome.added, outcome.split = apply(
                unit, candidate.found, missing, splits, anomalies)
            parsed[alias] = {"segmento": unit.segment.pk, "valida": True,
                             KEY_MISSING: len(missing), KEY_SPLITS: len(splits),
                             "agregados": outcome.added, "divididos": outcome.split}
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
        self.stats["split"] = sum(r.split for r in results.values())
        self.stats["steps"] = len(self.steps)
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        return Completion(results=results, steps=self.steps,
                          anomalies=self.anomalies + step_anomalies, stats=self.stats)
