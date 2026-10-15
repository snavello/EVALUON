"""Medición de la evaluación asistida contra una lista esperada (REQ-052, REQ-053, REQ-054,
REQ-055, REQ-059, REQ-060; plan 004, "Cómo se cuenta" y "Umbrales"; ADR-0025, ADR-0038;
T-151).

Reutiliza lo que la 008 y la 003 ya resolvieron (`evaluon/offers/evaluation.py`,
`evaluon/tenders/evaluation.py`): la proporción con su intervalo de Wilson, la ubicación de un
ancla en una lectura, el armado de las ofertas en la base y la forma de la carpeta de la corrida
(`parametros.json`, `resultados.jsonl`, `resumen.md`, `resumen-publico.md`). Lo nuevo es lo que
compara la evaluación.

Dos formas de lista, las dos con visto bueno:

- `evaluacion-esperada.yaml` (caso chico, T-149): por oferta, un resultado esperado por par
  (`resultado`), con sus citas, el motivo de un «no determinado» y si debe traer pregunta.
- `dictamen-esperado.yaml` (caso-00, T-149): por oferta, lo que el dictamen dice de cada par
  (`dictamen`: cumple o no cumple) y su base (`oferta`, `externa`, `tecnica`). No trae la matriz
  ni los documentos: el procedimiento ya está cargado y el mapeo de `M-NNN` a la matriz sale de
  `fichas-esperadas.yaml` (`--fichas`), que además da los fragmentos y las copias equivalentes
  para REQ-054.

Cómo se cuenta (plan 004, "Cómo se cuenta"):

1. Coincidencia: el resultado vigente propuesto (sin decisión humana) es igual al esperado. Con
   un motivo esperado, el motivo también. En un par de base externa, «no determinado» por
   requisito externo coincide aunque el dictamen diga «cumple» (decisión 1 del responsable).
2. Contradicción: «cumple» donde se espera «no cumple», o al revés. Se informa aparte «no se
   encontró el documento» donde se espera «cumple».
3. Cita: toda propuesta «cumple» o «no cumple» tiene una cita de la oferta; toda cita de la
   oferta es igual al recorte del texto canónico de su documento y su página es la del recorte.
4. Fragmentos de la ficha (REQ-054): de las propuestas con cita de pares cuyo requisito tiene
   fragmentos esperados, las que citan el mismo documento y la misma página que uno de ellos
   (un documento equivalente cuenta como el mismo). Sin lista de fichas, los fragmentos son las
   citas de la lista de la evaluación.
5. Matriz (REQ-059): las ofertas evaluadas y un resultado vigente por par; el descarte propuesto
   (algún «no cumple») contra el esperado. El orden económico lo muestra la matriz de la
   evaluación (T-152) y se mide con ella.
6. Tiempo: por oferta, con los tokens por pedido y las páginas sin leer; informado, sin máximo.

Regla nueva (enmienda 2026-10-06, decisiones literales; REQ-052, REQ-053, REQ-061 a REQ-064;
T-170): la coincidencia se mira por el tipo de par, no por igualdad exacta del resultado.

- externo: «falta la hoja de compliance» coincide con lo que diga el dictamen; con la hoja cargada,
  el mismo resultado del dictamen;
- técnico: «pendiente del informe técnico» (o «no se encontró el documento» si lo esperado es que
  falta) **y** `documento_tecnico` y `renglon_ofertado` de `facts` iguales a la lista;
- ilegible: «no se pudo leer» con el documento y la página de la lista (`ilegible`);
- Portal: una cita del Portal del tipo y valor de la lista (`portal`);
- oferta: igual que antes.

Contradicciones: «cumple» contra «no cumple» del resultado, y un hecho técnico o un valor del
Portal opuestos a la lista (se informan aparte). La opinión técnica no es el resultado: se
compara con el dictamen y se informa. Sin contar quedan `duda`, `sin_dato`, `sin_corroborar`,
`sin_cita` y «no se encontró el documento» donde el dictamen dice «cumple»; su residuo se
informa aparte.

Medidas de la 015 (T-238; REQ-103, REQ-104, REQ-105; plan 015, "Criterio de aceptación numérico
y umbrales"):

- «No determinado» que no espera un documento ausente: sobre todas las celdas de la corrida (no
  sobre los pares de la lista), sin contar las que esperan el informe técnico o una hoja de
  compliance. Umbral del caso-00: 15 % o menos.
- Celdas del Portal: de las celdas cuyo dato del Portal coincide con lo que exige el pliego, las
  propuestas «cumple» con la cita del Portal (100 %); y las «cumple» con un dato que no coincide
  (0). Salen de los pares con `portal` de la lista (`coincide`: por omisión, si el resultado
  esperado es «cumple») y de un archivo aparte de celdas (`--celdas-portal`, por oferta y fila de
  la matriz validada).
- Forma de las preguntas: dirigidas a la Comisión (nunca al oferente), con el requisito, la
  conclusión y el texto de la oferta. Comprobación mecánica (`question_form`) más la plantilla
  local `muestra-preguntas.md`, con todas las preguntas, para leerlas de a una.
- Tiempo total y memoria de video máxima de lo registrado.
"""

import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

import yaml
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment import combine, criteria, not_applicable
from evaluon.assessment import models as am
from evaluon.assessment.citations import PageFinder
from evaluon.assessment.models import Channel as RunChannel
from evaluon.assessment.services import evaluate
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers import evaluation as sheets_measure
from evaluon.offers.evaluation import (
    ExpectedError,
    ExpectedNotApproved,
    MeasurementRefused,
    Verification,
)
from evaluon.offers.services import offers as offers_service
from evaluon.queries.evaluation import proportion_text
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.evaluation import (
    VIDEO_MAXIMUM_MIB,
    max_video_mib,
    ratio,
    video_memory,
)
from evaluon.tenders.proposal import quotes
from evaluon.tenders.services import procedures as tender_procedures
from evaluon.tenders.services.validation import _copy as copy_version
from evaluon.tenders.services.validation import latest_validated

__all__ = ["ExpectedError", "ExpectedNotApproved", "MeasurementRefused"]

OPERATION = "evaluon.assessment.evaluation.measure"
RUN_FILE_NAMES = ("parametros.json", "resultados.jsonl", "resumen.md", "resumen-publico.md")
CASE_00 = "caso-00"

# Resultado de la lista -> resultado del sistema.
RESULTS = {"cumple": am.Outcome.CUMPLE, "no_cumple": am.Outcome.NO_CUMPLE,
           "no_determinado": am.Outcome.NO_DETERMINADO,
           "no_se_encontro_documento": am.Outcome.SIN_DOCUMENTO}
BASES = ("oferta", "externa", "tecnica")
TECHNICAL_DOCUMENT = ("hay", "no_se_encontro")
OFFERED = ("si", "no", "no_aplica")
PAIR_TYPES = ("oferta", "externo", "tecnico", "ilegible", "portal")
# Motivos que quedan sin una causa concreta: el residuo que se informa aparte.
RESIDUE = (am.Doubt.DUDA, am.Doubt.SIN_DATO, am.Doubt.SIN_CORROBORAR)
DECISION_MARK = "decision_literal"
# Motivo de la lista -> motivo de la duda del sistema.
MOTIVES = {"falta_hoja_compliance": am.Doubt.EXTERNO, "pagina_ilegible": am.Doubt.LECTURA_INCOMPLETA,
           "lectura_incompleta": am.Doubt.LECTURA_INCOMPLETA,
           "pendiente_informe_tecnico": am.Doubt.PENDIENTE_INFORME_TECNICO,
           "no_se_pudo_leer": am.Doubt.NO_SE_PUDO_LEER, "en_portal": am.Doubt.EN_PORTAL,
           "falta_coincidencia": am.Doubt.FALTA_COINCIDENCIA}

# Umbrales escritos antes de medir (plan 004, "Umbrales"). Cada uno es `(mínimo, bloquea)` o,
# para los que cuentan fallas, `(máximo, bloquea)`. `None` = se informa sin tope.
THRESHOLDS_SMALL = {
    "match": (1.0, True), "contradictions": (0, True), "no_citation": (0, True),
    "literal": (1.0, True), "missing_document": (1.0, True), "questions": (1.0, True),
    "fragments": (None, False), "matrix": (1.0, True), "portal_literal": (1.0, True),
}
THRESHOLDS_CASE_00 = {
    "match": (0.80, True), "contradictions": (0, True), "no_citation": (0, True),
    "literal": (1.0, True), "missing_document": (None, False), "questions": (None, False),
    "fragments": (0.90, True), "matrix": (1.0, True), "portal_literal": (1.0, True),
}
MAXIMUMS = ("contradictions", "no_citation")

# Umbrales de la 015 (plan 015), escritos antes de medir. `undetermined` rige en el caso-00.
UNDETERMINED_MAXIMUM = 0.15
PORTAL_CUMPLE_MINIMUM = 1.0
PORTAL_WRONG_MAXIMUM = 0
QUESTIONS_FORM_MINIMUM = 1.0
# «No determinado» que espera un documento ausente: el informe técnico o la hoja de compliance.
WAITING_DOCUMENT = (am.Doubt.PENDIENTE_INFORME_TECNICO, am.Doubt.EXTERNO)
# T-256 (D3): el «externo» que decide el modelo no espera un documento: sale del numerador sin
# control. Solo espera el del catálogo o el de la lista.
MODEL_EXTERNAL_RULE = "externo_modelo"
QUESTIONS_SAMPLE_FILE = "muestra-preguntas.md"
# T-257: las celdas que decidió un criterio de la Comisión del 2026-10-12 (la ausencia verificada o
# el IVA del precio del Portal), para leerlas de a una (local: trae texto de la oferta).
CRITERIA_SAMPLE_FILE = "muestra-criterios.md"
# T-257 (constitución 1.4, P3): el «cumple» por ausencia tiene su fundamento sin cita de la oferta
# (los documentos leídos y que ninguno lo contradice): no es un «cumple» sin cita.
GROUNDED_WITHOUT_CITATION = (criteria.ABSENCE,)


def criteria_of(result):
    """Los criterios de la Comisión que aplicó la regla que decidió el resultado
    (`facts.criterios`, T-257), por nombre; lista vacía si ninguno."""
    facts = getattr(result, "facts", None) or {}
    return [c.get("nombre", "") for c in facts.get("criterios") or [] if isinstance(c, dict)]


def grounded_without_citation(names):
    """Si un «cumple» sin cita tiene su fundamento en un criterio (la ausencia verificada)."""
    return bool(set(names or ()) & set(GROUNDED_WITHOUT_CITATION))
# La pregunta se dirige al oferente según `combine.addresses_offeror`: una sola definición para el
# producto y para la medida (T-233b, D-235-1).
COMMISSION = re.compile(r"\bcomisi[oó]n\b", re.IGNORECASE)
# Las líneas que `combine.compose_question` rotula (T-235): el requisito, la conclusión del
# sistema y el texto de la oferta. Lo que dicen es del pliego, del sistema o de la oferta; lo que
# la pregunta le pide a alguien es el resto (la línea de cierre).
LABELED_LINE = re.compile(
    r"^\s*(?:requisito\s+\d+|conclusi[oó]n del sistema|texto de la oferta)\s*:", re.IGNORECASE)
NO_OFFER_TEXT = re.compile(
    r"no\s+(?:se\s+)?(?:encontr|consta|hay|figura)|sin\s+texto|ning[uú]n", re.IGNORECASE)
# Mínimos que piden «más de» (la spec: coincidencia de más del 80 % en el caso-00).
MORE_THAN = {CASE_00: ("match",)}

LABELS = {
    "match": "Coincidencia con el esperado según el tipo de par (REQ-052)",
    "contradictions": "Contradicciones (conclusiones erradas): «cumple» por «no cumple», «no "
                      "se encontró el documento» por «cumple», hecho técnico o dato del Portal "
                      "opuesto (REQ-052)",
    "no_citation": "«Cumple» o «no cumple» sin cita de la oferta ni del Portal (REQ-053)",
    "literal": "Citas de la oferta iguales al recorte del texto canónico (REQ-053)",
    "missing_document": "«No se encontró el documento» con la cita del pliego (REQ-060)",
    "questions": "Pregunta formulada donde falta un dato (REQ-055)",
    "fragments": "Propuestas que citan el fragmento de la ficha (REQ-054)",
    "matrix": "Ofertas evaluadas con un resultado por par (REQ-059)",
    "portal_literal": "Citas del Portal iguales al dato de la fila (REQ-062)",
}


def thresholds_for(case):
    """Los umbrales del caso de la lista (el caso-00 tiene los suyos)."""
    return THRESHOLDS_CASE_00 if case == CASE_00 else THRESHOLDS_SMALL


# --- Lectura de la lista esperada ---------------------------------------------------------------


@dataclass
class ExpectedPair:
    requirement: str            # id M-NNN
    result: str                 # resultado del sistema (`am.Outcome`)
    base: str                   # oferta, externa o tecnica
    doubt: str = ""             # motivo esperado de un «no determinado», ya traducido
    question: bool = False
    citations: list = field(default_factory=list)
    via: str = ""
    note: str = ""
    # Campos de la regla nueva (T-170). `None` = la lista no los trae.
    dictamen: str = ""                    # lo que dice el dictamen (cumple o no_cumple)
    technical_document: str | None = None  # hay o no_se_encontro (fila técnica)
    offered: str | None = None            # si, no o no_aplica (fila técnica)
    unreadable: dict | None = None        # {documento, pagina}
    portal: dict | None = None            # {tipo, valor}

    @property
    def kind(self):
        """El tipo de par que decide cómo se cuenta la coincidencia."""
        return pair_type(self)


def pair_type(pair):
    if pair.unreadable:
        return "ilegible"
    if pair.portal:
        return "portal"
    if pair.base == "tecnica":
        return "tecnico"
    return "externo" if pair.base == "externa" else "oferta"


@dataclass
class ExpectedOffer:
    bidder: str
    documents: list
    pairs: list
    discarded: str              # si, no o parcial
    discard: dict
    unreadable_pages: list
    total: float | None
    copies: dict                # archivo -> archivo del que es copia


@dataclass
class Expected:
    case: str
    path: Path
    sha256: str
    approval: str
    matrix: dict
    requirements: list          # entradas de `matriz.requisitos`, vacío en el dictamen
    offers: list
    order: dict
    kind: str                   # "evaluacion" o "dictamen"


def _text(data, name, where):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExpectedError(f"{where}: falta `{name}`")
    return value.strip()


def _pair(entry, where, kind):
    ident = _text(entry, "requisito", where)
    if kind == "dictamen":
        raw = entry.get("dictamen")
        if raw not in ("cumple", "no_cumple"):
            raise ExpectedError(f"{where}: {ident}: `dictamen` es `cumple` o `no_cumple`")
    else:
        raw = entry.get("resultado")
        if raw not in RESULTS:
            raise ExpectedError(f"{where}: {ident}: `resultado` no válido")
    base = entry.get("base") or "oferta"
    if base not in ("oferta", "externa", "tecnica"):
        raise ExpectedError(f"{where}: {ident}: `base` no válida")
    motive = entry.get("motivo") or ""
    if motive and motive not in MOTIVES:
        raise ExpectedError(f"{where}: {ident}: `motivo` no válido")
    citations = entry.get("citas") or []
    if kind == "evaluacion" and raw in ("cumple", "no_cumple") and not citations:
        raise ExpectedError(f"{where}: {ident}: un cumple o un no cumple lleva citas")
    technical_document = entry.get("documento_tecnico")
    if technical_document is not None and technical_document not in TECHNICAL_DOCUMENT:
        raise ExpectedError(f"{where}: {ident}: `documento_tecnico` es `hay` o `no_se_encontro`")
    offered = entry.get("renglon_ofertado")
    if offered is not None and offered not in OFFERED:
        raise ExpectedError(f"{where}: {ident}: `renglon_ofertado` es `si`, `no` o `no_aplica`")
    unreadable = entry.get("ilegible")
    if unreadable is not None and not (
            isinstance(unreadable, dict) and unreadable.get("documento")
            and isinstance(unreadable.get("pagina"), int)):
        raise ExpectedError(f"{where}: {ident}: `ilegible` lleva `documento` y `pagina`")
    portal = entry.get("portal")
    if portal is not None and not (
            isinstance(portal, dict) and portal.get("tipo") in am.PortalKind.values
            and str(portal.get("valor") or "").strip()):
        raise ExpectedError(f"{where}: {ident}: `portal` lleva `tipo` "
                            f"({', '.join(am.PortalKind.values)}) y `valor`")
    if portal is not None and not isinstance(portal.get("coincide", True), bool):
        raise ExpectedError(f"{where}: {ident}: `portal.coincide` es verdadero o falso")
    dictamen = entry.get("dictamen") if entry.get("dictamen") in ("cumple", "no_cumple") else ""
    return ExpectedPair(
        requirement=ident, result=RESULTS[raw], base=base, doubt=MOTIVES.get(motive, ""),
        question=str(entry.get("pregunta") or "").lower() in ("si", "sí", "true"),
        citations=list(citations), via=str(entry.get("via") or ""),
        note=str(entry.get("nota") or entry.get("fundamento") or ""), dictamen=dictamen,
        technical_document=technical_document, offered=offered, unreadable=unreadable,
        portal=portal)


