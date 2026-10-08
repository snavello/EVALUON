"""Nombre y CUIT del oferente que se proponen al leer los archivos de una oferta (REQ-083;
ADR-0049; T-220).

Primera ronda, por reglas (mismo patrón que `tenders/proposal/procedure_fields.py`):

- CUIT: se buscan números de 11 cifras con prefijo de persona o sociedad, con o sin guiones,
  y solo valen los que cumplen el dígito verificador. Se elige el que más respaldo tiene en
  los archivos: aparece rotulado («CUIT»), junto a un rótulo de oferente o razón social y en
  más de un lugar. Se descartan el CUIT del organismo contratante y los que figuran en una
  línea de aseguradora, banco o fiador (una póliza lleva el CUIT de la aseguradora).
- Nombre: «Razón social: …», «Denominación: …», «Oferente: …» y similares; el texto que
  precede a un CUIT cuando termina en un tipo societario («S.A.», «S.R.L.»…); una línea corta
  de la carátula que es solo un nombre con tipo societario. Un nombre rotulado pesa más que
  los otros.

Cada dato lleva su cita: documento (nombre y huella), página y texto de la línea. Sin cita
verificable queda «no determinado» y no se propone (P3).

El modelo local entra solo para el nombre cuando las reglas no lo hallaron, pidiéndole la
cita literal; la cita se verifica contra el texto de la página y el valor tiene que estar
dentro de ella. Una falla del modelo deja el nombre sin determinar; nunca hace fallar la
propuesta. El CUIT nunca lo propone el modelo. Todo corre en local (P4) y el pedido, con sus
instrucciones, parámetros y fragmentos, queda en la traza que devuelve `propose` (P6).

Este módulo no toca la base: recibe las lecturas y devuelve datos.
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

from evaluon.ai import AIServiceError, generation
from evaluon.tenders.proposal.procedure_fields import page_lines

RULES_VERSION = "oferente-reglas-v1"
PROMPT_VERSION = "oferente-nombre-v1"

FIELDS = ("bidder", "cuit")

STATE_PROPOSED = "propuesto"
STATE_UNDETERMINED = "no_determinado"

METHOD_RULE = "regla"
METHOD_MODEL = "modelo"

# Páginas de cada archivo donde se buscan los datos; y de ellas, las del comienzo que se le
# muestran al modelo, con el texto máximo (en caracteres) del fragmento.
SCAN_PAGES = 8
MODEL_PAGES = 2
MODEL_MAX_CHARS = 6000

# Del nombre que se propone.
NAME_MIN_CHARS = 3
NAME_MAX_CHARS = 120

# CUIT del organismo contratante (AFIP/ARCA): figura en formularios que el oferente completa
# y no es el del oferente.
ORGANISM_CUITS = frozenset({"33693450239"})
_ORGANISM_NAMES = ("afip", "arca", "administracion federal de ingresos publicos",
                   "agencia de recaudacion y control aduanero")

MODEL_INSTRUCTIONS = (
    "Sos un lector de ofertas presentadas a un procedimiento de compras. Del texto que sigue, "
    "que es el comienzo de los archivos de una oferta, indicá el nombre o razón social del "
    "oferente (quien presenta la oferta; no el organismo que contrata ni una aseguradora o "
    "un banco). Devolvé el valor y la cita: un fragmento copiado literal del texto, sin "
    "cambiar ni una letra, que contenga el valor. Si el texto no lo dice, devolvé el valor y "
    "la cita vacíos. No inventes."
)
MODEL_SCHEMA = {
    "type": "object",
    "properties": {
        "bidder": {
            "type": "object",
            "properties": {"valor": {"type": "string"}, "cita": {"type": "string"}},
            "required": ["valor", "cita"],
            "additionalProperties": False,
        }
    },
    "required": ["bidder"],
    "additionalProperties": False,
}

# --- CUIT ------------------------------------------------------------------------------

_PREFIXES = "20|23|24|25|26|27|30|33|34"
_CUIT_ANY = re.compile(
    r"(?<![\d])(" + _PREFIXES + r")[-\s.]?(\d{8})[-\s.]?(\d)(?!\d)")
_CUIT_HYPHENS = re.compile(r"(?<![\d])(" + _PREFIXES + r")-(\d{8})-(\d)(?!\d)")
_CUIT_LABEL = re.compile(r"\bC\.?\s?U\.?\s?I\.?\s?T\.?\b|\bCUIL\b", re.I)
_OWNER_LABEL = re.compile(
    r"raz[oó]n\s+social|oferente|proponente|proveedor|denominaci[oó]n|empresa|firma", re.I)
_THIRD_PARTY = re.compile(
    r"asegurador|compa[ñn][ií]a\s+de\s+seguros|\bbanco\b|entidad\s+financiera|fiador|"
    r"escribano|contador", re.I)
_WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def cuit_is_valid(digits):
    """`True` si `digits` (solo cifras) es un CUIT de 11 cifras con prefijo conocido y dígito
    verificador correcto."""
    if not re.fullmatch(r"\d{11}", digits or "") or digits[:2] not in _PREFIXES.split("|"):
        return False
    total = sum(int(d) * w for d, w in zip(digits[:10], _WEIGHTS, strict=True))
    check = 11 - total % 11
    if check == 11:
        check = 0
    return check != 10 and check == int(digits[10])


def normalize_cuit(text):
    """El CUIT escrito como `NN-NNNNNNNN-N` si `text` es un CUIT válido (con o sin guiones o
    espacios); `None` si no."""
    digits = re.sub(r"[-\s.]", "", str(text or ""))
    if not cuit_is_valid(digits):
        return None
    return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"


# --- Texto -----------------------------------------------------------------------------


def _fold(text):
    return " ".join(unicodedata.normalize("NFC", text or "").split())


def _plain(text):
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").casefold()


def _key(name):
    return re.sub(r"[^a-z0-9]", "", _plain(name))


@dataclass
class Source:
    """La lectura de un archivo de la oferta: su nombre, su huella y sus líneas por página."""

    file_name: str
    file_sha256: str
    pages: list  # [(número de página, [línea, …]), …]

    @classmethod
    def from_reading(cls, file_name, file_sha256, reading):
        return cls(file_name, file_sha256, page_lines(reading))


@dataclass
class Citation:
    file_name: str
    file_sha256: str
    page: int
    text: str

    def as_json(self):
        return {"document": self.file_name, "file_sha256": self.file_sha256,
                "page": self.page, "text": self.text}


@dataclass
class Datum:
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
    warnings: list
    reading: list
    model_trace: list = field(default_factory=list)

    def as_json(self):
        return {"fields": {name: self.fields[name].as_json() for name in FIELDS},
                "warnings": self.warnings}


def _scanned(sources):
    """`(fuente, página, índice de línea, líneas, línea)` de las primeras páginas."""
    for source in sources:
        for page, lines in source.pages[:SCAN_PAGES]:
            for index, line in enumerate(lines):
                yield source, page, index, lines, line


# --- Reglas del CUIT -------------------------------------------------------------------


def _cuits_in(line, next_line=""):
    """CUIT válidos de una línea (y, si la línea es un rótulo «CUIT:» sin número, de la que
    sigue): `[(cuit con guiones, rotulado)]`. Sin rótulo solo valen los escritos con guiones."""
    found = []
    labeled = bool(_CUIT_LABEL.search(line))
    text = line
    if labeled and not _CUIT_ANY.search(line) and next_line:
        text = f"{line} {next_line}"
    pattern = _CUIT_ANY if labeled else _CUIT_HYPHENS
    for match in pattern.finditer(text):
        digits = "".join(match.groups())
        if cuit_is_valid(digits) and digits not in ORGANISM_CUITS:
            found.append((f"{digits[:2]}-{digits[2:10]}-{digits[10]}", labeled))
    return found


def find_cuit(sources):
    """El CUIT con más respaldo y los demás como candidatos: `Datum`."""
    score, first, citations = {}, {}, {}
    order = 0
    for source, page, index, lines, line in _scanned(sources):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        previous = lines[index - 1] if index else ""
        for cuit, labeled in _cuits_in(line, next_line):
            weight = 3 if labeled else 1
            if _OWNER_LABEL.search(line) or _OWNER_LABEL.search(previous):
                weight += 2
            if _THIRD_PARTY.search(line) or _THIRD_PARTY.search(previous):
                weight -= 4
            score[cuit] = score.get(cuit, 0) + weight
            if cuit not in first:
                first[cuit] = order
                citations[cuit] = Citation(source.file_name, source.file_sha256, page, line)
            elif weight > 0 and score[cuit] - weight <= 0:
                citations[cuit] = Citation(source.file_name, source.file_sha256, page, line)
            order += 1
    ranked = sorted((c for c in score if score[c] > 0), key=lambda c: (-score[c], first[c]))
    if not ranked:
        return Datum()
    return Datum(value=ranked[0], citation=citations[ranked[0]], candidates=ranked,
                 method=METHOD_RULE)


# --- Reglas del nombre -----------------------------------------------------------------

_NAME_LABEL = re.compile(
    r"^\s*(?:[\dA-Za-z]{1,2}[.)]\s+)?"
    r"(?:nombre\s+(?:o|y)\s+raz[oó]n\s+social|apellido\s+y\s+nombre\s+o\s+raz[oó]n\s+social|"
    r"raz[oó]n\s+social|denominaci[oó]n(?:\s+social)?|nombre\s+del\s+oferente|oferente|"
    r"proponente|firma\s+oferente|proveedor|empresa)"
    r"\s*(?:\([^)]*\))?\s*[:\-–]\s*(.*)$", re.I)
_LABEL_ONLY = re.compile(
    r"^\s*(?:nombre\s+(?:o|y)\s+raz[oó]n\s+social|raz[oó]n\s+social|denominaci[oó]n"
    r"(?:\s+social)?|oferente|proponente)\s*:\s*$", re.I)
_SUFFIX = re.compile(
    r"(?:\bS\.?\s?A\.?\s?S\.?|\bS\.?\s?R\.?\s?L\.?|\bS\.?\s?A\.?|\bS\.?\s?C\.?\s?A\.?|"
    r"\bS\.?\s?C\.?\s?S\.?|\bS\.?\s?H\.?|\bS\.?\s?E\.?|\bU\.?\s?T\.?\s?E\.?|"
    r"\bSOCIEDAD\s+AN[OÓ]NIMA|\bSOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA)\s*[.,;]?\s*$",
    re.I)
_TAIL_CUT = re.compile(
    r"\s*[-–,;(]?\s*\bC\.?\s?U\.?\s?I\.?\s?T\.?\b.*$|,?\s+con\s+domicilio\b.*$|"
    r",?\s+inscript[oa]\b.*$", re.I)
_PLACEHOLDER = re.compile(r"^(?:ver\b|seg[uú]n\b|completar|a\s+completar|\.{2,}|_{2,}|-+$)", re.I)

WEIGHT_LABELED = 3
WEIGHT_BEFORE_CUIT = 2
WEIGHT_STANDALONE = 1


def _clean_name(value):
    value = _TAIL_CUT.sub("", _fold(value)).strip(" ,;:-–\"'“”")
    # El punto final solo se conserva si cierra una sigla («S.A.»).
    if value.endswith(".") and not re.search(r"(?:^|[\s.])[A-Za-z]\.$", value):
        value = value.rstrip(". ")
    return value


_THIRD_NAME = re.compile(
    r"asegurador|aseguradora|\bseguros?\b|compa[ñn][ií]a\s+de\s+seguros|\bbanco\b|"
    r"entidad\s+financiera|fiador|escriban|contador|estudio\s+jur[ií]dico", re.I)
# Palabras de títulos y rótulos: una línea que las trae no es el nombre de una persona.
_NOT_A_PERSON = re.compile(
    r"constancia|inscripci|declaraci|jurada|nota\b|presentaci|oferta|formulario|impuesto|"
    r"datos|domicilio|responsable|monotribut|afip|arca|certificado|anexo|planilla|"
    r"p[oó]liza|propuesta|contribuyente|cuit|cuil|\bdni\b|documento|fecha|firma|"
    r"representante|sociedad|licitaci|pliego|rengl[oó]n|precio|garant[ií]a|"
    r"s\.?\s?a\.?\b|s\.?\s?r\.?\s?l\.?\b", re.I)
_PERSON_WORD = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñü'\-]+$|^(?:de|del|la|las|los|y)$")
_PERSON_LABEL = re.compile(
    r"^\s*(?:apellido\s+y\s+nombres?|nombres?\s+y\s+apellidos?|titular)"
    r"\s*(?:\([^)]*\))?\s*[:\-–]\s*(.*)$", re.I)
_DNI = re.compile(r"\bD\.?\s?N\.?\s?I\.?\b", re.I)
PERSON_PREFIXES = ("20", "23", "24", "27")
# Cuántas líneas alrededor de la línea del CUIT se busca el nombre.
ANCHOR_WINDOW = 3

WEIGHT_PERSON = 2


def _acceptable(name):
    if not (NAME_MIN_CHARS <= len(name) <= NAME_MAX_CHARS):
        return False
    if not re.search(r"[^\W\d_]{2,}", name) or _PLACEHOLDER.match(name):
        return False
    plain = _plain(name)
    if _THIRD_NAME.search(plain):
        return False
    return not any(re.search(rf"\b{re.escape(o)}\b", plain) for o in _ORGANISM_NAMES)


def _person_like(text):
    """`True` si `text` parece nombre y apellido: de 2 a 5 palabras con mayúscula inicial (o
    todo en mayúsculas), solo letras, sin palabras de títulos ni de rótulos."""
    text = _fold(text).strip(" ,;:.-–")
    words = text.split()
    if not 2 <= len(words) <= 5 or len(text) > 60 or _NOT_A_PERSON.search(_plain(text)):
        return False
    if text != text.upper() and not all(_PERSON_WORD.match(w) for w in words):
        return False
    return all(re.fullmatch(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü'\-]+", w) for w in words)


def _anchors(sources, cuit):
    """Dónde está el CUIT elegido: `{(huella del archivo, página): [índice de línea, …]}`."""
    found = {}
    for source in sources:
        for page, lines in source.pages[:SCAN_PAGES]:
            for index, line in enumerate(lines):
                following = lines[index + 1] if index + 1 < len(lines) else ""
                if any(c == cuit for c, _ in _cuits_in(line, following)):
                    found.setdefault((source.file_sha256, page), []).append(index)
    return found


def _candidate_names(sources, cuit):
    """`[(nombre, peso, Citation)]` en el orden en que aparecen. Solo valen los nombres que
    se justifican por su cercanía al CUIT elegido (`ANCHOR_WINDOW` líneas) y que no son de un
    tercero (aseguradora, banco, escribanía, el organismo)."""
    found = []
    anchors = _anchors(sources, cuit)
    person = cuit[:2] in PERSON_PREFIXES
    for source, page, index, lines, line in _scanned(sources):
        marks = anchors.get((source.file_sha256, page))
        if not marks or all(abs(index - m) > ANCHOR_WINDOW for m in marks):
            continue
        on_cuit = index in marks
        distance = min(abs(index - m) for m in marks)

        def take(name, weight, text, page=page, source=source):
            if _acceptable(name) and not _THIRD_NAME.search(_plain(text)):
                found.append((name, weight,
                              Citation(source.file_name, source.file_sha256, page, text)))
                return True
            return False

        match = _NAME_LABEL.match(line)
        if match:
            value, text = match.group(1), line
            if not value.strip() and index + 1 < len(lines):
                value, text = lines[index + 1], f"{line} {lines[index + 1]}"
            take(_clean_name(value), WEIGHT_LABELED, text)
            continue
        if _LABEL_ONLY.match(line) and index + 1 < len(lines):
            take(_clean_name(lines[index + 1]), WEIGHT_LABELED, f"{line} {lines[index + 1]}")
            continue
        match = _PERSON_LABEL.match(line)
        if match and person:
            value, text = match.group(1), line
            if not value.strip() and index + 1 < len(lines):
                value, text = lines[index + 1], f"{line} {lines[index + 1]}"
            name = _clean_name(value)
            if _person_like(name):
                take(name, WEIGHT_LABELED, text)
            continue
        label = _CUIT_LABEL.search(line)
        if on_cuit and label and label.start() > 0:
            segments = [part for part in re.split(r"\s[-–]\s|:", line[:label.start()])
                        if part.strip()]
            name = _clean_name(segments[-1]) if segments else ""
            if _SUFFIX.search(name) and take(name, WEIGHT_BEFORE_CUIT, line):
                continue
            if person and _person_like(name) and take(name, WEIGHT_PERSON, line):
                continue
        if person:
            # Persona humana: nombre y apellido antes del DNI, o solo en una línea vecina.
            dni = _DNI.search(line)
            if dni and dni.start() > 0:
                segments = [part for part in re.split(r"\s[-–]\s|:|,", line[:dni.start()])
                            if part.strip()]
                name = _clean_name(segments[-1]) if segments else ""
                if _person_like(name) and take(name, WEIGHT_PERSON, line):
                    continue
            if not on_cuit and distance <= 1 and ":" not in line and _person_like(line):
                take(_clean_name(line), WEIGHT_STANDALONE, line)
                continue
        # Una línea corta que es solo un nombre con tipo societario, junto al CUIT.
        if not on_cuit and len(line) <= 80 and ":" not in line and len(line.split()) <= 8 \
                and _SUFFIX.search(line):
            take(_clean_name(line), WEIGHT_STANDALONE, line)
    return found


def find_name(sources, cuit=None):
    """El nombre anclado al CUIT elegido `cuit` (texto `NN-NNNNNNNN-N`), con los demás como
    candidatos: `Datum`. Sin CUIT, o ante un empate entre nombres distintos, no se propone
    ninguno (P3): es preferible «no determinado» a un valor equivocado."""
    if not cuit:
        return Datum()
    found = _candidate_names(sources, cuit)
    if not found:
        return Datum()
    score, first = {}, {}
    for order, (name, weight, citation) in enumerate(found):
        key = _key(name)
        score[key] = score.get(key, 0) + weight
        first.setdefault(key, (order, name, citation))
    ordered = sorted(score, key=lambda k: (-score[k], first[k][0]))
    candidates = []
    for key in ordered:
        if first[key][1] not in candidates:
            candidates.append(first[key][1])
    if len(ordered) > 1 and score[ordered[0]] == score[ordered[1]]:
        return Datum(candidates=candidates, method=METHOD_RULE)
    _, value, citation = first[ordered[0]]
    return Datum(value=value, citation=citation, candidates=candidates, method=METHOD_RULE)


# --- Modelo ----------------------------------------------------------------------------


def _verified(answer, page_texts):
    """`(valor, Citation)` si la cita es literal de una página y el valor está dentro de ella;
    si no, `None`."""
    if not isinstance(answer, dict):
        return None
    value, quote = _fold(str(answer.get("valor") or "")), _fold(str(answer.get("cita") or ""))
    if not value or not quote or _plain(value) not in _plain(quote) or not _acceptable(value) \
            or _THIRD_NAME.search(_plain(quote)):
        return None
    for source, page, text in page_texts:
        if quote in text:
            return value, Citation(source.file_name, source.file_sha256, page, quote)
    return None


def ask_model(sources):
    """Pregunta al modelo local por el nombre del oferente. Devuelve `(Datum, traza)`; la
    traza (instrucciones, parámetros, fragmento, pedido y salida) va al registro de
    auditoría (P6). `Datum` vacío si el modelo no responde o su cita no se verifica."""
    page_texts = [(source, page, _fold(" ".join(lines)))
                  for source in sources for page, lines in source.pages[:SCAN_PAGES]]
    fragment = "\n\n".join(
        f"[Archivo {number}, página {page}]\n" + "\n".join(lines)
        for number, source in enumerate(sources, start=1)
        for page, lines in source.pages[:MODEL_PAGES])[:MODEL_MAX_CHARS]
    messages = [{"role": "system", "content": MODEL_INSTRUCTIONS},
                {"role": "user", "content": fragment}]
    trace = {
        "prompt_version": PROMPT_VERSION,
        "instructions_sha256": hashlib.sha256(MODEL_INSTRUCTIONS.encode()).hexdigest(),
        "asked": ["bidder"],
        "fragment_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
        "fragment_chars": len(fragment),
    }
    if not fragment.strip():
        trace["error"] = "sin_texto"
        return Datum(), trace
    try:
        answer = generation.generate(messages, MODEL_SCHEMA)
    except AIServiceError as error:
        trace["error"] = f"{error.reason}: {error}"
        return Datum(), trace
    trace["request"] = answer.request
    trace["output"] = answer.content
    trace["finish_reason"] = answer.finish_reason
    try:
        parsed = json.loads(answer.content)
    except (TypeError, ValueError):
        trace["error"] = "salida_invalida"
        return Datum(), trace
    verified = _verified(parsed.get("bidder") if isinstance(parsed, dict) else None, page_texts)
    if not verified:
        return Datum(), trace
    value, citation = verified
    return Datum(value=value, citation=citation, candidates=[value], method=METHOD_MODEL), trace


# --- Propuesta -------------------------------------------------------------------------


def propose(sources, reading=None):
    """Propone nombre y CUIT del oferente con las lecturas de los archivos de una oferta
    (`Source`). El nombre cae al modelo solo si las reglas no lo hallaron."""
    cuit = find_cuit(sources)
    name = find_name(sources, cuit.value)
    traces = []
    if not name.value:
        asked, trace = ask_model(sources)
        traces.append(trace)
        if asked.value:
            name = asked
    warnings = []
    if not cuit.value:
        warnings.append("No se encontró un CUIT válido en los archivos.")
    if not name.value:
        warnings.append("No se encontró el nombre del oferente en los archivos.")
    return Proposal(fields={"bidder": name, "cuit": cuit}, warnings=warnings,
                    reading=reading or [], model_trace=traces)
