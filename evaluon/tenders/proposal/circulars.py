"""Efecto de las circulares y de las respuestas a consultas sobre la matriz (REQ-031; plan
003, "Circulares y respuestas"; T-083).

Una circular modificatoria o aclaratoria, o la respuesta a la pregunta de un oferente, puede
cambiar, precisar o quitar un requisito del pliego, o agregar uno. La pasada corre después de
las filas técnicas, sobre los requisitos ya numerados como van a quedar en la versión.

**Entrega 2 (T-115).** Lo que `circular_units` no resuelve por clave pasa primero a
`circular_changes`: el modelo extrae, sin ver el pliego, la lista de cambios de la unidad y el
código los aplica por clave; solo los tramos de los cambios sin objetivo, no estables o sin
cita verificable (o toda la unidad, si el modelo falla) siguen el flujo de candidatas que
sigue. Con `CIRCULAR_EXTRACTION_ENABLED` en falso queda la entrega 1 más ese flujo.

**Orden.** Los documentos se procesan por fecha y, a igual fecha, por orden de carga. Cada
tramo de cada documento es un pedido al modelo. El texto que se le muestra de cada cita es el
vigente: si una circular anterior lo modificó, ve el original y el vigente, de modo que dos
circulares sobre la misma cita se aplican una sobre otra, la última por fecha al final.

**Citas candidatas de un tramo.** Las citas de los requisitos que el tramo nombra ("cláusula
1.1", "Renglón N° 2") y, de las demás, las `MATRIX_CIRCULAR_CANDIDATES` (8) que el reranker
puntúa más alto contra el texto del tramo. Una cita del pliego es una sola candidata aunque
varios requisitos la compartan: en un técnico, cada tramo citado es una candidata aparte, y un
tramo común a todos los renglones alcanza la fila de cada uno. Si no entran en el contexto,
se descartan las de menor puntaje; las que el tramo nombra no se descartan salvo que ellas
solas no quepan.

**Qué devuelve el modelo** (instrucciones `prompts/matriz-circulares-v2.md`): `efectos`
(`modifica`, `aclara` o `suprime` sobre una candidata, con el fragmento de la circular que lo
produce), `nuevos` (requisitos formales o económicos que la circular agrega, con su
fragmento) o un motivo de `sin_efecto` (la lista cerrada de descartes del ADR-0019).

**Validación**, como en la extracción. Un efecto sobre una cita que el pedido no mostró se
descarta. Un tramo cuya salida no tiene la forma, o no tiene ni efectos ni nuevos ni motivo,
se vuelve a pedir una vez; si sigue igual queda pendiente (`sin_disposicion`). Cada fragmento
se busca exacto dentro del tramo (`quotes.locate`); si no está, se vuelve a pedir el tramo
una vez y, si sigue sin estar, el fragmento es el tramo entero de la circular y se anota
(`circular_cita_amplia`). Un efecto nunca se pierde por una cita mal copiada.

**Contexto de un tramo suelto** (T-098): una circular sin cláusulas parte un apartado en una
línea por tramo; un tramo que no es una cláusula numerada se muestra con el encabezado del
apartado ("II. …") y los dos tramos anteriores, y el reranker lo puntúa con ese encabezado.
La cláusula completa (y su ruta) es lo que el reranker puntúa de cada cita. Además de las que
nombra por cláusula o renglón, el tramo alcanza las citas cuya cláusula define el anexo que
nombra ("Anexo VI") o que mencionan el título entre comillas que el tramo repite.

**Disposición de cada tramo de circular** (nunca desaparece): con efectos o requisitos
nuevos, `requisitos`; sin efecto, `descartado` con el motivo; un título, `descartado`
(`titulo`); una página, `pendiente`; un tramo no ubicado lo ve el modelo (y sigue pendiente
por la lectura); una salida sin forma después del
reintento, `pendiente` (`sin_disposicion`).

Este módulo no escribe los requisitos: devuelve el `Result` y quien guarda la versión
(`run._save`) crea las fuentes (`tenders_requirement_source`) y los requisitos nuevos
(origen `circular`). Los pedidos sí se guardan apenas vuelven, en `tenders_run_step` (P6).
"""

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import AIServiceError, generation, reranker
from evaluon.tenders.models import (
    DATED_DOCUMENT_KINDS,
    DiscardReason,
    DispositionOutcome,
    DispositionSource,
    PassName,
    PendingReason,
    RequirementClass,
    RunStep,
    SegmentType,
    SourceEffect,
)
from evaluon.tenders.proposal import extraction, quotes

EFFECTS = tuple(effect.value for effect in SourceEffect)
BODY_CLASSES = extraction.BODY_CLASSES

ANOMALY_NO_READING = "circular_sin_lectura"
ANOMALY_SERVICE = "servicio"
ANOMALY_INVALID = "circular_salida_invalida"
ANOMALY_NO_DISPOSITION = "circular_sin_disposicion"
ANOMALY_UNKNOWN_QUOTE = "circular_cita_inexistente"
ANOMALY_QUOTE_NOT_FOUND = "circular_texto_no_encontrado"
ANOMALY_WIDE = "circular_cita_amplia"
ANOMALY_CANDIDATES_CUT = "circular_candidatas_recortadas"
ANOMALY_NO_FIT = "circular_tramo_no_entra"
# T-127: el respaldo contradijo el efecto de la extracción; un `suprime` sin frase explícita.
ANOMALY_EFFECT_CONTRADICTED = "circular_efecto_contradice_extraccion"
ANOMALY_SUPPRESSION_WITHOUT_PHRASE = "circular_supresion_sin_frase"
# T-137 (P3): un cambio de circular que no se pudo aplicar con certeza no se pierde en silencio:
# las filas que la circular nombra quedan "a revisión obligatoria".
ANOMALY_REVIEW_REQUIRED = "circular_revision_obligatoria"
ANOMALY_TITLE_NOT_CLARIFICATION = "circular_titulo_no_es_aclaracion"
REVIEW_UNRESOLVED = "cambio_sin_resolver"
REVIEW_INVALID = "salida_invalida"
REVIEW_SERVICE = "servicio"
REVIEW_RETRY_LOST = "reintento_pierde_cambios"
REVIEW_NO_FIT = "unidad_no_entra"

# Frases explícitas de supresión (T-127), sobre texto sin tildes ni mayúsculas: "se suprime(n)",
# "se elimina(n)", "se deroga(n)", "suprímase", "elimínase", "derógase", "queda(n) / déjase
# sin efecto", "no será exigible", "queda(n) derogado".
# T-129: también el infinitivo ("se dispone suprimir…") y el sustantivo con objeto de pliego
# ("la eliminación de la subcláusula…"); sin objeto de pliego ("eliminación de residuos") no
# cuenta.
_SUPPRESSION_OBJECT = (r"(?:sub)?(?:clausulas?|articulos?|puntos?|apartados?|numerales?|incisos?"
                       r"|renglon(?:es)?|anexos?|requisitos?|exigencias?|parrafos?|items?)")
