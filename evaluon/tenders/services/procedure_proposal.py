"""Alta de un procedimiento desde el pliego subido (REQ-077; ADR-0049; plan 014; T-196).

No hay alta en blanco: el procedimiento nace de un pliego que se sube, se lee y se propone.

- `upload_tender(user, data, file_name)`: guarda el pliego en un borrador (`ProcedureDraft`,
  estado «leyendo») y encola el pedido `propose_procedure`. Lo hacen el operador y el
  evaluador. Rechaza un archivo vacío, de formato no soportado o que ya está subido (en otro
  borrador pendiente o como pliego de un procedimiento).
- `run_propose_procedure(job)`: el manejador del pedido (lo registra `jobs.HANDLERS`). Lee el
  pliego con la lectura local, propone número, expediente, tipo, objeto y fecha de
  autorización, cada uno con su cita (página y texto), y los renglones (número, descripción,
  cantidad); lo que no tiene cita verificable queda «no determinado». Deja el borrador
  «propuesto» y el hecho `procedure_proposal`; si falla, «fallido» y el hecho fallido.
- `proposal_of(user, draft_id)`: el borrador con su propuesta, para mostrarlo.
- `correct(user, draft_id, field, value, reason)`: solo el evaluador. Cambia un dato o un dato
  de un renglón ya propuesto escribiendo el valor y el motivo (obligatorio); guarda el valor
  propuesto, el corregido, el motivo, quién y cuándo, y nada de eso se borra. `field` es un
  dato (`number`, `file_number`, `procedure_type`, `subject`, `authorization_date`) o
  `line.N.description`, `line.N.quantity` o `line.N.unit`. No se agregan renglones.
- `approve(user, draft_id, decisions=None)`: solo el evaluador. Con los cuatro datos
  obligatorios resueltos (propuestos o corregidos), crea el procedimiento con
  `register_procedure`, le carga el pliego con `load_document`, escribe renglones y expediente
  en `portal_line` y `portal_procedure_data` con el documento como origen, y marca el borrador
  «aprobado»: todo en una transacción (el esquema exige que `aprobado` y el procedimiento
  resultante se escriban juntos). `decisions={"discard_lines": [n, …]}` descarta renglones.
  Deja el hecho `procedure_proposal` con lo propuesto, lo corregido, los motivos y lo descartado.
- `reject(user, draft_id, reason)`: solo el evaluador. Descarta un borrador mal leído («rechazado»,
  o un borrador «fallido» que se da por cerrado), con motivo obligatorio, quién y cuándo, y deja
  el hecho: el mismo archivo se puede volver a subir. No crea nada.

El rol se comprueba fuera de toda transacción para que el hecho `rejected` no se pierda. Los
mensajes son para la persona que usa la pantalla: español llano.
"""

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.norms.reading import detect_format
from evaluon.portal.models import PortalLine, PortalProcedureData
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    Document,
    DocumentKind,
    JobKind,
    ProcedureDraft,
)
from evaluon.tenders.proposal import procedure_fields as fields_module
from evaluon.tenders.proposal.procedure_fields import FIELDS, REQUIRED_FIELDS
from evaluon.tenders.services import documents
from evaluon.tenders.services.procedures import (
    ProcedureRefused,
    register_procedure,
    today,
)

UPLOAD_OPERATION = "evaluon.tenders.services.procedure_proposal.upload_tender"
VIEW_OPERATION = "evaluon.tenders.services.procedure_proposal.proposal_of"
CORRECT_OPERATION = "evaluon.tenders.services.procedure_proposal.correct"
APPROVE_OPERATION = "evaluon.tenders.services.procedure_proposal.approve"
REJECT_OPERATION = "evaluon.tenders.services.procedure_proposal.reject"

LINE_ATTRS = ("description", "quantity", "unit")
_LINE_FIELD = re.compile(r"line\.(\d+)\.(description|quantity|unit)")

FIELD_NAMES = {
    "number": "el número",
    "file_number": "el expediente",
    "procedure_type": "el tipo",
    "subject": "el objeto",
    "authorization_date": "la fecha de autorización",
}


class ProposalRefused(ValueError):
    """No se hizo lo pedido sobre la propuesta. `reason` es el motivo que queda en el
    registro y `field`, el dato que lo impidió."""

    reason = "invalid_data"

    def __init__(self, message, field=None, reason=None):
        super().__init__(message)
        self.field = field
        if reason is not None:
            self.reason = reason


class DuplicateTender(ProposalRefused):
    reason = "duplicate_file"


