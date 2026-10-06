"""Doble del motor de lotes para la evaluación asistida (T-150): un guion que contesta los
pedidos de lectura de un grupo, de contraste y de reescritura, y deja anotado cada pedido.

Cada pedido de lectura llega al guion como un `Call`: el requisito (el bloque del final del
mensaje), los documentos del grupo (`{alias: texto}`), las respuestas de la Comisión y las
normas que trae. El guion devuelve lo que contestaría el modelo: un diccionario, un texto
(salida sin tocar) o `None` (por omisión, "no consta" un documento). Textos inventados (P4).
"""

import base64
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from evaluon.ai import generation as generation_client
from evaluon.norms.reading import DocumentReading, Line, Page
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.offers import models as om
from evaluon.offers import passages as passage_rules
from evaluon.offers.services import offers as offers_service

CASO_CHICO = Path(__file__).resolve().parent / "data" / "caso-chico"
VISION_DATA = Path(__file__).resolve().parent / "data" / "vision"

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


@dataclass
class Seen:
    """Un pedido de lectura con visión: la imagen que llegó (bytes PNG, huella y tamaño) y los
    mensajes."""

    number: int
    messages: list
    schema: dict
    kwargs: dict
    image: bytes = b""

    @property
    def sha256(self):
        return hashlib.sha256(self.image).hexdigest()

    @property
    def size(self):
        return Image.open(io.BytesIO(self.image)).size


def sees_message(messages):
    """Los bytes de la imagen del último mensaje, o `b""` si no trae."""
    content = messages[-1]["content"]
    if not isinstance(content, list):
        return b""
    for part in content:
        if part.get("type") == "image_url":
            return base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
    return b""


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
        self.vision_calls = []
        self._vision = None
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

    def sees(self, function):
        """Guion de la lectura con visión: recibe un `Seen`; devuelve la transcripción (texto),
        un diccionario o un texto de salida sin tocar si empieza con `{`. Por omisión, una
        página sin texto."""
        self._vision = function

    def contrasts(self, function):
        self._contrast = function

    def rewrites(self, function):
        self._rewrite = function

    def respond(self, messages, schema, **kwargs):
        properties = schema["properties"]
        if "transcripcion" in properties:
            return self._respond_vision(messages, schema, **kwargs)
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

    def _respond_vision(self, messages, schema, **kwargs):
        call = Seen(number=len(self.vision_calls) + 1, messages=messages, schema=schema,
                    kwargs=kwargs, image=sees_message(messages))
        self.vision_calls.append(call)
        answer = self._vision(call) if self._vision else ""
        if isinstance(answer, str) and not answer.startswith("{"):
            answer = {"transcripcion": answer}
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


# --- Documentos con lectura para la lectura con visión (T-160) -------------------------------


def pdf_of(pages):
    """Un PDF de `pages` páginas, cada una una imagen con un texto inventado (nada real, P4):
    sirve para que pypdfium2 dibuje la página."""
    images = []
    for number in range(1, pages + 1):
        image = Image.new("RGB", (595, 842), "white")
        ImageDraw.Draw(image).text((60, 80), f"Página inventada {number}", fill="black")
        images.append(image)
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def make_read_document(offer, user, name, pages, *, file_format="pdf", content=None):
    """Un documento de `offer` con su primera lectura armada como la de la 008 (texto
    canónico, pasajes con vector e informe). `pages` es una lista de `(estado, texto)`: `legible`
    (texto de un PDF), `dudosa` (reconocimiento de baja confianza), `ilegible` (sin texto) y
    `en_blanco`; un texto con varias líneas se separa por salto de línea. `content` es el original (por
    omisión un PDF de imagen con tantas páginas)."""
    content = content or pdf_of(len(pages))
    sha = hashlib.sha256(content).hexdigest()
    document = om.Document.objects.create(
        offer=offer, title=name, file_name=name, file_format=file_format,
        file_size=len(content), file_sha256=sha, loaded_by=user)
    om.DocumentFile.objects.create(document=document, content=content)
    reading_pages = []
    for number, (status, text) in enumerate(pages, start=1):
        ocr = status == "dudosa"
        lines = []
        if status in ("legible", "dudosa"):
            lines = [Line(text=line, x0=72.0, top=100.0 + 20 * i, x1=540.0,
                          bottom=112.0 + 20 * i, origin="ocr" if ocr else "pdf_text",
                          confidence=65.0 if ocr else None)
                     for i, line in enumerate(text.split(chr(10))) if line]
        reading_pages.append(Page(
            number=number, width=612.0, height=792.0, status=status, lines=lines,
            origin="ocr" if ocr or status == "ilegible" else (
                "pdf_text" if lines else None),
            confidence={"dudosa": 65.0, "ilegible": 20.0}.get(status),
            classification="escaneada" if status in ("dudosa", "ilegible") else "con_texto"))
    reading = DocumentReading(file_format="pdf", pages=reading_pages,
                              tool_versions={"pdf_text": "sintetico"})
    canonical = build_canonical_text(reading)
    specs = passage_rules.build_passages(canonical)
    vectors = offers_service._vectors(specs)
    saved = om.Reading.objects.create(
        document=document, sequence=1, pages=reading.as_json(),
        canonical_text=canonical.text,
        canonical_sha256=hashlib.sha256(canonical.text.encode()).hexdigest(),
        tool_versions=reading.tool_versions,
        report=offers_service.read_report(document, reading, specs))
    om.Passage.objects.bulk_create(
        om.Passage(reading=saved, order=spec.order, key=spec.key, page=spec.page,
                   char_start=spec.char_start, char_end=spec.char_end, text=spec.text,
                   text_origin=spec.text_origin, ocr_confidence_min=spec.ocr_confidence_min,
                   ocr_confidence_avg=spec.ocr_confidence_avg, embedding=vector)
        for spec, vector in zip(specs, vectors, strict=True))
    return document
