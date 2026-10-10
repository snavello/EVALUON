"""Fixtures de la feature 008 (ofertas y ficha por oferta; T-130).

- Usuarios de la Comisión: los de la 003 (`operator_user`, `evaluator_user`,
  `no_commission_user`).
- `procedure` y `matrix`: un procedimiento con una matriz validada armada sobre el pliego
  inventado del caso chico (`tests/offers/data/caso-chico/`); los requisitos son los de su
  lista esperada. Todo el texto es inventado y público (P4).
- `make_offer`: una oferta con documentos ya leídos, sin pasar por la lectura real: cada
  página es un pasaje, con su vector y su texto igual al recorte del texto canónico. Sirve
  para probar la ficha rápido.
- `script`: guion del doble del modelo de la ficha. Recibe una función que, dado el
  requisito, los pasajes candidatos (`{alias: texto}`) y el número de pedido, devuelve lo que
  el modelo contesta (un diccionario o un texto).
"""

import dataclasses
import hashlib
import itertools
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluon.ai import generation as generation_client
from evaluon.audit.models import Channel
from evaluon.offers import evaluation
from evaluon.offers import models as om
from evaluon.offers.services import offers as offers_service
from tests.conftest import unit_vector
from tests.tenders.conftest import (  # noqa: F401 - fixtures de la 003
    evaluator_user,
    no_commission_user,
    operator_user,
)

DATA = Path(__file__).resolve().parent / "data" / "caso-chico"

_counter = itertools.count(1)


@pytest.fixture
def expected():
    """La lista esperada del caso chico."""
    return evaluation.load_expected(DATA / "fichas-esperadas.yaml")


@pytest.fixture
def matrix(evaluator_user, db, operator_user, expected):
    """El procedimiento del caso chico con su pliego leído y su matriz validada (sin
    ofertas). Devuelve `SimpleNamespace(procedure, version, expected)`."""
    bare = dataclasses.replace(expected, offers=[])
    procedure, _ = evaluation.build_case(evaluator_user, bare)
    version = procedure.matrix_versions.get(number=1)
    return SimpleNamespace(procedure=procedure, version=version, expected=expected)


@pytest.fixture
def procedure(matrix):
    return matrix.procedure


def make_offer(procedure, user, bidder, documents, *, unread=(), kinds=None):
    """Una oferta con documentos ya leídos. `documents` es `{nombre de archivo: [texto de
    cada página]}`; cada página es un pasaje. `unread` son pares `(archivo, página)` que
    figuran como no leídas en el informe de su lectura. `kinds` fija el tipo de algún
    documento (`{archivo: tipo}`)."""
    offer = offers_service.register_offer(user, procedure, bidder=bidder,
                                          channel=Channel.COMMAND)
    for name, pages in documents.items():
        n = next(_counter)
        sha = hashlib.sha256(f"{name}-{n}".encode()).hexdigest()
        document = om.Document.objects.create(
            offer=offer, title=name, file_name=name, file_format="pdf", file_size=1,
            file_sha256=sha, loaded_by=user, kind=(kinds or {}).get(name, ""))
        om.DocumentFile.objects.create(document=document, content=b"%PDF-sintetico")
        canonical, spans = "", []
        for page_number, text in enumerate(pages, start=1):
            start = len(canonical) + (1 if canonical else 0)
            canonical = (canonical + "\n" if canonical else "") + text
            spans.append((page_number, start, start + len(text), text))
        unread_pages = [{"document": document.pk, "title": name, "page": page,
                         "status": "ilegible", "confidence": 10.0}
                        for file, page in unread if file == name]
        reading = om.Reading.objects.create(
            document=document, sequence=1, pages={"pages": []}, canonical_text=canonical,
            canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
            tool_versions={}, report={"pages": len(pages), "unread": unread_pages,
                                      "low_confidence": [], "without_text_unlisted": []})
        for order, (page_number, start, end, text) in enumerate(spans, start=1):
            om.Passage.objects.create(
                reading=reading, order=order, key=f"p{page_number}/b1", page=page_number,
                char_start=start, char_end=end, text=text, text_origin="pdf_text",
                embedding=unit_vector(next(_counter)))
    return offer


@pytest.fixture
def offer(procedure, operator_user, fake_ai):
    """Una oferta de dos documentos leídos: uno con la declaración, la validez y los precios;
    otro con una constancia."""
    return make_offer(procedure, operator_user, "Oferente de prueba", {
        "oferta.pdf": [
            "Declaro bajo juramento que me encuentro habilitado para contratar. "
            "La oferta mantiene su validez por sesenta días corridos.",
            "Los precios se cotizan en pesos con impuestos incluidos. "
            "Renglón 1: resma de papel A4, 100 unidades, precio unitario $ 3.000.",
        ],
        "constancia.pdf": [
            "Constancia de inscripción en el registro de proveedores, número 000123.",
        ],
    })


_BLOCK = re.compile(r"\[(P\d+)\]\nDocumento: (.*?)\nPágina: (\d+)\nTexto:\n(.*?)\n\[/\1\]",
                    re.DOTALL)
_REQUIREMENT = re.compile(r"^(?:Requisito|Renglón \d+) del pliego:\n«(.*?)»\n", re.DOTALL)


_REWRITE_REQUEST = re.compile(r"^Requisito del pliego:\n«(.*?)»\n", re.DOTALL)


def parse_request(messages):
    """`(texto del requisito, {alias: texto}, es_renglón)` de un pedido de la ficha."""
    user = messages[-1]["content"]
    match = _REQUIREMENT.match(user)
    blocks = {alias: text for alias, _, _, text in _BLOCK.findall(user)}
    return match.group(1), blocks, user.startswith("Renglón")


class Script:
    """Guion del doble del modelo de la ficha. `choose(función)`: la función recibe
    `(requisito, bloques, número de pedido, mensajes)` y devuelve un diccionario (la
    salida), un texto (salida sin tocar) o `None` (la respuesta por omisión: ningún
    pasaje)."""

    def __init__(self, fake):
        self.fake = fake
        self.calls = []
        self.rewrites = []  # pedidos de reescritura (T-146): no cuentan en `calls`
        self._function = None
        self._rewrite = None

    def choose(self, function):
        self._function = function

    def rewrite_with(self, function):
        """Qué contesta el modelo a la reescritura: `función(requisito) -> consulta` (por
        omisión, el mismo requisito)."""
        self._rewrite = function

    def respond(self, messages, schema, **kwargs):
        if "consulta" in schema["properties"]:
            return self._respond_rewrite(messages, schema, **kwargs)
        requirement, blocks, item_row = parse_request(messages)
        number = len(self.calls) + 1
        self.calls.append({"requirement": requirement, "blocks": blocks, "messages": messages,
                           "schema": schema, "kwargs": kwargs})
        answer = self._function(requirement, blocks, number, messages) if self._function else None
        if answer is None:
            answer = {"pasajes": [], "sintesis": ""}
            if item_row:
                answer = {"cotizado": "no", **answer}
        content = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        self.fake.respond(content)
        return self.fake.generate(messages, schema, **kwargs)

    def _respond_rewrite(self, messages, schema, **kwargs):
        text = _REWRITE_REQUEST.match(messages[-1]["content"]).group(1)
        self.rewrites.append({"requirement": text, "messages": messages, "kwargs": kwargs})
        query = self._rewrite(text) if self._rewrite else text
        content = query if query.startswith("{") else json.dumps({"consulta": query},
                                                                  ensure_ascii=False)
        self.fake.respond(content)
        return self.fake.generate(messages, schema, **kwargs)


@pytest.fixture
def script(fake_ai, monkeypatch):
    """El doble del modelo con guion (ver `Script`)."""
    guion = Script(fake_ai.generation)
    monkeypatch.setattr(generation_client, "generate", guion.respond)
    return guion


def pick(*needles, synthesis="Lo que ofrece el oferente.", quoted=None, when=""):
    """Una función de guion que elige los pasajes cuyo texto contiene alguna de `needles`;
    con `when`, solo responde a los requisitos cuyo texto lo contiene (a los demás, ninguno)."""

    def function(requirement, blocks, number, messages):
        if when not in requirement:
            return None
        chosen = [alias for alias, text in blocks.items()
                  if any(n in text for n in needles)]
        answer = {"pasajes": chosen, "sintesis": synthesis if chosen else ""}
        if messages[-1]["content"].startswith("Renglón"):
            answer = {"cotizado": quoted or ("si" if chosen else "no"), **answer}
        return answer

    return function


@pytest.fixture(autouse=True)
def _no_minimum_rerank_score(settings):
    """Los dobles del reranker puntúan 0,0 por omisión: las pruebas que no hablan del puntaje
    mínimo (T-136) lo dejan en 0 para que pasen los mejores candidatos como antes."""
    settings.OFFERS_MIN_RERANK_SCORE = 0.0