class ReasonRequired(ProposalRefused):
    reason = "missing_reason"


class IncompleteProposal(ProposalRefused):
    reason = "incomplete"


class NotPending(ProposalRefused):
    reason = "not_proposed"


# --- Ayudas ------------------------------------------------------------------------------


def _username(user):
    return user.get_username() if user is not None else ""


def _file_detail(file_name, file_format, data, sha256):
    return {"name": file_name, "format": file_format, "size": len(data), "sha256": sha256}


def _draft_detail(draft, **extra):
    return {"draft": draft.pk, "file": _file_detail(draft.file_name, draft.file_format,
                                                    bytes(draft.content),
                                                    draft.file_sha256), **extra}


def _record_refusal(user, channel, error, detail):
    audit.record(EventType.PROCEDURE_PROPOSAL, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason, "message": str(error)})


def _tender_already_loaded(sha256, exclude_draft=None):
    """Mensaje si el mismo archivo ya está como pliego de un procedimiento o en otro borrador
    pendiente; `None` si no."""
    loaded = Document.objects.filter(file_sha256=sha256, kind=DocumentKind.PLIEGO).first()
    if loaded is not None:
        return (f"Ese pliego ya está cargado en el procedimiento {loaded.procedure.number}: "
                "no se subió de nuevo.")
    pending = ProcedureDraft.objects.filter(
        file_sha256=sha256, state__in=[ProposalState.LEYENDO, ProposalState.PROPUESTO])
    if exclude_draft is not None:
        pending = pending.exclude(pk=exclude_draft)
    if pending.exists():
        return "Ese pliego ya se subió y espera su aprobación: no se subió de nuevo."
    return None


def _get_draft(draft_id, *, lock=False):
    queryset = ProcedureDraft.objects.select_for_update() if lock else ProcedureDraft.objects
    return queryset.get(pk=draft_id)


def _effective(proposal):
    """Valores vigentes de la propuesta: `({dato: valor}, {número: {atributo: valor}})`, con la
    última corrección de cada uno por encima de lo propuesto."""
    corrections = {}
    for item in proposal.get("corrections", []):
        corrections[item["field"]] = item["corrected"]
    values = {name: corrections.get(name, proposal["fields"][name]["proposed"]) for name in FIELDS}
    lines = {}
    for line in proposal["lines"]:
        number = line["number"]
        lines[number] = {
            "number": number,
            **{attr: corrections.get(f"line.{number}.{attr}", line[attr]) for attr in LINE_ATTRS},
        }
    return values, lines


def _parse_date(value):
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _clean_value(field, value):
    """El valor corregido ya validado y normalizado, o `ProposalRefused`."""
    text = str(value if value is not None else "").strip()
    if not text:
        raise ProposalRefused("Escriba el valor correcto.", field, "missing_value")
    if field == "authorization_date":
        parsed = _parse_date(text)
        if parsed is None:
            raise ProposalRefused("La fecha de autorización no es una fecha válida.", field)
        if parsed > today():
            raise ProposalRefused("La fecha de autorización no puede ser posterior a hoy.",
                                  field)
        return parsed.isoformat()
    if field.endswith(".quantity"):
        try:
            number = Decimal(text.replace(",", "."))
        except InvalidOperation:
            raise ProposalRefused("La cantidad tiene que ser un número.", field) from None
        if number <= 0:
            raise ProposalRefused("La cantidad tiene que ser mayor que cero.", field)
        return format(number.normalize(), "f")
    return text


# --- Subir -------------------------------------------------------------------------------


