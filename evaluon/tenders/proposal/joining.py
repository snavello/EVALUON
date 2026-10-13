"""Unión de las filas del mismo asunto (T-258; REQ-101; ADR-0054, regla 3; hallazgos H3 y H4 del
comité de calidad del 2026-10-12).

Una fila es una unidad de sentido: la oración completa y las oraciones cortas contiguas que siguen
el mismo asunto. El código une solo las continuaciones explícitas (`sentences.is_continuation`);
las demás las tiene que juntar la extracción, y el modelo a veces las parte en dos filas («La
existencia de deuda también deberá verificarse…» después de la verificación de deuda, la condición
MiPyME y su vigencia). Esta pasada corta, después de la completitud y antes de la unificación y del
filtro, le pregunta al modelo por cada par candidato si es el mismo requisito o son dos, con su
`razonamiento` antes de la respuesta (ADR-0055, regla 1):

- **Filas contiguas** (`contiguas`): dos filas seguidas del mismo tramo, sin otra fila entre ellas
  y con a lo sumo dos oraciones cortas en el medio (por ejemplo, cómo se cuenta un plazo entre el
  plazo y su prórroga automática, o cómo se hace el trámite de una declaración). Si son el mismo requisito, quedan en una fila cuya cita va de la
  primera a la última: un recorte contiguo del tramo, literal (REQ-025).
- **Nota de una tabla** (`nota_de_tabla`): una fila de un tramo `tabla` y la última fila del tramo
  del que cuelga la tabla (su padre por la clave). Si la nota complementa esa fila (la declaración
  que ya es fila), pasa a ser una cita más de esa fila (alcance `repetida`, como las citas de las
  filas que repiten una condición) y deja de ser una fila propia.

Se une solo si el modelo responde «una». Con «dos», con una respuesta que no tiene la forma, sin la
propiedad del par o con una falla del servicio, las filas quedan como estaban: nada se pierde. Dos
filas con distinta opción (`opcion`: una vacía y otra no, o dos distintas) no son un par y nunca se
unen (H-258-2): la fila de toda oferta no pasa a ser de una opción. Cada
pedido se guarda en `tenders_run_step` apenas vuelve (P6), con la pasada `unificacion` (la pasada de
las filas que se juntan; el esquema no cambia) y `parsed.pasada = "union_oraciones"`, la versión y
la huella de su instrucción (`matriz-union-vN`) y lo que se unió, con sus posiciones.
"""

import json
import time
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.models import PassName, RunStep, SegmentType
from evaluon.tenders.proposal import extraction, quotes, sentences
from evaluon.tenders.proposal.completeness import passes_of

PASS_LABEL = "union_oraciones"
INSTRUCTION = "union"

ONE, TWO = "una", "dos"
KEY_REASONING = "razonamiento"
KEY_ANSWER = "filas"
# El razonamiento es una o dos oraciones (como en el filtro).
REASONING_MAX_CHARS = 400
# Pares por pedido: pocos, para que cada uno tenga la atención del modelo.
PAIRS_PER_REQUEST = 6
# Lo que puede haber entre dos filas contiguas: a lo sumo dos oraciones, de hasta 400 caracteres.
GAP_MAX_SENTENCES = 2
GAP_MAX_CHARS = 400
MAX_OUTPUT_TOKENS = 1024
# Cuánto del texto de la tabla, antes de la nota, ve el modelo (de qué es la tabla).
NOTE_CONTEXT_CHARS = 300

CONTIGUOUS = "contiguas"
TABLE_NOTE = "nota_de_tabla"

ANOMALY_INVALID = "union_salida_invalida"
ANOMALY_MISSING_ALIAS = "union_par_sin_propiedad"
ANOMALY_SERVICE = "servicio"


@dataclass
class Pair:
    """Dos filas que pueden ser el mismo requisito: `first` es la fila que queda."""

    kind: str
    first_unit: object
    first: object
    second_unit: object
    second: object
    between: str = ""


@dataclass
class Joining:
    """Lo que dejó la pasada: los pedidos, las anomalías, las cuentas y las notas de tabla que
    pasaron a ser citas de otra fila (`attached`: `id(Found)` de la fila que queda → `[(unidad,
    Found)]`)."""

    steps: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    attached: dict = field(default_factory=dict)


# --- Pares candidatos -----------------------------------------------------------------------------


def _plain(found):
    return found.flag != quotes.WIDE and not found.too_long


def same_option(first, second):
    """Si las dos filas tienen la misma opción (las dos vacías, o la misma): si no, no se unen."""
    return getattr(first, "option", "") == getattr(second, "option", "")


def _gap_is_short(text):
    """Si entre dos filas hay a lo sumo `GAP_MAX_SENTENCES` oraciones cortas (o nada)."""
    chunk = text.strip()
    if not chunk:
        return True
    return (len(chunk) <= GAP_MAX_CHARS
            and len(sentences.sentence_spans(chunk)) <= GAP_MAX_SENTENCES)


