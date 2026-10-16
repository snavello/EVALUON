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
- Doble del cliente de la API externa (T-289, REQ-122): `fake_external` y `external_payload`.
  Un fixture automático (`no_real_external_calls`) hace fallar toda llamada real a esa API
  dentro de la suite, aunque la configuración esté encendida por error.

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
from evaluon.ai.external import client as external_client
from evaluon.ai.external.payload import ExternalPayload

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

    def generate(self, messages, schema, *, max_tokens=None, base_url=None, timeout=None,
                 reasoning=None):
        self.calls.append((messages, schema))
        options = {"max_tokens": max_tokens, "base_url": base_url, "timeout": timeout}
        if reasoning:  # solo si el paso piensa (T-253): apagado, `options` es el de siempre
            options["reasoning"] = reasoning
        self.options.append(options)
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
        request = generation_client.build_request(messages, schema, max_tokens, base_url,
                                                  reasoning)
        prompt_tokens = sum(count_words(str(m.get("content", ""))) for m in messages)
        completion_tokens = count_words(content)
        message = {"role": "assistant", "content": content}
        thought = ""
        if reasoning:  # el razonamiento propio del modelo, como lo devuelve `llama-server`
            thought = f"Razonamiento propio sintético del doble ({reasoning})."
            message["reasoning_content"] = thought
        response = {
            "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
            "model": request["model"],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens},
        }
        return generation_client.GenerationResult(
            content=content, finish_reason=finish_reason, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, request=request, response=response,
            reasoning=thought, reasoning_tokens=count_words(thought) if reasoning else None,
            reasoning_level=reasoning or None,
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
    """Doble del cliente de generación (`evaluon.ai.generation`): reemplaza `generate`,
    `count_tokens` y `count_tokens_batch`. Ver `FakeGeneration`."""
    double = FakeGeneration()
    monkeypatch.setattr(generation_client, "generate", double.generate)
    monkeypatch.setattr(generation_client, "count_tokens", double.count_tokens)
    monkeypatch.setattr(generation_client, "count_tokens_batch", double.count_tokens)
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


# El chequeo de salud real de `generation` (T-247), para probarlo; las demás pruebas lo reemplazan.
REAL_IS_AVAILABLE = generation_client.is_available


@pytest.fixture(autouse=True)
def consulta_engine_up(monkeypatch):
    """Las pruebas dan por encendido el motor de la Consulta (T-247): las pantallas de la Consulta
    preguntan `generation.is_available()`, que sin esto llamaría a la red del entorno. Una prueba
    que necesita el motor apagado lo reemplaza con `monkeypatch.setattr(generation_client,
    "is_available", lambda timeout=None: False)`."""
    monkeypatch.setattr(generation_client, "is_available", lambda timeout=None: True)


@pytest.fixture
def fake_ai(fake_generation, fake_embeddings, fake_reranker):
    """Los tres dobles a la vez, en `.generation`, `.embeddings` y `.reranker`."""
    return SimpleNamespace(
        generation=fake_generation, embeddings=fake_embeddings, reranker=fake_reranker
    )


# --- API externa (T-289; ADR-0066) --------------------------------------------------------------


class RealExternalCallError(AssertionError):
    """Una prueba intentó una llamada real a la API externa."""


@pytest.fixture(autouse=True)
def no_real_external_calls(monkeypatch):
    """Ninguna prueba sale a internet por el cliente de la API externa (REQ-122, P4).

    Reemplaza el único punto del cliente que toca la red (`client._urlopen`) por uno que
    falla, y saca la clave del entorno. Aunque una prueba encienda `EXTERNAL_ENABLED`, ponga
    la etapa en `externo` y una clave, sin el doble (`fake_external`) la llamada falla con
    `RealExternalCallError`. Las pruebas del propio cliente lo reemplazan por un servidor
    local de prueba (`tests/ai/test_external_client.py`)."""

    def blocked(request, timeout):
        raise RealExternalCallError(
            f"Llamada real a la API externa dentro de la suite: {request.full_url}")

    monkeypatch.setattr(external_client, "_urlopen", blocked)
    monkeypatch.delenv(external_client.KEY_ENV, raising=False)


def external_payload(**overrides):
    """Un `ExternalPayload` sintético (T-289): lo que `guard.py` va a construir, sin pasar por
    la puerta. Cualquier campo de `from_guard` se pisa con `overrides`."""
    fields = {
        "stage": "matriz_extraccion", "model": "claude-sonnet-5-5", "max_tokens": 1000,
        "system": "Instrucción sintética de la prueba.",
        "messages": [{"role": "user", "content": "Texto público sintético."}],
        "custom_id": "ext-0001", "effort": "medium", "thinking": "adaptive",
        "procedure_id": 7, "run_kind": "matrix", "run_id": 1,
    }
    fields.update(overrides)
    return ExternalPayload.from_guard(**fields)


class FakeExternal:
    """Doble del cliente de la API externa (`evaluon.ai.external.client`).

    Reemplaza las operaciones del cliente (`send_message`, `create_batch`, `retrieve_batch`,
    `fetch_results`) y su reloj (`_sleep`, `_now`: nadie espera de verdad). Lo demás del
    cliente es el real: la comprobación de que esté habilitado (`require_enabled`), la
    validación de los lotes, la lectura de las respuestas (`parse_message` y
    `parse_batch_results`) y `run_batch` con su sondeo. Por eso el doble fabrica respuestas con
    la forma de la API y el cliente real las lee.

    Respuestas guiadas por `custom_id` (el de `ExternalPayload`; sin `custom_id`, para todos
    los que no tengan la suya):

    - `respond(text, ...)`: un mensaje con ese texto (y `model`, `stop_reason`, `usage`).
    - `fail()`, `expire()`, `cancel()`: en un lote, el pedido termina `errored`, `expired` o
      `canceled`; en el modo directo, `fail` lanza `ExternalUnavailableError` y `expire`,
      `ExternalExpired`.
    - `fail_call(error_class)`, `timeout()`, `unavailable()`, `input_too_long()`: la llamada
      entera lanza ese error (también al crear un lote); `working()` vuelve a responder.
    - `polls_before_end(n)` (1 por omisión): el lote informa `in_progress` en las primeras n
      consultas y `ended` en la siguiente; `never_ends()` no termina nunca.
    - `enable(*stages)`: enciende `EXTERNAL_ENABLED`, pone las etapas en `externo` (por omisión
      `matriz` y `verificador`) y una clave sintética en el entorno.

    Registros: `messages` (pedidos directos), `batches` (listas de pedidos de cada lote
    creado), `retrievals` (consultas por lote), `sleeps` (esperas pedidas) y `clock`.
    """

    def __init__(self, test_settings, monkeypatch):
        self._settings = test_settings
        self._monkeypatch = monkeypatch
        self.messages = []
        self.batches = []
        self.retrievals = {}
        self.sleeps = []
        self.clock = 0.0
        self._replies = {}
        self._default = {"kind": "respond", "text": "Respuesta sintética del doble externo.",
                         "model": None, "stop_reason": "end_turn", "usage": None}
        self._call_error = None
        self._polls = 1
        self._serial = itertools.count(1)

    # --- guion

    def _script(self, custom_id, **reply):
        if custom_id is None:
            self._default = {**self._default, **reply}
        else:
            self._replies[custom_id] = {**self._default, **reply}

    def respond(self, text, custom_id=None, *, model=None, stop_reason="end_turn", usage=None):
        self._script(custom_id, kind="respond", text=text, model=model,
                     stop_reason=stop_reason, usage=usage)

    def fail(self, custom_id=None):
        self._script(custom_id, kind="errored")

    def expire(self, custom_id=None):
        self._script(custom_id, kind="expired")

    def cancel(self, custom_id=None):
        self._script(custom_id, kind="canceled")

    def fail_call(self, error_class):
        self._call_error = error_class

    def timeout(self):
        self._call_error = external_client.ExternalTimeoutError

    def unavailable(self):
        self._call_error = external_client.ExternalUnavailableError

    def input_too_long(self):
        self._call_error = external_client.ExternalInputTooLongError

    def working(self):
        self._call_error = None

    def polls_before_end(self, count):
        self._polls = count

    def never_ends(self):
        self._polls = float("inf")

    def enable(self, *stages):
        self._settings.EXTERNAL_ENABLED = True
        stages = stages or tuple(self._settings.EXTERNAL_STAGE_NAMES)
        self._settings.EXTERNAL_STAGES = {**self._settings.EXTERNAL_STAGES,
                                          **{stage: "externo" for stage in stages}}
        self._monkeypatch.setenv(external_client.KEY_ENV, "clave-sintetica-de-prueba-externa")

    # --- cuerpos con la forma de la API

    def _reply(self, payload):
        return self._replies.get(payload.custom_id, self._default)

    def _message(self, payload, reply):
        text = reply["text"]
        sent = " ".join([payload.system] + [content for _, content in payload.messages])
        usage = {"input_tokens": count_words(sent), "output_tokens": count_words(text),
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        usage.update(reply["usage"] or {})
        return {"id": f"msg_fake_{next(self._serial)}", "type": "message", "role": "assistant",
                "model": reply["model"] or payload.model,
                "content": [{"type": "text", "text": text}],
                "stop_reason": reply["stop_reason"], "stop_sequence": None, "usage": usage}

    def _raise_call_error(self):
        if self._call_error:
            raise self._call_error("Falla simulada por el doble de lo externo.")

    # --- las operaciones del cliente

    def send_message(self, payload, *, timeout=None):
        external_client._check_payload(payload)
        external_client.require_enabled(payload.stage)
        self.messages.append(payload)
        self._raise_call_error()
        reply = self._reply(payload)
        if reply["kind"] == "errored":
            raise external_client.ExternalUnavailableError("Falla simulada del pedido.")
        if reply["kind"] in ("expired", "canceled"):
            raise external_client.ExternalExpired("Pedido vencido en el doble.")
        return external_client.parse_message(payload, self._message(payload, reply),
                                             mode="directo", duration_s=0.0)

    def create_batch(self, payloads):
        payloads = external_client.check_batch(payloads)
        external_client.require_enabled(payloads[0].stage)
        self.batches.append(payloads)
        self._raise_call_error()
        batch_id = f"msgbatch_fake_{len(self.batches)}"
        request_body = {"requests": [{"custom_id": p.custom_id, "params": p.to_params()}
                                     for p in payloads]}
        counts = {"processing": len(payloads), "succeeded": 0, "errored": 0, "canceled": 0,
                  "expired": 0}
        self.retrievals[batch_id] = 0
        return external_client.ExternalBatch(
            id=batch_id, stage=payloads[0].stage, status="in_progress", request_counts=counts,
            payloads=payloads, request_body=request_body,
            response_body={"id": batch_id, "type": "message_batch",
                           "processing_status": "in_progress", "request_counts": counts})

    def retrieve_batch(self, batch):
        external_client.require_enabled(batch.stage)
        self._raise_call_error()
        self.retrievals[batch.id] += 1
        status = "ended" if self.retrievals[batch.id] > self._polls else "in_progress"
        counts = ({"processing": 0, "succeeded": len(batch.payloads), "errored": 0,
                   "canceled": 0, "expired": 0} if status == "ended" else batch.request_counts)
        return external_client.replace(
            batch, status=status, request_counts=counts,
            response_body={"id": batch.id, "type": "message_batch",
                           "processing_status": status, "request_counts": counts})

    def fetch_results(self, batch):
        if batch.status != "ended":
            raise ValueError(f"El lote {batch.id} no terminó (estado {batch.status}).")
        external_client.require_enabled(batch.stage)
        self._raise_call_error()
        lines = []
        for payload in batch.payloads:
            reply = self._reply(payload)
            if reply["kind"] == "respond":
                result = {"type": "succeeded", "message": self._message(payload, reply)}
            elif reply["kind"] == "errored":
                result = {"type": "errored", "error": {"type": "error", "error": {
                    "type": "api_error", "message": "Falla simulada del pedido."}}}
            else:
                result = {"type": reply["kind"]}
            lines.append(json.dumps({"custom_id": payload.custom_id, "result": result}))
        return external_client.parse_batch_results(batch, "\n".join(lines))

    # --- reloj: nadie espera de verdad

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.clock += seconds

    def now(self):
        return self.clock


@pytest.fixture
def fake_external(monkeypatch, settings):
    """Doble del cliente de la API externa (T-289): ver `FakeExternal`. Arranca apagado, como
    la configuración por omisión; `fake_external.enable()` lo enciende."""
    double = FakeExternal(settings, monkeypatch)
    monkeypatch.setattr(external_client, "send_message", double.send_message)
    monkeypatch.setattr(external_client, "create_batch", double.create_batch)
    monkeypatch.setattr(external_client, "retrieve_batch", double.retrieve_batch)
    monkeypatch.setattr(external_client, "fetch_results", double.fetch_results)
    monkeypatch.setattr(external_client, "_sleep", double.sleep)
    monkeypatch.setattr(external_client, "_now", double.now)
    return double
