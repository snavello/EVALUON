"""Consecuencias sugeridas de cada requisito, con su fundamento (REQ-029; plan 003,
"Consecuencias"; principio P3).

El sistema solo sugiere: nunca decide si un requisito es subsanable ni si una oferta cumple.
Para cada requisito de la versión propone hasta tres consecuencias de no cumplirlo, cada una
con el fundamento que la sostiene, o la deja "no determinada" si no hay ninguno. La
consecuencia la elige después un evaluador (T-081).

**Fundamentos del pliego** (`P1…`). Los tramos de los documentos base con marcadores de
consecuencia (`CONSEQUENCE_MARKERS`) más los tramos del propio requisito: el de su cita, o el
del encabezado de su renglón si es técnico. Los del propio requisito entran siempre; los demás
entran mientras quepan en la mitad del espacio que queda, y si no caben todos los elige el
reranker contra una pregunta fija (`PLIEGO_QUESTION`).

**Fundamentos de la norma** (`N1…`). Las preguntas fijas (`NORM_QUESTIONS`, las mismas que
nombra `prompts/matriz-consecuencias-v1.md`) pasan por `retrieve` de la 001 con la fecha de
autorización del procedimiento; se juntan sus resultados (por unidad, el mejor puntaje) y
`select_units` elige las que entran en el espacio que queda. Sin régimen a esa fecha
(`run.regime` vacío) no se busca nada: solo hay fundamentos del pliego.

**Pedidos.** De a `MATRIX_CONSEQUENCES_PER_REQUEST` requisitos (25). Un pedido que no entra en
el contexto se parte por la mitad; un requisito que no entra solo queda "no determinada" con
la anomalía `consecuencias_requisito_no_entra`. Una salida cortada por el máximo se parte y se
vuelve a pedir. Cada pedido queda en `tenders_run_step` con las unidades de la norma
mostradas (con su puntaje), la selección, la versión de la normativa y el fundamento de cada
alias (P6).

**Validación**, como en la 001. El modelo devuelve por requisito hasta tres opciones
`{tipo, fundamentos}`. Una opción se descarta si su tipo no es uno de los que el sistema puede
sugerir (nunca `aprobacion_condicionada` ni `aprobar_igual`), si no tiene fundamentos, si cita
un alias que el pedido no mostró, o si `consultar_oferente` u `otra_pliego` no tiene al menos
un fundamento del pliego. Un requisito sin opciones válidas queda con la consecuencia
`no_determinada`, sin fundamentos, que solo pone el sistema. Si la forma de lo devuelto para un
requisito no es la del esquema, se vuelve a pedir una vez, solo; si sigue mal, queda
"no determinada". El texto de cada fundamento sale de la base, no del modelo: las opciones
guardan solo sus posiciones.
"""

import json
import time
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation, reranker
from evaluon.audit import services as audit
from evaluon.norms.models import Unit as NormUnit
from evaluon.queries import answering, retrieval
from evaluon.tenders.models import (
    ConsequenceType,
    PassName,
    RequirementClass,
    RunStep,
    SegmentType,
)
from evaluon.tenders.proposal import extraction

# Tipos que el sistema puede sugerir (plan 003, "Consecuencias").
SYSTEM_TYPES = (
    ConsequenceType.DESESTIMACION.value,
    ConsequenceType.INTIMACION_SUBSANAR.value,
    ConsequenceType.CONSULTAR_OFERENTE.value,
    ConsequenceType.OTRA_PLIEGO.value,
)
# Tipos que exigen al menos un fundamento del pliego.
NEED_PLIEGO = (ConsequenceType.CONSULTAR_OFERENTE.value, ConsequenceType.OTRA_PLIEGO.value)
MAX_OPTIONS = 3

# Marcadores de consecuencia de los tramos del pliego (se comparan sin tildes ni mayúsculas).
CONSEQUENCE_MARKERS = (
    "desestim",
    "inadmisib",
    "subsan",
    "intim",
    "apercibimiento",
    "causal suficiente",
    "rechaz",
    "requerir",
    "solicitar aclaraciones",
)

