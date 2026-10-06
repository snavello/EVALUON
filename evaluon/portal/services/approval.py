"""Aprobar o rechazar lo propuesto y cargarlo (REQ-048, REQ-049; plan 012, "Flujo, paso 4";
ADR-0030).

- `proposal_page`: lo que ve la persona: los ítems pendientes y los de la última propuesta,
  con su origen, su marca de texto dañado y si puede decidir cada uno.
- `decide(user, item_ids, decision)`: aprueba o rechaza ítems, uno por uno. Comprueba el rol
  por tipo de ítem (el operador solo decide los documentos; el evaluador, todos) antes de
  tocar nada. Procesa en el orden procedimiento, renglones, documentos, ofertas. Un ítem
  aprobado se carga en la misma transacción que su decisión, llamando al importador de su
  tipo (que usa los servicios de la 003 y la 008); si la carga falla, el ítem queda
  `fallido` con el motivo, no se carga nada de ese ítem y los demás siguen. Un ítem que
  depende de otro no cargado, o que pide un dato que falta (la fecha de autorización), no
  se decide: queda `propuesto` con el motivo.
- `approve_all`: aprueba todo lo pendiente del enlace; solo el evaluador.
- Al decidirse el ítem del dictamen termina el seguimiento del proceso (REQ-050).

Cada decisión deja el hecho `portal_decision` con usuario y fecha (P6). Nada se carga sin una
aprobación explícita.
"""

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.portal.importers import discover
from evaluon.portal.models import ItemKind, ItemState, PortalItem, PortalLink
from evaluon.portal.services.schedule import end_following_for_dictamen

DECIDE_OPERATION = "evaluon.portal.services.approval.decide"
APPROVE_ALL_OPERATION = "evaluon.portal.services.approval.approve_all"
PAGE_OPERATION = "evaluon.portal.services.approval.proposal_page"

APPROVE = "aprobar"
REJECT = "rechazar"

# Orden de carga: lo que depende de otro va después.
ORDER = (ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES, ItemKind.DOCUMENTO, ItemKind.OFERTA)

# Resultado de decidir un ítem.
LOADED = "cargado"
REJECTED = "rechazado"
FAILED = "fallido"
PENDING = "pendiente"  # no se decidió: queda propuesto con su motivo
ALREADY = "ya_decidido"
KEPT_AS_FILE = "guardado_como_archivo"  # aprobado sin crear nada: queda el archivo del Portal


@dataclass
class ItemResult:
    item: PortalItem
    result: str
    reason: str = ""


@dataclass
class ItemRow:
    item: PortalItem
    can_decide: bool
    changed: bool = False
    template: str = ""
    action: str = ""  # del ítem procedimiento: "crear" o "asociar"


@dataclass
class Page:
    link: PortalLink
    proposals: list
    anomalies: list
    rows: dict  # tipo de ítem -> [ItemRow]
    can_approve_all: bool
    pending: int


def required_role(kind):
    """El operador decide los documentos; el evaluador, todo lo demás."""
    return CommissionRole.OPERATOR if kind == ItemKind.DOCUMENTO else CommissionRole.EVALUATOR


def _can(user, role):
    return getattr(user, "commission_role", None) in {
        CommissionRole.OPERATOR: (CommissionRole.OPERATOR, CommissionRole.EVALUATOR),
        CommissionRole.EVALUATOR: (CommissionRole.EVALUATOR,),
    }[role]


def proposal_page(user, link_id, *, channel=Channel.SCREEN):
    """Lo propuesto para un enlace, agrupado por tipo. Lo ve el operador y el evaluador."""
    require_commission_role(user, CommissionRole.OPERATOR,
                            operation=PAGE_OPERATION, channel=channel)
    link = PortalLink.objects.get(pk=link_id)
    proposals = list(link.proposals.order_by("-exploration", "-id"))
    latest = proposals[0] if proposals else None
    items = (PortalItem.objects.filter(proposal__link=link)
             .filter(Q(state=ItemState.PROPUESTO) | Q(proposal=latest))
             .select_related("proposal", "page", "decided_by").order_by("proposal_id", "id"))
    rows = {kind: [] for kind in ORDER}
    for item in items:
        changed = False
        if item.state == ItemState.PROPUESTO:
            changed = PortalItem.objects.filter(
                proposal__link=link, kind=item.kind, key=item.key,
                state__in=(ItemState.APROBADO, ItemState.CARGADO), id__lt=item.id,
            ).exclude(content_sha256=item.content_sha256).exists()
        action = (discover()[item.kind].action(item)
                  if item.kind == ItemKind.PROCEDIMIENTO and item.state == ItemState.PROPUESTO
                  else "")
        rows[item.kind].append(ItemRow(item=item, can_decide=_can(user, required_role(item.kind)),
                                       action=action,
                                       changed=changed))
    pending = sum(1 for group in rows.values() for row in group
                  if row.item.state == ItemState.PROPUESTO)
    return Page(link=link, proposals=proposals, anomalies=latest.anomalies if latest else [],
                rows={kind: group for kind, group in rows.items() if group},
                can_approve_all=_can(user, CommissionRole.EVALUATOR), pending=pending)


