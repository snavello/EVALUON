"""Filtro de precisión y reparto de cada fila en firme, sugerencia o descartada (REQ-024,
REQ-033, REQ-035; plan 003, "Filtro de precisión" y "Tres destinos en vez de dos";
ADR-0021 y ADR-0022).

Principio de la spec: un requisito que falta no lo evalúa nadie; ante la duda la fila se
queda. Por eso el filtro nunca pierde una fila por una falla técnica ni por una sola
respuesta del modelo.

**Qué filas.** Las formales y económicas que propuso el modelo, después de la unificación.
No pasan por el filtro y quedan firmes: las filas técnicas y las de circulares (no están
en esta lista: se arman por otro camino), las de tramos `tabla`, las de cita amplia y las
de un tramo cuya sección el pliego titula como formal o económica (`section_class`).

**Dos preguntas, cada una en su pedido** (temperatura 0, salida estructurada con una
propiedad obligatoria por alias; la segunda no ve la respuesta de la primera):

- A (`filtro`): `mantener` o `descartar`; si descarta, un motivo de `FILTER_MOTIVES` y un
  indicio, un fragmento literal del tramo que lo sostiene.
- B (`filtro_2`): si la oferta puede presentar, ofrecer, comprometer, contradecir o
  condicionar lo que dice el fragmento: `si`, `no` o `duda`.

**Destino** (`decide`, la tabla del plan; se aplica en código a las respuestas validadas):

| A | B | Destino | `doubt_reason` |
|---|---|---|---|
| mantener | `si` | firme | |
| mantener | `no` | sugerencia | `no_coinciden` |
| mantener | `duda` | sugerencia | `duda` |
| descartar con motivo de la lista e indicio hallado | `no` | descartada | |
| descartar con motivo de la lista e indicio hallado | `si` | sugerencia | `no_coinciden` |
| descartar con motivo de la lista e indicio hallado | `duda` | sugerencia | `duda` |
| descartar con motivo fuera de la lista o indicio que no está | cualquiera | sugerencia | `descarte_sin_sustento` |
| una sola respuesta válida: `descartar`, `no` o `duda` | | sugerencia | `opinion_incompleta` |
| una sola respuesta válida: `mantener` o `si`; o ninguna válida | | firme, con la anomalía | |

Guarda en código (T-125, REQ-024): una fila descartada que comparte oración con una fila
firme del mismo tramo pasa a sugerencia con la duda `duda` (`protect_shared_sentences`).
Guarda en código (T-178): si el pliego nombra la garantía de la oferta y ninguna fila la
cubre, entra como sugerencia (`run.protect_offer_guarantee`, que usa `OFFER_GUARANTEE` y
`sentence_bounds` de este módulo).

Con `SUGGESTIONS_ENABLED` en falso, lo que sería sugerencia queda firme. Un lote cuya salida
se corta por el máximo se parte en dos, como en la extracción. Una falla del servicio no
detiene la propuesta: ese pedido no da opinión. Cada pedido se guarda en `tenders_run_step`
apenas vuelve (P6).

`Filter.filter_rows` no toca la base salvo por `tenders_run_step`; quien guarda la versión
(`run._save`) crea las filas descartadas y los requisitos sugeridos.
"""

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.models import PassName, RunStep, SegmentType
from evaluon.tenders.proposal import dedup, extraction, quotes
from evaluon.tenders.proposal.completeness import passes_of
from evaluon.tenders.proposal.extraction import BODY_CLASSES

# Las funciones de oración viven en `sentences.py` (T-234); acá se importan con los mismos
# nombres para quien las llamaba desde este módulo.
from evaluon.tenders.proposal.sentences import (  # noqa: F401
    ABBREVIATIONS,
    SENTENCE_END,
    _sentence_ends,
    sentence_bounds,
    sentence_range,
)

RULE_VERSION = "filtro-v3"

FIRME = "firme"
SUGERENCIA = "sugerencia"
DESCARTADA = "descartada"