# Preguntas fijas con que se busca en la norma; están también en las instrucciones.
NORM_QUESTIONS = (
    "¿Qué deficiencias de una oferta no son subsanables y causan su desestimación?",
    "¿Qué errores u omisiones de una oferta se pueden subsanar y cómo se intima al "
    "oferente?",
    "¿Cuándo un renglón de una oferta es inadmisible?",
)
# Pregunta fija con que el reranker elige entre los tramos del pliego si no caben todos.
PLIEGO_QUESTION = ("¿Qué consecuencia tiene para el oferente que su oferta no cumpla una "
                   "condición del pliego: desestimación, intimación a subsanar o pedido "
                   "de aclaraciones?")

ANOMALY_CUT = "consecuencias_salida_cortada"
ANOMALY_INVALID = "consecuencias_salida_invalida"
ANOMALY_MISSING_ALIAS = "consecuencias_requisito_sin_propiedad"
ANOMALY_NO_RESULT = "consecuencias_sin_resultado"
ANOMALY_OPTION_DROPPED = "consecuencias_opcion_descartada"
ANOMALY_NO_FIT = "consecuencias_requisito_no_entra"
ANOMALY_NO_GROUNDS = "consecuencias_sin_fundamentos"
ANOMALY_CORPUS_CHANGED = "consecuencias_normativa_cambio"
ANOMALY_SERVICE = "servicio"

_CLASS_LABELS = {"formal": "formal", "economico": "económico", "tecnico": "técnico"}


def _fold(text):
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_FOLDED_MARKERS = tuple(_fold(marker) for marker in CONSEQUENCE_MARKERS)


def has_consequence_markers(text):
    """Si el texto tiene algún marcador de consecuencia."""
    folded = _fold(text)
    return any(marker in folded for marker in _FOLDED_MARKERS)


class InvalidItem(ValueError):
    """Lo devuelto para un requisito no tiene la forma del esquema."""


# --- Lo que se le pregunta -----------------------------------------------------------------


@dataclass
class Subject:
    """Un requisito de la versión que se va a proponer, con lo que hace falta para
    preguntar por sus consecuencias. `own` son los tramos del propio requisito (`Segment`)
    y `unit` el `extraction.Unit` desde el que se lo describe."""

    number: int
    category: str
    items: list
    text: str = ""
    unit: object = None
    own: list = field(default_factory=list)


def build_subjects(loaded, body, rows):
    """Los `Subject` de la versión, numerados como `run._save` numera los requisitos:
    primero los formales y económicos (`body`: `[(unidad, Found, texto)]`, en el orden del
    pliego) y después las filas técnicas (`rows`: las de `technical.build_rows`)."""
    by_pk = {unit.segment.pk: unit for unit in loaded.units}
    headers = dict(loaded.items)
    subjects = []
    for unit, found, text in body:
        subjects.append(Subject(number=len(subjects) + 1, category=found.category,
                                items=list(unit.segment.items), text=text, unit=unit,
                                own=[unit.segment]))
    for row in rows:
        header = headers.get(row.number) if row.number is not None else None
        unit = by_pk.get(header.pk) if header is not None else None
        if unit is None and row.quotes:
            unit = by_pk.get(row.quotes[0].segment.pk)
        subjects.append(Subject(
            number=len(subjects) + 1, category=RequirementClass.TECNICO.value,
            items=[row.number] if row.number is not None else [], unit=unit,
            own=[header] if header is not None else []))
    return subjects


def render_subject(alias, subject):
    """El requisito tal como lo ve el modelo."""
    lines = [f"[{alias}]", f"Clase: {_CLASS_LABELS.get(subject.category, subject.category)}"]
    if subject.category == RequirementClass.TECNICO.value:
        number = subject.items[0] if subject.items else None
        lines.append(f"Renglón {number}, especificaciones técnicas" if number is not None
                     else "Especificaciones técnicas del pliego")
    if subject.unit is not None:
        lines.append(f"Documento: {subject.unit.document_title}")
        segment = subject.unit.segment
        lines.append(f"Ruta: {segment.path or segment.label or segment.key}")
    if subject.category != RequirementClass.TECNICO.value:
        lines += ["Texto:", subject.text]
    lines.append(f"[/{alias}]")
    return "\n".join(lines)


def render_pliego(alias, unit):
    """Un tramo del pliego como fundamento."""
    segment = unit.segment
    return "\n".join([
        f"[{alias}]", f"Documento: {unit.document_title}",
        f"Ruta: {segment.path or segment.label or segment.key}", "Texto:", segment.text,
        f"[/{alias}]",
    ])


def render_norm(alias, unit, spans):
    """Una unidad de la norma como fundamento (formato de la 001, `answering.unit_block`)."""
    return answering.unit_block(f"[{alias}]", unit, spans) + f"\n[/{alias}]"