def check_fields(expected):
    """Lo que la lista no trae y su tipo de par necesita (regla nueva, T-170): una fila técnica
    sin `documento_tecnico` y `renglon_ofertado`, un «no se pudo leer» sin `ilegible`. Devuelve
    los motivos, uno por par y oferta (vacío si la lista está completa). Los datos del
    oferente no figuran en el motivo (P4)."""
    problems = []
    for number, offer in enumerate(expected.offers, start=1):
        for pair in offer.pairs:
            where = f"oferta {number}, {pair.requirement}"
            if pair.base == "tecnica":
                for name, value in (("documento_tecnico", pair.technical_document),
                                    ("renglon_ofertado", pair.offered)):
                    if value is None:
                        problems.append(f"{where}: fila técnica sin `{name}`")
            if pair.doubt == am.Doubt.NO_SE_PUDO_LEER and not pair.unreadable:
                problems.append(f"{where}: «no se pudo leer» sin `ilegible` (documento y página)")
    return problems


def load_expected(path, *, require_approval=True):
    """Lee y valida la lista (`evaluacion-esperada.yaml` o `dictamen-esperado.yaml`). Lanza
    `ExpectedError`; sin visto bueno y con `require_approval`, `ExpectedNotApproved`. Un visto
    bueno «pendiente» no es un visto bueno."""
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
    approval = str(data.get("visto_bueno") or "").strip()
    if approval.lower().startswith("pendiente"):
        approval = ""
    if require_approval and not approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    matrix = data.get("matriz")
    if not isinstance(matrix, dict) or not matrix.get("procedimiento"):
        raise ExpectedError("falta `matriz.procedimiento`")
    offers_data = data.get("ofertas")
    if not isinstance(offers_data, list) or not offers_data:
        raise ExpectedError("faltan las `ofertas` de la lista")
    kind = "evaluacion" if matrix.get("requisitos") else "dictamen"
    requirements = matrix.get("requisitos") or []
    ids = {e.get("id") for e in requirements}
    offers = []
    for offer in offers_data:
        bidder = _text(offer, "oferente", "oferta")
        where = f"oferta «{bidder}»"
        documents = offer.get("documentos") or []
        copies = {d["archivo"]: d["copy_of"] for d in documents if d.get("copy_of")}
        pairs = [_pair(e, where, kind) for e in offer.get("requisitos") or []]
        if not pairs:
            raise ExpectedError(f"{where}: faltan los `requisitos`")
        seen = set()
        for pair in pairs:
            if pair.requirement in seen:
                raise ExpectedError(f"{where}: {pair.requirement} repetido")
            seen.add(pair.requirement)
            if ids and pair.requirement not in ids:
                raise ExpectedError(f"{where}: {pair.requirement}: requisito desconocido")
        offers.append(ExpectedOffer(
            bidder=bidder, documents=documents, pairs=pairs,
            discarded=str(offer.get("descartada") or "no").lower().replace("sí", "si"),
            discard=offer.get("descarte") or {},
            unreadable_pages=list(offer.get("paginas_no_legibles") or []),
            total=offer.get("total"), copies=copies))
    return Expected(case=str(data.get("caso") or ""), path=path,
                    sha256=hashlib.sha256(raw).hexdigest(), approval=approval, matrix=matrix,
                    requirements=requirements, offers=offers,
                    order=data.get("orden_economico") or {}, kind=kind)


@dataclass
class Fichas:
    """`fichas-esperadas.yaml` leída para REQ-054: los requisitos de la matriz, los fragmentos
    por oferente y las copias equivalentes."""

    requirements: list
    fragments: dict             # oferente -> [ {requisito, documento, pagina} ]
    equivalents: dict           # oferente -> {archivo: archivo al que equivale}


def load_fichas(path):
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(f"no se puede leer la lista de fichas ({error.__class__.__name__})")
    if not isinstance(data, dict) or not isinstance(data.get("ofertas"), list):
        raise ExpectedError("la lista de fichas no tiene la forma esperada")
    fragments, equivalents = {}, {}
    for offer in data["ofertas"]:
        bidder = _text(offer, "oferente", "oferta de la lista de fichas")
        fragments[bidder] = [
            {"requisito": f["requisito"], "documento": f["documento"], "pagina": f["pagina"]}
            for f in offer.get("fragmentos") or []]
        equivalents[bidder] = {e["archivo"]: e["equivale_a"]
                               for e in offer.get("equivalentes") or []}
    return Fichas(requirements=(data.get("matriz") or {}).get("requisitos") or [],
                  fragments=fragments, equivalents=equivalents)


# --- Armado del caso chico en la base -------------------------------------------------------------


def _descendant(key, header):
    return key == header or key.startswith((f"{header}/", f"{header}."))


def _create_matrix(user, procedure, document, entries):
    """La matriz validada del caso: un requisito por entrada de la lista, con su cita ubicada
    en un tramo del pliego. Una fila técnica lleva el encabezado del renglón y todas sus
    cláusulas (`sec-iii/1` y `sec-iii/1.1`, ...): la de la 008 solo trae el encabezado."""
    reading = document.readings.order_by("-sequence").first()
    segments = list(reading.segments.order_by("order"))
    with transaction.atomic():
        version = m.MatrixVersion.objects.create(
            procedure=procedure, number=1, status=m.VersionStatus.DRAFT, created_by=user)
        for number, entry in enumerate(entries, start=1):
            technical = entry["clase"] == "tecnico"
            requirement = m.Requirement.objects.create(
                version=version, number=number, category=entry["clase"],
                items=[entry["renglon"]] if technical else [],
                origin=m.RequirementOrigin.AGREGADO, state=m.RequirementState.CONFIRMADO)
            if technical:
                header = next((item["key"] for item in reading.items
                               if item["number"] == entry["renglon"]), None)
                chosen = [s for s in segments if _descendant(s.key, header)] if header else []
                if not chosen:
                    raise MeasurementRefused(
                        f"El renglón {entry['renglon']} no está en el pliego del caso.")
                for order, segment in enumerate(chosen, start=1):
                    m.RequirementQuote.objects.create(
                        requirement=requirement, order=order, segment=segment,
                        char_start=segment.char_start, char_end=segment.char_end,
                        text=segment.text, scope=m.QuoteScope.PROPIA)
            else:
                placed = None
                for segment in segments:
                    span = quotes.locate(segment.text, entry["cita"])
                    if span is not None:
                        placed = (segment, quotes.absolute(segment, span))
                        break
                if placed is None:
                    raise MeasurementRefused(
                        f"La cita de {entry['id']} no está en el pliego del caso.")
                segment, (start, end) = placed
                m.RequirementQuote.objects.create(
                    requirement=requirement, order=1, segment=segment, char_start=start,
                    char_end=end, text=reading.canonical_text[start:end])
        version.status = m.VersionStatus.VALIDATED
        version.validated_at = timezone.now()
        version.validated_by = user
        version.save(update_fields=["status", "validated_at", "validated_by"])
    return version


def build_case(user, expected, folder=None):
    """Arma el caso de la lista en la base y devuelve `(procedimiento, {oferente: oferta})`.
    Idempotente. Es un armado de datos de prueba, no una validación de la Comisión."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    if expected.kind != "evaluacion":
        raise MeasurementRefused("Solo la lista de evaluación del caso chico se arma en la base.")
    folder = Path(folder) if folder else expected.path.parent
    matrix = expected.matrix
    number = matrix["procedimiento"]
    procedure = m.Procedure.objects.filter(number=number).first()
    if procedure is None:
        registration = tender_procedures.register_procedure(
            user, number=number, procedure_type=matrix.get("tipo") or "Caso de medición",
            subject=matrix.get("objeto") or number,
            authorization_date=matrix.get("fecha_autorizacion") or date(2026, 1, 15),
            channel=Channel.COMMAND)
        procedure = registration.procedure
        pliego = matrix.get("pliego")
        if not pliego:
            raise MeasurementRefused("La lista no trae `matriz.pliego` para armar el caso.")
        document = sheets_measure._read_pliego(user, procedure, folder, pliego)
        _create_matrix(user, procedure, document, matrix["requisitos"])
    offers = {}
    for offer_expected in expected.offers:
        offer = procedure.offers.filter(bidder=offer_expected.bidder).first()
        if offer is None:
            offer = offers_service.register_offer(
                user, procedure, bidder=offer_expected.bidder, channel=Channel.COMMAND)
        for spec in offer_expected.documents:
            data = (folder / spec["archivo"]).read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            if sha256 != spec["sha256"]:
                raise MeasurementRefused(
                    f"La huella de {spec['archivo']} no coincide con la lista.")
            if offer.documents.filter(file_sha256=sha256).exists():
                continue
            loaded = offers_service.load_document(
                user, offer, data=data, file_name=spec["archivo"], channel=Channel.COMMAND)
            sheets_measure._run_now(loaded.job)
        offers[offer_expected.bidder] = offer
    return procedure, offers


# --- Comprobación de la lista contra las lecturas -------------------------------------------------


def verify_expected(expected, offers, folder=None):
    """Comprueba la lista contra las lecturas, sin usar el modelo: la huella de cada documento,
    que cada ancla de cada cita esté en su página y que cada página no legible lo sea. Con la
    lista del dictamen comprueba la huella del dictamen si el archivo está."""
    result = Verification()
    anchors = pages = documents = 0
    for entry in expected.offers:
        offer = offers.get(entry.bidder)
        if offer is None:
            result.fail("una oferta de la lista no está cargada")
            continue
        for spec in entry.documents:
            if spec.get("copy_of"):
                # Una copia byte a byte no se carga (la carga rechaza el duplicado): vale el
                # documento del que es copia, con la misma huella.
                original = next((d for d in entry.documents
                                 if d["archivo"] == spec["copy_of"]), None)
                if original is None or original["sha256"] != spec["sha256"]:
                    result.fail(f"{spec['archivo']}: la huella no es la de su original")
                continue
            document, reading = sheets_measure._reading_of(offer, spec["archivo"])
            documents += 1
            if document is None or document.file_sha256 != spec["sha256"]:
                result.fail(f"{spec['archivo']}: la huella no coincide o no está cargado")
            elif reading is None:
                result.fail(f"{spec['archivo']}: todavía no se leyó")
        for pair in entry.pairs:
            for cite in pair.citations:
                _, reading = sheets_measure._reading_of(offer, cite["documento"])
                anchors += 1
                if reading is None or sheets_measure.locate_anchor(
                        reading, cite["pagina"], cite["ancla"]) is None:
                    result.fail(f"{pair.requirement}: el ancla no está en la página "
                                f"{cite['pagina']} de {cite['documento']}")
        # Las páginas no legibles de la oferta y las de los pares `ilegible` (T-170).
        listed_pages = list(entry.unreadable_pages)
        seen_pages = {(u["documento"], u["pagina"]) for u in listed_pages}
        from_pairs = [p.unreadable for p in entry.pairs if p.unreadable
                      and (p.unreadable["documento"], p.unreadable["pagina"]) not in seen_pages]
        for unreadable in listed_pages + from_pairs:
            _, reading = sheets_measure._reading_of(offer, unreadable["documento"])
            pages += 1
            listed = reading is not None and any(
                p["page"] == unreadable["pagina"]
                for p in reading.report.get("unread", []) + reading.report.get(
                    "low_confidence", []) + reading.report.get("handwritten", []))
            if not listed:
                result.fail(f"{unreadable['documento']} página {unreadable['pagina']}: no "
                            "está en las listas de no leídas ni de baja confianza")
    result.counts = {"documents": documents, "anchors": anchors, "unreadable_pages": pages}
    result.lines.insert(0, f"Documentos {documents}, anclas {anchors}, páginas no legibles "
                           f"{pages}: " + ("sin fallas" if result.ok else "con fallas"))
    return result


# --- Medición ---------------------------------------------------------------------------------------


def _name(path):
    return PurePosixPath(str(path).replace("\\", "/")).name


def _number(token):
    """Un número escrito a la argentina («26.750,00») o sin separadores, como `Decimal`."""
    token = token.strip(".,")
    if "," in token:
        whole, _, fraction = token.rpartition(",")
        token = f"{whole.replace('.', '')}.{fraction}"
    elif token.count(".") > 1 or (token.count(".") == 1 and len(token.split(".")[1]) == 3):
        token = token.replace(".", "")
    try:
        return Decimal(token).normalize()
    except InvalidOperation:
        return None


def _numbers(text):
    found = {_number(t) for t in re.findall(r"\d[\d.,]*", str(text or ""))}
    found.discard(None)
    return found


def portal_value_in(kind, text, value):
    """Si el texto de una cita del Portal trae `value` (un monto, un total, una cotización, o
    un CUIT por sus dígitos)."""
    if kind == am.PortalKind.CUIT:
        wanted = re.sub(r"\D", "", str(value))
        return bool(wanted) and wanted in re.sub(r"\D", "", str(text or ""))
    if kind == am.PortalKind.COTIZACION:
        # T-175 (H-3): de «Renglón N: precio P, cantidad Q» solo cuenta el precio.
        prices = re.findall(r"precio\s+(\d[\d.,]*)", str(text or ""))
        if prices:
            text = " ".join(prices)
    wanted = _numbers(value)
    return bool(wanted) and wanted <= _numbers(text)


def _portal_cites(result):
    return list(result.citations.filter(kind=am.CitationKind.PORTAL)) if result.pk else []


def _portal_check(pair, result):
    """`(coincide, opuesto)`: hay una cita del Portal del tipo esperado con el valor esperado, o
    solo con otro valor (opuesto al dictamen)."""
    same_kind = [c for c in _portal_cites(result) if c.portal_kind == pair.portal["tipo"]]
    if any(portal_value_in(c.portal_kind, c.text, pair.portal["valor"]) for c in same_kind):
        return True, False
    return False, bool(same_kind)


def _facts_check(pair, facts):
    """`(iguales, opuestos)` de los dos hechos de una fila técnica contra la lista."""
    found_doc = facts.get("documento_tecnico")
    found_offered = facts.get("renglon_ofertado", "no_aplica")
    equal = (found_doc == pair.technical_document and found_offered == pair.offered)
    opposed = []
    if {found_doc, pair.technical_document} == set(TECHNICAL_DOCUMENT):
        opposed.append(f"documento_tecnico: esperado {pair.technical_document}, "
                       f"obtenido {found_doc}")
    if {found_offered, pair.offered} == {"si", "no"}:
        opposed.append(f"renglon_ofertado: esperado {pair.offered}, obtenido {found_offered}")
    return equal, opposed


def _unreadable_equal(pair, facts):
    """El documento por `archivo` (o `documento`, si no trae archivo) y la página por `pagina` o
    por `paginas`; el título del documento no sirve para comparar (T-166)."""
    found = facts.get("ilegible") or {}
    wanted = _name(pair.unreadable["documento"])
    names = {_name(found.get("archivo") or found.get("documento") or "")}
    pages = {found.get("pagina"), *(found.get("paginas") or [])}
    return wanted in names and pair.unreadable["pagina"] in pages


def _match(pair, result):
    """Si el resultado propuesto coincide con el esperado, según el tipo del par (regla nueva:
    no es una igualdad exacta del resultado)."""
    kind = pair.kind
    facts = result.facts or {}
    if not_applicable.is_not_applicable(result):
        # «No aplica» no es «cumple»: no coincide con un dictamen que espera «cumple»; se informa
        # aparte y queda fuera de la cuenta de coincidencias (T-240, O-240-4).
        return False
    if kind == "ilegible":
        return (result.outcome == am.Outcome.NO_DETERMINADO
                and result.doubt == am.Doubt.NO_SE_PUDO_LEER and _unreadable_equal(pair, facts))
    if kind == "portal":
        # T-256 (D1): el par del Portal coincide solo si el resultado es el esperado; una cita
        # del Portal con el valor no alcanza.
        return _portal_check(pair, result)[0] and result.outcome == pair.result
    if kind == "tecnico":
        # Regla de la spec (enmienda 2026-10-06, "Medición"): «pendiente del informe técnico»
        # coincide si los dos hechos son iguales a la lista, también cuando el documento no se
        # encontró (T-175); «no se encontró el documento» sigue coincidiendo en ese caso.
        outcome_ok = (result.outcome == am.Outcome.NO_DETERMINADO
                      and result.doubt == am.Doubt.PENDIENTE_INFORME_TECNICO)
        if pair.technical_document == "no_se_encontro":
            outcome_ok = outcome_ok or result.outcome == am.Outcome.SIN_DOCUMENTO
        return outcome_ok and _facts_check(pair, facts)[0]
    if result.outcome != pair.result:
        # Decisión 1 del responsable: lo externo sin hoja de compliance coincide con lo que
        # diga el dictamen (la abstención correcta, P3 y P9).
        return (kind == "externo" and result.outcome == am.Outcome.NO_DETERMINADO
                and result.doubt == am.Doubt.EXTERNO)
    return not pair.doubt or result.doubt == pair.doubt


def _reference(pair):
    """Lo que concluye el dictamen: en una fila técnica, su `dictamen`; si no, el resultado."""
    return pair.dictamen if pair.base == "tecnica" and pair.dictamen else pair.result


def _contradiction(pair, result):
    """Una conclusión errada: «cumple» contra «no cumple» y, desde T-256 (D2), «no se encontró el
    documento» donde el dictamen dice «cumple» (salvo que la lista espere que falte)."""
    reference = _reference(pair)
    if {reference, result.outcome} == {am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE}:
        return True
    return (reference == am.Outcome.CUMPLE and result.outcome == am.Outcome.SIN_DOCUMENTO
            and not _match(pair, result))


def _fact_contradictions(pair, result):
    """Los hechos técnicos y el valor del Portal opuestos a la lista (se informan aparte)."""
    kind = pair.kind
    if kind == "tecnico" and pair.technical_document is not None:
        return _facts_check(pair, result.facts or {})[1]
    if kind == "portal" and _portal_check(pair, result)[1]:
        return [f"portal {pair.portal['tipo']}: valor distinto del esperado"]
    return []


def _canonical_document(name, equivalents):
    seen = set()
    while name in equivalents and name not in seen:
        seen.add(name)
        name = equivalents[name]
    return name


def _portal_cite_is_literal(cite, offer):
    """La cita del Portal es igual al dato de su fila: el monto, el total, el precio o el CUIT
    de la fila de la que sale (`portal_item`) está en el texto de la cita (T-170)."""
    item, kind = cite.portal_item, cite.portal_kind
    if item is None or not cite.text:
        return False
    if kind == am.PortalKind.GARANTIA:
        values = [g.amount for g in item.guarantees.all()]
    elif kind == am.PortalKind.TOTAL:
        values = [d.total for d in item.offer_data.all()]
    elif kind == am.PortalKind.CUIT:
        return any(portal_value_in(kind, cite.text, d.cuit) for d in item.offer_data.all())
    else:
        from evaluon.portal.models import PortalQuote
        quotes = PortalQuote.objects.filter(offer=offer, line__item=item)
        values = [q.price for q in (quotes or PortalQuote.objects.filter(offer=offer))]
    return any(v is not None and portal_value_in(kind, cite.text, v) for v in values)


# --- Medidas de la 015 (T-238) --------------------------------------------------------------------


@dataclass
class PortalCell:
    """Una celda cuyo dato está en el Portal: la oferta y la fila de la matriz validada, el tipo y
    el valor del dato, y si ese dato coincide con lo que exige el pliego."""

    offer: int
    row: int
    kind: str
    value: str
    matches: bool


@dataclass
class PortalCells:
    path: Path
    sha256: str
    approval: str
    procedure: str
    cells: list


def load_portal_cells(path, *, require_approval=True):
    """Lee el archivo de celdas del Portal (`--celdas-portal`): `procedimiento`, `visto_bueno` y
    `celdas` con `oferta`, `fila`, `tipo`, `valor` y `coincide`. Lanza `ExpectedError`; sin visto
    bueno y con `require_approval`, `ExpectedNotApproved`."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
    except OSError as error:
        raise ExpectedError(f"no se puede leer la lista de celdas: {error.__class__.__name__}")
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(
            f"la lista de celdas no se puede leer como YAML ({error.__class__.__name__})")
    if not isinstance(data, dict) or not isinstance(data.get("celdas"), list):
        raise ExpectedError("la lista de celdas no tiene la forma esperada")
    approval = str(data.get("visto_bueno") or "").strip()
    if approval.lower().startswith("pendiente"):
        approval = ""
    if require_approval and not approval:
        raise ExpectedNotApproved("la lista de celdas no tiene visto bueno: no se usa")
    cells, seen = [], set()
    for entry in data["celdas"]:
        if not (isinstance(entry, dict) and isinstance(entry.get("oferta"), int)
                and isinstance(entry.get("fila"), int)):
            raise ExpectedError("una celda del Portal lleva `oferta` y `fila` numéricas")
        where = f"oferta {entry['oferta']}, fila {entry['fila']}"
        if entry.get("tipo") not in am.PortalKind.values or not str(entry.get("valor") or "").strip():
            raise ExpectedError(f"{where}: lleva `tipo` ({', '.join(am.PortalKind.values)}) y "
                                "`valor`")
        if not isinstance(entry.get("coincide"), bool):
            raise ExpectedError(f"{where}: `coincide` es verdadero o falso")
        if (entry["oferta"], entry["fila"]) in seen:
            raise ExpectedError(f"{where}: celda repetida")
        seen.add((entry["oferta"], entry["fila"]))
        cells.append(PortalCell(offer=entry["oferta"], row=entry["fila"], kind=entry["tipo"],
                                value=str(entry["valor"]).strip(), matches=entry["coincide"]))
    return PortalCells(path=path, sha256=hashlib.sha256(raw).hexdigest(), approval=approval,
                       procedure=str(data.get("procedimiento") or ""), cells=cells)


