"""Verificador externo de citas (T-299; REQ-121, REQ-122, REQ-124; plan 016, «Paso 4 · Verificador
externo de citas»; ADR-0065 a ADR-0068; constitución 1.6, P3, P4, P6 y P9).

Un paso posterior al contraste local y a las reglas, y anterior a la pregunta a la Comisión
(`combine.compose_question`) y al guardado de cada par: un modelo externo revisa si la cita de una
celda «cumple» o «no cumple» sostiene la conclusión. **Solo puede restar** (REQ-124): una celda que
no corrobora pasa a «no determinado» `sin_corroborar`; nunca un «no determinado» pasa a «cumple»,
nunca se agrega una cita ni un texto.

**A qué celdas** (`skip_reason`): a las «cumple» o «no cumple» que se apoyan en una oración citada
de la oferta o en un dato citado del Portal: las que decidieron el modelo y el contraste (sin regla
o con la cita del Portal agregada) y las de `portal_cumple` y `portal_no_cumple`. No van las que
decide el código con documentos nombrados (ausencia, criterio del IVA, presentación física, forma de
garantía, opción, informe técnico), las que no concluyen, los requisitos externos (P9, por el
catálogo o por la marca del modelo) ni las celdas con un documento `compliance` (o con la sugerencia)
en su grupo de lectura o en su cita. La puerta (`guard.build`) bloquea igual todo eso: esto evita
mandar lo que se sabe que no sale.

**Qué se manda** (lo mismo que ve el contraste local, y menos): el requisito con su punto completo y
la oración marcada (`guard.requirement`), la conclusión (`guard.instruction`), cada oración citada
de la oferta con su documento, su página y el contexto de la misma página (`guard.offer_document`,
`citations.context_of`) y los datos del Portal citados (`guard.portal`). No va el razonamiento ni la
explicación del modelo local, ni respuestas de la Comisión, ni otras partes de la oferta. Cada pieza
entra con su origen (O-290-3) y cada pedido lleva su celda (`guard.Cell`).

**Qué se le pide**: `verificador-v2` (`EXTERNAL_PROMPT_VERSIONS["verificador"]`), un objeto JSON con
`razonamiento`, `sostiene` (`si`, `no`, `parcial`) y `pregunta`; esfuerzo y pensamiento de la etapa
(`EXTERNAL_EFFORT`, `EXTERNAL_THINKING`: `low` y `between_tools`). Un pedido por celda, todos los de
una oferta en un lote (`ledger.send`, que registra cada pedido, hace cumplir el tope y guarda el
lote apenas existe: O-290-6).

**Qué hace con la respuesta** (`decide`): `si`, la celda queda; `no` o `parcial`, «no determinado»
`sin_corroborar` con las mismas citas; la pregunta del verificador queda como la de la celda solo si
no se dirige al oferente y tiene la forma de REQ-105 (`evaluation.question_form`); si no, queda la
que la celda ya traía y, sin ninguna, la arma el código (`combine.compose_question`). Una respuesta
inválida, un pedido vencido o con error, un bloqueo de la puerta o del tope dejan la celda como
estaba, con la anomalía `verificador_sin_respuesta`.

**Registro** (P6): `facts["verificador"]` en cada celda mandada (`antes`, `despues`, `respuesta`,
`razonamiento`, `pregunta`, `hecho`), el hecho `external_request` de cada pedido y la clave `externo`
de la corrida (`Verification.record`, con la entrada propia `verificador`, como la matriz de T-291).

`verify` sirve a los dos caminos: la evaluación (`services/evaluate.py`) y la pasada sobre una
evaluación guardada (`verify_saved`, que usa `medir_evaluacion --verificador-sobre`). La base de
resultados es de solo inserción: la pasada guarda una evaluación nueva derivada de la anterior.
"""

import json
import time
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from evaluon.ai.external import client, guard, ledger
from evaluon.assessment import citations as citing
from evaluon.assessment import combine, externals, grounds, not_applicable, portal_facts
from evaluon.assessment import models as am
from evaluon.assessment.prompting import prompt_hash
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import Offer

STAGE = "verificador"
RUN_KIND = "evaluacion"
INSTRUCTION_NAME = "verificador"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Salida: razonamiento (hasta 400 caracteres), el veredicto y una pregunta. El tope deja lugar al
# pensamiento previo de `between_tools`; una salida cortada no es JSON y deja la celda como estaba.
MAX_TOKENS = 1500
CACHE_TTL = "1h"
REASONING_MAX_CHARS = 400
ANSWERS = ("si", "no", "parcial")

