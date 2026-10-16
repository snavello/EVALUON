"""Puerta de filtrado de lo reservado: el único lugar que arma un pedido externo (T-290; REQ-121;
ADR-0067; plan 016, "Un solo punto de filtrado de lo reservado"; constitución 1.6, P4 y P9).

Es el único módulo que llama a `ExternalPayload.from_guard`; el cliente rechaza todo lo que no sea
un pedido salido de acá (y uno copiado, rehecho o cambiado después: O-289-4, `payload.py`).

**Cada pieza de texto entra con el documento del que sale** (`Piece`), armada con estas funciones
y nunca como texto suelto:

- `instruction(texto)`: lo que escribe el código (la instrucción, los rótulos, el armado).
- `tender_document(documento, texto)`: texto de un documento del pliego (`tenders.Document`).
- `offer_document(documento, texto)`: texto de un documento de la oferta (`offers.Document`).
- `requirement(requisito, texto)`: el texto de un requisito de la matriz (`tenders.Requirement`).
- `portal(texto)`: un dato publicado en el Portal de Compras.
- `commission_answer(texto)` y `technical_report(texto)`: existen para que la etapa las declare;
  **nunca salen**.

Reglas (ADR-0067), todas en `build`; si alguna falla, el pedido entero no sale:

1. **Lista permitida por tipo**, con el tipo que dice la base (no el que diga quien llama): del
   pliego, `pliego`, `anexo`, `especificaciones`, las dos circulares y `respuesta_consulta`; de la
   oferta, `economica`, `tecnica`, `garantia`, `anexo_tecnico`, `otro` y sin clasificar. Todo otro
   tipo, también uno que se agregue mañana (y el `dictamen`), queda bloqueado. `compliance` nunca.
   Un documento tiene que ser del procedimiento del pedido y, si es de una oferta, de la oferta del
   pedido.
   **Ampliación (H-290-3, decisión del Coordinador del 2026-10-16, P4 y falla cerrada; el ADR-0067
   lo enmienda el Coordinador):** un documento de la oferta con la sugerencia `compliance` en el
   informe de alguna de sus lecturas (`report["suggestion"]["kind"] == "compliance"`, la que pone
   `offers/suggestions.py` a un informe de consultas, T-259) se trata como reservado aunque nadie
   la haya confirmado y su tipo sea otro: no sale (motivo `documento_compliance_sugerido`), una
   celda que lo tenga en su grupo o su cita no sale, y sus párrafos entran en la comparación por
   huellas igual que los de una hoja.
2. **Exclusiones por contenido**: las respuestas de la Comisión, el informe técnico del área (como
   pieza o como documento de ese tipo), y en un pedido sobre una oferta, los requisitos que
   dependen de consultas externas (por el catálogo de `assessment/externals.py`, por la marca del
   modelo que trae la celda o por una marca ya guardada en un resultado del par), y toda celda cuyo
   grupo de lectura o cuya cita salga de un documento `compliance` (o con la sugerencia).
3. **Huellas**: el pedido armado entero (sistema, salto de línea y mensajes en orden: H-290-1) se
   compara con los párrafos de todos los
   documentos `compliance` del procedimiento, en secuencias de 8 palabras normalizadas (sin tildes
   ni mayúsculas). Una coincidencia bloquea el pedido entero. Una hoja sin lectura no se puede
   comparar: bloquea también (falla cerrada).
4. **Al bloquear**: el pedido no sale, queda en el registro como `bloqueado` **sin texto**, con el
   motivo y lo que se comprobó (`ledger.record_blocked`), y `build` devuelve `Blocked` con la
   anomalía `externo_bloqueado` para que la etapa siga por el camino local, sin bajar la celda.

Lo admitido (`Admitted`) se manda con `ledger.send([...])`, que registra cada pedido.

Lo que la puerta guarda en el registro (`filtro`) son tipos, identificadores, motivos y cuentas:
nunca texto ni huellas del texto reservado.
"""

import re
import unicodedata
from dataclasses import dataclass

from django.conf import settings

from evaluon.ai.external import ledger
from evaluon.ai.external.payload import ExternalPayload, stage_group
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import Passage as OfferPassage
from evaluon.offers.models import Reading as OfferReading
from evaluon.tenders.models import Document as TenderDocument
from evaluon.tenders.models import Requirement