KEEP, DISCARD = "mantener", "descartar"
YES, NO, DOUBT = "si", "no", "duda"

ANOMALY_CUT = "filtro_salida_cortada"
ANOMALY_INVALID = "filtro_salida_invalida"
ANOMALY_MISSING_ALIAS = "filtro_fila_sin_propiedad"
ANOMALY_SERVICE = "servicio"
ANOMALY_NO_OPINION = "filtro_sin_opinion"
ANOMALY_ONE_OPINION = "filtro_una_opinion"
ANOMALY_NOT_SUPPORTED = "filtro_descarte_sin_sustento"

ANOMALY_REPEATED_ALIAS = "filtro_fila_repetida"

# Un indicio trivial (una letra, una palabra suelta) está en cualquier tramo y no sostiene un
# descarte: el indicio tiene que tener al menos estas palabras con contenido (sin las de
# uso común, `dedup.content_words`).
MIN_CLUE_WORDS = 4

# Clave con la que `_no_repeats` marca los ids que el modelo repitió en un objeto.
_REPEATED = "__repetidos__"


def _no_repeats(pairs):
    """Lee un objeto JSON sin perder los ids repetidos (`json` se queda con el último): los
    deja marcados en `_REPEATED`. En un objeto interno, la marca rompe la forma esperada y la
    respuesta de esa fila no vale."""
    result, repeated = {}, []
    for key, value in pairs:
        if key in result:
            repeated.append(key)
        result[key] = value
    if repeated:
        result[_REPEATED] = repeated
    return result


MARK_OPEN, MARK_CLOSE = "<<<", ">>>"
_CLASS_LABELS = {"formal": "formal", "economico": "económico"}
_PART = re.compile(r"^# (COMÚN|PREGUNTA A|PREGUNTA B)\b.*$", re.MULTILINE)


class InvalidItem(ValueError):
    """La salida de una fila no tiene la forma del esquema."""


# --- Alcance -----------------------------------------------------------------------------------


@dataclass
class Row:
    """Una fila formal o económica en el orden del pliego. `order` es su lugar entre las
    filas que llegaron al filtro (desde 1); `repeated` son las filas que unificó la
    unificación, `[(unidad, Found)]`."""

    unit: object
    found: object
    order: int
    repeated: list = field(default_factory=list)
    # Lo que se le pregunta a la normativa (REQ-036) si no es el fragmento: la condición que
    # el pliego da por supuesta (T-178).
    query: str = ""

    @property
    def segment(self):
        return self.unit.segment

    @property
    def text(self):
        return self.segment.text[self.found.span[0]:self.found.span[1]]

    @property
    def passes(self):
        return passes_of(self.found)


# Un anexo del pliego: su clave lleva `anexo` como un componente ("sec-ii/anexo-iii/tabla-5").
_ANNEX_KEY = re.compile(r"(?:^|/)anexo(?:-|~|/|$)")


def in_scope(unit, found):
    """Si la fila pasa por el modelo: ni cita amplia, ni tramo `tabla`, ni sección
    titulada como formal o económica. Una tabla dentro de un anexo sí pasa (T-178): casi
    siempre es el formulario que la oferta completa, y sus celdas no son condiciones; las
    tablas del cuerpo del pliego (detalle de bienes, tipos de cotización) siguen firmes."""
    segment = unit.segment
    is_table = segment.segment_type == SegmentType.TABLA
    return (
        found.flag != quotes.WIDE
        and (not is_table or bool(_ANNEX_KEY.search(segment.key)))
        and segment.section_class not in BODY_CLASSES
    )


def candidates(body, repeated=None):
    """Separa las filas de `body` (`[(unidad, Found)]`, en el orden del pliego): devuelve
    las `Row` que pasan por el modelo, con su orden entre todas las filas. `repeated` es
    `{id(Found): [(unidad, Found)]}` de la unificación."""
    repeated = repeated or {}
    return [Row(unit, found, order, list(repeated.get(id(found), ())))
            for order, (unit, found) in enumerate(body, start=1) if in_scope(unit, found)]


