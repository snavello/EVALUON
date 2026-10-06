"""Enlaces del Portal: registrar, listar y dejar de seguir (REQ-045; plan 012, "Flujo, paso 1").

- `register_link`: el operador o el evaluador pegan el enlace público del proceso. Se acepta
  solo HTTPS de un host permitido y con la forma de enlace de proceso (la página del pliego
  con su `qs`); si no, se explica por qué. Guarda el enlace y encola `portal_explore`, que
  atiende `portal_worker`. Deja siempre el hecho `portal_link`, también al rechazar.
- `list_links`: los enlaces con el estado de su última exploración y sus novedades.
- `stop_following`: deja de revisar el proceso.

El rol se comprueba fuera de toda transacción, como en la 003, para que el hecho `rejected`
no se pierda. Los mensajes son para la persona que pega el enlace.
"""

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from django.db import IntegrityError, transaction

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.portal.client import DestinationNotAllowed, validate_url
from evaluon.portal.models import ItemState, PortalItem, PortalLink
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS, Job, JobKind

REGISTER_OPERATION = "evaluon.portal.services.links.register_link"
LIST_OPERATION = "evaluon.portal.services.links.list_links"
STOP_OPERATION = "evaluon.portal.services.links.stop_following"

PROCESS_PATH = "/pliego/vistapreviapliegociudadano.aspx"


class LinkRefused(ValueError):
    """No se registró el enlace; el mensaje dice por qué."""


@dataclass
class LinkRow:
    link: PortalLink
    last_job: Job | None
    pending: int


def _explain(url):
    """Levanta `LinkRefused` si `url` no es el enlace de un proceso; devuelve la dirección."""
    url = (url or "").strip()
    if not url:
        raise LinkRefused("Pegue el enlace del proceso.")
    try:
        validate_url(url)
    except DestinationNotAllowed as error:
        raise LinkRefused(f"No se puede usar ese enlace: {error}.") from None
    parts = urlsplit(url)
    if parts.path.lower() != PROCESS_PATH:
        raise LinkRefused(
            "Ese enlace no es la página de un proceso del Portal "
            "(debe ser la vista previa del pliego)."
        )
    if not parse_qs(parts.query).get("qs"):
        raise LinkRefused("Al enlace le falta el dato «qs»: copie la dirección completa.")
    return url


def _event(user, channel, outcome, detail):
    return audit.record(EventType.PORTAL_LINK, outcome=outcome, channel=channel,
                        user=user, detail=detail)


def register_link(user, url, *, channel=Channel.SCREEN):
    """Registra el enlace, encola la exploración y devuelve el `PortalLink`.

    Lanza `RoleRejected` sin rol de la Comisión y `LinkRefused` con un enlace que no
    sirve o ya registrado (con su hecho `portal_link` fallido)."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=REGISTER_OPERATION, channel=channel)
    try:
        url = _explain(url)
        if PortalLink.objects.filter(url=url).exists():
            raise LinkRefused("Ese proceso ya está registrado.")
        with transaction.atomic():
            link = PortalLink.objects.create(url=url, created_by=user)
            job = jobs.enqueue(JobKind.PORTAL_EXPLORE, procedure=None, requested_by=user,
                               target_id=link.pk)
            _event(user, channel, Outcome.OK,
                   {"action": "registrar", "link": link.pk, "url": url, "job": job.pk})
    except IntegrityError:
        refused = LinkRefused("Ese proceso ya está registrado.")
    except LinkRefused as error:
        refused = error
    else:
        return link
    _event(user, channel, Outcome.FAILED,
           {"action": "registrar", "url": (url or "").strip(), "reason": str(refused)})
    raise refused


def list_links(user, *, channel=Channel.SCREEN):
    """Los enlaces, el más reciente primero, con su último pedido y sus ítems por decidir."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=LIST_OPERATION, channel=channel)
    rows = []
    for link in PortalLink.objects.order_by("-created_at", "-id"):
        last = (Job.objects.filter(kind__in=PORTAL_JOB_KINDS, target_id=link.pk)
                .order_by("-id").first())
        pending = PortalItem.objects.filter(proposal__link=link,
                                            state=ItemState.PROPUESTO).count()
        rows.append(LinkRow(link=link, last_job=last, pending=pending))
    return rows


def stop_following(user, link_id, *, channel=Channel.SCREEN):
    """Deja de revisar el proceso. Devuelve el enlace."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=STOP_OPERATION, channel=channel)
    with transaction.atomic():
        link = PortalLink.objects.select_for_update().get(pk=link_id)
        link.following = False
        link.save(update_fields=["following"])
        _event(user, channel, Outcome.OK,
               {"action": "dejar_de_seguir", "link": link.pk, "url": link.url})
    return link
