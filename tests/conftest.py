"""Fixtures comunes de la suite de EVALUON.

- Usuarios de prueba de los dos roles (T-006, REQ-016). Las claves son sintéticas y solo
  existen en la base de pruebas que pytest-django crea y borra.
- Armado de normativa de prueba (T-009): normas, documentos con su parte, lecturas,
  unidades, pasajes con su vector, relaciones con fecha y modificatorias sin cargar, en
  cualquier estado. Son fábricas componibles: cada una recibe lo que arma la anterior y
  acepta cualquier campo del modelo para pisar los valores por omisión. `two_regimes`
  arma con ellas los dos regímenes de prueba de REQ-020.

Todos los textos son sintéticos (P4). Las fábricas no crean versiones de la normativa:
si una prueba las necesita, usa `record(..., creates_corpus_version=True)`.
"""

import hashlib
import itertools
from datetime import date
from types import SimpleNamespace

import pytest

# Clave sintética de 15 caracteres o más, el mínimo de la feature (plan 001, ADR-0005).
TEST_PASSWORD = "clave-sintetica-de-prueba"

# Dimensiones del vector de `bge-m3` (plan 001, "Servicios").
EMBEDDING_DIMENSIONS = 1024


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
    llamada."""
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
    cubre todo el texto de la unidad, con su encabezado y un vector fijo. La base
    calcula la columna `tsv`."""
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
            "header": f"{norm.norm_type.title()} {norm.number}/{norm.year}, {unit.path}",
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

    - `old`: como la Disposición 297/03 (`disposicion` 297/2003, organismo `afip`).
      Régimen general, un solo documento (cuerpo) vigente desde `old_from`, con `art-1`,
      `art-2`, `anexo-i` y, dentro del anexo, `anexo-i/art-1` y `anexo-i/art-1/inc-a`.
    - `new`: como la Disposición 247/2022 (`disposicion` 247/2022, `afip`). Régimen
      general en dos partes vigentes desde `v`: el cuerpo (`art-1`, `art-2`) y el anexo
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
