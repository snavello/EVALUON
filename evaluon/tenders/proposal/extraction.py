"""Extracción de requisitos formales y económicos por lotes de tramos, con disposición
obligatoria (REQ-024, REQ-025, REQ-028; plan 003, "Extracción: qué recibe y qué devuelve
el modelo"; ADR-0019, decisiones 2 y 3).

1. `batches` arma lotes de tramos consecutivos de hasta `MATRIX_BATCH_INPUT_TOKENS` tokens
   (un tramo más largo va solo). Cada tramo recibe un alias (`T1`, `T2`, …) dentro del
   lote.
2. `Extractor.ask` hace un pedido al motor de los pedidos largos
   (`generation.generate_batch`, con `MATRIX_MAX_OUTPUT_TOKENS`) con las instrucciones
   versionadas (`prompts/matriz-extraccion-v1.md`) y los tramos del lote. El esquema de la
   salida tiene una propiedad obligatoria por alias; cada una trae `requisitos` (lista de
   `{cita, clase}`, con `clase` formal o economico), `tecnico` (vacía, o los renglones a
   los que se aplica el tramo, o `todos`) y `descarte` (un motivo de la lista cerrada del
   ADR-0019, o vacío).
3. Se valida tramo por tramo:
   - sin requisitos, sin marca técnica y sin descarte, o con descarte y algo más, o con la
     forma rota: el tramo queda sin disposición;
   - cada `cita` se busca exacta dentro del tramo (`quotes.locate`); dos requisitos del
     mismo tramo con la misma cita se unen;
   - si la salida se cortó por el máximo de salida, el lote se parte en dos y se repite
     cada mitad.
4. Los tramos sin disposición y los que tienen una cita que no está en el tramo se vuelven
   a pedir una vez, solos. Si siguen igual: el tramo queda sin disposición (quien llama lo
   deja pendiente) y la cita que no se pudo ubicar queda con el tramo entero como cita y la
   marca `cita_amplia` (una por clase y tramo). Un requisito nunca se pierde por una cita
   mal copiada.

La clase de un requisito cuyo tramo está en una sección que nombra una clase (`section_class`
formal o economico) la pone la regla, no el modelo. Los renglones de un requisito son los
del tramo, no los del modelo (eso lo resuelve quien crea el requisito).

Cada pedido al modelo se guarda en `tenders_run_step` apenas vuelve, con el pedido completo,
la salida sin tocar y lo interpretado (P6). Una falla del servicio queda también como un
pedido con su motivo y se vuelve a lanzar. Las filas de `tenders_run_step` solo se insertan:
por eso se crean con todo lo que se sabe del pedido, después de validarlo.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.models import DiscardReason, PassName, RequirementClass, RunStep
from evaluon.tenders.proposal import quotes

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Claves de lo que el modelo devuelve por tramo.
KEY_REQUIREMENTS = "requisitos"
KEY_TECHNICAL = "tecnico"
KEY_DISCARD = "descarte"

ALL_ITEMS = "todos"
BODY_CLASSES = (RequirementClass.FORMAL.value, RequirementClass.ECONOMICO.value)
_CLASS_LABELS = {"formal": "formal", "economico": "económico"}

# Anomalías (tipos que se registran).
ANOMALY_CUT = "salida_cortada"
ANOMALY_INVALID_OUTPUT = "salida_invalida"
ANOMALY_MISSING_ALIAS = "tramo_sin_propiedad"
ANOMALY_EXTRA_ALIAS = "propiedad_de_mas"
ANOMALY_NO_DISPOSITION = "sin_disposicion"
ANOMALY_QUOTE_NOT_FOUND = "cita_no_encontrada"
ANOMALY_QUOTES_JOINED = "citas_unidas"
ANOMALY_SERVICE = "servicio"


class InvalidItem(ValueError):
    """La salida de un tramo no tiene la forma del esquema."""


@dataclass(frozen=True)
class Unit:
    """Un tramo con lo que hace falta para pedirlo: el tramo (`Segment`), el título de su
    documento y su lugar en el pliego (el orden en que se muestran y se numeran)."""

    segment: object
    document_title: str
    position: int


@dataclass
class Found:
    """Un requisito ubicado: su clase y sus posiciones relativas al tramo. `flag` es
    `cita_amplia` si no se pudo ubicar el fragmento; `step`, el pedido que lo produjo."""

    category: str
    span: tuple
    flag: str = ""
    step: object = None


@dataclass
class Item:
    """La salida de un tramo con la forma comprobada."""

    quotes: list
    technical: list
    discard: str

    @property
    def has_disposition(self):
        """Tiene requisitos o marca técnica, o un descarte; no ambas cosas ni ninguna."""
        return bool(self.quotes or self.technical) != bool(self.discard)


@dataclass
class Outcome:
    """Lo que el modelo dijo de un tramo, ya validado. `valid` es falso si el tramo
    quedó sin disposición. `unfound` lleva las clases de los requisitos cuya cita no se
    ubicó, mientras esperan el reintento."""

    unit: Unit
    valid: bool = False
    found: list = field(default_factory=list)
    unfound: list = field(default_factory=list)
    technical: list = field(default_factory=list)
    discard: str = ""
    step: object = None
    retried: bool = False
    item: Item | None = None


@dataclass
class Extraction:
    """Resultado de la extracción: un `Outcome` por tramo (por `pk`), los pedidos al modelo
    en el orden en que se hicieron, las anomalías y las cuentas."""

    outcomes: dict
    steps: list
    anomalies: list
    stats: dict


# --- Pedido ------------------------------------------------------------------------------


def load_prompt(name="extraccion"):
    """Texto de las instrucciones de la versión que fija `MATRIX_PROMPT_VERSIONS`."""
    version = settings.MATRIX_PROMPT_VERSIONS[name]
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def build_schema(aliases, numbers):
    """Esquema de la salida: una propiedad obligatoria por alias. `numbers` son los
    renglones del pliego; `tecnico` solo admite `todos` o uno de ellos."""
    item = {
        "type": "object",
        "properties": {
            KEY_REQUIREMENTS: {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cita": {"type": "string", "minLength": 1},
                        "clase": {"type": "string", "enum": list(BODY_CLASSES)},
                    },
                    "required": ["cita", "clase"],
                    "additionalProperties": False,
                },
            },
            KEY_TECHNICAL: {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [ALL_ITEMS, *[str(n) for n in numbers]],
                },
            },
            KEY_DISCARD: {
                "type": "string",
                "enum": ["", *[reason.value for reason in DiscardReason]],
            },
        },
        "required": [KEY_REQUIREMENTS, KEY_TECHNICAL, KEY_DISCARD],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {alias: item for alias in aliases},
        "required": list(aliases),
        "additionalProperties": False,
    }


def render_block(alias, unit):
    """El tramo tal como lo ve el modelo: alias, documento, ruta, renglones, clase de la
    sección y texto literal, entre `[alias]` y `[/alias]`."""
    segment = unit.segment
    lines = [f"[{alias}]", f"Documento: {unit.document_title}"]
    lines.append(f"Ruta: {segment.path or segment.label or segment.key}")
    if segment.items:
        lines.append("Renglones: " + ", ".join(str(n) for n in segment.items))
    if segment.section_class in _CLASS_LABELS:
        lines.append(f"Clase de la sección: {_CLASS_LABELS[segment.section_class]}")
    lines.append("Texto:")
    lines.append(segment.text)
    lines.append(f"[/{alias}]")
    return "\n".join(lines)


def build_messages(prompt, aliased):
    """Mensajes del pedido: las instrucciones como sistema; los tramos del lote como
    usuario."""
    blocks = "\n\n".join(render_block(alias, unit) for alias, unit in aliased)
    names = ", ".join(alias for alias, _ in aliased)
    user = (
        "Tramos del pliego:\n\n"
        f"{blocks}\n\n"
        f"Devolvé un objeto JSON con una propiedad por cada alias: {names}."
    )
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


def batches(units):
    """Divide `units` en lotes de tramos consecutivos de hasta `MATRIX_BATCH_INPUT_TOKENS`
    tokens (contados con el cliente de generación). Un tramo más largo va solo."""
    limit = settings.MATRIX_BATCH_INPUT_TOKENS
    result, current, total = [], [], 0
    for unit in units:
        tokens = generation.count_tokens(render_block("T00", unit))
        if current and total + tokens > limit:
            result.append(current)
            current, total = [], 0
        current.append(unit)
        total += tokens
    if current:
        result.append(current)
    return result


# --- Validación ----------------------------------------------------------------------------


def shape_item(raw):
    """Comprueba la forma de lo que el modelo devolvió para un tramo y devuelve un
    `Item`. Lanza `InvalidItem`."""
    if not isinstance(raw, dict) or set(raw) != {KEY_REQUIREMENTS, KEY_TECHNICAL,
                                                  KEY_DISCARD}:
        raise InvalidItem("no es un objeto con requisitos, tecnico y descarte")
    required = raw[KEY_REQUIREMENTS]
    if not isinstance(required, list):
        raise InvalidItem("requisitos no es una lista")
    pairs = []
    for entry in required:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"cita", "clase"}
            or not isinstance(entry["cita"], str)
            or entry["clase"] not in BODY_CLASSES
        ):
            raise InvalidItem("un requisito no es {cita, clase} con clase válida")
        pairs.append((entry["cita"], entry["clase"]))
    marks = raw[KEY_TECHNICAL]
    if not isinstance(marks, list):
        raise InvalidItem("tecnico no es una lista")
    technical = []
    for mark in marks:
        if mark == ALL_ITEMS:
            value = ALL_ITEMS
        elif isinstance(mark, str) and mark.isdigit():
            value = int(mark)
        else:
            raise InvalidItem(f"marca técnica inválida: {mark!r}")
        if value not in technical:
            technical.append(value)
    if ALL_ITEMS in technical:
        technical = [ALL_ITEMS]
    discard = raw[KEY_DISCARD]
    if not isinstance(discard, str) or (discard and discard not in DiscardReason.values):
        raise InvalidItem(f"motivo de descarte desconocido: {discard!r}")
    return Item(quotes=pairs, technical=technical, discard=discard)


def _category(unit, kind):
    """La clase de un requisito: la de la sección si la nombra; si no, la del modelo."""
    section = unit.segment.section_class
    return section if section in BODY_CLASSES else kind


def _resolve(unit, item, anomalies):
    """Ubica las citas de `item` dentro del tramo. Devuelve `(found, unfound)`: los
    requisitos ubicados y las clases de los que no. Dos citas iguales se unen."""
    text = unit.segment.text
    seen, used = set(), set()
    found, unfound = [], []
    for quote, kind in item.quotes:
        key = quote.strip()
        if key in seen:
            anomalies.append({"type": ANOMALY_QUOTES_JOINED, "segment": unit.segment.pk,
                              "key": unit.segment.key})
            continue
        seen.add(key)
        span = quotes.locate(text, key, used)
        category = _category(unit, kind)
        if span is None:
            unfound.append(category)
        else:
            used.add(span)
            found.append(Found(category=category, span=span))
    return found, unfound


def wide_quotes(unit, categories, existing=()):
    """Un requisito con el tramo entero como cita, por clase, salvo las que ya tienen
    uno."""
    have = {f.category for f in existing if f.flag == quotes.WIDE}
    wide = []
    for category in categories:
        if category in have:
            continue
        have.add(category)
        wide.append(Found(category=category, span=(0, len(unit.segment.text)),
                          flag=quotes.WIDE))
    return wide


def _parsed(outcome):
    """Lo interpretado de un tramo, para `tenders_run_step.parsed`."""
    if outcome.item is None:
        return {"segmento": outcome.unit.segment.pk, "valida": False}
    return {
        "segmento": outcome.unit.segment.pk,
        "valida": outcome.valid,
        KEY_REQUIREMENTS: [
            {"clase": found.category, "inicio": found.span[0], "fin": found.span[1]}
            for found in outcome.found
        ] + [{"clase": category, "inicio": None, "fin": None}
             for category in outcome.unfound],
        KEY_TECHNICAL: list(outcome.item.technical),
        KEY_DISCARD: outcome.item.discard,
    }


def _union(first, second):
    if ALL_ITEMS in first or ALL_ITEMS in second:
        return [ALL_ITEMS]
    return list(dict.fromkeys([*first, *second]))


# --- El extractor ----------------------------------------------------------------------------


class Extractor:
    """Hace los pedidos de la extracción de una propuesta (`MatrixRun`) y guarda cada uno
    en `tenders_run_step`. `numbers` son los renglones del pliego."""

    def __init__(self, run, numbers, pass_name=PassName.EXTRACCION):
        self.run = run
        self.numbers = list(numbers)
        self.pass_name = pass_name
        self.prompt = load_prompt("extraccion")
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "split_batches": 0, "segments_retried": 0,
                      "quotes_retried": 0, "wide_quotes": 0}
        self._batch = 0

    def _record(self, units, result, *, parsed, anomalies, retry_of, seconds):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run,
            pass_name=self.pass_name,
            batch=self._batch,
            segment_keys=[unit.segment.key for unit in units],
            request=result["request"],
            raw_output=result["content"],
            parsed=parsed,
            anomalies=anomalies,
            retry_of=retry_of,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": result["prompt_tokens"],
                     "completion_tokens": result["completion_tokens"]},
        )
        self.steps.append(step)
        return step

    @staticmethod
    def _load(output, anomalies):
        """La salida como diccionario, o `None` si no es un objeto JSON."""
        try:
            data = json.loads(output.content)
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID_OUTPUT,
                              "detail": f"no es JSON: {error}",
                              "finish_reason": output.finish_reason})
            return None
        if not isinstance(data, dict):
            anomalies.append({"type": ANOMALY_INVALID_OUTPUT, "detail": "no es un objeto",
                              "finish_reason": output.finish_reason})
            return None
        return data

    def ask(self, units, retry_of=None):
        """Un pedido con `units` (o dos, si la salida se corta). Devuelve un `Outcome` por
        tramo, en el orden de `units`."""
        aliased = [(f"T{n}", unit) for n, unit in enumerate(units, start=1)]
        messages = build_messages(self.prompt, aliased)
        schema = build_schema([alias for alias, _ in aliased], self.numbers)
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens)
        except AIServiceError as error:
            self._record(
                units,
                {"request": generation.build_request(messages, schema, max_tokens),
                 "content": "", "prompt_tokens": None, "completion_tokens": None},
                parsed=None,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error)}],
                retry_of=retry_of,
                seconds=time.monotonic() - started,
            )
            raise
        seconds = time.monotonic() - started
        result = {"request": output.request, "content": output.content,
                  "prompt_tokens": output.prompt_tokens,
                  "completion_tokens": output.completion_tokens}
        self.stats["requests"] += 1

        if output.finish_reason == "length" and len(units) > 1:
            step = self._record(
                units, result, parsed=None, retry_of=retry_of, seconds=seconds,
                anomalies=[{"type": ANOMALY_CUT, "tramos": len(units)}],
            )
            self.stats["split_batches"] += 1
            middle = len(units) // 2
            return self.ask(units[:middle], retry_of=step) + self.ask(
                units[middle:], retry_of=step
            )

        anomalies = []
        outcomes = []
        data = self._load(output, anomalies)
        for alias, unit in aliased:
            outcome = Outcome(unit=unit)
            outcomes.append(outcome)
            if data is None:
                continue
            if alias not in data:
                anomalies.append({"type": ANOMALY_MISSING_ALIAS, "alias": alias,
                                  "segment": unit.segment.pk})
                continue
            try:
                item = shape_item(data[alias])
            except InvalidItem as error:
                anomalies.append({"type": ANOMALY_INVALID_OUTPUT, "alias": alias,
                                  "segment": unit.segment.pk, "detail": str(error)})
                continue
            outcome.item = item
            if not item.has_disposition:
                anomalies.append({"type": ANOMALY_NO_DISPOSITION, "alias": alias,
                                  "segment": unit.segment.pk})
                continue
            outcome.valid = True
            outcome.technical = list(item.technical)
            outcome.discard = item.discard
            outcome.found, outcome.unfound = _resolve(unit, item, anomalies)
            for category in outcome.unfound:
                anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND,
                                  "segment": unit.segment.pk, "key": unit.segment.key,
                                  "clase": category})
        if data is not None:
            extra = sorted(set(data) - {alias for alias, _ in aliased})
            if extra:
                anomalies.append({"type": ANOMALY_EXTRA_ALIAS, "aliases": extra})
        step = self._record(
            units, result, retry_of=retry_of, seconds=seconds, anomalies=anomalies,
            parsed={"tramos": {alias: _parsed(outcome)
                               for (alias, _), outcome in zip(aliased, outcomes)},
                    "finish_reason": output.finish_reason},
        )
        for outcome in outcomes:
            outcome.step = step
            for found in outcome.found:
                found.step = step
        return outcomes

    def _retry(self, outcome):
        """Pide de nuevo el tramo, solo, y une lo que vuelve con lo primero."""
        unit = outcome.unit
        self.stats["segments_retried"] += 1
        self.stats["quotes_retried"] += len(outcome.unfound)
        outcome.retried = True
        again = self.ask([unit], retry_of=outcome.step)[0]
        if not outcome.valid:
            if again.valid:
                outcome.valid = True
                outcome.item = again.item
                outcome.found = again.found
                outcome.unfound = again.unfound
                outcome.technical = again.technical
                outcome.discard = again.discard
                outcome.step = again.step
        elif again.valid and (again.found or again.unfound):
            # Lo que vuelve reemplaza a las citas que no se ubicaron; lo ya ubicado queda.
            known = {found.span for found in outcome.found}
            outcome.found += [f for f in again.found if f.span not in known]
            outcome.unfound = again.unfound
            outcome.technical = _union(outcome.technical, again.technical)
        elif again.valid:
            outcome.technical = _union(outcome.technical, again.technical)
        # Lo que sigue sin ubicarse queda con el tramo entero como cita.
        if outcome.valid and outcome.unfound:
            wide = wide_quotes(unit, outcome.unfound, outcome.found)
            for found in wide:
                found.step = again.step
            outcome.found += wide
            outcome.unfound = []
        if not outcome.valid:
            self.anomalies.append({"type": ANOMALY_NO_DISPOSITION,
                                   "segment": unit.segment.pk, "key": unit.segment.key,
                                   "detail": "sin disposición después del reintento"})

    def extract(self, units):
        """Recorre `units` en lotes, reintenta lo que lo necesita y devuelve la
        `Extraction`."""
        outcomes = {}
        for batch in batches(units):
            for outcome in self.ask(batch):
                outcomes[outcome.unit.segment.pk] = outcome
        for outcome in outcomes.values():
            if not outcome.valid or outcome.unfound:
                self._retry(outcome)
        self.stats["wide_quotes"] = sum(
            1 for o in outcomes.values() for f in o.found if f.flag == quotes.WIDE
        )
        self.stats["steps"] = len(self.steps)
        step_anomalies = [anomaly for step in self.steps for anomaly in step.anomalies]
        return Extraction(outcomes=outcomes, steps=self.steps,
                          anomalies=self.anomalies + step_anomalies, stats=self.stats)