def verify_portal_cells(portal_cells, procedure):
    """Comprueba, sin el modelo, que cada celda nombre una oferta del procedimiento y una fila
    de su última matriz validada. Devuelve las líneas del informe y si no hay fallas."""
    version = latest_validated(procedure)
    offers = {o.number for o in procedure.offers.all()}
    rows = {r.number for r in version.requirements.all()} if version else set()
    problems = [f"oferta {c.offer}, fila {c.row}: no está en el procedimiento o en su matriz "
                "validada" for c in portal_cells.cells
                if c.offer not in offers or c.row not in rows]
    matching = sum(c.matches for c in portal_cells.cells)
    lines = [f"Celdas del Portal: {len(portal_cells.cells)} ({matching} con el dato que "
             f"coincide, {len(portal_cells.cells) - matching} sin coincidir); visto bueno: "
             f"{portal_cells.approval or 'pendiente'}"]
    lines += [f"BLOQUEA: {p}" for p in problems]
    return lines, not problems


def waits_for_document(result, external=frozenset()):
    """Si un «no determinado» espera un documento ausente (REQ-104): el informe técnico, o la hoja
    de compliance de un requisito externo del catálogo o de la lista (`external`, los requisitos
    de los pares de base externa). El «externo» que marca el modelo no se descuenta (T-256, D3)."""
    if result.doubt == am.Doubt.PENDIENTE_INFORME_TECNICO:
        return True
    if result.doubt != am.Doubt.EXTERNO:
        return False
    return ((result.facts or {}).get("regla") != MODEL_EXTERNAL_RULE
            or result.requirement_id in external)


def cell_counts(run, external=frozenset(), excluded=frozenset()):
    """Las celdas de una evaluación y cuántas son «no determinado»; de esas, cuántas esperan un
    documento ausente (informe técnico u hoja de compliance) y no cuentan (REQ-104). `external`
    son los requisitos externos de la lista; `excluded`, los de las filas que la medida excluye
    (archivo de exclusión de celdas, T-256): no se cuentan y se informan aparte."""
    total = undetermined = waiting = inapplicable = model_external = left_out = 0
    for result in run.results.all():
        if excluded and result.requirement_id in excluded:
            left_out += 1
            continue
        if not_applicable.is_not_applicable(result):
            inapplicable += 1   # se cuentan aparte: ni «cumple» ni «no determinado» (T-240)
            continue
        total += 1
        if result.outcome == am.Outcome.NO_DETERMINADO:
            undetermined += 1
            waits = waits_for_document(result, external)
            waiting += waits
            model_external += result.doubt == am.Doubt.EXTERNO and not waits
    return {"total": total, "undetermined": undetermined, "waiting_document": waiting,
            "not_applicable": inapplicable, "model_external": model_external,
            "excluded": left_out}


def result_problem(result, *, with_question, cited):
    """La forma de una celda guardada contra las tres salidas (REQ-120; `combine.cell_problem`):
    `with_question` es si tiene la pregunta a la Comisión (suya o una abierta del par) y `cited` si
    tiene citas de la oferta o del Portal. Devuelve `""` o el nombre de lo que falla."""
    return combine.cell_problem(
        result.outcome, doubt=result.doubt, has_question=with_question, has_citation=cited,
        facts=result.facts, explanation=result.explanation)


def three_outputs(run, excluded=frozenset()):
    """Las tres salidas de una evaluación (REQ-120; T-277, umbral 9): cuántas celdas son «no se
    encontró el documento» sin pregunta y cuántas «no determinado» sin pregunta ni documento nombrado;
    de cada una, los requisitos. `problems` suma cualquier otra celda que no cumple una de las tres
    formas («cumple» sin fundamento, «no cumple» sin cita ni regla, «no determinado» sin motivo).
    Las filas de `excluded` (sus requisitos, como en `cell_counts`) no se cuentan."""
    with_question = set(am.Question.objects.filter(result__run=run).values_list(
        "result_id", flat=True))
    # Una pregunta abierta de una evaluación anterior del par sigue valiendo: la evaluación nueva no
    # abre otra encima (`evaluate._save_pair`).
    open_pairs = set(am.Question.objects.filter(offer=run.offer, answers__isnull=True)
                     .values_list("requirement_id", flat=True))
    cited = set(am.Citation.objects.filter(
        result__run=run, kind__in=(am.CitationKind.OFERTA, am.CitationKind.PORTAL))
        .values_list("result_id", flat=True))
    out = {"cells": 0, "sin_documento": 0, "no_determinado": 0, "sin_documento_sin_pregunta": [],
           "no_determinado_sin_nombrar": [], "problems": []}
    for result in run.results.select_related("requirement"):
        if excluded and result.requirement_id in excluded:
            continue
        out["cells"] += 1
        out["sin_documento"] += result.outcome == am.Outcome.SIN_DOCUMENTO
        out["no_determinado"] += result.outcome == am.Outcome.NO_DETERMINADO
        asked = result.pk in with_question or result.requirement_id in open_pairs
        problem = result_problem(result, with_question=asked, cited=result.pk in cited)
        if not problem:
            continue
        number = result.requirement.number
        if problem == combine.PROBLEM_NO_QUESTION:
            out["sin_documento_sin_pregunta"].append(number)
        elif problem == combine.PROBLEM_UNNAMED:
            out["no_determinado_sin_nombrar"].append(number)
        else:
            out["problems"].append((number, problem))
    return out


def portal_cell_record(result, kind, value, matches):
    """Una celda del Portal medida (REQ-103): si la propuesta es «cumple» con la cita del Portal
    del dato esperado, y si es «cumple» con un dato que no coincide (el esperado no coincide con
    el pliego, o la cita del Portal trae otro valor)."""
    cites = [c for c in _portal_cites(result) if c.portal_kind == kind]
    with_value = any(portal_value_in(kind, c.text, value) for c in cites)
    inapplicable = not_applicable.is_not_applicable(result)
    cumple = result.outcome == am.Outcome.CUMPLE and not inapplicable
    return {"tipo_portal": kind, "coincide_dato": matches,
            "obtenido": not_applicable.outcome_key(result), "no_aplica": inapplicable,
            "motivo": result.doubt, "regla": (result.facts or {}).get("regla", ""),
            "cumple_con_cita_portal": cumple and with_value,
            "cumple_con_dato_distinto": cumple and (not matches or (bool(cites) and not with_value))}


def _words(text):
    return " ".join(re.findall(r"\w+", (text or "").casefold()))


def _starts_with(snippet, text, size=6):
    """Si las primeras `size` palabras de `snippet` están en `text` (sin mayúsculas ni signos)."""
    head = " ".join(_words(snippet).split()[:size])
    return bool(head) and head in _words(text)


CONCLUSION = re.compile(r"conclu|propon|propus|no\s+pudo|no\s+se\s+pudo|sin\s+corroborar",
                        re.IGNORECASE)


def question_form(text, *, requirement_text, requirement_number, outcome_label, doubt_label,
                  offer_texts):
    """La forma de una pregunta a la Comisión (REQ-105), comprobación mecánica: dirige a la
    Comisión (no al oferente), dice el requisito (su cita del pliego o su número), la conclusión
    (el resultado o el motivo del sistema) y el texto de la oferta (o que no hay). Los patrones
    son constantes del módulo. Devuelve cada punto y `conforme`; `nombra_comision` se informa."""
    requirement_ok = _starts_with(requirement_text, text) or bool(re.search(
        rf"\brequisito\s+(?:n\w*\s*)?{requirement_number}\b", text or "", re.IGNORECASE))
    normal = _words(text)
    conclusion_ok = any(label and _words(label) in normal
                        for label in (outcome_label, doubt_label)) or bool(CONCLUSION.search(text))
    text_ok = (any(_starts_with(t, text) for t in offer_texts) if offer_texts
               else bool(NO_OFFER_TEXT.search(text or "")))
    # Lo que la pregunta cita del pliego o de la oferta no cuenta: «El oferente deberá…» es del
    # requisito, no un pedido de la pregunta.
    own = "\n".join(line for line in (text or "").splitlines()
                    if not LABELED_LINE.match(line))
    own = re.sub(r"«[^»]*»", " ", own)
    for quoted in [requirement_text, *offer_texts]:
        own = own.replace(quoted, " ") if quoted else own
    directed = not combine.addresses_offeror(own)
    return {"requisito_ok": requirement_ok, "conclusion_ok": conclusion_ok, "texto_ok": text_ok,
            "dirigida_ok": directed, "nombra_comision": bool(COMMISSION.search(text or "")),
            "conforme": requirement_ok and conclusion_ok and text_ok and directed}


def question_records(run, excluded_rows=frozenset()):
    """Las preguntas de una evaluación con su forma comprobada, sin las de las filas excluidas
    (T-256). El texto de la pregunta, del requisito y de la oferta va en `detalle` (local, no al
    resumen público)."""
    records = []
    questions = am.Question.objects.filter(result__run=run).select_related(
        "requirement", "result", "offer").order_by("result_id", "id")
    for question in questions:
        if question.requirement.number in excluded_rows:
            continue
        result = question.result
        first = question.requirement.quotes.order_by("order").first()
        requirement_text = first.text if first else ""
        # El texto que motiva la pregunta: lo citado de la oferta o, si solo hay, el dato del
        # Portal (`combine._evidence`).
        offer_texts = list(result.citations.filter(
            kind__in=(am.CitationKind.OFERTA, am.CitationKind.PORTAL))
            .order_by("kind", "order").values_list("text", flat=True))
        doubt = am.Doubt(result.doubt).label if result.doubt else ""
        form = question_form(
            question.text, requirement_text=requirement_text,
            requirement_number=question.requirement.number,
            outcome_label=not_applicable.result_label(result), doubt_label=doubt,
            offer_texts=offer_texts)
        records.append({
            "oferta": question.offer.number, "fila": question.requirement.number,
            "resultado_pk": result.pk, "obtenido": result.outcome, "motivo": result.doubt,
            **form, "detalle": {"pregunta": question.text, "requisito": requirement_text,
                                "citas_oferta": offer_texts}})
    return records


def thresholds_015(total, case=None, video=None):
    """Las medidas de la 015 contra su umbral: `[(nombre, medido, cumple)]`. Los umbrales están en
    el plan 015 y en las constantes del módulo. Solo se evalúa lo que la corrida mide."""
    rows = []
    cells = total["cells"]
    if case == CASE_00 and cells["total"]:
        rows.append(("«No determinado» sin las que esperan un documento ausente (REQ-104)",
                     proportion_text(cells["ratio"]),
                     cells["ratio"]["rate"] <= UNDETERMINED_MAXIMUM + 1e-9))
    portal = total["portal_cumple"]
    if portal["total"] or total["portal_cells"]["total"]:
        rows.append(("Celdas del Portal que coinciden, propuestas «cumple» con la cita del Portal "
                     "(REQ-103)", proportion_text(portal),
                     portal["total"] == 0 or portal["rate"] >= PORTAL_CUMPLE_MINIMUM - 1e-9))
        rows.append(("Celdas «cumple» con un dato del Portal que no coincide (REQ-103)",
                     str(len(total["portal_wrong"])),
                     len(total["portal_wrong"]) <= PORTAL_WRONG_MAXIMUM))
    forms = total["questions_form"]
    if forms["total"]:
        rows.append(("Preguntas con la forma de REQ-105 (dirigida a la Comisión, con requisito, "
                     "conclusión y texto)", proportion_text(forms),
                     forms["rate"] >= QUESTIONS_FORM_MINIMUM - 1e-9))
    memory = max_video_mib(video)
    if memory is not None:
        rows.append(("Memoria de video máxima registrada", f"{memory} MiB",
                     memory <= VIDEO_MAXIMUM_MIB))
    return rows


