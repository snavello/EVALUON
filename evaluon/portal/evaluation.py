"""Medición de la importación del Portal con las páginas guardadas (REQ-045 a REQ-051; plan
012, "Medición"; ADR-0025; T-145).

Sin conexión: la exploración se reproduce con un transporte que sirve los archivos guardados en
`<caso>/portal/` (cada `.bin` con su `.meta.json`: la URL o el destino del formulario, y lo que
respondió el Portal). Nunca abre un socket. Una solicitud que no está guardada responde 404 y
queda anotada: significa que el lector pide algo que no se guardó.

Reutiliza lo que ya resolvieron la 003 y la 008: la proporción (`tenders.evaluation.ratio`), su
margen de error (`queries.evaluation.proportion_text`) y la forma de la carpeta de la corrida
(`parametros.json`, `resultados.jsonl`, `resumen.md` y `resumen-publico.md`).

Qué mide, por caso (umbral: 100 % en todo, plan 012):

- `procedimiento`: los datos propuestos son iguales a los de la lista (número, expediente,
  objeto, tipo, encuadre, fecha de autorización candidata, cronograma, garantías...), con el
  texto dañado tal cual lo entrega el Portal (se comparan los espacios ya colapsados, que es la
  normalización de T-140).
- `renglones`: cada renglón con su código, descripción, cantidad y unidad.
- `documentos`: cada documento de la lista bajado, con su huella; la pantalla de error del
  Portal se espera como anomalía y no como documento. No cuentan como documento las vistas del
  propio proceso (ver un renglón, una versión anterior, una circular dentro de la página).
- `huellas`: la huella del archivo guardado es la del archivo que sirvió el Portal, y la del
  documento cargado es la del archivo guardado.
- `ofertas` y `pares`: total, garantías y precio y cantidad por renglón.
- `novedad`: explorar sin las circulares, aprobar todo y revisar con la página completa propone
  las circulares y no repite nada de lo decidido.
- `sin_aprobacion`: antes de aprobar, nada quedó cargado.

Cada escenario corre en una transacción que se deshace al terminar: la base queda como estaba.
La carpeta de la corrida es el registro.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, unquote

import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.offers.models import Offer
from evaluon.portal.client import PortalClient, Response, https_transport
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    PageKind,
    PortalItem,
    PortalLine,
    PortalLink,
    PortalOfferData,
    PortalQuote,
)
from evaluon.portal.services import approval, explore, links
from evaluon.queries.evaluation import proportion_text
from evaluon.tenders import jobs
from evaluon.tenders.evaluation import ratio
from evaluon.tenders.models import Document, DocumentKind, Job, JobKind, Procedure

OPERATION = "evaluon.portal.evaluation.measure"

THRESHOLD = 1.0
MEASURES = ("procedimiento", "renglones", "documentos", "huellas", "ofertas", "pares",
            "novedad", "sin_aprobacion")
LABELS = {
    "procedimiento": "Datos del procedimiento iguales a los del Portal (REQ-046)",
    "renglones": "Renglones con su cantidad (REQ-046)",
    "documentos": "Documentos de la lista con su origen (REQ-046)",
    "huellas": "Huella del documento cargado = huella del archivo bajado (REQ-049)",
    "ofertas": "Ofertas con total y garantía (REQ-047)",
    "pares": "Pares oferta y renglón con precio y cantidad (REQ-047)",
    "novedad": "Novedad propuesta y nada ya decidido repetido (REQ-050)",
    "sin_aprobacion": "Nada cargado sin aprobación (REQ-048)",
}
RUN_FILE_NAMES = ("parametros.json", "resultados.jsonl", "resumen.md", "resumen-publico.md")

# Archivos guardados que son vistas de la propia página del proceso, no documentos.
_VIEW_FILES = ("lnkVerItem", "btnVerVersion", "btnVerCircular")


class ExpectedError(ValueError):
    """La lista esperada no se puede leer o le falta algo."""


class MeasurementRefused(ValueError):
    """No se puede medir (carpeta sin páginas, falta el rol)."""


# --- Lista esperada --------------------------------------------------------------------------


@dataclass
class Expected:
    case: str
    sha256: str
    approval: str
    data: dict


def load_expected(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
        data = yaml.safe_load(raw.decode("utf-8"))
    except OSError as error:
        raise ExpectedError(f"no se puede leer la lista: {error.__class__.__name__}") from None
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise ExpectedError(f"la lista no se lee como YAML ({error.__class__.__name__})") from None
    if not isinstance(data, dict):
        raise ExpectedError("la lista no tiene la forma esperada")
    for key in ("procedimiento", "renglones", "documentos"):
        if not data.get(key):
            raise ExpectedError(f"falta `{key}` en la lista")
    return Expected(case=str(data.get("caso") or path.parent.parent.name),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    approval=str(data.get("visto_bueno") or "").strip(), data=data)


# --- Portal guardado -------------------------------------------------------------------------


def _key(url):
    return unquote(url or "").replace(" ", "")


class ReplayTransport:
    """Transporte de `PortalClient` que responde con las páginas guardadas. No usa la red."""

    def __init__(self, folder, transform=None):
        self.folder = Path(folder)
        self.transform = transform  # función de bytes a bytes para la página del proceso
        self.gets, self.posts = {}, {}
        self.process_url = None
        self.requests, self.missing, self.served = [], [], {}
        for meta_path in sorted(self.folder.glob("*.meta.json")):
            body_path = meta_path.with_name(meta_path.name[: -len(".meta.json")])
            if not body_path.exists():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            entry = (body_path, meta)
            if meta.get("target"):
                self.posts[meta["target"]] = entry
            elif meta.get("url"):
                self.gets[_key(meta["url"])] = entry
                if body_path.name == "proceso.html":
                    self.process_url = meta["url"]
        if not self.process_url:
            raise MeasurementRefused(f"{self.folder}: falta proceso.html con su .meta.json")

    def __call__(self, request):
        self.requests.append((request.method, request.url))
        if request.method == "POST":
            fields = parse_qs(request.body.decode("ascii", "replace"))
            target = (fields.get("__EVENTTARGET") or [""])[0]
            entry = self.posts.get(target)
            label = f"POST {target}"
        else:
            entry = self.gets.get(_key(request.url))
            label = f"GET {request.url}"
        if entry is None:
            self.missing.append(label)
            return Response(request.url, 404, {}, b"no guardado")
        path, meta = entry
        body = path.read_bytes()
        if self.transform and path.name == "proceso.html":
            body = self.transform(body)
        else:
            self.served[label] = hashlib.sha256(body).hexdigest()
        headers = {"content-type": meta.get("content_type") or ""}
        if meta.get("content_disposition"):
            headers["content-disposition"] = meta["content_disposition"]
        return Response(request.url, meta.get("status") or 200, headers, body)

    def client(self):
        return PortalClient(transport=self, allowed_hosts=list(settings.PORTAL_ALLOWED_HOSTS),
                            pause=0, timeout=5, max_bytes=settings.PORTAL_MAX_BYTES)


class LiveTransport:
    """La pasada «en vivo» (`medir_portal --en-vivo`, una sola vez, con el Coordinador): el
    cliente real con la configuración de la aplicación (lista de destinos, pausa, tope), y
    la huella de todo lo que sirvió el Portal. Solo se arma desde `portal_worker`, el único
    servicio con salida. La dirección del proceso sale de `proceso.html.meta.json`."""

    def __init__(self, folder):
        meta_path = Path(folder) / "proceso.html.meta.json"
        try:
            self.process_url = json.loads(meta_path.read_text(encoding="utf-8"))["url"]
        except (OSError, KeyError, ValueError):
            raise MeasurementRefused(f"{meta_path}: falta la dirección del proceso") from None
        self.requests, self.missing, self.served = [], [], {}

    def client(self):
        return PortalClient(transport=self)

    def __call__(self, request):
        self.requests.append((request.method, request.url))
        response = https_transport(request, timeout=settings.PORTAL_TIMEOUT_SECONDS,
                                   max_bytes=settings.PORTAL_MAX_BYTES)
        self.served[f"{request.method} {request.url} {len(self.served)}"] = hashlib.sha256(
            response.body).hexdigest()
        return response


def without_circulars(body):
    """La página del proceso como estaba antes de publicarse las circulares: sin las filas de
    la tabla de circulares."""
    text = body.decode("utf-8", "surrogateescape")
    text = re.sub(r"<tr[^>]*>(?:(?!</tr>).)*?gvCirculares_ctl\d+_.*?</tr>", "", text,
                  flags=re.DOTALL)
    return text.encode("utf-8", "surrogateescape")


# --- Comparación -----------------------------------------------------------------------------


@dataclass
class Check:
    measure: str
    key: str
    ok: bool
    detail: str = ""


@dataclass
class CaseResult:
    case: str
    checks: list = field(default_factory=list)
    anomalies: list = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def add(self, measure, key, ok, detail=""):
        self.checks.append(Check(measure, key, bool(ok), detail))

    def ratio(self, measure):
        rows = [c for c in self.checks if c.measure == measure]
        return ratio(sum(c.ok for c in rows), len(rows))


def _collapse(value):
    if isinstance(value, dict):
        return {_collapse(k): _collapse(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_collapse(v) for v in value]
    if value is None:
        return ""
    return " ".join(str(value).split())


def _number(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _same_number(a, b):
    x, y = _number(a), _number(b)
    return x is not None and y is not None and abs(x - y) <= Decimal("0.005")


def _items(proposal, kind):
    return [i for i in proposal.items.all() if i.kind == kind]


def _compare_procedure(result, expected, proposal):
    items = _items(proposal, ItemKind.PROCEDIMIENTO)
    want = expected.data["procedimiento"]
    if len(items) != 1:
        result.add("procedimiento", "ítem", False, f"se esperaba 1 ítem y hay {len(items)}")
        return None
    item = items[0]
    got = item.payload
    for field_name in ("numero", "expediente", "nombre", "objeto", "unidad_operativa", "tipo",
                       "encuadre_legal", "moneda", "cronograma", "garantias"):
        ok = _collapse(got.get(field_name)) == _collapse(want.get(field_name))
        result.add("procedimiento", field_name, ok,
                   "" if ok else f"esperado {want.get(field_name)!r}, propuesto "
                                 f"{got.get(field_name)!r}")
    authorization = want.get("fecha_autorizacion") or {}
    proposed = (got.get("fecha_autorizacion") or {}).get("candidata")
    result.add("procedimiento", "fecha_autorizacion",
               str(proposed) == str(authorization.get("candidata")),
               f"esperado {authorization.get('candidata')!r}, propuesto {proposed!r}")
    broken = [name for name in ("unidad_operativa", "encuadre_legal")
              if "¿" in str(got.get(name) or "")]
    marked = all(name in item.damaged_fields for name in broken)
    result.add("procedimiento", "texto_dañado_marcado", marked,
               "" if marked else f"sin marca: {broken}")
    return item


def _compare_lines(result, expected, proposal):
    items = _items(proposal, ItemKind.RENGLONES)
    got = {}
    for item in items:
        for line in item.payload["renglones"]:
            got[line["numero"]] = line
    for line in expected.data["renglones"]:
        number = line["numero"]
        mine = got.get(number)
        ok = (mine is not None
              and _collapse(mine["codigo_item"]) == _collapse(line["codigo_item"])
              and _collapse(mine["descripcion"]) == _collapse(line["descripcion"])
              and _same_number(mine["cantidad"], line["cantidad"])
              and _collapse(mine["unidad"]) == _collapse(line["unidad"]))
        result.add("renglones", f"renglón {number}", ok,
                   "" if ok else f"esperado {line}, propuesto {mine}")
    extra = sorted(set(got) - {line["numero"] for line in expected.data["renglones"]})
    if extra:
        result.add("renglones", "renglones de más", False, f"propuestos de más: {extra}")


def _view_file(name):
    return any(marker in name for marker in _VIEW_FILES)


def _compare_documents(result, expected, link, transport, anomalies):
    downloaded = {f.sha256 for f in link.files.all()} | {p.sha256 for p in link.pages.all()}
    error_anomalies = [a for a in anomalies if "pantalla de error" in a.get("motivo", "")]
    expected_errors = 0
    for entry in expected.data["documentos"]:
        name = entry["archivo"]
        if _view_file(name):
            continue
        if "PantallaError" in (entry.get("final_url") or ""):
            expected_errors += 1
            continue
        stable = _stable_identity(name, entry, link)
        if stable is None:  # PDF y demás archivos: la huella es la identidad
            ok, why = entry["sha256"] in downloaded, "la huella esperada no se bajó"
        else:  # páginas HTML: llevan campos que cambian en cada visita; se compara quién es
            ok, why = stable, "el documento no se bajó (por su clase)"
        if name.startswith("circular-"):
            continue  # cada circular se mide abajo, por número, fecha y tipo
        result.add("documentos", name, ok, "" if ok else why)
    for index in range(expected_errors):
        ok = index < len(error_anomalies)
        result.add("documentos", f"pantalla de error {index + 1}", ok,
                   "" if ok else "no quedó anomalía de la pantalla de error")
    # Las circulares del caso con circulares: cada una con su fecha y su tipo del Portal.
    items = {i.payload.get("numero"): i for i in link.proposals.first().items.all()
             if i.kind == ItemKind.DOCUMENTO and i.payload.get("clase") == "circular"} \
        if link.proposals.exists() else {}
    for circular in expected.data.get("circulares") or []:
        mine = items.get(circular["numero"])
        ok = (mine is not None
              and _collapse(mine.payload.get("tipo_portal")) == _collapse(circular["tipo"])
              and mine.payload.get("fecha") == _iso(circular["fecha_publicacion"]))
        result.add("documentos", f"circular {circular['numero']}", ok,
                   "" if ok else f"esperada {circular}, propuesta "
                                 f"{mine.payload if mine else None}")


def _iso(text):
    try:
        day, month, year = str(text).strip().split("/")
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def _money(value):
    """El monto con dos decimales; un monto que el Portal no trae queda vacío."""
    number = _number(value) if value not in (None, "") else None
    return "" if number is None else str(number.quantize(Decimal("0.01")))


def _compare_offers(result, expected, proposal):
    items = {i.payload["cuit"]: i for i in _items(proposal, ItemKind.OFERTA)}
    by_cuit = {}
    for offer in expected.data.get("ofertas") or []:
        by_cuit.setdefault(str(offer["cuit"]), []).append(offer)
    for cuit, entries in by_cuit.items():
        mine = items.get(cuit)
        # Una garantía sin tipo, forma ni monto es "sin garantía" en la lista.
        wanted = sorted(row for row in ((_collapse(e["garantia"]["tipo"]),
                                         _collapse(e["garantia"]["forma"]),
                                         _money(e["garantia"]["monto"])) for e in entries)
                        if any(row))
        got = sorted((_collapse(g.get("tipo")), _collapse(g.get("forma")), _money(g.get("monto")))
                     for g in (mine.payload["garantias"] if mine else []))
        ok = mine is not None and _same_number(mine.payload["total"], entries[0]["total"]) \
            and got == wanted
        result.add("ofertas", f"oferta {cuit}", ok,
                   "" if ok else f"esperado total {entries[0]['total']} y garantías {wanted}; "
                                 f"propuesto {mine.payload['total'] if mine else None} y {got}")
    # Comprobación propia de la página, sin la lista: la suma de lo cotizado es el total.
    sums = []
    for cuit, item in items.items():
        spent = sum((_number(q["precio"]) * _number(q["cantidad"])
                     for q in item.payload["cotizaciones"]), Decimal(0))
        sums.append(_same_number(spent, item.payload["total"]))
    result.info["suma_cotizaciones_igual_total"] = f"{sum(sums)} de {len(sums)}"
    extra = sorted(set(items) - set(by_cuit))
    if extra:
        result.add("ofertas", "ofertas de más", False, f"propuestas de más: {extra}")
    for pair in expected.data.get("pares_oferta_renglon") or []:
        mine = items.get(str(pair["cuit"]))
        quotes = [q for q in (mine.payload["cotizaciones"] if mine else [])
                  if q["renglon"] == pair["renglon"]]
        ok = any(_same_number(q["precio"], pair["precio_unitario"])
                 and _same_number(q["cantidad"], pair["cantidad"]) for q in quotes)
        result.add("pares", f"renglón {pair['renglon']} · {pair['cuit']}", ok,
                   "" if ok else f"esperado {pair}, propuesto {quotes}")


# --- Escenarios ------------------------------------------------------------------------------


class _Rollback(Exception):
    pass


def _counts(link=None):
    return {
        "procedimientos": Procedure.objects.count(),
        "renglones": PortalLine.objects.count(),
        "documentos": Document.objects.count(),
        "ofertas": Offer.objects.count(),
        "datos_de_oferta": PortalOfferData.objects.count(),
        "cotizaciones": PortalQuote.objects.count(),
    }


def _confirmations(proposal):
    out = {}
    for item in proposal.items.filter(state=ItemState.PROPUESTO):
        if item.kind == ItemKind.PROCEDIMIENTO:
            candidate = (item.payload.get("fecha_autorizacion") or {}).get("candidata")
            if candidate:
                out[item.pk] = {"authorization_date": date.fromisoformat(candidate)}
        elif item.kind == ItemKind.DOCUMENTO and item.payload.get("clase") == "circular":
            out[item.pk] = {"circular_kind": DocumentKind.CIRCULAR_ACLARATORIA}
    return out


def _run_job(link, user, transport, kind):
    """Atiende el pedido y devuelve la propuesta que dejó, o `None` si no dejó ninguna."""
    if kind == JobKind.PORTAL_EXPLORE:
        job = Job.objects.get(kind=kind, target_id=link.pk)
        explore.run_explore(job, client=transport.client())
    else:
        job = jobs.enqueue(kind, procedure=None, requested_by=user, target_id=link.pk)
        explore.run_review(job, client=transport.client())
    return link.proposals.filter(job=job).first()  # una revisión sin novedades no la deja


def _scenario_base(user, folder, expected, live=False):
    """Exploración con la página completa, comparación con la lista, carga previa vacía,
    aprobación y comprobación de lo cargado."""
    result = CaseResult(expected.case)
    transport = LiveTransport(folder) if live else ReplayTransport(folder)
    before = _counts()
    link = links.register_link(user, transport.process_url, channel=Channel.COMMAND)
    proposal = _run_job(link, user, transport, JobKind.PORTAL_EXPLORE)
    if proposal is None:
        result.add("procedimiento", "propuesta", False, "la exploración no dejó propuesta")
        return result, transport
    result.anomalies = list(proposal.anomalies)
    _compare_procedure(result, expected, proposal)
    _compare_lines(result, expected, proposal)
    _compare_documents(result, expected, link, transport, proposal.anomalies)
    _compare_offers(result, expected, proposal)

    after = _counts()
    for name, value in after.items():
        result.add("sin_aprobacion", name, value == before[name],
                   f"{name}: {before[name]} antes de aprobar y {value} después de explorar")
    result.info["items_propuestos"] = {
        kind: len(_items(proposal, kind)) for kind in ItemKind.values}

    results = approval.approve_all(user, link.pk, confirmations=_confirmations(proposal),
                                   channel=Channel.COMMAND)
    states = {}
    for entry in results:
        states[entry.result] = states.get(entry.result, 0) + 1
    result.info["decisiones"] = states
    result.info["fallidos"] = [
        {"tipo": r.item.kind, "motivo": r.reason} for r in results if r.result == "fallido"]
    result.info["pendientes"] = [
        {"tipo": r.item.kind, "motivo": r.reason} for r in results if r.result == "pendiente"]

    served = set(transport.served.values())
    for stored in list(link.files.all()):
        result.add("huellas", f"archivo {stored.pk}", stored.sha256 in served
                   and hashlib.sha256(bytes(stored.content)).hexdigest() == stored.sha256,
                   "la huella no es la de lo que sirvió el Portal")
    for item in PortalLink.objects.get(pk=link.pk).proposals.first().items.filter(
            kind=ItemKind.DOCUMENTO, state=ItemState.CARGADO):
        document = Document.objects.get(pk=item.loaded_id)
        result.add("huellas", f"documento cargado {document.pk}",
                   document.file_sha256 == item.file.sha256,
                   "la huella del documento cargado no es la del archivo bajado")
    result.info["pedidos_no_guardados"] = list(dict.fromkeys(transport.missing))
    result.info["solicitudes"] = len(transport.requests)
    return result, transport


def _scenario_novelty(user, folder, expected, result):
    """Explora sin las circulares, aprueba todo y revisa con la página completa."""
    first = ReplayTransport(folder, transform=without_circulars)
    link = links.register_link(user, first.process_url, channel=Channel.COMMAND)
    proposal = _run_job(link, user, first, JobKind.PORTAL_EXPLORE)
    approval.approve_all(user, link.pk, confirmations=_confirmations(proposal),
                         channel=Channel.COMMAND)
    decided = proposal.items.exclude(state=ItemState.PROPUESTO).count()
    full = ReplayTransport(folder)
    review = _run_job(link, user, full, JobKind.PORTAL_REVIEW)
    new_items = list(review.items.all()) if review else []
    circulars = [i for i in new_items if i.kind == ItemKind.DOCUMENTO
                 and i.payload.get("clase") == "circular"]
    repeated = [i for i in new_items if i not in circulars]
    wanted = len(expected.data.get("circulares") or [])
    result.add("novedad", "circulares nuevas propuestas", len(circulars) == wanted,
               f"esperadas {wanted}, propuestas {len(circulars)}")
    for index in range(decided):
        result.add("novedad", f"ítem decidido {index + 1} no repetido",
                   index >= len(repeated),
                   "se volvió a proponer: " + "; ".join(
                       f"{i.kind} {i.key}" for i in repeated) if index < len(repeated) else "")
    result.info["novedad"] = {"decididos": decided, "circulares_nuevas": len(circulars),
                              "repetidos": [f"{i.kind}" for i in repeated]}


def measure_case(user, case_dir, live=False):
    """Mide un caso. Cada escenario se deshace al terminar."""
    case_dir = Path(case_dir)
    expected = load_expected(case_dir / "esperado" / "portal-esperado.yaml")
    folder = case_dir / "portal"
    if not folder.is_dir():
        raise MeasurementRefused(f"{folder}: no hay páginas guardadas")
    holder = {}
    try:
        with transaction.atomic():
            holder["result"], _ = _scenario_base(user, folder, expected, live)
            raise _Rollback
    except _Rollback:
        pass
    result = holder["result"]
    if live:
        result.info["en_vivo"] = True  # la novedad necesita dos estados del Portal: no se mide
        return expected, result
    try:
        with transaction.atomic():
            _scenario_novelty(user, folder, expected, result)
            raise _Rollback
    except _Rollback:
        pass
    return expected, result


# --- Corrida ---------------------------------------------------------------------------------


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


@dataclass
class Report:
    folder: Path
    cases: list  # [(Expected, CaseResult)]
    live: bool = False

    @property
    def blocking(self):
        failed = []
        for expected, result in self.cases:
            for name in (m for m in MEASURES if not (result.info.get("en_vivo") and m == "novedad")):
                value = result.ratio(name)
                if value["total"] and value["rate"] < THRESHOLD:
                    failed.append(f"{expected.case} · {LABELS[name]}: "
                                  f"{proportion_text(value)}, mínimo 100 %")
                if not value["total"]:
                    failed.append(f"{expected.case} · {LABELS[name]}: sin casos medidos")
        return failed


def measure(user, case_dirs, runs_dir, *, commit=None, live=False):
    require_commission_role(user, CommissionRole.EVALUATOR, operation=OPERATION,
                            channel=Channel.COMMAND)
    started_at = timezone.now()
    cases = [measure_case(user, case_dir, live) for case_dir in case_dirs]
    base = f"{started_at:%Y%m%d-%H%M%S}-{commit or 'sin-commit'}"
    folder = Path(runs_dir) / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = Path(runs_dir) / f"{base}-{suffix}"
    report = Report(folder, cases, live=live)
    _write(report, started_at, commit)
    return report


def _write(report, started_at, commit):
    report.folder.mkdir(parents=True, exist_ok=False)
    parameters = {
        "iniciada": started_at, "commit": commit or "sin-commit", "sin_conexion": not report.live, "en_vivo": report.live,
        "umbral": THRESHOLD,
        "casos": [{"caso": e.case, "lista": {"sha256": e.sha256, "visto_bueno": e.approval},
                   "solicitudes": r.info.get("solicitudes"),
                   "pedidos_no_guardados": len(r.info.get("pedidos_no_guardados") or [])}
                  for e, r in report.cases],
    }
    (report.folder / "parametros.json").write_text(
        _dumps(parameters, indent=2) + "\n", encoding="utf-8")
    with (report.folder / "resultados.jsonl").open("w", encoding="utf-8") as handle:
        for expected, result in report.cases:
            for check in result.checks:
                handle.write(_dumps({"caso": expected.case, "medida": check.measure,
                                     "clave": check.key, "ok": check.ok,
                                     "detalle": check.detail}) + "\n")
    (report.folder / "resumen.md").write_text(_summary(report, public=False), encoding="utf-8")
    (report.folder / "resumen-publico.md").write_text(_summary(report, public=True),
                                                      encoding="utf-8")


def _summary(report, *, public):
    lines = ["# Medición de la importación del Portal" + (" · pasada en vivo" if report.live else ""), ""]
    failed = report.blocking
    lines.append("Cumple el umbral." if not failed else "No cumple: " + "; ".join(failed) + ".")
    for expected, result in report.cases:
        lines += ["", f"## {expected.case}", "",
                  f"Lista: `{expected.sha256[:12]}` · visto bueno: {expected.approval or '—'}",
                  "", "| Medida | Umbral | Medido |", "|---|---|---|"]
        for name in MEASURES:
            lines.append(f"| {LABELS[name]} | 100 % | {proportion_text(result.ratio(name))} |")
        info = result.info
        lines += ["", "Se informa, no bloquea:", "",
                  f"- Anomalías informadas al explorar: {len(result.anomalies)}.",
                  f"- Solicitudes servidas con lo guardado: {info.get('solicitudes')}; "
                  f"no guardadas: {len(info.get('pedidos_no_guardados') or [])}.",
                  f"- Decisiones al aprobar todo: {info.get('decisiones')}.",
                  f"- Ítems propuestos por tipo: {info.get('items_propuestos')}.",
                  "- Ofertas cuya suma de cotizaciones da su total: "
                  f"{info.get('suma_cotizaciones_igual_total')}."]
        if not public:
            lines += ["", "### Fallas", ""]
            bad = [c for c in result.checks if not c.ok]
            lines += [f"- {c.measure} · {c.key}: {c.detail}" for c in bad] or ["- ninguna"]
            lines += ["", "### Anomalías", ""]
            lines += [f"- {a.get('parte')}: {a.get('motivo')}" for a in result.anomalies] \
                or ["- ninguna"]
            lines += ["", "### Cargas fallidas o pendientes", ""]
            both = (info.get("fallidos") or []) + (info.get("pendientes") or [])
            lines += [f"- {x['tipo']}: {x['motivo']}" for x in both] or ["- ninguna"]
    if public:
        lines += ["", "Los datos de los procesos y de los oferentes no figuran en este resumen."]
    return "\n".join(lines) + "\n"


def _stable_identity(name, entry, link):
    """Para una página HTML guardada (acta, dictamen, cuadro): si el documento de su clase
    se bajó. La huella de esas páginas cambia en cada visita (campos del formulario y
    direcciones con `qs`), así que no es su identidad; la clase, el número y la fecha sí.
    `None` si no es una página HTML o no se la reconoce: se compara la huella."""
    if "html" not in str(entry.get("tipo") or ""):
        return None
    classes = {i.payload.get("clase") for i in PortalItem.objects.filter(
        proposal__link=link, kind=ItemKind.DOCUMENTO)}
    if "ActaApertura" in name:
        return "acta" in classes
    if "Dictamen" in name:
        return "dictamen" in classes
    if "CuadroComparativo" in name:
        return link.pages.filter(kind=PageKind.CUADRO).exists()
    return None