# El esquema que se manda con el pedido (`output_config.format`): sin largos (los valida el código).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"razonamiento": {"type": "string"},
                   "sostiene": {"type": "string", "enum": list(ANSWERS)},
                   "pregunta": {"type": "string"}},
    "required": ["razonamiento", "sostiene", "pregunta"],
    "additionalProperties": False,
}

ANOMALY = "verificador_sin_respuesta"

# Las reglas cuya conclusión se apoya en una cita de la oferta o del Portal (además de la celda sin
# regla, que decidieron el modelo y el contraste).
CITED_RULES = (portal_facts.RULE_CUMPLE, portal_facts.RULE_NO_CUMPLE, portal_facts.RULE_BOTH)

# Por qué una celda no se manda.
SKIP_OUTCOME = "no_concluye"
SKIP_RULE = "decidida_por_regla"
SKIP_CRITERION = "criterio_de_la_comision"
SKIP_NO_CITATION = "sin_cita"
SKIP_EXTERNAL = "requisito_externo"
SKIP_COMPLIANCE = "documento_compliance"

CONCLUSIONS = {combine.OUT_CUMPLE: "cumple", combine.OUT_NO_CUMPLE: "no cumple"}


def enabled():
    """Si el verificador corre: el uso externo encendido y la etapa en `externo`."""
    return bool(settings.EXTERNAL_ENABLED) and settings.EXTERNAL_STAGES.get(STAGE) == "externo"


# --- Instrucción -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Instruction:
    version: str
    text: str
    sha256: str