def thresholds_016(total):
    """Las tres salidas contra su umbral (T-277, umbral 9 del plan 016, REQ-120): 0 «no se encontró
    el documento» sin pregunta y todo «no determinado» con la pregunta o el documento nombrado.
    `[(nombre, medido, cumple)]`; vacío si la corrida no trae la cuenta."""
    found = total.get("three_outputs")
    if not found or not found["cells"]:
        return []
    undetermined = found["no_determinado"]
    unnamed = len(found["no_determinado_sin_nombrar"])
    return [
        ("«No se encontró el documento» sin pregunta (REQ-120)",
         f"{len(found['sin_documento_sin_pregunta'])} de {found['sin_documento']}",
         not found["sin_documento_sin_pregunta"]),
        ("«No determinado» con la pregunta o el documento nombrado (REQ-120)",
         f"{undetermined - unnamed} de {undetermined}", not unnamed),
        ("Otras celdas que no cumplen una de las tres formas (REQ-120)",
         str(len(found["problems"])), not found["problems"])]


# --- Medida honesta (T-256; REQ-103, REQ-104, REQ-107; mesa de comité del 2026-10-12) ------------
#
# Exactitud por celda contra las decisiones de la Comisión de prueba (`celdas-comision-*.yaml`),
# exclusión de las filas agregadas solo para la medida (`exclusiones-celdas-*.yaml`) y el
# recálculo, sin GPU, de una corrida ya guardada (`celdas-todas.txt` y `resultados.jsonl`).

# Resultado de la Comisión -> clave con que se cuenta el resultado del sistema.
COMMISSION_RESULTS = {"cumple": am.Outcome.CUMPLE, "no_cumple": am.Outcome.NO_CUMPLE,
                      "no_aplica": not_applicable.KEY,
                      "no_se_encontro_documento": am.Outcome.SIN_DOCUMENTO,
                      # T-271 (REQ-118): en la verdad ampliada un «no determinado» del sistema
                      # contra un «no determinado» de la verdad es exacto.
                      "no_determinado": am.Outcome.NO_DETERMINADO}
EXACT_SAMPLE_FILE = "muestra-exactas.md"
CELLS_FILE = "celdas-todas.txt"
NOT_APPLICABLE_RULE = "forma_garantia_no_elegida"
PORTAL_RULE = "portal_cumple"
CELLS_FILE_PORTAL_CITES = 3


def _load_yaml(path, what):
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
    except OSError as error:
        raise ExpectedError(f"no se puede leer {what}: {error.__class__.__name__}")
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(f"{what} no se puede leer como YAML ({error.__class__.__name__})")
    if not isinstance(data, dict):
        raise ExpectedError(f"{what} no tiene la forma esperada")
    return path, raw, data


def _approval(data):
    approval = str(data.get("visto_bueno") or "").strip()
    return "" if approval.lower().startswith("pendiente") else approval


DECIDED_RESULTS = ("cumple", "no_cumple", "no_aplica", "no_se_encontro_documento")
TRUTH_BATCHES = ("ajuste", "aceptacion")
BASIS_TYPES = ("cita_oferta", "dato_portal", "ausencia", "pregunta", "documento_faltante")
REVIEW_STATES = ("confirmada", "corregida")
REQUIREMENT_ID = re.compile(r"^M-\d{3,}$")
TRUTH_FILE = "verdad-celdas.yaml"
FROZEN_FILE = "congelado-016.txt"


def cells_fingerprint(cells):
    """La huella de las decisiones (oferta, fila, resultado, en orden): cambia si alguien toca una
    decisión del archivo, aunque no cambie su forma."""
    lines = [f"{c['oferta']}|{c['fila']}|{c['resultado']}" for c in
             sorted(cells, key=lambda c: (c["oferta"], c["fila"]))]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


@dataclass
class TruthCell:
    """Una celda de la verdad ampliada (`verdad-celdas.yaml`, T-271): la oferta (número en el
    procedimiento), el requisito de la lista esperada (`M-NNN`), el resultado, su fundamento, la
    pregunta si es «no determinado» y la revisión (`None` si todavía no la tiene)."""

    offer: int
    requirement: str
    result: str
    basis: dict
    question: str
    review: dict | None

    @property
    def decided(self):
        return self.result in DECIDED_RESULTS

    @property
    def reviewed(self):
        return self.review is not None


@dataclass
class CommissionCells:
    """Las decisiones de la Comisión por celda: `{(oferta, fila): resultado}`. En el formato de
    la verdad ampliada (`kind == "verdad"`) las celdas se piden por `M-NNN` y `cells` queda vacío
    hasta `resolved()`, que las traduce a la fila de la matriz y deja solo las revisadas."""

    path: Path
    sha256: str
    approval: str
    procedure: str
    fingerprint: str
    cells: dict
    notes: dict
    kind: str = "comision"
    case: str = ""
    batch: str = ""
    armed_by: dict = field(default_factory=dict)
    truth: list = field(default_factory=list)

    def resolved(self, rows):
        """Con `rows` (`{M-NNN: fila de la matriz}`), las celdas revisadas de la verdad con su
        fila. Una celda sin revisión no se cuenta. Sin nada que contar, `ExpectedError`."""
        if self.kind != "verdad":
            return self
        cells, notes, missing = {}, {}, set()
        for cell in self.truth:
            if not cell.reviewed:
                continue
            row = rows.get(cell.requirement)
            if row is None:
                missing.add(cell.requirement)
                continue
            cells[(cell.offer, row)] = COMMISSION_RESULTS[cell.result]
            notes[(cell.offer, row)] = str(cell.basis.get("nota") or "")
        if missing:
            raise MeasurementRefused("Requisitos de la verdad que no están en la matriz "
                                     "validada: " + ", ".join(sorted(missing)))
        if not cells:
            raise ExpectedError("la verdad no tiene ninguna celda con revisión: no se cuenta "
                                "ninguna")
        return replace(self, cells=cells, notes=notes)


def load_commission_cells(path, *, require_approval=True):
    """Lee `celdas-comision-*.yaml`: `procedimiento`, `huella`, `visto_bueno` y `celdas` con
    `oferta`, `fila` y `resultado` (cumple, no_cumple, no_aplica, no_se_encontro_documento o
    no_determinado). La huella declarada tiene que ser la de las celdas. Sin visto bueno y con
    `require_approval`, `ExpectedNotApproved`. Si las celdas traen `requisito` (M-NNN) en lugar de
    `fila`, es el formato de la verdad ampliada (`verdad-celdas.yaml`, T-271): ver `_load_truth`."""
    path, raw, data = _load_yaml(path, "la lista de celdas de la Comisión")
    entries = data.get("celdas")
    if not isinstance(entries, list) or not entries:
        raise ExpectedError("la lista de celdas de la Comisión no trae `celdas`")
    if any(isinstance(e, dict) and "requisito" in e for e in entries):
        return _load_truth(path, raw, data, entries, require_approval)
    cells, notes = {}, {}
    for entry in entries:
        if not (isinstance(entry, dict) and isinstance(entry.get("oferta"), int)
                and isinstance(entry.get("fila"), int)):
            raise ExpectedError("una celda de la Comisión lleva `oferta` y `fila` numéricas")
        key = (entry["oferta"], entry["fila"])
        if entry.get("resultado") not in COMMISSION_RESULTS:
            raise ExpectedError(f"oferta {key[0]}, fila {key[1]}: `resultado` es "
                                + ", ".join(COMMISSION_RESULTS))
        if key in cells:
            raise ExpectedError(f"oferta {key[0]}, fila {key[1]}: celda repetida")
        cells[key] = COMMISSION_RESULTS[entry["resultado"]]
        notes[key] = str(entry.get("nota") or "")
    fingerprint = cells_fingerprint(entries)
    if str(data.get("huella") or "") != fingerprint:
        raise ExpectedError("la huella de la lista de celdas de la Comisión no es la de sus celdas")
    approval = _approval(data)
    if require_approval and not approval:
        raise ExpectedNotApproved("la lista de celdas de la Comisión no tiene visto bueno: no "
                                  "se usa")
    return CommissionCells(path=path, sha256=hashlib.sha256(raw).hexdigest(), approval=approval,
                           procedure=str(data.get("procedimiento") or ""),
                           fingerprint=fingerprint, cells=cells, notes=notes)


# --- Verdad ampliada celda por celda (016, REQ-118; ADR-0069) -----------------------------------
#
# `verdad-celdas.yaml` extiende `celdas-comision-*.yaml`: la clave de cada celda es la oferta (número
# en el procedimiento) y el requisito de la lista esperada (`M-NNN`); la medida lo traduce a la fila
# de la matriz que arma `build_case`. Lleva `procedimiento`, `caso`, `lote` (ajuste o aceptacion),
# `huella` (de oferta, requisito y resultado), `armada_por`, `visto_bueno` y `celdas` con `oferta`,
# `requisito`, `resultado`, `fundamento` (`tipo`, `documento`, `pagina`, `texto`, `nota`; en un dato
# del Portal, `portal` y `valor`; en una ausencia, `documentos`: los documentos leídos), `pregunta` y `revision` (`por`, `fecha`, `estado`, y
# `resultado_anterior` si la corrigió). Una celda sin revisión no se cuenta.
#
# `congelado-016.txt` (junto a la verdad, en los casos de aceptación) lleva una clave por línea:
# `huella-verdad` (la del archivo), `huella-lista` (sha256 de la lista esperada), `commit` y `fecha`.


def truth_fingerprint(cells):
    """La huella de la verdad (oferta, requisito, resultado, en orden): cambia si alguien toca una
    decisión del archivo."""
    lines = [f"{c['oferta']}|{c['requisito']}|{c['resultado']}" for c in
             sorted(cells, key=lambda c: (c["oferta"], c["requisito"]))]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _truth_review(entry, where):
    """La revisión de una celda, o `None` si no la tiene todavía. Una revisión incompleta o con
    otro estado es un error: no se cuenta a medias."""
    raw = entry.get("revision")
    if raw in (None, "", {}):
        return None
    if not isinstance(raw, dict):
        raise ExpectedError(f"{where}: `revision` lleva `por`, `fecha` y `estado`")
    state = raw.get("estado")
    if state == "pendiente":
        return None
    by, when = str(raw.get("por") or "").strip(), str(raw.get("fecha") or "").strip()
    if not by or not when or state not in REVIEW_STATES:
        raise ExpectedError(f"{where}: la revisión lleva `por`, `fecha` y `estado` "
                            f"({', '.join(REVIEW_STATES)})")
    previous = raw.get("resultado_anterior")
    if state == "corregida" and previous not in COMMISSION_RESULTS:
        raise ExpectedError(f"{where}: una celda corregida lleva `resultado_anterior`")
    return {"por": by, "fecha": when, "estado": state, "resultado_anterior": previous or ""}


def _truth_basis(entry, where):
    raw = entry.get("fundamento")
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict) or raw.get("tipo") not in BASIS_TYPES:
        raise ExpectedError(f"{where}: `fundamento.tipo` es " + ", ".join(BASIS_TYPES))
    if raw.get("pagina") is not None and not isinstance(raw["pagina"], int):
        raise ExpectedError(f"{where}: `fundamento.pagina` es un número")
    return dict(raw)


def _load_truth(path, raw, data, entries, require_approval):
    batch = data.get("lote")
    if batch not in TRUTH_BATCHES:
        raise ExpectedError("la verdad lleva `lote`: " + " o ".join(TRUTH_BATCHES))
    truth, seen = [], set()
    for entry in entries:
        if not (isinstance(entry, dict) and isinstance(entry.get("oferta"), int)
                and REQUIREMENT_ID.match(str(entry.get("requisito") or ""))):
            raise ExpectedError("una celda de la verdad lleva `oferta` numérica y `requisito` "
                                "(M-NNN)")
        where = f"oferta {entry['oferta']}, {entry['requisito']}"
        if entry.get("resultado") not in COMMISSION_RESULTS:
            raise ExpectedError(f"{where}: `resultado` es " + ", ".join(COMMISSION_RESULTS))
        if (entry["oferta"], entry["requisito"]) in seen:
            raise ExpectedError(f"{where}: celda repetida")
        seen.add((entry["oferta"], entry["requisito"]))
        truth.append(TruthCell(
            offer=entry["oferta"], requirement=entry["requisito"], result=entry["resultado"],
            basis=_truth_basis(entry, where), question=str(entry.get("pregunta") or "").strip(),
            review=_truth_review(entry, where)))
    fingerprint = truth_fingerprint(entries)
    if str(data.get("huella") or "") != fingerprint:
        raise ExpectedError("la huella de la verdad no es la de sus celdas")
    approval = _approval(data)
    if require_approval and not approval:
        raise ExpectedNotApproved("la verdad no tiene visto bueno: no se usa")
    armed_by = data.get("armada_por")
    return CommissionCells(
        path=path, sha256=hashlib.sha256(raw).hexdigest(), approval=approval,
        procedure=str(data.get("procedimiento") or ""), fingerprint=fingerprint, cells={},
        notes={}, kind="verdad", case=str(data.get("caso") or ""), batch=batch,
        armed_by=armed_by if isinstance(armed_by, dict) else {}, truth=truth)


def _truth_reading(offer, name):
    """`(documento, lectura)` del documento de la oferta que nombra la verdad: por nombre de
    archivo exacto o, si no hay y el nombre viene sin carpetas, por ese nombre cuando es único."""
    name = str(name)
    document, reading = sheets_measure._reading_of(offer, name)
    if document is None and "/" not in name and "\\" not in name:
        same = [d for d in offer.documents.all() if _name(d.file_name) == _name(name)]
        if len(same) == 1:
            document = same[0]
            reading = document.readings.order_by("-sequence").first()
    return document, reading


def _truth_quote_problem(offer, basis):
    """Por qué la cita de una celda no está ubicada en la lectura de la oferta, o `None` si lo
    está: `quotes.locate` en el texto de la página citada, palabra por palabra."""
    if not basis.get("documento") or not str(basis.get("texto") or "").strip():
        return "la cita no trae `documento` y `texto`"
    if not isinstance(basis.get("pagina"), int):
        return "la cita no trae la página"
    document, reading = _truth_reading(offer, basis["documento"])
    if document is None:
        return "el documento citado no está cargado en la oferta"
    if reading is None:
        return "el documento citado todavía no se leyó"
    passages = list(reading.passages.filter(page=basis["pagina"]).order_by("order"))
    if not passages:
        return f"la página {basis['pagina']} no está en la lectura del documento citado"
    start = min(p.char_start for p in passages)
    end = max(p.char_end for p in passages)
    if quotes.locate(reading.canonical_text[start:end], basis["texto"],
                     ignore_private=True) is None:
        return (f"la cita no está palabra por palabra en la página {basis['pagina']} de la "
                "lectura")
    return None


def _truth_portal_problem(offer, basis):
    """Por qué el dato del Portal de una celda no está, o `None` si el Portal trae ese dato de
    esa oferta (`portal`: garantia, cotizacion, total o cuit; `valor`)."""
    from evaluon.portal import models as pm
    kind, value = basis.get("portal"), str(basis.get("valor") or "").strip()
    if kind not in am.PortalKind.values or not value:
        return ("el dato del Portal lleva `portal` (" + ", ".join(am.PortalKind.values)
                + ") y `valor`")
    data = pm.PortalOfferData.objects.filter(offer=offer).first()
    if kind == am.PortalKind.COTIZACION:
        found = [q.price for q in pm.PortalQuote.objects.filter(offer=offer)]
    elif data is None:
        found = []
    elif kind == am.PortalKind.GARANTIA:
        found = [g.amount for g in data.guarantees.all()]
    elif kind == am.PortalKind.TOTAL:
        found = [data.total]
    else:
        found = [data.cuit]
    if any(v is not None and portal_value_in(kind, f"{v:f}" if isinstance(v, Decimal) else v,
                                              value) for v in found):
        return None
    return "el Portal no trae ese dato de la oferta"


