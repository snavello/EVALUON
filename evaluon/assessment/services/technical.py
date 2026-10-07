"""Ok de la Comisión al informe técnico (REQ-061; plan 004, "Ok del informe técnico" y "Cuándo
deja de estar pendiente"; ADR-0043; T-168).

El juicio técnico es del área correspondiente: el sistema no lee el informe. La Comisión da su
ok de que **tiene el informe técnico aprobado** y carga por renglón lo que ese informe dice
(`apto` o `no_apto`). Con el ok, la fila técnica del renglón pasa a "cumple" o "no cumple" con
el fundamento «informe técnico aprobado, ok de la Comisión por … el …»; un "no cumple" entra al
descarte propuesto por renglón (`ordering.propose_discards`, sin cambios).

- `give_ok` y `withdraw_ok`: solo el evaluador (P3). Cada una inserta su fila en
  `assessment_technical_ok` y deja el hecho `eval_decision` con `kind = technical_ok`, en la
  misma transacción (P6). Retirar pide nota.
- **Resultado nuevo de solo inserción.** Las tablas son de solo inserción: el cambio de la fila
  es un resultado nuevo del par (`previous` apunta al anterior, que queda en el historial) dentro
  de una evaluación `manual` mínima (sin documentos ni modelo; `counts.technical_ok` la explica).
  Solo se cambia una fila que hoy está pendiente del informe técnico o que ya salió de un ok;
  cualquier otra (por ejemplo, un renglón que la oferta no cotizó) no se toca y queda en
  `skipped`. Retirar el ok devuelve la fila a "pendiente del informe técnico".
- `ok_of(offer, item)`: la última fila de ok que nombra al renglón (`items` nulo nombra a todos).
- **Propuesta del informe del área (T-190; REQ-074).** Cuando la Comisión sube el informe técnico
  aprobado del área, `technical_report.py` lo lee y propone por renglón apto o no apto con la cita
  literal del informe (o dice que no lo trata). `proposals_of` devuelve esa propuesta vigente y la
  matriz la precarga junto al ok: la Comisión la confirma o la corrige al dar el ok, y el hecho del
  ok registra qué se propuso y si se corrigió (P6). El sistema no juzga lo técnico: solo toma lo
  que dice el informe (P3).
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment.models import (
    Citation,
    CitationKind,
    Cause,
    Doubt,
    Outcome,
    Request,
    Result,
    Run,
    TechnicalAction,
    TechnicalOk,
    TechnicalVerdict,
)
from evaluon.assessment.models import Channel as RunChannel
from evaluon.assessment.services.evaluate import current_result
from evaluon.assessment import grounds
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers.models import Offer
from evaluon.offers.services import sheets
from evaluon.tenders.services.validation import latest_validated

GIVE_OPERATION = "evaluon.assessment.services.technical.give_ok"
WITHDRAW_OPERATION = "evaluon.assessment.services.technical.withdraw_ok"

KIND = "technical_ok"
RULE = "ok_informe_tecnico"


class TechnicalRefused(ValueError):
    """No se guardó el ok. `reason` es el motivo que queda en el registro y `field`, el dato
    que lo impidió. El mensaje es para la persona: español llano."""

    def __init__(self, message, reason, field=None):
        super().__init__(message)
        self.reason = reason
        self.field = field


@dataclass
class Applied:
    """Lo que dejó un ok: su fila, el hecho, la evaluación mínima con los resultados nuevos y
    los renglones que no se tocaron (por no estar pendientes del informe técnico)."""

    ok: TechnicalOk
    event: object
    run: Run | None
    results: list = field(default_factory=list)
    skipped: list = field(default_factory=list)


@dataclass
class TechnicalRow:
    """El estado del ok de un renglón de una oferta, para la matriz."""

    item: int
    requirement: object
    ok: TechnicalOk | None
    # Lo que el informe del área dice de este renglón de esta oferta (`Proposal`), si se subió.
    proposal: object = None

    @property
    def approved(self):
        return self.ok is not None and self.ok.action == TechnicalAction.DAR_OK

    @property
    def withdrawn(self):
        return self.ok is not None and self.ok.action == TechnicalAction.RETIRAR_OK

    @property
    def verdict(self):
        if not self.approved:
            return ""
        return self.ok.verdicts.get(str(self.item), "")

    @property
    def verdict_label(self):
        return TechnicalVerdict(self.verdict).label if self.verdict else ""


# --- Qué renglones hay ---------------------------------------------------------------------


def _version_of(offer):
    """La versión de la matriz de las filas de la oferta: la de su evaluación más reciente; si
    no se evaluó, la validada vigente."""
    latest = (Result.objects.filter(offer=offer).select_related("run__matrix_version")
              .order_by("-run__matrix_version__number", "-run__number", "-pk").first())
    return latest.run.matrix_version if latest else latest_validated(offer.procedure)


def item_rows(offer, version=None):
    """`{renglón: requisito}` de las filas técnicas por renglón de la matriz de la oferta."""
    version = version or _version_of(offer)
    rows = {}
    for requirement in (sheets.firm_requirements(version) if version else []):
        if sheets.is_item_row(requirement):
            try:
                rows[int(requirement.items[0])] = requirement
            except (TypeError, ValueError):
                continue
    return rows


def _as_item(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise TechnicalRefused("Hay un renglón que no es un número.", "unknown_item", "items")


def _scope(rows, items):
    """Los renglones que alcanza un ok: todos si `items` es `None`."""
    if items is None:
        scope = sorted(rows)
    else:
        scope = sorted({_as_item(i) for i in items})
        unknown = [i for i in scope if i not in rows]
        if unknown:
            raise TechnicalRefused(
                "La oferta no tiene fila técnica para el renglón "
                + ", ".join(str(i) for i in unknown) + ".", "unknown_item", "items")
    if not scope:
        raise TechnicalRefused("Elija al menos un renglón.", "no_items", "items")
    return scope


# --- Estado --------------------------------------------------------------------------------


def ok_of(offer, item):
    """La última fila de ok que nombra al renglón `item` (dar o retirar), o `None`."""
    item = _as_item(item)
    for row in TechnicalOk.objects.filter(offer=offer).select_related("user") \
            .order_by("-at", "-pk"):
        if row.items is None or item in [int(i) for i in row.items]:
            return row
    return None


def has_ok(offer, item):
    """El renglón tiene hoy un ok vigente (el último que lo nombra es "dar el ok")."""
    row = ok_of(offer, item)
    return row is not None and row.action == TechnicalAction.DAR_OK


def status_of(offer, version=None):
    """Las filas técnicas por renglón de la oferta con su ok vigente y la propuesta del informe
    del área, en orden de renglón."""
    proposals = proposals_of(offer)
    return [TechnicalRow(item=item, requirement=requirement, ok=ok_of(offer, item),
                         proposal=proposals.get(item))
            for item, requirement in sorted(item_rows(offer, version).items())]


# --- Propuesta del informe del área --------------------------------------------------------------

PROPOSAL_KIND = "technical_proposal"

NOT_TREATED = "no_trata"
REASON_LABELS = {
    NOT_TREATED: "El informe no trata este renglón de esta oferta.",
    "contradictorio": "El informe dice cosas distintas de este renglón en tramos distintos.",
    "cita_no_ubicada": ("El sistema no pudo copiar del informe la frase donde lo dice, "
                        "así que no propone."),
    "paginas_sin_leer": "Hay páginas del informe que no se pudieron leer.",
    "sin_lectura": "El informe todavía no tiene lectura.",
    "falla": "No se pudo leer el informe con el modelo.",
}


@dataclass
class Proposal:
    """Lo que el informe del área dice de un renglón de una oferta (T-190). Con `verdict` hay
    propuesta y `quote` es la cita literal del informe; sin él, `reason` dice por qué no se
    propone."""

    item: int
    verdict: str = ""
    quote: str = ""
    page: int | None = None
    document: int | None = None
    document_title: str = ""
    motive: str = ""
    reason: str = ""
    event: int | None = None

    @property
    def verdict_label(self):
        return TechnicalVerdict(self.verdict).label if self.verdict else ""

    @property
    def reason_label(self):
        return REASON_LABELS.get(self.reason, self.reason)


def proposals_of(offer):
    """`{renglón: Proposal}` vigente de la oferta, según los informes del área que se leyeron.
    Se toma la última propuesta de cada informe; entre informes, para cada renglón rige la más
    nueva que trae dictamen (si ninguna lo trae, queda el motivo de la más nueva)."""
    found, seen = {}, set()
    events = AuditEvent.objects.filter(
        event_type=EventType.EVAL_BUILD, outcome=EventOutcome.OK,
        detail__kind=PROPOSAL_KIND, detail__offer=offer.pk).order_by("-pk")
    for event in events:
        detail = event.detail
        if detail.get("document") in seen:
            continue
        seen.add(detail.get("document"))
        for key, entry in (detail.get("items") or {}).items():
            item = int(key)
            proposal = Proposal(
                item=item, verdict=entry.get("verdict") or "", quote=entry.get("quote", ""),
                page=entry.get("page"), document=detail.get("document"),
                document_title=detail.get("document_title", ""), motive=entry.get("motive", ""),
                reason=entry.get("reason", ""), event=event.pk)
            if item not in found or (proposal.verdict and not found[item].verdict):
                found[item] = proposal
    return found


def _proposal_record(offer, scope, clean):
    """Lo que el ok deja anotado de la propuesta: por renglón, qué se propuso y si la Comisión
    lo corrigió (P6)."""
    proposals = proposals_of(offer)
    record = {}
    for item in scope:
        proposal = proposals.get(item)
        proposed = proposal.verdict if proposal and proposal.verdict else None
        record[str(item)] = {
            "proposed": proposed, "given": clean.get(str(item)),
            "corrected": proposed is not None and proposed != clean.get(str(item)),
            "document": proposal.document if proposed else None,
            "event": proposal.event if proposed else None}
    return record


# --- Dar y retirar ---------------------------------------------------------------------------


def _name(user):
    return user.get_username()


def _clean_verdicts(scope, verdicts):
    verdicts = {str(k): v for k, v in (verdicts or {}).items()}
    extra = sorted(set(verdicts) - {str(i) for i in scope})
    if extra:
        raise TechnicalRefused(
            "Hay lo que dice el informe de renglones que el ok no nombra: "
            + ", ".join(extra) + ".", "verdict_out_of_scope", "verdicts")
    clean = {}
    for item in scope:
        value = verdicts.get(str(item))
        if value is None or value == "":
            raise TechnicalRefused(
                f"Falta lo que dice el informe técnico del renglón {item}: apto o no apto.",
                "verdict_required", "verdicts")
        if value not in TechnicalVerdict.values:
            raise TechnicalRefused(
                f"Lo que dice el informe técnico del renglón {item} debe ser apto o no apto.",
                "verdict_invalid", "verdicts")
        clean[str(item)] = value
    return clean


def _reject_record(error, operation, channel, user, detail):
    audit.record(
        EventType.EVAL_DECISION, outcome=EventOutcome.REJECTED, channel=channel, user=user,
        detail={**detail, "kind": KIND, "reason": error.reason, "message": str(error),
                "operation": operation})


def give_ok(user, offer, items=None, verdicts=None, note="", *, channel=Channel.SCREEN):
    """El evaluador da el ok: la Comisión tiene aprobado el informe técnico de la oferta (todo,
    si `items` es `None`, o los renglones de `items`). `verdicts` es `{renglón: "apto" o
    "no_apto"}` y tiene que traer todos los renglones del ok. Lanza `RoleRejected` sin rol de
    evaluador y `TechnicalRefused` si falta algún dato."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=GIVE_OPERATION,
                            channel=channel)
    detail = {"offer": offer.pk, "action": TechnicalAction.DAR_OK,
              "items": None if items is None else list(items)}
    try:
        with transaction.atomic():
            return _apply(user, offer, TechnicalAction.DAR_OK, items, verdicts,
                          (note or "").strip(), channel)
    except TechnicalRefused as error:
        _reject_record(error, GIVE_OPERATION, channel, user, detail)
        raise


