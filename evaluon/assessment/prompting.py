"""Mensajes, esquemas JSON y análisis de la salida del modelo (REQ-052, REQ-053; plan 004,
"Qué recibe y qué devuelve el modelo"; ADR-0038; T-150).

Un pedido de lectura lleva las instrucciones como sistema y, como usuario y en este orden: los
documentos del grupo (alias `D1…`), las respuestas de la Comisión que aplican (`R1…`), las
normas que respaldan el requisito (`N1…`) y, **al final**, el requisito. Así el servidor
reutiliza el prefijo ya procesado cuando se piden seguidos varios requisitos sobre el mismo
grupo. El modelo devuelve un JSON obligado por esquema; este módulo no lo juzga: lo interpreta
y avisa si no tiene la forma pedida (`InvalidOutput`).

El contraste (ADR-0038) es un pedido corto aparte: recibe el requisito, la oración citada con su
contexto, la cita del Portal y los fundamentos.

T-237 (REQ-104, REQ-105, REQ-106; ADR-0055): el orden del esquema es el del razonamiento. El modelo
razona (`razonamiento`, 2 a 4 oraciones), cita la oración completa, marca `externo` e `ilegible`,
revisa **cada condición** del requisito con su dato, su cita y su resultado (`condiciones`) y recién
después da `resultado`, `explicacion` y `pregunta`. El resultado del grupo no lo decide el modelo:
se deriva por código de las condiciones (`derive_result`). El reintento le muestra su respuesta
anterior (turno del asistente). Cada instrucción tiene su versión y su huella (`prompt_record`).
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

CUMPLE = "cumple"
NO_CUMPLE = "no_cumple"
NO_CONSTA = "no_consta"
NO_DETERMINADO = "no_determinado"
RESULTS = (CUMPLE, NO_CUMPLE, NO_CONSTA, NO_DETERMINADO)
EXIGENCES = ("documento", "condicion")
VERDICTS = ("si", "no", "parcial")

ANOMALY_INVALID_OUTPUT = "salida_invalida"
ANOMALY_NO_CITATION = "conclusion_sin_cita"

# Razonamiento breve antes del veredicto (ADR-0055): tope de caracteres en el esquema, condiciones
# por requisito y tokens de salida que se suman al máximo de los pedidos de lectura de
# `settings.py` (el razonamiento y la lista de condiciones).
REASONING_MAX_CHARS = 700
CONTRAST_REASONING_MAX_CHARS = 500
CONDITIONS_MAX = 6
EXTRA_OUTPUT_TOKENS = 600


class InvalidOutput(ValueError):
    """La salida del modelo no tiene la forma pedida."""

    def __init__(self, message, kind=ANOMALY_INVALID_OUTPUT):
        super().__init__(message)
        self.kind = kind


def load_prompt(name):
    """Texto de las instrucciones de la versión que fija `ASSESSMENT_PROMPT_VERSIONS`."""
    version = settings.ASSESSMENT_PROMPT_VERSIONS[name]
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def prompt_hash(text):
    """Huella SHA-256 del texto de una instrucción, con los saltos de línea normalizados para que
    sea la misma en cualquier equipo."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def prompt_record(name):
    """`{"nombre", "version", "sha256"}` de la instrucción vigente `name`: lo que cada pedido deja
    anotado de su instrucción (P6, REQ-106)."""
    return {"nombre": name, "version": settings.ASSESSMENT_PROMPT_VERSIONS[name],
            "sha256": prompt_hash(load_prompt(name))}


def prompt_hashes():
    """`{nombre: huella}` de las instrucciones vigentes, para el registro de la corrida."""
    return {name: prompt_hash(load_prompt(name)) for name in settings.ASSESSMENT_PROMPT_VERSIONS}


def evaluation_max_tokens():
    """Máximo de tokens de salida de un pedido de lectura: el de `settings.py` más lo que suman el
    razonamiento y la lista de condiciones (ADR-0055)."""
    return settings.ASSESSMENT_MAX_OUTPUT_TOKENS + EXTRA_OUTPUT_TOKENS


# --- Pedido de lectura de un grupo -----------------------------------------------------------


def doc_alias(number):
    return f"D{number}"