@dataclass
class TruthCheck:
    """Lo que `verify_truth` cuenta de un caso: las celdas, las decididas, las revisadas (quién y
    cuándo), las citas ubicadas, los «no determinado» con su pregunta, el congelado y las
    corridas de evaluación guardadas; `problems` son las fallas que bloquean."""

    case: str
    batch: str
    procedure: str
    approval: str
    cells: int = 0
    by_result: dict = field(default_factory=dict)
    decided: int = 0
    decided_reviewed: int = 0
    reviewed: int = 0
    reviewers: dict = field(default_factory=dict)
    dates: tuple = ()
    cites_needed: int = 0
    cites_located: int = 0
    absence: int = 0
    absence_missing: int = 0
    undetermined: int = 0
    undetermined_named: int = 0
    frozen: str = ""
    runs: int = 0
    problems: list = field(default_factory=list)

    @property
    def unreviewed(self):
        return self.cells - self.reviewed

    @property
    def ok(self):
        return not self.problems

    def lines(self):
        names = {"cumple": "cumple", "no_cumple": "no cumple", "no_aplica": "no aplica",
                 "no_se_encontro_documento": "no se encontró el documento",
                 "no_determinado": "no determinado"}
        who = ", ".join(f"{name}: {n}" for name, n in sorted(self.reviewers.items())) or "nadie"
        when = f"del {self.dates[0]} al {self.dates[1]}" if self.dates else "sin fechas"
        out = [
            f"Verdad · caso {self.case or '?'} (lote {self.batch}) · procedimiento "
            f"{self.procedure or '?'} · visto bueno: {self.approval or 'pendiente'}",
            f"Celdas: {self.cells} (" + ", ".join(
                f"{names[r]} {self.by_result.get(r, 0)}" for r in COMMISSION_RESULTS) + ")",
            f"Decididas: {self.decided}; decididas con revisión (las que cuentan): "
            f"{self.decided_reviewed}",
            f"Con revisión (quién y cuándo): {self.reviewed} ({who}; {when}); sin revisión: "
            f"{self.unreviewed} (no se cuentan)",
            f"Citas ubicadas en la lectura o ítem del Portal: {self.cites_located} de "
            f"{self.cites_needed}",
            f"«Cumple» por ausencia (documentos leídos nombrados): {self.absence} (con "
            f"documentos no encontrados: {self.absence_missing})",
            f"«No determinado» con pregunta o documento nombrado: {self.undetermined_named} de "
            f"{self.undetermined}",
            f"Congelado (congelado-016.txt): {self.frozen}",
            f"Corridas de evaluación guardadas del procedimiento: {self.runs}"]
        out += ["FALLA: " + p for p in self.problems]
        out.append("Verdad: " + ("sin fallas" if self.ok else f"con {len(self.problems)} fallas"))
        return out


def truth_total(checks):
    """La suma de varios casos (`TruthCheck`): cantidad de casos, celdas, decididas, decididas con
    revisión, citas ubicadas y «no determinado» con pregunta, y la línea que la muestra."""
    total = {"cases": len(checks)}
    for name in ("cells", "decided", "decided_reviewed", "reviewed", "cites_needed",
                 "cites_located", "absence", "absence_missing", "undetermined", "undetermined_named", "runs"):
        total[name] = sum(getattr(c, name) for c in checks)
    total["problems"] = sum(len(c.problems) for c in checks)
    total["line"] = (
        f"Total de {total['cases']} casos: {total['cells']} celdas, {total['decided']} decididas "
        f"({total['decided_reviewed']} con revisión), {total['reviewed']} con revisión; citas "
        f"ubicadas {total['cites_located']} de {total['cites_needed']}; «no determinado» con "
        f"pregunta {total['undetermined_named']} de {total['undetermined']}; «cumple» por ausencia "
        f"{total['absence']} (documentos no encontrados {total['absence_missing']}); corridas guardadas "
        f"{total['runs']}; fallas {total['problems']}")
    return total


def _frozen_state(truth, expected):
    """`(estado, falla)` del congelado de un caso de aceptación. Sin archivo, queda pendiente hasta
    que la verdad tenga visto bueno (se escribe al cerrar el paso 1); con archivo, las dos
    huellas tienen que ser las vigentes."""
    path = Path(truth.path).parent / FROZEN_FILE
    if not path.is_file():
        if truth.approval:
            return "falta", "la verdad tiene visto bueno y no hay congelado-016.txt"
        return "pendiente (se escribe al cerrar el paso 1)", None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "ilegible", "congelado-016.txt no se puede leer"
    values = {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in lines)
              if k.strip()}
    missing = [k for k in ("huella-verdad", "huella-lista", "commit", "fecha")
               if not values.get(k)]
    if missing:
        return "incompleto", "congelado-016.txt no trae " + ", ".join(missing)
    if values["huella-verdad"] != truth.fingerprint:
        return "no coincide", "la huella de la verdad cambió después del congelado"
    if values["huella-lista"] != expected.sha256:
        return "no coincide", "la lista esperada cambió después del congelado"
    return f"coincide (commit {values['commit'][:12]}, {values['fecha']})", None


def verify_truth(truth, expected, procedure):
    """Comprueba la verdad de un caso sin usar el modelo (T-271): cuenta las celdas, las decididas
    (cumple, no cumple, no aplica y no se encontró el documento), las revisadas con quién y cuándo
    y los «no determinado» con pregunta; comprueba que cada «no cumple» y cada «cumple» con cita
    tenga su cita palabra por palabra en la lectura de la oferta (`quotes.locate`) o su ítem del
    Portal, y que cada «cumple» por ausencia nombre documentos que existan en la oferta (P3,
    ADR-0058; se cuentan aparte y no llevan cita); en un
    caso de aceptación, el congelado y que no haya corridas de evaluación guardadas del
    procedimiento. Una celda sin revisión no se cuenta."""
    if truth.kind != "verdad":
        raise ExpectedError("el archivo no es una verdad celda por celda (`requisito` por celda)")
    check = TruthCheck(case=truth.case, batch=truth.batch, procedure=procedure.number,
                       approval=truth.approval)
    if truth.procedure and truth.procedure != procedure.number:
        check.problems.append("el procedimiento de la verdad no es el del caso")
    ids = ({r["id"] for r in expected.requirements}
           or {p.requirement for o in expected.offers for p in o.pairs})
    offers = {o.number: o for o in procedure.offers.all()}
    version = latest_validated(procedure)
    mapped = (set(sheets_measure._requirement_map(version, expected.requirements))
              if version is not None and expected.requirements else None)
    dates, reviewers = [], Counter()
    for cell in truth.truth:
        where = f"oferta {cell.offer}, {cell.requirement}"
        check.cells += 1
        check.by_result[cell.result] = check.by_result.get(cell.result, 0) + 1
        if cell.decided:
            check.decided += 1
            check.decided_reviewed += cell.reviewed
        if cell.reviewed:
            check.reviewed += 1
            reviewers[cell.review["por"]] += 1
            dates.append(cell.review["fecha"])
        offer = offers.get(cell.offer)
        if offer is None:
            check.problems.append(f"{where}: la oferta no está en el procedimiento")
        if cell.requirement not in ids:
            check.problems.append(f"{where}: el requisito no está en la lista esperada")
        elif mapped is not None and cell.requirement not in mapped:
            check.problems.append(f"{where}: el requisito no está en la matriz validada")
        basis, kind = cell.basis, cell.basis.get("tipo")
        if cell.result == "no_determinado":
            check.undetermined += 1
            named = bool(cell.question) or (kind == "documento_faltante"
                                            and bool(basis.get("documento")))
            check.undetermined_named += named
            if not named:
                check.problems.append(f"{where}: «no determinado» sin pregunta ni documento "
                                      "nombrado")
        elif cell.result == "no_se_encontro_documento":
            if kind not in ("ausencia", "documento_faltante") or not basis.get("nota"):
                check.problems.append(f"{where}: «no se encontró el documento» sin los "
                                      "documentos leídos en el fundamento")
        if cell.result == "cumple" and kind == "ausencia":
            # P3 (constitución 1.6, ADR-0058): la ausencia verificada en la lectura completa de la
            # oferta nombra los documentos leídos; la comprobación de citas no aplica.
            check.absence += 1
            named = basis.get("documentos")
            if offer is None:
                pass
            elif not (isinstance(named, list) and named
                      and all(isinstance(n, str) and n.strip() for n in named)):
                check.absence_missing += 1
                check.problems.append(f"{where}: «cumple» por ausencia sin la lista de los "
                                      "documentos leídos (`documentos`)")
            else:
                unknown = [n for n in named if _truth_reading(offer, n)[0] is None]
                if unknown:
                    check.absence_missing += 1
                    check.problems.append(
                        f"{where}: «cumple» por ausencia con documentos que no están en la "
                        "oferta cargada: " + ", ".join(unknown))
        elif cell.result in ("cumple", "no_cumple") or kind in ("cita_oferta", "dato_portal"):
            needed = cell.result in ("cumple", "no_cumple")
            check.cites_needed += needed
            if offer is None:
                problem = "sin oferta"
            elif kind == "cita_oferta":
                problem = _truth_quote_problem(offer, basis)
            elif kind == "dato_portal":
                problem = _truth_portal_problem(offer, basis)
            else:
                problem = "sin cita de la oferta ni dato del Portal"
            if problem is None:
                check.cites_located += needed
            else:
                check.problems.append(f"{where}: {problem}")
        elif cell.result == "no_aplica" and not kind:
            check.problems.append(f"{where}: «no aplica» sin fundamento")
    check.reviewers = dict(reviewers)
    check.dates = (min(dates), max(dates)) if dates else ()
    check.runs = am.Run.objects.filter(offer__procedure=procedure).count()
    if truth.batch == "aceptacion":
        check.frozen, problem = _frozen_state(truth, expected)
        if problem:
            check.problems.append(problem)
        if check.runs:
            check.problems.append(f"caso de aceptación con {check.runs} corridas de evaluación "
                                  "guardadas: dejó de ser a ciegas del sistema")
    else:
        check.frozen = "no se exige en el lote de ajuste"
    return check


@dataclass
class CellExclusions:
    """Las filas de la matriz evaluada que la medida no cuenta (`{fila: motivo}`), con el
    requisito de la lista que les corresponde (`{fila: M-NNN}`, para los pares)."""

    path: Path
    sha256: str
    approval: str
    rows: dict
    list_ids: dict

    @property
    def ids(self):
        return set(self.list_ids.values())


def load_cell_exclusions(path, *, require_approval=True):
    """Lee `exclusiones-celdas-*.yaml`: `visto_bueno` y `filas` con `fila`, `motivo` y, si la
    fila es la de un par de la lista, `requisito` (M-NNN). Sin visto bueno y con
    `require_approval`, `ExpectedNotApproved`."""
    path, raw, data = _load_yaml(path, "el archivo de exclusión de celdas")
    entries = data.get("filas")
    if not isinstance(entries, list) or not entries:
        raise ExpectedError("el archivo de exclusión de celdas no trae `filas`")
    rows, list_ids = {}, {}
    for entry in entries:
        if not (isinstance(entry, dict) and isinstance(entry.get("fila"), int)):
            raise ExpectedError("una exclusión de celdas lleva `fila` numérica")
        motive = str(entry.get("motivo") or "").strip()
        if not motive:
            raise ExpectedError(f"fila {entry['fila']}: falta el `motivo` de la exclusión")
        if entry["fila"] in rows:
            raise ExpectedError(f"fila {entry['fila']}: repetida")
        rows[entry["fila"]] = motive
        if entry.get("requisito"):
            list_ids[entry["fila"]] = str(entry["requisito"])
    approval = _approval(data)
    if require_approval and not approval:
        raise ExpectedNotApproved("el archivo de exclusión de celdas no tiene visto bueno: no "
                                  "se usa")
    return CellExclusions(path=path, sha256=hashlib.sha256(raw).hexdigest(), approval=approval,
                          rows=rows, list_ids=list_ids)


def observed_cell(offer_number, row, key, *, doubt="", rule="", offer_cites=(),
                  portal_cites=(), explanation="", criteria_used=()):
    """Una celda de la evaluación tal como se compara con la Comisión. `criteria_used`: los
    criterios de la Comisión con que la decidió una regla (T-257)."""
    return {"oferta": offer_number, "fila": row, "obtenido": key, "motivo": doubt or "",
            "regla": rule or "", "citas_oferta": list(offer_cites),
            "citas_portal": list(portal_cites), "explicacion": explanation or "",
            "criterios": list(criteria_used)}


def observed_cells(run, offer_number, excluded_rows=frozenset()):
    """Las celdas de una evaluación guardada, sin las filas excluidas."""
    cells = []
    for result in run.results.select_related("requirement").order_by("requirement__number"):
        row = result.requirement.number
        if row in excluded_rows:
            continue
        cites = list(result.citations.order_by("order").values_list("kind", "text"))
        cells.append(observed_cell(
            offer_number, row, not_applicable.outcome_key(result), doubt=result.doubt,
            rule=(result.facts or {}).get("regla", ""),
            offer_cites=[t for k, t in cites if k == am.CitationKind.OFERTA],
            portal_cites=[t for k, t in cites if k == am.CitationKind.PORTAL],
            explanation=result.explanation, criteria_used=criteria_of(result)))
    return cells


def cell_accuracy(cells, commission, excluded_rows=frozenset()):
    """Exactitud por celda contra la Comisión (T-256): exacta si el resultado es el que decidió
    la Comisión; abstención si es «no determinado»; errada en otro caso (un «no se encontró el
    documento» donde la Comisión dijo «cumple» o «no aplica» es errada). Las exactas se separan
    en «con cita» (de la oferta o del Portal) y «sin cita»: que la cita sostenga lo afirmado no se
    puede comprobar sin leerla, así que todas las exactas se listan para leerlas de a una."""
    by_key = {(c["oferta"], c["fila"]): c for c in cells}
    exact, abstained, wrong, missing, left_out = [], [], [], [], []
    for key, wanted in sorted(commission.cells.items()):
        if key[1] in excluded_rows:
            left_out.append(key)
            continue
        cell = by_key.get(key)
        if cell is None:
            missing.append(key)
            continue
        found = cell["obtenido"]
        entry = dict(cell, esperado=wanted, nota_comision=commission.notes.get(key, ""))
        if found == wanted:
            exact.append(entry)
        elif found == am.Outcome.NO_DETERMINADO:
            abstained.append(entry)
        else:
            wrong.append(entry)
    measured = len(exact) + len(abstained) + len(wrong)
    cited = [c for c in exact if c["citas_oferta"] or c["citas_portal"]]
    return {
        "total": measured, "exact": ratio(len(exact), measured),
        "abstained": ratio(len(abstained), measured), "wrong": ratio(len(wrong), measured),
        "exact_with_citation": len(cited), "exact_without_citation": len(exact) - len(cited),
        "exact_cells": [(c["oferta"], c["fila"]) for c in exact],
        "wrong_cells": [(c["oferta"], c["fila"], c["esperado"], c["obtenido"]) for c in wrong],
        "abstained_cells": [(c["oferta"], c["fila"]) for c in abstained],
        "without_result": missing, "excluded": left_out, "to_read": exact,
    }


def write_exact_sample(folder, accuracy):
    """La plantilla local `muestra-exactas.md` (texto de la oferta: no va al repositorio): cada
    celda exacta con su cita y lo que decidió la Comisión, y una columna para decir si la cita
    sostiene lo afirmado («exacta con fundamento») o no («exacta sin fundamento»)."""
    if not accuracy or not accuracy["to_read"]:
        return None
    out = ["# Celdas exactas para leer una por una (T-256)", "",
           "Texto de la oferta y del Portal: no se copia al repositorio. El resultado coincide "
           "con el de la Comisión; falta leer si la cita sostiene lo afirmado. Completar la "
           "última columna con sí (con fundamento) o no (sin fundamento).", "",
           "| Oferta | Fila | Resultado | Regla | Citas | Explicación | Comisión | "
           "¿La cita sostiene lo afirmado? |", "|---|---|---|---|---|---|---|---|"]
    for cell in accuracy["to_read"]:
        cites = " / ".join([f"[oferta] {t}" for t in cell["citas_oferta"]]
                           + [f"[Portal] {t}" for t in cell["citas_portal"]]) or "(sin cita)"
        out.append(f"| {cell['oferta']} | {cell['fila']} | {cell['obtenido']} | "
                   f"{cell['regla'] or '—'} | {_cell(cites)[:600]} | "
                   f"{_cell(cell['explicacion'])[:300]} | {_cell(cell['nota_comision'])[:300]} | |")
    path = Path(folder) / EXACT_SAMPLE_FILE
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def write_criteria_sample(folder, cells):
    """La plantilla local `muestra-criterios.md` (texto de la oferta: no va al repositorio): las
    celdas que decidió un criterio de la Comisión del 2026-10-12 (T-257: «cumple» por ausencia,
    con los documentos leídos; el IVA del precio del Portal), aparte de las demás, con una columna
    para decir si el fundamento alcanza. `None` si no hay ninguna."""
    chosen = [c for c in cells if c.get("criterios")]
    if not chosen:
        return None
    out = ["# Celdas decididas por un criterio de la Comisión, para leer una por una (T-257)", "",
           "Texto de la oferta y del Portal: no se copia al repositorio. El «cumple» por ausencia "
           "tiene su fundamento en los documentos leídos y en que ninguno lo contradice "
           "(constitución 1.4): no se cuenta como «cumple sin cita». Completar la última columna "
           "con sí o no.", "",
           "| Oferta | Fila | Resultado | Regla | Criterios | Citas | Explicación | "
           "¿El fundamento alcanza? |", "|---|---|---|---|---|---|---|---|"]
    for cell in sorted(chosen, key=lambda c: (str(c["oferta"]), c["fila"])):
        cites = " / ".join([f"[oferta] {t}" for t in cell["citas_oferta"]]
                           + [f"[Portal] {t}" for t in cell["citas_portal"]]) or "(sin cita)"
        out.append(f"| {cell['oferta']} | {cell['fila']} | {cell['obtenido']} | "
                   f"{cell['regla'] or '—'} | {', '.join(cell['criterios'])} | "
                   f"{_cell(cites)[:600]} | {_cell(cell['explicacion'])[:400]} | |")
    path = Path(folder) / CRITERIA_SAMPLE_FILE
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def excluded_rows_line(excluded):
    """La línea del resumen con las filas que la medida excluye de la evaluación, cada una con el
    motivo de su archivo (H-256-3): no todas se agregaron para la medida."""
    rows = list(excluded.get("rows") or [])
    motives = excluded.get("motives") or {}
    detail = "; ".join(f"fila {row}: {motives.get(row) or 'sin motivo'}" for row in rows)
    return (f"- Filas excluidas de la evaluación (motivo del archivo de exclusión de celdas): "
            f"{len(rows)}" + (f" ({detail})" if rows else "")
            + f"; {excluded.get('cells', 0)} celdas y {excluded.get('pairs', 0)} pares de la "
            "lista.")