def withdraw_ok(user, offer, items=None, note="", *, channel=Channel.SCREEN):
    """El evaluador retira el ok: las filas vuelven a "pendiente del informe técnico". La nota
    es obligatoria."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=WITHDRAW_OPERATION,
                            channel=channel)
    detail = {"offer": offer.pk, "action": TechnicalAction.RETIRAR_OK,
              "items": None if items is None else list(items)}
    try:
        with transaction.atomic():
            return _apply(user, offer, TechnicalAction.RETIRAR_OK, items, None,
                          (note or "").strip(), channel)
    except TechnicalRefused as error:
        _reject_record(error, WITHDRAW_OPERATION, channel, user, detail)
        raise


def _eligible(offer, requirement, action):
    """El resultado vigente de la fila si el ok puede cambiarla, o `None`."""
    current = current_result(offer, requirement)
    if current is None:
        return None
    if action == TechnicalAction.DAR_OK:
        pending = (current.outcome == Outcome.NO_DETERMINADO
                   and current.doubt == Doubt.PENDIENTE_INFORME_TECNICO)
        return current if pending or current.facts.get("technical_ok") else None
    return current if current.facts.get("technical_ok") else None


def _apply(user, offer, action, items, verdicts, note, channel):
    if action == TechnicalAction.RETIRAR_OK and not note:
        raise TechnicalRefused("Escriba el motivo por el que retira el ok.", "note_required",
                               "note")
    Offer.objects.select_for_update().get(pk=offer.pk)
    version = _version_of(offer)
    rows = item_rows(offer, version)
    scope = _scope(rows, items)
    clean = _clean_verdicts(scope, verdicts) if action == TechnicalAction.DAR_OK else {}
    if action == TechnicalAction.RETIRAR_OK and not any(has_ok(offer, i) for i in scope):
        raise TechnicalRefused("No hay un ok vigente para retirar en esos renglones.",
                               "no_ok", "items")

    targets, skipped = [], []
    for item in scope:
        current = _eligible(offer, rows[item], action)
        if action == TechnicalAction.RETIRAR_OK and not has_ok(offer, item):
            current = None
        if current is None:
            skipped.append(item)
        else:
            targets.append((item, rows[item], current))

    at = timezone.now()
    event = audit.record(
        EventType.EVAL_DECISION, outcome=EventOutcome.OK, channel=channel, user=user,
        detail={"kind": KIND, "offer": offer.pk, "action": action,
                "items": None if items is None else scope, "verdicts": clean, "note": note,
                "proposal": (_proposal_record(offer, scope, clean)
                             if action == TechnicalAction.DAR_OK else {}),
                "user": user.get_username(), "changed": [t[0] for t in targets],
                "skipped": skipped})
    ok = TechnicalOk.objects.create(
        offer=offer, items=None if items is None else scope, verdicts=clean, action=action,
        note=note, user=user, at=at, event=event)
    if not targets:
        return Applied(ok=ok, event=event, run=None, skipped=skipped)

    request = Request.objects.create(
        procedure=offer.procedure, matrix_version=version, offers=[offer.pk],
        requirements=[t[1].pk for t in targets], cause=Cause.MANUAL, requested_by=user,
        requested_at=at)
    last = Run.objects.filter(offer=offer).aggregate(last=Max("number"))["last"] or 0
    run = Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=last + 1,
        channel=RunChannel.SCREEN, documents=[], norms=grounds.norms_record(version),
        models_used={}, parameters={"origen": KIND},
        prompt_versions={}, counts={"technical_ok": len(targets), "action": action},
        built_at=at)
    results = [_insert_result(run, offer, ok, user, action, item, requirement, current, at)
               for item, requirement, current in targets]
    return Applied(ok=ok, event=event, run=run, results=results, skipped=skipped)


def _when(at):
    return timezone.localtime(at).strftime("%d/%m/%Y %H:%M")


def _insert_result(run, offer, ok, user, action, item, requirement, current, at):
    who = f"{_name(user)} el {_when(at)}"
    facts = {"regla": RULE, "technical_ok": ok.pk, "renglon": item, "usuario": user.get_username()}
    if action == TechnicalAction.DAR_OK:
        verdict = ok.verdicts[str(item)]
        outcome = Outcome.CUMPLE if verdict == TechnicalVerdict.APTO else Outcome.NO_CUMPLE
        doubt = ""
        explanation = f"informe técnico aprobado, ok de la Comisión por {who}"
        facts["dictamen"] = verdict
    else:
        outcome, doubt = Outcome.NO_DETERMINADO, Doubt.PENDIENTE_INFORME_TECNICO
        explanation = (f"Ok del informe técnico retirado por {who}: {ok.note} "
                       "Pendiente del informe técnico.")
    result = Result.objects.create(
        run=run, offer=offer, requirement=requirement, outcome=outcome, doubt=doubt,
        exigence=current.exigence, explanation=explanation, opinion=current.opinion,
        facts=facts, previous=current)
    # El pliego sigue siendo el fundamento de la fila: se copia la cita vigente del anterior.
    order = 0
    for cited in current.citations.filter(kind=CitationKind.PLIEGO).order_by("order"):
        order += 1
        Citation.objects.create(
            result=result, order=order, kind=CitationKind.PLIEGO,
            requirement_quote=cited.requirement_quote, text=cited.text,
            original_text=cited.original_text)
    return result