_SUPPRESSION_PHRASE = re.compile(
    r"\b(?:se\s+(?:suprim\w+|elimin\w+|derog\w+)|suprimase|eliminase|derogase"
    r"|(?:queda\w*|dejase|dejan?|deja)\s+sin\s+efecto"
    r"|no\s+(?:sera|seran)\s+exigibles?|queda\w*\s+derogad\w+"
    r"|(?:dispone|resuelve|decide|ordena)\s+(?:suprimir|eliminar|derogar)"
    r"|(?:eliminacion|supresion|derogacion)\s+(?:total\s+|parcial\s+)?(?:de|del)\s+"
    rf"(?:(?:la|el|las|los|dicha|dicho)\s+)?{_SUPPRESSION_OBJECT})\b")

_CLASS_LABELS = {"formal": "formal", "economico": "económico"}

# Lo que un tramo nombra: cláusulas, artículos, puntos… y renglones.
_NUMBER = r"\d+(?:\.\d+)*"
_CLAUSE = re.compile(
    r"(?:cl[aá]usulas?|art[ií]culos?|puntos?|apartados?|numerales?|incisos?)\s*"
    r"(?:n[°º]\s*|n[úu]m(?:ero)?s?\.?\s*|nros?\.?\s*)?"
    rf"({_NUMBER}(?:\s*(?:,|;|y|e|o)\s*{_NUMBER})*)", re.IGNORECASE)
_ITEM = re.compile(
    r"rengl[oó]n(?:es)?\s*(?:n[°º]\s*|n[úu]m(?:ero)?s?\.?\s*|nros?\.?\s*)?"
    r"(\d+(?:\s*(?:,|;|y|e|a)\s*\d+)*)", re.IGNORECASE)
# Un anexo por su número ("Anexo VI", "ANEXO N° 2"), sobre texto sin tildes ni mayúsculas.
_ANNEX = re.compile(r"\banexos?\s*(?:n[°º]\s*|num(?:ero)?s?\.?\s*|nros?\.?\s*)?"
                    r"([ivxlc]+|\d+)\b")
# Lo que sigue a un anexo de una norma externa ("… de la Disposición N° 12/20"), sobre texto
# sin tildes ni mayúsculas.
_EXTERNAL_NORM = re.compile(
    r"\s*(?:,\s*)?(?:de|del)\s+(?:la\s+|el\s+|las\s+|los\s+)?"
    r"(?:disposicion(?:es)?|resolucion(?:es)?|decretos?|leyes|ley|circulares|circular|"
    r"notas?|acuerdos?)\b")
# Un número de cláusula con varios niveles al comienzo de una línea ("7.5.5 CONFLICTO…").
_LEADING_CLAUSE = re.compile(r"^[ \t]*(\d+(?:\.\d+)+)\.?[ \t]+\S", re.MULTILINE)
# El título entre comillas de un anexo o documento ("Anexo “FECHA DE VISITA”").
_QUOTED_TITLE = re.compile(r"[“\"]([^”\"\n]{6,80})[”\"]")
# Encabezado de un apartado de una circular sin cláusulas ("II. SE FIJAN NUEVAS FECHAS").
_HEADING = re.compile(r"^\s*[IVXLC]+(?:\.\s*-|\.|\s+-|\))\s+\S")
HEADING_LOOKBACK = 60       # tramos hacia atrás en que se busca el encabezado
ITEM_LOOKBACK = 12          # tramos hacia atrás en que se busca el encabezado de un renglón
# Un tramo que abre con un renglón ("Renglón N° 6", "En el renglón nro 6, ...") es el encabezado
# de lo que sigue hasta que otro renglón o un apartado nuevo lo reemplace (T-137).
_ITEM_HEADING = re.compile(
    r"^\W*(?:[\w.\-)°º]+\s+){0,4}?rengl[oó]n(?:es)?\b", re.IGNORECASE)
CONTEXT_PREVIOUS = 2        # tramos anteriores que se muestran como contexto
CONTEXT_CHARS = 400         # largo máximo de cada tramo de contexto
RANK_SEGMENT_CHARS = 1200   # largo máximo de la cláusula que se le da al reranker