VERSION = "puerta-v1"
ANOMALY = "externo_bloqueado"
FINGERPRINT_WORDS = 8

# Orígenes de una pieza de texto.
INSTRUCTION = "instruccion"
TENDER = "pliego"
OFFER = "oferta"
REQUIREMENT = "requisito"
PORTAL = "portal"
COMMISSION_ANSWER = "respuesta_comision"
TECHNICAL_REPORT = "informe_tecnico"

ALLOWED_SOURCES = frozenset({INSTRUCTION, TENDER, OFFER, REQUIREMENT, PORTAL})

# Lista permitida por tipo (regla 1). Escrita a mano y no derivada de los `DocumentKind`: un tipo
# nuevo de los modelos queda afuera hasta que alguien lo agregue acá, con su prueba.
TENDER_KINDS_ALLOWED = frozenset({
    "pliego", "anexo", "especificaciones", "circular_modificatoria", "circular_aclaratoria",
    "respuesta_consulta"})
OFFER_KINDS_ALLOWED = frozenset({"economica", "tecnica", "garantia", "anexo_tecnico", "otro", ""})
COMPLIANCE = "compliance"

# Motivos de bloqueo (los guarda el registro y los recibe la etapa).
R_SOURCE = "origen_no_permitido"
R_COMMISSION = "respuesta_comision"
R_TECHNICAL = "informe_tecnico"
R_COMPLIANCE = "documento_compliance"
R_KIND = "tipo_no_permitido"
R_MISSING = "documento_inexistente"
R_OTHER_PROCEDURE = "documento_de_otro_procedimiento"
R_OTHER_OFFER = "documento_de_otra_oferta"
R_REQUIREMENT_MISSING = "requisito_inexistente"
R_REQUIREMENT_OTHER = "requisito_de_otro_procedimiento"
R_CATALOG = "requisito_externo_catalogo"
R_MODEL = "requisito_externo_modelo"
R_CELL = "celda_con_compliance"
R_FINGERPRINT = "huella_compliance"
R_UNREAD = "hoja_sin_lectura"
R_SUGGESTED = "documento_compliance_sugerido"

EXCLUSIONS = (R_COMMISSION, R_TECHNICAL, R_CATALOG, R_MODEL, R_CELL)


# --- Piezas -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Piece:
    """Una pieza de texto del pedido con su origen: `source` (ver arriba), el documento del que
    sale (`document_id`) y, si es un requisito o una respuesta, su identificador (`ref`)."""

    text: str
    source: str
    document_id: int | None = None
    ref: int | str | None = None

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise TypeError("Una pieza del pedido externo es un texto.")


def _pk(value):
    if value is None:
        return None
    value = getattr(value, "pk", value)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"Identificador inválido: {value!r}.")
    return int(value)


def instruction(text):
    """Texto que escribe el código: la instrucción, los rótulos y el armado del pedido."""
    return Piece(text, INSTRUCTION)


def tender_document(document, text):
    """Texto de un documento del pliego (`tenders.Document` o su id)."""
    return Piece(text, TENDER, document_id=_pk(document))


def offer_document(document, text):
    """Texto de un documento de la oferta (`offers.Document` o su id)."""
    return Piece(text, OFFER, document_id=_pk(document))


def requirement(requirement_or_id, text):
    """El texto de un requisito de la matriz (`tenders.Requirement` o su id)."""
    return Piece(text, REQUIREMENT, ref=_pk(requirement_or_id))


def portal(text, *, ref=None):
    """Un dato publicado en el Portal de Compras (público, ADR-0065)."""
    return Piece(text, PORTAL, ref=ref)


def commission_answer(text, *, ref=None):
    """Una respuesta de la Comisión: nunca sale (puede transcribir una consulta reservada)."""
    return Piece(text, COMMISSION_ANSWER, ref=ref)


def technical_report(text, *, document=None):
    """El informe técnico del área: nunca sale (el ADR-0065 no lo clasifica)."""
    return Piece(text, TECHNICAL_REPORT, document_id=_pk(document))


@dataclass(frozen=True)
class Cell:
    """La celda (oferta y requisito) de la que trata un pedido de la evaluación: el requisito, si
    el modelo local lo marcó `externo`, y los documentos de la oferta de su grupo de lectura y de
    su cita."""

    requirement: object
    external_flagged: bool = False
    group_documents: tuple = ()
    cited_documents: tuple = ()


