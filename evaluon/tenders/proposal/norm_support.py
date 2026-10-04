"""Respaldo normativo de cada sugerencia de condición (REQ-036, REQ-022; plan 003,
"Consulta normativa"; ADR-0022; principios P3, P6, P8).

**La norma solo confirma, nunca descarta.** Este módulo no tiene ningún camino que cambie el
estado de una fila: recibe los veredictos del filtro, no los toca y devuelve únicamente
respaldos para insertar en `tenders_norm_support`. Que una condición no figure en la norma
cargada no prueba que no se exija (el pliego puede agregar exigencias propias): sin respaldo,
la sugerencia queda exactamente como estaba.

Para cada sugerencia, una consulta:

1. Sin régimen a la fecha de autorización (`run.regime` vacío) no se consulta nada: queda la
   anomalía `sin_regimen`.
2. La pregunta fija (`QUESTION`) lleva el fragmento del pliego, recortado en un límite de
   oración a `NORM_SUPPORT_QUERY_MAX_CHARS`. Pasa por `retrieve` de la 001 con la fecha de
   autorización (régimen y marco nacional; AFIP y ARCA valen lo mismo, ADR-0010).
3. Solo cuentan unidades de normas con puntaje de al menos `NORM_SUPPORT_MIN_SCORE`: no los
   considerandos, ni los dictámenes ni las recomendaciones de auditoría. Hasta
   `NORM_SUPPORT_MAX_UNITS`, las de mayor puntaje; `select_units` de la 001 elige las que
   caben en el pedido.
4. Un pedido corto a `generation_batch` (alias `N1…`, salida estructurada): por unidad,
   `exige` (`si` o `no`) y `cita`.
5. Una unidad es respaldo solo con las tres condiciones: puntaje de al menos
   `NORM_SUPPORT_MIN_SCORE`, `exige` igual a `si` y `cita` hallada, palabra por palabra, en el
   texto de la unidad en la base (`quotes.locate`). Un alias inexistente o una cita que no
   está invalidan esa unidad. Se guardan hasta dos por sugerencia, las de mayor puntaje; el
   texto guardado es el recorte de la unidad, no lo que escribió el modelo.

Cada consulta queda en `tenders_run_step` (`respaldo_normativo`): pregunta, unidades,
puntajes, respuesta y versión de la normativa. Una falla de la recuperación o del pedido deja
la sugerencia sin respaldo, con su anomalía; nunca detiene la propuesta.
"""

import dataclasses
import json
import time
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation
from evaluon.audit import services as audit
from evaluon.norms import indexing
from evaluon.norms.models import Category
from evaluon.norms.models import Unit as NormUnit
from evaluon.norms.models import UnitType
from evaluon.queries import answering, retrieval
from evaluon.tenders.models import PassName, RunStep
from evaluon.tenders.proposal import extraction, quotes

QUESTION = (
    "El pliego de un procedimiento de contratación dice: «{fragment}». ¿Qué artículo del "
    "régimen de contrataciones exige esta condición a las ofertas?"
)
# Respaldos que se guardan por sugerencia.
MAX_SUPPORTS = 2
# Máximo de la salida del pedido (por cada unidad, un sí o no y una cita corta).
MAX_OUTPUT_TOKENS = 1500
# Normas que no exigen: fundamentan o interpretan (plan 003, "Consulta normativa").
NOT_NORMS = (Category.DICTAMEN_LEGAL.value, Category.RECOMENDACION_AUDITORIA.value)

ANOMALY_NO_REGIME = "sin_regimen"
ANOMALY_RETRIEVAL = "respaldo_recuperacion_fallo"
ANOMALY_SERVICE = "respaldo_pedido_fallo"
ANOMALY_INVALID = "respaldo_salida_invalida"
ANOMALY_BAD_ALIAS = "respaldo_alias_inexistente"
ANOMALY_BAD_ITEM = "respaldo_unidad_invalida"
ANOMALY_QUOTE_MISSING = "respaldo_cita_no_esta"
ANOMALY_NO_FIT = "respaldo_unidades_no_entran"
ANOMALY_CORPUS_CHANGED = "respaldo_normativa_cambio"