def render_documents(pieces):
    """`(texto, {alias: pieza})` de los documentos de un grupo."""
    blocks, aliased = [], {}
    for number, piece in enumerate(pieces, start=1):
        alias = doc_alias(number)
        aliased[alias] = piece
        blocks.append(f"[{alias}]\n{piece.render()}\n[/{alias}]")
    return "Documentos de la oferta:\n\n" + "\n\n".join(blocks), aliased


def render_answers(answers):
    """`(texto, {alias: respuesta})` de las respuestas de la Comisión que aplican."""
    if not answers:
        return "", {}
    blocks, aliased = [], {}
    for number, answer in enumerate(answers, start=1):
        alias = f"R{number}"
        aliased[alias] = answer
        who = answer.answered_by.get_username()
        when = answer.answered_at.strftime("%d/%m/%Y")
        blocks.append(f"[{alias}] (respondió {who} el {when})\n"
                      f"Pregunta: {answer.question.text}\nRespuesta: {answer.text}\n"
                      f"[/{alias}]")
    return "Respuestas de la Comisión:\n\n" + "\n\n".join(blocks), aliased


def render_norms(grounds):
    """`(texto, {alias: fundamento})` de las normas que respaldan el requisito."""
    if not grounds:
        return "", {}
    blocks, aliased = [], {}
    for number, ground in enumerate(grounds, start=1):
        alias = f"N{number}"
        aliased[alias] = ground
        blocks.append(f"[{alias}]\nNorma: {ground.label}\nTexto: {ground.text}\n[/{alias}]")
    return "Normativa:\n\n" + "\n\n".join(blocks), aliased


# El cierre del mensaje: un recordatorio de tres líneas con el orden de la salida. El requisito
# va al final y la instrucción queda lejos (ADR-0055, regla 3 del informe de revisión).
CLOSING = ("Devolvé un objeto JSON con los campos pedidos, en este orden:\n"
           "1. razonamiento, citas (la oración completa), externo e ilegible.\n"
           "2. condiciones (cada una con su dato, su cita y su resultado) y, al final, resultado, "
           "explicacion y pregunta (para la Comisión).")


def _with_retry(messages, correction, previous):
    """Con `previous` (la salida anterior del modelo), el reintento la muestra como turno del
    asistente y la corrección como turno nuevo del usuario (ADR-0055, regla 7): el primer
    mensaje del usuario queda igual y el prefijo se reutiliza. Sin `previous`, la corrección se
    suma al mensaje del usuario."""
    if not correction:
        return messages
    if previous:
        return [*messages, {"role": "assistant", "content": previous},
                {"role": "user", "content": correction}]
    last = messages[-1]
    return [*messages[:-1], {**last, "content": f"{last['content']}\n\n{correction}"}]