# --- Resultado de la puerta -------------------------------------------------------------------


@dataclass(frozen=True)
class Admitted:
    """Un pedido que puede salir: el `ExternalPayload` y lo que comprobó la puerta (`filter`)."""

    payload: ExternalPayload
    filter: dict
    blocked = False

    @property
    def custom_id(self):
        return self.payload.custom_id


@dataclass(frozen=True)
class Blocked:
    """Un pedido que no sale. `reason` es el primer motivo, `reasons` todos; `event_id` es el
    hecho `bloqueado` del registro; `anomaly` (`externo_bloqueado`) es lo que la etapa registra
    al seguir por el camino local."""

    custom_id: str
    stage: str
    reason: str
    reasons: tuple
    filter: dict
    event_id: int
    anomaly: str = ANOMALY
    blocked = True


# --- Huellas ----------------------------------------------------------------------------------


# Una palabra son letras y números seguidos: el guion bajo también corta (H-290-6).
_WORD = re.compile(r"[^\W_]+")


def _invisible(ch):
    """Un carácter invisible de formato (categoría Unicode `Cf`) o el guion blando."""
    return ch == "\u00ad" or unicodedata.category(ch) == "Cf"


def words(text, *, invisible=""):
    """Las palabras de `text` sin tildes ni mayúsculas. Antes de cortar se reemplazan los
    caracteres invisibles de formato (categoría `Cf`: espacio de ancho cero, unión de palabras,
    marca de orden de bytes) y el guion blando por `invisible` (por omisión se descartan, H-290-2)
    y se normaliza con NFKC (letras de ancho completo, ligaduras). Las palabras se cortan en todo
    lo que no sea letra o número, también el guion bajo (H-290-6)."""
    visible = "".join(invisible if _invisible(ch) else ch for ch in (text or ""))
    plain = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", visible))
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch)).lower()
    return _WORD.findall(plain)


def shingles(text, size=FINGERPRINT_WORDS):
    """Las secuencias de `size` palabras seguidas de `text`, de dos lecturas del texto (H-290-6):
    con los invisibles descartados (un invisible en medio de una palabra no la parte) y con los
    invisibles como espacios (un invisible entre dos palabras no las pega)."""
    found = set()
    for invisible in ("", " "):
        sequence = words(text, invisible=invisible)
        found |= {tuple(sequence[i:i + size]) for i in range(len(sequence) - size + 1)}
    return found


def suggested_compliance(procedure_id):
    """Los documentos de las ofertas del procedimiento con la sugerencia `compliance` en el informe
    de alguna de sus lecturas (H-290-3): reservados aunque nadie la haya confirmado."""
    return set(OfferReading.objects.filter(
        document__offer__procedure_id=procedure_id,
        report__suggestion__kind=COMPLIANCE).values_list("document_id", flat=True))


def _compliance_fingerprints(procedure_id, suggested):
    """Las secuencias de los documentos `compliance` del procedimiento y de los que tienen la
    sugerencia `compliance` (todas sus lecturas y pasajes), por documento, y las hojas que no
    tienen lectura."""
    sheets = set(OfferDocument.objects.filter(
        kind=COMPLIANCE, offer__procedure_id=procedure_id).values_list("pk", flat=True))
    documents = sorted(sheets | set(suggested))
    by_document = {pk: set() for pk in documents}
    for document_id, text in OfferReading.objects.filter(document_id__in=documents) \
            .values_list("document_id", "canonical_text"):
        by_document[document_id] |= shingles(text)
    for document_id, text in OfferPassage.objects.filter(
            reading__document_id__in=documents).values_list("reading__document_id", "text"):
        by_document[document_id] |= shingles(text)
    read = set(OfferReading.objects.filter(document_id__in=documents)
               .values_list("document_id", flat=True))
    return by_document, [pk for pk in documents if pk not in read]


# --- Comprobaciones ---------------------------------------------------------------------------


