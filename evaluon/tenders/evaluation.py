"""Medición de la propuesta de matriz contra una lista de requisitos esperada
(REQ-024, REQ-025; plan 003, "Medición"; ADR-0014, punto 7).

Qué hace:

- `load_expected`: lee y valida la lista esperada (`matriz-esperada.yaml`). Una lista sin
  visto bueno no se mide (`ExpectedNotApproved`).
- `verify_expected`: comprueba la lista contra los documentos cargados, sin usar el modelo:
  la huella de cada archivo, que cada ancla esté en su tramo (en el texto canónico de la
  lectura) y que cada tramo técnico exista. Lo que falla en el pliego bloquea; lo que falla
  en una circular se informa y no bloquea (sus claves son tentativas, y las circulares se
  usan recién con T-083).
- `measure`: corre la propuesta del proceso único con el canal `eval`, la mide,
  descarta la versión que creó y guarda la carpeta de la corrida (`parametros.json`,
  `resultados.jsonl`, `resumen.md` y `resumen-publico.md`).

Cómo se cuenta (ver el plan):

- Formales y económicos: emparejamiento uno a uno por cita, no por redacción. Un propuesto
  empareja con un esperado si están en la misma lectura y la cita cubre al menos la mitad
  de los caracteres del ancla; los pares se asignan de mayor a menor superposición.
- Técnicos: una fila propuesta por renglón; se informa, por renglón, qué tramos esperados
  (propios, generales y de anexos) no están entre sus citas. No bloquea.
- Un esperado formal o económico sin pareja cuyo ancla cae dentro de un tramo citado por
  una fila técnica cuenta como encontrado con clase equivocada.
- Faltante con causa: `agrupado`, `tramo_descartado`, `tramo_con_requisitos_sin_este`,
  `tramo_tecnico`, `sin_disposicion` y, en técnicos, `renglon_sin_fila`.
- A revisión obligatoria: un esperado sin pareja en un tramo pendiente (`tramo_pendiente`)
  no es faltante; suma a los encontrados y se informa aparte (decisión del 2026-10-04).
- Sobrante: fila firme (propuesta o confirmada; sin las descartadas por el sistema ni las
  sugerencias) sin pareja. Tope: hasta `MATRIX_SOBRANTES_LIMIT` de las filas firmes y el 100 %
  de encontrados (T-103; REQ-024, REQ-033). Una fila empareja por cualquiera de sus citas; un
  esperado en una cita `repetida` de una fila ya emparejada es "unificado"; un esperado
  cuya cita está en una descartada es faltante `descartado_por_el_sistema`.
- Sugerencias de condición (T-111; REQ-035, REQ-036): no entran en el tope. Orden de
  emparejamiento: firmes, sugerencias, descartadas. Un esperado sin pareja firme con pareja en
  una sugerencia es "a revisión obligatoria" con causa `sugerencia`: suma a los encontrados y se
  informa aparte. El informe de sugerencias da cantidad, motivos, tramos, cuántas eran
  esperadas, cuántas tienen respaldo normativo y cuántas de esas eran esperadas.

Campos de las listas reales que se leen (aviso del Coordinador, 2026-10-03):

- `tramo: "*"` (en `tramos_anexos` y en las claves de tramos): empareja con cualquier tramo
  del documento; `a/b/*`, con cualquier tramo bajo `a/b`.
- Bloques `circulares:` en las filas afectadas, y `origen: circular` en las filas que agrega
  una circular. Una fila con `origen: circular` cita un documento que la propuesta todavía no
  usa (T-083): se informa aparte (`circular_sin_medir`) y no entra en la proporción de
  encontrados. Las filas con bloque `circulares:` se miden por su ancla del pliego.
- `rol` (en `documentos`) y `nota` (en filas): informativos, se ignoran.

Decisiones fuera del plan (informadas en la entrega de T-077):

- La página de una cita se toma del tramo que la contiene: la cita cuenta como bien ubicada
  si cae dentro del tramo y el tramo tiene página.
- Las citas amplias (`cita_amplia`) se cuentan aparte y no entran en el denominador de la cita
  literal.
- Si el procedimiento ya tiene un borrador abierto, la medición se rechaza: la base admite a
  lo sumo uno por procedimiento.
"""

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.queries.evaluation import proportion_text  # usa el Wilson de la 001
from evaluon.tenders import models as m
from evaluon.tenders.proposal import quotes
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.services import matrix as matrix_service

OPERATION = "evaluon.tenders.evaluation.measure"

FORMAL = m.RequirementClass.FORMAL.value
ECONOMIC = m.RequirementClass.ECONOMICO.value
TECHNICAL = m.RequirementClass.TECNICO.value
CLASSES = (FORMAL, ECONOMIC, TECHNICAL)

ORIGIN_CIRCULAR = "circular"
WILDCARD = "*"
REQUIRED_OVERLAP = 0.5
FIRM_STATES = (m.RequirementState.PROPUESTO.value, m.RequirementState.CONFIRMADO.value)
SUGGESTION = m.RequirementState.SUGERIDO.value
SAMPLE_FILE = "muestra-descartadas.md"
SUGGESTIONS_SAMPLE_FILE = "muestra-sugerencias.md"
EXTRAPOLATED_PAGES = 50

# Causas de un faltante.
GROUPED = "agrupado"
DISCARDED = "tramo_descartado"
DISCARDED_BY_SYSTEM = "descartado_por_el_sistema"
PENDING = "tramo_pendiente"
MANDATORY_REVIEW = "a_revision_obligatoria"
SUGGESTION_CAUSE = "sugerencia"
SEGMENT_WITH_OTHERS = "tramo_con_requisitos_sin_este"
SEGMENT_TECHNICAL = "tramo_tecnico"
NO_DISPOSITION = "sin_disposicion"
ITEM_WITHOUT_ROW = "renglon_sin_fila"
CIRCULAR_UNMEASURED = "circular_sin_medir"
SCOPE_CIRCULARS = "circulares"
CIRCULAR_EFFECTS = ("modifica", "suprime", "aclara", "precisa", "agrega")
# Los efectos de la lista que la base guarda con otro nombre: `precisa` (una respuesta que
# precisa un requisito) se guarda como `aclara`.
SOURCE_EFFECT = {"precisa": "aclara"}


class ExpectedError(ValueError):
    """La lista esperada no se puede leer o está mal formada."""


class ExpectedNotApproved(ExpectedError):
    """La lista no tiene visto bueno: no se usa."""


class MeasurementRefused(ValueError):
    """La medición no se puede hacer (por ejemplo, un borrador abierto)."""


# --- Lectura de la lista esperada ---------------------------------------------------------


@dataclass(frozen=True)
class Ref:
    """Un tramo de un documento, o un conjunto de tramos si la clave termina en `*`."""

    document: str
    key: str

    def matches(self, document, key):
        if document != self.document:
            return False
        if self.key == WILDCARD:
            return True
        if self.key.endswith("/" + WILDCARD):
            prefix = self.key[:-2]
            return key == prefix or key.startswith(prefix + "/")
        return key == self.key

    @property
    def wildcard(self):
        return self.key == WILDCARD or self.key.endswith("/" + WILDCARD)


@dataclass
class CircularBlock:
    """Un bloque `circulares:` de una fila esperada (REQ-031, T-117): qué hizo una circular con
    la fila. Se lee tal como lo escriben las listas reales: `documento`, `fecha`, `efecto`,
    `tramo`, `pagina`, `ancla`, `texto_original` (texto o `{documento, pagina, cita}`),
    `texto_vigente` o `texto`; también se aceptan los nombres del plan (`ancla_original`,
    `ancla_vigente`)."""

    document: str
    date: str
    effect: str
    key: str = ""
    anchor: str = ""
    original_document: str = ""
    original_anchor: str = ""
    current_anchor: str = ""

    @property
    def source_effect(self):
        return SOURCE_EFFECT.get(self.effect, self.effect)

    @property
    def adds(self):
        return self.effect == "agrega"


def _block(entry, where):
    if not isinstance(entry, dict):
        raise ExpectedError(f"{where}: un bloque `circulares` no tiene la forma esperada")
    document = _text(entry, "documento", where + ", circulares")
    date = str(entry.get("fecha") or "").strip()
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ExpectedError(f"{where}, circulares: `fecha` debe ser AAAA-MM-DD") from None
    effect = str(entry.get("efecto") or "").strip()
    if effect not in CIRCULAR_EFFECTS:
        raise ExpectedError(f"{where}, circulares: `efecto` debe ser uno de "
                            f"{', '.join(CIRCULAR_EFFECTS)}")
    original = entry.get("texto_original")
    original_document = ""
    if isinstance(original, dict):
        original_document = str(original.get("documento") or "").strip()
        original = original.get("cita")
    original = str(entry.get("ancla_original") or original or "").strip()
    current = ""
    if effect != "suprime":
        current = str(entry.get("ancla_vigente") or entry.get("texto_vigente")
                      or entry.get("texto") or "").strip()
    return CircularBlock(
        document=document, date=date, effect=effect, key=str(entry.get("tramo") or "").strip(),
        anchor=str(entry.get("ancla") or "").strip(), original_document=original_document,
        original_anchor=original, current_anchor=current)


@dataclass
class Item:
    """Un requisito esperado."""

    id: str
    clase: str
    document: str
    key: str = ""
    page: int | None = None
    anchor: str = ""
    occurrence: int = 1
    renglon: int | None = None
    refs: list = field(default_factory=list)
    annexes: list = field(default_factory=list)
    origin: str = ""
    circulars: list = field(default_factory=list)
    blocks: list = field(default_factory=list)  # `CircularBlock` ya validados (T-117)
    consequence: str = ""
    in_report: str = ""

    @property
    def technical(self):
        return self.clase == TECHNICAL

    @property
    def from_circular(self):
        return self.origin == ORIGIN_CIRCULAR