def build_schema(subject_aliases, ground_aliases):
    """Esquema de la salida: una propiedad obligatoria por requisito; los fundamentos, solo
    entre los alias mostrados."""
    option = {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": list(SYSTEM_TYPES)},
            "fundamentos": {"type": "array", "minItems": 1,
                            "items": {"type": "string", "enum": list(ground_aliases)}},
        },
        "required": ["tipo", "fundamentos"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {"opciones": {"type": "array", "items": option,
                                    "maxItems": MAX_OPTIONS}},
        "required": ["opciones"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {alias: item for alias in subject_aliases},
        "required": list(subject_aliases),
        "additionalProperties": False,
    }


def build_messages(prompt, authorization_date, subject_blocks, pliego_blocks, norm_blocks,
                   aliases):
    parts = [
        f"Fecha de autorización del procedimiento: "
        f"{authorization_date.strftime('%d/%m/%Y')}",
        "Requisitos:\n\n" + "\n\n".join(subject_blocks),
        "Fundamentos del pliego:\n\n" + "\n\n".join(pliego_blocks),
        "Fundamentos de la norma:\n\n" + ("\n\n".join(norm_blocks) if norm_blocks
                                          else "ninguno"),
        "Devolvé un objeto JSON con una propiedad por cada alias de requisito: "
        + ", ".join(aliases) + ".",
    ]
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": "\n\n".join(parts)}]


# --- Lo que devuelve -----------------------------------------------------------------------


def shape_item(raw, valid_aliases, pliego_aliases):
    """Interpreta lo devuelto para un requisito. Devuelve `(opciones, descartes)`: las
    opciones válidas como `(tipo, [alias])`, sin repetir tipo y hasta `MAX_OPTIONS`, y los
    motivos de las que se descartaron. Lanza `InvalidItem` si la forma no es la del
    esquema."""
    if not isinstance(raw, dict) or set(raw) != {"opciones"} or not isinstance(
            raw["opciones"], list):
        raise InvalidItem("no es un objeto con la lista de opciones")
    options, dropped, seen = [], [], set()
    for entry in raw["opciones"]:
        if (not isinstance(entry, dict) or set(entry) != {"tipo", "fundamentos"}
                or not isinstance(entry["tipo"], str)
                or not isinstance(entry["fundamentos"], list)
                or not all(isinstance(a, str) for a in entry["fundamentos"])):
            dropped.append("la opción no es {tipo, fundamentos}")
            continue
        kind = entry["tipo"]
        if kind not in SYSTEM_TYPES:
            dropped.append(f"tipo que el sistema no sugiere: {kind}")
            continue
        aliases = []
        for alias in entry["fundamentos"]:
            alias = alias.strip().strip("[]").strip()
            if alias not in aliases:
                aliases.append(alias)
        unknown = [a for a in aliases if a not in valid_aliases]
        if not aliases:
            dropped.append("sin fundamentos")
        elif unknown:
            dropped.append(f"alias inexistente: {', '.join(unknown)}")
        elif kind in NEED_PLIEGO and not any(a in pliego_aliases for a in aliases):
            dropped.append(f"{kind} sin fundamento del pliego")
        elif kind in seen:
            dropped.append(f"tipo repetido: {kind}")
        elif len(options) >= MAX_OPTIONS:
            dropped.append("más de tres opciones")
        else:
            seen.add(kind)
            options.append((kind, aliases))
    return options, dropped


@dataclass
class Option:
    """Una consecuencia sugerida: tipo, fundamentos (posiciones) y el pedido que la
    produjo. `no_determinada` no tiene fundamentos."""

    consequence_type: str
    grounds: list
    step: object = None


@dataclass
class Suggestions:
    options: dict
    steps: list
    anomalies: list
    stats: dict


@dataclass
class _Lot:
    """Un pedido armado: los requisitos que lleva, sus alias y los fundamentos."""

    subjects: list
    aliases: dict            # alias de requisito -> Subject
    grounds: dict            # alias de fundamento -> registro de sus posiciones
    pliego_aliases: set
    messages: list
    schema: dict
    context: dict            # lo que se anota del pedido (normativa, puntajes)
    segment_keys: list


class Suggester:
    """Hace los pedidos de consecuencias de una propuesta (`MatrixRun`) y guarda cada uno en
    `tenders_run_step`."""

    pass_name = PassName.CONSECUENCIAS

    def __init__(self, run, loaded):
        self.run = run
        self.loaded = loaded
        self.prompt = extraction.load_prompt("consecuencias")
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "split_batches": 0, "requirements": 0,
                      "retried": 0, "invalid": 0, "options": 0, "undetermined": 0,
                      "dropped_options": 0, "norm_units": 0}
        self._batch = 0
        self._found = None
        self._searched = False
        self._candidates = [unit for unit in loaded.units if self._is_base(unit)]
        self._results = {}
        self._step_of = {}

    @staticmethod
    def _is_base(unit):
        segment = unit.segment
        return (segment.segment_type not in (SegmentType.TITULO, SegmentType.PAGINA,
                                             SegmentType.NO_UBICADO)
                and has_consequence_markers(segment.text))

    # -- Fundamentos de la norma ------------------------------------------------------------

    def _norm_search(self):
        """La recuperación de la 001 con las preguntas fijas, una vez por propuesta, a la
        fecha de autorización. `None` si no hay régimen a esa fecha."""
        if self._searched:
            return self._found
        self._searched = True
        if not self.run.regime:
            return None
        if audit.current_corpus_version() != self.run.corpus_version:
            self.anomalies.append({"type": ANOMALY_CORPUS_CHANGED,
                                   "begin": self.run.corpus_version,
                                   "now": audit.current_corpus_version()})
        results = [retrieval.retrieve(question, self.run.authorization_date)
                   for question in NORM_QUESTIONS]
        self._found = merge_results(results)
        self.stats["norm_units"] = len(self._found.selected)
        return self._found

    # -- Armado de un pedido ----------------------------------------------------------------

    def _space(self):
        """Tokens para lo que cambia en cada pedido: el contexto, menos la salida, el margen
        de la plantilla y las instrucciones con la fecha."""
        head = generation.count_tokens(
            f"Fecha de autorización del procedimiento: "
            f"{self.run.authorization_date.strftime('%d/%m/%Y')}")
        return (settings.GENERATION_CONTEXT_TOKENS - settings.MATRIX_MAX_OUTPUT_TOKENS
                - settings.PROMPT_TEMPLATE_MARGIN_TOKENS
                - generation.count_tokens(self.prompt) - head)

    def _build(self, subjects):
        """Arma el pedido de `subjects`, o devuelve `None` si no entra en el contexto."""
        space = self._space()
        aliases = {f"R{n}": s for n, s in enumerate(subjects, start=1)}
        subject_blocks = [render_subject(a, s) for a, s in aliases.items()]
        used = sum(generation.count_tokens(b) for b in subject_blocks)

        by_pk = {unit.segment.pk: unit for unit in self.loaded.units}
        own_pks = []
        for subject in subjects:
            for segment in subject.own:
                if segment.pk not in own_pks:
                    own_pks.append(segment.pk)
        chosen = {pk: by_pk[pk] for pk in own_pks}
        used += sum(generation.count_tokens(render_pliego("P0", u))
                    for u in chosen.values())
        if used > space:
            return None

        extra = [u for u in self._candidates if u.segment.pk not in chosen]
        budget = (space - used) // 2
        sizes = {u.segment.pk: generation.count_tokens(render_pliego("P0", u))
                 for u in extra}
        if sum(sizes.values()) <= budget:
            picked = extra
        else:
            scores = reranker.rerank(PLIEGO_QUESTION, [u.segment.text for u in extra])
            picked, left = [], budget
            for unit, _ in sorted(zip(extra, scores), key=lambda pair: -pair[1]):
                if sizes[unit.segment.pk] <= left:
                    picked.append(unit)
                    left -= sizes[unit.segment.pk]
        for unit in picked:
            chosen[unit.segment.pk] = unit
        used += sum(sizes[u.segment.pk] for u in picked)

        pliego = sorted(chosen.values(), key=lambda unit: unit.position)
        grounds, pliego_blocks = {}, []
        for number, unit in enumerate(pliego, start=1):
            alias = f"P{number}"
            pliego_blocks.append(render_pliego(alias, unit))
            segment = unit.segment
            grounds[alias] = {"source": "pliego", "reading": segment.reading_id,
                              "segment": segment.pk, "key": segment.key,
                              "char_start": segment.char_start, "char_end": segment.char_end}
        pliego_aliases = set(grounds)

        norm_blocks, context = [], {"corpus_version": self.run.corpus_version,
                                    "regime": self.run.regime}
        found = self._norm_search()
        if found is not None and found.selected:
            # `select_units` descuenta el máximo de salida y el margen de la 001; acá
            # rigen los de la matriz y lo que queda para la norma es `space - used`.
            prompt_tokens = (settings.GENERATION_CONTEXT_TOKENS
                             - settings.PROMPT_TEMPLATE_MARGIN_TOKENS
                             - settings.GENERATION_MAX_OUTPUT_TOKENS - space + used)
            selection = retrieval.select_units(found, prompt_tokens)
            units = NormUnit.objects.select_related("reading__document__norm").in_bulk(
                selection.unit_ids)
            score_of = {u.unit_id: u.score for u in found.units}
            shown = []
            for number, unit_id in enumerate(selection.unit_ids, start=1):
                alias = f"N{number}"
                unit = units[unit_id]
                norm_blocks.append(render_norm(alias, unit, selection.passages.get(unit_id)))
                grounds[alias] = {"source": "norma", "unit": unit_id}
                shown.append({"alias": alias, "unit": unit_id, "path": unit.path,
                              "score": score_of.get(unit_id)})
            context.update(
                questions=list(NORM_QUESTIONS),
                retrieved=[u.as_record() for u in found.units],
                selection=selection.as_record(), shown=shown)

        if not grounds:
            return _Lot(subjects, aliases, {}, set(), [], {}, context, [])
        messages = build_messages(self.prompt, self.run.authorization_date, subject_blocks,
                                  pliego_blocks, norm_blocks, list(aliases))
        return _Lot(subjects, aliases, grounds, pliego_aliases, messages,
                    build_schema(list(aliases), list(grounds)), context,
                    [u.segment.key for u in pliego])

    # -- Pedidos ----------------------------------------------------------------------------

    def _record(self, lot, output, *, parsed, anomalies, retry_of, seconds):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch,
            segment_keys=lot.segment_keys, request=output["request"],
            raw_output=output["content"], parsed=parsed, anomalies=anomalies,
            retry_of=retry_of,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": output["prompt_tokens"],
                     "completion_tokens": output["completion_tokens"]},
        )
        self.steps.append(step)
        return step

    def _run_lot(self, subjects, retry_of=None):
        lot = self._build(subjects)
        if lot is None:
            if len(subjects) > 1:
                middle = len(subjects) // 2
                self._run_lot(subjects[:middle], retry_of)
                self._run_lot(subjects[middle:], retry_of)
                return
            self.anomalies.append({"type": ANOMALY_NO_FIT, "requirement": subjects[0].number})
            self._results[subjects[0].number] = []
            return
        if not lot.grounds:
            for subject in subjects:
                self.anomalies.append({"type": ANOMALY_NO_GROUNDS,
                                       "requirement": subject.number})
                self._results[subject.number] = []
            return
        self._ask(lot, retry_of)

    def _ask(self, lot, retry_of):
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(lot.messages, lot.schema,
                                               max_tokens=max_tokens)
        except AIServiceError as error:
            self._record(
                lot, {"request": generation.build_request(lot.messages, lot.schema,
                                                          max_tokens),
                      "content": "", "prompt_tokens": None, "completion_tokens": None},
                parsed=None, retry_of=retry_of, seconds=time.monotonic() - started,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error)}])
            raise
        seconds = time.monotonic() - started
        result = {"request": output.request, "content": output.content,
                  "prompt_tokens": output.prompt_tokens,
                  "completion_tokens": output.completion_tokens}
        self.stats["requests"] += 1

        if output.finish_reason == "length" and len(lot.subjects) > 1:
            step = self._record(lot, result, parsed=None, retry_of=retry_of,
                                seconds=seconds,
                                anomalies=[{"type": ANOMALY_CUT,
                                            "requisitos": len(lot.subjects)}])
            self.stats["split_batches"] += 1
            middle = len(lot.subjects) // 2
            self._run_lot(lot.subjects[:middle], step)
            self._run_lot(lot.subjects[middle:], step)
            return

        anomalies, data = [], {}
        try:
            data = json.loads(output.content)
            if not isinstance(data, dict):
                raise ValueError("no es un objeto")
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID, "detail": f"no es JSON: {error}",
                              "finish_reason": output.finish_reason})
            data = {}
        parsed, shaped = {}, {}
        valid = set(lot.grounds)
        for alias, subject in lot.aliases.items():
            parsed[alias] = {"requisito": subject.number, "valida": False}
            if alias not in data:
                if data:
                    anomalies.append({"type": ANOMALY_MISSING_ALIAS, "alias": alias,
                                      "requirement": subject.number})
                shaped[subject.number] = None
                continue
            try:
                options, dropped = shape_item(data[alias], valid, lot.pliego_aliases)
            except InvalidItem as error:
                anomalies.append({"type": ANOMALY_INVALID, "alias": alias,
                                  "requirement": subject.number, "detail": str(error)})
                shaped[subject.number] = None
                continue
            for reason in dropped:
                anomalies.append({"type": ANOMALY_OPTION_DROPPED, "alias": alias,
                                  "requirement": subject.number, "detail": reason})
            self.stats["dropped_options"] += len(dropped)
            shaped[subject.number] = options
            parsed[alias] = {"requisito": subject.number, "valida": True,
                             "opciones": len(options), "descartadas": len(dropped)}
        step = self._record(
            lot, result, retry_of=retry_of, seconds=seconds, anomalies=anomalies,
            parsed={"requisitos": parsed, "finish_reason": output.finish_reason,
                    "fundamentos": lot.grounds, "normativa": lot.context})
        for number, options in shaped.items():
            self._step_of[number] = step
            if options is None:
                self._results[number] = None
            else:
                self._results[number] = [
                    Option(kind, [lot.grounds[a] for a in aliases], step)
                    for kind, aliases in options]

    def suggest(self, subjects):
        """Pide las consecuencias de `subjects` (lista de `Subject`, en el orden de la
        versión), reintenta una vez los requisitos de salida inválida y devuelve las
        `Suggestions`: por número de requisito, la lista de `Option` (una sola
        `no_determinada` si no hay ninguna válida)."""
        size = settings.MATRIX_CONSEQUENCES_PER_REQUEST
        for start in range(0, len(subjects), size):
            self._run_lot(subjects[start:start + size])
        invalid = [s for s in subjects if self._results.get(s.number, None) is None]
        for start in range(0, len(invalid), size):
            lot = invalid[start:start + size]
            self.stats["retried"] += len(lot)
            self._run_lot(lot, retry_of=self._step_of.get(lot[0].number))
        options = {}
        for subject in subjects:
            found = self._results.get(subject.number)
            if found is None:
                self.stats["invalid"] += 1
                self.anomalies.append({"type": ANOMALY_NO_RESULT,
                                       "requirement": subject.number})
                found = []
            if found:
                self.stats["options"] += len(found)
            else:
                self.stats["undetermined"] += 1
                found = [Option(ConsequenceType.NO_DETERMINADA.value, [],
                                self._step_of.get(subject.number))]
            options[subject.number] = found
        self.stats["requirements"] = len(subjects)
        self.stats["steps"] = len(self.steps)
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        return Suggestions(options=options, steps=self.steps,
                           anomalies=self.anomalies + step_anomalies, stats=self.stats)


