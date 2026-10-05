"""Medición de la ficha contra una lista de fragmentos esperados (REQ-038, REQ-039, REQ-040,
REQ-041, REQ-044; plan 008, "Medición"; ADR-0025).

Reutiliza lo que la 003 ya resolvió (`evaluon/tenders/evaluation.py`, `evaluon/queries/
evaluation.py`): la proporción con su intervalo de Wilson, la proporción como cuenta, el
emparejamiento de citas del pliego (`quotes.locate`) y la forma de la carpeta de la corrida
(`parametros.json`, `resultados.jsonl`, `resumen.md` y `resumen-publico.md`). Lo nuevo es lo
que compara la ficha.

Qué hace:

- `load_expected`: lee y valida la lista (`fichas-esperadas.yaml`): el caso, la matriz con
  sus requisitos (cada uno con su id `M-NNN` y la cita del pliego con que se lo reconoce),
  y por oferta: documentos con huella, fragmentos esperados (documento, página y ancla),
  requisitos sin respuesta, estado esperado de cada renglón, si trae documentación técnica
  y páginas no legibles. Una lista sin visto bueno no se mide (`ExpectedNotApproved`).
- `build_case`: arma el caso en la base (`medir_fichas --caso-chico`): el procedimiento, el
  pliego leído, la matriz validada y las ofertas con sus documentos leídos. Es un armado de
  datos de prueba, no una validación de la Comisión: no deja el hecho `matrix_validation`.
  Es idempotente: lo que ya existe no se vuelve a crear.
- `verify_expected`: sin usar el modelo, comprueba la lista contra las lecturas: la huella
  de cada documento, que cada ancla esté en su página y que cada página no legible lo sea
  (`--verificar-esperada`).
- `measure`: arma la ficha de cada oferta con el canal `eval`, la mide y guarda la carpeta
  de la corrida.

Cómo se cuenta (plan 008, "Cómo se cuenta"):

1. Fragmento encontrado: el esperado se ubica en el texto de su página (búsqueda aproximada,
   similitud de al menos 0,8 sobre ventanas del largo del ancla). Un fragmento propuesto de
   la fila del mismo requisito lo encuentra si está en el mismo documento y la misma página y
   cae en el mismo pasaje o su texto cubre al menos la mitad del pasaje ubicado. No se exige
   igualdad de palabras.
   Una copia idéntica en otro documento de la misma oferta cuenta como encontrada
   (`is_identical_copy`, T-135).
2. Texto literal: todo fragmento mostrado es igual al recorte del texto canónico y cae dentro
   de su pasaje y su página.
3. Sin respuesta: el requisito figura "no se encontró"; un fragmento propuesto ahí es un
   falso hallazgo (se informa, no bloquea).
4. Los fragmentos propuestos sin pareja se cuentan y se informan; no bloquean.
5. Renglones: el estado de cotización esperado. Un renglón "no se pudo leer" con páginas sin
   leer en la oferta se informa aparte (no es acierto ni "no cotizado"); sin esas páginas, es
   una falla.
6. Páginas: toda página no legible esperada está en la lista de no leídas o de baja
   confianza, y ninguna página sin texto queda fuera de la lista.
7. Síntesis: ninguna con palabras de juicio.
8. Tiempo: por oferta y por página, informado, sin máximo.

Decisiones fuera del plan (T-130): el id `M-NNN` se traduce a la fila de la matriz con el
bloque `matriz.requisitos` de la misma lista (id, clase, cita del pliego o renglón); el
caso-00 lo trae armado por el Coordinador desde la lista de la 003.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.offers import models as om
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets as sheets_service
from evaluon.queries.evaluation import proportion_text
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.evaluation import ratio
from evaluon.tenders.proposal import quotes
from evaluon.tenders.services import documents as tender_documents
from evaluon.tenders.services import procedures as tender_procedures
from evaluon.tenders.services.validation import latest_validated

OPERATION = "evaluon.offers.evaluation.measure"

RUN_FILE_NAMES = ("parametros.json", "resultados.jsonl", "resumen.md", "resumen-publico.md")
ANCHOR_SIMILARITY = 0.8
COVERS = 0.5
STATES = ("cotizado", "no_cotizado")

# Umbrales del caso chico (plan 008, "Umbrales"), escritos antes de medir: cada uno es
# `(medida, mínimo)`; "pages_unlisted" es un máximo.
THRESHOLDS = {
    "found": 0.90,
    "literal": 1.0,
    "no_answer": 1.0,
    "synthesis": 1.0,
    "items": 1.0,
    "technical_documents": 1.0,
}
MAX_PAGES_UNLISTED = 0

# Umbrales del caso-00, tres ofertas reales (plan 008, "Umbrales"): "sin respuesta" se informa
# sin tope (`None`) y los renglones piden 90 %. Se aplican cuando la lista dice `caso: caso-00`.
CASE_00 = "caso-00"
THRESHOLDS_CASE_00 = {**THRESHOLDS, "no_answer": None, "items": 0.90}


def thresholds_for(case):
    """Los umbrales que corresponden al caso de la lista (el caso-00 tiene los suyos)."""
    return THRESHOLDS_CASE_00 if case == CASE_00 else THRESHOLDS

LABELS = {
    "found": "Fragmentos esperados encontrados (REQ-039)",
    "literal": "Texto literal (REQ-039)",
    "no_answer": "Requisitos sin respuesta con \"no se encontró\" (REQ-040)",
    "synthesis": "Síntesis sin palabras de juicio (REQ-041)",
    "items": "Renglones con el estado correcto (REQ-044)",
    "technical_documents": "Documentación técnica indicada (REQ-044)",
}


class ExpectedError(ValueError):
    """La lista esperada no se puede leer o está mal formada."""


class ExpectedNotApproved(ExpectedError):
    """La lista no tiene visto bueno: no se usa."""


class MeasurementRefused(ValueError):
    """La medición no se puede hacer."""


# --- Lectura de la lista esperada ---------------------------------------------------------------


@dataclass
class ExpectedFragment:
    id: str
    requirement: str
    document: str
    page: int
    anchor: str


@dataclass
class ExpectedOffer:
    bidder: str
    documents: list
    fragments: list
    no_answer: list
    items: dict
    technical_documents: bool | None
    unreadable_pages: list


@dataclass
class Expected:
    case: str
    path: Path
    sha256: str
    approval: str
    matrix: dict
    requirements: list
    offers: list


def _text(data, name, where):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExpectedError(f"{where}: falta `{name}`")
    return value.strip()


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
    approval = str(data.get("visto_bueno") or "").strip()
    if require_approval and not approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    matrix = data.get("matriz")
    if not isinstance(matrix, dict) or not matrix.get("procedimiento"):
        raise ExpectedError("falta `matriz.procedimiento`")
    requirements = matrix.get("requisitos")
    if not isinstance(requirements, list) or not requirements:
        raise ExpectedError("falta `matriz.requisitos`")
    ids = set()
    for entry in requirements:
        ident = _text(entry, "id", "requisito de la matriz")
        if ident in ids:
            raise ExpectedError(f"requisito {ident}: id repetido")
        ids.add(ident)
        if entry.get("clase") not in ("formal", "economico", "tecnico"):
            raise ExpectedError(f"requisito {ident}: `clase` no válida")
        if entry.get("clase") == "tecnico" and not isinstance(entry.get("renglon"), int):
            raise ExpectedError(f"requisito {ident}: un técnico lleva `renglon` numérico")
        if entry.get("clase") != "tecnico":
            _text(entry, "cita", f"requisito {ident}")
    offers_data = data.get("ofertas")
    if not isinstance(offers_data, list) or not offers_data:
        raise ExpectedError("faltan las `ofertas` de la lista")
    offers, fragment_ids = [], set()
    for offer in offers_data:
        bidder = _text(offer, "oferente", "oferta")
        where = f"oferta «{bidder}»"
        documents = offer.get("documentos")
        if not isinstance(documents, list) or not documents:
            raise ExpectedError(f"{where}: faltan los `documentos`")
        for doc in documents:
            _text(doc, "archivo", where)
            _text(doc, "sha256", where)
        names = {doc["archivo"] for doc in documents}
        fragments = []
        for fragment in offer.get("fragmentos") or []:
            ident = _text(fragment, "id", where)
            if ident in fragment_ids:
                raise ExpectedError(f"{where}: fragmento {ident} repetido")
            fragment_ids.add(ident)
            if fragment.get("requisito") not in ids:
                raise ExpectedError(f"{where}: {ident}: requisito desconocido")
            if fragment.get("documento") not in names:
                raise ExpectedError(f"{where}: {ident}: documento desconocido")
            if not isinstance(fragment.get("pagina"), int):
                raise ExpectedError(f"{where}: {ident}: `pagina` numérica")
            fragments.append(ExpectedFragment(
                id=ident, requirement=fragment["requisito"], document=fragment["documento"],
                page=fragment["pagina"], anchor=_text(fragment, "ancla", where)))
        no_answer = list(offer.get("sin_respuesta") or [])
        unknown = [i for i in no_answer if i not in ids]
        if unknown:
            raise ExpectedError(f"{where}: `sin_respuesta` nombra requisitos desconocidos")
        items = {int(k): v for k, v in (offer.get("renglones") or {}).items()}
        if any(v not in STATES for v in items.values()):
            raise ExpectedError(f"{where}: cada renglón es `cotizado` o `no_cotizado`")
        tech = offer.get("documentacion_tecnica")
        if isinstance(tech, bool):  # YAML lee `no` sin comillas como falso
            tech = "si" if tech else "no"
        if tech not in (None, "si", "no"):
            raise ExpectedError(f"{where}: `documentacion_tecnica` es `si` o `no`")
        offers.append(ExpectedOffer(
            bidder=bidder, documents=documents, fragments=fragments, no_answer=no_answer,
            items=items, technical_documents=None if tech is None else tech == "si",
            unreadable_pages=list(offer.get("paginas_no_legibles") or [])))
    return Expected(case=str(data.get("caso") or ""), path=path,
                    sha256=hashlib.sha256(raw).hexdigest(), approval=approval, matrix=matrix,
                    requirements=requirements, offers=offers)


# --- Armado del caso en la base ---------------------------------------------------------------


def _run_now(job):
    """Corre un pedido ya encolado en este proceso, sin esperar al `worker`: lo toma antes
    (pasa a `running`) para que el `worker` no lo tome también."""
    taken = m.Job.objects.filter(pk=job.pk, status=m.JobStatus.QUEUED).update(
        status=m.JobStatus.RUNNING, started_at=timezone.now())
    if not taken:
        raise MeasurementRefused("Otro proceso tomó el pedido de lectura: espere a que "
                                 "termine y vuelva a correr.")
    job.refresh_from_db()
    jobs.run(job)
    job.refresh_from_db()
    if job.status != m.JobStatus.DONE:
        raise MeasurementRefused(f"La lectura falló: {job.error}")


def _read_pliego(user, procedure, folder, spec):
    path = Path(folder) / spec["archivo"]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != spec.get("sha256"):
        raise MeasurementRefused(f"La huella de {spec['archivo']} no coincide con la lista.")
    loaded = tender_documents.load_document(
        user, procedure, data=data, file_name=path.name, kind=m.DocumentKind.PLIEGO,
        title=spec.get("titulo") or path.stem, channel=Channel.COMMAND)
    _run_now(loaded.job)
    return loaded.document


def _requirement_for(version_requirements, entry):
    """La fila de la matriz que corresponde a `entry` de la lista (por renglón o por cita)."""
    for requirement in version_requirements:
        if entry["clase"] == "tecnico":
            if requirement.category == "tecnico" and requirement.items == [entry["renglon"]]:
                return requirement
            continue
        if requirement.category == "tecnico":
            continue
        first = next(iter(requirement.quotes.order_by("order")), None)
        if first is not None and _normal(entry["cita"]) in _normal(first.text):
            return requirement
    return None


def _normal(text):
    return " ".join((text or "").split()).lower()


def _create_matrix(user, procedure, document, entries):
    """La matriz validada del caso: un requisito por entrada de la lista, con su cita
    ubicada en un tramo del pliego."""
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
                chosen = [s for s in segments
                          if s.key == header or s.key.startswith(f"{header}/")] \
                    if header else []
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
    Idempotente. Lanza `MeasurementRefused` si un archivo no coincide con su huella."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
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
        document = _read_pliego(user, procedure, folder, pliego)
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
            _run_now(loaded.job)
        offers[offer_expected.bidder] = offer
    return procedure, offers


# --- Comprobación de la lista contra las lecturas -------------------------------------------------


def _best_ratio(text, needle):
    """La mayor similitud de `needle` con una ventana de `text` del mismo largo."""
    text, needle = _normal(text), _normal(needle)
    if not needle:
        return 0.0
    if needle in text:
        return 1.0
    size = len(needle)
    if len(text) <= size:
        return SequenceMatcher(None, text, needle).ratio()
    step = max(1, size // 10)
    return max(SequenceMatcher(None, text[i:i + size], needle).ratio()
               for i in range(0, len(text) - size + 1, step))


def locate_anchor(reading, page, anchor):
    """El pasaje de la página `page` de `reading` donde está `anchor`, o `None`: el de mayor
    similitud si llega a `ANCHOR_SIMILARITY`."""
    best, best_ratio = None, 0.0
    for passage in reading.passages.filter(page=page).order_by("order"):
        value = _best_ratio(passage.text, anchor)
        if value > best_ratio:
            best, best_ratio = passage, value
    return best if best_ratio >= ANCHOR_SIMILARITY else None


@dataclass
class Verification:
    ok: bool = True
    lines: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def fail(self, text):
        self.ok = False
        self.lines.append("FALLA: " + text)


def _reading_of(offer, file_name):
    document = offer.documents.filter(file_name=file_name).first()
    if document is None:
        return None, None
    return document, document.readings.order_by("-sequence").first()


def verify_expected(expected, offers):
    """Comprueba la lista contra las lecturas, sin usar el modelo. `offers` es
    `{oferente: oferta}`."""
    result = Verification()
    anchors = pages = documents = 0
    for entry in expected.offers:
        offer = offers.get(entry.bidder)
        if offer is None:
            result.fail("una oferta de la lista no está cargada")
            continue
        for spec in entry.documents:
            document, reading = _reading_of(offer, spec["archivo"])
            documents += 1
            if document is None or document.file_sha256 != spec["sha256"]:
                result.fail(f"{spec['archivo']}: la huella no coincide o no está cargado")
            elif reading is None:
                result.fail(f"{spec['archivo']}: todavía no se leyó")
        for fragment in entry.fragments:
            _, reading = _reading_of(offer, fragment.document)
            anchors += 1
            if reading is None or locate_anchor(reading, fragment.page, fragment.anchor) is None:
                result.fail(f"{fragment.id}: el ancla no está en la página {fragment.page} "
                            f"de {fragment.document}")
        for unreadable in entry.unreadable_pages:
            _, reading = _reading_of(offer, unreadable["documento"])
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


# --- Medición de una ficha -----------------------------------------------------------------------


def _pct(value):
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def _requirement_map(version, entries):
    requirements = list(version.requirements.filter(
        state__in=sheets_service.FIRM_STATES).order_by("number"))
    mapping = {}
    for entry in entries:
        requirement = _requirement_for(requirements, entry)
        if requirement is not None:
            mapping[entry["id"]] = requirement
    return mapping


def _entry_of(sheet, requirement):
    return sheet.entries.filter(requirement=requirement).first()


def _literal(fragment):
    """El fragmento es igual al recorte del texto canónico y cae dentro de su pasaje."""
    passage = fragment.passage
    canonical = passage.reading.canonical_text
    return (canonical[fragment.char_start:fragment.char_end] == fragment.text
            and passage.char_start <= fragment.char_start
            and fragment.char_end <= passage.char_end
            and passage.text == canonical[passage.char_start:passage.char_end])


def _covers(fragment, passage):
    overlap = max(0, min(fragment.char_end, passage.char_end)
                  - max(fragment.char_start, passage.char_start))
    return overlap >= COVERS * max(1, passage.char_end - passage.char_start)


def _flat(text):
    return " ".join((text or "").lower().split())


def _page_text(reading_id, page, cache):
    key = (reading_id, page)
    if key not in cache:
        cache[key] = _flat(" ".join(om.Passage.objects.filter(
            reading_id=reading_id, page=page).order_by("order").values_list("text", flat=True)))
    return cache[key]


def is_identical_copy(passage, located, cache):
    """El `passage` es el mismo lugar que `located` en otro documento de la misma oferta
    (T-135, decisión del responsable: una copia idéntica cuenta como encontrada). Regla:
    el mismo pasaje literal (texto igual, sin distinguir mayúsculas ni espacios) o el mismo
    lugar (misma clave de pasaje) de una página cuyo texto completo es igual. Dos
    documentos distintos que no son copias no coinciden."""
    if passage.reading_id == located.reading_id:
        return False
    if _flat(passage.text) == _flat(located.text):
        return True
    return (passage.key == located.key
            and _page_text(passage.reading_id, passage.page, cache) != ""
            and _page_text(passage.reading_id, passage.page, cache)
            == _page_text(located.reading_id, located.page, cache))


def measure_sheet(sheet, entry, offer, mapping):
    """Mide una ficha contra lo esperado de su oferta. Devuelve un diccionario con las
    medidas, las líneas de detalle y lo que bloquea."""
    lines = []
    readings = [r for r in offers_service.latest_readings(offer)]
    by_document = {r.document.file_name: r for r in readings}

    # 1. Fragmentos esperados encontrados.
    found = 0
    matched_fragments = set()
    page_cache = {}
    for expected in entry.fragments:
        requirement = mapping.get(expected.requirement)
        reading = by_document.get(expected.document)
        cause, ok = "", False
        located = locate_anchor(reading, expected.page, expected.anchor) if reading else None
        row = _entry_of(sheet, requirement) if requirement else None
        if requirement is None:
            cause = "requisito_sin_fila"
        elif located is None:
            cause = "ancla_no_ubicada"
        elif row is None:
            cause = "sin_fila_en_la_ficha"
        else:
            for fragment in row.fragments.exclude(state="quitado").select_related(
                    "passage__reading__document"):
                same_place = (fragment.passage.reading_id == reading.pk
                              and fragment.passage.page == expected.page)
                copy = is_identical_copy(fragment.passage, located, page_cache)
                if copy or (same_place and (fragment.passage_id == located.pk
                                            or _covers(fragment, located))):
                    ok = True
                    matched_fragments.add(fragment.pk)
                    break
            cause = "" if ok else ("no_encontrado" if row.outcome == "no_encontrado"
                                   else "otro_pasaje")
        found += ok
        lines.append({"tipo": "fragmento", "id": expected.id, "encontrado": ok,
                      "causa": cause})

    # 2. Texto literal de todo lo mostrado, 4. fragmentos de más.
    shown = list(om.Fragment.objects.filter(entry__sheet=sheet).exclude(state="quitado")
                 .select_related("passage__reading"))
    literal_ok = sum(1 for f in shown if _literal(f))
    extra = [f.pk for f in shown if f.pk not in matched_fragments]

    # 3. Sin respuesta.
    no_answer_ok, false_findings = 0, []
    for ident in entry.no_answer:
        requirement = mapping.get(ident)
        row = _entry_of(sheet, requirement) if requirement else None
        ok = row is not None and row.outcome == om.Outcome.NO_ENCONTRADO
        no_answer_ok += ok
        if not ok:
            false_findings.append(ident)
        lines.append({"tipo": "sin_respuesta", "id": ident, "no_encontrado": ok})

    # 5. Renglones.
    unread_pages = [p for r in readings for p in r.report.get("unread", [])]
    items_ok, items_total, items_unreadable = 0, 0, []
    for number, state in sorted(entry.items.items()):
        row = sheet.entries.filter(requirement__category="tecnico",
                                   requirement__items=[number]).first()
        actual = row.quoted if row else ""
        if actual == om.Quoted.NO_SE_PUDO_LEER and unread_pages:
            items_unreadable.append(number)
            lines.append({"tipo": "renglon", "renglon": number, "esperado": state,
                          "ficha": actual, "aparte": True})
            continue
        items_total += 1
        items_ok += actual == state
        lines.append({"tipo": "renglon", "renglon": number, "esperado": state,
                      "ficha": actual, "ok": actual == state})

    # Documentación técnica.
    tech_ok = None
    if entry.technical_documents is not None:
        tech_ok = bool(sheet.technical_documents.get("present")) == entry.technical_documents

    # 7. Síntesis sin juicio.
    syntheses = [e.synthesis for e in sheet.entries.all() if e.synthesis]
    synthesis_ok = sum(1 for text in syntheses if not sheets_service.judgment_words(text))

    # 6. Páginas.
    pages_ok, pages_total = 0, 0
    for unreadable in entry.unreadable_pages:
        reading = by_document.get(unreadable["documento"])
        listed = reading is not None and any(
            p["page"] == unreadable["pagina"]
            for p in reading.report.get("unread", []) + reading.report.get("low_confidence", []))
        pages_total += 1
        pages_ok += listed
    unlisted = [{"documento": r.document.file_name, "pagina": n}
                for r in readings for n in r.report.get("without_text_unlisted", [])]
    pages = sum(r.report.get("pages", 0) for r in readings)
    low = sum(len(r.report.get("low_confidence", [])) for r in readings)

    seconds = sheet.timings.get("total_seconds", 0)
    return {
        "found": ratio(found, len(entry.fragments)),
        "literal": ratio(literal_ok, len(shown)),
        "no_answer": ratio(no_answer_ok, len(entry.no_answer)),
        "synthesis": ratio(synthesis_ok, len(syntheses)),
        "items": ratio(items_ok, items_total),
        "items_unreadable": items_unreadable,
        "technical_documents": (ratio(int(bool(tech_ok)), 1) if tech_ok is not None
                                else ratio(0, 0)),
        "expected_pages": ratio(pages_ok, pages_total),
        "pages_unlisted": unlisted,
        "false_findings": false_findings,
        "extra_fragments": len(extra),
        "unread_pages": len(unread_pages),
        "low_confidence_pages": low,
        "pages": pages,
        "sheet": sheet.pk,
        "anomalies": sheet.anomalies,
        "counts": sheet.counts,
        "seconds": seconds,
        "seconds_per_page": round(seconds / pages, 3) if pages else None,
        "lines": lines,
    }


def _sum(measures, name):
    ok = sum(x[name]["ok"] for x in measures)
    total = sum(x[name]["total"] for x in measures)
    return ratio(ok, total)


def aggregate(measures):
    """Reúne las medidas de todas las ofertas."""
    result = {name: _sum(measures, name) for name in
              ("found", "literal", "no_answer", "synthesis", "items", "technical_documents",
               "expected_pages")}
    result["pages_unlisted"] = [p for x in measures for p in x["pages_unlisted"]]
    result["false_findings"] = [i for x in measures for i in x["false_findings"]]
    result["items_unreadable"] = [n for x in measures for n in x["items_unreadable"]]
    result["extra_fragments"] = sum(x["extra_fragments"] for x in measures)
    result["pages"] = sum(x["pages"] for x in measures)
    result["seconds"] = round(sum(x["seconds"] for x in measures), 3)
    result["anomalies"] = [a for x in measures for a in x["anomalies"]]
    return result


def blocking(total, case=None):
    """Lo que no llega al umbral del caso (vacío si todo cumple); por omisión, el del caso
    chico."""
    failed = []
    for name, minimum in thresholds_for(case).items():
        value = total[name]
        if minimum is not None and value["total"] and value["rate"] < minimum:
            failed.append(f"{LABELS[name]}: {proportion_text(value)}, mínimo {_pct(minimum)}")
    pages = total["expected_pages"]
    if pages["total"] and pages["ok"] < pages["total"]:
        failed.append("Páginas no legibles esperadas en las listas: "
                      f"{pages['ok']} de {pages['total']}")
    if len(total["pages_unlisted"]) > MAX_PAGES_UNLISTED:
        failed.append(f"Páginas sin texto ni lista: {len(total['pages_unlisted'])}, máximo "
                      f"{MAX_PAGES_UNLISTED}")
    return failed


# --- Corrida ----------------------------------------------------------------------------------------


@dataclass
class Report:
    folder: Path
    expected: Expected
    verification: Verification
    results: list
    total: dict

    @property
    def blocking(self):
        return blocking(self.total, self.expected.case)


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


def measure(user, procedure, expected, offers, runs_dir, *, commit=None,
            clock=time.monotonic):
    """Comprueba la lista, arma la ficha de cada oferta con el canal `eval`, la mide y guarda
    la carpeta de la corrida en `runs_dir`. Devuelve el `Report`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    if not expected.approval:
        raise ExpectedNotApproved("la lista no tiene visto bueno: no se usa")
    verification = verify_expected(expected, offers)
    if not verification.ok:
        raise MeasurementRefused("La lista no se puede usar:\n" + "\n".join(verification.lines))
    started_at = timezone.now()
    version = latest_validated(procedure)
    if version is None:
        raise MeasurementRefused("El procedimiento no tiene una matriz validada.")
    mapping = _requirement_map(version, expected.requirements)
    missing = [e["id"] for e in expected.requirements if e["id"] not in mapping]
    if missing:
        raise MeasurementRefused("Requisitos de la lista que no están en la matriz validada: "
                                 + ", ".join(missing))
    results = []
    for entry in expected.offers:
        offer = offers[entry.bidder]
        started = clock()
        sheet = sheets_service.build_sheet(offer, user, channel=om.SheetChannel.EVAL,
                                           audit_channel=Channel.EVAL, clock=clock)
        elapsed = clock() - started
        measures = measure_sheet(sheet, entry, offer, mapping)
        results.append({"offer": offer.pk, "number": offer.number, "bidder": entry.bidder,
                        "sheet": sheet.pk, "elapsed_seconds": round(elapsed, 3),
                        "measures": measures, "parameters": sheet.parameters,
                        "prompt_versions": sheet.prompt_versions, "models": sheet.models_used})
    total = aggregate([r["measures"] for r in results])
    base = f"{started_at:%Y%m%d-%H%M%S}-{commit or 'sin-commit'}"
    folder = Path(runs_dir) / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = Path(runs_dir) / f"{base}-{suffix}"
    report = Report(folder, expected, verification, results, total)
    _write(report, procedure, version, started_at, commit)
    return report