def upload_tender(user, data, file_name, *, channel=Channel.SCREEN):
    """Guarda el pliego en un borrador y encola su lectura. Devuelve el borrador (con su
    pedido en `.job`). Ver el módulo."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=UPLOAD_OPERATION,
                            channel=channel)
    data = bytes(data or b"")
    file_name = (file_name or "").strip()
    sha256 = hashlib.sha256(data).hexdigest()
    file_format = detect_format(data) if data else None
    detail = {"file": _file_detail(file_name, file_format, data, sha256), "action": "upload"}
    try:
        if not data or not file_name:
            raise ProposalRefused("Elija el archivo del pliego.", "file", "missing_data")
        if file_format is None:
            raise ProposalRefused(
                "El archivo no es un PDF ni una página web guardada (.html): no se subió.",
                "file", "unsupported_format")
        message = _tender_already_loaded(sha256)
        if message:
            raise DuplicateTender(message, "file")
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    with transaction.atomic():
        draft = ProcedureDraft.objects.create(
            file_name=file_name, file_format=file_format, file_size=len(data),
            file_sha256=sha256, content=data, created_by=user)
        job = jobs.enqueue(JobKind.PROPOSE_PROCEDURE, procedure=None, requested_by=user,
                           target_id=draft.pk)
        draft.job = job
        draft.save(update_fields=["job"])
        audit.record(EventType.PROCEDURE_PROPOSAL, outcome=Outcome.OK, channel=channel,
                     user=user, detail={**detail, "draft": draft.pk, "job": job.pk})
    return draft


# --- Pedido en segundo plano ---------------------------------------------------------------


def _initial_proposal(proposal):
    data = proposal.as_json()
    data["corrections"] = []
    return data


def run_propose_procedure(job):
    """Manejador del pedido `propose_procedure`: lee el pliego del borrador `job.target_id` y
    guarda la propuesta. Ver el módulo. Si falla, deja el borrador «fallido» y el hecho
    fallido, y vuelve a lanzar el error para que la cola deje el pedido `failed`."""
    draft = _get_draft(job.target_id)
    if draft.state != ProposalState.LEYENDO:
        return
    base = {"draft": draft.pk, "job": job.pk, "file_sha256": draft.file_sha256,
            "action": "propose"}
    try:
        data = bytes(draft.content)
        if hashlib.sha256(data).hexdigest() != draft.file_sha256:
            raise ValueError("El original guardado no coincide con la huella con que se subió.")
        proposal = fields_module.propose(data)
        stored = _initial_proposal(proposal)
        with transaction.atomic():
            draft = _get_draft(draft.pk, lock=True)
            draft.proposal = stored
            draft.state = ProposalState.PROPUESTO
            draft.save(update_fields=["proposal", "state"])
            audit.record(
                EventType.PROCEDURE_PROPOSAL, outcome=Outcome.OK, channel=Channel.COMMAND,
                user=job.requested_by,
                detail={**base, "fields": {name: stored["fields"][name]["state"]
                                           for name in FIELDS},
                        "lines": len(stored["lines"]), "reading": proposal.reading,
                        "rules_version": fields_module.RULES_VERSION,
                        "model": proposal.model_trace})
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        with transaction.atomic():
            ProcedureDraft.objects.filter(pk=draft.pk).update(
                state=ProposalState.FALLIDO, failure=message)
            audit.record(EventType.PROCEDURE_PROPOSAL, outcome=Outcome.FAILED,
                         channel=Channel.COMMAND, user=job.requested_by,
                         detail={**base, "reason": message})
        raise


# --- Ver, corregir, aprobar ----------------------------------------------------------------


def proposal_of(user, draft_id, *, channel=Channel.SCREEN):
    """El borrador con su propuesta. Lo ven el operador y el evaluador."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=VIEW_OPERATION,
                            channel=channel)
    return _get_draft(draft_id)


def _check_pending(draft):
    if draft.state != ProposalState.PROPUESTO:
        raise NotPending("La propuesta todavía no está lista o ya se resolvió.", None)


