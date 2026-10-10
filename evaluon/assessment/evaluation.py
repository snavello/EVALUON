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
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

import yaml
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
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
QUESTIONS_SAMPLE_FILE = "muestra-preguntas.md"
# La pregunta se dirige al oferente si le pide algo («¿Podría el oferente…?», «solicitamos al
# oferente…», «el oferente deberá aclarar…», o una orden que empieza la pregunta). Los patrones
# son constantes del módulo: si la forma de las preguntas cambia, se ajustan acá.
ADDRESSED_TO_BIDDER = re.compile(
    r"\b(?:podr[ií]a|solicitamos|solicitar|pedimos|ruego|rogamos|favor\s+de"
    r"|se\s+(?:le\s+)?(?:pide|solicita|ruega))\b[^.?!]{0,60}\boferente\b"
    r"|\boferente\b\s+(?:deber[aá]|debe|tendr[aá]|podr[aá])\b"
    r"|\b(?:al|a\s+la)\s+(?:oferente|firma|empresa)\b[^.?!]{0,40}\b(?:aclare|aclarar|"
    r"presente|presentar|informe|informar|acompañe|acompañar|adjunte|adjuntar|indique|indicar)"
    r"|^\W*(?:aclare|presente|informe|acompañe|adjunte|indique|env[ií]e|confirme)\b",
    re.IGNORECASE)
COMMISSION = re.compile(r"\bcomisi[oó]n\b", re.IGNORECASE)
NO_OFFER_TEXT = re.compile(
    r"no\s+(?:se\s+)?(?:encontr|consta|hay|figura)|sin\s+texto|ning[uú]n", re.IGNORECASE)
# Mínimos que piden «más de» (la spec: coincidencia de más del 80 % en el caso-00).
MORE_THAN = {CASE_00: ("match",)}

LABELS = {
    "match": "Coincidencia con el esperado según el tipo de par (REQ-052)",
    "contradictions": "Contradicciones: «cumple» por «no cumple», hecho técnico o dato del "
                      "Portal opuesto (REQ-052)",
    "no_citation": "«Cumple» o «no cumple» sin cita de la oferta (REQ-053)",
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
                    "low_confidence", []))
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
    if kind == "ilegible":
        return (result.outcome == am.Outcome.NO_DETERMINADO
                and result.doubt == am.Doubt.NO_SE_PUDO_LEER and _unreadable_equal(pair, facts))
    if kind == "portal":
        return _portal_check(pair, result)[0]
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
    return {_reference(pair), result.outcome} == {am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE}


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


def cell_counts(run):
    """Las celdas de una evaluación y cuántas son «no determinado»; de esas, cuántas esperan un
    documento ausente (informe técnico u hoja de compliance) y no cuentan (REQ-104)."""
    total = undetermined = waiting = 0
    for result in run.results.all():
        total += 1
        if result.outcome == am.Outcome.NO_DETERMINADO:
            undetermined += 1
            waiting += result.doubt in WAITING_DOCUMENT
    return {"total": total, "undetermined": undetermined, "waiting_document": waiting}