def _write(report, procedure, version, started_at, commit):
    report.folder.mkdir(parents=True, exist_ok=False)
    expected = report.expected
    parameters = {
        "caso": expected.case, "procedimiento": procedure.number,
        "version_matriz": version.number, "iniciada": started_at,
        "commit": commit or "sin-commit",
        "lista": {"sha256": expected.sha256, "visto_bueno": expected.approval,
                  "ofertas": len(expected.offers),
                  "fragmentos": sum(len(o.fragments) for o in expected.offers)},
        "umbrales": {**thresholds_for(expected.case), "paginas_sin_lista_maximo": MAX_PAGES_UNLISTED},
        "comprobacion": dict(report.verification.counts),
        "fichas": [{"oferta": r["number"], "ficha": r["sheet"], "parametros": r["parameters"],
                    "instrucciones": r["prompt_versions"], "modelos": r["models"]}
                   for r in report.results],
    }
    (report.folder / "parametros.json").write_text(
        _dumps(parameters, indent=2) + "\n", encoding="utf-8")
    with (report.folder / "resultados.jsonl").open("w", encoding="utf-8") as handle:
        for result in report.results:
            for line in result["measures"]["lines"]:
                handle.write(_dumps({"oferta": result["number"], **line}) + "\n")
    (report.folder / "resumen.md").write_text(_summary(report, public=False),
                                              encoding="utf-8")
    (report.folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                                      encoding="utf-8")