def correct(user, draft_id, field, value, reason, *, channel=Channel.SCREEN):
    """Corrige un dato o un renglón propuesto con el valor y el motivo. Ver el módulo."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=CORRECT_OPERATION,
                            channel=channel)
    detail = {"draft": draft_id, "action": "correct", "field": field}
    try:
        reason = (reason or "").strip()
        if not reason:
            raise ReasonRequired("Escriba el motivo de la corrección.", field)
        with transaction.atomic():
            draft = _get_draft(draft_id, lock=True)
            _check_pending(draft)
            proposal = draft.proposal
            values, lines = _effective(proposal)
            line_match = _LINE_FIELD.fullmatch(field)
            if line_match:
                number = int(line_match.group(1))
                if number not in lines:
                    raise ProposalRefused("Ese renglón no está en la propuesta.", field,
                                          "unknown_field")
                proposed = lines[number][line_match.group(2)]
                original = next(item for item in proposal["lines"]
                                if item["number"] == number)[line_match.group(2)]
            elif field in FIELDS:
                proposed = values[field]
                original = proposal["fields"][field]["proposed"]
            else:
                raise ProposalRefused("Ese dato no se puede corregir.", field, "unknown_field")
            corrected = _clean_value(field, value)
            entry = {"field": field, "proposed": original, "previous": proposed,
                     "corrected": corrected, "reason": reason, "by": _username(user),
                     "by_id": user.pk, "at": timezone.now().isoformat(timespec="seconds")}
            proposal["corrections"] = [*proposal.get("corrections", []), entry]
            draft.proposal = proposal
            draft.save(update_fields=["proposal"])
            audit.record(EventType.PROCEDURE_PROPOSAL, outcome=Outcome.OK, channel=channel,
                         user=user, detail={**detail, **entry})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft


def approve(user, draft_id, decisions=None, *, channel=Channel.SCREEN):
    """Aprueba la propuesta y crea el procedimiento. Ver el módulo. Devuelve el borrador
    aprobado (con `.procedure`)."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=APPROVE_OPERATION,
                            channel=channel)
    detail = {"draft": draft_id, "action": "approve"}
    try:
        with transaction.atomic():
            draft = _get_draft(draft_id, lock=True)
            _check_pending(draft)
            proposal = draft.proposal
            values, lines = _effective(proposal)
            discarded = sorted({int(n) for n in (decisions or {}).get("discard_lines", [])})
            unknown = [n for n in discarded if n not in lines]
            if unknown:
                raise ProposalRefused(f"El renglón {unknown[0]} no está en la propuesta.",
                                      "discard_lines", "unknown_field")
            missing = [name for name in REQUIRED_FIELDS if not values[name]]
            if missing:
                raise IncompleteProposal(
                    f"Falta {FIELD_NAMES[missing[0]]}: no está determinado en el pliego. "
                    "Corríjalo con su motivo para poder aprobar.", missing[0])
            authorization_date = _parse_date(values["authorization_date"])
            message = _tender_already_loaded(draft.file_sha256, exclude_draft=draft.pk)
            if message:
                raise DuplicateTender(message, "file")
            try:
                registration = register_procedure(
                    user, number=values["number"], procedure_type=values["procedure_type"],
                    subject=values["subject"], authorization_date=authorization_date,
                    channel=channel)
            except ProcedureRefused as error:
                raise ProposalRefused(str(error), error.field,
                                      type(error).__name__) from error
            procedure = registration.procedure
            loaded = documents.load_document(
                user, procedure, data=bytes(draft.content), file_name=draft.file_name,
                kind=DocumentKind.PLIEGO, title=f"Pliego {procedure.number}", channel=channel)
            if values["file_number"]:
                PortalProcedureData.objects.create(
                    procedure=procedure, file_number=values["file_number"][:100],
                    document=loaded.document)
            kept = [lines[number] for number in sorted(lines) if number not in discarded]
            for line in kept:
                PortalLine.objects.create(
                    procedure=procedure, number=line["number"],
                    description=line["description"],
                    quantity=Decimal(line["quantity"]) if line["quantity"] else None,
                    unit=(line["unit"] or "")[:100], document=loaded.document)
            draft.state = ProposalState.APROBADO
            draft.procedure = procedure
            draft.save(update_fields=["state", "procedure"])
            audit.record(
                EventType.PROCEDURE_PROPOSAL, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "procedure": procedure.pk, "document": loaded.document.pk,
                        "file_sha256": draft.file_sha256, "values": values,
                        "corrections": proposal.get("corrections", []),
                        "discarded_lines": discarded, "lines": len(kept)})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft


def reject(user, draft_id, reason, *, channel=Channel.SCREEN):
    """Descarta la propuesta de un pliego mal leído. Ver el módulo. Devuelve el borrador."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=REJECT_OPERATION,
                            channel=channel)
    detail = {"draft": draft_id, "action": "reject"}
    try:
        reason = (reason or "").strip()
        if not reason:
            raise ReasonRequired("Escriba el motivo por el que se descarta la propuesta.",
                                 "reason")
        with transaction.atomic():
            draft = _get_draft(draft_id, lock=True)
            if draft.state not in (ProposalState.PROPUESTO, ProposalState.FALLIDO):
                raise NotPending("La propuesta todavía no está lista o ya se resolvió.", None)
            entry = {"reason": reason, "by": _username(user), "by_id": user.pk,
                     "at": timezone.now().isoformat(timespec="seconds"),
                     "previous_state": draft.state}
            draft.proposal = {**draft.proposal, "rejection": entry}
            draft.state = ProposalState.RECHAZADO
            draft.save(update_fields=["proposal", "state"])
            audit.record(EventType.PROCEDURE_PROPOSAL, outcome=Outcome.OK, channel=channel,
                         user=user, detail={**detail, **entry,
                                            "file_sha256": draft.file_sha256})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft
