"""Revisión periódica de los procesos seguidos (REQ-050; ADR-0033).

- `enqueue_due(now)`: lo llama `procesar_portal` en cada vuelta, antes de tomar un pedido. Por
  cada enlace en curso (sin fin de seguimiento) que no tiene revisión hecha ni pedida hoy, sin
  pedido del Portal en espera o en curso, y siempre que hoy sea día hábil (lunes a viernes) y
  ya haya pasado `PORTAL_REVIEW_HOUR` (hora de la aplicación), encola un `portal_review`. No hay
  calendario de feriados. El reloj se recibe por parámetro para probarlo.
- `review_now`: el botón "Revisar ahora"; encola el mismo pedido y no apila otro si ya hay uno
  en espera o en curso para el enlace.
- `end_following_for_dictamen`: al decidirse el ítem del dictamen se termina el seguimiento.

La revisión pedida lleva como solicitante a quien registró el enlace: a esa persona le llega
el aviso de fin, también cuando falla.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.portal.models import PortalLink
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS, Job, JobKind, JobStatus

REVIEW_OPERATION = "evaluon.portal.services.schedule.review_now"
_OPEN = (JobStatus.QUEUED, JobStatus.RUNNING)


def _has_open_job(link):
    return Job.objects.filter(kind__in=PORTAL_JOB_KINDS, target_id=link.pk,
                              status__in=_OPEN).exists()


def _enqueue(link, user, local_date, origin, detail_user=None):
    job = jobs.enqueue(JobKind.PORTAL_REVIEW, procedure=None, requested_by=user,
                       target_id=link.pk)
    link.last_review_on = local_date
    link.save(update_fields=["last_review_on"])
    audit.record(EventType.PORTAL_LINK, outcome=Outcome.OK, channel=Channel.COMMAND,
                 user=detail_user,
                 detail={"action": "revisar", "origin": origin, "link": link.pk,
                         "url": link.url, "job": job.pk})
    return job


def enqueue_due(now=None):
    """Encola las revisiones que corresponden en `now`. Devuelve los pedidos creados."""
    local = timezone.localtime(now or timezone.now())
    if local.weekday() >= 5 or local.hour < settings.PORTAL_REVIEW_HOUR:
        return []
    created = []
    for pk in (PortalLink.objects.filter(following=True).order_by("id")
               .values_list("pk", flat=True)):
        with transaction.atomic():
            link = PortalLink.objects.select_for_update().get(pk=pk)
            if (not link.following or link.last_review_on == local.date()
                    or _has_open_job(link)):
                continue
            created.append(_enqueue(link, link.created_by, local.date(), "programada"))
    return created


def review_now(user, link_id, *, channel=Channel.SCREEN, now=None):
    """"Revisar ahora". Devuelve `(pedido, creado)`: si ya había uno en espera o en curso,
    ese mismo y `False`."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REVIEW_OPERATION,
                            channel=channel)
    with transaction.atomic():
        link = PortalLink.objects.select_for_update().get(pk=link_id)
        open_job = (Job.objects.filter(kind__in=PORTAL_JOB_KINDS, target_id=link.pk,
                                       status__in=_OPEN).order_by("id").first())
        if open_job is not None:
            return open_job, False
        local = timezone.localtime(now or timezone.now())
        job = jobs.enqueue(JobKind.PORTAL_REVIEW, procedure=None, requested_by=user,
                           target_id=link.pk)
        link.last_review_on = local.date()
        link.save(update_fields=["last_review_on"])
        audit.record(EventType.PORTAL_LINK, outcome=Outcome.OK, channel=channel, user=user,
                     detail={"action": "revisar", "origin": "a_demanda", "link": link.pk,
                             "url": link.url, "job": job.pk})
    return job, True


def end_following_for_dictamen(item, user, channel):
    """Se decidió el ítem del dictamen: el proceso terminó y ya no se revisa."""
    link = PortalLink.objects.select_for_update().get(pk=item.proposal.link_id)
    if not link.following:
        return
    link.following = False
    link.save(update_fields=["following"])
    audit.record(EventType.PORTAL_LINK, outcome=Outcome.OK, channel=channel, user=user,
                 detail={"action": "fin_de_seguimiento", "reason": "dictamen decidido",
                         "link": link.pk, "url": link.url, "item": item.pk})
