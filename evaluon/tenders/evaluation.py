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
  `tramo_tecnico`, `sin_disposicion`, `suprimido_por_circular` (T-123: su única pareja es una
  fila quitada por una circular) y, en técnicos, `renglon_sin_fila`.
- Una fila quitada por una circular con fuente `suprime` es el comportamiento correcto
  (REQ-031): un esperado con bloque `circulares` de efecto `suprime` empareja con ella (uno a
  uno) y cuenta como encontrado ("suprimido por circular"); no es sobrante ni entra en el
  denominador de los sobrantes.
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

Medidas de la 015 (T-238; REQ-101, REQ-102; plan 015, "Criterio de aceptación numérico y
umbrales"):

- Filas conservadas: las filas firmes con pareja en la lista, sobre las filas firmes (70 % o
  más). La pareja se busca contra la lista sin las entradas que excluyen las decisiones del
  2026-10-10.
- Pedazos sin sujeto: comprobación mecánica; la cita tiene que empezar donde empieza una
  oración y terminar donde termina una oración (`piece_problem`, con las oraciones de
  `proposal.sentences`). Umbral: 0.
- Recall sobre la lista sin las entradas excluidas (95 % o más). Las exclusiones están en un
  archivo aparte (`exclusiones.yaml`), con la huella de la lista a la que se refieren y el
  visto bueno del Coordinador; la lista esperada no se toca. La medida informa cuántas
  entradas excluye cada caso.
- Tiempo total y memoria de video máxima de lo registrado (22.000 MiB).
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai.external import ledger
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.queries.evaluation import proportion_text  # usa el Wilson de la 001
from evaluon.tenders import models as m
from evaluon.tenders.proposal import quotes
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.proposal.sentences import piece_problem
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

# Umbrales de la 015 (plan 015), escritos antes de medir.
KEPT_MINIMUM = 0.70
RECALL_MINIMUM = 0.95
RECALL_LABEL = ("Requisitos de la lista que están, sin las excluidas ni lo que está a revisión "
                "(REQ-101, REQ-102)")
PIECES_MAXIMUM = 0
VIDEO_MAXIMUM_MIB = 22000
# Motivos con que las decisiones del 2026-10-10 excluyen una entrada de la lista. `no_exige_nada`
# (T-254, H-244-6): la oración no le exige nada a ninguna oferta (una excepción o una dispensa);
# lo usan los archivos de exclusiones ampliados de los casos 01, 02 y 05.
EXCLUSION_MOTIVES = ("pago", "moneda_de_pago", "factura", "forma_de_presentar_por_el_portal",
                     "compromiso_al_presentarse", "no_exige_nada")

# Causas de un faltante.
GROUPED = "agrupado"
DISCARDED = "tramo_descartado"
DISCARDED_BY_SYSTEM = "descartado_por_el_sistema"
PENDING = "tramo_pendiente"
MANDATORY_REVIEW = "a_revision_obligatoria"
SUGGESTION_CAUSE = "sugerencia"
SUPPRESSED = "suprimido_por_circular"
ADDED_BY_CIRCULAR = "agregada_por_circular"
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
    exclusions: object = None  # `Exclusions` (T-238), o `None` si no se pasó el archivo
    # La huella de la lista de la que se re-ancló esta (`reanclaje.lista_original`, T-262), o
    # vacía: las exclusiones marcadas sobre la original valen para la re-anclada.
    original_sha256: str = ""

    @property
    def excluded(self):
        """`{id: motivo}` de las entradas que excluyen las decisiones del 2026-10-10."""
        return self.exclusions.motives if self.exclusions else {}

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
    reanchoring = data.get("reanclaje")
    original = reanchoring.get("lista_original") if isinstance(reanchoring, dict) else None
    original_sha256 = (str(original.get("sha256") or "").strip().lower()
                       if isinstance(original, dict) else "")
    return Expected(
        case=str(data.get("caso") or ""), path=path,
        sha256=hashlib.sha256(raw).hexdigest(), documents=documents, approval=approval,
        use=str(data.get("uso") or ""),
        general=_refs(data.get("tecnico_general"), default, "tecnico_general"),
        annexes=_refs(data.get("tramos_anexos"), default, "tramos_anexos"),
        items=items, scope=scope, original_sha256=original_sha256,
    )


@dataclass
class Exclusions:
    """Las entradas de la lista que excluyen las decisiones del 2026-10-10 (T-238), leídas de un
    archivo aparte: la lista esperada no se modifica. El archivo lleva la huella de la lista a la
    que se refiere y el visto bueno del Coordinador."""

    path: Path
    sha256: str
    list_sha256: str
    approval: str
    motives: dict  # id -> motivo

    @property
    def by_motive(self):
        return dict(Counter(self.motives.values()))


def load_exclusions(path, expected, *, require_approval=True):
    """Lee el archivo de exclusiones de `expected`. Lanza `ExpectedError` si no se puede leer, si
    la huella no es la de la lista (la lista cambió desde que se marcó), si una entrada no está en
    la lista, es técnica o trae un motivo desconocido; sin visto bueno y con `require_approval`,
    `ExpectedNotApproved`. No modifica `expected`."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
    except OSError as error:
        raise ExpectedError(f"no se pueden leer las exclusiones: {error.__class__.__name__}")
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(
            f"las exclusiones no se pueden leer como YAML ({error.__class__.__name__})")
    if not isinstance(data, dict):
        raise ExpectedError("las exclusiones no tienen la forma esperada")
    listed = str(data.get("lista_sha256") or "").strip().lower()
    # Una lista re-anclada (T-262) tiene las mismas entradas que su original: valen las
    # exclusiones marcadas sobre la original.
    if listed not in {expected.sha256, expected.original_sha256} - {""}:
        raise ExpectedError("las exclusiones se marcaron sobre otra versión de la lista (la "
                            "huella no coincide): se vuelven a marcar y a aprobar")
    approval = str(data.get("visto_bueno") or "").strip()
    if approval.lower().startswith("pendiente"):
        approval = ""
    if require_approval and not approval:
        raise ExpectedNotApproved("las exclusiones no tienen visto bueno: no se usan")
    items = {i.id: i for i in expected.items}
    motives = {}
    for entry in data.get("excluidas") or []:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise ExpectedError("una exclusión no tiene la forma esperada (`id` y `motivo`)")
        ident, motive = str(entry["id"]), str(entry.get("motivo") or "")
        if ident not in items:
            raise ExpectedError(f"{ident}: la exclusión nombra una entrada que no está en la lista")
        if items[ident].technical:
            raise ExpectedError(f"{ident}: una entrada técnica no se excluye")
        if motive not in EXCLUSION_MOTIVES:
            raise ExpectedError(f"{ident}: `motivo` debe ser uno de "
                                f"{', '.join(EXCLUSION_MOTIVES)}")
        if ident in motives:
            raise ExpectedError(f"{ident}: exclusión repetida")
        motives[ident] = motive
    return Exclusions(path=path, sha256=hashlib.sha256(raw).hexdigest(), list_sha256=listed,
                      approval=approval, motives=motives)


def _exclusions_match(exclusions, expected):
    if exclusions.list_sha256 == expected.sha256:
        return "coincide"
    if expected.original_sha256 and exclusions.list_sha256 == expected.original_sha256:
        return "coincide con la de la lista original (re-anclada)"
    return "NO coincide"


def exclusion_lines(expected):
    """Las cuentas de las exclusiones, sin texto del pliego (para `--verificar-esperada`)."""
    exclusions = expected.exclusions
    if exclusions is None:
        return ["Exclusiones de la decisión del 2026-10-10: no se pasó el archivo"]
    return [f"Exclusiones de la decisión del 2026-10-10: {len(exclusions.motives)} de "
            f"{len(expected.items)} entradas ({_counter_text(exclusions.by_motive)}); huella de "
            f"la lista {_exclusions_match(exclusions, expected)}"
            f"; visto bueno: {exclusions.approval or 'pendiente'}"]


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


# --- Re-anclaje de la lista a la lectura vigente (T-262, D-260-2) --------------------------
#
# Una relectura del pliego puede cambiar la partición (las claves de los tramos) sin cambiar el
# texto, o cambiando solo cómo se escribe una tabla. La lista congelada nombra las claves de la
# lectura con que se preparó, y deja de encajar. `reanchor_expected` reubica cada entrada en la
# lectura vigente, sin el modelo: una formal o económica, por su ancla (si el ancla está más de
# una vez, la que ocupa su lugar de la lectura anterior); una clave técnica, por los tramos
# vigentes que ocupan el texto que tenía en la lectura anterior (palabra por palabra). Lo que no
# se puede reubicar se informa con su motivo y conserva su clave: no se inventa.
# `write_reanchored` escribe la lista re-anclada en un archivo NUEVO, al lado de la original
# (que no se toca), con la huella de la original y de cada lectura, y el visto bueno vacío.

REANCHOR_TAG = "reanclada"
_WORD = re.compile(r"\w+")
# Parte del texto de una clave técnica de la lectura anterior que se tiene que encontrar en la
# vigente para reubicarla; por debajo, se informa y no se reubica.
REANCHOR_COVERAGE_MINIMUM = 0.9
# Un tramo vigente sucede a uno anterior si al menos esta parte de sus palabras viene de él, o si
# tiene al menos esta parte de las palabras del anterior.
REANCHOR_SUCCESSOR_SHARE = 0.5
REANCHOR_ENTRY_STATES = ("sin_cambio", "reubicada", "no_reubicada")


@dataclass
class Relocation:
    """Qué pasó con una clave de la lista al re-anclarla. `new` vacía: no se pudo (`reason`)."""

    owner: str  # id de la entrada, o `tecnico_general` / `tramos_anexos`
    field: str  # `tramo`, `tramos`, `tramos_anexos` o `circulares`
    document: str
    old: str
    new: tuple = ()
    occurrence: int = 1
    reason: str = ""

    @property
    def relocated(self):
        return bool(self.new)

    @property
    def changed(self):
        return self.relocated and self.new != (self.old,)


@dataclass
class Reanchoring:
    """El resultado de re-anclar una lista: una `Relocation` por clave que cambia o que no se
    pudo reubicar (las que siguen igual no se listan) y la lectura vigente de cada documento."""

    expected: Expected
    readings: dict  # archivo -> lectura vigente
    relocations: list = field(default_factory=list)

    def of(self, owner):
        return [r for r in self.relocations if r.owner == owner]

    @property
    def entries(self):
        """`{id: "sin_cambio" | "reubicada" | "no_reubicada"}` de cada entrada de la lista."""
        states = {}
        for item in self.expected.items:
            own = self.of(item.id)
            if any(not r.relocated for r in own):
                states[item.id] = "no_reubicada"
            elif any(r.changed for r in own):
                states[item.id] = "reubicada"
            else:
                states[item.id] = "sin_cambio"
        return states

    @property
    def unplaced(self):
        return [r for r in self.relocations if not r.relocated]


class _Alignment:
    """Correspondencia palabra por palabra entre una lectura anterior y la vigente de un mismo
    documento (las palabras en minúscula; los espacios y los signos no cuentan)."""

    def __init__(self, old, new):
        old_words = [(w.group().casefold(), w.start()) for w in _WORD.finditer(old.canonical_text)]
        new_words = [(w.group().casefold(), w.start(), w.end())
                     for w in _WORD.finditer(new.canonical_text)]
        self.old_starts = [start for _, start in old_words]
        self.new_starts = [start for _, start, _ in new_words]
        self.new_ends = [end for _, _, end in new_words]
        a, b = [w for w, _ in old_words], [w for w, _, _ in new_words]
        self.mapping = None  # identidad
        if a != b:
            self.mapping = {}
            for i, j, size in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
                for k in range(size):
                    self.mapping[i + k] = j + k

    def mapped(self, start, end):
        """Los índices de las palabras vigentes que corresponden a las palabras de la lectura
        anterior que empiezan en `[start, end)`, y cuántas palabras anteriores hay ahí."""
        words = range(bisect_left(self.old_starts, start), bisect_left(self.old_starts, end))
        if self.mapping is None:
            return list(words), len(words)
        return [self.mapping[i] for i in words if i in self.mapping], len(words)

    def words_in(self, start, end):
        return bisect_left(self.new_starts, end) - bisect_left(self.new_starts, start)


def _anchor_hits(segments, anchor):
    """Cada aparición de `anchor` en la lectura: `(tramo, ocurrencia en el tramo, posiciones
    absolutas)`, en el orden de la lectura."""
    hits = []
    for segment in segments:
        used = []
        while (span := quotes.locate(segment.text, anchor, used=used)) is not None:
            used.append(span)
            hits.append((segment, len(used), quotes.absolute(segment, span)))
    return hits


class _Reanchorer:
    def __init__(self, expected, procedure, readings=None):
        self.expected = expected
        self.readings = readings or latest_readings(procedure)
        self.documents = {d.file_name: d for d in procedure.documents.all()}
        self._segments, self._previous, self._alignments = {}, {}, {}

    def segments(self, name):
        """Los tramos de la lectura vigente de `name`, en orden (vacía si no tiene lectura)."""
        if name not in self._segments:
            reading = self.readings.get(name)
            self._segments[name] = (list(reading.segments.order_by("order"))
                                    if reading is not None else [])
        return self._segments[name]

    def previous(self, name, key):
        """`(lectura, tramo)` de la lectura anterior más reciente de `name` que tiene `key`."""
        if (name, key) not in self._previous:
            found = None
            document, current = self.documents.get(name), self.readings.get(name)
            if document is not None and current is not None:
                older = document.readings.filter(sequence__lt=current.sequence)
                segment = (m.Segment.objects.filter(reading__in=older, key=key)
                           .select_related("reading", "reading__document")
                           .order_by("-reading__sequence").first())
                if segment is not None:
                    found = (segment.reading, segment)
            self._previous[(name, key)] = found
        return self._previous[(name, key)]

    def alignment(self, old):
        if old.pk not in self._alignments:
            self._alignments[old.pk] = _Alignment(old, self.readings[old.document.file_name])
        return self._alignments[old.pk]

    def anchor(self, owner, field_name, name, key, anchor, occurrence):
        """Reubica una clave por su ancla. `None` si la clave sigue igual."""
        segments = self.segments(name)
        if not segments:  # sin lectura (una circular sin cargar): lo informa la comprobación
            return None
        current = next((s for s in segments if s.key == key), None)
        if current is not None and find_anchor(current, anchor, occurrence) is not None:
            return None
        hits = _anchor_hits(segments, anchor)
        if not hits:
            return Relocation(owner, field_name, name, key,
                              reason="el ancla no está en la lectura vigente")
        if len(hits) > 1:
            hits = self._same_place(name, key, anchor, occurrence, hits)
        if len(hits) != 1:
            return Relocation(owner, field_name, name, key,
                              reason="el ancla está más de una vez en la lectura vigente y la "
                                     "lectura anterior no dice cuál es")
        segment, found_occurrence, _ = hits[0]
        return Relocation(owner, field_name, name, key, (segment.key,), found_occurrence)

    def _same_place(self, name, key, anchor, occurrence, hits):
        """De las apariciones del ancla, las que ocupan el lugar que tenía en la lectura
        anterior que tiene la clave."""
        previous = self.previous(name, key)
        if previous is None:
            return hits
        old, segment = previous
        span = find_anchor(segment, anchor, occurrence)
        if span is None:
            return hits
        alignment = self.alignment(old)
        mapped, _ = alignment.mapped(*span)
        if not mapped:
            return hits
        start, end = alignment.new_starts[min(mapped)], alignment.new_ends[max(mapped)]
        return [hit for hit in hits if hit[2][0] < end and start < hit[2][1]]

    def ref(self, owner, field_name, ref):
        """Reubica una clave técnica por su texto en la lectura anterior. `None` si sigue."""
        segments = self.segments(ref.document)
        if not segments:  # sin lectura: lo informa la comprobación
            return None
        if any(ref.matches(ref.document, s.key) for s in segments):
            return None
        if ref.wildcard:
            return Relocation(owner, field_name, ref.document, ref.key,
                              reason="el comodín no abarca ningún tramo de la lectura vigente")
        previous = self.previous(ref.document, ref.key)
        if previous is None:
            return Relocation(owner, field_name, ref.document, ref.key,
                              reason="ninguna lectura anterior tiene ese tramo")
        old, old_segment = previous
        alignment = self.alignment(old)
        mapped, total = alignment.mapped(old_segment.char_start, old_segment.char_end)
        if not total:
            return Relocation(owner, field_name, ref.document, ref.key,
                              reason="el tramo no tiene texto en la lectura anterior")
        if len(mapped) < REANCHOR_COVERAGE_MINIMUM * total:
            return Relocation(owner, field_name, ref.document, ref.key,
                              reason=f"solo el {_percent(len(mapped) / total)} del texto del "
                                     "tramo está en la lectura vigente")
        starts = sorted(alignment.new_starts[j] for j in mapped)
        keys = []
        for segment in segments:
            share = (bisect_left(starts, segment.char_end)
                     - bisect_left(starts, segment.char_start))
            own = alignment.words_in(segment.char_start, segment.char_end)
            if share and (share >= REANCHOR_SUCCESSOR_SHARE * own
                          or share >= REANCHOR_SUCCESSOR_SHARE * total):
                keys.append(segment.key)
        if not keys:
            return Relocation(owner, field_name, ref.document, ref.key,
                              reason="ningún tramo vigente ocupa el texto del tramo")
        return Relocation(owner, field_name, ref.document, ref.key, tuple(dict.fromkeys(keys)))


def reanchor_expected(expected, procedure, readings=None):
    """Reubica las claves de `expected` en la lectura vigente de cada documento de `procedure`
    (T-262). No usa el modelo, no modifica `expected` ni la base."""
    worker = _Reanchorer(expected, procedure, readings)
    result = Reanchoring(expected, worker.readings)

    def add(relocation):
        if relocation is not None:
            result.relocations.append(relocation)

    for item in expected.items:
        if item.technical:
            for field_name, refs in (("tramos", item.refs), ("tramos_anexos", item.annexes)):
                for ref in refs:
                    add(worker.ref(item.id, field_name, ref))
        else:
            add(worker.anchor(item.id, "tramo", item.document, item.key, item.anchor,
                              item.occurrence))
        for block in item.blocks:
            if block.key and block.anchor and worker.segments(block.document):
                add(worker.anchor(item.id, "circulares", block.document, block.key,
                                  block.anchor, 1))
    for field_name, refs in (("tecnico_general", expected.general),
                             ("tramos_anexos", expected.annexes)):
        for ref in refs:
            add(worker.ref(field_name, field_name, ref))
    return result


def reanchored_path(expected, day):
    """`matriz-esperada.reanclada-AAAA-MM-DD.yaml`, al lado de la lista."""
    path = Path(expected.path)
    return path.with_name(f"{path.stem}.{REANCHOR_TAG}-{day.isoformat()}{path.suffix}")


def _partition_sha256(reading):
    """La huella de la partición de una lectura: clave y posiciones de cada tramo, en orden (dos
    lecturas con el mismo texto y otra partición tienen huellas distintas)."""
    rows = "\n".join(f"{s.key}\t{s.char_start}\t{s.char_end}"
                     for s in reading.segments.order_by("order"))
    return hashlib.sha256(rows.encode("utf-8")).hexdigest()


def _moved(relocations, field_name, document, key):
    """La reubicación de `key` en `field_name`, o `None`."""
    return next((r for r in relocations
                 if r.field == field_name and r.document == document and r.old == key
                 and r.relocated), None)


def _new_refs(entries, relocations, field_name, default_document):
    """La lista de tramos de la lista con cada clave reubicada reemplazada por sus sucesoras,
    con la misma forma (texto o `{documento, tramo}`)."""
    out, seen = [], set()

    def keep(entry, document, key):
        if (document, key) not in seen:  # dos claves viejas pueden tener la misma sucesora
            seen.add((document, key))
            out.append(entry)

    for entry in entries or []:
        is_text = isinstance(entry, str)
        document = (default_document if is_text
                    else str(entry.get("documento") or default_document))
        key = (entry if is_text else str(entry.get("tramo") or "")).strip()
        moved = _moved(relocations, field_name, document, key)
        if moved is None:
            keep(entry, document, key)
            continue
        for new_key in moved.new:
            keep(new_key if is_text else {**entry, "tramo": new_key}, document, new_key)
    return out


REANCHOR_HEADER = (
    "# Lista re-anclada por `medir_matriz --reanclar` (T-262, D-260-2): las mismas entradas que\n"
    "# la lista original, con las claves de tramo de la lectura vigente. La original no se toca\n"
    "# (su huella está en `reanclaje`); los comentarios quedan en ella. Las entradas que no se\n"
    "# pudieron reubicar conservan su clave y están en `reanclaje.no_reubicadas`. Sin visto bueno\n"
    "# no se usa.\n")


def write_reanchored(result, day):
    """Escribe la lista re-anclada en un archivo nuevo al lado de la original y lo devuelve.
    No pisa un archivo que ya existe. La original no se toca."""
    expected = result.expected
    target = reanchored_path(expected, day)
    if target.exists():
        raise ExpectedError(f"ya existe {target.name}: no se pisa")
    raw = Path(expected.path).read_bytes()
    data = yaml.safe_load(raw.decode("utf-8"))
    default = expected.default_document
    for entry in data["requisitos"]:
        own = result.of(str(entry["id"]).strip())
        document = str(entry.get("documento") or default)
        if entry.get("clase") == TECHNICAL:
            for name in ("tramos", "tramos_anexos"):
                if entry.get(name):
                    entry[name] = _new_refs(entry[name], own, name, document)
        else:
            moved = _moved(own, "tramo", document, str(entry.get("tramo") or "").strip())
            if moved is not None:
                entry["tramo"] = moved.new[0]
                if moved.occurrence != 1:
                    entry["ocurrencia"] = moved.occurrence
                else:
                    entry.pop("ocurrencia", None)
        for block in entry.get("circulares") or []:
            moved = _moved(own, "circulares", str(block.get("documento") or ""),
                           str(block.get("tramo") or "").strip())
            if moved is not None:
                block["tramo"] = moved.new[0]
    for name in ("tecnico_general", "tramos_anexos"):
        if data.get(name):
            data[name] = _new_refs(data[name], result.of(name), name, default)

    used = ({i.document for i in expected.items}
            | {r.document for r in expected.general + expected.annexes}
            | {b.document for i in expected.items for b in i.blocks})
    states = Counter(result.entries.values())
    reanchoring = {
        "fecha": day.isoformat(),
        "hecho_con": "medir_matriz --reanclar (T-262)",
        "lista_original": {"archivo": Path(expected.path).name,
                           "sha256": hashlib.sha256(raw).hexdigest(),
                           "visto_bueno": expected.approval},
        "lecturas": [
            {"archivo": name, "lectura": reading.sequence,
             "texto_canonico_sha256": reading.canonical_sha256,
             "particion_sha256": _partition_sha256(reading)}
            for name, reading in sorted(result.readings.items()) if name in used],
        "entradas": {"total": len(expected.items), "sin_cambio": states["sin_cambio"],
                     "reubicadas": states["reubicada"],
                     "no_reubicadas": states["no_reubicada"]},
        "no_reubicadas": [{"id": r.owner, "campo": r.field, "tramo": r.old, "motivo": r.reason}
                          for r in result.unplaced],
    }
    out = {}
    for name, value in data.items():
        if name == "reanclaje":
            continue
        out[name] = "" if name == "visto_bueno" else value
        if name == "visto_bueno":
            out["reanclaje"] = reanchoring
    if "reanclaje" not in out:
        out["visto_bueno"], out["reanclaje"] = "", reanchoring
    text = yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=100)
    target.write_text(REANCHOR_HEADER + text, encoding="utf-8")
    return target


def reanchoring_lines(result):
    """Las cuentas del re-anclaje, con las claves y los ids pero sin texto del pliego (P4)."""
    states = Counter(result.entries.values())
    general = [r for r in result.relocations if r.owner in ("tecnico_general", "tramos_anexos")]
    lines = [
        f"Entradas de la lista: {len(result.expected.items)}; sin cambio "
        f"{states['sin_cambio']}; reubicadas {states['reubicada']}; no reubicadas "
        f"{states['no_reubicada']}",
        f"Claves reubicadas: {sum(r.changed for r in result.relocations)} (de los tramos "
        f"generales y de anexos de la lista: {sum(r.changed for r in general)}); claves que no "
        f"se pudieron reubicar: {len(result.unplaced)}",
    ]
    lines += [f"No se reubica: {r.owner} ({r.field} {r.old}): {r.reason}"
              for r in result.unplaced]
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


def pieces_of(proposed):
    """Los pedazos de las filas firmes y las unidades largas sin ampliar.

    Devuelve `(pedazos, revisadas, largas)`: `pedazos` es `[(fila, tramo, problema)]`;
    `revisadas`, la cantidad de citas revisadas; `largas`, `[(fila, tramo)]` de las citas que
    quedaron como fragmento del modelo porque su unidad pasa del tope (marca `cita_amplia`,
    T-234): no son un pedazo sin sujeto sino una cita a revisar, y no cuentan contra el umbral
    de 0 pedazos. No se revisan las citas de un tramo de tabla (no tiene oraciones) ni las
    largas. Una cita amplia que es el tramo entero sí se revisa. Una cita se revisa dentro del
    texto de su propio tramo."""
    found, checked, long_units = [], 0, []
    for row in proposed:
        for quote in row.quotes:
            segment = quote.segment
            if segment.segment_type == m.SegmentType.TABLA:
                continue  # el texto de una tabla no tiene oraciones: la cita queda en la celda
            whole = quote.char_start == segment.char_start and quote.char_end == segment.char_end
            if quote.quote_flag == m.QuoteFlag.CITA_AMPLIA and not whole:
                long_units.append((row.number, segment.key))
                continue
            checked += 1
            problem = piece_problem(segment.text, quote.char_start - segment.char_start,
                                    quote.char_end - segment.char_start)
            if problem:
                found.append((row.number, segment.key, problem))
    return found, checked, long_units


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
    origin: str = ""

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
            segment=first, quotes=quote_list, requirement_id=requirement.pk,
            origin=requirement.origin))
    return rows


def _suppressed(version):
    """Las filas que una circular dejó `quitado` con una fuente `suprime` (T-123)."""
    rows = _rows(version, (m.RequirementState.QUITADO.value,))
    with_source = set(m.RequirementSource.objects.filter(
        requirement__version=version, effect=m.SourceEffect.SUPRIME.value,
        requirement__state=m.RequirementState.QUITADO.value).values_list(
            "requirement_id", flat=True))
    return [r for r in rows if r.requirement_id in with_source]


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

    # T-238: las entradas que excluyen las decisiones del 2026-10-10 no se esperan: no entran en
    # el emparejamiento ni en el denominador (una fila que solo las cubre es sobrante).
    excluded = expected.excluded
    measured = [i for i in expected.items if not i.from_circular and i.id not in excluded]
    circular_items = [i for i in expected.items if i.from_circular and not i.blocks]
    fe_items = [i for i in measured if not i.technical]
    tech_items = [i for i in measured if i.technical]

    located = [verification.located[i.id] for i in fe_items]
    pairs = _pairs(located, fe_rows)
    paired_rows = set(pairs.values())
    discarded = _discarded_rows(run)
    # Un esperado con bloque `suprime` sin pareja firme se empareja, uno a uno, con las filas
    # que una circular dejó quitadas (T-123).
    suppressed = _suppressed(version)
    wants_suppressed = [i for i, entry in enumerate(located) if i not in pairs and any(
        b.effect == "suprime" for b in entry.item.blocks)]
    suppressed_pairs = _pairs([located[i] for i in wants_suppressed], suppressed)
    suppressed_for = {wants_suppressed[c]: suppressed[p] for c, p in suppressed_pairs.items()}
    # T-256 (D7): el que no consiguió una suprimida propia porque otro la tomó, pero está en una
    # fila suprimida (o repartido entre varias), cuenta como «suprimido, en otra fila» (unidad de
    # sentido: la circular suprimió la subcláusula entera en una fila).
    suppressed_elsewhere = {}
    for index in wants_suppressed:
        if index in suppressed_for:
            continue
        entry = located[index]
        host = _covering_row(entry, suppressed)
        hosts = [host] if host is not None else _union_rows(entry, suppressed)
        if hosts:
            suppressed_elsewhere[index] = hosts
    # Esperados sin pareja firme, ni por una fila técnica ni por unificación: se emparejan uno a
    # uno con las sugerencias, con la misma regla (T-111).
    candidates = [
        i for i, entry in enumerate(located)
        if i not in pairs and i not in suppressed_for and i not in suppressed_elsewhere
        and _technical_citing(entry, tech_rows.values()) is None
        and _repeated_in(entry, fe_rows, paired_rows) is None]
    suggestion_pairs = _pairs([located[i] for i in candidates], suggestions)
    suggested_for = {candidates[c]: suggestions[p] for c, p in suggestion_pairs.items()}
    lines, found_count, class_ok = [], 0, 0
    causes, wrong_class = Counter(), 0
    review, unified, suggestion_review, suppressed_ids = [], [], [], []
    matched_pk = {}
    elsewhere = {}

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
        elif (gone := suppressed_for.get(e_index)) is not None:
            # REQ-031: la fila que la circular quitó es la que mide el efecto `suprime`.
            suppressed_ids.append(item.id)
            found_count += 1
            ok_class = gone.category == item.clase
            class_ok += ok_class
            matched_pk[item.id] = gone.requirement_id
            line.update(estado="encontrado", clase_propuesta=gone.category,
                        clase_correcta=ok_class, propuesto=gone.number,
                        detalle="suprimido por circular")
        elif (gone_hosts := suppressed_elsewhere.get(e_index)) is not None:
            suppressed_ids.append(item.id)
            elsewhere[item.id] = [h.number for h in gone_hosts]
            matched_pk[item.id] = gone_hosts[0].requirement_id
            line.update(estado="encontrado", detalle="suprimido por circular, en otra fila",
                        propuesto=gone_hosts[0].number, filas=[h.number for h in gone_hosts])
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
        elif hosts := ([host] if (host := _covering_row(entry, fe_rows)) is not None
                       else _union_rows(entry, fe_rows)):
            # ADR-0034: el contenido del requisito está en otra fila de la matriz, o repartido
            # entre varias del mismo tramo (una oración partida, un encabezado de lista):
            # cuenta como encontrado y se informa aparte con las filas que lo contienen.
            elsewhere[item.id] = [h.number for h in hosts]
            matched_pk[item.id] = hosts[0].requirement_id
            line.update(estado="encontrado", detalle="en otra fila",
                        propuesto=hosts[0].number, filas=[h.number for h in hosts])
        else:
            cause, detail = _cause(entry, fe_rows, dispositions, pending, discarded,
                                   suppressed)
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
    technical_checked = technical_present = technical_found = 0
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
            technical_found += 1
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
    added_by_circular = []
    for row in proposed:
        entry = {"tipo": "propuesto", "numero": row.number, "clase": row.category}
        if row.category == TECHNICAL:
            entry["renglon"] = row.items[0] if row.items else None
        else:
            entry["tramo"] = row.segment.key if row.segment else ""
        if row.matched:
            entry.update(estado="emparejado", esperado=row.matched)
        elif row.origin == ORIGIN_CIRCULAR:
            # T-256: la fila que agregó una circular no es sobrante (la lista no mide todavía
            # lo que agregan las circulares); se informa aparte.
            entry.update(estado=ADDED_BY_CIRCULAR)
            added_by_circular.append(row.number)
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

    # Medidas de la 015 (T-238): pedazos sin sujeto, unidades largas sin ampliar y entradas
    # excluidas.
    pieces, pieces_checked, long_units = pieces_of(proposed)
    lines += [{"tipo": "pedazo", "numero": number, "tramo": key, "problema": problem}
              for number, key, problem in pieces]
    lines += [{"tipo": "unidad_larga", "numero": number, "tramo": key}
              for number, key in long_units]
    excluded_here = [i.id for i in expected.items if i.id in excluded]
    lines += [{"tipo": "excluida", "id": ident, "motivo": excluded[ident]}
              for ident in excluded_here]

    # Descartadas por el sistema (informe, REQ-033).
    discarded_report = _discarded_report(discarded, located, leftovers)
    lines += discarded_report.pop("lines")

    measured_total = len(measured)
    reviewed = len(review) + len(suggestion_review)
    found = ratio(found_count + len(unified) + len(elsewhere) + reviewed, measured_total)
    # T-256 (D5): lo que está a revisión obligatoria no está encontrado; la cifra principal va
    # sin eso y la otra se informa al lado.
    found_without_review = ratio(found_count + len(unified) + len(elsewhere), measured_total)
    # T-256 (D9): las filas técnicas las arma una regla (pasada `filas_tecnicas`): las cifras sin
    # ellas se informan aparte.
    technical_rows = firm_total - firm_fe
    found_without_technical = ratio(
        found_count - technical_found + len(unified) + len(elsewhere), len(fe_items))
    kept_without_technical = ratio(firm_fe - leftovers_fe, firm_fe)
    leftover_ratio = ratio(leftovers, firm_total)
    suggestions_report = _suggestions_report(
        suggestions, [located[i] for i in candidates], len(suggestion_pairs),
        len(suggestion_review), leftovers, firm_total, found, measured_total)
    lines += suggestions_report.pop("lines")
    circulars = measure_circulars(version, expected, verification, matched_pk,
                                  marked_rows(run))
    if circulars:
        lines += circulars.pop("lines")
    return {
        "circulars": circulars,
        "lines": lines,
        "found": found,
        "found_without_review": found_without_review,
        "found_without_technical": found_without_technical,
        "kept_without_technical": kept_without_technical,
        "technical": {"items": len(tech_items), "found": technical_found,
                      "rows": technical_rows},
        "added_by_circular": {"count": len(added_by_circular), "rows": added_by_circular},
        "suppressed_elsewhere": {"count": len(suppressed_elsewhere),
                                 "ids": [located[i].item.id for i in suppressed_elsewhere]},
        "elsewhere": {"count": len(elsewhere), "ids": list(elsewhere), "rows": dict(elsewhere)},
        "review": {"count": len(review), "ids": [r["id"] for r in review],
                   "keys": sorted({r["tramo"] for r in review})},
        "suggestion_review": {"count": len(suggestion_review),
                              "ids": [e.item.id for e in suggestion_review]},
        "unified": {"count": len(unified), "ids": unified},
        "suppressed": {"count": len(suppressed_ids), "ids": suppressed_ids},
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
        "kept": ratio(firm_total - leftovers, firm_total),
        "pieces": {"count": len(pieces), "checked": pieces_checked,
                   "rows": sorted({number for number, _, _ in pieces}),
                   "by_problem": dict(Counter(problem for _, _, problem in pieces))},
        "long_units": {"count": len(long_units),
                       "rows": sorted({number for number, _ in long_units})},
        "recall": found_without_review,
        "excluded": {"count": len(excluded_here), "ids": excluded_here,
                     "by_motive": dict(Counter(excluded[i] for i in excluded_here)),
                     "applied": expected.exclusions is not None},
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


def best_source_points(item, block, sources):
    """Los puntos de la mejor fuente de una fila para el bloque (T-137). Gana la de más
    puntos; en empate, la que es del documento y la fecha esperados (punto 4) y, después, la
    de los primeros puntos; si siguen iguales, la de menor id: el resultado no depende del
    orden en que la base devuelve las fuentes."""
    best = (False,) * 4
    best_key = (0, False, best)
    for source in sorted(sources, key=lambda s: s.pk or 0):
        candidate = _source_points(item, block, source)
        key = (sum(candidate), candidate[3], candidate)
        if key > best_key:
            best, best_key = candidate, key
    return best


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


def marked_rows(run):
    """Los números de fila que la propuesta dejó "a revisión obligatoria" por una circular (la
    misma regla que usa la pantalla: anomalía `review_required` con circular)."""
    return {number for anomaly in (run.anomalies or []) if anomaly.get("review_required")
            and anomaly.get("circular") for number in anomaly.get("requirements", [])}


def _shows_change(row, block):
    """Si la fila muestra un cambio de la circular esperada con su cita: una fuente cuyo
    documento es el del bloque, o, en `agrega`, la fila de origen `circular` con cita en él."""
    if row is None:
        return False
    if block.adds:
        return True
    return any(source.segment.reading.document.file_name == block.document
               for source in row.sources.all())


def measure_circulars(version, expected, verification, matched_pk, marked=frozenset()):
    """REQ-031 por fila (plan 003, "Cambios en `medir_matriz` (T-117)"): cada bloque
    `circulares` de la lista se mide en cuatro puntos, por separado: (1) una fuente con el
    efecto esperado; (2) el original mostrado contiene el ancla original; (3) el vigente
    contiene el ancla vigente; (4) documento y fecha de la fuente son los esperados. Una fila
    cumple si una misma fuente cumple los cuatro. Para `agrega` vale la fila de origen
    `circular` con cita en el documento esperado. Ruido: fuentes en filas sin esperado de
    circular, por documento y por fila, y filas de origen `circular` sin esperado.
    `matched_pk` es `{id esperado: requisito}`. Sin bloques, devuelve `None`.

    Lo que bloquea (ADR-0034, P3) es otra medida: la fila cumple si muestra el cambio de la
    circular esperada con su cita o está en `marked` ("a revisión obligatoria"). Los cuatro
    puntos se informan aparte y no bloquean."""
    entries = [(i, b) for i in expected.items for b in i.blocks]
    if not entries:
        return None
    sources = Prefetch("sources", queryset=m.RequirementSource.objects.select_related(
        "segment__reading__document", "quote", "original_segment__reading"))
    rows = list(version.requirements.filter(state__in=FIRM_STATES).prefetch_related(
        sources, "quotes__segment__reading__document").order_by("number"))
    # Las filas quitadas por una circular sirven para medir `suprime`, pero no son ruido.
    by_pk = {r.pk: r for r in rows}
    by_pk.update({r.pk: r for r in version.requirements.filter(
        state=m.RequirementState.QUITADO.value, sources__effect=m.SourceEffect.SUPRIME.value
    ).distinct().prefetch_related(sources, "quotes__segment__reading__document")})
    claimed, lines, unmeasured = set(), [], []
    points, met, failing = Counter(), 0, []
    by_document, measured = {}, 0
    p3_ok, p3_failing, p3_marked = 0, [], []
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
            flags = best_source_points(item, block, row.sources.all() if row else [])
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
        if _shows_change(row, block):
            notice = "cambio"
        elif row is not None and row.number in marked:
            notice = "marca"
            p3_marked.append(item.id)
        else:
            notice = "falta"
            p3_failing.append(item.id)
        p3_ok += notice != "falta"
        lines.append({**line, "estado": "cumple" if ok else "no_cumple", "p3": notice,
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
        "p3": ratio(p3_ok, measured), "p3_failing": p3_failing, "p3_marked": p3_marked,
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
    circulars = measure_circulars(run.version, expected, verification, matched,
                                  marked_rows(run))
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


def _union_rows(entry, rows):
    """Las filas con una cita en el tramo del ancla que, juntas, cubren al menos la mitad del
    ancla (una oración partida en varias filas), o `[]` (ADR-0034)."""
    pieces = []
    for row in rows:
        for quote in row.quotes:
            if quote.segment_id != entry.segment.pk:
                continue
            start, end = max(quote.char_start, entry.span[0]), min(quote.char_end, entry.span[1])
            if start < end:
                pieces.append((start, end, row))
    pieces.sort(key=lambda p: (p[0], p[1]))
    covered, edge = 0, entry.span[0]
    for start, end, _ in pieces:
        start = max(start, edge)
        if end > start:
            covered += end - start
            edge = end
    if covered < REQUIRED_OVERLAP * (entry.span[1] - entry.span[0]):
        return []
    found = []
    for _, _, row in pieces:
        if row not in found:
            found.append(row)
    return sorted(found, key=lambda r: r.number)


def _covering_row(entry, rows):
    """La primera fila propuesta que cubre el ancla de `entry` (aunque esté emparejada con otro
    esperado), o `None`."""
    return next((row for row in rows if _covers(entry, row.spans)), None)


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
            if (quote.segment.reading_id == entry.reading.pk
                    and quote.char_start <= entry.span[0] and entry.span[1] <= quote.char_end):
                return row
    return None


def _cause(entry, fe_rows, dispositions, pending, discarded=(), suppressed=()):
    if _would_match(entry, fe_rows):
        return GROUPED, ""
    if _would_match(entry, suppressed):
        return SUPPRESSED, ""
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
            if circulars and circulars["p3"]["ok"] < circulars["p3"]["total"]:
                reasons.append(f"{result['process']}: REQ-031 (P3): "
                               f"{circulars['p3']['total'] - circulars['p3']['ok']} filas de "
                               "circular sin el cambio con su cita ni la marca "
                               "\"a revisión obligatoria\"")
            if measures.get("scope") == SCOPE_CIRCULARS:
                continue
            for name in ("found", "literal"):
                if measures[name]["ok"] < measures[name]["total"]:
                    reasons.append(f"{result['process']}: {name} no llega al 100 %")
            # Los sobrantes son informativos hasta el piloto (ADR-0024): no bloquean.
            coverage = measures["coverage"]
            if coverage["with_disposition"] < coverage["segments"]:
                reasons.append(f"{result['process']}: hay tramos sin disposición")
        return reasons

    @property
    def unmet_015(self):
        """Las medidas de la 015 que no llegan a su umbral (T-238)."""
        return unmet_015(self)


def unmet_015(report):
    """Las medidas de la 015 que no llegan a su umbral, por proceso (se informan; el bloqueo de
    la aceptación sigue siendo el de la 003)."""
    unmet = []
    for result in report.results:
        if result.get("error") or result["measures"].get("scope") == SCOPE_CIRCULARS:
            continue
        for name, _, ok in thresholds_015(result["measures"], result.get("video_memory")):
            if not ok:
                unmet.append(f"{result['process']}: {name}")
    return unmet


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


VIDEO_MEMORY_COMMAND = ("nvidia-smi --query-gpu=memory.used,memory.total "
                        "--format=csv,noheader,nounits")


def video_memory():
    """La memoria de video usada y total, en MiB (P6). El comando se toma de la variable de
    entorno `MEASURE_VIDEO_MEMORY_COMMAND` (por defecto `nvidia-smi`) y debe escribir
    "usada, total". Si no se puede leer, devuelve que no estaba disponible y por qué: la
    medición no falla por eso."""
    command = os.environ.get("MEASURE_VIDEO_MEMORY_COMMAND") or VIDEO_MEMORY_COMMAND
    try:
        output = subprocess.run(shlex.split(command), capture_output=True, text=True,
                                timeout=10, check=True).stdout
        used, total = [int(part) for part in output.strip().splitlines()[0].split(",")[:2]]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
        return {"available": False, "reason": type(error).__name__}
    return {"available": True, "used_mib": used, "total_mib": total}


def max_video_mib(video):
    """La memoria de video máxima de las lecturas registradas (antes y después), en MiB, o
    `None` si ninguna se pudo leer."""
    seen = [moment["used_mib"] for moment in (video or {}).values()
            if moment and moment.get("available")]
    return max(seen) if seen else None


def thresholds_015(measures, video=None):
    """Las medidas de la 015 contra su umbral: `[(nombre, texto de lo medido, cumple)]`. Los
    umbrales están escritos en el plan 015 (cuadro "Criterio de aceptación numérico y
    umbrales") y arriba, en las constantes del módulo."""
    kept, found, pieces = measures["kept"], measures["recall"], measures["pieces"]
    rows = [
        ("Filas conservadas (REQ-101, REQ-102)", kept, _at_least(kept, KEPT_MINIMUM)),
        ("Pedazos sin sujeto (REQ-101)", pieces, pieces["count"] <= PIECES_MAXIMUM),
        (RECALL_LABEL, found, _at_least(found, RECALL_MINIMUM)),
    ]
    memory = max_video_mib(video)
    if memory is not None:
        rows.append(("Memoria de video máxima registrada", memory, memory <= VIDEO_MAXIMUM_MIB))
    return rows


def _at_least(value, minimum):
    return value["total"] > 0 and value["ok"] / value["total"] >= minimum - 1e-9


def measure_process(user, procedure, expected, clock=time.monotonic, *, use_external=None,
                    label=None, snapshot=None, measurement=None):
    """Corre la propuesta del proceso único con el canal `eval`, la mide y descarta la
    versión. Con `--externo matriz` (T-291) se corre dos veces sobre la misma lectura
    (`snapshot`): `use_external=False` (local) y `True` (externa, con su `measurement` del libro
    de pedidos externos); `label` es el nombre de cada una en el resumen."""
    snapshot = snapshot or matrix_service._documents_snapshot(procedure)
    named = {"etiqueta": label} if label else {}
    label = label or settings.MATRIX_PROCESS
    run = m.MatrixRun.objects.create(
        procedure=procedure, job=None, process=settings.MATRIX_PROCESS,
        channel=m.RunChannel.EVAL,
        documents=snapshot, authorization_date=procedure.authorization_date)
    readings = {}
    for entry in snapshot:
        reading = m.Reading.objects.select_related("document").get(pk=entry["reading"])
        readings[reading.document.file_name] = reading
    video = {"before": video_memory()}
    started = clock()
    try:
        version = proposal.propose(run, user=user, channel=Channel.COMMAND,
                                   use_external=use_external, measurement=measurement)
    except Exception as error:
        video["after"] = video_memory()
        failed = {"process": label, **named, "run": run.pk,
                  "error": f"{type(error).__name__}: {error}",
                  "error_class": type(error).__name__, "video_memory": video,
                  "seconds": round(clock() - started, 1)}
        if measurement:
            failed["gasto_externo"] = external_spending(procedure, measurement, run)
        return failed
    video["after"] = video_memory()
    run.refresh_from_db()
    try:
        result = _result_of_run(run, version, procedure, expected, readings)
        result.update(process=label, **named)
        result["video_memory"] = video
        if measurement:
            result["gasto_externo"] = external_spending(procedure, measurement, run)
    finally:
        _discard(version, user, run)
    return result


EXTERNAL_STAGE = "matriz"


def external_spending(procedure, measurement, run):
    """El gasto real de la propuesta externa (T-291; plan 016, «Costo y tope»), con el costo que
    informó el proveedor: el de los pedidos de esta propuesta en el libro (`gasto_usd`; 0 si todos
    se reutilizaron por huella) y el de la etapa de la matriz en toda la medición
    (`gasto_medicion_usd`, `ledger.spent_stage`), más lo que la propuesta registró en su clave
    `externo` (pedidos, gasto por pedido y si volvió a lo local)."""
    run.refresh_from_db()
    key = (run.counts or {}).get("externo", {}).get(EXTERNAL_STAGE, {})
    stages = ((run.models or {}).get("externo") or {}).get("etapas") or {}
    own = AuditEvent.objects.filter(
        event_type=EventType.EXTERNAL_REQUEST,
        detail__corrida={"tipo": EXTERNAL_STAGE, "numero": run.pk}).exclude(
        detail__resultado=ledger.IN_FLIGHT).values_list("detail__costo_usd", flat=True)
    return {
        "medicion": measurement,
        "gasto_usd": float(sum((Decimal(str(cost or 0)) for cost in own), Decimal(0))),
        "gasto_medicion_usd": float(ledger.spent_stage(EXTERNAL_STAGE, procedure.pk,
                                                       measurement=measurement)),
        "pedidos": key.get("pedidos"),
        "por_etapa": {stage: {"pedidos": summary.get("pedidos"),
                              "gasto_usd": summary.get("gasto_usd")}
                      for stage, summary in (key.get("por_etapa") or {}).items()},
        "etapa": stages.get(EXTERNAL_STAGE, "local"),
        "volvio_a_local": key.get("volvio_a_local"),
    }


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


def _matrix_figures(lines, *, corrected, excluded, suprime_ids):
    """Las cifras de la 015 de las líneas guardadas de una corrida, con las reglas de antes o con
    las de T-256 (D5, D7, D9) y las entradas `excluded` (las del archivo de exclusiones que se
    aplica)."""
    measured = [line for line in lines if line["tipo"] == "esperado"
                and line.get("estado") != "sin_medir"]
    proposed = [line for line in lines if line["tipo"] == "propuesto"]
    if corrected:
        measured = [line for line in measured if line["id"] not in excluded]
    gone = {line["id"] for line in lines if line["tipo"] == "esperado"} - {
        line["id"] for line in measured}

    def found(line):
        if line.get("estado") == "encontrado":
            return True
        # D7: el esperado con bloque `suprime` que una fila suprimida cubre está encontrado.
        return corrected and line.get("causa") == SUPPRESSED and line["id"] in suprime_ids

    claimed = Counter()
    for line in measured:
        for number in {line.get("propuesto"), *(line.get("filas") or [])} - {None}:
            claimed[number] += 1
    leftovers = technical_leftovers = 0
    for row in proposed:
        freed = (row.get("estado") == "emparejado" and row.get("esperado") in gone
                 and not claimed[row.get("numero")])
        if row.get("estado") == "sobrante" or freed:
            # Una fila cuyo único esperado salió de la lista es sobrante (la Comisión la quitaría).
            leftovers += 1
            technical_leftovers += row.get("clase") == TECHNICAL
    review = sum(1 for line in measured if line.get("estado") == MANDATORY_REVIEW)
    hits = sum(1 for line in measured if found(line))
    fe = [line for line in measured if line.get("clase") != TECHNICAL]
    fe_rows = [row for row in proposed if row.get("clase") != TECHNICAL]
    return {
        "recall": ratio(hits, len(measured)) if corrected else ratio(hits + review, len(measured)),
        "found_with_review": ratio(hits + review, len(measured)),
        "review": review,
        "kept": ratio(len(proposed) - leftovers, len(proposed)),
        "found_without_technical": ratio(sum(1 for line in fe if found(line)), len(fe)),
        "kept_without_technical": ratio(len(fe_rows) - (leftovers - technical_leftovers),
                                        len(fe_rows)),
        "suppressed_elsewhere": sum(1 for line in measured if line.get("causa") == SUPPRESSED
                                    and line["id"] in suprime_ids) if corrected else 0,
        "excluded": len({line["id"] for line in lines if line["tipo"] == "excluida"})
        if not corrected else len(excluded),
    }


def recompute_matrix_run(folder, expected, exclusions=None):
    """Recalcula, sin modelo ni base, las cifras de la 015 de una corrida guardada de
    `medir_matriz` (su `resultados.jsonl`): con las reglas de antes y con las de T-256 y el
    archivo de exclusiones `exclusions` (el corregido; sin archivo, las de la corrida). Una
    entrada que la corrida excluyó y el archivo ya no excluye no tiene línea: no se puede medir
    sin la base y se informa en `without_line`. El origen de cada fila tampoco está en el archivo:
    las filas agregadas por una circular se ven solo en una medición nueva."""
    folder = Path(folder)
    try:
        lines = [json.loads(raw) for raw in (folder / "resultados.jsonl").read_text(
            encoding="utf-8").splitlines() if raw.strip()]
    except OSError as error:
        raise MeasurementRefused(f"La corrida no se puede leer: {error.__class__.__name__}")
    run_excluded = {line["id"] for line in lines if line["tipo"] == "excluida"}
    excluded = set(exclusions.motives) if exclusions is not None else run_excluded
    suprime_ids = {item.id for item in expected.items
                   if any(block.effect == "suprime" for block in item.blocks)}
    common = dict(excluded=excluded, suprime_ids=suprime_ids)
    after = _matrix_figures(lines, corrected=True, **common)
    after["without_line"] = sorted(run_excluded - excluded)
    return {"folder": str(folder),
            "before": _matrix_figures(lines, corrected=False, **common), "after": after}


def _read_run_folder(procedure, expected, folder):
    """`(parametros, errores)` de una corrida ya hecha: `parametros.json` y los errores de
    `resultados.jsonl` por proceso. Lanza `MeasurementRefused` si la carpeta no es una corrida
    legible de esta lista y este procedimiento."""
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
    return parameters, errors


def _results_of_entries(entries, errors, procedure, expected):
    """Las medidas de las propuestas `entries` de un `parametros.json` (siguen en la base aunque sus
    versiones estén descartadas), sin usar el modelo. Lanza `MeasurementRefused` si falta una."""
    results = []
    for entry in entries:
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
        result = _result_of_run(run, version, procedure, expected, readings)
        result["video_memory"] = entry.get("video_memory")
        if entry.get("etiqueta"):
            # Una medición con `--externo matriz` (T-291): el nombre de cada propuesta es el de la
            # medición («completo · local», «completo · externo») y la externa trae su gasto.
            result["process"] = entry["etiqueta"]
        if entry.get("gasto_externo"):
            result["gasto_externo"] = entry["gasto_externo"]
        results.append(result)
    return results


def regenerate_summaries(procedure, expected, folder):
    """Reescribe `resumen.md` y `resumen-publico.md` de una corrida ya hecha, sin el modelo
    (T-096): vuelve a medir las propuestas que `parametros.json` nombra, que siguen en la
    base aunque sus versiones estén descartadas. No toca `parametros.json` ni
    `resultados.jsonl`. Lanza `MeasurementRefused` si la carpeta no es una corrida de esta
    lista y este procedimiento, o si falta una propuesta en la base. Las corridas hechas
    con niveles (claves `niveles`, `level` y `nivel`) siguen siendo legibles: el nivel se
    muestra como el proceso de la propuesta."""

    folder = Path(folder)
    parameters, errors = _read_run_folder(procedure, expected, folder)
    verification = verify_expected(expected, procedure)
    results = _results_of_entries(parameters["propuestas"], errors, procedure, expected)
    report = Report(folder, expected, verification, results)
    (folder / "resumen.md").write_text(_summary(report, public=False), encoding="utf-8")
    (folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                               encoding="utf-8")
    _write_sample(report, overwrite=False)  # la que ya completó el verificador no se pisa
    _write_suggestions_sample(report, overwrite=False)
    return report


REFERENCE_LABEL = f"{settings.MATRIX_PROCESS} · local (referencia)"


def reference_result(procedure, expected, folder):
    """La propuesta local de una corrida ya hecha como referencia de `medir_matriz
    --solo-externo` (T-294, O-293-2): `(resultado, snapshot)`. El resultado son las medidas de esa
    propuesta (que sigue en la base) recalculadas sin el modelo y con el nombre `REFERENCE_LABEL`;
    el snapshot, las lecturas con que se hizo, para que la propuesta externa corra sobre la misma.
    La primera propuesta de la carpeta que no es externa. Lanza `MeasurementRefused` si la carpeta
    no es una corrida de esta lista y este procedimiento, no trae una propuesta local o esa falló."""
    parameters, errors = _read_run_folder(procedure, expected, folder)
    local = [entry for entry in parameters["propuestas"]
             if not entry.get("gasto_externo")
             and not str(entry.get("etiqueta") or "").endswith("· externo")]
    if not local:
        raise MeasurementRefused("La corrida de referencia no trae una propuesta local.")
    result = _results_of_entries(local[:1], errors, procedure, expected)[0]
    if result.get("error"):
        raise MeasurementRefused("La propuesta local de la corrida de referencia falló.")
    result.update(process=REFERENCE_LABEL, etiqueta=REFERENCE_LABEL)
    return result, m.MatrixRun.objects.get(pk=result["run"]).documents


def measure(user, procedure, expected, runs_dir, *, commit=None, clock=time.monotonic,
            external=False, measurement=None, reference=None):
    """Comprueba la lista, corre el proceso único y guarda la carpeta de la corrida en
    `runs_dir`. Devuelve el `Report`. Lanza `MeasurementRefused` si la lista no se puede
    usar o si hay un borrador abierto. Ya no hay niveles ni comparación entre ellos (T-100).

    Con `external` (`medir_matriz --externo matriz`, T-291; plan 016, «Medición del paso 3»):
    dos propuestas sobre la misma lectura en la misma base, una local y otra con la etapa externa,
    cada una con su registro y medida con la misma lista; la externa con su gasto real. Pide el
    uso externo encendido y la matriz en `externo`. `measurement` nombra la medición en el libro
    de pedidos externos (`--medicion`): repetirla con el mismo nombre reutiliza por huella las
    respuestas ya pagadas (costo 0); por omisión, el procedimiento con la fecha y la hora.

    Con `reference` (`--solo-externo CARPETA`, T-294, O-293-2): una corrida ya hecha con la
    propuesta local; no se repite la local (de 15 a 60 minutos de GPU por caso). Se corre solo la
    externa, sobre las mismas lecturas que la referencia, y se mide con la misma lista; el resumen
    trae las medidas de la referencia (recalculadas sin el modelo) y las de la externa. Implica
    `external`."""
    external = external or bool(reference)
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
    if external:
        if not proposal.external.enabled():
            raise MeasurementRefused(
                "Para medir con el modelo externo, el uso externo tiene que estar encendido y la "
                "matriz en «externo» (EXTERNAL_ENABLED y EXTERNAL_STAGE_MATRIZ).")
        measurement = (measurement
                       or f"medir_matriz-{procedure.number}-{timezone.now():%Y%m%d-%H%M%S}")
        if reference:
            local, snapshot = reference_result(procedure, expected, reference)
            results = [local]
        else:
            snapshot = matrix_service._documents_snapshot(procedure)
            results = [measure_process(user, procedure, expected, clock, use_external=False,
                                       label=f"{settings.MATRIX_PROCESS} · local",
                                       snapshot=snapshot)]
        results.append(measure_process(user, procedure, expected, clock, use_external=True,
                                       label=f"{settings.MATRIX_PROCESS} · externo",
                                       snapshot=snapshot, measurement=measurement))
    else:
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
        "exclusiones": ({"sha256": expected.exclusions.sha256,
                         "lista_sha256": expected.exclusions.list_sha256,
                         "visto_bueno": expected.exclusions.approval,
                         "cantidad": len(expected.exclusions.motives),
                         "por_motivo": expected.exclusions.by_motive}
                        if expected.exclusions else None),
        "propuestas": [
            {**{k: r.get(k) for k in ("process", "run", "version", "parameters",
                                      "prompt_versions", "models", "corpus_version", "error",
                                      "video_memory")},
             # T-291: el nombre y el gasto de cada propuesta de una medición con el externo.
             **{k: r[k] for k in ("etiqueta", "gasto_externo") if k in r}}
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
        out += _video_lines(result.get("video_memory"))
        out += external_spending_lines(result.get("gasto_externo"))
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
            *_015_lines(measures, result),
            *_review_summary(measures),
            *_suggestion_review_summary(measures),
            *_elsewhere_lines(measures),
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
            f"- Suprimidas por una circular y encontradas (T-123): "
            f"{measures['suppressed']['count']}"
            + (f" ({', '.join(measures['suppressed']['ids'])})"
               if measures["suppressed"]["ids"] else ""),
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


def external_spending_lines(spending):
    """El gasto externo de una propuesta en el resumen (T-291): cifras, sin texto del pliego."""
    if not spending:
        return []
    by_stage = "; ".join(f"{stage}: {info.get('pedidos')} pedidos, {info.get('gasto_usd')} USD"
                         for stage, info in (spending.get("por_etapa") or {}).items())
    lines = [f"- Gasto externo real (libro de pedidos, medición {spending.get('medicion')}): "
             f"{spending.get('gasto_usd')} USD en {spending.get('pedidos')} pedidos"
             + (f" ({by_stage})" if by_stage else "")
             + (f"; en toda la medición, {spending['gasto_medicion_usd']} USD"
                if "gasto_medicion_usd" in spending else "")]
    if spending.get("etapa") != "externo":
        lines.append("- La etapa externa no terminó: la propuesta siguió por la cadena local "
                     "(ver las anomalías `externo_no_disponible`)")
    return lines


def _count_text(value):
    """`x de y (z %)` de una proporción `{ok, total, rate}`."""
    return f"{value['ok']} de {value['total']} ({_percent(value['rate'])})"


def _015_lines(measures, result):
    """Las medidas de la 015 (T-238) contra su umbral, solo con cifras."""
    kept, pieces, found = measures["kept"], measures["pieces"], measures["recall"]
    excluded = measures["excluded"]
    verdict = {name: "cumple" if ok else "no cumple"
               for name, _, ok in thresholds_015(measures, result.get("video_memory"))}
    memory = max_video_mib(result.get("video_memory"))
    total = result["timings"]["passes"].get("total")
    return [
        f"- Medidas de la 015, filas conservadas (con pareja en la lista): {_count_text(kept)}; "
        f"umbral {_percent(KEPT_MINIMUM)} o más: "
        f"{verdict['Filas conservadas (REQ-101, REQ-102)']}",
        f"- Medidas de la 015, pedazos sin sujeto: {pieces['count']} de {pieces['checked']} "
        f"citas ({_counter_text(pieces['by_problem'])}); umbral {PIECES_MAXIMUM}: "
        f"{verdict['Pedazos sin sujeto (REQ-101)']}",
        f"- Medidas de la 015, unidades largas sin ampliar (cita_amplia, se revisan aparte y "
        f"no cuentan como pedazos): {measures['long_units']['count']} "
        f"de {pieces['checked'] + measures['long_units']['count']} citas",
        f"- Medidas de la 015, recall sobre la lista sin las excluidas ni lo que está a "
        f"revisión: {_count_text(found)}; umbral {_percent(RECALL_MINIMUM)} o más: "
        f"{verdict[RECALL_LABEL]}",
        f"- Medidas de la 015, recall contando lo que está a revisión (informado): "
        f"{_count_text(measures['found'])}",
        f"- Medidas de la 015, sin las filas técnicas que arma una regla (informado): recall "
        f"{_count_text(measures['found_without_technical'])}; filas conservadas "
        f"{_count_text(measures['kept_without_technical'])} "
        f"({measures['technical']['rows']} filas técnicas aparte)",
        f"- Medidas de la 015, filas agregadas por una circular (no son sobrantes): "
        f"{measures['added_by_circular']['count']}",
        "- Medidas de la 015, entradas de la lista excluidas por la decisión del 2026-10-10: "
        + (f"{excluded['count']} ({_counter_text(excluded['by_motive'])})"
           if excluded["applied"] else "no se aplicó el archivo de exclusiones"),
        f"- Medidas de la 015, tiempo total de la propuesta: {_seconds(total)}; memoria de "
        "video máxima registrada: "
        + (f"{memory} MiB (umbral {VIDEO_MAXIMUM_MIB} MiB)" if memory is not None
           else "no registrada"),
    ]


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
        f"- REQ-031, filas con el cambio y su cita o con la marca \"a revisión obligatoria\" "
        f"(P3, bloquea): {proportion_text(info['p3'])}"
        + (f"; solo con la marca: {', '.join(info['p3_marked'])}" if info["p3_marked"] else "")
        + (f"; sin cambio ni marca: {', '.join(info['p3_failing'])}"
           if info["p3_failing"] else ""),
        f"- REQ-031, cumplen los cuatro puntos (se informa; no bloquea, ADR-0034): "
        f"{proportion_text(info['met'])}",
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


def _video_lines(video):
    if not video:
        return []

    def one(moment):
        if not moment or not moment.get("available"):
            return f"no disponible ({(moment or {}).get('reason', 'sin dato')})"
        return f"{moment['used_mib']} de {moment['total_mib']} MiB"

    return ["", f"- Memoria de video (P6): antes de la propuesta {one(video.get('before'))}; "
            f"después {one(video.get('after'))}"]


def _elsewhere_lines(measures):
    info = measures["elsewhere"]
    return [f"- Encontrados en otra fila (ADR-0034, ya sumados a los encontrados): "
            f"{info['count']}"
            + (" (" + ", ".join(f"{i} en las filas " + ", ".join(f"#{n}" for n in numbers)
                                for i, numbers in info["rows"].items()) + ")"
               if info["count"] else "")]


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
            f"100 %: {_yes(cap['found_ok'])}); el intervalo se informa y no decide; "
            "informativo, no bloquea hasta el piloto (ADR-0024)"]


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
