"""Partición de documentos en unidades citables (ADR-0004; plan 001, "Ingesta"; T-013).

Entrada única: `split_document(lectura, parte)`. Recibe la lectura de `norms/reading/`
y la parte del documento (`cuerpo`, por omisión, o la clave de un anexo: `anexo`,
`anexo-i`), y devuelve un `SplitResult` con:

- el texto canónico, su huella y la versión de las reglas (`canonical.py`);
- las unidades, en el orden del documento (`Unit`). Con una parte que es un anexo, la
  primera es la unidad raíz de tipo `anexo`, cuya clave es la parte, y las demás cuelgan
  de ella (`anexo/art-1`); con `cuerpo` no hay unidad raíz (`art-1`). El texto de cada
  unidad es igual a `canonical_text[char_start:char_end]`;
- el informe de lectura, en datos y en texto (`report.py`).

En esta etapa la partición reconoce solo artículos (`articles.py`). Todo corre en CPU,
sin los servicios de IA, y la misma lectura da siempre el mismo resultado.
"""

import hashlib
import re
from dataclasses import dataclass, field

from evaluon.norms.reading import FORMAT_HTML, ORIGIN_OCR, ORIGIN_PDF_TEXT, ORIGIN_WEB
from evaluon.norms.splitting import articles
from evaluon.norms.splitting.canonical import CanonicalText, build_canonical_text
from evaluon.norms.splitting.report import BODY_CONTAINER, build_report, report_text

# Versión de las reglas de partición; se guarda con la lectura (`tool_versions`) y en el
# informe. Cambia cada vez que cambia una regla, para saber con qué reglas se partió.
RULES_VERSION = "1"

BODY = "cuerpo"
# `cuerpo`, o la clave de un anexo: `anexo` o `anexo-` y su número o letra.
_PART = re.compile(r"cuerpo|anexo(?:-[a-z0-9]+)?")

PATH_SEPARATOR = " › "


@dataclass
class Unit:
    """Una unidad citable, con los campos de `norms_unit`. `parent_key` es la clave de
    la unidad que la contiene; vacía si cuelga de la norma."""

    unit_type: str
    number: str
    label: str
    key: str
    path: str
    order: int
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int
    text: str
    text_origin: str
    parent_key: str | None = None
    ocr_confidence_min: float | None = None
    ocr_confidence_avg: float | None = None


@dataclass
class SplitResult:
    canonical: CanonicalText
    canonical_sha256: str
    rules_version: str
    units: list[Unit] = field(default_factory=list)
    report: dict = field(default_factory=dict)
    report_text: str = ""

    @property
    def canonical_text(self):
        return self.canonical.text


def split_document(reading, part=BODY):
    """Parte la lectura de un documento en unidades y arma su informe de lectura."""
    if not isinstance(part, str) or not _PART.fullmatch(part):
        raise ValueError(
            f"La parte {part!r} no es válida: tiene que ser 'cuerpo' o la clave de un "
            "anexo, como 'anexo' o 'anexo-i'."
        )
    canonical = build_canonical_text(reading)
    text = canonical.text
    paragraphs = [
        articles.classify(text[start:end], start, end, index)
        for index, (start, end) in enumerate(canonical.paragraphs)
    ]
    with_root = part != BODY
    segments = articles.partition(paragraphs, with_root=with_root)

    root = _annex_root(part) if with_root else None
    units, others = [], []
    for segment in segments:
        if segment.first > segment.last:
            start = end = 0  # unidad raíz sin texto propio
        else:
            start, end = paragraphs[segment.first].start, paragraphs[segment.last].end
        if segment.kind == "root":
            units.append(_root_unit(root, canonical, reading, paragraphs, segment, start, end))
        elif segment.kind == "article":
            units.append(_article_unit(root, canonical, reading, start, end, segment.number))
        else:
            others.append((segment.kind, start, end, segment.reason))
    for order, unit in enumerate(units, start=1):
        unit.order = order

    container = {"name": root["path"], "key": part} if root else {"name": BODY_CONTAINER, "key": ""}
    report = build_report(
        reading=reading,
        canonical=canonical,
        units=units,
        segments=others,
        part=part,
        rules_version=RULES_VERSION,
        container=container,
    )
    return SplitResult(
        canonical=canonical,
        canonical_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        rules_version=RULES_VERSION,
        units=units,
        report=report,
        report_text=report_text(report),
    )


def _annex_root(part):
    """Clave, número y nombre de la unidad raíz de un anexo: `anexo-i` → `I`, "Anexo I"."""
    suffix = part.partition("-")[2]
    number = suffix.upper()
    return {"key": part, "number": number, "path": "Anexo" + (f" {number}" if number else "")}


def _root_unit(root, canonical, reading, paragraphs, segment, start, end):
    label = root["path"]
    for paragraph in paragraphs[segment.first : segment.last + 1]:
        if articles.ANNEX_HEADING.match(paragraph.text):
            label = paragraph.text
            break
    page_start, page_end = canonical.pages_at(start, end)
    return Unit(
        unit_type="anexo",
        number=root["number"],
        label=label,
        key=root["key"],
        path=root["path"],
        order=0,
        page_start=page_start,
        page_end=page_end,
        char_start=start,
        char_end=end,
        text=canonical.text[start:end],
        text_origin=_origin(canonical, reading, start, end),
    )


def _article_unit(root, canonical, reading, start, end, number):
    text = canonical.text[start:end]
    page_start, page_end = canonical.pages_at(start, end)
    key = f"art-{number}"
    path = f"Artículo {number}"
    if root:
        key = f"{root['key']}/{key}"
        path = root["path"] + PATH_SEPARATOR + path
    return Unit(
        unit_type="articulo",
        number=str(number),
        label=articles.article_label(text),
        key=key,
        path=path,
        order=0,
        page_start=page_start,
        page_end=page_end,
        char_start=start,
        char_end=end,
        text=text,
        text_origin=_origin(canonical, reading, start, end),
        parent_key=root["key"] if root else None,
    )


def _origin(canonical, reading, start, end):
    """Origen del texto de una unidad (REQ-015): `ocr` si alguna de sus líneas vino de
    reconocimiento; si no, el de sus líneas. Una unidad sin texto toma el del formato."""
    origins = {line.origin for line in canonical.lines_in(start, end)}
    if ORIGIN_OCR in origins:
        return ORIGIN_OCR
    if origins == {ORIGIN_WEB} or (not origins and reading.file_format == FORMAT_HTML):
        return ORIGIN_WEB
    return ORIGIN_PDF_TEXT
