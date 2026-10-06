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
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

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
from evaluon.tenders.evaluation import ratio
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
# Motivo de la lista -> motivo de la duda del sistema.
MOTIVES = {"falta_hoja_compliance": am.Doubt.EXTERNO, "pagina_ilegible": am.Doubt.LECTURA_INCOMPLETA,
           "lectura_incompleta": am.Doubt.LECTURA_INCOMPLETA}

# Umbrales escritos antes de medir (plan 004, "Umbrales"). Cada uno es `(mínimo, bloquea)` o,
# para los que cuentan fallas, `(máximo, bloquea)`. `None` = se informa sin tope.
THRESHOLDS_SMALL = {
    "match": (1.0, True), "contradictions": (0, True), "no_citation": (0, True),
    "literal": (1.0, True), "missing_document": (1.0, True), "questions": (1.0, True),
    "fragments": (None, False), "matrix": (1.0, True),
}
THRESHOLDS_CASE_00 = {
    "match": (0.80, True), "contradictions": (0, True), "no_citation": (0, True),
    "literal": (1.0, True), "missing_document": (None, False), "questions": (None, False),
    "fragments": (0.90, True), "matrix": (1.0, True),
}
MAXIMUMS = ("contradictions", "no_citation")

LABELS = {
    "match": "Coincidencia con el esperado (REQ-052)",
    "contradictions": "Contradicciones: «cumple» por «no cumple» o al revés (REQ-052)",
    "no_citation": "«Cumple» o «no cumple» sin cita de la oferta (REQ-053)",
    "literal": "Citas de la oferta iguales al recorte del texto canónico (REQ-053)",
    "missing_document": "«No se encontró el documento» con la cita del pliego (REQ-060)",
    "questions": "Pregunta formulada donde falta un dato (REQ-055)",
    "fragments": "Propuestas que citan el fragmento de la ficha (REQ-054)",
    "matrix": "Ofertas evaluadas con un resultado por par (REQ-059)",
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
    return ExpectedPair(
        requirement=ident, result=RESULTS[raw], base=base, doubt=MOTIVES.get(motive, ""),
        question=str(entry.get("pregunta") or "").lower() in ("si", "sí", "true"),
        citations=list(citations), via=str(entry.get("via") or ""),
        note=str(entry.get("nota") or entry.get("fundamento") or ""))


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
        for unreadable in entry.unreadable_pages:
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


def _match(pair, result):
    """Si el resultado propuesto coincide con el esperado del par."""
    if result.outcome != pair.result:
        # Decisión 1 del responsable: lo externo sin hoja de compliance coincide con el
        # «cumple» del dictamen (la abstención correcta, P3 y P9).
        return (pair.base == "externa" and pair.result == am.Outcome.CUMPLE
                and result.outcome == am.Outcome.NO_DETERMINADO
                and result.doubt == am.Doubt.EXTERNO)
    return not pair.doubt or result.doubt == pair.doubt


def _contradiction(pair, result):
    return {pair.result, result.outcome} == {am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE}


def _canonical_document(name, equivalents):
    seen = set()
    while name in equivalents and name not in seen:
        seen.add(name)
        name = equivalents[name]
    return name


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
    return {
        "requisito": pair.requirement, "base": pair.base, "via": pair.via,
        "esperado": pair.result, "motivo_esperado": pair.doubt,
        "obtenido": result.outcome, "motivo": result.doubt,
        "coincide": _match(pair, result), "contradiccion": _contradiction(pair, result),
        "sin_documento_donde_cumple": (result.outcome == am.Outcome.SIN_DOCUMENTO
                                       and pair.result == am.Outcome.CUMPLE),
        "citas_oferta": len(cites), "citas_literales": literal,
        "sin_cita": concluded and not cites,
        "pregunta_esperada": pair.question, "pregunta_formulada": asked,
        "cita_pliego": pliego, "fragmento": fragment_ok,
        "anomalias": [], "resultado_pk": result.pk,
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


def measure_offer(entry, offer, run, mapping, finder, fragments, equivalents):
    """Mide una oferta contra su lista; `run` es la evaluación recién hecha."""
    results = {r.requirement_id: r for r in run.results.select_related("requirement")}
    records = []
    for pair in entry.pairs:
        requirement = mapping.get(pair.requirement)
        result = results.get(requirement.pk) if requirement else None
        if result is None:
            records.append({"requisito": pair.requirement, "base": pair.base,
                            "esperado": pair.result, "obtenido": None, "coincide": False,
                            "contradiccion": False, "sin_cita": False, "citas_oferta": 0,
                            "citas_literales": 0, "pregunta_esperada": pair.question,
                            "pregunta_formulada": False, "cita_pliego": False,
                            "fragmento": None, "sin_documento_donde_cumple": False,
                            "anomalias": ["sin_resultado"], "resultado_pk": None})
            continue
        records.append(measure_pair(pair, result, requirement, offer, finder,
                                    fragments, equivalents))
    proposed = [r for r in records if r["obtenido"] == am.Outcome.NO_CUMPLE]
    proposed_ids = [r["requisito"] for r in proposed]
    discard_ok = None
    if entry.discarded in ("si", "no", "parcial"):
        want = entry.discarded != "no"
        discard_ok = bool(proposed_ids) == want
        if discard_ok and entry.discarded == "si" and entry.discard.get("requisito"):
            discard_ok = entry.discard["requisito"] in proposed_ids
    return {
        "records": records, "proposed_discard": proposed_ids, "discard_ok": discard_ok,
        "counts": run.counts, "timings": run.timings, "anomalies": run.anomalies,
        "steps": _steps_summary(run), "run": run.pk, "number": run.number,
        "unread_pages": run.counts.get("unread_pages", 0),
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
    return {
        "pairs": len(records),
        "match": _sum(records, lambda r: r["coincide"]),
        "contradictions": [(r["requisito"], r["esperado"], r["obtenido"])
                           for r in records if r["contradiccion"]],
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
        elif value["total"] and value["rate"] < limit:
            failed.append(f"{LABELS[name]}: {proportion_text(value)}, mínimo {_pct(limit)}")
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

    @property
    def blocking(self):
        return blocking(self.total, self.expected.case)


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
            clock=time.monotonic):
    """Comprueba la lista, evalúa todas las ofertas con el canal `eval`, las mide y guarda la
    carpeta de la corrida en `runs_dir`. Devuelve el `Report`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    if not expected.approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    verification = verify_expected(expected, offers)
    if not verification.ok:
        raise MeasurementRefused("La lista no se puede usar:\n" + "\n".join(verification.lines))
    version = latest_validated(procedure)
    if version is None:
        raise MeasurementRefused("El procedimiento no tiene una matriz validada.")
    mapping = _requirement_mapping(version, expected, fichas)
    started_at = timezone.now()
    started = clock()
    request, runs = run_evaluation(user, procedure, clock=clock)
    elapsed = clock() - started
    by_offer = {run.offer_id: run for run in runs}
    finder = PageFinder()
    results = []
    for entry in expected.offers:
        offer = offers[entry.bidder]
        run = by_offer.get(offer.pk)
        if run is None:
            raise MeasurementRefused(f"La oferta {offer.number} no quedó evaluada.")
        fragments, equivalents = _fragments_for(expected, entry, fichas)
        measures = measure_offer(entry, offer, run, mapping, finder, fragments, equivalents)
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
                    round(elapsed, 3))
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
              f"- Descarte propuesto igual al esperado: {proportion_text(total['discards'])}.",
              "- Orden económico: lo muestra la matriz de la evaluación (T-152); no se mide acá.",
              f"- Páginas sin leer en las ofertas: {total['unread_pages']}.", "",
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