# --- Instrucciones, esquemas y pedido -------------------------------------------------------------


def load_prompts():
    """`(instrucciones de A, instrucciones de B)`: la parte común más la de cada pregunta,
    del archivo de la versión que fija `MATRIX_PROMPT_VERSIONS["filtro"]`."""
    text = extraction.load_prompt("filtro")
    marks = list(_PART.finditer(text))
    parts = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        parts[mark.group(1)] = text[mark.end():end].strip()
    common = parts["COMÚN"]
    return (f"{common}\n\n{parts['PREGUNTA A']}", f"{common}\n\n{parts['PREGUNTA B']}")


def schema_a(aliases):
    item = {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": [KEEP, DISCARD]},
            "motivo": {"type": "string", "enum": ["", *settings.FILTER_MOTIVES]},
            "indicio": {"type": "string"},
        },
        "required": ["decision", "motivo", "indicio"],
        "additionalProperties": False,
    }
    return _schema(aliases, item)


def schema_b(aliases):
    item = {
        "type": "object",
        "properties": {"respuesta": {"type": "string", "enum": [YES, NO, DOUBT]}},
        "required": ["respuesta"],
        "additionalProperties": False,
    }
    return _schema(aliases, item)


def _schema(aliases, item):
    return {
        "type": "object",
        "properties": {alias: item for alias in aliases},
        "required": list(aliases),
        "additionalProperties": False,
    }


def shape_a(raw):
    """La respuesta de A con la forma comprobada. Lanza `InvalidItem`. El motivo y el
    indicio se comprueban después (`decide`): uno fuera de lista no invalida la respuesta."""
    if not isinstance(raw, dict) or set(raw) != {"decision", "motivo", "indicio"}:
        raise InvalidItem("no es un objeto con decision, motivo e indicio")
    if raw["decision"] not in (KEEP, DISCARD):
        raise InvalidItem("decision no es mantener ni descartar")
    if not isinstance(raw["motivo"], str) or not isinstance(raw["indicio"], str):
        raise InvalidItem("motivo e indicio tienen que ser texto")
    return {"decision": raw["decision"], "motivo": raw["motivo"], "indicio": raw["indicio"]}


def shape_b(raw):
    if not isinstance(raw, dict) or set(raw) != {"respuesta"}:
        raise InvalidItem("no es un objeto con respuesta")
    if raw["respuesta"] not in (YES, NO, DOUBT):
        raise InvalidItem("respuesta no es si, no ni duda")
    return {"respuesta": raw["respuesta"]}


def marked_text(row):
    """El texto del tramo con el fragmento de la fila entre marcas."""
    text = row.segment.text
    start, end = row.found.span
    return f"{text[:start]}{MARK_OPEN}{text[start:end]}{MARK_CLOSE}{text[end:]}"


def render_block(alias, row):
    """La fila tal como la ve el modelo: alias, documento, ruta, clase propuesta, fragmento
    y texto del tramo con el fragmento marcado."""
    segment = row.segment
    return "\n".join([
        f"[{alias}]",
        f"Documento: {row.unit.document_title}",
        f"Ruta: {segment.path or segment.label or segment.key}",
        f"Clase propuesta: {_CLASS_LABELS.get(row.found.category, row.found.category)}",
        "Fragmento:",
        row.text,
        "Texto del tramo (el fragmento va entre "
        f"{MARK_OPEN} y {MARK_CLOSE}):",
        marked_text(row),
        f"[/{alias}]",
    ])


def build_messages(prompt, aliased):
    blocks = "\n\n".join(render_block(alias, row) for alias, row in aliased)
    names = ", ".join(alias for alias, _ in aliased)
    user = (
        "Filas propuestas del pliego:\n\n"
        f"{blocks}\n\n"
        f"Devolvé un objeto JSON con una propiedad por cada alias: {names}."
    )
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