def fold(text):
    """Minúsculas y sin tildes."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def has_suppression_phrase(text):
    """Si `text` dice de forma explícita que algo se suprime o queda sin efecto (T-127)."""
    return _SUPPRESSION_PHRASE.search(fold(text)) is not None


class InvalidOutput(ValueError):
    """Lo que el modelo devolvió no tiene la forma del esquema."""


# --- Documentos -------------------------------------------------------------------------------


@dataclass
class CircularDocument:
    """Una circular o respuesta con su lectura y sus tramos (`extraction.Unit`)."""

    document: object
    reading: object
    units: list

    def item_heading(self, unit):
        """T-137: el renglón bajo el que está el tramo: `(línea, {números})` del tramo anterior
        más cercano que abre con un renglón, sin cruzar el encabezado de un apartado nuevo;
        `("", set())` si no hay. Un cambio sin renglón propio es de ese renglón y no de otro
        con el mismo texto."""
        if unit not in self.units:
            return "", set()
        index = self.units.index(unit)
        for back in range(index - 1, max(index - 1 - ITEM_LOOKBACK, -1), -1):
            first = self.units[back].segment.text.strip().split("\n")[0]
            if _ITEM_HEADING.match(first) and len(first) <= CONTEXT_CHARS:
                items = named_in(first)[1]
                if items:
                    return first, items
            if _HEADING.match(first):
                break
        return "", set()

    def context(self, unit):
        """Lo que precede a un tramo suelto de la circular: `(encabezado, anteriores)`. Una
        circular sin cláusulas parte un apartado en una línea por tramo ("II. SE FIJAN
        NUEVAS FECHAS", "FECHA: …", "HORA: …"); sola, cada línea no dice de qué trata. El
        encabezado es el último tramo que empieza con un número romano ("II. …"), buscado
        hacia atrás; los anteriores son los `CONTEXT_PREVIOUS` tramos inmediatos. Una cláusula
        numerada se entiende sola: no lleva contexto."""
        if unit.segment.segment_type == SegmentType.CLAUSULA:
            return "", []
        index = self.units.index(unit)
        heading = None
        for back in range(index - 1, max(index - 1 - HEADING_LOOKBACK, -1), -1):
            first = self.units[back].segment.text.strip().split("\n")[0]
            if _HEADING.match(first) and len(first) <= CONTEXT_CHARS:
                heading = back
                break
        previous = [u.segment.text.strip()[:CONTEXT_CHARS]
                    for i, u in enumerate(self.units[max(index - CONTEXT_PREVIOUS, 0):index],
                                          start=max(index - CONTEXT_PREVIOUS, 0))
                    if i != heading]
        title = (self.units[heading].segment.text.strip().split("\n")[0]
                 if heading is not None else "")
        return title, previous


@dataclass
class Circulars:
    """Los documentos con fecha del procedimiento que se procesan, en orden, y los que no
    se pudieron (sin lectura)."""

    documents: list
    missing: list
    reading_of: dict

    def __bool__(self):
        return bool(self.documents or self.missing)


def load(run, first_position):
    """Las circulares y respuestas del procedimiento con su lectura vigente, por fecha y,
    a igual fecha, por orden de carga. Los tramos se numeran desde `first_position`."""
    documents = sorted(
        run.procedure.documents.filter(kind__in=[k.value for k in DATED_DOCUMENT_KINDS]),
        key=lambda d: (d.issued_on, d.loaded_at, d.pk))
    found, missing, reading_of = [], [], {}
    position = first_position
    for document in documents:
        reading = document.readings.order_by("-sequence").first()
        if reading is None:
            missing.append(document)
            continue
        units = []
        for segment in reading.segments.order_by("order"):
            segment.reading = reading
            position += 1
            units.append(extraction.Unit(segment, document.title, position))
            reading_of[segment.pk] = reading
        found.append(CircularDocument(document, reading, units))
    return Circulars(found, missing, reading_of)


# --- Lo que se le muestra -----------------------------------------------------------------------


@dataclass
class Target:
    """Un requisito de la versión y la cita (por orden) a la que corresponde."""

    number: int
    order: int
    category: str
    items: list
    scope: str = ""


@dataclass
class Candidate:
    """Una cita del pliego que una circular puede alcanzar. Varios requisitos pueden
    compartirla (`targets`). `current` es el texto vigente; `history` las circulares que
    lo cambiaron."""

    key: tuple
    unit: object
    start: int
    end: int
    text: str
    targets: list
    current: str = ""
    suppressed: bool = False
    history: list = field(default_factory=list)
    _folded: str = ""

    def __post_init__(self):
        self.current = self.text

    @property
    def segment(self):
        return self.unit.segment

    @property
    def folded(self):
        """La cláusula completa que contiene la cita, con su ruta, sin tildes ni mayúsculas."""
        if not self._folded:
            segment = self.segment
            self._folded = fold(f"{segment.path} {segment.key} {segment.text}")
        return self._folded

    def rank_text(self):
        """Lo que se le da al reranker: la ruta y la cláusula completa que contiene la cita
        (el nombre de un anexo suele estar en la cláusula y no en el recorte citado); si una
        circular ya la cambió, el texto vigente."""
        segment = self.segment
        if self.current != self.text:
            body = self.current
        elif len(segment.text) <= RANK_SEGMENT_CHARS:
            body = segment.text
        else:
            body = self.text
        return f"{segment.path or segment.label or segment.key}\n{body}"


def build_candidates(loaded, body, rows):
    """Las citas del pliego de los requisitos de la versión. `body` es lo que arma
    `run.propose` (`[(unidad, Found, texto)]`, formales y económicos en el orden del pliego)
    y `rows` las filas de `technical.build_rows`; los números son los de `_save`."""
    by_pk = {unit.segment.pk: unit for unit in loaded.units}
    found = {}

    def add(unit, start, end, text, target):
        key = (unit.segment.pk, start, end)
        if key not in found:
            found[key] = Candidate(key=key, unit=unit, start=start, end=end, text=text,
                                   targets=[])
        found[key].targets.append(target)

    for number, (unit, item, text) in enumerate(body, start=1):
        segment = unit.segment
        if item.flag == quotes.WIDE:
            start, end = quotes.whole(segment)
        else:
            start, end = quotes.absolute(segment, item.span)
        add(unit, start, end, text,
            Target(number, 1, item.category, list(segment.items)))
    number = len(body)
    for row in rows:
        number += 1
        items = [row.number] if row.number is not None else []
        for order, quote in enumerate(row.quotes, start=1):
            segment = quote.segment
            add(by_pk[segment.pk], segment.char_start, segment.char_end, segment.text,
                Target(number, order, RequirementClass.TECNICO.value, items, quote.scope))
    return sorted(found.values(), key=lambda c: (c.unit.position, c.start))


def _key_numbers(key):
    """Los números de cláusula de la clave de un tramo (`sec-i/1.1/v-2` → `{"1.1"}`)."""
    numbers = set()
    for part in key.split("/"):
        part = re.split(r"[#~]", part)[0]
        if re.fullmatch(_NUMBER, part):
            numbers.add(part)
    return numbers


def named_in(text):
    """Los números de cláusula y de renglón que `text` nombra: `(cláusulas, renglones)`."""
    clauses = set()
    for match in _CLAUSE.finditer(text):
        clauses.update(re.findall(_NUMBER, match.group(1)))
    items = set()
    for match in _ITEM.finditer(text):
        group = match.group(1)
        numbers = [int(n) for n in re.findall(r"\d+", group)]
        items.update(numbers)
        for first, second in re.findall(r"(\d+)\s*a\s*(\d+)", group, re.IGNORECASE):
            items.update(range(int(first), int(second) + 1))
    # Un "Debe decir" reproduce la cláusula con su número ("7.5.5 CONFLICTO…") sin decir
    # "cláusula". Solo cuenta desde la segunda línea: el número con que empieza el tramo es
    # el de la circular misma.
    _, _, rest = text.partition("\n")
    for match in _LEADING_CLAUSE.finditer(rest):
        clauses.add(match.group(1))
    return clauses, items


def candidate_items(candidate):
    """Los renglones a los que pertenece una cita del pliego."""
    return {i for t in candidate.targets for i in t.items}


def scope_items_of(document, unit, text):
    """Los renglones de una unidad (`circular_units.ChangeUnit`): los que nombra su texto o,
    si no nombra ninguno, los del encabezado que la precede (T-137)."""
    own = named_in(text)[1]
    if own:
        return set(own)
    if not hasattr(document, "item_heading"):
        return set()
    clauses = named_in(text)[0]
    if clauses:
        return set()
    return set(document.item_heading(unit.members[0])[1])


def named_annexes(text):
    """Los anexos que `text` nombra por su número, en minúsculas ("vi", "2"). "Anexo IV de la
    Disposición N° …" es el anexo de una norma externa, no uno del pliego (T-113)."""
    folded = fold(text)
    return {m.group(1) for m in _ANNEX.finditer(folded)
            if not _EXTERNAL_NORM.match(folded, m.end())}


def is_named(candidate, clauses, items):
    """Si el tramo nombra la cláusula o el renglón de la candidata."""
    if clauses and clauses & _key_numbers(candidate.segment.key):
        return True
    if items:
        for target in candidate.targets:
            if items & set(target.items):
                return True
    return False


def is_referred(candidate, annexes, haystack):
    """Si el tramo alude a la candidata sin decir su cláusula: nombra un anexo que su
    cláusula define o contiene ("Anexo VI"), o repite el título entre comillas de un anexo
    que la cita menciona ("Anexo “FECHA DE VISITA”"). `haystack` es el texto del tramo (y su
    contexto) sin tildes ni mayúsculas."""
    if annexes:
        segment = candidate.segment
        if any(f"anexo-{a}" in segment.key.lower() for a in annexes):
            return True
        if annexes & named_annexes(candidate.folded):
            return True
    if haystack:
        for title in _QUOTED_TITLE.findall(candidate.text):
            folded = fold(title).strip()
            if len(folded.split()) >= 2 and folded in haystack:
                return True
    return False


def _scope_line(candidate):
    lines = []
    for target in candidate.targets:
        if target.category == RequirementClass.TECNICO.value:
            if target.scope == "general":
                lines.append("Especificaciones técnicas comunes a todos los renglones")
            elif target.items:
                lines.append(f"Renglón {target.items[0]}, especificaciones técnicas")
            else:
                lines.append("Especificaciones técnicas del pliego")
        else:
            label = _CLASS_LABELS.get(target.category, target.category)
            lines.append(f"Requisito {label}")
    return "; ".join(dict.fromkeys(lines))


def render_candidate(alias, candidate):
    """Una cita del pliego tal como la ve el modelo."""
    segment = candidate.segment
    lines = [f"[{alias}]", _scope_line(candidate),
             f"Documento: {candidate.unit.document_title}",
             f"Ruta: {segment.path or segment.label or segment.key}"]
    if candidate.history:
        lines += ["Texto original:", candidate.text,
                  "Cambiado por: " + "; ".join(candidate.history)]
        if candidate.suppressed:
            lines.append("Una circular anterior la dejó sin efecto.")
        else:
            lines += ["Texto vigente:", candidate.current]
    else:
        lines += ["Texto:", candidate.text]
    lines.append(f"[/{alias}]")
    return "\n".join(lines)


def render_circular(circular, unit):
    document = circular.document
    segment = unit.segment
    kind = document.get_kind_display()
    return "\n".join([
        f"Documento: {document.title} ({kind}), del {document.issued_on.strftime('%d/%m/%Y')}",
        f"Ruta: {segment.path or segment.label or segment.key}",
        "Texto:", segment.text,
    ])


def build_schema(aliases):
    """Esquema de la salida. Las citas de `efectos` son solo entre las mostradas."""
    cites = {"type": "string", "enum": list(aliases)} if aliases else {"type": "string"}
    effects = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "cita": cites,
                "efecto": {"type": "string", "enum": list(EFFECTS)},
                "texto": {"type": "string", "minLength": 1},
            },
            "required": ["cita", "efecto", "texto"],
            "additionalProperties": False,
        },
    }
    if not aliases:
        effects["maxItems"] = 0
    return {
        "type": "object",
        "properties": {
            "efectos": effects,
            "nuevos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cita": {"type": "string", "minLength": 1},
                        "clase": {"type": "string", "enum": list(BODY_CLASSES)},
                    },
                    "required": ["cita", "clase"],
                    "additionalProperties": False,
                },
            },
            "sin_efecto": {"type": "string",
                           "enum": ["", *[reason.value for reason in DiscardReason]]},
        },
        "required": ["efectos", "nuevos", "sin_efecto"],
        "additionalProperties": False,
    }