def accuracy_lines(accuracy):
    """Las líneas del resumen con la exactitud por celda (solo cifras)."""
    if not accuracy:
        return []
    return [f"- Exactitud por celda contra la Comisión de prueba ({accuracy['total']} celdas): "
            f"exactas {proportion_text(accuracy['exact'])}, de ellas con cita "
            f"{accuracy['exact_with_citation']} y sin cita {accuracy['exact_without_citation']} "
            f"(con o sin fundamento: se lee en `{EXACT_SAMPLE_FILE}`); abstenciones "
            f"{proportion_text(accuracy['abstained'])}; erradas "
            f"{proportion_text(accuracy['wrong'])}; sin resultado "
            f"{len(accuracy['without_result'])}; excluidas {len(accuracy['excluded'])}."]


# --- Recálculo de una corrida guardada, sin GPU (T-256) ---------------------------------------------

CELL_LINE = re.compile(r"^O(\d+) R(\d+) (\w+) +(?:(\w+) +)?regla=(\S*)\s*$")
CITE_LINE = re.compile(r"^\s+cita (oferta|portal|pliego)\s*: ?(.*)$")
EXPLANATION_LINE = re.compile(r"^\s+expl: ?(.*)$")


def read_cells_file(path):
    """Las celdas de `celdas-todas.txt` de una corrida: una línea `O<n> R<fila> <resultado>
    [<motivo>] regla=<regla>` por celda, con sus líneas `cita …` y `expl:` debajo."""
    cells, current = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        found = CELL_LINE.match(line)
        if found:
            offer, row, outcome, doubt, rule = found.groups()
            key = not_applicable.KEY if rule == NOT_APPLICABLE_RULE else outcome
            current = observed_cell(int(offer), int(row), key, doubt=doubt or "", rule=rule)
            cells.append(current)
            continue
        if current is None:
            continue
        cite = CITE_LINE.match(line)
        if cite and cite.group(1) in ("oferta", "portal"):
            current[f"citas_{cite.group(1)}"].append(cite.group(2).strip())
        elif (explanation := EXPLANATION_LINE.match(line)):
            current["explicacion"] = explanation.group(1).strip()
        elif not line.startswith(" "):
            current = None
    return cells


def rows_of_pairs(records, cells):
    """`{resultado_pk: (oferta, fila)}` de los pares guardados. Los resultados de una oferta se
    crean en el orden de las filas: se busca el comienzo con el que todos los pares de la oferta
    caen en una celda con el mismo resultado y motivo. Si no hay uno solo, `None`."""
    mapping = {}
    for offer in sorted({r["oferta"] for r in records}):
        own = [r for r in records if r["oferta"] == offer and r.get("resultado_pk")]
        rows = sorted((c for c in cells if c["oferta"] == offer), key=lambda c: c["fila"])
        if not own or not rows:
            return None
        first = min(r["resultado_pk"] for r in own)
        fits = []
        for index in range(len(rows)):
            start = first - index
            if all(0 <= r["resultado_pk"] - start < len(rows)
                   and rows[r["resultado_pk"] - start]["obtenido"] == r["obtenido"]
                   and (rows[r["resultado_pk"] - start]["motivo"] or "") == (r.get("motivo") or "")
                   for r in own):
                fits.append(start)
        if len(fits) != 1:
            return None
        mapping.update({r["resultado_pk"]: (offer, rows[r["resultado_pk"] - fits[0]]["fila"])
                        for r in own})
    return mapping


def _offline_portal_record(cell, portal_cell):
    """`portal_cell_record` sobre una celda leída de `celdas-todas.txt` (sin el tipo de cada cita:
    se busca el valor en todas las citas del Portal de la celda)."""
    kind, value, matches = portal_cell.kind, portal_cell.value, portal_cell.matches
    cites = cell["citas_portal"]
    with_value = any(portal_value_in(kind, text, value) for text in cites)
    if not with_value and len(cites) >= CELLS_FILE_PORTAL_CITES and cell["regla"] == PORTAL_RULE:
        # `celdas-todas.txt` muestra hasta tres citas del Portal por celda: si las tres no traen
        # el valor, la regla del Portal (que propone «cumple» citando el dato que coincide) lo
        # trae en otra.
        with_value = True
    inapplicable = cell["obtenido"] == not_applicable.KEY
    cumple = cell["obtenido"] == am.Outcome.CUMPLE
    return {"fila": cell["fila"], "tipo_portal": kind, "coincide_dato": matches,
            "obtenido": cell["obtenido"], "no_aplica": inapplicable, "motivo": cell["motivo"],
            "regla": cell["regla"], "cumple_con_cita_portal": cumple and with_value,
            "cumple_con_dato_distinto": cumple and (not matches or (bool(cites) and not with_value))}


def _figures(records, cells, *, corrected, portal_cells, pair_rows, excluded_rows, external_rows):
    """Las cifras de una corrida guardada con las reglas de antes (`corrected` falso) o con las
    corregidas de T-256 (D1, D2, D3, D8 y las filas excluidas)."""
    excluded_rows = excluded_rows if corrected else frozenset()
    kept = []
    for record in records:
        if excluded_rows and record.get("_excluida"):
            continue
        where = pair_rows.get(record.get("resultado_pk"))
        record = dict(record, _fila=where[1] if where else None)
        if corrected:
            is_portal = record.get("tipo") == "portal"
            record["coincide"] = bool(record["coincide"]) and (
                not is_portal or record["obtenido"] == record["esperado"])
            reference = (record.get("dictamen") if record.get("tipo") == "tecnico"
                         and record.get("dictamen") else record["esperado"])
            record["contradiccion"] = bool(record["contradiccion"]) or (
                reference == am.Outcome.CUMPLE and record["obtenido"] == am.Outcome.SIN_DOCUMENTO
                and not record["coincide"])
            record["sin_cita"] = (bool(record["sin_cita"]) and not record.get("citas_portal")
                                  and not grounded_without_citation(record.get("criterios")))
        kept.append(record)
    applicable = [r for r in kept if not r.get("no_aplica")]
    own_cells = [c for c in cells if c["fila"] not in excluded_rows]
    total = undetermined = waiting = model_external = 0
    for cell in own_cells:
        if cell["obtenido"] == not_applicable.KEY:
            continue
        total += 1
        if cell["obtenido"] != am.Outcome.NO_DETERMINADO:
            continue
        undetermined += 1
        if corrected:
            waits = (cell["motivo"] == am.Doubt.PENDIENTE_INFORME_TECNICO
                     or (cell["motivo"] == am.Doubt.EXTERNO
                         and (cell["regla"] != MODEL_EXTERNAL_RULE
                              or (cell["oferta"], cell["fila"]) in external_rows)))
        else:
            waits = cell["motivo"] in WAITING_DOCUMENT
        waiting += waits
        model_external += cell["motivo"] == am.Doubt.EXTERNO and not waits
    # Celdas del Portal: las de los pares con `portal` y las del archivo (vale la del archivo).
    portal = {}
    for record in kept:
        if record.get("portal_celda"):
            key = ((record["oferta"], record["_fila"]) if record["_fila"]
                   else ("par", record.get("resultado_pk")))
            portal[key] = record["portal_celda"]
    by_key = {(c["oferta"], c["fila"]): c for c in own_cells}
    for cell in portal_cells or ():
        if cell.row in excluded_rows:
            continue
        found = by_key.get((cell.offer, cell.row))
        if found is not None:
            portal[(cell.offer, cell.row)] = _offline_portal_record(found, cell)
    matching = [c for c in portal.values() if c["coincide_dato"] and not c.get("no_aplica")]
    return {
        "pairs": len(kept),
        "match": _sum(applicable, lambda r: r["coincide"]),
        "contradictions": sum(1 for r in kept if r["contradiccion"]),
        "no_citation": sum(1 for r in kept if r["sin_cita"]),
        "cells": {"total": total, "undetermined": undetermined, "waiting_document": waiting,
                  "counted": undetermined - waiting, "model_external": model_external,
                  "ratio": ratio(undetermined - waiting, total),
                  "ratio_decidable": ratio(undetermined - waiting, total - waiting)},
        "portal_cumple": ratio(sum(c["cumple_con_cita_portal"] for c in matching), len(matching)),
        "portal_wrong": sum(1 for c in portal.values() if c["cumple_con_dato_distinto"]),
        "excluded_cells": sum(1 for c in cells if c["fila"] in excluded_rows),
        "excluded_pairs": len(records) - len(kept),
    }


def recompute_run(folder, *, portal_cells=None, commission=None, cell_exclusions=None):
    """Recalcula, sin GPU ni base, una corrida de `medir_evaluacion` ya guardada: lee
    `resultados.jsonl` (los pares) y `celdas-todas.txt` (todas las celdas) y devuelve las cifras
    con las reglas de antes y con las corregidas de T-256, más la exactitud por celda contra la
    Comisión (sin y con las filas excluidas). Lanza `MeasurementRefused` si falta un archivo."""
    folder = Path(folder)
    if commission is not None and commission.kind == "verdad" and not commission.cells:
        raise MeasurementRefused("La verdad pide las celdas por M-NNN y acá no hay matriz para "
                                 "traducirlas a filas: se usa en una medición con --esperada.")
    pairs_file, cells_file = folder / "resultados.jsonl", folder / CELLS_FILE
    for needed in (pairs_file, cells_file):
        if not needed.exists():
            raise MeasurementRefused(f"La corrida no tiene `{needed.name}`.")
    records = [json.loads(line) for line in pairs_file.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    cells = read_cells_file(cells_file)
    excluded_rows = frozenset(cell_exclusions.rows) if cell_exclusions else frozenset()
    excluded_ids = cell_exclusions.ids if cell_exclusions else set()
    records = [dict(r, _excluida=r["requisito"] in excluded_ids) for r in records]
    pair_rows = rows_of_pairs(records, cells)
    external_rows = {pair_rows[r["resultado_pk"]] for r in records
                     if pair_rows and r.get("base") == "externa" and r.get("resultado_pk")}
    common = dict(portal_cells=portal_cells.cells if portal_cells is not None else (),
                  pair_rows=pair_rows or {},
                  excluded_rows=excluded_rows, external_rows=external_rows)
    result = {"folder": str(folder), "cells": len(cells), "pairs_mapped": pair_rows is not None,
              "before": _figures(records, cells, corrected=False, **common),
              "after": _figures(records, cells, corrected=True, **common)}
    if commission is not None:
        result["accuracy_before"] = cell_accuracy(cells, commission)
        result["accuracy_after"] = cell_accuracy(cells, commission, excluded_rows)
    return result


def measure_pair(pair, result, requirement, offer, finder, fragments, equivalents):
    """Mide un par. Devuelve el registro con lo contado y su detalle."""
    cites = list(result.citations.filter(kind=am.CitationKind.OFERTA)
                 .select_related("document", "reading").order_by("order"))
    literal = 0
    for cite in cites:
        reading = cite.reading
        literal += (cite.char_start is not None and cite.text != ""
                    and reading.canonical_text[cite.char_start:cite.char_end] == cite.text
                    and finder.page_of(reading, cite.char_start, cite.char_end) == cite.page)
    concluded = (result.outcome in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE)
                 and not not_applicable.is_not_applicable(result))
    asked = am.Question.objects.filter(result=result).exists()
    wanted = [f for f in fragments if f["requisito"] == pair.requirement]
    fragment_ok = None
    if wanted and cites:
        places = {(_canonical_document(f["documento"], equivalents), f["pagina"])
                  for f in wanted}
        fragment_ok = any(
            (_canonical_document(c.document.file_name, equivalents), c.page) in places
            for c in cites)
    pliego = result.citations.filter(kind=am.CitationKind.PLIEGO).exists()
    portal_cites = _portal_cites(result)
    portal_literal = sum(_portal_cite_is_literal(c, offer) for c in portal_cites)
    kind = pair.kind
    facts = result.facts or {}
    # T-257: los criterios de la Comisión con que una regla decidió la celda (ausencia, IVA).
    used = criteria_of(result) if result.outcome == am.Outcome.CUMPLE else []
    return {
        "requisito": pair.requirement, "base": pair.base, "via": pair.via, "tipo": kind,
        "esperado": pair.result, "motivo_esperado": pair.doubt,
        "obtenido": not_applicable.outcome_key(result), "motivo": result.doubt,
        "no_aplica": not_applicable.is_not_applicable(result),
        "coincide": _match(pair, result), "contradiccion": _contradiction(pair, result),
        "contradicciones_hecho": _fact_contradictions(pair, result),
        "hechos": {k: facts.get(k) for k in ("regla", "documento_tecnico", "renglon_ofertado",
                                              "ilegible") if k in facts},
        "opinion": result.opinion, "dictamen": pair.dictamen,
        "citas_portal": len(portal_cites), "citas_portal_literales": portal_literal,
        "tecnico_concluido": kind == "tecnico" and concluded,
        "sin_documento_donde_cumple": (result.outcome == am.Outcome.SIN_DOCUMENTO
                                       and pair.result == am.Outcome.CUMPLE),
        "citas_oferta": len(cites), "citas_literales": literal,
        # T-256 (D8): el «cumple» citado al Portal (REQ-103, P3) tiene cita. T-257: el «cumple»
        # por ausencia tiene su fundamento sin cita (constitución 1.4) y se lee aparte.
        "sin_cita": (concluded and not cites and not portal_cites
                     and not grounded_without_citation(used)),
        "criterios": used,
        "pregunta_esperada": pair.question, "pregunta_formulada": asked,
        "cita_pliego": pliego, "fragmento": fragment_ok,
        "anomalias": [], "resultado_pk": result.pk,
        "portal_celda": (portal_cell_record(
            result, pair.portal["tipo"], str(pair.portal["valor"]),
            pair.portal.get("coincide", pair.result == am.Outcome.CUMPLE))
            if pair.portal else None),
    }


def _steps_summary(run):
    steps = list(run.steps.all())
    by_purpose = {}
    for step in steps:
        entry = by_purpose.setdefault(step.purpose, {"pedidos": 0, "tokens_pedido": 0,
                                                     "tokens_salida": 0})
        entry["pedidos"] += 1
        entry["tokens_pedido"] += step.prompt_tokens or 0
        entry["tokens_salida"] += step.completion_tokens or 0
    return {"pedidos": len(steps), "por_clase": by_purpose,
            "tokens_pedido": sum(s.prompt_tokens or 0 for s in steps),
            "tokens_salida": sum(s.completion_tokens or 0 for s in steps)}


def measure_offer(entry, offer, run, mapping, finder, fragments, equivalents, cells=(),
                  excluded_rows=frozenset()):
    """Mide una oferta contra su lista; `run` es la evaluación recién hecha. `cells` son las
    celdas del Portal del archivo aparte que corresponden a esta oferta (T-238). Las filas de
    `excluded_rows` (agregadas solo para la medida, T-256) no entran en ninguna cifra: se
    cuentan aparte."""
    results = {r.requirement_id: r for r in run.results.select_related("requirement")}
    excluded_ids = {pk for pk, r in results.items() if r.requirement.number in excluded_rows}
    external_ids = {mapping[p.requirement].pk for p in entry.pairs
                    if p.base == "externa" and p.requirement in mapping}
    records, excluded_pairs = [], []
    for pair in entry.pairs:
        requirement = mapping.get(pair.requirement)
        if requirement is not None and requirement.number in excluded_rows:
            excluded_pairs.append(pair.requirement)
            continue
        result = results.get(requirement.pk) if requirement else None
        if result is None:
            records.append({"requisito": pair.requirement, "base": pair.base,
                            "tipo": pair.kind, "contradicciones_hecho": [], "opinion": "",
                            "dictamen": pair.dictamen, "citas_portal": 0,
                            "citas_portal_literales": 0, "tecnico_concluido": False,
                            "motivo": "", "hechos": {},
                            "esperado": pair.result, "obtenido": None, "coincide": False,
                            "contradiccion": False, "sin_cita": False, "citas_oferta": 0,
                            "citas_literales": 0, "pregunta_esperada": pair.question,
                            "pregunta_formulada": False, "cita_pliego": False,
                            "fragmento": None, "sin_documento_donde_cumple": False,
                            "anomalias": ["sin_resultado"], "resultado_pk": None})
            continue
        records.append(measure_pair(pair, result, requirement, offer, finder,
                                    fragments, equivalents))
    # Celdas del Portal (REQ-103): las de los pares de la lista y las del archivo aparte; si una
    # celda está en las dos, vale la del archivo.
    portal_cells = {r["resultado_pk"]: {"fila": None, **r["portal_celda"]}
                    for r in records if r.get("portal_celda")}
    by_row = {r.requirement.number: r for r in results.values()}
    for cell in cells:
        if cell.row in excluded_rows:
            continue
        result = by_row.get(cell.row)
        if result is None:
            portal_cells[("sin", cell.row)] = {
                "fila": cell.row, "tipo_portal": cell.kind, "coincide_dato": cell.matches,
                "obtenido": None, "motivo": "", "regla": "", "cumple_con_cita_portal": False,
                "cumple_con_dato_distinto": False}
            continue
        portal_cells[result.pk] = {"fila": cell.row, **portal_cell_record(
            result, cell.kind, cell.value, cell.matches)}
    proposed = [r for r in records if r["obtenido"] == am.Outcome.NO_CUMPLE]
    proposed_ids = [r["requisito"] for r in proposed]
    discard_ok = None
    if entry.discarded in ("si", "no", "parcial"):
        want = entry.discarded != "no"
        # El sistema ya no descarta por lo técnico (decisión 2): un descarte que el dictamen
        # sustenta solo con filas técnicas no se mide acá; se informa en `technical_discard`.
        technical_only = want and not any(
            p.result == am.Outcome.NO_CUMPLE and p.base != "tecnica" for p in entry.pairs)
        if not technical_only:
            discard_ok = bool(proposed_ids) == want
            if discard_ok and entry.discarded == "si" and entry.discard.get("requisito"):
                discard_ok = entry.discard["requisito"] in proposed_ids
    technical = [r for r in records if r.get("tipo") == "tecnico"]
    technical_discard = {
        "dictamen_no_cumple": sum(1 for r in technical if r["dictamen"] == "no_cumple"),
        "opinion_no_cumple": sum(1 for r in technical if r["opinion"] == "no_cumple"),
        "ambos": sum(1 for r in technical
                     if r["dictamen"] == "no_cumple" and r["opinion"] == "no_cumple")}
    return {
        "records": records, "proposed_discard": proposed_ids, "discard_ok": discard_ok,
        "technical_discard": technical_discard,
        "counts": run.counts, "timings": run.timings, "anomalies": run.anomalies,
        "steps": _steps_summary(run), "run": run.pk, "number": run.number,
        "offer_number": offer.number, "unread_pages": run.counts.get("unread_pages", 0),
        "cells": cell_counts(run, external_ids, excluded_ids),
        "three_outputs": three_outputs(run, excluded_ids),
        "portal_cells": list(portal_cells.values()),
        "questions": question_records(run, excluded_rows),
        "excluded_pairs": excluded_pairs,
        "observed": observed_cells(run, offer.number, excluded_rows),
    }


def _sum(records, predicate, universe=None):
    universe = records if universe is None else universe
    return ratio(sum(1 for r in universe if predicate(r)), len(universe))


def aggregate(measures):
    """Reúne las cuentas de todas las ofertas."""
    records = [r for m_ in measures for r in m_["records"]]
    # Los pares «No aplica» (forma de garantía no elegida) no cuentan como «cumple» ni como diferencia
    # con la lista: se informan aparte (`not_applicable`).
    applicable = [r for r in records if not r.get("no_aplica")]
    concluded = [r for r in records if r["obtenido"] in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE)]
    expected_missing = [r for r in records if r["esperado"] == am.Outcome.SIN_DOCUMENTO]
    expected_questions = [r for r in records if r["pregunta_esperada"]]
    fragmented = [r for r in records if r["fragmento"] is not None]
    cites = sum(r["citas_oferta"] for r in records)
    technical = [r for r in records if r.get("tipo") == "tecnico"]
    with_opinion = [r for r in technical if r.get("dictamen") and r.get("opinion")]
    fact_contradictions = [(r["requisito"], c) for r in records
                           for c in r.get("contradicciones_hecho", [])]
    return {
        "pairs": len(records),
        "match": _sum(applicable, lambda r: r["coincide"]),
        "match_by_type": {t: _sum([r for r in applicable if r.get("tipo", "oferta") == t],
                                  lambda r: r["coincide"])
                          for t in PAIR_TYPES},
        "contradictions": [(r["requisito"], r["esperado"], r["obtenido"])
                           for r in records if r["contradiccion"]] + fact_contradictions,
        "fact_contradictions": fact_contradictions,
        "portal_literal": ratio(sum(r.get("citas_portal_literales", 0) for r in records),
                                sum(r.get("citas_portal", 0) for r in records)),
        "residue": {d: sum(1 for r in records if r["obtenido"] == am.Outcome.NO_DETERMINADO
                           and r.get("motivo") == d) for d in RESIDUE},
        "technical_concluded": [r["requisito"] for r in technical
                                if r.get("tecnico_concluido")],
        "technical_opinion": _sum(with_opinion, lambda r: r["opinion"] == r["dictamen"]),
        "technical_discard": {
            k: sum(m_.get("technical_discard", {}).get(k, 0) for m_ in measures)
            for k in ("dictamen_no_cumple", "opinion_no_cumple", "ambos")},
        "no_citation": [r["requisito"] for r in records if r["sin_cita"]],
        "literal": ratio(sum(r["citas_literales"] for r in records), cites),
        "missing_document": _sum(
            records, lambda r: r["obtenido"] == am.Outcome.SIN_DOCUMENTO and r["cita_pliego"],
            expected_missing),
        "questions": _sum(records, lambda r: r["pregunta_formulada"], expected_questions),
        "fragments": _sum(fragmented, lambda r: r["fragmento"]),
        "matrix": ratio(sum(1 for r in records if r["obtenido"] is not None), len(records)),
        "missing_where_cumple": [r["requisito"] for r in records
                                 if r["sin_documento_donde_cumple"]],
        "concluded": len(concluded),
        "discards": ratio(sum(1 for m_ in measures if m_["discard_ok"]),
                          sum(1 for m_ in measures if m_["discard_ok"] is not None)),
        "by_outcome": {o: sum(1 for r in records if r["obtenido"] == o)
                       for o in [*am.Outcome.values, not_applicable.KEY]},
        "not_applicable": sum(1 for r in records if r.get("no_aplica")),
        "mismatches": [(r["requisito"], r["esperado"], r["obtenido"], r["motivo"])
                       for r in applicable if not r["coincide"]],
        "seconds": round(sum(m_["timings"].get("total_seconds", 0) for m_ in measures), 3),
        "model_requests": sum(m_["steps"]["pedidos"] for m_ in measures),
        "tokens_prompt": sum(m_["steps"]["tokens_pedido"] for m_ in measures),
        "tokens_output": sum(m_["steps"]["tokens_salida"] for m_ in measures),
        "unread_pages": sum(m_["unread_pages"] for m_ in measures),
        **aggregate_015(measures),
    }


def aggregate_three_outputs(measures):
    """Las cuentas de las tres salidas de todas las ofertas (T-277, REQ-120): cada lista trae
    `(oferta, requisito)`."""
    out = {"cells": 0, "sin_documento": 0, "no_determinado": 0, "sin_documento_sin_pregunta": [],
           "no_determinado_sin_nombrar": [], "problems": []}
    for m_ in measures:
        found = m_.get("three_outputs")
        if not found:
            continue
        offer = m_.get("offer_number")
        for name in ("cells", "sin_documento", "no_determinado"):
            out[name] += found[name]
        for name in ("sin_documento_sin_pregunta", "no_determinado_sin_nombrar"):
            out[name] += [(offer, number) for number in found[name]]
        out["problems"] += [(offer, number, why) for number, why in found["problems"]]
    return out


def aggregate_015(measures):
    """Las cuentas de la 015 de todas las ofertas (T-238)."""
    counts = [m_.get("cells") or {"total": 0, "undetermined": 0, "waiting_document": 0,
                                  "not_applicable": 0}
              for m_ in measures]
    total = sum(c["total"] for c in counts)
    undetermined = sum(c["undetermined"] for c in counts)
    waiting = sum(c["waiting_document"] for c in counts)
    inapplicable = sum(c.get("not_applicable", 0) for c in counts)
    model_external = sum(c.get("model_external", 0) for c in counts)
    left_out = sum(c.get("excluded", 0) for c in counts)
    portal = [dict(c, oferta=m_.get("offer_number")) for m_ in measures
              for c in m_.get("portal_cells", [])]
    matching = [c for c in portal if c["coincide_dato"] and not c.get("no_aplica")]
    forms = [dict(q, oferta=m_.get("offer_number")) for m_ in measures
             for q in m_.get("questions", [])]
    return {
        "cells": {"total": total, "undetermined": undetermined, "waiting_document": waiting,
                  "not_applicable": inapplicable, "counted": undetermined - waiting,
                  "ratio": ratio(undetermined - waiting, total),
                  # T-256 (D3): la misma cifra sobre las celdas decidibles (sin las que esperan
                  # un documento ausente), y los «externo» del modelo que ya no se descuentan.
                  "decidable": total - waiting,
                  "ratio_decidable": ratio(undetermined - waiting, total - waiting),
                  "model_external": model_external, "excluded": left_out},
        "portal_cells": {"total": len(portal), "matching": len(matching),
                         "not_applicable": sum(1 for c in portal if c.get("no_aplica"))},
        "portal_cumple": ratio(sum(c["cumple_con_cita_portal"] for c in matching),
                               len(matching)),
        "portal_wrong": [(c["oferta"], c["fila"]) for c in portal
                         if c["cumple_con_dato_distinto"]],
        "three_outputs": aggregate_three_outputs(measures),
        "questions_form": ratio(sum(q["conforme"] for q in forms), len(forms)),
        "questions_form_parts": {name: sum(q[name] for q in forms) for name in (
            "requisito_ok", "conclusion_ok", "texto_ok", "dirigida_ok", "nombra_comision")},
        "questions_nonconforming": [(q["oferta"], q["fila"]) for q in forms
                                    if not q["conforme"]],
    }


def blocking(total, case=None):
    """Lo que no llega al umbral del caso (vacío si todo cumple)."""
    failed = []
    for name, (limit, blocks) in thresholds_for(case).items():
        if not blocks or limit is None:
            continue
        value = total[name]
        if name in MAXIMUMS:
            if len(value) > limit:
                failed.append(f"{LABELS[name]}: {len(value)}, máximo {limit}")
        elif value["total"]:
            more = name in MORE_THAN.get(case, ())
            if (value["rate"] <= limit) if more else (value["rate"] < limit):
                failed.append(f"{LABELS[name]}: {proportion_text(value)}, "
                              f"{'más de' if more else 'mínimo'} {_pct(limit)}")
    return failed


def _pct(value):
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


@dataclass
class Report:
    folder: Path
    expected: Expected
    verification: Verification | None
    offers: list
    total: dict
    request: object = None
    seconds: float = 0.0
    video: dict | None = None            # memoria de video antes y después (P6)
    portal_cells: object = None          # `PortalCells` del archivo aparte, si se pasó
    commission_cells: object = None      # `CommissionCells` (T-256), si se pasó
    cell_exclusions: object = None       # `CellExclusions` (T-256), si se pasó

    @property
    def blocking(self):
        return blocking(self.total, self.expected.case)

    @property
    def unmet_015(self):
        """Las medidas de la 015 que no llegan a su umbral (T-238)."""
        return [name for name, _, ok in thresholds_015(self.total, self.expected.case,
                                                       self.video) if not ok]


def _requirement_mapping(version, expected, fichas):
    entries = expected.requirements or (fichas.requirements if fichas else [])
    if not entries:
        raise MeasurementRefused("Falta la lista de fichas (--fichas) para saber qué requisito "
                                 "de la matriz es cada M-NNN del dictamen.")
    mapping = sheets_measure._requirement_map(version, entries)
    needed = {p.requirement for o in expected.offers for p in o.pairs}
    missing = sorted(needed - set(mapping))
    if missing:
        raise MeasurementRefused("Requisitos de la lista que no están en la matriz validada: "
                                 + ", ".join(missing))
    return mapping


def _fragments_for(expected, entry, fichas):
    """Fragmentos esperados y copias equivalentes de una oferta para REQ-054."""
    name = match_name(entry.bidder, fichas.fragments) if fichas is not None else None
    if name is not None:
        return fichas.fragments[name], fichas.equivalents.get(name, {})
    derived = [{"requisito": p.requirement, "documento": c["documento"], "pagina": c["pagina"]}
               for p in entry.pairs for c in p.citations]
    return derived, dict(entry.copies)


def run_evaluation(user, procedure, *, clock=time.monotonic):
    """Pide la evaluación de todas las ofertas en el canal `eval` y la corre acá, sin esperar
    al `worker` (como `evaluar_ofertas`). Devuelve `(pedido, evaluaciones)`."""
    try:
        requested = evaluate.request_evaluation(user, procedure, channel=Channel.EVAL)
    except evaluate.EvaluationRefused as error:
        raise MeasurementRefused(f"No se pudo pedir la evaluación: {error}") from None
    job = requested.job
    taken = m.Job.objects.filter(pk=job.pk, status=m.JobStatus.QUEUED).update(
        status=m.JobStatus.RUNNING, started_at=timezone.now())
    if not taken:
        raise MeasurementRefused("Otro proceso tomó el pedido de evaluación: espere a que "
                                 "termine y vuelva a correr.")
    job.refresh_from_db()
    try:
        runs = evaluate.execute(requested.request, user, channel=RunChannel.EVAL,
                                audit_channel=Channel.EVAL, job=job, clock=clock)
    except Exception as error:  # noqa: BLE001 - el pedido queda fallido con su causa
        jobs.fail(job, f"{type(error).__name__}: {error}")
        raise MeasurementRefused(f"La evaluación no terminó: {error}") from None
    jobs.finish(job)
    return requested.request, runs


def measure(user, procedure, expected, offers, runs_dir, *, fichas=None, commit=None,
            clock=time.monotonic, portal_cells=None, commission_cells=None,
            cell_exclusions=None):
    """Comprueba la lista, evalúa todas las ofertas con el canal `eval`, las mide y guarda la
    carpeta de la corrida en `runs_dir`. Devuelve el `Report`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    if not expected.approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    missing = check_fields(expected)
    if missing:
        raise MeasurementRefused("La lista no trae los campos de la regla nueva:\n"
                                 + "\n".join(missing))
    verification = verify_expected(expected, offers)
    if not verification.ok:
        raise MeasurementRefused("La lista no se puede usar:\n" + "\n".join(verification.lines))
    version = latest_validated(procedure)
    if version is None:
        raise MeasurementRefused("El procedimiento no tiene una matriz validada.")
    mapping = _requirement_mapping(version, expected, fichas)
    if commission_cells is not None:
        # T-271: la verdad ampliada pide las celdas por M-NNN; acá se traducen a la fila de la
        # matriz validada y se queda con las revisadas. El formato anterior pasa sin cambios.
        commission_cells = commission_cells.resolved({i: r.number for i, r in mapping.items()})
    started_at = timezone.now()
    video = {"before": video_memory()}
    started = clock()
    request, runs = run_evaluation(user, procedure, clock=clock)
    elapsed = clock() - started
    video["after"] = video_memory()
    by_offer = {run.offer_id: run for run in runs}
    finder = PageFinder()
    excluded_rows = frozenset(cell_exclusions.rows) if cell_exclusions else frozenset()
    results = []
    for entry in expected.offers:
        offer = offers[entry.bidder]
        run = by_offer.get(offer.pk)
        if run is None:
            raise MeasurementRefused(f"La oferta {offer.number} no quedó evaluada.")
        fragments, equivalents = _fragments_for(expected, entry, fichas)
        own_cells = ([c for c in portal_cells.cells if c.offer == offer.number]
                     if portal_cells else ())
        measures = measure_offer(entry, offer, run, mapping, finder, fragments, equivalents,
                                 own_cells, excluded_rows)
        results.append({"offer": offer.pk, "number": offer.number, "bidder": entry.bidder,
                        "measures": measures, "parameters": run.parameters,
                        "prompt_versions": run.prompt_versions, "models": run.models_used})
    total = aggregate([r["measures"] for r in results])
    # T-256: la exactitud por celda contra la Comisión de prueba y las filas excluidas.
    observed = [c for r in results for c in r["measures"].get("observed", [])]
    total["accuracy"] = (cell_accuracy(observed, commission_cells, excluded_rows)
                         if commission_cells else None)
    total["excluded_rows"] = {
        "rows": sorted(excluded_rows),
        "motives": dict(cell_exclusions.rows) if cell_exclusions else {},
        "pairs": sum(len(r["measures"].get("excluded_pairs", [])) for r in results)}
    base = f"{started_at:%Y%m%d-%H%M%S}-{commit or 'sin-commit'}"
    folder = Path(runs_dir) / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = Path(runs_dir) / f"{base}-{suffix}"
    report = Report(folder, expected, verification, results, total, request,
                    round(elapsed, 3), video=video, portal_cells=portal_cells,
                    commission_cells=commission_cells, cell_exclusions=cell_exclusions)
    _write(report, procedure, version, started_at, commit, fichas)
    return report


def _write(report, procedure, version, started_at, commit, fichas):
    report.folder.mkdir(parents=True, exist_ok=False)
    expected = report.expected
    parameters = {
        "caso": expected.case, "procedimiento": procedure.number,
        "version_matriz": version.number, "iniciada": started_at,
        "commit": commit or "sin-commit", "pedido": report.request.pk,
        "lista": {"tipo": expected.kind, "sha256": expected.sha256,
                  "visto_bueno": expected.approval, "ofertas": len(expected.offers),
                  "pares": sum(len(o.pairs) for o in expected.offers),
                  "fichas": fichas is not None},
        "umbrales": {name: {"limite": limit, "bloquea": blocks}
                     for name, (limit, blocks) in thresholds_for(expected.case).items()},
        "comprobacion": dict(report.verification.counts),
        "memoria_de_video": report.video,
        "celdas_portal": ({"sha256": report.portal_cells.sha256,
                           "visto_bueno": report.portal_cells.approval,
                           "celdas": len(report.portal_cells.cells)}
                          if report.portal_cells else None),
        "celdas_comision": ({"sha256": report.commission_cells.sha256,
                             "huella": report.commission_cells.fingerprint,
                             "visto_bueno": report.commission_cells.approval,
                             "celdas": len(report.commission_cells.cells)}
                            if report.commission_cells else None),
        "exclusiones_celdas": ({"sha256": report.cell_exclusions.sha256,
                                "visto_bueno": report.cell_exclusions.approval,
                                "filas": report.cell_exclusions.rows}
                               if report.cell_exclusions else None),
        "evaluaciones": [{"oferta": r["number"], "evaluacion": r["measures"]["run"],
                          "parametros": r["parameters"],
                          "instrucciones": r["prompt_versions"], "modelos": r["models"]}
                         for r in report.offers],
    }
    (report.folder / "parametros.json").write_text(
        _dumps(parameters, indent=2) + "\n", encoding="utf-8")
    with (report.folder / "resultados.jsonl").open("w", encoding="utf-8") as handle:
        for result in report.offers:
            for record in result["measures"]["records"]:
                handle.write(_dumps({"oferta": result["number"], **record}) + "\n")
    (report.folder / "resumen.md").write_text(_summary(report, public=False), encoding="utf-8")
    (report.folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                                      encoding="utf-8")
    _write_questions_sample(report)
    write_exact_sample(report.folder, report.total.get("accuracy"))
    write_criteria_sample(report.folder, [cell for result in report.offers
                                          for cell in result["measures"].get("observed") or []])


def _cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def _write_questions_sample(report):
    """La plantilla local `muestra-preguntas.md`, con texto del pliego y de la oferta (no va al
    repositorio): todas las preguntas, una fila cada una, con la comprobación mecánica y una
    columna para que quien verifica diga si cumple REQ-105 (se leen de a una)."""
    rows = [q for r in report.offers for q in r["measures"].get("questions", [])]
    if not rows:
        return
    out = ["# Preguntas a la Comisión para leer una por una", "",
           "Texto del pliego y de la oferta: no se copia al repositorio. La forma mecánica "
           "(requisito, conclusión, texto, dirigida a la Comisión) es una ayuda: la lectura "
           "decide. Completar la última columna con sí o no.", "",
           "| Oferta | Fila | Resultado | Motivo | Forma | Pregunta | Requisito | "
           "¿Cumple REQ-105? |",
           "|---|---|---|---|---|---|---|---|"]
    for q in rows:
        form = ", ".join(f"{name} {'sí' if q[key] else 'NO'}" for name, key in (
            ("requisito", "requisito_ok"), ("conclusión", "conclusion_ok"),
            ("texto", "texto_ok"), ("dirigida", "dirigida_ok")))
        out.append(f"| {q['oferta']} | {q['fila']} | {q['obtenido']} | {q['motivo'] or '—'} | "
                   f"{form} | {_cell(q['detalle']['pregunta'])} | "
                   f"{_cell(q['detalle']['requisito'])[:300]} | |")
    (report.folder / QUESTIONS_SAMPLE_FILE).write_text("\n".join(out) + "\n", encoding="utf-8")


def _summary_015(report):
    """Las medidas de la 015 contra su umbral, solo con cifras."""
    total = report.total
    lines = ["", "## Medidas de la 015 (REQ-103 a REQ-105)", "", "| Medida | Medido | Cumple |",
             "|---|---|---|"]
    for name, measured, ok in thresholds_015(total, report.expected.case, report.video):
        lines.append(f"| {name} | {measured} | {'sí' if ok else 'no'} |")
    for name, measured, ok in thresholds_016(total):
        lines.append(f"| {name} | {measured} | {'sí' if ok else 'no'} |")
    cells = total["cells"]
    portal = total["portal_cells"]
    forms = total["questions_form_parts"]
    memory = max_video_mib(report.video)
    lines += ["",
              f"- Celdas de la evaluación: {cells['total']}; «no determinado»: "
              f"{cells['undetermined']}, de ellas esperan el informe técnico o una hoja de "
              f"compliance: {cells['waiting_document']}; las que cuentan: {cells['counted']}. "
              f"Aparte, sin contar en esas cifras, «{not_applicable.COUNT_LABEL}»: "
              f"{cells.get('not_applicable', 0)}.",
              f"- «No determinado» que cuenta sobre las celdas decidibles (sin las que esperan "
              f"un documento ausente): {proportion_text(cells['ratio_decidable'])}; «externo» "
              f"que marcó el modelo, que ya no se descuenta: {cells.get('model_external', 0)}.",
              excluded_rows_line(dict(total.get("excluded_rows") or {},
                                      cells=cells.get("excluded", 0))),
              *accuracy_lines(total.get("accuracy")),
              f"- Celdas del Portal medidas: {portal['total']} ({portal['matching']} con el "
              "dato que coincide con lo que exige el pliego; "
              f"{portal.get('not_applicable', 0)} «{not_applicable.COUNT_LABEL}», aparte).",
              f"- Preguntas: {total['questions_form']['total']}; con el requisito "
              f"{forms['requisito_ok']}, con la conclusión {forms['conclusion_ok']}, con el "
              f"texto {forms['texto_ok']}, no dirigidas al oferente {forms['dirigida_ok']}, "
              f"que nombran a la Comisión {forms['nombra_comision']}.",
              f"- Tiempo de la evaluación completa: {report.seconds} s; memoria de video máxima "
              "registrada: " + (f"{memory} MiB (umbral {VIDEO_MAXIMUM_MIB} MiB)"
                                if memory is not None else "no registrada") + "."]
    return lines


def _summary(report, *, public):
    total, case = report.total, report.expected.case
    lines = [f"# Medición de la evaluación asistida · {case}", "",
             f"Lista: `{report.expected.sha256[:12]}` ({report.expected.kind}) · visto bueno: "
             f"{report.expected.approval}", "",
             "## Resultado contra el umbral", "", "| Medida | Umbral | Medido |",
             "|---|---|---|"]
    for name, (limit, blocks) in thresholds_for(case).items():
        value = total[name]
        if limit is None:
            required = "informado, sin tope"
        elif name in MAXIMUMS:
            required = f"máximo {limit}"
        else:
            required = f"{_pct(limit)} o más"
        measured = len(value) if name in MAXIMUMS else proportion_text(value)
        lines.append(f"| {LABELS[name]} | {required}{'' if blocks else ' (no bloquea)'} | "
                     f"{measured} |")
    failed = report.blocking
    lines += ["", "Cumple el umbral." if not failed else "No cumple: " + "; ".join(failed) + ".",
              "", "## Se informa", "",
              f"- Pares: {total['pairs']}; por resultado propuesto: {total['by_outcome']}.",
              f"- «No se encontró el documento» donde se espera «cumple»: "
              f"{len(total['missing_where_cumple'])}.",
              f"- Descarte propuesto igual al esperado (sin lo técnico): "
              f"{proportion_text(total['discards'])}.",
              f"- Descarte técnico (informado): {total['technical_discard']}.",
              "- Coincidencia por tipo de par: " + "; ".join(
                  f"{t} {proportion_text(v)}" for t, v in total["match_by_type"].items()) + ".",
              f"- Residuo de «no determinado» sin causa concreta: {total['residue']}.",
              f"- Opinión técnica igual al dictamen (informada): "
              f"{proportion_text(total['technical_opinion'])}.",
              f"- Filas técnicas con «cumple» o «no cumple» en el resultado: "
              f"{len(total['technical_concluded'])}.",
              f"- Hechos o datos del Portal opuestos a la lista: "
              f"{len(total['fact_contradictions'])}.",
              "- Orden económico: lo muestra la matriz de la evaluación (T-152); no se mide acá.",
              f"- Páginas sin leer en las ofertas: {total['unread_pages']}.",
              *_summary_015(report), "",
              "## Tiempo y tokens", "",
              f"- Evaluación completa: {report.seconds} s; {total['model_requests']} pedidos "
              f"al modelo; {total['tokens_prompt']} tokens de pedido y {total['tokens_output']} "
              "de salida."]
    for result in report.offers:
        measures = result["measures"]
        lines.append(f"- Oferta {result['number']}: {measures['timings'].get('total_seconds')} s, "
                     f"{measures['steps']['pedidos']} pedidos "
                     f"({measures['counts'].get('retries', 0)} reintentos, "
                     f"{measures['counts'].get('contrasts', 0)} contrastes), "
                     f"{measures['steps']['tokens_pedido']} tokens de pedido, "
                     f"{measures['unread_pages']} páginas sin leer.")
    lines += ["", "## Diferencias con el esperado", ""]
    if not total["mismatches"]:
        lines.append("Ninguna.")
    for mismatch in total["mismatches"]:
        lines.append("- " + (" · ".join(str(x) for x in mismatch) if public
                             else _dumps(list(mismatch))))
    if not public:
        lines += ["", "## Detalle", ""]
        for result in report.offers:
            lines.append(f"### Oferta {result['number']} · {result['bidder']}")
            for record in result["measures"]["records"]:
                lines.append("- " + _dumps(record))
    else:
        lines += ["", "Los datos de los oferentes no figuran en este resumen."]
    return "\n".join(lines) + "\n"


# --- Decisiones aplicadas (T-170) -----------------------------------------------------------------


def run_decision_tests(runner=subprocess.run, *, cwd=None):
    """Corre los tests marcados `decision_literal` (uno por decisión del responsable, ADR-0043) en
    un proceso aparte. Devuelve `(estado, salida)`: `ok`, `fallo` o `ausente` (ningún test lleva
    todavía la marca: se informa, no bloquea). Cualquier otro resultado cuenta como fallo."""
    command = [sys.executable, "-m", "pytest", "-m", DECISION_MARK, "-q", "-p", "no:cacheprovider",
               "tests"]
    try:
        done = runner(command, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                      check=False)
    except OSError as error:
        return "fallo", f"no se pudo correr pytest ({error.__class__.__name__})"
    output = (done.stdout or "") + (done.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-15:])
    if done.returncode == 0:
        return "ok", tail
    if done.returncode == 5:
        return "ausente", tail
    return "fallo", tail


# --- Nombres de oferentes -----------------------------------------------------------------------


def _plain(text):
    """El nombre sin tildes, mayúsculas ni signos, para parear «Munoz» con «Muñoz Insumos S.R.L.»."""
    import re
    import unicodedata

    decomposed = unicodedata.normalize("NFD", text or "")
    base = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", base.lower()).split())


def match_name(name, candidates):
    """El candidato que corresponde a `name`: el igual o, si no hay, el único que contiene el
    nombre (o está contenido en él) sin tildes ni mayúsculas. `None` si no hay o hay varios."""
    candidates = list(candidates)
    if name in candidates:
        return name
    wanted = _plain(name)
    found = [c for c in candidates
             if wanted and (wanted in _plain(c) or _plain(c) in wanted)]
    return found[0] if len(found) == 1 else None


def resolve_offers(expected, procedure):
    """`{oferente de la lista: oferta del procedimiento}`; lanza `MeasurementRefused` si un
    oferente de la lista no está cargado (o no se puede decir cuál es)."""
    by_name = {o.bidder: o for o in procedure.offers.all()}
    offers = {}
    for entry in expected.offers:
        name = match_name(entry.bidder, by_name)
        if name is None:
            raise MeasurementRefused("Un oferente de la lista no está cargado en el "
                                     "procedimiento o su nombre no es unívoco.")
        offers[entry.bidder] = by_name[name]
    return offers


# --- Rehacer la matriz de un procedimiento ya armado (T-156) -------------------------------------


def rebuild_matrix(user, procedure, *, channel=Channel.COMMAND):
    """Una versión nueva y validada de la matriz con todas las cláusulas de cada renglón.

    La matriz que armó la 008 del caso-00 trae, en cada fila técnica, solo el encabezado del
    renglón: el modelo comparaba títulos. Copia la última versión validada (la anterior no se
    toca), reemplaza las citas de cada fila técnica por el encabezado y todas sus cláusulas
    (`_descendant`), la deja validada por `user` y lo registra (P6, evento `matrix_version`,
    acción `rebuilt`). Si ninguna fila cambia no crea nada. Devuelve la versión nueva y la
    cantidad de filas cambiadas; lanza `MeasurementRefused` si no hay nada que rehacer."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION + ".rebuild",
                            channel=channel)
    source = latest_validated(procedure)
    if source is None:
        raise MeasurementRefused("El procedimiento no tiene una matriz validada.")
    if procedure.matrix_versions.filter(status=m.VersionStatus.DRAFT).exists():
        raise MeasurementRefused("Hay un borrador abierto: se termina o se descarta antes.")
    plans = {}
    for requirement in source.requirements.filter(category="tecnico"):
        first = requirement.quotes.order_by("order").select_related("segment__reading").first()
        if first is None or not requirement.items:
            continue
        reading = first.segment.reading
        header = next((item["key"] for item in reading.items
                       if item["number"] == requirement.items[0]), None)
        if header is None:
            continue
        chosen = [s for s in reading.segments.order_by("order") if _descendant(s.key, header)]
        current = [q.segment_id for q in requirement.quotes.order_by("order")]
        if [s.pk for s in chosen] != current:
            plans[requirement.number] = chosen
    if not plans:
        raise MeasurementRefused(
            "Las filas técnicas de la última matriz validada ya tienen todas sus cláusulas.")
    with transaction.atomic():
        number = procedure.matrix_versions.order_by("-number").first().number + 1
        version = m.MatrixVersion.objects.create(
            procedure=procedure, number=number, status=m.VersionStatus.DRAFT,
            level=source.level, process=source.process, run=None, based_on=source,
            created_by=user)
        copied = copy_version(source, version)
        for requirement in version.requirements.filter(number__in=plans):
            requirement.quotes.all().delete()
            for order, segment in enumerate(plans[requirement.number], start=1):
                m.RequirementQuote.objects.create(
                    requirement=requirement, order=order, segment=segment,
                    char_start=segment.char_start, char_end=segment.char_end,
                    text=segment.text, scope=m.QuoteScope.PROPIA)
        version.status = m.VersionStatus.VALIDATED
        version.validated_at = timezone.now()
        version.validated_by = user
        version.save(update_fields=["status", "validated_at", "validated_by"])
        audit.record(
            EventType.MATRIX_VERSION, outcome=Outcome.OK, channel=channel, user=user,
            detail={"procedure": procedure.pk, "version": version.pk,
                    "version_number": version.number, "based_on": source.pk,
                    "based_on_number": source.number, "action": "rebuilt",
                    "reason": "clausulas_de_renglon", "rows": sorted(plans),
                    "copied": copied})
    return version, len(plans)
