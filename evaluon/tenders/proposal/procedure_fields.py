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

DEDUCED_FROM_NUMBER = "numero_de_proceso"

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
    r"^\s*(?:n[uú]mero\s+de\s+(?:proceso|procedimiento)|proceso\s+de\s+compras?|"
    r"proceso\s+(?:n[º°]\.?|nro\.?)|procedimiento\s+(?:n[º°]\.?|nro\.?)|"
    r"(?:proceso|procedimiento)\s*:)\s*:?\s*" + _VALUE,
    re.I)
_FILE_PATTERN = re.compile(
    r"(?:expediente|actuaci[oó]n)\s*(?:n[º°o]\.?|nro\.?|n[uú]mero)?\s*:?\s*"
    r"((?:EX-)?[0-9A-Za-z][0-9A-Za-z\-/#.]*[0-9A-Za-z-](?:\s+-[0-9A-Za-z\-/#.]*[0-9A-Za-z])?)",
    re.I)
_FILE_BARE = re.compile(r"\b(EX-\d{4}-\d+[0-9A-Za-z\-#]*)")
_TYPE_NAMES = (
    r"licitaci[oó]n\s+p[uú]blica|licitaci[oó]n\s+privada|contrataci[oó]n\s+directa|"
    r"concurso\s+p[uú]blico|concurso\s+privado|subasta\s+p[uú]blica|compulsa\s+abreviada|"
    r"contrataci[oó]n\s+menor"
)
_TYPE_PATTERN = re.compile(r"(" + _TYPE_NAMES + r")(\s+(?:nacional|internacional))?", re.I)
_TYPE_LABEL = re.compile(
    r"^\s*(?:tipo\s+de\s+(?:procedimiento|proceso|contrataci[oó]n)|modalidad|"
    r"procedimiento\s+de\s+selecci[oó]n)\s*:\s*(.+\S)\s*$", re.I)
# Los últimos letras del número de proceso del Portal de Compras dicen el tipo
# (A0PC000000-0001-LPU26: licitación pública). Solo los que el Régimen General nombra.
_TYPE_CODES = {
    "LPU": "Licitación pública",
    "LPR": "Licitación privada",
    "CDI": "Contratación directa",
}
_TYPE_CODE = re.compile(r"-(" + "|".join(_TYPE_CODES) + r")\d{2}(?!\d)")
_SUBJECT_LABEL = re.compile(
    r"^\s*(?:nombre\s+del\s+proceso|objeto\s+del\s+llamado|"
    r"objeto\s+de\s+la\s+contrataci[oó]n|objeto)\s*:\s*(.+\S)\s*$",
    re.I)
# Otro dato rotulado («EXPEDIENTE Nº: …»): corta el objeto que sigue en varias líneas.
_NEXT_LABEL = re.compile(r"^\s*[^:]{2,40}:(\s|$)")
# Una línea de ancho completo sigue en la de abajo; una corta cierra el párrafo.
_WRAPPED_LENGTH = 60
_DATE_LABEL = re.compile(
    r"fecha\s+de\s+autorizaci|autoriz\w*\s+(?:el\s+|la\s+)?"
    r"(?:llamado|convocatoria|contrataci|procedimiento|proceso)|"
    r"(?:llamado|convocatoria|procedimiento|proceso)\s+(?:fue\s+)?autorizad", re.I)
_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_DATE_WORDS = re.compile(r"\b(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})\b", re.I)


@dataclass
class Citation:
    page: int
    text: str
    # Si el dato no está escrito en la cita sino deducido de ella (por ejemplo, el tipo del
    # código del número de proceso): de qué se dedujo.
    deduced: str = ""

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
            "deduced": self.citation.deduced if self.citation else "",
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
            if match and any(char.isdigit() for char in match.group(1)):
                found.append((match.group(1).rstrip(".,;"), Citation(page, line)))
    return found