# --- Destino -----------------------------------------------------------------------------------


@dataclass
class Verdict:
    """El destino de una fila y todo lo que lo explica."""

    row: Row
    destination: str
    doubt_reason: str = ""
    reason: str = ""
    evidence: dict | None = None
    vote_a: dict | None = None
    vote_b: dict | None = None
    step_a: object = None
    step_b: object = None
    anomaly: str = ""

    @property
    def doubt(self):
        """El campo `doubt` de una sugerencia: las dos respuestas, el indicio literal con su
        ubicación y los pedidos que las produjeron."""
        return {
            "vote_a": self.vote_a,
            "vote_b": self.vote_b,
            "evidence": self.evidence,
            "step_a": self.step_a.pk if self.step_a is not None else None,
            "step_b": self.step_b.pk if self.step_b is not None else None,
        }


def find_evidence(segment, indicio):
    """El indicio ubicado dentro del tramo: `{segment, char_start, char_end, text}` con
    posiciones en el texto canónico y el texto literal del tramo, o `None` si no está."""
    span = quotes.locate(segment.text, indicio)
    if span is None:
        return None
    start, end = quotes.absolute(segment, span)
    return {"segment": segment.pk, "char_start": start, "char_end": end,
            "text": segment.text[span[0]:span[1]]}


def decide(row, a, b):
    """El `Verdict` de una fila según las respuestas validadas de A y B (`None` si esa
    respuesta no sirvió). Es la tabla de destinos del plan; ver el módulo."""
    evidence = None
    supported = False
    if a is not None and a["decision"] == DISCARD:
        evidence = find_evidence(row.segment, a["indicio"])
        supported = (
            a["motivo"] in settings.FILTER_MOTIVES
            and evidence is not None
            and len(dedup.content_words(dedup.normalize(evidence["text"]))) >= MIN_CLUE_WORDS
        )
    verdict = Verdict(row, FIRME, vote_a=a, vote_b=b, evidence=evidence)

    if a is None and b is None:
        verdict.anomaly = ANOMALY_NO_OPINION
        return verdict
    if a is None or b is None:
        only = a["decision"] if a is not None else b["respuesta"]
        if only in (KEEP, YES):
            verdict.anomaly = ANOMALY_ONE_OPINION
            return verdict
        verdict.destination = SUGERENCIA
        verdict.doubt_reason = "opinion_incompleta"
        verdict.anomaly = ANOMALY_ONE_OPINION
        return verdict

    answer = b["respuesta"]
    if a["decision"] == KEEP:
        if answer != YES:
            verdict.destination = SUGERENCIA
            verdict.doubt_reason = "no_coinciden" if answer == NO else "duda"
        return verdict
    if not supported:
        verdict.destination = SUGERENCIA
        verdict.doubt_reason = "descarte_sin_sustento"
        verdict.anomaly = ANOMALY_NOT_SUPPORTED
        return verdict
    if answer == NO:
        verdict.destination = DESCARTADA
        verdict.reason = a["motivo"]
        return verdict
    verdict.destination = SUGERENCIA
    verdict.doubt_reason = "no_coinciden" if answer == YES else "duda"
    return verdict


ANOMALY_SHARED_SENTENCE = "filtro_comparte_oracion"