@dataclass
class Expected:
    case: str
    path: Path
    sha256: str
    documents: list
    approval: str
    use: str
    general: list
    annexes: list
    items: list
    scope: str = ""

    @property
    def circulars_only(self):
        return self.scope == SCOPE_CIRCULARS

    @property
    def default_document(self):
        return self.documents[0]["archivo"]


def _text(data, name, where):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExpectedError(f"{where}: falta `{name}`")
    return value.strip()


def _refs(entries, default_document, where):
    refs = []
    for entry in entries or []:
        if isinstance(entry, str):
            refs.append(Ref(default_document, entry.strip()))
        elif isinstance(entry, dict) and entry.get("tramo"):
            refs.append(Ref(str(entry.get("documento") or default_document),
                            str(entry["tramo"]).strip()))
        else:
            raise ExpectedError(f"{where}: tramo mal formado")
    return refs


def load_expected(path, *, require_approval=True):
    """Lee y valida la lista. Lanza `ExpectedError`; sin visto bueno y con
    `require_approval`, `ExpectedNotApproved`."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
    except OSError as error:
        raise ExpectedError(f"no se puede leer la lista: {error.__class__.__name__}")
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(f"la lista no se puede leer como YAML ({error.__class__.__name__})")
    if not isinstance(data, dict):
        raise ExpectedError("la lista no tiene la forma esperada")
    documents = data.get("documentos")
    if not isinstance(documents, list) or not documents:
        raise ExpectedError("faltan los `documentos` de la lista")
    for entry in documents:
        if not isinstance(entry, dict) or not entry.get("archivo"):
            raise ExpectedError("cada documento lleva `archivo` y `sha256`")
        if not isinstance(entry.get("sha256"), str) or not entry["sha256"].strip():
            raise ExpectedError("el `sha256` de cada documento va entre comillas")
    approval = str(data.get("visto_bueno") or "").strip()
    if require_approval and not approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    entries = data.get("requisitos")
    if not isinstance(entries, list) or not entries:
        raise ExpectedError("la lista no tiene `requisitos`")

    default = documents[0]["archivo"]
    items, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ExpectedError("un requisito no tiene la forma esperada")
        ident = _text(entry, "id", "requisito")
        where = f"requisito {ident}"
        if ident in seen:
            raise ExpectedError(f"{where}: id repetido")
        seen.add(ident)
        clase = entry.get("clase")
        if clase not in CLASSES:
            raise ExpectedError(f"{where}: `clase` debe ser formal, economico o tecnico")
        document = str(entry.get("documento") or default)
        item = Item(
            id=ident, clase=clase, document=document,
            origin=str(entry.get("origen") or ""),
            circulars=list(entry.get("circulares") or []),
            consequence=str(entry.get("consecuencia") or ""),
            in_report=str(entry.get("en_dictamen") or ""),
        )
        if clase == TECHNICAL:
            if not isinstance(entry.get("renglon"), int):
                raise ExpectedError(f"{where}: un técnico lleva `renglon` numérico")
            item.renglon = entry["renglon"]
            item.refs = _refs(entry.get("tramos"), document, where)
            item.annexes = _refs(entry.get("tramos_anexos"), document, where)
        else:
            item.key = _text(entry, "tramo", where)
            item.anchor = _text(entry, "ancla", where)
            occurrence = entry.get("ocurrencia", 1)
            if not isinstance(occurrence, int) or occurrence < 1:
                raise ExpectedError(f"{where}: `ocurrencia` debe ser un entero desde 1")
            item.occurrence = occurrence
            page = entry.get("pagina")
            item.page = page if isinstance(page, int) else None
        item.blocks = [_block(c, where) for c in item.circulars]
        items.append(item)

    scope = str(data.get("alcance") or "").strip()
    if scope not in ("", SCOPE_CIRCULARS):
        raise ExpectedError("`alcance` solo puede ser `circulares`")
    return Expected(
        case=str(data.get("caso") or ""), path=path,
        sha256=hashlib.sha256(raw).hexdigest(), documents=documents, approval=approval,
        use=str(data.get("uso") or ""),
        general=_refs(data.get("tecnico_general"), default, "tecnico_general"),
        annexes=_refs(data.get("tramos_anexos"), default, "tramos_anexos"),
        items=items, scope=scope,
    )


# --- Comprobación de la lista contra la lectura --------------------------------------------


@dataclass
class Located:
    """Dónde cae el ancla de un esperado formal o económico."""

    item: Item
    reading: object = None
    segment: object = None
    span: tuple | None = None


@dataclass
class Verification:
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)
    located: dict = field(default_factory=dict)
    readings: dict = field(default_factory=dict)  # archivo -> lectura
    segments: dict = field(default_factory=dict)  # archivo -> {clave: tramo}

    @property
    def ok(self):
        return not self.problems


def latest_readings(procedure):
    """La lectura más reciente de cada documento del procedimiento, por nombre de
    archivo."""
    readings = {}
    for document in procedure.documents.order_by("loaded_at", "id"):
        reading = document.readings.order_by("-sequence").first()
        if reading is not None:
            readings[document.file_name] = reading
    return readings


def verify_expected(expected, procedure, readings=None):
    """Comprueba huellas, anclas y tramos de `expected` contra `procedure`. `readings` es
    `{archivo: lectura}`; por omisión, la más reciente de cada documento. No usa el
    modelo."""
    result = Verification()
    documents = {d.file_name: d for d in procedure.documents.all()}
    if readings is None:
        readings = latest_readings(procedure)
    else:
        for name, reading in latest_readings(procedure).items():
            readings.setdefault(name, reading)
    result.readings = readings
    for name, reading in readings.items():
        result.segments[name] = {s.key: s for s in reading.segments.order_by("order")}

    if not expected.approval:
        result.problems.append("la lista no tiene visto bueno")
    listed = {d["archivo"]: d for d in expected.documents}
    for name, entry in listed.items():
        document = documents.get(name)
        if document is None:
            continue
        if document.file_sha256 != str(entry["sha256"]).lower():
            result.problems.append(f"la huella del documento {_doc_label(expected, name)} "
                                   "no coincide con la de la lista")

    # Los documentos usados por filas del pliego tienen que estar cargados.
    needed = {i.document for i in expected.items if not i.from_circular}
    for name in sorted(needed):
        if name not in readings:
            result.problems.append(f"el documento {_doc_label(expected, name)} no está "
                                   "cargado o no tiene lectura")
    for name in sorted(set(listed) - needed - set(readings)):
        result.notes.append(f"el documento {_doc_label(expected, name)} no está cargado "
                            "(se usa en circulares)")

    seen_items = Counter(i.renglon for i in expected.items if i.technical)
    for number, times in sorted(seen_items.items()):
        if times > 1:
            ids = ", ".join(i.id for i in expected.items if i.technical and i.renglon == number)
            result.problems.append(f"la lista trae {times} entradas técnicas del renglón "
                                   f"{number} ({ids}): la regla es una fila por renglón")
    for item in expected.items:
        if item.technical:
            _verify_technical(expected, item, result)
        else:
            _verify_anchor(item, result)
        for block in item.blocks:
            _verify_circular(expected, item, block, result, documents)
    for ref in expected.general + expected.annexes:
        _verify_ref(ref, "tramos generales", result, blocking=True)
    # Dos esperados con el mismo ancla normalizado se unificarían (REQ-033).
    same = {}
    for item in expected.items:
        if not item.technical and item.anchor:
            same.setdefault(" ".join(item.anchor.casefold().split()), []).append(item.id)
    for ids in same.values():
        if len(ids) > 1:
            result.notes.append(f"{' y '.join(ids)}: tienen el mismo ancla normalizado "
                                "(la unificación los juntaría)")
    return result


def _doc_label(expected, name):
    for index, entry in enumerate(expected.documents, start=1):
        if entry["archivo"] == name:
            return f"D{index}"
    return "D?"


def _blocking(item):
    return not item.from_circular


def _report(result, item, text):
    (result.problems if _blocking(item) else result.notes).append(text)


def find_anchor(segment, anchor, occurrence):
    """Posiciones absolutas `(inicio, fin)` de la `occurrence`-ésima aparición de `anchor`
    en el tramo, o `None`."""
    used, span = [], None
    for _ in range(occurrence):
        span = quotes.locate(segment.text, anchor, used=used)
        if span is None:
            return None
        used.append(span)
    return quotes.absolute(segment, span)


def _verify_anchor(item, result):
    prefix = "circular_" if item.from_circular else ""
    result.counts[prefix + "anchors"] += 1
    segments = result.segments.get(item.document)
    if segments is None:
        _report(result, item, f"{item.id}: documento sin lectura")
        return
    segment = segments.get(item.key)
    if segment is None:
        _report(result, item, f"{item.id}: el tramo {item.key} no existe en la lectura")
        return
    span = find_anchor(segment, item.anchor, item.occurrence)
    if span is None:
        _report(result, item, f"{item.id}: el ancla no está en el tramo {item.key}")
        return
    result.counts[prefix + "anchors_ok"] += 1
    if (item.page is not None and segment.page_start is not None
            and not segment.page_start <= item.page <= (segment.page_end or segment.page_start)):
        result.counts["page_differs"] += 1
    result.located[item.id] = Located(item, result.readings[item.document], segment, span)


def _verify_ref(ref, label, result, blocking=True, item_id=""):
    result.counts["tramos"] += 1
    segments = result.segments.get(ref.document)
    found = segments is not None and any(ref.matches(ref.document, key) for key in segments)
    if found:
        result.counts["tramos_ok"] += 1
        return True
    text = f"{item_id + ': ' if item_id else ''}el tramo {ref.key} ({label}) no existe"
    (result.problems if blocking else result.notes).append(text)
    return False


def _verify_technical(expected, item, result):
    blocking = _blocking(item)
    for ref in item.refs + item.annexes:
        _verify_ref(ref, f"renglón {item.renglon}", result, blocking, item.id)


def _verify_circular(expected, item, block, result, documents):
    """Comprueba un bloque `circulares` contra la lectura (T-117). Un documento que no figura
    en la lista, o que figura y no está cargado sin que la lista lo declare (`cargado: false`),
    bloquea; el declarado sin cargar solo se informa. Si está cargada, bloquea
    que el tramo o el ancla no existan, que la fecha no sea la del documento, que el texto
    original no esté en el documento que lo contiene o que el texto vigente no esté en la
    circular."""
    name = block.document
    label = f"{item.id}: la circular {_doc_label(expected, name)}"
    result.counts["circular_anchors"] += 1
    listed = {d["archivo"]: d for d in expected.documents}
    if name not in listed:
        result.problems.append(f"{item.id}: el documento del bloque de circular no figura en "
                               "los documentos de la lista (¿nombre mal escrito?)")
        return
    segments = result.segments.get(name)
    if segments is None:
        # Solo se informa si la lista declara que esa circular no se carga (`cargado: false`).
        text = f"{label} no está cargada"
        if listed[name].get("cargado") is False:
            result.notes.append(text)
        else:
            result.problems.append(text + " (si es a propósito, la lista lo declara con "
                                   "`cargado: false`)")
        return
    problems = []
    document = documents.get(name)
    if (document is not None and document.issued_on is not None
            and document.issued_on.isoformat() != block.date):
        problems.append(f"{label}: la fecha de la lista no es la del documento cargado")
    segment = segments.get(block.key) if block.key else None
    if block.key and segment is None:
        problems.append(f"{label}: el tramo {block.key} no existe")
    elif segment is not None and block.anchor and quotes.locate(
            segment.text, block.anchor) is None:
        problems.append(f"{label}: el ancla no está en {block.key}")
    reading = result.readings[name]
    if block.current_anchor and quotes.locate(
            reading.canonical_text, block.current_anchor) is None:
        problems.append(f"{label}: el texto vigente no está en la circular")
    original_name = block.original_document or item.document
    original_reading = result.readings.get(original_name)
    if block.original_anchor and original_reading is not None and quotes.locate(
            original_reading.canonical_text, block.original_anchor) is None:
        problems.append(f"{label}: el texto original no está en "
                        f"{_doc_label(expected, original_name)}")
    if problems:
        result.problems.extend(problems)
    else:
        result.counts["circular_anchors_ok"] += 1


def verification_lines(verification):
    """Las cuentas de la comprobación, sin texto del pliego."""
    c = verification.counts
    lines = [
        f"Anclas encontradas: {c['anchors_ok']} de {c['anchors']}",
        f"Tramos técnicos que existen: {c['tramos_ok']} de {c['tramos']}",
        f"Páginas distintas de la lista (informativo): {c['page_differs']}",
    ]
    if c["circular_anchors"]:
        lines.append(f"Bloques de circulares comprobados (los de una circular no cargada "
                     f"solo se informan): "
                     f"{c['circular_anchors_ok']} de {c['circular_anchors']}")
    lines += [f"BLOQUEA: {p}" for p in verification.problems]
    lines += [f"Aviso: {n}" for n in verification.notes]
    lines.append("La lista se puede usar." if verification.ok
                 else "La lista no se puede usar: corregir lo que bloquea.")
    return lines


# --- Medición de una propuesta -------------------------------------------------------------


def _percent(value):
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def ratio(ok, total):
    return {"ok": ok, "total": total, "rate": ok / total if total else None}


def _overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _quote_state(reading, segment, quote):
    """Si la cita es igual al recorte del texto canónico de `reading` (la lectura de su propio
    tramo, no la de la primera cita de la fila), cae en su tramo y el tramo tiene
    página."""
    return (
        reading.canonical_text[quote.char_start:quote.char_end] == quote.text
        and segment.char_start <= quote.char_start and quote.char_end <= segment.char_end
        and segment.page_start is not None
    )


@dataclass
class Proposed:
    number: int
    category: str
    items: list
    reading: object
    segment: object
    quotes: list
    requirement_id: int
    state: str = ""
    matched: str = ""
    doubt_reason: str = ""
    supports: list = field(default_factory=list)

    @property
    def spans(self):
        """Todas las citas de la fila: `(lectura, inicio, fin, repetida)`."""
        return [(q.segment.reading_id, q.char_start, q.char_end,
                 q.scope == m.QuoteScope.REPETIDA.value) for q in self.quotes]


def _proposed(version):
    """Las filas firmes de la versión: lo que ve la Comisión."""
    return _rows(version, FIRM_STATES)


def _rows(version, states):
    """Las filas de la versión en los estados `states`: las firmes no incluyen sugerencias ni
    quitadas; las descartadas por el sistema están en otra tabla."""
    rows = []
    # Las citas se precargan ya ordenadas y `segment__reading` se resuelve en una sola
    # consulta, con una instancia por lectura: `requirement.quotes.order_by(...)` saltea la
    # precarga y carga una lectura completa (texto y páginas) por cada cita (T-121).
    quotes = Prefetch("quotes", queryset=m.RequirementQuote.objects.order_by("order")
                      .select_related("segment"))
    for requirement in version.requirements.filter(state__in=states).order_by(
            "number").prefetch_related(quotes, "quotes__segment__reading"):
        quote_list = list(requirement.quotes.all())
        first = quote_list[0].segment if quote_list else None
        rows.append(Proposed(
            number=requirement.number, category=requirement.category,
            items=list(requirement.items), reading=first.reading if first else None,
            segment=first, quotes=quote_list, requirement_id=requirement.pk))
    return rows


def _covers(entry, spans):
    """Si alguna de las citas `spans` (lectura, inicio, fin, ...) cubre al menos la mitad
    del ancla de `entry`."""
    size = entry.span[1] - entry.span[0]
    return any(
        span[0] == entry.reading.pk and (o := _overlap(entry.span, (span[1], span[2])))
        and o >= REQUIRED_OVERLAP * size
        for span in spans)


def _pairs(located, proposed):
    """Parejas uno a uno: de mayor a menor superposición; una cita cualquiera de la fila
    cubre al menos la mitad del ancla."""
    candidates = []
    for e_index, entry in enumerate(located):
        size = entry.span[1] - entry.span[0]
        for p_index, row in enumerate(proposed):
            overlap = max((_overlap(entry.span, (start, end))
                           for reading, start, end, _ in row.spans
                           if reading == entry.reading.pk), default=0)
            if overlap and overlap >= REQUIRED_OVERLAP * size:
                candidates.append((-overlap, e_index, p_index))
    candidates.sort()
    taken_e, taken_p, pairs = set(), set(), {}
    for _, e_index, p_index in candidates:
        if e_index in taken_e or p_index in taken_p:
            continue
        taken_e.add(e_index)
        taken_p.add(p_index)
        pairs[e_index] = p_index
    return pairs


def _would_match(entry, rows):
    """Si alguna fila propuesta cubriría el ancla (aunque esté tomada por otro)."""
    return any(_covers(entry, row.spans) for row in rows)


def _row_refs_present(refs, row_quotes):
    missing = []
    for ref in refs:
        if not any(ref.matches(document, key) for document, key, _ in row_quotes):
            missing.append(ref.key if not ref.wildcard else ref.key)
    return missing


def measure_version(run, expected, verification):
    """Mide la versión de `run` contra `expected` (ya comprobada). Devuelve un diccionario
    con las cuentas y las líneas de `resultados.jsonl`."""
    version = run.version
    proposed = _proposed(version)
    suggestions = _suggestions(version)
    file_of = {reading.pk: name for name, reading in verification.readings.items()}
    dispositions = {d.segment_id: d for d in m.Disposition.objects.filter(run=run)}
    pending = {p.segment_id: p.reason for p in m.PendingItem.objects.filter(version=version)}
    fe_rows = [p for p in proposed if p.category != TECHNICAL]
    tech_rows = {(p.items[0] if p.items else None): p for p in proposed
                 if p.category == TECHNICAL}
    if expected.circulars_only:
        return _measure_circulars_only(run, expected, verification, fe_rows, tech_rows)

    measured = [i for i in expected.items if not i.from_circular]
    circular_items = [i for i in expected.items if i.from_circular and not i.blocks]
    fe_items = [i for i in measured if not i.technical]
    tech_items = [i for i in measured if i.technical]

    located = [verification.located[i.id] for i in fe_items]
    pairs = _pairs(located, fe_rows)
    paired_rows = set(pairs.values())
    discarded = _discarded_rows(run)
    # Esperados sin pareja firme, ni por una fila técnica ni por unificación: se emparejan uno a
    # uno con las sugerencias, con la misma regla (T-111).
    candidates = [
        i for i, entry in enumerate(located)
        if i not in pairs and _technical_citing(entry, tech_rows.values()) is None
        and _repeated_in(entry, fe_rows, paired_rows) is None]
    suggestion_pairs = _pairs([located[i] for i in candidates], suggestions)
    suggested_for = {candidates[c]: suggestions[p] for c, p in suggestion_pairs.items()}
    lines, found_count, class_ok = [], 0, 0
    causes, wrong_class = Counter(), 0
    review, unified, suggestion_review = [], [], []
    matched_pk = {}

    for e_index, entry in enumerate(located):
        item = entry.item
        line = {"tipo": "esperado", "id": item.id, "clase": item.clase, "tramo": item.key}
        if e_index in pairs:
            row = fe_rows[pairs[e_index]]
            row.state, row.matched = "emparejado", item.id
            matched_pk[item.id] = row.requirement_id
            found_count += 1
            ok_class = row.category == item.clase
            class_ok += ok_class
            line.update(estado="encontrado", clase_propuesta=row.category,
                        clase_correcta=ok_class, propuesto=row.number)
        elif cited := _technical_citing(entry, tech_rows.values()):
            found_count += 1
            wrong_class += 1
            line.update(estado="encontrado", clase_propuesta=TECHNICAL,
                        clase_correcta=False, propuesto=cited.number,
                        detalle="clase equivocada: el ancla está en un tramo de una fila "
                                "técnica")
            matched_pk[item.id] = cited.requirement_id
        elif (host := _repeated_in(entry, fe_rows, paired_rows)) is not None:
            # La unificación no crea faltantes: el esperado está en una cita `repetida` de
            # una fila ya emparejada con otro (T-103).
            unified.append(item.id)
            line.update(estado="encontrado", detalle="unificado", propuesto=host.number)
            matched_pk[item.id] = host.requirement_id
        elif (suggested := suggested_for.get(e_index)) is not None:
            # Segundo destino de "a revisión obligatoria" (T-111): la pareja es una
            # sugerencia; la Comisión la decide antes de validar.
            suggestion_review.append(entry)
            line.update(estado=MANDATORY_REVIEW, causa=SUGGESTION_CAUSE,
                        detalle=f"motivo de la duda: {suggested.doubt_reason}")
        else:
            cause, detail = _cause(entry, fe_rows, dispositions, pending, discarded)
            if cause == PENDING:
                # Decisión del 2026-10-04: no es un faltante; la matriz no se valida sin
                # que el evaluador resuelva el pendiente.
                review.append({"id": item.id, "tramo": item.key})
                line.update(estado=MANDATORY_REVIEW, causa=cause, detalle=detail)
            else:
                causes[cause] += 1
                line.update(estado="faltante", causa=cause, detalle=detail)
        lines.append(line)

    # Técnicos.
    technical_missing = Counter()
    technical_checked = technical_present = 0
    for item in tech_items:
        row = tech_rows.get(item.renglon)
        line = {"tipo": "esperado", "id": item.id, "clase": TECHNICAL, "renglon": item.renglon}
        if row is None:
            causes[ITEM_WITHOUT_ROW] += 1
            line.update(estado="faltante", causa=ITEM_WITHOUT_ROW)
        else:
            row.state, row.matched = "emparejado", item.id
            matched_pk[item.id] = row.requirement_id
            found_count += 1
            class_ok += 1
            row_quotes = [(file_of.get(q.segment.reading_id), q.segment.key, q.scope)
                          for q in row.quotes]
            refs = item.refs + expected.general + item.annexes + expected.annexes
            missing = _row_refs_present(refs, row_quotes)
            technical_checked += len(refs)
            technical_present += len(refs) - len(missing)
            technical_missing.update(missing)
            line.update(estado="encontrado", clase_propuesta=TECHNICAL, clase_correcta=True,
                        propuesto=row.number, tramos_esperados=len(refs),
                        tramos_faltantes=missing)
        lines.append(line)

    # Circulares: la propuesta todavía no las usa.
    for item in circular_items:
        lines.append({"tipo": "esperado", "id": item.id, "clase": item.clase,
                      "estado": "sin_medir", "causa": CIRCULAR_UNMEASURED})

    # Propuestos.
    leftover_class, leftover_segment = Counter(), Counter()
    for row in proposed:
        entry = {"tipo": "propuesto", "numero": row.number, "clase": row.category}
        if row.category == TECHNICAL:
            entry["renglon"] = row.items[0] if row.items else None
        else:
            entry["tramo"] = row.segment.key if row.segment else ""
        if row.matched:
            entry.update(estado="emparejado", esperado=row.matched)
        elif row.category == TECHNICAL:
            entry.update(estado="sobrante")
            leftover_class[TECHNICAL] += 1
            leftover_segment[f"renglon-{entry['renglon']}"] += 1
        else:
            entry.update(estado="sobrante")
            leftover_class[row.category] += 1
            leftover_segment[entry["tramo"]] += 1
        lines.append(entry)
    # Una fila técnica propuesta y citada por una clase equivocada no es sobrante de nada.
    leftovers = sum(1 for line in lines
                    if line["tipo"] == "propuesto" and line["estado"] == "sobrante")
    leftovers_fe = leftovers - leftover_class[TECHNICAL]
    firm_total = len(proposed)
    firm_fe = len(fe_rows)

    # Citas.
    quote_total = quote_ok = wide = wide_ok = 0
    for row in proposed:
        for quote in row.quotes:
            state = _quote_state(quote.segment.reading, quote.segment, quote)
            if quote.quote_flag == m.QuoteFlag.CITA_AMPLIA:
                wide += 1
                wide_ok += state
            else:
                quote_total += 1
                quote_ok += state
            if not state:
                lines.append({"tipo": "cita", "numero": row.number,
                              "tramo": quote.segment.key, "estado": "no_literal"})

    # Consecuencias (informativo).
    consequences = Counter()
    for item in measured:
        if item.consequence and item.id in matched_pk:
            consequences["con_consecuencia_esperada"] += 1
            suggested = set(m.Consequence.objects.filter(
                requirement_id=matched_pk[item.id]).values_list("consequence_type", flat=True))
            if item.consequence in suggested:
                consequences["entre_las_sugeridas"] += 1

    # Descartadas por el sistema (informe, REQ-033).
    discarded_report = _discarded_report(discarded, located, leftovers)
    lines += discarded_report.pop("lines")

    measured_total = len(measured)
    reviewed = len(review) + len(suggestion_review)
    found = ratio(found_count + len(unified) + reviewed, measured_total)
    leftover_ratio = ratio(leftovers, firm_total)
    suggestions_report = _suggestions_report(
        suggestions, [located[i] for i in candidates], len(suggestion_pairs),
        len(suggestion_review), leftovers, firm_total, found, measured_total)
    lines += suggestions_report.pop("lines")
    circulars = measure_circulars(version, expected, verification, matched_pk)
    if circulars:
        lines += circulars.pop("lines")
    return {
        "circulars": circulars,
        "lines": lines,
        "found": found,
        "found_without_review": ratio(found_count + len(unified), measured_total),
        "review": {"count": len(review), "ids": [r["id"] for r in review],
                   "keys": sorted({r["tramo"] for r in review})},
        "suggestion_review": {"count": len(suggestion_review),
                              "ids": [e.item.id for e in suggestion_review]},
        "unified": {"count": len(unified), "ids": unified},
        "class": ratio(class_ok, found_count),
        "class_wrong_found": wrong_class,
        "causes": dict(causes),
        "leftovers": leftovers,
        "leftover_ratio": leftover_ratio,
        "leftover_ratio_formal_economic": ratio(leftovers_fe, firm_fe),
        "cap": cap_verdict(leftover_ratio, found),
        "discarded": discarded_report,
        "suggestions": suggestions_report,
        "leftovers_by_class": dict(leftover_class),
        "leftovers_by_segment": dict(leftover_segment),
        "literal": ratio(quote_ok, quote_total),
        "wide": {"total": wide, "ok": wide_ok},
        "technical_tramos": ratio(technical_present, technical_checked),
        "technical_missing": dict(technical_missing),
        "circular_unmeasured": len(circular_items),
        "consequences": dict(consequences),
        "coverage": _coverage(run, dispositions),
        "proposed_total": firm_total,
    }


# --- REQ-031 por fila (T-117) --------------------------------------------------------------


POINTS = ("effect", "original", "current", "document_date")
POINT_NAMES = {"effect": "efecto", "original": "texto original", "current": "texto vigente",
               "document_date": "documento y fecha"}


def _norm(text):
    return " ".join((text or "").casefold().split())


def covers_text(shown, anchor):
    """Si el texto mostrado contiene el ancla, con la regla de cobertura de la mitad: vale si
    el ancla está entera o si el tramo más largo que comparten cubre al menos la mitad del
    ancla. Un ancla vacía no se exige."""
    needle = _norm(anchor)
    if not needle:
        return True
    hay = _norm(shown)
    if needle in hay:
        return True
    if not hay:
        return False
    match = SequenceMatcher(None, hay, needle, autojunk=False).find_longest_match(
        0, len(hay), 0, len(needle))
    return match.size >= REQUIRED_OVERLAP * len(needle)


def _original_text(source):
    """El texto original que la pantalla muestra junto a la fuente: el del anexo, si la
    fuente lo referencia; si no, la cita alcanzada."""
    if source.original_segment_id:
        reading = source.original_segment.reading
        return reading.canonical_text[source.original_char_start:source.original_char_end]
    return source.quote.text if source.quote_id else ""


def _source_points(item, block, source):
    document = source.segment.reading.document
    return (
        source.effect == block.source_effect,
        covers_text(_original_text(source), block.original_anchor or item.anchor),
        block.effect == "suprime" or covers_text(source.text, block.current_anchor),
        document.file_name == block.document and source.issued_on.isoformat() == block.date,
    )


def _added_points(item, block, rows, claimed):
    """`agrega`: la fila de origen `circular` con una cita en el documento esperado que
    contiene el ancla de la lista. Devuelve `(fila, puntos)`."""
    best, best_points = None, None
    for row in rows:
        if row.origin != ORIGIN_CIRCULAR or row.pk in claimed:
            continue
        for quote in row.quotes.all():
            document = quote.segment.reading.document
            if document.file_name != block.document or not covers_text(quote.text, item.anchor):
                continue
            points = (True, True, covers_text(quote.text, block.current_anchor),
                      document.issued_on is not None
                      and document.issued_on.isoformat() == block.date)
            if best is None or sum(points) > sum(best_points):
                best, best_points = row, points
    return best, best_points or (False, False, False, False)


def measure_circulars(version, expected, verification, matched_pk):
    """REQ-031 por fila (plan 003, "Cambios en `medir_matriz` (T-117)"): cada bloque
    `circulares` de la lista se mide en cuatro puntos, por separado: (1) una fuente con el
    efecto esperado; (2) el original mostrado contiene el ancla original; (3) el vigente
    contiene el ancla vigente; (4) documento y fecha de la fuente son los esperados. Una fila
    cumple si una misma fuente cumple los cuatro. Para `agrega` vale la fila de origen
    `circular` con cita en el documento esperado. Ruido: fuentes en filas sin esperado de
    circular, por documento y por fila, y filas de origen `circular` sin esperado.
    `matched_pk` es `{id esperado: requisito}`. Sin bloques, devuelve `None`."""
    entries = [(i, b) for i in expected.items for b in i.blocks]
    if not entries:
        return None
    sources = Prefetch("sources", queryset=m.RequirementSource.objects.select_related(
        "segment__reading__document", "quote", "original_segment__reading"))
    rows = list(version.requirements.filter(state__in=FIRM_STATES).prefetch_related(
        sources, "quotes__segment__reading__document").order_by("number"))
    by_pk = {r.pk: r for r in rows}
    claimed, lines, unmeasured = set(), [], []
    points, met, failing = Counter(), 0, []
    by_document, measured = {}, 0
    for item, block in entries:
        line = {"tipo": "circular", "id": item.id, "documento": block.document,
                "fecha": block.date, "efecto": block.effect}
        if block.document not in verification.readings:
            unmeasured.append(item.id)
            lines.append({**line, "estado": "sin_medir", "causa": "circular_no_cargada"})
            continue
        measured += 1
        if block.adds:
            row, flags = _added_points(item, block, rows, claimed)
        else:
            row = by_pk.get(matched_pk.get(item.id))
            flags = (False,) * 4
            for source in (row.sources.all() if row else []):
                candidate = _source_points(item, block, source)
                if sum(candidate) > sum(flags):
                    flags = candidate
        if row is not None:
            claimed.add(row.pk)
        for name, flag in zip(POINTS, flags):
            points[name] += bool(flag)
        ok = all(flags)
        met += ok
        entry = by_document.setdefault(block.document, {"expected": 0, "met": 0})
        entry["expected"] += 1
        entry["met"] += ok
        if not ok:
            failing.append({"id": item.id, "documento": block.document,
                            "puntos": [i for i, flag in enumerate(flags, start=1) if not flag]})
        lines.append({**line, "estado": "cumple" if ok else "no_cumple",
                      "fila": row.number if row else None,
                      **{name: bool(flag) for name, flag in zip(POINTS, flags)}})
    noise_by_document, noise_by_row = Counter(), Counter()
    for row in rows:
        if row.pk in claimed:
            continue
        for source in row.sources.all():
            noise_by_document[source.segment.reading.document.file_name] += 1
            noise_by_row[row.number] += 1
    unexpected = [r.number for r in rows if r.origin == ORIGIN_CIRCULAR and r.pk not in claimed]
    return {
        "expected": measured, "unmeasured": unmeasured,
        "met": ratio(met, measured),
        "points": {name: ratio(points[name], measured) for name in POINTS},
        "by_document": by_document, "failing": failing,
        "noise": {"sources": sum(noise_by_row.values()), "rows": len(noise_by_row),
                  "by_document": dict(noise_by_document),
                  "by_row": {str(k): v for k, v in sorted(noise_by_row.items())},
                  "unexpected_requirements": unexpected},
        "lines": lines,
    }


def _measure_circulars_only(run, expected, verification, fe_rows, tech_rows):
    """Lista con `alcance: circulares` (casos de ajuste sin la lista completa del pliego): solo
    mide REQ-031. No calcula encontrados, sobrantes ni tope del resto. Las filas de los
    esperados se emparejan con la misma regla, solo para los que llevan bloque."""
    items = [i for i in expected.items if i.blocks and not i.from_circular]
    flat = [i for i in items if not i.technical]
    located = [verification.located[i.id] for i in flat if i.id in verification.located]
    pairs = _pairs(located, fe_rows)
    matched = {}
    for index, entry in enumerate(located):
        if index in pairs:
            matched[entry.item.id] = fe_rows[pairs[index]].requirement_id
    for item in items:
        row = tech_rows.get(item.renglon) if item.technical else None
        if row is not None:
            matched[item.id] = row.requirement_id
    circulars = measure_circulars(run.version, expected, verification, matched)
    lines = circulars.pop("lines") if circulars else []
    return {"scope": SCOPE_CIRCULARS, "circulars": circulars, "lines": lines}


def cap_verdict(leftover_ratio, found):
    """El tope de sobrantes (REQ-024, REQ-033): cumple si los sobrantes son hasta
    `MATRIX_SOBRANTES_LIMIT` de las filas firmes y los encontrados son el 100 % (con "a
    revisión obligatoria"). El intervalo de Wilson se informa y no decide."""
    limit = settings.MATRIX_SOBRANTES_LIMIT
    leftovers_ok = leftover_ratio["ok"] <= limit * leftover_ratio["total"] + 1e-9
    found_ok = found["ok"] >= found["total"]
    return {"limit": limit, "leftovers_ok": leftovers_ok, "found_ok": found_ok,
            "met": leftovers_ok and found_ok}


def _repeated_in(entry, fe_rows, paired_rows):
    """La fila ya emparejada con citas `repetida` que cubre el ancla de `entry` con
    cualquiera de sus citas (la principal incluida), o `None`. Una fila sin repetidas no
    cuenta para dos esperados."""
    for index in sorted(paired_rows):
        row = fe_rows[index]
        if any(span[3] for span in row.spans) and _covers(entry, row.spans):
            return row
    return None


def _suggestions(version):
    """Las sugerencias de condición de la versión (REQ-035), con su motivo de duda y los
    respaldos normativos que tienen (REQ-036). No entran en el tope."""
    rows = _rows(version, (SUGGESTION,))
    by_number = {r.number: r for r in version.requirements.filter(state=SUGGESTION)
                 .prefetch_related("norm_supports")}
    for row in rows:
        source = by_number[row.number]
        row.doubt_reason = source.doubt_reason
        row.supports = [(s.unit_label, s.text) for s in source.norm_supports.order_by("id")]
    return rows


def _suggestions_report(suggestions, located, matched, reviewed, leftovers, firm_total,
                        found, measured_total):
    """Informe de sugerencias (T-111; REQ-035, REQ-036): cantidad, por motivo y por tramo,
    cuántas eran esperadas (entre los esperados que ninguna fila firme empareja), cuántas tienen respaldo y cuántas de esas eran esperadas, los
    sobrantes y el tope informativos "si las sugerencias fueran firmes" y la muestra con
    texto."""
    by_reason, by_segment = Counter(), Counter()
    lines, with_pair, with_support, support_pair = [], 0, 0, 0
    for row in suggestions:
        key = row.segment.key if row.segment else ""
        by_reason[row.doubt_reason] += 1
        by_segment[key] += 1
        paired = any(_covers(entry, row.spans) for entry in located)
        with_pair += paired
        if row.supports:
            with_support += 1
            support_pair += paired
        lines.append({"tipo": "sugerencia", "numero": row.number, "tramo": key,
                      "clase": row.category, "motivo": row.doubt_reason,
                      "respaldos": [label for label, _ in row.supports],
                      "estado": "con_pareja" if paired else "sin_pareja"})
    # Si fueran firmes, las que tienen pareja (uno a uno) dejarían de ser sobrantes.
    if_firm = leftovers + len(suggestions) - matched
    sample = [{"number": suggestions[i].number,
               "tramo": suggestions[i].segment.key if suggestions[i].segment else "",
               "reason": suggestions[i].doubt_reason,
               "text": suggestions[i].quotes[0].text if suggestions[i].quotes else "",
               "supports": suggestions[i].supports}
              for i in sample_indexes(len(suggestions), settings.MATRIX_SAMPLE_DISCARDED)]
    return {
        "count": len(suggestions), "by_reason": dict(by_reason), "by_segment": dict(by_segment),
        "expected": ratio(with_pair, len(suggestions)),
        "expected_as_suggestion": ratio(reviewed, measured_total),
        "with_support": with_support,
        "with_support_expected": ratio(support_pair, with_support),
        "leftovers_if_firm": if_firm,
        "cap_if_firm": cap_verdict(ratio(if_firm, firm_total + len(suggestions)), found),
        "sample": sample, "lines": lines,
    }


@dataclass
class _Discarded:
    row: object
    key: str
    spans: list


def _discarded_rows(run):
    rows = list(m.DiscardedRow.objects.filter(run=run).order_by("order", "id")
                .select_related("segment"))
    extra_ids = {extra["segment"] for row in rows for extra in row.extra_quotes}
    extra_readings = dict(m.Segment.objects.filter(pk__in=extra_ids)
                          .values_list("pk", "reading_id"))
    result = []
    for row in rows:
        spans = [(row.segment.reading_id, row.char_start, row.char_end, False)]
        spans += [(extra_readings[extra["segment"]], extra["char_start"], extra["char_end"],
                   True) for extra in row.extra_quotes]
        result.append(_Discarded(row, row.segment.key, spans))
    return result


def sample_indexes(total, sample):
    """Posiciones (en el orden de la corrida) de la muestra de descartadas: una de cada
    `every`, con un mínimo de `minimum`, repartidas parejo; con menos filas que el mínimo,
    todas (REQ-033)."""
    if total <= 0:
        return []
    size = min(total, max(sample["minimum"], -(-total // sample["every"])))
    return [i * total // size for i in range(size)]


def _discarded_report(discarded, located, leftovers):
    """Cantidad de descartadas, reparto por motivo, tramo y pasada, cuántas cubren un ancla
    de la lista, los sobrantes que habría sin el filtro y la muestra con texto."""
    by_reason, by_segment, by_pass = Counter(), Counter(), Counter()
    lines, with_pair = [], 0
    for item in discarded:
        row = item.row
        by_reason[row.reason] += 1
        by_segment[item.key] += 1
        by_pass[row.source_pass] += 1
        paired = any(_covers(entry, item.spans) for entry in located)
        with_pair += paired
        lines.append({"tipo": "descartada", "orden": row.order, "tramo": item.key,
                      "clase": row.category, "motivo": row.reason,
                      "pasada": row.source_pass,
                      "estado": "con_pareja" if paired else "sin_pareja"})
    sample = [{"order": discarded[i].row.order, "tramo": discarded[i].key,
               "reason": discarded[i].row.reason, "text": discarded[i].row.text,
               "evidence": discarded[i].row.evidence_text}
              for i in sample_indexes(len(discarded), settings.MATRIX_SAMPLE_DISCARDED)]
    return {
        "count": len(discarded), "by_reason": dict(by_reason), "by_segment": dict(by_segment),
        "by_pass": dict(by_pass), "with_pair": with_pair,
        "leftovers_without_filter": leftovers + len(discarded) - with_pair,
        "sample": sample, "lines": lines,
    }


def _technical_citing(entry, rows):
    for row in rows:
        for quote in row.quotes:
            if (row.reading is not None and row.reading.pk == entry.reading.pk
                    and quote.char_start <= entry.span[0] and entry.span[1] <= quote.char_end):
                return row
    return None


def _cause(entry, fe_rows, dispositions, pending, discarded=()):
    if _would_match(entry, fe_rows):
        return GROUPED, ""
    for item in discarded:
        if _covers(entry, item.spans):
            return DISCARDED_BY_SYSTEM, f"motivo: {item.row.reason}; tramo: {item.key}"
    disposition = dispositions.get(entry.segment.pk)
    if disposition is None:
        return NO_DISPOSITION, ""
    outcome = disposition.outcome
    if outcome == m.DispositionOutcome.DESCARTADO:
        return DISCARDED, disposition.discard_reason
    if outcome == m.DispositionOutcome.PENDIENTE:
        return PENDING, pending.get(entry.segment.pk, "")
    if outcome == m.DispositionOutcome.REQUISITOS:
        return SEGMENT_WITH_OTHERS, ""
    return SEGMENT_TECHNICAL, ""


def _coverage(run, dispositions):
    """Cobertura sobre un solo conjunto: los tramos de los documentos de la corrida. Los tramos
    de circulares (que no son documentos base) también reciben disposición; se cuentan aparte,
    fuera de la proporción (T-096)."""
    readings = [d["reading"] for d in run.documents]
    total = m.Segment.objects.filter(reading_id__in=readings).count()
    in_base = m.Segment.objects.filter(
        pk__in=list(dispositions), reading_id__in=readings).count()
    by_source = Counter(d.source for d in dispositions.values())
    by_outcome = Counter(d.outcome for d in dispositions.values())
    pending = Counter(
        m.PendingItem.objects.filter(version=run.version).values_list("reason", flat=True))
    return {"segments": total, "with_disposition": in_base,
            "circular_with_disposition": len(dispositions) - in_base,
            "by_source": dict(by_source), "by_outcome": dict(by_outcome),
            "pending_by_reason": dict(pending)}


# --- Tiempos -------------------------------------------------------------------------------


def _page_count(reading):
    """Cantidad real de páginas de la lectura: `Reading.pages` es un diccionario con la lista
    `pages` (más `encoding`, `file_format`, etc.); no se cuentan sus claves."""
    data = reading.pages
    if isinstance(data, dict):
        data = data.get("pages", [])
    return len(data or [])


def timing_summary(run):
    """Tiempo por pasada, por página y por tramo, y la extrapolación a 50 páginas (provisoria
    mientras no haya un pliego de ese tamaño)."""
    readings = m.Reading.objects.filter(pk__in=[d["reading"] for d in run.documents])
    pages = sum(_page_count(r) for r in readings)
    segments = m.Segment.objects.filter(reading__in=readings).count()
    total = run.timings.get("total")
    summary = {"passes": dict(run.timings), "pages": pages, "segments": segments}
    if total is not None and pages:
        summary["seconds_per_page"] = round(total / pages, 2)
        summary["extrapolated_50_pages_seconds"] = round(total / pages * EXTRAPOLATED_PAGES, 1)
    if total is not None and segments:
        summary["seconds_per_segment"] = round(total / segments, 3)
    if "unificacion" in run.timings or "filtro" in run.timings:
        summary["filter_seconds"] = round(
            run.timings.get("unificacion", 0) + run.timings.get("filtro", 0), 3)
    if "respaldo_normativo" in run.timings:
        summary["support_seconds"] = round(run.timings["respaldo_normativo"], 3)
    return summary


# --- La corrida ----------------------------------------------------------------------------


@dataclass
class Report:
    folder: Path
    expected: Expected
    verification: Verification
    results: list

    @property
    def blocking(self):
        """Lo que impide dar por aceptada la medición."""
        reasons = []
        for result in self.results:
            if result.get("error"):
                reasons.append(f"{result['process']}: la propuesta falló")
                continue
            measures = result["measures"]
            circulars = measures.get("circulars")
            if circulars and circulars["met"]["ok"] < circulars["met"]["total"]:
                reasons.append(f"{result['process']}: REQ-031: "
                               f"{circulars['met']['total'] - circulars['met']['ok']} filas de "
                               "circular no cumplen los cuatro puntos")
            if measures.get("scope") == SCOPE_CIRCULARS:
                continue
            for name in ("found", "literal"):
                if measures[name]["ok"] < measures[name]["total"]:
                    reasons.append(f"{result['process']}: {name} no llega al 100 %")
            if not measures["cap"]["leftovers_ok"]:
                reasons.append(f"{result['process']}: los sobrantes pasan el tope de "
                               f"{_percent(measures['cap']['limit'])} de las filas firmes")
            coverage = measures["coverage"]
            if coverage["with_disposition"] < coverage["segments"]:
                reasons.append(f"{result['process']}: hay tramos sin disposición")
        return reasons


def _discard(version, user, run):
    """Descarta la versión que creó la medición, con su hecho de registro."""
    now = timezone.now()
    m.MatrixVersion.objects.filter(pk=version.pk, status=m.VersionStatus.DRAFT).update(
        status=m.VersionStatus.DISCARDED, discarded_at=now, discarded_by=user)
    audit.record(
        EventType.MATRIX_VERSION, outcome=Outcome.OK, channel=Channel.COMMAND, user=user,
        detail={"procedure": version.procedure_id, "version": version.pk,
                "version_number": version.number, "run": run.pk, "action": "discarded",
                "reason": "medicion"},
    )


def measure_process(user, procedure, expected, clock=time.monotonic):
    """Corre la propuesta del proceso único con el canal `eval`, la mide y descarta la
    versión."""
    snapshot = matrix_service._documents_snapshot(procedure)
    run = m.MatrixRun.objects.create(
        procedure=procedure, job=None, process=settings.MATRIX_PROCESS,
        channel=m.RunChannel.EVAL,
        documents=snapshot, authorization_date=procedure.authorization_date)
    readings = {}
    for entry in snapshot:
        reading = m.Reading.objects.select_related("document").get(pk=entry["reading"])
        readings[reading.document.file_name] = reading
    started = clock()
    try:
        version = proposal.propose(run, user=user, channel=Channel.COMMAND)
    except Exception as error:
        return {"process": settings.MATRIX_PROCESS, "run": run.pk,
                "error": f"{type(error).__name__}: {error}",
                "error_class": type(error).__name__,
                "seconds": round(clock() - started, 1)}
    run.refresh_from_db()
    try:
        result = _result_of_run(run, version, procedure, expected, readings)
    finally:
        _discard(version, user, run)
    return result


def _result_of_run(run, version, procedure, expected, readings):
    """Las medidas de una propuesta ya hecha, sin usar el modelo."""
    # La comprobación usa las lecturas de esta propuesta.
    check = verify_expected(expected, procedure, readings)
    measures = measure_version(run, expected, check)
    return {
        "process": run.process or run.level, "run": run.pk, "version": version.number,
        "measures": measures, "timings": timing_summary(run),
        "counts": run.counts,
        "anomalies": dict(Counter(a["type"] for a in run.anomalies)),
        "parameters": run.parameters, "prompt_versions": run.prompt_versions,
        "models": run.models, "corpus_version": run.corpus_version,
    }


def regenerate_summaries(procedure, expected, folder):
    """Reescribe `resumen.md` y `resumen-publico.md` de una corrida ya hecha, sin el modelo
    (T-096): vuelve a medir las propuestas que `parametros.json` nombra, que siguen en la
    base aunque sus versiones estén descartadas. No toca `parametros.json` ni
    `resultados.jsonl`. Lanza `MeasurementRefused` si la carpeta no es una corrida de esta
    lista y este procedimiento, o si falta una propuesta en la base. Las corridas hechas
    con niveles (claves `niveles`, `level` y `nivel`) siguen siendo legibles: el nivel se
    muestra como el proceso de la propuesta."""

    folder = Path(folder)
    try:
        parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
        errors = {}
        for raw in (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines():
            line = json.loads(raw)
            if line.get("tipo") == "error":
                errors[line.get("proceso") or line["nivel"]] = line["error"]
    except (OSError, ValueError):
        raise MeasurementRefused("La carpeta no tiene una corrida legible.") from None
    if (parameters.get("procedimiento") != procedure.number
            or parameters.get("lista", {}).get("sha256") != expected.sha256):
        raise MeasurementRefused("La corrida es de otro procedimiento u otra lista.")
    verification = verify_expected(expected, procedure)
    results = []
    for entry in parameters["propuestas"]:
        label = entry.get("process") or entry["level"]
        if label in errors:
            results.append({"process": label, "run": entry.get("run"), "error": errors[label],
                            "error_class": errors[label].split(":", 1)[0]})
            continue
        try:
            run = m.MatrixRun.objects.get(pk=entry["run"])
            version = run.version
        except (m.MatrixRun.DoesNotExist, m.MatrixVersion.DoesNotExist):
            raise MeasurementRefused(
                f"La propuesta {entry['run']} ya no está en la base.") from None
        readings = {}
        for document in run.documents:
            reading = m.Reading.objects.select_related("document").get(pk=document["reading"])
            readings[reading.document.file_name] = reading
        results.append(_result_of_run(run, version, procedure, expected, readings))
    report = Report(folder, expected, verification, results)
    (folder / "resumen.md").write_text(_summary(report, public=False), encoding="utf-8")
    (folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                               encoding="utf-8")
    _write_sample(report, overwrite=False)  # la que ya completó el verificador no se pisa
    _write_suggestions_sample(report, overwrite=False)
    return report


def measure(user, procedure, expected, runs_dir, *, commit=None, clock=time.monotonic):
    """Comprueba la lista, corre el proceso único y guarda la carpeta de la corrida en
    `runs_dir`. Devuelve el `Report`. Lanza `MeasurementRefused` si la lista no se puede
    usar o si hay un borrador abierto. Ya no hay niveles ni comparación entre ellos (T-100)."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    if not expected.approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    verification = verify_expected(expected, procedure)
    if not verification.ok:
        raise MeasurementRefused("La lista no se puede usar:\n"
                                 + "\n".join(verification_lines(verification)))
    if procedure.matrix_versions.filter(status=m.VersionStatus.DRAFT).exists():
        raise MeasurementRefused("El procedimiento tiene un borrador abierto: la base admite "
                                 "uno solo. Descártelo o mida en otra base.")
    results = [measure_process(user, procedure, expected, clock)]
    started_at = timezone.now()
    base = f"{started_at:%Y%m%d-%H%M%S}-{commit or 'sin-commit'}"
    folder = Path(runs_dir) / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = Path(runs_dir) / f"{base}-{suffix}"
    report = Report(folder, expected, verification, results)
    _write(report, procedure, started_at, commit)
    return report


# --- Salida --------------------------------------------------------------------------------


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


def _write(report, procedure, started_at, commit):
    report.folder.mkdir(parents=True, exist_ok=False)
    expected = report.expected
    parameters = {
        "caso": expected.case, "procedimiento": procedure.number, "uso": expected.use,
        "alcance": expected.scope,
        "iniciada": started_at, "commit": commit or "sin-commit",
        "proceso": settings.MATRIX_PROCESS,
        "lista": {"sha256": expected.sha256,
                  "visto_bueno": expected.approval,
                  "requisitos": len(expected.items)},
        "comprobacion": dict(report.verification.counts),
        "propuestas": [
            {k: r.get(k) for k in ("process", "run", "version", "parameters",
                                    "prompt_versions", "models", "corpus_version", "error")}
            for r in report.results
        ],
    }
    (report.folder / "parametros.json").write_text(
        _dumps(parameters, indent=2) + "\n", encoding="utf-8")
    with (report.folder / "resultados.jsonl").open("w", encoding="utf-8") as handle:
        for result in report.results:
            if result.get("error"):
                handle.write(_dumps({"proceso": result["process"], "tipo": "error",
                                     "error": result["error"]}) + "\n")
                continue
            for line in result["measures"]["lines"]:
                handle.write(_dumps({"proceso": result["process"], **line}) + "\n")
    (report.folder / "resumen.md").write_text(_summary(report, public=False),
                                              encoding="utf-8")
    (report.folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                                      encoding="utf-8")
    _write_sample(report, overwrite=True)
    _write_suggestions_sample(report, overwrite=True)


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def _write_sample(report, *, overwrite):
    """La plantilla local `muestra-descartadas.md`, con texto del pliego (no va al
    repositorio): una fila por descartada de la muestra y una columna para que quien
    verifica diga si el descarte era correcto."""
    for result in report.results:
        sample = [] if result.get("error") else result["measures"]["discarded"]["sample"]
        target = report.folder / SAMPLE_FILE
        if not sample or (target.exists() and not overwrite):
            continue
        out = ["# Muestra de descartadas por el sistema", "",
               "Texto del pliego: no se copia al repositorio. Completar la última columna "
               "con sí o no.", "",
               "| N.º | Tramo | Motivo | Cita | Indicio | ¿Descarte correcto? |",
               "|---|---|---|---|---|---|"]
        out += [f"| {r['order']} | {r['tramo']} | {r['reason']} | {_cell(r['text'])} | "
                f"{_cell(r['evidence'])} | |" for r in sample]
        target.write_text("\n".join(out) + "\n", encoding="utf-8")


def _write_suggestions_sample(report, *, overwrite):
    """La plantilla local `muestra-sugerencias.md`, con texto del pliego y de la norma (no va
    al repositorio): una fila por sugerencia de la muestra y una columna para que quien
    verifica diga si la sugerencia y su respaldo eran correctos."""
    for result in report.results:
        sample = [] if result.get("error") else result["measures"]["suggestions"]["sample"]
        target = report.folder / SUGGESTIONS_SAMPLE_FILE
        if not sample or (target.exists() and not overwrite):
            continue
        out = ["# Muestra de sugerencias de condición", "",
               "Texto del pliego y de la norma: no se copia al repositorio. Completar la "
               "última columna con sí o no.", "",
               "| N.º | Tramo | Motivo | Cita | Respaldo normativo | "
               "¿Sugerencia y respaldo correctos? |",
               "|---|---|---|---|---|---|"]
        out += [f"| {r['number']} | {r['tramo']} | {r['reason']} | {_cell(r['text'])} | "
                f"{_cell(_support_text(r['supports']))} | |" for r in sample]
        target.write_text("\n".join(out) + "\n", encoding="utf-8")


def _support_text(supports):
    return "; ".join(f"{label}: «{text}»" for label, text in supports) or "sin respaldo"


def _seconds(value):
    return "—" if value is None else f"{value:.1f} s".replace(".", ",")


def _summary(report, *, public):
    expected = report.expected
    out = [f"# Medición de la matriz · {expected.case}", ""]
    out.append("Resumen público: solo identificadores, claves de tramo, cuentas, causas y "
               "tiempos." if public else
               "Resumen completo: puede incluir texto del pliego. No se copia al repositorio.")
    out += ["", "Medición provisoria: un solo pliego; los requisitos de un pliego no son "
            "independientes entre sí (plan 003, \"Por qué la medida es provisoria\").",
            f"Uso de la lista: {expected.use or 'sin indicar'}.", ""]
    for result in report.results:
        out.append(f"## Proceso {result['process']}")
        if result.get("error"):
            shown = result["error_class"] if public else result["error"]
            out += ["", f"La propuesta falló: {shown}", ""]
            continue
        measures = result["measures"]
        if measures.get("scope") == SCOPE_CIRCULARS:
            out += ["", "- Alcance de la lista: solo circulares (REQ-031); no se calculan "
                    "encontrados, sobrantes ni tope del resto",
                    *_circular_lines(measures["circulars"], report.expected)]
            out += _timing_lines(result["timings"])
            out.append("")
            continue
        coverage = measures["coverage"]
        out += [
            "",
            f"- Requisitos encontrados: {proportion_text(measures['found'])} "
            "(meta: 100 %)",
            f"- Con clase equivocada entre los encontrados: {measures['class_wrong_found']}",
            f"- Clase correcta entre los encontrados: {proportion_text(measures['class'])} "
            "(se informa; no bloquea)",
            f"- Cita literal: {proportion_text(measures['literal'])} (meta: 100 %); "
            f"citas amplias aparte: {measures['wide']['total']}",
            f"- Tramos con disposición: "
            f"{proportion_text(ratio(coverage['with_disposition'], coverage['segments']))} "
            "(meta: 100 %)",
            f"- Tramos de circulares con disposición (aparte): "
            f"{coverage.get('circular_with_disposition', 0)}",
            f"- Disposición por origen (incluye circulares): "
            f"{_counter_text(coverage['by_source'])}",
            f"- Pendientes por motivo: {_counter_text(coverage['pending_by_reason'])}",
            f"- Tramos técnicos citados por renglón: "
            f"{proportion_text(measures['technical_tramos'])} (se informa; no bloquea)",
            *_review_summary(measures),
            *_suggestion_review_summary(measures),
            f"- Unificados (encontrados por una cita repetida): "
            f"{measures['unified']['count']}"
            + (f" ({', '.join(measures['unified']['ids'])})" if measures["unified"]["ids"]
               else ""),
            f"- Sobrantes (filas firmes sin pareja, sin descartadas ni sugerencias): "
            f"{proportion_text(measures['leftover_ratio'])} "
            f"(por clase: {_counter_text(measures['leftovers_by_class'])})",
            f"- Sobrantes solo sobre formales y económicas: "
            f"{proportion_text(measures['leftover_ratio_formal_economic'])}",
            *_cap_lines(measures),
            f"- Sobrantes por tramo: {_counter_text(measures['leftovers_by_segment'])}",
            *_discarded_lines(measures["discarded"], measures["leftovers"]),
            *_suggestion_lines(measures["suggestions"]),
            f"- Faltantes por causa: {_counter_text(measures['causes'])}",
            f"- Filas de circulares sin medir (T-083): {measures['circular_unmeasured']}",
            *_circular_lines(measures.get("circulars"), report.expected),
        ]
        if measures["consequences"]:
            out.append(f"- Consecuencias (informativo): "
                       f"{_counter_text(measures['consequences'])}")
        out += _timing_lines(result["timings"])
        out += _detail_lines(result, report, public)
        out.append("")
    blocking = report.blocking
    out += ["", "## Bloqueos de la aceptación", ""]
    out += [f"- {reason}" for reason in blocking] or ["- ninguno"]
    out.append("")
    return "\n".join(out)


def _circular_lines(info, expected):
    """REQ-031 por fila, sin texto: cuentas, claves `M-NNN`, títulos de documentos y números de
    fila."""
    if not info:
        return ["- REQ-031 por fila: la lista no tiene bloques de circulares"]

    def label(name):
        return f"{_doc_label(expected, name)} ({name})"

    lines = [
        f"- REQ-031, filas de circular esperadas: {info['expected']}"
        + (f"; sin medir porque la circular no está cargada: {', '.join(info['unmeasured'])}"
           if info["unmeasured"] else ""),
        f"- REQ-031, cumplen los cuatro puntos: {proportion_text(info['met'])}",
        *[f"- REQ-031, punto {number} ({POINT_NAMES[name]}): "
          f"{proportion_text(info['points'][name])}"
          for number, name in enumerate(POINTS, start=1)],
    ]
    for name, entry in sorted(info["by_document"].items()):
        lines.append(f"- REQ-031, circular {label(name)}: cumplen {entry['met']} de "
                     f"{entry['expected']}")
    for failure in info["failing"]:
        lines.append(f"- REQ-031, no cumple {failure['id']} ({label(failure['documento'])}): "
                     f"puntos {', '.join(str(n) for n in failure['puntos'])}")
    noise = info["noise"]
    lines.append(f"- REQ-031, ruido (fuentes en filas sin esperado de circular): "
                 f"{noise['sources']} en {noise['rows']} filas")
    if noise["sources"]:
        lines.append("- REQ-031, ruido por documento: "
                     + ", ".join(f"{label(k)}: {v}" for k, v in sorted(
                         noise["by_document"].items())))
        lines.append("- REQ-031, ruido por fila: "
                     + ", ".join(f"#{k}: {v}" for k, v in noise["by_row"].items()))
    lines.append(f"- REQ-031, requisitos de origen circular sin esperado: "
                 f"{len(noise['unexpected_requirements'])}"
                 + (" (filas " + ", ".join(f"#{n}" for n in noise["unexpected_requirements"])
                    + ")" if noise["unexpected_requirements"] else ""))
    return lines


def _review_summary(measures):
    review = measures.get("review") or {"count": 0, "ids": [], "keys": []}
    if not review["count"]:
        return ["- A revisión obligatoria (tramos pendientes): 0"]
    return [f"- A revisión obligatoria (tramos pendientes): {review['count']}, ya sumados "
            f"a los encontrados; sin ellos: {proportion_text(measures['found_without_review'])}",
            f"- A revisión obligatoria, requisitos: {', '.join(review['ids'])}; "
            f"tramos: {', '.join(review['keys'])}"]


def _suggestion_review_summary(measures):
    review = measures["suggestion_review"]
    if not review["count"]:
        return ["- A revisión obligatoria (sugerencias): 0"]
    return [f"- A revisión obligatoria (sugerencias): {review['count']}, ya sumados a los "
            f"encontrados; sin ellos ni los pendientes: "
            f"{proportion_text(measures['found_without_review'])}",
            f"- A revisión obligatoria, sugerencias, requisitos: {', '.join(review['ids'])}"]


def _suggestion_lines(info):
    lines = [f"- Sugerencias de condición: {info['count']} (no entran en el tope)"]
    if not info["count"]:
        return lines
    lines += [
        f"- Sugerencias por motivo: {_counter_text(info['by_reason'])}",
        f"- Sugerencias por tramo: {_counter_text(info['by_segment'])}",
        f"- Sugerencias que eran requisitos esperados: {proportion_text(info['expected'])}",
        f"- Esperados que quedaron como sugerencia: "
        f"{proportion_text(info['expected_as_suggestion'])}",
        f"- Sugerencias con respaldo normativo: {info['with_support']}; de esas, eran "
        f"esperadas: {proportion_text(info['with_support_expected'])}",
        f"- Sobrantes si las sugerencias fueran firmes (informativo): "
        f"{info['leftovers_if_firm']}; tope con ellas como firmes: "
        f"{'cumpliría' if info['cap_if_firm']['met'] else 'no cumpliría'}",
    ]
    return lines


def _yes(value):
    return "sí" if value else "no"


def _cap_lines(measures):
    cap = measures["cap"]
    return [f"- Tope de sobrantes (hasta {_percent(cap['limit'])} de las filas firmes y "
            f"100 % de encontrados): {'cumple' if cap['met'] else 'no cumple'} "
            f"(sobrantes dentro del tope: {_yes(cap['leftovers_ok'])}; encontrados al "
            f"100 %: {_yes(cap['found_ok'])}); el intervalo se informa y no decide"]


def _discarded_lines(info, leftovers):
    lines = [f"- Descartadas por el sistema: {info['count']}"]
    if not info["count"]:
        return lines
    lines += [
        f"- Descartadas por motivo: {_counter_text(info['by_reason'])}",
        f"- Descartadas por tramo: {_counter_text(info['by_segment'])}",
        f"- Descartadas por pasada: {_counter_text(info['by_pass'])}",
        f"- Descartadas que cubren un ancla de la lista: {info['with_pair']}",
        f"- Sobrantes que habría sin el filtro: {info['leftovers_without_filter']} "
        f"(los {leftovers} de ahora más {info['count'] - info['with_pair']} descartadas "
        "sin pareja)",
    ]
    return lines


def _counter_text(values):
    if not values:
        return "ninguno"
    return ", ".join(f"{key or 'sin motivo'}: {value}" for key, value in sorted(values.items()))


def _timing_lines(timings):
    lines = [f"- Tiempo total: {_seconds(timings['passes'].get('total'))}; por pasada: "
             + ", ".join(f"{name} {_seconds(value)}"
                         for name, value in timings["passes"].items() if name != "total")]
    if "filter_seconds" in timings:
        passes = timings["passes"]
        lines.append(f"- Unificación y filtro: {_seconds(timings['filter_seconds'])} "
                     f"(unificacion {_seconds(passes.get('unificacion'))}, "
                     f"filtro {_seconds(passes.get('filtro'))})")
    if "support_seconds" in timings:
        lines.append(f"- Respaldo normativo: {_seconds(timings['support_seconds'])}")
    if "seconds_per_page" in timings:
        lines.append(
            f"- Por página: {_seconds(timings['seconds_per_page'])}; por tramo: "
            f"{_seconds(timings.get('seconds_per_segment'))}; extrapolado a "
            f"{EXTRAPOLATED_PAGES} páginas: "
            f"{_seconds(timings['extrapolated_50_pages_seconds'])} (provisorio)")
    return lines


def _detail_lines(result, report, public):
    """Faltantes y sobrantes. Con `public`, solo identificadores y claves."""
    lines = ["", "Faltantes:"]
    by_id = {i.id: i for i in report.expected.items}
    rows = result["measures"]["lines"]
    if result["measures"].get("scope") == SCOPE_CIRCULARS:
        return []
    missing = [r for r in rows if r["tipo"] == "esperado" and r["estado"] == "faltante"]
    for row in missing:
        extra = f" ({row['detalle']})" if row.get("detalle") else ""
        text = ""
        if not public and row["id"] in by_id and by_id[row["id"]].anchor:
            text = f" «{by_id[row['id']].anchor}»"
        lines.append(f"- {row['id']} {row.get('tramo') or 'renglón ' + str(row.get('renglon'))}"
                     f": {row['causa']}{extra}{text}")
    if not missing:
        lines.append("- ninguno")
    absent = [(r["id"], r["tramos_faltantes"]) for r in rows
              if r["tipo"] == "esperado" and r.get("tramos_faltantes")]
    if absent:
        lines += ["", "Tramos técnicos esperados que la fila no cita:"]
        lines += [f"- {ident}: {', '.join(keys)}" for ident, keys in absent]
    wrong = [r for r in rows if r["tipo"] == "esperado" and r.get("detalle", "").startswith(
        "clase equivocada")]
    if wrong:
        lines += ["", "Encontrados con clase equivocada: "
                  + ", ".join(r["id"] for r in wrong)]
    suggestions = result["measures"]["suggestions"]
    if suggestions["count"]:
        lines += ["", "Sugerencias (clave, motivo, respaldo):"]
        lines += [f"- #{r['numero']} {r['tramo']} [{r['motivo']}] ({r['estado']}): "
                  + (", ".join(r["respaldos"]) if r["respaldos"] else "sin respaldo")
                  for r in rows if r["tipo"] == "sugerencia"]
    if not public:
        texts = _proposed_texts(result)
        leftovers = [r for r in rows if r["tipo"] == "propuesto" and r["estado"] == "sobrante"
                     and r["clase"] != TECHNICAL]
        if leftovers:
            lines += ["", "Sobrantes (primeros 80 caracteres de la cita):"]
            lines += [f"- #{r['numero']} {r['tramo']}: «{texts.get(r['numero'], '')[:80]}»"
                      for r in leftovers]
        sample = suggestions["sample"]
        if sample:
            lines += ["", f"Muestra de sugerencias ({len(sample)} de {suggestions['count']}):"]
            lines += [f"- #{r['number']} {r['tramo']} [{r['reason']}]: "
                      f"«{_cell(r['text'])[:200]}»; respaldo: "
                      f"{_cell(_support_text(r['supports']))[:300]}" for r in sample]
        sample = result["measures"]["discarded"]["sample"]
        if sample:
            lines += ["", f"Muestra de descartadas ({len(sample)} de "
                      f"{result['measures']['discarded']['count']}):"]
            lines += [f"- #{r['order']} {r['tramo']} [{r['reason']}]: "
                      f"«{_cell(r['text'])[:200]}»; indicio «{_cell(r['evidence'])[:120]}»"
                      for r in sample]
    return lines


def _proposed_texts(result):
    run = m.MatrixRun.objects.get(pk=result["run"])
    return {rq.number: rq.quotes.order_by("order").first().text
            for rq in m.Requirement.objects.filter(version=run.version).prefetch_related(
                "quotes")
            if rq.quotes.exists()}
