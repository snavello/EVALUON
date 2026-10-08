"""Datos y renglones que se proponen al leer un pliego subido (REQ-077; ADR-0049; T-196).

Primera ronda, por reglas (alternativa B del ADR): número, expediente, tipo, objeto y fecha de
autorización se buscan en las primeras páginas del pliego; los renglones salen de la tabla de
renglones (número, descripción, cantidad). Cada dato propuesto lleva su cita: la página y el
texto literal donde se encontró. Sin cita verificable, el dato queda «no determinado» y no se
propone.

El modelo local entra solo para el tipo y el objeto que las reglas no hallaron, pidiéndole la
cita literal; la cita se verifica contra el texto de la página y el valor tiene que estar dentro
de ella (mismo patrón que la matriz). Una falla del modelo deja el dato sin determinar; nunca
hace fallar la propuesta. Todo corre en local (P4) y el pedido, con sus instrucciones, parámetros
y fragmentos, queda en la traza que devuelve `propose` (P6).

Este módulo no toca la base: lee los bytes del pliego y devuelve datos.
"""

import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from evaluon.ai import AIServiceError, generation
from evaluon.norms.reading import FORMAT_PDF, detect_format, read_document

RULES_VERSION = "procedimiento-reglas-v1"
PROMPT_VERSION = "procedimiento-datos-v1"

# Páginas del comienzo donde se buscan los datos de la carátula.
FRONT_PAGES = 3
# Texto máximo (en caracteres) que se le muestra al modelo.
MODEL_MAX_CHARS = 6000

FIELDS = ("number", "file_number", "procedure_type", "subject", "authorization_date")
REQUIRED_FIELDS = ("number", "procedure_type", "subject", "authorization_date")

STATE_PROPOSED = "propuesto"
STATE_UNDETERMINED = "no_determinado"

METHOD_RULE = "regla"
METHOD_MODEL = "modelo"

MODEL_INSTRUCTIONS = (
    "Sos un lector de pliegos de bases y condiciones. Del texto que sigue, que es el comienzo "
    "de un pliego, indicá el tipo de procedimiento (por ejemplo, licitación pública, "
    "contratación directa) y el objeto de la contratación. Para cada uno devolvé el valor y la "
    "cita: un fragmento copiado literal del texto, sin cambiar ni una letra, que contenga el "
    "valor. Si el texto no lo dice, devolvé el valor y la cita vacíos. No inventes."
)
MODEL_SCHEMA = {
    "type": "object",
    "properties": {
        key: {
            "type": "object",
            "properties": {"valor": {"type": "string"}, "cita": {"type": "string"}},
            "required": ["valor", "cita"],
            "additionalProperties": False,
        }
        for key in ("procedure_type", "subject")
    },
    "required": ["procedure_type", "subject"],
    "additionalProperties": False,
}

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

_VALUE = r"([A-Za-z0-9][A-Za-z0-9\-/.#_]*[A-Za-z0-9]|[A-Za-z0-9])"
_NUMBER_LABEL = re.compile(
    r"^\s*(?:n[uú]mero\s+de\s+(?:proceso|procedimiento)|proceso\s+(?:n[º°]\.?|nro\.?)|"
    r"procedimiento\s+(?:n[º°]\.?|nro\.?)|(?:proceso|procedimiento)\s*:)\s*:?\s*" + _VALUE,
    re.I)
_FILE_PATTERN = re.compile(
    r"(?:expediente|actuaci[oó]n)\s*(?:n[º°o]\.?|nro\.?|n[uú]mero)?\s*:?\s*"
    r"((?:EX-)?[0-9A-Za-z][0-9A-Za-z\-/#.]*[0-9A-Za-z])", re.I)
_FILE_BARE = re.compile(r"\b(EX-\d{4}-\d+[0-9A-Za-z\-#]*)")
_TYPE_PATTERN = re.compile(
    r"(licitaci[oó]n\s+p[uú]blica|licitaci[oó]n\s+privada|contrataci[oó]n\s+directa|"
    r"concurso\s+p[uú]blico|concurso\s+privado|subasta\s+p[uú]blica|compulsa\s+abreviada|"
    r"contrataci[oó]n\s+menor)(\s+(?:nacional|internacional))?", re.I)
_SUBJECT_LABEL = re.compile(
    r"^\s*(?:nombre\s+del\s+proceso|objeto\s+de\s+la\s+contrataci[oó]n|objeto)\s*:\s*(.+\S)\s*$",
    re.I)
_DATE_LABEL = re.compile(r"autoriza", re.I)
_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_DATE_WORDS = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\b", re.I)


@dataclass
class Citation:
    page: int
    text: str

    def as_json(self):
        return {"page": self.page, "text": self.text}