def _external_requirement(requirement_id, offer_id, flagged):
    """Los motivos por los que el requisito depende de una consulta externa (P9)."""
    from evaluon.assessment import externals, grounds
    from evaluon.assessment.models import Doubt, Result

    found = []
    requirement = Requirement.objects.filter(pk=requirement_id).first()
    if requirement is not None:
        checks = externals.match(grounds.requirement_text(requirement).context)
        if checks:
            found.append({"motivo": R_CATALOG, "requisito": requirement_id,
                          "consultas": [check.key for check in checks]})
    marked = Result.objects.filter(offer_id=offer_id, requirement_id=requirement_id).filter(
        doubt=Doubt.EXTERNO).exists() or Result.objects.filter(
        offer_id=offer_id, requirement_id=requirement_id, facts__has_key="externo").exists()
    if flagged or marked:
        found.append({"motivo": R_MODEL, "requisito": requirement_id,
                      "marca": "celda" if flagged else "resultado_guardado"})
    return found


class _Check:
    """Las comprobaciones de un pedido: junta todos los motivos y lo que se miró."""

    def __init__(self, procedure_id, offer_id):
        self.procedure_id = procedure_id
        self.offer_id = offer_id
        self.reasons = []
        self.documents = {}
        self.sources = {}
        # Las exclusiones por pieza se comprueban siempre; las del requisito y la celda, cuando
        # el pedido es sobre una oferta o una celda.
        self.exclusions = {R_COMMISSION, R_TECHNICAL}
        self.suggested = suggested_compliance(procedure_id)

    def fail(self, reason, **data):
        entry = {"motivo": reason, **data}
        if entry not in self.reasons:
            self.reasons.append(entry)

    def pieces(self, pieces):
        tender_ids = {p.document_id for p in pieces if p.source == TENDER}
        offer_ids = {p.document_id for p in pieces if p.source == OFFER}
        tenders = {row["pk"]: row for row in TenderDocument.objects.filter(
            pk__in=tender_ids).values("pk", "kind", "procedure_id")}
        offers = {row["pk"]: row for row in OfferDocument.objects.filter(
            pk__in=offer_ids).values("pk", "kind", "offer_id", "offer__procedure_id")}
        requirement_ids = {p.ref for p in pieces if p.source == REQUIREMENT}
        requirements = dict(Requirement.objects.filter(pk__in=requirement_ids)
                            .values_list("pk", "version__procedure_id"))
        for piece in pieces:
            self.sources[piece.source] = self.sources.get(piece.source, 0) + 1
            if piece.source == COMMISSION_ANSWER:
                self.fail(R_COMMISSION, origen=piece.source, ref=piece.ref)
            elif piece.source == TECHNICAL_REPORT:
                self.fail(R_TECHNICAL, origen=piece.source, documento=piece.document_id)
            elif piece.source not in ALLOWED_SOURCES:
                self.fail(R_SOURCE, origen=piece.source)
            elif piece.source == TENDER:
                self._tender(piece, tenders.get(piece.document_id))
            elif piece.source == OFFER:
                self._offer(piece, offers.get(piece.document_id))
            elif piece.source == REQUIREMENT:
                self._requirement(piece.ref, requirements.get(piece.ref))

    def _note(self, source, document_id, kind):
        self.documents[(source, document_id)] = {"origen": source, "documento": document_id,
                                                 "tipo": kind}

    def _tender(self, piece, row):
        if row is None:
            self.fail(R_MISSING, origen=TENDER, documento=piece.document_id)
            return
        self._note(TENDER, row["pk"], row["kind"])
        if row["procedure_id"] != self.procedure_id:
            self.fail(R_OTHER_PROCEDURE, origen=TENDER, documento=row["pk"])
        if row["kind"] not in TENDER_KINDS_ALLOWED:
            reason = R_COMPLIANCE if row["kind"] == COMPLIANCE else R_KIND
            self.fail(reason, origen=TENDER, documento=row["pk"], tipo=row["kind"])

    def _offer(self, piece, row):
        if row is None:
            self.fail(R_MISSING, origen=OFFER, documento=piece.document_id)
            return
        kind = row["kind"] or ""
        self._note(OFFER, row["pk"], kind)
        if row["offer__procedure_id"] != self.procedure_id:
            self.fail(R_OTHER_PROCEDURE, origen=OFFER, documento=row["pk"])
        if self.offer_id is None or row["offer_id"] != self.offer_id:
            self.fail(R_OTHER_OFFER, origen=OFFER, documento=row["pk"])
        if row["pk"] in self.suggested and kind != COMPLIANCE:
            self.fail(R_SUGGESTED, origen=OFFER, documento=row["pk"], tipo=kind)
        if kind not in OFFER_KINDS_ALLOWED:
            if kind == COMPLIANCE:
                reason = R_COMPLIANCE
            elif kind == TECHNICAL_REPORT:
                reason = R_TECHNICAL
            else:
                reason = R_KIND
            self.fail(reason, origen=OFFER, documento=row["pk"], tipo=kind)

    def _requirement(self, requirement_id, procedure_id):
        if procedure_id is None:
            self.fail(R_REQUIREMENT_MISSING, requisito=requirement_id)
        elif procedure_id != self.procedure_id:
            self.fail(R_REQUIREMENT_OTHER, requisito=requirement_id)
        elif self.offer_id is not None:
            self.external(requirement_id, flagged=False)

    def external(self, requirement_id, *, flagged):
        self.exclusions.update((R_CATALOG, R_MODEL))
        for entry in _external_requirement(requirement_id, self.offer_id, flagged):
            self.fail(entry.pop("motivo"), **entry)

    def cell(self, cell):
        self.exclusions.add(R_CELL)
        requirement_id = _pk(cell.requirement)
        self._requirement_of_cell(requirement_id)
        self.external(requirement_id, flagged=bool(cell.external_flagged))
        ids = {_pk(d) for d in (*cell.group_documents, *cell.cited_documents)}
        rows = {row["pk"]: row for row in OfferDocument.objects.filter(pk__in=ids).values(
            "pk", "kind", "offer_id")}
        for document_id in sorted(ids):
            row = rows.get(document_id)
            if row is None:
                self.fail(R_MISSING, origen="celda", documento=document_id)
            elif row["kind"] == COMPLIANCE or document_id in self.suggested:
                self.fail(R_CELL, documento=document_id)
            elif row["offer_id"] != self.offer_id:
                self.fail(R_OTHER_OFFER, origen="celda", documento=document_id)

    def _requirement_of_cell(self, requirement_id):
        procedure_id = Requirement.objects.filter(pk=requirement_id).values_list(
            "version__procedure_id", flat=True).first()
        if procedure_id is None:
            self.fail(R_REQUIREMENT_MISSING, requisito=requirement_id)
        elif procedure_id != self.procedure_id:
            self.fail(R_REQUIREMENT_OTHER, requisito=requirement_id)

    def fingerprints(self, text):
        by_document, unread = _compliance_fingerprints(self.procedure_id, self.suggested)
        sent = shingles(text)
        matched = {}
        for document_id, prints in by_document.items():
            common = len(sent & prints)
            if common:
                matched[document_id] = common
        for document_id in unread:
            self.fail(R_UNREAD, documento=document_id)
        for document_id, count in sorted(matched.items()):
            self.fail(R_FINGERPRINT, documento=document_id, secuencias=count)
        return {"palabras": FINGERPRINT_WORDS, "documentos_compliance": sorted(by_document),
                "secuencias_hoja": sum(len(p) for p in by_document.values()),
                "secuencias_pedido": len(sent), "coincidencias": sum(matched.values()),
                "sin_lectura": unread, "documentos_sugeridos": sorted(self.suggested)}

    def record(self, fingerprints):
        return {"version": VERSION, "documentos": list(self.documents.values()),
                "piezas": dict(sorted(self.sources.items())),
                "exclusiones": sorted(self.exclusions), "huellas": fingerprints,
                "motivos": self.reasons}


