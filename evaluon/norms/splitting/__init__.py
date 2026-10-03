"""Partición de documentos en unidades citables (ADR-0004; plan 001, "Ingesta"; T-013 y
T-023).

Entrada única: `split_document(lectura, parte)`. Recibe la lectura de `norms/reading/`
y la parte del documento (`cuerpo`, por omisión, o la clave de un anexo: `anexo`,
`anexo-i`), y devuelve un `SplitResult` con:

- el texto canónico, su huella y la versión de las reglas (`canonical.py`);
- las unidades, en el orden del documento (`Unit`): artículos con sus incisos, cláusulas
  (texto normativo sin número), anexos, visto y considerandos (`headings.py` y
  `partition.py`). Con una parte que es un anexo, la primera es la unidad raíz de tipo
  `anexo`, cuya clave es la parte, y las demás cuelgan de ella (`anexo/art-1`); con
  `cuerpo` no hay unidad raíz (`art-1`). Una unidad viene siempre después de la que la
  contiene. El texto de cada unidad es igual a `canonical_text[char_start:char_end]`;
- el informe de lectura, en datos y en texto (`report.py`).

Todo corre en CPU, sin los servicios de IA, y la misma lectura da siempre el mismo
resultado.
"""

import hashlib
import re
from dataclasses import dataclass, field

from evaluon.norms.reading import FORMAT_HTML, ORIGIN_OCR, ORIGIN_PDF_TEXT, ORIGIN_WEB
from evaluon.norms.splitting import partition as rules
from evaluon.norms.splitting.canonical import CanonicalText, build_canonical_text
from evaluon.norms.splitting.report import build_report, report_text

# Versión de las reglas de partición; se guarda con la lectura (`tool_versions`) y en el
# informe. Cambia cada vez que cambia una regla, para saber con qué reglas se partió.
# 2: T-023 (incisos, títulos en la ruta, cláusulas, anexos, considerandos, carátula,
# encabezados y pies, secuencia con margen, encabezados de reconocimiento).
RULES_VERSION = "2"

BODY = "cuerpo"
# `cuerpo`, o la clave de un anexo: `anexo` o `anexo-` y su número o letra.
_PART = re.compile(r"cuerpo|anexo(?:-[a-z0-9]+)?")

PATH_SEPARATOR = rules.PATH_SEPARATOR


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
    ocr_flags = [
        any(line.origin == ORIGIN_OCR for line in canonical.lines_in(start, end))
        for start, end in canonical.paragraphs
    ]
    paragraphs = rules.classify(canonical.paragraphs, text, canonical, ocr_flags)
    root = _annex_root(part) if part != BODY else None
    result = rules.partition(paragraphs, root=root)

    units, spans = [], []
    for item in result.items:
        start, end = _range(paragraphs, item.first, item.last, len(text))
        if isinstance(item, rules.Span):
            spans.append((item.kind, start, end, item.reason))
            continue
        unit = _unit(canonical, reading, item, start, end)
        units.append(unit)
        if item.unit_type == "articulo":
            for node in rules.find_incisos(paragraphs, item):
                _add_incisos(units, canonical, reading, paragraphs, unit, node)
    for order, unit in enumerate(units, start=1):
        unit.order = order

    report = build_report(
        reading=reading,
        canonical=canonical,
        units=units,
        segments=spans,
        part=part,
        rules_version=RULES_VERSION,
        containers=[{"name": c.name, "key": c.key} for c in result.containers],
        sequence=[
            {"container": c.name, "key": c.key, "gaps": c.gaps, "not_accepted": c.not_accepted}
            for c in result.containers
        ],
        uppercase_in_units=result.uppercase_in_units,
        doubtful_headings=result.doubtful_headings,
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


def _range(paragraphs, first, last, length):
    """Posición en el texto canónico de los párrafos `first` a `last`. Un tramo vacío
    queda en el comienzo del párrafo que le seguiría."""
    if first > last:
        start = paragraphs[first].start if first < len(paragraphs) else length
        return start, start
    return paragraphs[first].start, paragraphs[last].end


def _unit(canonical, reading, block, start, end):
    page_start, page_end = canonical.pages_at(start, end)
    return Unit(
        unit_type=block.unit_type,
        number=block.number,
        label=block.label,
        key=block.key,
        path=block.path,
        order=0,
        page_start=page_start,
        page_end=page_end,
        char_start=start,
        char_end=end,
        text=canonical.text[start:end],
        text_origin=_origin(canonical, reading, start, end),
        parent_key=block.parent_key,
    )


def _add_incisos(units, canonical, reading, paragraphs, parent, node):
    """Suma el inciso `node` y los suyos, en el orden del documento."""
    start, end = paragraphs[node.index].start, paragraphs[node.end].end
    number = node.heading.number
    block = rules.Block(
        unit_type="inciso",
        number=number,
        label=node.heading.label,
        key=f"{parent.key}/inc-{number}",
        path=f"{parent.path}{PATH_SEPARATOR}Inciso {number}",
        parent_key=parent.key,
        first=node.index,
        last=node.end,
    )
    unit = _unit(canonical, reading, block, start, end)
    units.append(unit)
    for child in node.children:
        _add_incisos(units, canonical, reading, paragraphs, unit, child)


def _origin(canonical, reading, start, end):
    """Origen del texto de una unidad (REQ-015): `ocr` si alguna de sus líneas vino de
    reconocimiento; si no, el de sus líneas. Una unidad sin texto toma el del formato."""
    origins = {line.origin for line in canonical.lines_in(start, end)}
    if ORIGIN_OCR in origins:
        return ORIGIN_OCR
    if origins == {ORIGIN_WEB} or (not origins and reading.file_format == FORMAT_HTML):
        return ORIGIN_WEB
    return ORIGIN_PDF_TEXT