@dataclass
class Datum:
    """Un dato propuesto (o no determinado) con sus candidatos y su cita."""

    value: str | None = None
    citation: Citation | None = None
    candidates: list = field(default_factory=list)
    method: str = ""

    @property
    def state(self):
        return STATE_PROPOSED if self.value else STATE_UNDETERMINED

    def as_json(self):
        return {
            "state": self.state,
            "proposed": self.value,
            "candidates": self.candidates,
            "citation": self.citation.as_json() if self.citation else None,
            "method": self.method,
        }


@dataclass
class Proposal:
    fields: dict
    lines: list
    warnings: list
    reading: dict
    model_trace: list = field(default_factory=list)

    def as_json(self):
        return {
            "fields": {name: self.fields[name].as_json() for name in FIELDS},
            "lines": self.lines,
            "warnings": self.warnings,
        }


# --- Texto -------------------------------------------------------------------------------


def _fold(text):
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def _plain(text):
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").casefold()


def page_lines(reading):
    """Las líneas útiles de cada página: `[(numero_de_pagina, [texto, …]), …]`. Se dejan afuera
    las líneas que la lectura descartó (encabezados y pies)."""
    pages = []
    for page in reading.pages:
        lines = [_fold(line.text) for line in page.lines if not line.discarded and line.text.strip()]
        pages.append((page.number, lines))
    return pages


def _front(pages):
    return pages[:FRONT_PAGES]


def _add(candidates, value):
    if value not in candidates:
        candidates.append(value)


def _datum(candidates_found, method=METHOD_RULE):
    """`candidates_found` son `(valor, Citation)`; el primero se propone y los distintos quedan
    como candidatos."""
    if not candidates_found:
        return Datum()
    value, citation = candidates_found[0]
    candidates = []
    for other, _ in candidates_found:
        _add(candidates, other)
    return Datum(value=value, citation=citation, candidates=candidates, method=method)


# --- Reglas ------------------------------------------------------------------------------


def _find_number(front):
    found = []
    for page, lines in front:
        for line in lines:
            match = _NUMBER_LABEL.match(line) or None
            if match is None:
                continue
            found.append((match.group(1).rstrip(".,;"), Citation(page, line)))
    return found


def _find_file_number(front):
    found = []
    for page, lines in front:
        for line in lines:
            match = _FILE_PATTERN.search(line) or _FILE_BARE.search(line)
            if match:
                found.append((match.group(1).rstrip(".,;"), Citation(page, line)))
    return found


def _find_type(front):
    found = []
    for page, lines in front:
        for line in lines:
            match = _TYPE_PATTERN.search(line)
            if match:
                value = _fold(match.group(0)).capitalize()
                found.append((value, Citation(page, line)))
    return found


def _find_subject(front):
    found = []
    for page, lines in front:
        for line in lines:
            match = _SUBJECT_LABEL.match(line)
            if match:
                found.append((match.group(1).strip(), Citation(page, line)))
    return found