def trim_fragment(text, limit):
    """El fragmento recortado a `limit` caracteres como máximo, en el último límite de oración
    que entre; sin límite de oración, en el último espacio. Un texto que cabe no se toca."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(mark) for mark in (". ", "; ", "? ", "! "))
    if end > 0:
        return cut[:end + 1]
    space = cut.rfind(" ")
    return cut[:space] if space > 0 else cut


def build_question(fragment):
    return QUESTION.format(
        fragment=trim_fragment(fragment, settings.NORM_SUPPORT_QUERY_MAX_CHARS))


def build_schema(aliases):
    item = {
        "type": "object",
        "properties": {"exige": {"type": "string", "enum": ["si", "no"]},
                       "cita": {"type": "string"}},
        "required": ["exige", "cita"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {alias: item for alias in aliases},
            "required": list(aliases), "additionalProperties": False}


def build_head(authorization_date, question):
    return (f"Fecha de autorización del procedimiento: "
            f"{authorization_date.strftime('%d/%m/%Y')}\n\n{question}\n\nUnidades:")


def build_messages(prompt, head, blocks, aliases):
    user = "\n\n".join([head, *blocks,
                        "Devolvé un objeto JSON con una propiedad por cada alias: "
                        + ", ".join(aliases) + "."])
    return [{"role": "system", "content": prompt}, {"role": "user", "content": user}]


@dataclass
class Support:
    """Un respaldo listo para guardar: la cita es el recorte de la unidad."""

    unit: object
    unit_label: str
    char_start: int
    char_end: int
    text: str
    score: float
    step: object


@dataclass
class Result:
    supports: dict = field(default_factory=dict)  # id(found) -> [Support]
    steps: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


class Supporter:
    """Hace las consultas de respaldo de una propuesta (`MatrixRun`)."""

    pass_name = PassName.RESPALDO_NORMATIVO

    def __init__(self, run):
        self.run = run
        self.prompt = extraction.load_prompt("respaldo")
        self.steps = []
        self.anomalies = []
        self.stats = {"suggestions": 0, "consulted": 0, "with_support": 0, "supports": 0,
                      "no_regime": 0, "failed_retrieval": 0, "failed_requests": 0,
                      "requests": 0, "invalid": 0, "no_units": 0}
        self._batch = 0

    def _record(self, request, content, *, parsed, anomalies, seconds, tokens=(None, None)):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch, segment_keys=[],
            request=request, raw_output=content, parsed=parsed, anomalies=anomalies,
            timings={"seconds": round(seconds, 3), "prompt_tokens": tokens[0],
                     "completion_tokens": tokens[1]},
        )
        self.steps.append(step)
        return step

    def _context(self, question):
        return {"question": question, "regime": self.run.regime,
                "corpus_version": self.run.corpus_version,
                "min_score": settings.NORM_SUPPORT_MIN_SCORE}

    def support(self, verdicts):
        """Consulta cada sugerencia de `verdicts` (los `filter.Verdict` de destino
        sugerencia) y devuelve el `Result`. No cambia ningún veredicto ni ninguna fila."""
        supports = {}
        for verdict in verdicts:
            self.stats["suggestions"] += 1
            found = self._consult(verdict.row)
            if found:
                supports[id(verdict.row.found)] = found
        self.stats["steps"] = len(self.steps)
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        return Result(supports=supports, steps=self.steps,
                      anomalies=self.anomalies + step_anomalies, stats=self.stats)

    # -- Una consulta -----------------------------------------------------------------------

    def _consult(self, row):
        key = row.segment.key
        if not self.run.regime:
            self.stats["no_regime"] += 1
            self.anomalies.append({"type": ANOMALY_NO_REGIME, "segment": key})
            return []
        question = build_question(row.text)
        context = self._context(question)
        self.stats["consulted"] += 1
        started = time.monotonic()
        try:
            now = audit.current_corpus_version()
            if now != self.run.corpus_version:
                self.anomalies.append({"type": ANOMALY_CORPUS_CHANGED, "segment": key,
                                       "begin": self.run.corpus_version, "now": now})
            result = retrieval.retrieve(question, self.run.authorization_date)
        except AIServiceError as error:
            self.stats["failed_retrieval"] += 1
            self._record(context, "", parsed=None, seconds=time.monotonic() - started,
                         anomalies=[{"type": ANOMALY_RETRIEVAL, "reason": error.reason,
                                     "service": error.service, "message": str(error),
                                     "segment": key}])
            return []

        units = self._candidates(result)
        context["retrieved"] = [u.as_record() for u in result.units]
        if not units:
            self.stats["no_units"] += 1
            self._record(context, "", parsed={"unidades": {}, "respaldos": 0},
                         seconds=time.monotonic() - started, anomalies=[])
            return []
        return self._ask(row, question, context, result, units, started)

    def _candidates(self, result):
        """Las unidades de normas con puntaje de al menos `NORM_SUPPORT_MIN_SCORE`, las de
        mayor puntaje, hasta `NORM_SUPPORT_MAX_UNITS`."""
        floor = settings.NORM_SUPPORT_MIN_SCORE
        scored = [u for u in result.units if u.score is not None and u.score >= floor]
        found = NormUnit.objects.select_related("reading__document__norm").in_bulk(
            [u.unit_id for u in scored])
        norms = [u for u in scored
                 if u.unit_id in found
                 and found[u.unit_id].unit_type != UnitType.CONSIDERANDO
                 and found[u.unit_id].reading.document.norm.category not in NOT_NORMS]
        return norms[:settings.NORM_SUPPORT_MAX_UNITS]

    def _ask(self, row, question, context, result, units, started):
        key = row.segment.key
        head = build_head(self.run.authorization_date, question)
        prompt_tokens = generation.count_tokens(self.prompt) + generation.count_tokens(head)
        narrowed = dataclasses.replace(result, selected=list(units))
        selection = retrieval.select_units(narrowed, prompt_tokens)
        context["selection"] = selection.as_record()
        score_of = {u.unit_id: u.score for u in result.units}
        if not selection.unit_ids:
            self.stats["no_units"] += 1
            self._record(context, "", parsed={"unidades": {}, "respaldos": 0},
                         seconds=time.monotonic() - started,
                         anomalies=[{"type": ANOMALY_NO_FIT, "segment": key}])
            return []
        loaded = NormUnit.objects.select_related("reading__document__norm").in_bulk(
            selection.unit_ids)
        shown, blocks = {}, []
        for number, unit_id in enumerate(selection.unit_ids, start=1):
            alias = f"N{number}"
            shown[alias] = loaded[unit_id]
            blocks.append(answering.unit_block(f"[{alias}]", loaded[unit_id],
                                               selection.passages.get(unit_id))
                          + f"\n[/{alias}]")
        context["shown"] = [{"alias": alias, "unit": unit.pk, "path": unit.path,
                             "score": score_of.get(unit.pk)} for alias, unit in shown.items()]
        messages = build_messages(self.prompt, head, blocks, list(shown))
        schema = build_schema(list(shown))
        try:
            output = generation.generate_batch(messages, schema, max_tokens=MAX_OUTPUT_TOKENS)
        except AIServiceError as error:
            self.stats["failed_requests"] += 1
            self._record(
                {**context, "request": generation.build_request(
                    messages, schema, MAX_OUTPUT_TOKENS)},
                "", parsed=None, seconds=time.monotonic() - started,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error),
                            "segment": key}])
            return []
        self.stats["requests"] += 1

        anomalies, accepted, parsed = [], [], {}
        try:
            data = json.loads(output.content)
            if not isinstance(data, dict):
                raise ValueError("no es un objeto")
        except ValueError as error:
            anomalies.append({"type": ANOMALY_INVALID, "detail": f"no es JSON: {error}",
                              "segment": key})
            self.stats["invalid"] += 1
            data = {}
        for alias in data:
            if alias not in shown:
                anomalies.append({"type": ANOMALY_BAD_ALIAS, "alias": alias, "segment": key})
        for alias, unit in shown.items():
            answer = data.get(alias)
            parsed[alias] = {"unidad": unit.pk, "valida": False, "respaldo": False}
            if (not isinstance(answer, dict) or answer.get("exige") not in ("si", "no")
                    or not isinstance(answer.get("cita"), str)):
                if data:
                    anomalies.append({"type": ANOMALY_BAD_ITEM, "alias": alias,
                                      "segment": key})
                continue
            parsed[alias].update(valida=True, exige=answer["exige"], cita=answer["cita"])
            score = score_of.get(unit.pk)
            if (answer["exige"] != "si" or score is None
                    or score < settings.NORM_SUPPORT_MIN_SCORE):
                continue
            span = quotes.locate(answering.unit_text(unit), answer["cita"])
            if span is None:
                anomalies.append({"type": ANOMALY_QUOTE_MISSING, "alias": alias,
                                  "segment": key})
                continue
            parsed[alias]["respaldo"] = True
            accepted.append((unit, span, score))
        accepted.sort(key=lambda item: -item[2])
        accepted = accepted[:MAX_SUPPORTS]
        step = self._record(
            {**context, "request": output.request}, output.content,
            parsed={"unidades": parsed, "respaldos": len(accepted),
                    "finish_reason": output.finish_reason},
            anomalies=anomalies, seconds=time.monotonic() - started,
            tokens=(output.prompt_tokens, output.completion_tokens))
        found = [
            Support(unit=unit,
                    unit_label=indexing.passage_header(unit.reading.document.norm, unit),
                    char_start=span[0], char_end=span[1],
                    text=answering.unit_text(unit)[span[0]:span[1]], score=score, step=step)
            for unit, span, score in accepted
        ]
        if found:
            self.stats["with_support"] += 1
            self.stats["supports"] += len(found)
        return found