def contiguous_pairs(unit, found_list):
    """Los pares de filas seguidas del mismo tramo (`contiguas`), en el orden del tramo. Un tramo
    `tabla` no tiene oraciones: sus filas no se unen así."""
    if unit.segment.segment_type == SegmentType.TABLA:
        return []
    text = unit.segment.text
    rows = sorted((f for f in found_list if _plain(f)), key=lambda f: f.span)
    limit = settings.ASSESSMENT_CITATION_MAX_CHARS
    pairs = []
    for first, second in zip(rows, rows[1:]):
        if second.span[0] < first.span[1]:
            continue
        between = text[first.span[1]:second.span[0]]
        if (not _gap_is_short(between) or second.span[1] - first.span[0] > limit
                or not same_option(first, second)):
            continue
        pairs.append(Pair(CONTIGUOUS, unit, first, unit, second, between=between.strip()))
    return pairs


def table_pairs(units, decisions):
    """Los pares de nota de tabla: cada fila de un tramo `tabla` con la última fila del tramo del
    que cuelga la tabla (el padre por la clave, en la misma lectura)."""
    by_key = {(getattr(u.segment, "reading_id", None), u.segment.key): u for u in units}
    pairs = []
    for unit in units:
        segment = unit.segment
        if segment.segment_type != SegmentType.TABLA:
            continue
        notes = [f for f in decisions[segment.pk].found if f.flag != quotes.WIDE]
        if not notes:
            continue
        parent = by_key.get((getattr(segment, "reading_id", None),
                             sentences.parent_key(segment.key)))
        if parent is None:
            continue
        rows = [f for f in decisions[parent.segment.pk].found if _plain(f)]
        if not rows:
            continue
        last = max(rows, key=lambda f: f.span)
        pairs += [Pair(TABLE_NOTE, parent, last, unit, note) for note in notes
                  if same_option(last, note)]
    return pairs


# --- Pedido ---------------------------------------------------------------------------------------


def _text(unit, found):
    return " ".join(quotes.visible(unit.segment.text[found.span[0]:found.span[1]]).split())


def render_pair(alias, pair):
    """El par tal como lo ve el modelo."""
    first = pair.first_unit
    lines = [f"[{alias}]", f"Documento: {first.document_title}",
             f"Ruta: {first.segment.path or first.segment.label or first.segment.key}"]
    if first.heading:
        lines.append(f"Encabezado: {first.heading}")
    lines.append(f"Fila A: «{_text(first, pair.first)}»")
    if pair.kind == TABLE_NOTE:
        second = pair.second_unit.segment
        lines.append("La fila B está en una tabla que cuelga del mismo punto "
                     f"({second.path or second.label or second.key}).")
        before = " ".join(quotes.visible(second.text[:pair.second.span[0]]).split())
        if len(before) > NOTE_CONTEXT_CHARS:
            before = "…" + before[-NOTE_CONTEXT_CHARS:]
        if before:
            lines.append(f"Texto de la tabla, antes de la fila B: «{before}»")
    elif pair.between:
        lines.append(f"Entre las dos, el pliego dice: «{' '.join(quotes.visible(pair.between).split())}»")
    lines.append(f"Fila B: «{_text(pair.second_unit, pair.second)}»")
    lines.append(f"[/{alias}]")
    return "\n".join(lines)


def build_messages(prompt, aliased):
    blocks = "\n\n".join(render_pair(alias, pair) for alias, pair in aliased)
    names = ", ".join(alias for alias, _ in aliased)
    user = ("Pares de filas propuestas:\n\n"
            f"{blocks}\n\n"
            f"Devolvé un objeto JSON con una propiedad por cada alias: {names}.")
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


def build_schema(aliases):
    item = {
        "type": "object",
        "properties": {
            KEY_REASONING: {"type": "string", "maxLength": REASONING_MAX_CHARS},
            KEY_ANSWER: {"type": "string", "enum": [ONE, TWO]},
        },
        "required": [KEY_REASONING, KEY_ANSWER],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {alias: item for alias in aliases},
            "required": list(aliases), "additionalProperties": False}


def shape_answer(raw):
    """`(razonamiento, respuesta)` de un par, o `None` si no tiene la forma."""
    if (not isinstance(raw, dict) or set(raw) != {KEY_REASONING, KEY_ANSWER}
            or raw[KEY_ANSWER] not in (ONE, TWO) or not isinstance(raw[KEY_REASONING], str)):
        return None
    return raw[KEY_REASONING], raw[KEY_ANSWER]


# --- La pasada ------------------------------------------------------------------------------------


def _span_record(unit, found):
    return {"segmento": unit.segment.pk, "clave": unit.segment.key,
            "inicio": found.span[0], "fin": found.span[1]}