def build_evaluation_messages(system, documents_text, answers_text, norms_text,
                              requirement_block, correction="", portal_text="", previous=""):
    """Mensajes del pedido de un grupo: documentos, datos del Portal (`P…`, T-235), respuestas,
    normas y, al final, el requisito y el cierre. El bloque del Portal es de la oferta, no del
    requisito: va justo después de los documentos para no romper el prefijo que el servidor
    reutiliza. El reintento (`correction`, con la salida anterior en `previous`) agrega dos turnos
    y deja intacto el primer mensaje del usuario."""
    parts = [documents_text, portal_text, answers_text, norms_text, requirement_block, CLOSING]
    user = "\n\n".join(part for part in parts if part)
    return _with_retry([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       correction, previous)


def condition_schema():
    """Una condición del requisito: lo que exige, el dato que tiene la oferta (o el Portal), la
    cita que lo sostiene (el número de la cita en `citas`, 0 si ninguna) y su resultado."""
    return {
        "type": "object",
        "properties": {
            "condicion": {"type": "string"},
            "dato": {"type": "string"},
            "cita": {"type": "integer",
                     "enum": list(range(settings.ASSESSMENT_MAX_CITATIONS + 1))},
            "resultado": {"type": "string", "enum": list(RESULTS)},
        },
        "required": ["condicion", "dato", "cita", "resultado"], "additionalProperties": False}


def evaluation_schema(doc_aliases, support_aliases, portal_aliases=()):
    """Esquema del resultado de un grupo, en el orden en que el modelo lo escribe (ADR-0055):
    `razonamiento`, citas (alias de documento o del Portal, y texto), fundamentos (alias N y R),
    `externo`, `ilegible`, `datos`, exigencia, `condiciones` y, al final, resultado, cláusula,
    explicación y pregunta."""
    citation = {
        "type": "object",
        "properties": {"documento": {"type": "string", "enum": list(doc_aliases)},
                       "texto": {"type": "string"}},
        "required": ["documento", "texto"], "additionalProperties": False}
    # T-235: una cita puede ser de un dato del Portal (alias `P…`); `datos` es solo de documentos.
    portal_citation = {
        **citation, "properties": {**citation["properties"], "documento": {
            "type": "string", "enum": [*doc_aliases, *portal_aliases]}}}
    if support_aliases:
        fundamentos = {"type": "array", "items": {"type": "string", "enum": list(support_aliases)}}
    else:
        fundamentos = {"type": "array", "items": {"type": "string"}, "maxItems": 0}
    return {
        "type": "object",
        "properties": {
            "razonamiento": {"type": "string", "maxLength": REASONING_MAX_CHARS},
            "citas": {"type": "array", "items": portal_citation,
                      "maxItems": settings.ASSESSMENT_MAX_CITATIONS},
            "fundamentos": fundamentos,
            "externo": {"type": "boolean"},
            # El alias del documento que debería responder el requisito y tiene una página «no se
            # pudo leer»; vacío si no hay (REQ-064).
            "ilegible": {"type": "string", "enum": ["", *doc_aliases]},
            # Texto literal de la oferta con el monto, la forma de la garantía, el precio o el CUIT
            # que pide el requisito (REQ-062).
            "datos": {"type": "array", "items": citation, "maxItems": 2},
            "exigencia": {"type": "string", "enum": list(EXIGENCES)},
            "condiciones": {"type": "array", "items": condition_schema(), "minItems": 1,
                            "maxItems": CONDITIONS_MAX},
            "resultado": {"type": "string", "enum": list(RESULTS)},
            # Opcional: solo en un "no cumple" de un renglón (evaluacion-v2 y siguientes).
            "clausula": {"type": "string"},
            "explicacion": {"type": "string"},
            "pregunta": {"type": "string"},
        },
        "required": ["razonamiento", "citas", "fundamentos", "externo", "ilegible", "datos",
                     "exigencia", "condiciones", "resultado", "explicacion", "pregunta"],
        "additionalProperties": False,
    }


@dataclass
class Condition:
    """Una condición del requisito tal como la revisó el modelo: lo que exige, el dato, el número
    de su cita en `citas` (0 si ninguna) y su resultado."""

    text: str
    datum: str
    cite: int
    result: str

    def as_json(self):
        return {"condicion": self.text, "dato": self.datum, "cita": self.cite,
                "resultado": self.result}


@dataclass
class Evaluation:
    """La salida de un grupo, interpretada pero todavía sin controlar contra el texto."""

    result: str
    exigence: str
    citations: list = field(default_factory=list)   # [(alias del documento, texto)]
    supports: list = field(default_factory=list)    # alias N y R
    explanation: str = ""
    external: bool = False
    question: str = ""
    clause: str = ""        # la cláusula del pliego que contradice un "no cumple" técnico
    unreadable: str = ""    # alias del documento con una página ilegible que podría responder
    data: list = field(default_factory=list)   # [(alias, texto)] con el monto o el CUIT (REQ-062)
    reasoning: str = ""     # el razonamiento breve que el modelo escribió antes de decidir
    conditions: list = field(default_factory=list)   # [Condition]

    def as_json(self, conditions=None):
        """Lo que se guarda en `parsed`, en el orden del esquema. `conditions`: las condiciones
        ya controladas por el sistema (si no, las que escribió el modelo)."""
        return {"razonamiento": self.reasoning,
                "citas": [{"documento": a, "texto": t} for a, t in self.citations],
                "fundamentos": self.supports, "externo": self.external,
                "ilegible": self.unreadable,
                "datos": [{"documento": a, "texto": t} for a, t in self.data],
                "exigencia": self.exigence,
                "condiciones": (conditions if conditions is not None
                                else [c.as_json() for c in self.conditions]),
                "resultado": self.result, "clausula": self.clause,
                "explicacion": self.explanation, "pregunta": self.question}


_FIELDS = {"resultado", "exigencia", "citas", "fundamentos", "explicacion", "externo",
           "pregunta"}
# Opcionales al leer: una salida anterior a `evaluacion-v6` no trae `razonamiento` ni `condiciones`
# (el pedido nuevo los exige por esquema).
_OPTIONAL = {"clausula", "ilegible", "datos", "razonamiento", "condiciones"}


def _parse_conditions(raw):
    conditions = []
    for item in raw:
        if (not isinstance(item, dict)
                or set(item) != {"condicion", "dato", "cita", "resultado"}
                or not isinstance(item["condicion"], str) or not isinstance(item["dato"], str)
                or isinstance(item["cita"], bool) or not isinstance(item["cita"], int)
                or item["cita"] < 0 or item["resultado"] not in RESULTS):
            raise InvalidOutput("una condición no tiene la forma pedida")
        conditions.append(Condition(item["condicion"].strip(), item["dato"].strip(),
                                    item["cita"], item["resultado"]))
    return conditions


def parse_evaluation(content, doc_aliases, support_aliases):
    """Interpreta la salida de un grupo. Lanza `InvalidOutput` si no es el objeto pedido. Un
    alias que no existe en una cita o en los fundamentos se descarta sin invalidar la salida
    (la cita quedaría sin ubicar de todos modos)."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidOutput("la salida no es JSON") from error
    if not isinstance(data, dict) or not _FIELDS <= set(data) <= _FIELDS | _OPTIONAL:
        raise InvalidOutput("la salida no tiene los campos pedidos")
    if data["resultado"] not in RESULTS:
        raise InvalidOutput("resultado no es uno de los cuatro")
    if data["exigencia"] not in EXIGENCES:
        raise InvalidOutput("exigencia no es documento ni condicion")
    if not isinstance(data["citas"], list) or not isinstance(data["fundamentos"], list):
        raise InvalidOutput("citas y fundamentos son listas")
    if not isinstance(data["explicacion"], str) or not isinstance(data["pregunta"], str):
        raise InvalidOutput("explicacion y pregunta son texto")
    if not isinstance(data.get("clausula", ""), str):
        raise InvalidOutput("clausula es texto")
    if not isinstance(data.get("ilegible", ""), str):
        raise InvalidOutput("ilegible es texto")
    if not isinstance(data.get("razonamiento", ""), str):
        raise InvalidOutput("razonamiento es texto")
    if not isinstance(data.get("datos", []), list):
        raise InvalidOutput("datos es una lista")
    if not isinstance(data.get("condiciones", []), list):
        raise InvalidOutput("condiciones es una lista")
    if not isinstance(data["externo"], bool):
        raise InvalidOutput("externo es verdadero o falso")
    citations = []
    for cite in data["citas"]:
        if (not isinstance(cite, dict) or set(cite) != {"documento", "texto"}
                or not isinstance(cite["documento"], str)
                or not isinstance(cite["texto"], str)):
            raise InvalidOutput("una cita no tiene documento y texto")
        citations.append((cite["documento"], cite["texto"]))
    quotes = []
    for cite in data.get("datos", []):
        if (not isinstance(cite, dict) or set(cite) != {"documento", "texto"}
                or not isinstance(cite["documento"], str)
                or not isinstance(cite["texto"], str)):
            raise InvalidOutput("un dato no tiene documento y texto")
        quotes.append((cite["documento"], cite["texto"]))
    conditions = _parse_conditions(data.get("condiciones", []))
    supports = [a for a in data["fundamentos"] if isinstance(a, str) and a in support_aliases]
    return Evaluation(
        result=data["resultado"], exigence=data["exigencia"],
        citations=citations[:settings.ASSESSMENT_MAX_CITATIONS],
        supports=list(dict.fromkeys(supports)), explanation=data["explicacion"].strip(),
        external=data["externo"], question=data["pregunta"].strip(),
        clause=data.get("clausula", "").strip(), unreadable=data.get("ilegible", "").strip(),
        data=quotes[:2], reasoning=data.get("razonamiento", "").strip(), conditions=conditions)


def derive_result(conditions):
    """El resultado del grupo a partir del de cada condición (REQ-104, decisión «Unidad de la
    fila»): «no cumple» si falla alguna; «cumple» solo si se cumplen todas; «no consta» si ninguna
    tiene nada en los documentos; «no determinado» si falta el dato de alguna (la que falta se
    nombra con `missing_note`). Sin condiciones devuelve `None`."""
    results = [c.result for c in conditions]
    if not results:
        return None
    if NO_CUMPLE in results:
        return NO_CUMPLE
    if all(r == CUMPLE for r in results):
        return CUMPLE
    if all(r == NO_CONSTA for r in results):
        return NO_CONSTA
    return NO_DETERMINADO


def missing_note(conditions):
    """La frase que dice qué condición no se pudo determinar, o `""` si todas tienen resultado.
    Se agrega a la explicación de un «no determinado» (REQ-104)."""
    missing = [c.text for c in conditions if c.result in (NO_CONSTA, NO_DETERMINADO)]
    if not missing:
        return ""
    names = "; ".join(f"«{text.strip(' .')}»" for text in missing)
    word = "la condición" if len(missing) == 1 else "las condiciones"
    return f"Falta el dato de {word}: {names}."


def missing_question(conditions):
    """Una pregunta a la Comisión que nombra la condición que falta (REQ-105), para cuando el
    modelo no escribió una o la dirigió al oferente. Vacía si ninguna condición falta."""
    missing = [c.text for c in conditions if c.result in (NO_CONSTA, NO_DETERMINADO)]
    if not missing:
        return ""
    names = " y ".join(f"«{text.strip(' .')}»" for text in missing)
    if len(missing) == 1:
        return (f"¿Cómo resuelve la Comisión la condición {names}, de la que no hay dato en la "
                "oferta ni en el Portal?")
    return (f"¿Cómo resuelve la Comisión las condiciones {names}, de las que no hay dato en la "
            "oferta ni en el Portal?")


def correction_for(problem, unlocated=()):
    """El aviso del reintento según lo que falló: una salida inválida o una conclusión sin cita
    ubicada. `unlocated` son las citas que el sistema no encontró en los documentos (se las
    muestra al modelo). Va después de la respuesta anterior del modelo (turno del asistente)."""
    if problem == ANOMALY_NO_CITATION:
        shown = "".join(f"\n- «{' '.join(q.split())[:200]}»" for q in unlocated)
        listed = f" Las citas que no se encontraron:{shown}\n" if shown else " "
        return ("Tu respuesta anterior concluyó \"cumple\" o \"no_cumple\" sin una cita que se "
                f"encuentre letra por letra en los documentos.{listed}"
                "Volvé a responder con la misma forma: copiá en \"citas\" la oración completa "
                "tal como figura en el documento, desde su primera palabra hasta el punto, sin "
                "resumir ni cambiar palabras. Si no hay una oración que muestre el dato, esa "
                "condición es \"no_determinado\" y la pregunta dice cuál falta.")
    return ("Tu respuesta anterior no tuvo la forma pedida. Respondé solo con el objeto JSON "
            "pedido, con los campos en el orden indicado y usando solo los alias de la lista.")


# --- Contraste ---------------------------------------------------------------------------------

# El contraste razona (una o dos oraciones) antes de responder; `motivo` es ese razonamiento.
CONTRAST_SCHEMA = {
    "type": "object",
    "properties": {"razonamiento": {"type": "string", "maxLength": CONTRAST_REASONING_MAX_CHARS},
                   "respuesta": {"type": "string", "enum": list(VERDICTS)}},
    "required": ["razonamiento", "respuesta"], "additionalProperties": False}


def build_contrast_messages(system, requirement_block, conclusion, cited, supports_text="",
                            correction="", portal_cites=(), previous=""):
    """El pedido corto del contraste: el requisito, la conclusión, la oración citada de la oferta
    con su contexto (`cited`: lista de `(título, página, texto, contexto)`, T-235), los datos del
    Portal citados (`portal_cites`: textos escritos por el sistema) y los fundamentos. El
    reintento suma la respuesta anterior (`previous`) y la corrección como dos turnos."""
    lines = []
    for title, page, text, context in cited:
        lines.append(f"- {title}, página {page}: «{text}»")
        if context:
            lines.append(f"  Contexto en la misma página (no es la cita): {context}")
    quotes = "Texto citado de la oferta (la oración completa y su contexto):\n" + "\n".join(
        lines) if lines else ""
    portal = ("Datos del Portal citados (fuente oficial):\n"
              + "\n".join(f"- {text}" for text in portal_cites)) if portal_cites else ""
    parts = [requirement_block, f"Conclusión propuesta: {conclusion}", quotes, portal,
             supports_text, "Devolvé un objeto JSON con los campos pedidos: primero el "
             "razonamiento y después la respuesta."]
    user = "\n\n".join(part for part in parts if part)
    return _with_retry([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       correction, previous)


def parse_contrast(content):
    """`(respuesta, motivo)` del contraste; el motivo es el razonamiento. Lanza `InvalidOutput` si
    no tiene la forma. Acepta también la forma anterior (`respuesta` y `motivo`)."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidOutput("la salida no es JSON") from error
    if (not isinstance(data, dict) or "respuesta" not in data
            or not set(data) <= {"respuesta", "motivo", "razonamiento"}
            or not ("motivo" in data or "razonamiento" in data)
            or data["respuesta"] not in VERDICTS
            or not all(isinstance(data.get(k, ""), str) for k in ("motivo", "razonamiento"))):
        raise InvalidOutput("la salida no tiene los campos pedidos")
    return data["respuesta"], (data.get("razonamiento") or data.get("motivo") or "").strip()


# --- Contraste por cláusula (T-158) -------------------------------------------------------------

CLAUSE_STATES = ("coincide", "contradice", "no_aparece", "no_legible")

# `razonamiento` primero; en cada cláusula, el `motivo` antes del `estado` (ADR-0055).
CLAUSES_SCHEMA = {
    "type": "object",
    "properties": {
        "razonamiento": {"type": "string", "maxLength": CONTRAST_REASONING_MAX_CHARS},
        "clausulas": {"type": "array", "items": {
            "type": "object",
            "properties": {"clausula": {"type": "string"},
                           "motivo": {"type": "string"},
                           "estado": {"type": "string", "enum": list(CLAUSE_STATES)},
                           "cita": {"type": "string"}},
            "required": ["clausula", "motivo", "estado", "cita"],
            "additionalProperties": False}},
        "pregunta": {"type": "string"}},
    "required": ["razonamiento", "clausulas", "pregunta"], "additionalProperties": False}


def build_clauses_messages(system, requirement_block, cited, correction="", documents="",
                           previous=""):
    """El pedido del contraste por cláusula de un renglón (o de un grupo de sus cláusulas): el
    requisito, el texto citado y el documento de la oferta donde está (T-164). El reintento suma
    la respuesta anterior (`previous`) y la corrección como dos turnos."""
    quotes = "\n".join(f"- {title}, página {page}: «{text}»" for title, page, text in cited)
    parts = [requirement_block, "Texto citado de la oferta:\n" + quotes,
             ("Documento de la oferta donde está el texto citado:\n" + documents)
             if documents else "",
             "Devolvé un objeto JSON con los campos pedidos: primero el razonamiento, y en cada "
             "cláusula el motivo antes del estado."]
    user = "\n\n".join(part for part in parts if part)
    return _with_retry([{"role": "system", "content": system}, {"role": "user", "content": user}],
                       correction, previous)


def parse_clauses(content):
    """`([(cláusula, estado, motivo, cita)], pregunta)`. Lanza `InvalidOutput` si no tiene la
    forma o si no trae ninguna cláusula. `cita` es opcional (vacía si falta); `razonamiento`
    también (las salidas anteriores a `clausulas-v3` no lo traen)."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidOutput("la salida no es JSON") from error
    if (not isinstance(data, dict)
            or not {"clausulas", "pregunta"} <= set(data) <= {"clausulas", "pregunta",
                                                              "razonamiento"}
            or not isinstance(data["clausulas"], list) or not data["clausulas"]
            or not isinstance(data["pregunta"], str)
            or not isinstance(data.get("razonamiento", ""), str)):
        raise InvalidOutput("la salida no tiene los campos pedidos")
    rows = []
    for item in data["clausulas"]:
        if (not isinstance(item, dict)
                or not {"clausula", "estado", "motivo"} <= set(item) <= {
                    "clausula", "estado", "motivo", "cita"}
                or item["estado"] not in CLAUSE_STATES
                or not isinstance(item["clausula"], str)
                or not isinstance(item["motivo"], str)
                or not isinstance(item.get("cita", ""), str)):
            raise InvalidOutput("una cláusula no tiene la forma pedida")
        rows.append((item["clausula"].strip(), item["estado"], item["motivo"].strip(),
                     item.get("cita", "").strip()))
    return rows, data["pregunta"].strip()


def clauses_reasoning(content):
    """El `razonamiento` de la salida del contraste por cláusula, o `""` (para el registro)."""
    try:
        return str(json.loads(content).get("razonamiento", "")).strip()
    except (ValueError, AttributeError):
        return ""