def decide(user, item_ids, decision, *, confirmations=None, channel=Channel.SCREEN):
    """Aprueba o rechaza los ítems. `confirmations` es `{id del ítem: {"authorization_date":
    fecha}}`: lo que confirma quien aprueba (la fecha de autorización del procedimiento).
    Devuelve un `ItemResult` por ítem, en el orden en que se procesaron.

    Lanza `RoleRejected` si el usuario no puede decidir alguno de los ítems (no se decide
    ninguno) y `PortalItem.DoesNotExist` si falta alguno."""
    if decision not in (APPROVE, REJECT):
        raise ValueError(f"decisión desconocida: {decision!r}")
    ids = list(dict.fromkeys(item_ids))
    items = list(PortalItem.objects.filter(pk__in=ids))
    if len(items) != len(ids):
        raise PortalItem.DoesNotExist("falta alguno de los ítems pedidos")
    for role in {required_role(item.kind) for item in items}:
        require_commission_role(user, role, operation=DECIDE_OPERATION, channel=channel)
    confirmations = confirmations or {}
    results = []
    for item in sorted(items, key=lambda i: (ORDER.index(i.kind), i.pk)):
        results.append(_decide_one(user, item.pk, decision, confirmations.get(item.pk) or {},
                                   channel))
    return results


def approve_all(user, link_id, *, confirmations=None, channel=Channel.SCREEN):
    """Aprueba todo lo pendiente del enlace. Solo el evaluador."""
    require_commission_role(user, CommissionRole.EVALUATOR,
                            operation=APPROVE_ALL_OPERATION, channel=channel)
    ids = list(PortalItem.objects.filter(proposal__link_id=link_id, state=ItemState.PROPUESTO)
               .values_list("pk", flat=True))
    return decide(user, ids, APPROVE, confirmations=confirmations, channel=channel)


def _event(item, user, channel, outcome, decision, result, **extra):
    audit.record(
        EventType.PORTAL_DECISION, outcome=outcome, channel=channel, user=user,
        detail={
            "link": item.proposal.link_id, "item": item.pk, "kind": item.kind, "key": item.key,
            "content_sha256": item.content_sha256, "decision": decision, "result": result,
            **extra,
        },
    )


def _blocker(item, confirmation):
    """Por qué un ítem aprobado no se puede cargar todavía, o `""`."""
    link = PortalLink.objects.get(pk=item.proposal.link_id)
    if item.kind != ItemKind.PROCEDIMIENTO and link.procedure_id is None:
        return "Falta el procedimiento: apruebe antes el procedimiento."
    if item.kind == ItemKind.OFERTA and not link.procedure.portal_lines.exists():
        return "Faltan los renglones: apruébelos antes que las ofertas."
    if item.kind == ItemKind.PROCEDIMIENTO:
        module = discover()[item.kind]
        if module.needs_authorization_date(item) and not isinstance(
            confirmation.get("authorization_date"), date
        ):
            return "Confirme la fecha de autorización del procedimiento."
    check = getattr(discover()[item.kind], "blocker", None)  # p. ej. el tipo de una circular
    return check(item, confirmation) if check else ""


def _reason(error):
    text = str(error)
    return text if isinstance(error, ValueError) and text else f"{type(error).__name__}: {text}"


def _decide_one(user, item_id, decision, confirmation, channel):
    with transaction.atomic():
        item = (PortalItem.objects.select_for_update().select_related("proposal__link")
                .get(pk=item_id))
        if item.state != ItemState.PROPUESTO:
            return ItemResult(item, ALREADY, f"El ítem ya está {item.get_state_display().lower()}.")
        now = timezone.now()
        item.decided_by, item.decided_at = user, now
        if decision == REJECT:
            item.state = ItemState.RECHAZADO
            item.save(update_fields=["state", "decided_by", "decided_at"])
            _event(item, user, channel, Outcome.OK, REJECT, REJECTED)
            _end_if_dictamen(item, user, channel)
            return ItemResult(item, REJECTED)
        blocker = _blocker(item, confirmation)
        if blocker:
            _event(item, user, channel, Outcome.FAILED, APPROVE, PENDING, reason=blocker)
            item.decided_by = item.decided_at = None
            return ItemResult(item, PENDING, blocker)
        try:
            with transaction.atomic():
                loaded = discover()[item.kind].load(user, item, confirmation, channel)
                if loaded is None:
                    # No se creó nada: el original queda como archivo del Portal (acta,
                    # dictamen, actos); el ítem queda aprobado.
                    item.state, item.loaded_model, item.loaded_id = ItemState.APROBADO, "", None
                else:
                    item.state = ItemState.CARGADO
                    item.loaded_model, item.loaded_id = loaded
                item.save(update_fields=["state", "decided_by", "decided_at", "loaded_model",
                                         "loaded_id"])
        except Exception as error:  # noqa: BLE001 - toda falla de carga deja el ítem fallido
            reason = _reason(error)
            item.state, item.failure = ItemState.FALLIDO, reason
            item.loaded_model, item.loaded_id = "", None
            item.save(update_fields=["state", "decided_by", "decided_at", "failure",
                                     "loaded_model", "loaded_id"])
            _event(item, user, channel, Outcome.FAILED, APPROVE, FAILED, reason=reason)
            return ItemResult(item, FAILED, reason)
        _end_if_dictamen(item, user, channel)
        if item.state == ItemState.APROBADO:
            _event(item, user, channel, Outcome.OK, APPROVE, KEPT_AS_FILE, file=item.file_id)
            return ItemResult(item, KEPT_AS_FILE)
        _event(item, user, channel, Outcome.OK, APPROVE, LOADED,
               loaded_model=item.loaded_model, loaded_id=item.loaded_id)
        # Un importador puede dejar en `item.notice` un aviso para quien aprobó (por ejemplo,
        # que el Portal cambió el nombre o el objeto y el procedimiento conserva el anterior).
        return ItemResult(item, LOADED, getattr(item, "notice", ""))


def _end_if_dictamen(item, user, channel):
    """Decidido el ítem del dictamen (aprobado o rechazado), termina el seguimiento."""
    if item.kind == ItemKind.DOCUMENTO and item.payload.get("clase") == "dictamen":
        end_following_for_dictamen(item, user, channel)