def portal_cell_record(result, kind, value, matches):
    """Una celda del Portal medida (REQ-103): si la propuesta es «cumple» con la cita del Portal
    del dato esperado, y si es «cumple» con un dato que no coincide (el esperado no coincide con
    el pliego, o la cita del Portal trae otro valor)."""
    cites = [c for c in _portal_cites(result) if c.portal_kind == kind]
    with_value = any(portal_value_in(kind, c.text, value) for c in cites)
    cumple = result.outcome == am.Outcome.CUMPLE
    return {"tipo_portal": kind, "coincide_dato": matches, "obtenido": result.outcome,
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
    own = re.sub(r"«[^»]*»", " ", text or "")
    for quoted in [requirement_text, *offer_texts]:
        own = own.replace(quoted, " ") if quoted else own
    directed = not ADDRESSED_TO_BIDDER.search(own)
    return {"requisito_ok": requirement_ok, "conclusion_ok": conclusion_ok, "texto_ok": text_ok,
            "dirigida_ok": directed, "nombra_comision": bool(COMMISSION.search(text or "")),
            "conforme": requirement_ok and conclusion_ok and text_ok and directed}


def question_records(run):
    """Las preguntas de una evaluación con su forma comprobada. El texto de la pregunta, del
    requisito y de la oferta va en `detalle` (local, no al resumen público)."""
    records = []
    questions = am.Question.objects.filter(result__run=run).select_related(
        "requirement", "result", "offer").order_by("result_id", "id")
    for question in questions:
        result = question.result
        first = question.requirement.quotes.order_by("order").first()
        requirement_text = first.text if first else ""
        offer_texts = list(result.citations.filter(kind=am.CitationKind.OFERTA)
                           .order_by("order").values_list("text", flat=True))
        doubt = am.Doubt(result.doubt).label if result.doubt else ""
        form = question_form(
            question.text, requirement_text=requirement_text,
            requirement_number=question.requirement.number,
            outcome_label=am.Outcome(result.outcome).label, doubt_label=doubt,
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
    concluded = result.outcome in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE)
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
    return {
        "requisito": pair.requirement, "base": pair.base, "via": pair.via, "tipo": kind,
        "esperado": pair.result, "motivo_esperado": pair.doubt,
        "obtenido": result.outcome, "motivo": result.doubt,
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
        "sin_cita": concluded and not cites,
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


def measure_offer(entry, offer, run, mapping, finder, fragments, equivalents, cells=()):
    """Mide una oferta contra su lista; `run` es la evaluación recién hecha. `cells` son las
    celdas del Portal del archivo aparte que corresponden a esta oferta (T-238)."""
    results = {r.requirement_id: r for r in run.results.select_related("requirement")}
    records = []
    for pair in entry.pairs:
        requirement = mapping.get(pair.requirement)
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
        "cells": cell_counts(run), "portal_cells": list(portal_cells.values()),
        "questions": question_records(run),
    }


def _sum(records, predicate, universe=None):
    universe = records if universe is None else universe
    return ratio(sum(1 for r in universe if predicate(r)), len(universe))


def aggregate(measures):
    """Reúne las cuentas de todas las ofertas."""
    records = [r for m_ in measures for r in m_["records"]]
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
        "match": _sum(records, lambda r: r["coincide"]),
        "match_by_type": {t: _sum([r for r in records if r.get("tipo", "oferta") == t],
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
                       for o in am.Outcome.values},
        "mismatches": [(r["requisito"], r["esperado"], r["obtenido"], r["motivo"])
                       for r in records if not r["coincide"]],
        "seconds": round(sum(m_["timings"].get("total_seconds", 0) for m_ in measures), 3),
        "model_requests": sum(m_["steps"]["pedidos"] for m_ in measures),
        "tokens_prompt": sum(m_["steps"]["tokens_pedido"] for m_ in measures),
        "tokens_output": sum(m_["steps"]["tokens_salida"] for m_ in measures),
        "unread_pages": sum(m_["unread_pages"] for m_ in measures),
        **aggregate_015(measures),
    }


def aggregate_015(measures):
    """Las cuentas de la 015 de todas las ofertas (T-238)."""
    counts = [m_.get("cells") or {"total": 0, "undetermined": 0, "waiting_document": 0}
              for m_ in measures]
    total = sum(c["total"] for c in counts)
    undetermined = sum(c["undetermined"] for c in counts)
    waiting = sum(c["waiting_document"] for c in counts)
    portal = [dict(c, oferta=m_.get("offer_number")) for m_ in measures
              for c in m_.get("portal_cells", [])]
    matching = [c for c in portal if c["coincide_dato"]]
    forms = [dict(q, oferta=m_.get("offer_number")) for m_ in measures
             for q in m_.get("questions", [])]
    return {
        "cells": {"total": total, "undetermined": undetermined, "waiting_document": waiting,
                  "counted": undetermined - waiting,
                  "ratio": ratio(undetermined - waiting, total)},
        "portal_cells": {"total": len(portal), "matching": len(matching)},
        "portal_cumple": ratio(sum(c["cumple_con_cita_portal"] for c in matching),
                               len(matching)),
        "portal_wrong": [(c["oferta"], c["fila"]) for c in portal
                         if c["cumple_con_dato_distinto"]],
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
            clock=time.monotonic, portal_cells=None):
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
    started_at = timezone.now()
    video = {"before": video_memory()}
    started = clock()
    request, runs = run_evaluation(user, procedure, clock=clock)
    elapsed = clock() - started
    video["after"] = video_memory()
    by_offer = {run.offer_id: run for run in runs}
    finder = PageFinder()
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
                                 own_cells)
        results.append({"offer": offer.pk, "number": offer.number, "bidder": entry.bidder,
                        "measures": measures, "parameters": run.parameters,
                        "prompt_versions": run.prompt_versions, "models": run.models_used})
    total = aggregate([r["measures"] for r in results])
    base = f"{started_at:%Y%m%d-%H%M%S}-{commit or 'sin-commit'}"
    folder = Path(runs_dir) / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = Path(runs_dir) / f"{base}-{suffix}"
    report = Report(folder, expected, verification, results, total, request,
                    round(elapsed, 3), video=video, portal_cells=portal_cells)
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
    cells = total["cells"]
    portal = total["portal_cells"]
    forms = total["questions_form_parts"]
    memory = max_video_mib(report.video)
    lines += ["",
              f"- Celdas de la evaluación: {cells['total']}; «no determinado»: "
              f"{cells['undetermined']}, de ellas esperan el informe técnico o una hoja de "
              f"compliance: {cells['waiting_document']}; las que cuentan: {cells['counted']}.",
              f"- Celdas del Portal medidas: {portal['total']} ({portal['matching']} con el "
              "dato que coincide con lo que exige el pliego).",
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