def load_instruction():
    """La instrucción de `EXTERNAL_PROMPT_VERSIONS["verificador"]`, con los fines de línea en LF."""
    version = settings.EXTERNAL_PROMPT_VERSIONS[STAGE]
    text = (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    return Instruction(version, text, prompt_hash(text))


# --- Celdas ------------------------------------------------------------------------------------


@dataclass
class Cell:
    """Una celda de la evaluación de una oferta, tal como queda después del contraste y de las
    reglas: el requisito, su texto (`grounds.RequirementText`), el resultado (`combine.Combined`),
    si el modelo local lo marcó externo y los documentos de su grupo de lectura."""

    requirement: object
    text: object
    combined: object
    external_flagged: bool = False
    group_documents: tuple = ()


@dataclass
class Checked:
    """Lo que pasó con una celda: el resultado después del verificador (`combined`), por qué no se
    mandó (`skipped`) o la respuesta (`answer`: `si`, `no`, `parcial`, o `None` si no hubo una
    válida), el razonamiento, la pregunta que propuso, si se usó, el hecho del registro y la
    anomalía, si la hubo."""

    cell: Cell
    combined: object
    skipped: str | None = None
    custom_id: str | None = None
    answer: str | None = None
    reasoning: str = ""
    question: str = ""
    question_used: bool = False
    event_id: int | None = None
    anomaly: dict | None = None

    @property
    def sent(self):
        return self.skipped is None

    @property
    def changed(self):
        return self.combined.outcome != self.cell.combined.outcome


def reserved_documents(offer):
    """Los documentos de la oferta que nunca salen: los `compliance` y los que tienen la sugerencia
    `compliance` en alguna lectura (la misma definición que la puerta, H-290-3)."""
    sheets = set(OfferDocument.objects.filter(offer=offer, kind=guard.COMPLIANCE)
                 .values_list("pk", flat=True))
    return sheets | guard.suggested_compliance(offer.procedure_id)


def _document_id(value):
    return getattr(value, "pk", value)


def cited_documents(combined):
    return tuple(dict.fromkeys(_document_id(c.document) for c in combined.citations))


def skip_reason(cell, reserved=frozenset()):
    """Por qué la celda no va al verificador (uno de los `SKIP_*`), o `None` si va."""
    combined = cell.combined
    facts = combined.facts or {}
    if combined.outcome not in CONCLUSIONS:
        return SKIP_OUTCOME
    rule = facts.get("regla")
    if (rule and rule not in CITED_RULES) or not_applicable.is_not_applicable(combined):
        return SKIP_RULE
    if facts.get("criterios"):
        return SKIP_CRITERION
    if not (combined.citations or combined.portal):
        return SKIP_NO_CITATION
    context = getattr(cell.text, "context", None) or getattr(cell.text, "text", "")
    if cell.external_flagged or externals.match(context):
        return SKIP_EXTERNAL
    documents = {_document_id(d) for d in (*cell.group_documents, *cited_documents(combined))}
    if documents & set(reserved):
        return SKIP_COMPLIANCE
    return None


def custom_id_of(offer, requirement):
    return f"verificador-o{offer.pk}-r{requirement.pk}"


def _message(cell, finder):
    """Las piezas del pedido de una celda, cada una con su origen (O-290-3)."""
    combined = cell.combined
    pieces = [guard.requirement(cell.requirement, cell.text.render()),
              guard.instruction(f"\n\nConclusión propuesta: {CONCLUSIONS[combined.outcome]}")]
    if combined.citations:
        pieces.append(guard.instruction(
            "\n\nTexto citado de la oferta (la oración completa y su contexto):"))
        for found in combined.citations:
            pieces.append(guard.offer_document(
                found.document,
                f"\n- {found.document.title}, página {found.page}: «{found.text}»"))
            before, after = ("", "")
            if getattr(found, "reading", None) is not None:
                before, after = citing.context_of(found, finder)
            context = " ".join(part for part in (
                f"antes: «{before}»" if before else "", f"después: «{after}»" if after else "")
                if part)
            if context:
                pieces.append(guard.instruction("\n  Contexto en la misma página (no es la cita): "))
                pieces.append(guard.offer_document(found.document, context))
    if combined.portal:
        pieces.append(guard.instruction("\n\nDatos del Portal citados (fuente oficial):"))
        for datum in combined.portal:
            pieces.append(guard.portal(f"\n- {datum['text']}", ref=datum.get("item")))
    pieces.append(guard.instruction(
        "\n\nDevolvé el objeto JSON pedido: primero el razonamiento, después si el texto citado "
        "sostiene la conclusión y, si no la sostiene, la pregunta a la Comisión."))
    return pieces


# --- Respuesta ---------------------------------------------------------------------------------


class InvalidAnswer(ValueError):
    """La respuesta no es el objeto JSON pedido."""


def parse(text):
    """`(sostiene, razonamiento, pregunta)` de la respuesta del verificador. Lanza `InvalidAnswer`
    si no tiene la forma pedida. El razonamiento se recorta a 400 caracteres, contado el «…» del
    recorte (O-299-4; la respuesta completa queda en el hecho del registro)."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as error:
        raise InvalidAnswer("la respuesta no es JSON") from error
    if (not isinstance(data, dict) or not set(data) <= set(OUTPUT_SCHEMA["properties"])
            or data.get("sostiene") not in ANSWERS
            or not all(isinstance(data.get(k, ""), str) for k in ("razonamiento", "pregunta"))):
        raise InvalidAnswer("la respuesta no tiene los campos pedidos")
    reasoning = combine.clip(data.get("razonamiento", ""), REASONING_MAX_CHARS)
    if len(reasoning) > REASONING_MAX_CHARS:
        reasoning = combine.clip(reasoning, REASONING_MAX_CHARS - 1)
    return data["sostiene"], reasoning, " ".join(data.get("pregunta", "").split())


def question_acceptable(question, cell):
    """Si la pregunta del verificador puede quedar como la de la celda (REQ-105): no se dirige al
    oferente y tiene la forma mecánica de `evaluation.question_form` (requisito, conclusión, texto
    de la oferta y dirigida a la Comisión), con el resultado que va a tener la celda."""
    from evaluon.assessment import evaluation

    if not question or combine.asks_the_offeror(question):
        return False
    combined = cell.combined
    first = cell.text.quotes[0].text if cell.text.quotes else ""
    form = evaluation.question_form(
        question, requirement_text=first, requirement_number=cell.requirement.number,
        outcome_label=am.Outcome(am.Outcome.NO_DETERMINADO).label,
        doubt_label=am.Doubt(am.Doubt.SIN_CORROBORAR).label,
        offer_texts=[c.text for c in combined.citations] + [d["text"] for d in combined.portal])
    return bool(form["conforme"])


def missing_closing(missing, outcome):
    """La línea de cierre de la pregunta a la Comisión cuando el verificador no corroboró la
    conclusión `outcome`: dice qué no consta en el texto citado, con lo que dio el verificador,
    completo (T-302, D-301-3). `""` si no hay nada que decir o si, dicho así, se dirigiría al
    oferente (`combine.asks_the_offeror`): entonces la pregunta sigue con la que ya traía la celda
    o con la que arma el código por el motivo."""
    missing = " ".join((missing or "").split()).rstrip(" .")
    if not missing or outcome not in CONCLUSIONS:
        return ""
    closing = (f"¿La Comisión confirma, corrige o rechaza la conclusión «{CONCLUSIONS[outcome]}»? "
               f"Lo que no consta en el texto citado: {missing}.")
    return "" if combine.asks_the_offeror(closing) else closing


def decide(cell, answer, *, reasoning="", question="", event_id=None, anomaly=None,
           version=""):
    """El resultado de la celda después del verificador y su registro `facts["verificador"]`.
    `si` (o sin respuesta válida): la celda queda. `no` o `parcial`: «no determinado»
    `sin_corroborar`, con las mismas citas y la pregunta. Nunca cambia otra cosa que una
    conclusión: un «no determinado» queda como está."""
    combined = cell.combined
    used = False
    after = combined
    if answer in ("no", "parcial") and combined.outcome in CONCLUSIONS:
        used = question_acceptable(question, cell)
        # D-301-3: si la del verificador no sirve, la pregunta del código lleva lo que falta.
        ask = (question if used
               else missing_closing(reasoning, combined.outcome) or combined.question)
        note = f"El verificador externo no corroboró la conclusión ({answer})"
        note = f"{note}: {reasoning}" if reasoning else f"{note}."
        after = replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.UNCORROBORATED,
            explanation=f"{combined.explanation} {note}".strip(),
            question=ask, ask=True, proposed=combined.outcome)
    record = {"antes": {"resultado": combined.outcome, "motivo": combined.doubt},
              "despues": {"resultado": after.outcome, "motivo": after.doubt},
              "respuesta": answer, "razonamiento": reasoning, "pregunta": question,
              "pregunta_usada": used, "hecho": event_id, "instruccion": version}
    if anomaly:
        record["anomalia"] = anomaly
    return replace(after, facts={**(after.facts or {}), "verificador": record}), used


# --- Verificación de las celdas de una oferta -------------------------------------------------


@dataclass
class Verification:
    """Lo que hizo el verificador con las celdas de una oferta: una `Checked` por celda, en el
    orden recibido, el envío del libro (`sent`, o `None` si no salió ningún pedido) y las anomalías
    de la etapa (las del libro: bloqueo por tope, etapa frenada, proveedor no disponible)."""

    checked: list
    instruction: Instruction
    mode: str
    model: str
    measurement: str | None
    run_id: object
    sent: object = None
    anomalies: list = field(default_factory=list)
    blocked: int = 0
    seconds: float = 0.0

    @property
    def ran(self):
        """Si alguna respuesta volvió: la etapa corrió fuera del equipo."""
        return any(item.answer is not None for item in self.checked)

    def record(self):
        """La clave `externo` de la corrida (plan 016, «Modelo de datos»; contrato de T-300):
        `models` (etapas, proveedor y modelo), `parameters` (modo y parámetros), `prompt_versions`
        (versión y huella) y `counts` (pedidos, gasto y lo que pasó con las celdas), con la
        entrada propia `verificador`."""
        stages = {name: "local" for name in settings.EXTERNAL_STAGE_NAMES}
        stages[STAGE] = "externo" if self.ran else "local"
        own = {"proveedor": client.PROVIDER, "modelo": self.model}
        summary = self.sent.summary() if self.sent is not None else None
        skipped, answers = {}, {name: 0 for name in ANSWERS}
        for item in self.checked:
            if item.skipped:
                skipped[item.skipped] = skipped.get(item.skipped, 0) + 1
            elif item.answer:
                answers[item.answer] += 1
        sent = [item for item in self.checked if item.sent]
        return {
            "models": {"habilitado": True, "etapas": stages, **own, STAGE: dict(own)},
            "parameters": {"modo": self.mode, STAGE: {
                "modo": self.mode, "effort": settings.EXTERNAL_EFFORT.get(STAGE),
                "thinking": settings.EXTERNAL_THINKING.get(STAGE), "max_tokens": MAX_TOKENS,
                "cache_system_ttl": CACHE_TTL, "medicion": self.measurement,
                "corrida_registro": {"tipo": RUN_KIND, "numero": self.run_id},
                "lote_id": getattr(self.sent, "batch_id", None),
                "segundos": round(self.seconds, 3)}},
            "prompt_versions": {STAGE: self.instruction.version,
                                "huellas": {STAGE: self.instruction.sha256}},
            "counts": {STAGE: {
                "pedidos": summary["pedidos"] if summary else 0,
                "gasto_usd": summary["gasto_usd"] if summary else 0.0,
                "frenada": bool(summary and summary["frenada"]),
                "volvio_a_local": not self.ran,
                "celdas": len(self.checked), "enviadas": len(sent),
                "bloqueadas_puerta": self.blocked, "no_enviadas": dict(sorted(skipped.items())),
                "sostiene": answers,
                "sin_respuesta": sum(1 for item in sent if item.answer is None),
                "a_no_determinado": sum(1 for item in self.checked if item.changed),
                "preguntas_del_verificador": sum(1 for item in self.checked
                                                 if item.question_used)}},
        }


def _stage_anomalies(sent):
    return [{"type": entry.get("anomalia", ledger.ANOMALY_UNAVAILABLE), "etapa": STAGE,
             **{k: v for k, v in entry.items() if k not in ("anomalia", "etapa")}}
            for entry in sent.anomalies]


def verify(cells, *, offer, run_id, finder=None, measurement=None, mode=None, user=None,
           channel=None, clock=time.monotonic):
    """Verifica las celdas de la oferta `offer` (una lista de `Cell`) con el modelo externo: arma
    cada pedido con la puerta, los manda juntos en un envío del libro y aplica cada respuesta
    (`decide`). Devuelve una `Verification`. Nunca lanza por una falla del proveedor, un bloqueo
    o el tope: la celda queda como estaba con la anomalía `verificador_sin_respuesta`.

    `run_id` identifica la corrida en el registro (`corrida`: tipo `evaluacion`); sin medición,
    el freno de la etapa se cuenta por esa corrida. `measurement` delimita el reuso por huella y
    el freno de la etapa (`ledger.send`). `finder`: el `PageFinder` de la evaluación."""
    started = clock()
    instruction = load_instruction()
    mode = mode or settings.EXTERNAL_MODE
    finder = finder or citing.PageFinder()
    reserved = reserved_documents(offer)
    done = Verification(checked=[], instruction=instruction, mode=mode,
                        model=settings.EXTERNAL_MODELS[STAGE], measurement=measurement,
                        run_id=run_id)
    admitted, refused = {}, {}
    for cell in cells:
        reason = skip_reason(cell, reserved)
        if reason:
            done.checked.append(Checked(cell, cell.combined, skipped=reason))
            continue
        custom_id = custom_id_of(offer, cell.requirement)
        decision = guard.build(
            stage=STAGE, custom_id=custom_id, procedure=offer.procedure_id, offer=offer,
            cell=guard.Cell(cell.requirement, external_flagged=bool(cell.external_flagged),
                            group_documents=tuple(cell.group_documents),
                            cited_documents=cited_documents(cell.combined)),
            system=guard.instruction(instruction.text),
            messages=[("user", _message(cell, finder))], max_tokens=MAX_TOKENS,
            output_schema=OUTPUT_SCHEMA, cache_system_ttl=CACHE_TTL, run_kind=RUN_KIND,
            run_id=run_id, instruction_name=INSTRUCTION_NAME,
            instruction_version=instruction.version, instruction_sha256=instruction.sha256,
            measurement=measurement, channel=channel, user=user)
        if decision.blocked:
            refused[custom_id] = decision
        else:
            admitted[custom_id] = decision
        done.checked.append(Checked(cell, cell.combined, custom_id=custom_id))
    done.blocked = len(refused)

    answers = {}
    if admitted:
        try:
            done.sent = ledger.send(list(admitted.values()), measurement=measurement, mode=mode,
                                    channel=channel, user=user)
            answers = done.sent.answers
            done.anomalies.extend(_stage_anomalies(done.sent))
        except ImproperlyConfigured as error:
            # Un tope o un precio mal configurado: no sale nada y la evaluación local sigue.
            done.anomalies.append({"type": ANOMALY, "etapa": STAGE, "motivo": "configuracion",
                                   "mensaje": str(error)})

    for item in done.checked:
        if item.skipped:
            continue
        if item.custom_id in refused:
            blocked = refused[item.custom_id]
            item.event_id = blocked.event_id
            item.anomaly = {"type": ANOMALY, "motivo": guard.ANOMALY,
                            "motivos": list(blocked.reasons)}
        else:
            answer = answers.get(item.custom_id)
            item.event_id = getattr(answer, "event_id", None)
            if answer is None or not answer.ok:
                item.anomaly = {"type": ANOMALY, "motivo": getattr(answer, "outcome", None)
                                or "configuracion", "detalle": getattr(answer, "reason", None)}
            else:
                try:
                    item.answer, item.reasoning, item.question = parse(answer.text)
                except InvalidAnswer as error:
                    item.anomaly = {"type": ANOMALY, "motivo": "respuesta_invalida",
                                    "detalle": str(error)}
        item.combined, item.question_used = decide(
            item.cell, item.answer, reasoning=item.reasoning, question=item.question,
            event_id=item.event_id, anomaly=item.anomaly, version=instruction.version)
    done.seconds = clock() - started
    return done


# --- Pasada sobre una evaluación guardada (medición, plan 016, «Medición del paso 4») ---------


def _saved_combined(result, citations):
    """El `Combined` de un resultado guardado: lo que el verificador necesita (resultado, citas de
    la oferta y del Portal, hechos, explicación). La pregunta de una conclusión es vacía."""
    return combine.Combined(
        outcome=result.outcome, doubt=result.doubt, exigence=result.exigence,
        citations=[c for c in citations if c.kind == am.CitationKind.OFERTA],
        explanation=result.explanation, unread_warning=result.unread_pages_warning,
        facts=dict(result.facts or {}), opinion=result.opinion,
        portal=[{"item": c.portal_item_id, "kind": c.portal_kind, "text": c.text,
                 "label": c.label} for c in citations if c.kind == am.CitationKind.PORTAL])


def _saved_cells(run, results, citations):
    steps = list(run.steps.filter(purpose=am.Purpose.GRUPO))
    cells = []
    for result in results:
        own = [s for s in steps if s.requirement_id == result.requirement_id]
        group = tuple(dict.fromkeys(
            entry["document"] for step in own for entry in (step.documents or [])
            if isinstance(entry, dict) and "document" in entry))
        cells.append(Cell(
            requirement=result.requirement, text=grounds.requirement_text(result.requirement),
            combined=_saved_combined(result, citations[result.pk]),
            external_flagged=any((step.parsed or {}).get("externo") is True for step in own),
            group_documents=group))
    return cells


def _documents_read(run):
    """Los títulos de los documentos leídos y las páginas sin leer, como los arma la evaluación
    para la pregunta (`documents.OfferText`)."""
    titles = [d.get("title", "") for d in run.documents or []]
    unread = [{"document": d.get("document"), "title": d.get("title", ""), "page": page}
              for d in run.documents or [] if d.get("copy_of") is None
              for page in d.get("unread_pages") or []]
    return titles, unread


def _copy_citation(citation, result):
    return am.Citation.objects.create(
        result=result, order=citation.order, kind=citation.kind, document_id=citation.document_id,
        reading_id=citation.reading_id, page=citation.page, char_start=citation.char_start,
        char_end=citation.char_end, text=citation.text,
        requirement_quote_id=citation.requirement_quote_id, original_text=citation.original_text,
        norm_unit_id=citation.norm_unit_id, label=citation.label, answer_id=citation.answer_id,
        portal_item_id=citation.portal_item_id, portal_kind=citation.portal_kind)


def _open_question(offer, requirement):
    return am.Question.objects.filter(offer=offer, requirement=requirement,
                                      answers__isnull=True).exists()


def _outcome_counts(combineds):
    by_outcome, by_doubt = {}, {}
    for combined in combineds:
        key = not_applicable.outcome_key(combined)
        by_outcome[key] = by_outcome.get(key, 0) + 1
        if combined.doubt:
            by_doubt[combined.doubt] = by_doubt.get(combined.doubt, 0) + 1
    return {"by_outcome": by_outcome, "by_doubt": by_doubt}


def verify_saved(run, user, *, measurement=None, mode=None, channel=Channel.COMMAND):
    """Aplica el verificador a la evaluación guardada `run` con la misma función que la
    evaluación (`verify`), sin GPU, y guarda una **evaluación nueva derivada** (la base es de solo
    inserción): los mismos resultados y citas, con las conclusiones que el verificador no corroboró
    en «no determinado», `facts["verificador"]` en cada celda mandada, la clave `externo` y
    `parameters["derivada_de"]`. Cada resultado nuevo apunta al de `run` como anterior. La celda
    que el verificador pasó a «no determinado» lleva siempre su pregunta, ligada a la derivada
    (H-299-1); las demás copian la del origen si no hay una abierta del par. Devuelve
    `(evaluación derivada, Verification)`."""
    results = list(run.results.select_related("requirement").order_by("requirement__number", "pk"))
    citations = {r.pk: list(r.citations.select_related("document", "reading").order_by("order"))
                 for r in results}
    cells = _saved_cells(run, results, citations)
    offer = run.offer
    done = verify(cells, offer=offer, run_id=f"sobre-evaluacion-{run.pk}",
                  measurement=measurement, mode=mode, user=user, channel=channel)
    titles, unread = _documents_read(run)
    record = done.record()
    cell_anomalies = [{**item.anomaly, "requirement": item.cell.requirement.number}
                      for item in done.checked if item.anomaly]
    with transaction.atomic():
        Offer.objects.select_for_update().get(pk=offer.pk)
        last = am.Run.objects.filter(offer=offer).aggregate(last=Max("number"))["last"] or 0
        derived = am.Run.objects.create(
            request=run.request, offer=offer, matrix_version=run.matrix_version,
            number=last + 1, channel=run.channel, documents=run.documents, norms=run.norms,
            models_used={**run.models_used, "externo": record["models"]},
            parameters={**run.parameters, "externo": record["parameters"],
                        "derivada_de": {"evaluacion": run.pk, "numero": run.number}},
            prompt_versions={**run.prompt_versions, "externo": record["prompt_versions"]},
            counts={**run.counts, **_outcome_counts([i.combined for i in done.checked]),
                    "externo": record["counts"]},
            timings={**run.timings, "verificador_seconds": round(done.seconds, 3)},
            anomalies=[*run.anomalies, *done.anomalies, *cell_anomalies],
            built_at=timezone.now())
        questions = 0
        for result, item in zip(results, done.checked):
            combined = item.combined
            new = am.Result.objects.create(
                run=derived, offer=offer, requirement=result.requirement,
                outcome=combined.outcome, doubt=combined.doubt, exigence=result.exigence,
                explanation=combined.explanation,
                unread_pages_warning=result.unread_pages_warning, facts=combined.facts,
                opinion=result.opinion, previous=result)
            for citation in citations[result.pk]:
                _copy_citation(citation, new)
            if item.changed:
                text = combine.compose_question(
                    result.requirement.number, item.cell.text.text, combined, documents=titles,
                    unread=unread)
            else:
                source = am.Question.objects.filter(result=result).order_by("-pk").first()
                text = source.text if source else ""
            # H-299-1: la celda que el verificador cambió tiene su propia pregunta en cada
            # derivada, aunque siga abierta la de una pasada anterior sobre el mismo origen (si
            # no, la segunda ronda de ajuste no la mide). Las demás siguen la regla de siempre:
            # una pregunta abierta por requisito.
            if text and (item.changed or not _open_question(offer, result.requirement)):
                am.Question.objects.create(
                    procedure=offer.procedure, requirement=result.requirement, offer=offer,
                    result=new, text=text, reason=combined.doubt)
                questions += 1
        audit.record(
            EventType.EVAL_BUILD, outcome=Outcome.OK, channel=channel, user=user,
            detail={"procedure": offer.procedure_id, "offer": offer.pk,
                    "request": run.request_id, "run": derived.pk, "number": derived.number,
                    "derivada_de": {"evaluacion": run.pk, "numero": run.number},
                    "externo": record, "questions_created": questions,
                    "anomalies": derived.anomalies})
    return derived, done


def spent(verifications):
    """El gasto real de varias verificaciones (USD, `Decimal`)."""
    return sum((v.sent.cost_usd for v in verifications if v.sent is not None), Decimal(0))
