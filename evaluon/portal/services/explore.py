"""Explorar un proceso del Portal y armar la propuesta (REQ-046, REQ-049; plan 012, "Flujo,
paso 2"; ADR-0030, ADR-0031).

`run_explore` y `run_review` son los manejadores de `portal_explore` y `portal_review`; los
atiende `portal_worker`, único servicio con salida al Portal. La revisión reutiliza la
exploración y solo cambia el origen de la propuesta y el hecho que deja.

Una exploración:

1. baja la página del proceso con el cliente acotado y la guarda tal cual (`portal_page`,
   con su huella y la fecha de consulta);
2. la lee con `parsing/pagina.py`; si ni siquiera es la página de un proceso, el pedido falla
   con el motivo;
3. pasa el resultado a cada importador de `importers/` (se descubren por nombre de archivo),
   que devuelven los ítems y las anomalías (lo que no se pudo leer no frena el resto);
4. guarda la propuesta con sus ítems, dejando afuera los ya decididos con la misma huella
   (no se repite lo aprobado ni lo rechazado). Una revisión sin ítems nuevos y sin anomalías
   nuevas (una ya informada en otra propuesta del enlace no cuenta) no crea propuesta (REQ-050).

Nada se carga acá: eso lo hace `approval.decide` cuando una persona aprueba. Cada exploración
deja el hecho `portal_explore` (o `portal_review`), también cuando falla (P6). No usa IA.
"""

import hashlib
import time
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Max

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.portal.client import PortalClient
from evaluon.portal.importers import content_sha256, discover
from evaluon.portal.models import (
    ItemState,
    Origin,
    PageKind,
    PortalItem,
    PortalLink,
    PortalPage,
    PortalProposal,
)
from evaluon.portal.parsing.pagina import ProcessPage, parse_page

READER_VERSION = "pagina-1"

# Estados de un ítem anterior que impiden volver a proponer el mismo contenido.
_SETTLED = (ItemState.PROPUESTO, ItemState.APROBADO, ItemState.CARGADO, ItemState.RECHAZADO)


class UnreadablePage(Exception):
    """La página bajada no es la de un proceso."""


@dataclass
class Context:
    """Lo que reciben los importadores."""

    link: PortalLink
    exploration: int
    client: PortalClient
    page: PortalPage
    parsed: ProcessPage
    anomalies: list = field(default_factory=list)
    files: list = field(default_factory=list)  # archivos bajados: URL, huella y fecha (P6)


def new_client():
    """Cliente con los parámetros de `settings.py` (lista de destinos, tope y pausa)."""
    return PortalClient()


def run_explore(job, client=None):
    """Manejador de `portal_explore`."""
    _run(job, Origin.IMPORTACION, EventType.PORTAL_EXPLORE, client)


def run_review(job, client=None):
    """Manejador de `portal_review`: lo mismo, con otro origen y otro hecho."""
    _run(job, Origin.REVISION, EventType.PORTAL_REVIEW, client)


def _next_exploration(link):
    last = max(
        link.pages.aggregate(m=Max("exploration"))["m"] or 0,
        link.proposals.aggregate(m=Max("exploration"))["m"] or 0,
    )
    return last + 1


def _already_decided(link, draft, sha):
    """Hay un ítem anterior de la misma clave con la misma huella: no se vuelve a proponer.
    Se mira el más reciente; si cambió desde entonces, se propone de nuevo."""
    previous = (PortalItem.objects.filter(proposal__link=link, kind=draft.kind, key=draft.key)
                .exclude(state=ItemState.FALLIDO).order_by("-id").first())
    return previous is not None and previous.state in _SETTLED and previous.content_sha256 == sha


def _new_anomalies(link, anomalies):
    """Las anomalías que ninguna propuesta anterior del enlace informó ya."""
    known = []
    for earlier in link.proposals.values_list("anomalies", flat=True):
        known.extend(earlier or [])
    return [a for a in anomalies if a not in known]


def _run(job, origin, event_type, client):
    started = time.monotonic()
    link = PortalLink.objects.get(pk=job.target_id)
    exploration = _next_exploration(link)
    detail = {"link": link.pk, "exploration": exploration, "origin": origin,
              "url": link.url, "reader_version": READER_VERSION, "job": job.pk,
              "pages": [], "files": []}
    try:
        client = client or new_client()
        response = client.get(link.url)
        page = PortalPage.objects.create(
            link=link, exploration=exploration, kind=PageKind.PROCESO, url=link.url,
            sha256=hashlib.sha256(response.body).hexdigest(), content=response.body,
        )
        detail["pages"].append({"kind": page.kind, "url": page.url, "sha256": page.sha256,
                                "fetched_at": page.fetched_at.isoformat()})
        parsed = parse_page(response.body)
        if not parsed.data.get("numero"):
            raise UnreadablePage(
                "la página no es la de un proceso o no se pudo leer "
                f"(falta: {', '.join(parsed.missing) or 'el número del proceso'})"
            )
        context = Context(link=link, exploration=exploration, client=client, page=page,
                          parsed=parsed)
        detail["files"] = context.files
        context.anomalies.extend(
            {"parte": "pagina", "motivo": f"falta el dato obligatorio {key}"}
            for key in parsed.missing if key != "numero"
        )
        context.anomalies.extend(
            {"parte": issue["seccion"], "motivo": issue["motivo"]} for issue in parsed.issues
        )
        drafts = []
        for module in dict.fromkeys(discover().values()):
            drafts.extend(module.explore(context))
        proposal, counts, omitted = _save(link, exploration, origin, job, page, drafts,
                                          context.anomalies, parsed)
    except Exception as error:
        detail.update(elapsed_seconds=round(time.monotonic() - started, 3),
                      reason=f"{type(error).__name__}: {error}")
        audit.record(event_type, outcome=Outcome.FAILED, channel=Channel.COMMAND,
                     user=job.requested_by, detail=detail)
        raise
    detail.update(proposal=proposal.pk if proposal else None, items=counts, omitted=omitted,
                  anomalies=context.anomalies,
                  elapsed_seconds=round(time.monotonic() - started, 3))
    audit.record(event_type, outcome=Outcome.OK, channel=Channel.COMMAND,
                 user=job.requested_by, detail=detail)


def _save(link, exploration, origin, job, page, drafts, anomalies, parsed):
    """Guarda la propuesta y sus ítems nuevos. Devuelve (propuesta o None, ítems por tipo,
    ítems omitidos por ya decididos)."""
    fresh, omitted = [], 0
    for draft in drafts:
        sha = content_sha256(draft.payload)
        if _already_decided(link, draft, sha):
            omitted += 1
        else:
            fresh.append((draft, sha))
    counts = {}
    for draft, _ in fresh:
        counts[draft.kind] = counts.get(draft.kind, 0) + 1
    with transaction.atomic():
        link.process_number = parsed.data["numero"]
        link.save(update_fields=["process_number"])
        news = _new_anomalies(link, anomalies) if origin == Origin.REVISION else anomalies
        if origin == Origin.REVISION and not fresh and not news:
            return None, counts, omitted
        proposal = PortalProposal.objects.create(
            link=link, exploration=exploration, origin=origin, job=job, anomalies=anomalies
        )
        for draft, sha in fresh:
            PortalItem.objects.create(
                proposal=proposal, kind=draft.kind, key=draft.key, payload=draft.payload,
                content_sha256=sha, damaged_fields=list(draft.damaged_fields),
                page=draft.page or page,
                file=draft.file,
            )
    return proposal, counts, omitted