def render_context(heading, previous):
    """El contexto de un tramo suelto (`CircularDocument.context`), o vacío."""
    lines = ([f"Apartado: {heading}"] if heading else [])
    lines += [f"Tramo anterior: {text}" for text in previous]
    return "\n".join(lines)


def build_messages(prompt, circular_block, candidate_blocks, context=""):
    parts = [
        "Citas del pliego:\n\n" + ("\n\n".join(candidate_blocks) if candidate_blocks
                                   else "ninguna"),
    ]
    if context:
        parts.append("Contexto de la circular (lo que precede al tramo en el mismo documento; "
                     "sirve para entender de qué trata, no se analiza):\n\n" + context)
    parts += [
        "Tramo de la circular:\n\n" + circular_block,
        "Devolvé un objeto JSON con efectos, nuevos y sin_efecto.",
    ]
    return [{"role": "system", "content": prompt},
            {"role": "user", "content": "\n\n".join(parts)}]


# --- Lo que devuelve ------------------------------------------------------------------------------


@dataclass
class Shaped:
    """La salida de un tramo con la forma comprobada: efectos `(alias, efecto, texto)`,
    nuevos `(texto, clase)` y el motivo de `sin_efecto`."""

    effects: list
    new: list
    discard: str

    @property
    def has_disposition(self):
        return bool(self.effects or self.new) != bool(self.discard)


def shape(raw):
    """Comprueba la forma de lo devuelto. Lanza `InvalidOutput`."""
    if not isinstance(raw, dict) or set(raw) != {"efectos", "nuevos", "sin_efecto"}:
        raise InvalidOutput("no es un objeto con efectos, nuevos y sin_efecto")
    effects, new = [], []
    if not isinstance(raw["efectos"], list) or not isinstance(raw["nuevos"], list):
        raise InvalidOutput("efectos y nuevos deben ser listas")
    for entry in raw["efectos"]:
        if (not isinstance(entry, dict) or set(entry) != {"cita", "efecto", "texto"}
                or not all(isinstance(entry[k], str) for k in entry)
                or entry["efecto"] not in EFFECTS):
            raise InvalidOutput("un efecto no es {cita, efecto, texto} con efecto válido")
        effects.append((entry["cita"].strip().strip("[]").strip(), entry["efecto"],
                        entry["texto"]))
    for entry in raw["nuevos"]:
        if (not isinstance(entry, dict) or set(entry) != {"cita", "clase"}
                or not all(isinstance(entry[k], str) for k in entry)
                or entry["clase"] not in BODY_CLASSES):
            raise InvalidOutput("un nuevo no es {cita, clase} con clase válida")
        new.append((entry["cita"], entry["clase"]))
    discard = raw["sin_efecto"]
    if not isinstance(discard, str) or (discard and discard not in DiscardReason.values):
        raise InvalidOutput(f"motivo de sin efecto desconocido: {discard!r}")
    return Shaped(effects, new, discard)


# --- Resultado --------------------------------------------------------------------------------------


@dataclass
class Verdict:
    """Qué pasó con un tramo de circular (con los nombres de `run.Decision`)."""

    outcome: str
    discard_reason: str = ""
    source: str = DispositionSource.REGLA.value
    step: object = None
    pending_reason: str = ""


@dataclass
class Source:
    """Lo que un tramo de circular hace a una cita del pliego: el texto de la circular, sus
    posiciones absolutas en la lectura de la circular y a qué requisitos alcanza."""

    effect: str
    candidate: Candidate
    segment: object
    start: int
    end: int
    text: str
    issued_on: object
    step: object
    wide: bool = False
    # Dónde está el texto que reemplaza cuando no es la cita alcanzada (T-113): un
    # `circular_units.Original` (tramo del anexo y posiciones), o `None`.
    original: object = None


@dataclass
class NewRequirement:
    """Un requisito que agrega una circular."""

    category: str
    segment: object
    start: int
    end: int
    text: str
    issued_on: object
    step: object
    wide: bool = False
    number: int = 0
    suggested: bool = False      # una reformulación probable: va como sugerencia


@dataclass
class Result:
    verdicts: dict
    sources: list
    new_requirements: list
    steps: list
    anomalies: list
    stats: dict

    def subjects(self, first_number, units):
        """Los requisitos nuevos como `consequences.Subject`, numerados desde
        `first_number`; `units` es `{pk del tramo: extraction.Unit}`."""
        from evaluon.tenders.proposal import consequences

        subjects = []
        for offset, new in enumerate(self.new_requirements):
            new.number = first_number + offset
            subjects.append(consequences.Subject(
                number=new.number, category=new.category, items=list(new.segment.items),
                text=new.text, unit=units[new.segment.pk], own=[]))
        return subjects


@dataclass
class _Outcome:
    shaped: Shaped | None = None
    step: object = None
    effects: list = field(default_factory=list)   # (alias, candidata, efecto, span, texto)
    new: list = field(default_factory=list)       # (clase, span | None, texto)
    unfound: int = 0

    @property
    def valid(self):
        return self.shaped is not None and self.shaped.has_disposition


# --- El procesador --------------------------------------------------------------------------------------