def protect_shared_sentences(verdicts):
    """Guarda en código (REQ-024): una fila que comparte oración con una fila firme del mismo
    tramo no puede descartarse, porque es parte de una condición que el filtro mantuvo (la
    cola de la misma oración leída sola parece otra cosa). Pasa a sugerencia con la duda
    `duda`; sus dos respuestas y el indicio quedan en `doubt`. La comparación es por
    posiciones del texto canónico: dos filas comparten oración si sus fragmentos tocan una
    misma oración del tramo. Las firmes se miden antes de aplicar esta guarda."""
    firm = {}
    for verdict in verdicts:
        if verdict.destination == FIRME:
            row = verdict.row
            firm.setdefault(row.segment.pk, []).append(
                sentence_range(row.segment.text, row.found.span))
    for verdict in verdicts:
        if verdict.destination != DESCARTADA:
            continue
        row = verdict.row
        first, last = sentence_range(row.segment.text, row.found.span)
        if any(first <= other_last and other_first <= last
               for other_first, other_last in firm.get(row.segment.pk, ())):
            verdict.destination = SUGERENCIA
            verdict.doubt_reason = "duda"
            verdict.reason = ""
            verdict.anomaly = ANOMALY_SHARED_SENTENCE


# La garantía con que se mantiene la oferta, en singular o plural, con o sin artículo.
OFFER_GUARANTEE = re.compile(
    r"garant[ií]as?\s+de\s+(?:mantenimiento\s+de\s+)?(?:la\s+)?oferta", re.IGNORECASE
)
ANOMALY_OFFER_GUARANTEE = "filtro_garantia_oferta_mencionada"


# --- El filtro ---------------------------------------------------------------------------------


@dataclass
class Result:
    verdicts: list
    steps: list
    anomalies: list
    stats: dict

    def of(self, destination):
        return [v for v in self.verdicts if v.destination == destination]


