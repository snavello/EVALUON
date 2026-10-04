"""Fixtures comunes de la suite de EVALUON.

- Usuarios de prueba de los dos roles (T-006, REQ-016). Las claves son sintéticas y solo
  existen en la base de pruebas que pytest-django crea y borra.
- Armado de normativa de prueba (T-009): normas, documentos con su parte, lecturas,
  unidades, pasajes con su vector, relaciones con fecha y modificatorias sin cargar, en
  cualquier estado. Son fábricas componibles: cada una recibe lo que arma la anterior y
  acepta cualquier campo del modelo para pisar los valores por omisión. `two_regimes`
  arma con ellas los dos regímenes de prueba de REQ-020.
- Dobles de los tres clientes de IA (T-011): `fake_generation`, `fake_embeddings`,
  `fake_reranker` y los tres juntos en `fake_ai`. Sin red ni GPU.

Todos los textos son sintéticos (P4). Las fábricas no crean versiones de la normativa:
si una prueba las necesita, usa `record(..., creates_corpus_version=True)`.
"""

import hashlib
import itertools
import json
from datetime import date
from types import SimpleNamespace

import pytest
from django.conf import settings

from evaluon.ai import (
    InputTooLongError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from evaluon.ai import embeddings as embeddings_client
from evaluon.ai import generation as generation_client
from evaluon.ai import reranker as reranker_client

# Clave sintética de 15 caracteres o más, el mínimo de la feature (plan 001, ADR-0005).
TEST_PASSWORD = "clave-sintetica-de-prueba"

# Dimensiones del vector de `bge-m3` (plan 001, "Servicios"): la única definición, la de
# settings.py (T-054).
EMBEDDING_DIMENSIONS = settings.EMBEDDINGS_DIMENSIONS


@pytest.fixture
def read_user(db):
    """Usuario con rol de lectura: consulta y busca."""
    from django.contrib.auth import get_user_model

    from evaluon.accounts.models import Role

    return get_user_model().objects.create_user(
        username="lectura", password=TEST_PASSWORD, role=Role.READ
    )


@pytest.fixture
def read_write_user(db):
    """Usuario con rol de lectura y escritura: además carga y valida normas."""
    from django.contrib.auth import get_user_model

    from evaluon.accounts.models import Role

    return get_user_model().objects.create_user(
        username="escritura", password=TEST_PASSWORD, role=Role.READ_WRITE
    )


# --- Normativa de prueba (T-009) -----------------------------------------------------

_counter = itertools.count(1)


def sha256_hex(text):
    """Huella SHA-256 en hexadecimal de 64 caracteres en minúsculas, como exige la base."""
    return hashlib.sha256(text.encode()).hexdigest()


def unit_vector(position=0):
    """Vector de 1024 dimensiones con un 1 en `position` y ceros en el resto."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[position % EMBEDDING_DIMENSIONS] = 1.0
    return vector


# Tipo de unidad según el prefijo del último tramo de la clave (plan 001,
# "Identificación de unidades"). Las unidades `clausula` no llevan número.
_KEY_PREFIXES = (
    ("art-", "articulo", "Artículo"),
    ("inc-", "inciso", "Inciso"),
    ("considerando-", "considerando", "Considerando"),
    ("clausula-", "clausula", "Cláusula"),
    ("punto-", "punto", "Punto"),
    ("parrafo-", "parrafo", "Párrafo"),
    ("anexo", "anexo", "Anexo"),
)


def _unit_defaults_from_key(key):
    last = key.rsplit("/", 1)[-1]
    for prefix, unit_type, label in _KEY_PREFIXES:
        if last.startswith(prefix):
            if unit_type == "clausula":
                number = ""
            elif unit_type == "anexo":
                number = last[len("anexo-"):].upper() if last != "anexo" else ""
            else:
                number = last[len(prefix):].replace("-", " ")
            return unit_type, number, f"{label} {number}".strip()
    raise ValueError(f"No se reconoce el tipo de unidad de la clave {key!r}.")


@pytest.fixture
def make_norm(read_write_user):
    """Fábrica de normas. `make_norm(**campos)`; por omisión, una disposición de
    régimen específico, sin marca de régimen general, con número propio de cada
    llamada. Sin `citation`, el nombre de cita es "Norma sintética número/año", con el
    número y el año que queden (T-055)."""
    from evaluon.norms.models import Norm

    def _make(**fields):
        n = next(_counter)
        values = {
            "category": "regimen_especifico",
            "norm_type": "disposicion",
            "number": str(9000 + n),
            "year": 2099,
            "issuer": "organismo sintetico",
            "title": f"Norma sintética {n}",
            "general_regime": False,
            "created_by": read_write_user,
        }
        values.update(fields)
        values.setdefault("citation", f"Norma sintética {values['number']}/{values['year']}")
        return Norm.objects.create(**values)

    return _make


@pytest.fixture
def make_document(read_write_user):
    """Fábrica de documentos. `make_document(norma, part=..., effective_from=...,
    effective_to=..., in_use=..., version_number=..., **campos)`.

    Por omisión es el cuerpo, versión 1 y en uso, vigente desde el 2000-01-01 y sin
    fecha de fin. Para un documento cargado y todavía sin registrar como versión:
    `in_use=False, version_number=None`.
    """
    from evaluon.norms.models import Document

    def _make(norm, **fields):
        n = next(_counter)
        values = {
            "norm": norm,
            "part": "cuerpo",
            "publication_date": date(2000, 1, 1),
            "effective_from": date(2000, 1, 1),
            "effective_to": None,
            "source": "https://example.org/norma-sintetica",
            "version_number": 1,
            "in_use": True,
            "file_name": f"documento-{n}.pdf",
            "file_format": "pdf",
            "file_size": 100,
            "file_sha256": sha256_hex(f"documento sintetico {n}"),
            "loaded_by": read_write_user,
        }
        values.update(fields)
        return Document.objects.create(**values)

    return _make


@pytest.fixture
def make_passage():
    """Fábrica de pasajes. `make_passage(unidad, **campos)`; por omisión, un pasaje que
    cubre todo el texto de la unidad, con su encabezado y un vector fijo. El encabezado
    se arma con `indexing.passage_header`, como en la validación. La base calcula la
    columna `tsv`."""
    from evaluon.norms import indexing
    from evaluon.norms.models import Passage

    def _make(unit, **fields):
        reading = unit.reading
        norm = reading.document.norm
        order = fields.pop("order", unit.passages.count() + 1)
        values = {
            "unit": unit,
            "order": order,
            "char_start": 0,
            "char_end": len(unit.text),
            "header": indexing.passage_header(norm, unit),
            "text": unit.text,
            "embedding": unit_vector(unit.pk),
            "embedding_model": "bge-m3-doble",
            "embedding_revision": sha256_hex("modelo de embeddings de prueba"),
        }
        values.update(fields)
        return Passage.objects.create(**values)

    return _make


@pytest.fixture
def make_reading(read_write_user, make_passage):
    """Fábrica de lecturas con sus unidades. `make_reading(documento, unidades,
    status="validated", passages=True, sequence=None)`.

    `unidades` es una lista de pares `(clave, texto)` o de diccionarios con `key`,
    `text` y cualquier otro campo de `norms_unit`. El tipo, el número, la etiqueta y la
    ruta salen de la clave si no se indican (`art-14 bis` no: escribir `art-14-bis`, que
    da el número `14 bis`); la unidad que contiene a otra es la de la clave más larga que
    es prefijo seguido de `/`, y tiene que venir antes en la lista. El texto canónico es
    la unión de los textos con un salto de línea, así cada unidad cumple
    `text == canonical_text[char_start:char_end]`.

    Con `passages=True`, cada unidad base (toda la que no es `inciso`) recibe un pasaje
    con su texto. `status` admite `pending`, `validated` y `superseded`.

    Devuelve la lectura; sus unidades, por clave, en `lectura.units_by_key`.
    """
    from evaluon.norms.models import Reading, Unit

    def _make(document, units=(), *, status="validated", passages=True, sequence=None):
        specs = [
            dict(u) if isinstance(u, dict) else {"key": u[0], "text": u[1]}
            for u in units
        ]
        canonical_text = "\n".join(spec["text"] for spec in specs)
        if sequence is None:
            sequence = document.readings.count() + 1
        reading = Reading.objects.create(
            document=document,
            sequence=sequence,
            status=status,
            pages=[],
            canonical_text=canonical_text,
            canonical_sha256=sha256_hex(canonical_text),
            tool_versions={"fixture": "conftest"},
            report={},
            report_text="",
            created_by=read_write_user,
        )

        by_key = {}
        offset = 0
        for order, spec in enumerate(specs, start=1):
            key = spec["key"]
            text = spec["text"]
            unit_type, number, label = _unit_defaults_from_key(key)
            parents = [k for k in by_key if key.startswith(k + "/")]
            parent = by_key[max(parents, key=len)] if parents else None
            path = label if parent is None else f"{parent.path} › {label}"
            values = {
                "reading": reading,
                "parent": parent,
                "unit_type": unit_type,
                "number": number,
                "label": label.upper(),
                "path": path,
                "order": order,
                "char_start": offset,
                "char_end": offset + len(text),
                "text_origin": "pdf_text",
            }
            values.update(spec)
            unit = Unit.objects.create(**values)
            by_key[key] = unit
            offset += len(text) + 1

        if passages:
            for unit in by_key.values():
                if unit.unit_type != "inciso":
                    make_passage(unit)

        reading.units_by_key = by_key
        return reading

    return _make


@pytest.fixture
def make_relation(read_write_user):
    """Fábrica de relaciones. `make_relation(origen, alcanzada, relation_type="modifica",
    effective_date=..., source_unit_key="", target_unit_key="")`. Por omisión, rige
    desde el 2000-01-01 y es entre normas enteras."""
    from evaluon.norms.models import Relation

    def _make(source_norm, target_norm, relation_type="modifica", **fields):
        values = {
            "relation_type": relation_type,
            "source_norm": source_norm,
            "target_norm": target_norm,
            "source_unit_key": "",
            "target_unit_key": "",
            "effective_date": date(2000, 1, 1),
            "registered_by": read_write_user,
        }
        values.update(fields)
        return Relation.objects.create(**values)

    return _make


@pytest.fixture
def make_pending_amendment(read_write_user):
    """Fábrica de modificatorias sin cargar. `make_pending_amendment(alcanzada,
    **campos)`; por omisión, una disposición con número propio de cada llamada y sin
    norma cargada."""
    from evaluon.norms.models import PendingAmendment

    def _make(target_norm, **fields):
        n = next(_counter)
        values = {
            "target_norm": target_norm,
            "norm_type": "disposicion",
            "number": str(8000 + n),
            "year": 2010,
            "issuer": "organismo sintetico",
            "source_ref": f"https://example.org/modificatoria-{n}",
            "registered_by": read_write_user,
            "loaded_norm": None,
        }
        values.update(fields)
        return PendingAmendment.objects.create(**values)

    return _make


@pytest.fixture
def two_regimes(make_norm, make_document, make_reading, make_relation):
    """Los dos regímenes de prueba de REQ-020 (ADR-0006), con textos sintéticos.

    - `old`: como la Disposición 297/03 (`disposicion` 297/2003, organismo `afip`,
      nombre de cita "Disposición AFIP 297/03"). Régimen general, un solo documento (cuerpo) vigente desde `old_from`, con `art-1`,
      `art-2`, `anexo-i` y, dentro del anexo, `anexo-i/art-1` y `anexo-i/art-1/inc-a`.
    - `new`: como la Disposición 247/2022 (`disposicion` 247/2022, `afip`, nombre de
      cita "Disposición AFIP 247/2022"). Régimen general en dos partes vigentes desde `v`: el cuerpo (`art-1`, `art-2`) y el anexo
      (`anexo`, `anexo/art-1`, `anexo/art-2`).
    - `repeal`: relación `deroga` desde `new` (`art-2`) sobre `old` entera, con fecha `v`.

    Fechas: `old_from` (2003-06-14), `v` (2023-01-01), y para consultar `before_all`
    (2001-01-10), `before_v` (2021-03-15) y `after_v` (2024-05-20).
    Unidades por clave en `old_units` y `new_units`.
    """
    old_from = date(2003, 6, 14)
    v = date(2023, 1, 1)

    old = make_norm(
        norm_type="disposicion", number="297", year=2003, issuer="afip",
        citation="Disposición AFIP 297/03",
        title="Régimen de contrataciones sintético anterior", general_regime=True,
    )
    old_body = make_document(old, part="cuerpo", effective_from=old_from,
                             publication_date=date(2003, 6, 13))
    old_reading = make_reading(old_body, [
        ("art-1", "ARTICULO 1.- Apruébase el régimen sintético de licitaciones."),
        ("art-2", "ARTICULO 2.- Comuníquese."),
        ("anexo-i", "ANEXO I"),
        ("anexo-i/art-1", "ARTICULO 1.- Objeto del régimen sintético anterior."),
        ("anexo-i/art-1/inc-a", "a) inciso sintético."),
    ])

    new = make_norm(
        norm_type="disposicion", number="247", year=2022, issuer="afip",
        citation="Disposición AFIP 247/2022",
        title="Régimen de contrataciones sintético vigente", general_regime=True,
    )
    new_body = make_document(new, part="cuerpo", effective_from=v,
                             publication_date=date(2022, 10, 31), file_format="html")
    new_annex = make_document(new, part="anexo", effective_from=v,
                              publication_date=date(2022, 10, 31))
    new_body_reading = make_reading(new_body, [
        ("art-1", "ARTICULO 1.- Apruébase el régimen sintético de contrataciones."),
        ("art-2", "ARTICULO 2.- Derógase el régimen sintético anterior."),
    ])
    new_annex_reading = make_reading(new_annex, [
        ("anexo", "ANEXO"),
        ("anexo/art-1", "ARTÍCULO 1°.- OBJETO. Régimen sintético vigente."),
        ("anexo/art-2", "ARTÍCULO 2°.- Garantías sintéticas."),
    ])

    repeal = make_relation(new, old, "deroga", source_unit_key="art-2",
                           effective_date=v)

    return SimpleNamespace(
        old=old,
        new=new,
        old_body=old_body,
        new_body=new_body,
        new_annex=new_annex,
        old_units=old_reading.units_by_key,
        new_units={**new_body_reading.units_by_key, **new_annex_reading.units_by_key},
        repeal=repeal,
        old_from=old_from,
        v=v,
        before_all=date(2001, 1, 10),
        before_v=date(2021, 3, 15),
        after_v=date(2024, 5, 20),
    )


# --- Dobles de los clientes de IA (T-011) --------------------------------------------
#
# Reemplazan las funciones de `evaluon/ai/` durante la prueba (por eso el código llama
# siempre `generation.generate(...)`, importando el módulo). Responden sin red ni GPU, con
# la misma forma que los clientes reales, y guardan en `calls` lo que recibieron. Cada
# uno tiene modos de falla que lanzan los errores propios de `evaluon.ai`. Los textos
# son sintéticos (P4).


def count_words(text):
    """Cuenta fija de los dobles: una palabra, un token."""
    return len(text.split())


def _statement_properties(schema):
    try:
        return schema["properties"]["statements"]["items"]["properties"]
    except (KeyError, TypeError):
        return {}


def _schema_aliases(schema):
    """Alias que el esquema de la consulta permite citar, o `["U1"]` si no los trae."""
    try:
        aliases = _statement_properties(schema)["citations"]["items"]["enum"]
    except (KeyError, TypeError):
        return ["U1"]
    return list(aliases) or ["U1"]


class FakeGeneration:
    """Doble del cliente de generación.

    Por omisión responde `grounded` con una afirmación sintética que cita el primer alias
    que permite el esquema (y `regimes_differ` falso si el esquema lo tiene). Modos:

    - `answer(statements)`: `grounded` con esas afirmaciones, tal cual.
    - `abstain()`: `undetermined` sin afirmaciones.
    - `invalid_output(content=...)`: una salida cortada que no es JSON (`finish_reason`
      `length`).
    - `respond(content)`: cualquier texto como salida sin tocar.
    - `timeout()`, `input_too_long()`, `unavailable()`: lanzan el error propio (la
      demora agotada, el rechazo por entrada demasiado larga, el servicio caído).

    `calls` guarda `(messages, schema)` de cada pedido y `options`, en el mismo orden, el
    máximo de salida, la dirección y la espera con que se lo pidió (`None` si no se
    indicaron; T-071). El resultado es un `GenerationResult` con el mismo `request` que
    armaría el cliente real, con el máximo de salida pedido. `generate_batch` del
    cliente llama a `generate`, así que también pasa por el doble.
    """

    def __init__(self):
        self.calls = []
        self.options = []
        self._mode = ("default", None)

    def answer(self, statements):
        output = {"status": "grounded", "statements": statements}
        self._mode = ("content", json.dumps(output, ensure_ascii=False))

    def abstain(self):
        self._mode = ("content", json.dumps({"status": "undetermined", "statements": []}))

    def invalid_output(self, content='{"status": "grounded", "statements": [{"text": "La'):
        self._mode = ("cut", content)

    def respond(self, content):
        self._mode = ("content", content)

    def timeout(self):
        self._mode = ("raise", ServiceTimeoutError)

    def input_too_long(self):
        self._mode = ("raise", InputTooLongError)

    def unavailable(self):
        self._mode = ("raise", ServiceUnavailableError)

    def generate(self, messages, schema, *, max_tokens=None, base_url=None, timeout=None):
        self.calls.append((messages, schema))
        self.options.append({"max_tokens": max_tokens, "base_url": base_url,
                             "timeout": timeout})
        kind, value = self._mode
        if kind == "raise":
            raise value("generation: falla simulada por el doble", service="generation")
        finish_reason = "stop"
        if kind == "default":
            statement = {"text": "Afirmación sintética del doble.",
                         "citations": _schema_aliases(schema)[:1]}
            if "regimes_differ" in _statement_properties(schema):
                statement["regimes_differ"] = False
            content = json.dumps({"status": "grounded", "statements": [statement]},
                                 ensure_ascii=False)
        elif kind == "cut":
            content, finish_reason = value, "length"
        else:
            content = value
        request = generation_client.build_request(messages, schema, max_tokens)
        prompt_tokens = sum(count_words(str(m.get("content", ""))) for m in messages)
        completion_tokens = count_words(content)
        response = {
            "choices": [{"index": 0, "finish_reason": finish_reason,
                         "message": {"role": "assistant", "content": content}}],
            "model": request["model"],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens},
        }
        return generation_client.GenerationResult(
            content=content, finish_reason=finish_reason, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, request=request, response=response,
        )

    def count_tokens(self, text):
        return count_words(text)


class _FailureModes:
    """Modos de falla comunes de los dobles de embeddings y reranker."""

    service = ""

    def timeout(self):
        self._error = ServiceTimeoutError

    def input_too_long(self):
        self._error = InputTooLongError

    def unavailable(self):
        self._error = ServiceUnavailableError

    def working(self):
        self._error = None

    def _fail_if_set(self):
        if self._error:
            raise self._error(f"{self.service}: falla simulada por el doble",
                              service=self.service)


class FakeEmbeddings(_FailureModes):
    """Doble del cliente de embeddings.

    Da vectores fijos de 1024 dimensiones: el de un texto anotado en `vectors[texto]`, o
    si no, `unit_vector` en una posición que sale de la huella del texto (el mismo texto
    da siempre el mismo vector). Modos de falla: `timeout()`, `input_too_long()`,
    `unavailable()`; `working()` vuelve a responder. `calls` guarda la lista de textos de
    cada pedido.
    """

    service = "embeddings"

    def __init__(self):
        self.calls = []
        self.vectors = {}
        self._error = None

    def vector_for(self, text):
        if text in self.vectors:
            return list(self.vectors[text])
        return unit_vector(int(sha256_hex(text)[:8], 16))

    def embed(self, texts):
        texts = list(texts)
        if not texts:
            return []
        self.calls.append(texts)
        self._fail_if_set()
        return [self.vector_for(text) for text in texts]

    def count_tokens(self, text):
        self._fail_if_set()
        return count_words(text)


class FakeReranker(_FailureModes):
    """Doble del cliente del reranker.

    Puntajes configurables entre 0 y 1, en el orden de los textos: cada texto recibe el
    mayor de `scores[marca]` entre las marcas que contiene, o `default` (0,0 de inicio) si
    no contiene ninguna. Modos de falla: `timeout()`, `input_too_long()`,
    `unavailable()`; `working()` vuelve a responder. `calls` guarda `(pregunta, textos)`.
    """

    service = "reranker"

    def __init__(self):
        self.calls = []
        self.scores = {}
        self.default = 0.0
        self._error = None

    def score_for(self, document):
        matches = [score for mark, score in self.scores.items() if mark in document]
        return max(matches) if matches else self.default

    def rerank(self, query, documents):
        documents = list(documents)
        if not documents:
            return []
        self.calls.append((query, documents))
        self._fail_if_set()
        return [self.score_for(document) for document in documents]


@pytest.fixture
def fake_generation(monkeypatch):
    """Doble del cliente de generación (`evaluon.ai.generation`): reemplaza `generate` y
    `count_tokens`. Ver `FakeGeneration`."""
    double = FakeGeneration()
    monkeypatch.setattr(generation_client, "generate", double.generate)
    monkeypatch.setattr(generation_client, "count_tokens", double.count_tokens)
    return double


@pytest.fixture
def fake_embeddings(monkeypatch):
    """Doble del cliente de embeddings (`evaluon.ai.embeddings`): reemplaza `embed` y
    `count_tokens`. Ver `FakeEmbeddings`."""
    double = FakeEmbeddings()
    monkeypatch.setattr(embeddings_client, "embed", double.embed)
    monkeypatch.setattr(embeddings_client, "count_tokens", double.count_tokens)
    return double


@pytest.fixture
def fake_reranker(monkeypatch):
    """Doble del cliente del reranker (`evaluon.ai.reranker`): reemplaza `rerank`. Ver
    `FakeReranker`."""
    double = FakeReranker()
    monkeypatch.setattr(reranker_client, "rerank", double.rerank)
    return double


@pytest.fixture
def fake_ai(fake_generation, fake_embeddings, fake_reranker):
    """Los tres dobles a la vez, en `.generation`, `.embeddings` y `.reranker`."""
    return SimpleNamespace(
        generation=fake_generation, embeddings=fake_embeddings, reranker=fake_reranker
    )
