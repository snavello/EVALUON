"""Doble del motor de lotes para la evaluación asistida (T-150): un guion que contesta los
pedidos de lectura de un grupo, de contraste y de reescritura, y deja anotado cada pedido.

Cada pedido de lectura llega al guion como un `Call`: el requisito (el bloque del final del
mensaje), los documentos del grupo (`{alias: texto}`), las respuestas de la Comisión y las
normas que trae. El guion devuelve lo que contestaría el modelo: un diccionario, un texto
(salida sin tocar) o `None` (por omisión, "no consta" un documento). Textos inventados (P4).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from evaluon.ai import generation as generation_client

CASO_CHICO = Path(__file__).resolve().parent / "data" / "caso-chico"

_DOCUMENT = re.compile(r"\[(D\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)
_ANSWER = re.compile(r"\[(R\d+)\] \(respondió (.*?) el (.*?)\)\n(.*?)\n\[/\1\]", re.DOTALL)
_NORM = re.compile(r"\[(N\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)
_REQUIREMENT = re.compile(r"((?:Requisito|Renglón \d+) del pliego .*)", re.DOTALL)
_REWRITE = re.compile(r"^Requisito del pliego:\n«(.*?)»\n", re.DOTALL)


@dataclass
class Call:
    """Un pedido de lectura de un grupo, ya desarmado."""

    number: int
    messages: list
    schema: dict
    kwargs: dict
    requirement: str = ""
    documents: dict = field(default_factory=dict)
    answers: dict = field(default_factory=dict)
    norms: dict = field(default_factory=dict)

    def alias_with(self, needle):
        """El alias del primer documento del grupo cuyo texto contiene `needle`."""
        needle = " ".join(needle.split())
        return next((alias for alias, text in self.documents.items()
                     if needle in " ".join(text.split())), None)

    def quote(self, needle):
        """Una cita `(alias, texto)` con `needle` tal como figura en el documento del grupo."""
        alias = self.alias_with(needle)
        return None if alias is None else (alias, needle)


@dataclass
class Contrast:
    """Un pedido de contraste."""

    number: int
    messages: list
    user: str


def says(result, *citations, exigence="condicion", explanation="Porque lo dice el texto.",
         question="", external=False, supports=()):
    """La salida de un grupo como la devolvería el modelo."""
    return {"resultado": result, "exigencia": exigence,
            "citas": [{"documento": a, "texto": t} for a, t in citations if a],
            "fundamentos": list(supports), "explicacion": explanation, "externo": external,
            "pregunta": question}


class ScriptedModel:
    """Guion del motor de lotes. `evaluates(función)` recibe un `Call`; `contrasts(función)`
    recibe un `Contrast` (por omisión contesta `si`). `calls`, `contrast_calls` y
    `rewrite_calls` guardan lo pedido."""

    def __init__(self, fake):
        self.fake = fake
        self.calls, self.contrast_calls, self.rewrite_calls = [], [], []
        self.clause_calls = []
        self._evaluate = None
        self._contrast = None
        self._clauses = None
        self._rewrite = None

    def clauses(self, function):
        """Guion del contraste por cláusula: recibe un `Contrast`; por omisión, todas
        coinciden."""
        self._clauses = function

    def evaluates(self, function):
        self._evaluate = function

    def contrasts(self, function):
        self._contrast = function

    def rewrites(self, function):
        self._rewrite = function

    def respond(self, messages, schema, **kwargs):
        properties = schema["properties"]
        if "consulta" in properties:
            return self._respond_rewrite(messages, schema, **kwargs)
        if "clausulas" in properties:
            return self._respond_clauses(messages, schema, **kwargs)
        if "respuesta" in properties:
            return self._respond_contrast(messages, schema, **kwargs)
        return self._respond_evaluation(messages, schema, **kwargs)

    def _answer(self, answer, messages, schema, kwargs):
        content = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        self.fake.respond(content)
        return self.fake.generate(messages, schema, **kwargs)

    def _respond_evaluation(self, messages, schema, **kwargs):
        user = messages[-1]["content"]
        match = _REQUIREMENT.search(user)
        call = Call(
            number=len(self.calls) + 1, messages=messages, schema=schema, kwargs=kwargs,
            requirement=match.group(1) if match else "",
            documents={a: t for a, t in _DOCUMENT.findall(user)},
            answers={a: (who, text) for a, who, _, text in _ANSWER.findall(user)},
            norms={a: t for a, t in _NORM.findall(user)})
        self.calls.append(call)
        answer = self._evaluate(call) if self._evaluate else None
        if answer is None:
            answer = says("no_consta", exigence="documento")
        return self._answer(answer, messages, schema, kwargs)

    def _respond_contrast(self, messages, schema, **kwargs):
        call = Contrast(number=len(self.contrast_calls) + 1, messages=messages,
                        user=messages[-1]["content"])
        self.contrast_calls.append(call)
        answer = self._contrast(call) if self._contrast else None
        if answer is None:
            answer = {"respuesta": "si", "motivo": "El texto lo demuestra."}
        return self._answer(answer, messages, schema, kwargs)

    def _respond_clauses(self, messages, schema, **kwargs):
        call = Contrast(number=len(self.clause_calls) + 1, messages=messages,
                        user=messages[-1]["content"])
        self.clause_calls.append(call)
        answer = self._clauses(call) if self._clauses else None
        if answer is None:
            answer = {"clausulas": [{"clausula": "x", "estado": "coincide", "motivo": ""}],
                      "pregunta": ""}
        return self._answer(answer, messages, schema, kwargs)

    def _respond_rewrite(self, messages, schema, **kwargs):
        text = _REWRITE.match(messages[-1]["content"]).group(1)
        self.rewrite_calls.append(text)
        query = self._rewrite(text) if self._rewrite else text
        return self._answer({"consulta": query}, messages, schema, kwargs)


@pytest.fixture
def model(fake_ai, monkeypatch):
    """El doble del motor de lotes con guion (ver `ScriptedModel`). Reemplaza
    `generation.generate`; el contador de tokens es el del doble (una palabra, un token)."""
    script = ScriptedModel(fake_ai.generation)
    monkeypatch.setattr(generation_client, "generate", script.respond)
    return script