# --- Armado -----------------------------------------------------------------------------------


def assembled(system, messages):
    """El pedido armado como un solo texto: el sistema y los mensajes en orden, separados por un
    salto de línea. Es lo que se compara con las hojas (H-290-1)."""
    return "\n".join([system, *messages])


def _pieces(value, what):
    if isinstance(value, Piece):
        return [value]
    if isinstance(value, str):
        raise TypeError(f"{what}: cada texto entra con su origen (guard.instruction, "
                        "guard.offer_document...), nunca suelto.")
    pieces = list(value)
    for piece in pieces:
        if not isinstance(piece, Piece):
            raise TypeError(f"{what}: cada texto entra con su origen (guard.instruction, "
                            "guard.offer_document...), nunca suelto.")
    return pieces


def _messages(messages):
    out = []
    for message in messages:
        if isinstance(message, dict):
            role, content = message["role"], message["content"]
        else:
            role, content = message
        out.append((role, _pieces(content, "Un mensaje")))
    if not out:
        raise ValueError("Un pedido externo necesita al menos un mensaje.")
    return out


def build(*, stage, custom_id, procedure, system, messages, max_tokens, offer=None, cell=None,
          output_schema=None, model=None, effort=None, thinking=None, cache_system_ttl="1h",
          run_kind=None, run_id=None, instruction_name="", instruction_version="",
          instruction_sha256="", definitions_version="", definitions_sha256="",
          measurement=None, channel=None, user=None):
    """Arma un pedido externo pasando por todas las reglas. Devuelve `Admitted` (con el
    `ExternalPayload`) o `Blocked` (ya registrado como `bloqueado`, sin texto).

    `system`: una pieza o una lista de piezas; `messages`: lista de `(rol, piezas)` o de
    `{"role": ..., "content": piezas}`. Las piezas de cada parte se juntan tal cual, en orden.
    `procedure` (obligatorio), `offer` y `cell`: el procedimiento, la oferta y la celda del pedido
    (objetos o ids). `model`, `effort` y `thinking`, por omisión los de la etapa
    (`EXTERNAL_MODELS`, `EXTERNAL_EFFORT`, `EXTERNAL_THINKING`). `measurement`, `channel` y `user`
    van al registro del bloqueo. Un dato mal formado (texto suelto, rol desconocido) es
    `TypeError` o `ValueError`: no es un bloqueo, es un error de quien llama.
    """
    procedure_id = _pk(procedure)
    if procedure_id is None:
        raise ValueError("Un pedido externo es siempre de un procedimiento.")
    offer_id = _pk(offer)
    if cell is not None and offer_id is None:
        raise ValueError("Una celda es de una oferta: falta `offer`.")
    group = stage_group(stage)
    model = model or settings.EXTERNAL_MODELS.get(group)
    effort = effort or settings.EXTERNAL_EFFORT.get(group)
    thinking = thinking or settings.EXTERNAL_THINKING.get(group, "off")
    requirement_id = _pk(cell.requirement) if cell is not None else None

    system_pieces = _pieces(system, "El sistema")
    message_pieces = _messages(messages)
    every = system_pieces + [p for _, pieces in message_pieces for p in pieces]

    check = _Check(procedure_id, offer_id)
    check.pieces(every)
    if cell is not None:
        check.cell(cell)
    system_text = "".join(p.text for p in system_pieces)
    texts = [(role, "".join(p.text for p in pieces)) for role, pieces in message_pieces]
    # H-290-1: las secuencias salen del pedido armado entero (sistema, salto de línea y los
    # mensajes en orden), no de cada parte: un párrafo repartido entre partes se ve igual.
    fingerprints = check.fingerprints(assembled(system_text, [text for _, text in texts]))
    filter_record = check.record(fingerprints)

    ids = {"procedure_id": procedure_id, "offer_id": offer_id, "requirement_id": requirement_id,
           "run_kind": run_kind, "run_id": run_id, "instruction_name": instruction_name,
           "instruction_version": instruction_version, "instruction_sha256": instruction_sha256,
           "definitions_version": definitions_version,
           "definitions_sha256": definitions_sha256}
    if check.reasons:
        reasons = tuple(entry["motivo"] for entry in check.reasons)
        event = ledger.record_blocked(
            stage=stage, custom_id=custom_id, reason=reasons[0], reasons=reasons,
            filter=filter_record, procedure_id=procedure_id, offer_id=offer_id,
            requirement_id=requirement_id, run_kind=run_kind, run_id=run_id, model=model or "",
            parameters={"effort": effort, "thinking": thinking, "max_tokens": max_tokens},
            instruction={"nombre": instruction_name, "version": instruction_version,
                         "sha256": instruction_sha256},
            definitions=({"version": definitions_version, "sha256": definitions_sha256}
                         if definitions_version or definitions_sha256 else None),
            measurement=measurement, channel=channel, user=user)
        return Blocked(custom_id=custom_id, stage=stage, reason=reasons[0], reasons=reasons,
                       filter=filter_record, event_id=event.pk)

    payload = ExternalPayload.from_guard(
        stage=stage, model=model, max_tokens=max_tokens, system=system_text,
        messages=[{"role": role, "content": text} for role, text in texts],
        custom_id=custom_id, effort=effort, thinking=thinking, output_schema=output_schema,
        cache_system_ttl=cache_system_ttl, **ids)
    return Admitted(payload=payload, filter=filter_record)