def merge_results(results):
    """Junta los `RetrievalResult` de las preguntas fijas en uno: cada pasaje una vez (con el
    mejor puntaje), cada unidad con el mejor puntaje de sus pasajes, y como seleccionadas las
    que alcanzaron el umbral en alguna pregunta, de mayor a menor puntaje."""
    candidates = {}
    for result in results:
        for candidate in result.candidates:
            old = candidates.get(candidate.passage_id)
            if old is None or (candidate.score or 0) > (old.score or 0):
                candidates[candidate.passage_id] = candidate
    best, selected_ids = {}, set()
    for result in results:
        for unit in result.units:
            old = best.get(unit.unit_id)
            if old is None or (unit.score or 0) > (old.score or 0):
                best[unit.unit_id] = unit
        selected_ids.update(u.unit_id for u in result.selected)
    units = sorted(best.values(), key=lambda u: -(u.score or 0))
    selected = [u for u in units if u.unit_id in selected_ids]
    first = results[0]
    return retrieval.RetrievalResult(
        reference_date=first.reference_date, candidates=list(candidates.values()),
        units=units, selected=selected,
        max_score=units[0].score if units else None,
        reason=None if selected else retrieval.BELOW_THRESHOLD,
        parameters=dict(first.parameters),
        path_counts={f"pregunta_{n}": {"passages": len(r.candidates),
                                       "units": len(r.units)}
                     for n, r in enumerate(results, start=1)},
    )