class Processor:
    """Hace los pedidos de la pasada de circulares de una propuesta (`MatrixRun`) y guarda
    cada uno en `tenders_run_step`."""

    pass_name = PassName.CIRCULARES

    def __init__(self, run):
        self.run = run
        self.prompt = extraction.load_prompt("circulares")
        self.steps = []
        self.anomalies = []
        self.stats = {"requests": 0, "segments": 0, "retried": 0, "effects": 0,
                      "new_requirements": 0, "no_effect": 0, "pending": 0,
                      "wide_quotes": 0, "dropped_effects": 0, "units": 0, "units_applied": 0,
                      "units_data": 0, "units_fallback": 0,
                      "units_extracted": 0, "extraction_requests": 0, "changes_applied": 0,
                      "changes_unstable": 0, "changes_unresolved": 0, "review_marks": 0}
        self._batch = 0

    # -- Pedidos -----------------------------------------------------------------------------

    def _record(self, unit, result, *, parsed, anomalies, retry_of, seconds):
        self._batch += 1
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch,
            segment_keys=[unit.segment.key], request=result["request"],
            raw_output=result["content"], parsed=parsed, anomalies=anomalies,
            retry_of=retry_of,
            timings={"seconds": round(seconds, 3),
                     "prompt_tokens": result["prompt_tokens"],
                     "completion_tokens": result["completion_tokens"]},
        )
        self.steps.append(step)
        return step

    def _space(self):
        return (settings.GENERATION_CONTEXT_TOKENS - settings.MATRIX_MAX_OUTPUT_TOKENS
                - settings.PROMPT_TEMPLATE_MARGIN_TOKENS
                - generation.count_tokens(self.prompt))

    def _choose(self, circular, unit, candidates, anomalies, heading="", rendered="",
                scope_items=()):
        """Las candidatas del tramo: las que nombra (por cláusula o renglón), las que alude
        (por anexo o por el título entre comillas de un anexo) y las mejores del reranker.
        Devuelve `({alias: candidata}, qué se tuvo en cuenta)`. Si no entran todas en el
        contexto, se descartan primero las del reranker, después las aludidas."""
        segment = unit.segment
        clauses, items = named_in(segment.text)
        annexes = named_annexes(segment.text)
        haystack = fold(f"{segment.text} {rendered}")
        scope = set(scope_items) if not clauses and not items else set()
        if scope:
            # T-137: el tramo está bajo el encabezado de un renglón y no nombra otro: es de ese
            # renglón; las citas de otros renglones no se muestran (texto idéntico en dos
            # renglones no se confunde).
            items = items | scope
            candidates = [c for c in candidates
                          if not candidate_items(c) or candidate_items(c) & scope]
        named = [c for c in candidates if is_named(c, clauses, items)]
        referred = [c for c in candidates
                    if c not in named and is_referred(c, annexes, haystack)]
        rest = [c for c in candidates if c not in named and c not in referred]
        limit = settings.MATRIX_CIRCULAR_CANDIDATES
        scores = {}
        if len(rest) > limit:
            query = f"{heading}\n{segment.text}" if heading else segment.text
            values = reranker.rerank(query, [c.rank_text() for c in rest])
            scores = {c.key: v for c, v in zip(rest, values)}
            rest = sorted(rest, key=lambda c: -scores[c.key])[:limit]
        ordered = named + referred + rest

        space = (self._space() - generation.count_tokens(render_circular(circular, unit))
                 - (generation.count_tokens(rendered) if rendered else 0))
        chosen, used = [], 0
        for candidate in ordered:
            size = generation.count_tokens(render_candidate("Q00", candidate))
            if used + size > space:
                anomalies.append({"type": ANOMALY_CANDIDATES_CUT,
                                  "segment": segment.pk, "key": segment.key})
                break
            chosen.append(candidate)
            used += size
        chosen.sort(key=lambda c: (c.unit.position, c.start))
        aliases = {f"Q{n}": c for n, c in enumerate(chosen, start=1)}
        context = {"nombradas": [c.segment.key for c in named],
                   "aludidas": [c.segment.key for c in referred],
                   "anexos": sorted(annexes), "encabezado": heading,
                   "clausulas": sorted(clauses), "renglones": sorted(items),
                   "puntajes": {f"{k[0]}:{k[1]}:{k[2]}": round(v, 4)
                                for k, v in scores.items()},
                   "mostradas": {a: {"segmento": c.segment.pk, "clave": c.segment.key,
                                     "inicio": c.start, "fin": c.end,
                                     "requisitos": [t.number for t in c.targets]}
                                 for a, c in aliases.items()}}
        return aliases, context

    def _ask(self, circular, unit, aliases, context, rendered="", retry_of=None):
        """Un pedido con el tramo y sus candidatas. Devuelve un `_Outcome`."""
        blocks = [render_candidate(a, c) for a, c in aliases.items()]
        messages = build_messages(self.prompt, render_circular(circular, unit), blocks,
                                  rendered)
        schema = build_schema(list(aliases))
        max_tokens = settings.MATRIX_MAX_OUTPUT_TOKENS
        started = time.monotonic()
        try:
            output = generation.generate_batch(messages, schema, max_tokens=max_tokens)
        except AIServiceError as error:
            self._record(
                unit, {"request": generation.build_request(messages, schema, max_tokens),
                       "content": "", "prompt_tokens": None, "completion_tokens": None},
                parsed=None, retry_of=retry_of, seconds=time.monotonic() - started,
                anomalies=[{"type": ANOMALY_SERVICE, "reason": error.reason,
                            "service": error.service, "message": str(error)}])
            raise
        seconds = time.monotonic() - started
        result = {"request": output.request, "content": output.content,
                  "prompt_tokens": output.prompt_tokens,
                  "completion_tokens": output.completion_tokens}
        self.stats["requests"] += 1

        anomalies, shaped = [], None
        try:
            data = json.loads(output.content)
            shaped = shape(data)
        except ValueError as error:   # `InvalidOutput` es un `ValueError`
            anomalies.append({"type": ANOMALY_INVALID, "segment": unit.segment.pk,
                              "key": unit.segment.key, "detail": str(error),
                              "finish_reason": output.finish_reason})
        outcome = _Outcome()
        parsed = {"segmento": unit.segment.pk, "valida": False, "candidatas": context,
                  "finish_reason": output.finish_reason}
        if shaped is not None:
            kept = []
            for alias, effect, text in shaped.effects:
                if alias in aliases:
                    kept.append((alias, effect, text))
                else:
                    self.stats["dropped_effects"] += 1
                    anomalies.append({"type": ANOMALY_UNKNOWN_QUOTE,
                                      "segment": unit.segment.pk, "alias": alias})
            shaped.effects = kept
            if not shaped.has_disposition:
                anomalies.append({"type": ANOMALY_NO_DISPOSITION,
                                  "segment": unit.segment.pk, "key": unit.segment.key})
                shaped = None
        if shaped is not None:
            outcome.shaped = shaped
            self._locate(unit, aliases, outcome, anomalies)
            parsed.update(
                valida=True,
                efectos=[{"cita": a, "efecto": e, "texto": t, "ubicado": span is not None}
                         for a, _, e, span, t in outcome.effects],
                nuevos=[{"clase": k, "texto": t, "ubicado": span is not None}
                        for k, span, t in outcome.new],
                sin_efecto=shaped.discard)
        outcome.step = self._record(unit, result, parsed=parsed, anomalies=anomalies,
                                    retry_of=retry_of, seconds=seconds)
        return outcome

    @staticmethod
    def _locate(unit, aliases, outcome, anomalies):
        """Ubica cada fragmento dentro del tramo; `None` si no está."""
        text = unit.segment.text
        seen = set()
        for alias, effect, fragment in outcome.shaped.effects:
            span = quotes.locate(text, fragment)
            if span is None:
                outcome.unfound += 1
                anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND,
                                  "segment": unit.segment.pk, "alias": alias})
            key = (alias, effect, span)
            if key in seen:
                continue
            seen.add(key)
            outcome.effects.append((alias, aliases[alias], effect, span, fragment))
        used = set()
        for fragment, kind in outcome.shaped.new:
            span = quotes.locate(text, fragment, used)
            if span is None:
                outcome.unfound += 1
                anomalies.append({"type": ANOMALY_QUOTE_NOT_FOUND,
                                  "segment": unit.segment.pk, "clase": kind})
            else:
                used.add(span)
            outcome.new.append((kind, span, fragment))

    # -- Un tramo ----------------------------------------------------------------------------

    def _tramo(self, circular, unit, candidates, decided=()):
        """Pide el tramo (y lo repite una vez si hace falta) y devuelve su `_Outcome`. Si la
        extracción ya decidió el efecto del cambio (`decided`), el pedido lo trae (T-127)."""
        anomalies = []
        heading, previous = circular.context(unit)
        rendered = render_context(heading, previous)
        item_line, scope = circular.item_heading(unit)
        if item_line:
            line = f"Renglón del encabezado: {item_line}"
            rendered = f"{rendered}\n{line}" if rendered else line
        if decided:
            line = ("La extracción de cambios ya leyó este tramo como: "
                    + ", ".join(decided) + ". El efecto no se contradice.")
            rendered = f"{rendered}\n{line}" if rendered else line
        aliases, context = self._choose(circular, unit, candidates, anomalies, heading,
                                        rendered, scope)
        self.anomalies.extend(anomalies)
        first = self._ask(circular, unit, aliases, context, rendered)
        if first.valid and not first.unfound:
            return first
        self.stats["retried"] += 1
        second = self._ask(circular, unit, aliases, context, rendered, retry_of=first.step)
        if second.valid and (not first.valid or second.unfound <= first.unfound):
            return second
        return first if first.valid else second


    def process(self, circulars, candidates, pliego=None):
        """Procesa los documentos de `circulars` por fecha sobre las `candidates`
        (`build_candidates`). Cada circular se parte en unidades de cambio
        (`circular_units`); las que se resuelven por clave se aplican sin modelo y las demás
        van al flujo de respaldo, tramo por tramo. Devuelve el `Result`. `pliego` son los
        tramos del pliego (`circular_units.Pliego`); si falta, se leen de la propuesta."""
        from evaluon.tenders.proposal import circular_units as units

        if pliego is None:
            pliego = units.load_pliego(self.run)
        verdicts, sources, new_requirements = {}, [], []
        extractor = None
        if settings.CIRCULAR_EXTRACTION_ENABLED:
            from evaluon.tenders.proposal import circular_changes

            extractor = circular_changes.Extractor(self)
        for document in circulars.documents:
            issued_on = document.document.issued_on
            label = (f"{document.document.title} ({issued_on.strftime('%d/%m/%Y')})")
            for change in units.partition(document.units):
                resolution = units.resolve(change, document, candidates, pliego)
                step = self._record_unit(change, resolution) if resolution.record else None
                before, losses = len(sources), []
                if resolution.outcome == units.OUTCOME_FALLBACK:
                    extracted = None
                    if extractor is not None and not self._is_rule_only(change):
                        extracted = extractor.run(document, change, candidates, pliego,
                                                  resolution)
                        losses = self._extraction_losses(extractor, extracted, document,
                                                         change, units)
                    if extracted is not None:
                        self._apply_extracted(document, change, extracted, candidates,
                                              issued_on, label, verdicts, sources,
                                              new_requirements)
                    else:
                        if resolution.reason in units.UNRESOLVED_REASONS:
                            # El cambio se reconoció pero no se aplicó por clave (T-137).
                            whole = self._unit_names(document, change, units)
                            losses.append((REVIEW_UNRESOLVED, whole, whole))
                        self.stats["units_fallback"] += 1
                        for unit in change.members:
                            self._fallback(document, unit, candidates, issued_on, label,
                                           verdicts, sources, new_requirements)
                else:
                    self._apply_unit(change, resolution, step, issued_on, label, verdicts,
                                     sources, new_requirements)
                self._review_losses(label, change, candidates, sources[before:], losses)
        # Un tramo puede llegar a la misma fuente por dos caminos (la extracción por clave y
        # el respaldo): una fuente igual no se guarda dos veces.
        seen = set()
        unique = []
        for source in sources:
            key = (source.candidate.key, source.effect, source.segment.pk, source.start,
                   source.end)
            if key not in seen:
                seen.add(key)
                unique.append(source)
        sources[:] = unique
        seen_new = set()
        unique_new = []
        for new in new_requirements:
            key = (new.category, new.segment.pk, new.start, new.end)
            if key not in seen_new:
                seen_new.add(key)
                unique_new.append(new)
        new_requirements[:] = unique_new
        step_anomalies = [a for step in self.steps for a in step.anomalies]
        self.stats["steps"] = len(self.steps)
        return Result(verdicts=verdicts, sources=sources, new_requirements=new_requirements,
                      steps=self.steps, anomalies=self.anomalies + step_anomalies,
                      stats=self.stats)

    def _is_rule_only(self, change):
        """Un tramo suelto de página o de título: la regla lo resuelve, no hay nada que
        extraer."""
        return (change.kind == "suelto" and len(change.members) == 1
                and self._rule(change.members[0].segment) is not None)

    # -- Red de seguridad (T-137, P3) ---------------------------------------------------------

    @staticmethod
    def _named_candidates(text, candidates, scope=()):
        """Las citas que el texto nombra: por cláusula, renglón o anexo, o por el título entre
        comillas de un anexo; con `scope`, también las del renglón del encabezado."""
        clauses, items = named_in(text)
        items = items | set(scope)
        annexes = named_annexes(text)
        haystack = fold(text)
        return [c for c in candidates
                if is_named(c, clauses, items) or is_referred(c, annexes, haystack)]

    @staticmethod
    def _unit_names(document, change, units):
        """El texto de la unidad con el encabezado del renglón que la precede, para saber qué
        filas nombra."""
        heading = document.item_heading(change.members[0])[0]
        text = units.unit_text(change, document)
        return f"{heading}\n{text}" if heading else text

    def _extraction_losses(self, extractor, extracted, document, change, units):
        """Lo que la extracción de una unidad no pudo aplicar con certeza, como
        `[(motivo, texto que nombra lo afectado, texto de la unidad)]`: una salida inválida o
        un servicio caído, un reintento que pudo perder cambios y cada cambio que quedó sin
        resolver (sin objetivo, sin coincidencia, ambiguo, no estable o sin cita)."""
        heading = document.item_heading(change.members[0])[0]
        whole = self._unit_names(document, change, units)
        losses = [(reason, whole, whole) for reason in extractor.loss]
        for found in (extracted.changes if extracted is not None else []):
            if not found.reason:
                continue
            word = {"renglon": "renglón", "clausula": "cláusula", "anexo": "anexo"}.get(
                found.target, "")
            names = " ".join(part for part in (
                f"{word} {found.reference}" if word and found.reference else "",
                found.old_text, found.new_text) if part)
            losses.append((REVIEW_UNRESOLVED, f"{names}\n{heading}" if heading else names,
                           whole))
        return losses

    def _review_losses(self, label, change, candidates, produced, losses):
        """Marca "a revisión obligatoria" las filas que la circular nombra y a las que la
        unidad no dejó ninguna fuente, por cada pérdida posible (P3). Una fila con una fuente
        de la unidad se da por atendida: un técnico tiene varias citas (el título del renglón,
        sus cláusulas) y marcarlas por separado sería ruido."""
        reached = {t.number for source in produced for t in source.candidate.targets}
        for reason, names, whole in losses:
            named = (self._named_candidates(names, candidates)
                     or self._named_candidates(whole, candidates))
            self._mark_review(label, change.keys, reason,
                              [c for c in named
                               if not reached & {t.number for t in c.targets}])

    def _mark_review(self, label, keys, reason, marked):
        """Deja la anomalía que la pantalla y la impresión muestran como "a revisión
        obligatoria" en cada fila alcanzada, con la circular y su fecha."""
        self.stats["review_marks"] += 1
        self.anomalies.append({
            "type": ANOMALY_REVIEW_REQUIRED, "review_required": True, "circular": label,
            "reason": reason, "tramos": list(keys),
            "requirements": sorted({t.number for c in marked for t in c.targets})})

    def _apply_extracted(self, document, change, extracted, candidates, issued_on, label,
                         verdicts, sources, new_requirements):
        """Aplica los cambios que el modelo extrajo y el código resolvió por clave (T-115).
        Las fuentes y los requisitos nuevos son los de la resolución; los tramos donde quedó
        un cambio sin resolver, no estable o sin cita verificable van al respaldo (el modelo
        elige entre las candidatas, solo en esos tramos); los de datos del trámite se
        descartan; los demás quedan con `requisitos`. El pedido de la unidad queda en
        `tenders_run_step` sin llamada al modelo, con lo resuelto."""
        resolution, step = extracted.resolution, extracted.step
        self._record_unit(change, resolution)
        self.stats["units_extracted"] += 1
        for effect in resolution.effects:
            sources.append(Source(effect.effect, effect.candidate, effect.segment, effect.start,
                                  effect.end, effect.text, issued_on, step, False,
                                  effect.original))
            self.stats["effects"] += 1
            self._note(effect.candidate, effect.effect, effect.text, label)
        for addition in resolution.additions:
            new_requirements.append(NewRequirement(
                addition.category, addition.segment, addition.start, addition.end,
                addition.text, issued_on, step, suggested=addition.suggested))
            self.stats["new_requirements"] += 1
        base = Verdict(DispositionOutcome.REQUISITOS.value, source=DispositionSource.MODELO.value,
                       step=step)
        data = Verdict(DispositionOutcome.DESCARTADO.value,
                       discard_reason=DiscardReason.DATO_PROCEDIMIENTO.value,
                       source=DispositionSource.MODELO.value, step=step)
        for member in change.members:
            if member in extracted.fallback_members:
                self._fallback(document, member, candidates, issued_on, label, verdicts,
                               sources, new_requirements,
                               decided=self._decided_effects(extracted, member))
                continue
            rule = self._rule(member.segment)
            if rule is not None:
                verdicts[member.segment.pk] = rule
            elif member in extracted.data_members:
                verdicts[member.segment.pk] = data
                self.stats["no_effect"] += 1
            else:
                verdicts[member.segment.pk] = base

    @staticmethod
    def _decided_effects(extracted, member):
        """Los efectos que la extracción decidió para los cambios sin resolver que tocan el
        tramo (`aclara`, `modifica` por `reemplaza`, `suprime`), en ese orden (T-127)."""
        by_type = {"aclara": SourceEffect.ACLARA.value, "reemplaza": SourceEffect.MODIFICA.value,
                   "suprime": SourceEffect.SUPRIME.value}
        segment = member.segment
        found = set()
        for change in extracted.changes:
            if not change.reason or change.type not in by_type:
                continue
            spans = change.spans()
            if spans and not any(s < segment.char_end and e > segment.char_start
                                 for s, e in spans):
                continue
            found.add(by_type[change.type])
        return tuple(e for e in EFFECTS if e in found)

    def _fallback(self, document, unit, candidates, issued_on, label, verdicts, sources,
                  new_requirements, decided=()):
        """El flujo de respaldo de un tramo: el modelo elige entre las candidatas. `decided`
        son los efectos que la extracción ya decidió para el tramo; el respaldo no los
        contradice (T-127)."""
        verdict = self._rule(unit.segment)
        if verdict is not None:
            verdicts[unit.segment.pk] = verdict
            return
        self.stats["segments"] += 1
        outcome = self._tramo(document, unit, candidates, decided)
        verdicts[unit.segment.pk] = self._verdict(outcome)
        if not outcome.valid:
            self.stats["pending"] += 1
            self.anomalies.append({"type": ANOMALY_NO_DISPOSITION,
                                   "segment": unit.segment.pk, "key": unit.segment.key,
                                   "detail": "sin disposición después del reintento"})
            heading, scope = document.item_heading(unit)
            names = f"{unit.segment.text}\n{heading}" if heading else unit.segment.text
            self._mark_review(
                label, [unit.segment.key], REVIEW_INVALID,
                self._named_candidates(names, candidates, scope))
            return
        if outcome.shaped.discard:
            self.stats["no_effect"] += 1
            return
        self._apply(unit, outcome, issued_on, label, sources, new_requirements, decided)

    def _record_unit(self, change, resolution):
        """El pedido de una unidad, sin llamada al modelo (P6): sus tramos, el tipo y el
        objetivo detectados, las citas resueltas, las fuentes y el motivo del respaldo."""
        self._batch += 1
        parsed = {
            "unidad": change.kind, "tramos": change.keys, "cambio": resolution.change,
            "objetivo": resolution.target, "resultado": resolution.outcome,
            "motivo": resolution.reason,
            "citas": [{"segmento": e.candidate.segment.pk, "clave": e.candidate.segment.key,
                       "inicio": e.candidate.start, "fin": e.candidate.end,
                       "requisitos": [t.number for t in e.candidate.targets]}
                      for e in resolution.effects],
            "fuentes": [{"efecto": e.effect, "segmento": e.segment.pk, "inicio": e.start,
                         "fin": e.end,
                         "original": ({"segmento": e.original.segment.pk,
                                       "inicio": e.original.start, "fin": e.original.end}
                                      if e.original else None)}
                        for e in resolution.effects],
            "nuevos": [{"clase": a.category, "segmento": a.segment.pk, "inicio": a.start,
                        "fin": a.end} for a in resolution.additions],
        }
        step = RunStep.objects.create(
            run=self.run, pass_name=self.pass_name, batch=self._batch,
            segment_keys=change.keys,
            request={"sin_modelo": True,
                     "unidad": {"tipo": change.kind, "tramos": change.keys}},
            raw_output="", parsed=parsed, anomalies=[], retry_of=None,
            timings={"seconds": 0.0, "prompt_tokens": None, "completion_tokens": None},
        )
        self.steps.append(step)
        self.stats["units"] += 1
        return step

    def _apply_unit(self, change, resolution, step, issued_on, label, verdicts, sources,
                    new_requirements):
        """Aplica una unidad resuelta por clave: la disposición de sus tramos (con origen
        `regla`) y las fuentes y requisitos nuevos. Los tramos de página y de título
        conservan la disposición de su regla."""
        from evaluon.tenders.proposal import circular_units as units

        if resolution.outcome == units.OUTCOME_DATA:
            base = Verdict(DispositionOutcome.DESCARTADO.value,
                           discard_reason=DiscardReason.DATO_PROCEDIMIENTO.value, step=step)
            self.stats["units_data"] += 1
        else:
            base = Verdict(DispositionOutcome.REQUISITOS.value, step=step)
            self.stats["units_applied"] += 1
        for member in change.members:
            verdict = self._rule(member.segment)
            verdicts[member.segment.pk] = verdict if verdict is not None else base
            if verdict is None and base.outcome == DispositionOutcome.DESCARTADO.value:
                self.stats["no_effect"] += 1
        for effect in resolution.effects:
            sources.append(Source(effect.effect, effect.candidate, effect.segment, effect.start,
                                  effect.end, effect.text, issued_on, step, False,
                                  effect.original))
            self.stats["effects"] += 1
            self._note(effect.candidate, effect.effect, effect.text, label)
        for addition in resolution.additions:
            new_requirements.append(NewRequirement(
                addition.category, addition.segment, addition.start, addition.end,
                addition.text, issued_on, step, suggested=addition.suggested))
            self.stats["new_requirements"] += 1

    @staticmethod
    def _note(candidate, effect, text, label):
        """Deja al día el texto vigente de la cita para las circulares que siguen."""
        if effect == SourceEffect.MODIFICA.value:
            candidate.current = text
            candidate.suppressed = False
            candidate.history.append(f"modificada por {label}")
        elif effect == SourceEffect.SUPRIME.value:
            candidate.suppressed = True
            candidate.history.append(f"suprimida por {label}")


    @staticmethod
    def _rule(segment):
        """La disposición de un tramo que no pasa por el modelo, o `None`. Un tramo
        `no_ubicado` sí pasa (T-098): una circular suele repetir una cláusula con otra
        numeración o bajo el título de una sección ("Donde dice… / Debe decir…") y la lectura
        no la ubica; sigue en "Pendiente de revisión" por el motivo de la lectura (REQ-028),
        pero su efecto no se pierde."""
        kind = segment.segment_type
        if kind == SegmentType.PAGINA:
            return Verdict(DispositionOutcome.PENDIENTE.value)
        if kind == SegmentType.TITULO:
            return Verdict(DispositionOutcome.DESCARTADO.value, "titulo")
        return None

    @staticmethod
    def _verdict(outcome):
        base = {"source": DispositionSource.MODELO.value, "step": outcome.step}
        if not outcome.valid:
            return Verdict(DispositionOutcome.PENDIENTE.value,
                           pending_reason=PendingReason.SIN_DISPOSICION.value, **base)
        if outcome.shaped.discard:
            return Verdict(DispositionOutcome.DESCARTADO.value,
                           discard_reason=outcome.shaped.discard, **base)
        return Verdict(DispositionOutcome.REQUISITOS.value, **base)

    def _guard_effect(self, unit, outcome, alias, effect, text, wide, decided, candidate,
                      label):
        """Dos frenos al efecto que devuelve el respaldo (T-127, P3). (a) No contradice el
        efecto que decidió la extracción: se conserva el de la extracción. (b) Un `suprime`
        es firme solo si el texto citado de la circular tiene una frase explícita de
        supresión; si no, queda como `aclara` (no quita la fila ni suprime la cita) y como
        revisión obligatoria. Cada cambio deja su anomalía con el efecto original, el
        devuelto y el resultado (P6)."""
        segment = unit.segment
        returned = effect
        if decided and effect not in decided:
            effect = SourceEffect.ACLARA.value if SourceEffect.ACLARA.value in decided \
                else decided[0]
            self.anomalies.append({
                "type": ANOMALY_EFFECT_CONTRADICTED, "segment": segment.pk,
                "key": segment.key, "alias": alias, "decided": list(decided),
                "returned": returned, "result": effect, "step": outcome.step.pk})
        if effect == SourceEffect.SUPRIME.value and (wide or not has_suppression_phrase(text)):
            self.anomalies.append({
                "type": ANOMALY_SUPPRESSION_WITHOUT_PHRASE, "segment": segment.pk,
                "key": segment.key, "alias": alias, "decided": list(decided),
                "returned": returned, "result": SourceEffect.ACLARA.value, "text": text,
                "review_required": True, "step": outcome.step.pk,
                "circular": label, "requirements": [t.number for t in candidate.targets]})
            effect = SourceEffect.ACLARA.value
        return effect

    def _apply(self, unit, outcome, issued_on, label, sources, new_requirements, decided=()):
        """Pasa los efectos del tramo a las fuentes y a los requisitos nuevos, y deja el
        texto vigente de cada cita al día para las circulares que siguen."""
        from evaluon.tenders.proposal import circular_units as units

        segment = unit.segment

        def place(span, fragment):
            if span is None:
                self.stats["wide_quotes"] += 1
                self.anomalies.append({"type": ANOMALY_WIDE, "segment": segment.pk,
                                       "key": segment.key})
                start, end = quotes.whole(segment)
                return start, end, segment.text, True
            start, end = quotes.absolute(segment, span)
            return start, end, segment.text[span[0]:span[1]], False

        for alias, candidate, effect, span, fragment in outcome.effects:
            start, end, text, wide = place(span, fragment)
            effect = self._guard_effect(unit, outcome, alias, effect, text, wide, decided,
                                       candidate, label)
            if effect == SourceEffect.ACLARA.value and units.is_title_text(text):
                # T-137: el título de una carátula no precisa ninguna condición.
                self.anomalies.append({
                    "type": ANOMALY_TITLE_NOT_CLARIFICATION, "segment": segment.pk,
                    "key": segment.key, "alias": alias, "step": outcome.step.pk})
                continue
            sources.append(Source(effect, candidate, segment, start, end, text, issued_on,
                                  outcome.step, wide))
            self.stats["effects"] += 1
            self._note(candidate, effect, text, label)
        for kind, span, fragment in outcome.new:
            start, end, text, wide = place(span, fragment)
            new_requirements.append(NewRequirement(kind, segment, start, end, text,
                                                   issued_on, outcome.step, wide))
            self.stats["new_requirements"] += 1


def apply_to_subjects(subjects, candidates):
    """Pone en los `consequences.Subject` el texto vigente de las citas que una circular
    modificó, con el original: la consecuencia se evalúa sobre lo que se exige hoy."""
    by_number = {s.number: s for s in subjects}
    for candidate in candidates:
        if candidate.suppressed or candidate.current == candidate.text:
            continue
        for target in candidate.targets:
            subject = by_number.get(target.number)
            if subject is not None:
                subject.changes.append((candidate.text, candidate.current))
                if subject.category != RequirementClass.TECNICO.value:
                    subject.text = candidate.current


def circular_record(circulars):
    """Los documentos usados, para dejarlos en las cuentas y en el hecho de auditoría."""
    return [{"document": d.document.pk, "title": d.document.title,
             "kind": d.document.kind, "issued_on": d.document.issued_on.isoformat(),
             "reading": d.reading.pk, "sha256": d.document.file_sha256}
            for d in circulars.documents]


def missing_record(circulars):
    return [{"document": d.pk, "title": d.title} for d in circulars.missing]