class Filter:
    """Hace los pedidos del filtro de una propuesta (`MatrixRun`) y guarda cada uno en
    `tenders_run_step`."""

    def __init__(self, run):
        self.run = run
        self.prompt_a, self.prompt_b = load_prompts()
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "requests_a": 0, "requests_b": 0, "split_batches": 0,
                      "failed_requests": 0}
        self._batch = {PassName.FILTRO: 0, PassName.FILTRO_2: 0}

    def _record(self, name, result, *, parsed, anomalies, retry_of, seconds, keys):
        self._batch[name] += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=name, batch=self._batch[name], segment_keys=keys,
            request=result["request"], raw_output=result["content"], parsed=parsed,
            anomalies=anomalies, retry_of=retry_of,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": result["prompt_tokens"],
                     "completion_tokens": result["completion_tokens"]},
        )
        self.steps.append(step)
        return step

    def ask(self, name, rows, retry_of=None):
        """Un pedido de la pregunta `name` (`FILTRO` o `FILTRO_2`) con `rows` (o dos, si la
        salida se corta). Devuelve, por fila y en orden, `(respuesta validada o None,
        pedido)`."""
        first = name == PassName.FILTRO
        shape = shape_a if first else shape_b
        aliased = [(f"F{n}", row) for n, row in enumerate(rows, start=1)]
        keys = [row.segment.key for row in rows]
        messages = build_messages(self.prompt_a if first else self.prompt_b, aliased)
        schema = (schema_a if first else schema_b)([alias for alias, _ in aliased])
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens)
        except AIServiceError as error:
            # Una falla técnica no pierde la fila: el pedido queda registrado y la fila
            # sigue sin esa opinión.
            self.stats["failed_requests"] += 1
            step = self._record(
                name,
                {"request": generation.build_request(messages, schema, max_tokens),
                 "content": "", "prompt_tokens": None, "completion_tokens": None},
                parsed=None, retry_of=retry_of, seconds=time.monotonic() - started,
                keys=keys,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error)}])
            return [(None, step)] * len(rows)
        seconds = time.monotonic() - started
        result = {"request": output.request, "content": output.content,
                  "prompt_tokens": output.prompt_tokens,
                  "completion_tokens": output.completion_tokens}
        self.stats["requests"] += 1
        self.stats["requests_a" if first else "requests_b"] += 1

        if output.finish_reason == "length" and len(rows) > 1:
            step = self._record(name, result, parsed=None, retry_of=retry_of,
                                seconds=seconds, keys=keys,
                                anomalies=[{"type": ANOMALY_CUT, "filas": len(rows)}])
            self.stats["split_batches"] += 1
            middle = len(rows) // 2
            return (self.ask(name, rows[:middle], retry_of=step)
                    + self.ask(name, rows[middle:], retry_of=step))

        anomalies, data = [], {}
        try:
            data = json.loads(output.content, object_pairs_hook=_no_repeats)
            if not isinstance(data, dict):
                raise ValueError("no es un objeto")
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID, "detail": f"no es JSON: {error}",
                              "finish_reason": output.finish_reason})
            data = {}
        repeated_ids = set(data.pop(_REPEATED, ())) if isinstance(data, dict) else set()
        answers, parsed = [], {}
        for alias, row in aliased:
            parsed[alias] = {"segmento": row.segment.pk, "valida": False}
            answer = None
            if alias in repeated_ids:
                anomalies.append({"type": ANOMALY_REPEATED_ALIAS, "alias": alias,
                                  "segment": row.segment.pk})
            elif alias not in data:
                if data:
                    anomalies.append({"type": ANOMALY_MISSING_ALIAS, "alias": alias,
                                      "segment": row.segment.pk})
            else:
                try:
                    answer = shape(data[alias])
                    parsed[alias] = {"segmento": row.segment.pk, "valida": True, **answer}
                except InvalidItem as error:
                    anomalies.append({"type": ANOMALY_INVALID, "alias": alias,
                                      "segment": row.segment.pk, "detail": str(error)})
            answers.append(answer)
        step = self._record(
            name, result, retry_of=retry_of, seconds=seconds, keys=keys,
            anomalies=anomalies,
            parsed={"filas": parsed, "finish_reason": output.finish_reason})
        return [(answer, step) for answer in answers]

    def filter_rows(self, rows):
        """Pregunta A y pregunta B de cada lote de `FILTER_BATCH_ROWS` filas, y reparte
        cada fila. Devuelve el `Result`."""
        size = max(settings.FILTER_BATCH_ROWS, 1)
        verdicts = []
        for at in range(0, len(rows), size):
            batch = rows[at:at + size]
            answers_a = self.ask(PassName.FILTRO, batch)
            answers_b = self.ask(PassName.FILTRO_2, batch)
            for row, (a, step_a), (b, step_b) in zip(batch, answers_a, answers_b):
                verdict = decide(row, a, b)
                verdict.step_a, verdict.step_b = step_a, step_b
                verdicts.append(verdict)
        protect_shared_sentences(verdicts)
        for verdict in verdicts:
            if verdict.destination == SUGERENCIA and not settings.SUGGESTIONS_ENABLED:
                verdict.destination = FIRME
                verdict.anomaly = verdict.anomaly or "filtro_sugerencias_apagadas"
        self._count(rows, verdicts)
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        return Result(verdicts=verdicts, steps=self.steps,
                      anomalies=self.anomalies + step_anomalies, stats=self.stats)

    def _count(self, rows, verdicts):
        discarded = [v for v in verdicts if v.destination == DESCARTADA]
        suggestions = [v for v in verdicts if v.destination == SUGERENCIA]
        self.stats.update({
            "rows": len(rows),
            "firm": sum(1 for v in verdicts if v.destination == FIRME),
            "suggestions": len(suggestions),
            "discarded": len(discarded),
            "discarded_by_reason": dict(Counter(v.reason for v in discarded)),
            "discarded_by_pass": dict(Counter(v.row.passes[0] for v in discarded)),
            "suggestions_by_reason": dict(Counter(v.doubt_reason for v in suggestions)),
            "suggestions_by_pass": dict(Counter(v.row.passes[0] for v in suggestions)),
            # Firmes porque ninguna opinión sirvió, o la única mantenía.
            "firm_by_failure": sum(1 for v in verdicts if v.destination == FIRME
                                   and v.anomaly in (ANOMALY_NO_OPINION, ANOMALY_ONE_OPINION)),
            "steps": len(self.steps),
        })