class Joiner:
    """Hace los pedidos de la unión de una propuesta (`MatrixRun`) y aplica lo que responde el
    modelo a las disposiciones."""

    def __init__(self, run):
        self.run = run
        self.instruction = extraction.load_instruction(INSTRUCTION)
        self.prompt = self.instruction.text
        self.result = Joining(stats={"pairs": 0, "requests": 0, "joined": 0,
                                     "notes_attached": 0, "failed_requests": 0})
        self._batch = 0

    @property
    def steps(self):
        """Los pedidos guardados (los cuenta el registro de una propuesta fallida)."""
        return self.result.steps

    def _record(self, keys, request, content, parsed, anomalies, seconds, output=None):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=PassName.UNIFICACION.value, batch=self._batch,
            segment_keys=keys, request=request, raw_output=content,
            parsed=extraction.with_instruction({"pasada": PASS_LABEL, **(parsed or {})},
                                               self.instruction),
            anomalies=anomalies,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": getattr(output, "prompt_tokens", None),
                     "completion_tokens": getattr(output, "completion_tokens", None)})
        self.result.steps.append(step)
        return step

    def ask(self, pairs):
        """Un pedido con `pairs`. Devuelve `{índice del par: respuesta}` con las respuestas que
        tienen la forma pedida."""
        aliased = [(f"P{n}", pair) for n, pair in enumerate(pairs, start=1)]
        messages = build_messages(self.prompt, aliased)
        schema = build_schema([alias for alias, _ in aliased])
        keys = sorted({p.first_unit.segment.key for p in pairs}
                      | {p.second_unit.segment.key for p in pairs})
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=MAX_OUTPUT_TOKENS)
        except AIServiceError as error:
            # Una falla técnica no une nada: las filas quedan como estaban.
            self.result.stats["failed_requests"] += 1
            self._record(keys, generation.build_batch_request(messages, schema, MAX_OUTPUT_TOKENS),
                         "", None, [{"type": ANOMALY_SERVICE, "reason": error.reason,
                                     "service": error.service, "message": str(error)}],
                         time.monotonic() - started)
            return {}, None
        seconds = time.monotonic() - started
        self.result.stats["requests"] += 1
        anomalies, answers, parsed = [], {}, {}
        try:
            data = json.loads(output.content)
            if not isinstance(data, dict):
                raise ValueError("no es un objeto")
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID, "detail": str(error),
                              "finish_reason": output.finish_reason})
            data = {}
        for index, (alias, pair) in enumerate(aliased):
            record = {"tipo": pair.kind, "a": _span_record(pair.first_unit, pair.first),
                      "b": _span_record(pair.second_unit, pair.second)}
            if alias not in data:
                if data:
                    anomalies.append({"type": ANOMALY_MISSING_ALIAS, "alias": alias})
                parsed[alias] = {**record, "valida": False}
                continue
            shaped = shape_answer(data[alias])
            if shaped is None:
                anomalies.append({"type": ANOMALY_INVALID, "alias": alias})
                parsed[alias] = {**record, "valida": False}
                continue
            answers[index] = shaped[1]
            parsed[alias] = {**record, "valida": True, KEY_REASONING: shaped[0],
                             KEY_ANSWER: shaped[1]}
        step = self._record(keys, output.request, output.content,
                            {"pares": parsed, "finish_reason": output.finish_reason},
                            anomalies, seconds, output)
        self.result.anomalies += anomalies
        return answers, step

    def _answer(self, pairs):
        answers = {}
        for start in range(0, len(pairs), PAIRS_PER_REQUEST):
            chunk = pairs[start:start + PAIRS_PER_REQUEST]
            got, _ = self.ask(chunk)
            answers.update({start + index: answer for index, answer in got.items()})
        return answers

    def join(self, units, decisions):
        """Pregunta por los pares de filas contiguas, une las que el modelo dice que son una, y
        después hace lo mismo con las notas de tabla. Cambia `decisions` y devuelve el `Joining`."""
        survivor = {}

        def target_of(found):
            while id(found) in survivor:
                found = survivor[id(found)]
            return found

        pairs = [pair for unit in units
                 for pair in contiguous_pairs(unit, decisions[unit.segment.pk].found)]
        self.result.stats["pairs"] += len(pairs)
        answers = self._answer(pairs)
        limit = settings.ASSESSMENT_CITATION_MAX_CHARS
        for index, pair in enumerate(pairs):
            if answers.get(index) != ONE:
                continue
            first, second = target_of(pair.first), pair.second
            if second.span[1] - first.span[0] > limit or not same_option(first, second):
                continue
            first.span = (first.span[0], second.span[1])
            first.unit = first.span
            first.fragments = [*first.fragments, *second.fragments]
            first.passes = list(dict.fromkeys([*passes_of(first), *passes_of(second)]))
            decision = decisions[pair.first_unit.segment.pk]
            decision.found = [f for f in decision.found if f is not second]
            survivor[id(second)] = first
            self.result.stats["joined"] += 1

        notes = table_pairs(units, decisions)
        self.result.stats["pairs"] += len(notes)
        answers = self._answer(notes)
        for index, pair in enumerate(notes):
            if answers.get(index) != ONE or not same_option(target_of(pair.first), pair.second):
                continue
            decision = decisions[pair.second_unit.segment.pk]
            decision.found = [f for f in decision.found if f is not pair.second]
            self.result.attached.setdefault(id(target_of(pair.first)), []).append(
                (pair.second_unit, pair.second))
            self.result.stats["notes_attached"] += 1
        return self.result