def _find_type(front, number_found=()):
    found = []
    for page, lines in front:
        for line in lines:
            match = _TYPE_LABEL.match(line)
            if match:
                inner = _TYPE_PATTERN.search(match.group(1))
                value = _fold(inner.group(0) if inner else match.group(1)).capitalize()
                found.append((value, Citation(page, line)))
    # El código del número de proceso: la cita es la línea del número.
    for value, citation in number_found:
        code = _TYPE_CODE.search(value)
        if code:
            found.append((_TYPE_CODES[code.group(1)],
                          Citation(citation.page, citation.text, deduced=DEDUCED_FROM_NUMBER)))
    # El nombre del tipo en el texto, solo en la carátula (más lejos puede ser otra cosa).
    for page, lines in front[:1]:
        for line in lines:
            match = _TYPE_PATTERN.search(line)
            if match:
                found.append((_fold(match.group(0)).capitalize(), Citation(page, line)))
    return found


def _find_subject(front):
    found = []
    for page, lines in front:
        for index, line in enumerate(lines):
            match = _SUBJECT_LABEL.match(line)
            if not match:
                continue
            parts = [line]
            value = match.group(1).strip()
            # El objeto sigue en las líneas de abajo hasta otro dato rotulado (como máximo 3).
            previous = line
            for follow in lines[index + 1:index + 4]:
                if len(previous) < _WRAPPED_LENGTH or _NEXT_LABEL.match(follow)                         or re.match(r"^\s*\d+(\.\d+)*\.?\s", follow):
                    break
                previous = follow
                parts.append(follow)
                value = f"{value} {follow.strip()}"
            found.append((value, Citation(page, " ".join(parts))))
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
        for index, line in enumerate(lines):
            # La fecha puede quedar en la línea de abajo del renglón que dice «autoriza».
            text = line if _parse_date(line) else " ".join(lines[index:index + 2])
            if _DATE_LABEL.search(line) and _parse_date(text) is not None:
                found.append((_parse_date(text).isoformat(), Citation(page, text)))
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
    if {"number", "quantity"} <= set(mapping):
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
    afuera y queda en los avisos. Una tabla sin descripción (renglón y cantidad) da las
    cantidades aparte, como tercer valor."""
    lines, warnings, seen, quantities = [], [], set(), []
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
            description = cells[mapping["description"]] if "description" in mapping else ""
            if not digits or (not description and "description" in mapping):
                continue
            number = int(digits.group(0))
            if not description:
                quantity, unit = parse_quantity(cells[mapping["quantity"]])
                if quantity is not None:
                    if "unit" in mapping and cells[mapping["unit"]]:
                        unit = cells[mapping["unit"]]
                    quantities.append({
                        "number": number, "description": "", "quantity": quantity,
                        "unit": unit or "",
                        "citation": Citation(page, " | ".join(cells)).as_json()})
                continue
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
    return lines, warnings, quantities


# --- Renglones escritos como texto -------------------------------------------------------

# Encabezado de una tabla sin bordes: «RENGLÓN  BIEN / SERVICIO  CANTIDAD …» en una línea.
_LAYOUT_HEADER = re.compile(r"^\s*rengl[oó]n\b(?!.*\.{5}).*\bcantidad\b", re.I)
_ROW_START = re.compile(r"^\s*(\d{1,4})(?:\s+(.*\S))?\s*$")
_CLAUSE = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2})+\.?\s|^\s*\d{1,2}\.\s+[A-ZÁÉÍÓÚÑ]")
_TRAILING_QUANTITY = re.compile(r"^(.*\S)\s+(\d[\d.,]*)(?:\s+([^\W\d_][\w²³/%.]*))?$")
_ONLY_QUANTITY = re.compile(r"^(\d[\d.,]*)\s*([^\W\d_][\w²³/%.]*(?:\s+[^\W\d_][\w²³/%.]*)?)?$")
_COLUMN_TOLERANCE = 12
_MARGIN = 55  # puntos arriba y abajo de la página donde hay encabezado y pie

# «7.1 RENGLÓN N°1: DESCRIPCIÓN», «2. RENGLÓN N° 1 - DESCRIPCIÓN»: un título de renglón.
_HEADING = re.compile(
    r"^\s*\d{1,2}(?:\.\d{1,2})?\.?\s*RENGL[OÓ]N\s*(?:N[º°]|NRO\.?)\s*(\d+)\s*[-–:]\s*(\S.*)$", re.I)
_HEADING_NEXT = re.compile(r"\s+Y\s+RENGL[OÓ]N\s*(?:N[º°]|NRO\.?)\s*(\d+)\s*[-–:]\s*", re.I)
_QUANTITY_NEAR = re.compile(
    r"cantidad\s*(?:total)?\s*:\s*(?:[^\W\d_]+\s*)?\(?(\d[\d.,]*)\)?\s*([^\W\d_][\w²³/%.]*)?",
    re.I)


def _usable(page):
    """Las líneas de la página que están entre el encabezado y el pie."""
    height = page.height or 842
    return [line for line in page.lines
            if not line.discarded and line.text.strip() and line.top is not None
            and _MARGIN < line.top < height - _MARGIN]


def _row(number, pieces, page):
    """Un renglón de la tabla a partir de sus fragmentos de texto (`(x, texto)` en el orden de
    lectura). La cantidad es el fragmento de la derecha que es un número con su unidad, o el
    final del texto."""
    quantity = unit = None
    texts = list(pieces)
    if len(texts) > 1:
        x, last = texts[-1]
        if _ONLY_QUANTITY.match(last) and x > texts[0][0] + 60:
            quantity, unit = parse_quantity(last)
            texts = texts[:-1]
    description = _fold(" ".join(text for _, text in texts))
    if quantity is None:
        match = _TRAILING_QUANTITY.match(description)
        if match:
            parsed, _ = parse_quantity(match.group(2))
            if parsed is not None:
                description, quantity, unit = match.group(1), parsed, match.group(3)
    citation = _fold(" ".join([str(number)] + [text for _, text in pieces]))
    if quantity is None and _ONLY_QUANTITY.match(description):
        # Tabla de cantidades aparte: solo número, cantidad y unidad (sin descripción).
        quantity, unit = parse_quantity(description)
        description = ""
    if not description and quantity is None:
        return None
    return {"number": number, "description": description, "quantity": quantity,
            "unit": unit or "", "citation": Citation(page, citation).as_json()}


def layout_lines(reading):
    """Renglones de una tabla sin bordes dibujados, leída como líneas de texto con su posición:
    desde el encabezado «RENGLÓN … CANTIDAD» hasta la primera cláusula. Devuelve
    `(renglones, cantidades)`: las cantidades son las filas de una tabla aparte, sin descripción."""
    rows, current, in_table, number_x = [], None, False, None
    for page in reading.pages:
        for line in _usable(page):
            text = _fold(line.text)
            if _LAYOUT_HEADER.match(text):
                if current:
                    rows.append(current)
                current, in_table, number_x = None, True, None
                continue
            if not in_table:
                continue
            start = _ROW_START.match(text)
            if number_x is None:
                if start and not _CLAUSE.match(text):
                    number_x = line.x0
                else:
                    continue
            if (line.x0 is not None and line.x0 < number_x - 2 * _COLUMN_TOLERANCE) \
                    or _CLAUSE.match(text):
                if current:
                    rows.append(current)
                current, in_table, number_x = None, False, None
                continue
            if start and abs((line.x0 or 0) - number_x) <= _COLUMN_TOLERANCE:
                if current:
                    rows.append(current)
                rest = start.group(2)
                current = (int(start.group(1)), page.number,
                           [(line.x0, rest)] if rest else [])
            elif current:
                current[2].append((line.x0, text))
    if current:
        rows.append(current)
    lines, quantities = [], []
    for number, page_number, pieces in rows:
        row = _row(number, pieces, page_number)
        if row and row["description"]:
            lines.append(row)
        elif row:
            quantities.append(row)
    return lines, quantities


_LEADERS = re.compile(r"[.…·]{4,}|(?:\.\s){4,}")


def _is_index_entry(text, on_index_page):
    """Una entrada del índice: puntos guía, o (en la página del índice) un número de página al
    final. No es fuente de descripciones: manda el título del cuerpo."""
    return bool(_LEADERS.search(text)) or (
        on_index_page and bool(re.search(r"\s\d{1,3}$", text)))


def heading_lines(reading):
    """Renglones que el pliego titula «N. RENGLÓN N° 1 - DESCRIPCIÓN» (especificaciones). Se
    saltea el índice (líneas con puntos guía). La cantidad, si hay una «CANTIDAD: n unidad» en
    el título o en las tres líneas que siguen."""
    found = {}
    for page in reading.pages:
        usable = _usable(page)
        on_index = any(re.fullmatch(r"\s*[ÍI]NDICE\s*", line.text, re.I) for line in usable)
        for index, line in enumerate(usable):
            text = _fold(line.text)
            if _is_index_entry(text, on_index):
                continue
            match = _HEADING.match(text)
            if not match:
                continue
            full = text
            # El título sigue en la línea de abajo si esta no empieza otro título o cláusula.
            follow = usable[index + 1] if index + 1 < len(usable) else None
            if follow is not None and len(text) > 60 and not text.rstrip().endswith("."):
                nxt = _fold(follow.text)
                if not _HEADING.match(nxt) and not _CLAUSE.match(nxt) \
                        and not re.match(r"^\s*(\d+\.|RENGL)", nxt, re.I) \
                        and (follow.x0 or 0) >= (line.x0 or 0) - 2:
                    full = f"{text} {nxt}"
            body = _HEADING.match(full)
            number, description = int(body.group(1)), body.group(2)
            # «RENGLÓN N° 1 - A Y RENGLÓN N° 2 - B» en un mismo título.
            parts = [(number, description)]
            split = _HEADING_NEXT.search(description)
            if split:
                parts = [(number, description[:split.start()]),
                         (int(split.group(1)), description[split.end():])]
            # Hasta el título que sigue (como máximo 8 líneas): su «Cantidad: …» es de este.
            window_lines = [text]
            for item in usable[index + 1:index + 9]:
                if _HEADING.match(_fold(item.text)):
                    break
                window_lines.append(_fold(item.text))
            window = " ".join(window_lines)
            near = _QUANTITY_NEAR.search(window)
            for number, description in parts:
                quantity = unit = None
                if near and len(parts) == 1:
                    quantity, unit = parse_quantity(f"{near.group(1)} {near.group(2) or ''}")
                    unit = unit.rstrip(".,;")
                if number in found:
                    # El mismo renglón otra vez (por ejemplo, el alcance y luego el detalle): la
                    # descripción es la primera; la cantidad, la primera que aparezca.
                    if found[number]["quantity"] is None and quantity is not None:
                        found[number]["quantity"], found[number]["unit"] = quantity, unit or ""
                        found[number]["quantity_citation"] = Citation(page.number, full).as_json()
                    continue
                found[number] = {
                    "number": number, "description": _fold(description).rstrip(" .-"),
                    "quantity": quantity, "unit": unit or "",
                    "citation": Citation(page.number, full).as_json()}
    return list(found.values())


def merge_lines(*groups, quantities=()):
    """Une grupos de renglones; el primero que trae un número gana (las tablas, antes que los
    títulos). A los que quedan sin cantidad les completa cantidad y unidad la tabla de cantidades
    del mismo número, con la cita de esa fila (`quantity_citation`). Devuelve los renglones
    ordenados por número."""
    seen, merged = set(), []
    for group in groups:
        for line in group:
            if line["number"] not in seen:
                seen.add(line["number"])
                merged.append(line)
    by_number = {}
    for row in quantities:
        by_number.setdefault(row["number"], row)
    for line in merged:
        row = by_number.get(line["number"])
        if line["quantity"] is None and row is not None:
            line["quantity"], line["unit"] = row["quantity"], row["unit"]
            line["quantity_citation"] = row["citation"]
    merged.sort(key=lambda item: item["number"])
    return merged


# --- Entrada -----------------------------------------------------------------------------


def propose(data, *, use_model=True):
    """Lee el pliego `data` y arma la propuesta. Un archivo que no se puede leer levanta el
    error de la lectura (el pedido queda fallido)."""
    reading = read_document(data)
    pages = page_lines(reading)
    front = _front(pages)
    numbers = _find_number(front)
    found = {
        "number": _datum(numbers),
        "file_number": _datum(_find_file_number(front)),
        "procedure_type": _datum(_find_type(front, numbers)),
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
        drawn, warnings, drawn_quantities = extract_lines(data)
        laid_out, laid_quantities = layout_lines(reading)
        lines = merge_lines(laid_out, drawn, heading_lines(reading),
                            quantities=[*laid_quantities, *drawn_quantities])
    else:
        lines = merge_lines(heading_lines(reading))
    return Proposal(
        fields=found, lines=lines, warnings=warnings,
        reading={"tool_versions": {**reading.tool_versions, "rules_version": RULES_VERSION},
                 "pages": len(reading.pages)},
        model_trace=trace,
    )