def _verdict(total, case=None):
    failed = blocking(total, case)
    return "Cumple el umbral." if not failed else "No cumple: " + "; ".join(failed) + "."


def _summary(report, *, public):
    total = report.total
    lines = [
        f"# Medición de fichas · {report.expected.case}", "",
        f"Lista: `{report.expected.sha256[:12]}` · visto bueno: {report.expected.approval}",
        "", "## Resultado contra el umbral", "",
        "| Medida | Umbral | Medido |", "|---|---|---|"]
    for name, minimum in thresholds_for(report.expected.case).items():
        required = "informado, sin tope" if minimum is None else f"{_pct(minimum)} o más"
        lines.append(f"| {LABELS[name]} | {required} | {proportion_text(total[name])} |")
    lines.append(f"| Páginas sin texto ni lista (REQ-038) | {MAX_PAGES_UNLISTED} | "
                 f"{len(total['pages_unlisted'])} |")
    pages = total["expected_pages"]
    lines.append("| Páginas no legibles esperadas en las listas (REQ-038) | todas | "
                 f"{pages['ok']} de {pages['total']} |")
    lines += ["", _verdict(total, report.expected.case), "", "## Se informa, no bloquea", "",
              f"- Fragmentos mostrados sin pareja en la lista: {total['extra_fragments']}.",
              f"- Falsos hallazgos (fragmento en un requisito sin respuesta): "
              f"{len(total['false_findings'])}.",
              f"- Renglones «no se pudo leer» informados aparte: "
              f"{len(total['items_unreadable'])}.",
              f"- Anomalías del armado: {len(total['anomalies'])}.", "",
              "## Tiempo", ""]
    for result in report.results:
        measures = result["measures"]
        lines.append(f"- Oferta {result['number']}: {result['elapsed_seconds']} s en total, "
                     f"{measures['pages']} páginas, "
                     f"{measures['seconds_per_page']} s por página, "
                     f"{measures['counts'].get('model_requests', 0)} pedidos al modelo "
                     f"({measures['counts'].get('retries', 0)} reintentos).")
    if not public:
        lines += ["", "## Detalle", ""]
        for result in report.results:
            lines.append(f"### Oferta {result['number']} · {result['bidder']}")
            for line in result["measures"]["lines"]:
                lines.append("- " + _dumps(line))
    else:
        lines += ["", "Los datos de los oferentes no figuran en este resumen."]
    return "\n".join(lines) + "\n"