def _parse_date(line):
    for match in _DATE_NUMERIC.finditer(line):
        day, month, year = (int(g) for g in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            continue
    for match in _DATE_WORDS.finditer(line):
        month = _MONTHS.get(_plain(match.group(2)))
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                continue
    return None


def _find_date(front):
    found = []
    for page, lines in front:
        for line in lines:
            if _DATE_LABEL.search(line):
                parsed = _parse_date(line)
                if parsed is not None:
                    found.append((parsed.isoformat(), Citation(page, line)))
    return found


# --- Modelo ------------------------------------------------------------------------------


def _verified(answer, page_texts):
    """`(valor, Citation)` si la cita es literal de una página y el valor está dentro de ella;
    si no, `None`."""
    if not isinstance(answer, dict):
        return None
    value, quote = _fold(str(answer.get("valor") or "")), _fold(str(answer.get("cita") or ""))
    if not value or not quote or _plain(value) not in _plain(quote):
        return None
    for page, text in page_texts:
        if quote in text:
            return value, Citation(page, quote)
    return None


def ask_model(front, missing):
    """Pregunta al modelo local por los datos de `missing` (`procedure_type`, `subject`).
    Devuelve `({dato: Datum}, traza)`; la traza (instrucciones, parámetros, fragmento, pedido
    y salida) va al registro de auditoría (P6)."""
    page_texts = [(page, _fold(" ".join(lines))) for page, lines in front]
    fragment = "\n\n".join(f"[Página {page}]\n" + "\n".join(lines) for page, lines in front)
    fragment = fragment[:MODEL_MAX_CHARS]
    messages = [{"role": "system", "content": MODEL_INSTRUCTIONS},
                {"role": "user", "content": fragment}]
    trace = {
        "prompt_version": PROMPT_VERSION,
        "instructions_sha256": hashlib.sha256(MODEL_INSTRUCTIONS.encode()).hexdigest(),
        "asked": list(missing),
        "fragment_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
        "fragment_chars": len(fragment),
    }
    result = {}
    try:
        answer = generation.generate(messages, MODEL_SCHEMA)
    except AIServiceError as error:
        trace["error"] = f"{error.reason}: {error}"
        return result, trace
    trace["request"] = answer.request
    trace["output"] = answer.content
    trace["finish_reason"] = answer.finish_reason
    try:
        parsed = json.loads(answer.content)
    except (TypeError, ValueError):
        trace["error"] = "salida_invalida"
        return result, trace
    for name in missing:
        verified = _verified(parsed.get(name) if isinstance(parsed, dict) else None, page_texts)
        if verified:
            value, citation = verified
            result[name] = Datum(value=value, citation=citation, candidates=[value],
                                 method=METHOD_MODEL)
    return result, trace


# --- Renglones ---------------------------------------------------------------------------

_HEADER_KEYS = (
    ("number", ("renglon", "item", "nro", "n°", "nº")),
    ("description", ("descripcion", "detalle", "bien", "especificacion")),
    ("quantity", ("cantidad", "cant")),
    ("unit", ("unidad",)),
)
_QUANTITY = re.compile(r"^\s*(\d[\d.,]*)\s*(.*?)\s*$")


def _columns(row):
    """Qué columna es cuál, según una fila de títulos; `None` si no es una fila de títulos de
    renglones (necesita al menos número, descripción y cantidad)."""
    mapping = {}
    for index, cell in enumerate(row):
        plain = _plain(_fold(cell or ""))
        for name, keys in _HEADER_KEYS:
            if name not in mapping and any(plain.startswith(k) or plain == k for k in keys):
                mapping[name] = index
                break
    if {"number", "description", "quantity"} <= set(mapping):
        return mapping
    return None


def parse_quantity(text):
    """`(cantidad, unidad)` de una celda como «100 UNIDADES» o «1.500,50»; la cantidad como
    texto decimal, o `None` si no se entiende."""
    match = _QUANTITY.match(text or "")
    if not match:
        return None, ""
    raw, unit = match.group(1), match.group(2)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None, unit
    return format(value.normalize(), "f"), unit


def _tables(data):
    """Tablas de un PDF, página por página: `[(pagina, [fila, …]), …]`."""
    import pdfplumber

    found = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                found.append((number, table))
    return found


def extract_lines(data):
    """Los renglones de la tabla de renglones de un PDF: `(renglones, avisos)`. Cada renglón es
    `{number, description, quantity, unit, citation}`; el que repite un número ya tomado se deja
    afuera y queda en los avisos."""
    lines, warnings, seen = [], [], set()
    mapping = None
    for page, rows in _tables(data):
        start = 0
        header = _columns(rows[0]) if rows else None
        if header:
            mapping, start = header, 1
        elif mapping is None or len(rows[0]) <= max(mapping.values()):
            continue
        for row in rows[start:]:
            cells = [_fold(c or "") for c in row]
            if len(cells) <= max(mapping.values()):
                continue
            digits = re.fullmatch(r"\d+", cells[mapping["number"]])
            description = cells[mapping["description"]]
            if not digits or not description:
                continue
            number = int(digits.group(0))
            if number in seen:
                warnings.append(f"Renglón {number} repetido en la página {page}: se tomó el primero.")
                continue
            seen.add(number)
            quantity, unit = parse_quantity(cells[mapping["quantity"]])
            if "unit" in mapping and cells[mapping["unit"]]:
                unit = cells[mapping["unit"]]
            lines.append({
                "number": number,
                "description": description,
                "quantity": quantity,
                "unit": unit,
                "citation": Citation(page, " | ".join(cells)).as_json(),
            })
    return lines, warnings


# --- Entrada -----------------------------------------------------------------------------


def propose(data, *, use_model=True):
    """Lee el pliego `data` y arma la propuesta. Un archivo que no se puede leer levanta el
    error de la lectura (el pedido queda fallido)."""
    reading = read_document(data)
    pages = page_lines(reading)
    front = _front(pages)
    found = {
        "number": _datum(_find_number(front)),
        "file_number": _datum(_find_file_number(front)),
        "procedure_type": _datum(_find_type(front)),
        "subject": _datum(_find_subject(front)),
        "authorization_date": _datum(_find_date(front)),
    }
    trace = []
    missing = [name for name in ("procedure_type", "subject") if not found[name].value]
    if use_model and missing and front:
        answered, model_trace = ask_model(front, missing)
        found.update(answered)
        trace.append(model_trace)
    lines, warnings = ([], [])
    if detect_format(data) == FORMAT_PDF:
        lines, warnings = extract_lines(data)
    return Proposal(
        fields=found, lines=lines, warnings=warnings,
        reading={"tool_versions": {**reading.tool_versions, "rules_version": RULES_VERSION},
                 "pages": len(reading.pages)},
        model_trace=trace,
    )
