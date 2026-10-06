"""Mensajes, esquemas JSON y análisis de la salida del modelo (REQ-052, REQ-053; plan 004,
"Qué recibe y qué devuelve el modelo"; ADR-0038; T-150).

Un pedido de lectura lleva las instrucciones como sistema y, como usuario y en este orden: los
documentos del grupo (alias `D1…`), las respuestas de la Comisión que aplican (`R1…`), las
normas que respaldan el requisito (`N1…`) y, **al final**, el requisito. Así el servidor
reutiliza el prefijo ya procesado cuando se piden seguidos varios requisitos sobre el mismo
grupo. El modelo devuelve un JSON obligado por esquema; este módulo no lo juzga: lo interpreta
y avisa si no tiene la forma pedida (`InvalidOutput`).

El contraste (ADR-0038) es un pedido corto aparte: recibe solo el requisito, el texto citado y
los fundamentos.
"""

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


class InvalidOutput(ValueError):
    """La salida del modelo no tiene la forma pedida."""

    def __init__(self, message, kind=ANOMALY_INVALID_OUTPUT):
        super().__init__(message)
        self.kind = kind


def load_prompt(name):
    """Texto de las instrucciones de la versión que fija `ASSESSMENT_PROMPT_VERSIONS`."""
    version = settings.ASSESSMENT_PROMPT_VERSIONS[name]
    return (PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


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


def build_evaluation_messages(system, documents_text, answers_text, norms_text,
                              requirement_block, correction=""):
    """Mensajes del pedido de un grupo: documentos, respuestas, normas y, al final, el
    requisito. `correction` suma el aviso del reintento, después del requisito."""
    parts = [documents_text, answers_text, norms_text, requirement_block,
             "Devolvé un objeto JSON con los campos pedidos."]
    if correction:
        parts.append(correction)
    user = "\n\n".join(part for part in parts if part)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def evaluation_schema(doc_aliases, support_aliases):
    """Esquema del resultado de un grupo: resultado, exigencia, citas (alias de documento y
    texto), fundamentos (alias N y R), explicación, externo y pregunta."""
    citation = {
        "type": "object",
        "properties": {"documento": {"type": "string", "enum": list(doc_aliases)},
                       "texto": {"type": "string"}},
        "required": ["documento", "texto"], "additionalProperties": False}
    if support_aliases:
        fundamentos = {"type": "array", "items": {"type": "string", "enum": list(support_aliases)}}
    else:
        fundamentos = {"type": "array", "items": {"type": "string"}, "maxItems": 0}
    return {
        "type": "object",
        "properties": {
            "resultado": {"type": "string", "enum": list(RESULTS)},
            "exigencia": {"type": "string", "enum": list(EXIGENCES)},
            "citas": {"type": "array", "items": citation,
                      "maxItems": settings.ASSESSMENT_MAX_CITATIONS},
            "fundamentos": fundamentos,
            "explicacion": {"type": "string"},
            "externo": {"type": "boolean"},
            "pregunta": {"type": "string"},
            # Opcional: solo en un "no cumple" de un renglón (evaluacion-v2; v3 sigue igual).
            "clausula": {"type": "string"},
        },
        "required": ["resultado", "exigencia", "citas", "fundamentos", "explicacion",
                     "externo", "pregunta"],
        "additionalProperties": False,
    }


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

    def as_json(self):
        return {"resultado": self.result, "exigencia": self.exigence,
                "citas": [{"documento": a, "texto": t} for a, t in self.citations],
                "fundamentos": self.supports, "explicacion": self.explanation,
                "externo": self.external, "pregunta": self.question,
                "clausula": self.clause}


_FIELDS = {"resultado", "exigencia", "citas", "fundamentos", "explicacion", "externo",
           "pregunta"}
_OPTIONAL = {"clausula"}


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
    if not isinstance(data["externo"], bool):
        raise InvalidOutput("externo es verdadero o falso")
    citations = []
    for cite in data["citas"]:
        if (not isinstance(cite, dict) or set(cite) != {"documento", "texto"}
                or not isinstance(cite["documento"], str)
                or not isinstance(cite["texto"], str)):
            raise InvalidOutput("una cita no tiene documento y texto")
        citations.append((cite["documento"], cite["texto"]))
    supports = [a for a in data["fundamentos"] if isinstance(a, str) and a in support_aliases]
    return Evaluation(
        result=data["resultado"], exigence=data["exigencia"],
        citations=citations[:settings.ASSESSMENT_MAX_CITATIONS],
        supports=list(dict.fromkeys(supports)), explanation=data["explicacion"].strip(),
        external=data["externo"], question=data["pregunta"].strip(),
        clause=data.get("clausula", "").strip())


def correction_for(problem):
    """El aviso del reintento según lo que falló: una salida inválida o una conclusión sin
    cita ubicada."""
    if problem == ANOMALY_NO_CITATION:
        return ("Tu respuesta anterior concluyó \"cumple\" o \"no_cumple\" sin una cita que se "
                "encuentre letra por letra en los documentos. Volvé a responder: copiá "
                "exactamente un fragmento del documento que muestre el dato o, si no hay "
                "fragmento que lo demuestre, respondé \"no_determinado\".")
    return ("Tu respuesta anterior no tuvo la forma pedida. Respondé solo con el objeto JSON "
            "pedido y usá solo los alias de la lista.")


# --- Contraste ---------------------------------------------------------------------------------

CONTRAST_SCHEMA = {
    "type": "object",
    "properties": {"respuesta": {"type": "string", "enum": list(VERDICTS)},
                   "motivo": {"type": "string"}},
    "required": ["respuesta", "motivo"], "additionalProperties": False}


def build_contrast_messages(system, requirement_block, conclusion, cited, supports_text="",
                            correction=""):
    """El pedido corto del contraste: el requisito, la conclusión, el texto literal citado
    (`cited`: lista de `(título, página, texto)`) y los fundamentos."""
    quotes = "\n".join(f"- {title}, página {page}: «{text}»" for title, page, text in cited)
    parts = [requirement_block, f"Conclusión propuesta: {conclusion}",
             "Texto citado de la oferta:\n" + quotes, supports_text,
             "Devolvé un objeto JSON con los campos pedidos.", correction]
    user = "\n\n".join(part for part in parts if part)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_contrast(content):
    """`(respuesta, motivo)` del contraste. Lanza `InvalidOutput` si no tiene la forma."""
    try:
        data = json.loads(content)
    except ValueError as error:
        raise InvalidOutput("la salida no es JSON") from error
    if (not isinstance(data, dict) or set(data) != {"respuesta", "motivo"}
            or data["respuesta"] not in VERDICTS or not isinstance(data["motivo"], str)):
        raise InvalidOutput("la salida no tiene los campos pedidos")
    return data["respuesta"], data["motivo"].strip()
