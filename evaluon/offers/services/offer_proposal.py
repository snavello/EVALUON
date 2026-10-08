"""Alta de una oferta desde sus archivos (REQ-083; ADR-0049; plan 014; T-220).

La oferta no puede existir sin oferente, así que sus archivos esperan en un borrador
(`OfferDraft`) hasta que un evaluador aprueba el nombre y el CUIT que el sistema propone.

- `upload_offer_files(user, procedure, files)`: guarda los archivos (`[(nombre, bytes), …]`) en
  un borrador (estado «leyendo») y encola el pedido `propose_offer`. Lo hacen el operador y el
  evaluador. Rechaza una lista vacía, un archivo vacío o de formato no soportado, un archivo
  repetido en la lista, en otro borrador pendiente o ya cargado en una oferta del procedimiento.
- `run_propose_offer(job)`: el manejador del pedido (lo registra `tenders.jobs.HANDLERS`). Lee
  los archivos con la lectura local de ofertas y propone el nombre del oferente y su CUIT, cada
  uno con su cita (documento, página y texto); el CUIT por regla con dígito verificador, el
  nombre por regla y, si no alcanza, con el modelo local pidiendo cita literal verificada. Lo
  que no tiene cita verificable queda «no determinado». Deja el borrador «propuesto» y el hecho
  `offer_proposal`; si falla, «fallido» y el hecho fallido.
- `proposal_of(user, draft_id)`: el borrador con su propuesta, para mostrarlo.
- `correct(user, draft_id, field, value, reason)`: solo el evaluador. `field` es `bidder` o
  `cuit`; escribe el valor y el motivo (obligatorio) y guarda lo propuesto, lo corregido, el
  motivo, quién y cuándo; nada de eso se borra.
- `approve(user, draft_id)`: solo el evaluador. Con nombre y CUIT resueltos (propuestos o
  corregidos) crea la oferta con `register_offer`, carga los archivos con `load_document`,
  guarda el CUIT en `portal_offer_data` con su documento de origen y marca el borrador
  «aprobado»: todo en una transacción. Rechaza un oferente repetido (mismo nombre o mismo
  CUIT en el procedimiento). Deja el hecho `offer_proposal` con lo propuesto, lo corregido y
  los motivos, además del `offer_register` de siempre.
- `reject(user, draft_id, reason)`: solo el evaluador. Descarta un borrador mal leído
  («rechazado», o un «fallido» que se da por cerrado) con motivo obligatorio, quién y cuándo:
  los mismos archivos se pueden volver a subir. No crea nada.

El rol se comprueba fuera de toda transacción para que el hecho `rejected` no se pierda. Los
mensajes son para la persona que usa la pantalla: español llano.
"""

import hashlib

from django.db import transaction
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.offers import proposal_fields as fields_module
from evaluon.offers import reading as reading_tools
from evaluon.offers.models import Document, OfferDraft, OfferDraftFile
from evaluon.offers.proposal_fields import FIELDS, Source
from evaluon.offers.services import offers as offers_service
from evaluon.portal.models import PortalOfferData
from evaluon.tenders import jobs
from evaluon.tenders.models import JobKind

UPLOAD_OPERATION = "evaluon.offers.services.offer_proposal.upload_offer_files"
VIEW_OPERATION = "evaluon.offers.services.offer_proposal.proposal_of"
CORRECT_OPERATION = "evaluon.offers.services.offer_proposal.correct"
APPROVE_OPERATION = "evaluon.offers.services.offer_proposal.approve"
REJECT_OPERATION = "evaluon.offers.services.offer_proposal.reject"

FIELD_NAMES = {"bidder": "el nombre del oferente", "cuit": "el CUIT"}


class ProposalRefused(ValueError):
    """No se hizo lo pedido sobre la propuesta. `reason` es el motivo que queda en el
    registro y `field`, el dato que lo impidió."""

    reason = "invalid_data"

    def __init__(self, message, field=None, reason=None):
        super().__init__(message)
        self.field = field
        if reason is not None:
            self.reason = reason


class DuplicateFiles(ProposalRefused):
    reason = "duplicate_file"


class DuplicateBidder(ProposalRefused):
    reason = "duplicate_bidder"


class ReasonRequired(ProposalRefused):
    reason = "missing_reason"


class IncompleteProposal(ProposalRefused):
    reason = "incomplete"


class NotPending(ProposalRefused):
    reason = "not_proposed"


# --- Ayudas ------------------------------------------------------------------------------


def _username(user):
    return user.get_username() if user is not None else ""


def _file_detail(name, file_format, data, sha256):
    return {"name": name, "format": file_format, "size": len(data), "sha256": sha256}


def _record_refusal(user, channel, error, detail):
    audit.record(EventType.OFFER_PROPOSAL, outcome=Outcome.REJECTED, channel=channel,
                 user=user, detail={**detail, "reason": error.reason, "message": str(error)})


def _get_draft(draft_id, *, lock=False):
    queryset = OfferDraft.objects.select_for_update() if lock else OfferDraft.objects
    return queryset.get(pk=draft_id)


def _effective(proposal):
    """Valores vigentes de la propuesta, `{dato: valor}`: la última corrección de cada dato
    por encima de lo propuesto."""
    corrections = {}
    for item in proposal.get("corrections", []):
        corrections[item["field"]] = item["corrected"]
    return {name: corrections.get(name, proposal["fields"][name]["proposed"])
            for name in FIELDS}


def _clean_value(field, value):
    """El valor corregido ya validado y normalizado, o `ProposalRefused`."""
    text = " ".join(str(value if value is not None else "").split())
    if not text:
        raise ProposalRefused("Escriba el valor correcto.", field, "missing_value")
    if field == "cuit":
        cuit = fields_module.normalize_cuit(text)
        if cuit is None:
            raise ProposalRefused(
                "El CUIT no es válido: tiene que tener 11 cifras y su dígito verificador.",
                field)
        return cuit
    if len(text) > 300:
        raise ProposalRefused("El nombre es demasiado largo.", field)
    return text


def _pending_elsewhere(procedure, sha256s, exclude_draft=None):
    """Mensaje si alguno de los archivos ya está cargado en una oferta del procedimiento o en
    otro borrador pendiente del mismo; `None` si no."""
    loaded = Document.objects.filter(offer__procedure=procedure,
                                     file_sha256__in=sha256s).select_related("offer").first()
    if loaded is not None:
        return (f"El archivo «{loaded.file_name}» ya está cargado en la oferta "
                f"{loaded.offer.number} de este procedimiento: no se subió.")
    pending = OfferDraftFile.objects.filter(
        file_sha256__in=sha256s, draft__procedure=procedure,
        draft__state__in=[ProposalState.LEYENDO, ProposalState.PROPUESTO])
    if exclude_draft is not None:
        pending = pending.exclude(draft_id=exclude_draft)
    other = pending.first()
    if other is not None:
        return (f"El archivo «{other.file_name}» ya se subió y espera su aprobación: "
                "no se subió de nuevo.")
    return None


# --- Subir -------------------------------------------------------------------------------


def upload_offer_files(user, procedure, files, *, channel=Channel.SCREEN):
    """Guarda los archivos `files` (`[(nombre, bytes), …]`) en un borrador de oferta de
    `procedure` y encola su lectura. Devuelve el borrador (con su pedido en `.job`). Ver el
    módulo."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=UPLOAD_OPERATION,
                            channel=channel)
    prepared = []
    for name, data in files or []:
        data = bytes(data or b"")
        prepared.append((" ".join((name or "").split()), data,
                         hashlib.sha256(data).hexdigest()))
    detail = {"procedure": procedure.pk, "action": "upload",
              "files": [_file_detail(n, None, d, s) for n, d, s in prepared]}
    formats = []
    try:
        if not prepared:
            raise ProposalRefused("Elija los archivos de la oferta.", "files", "missing_data")
        seen = set()
        for name, data, sha256 in prepared:
            try:
                formats.append(offers_service._check(name, data))  # noqa: SLF001
            except offers_service.OfferRefused as error:
                raise ProposalRefused(f"{name or 'Un archivo'}: {error}", "files",
                                      error.reason) from error
            if sha256 in seen:
                raise DuplicateFiles(f"El archivo «{name}» está repetido en lo que se subió.",
                                     "files")
            seen.add(sha256)
        message = _pending_elsewhere(procedure, [s for _, _, s in prepared])
        if message:
            raise DuplicateFiles(message, "files")
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    detail["files"] = [_file_detail(n, f, d, s) for (n, d, s), f in zip(prepared, formats,
                                                                       strict=True)]
    with transaction.atomic():
        draft = OfferDraft.objects.create(procedure=procedure, created_by=user)
        for (name, data, sha256), file_format in zip(prepared, formats, strict=True):
            OfferDraftFile.objects.create(
                draft=draft, file_name=name, file_format=file_format, file_size=len(data),
                file_sha256=sha256, content=data)
        job = jobs.enqueue(JobKind.PROPOSE_OFFER, procedure=procedure, requested_by=user,
                           target_id=draft.pk)
        draft.job = job
        draft.save(update_fields=["job"])
        audit.record(EventType.OFFER_PROPOSAL, outcome=Outcome.OK, channel=channel, user=user,
                     detail={**detail, "draft": draft.pk, "job": job.pk})
    return draft


# --- Pedido en segundo plano ---------------------------------------------------------------


def _read_sources(draft):
    """Lee los archivos del borrador. Devuelve `(fuentes, informe, avisos)`; un archivo que
    no se pudo leer queda en el informe y en los avisos, y no frena a los demás."""
    sources, report, warnings = [], [], []
    for item in draft.files.order_by("id"):
        data = bytes(item.content)
        entry = {"name": item.file_name, "sha256": item.file_sha256}
        try:
            if hashlib.sha256(data).hexdigest() != item.file_sha256:
                raise offers_service.OriginalChanged(
                    "El original guardado no coincide con la huella con que se subió.")
            pdf = reading_tools.to_pdf(data, item.file_format)
            reading, attempts = reading_tools.read_with_second_attempt(pdf)
            source = Source.from_reading(item.file_name, item.file_sha256, reading)
            sources.append(source)
            entry.update(pages=len(source.pages), second_attempts=len(attempts),
                         statuses=[page.status for page in reading.pages])
        except Exception as error:  # noqa: BLE001 - un archivo ilegible no frena a los demás
            entry["error"] = f"{type(error).__name__}: {error}"
            warnings.append(f"No se pudo leer «{item.file_name}»: se siguió con los demás.")
        report.append(entry)
    if not sources:
        raise ValueError("No se pudo leer ninguno de los archivos de la oferta.")
    return sources, report, warnings


def run_propose_offer(job):
    """Manejador del pedido `propose_offer`: lee los archivos del borrador `job.target_id` y
    guarda la propuesta. Ver el módulo. Si falla, deja el borrador «fallido» y el hecho
    fallido, y vuelve a lanzar el error para que la cola deje el pedido `failed`."""
    draft = _get_draft(job.target_id)
    if draft.state != ProposalState.LEYENDO:
        return
    base = {"draft": draft.pk, "job": job.pk, "procedure": draft.procedure_id,
            "action": "propose"}
    try:
        sources, report, read_warnings = _read_sources(draft)
        proposal = fields_module.propose(sources, reading=report)
        stored = proposal.as_json()
        stored["warnings"] = [*read_warnings, *stored["warnings"]]
        stored["corrections"] = []
        with transaction.atomic():
            draft = _get_draft(draft.pk, lock=True)
            draft.proposal = stored
            draft.state = ProposalState.PROPUESTO
            draft.save(update_fields=["proposal", "state"])
            audit.record(
                EventType.OFFER_PROPOSAL, outcome=Outcome.OK, channel=Channel.COMMAND,
                user=job.requested_by,
                detail={**base,
                        "files": [{"name": f.file_name, "sha256": f.file_sha256}
                                  for f in draft.files.order_by("id")],
                        "fields": {name: stored["fields"][name]["state"] for name in FIELDS},
                        "citations": {name: stored["fields"][name]["citation"]
                                      for name in FIELDS},
                        "reading": report, "rules_version": fields_module.RULES_VERSION,
                        "model": proposal.model_trace})
    except Exception as error:
        message = f"{type(error).__name__}: {error}"
        with transaction.atomic():
            OfferDraft.objects.filter(pk=draft.pk).update(
                state=ProposalState.FALLIDO, failure=message)
            audit.record(EventType.OFFER_PROPOSAL, outcome=Outcome.FAILED,
                         channel=Channel.COMMAND, user=job.requested_by,
                         detail={**base, "reason": message})
        raise


# --- Ver, corregir, aprobar, rechazar -------------------------------------------------------


def proposal_of(user, draft_id, *, channel=Channel.SCREEN):
    """El borrador con su propuesta. Lo ven el operador y el evaluador."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=VIEW_OPERATION,
                            channel=channel)
    return _get_draft(draft_id)


def _check_pending(draft):
    if draft.state != ProposalState.PROPUESTO:
        raise NotPending("La propuesta todavía no está lista o ya se resolvió.", None)


def correct(user, draft_id, field, value, reason, *, channel=Channel.SCREEN):
    """Corrige el nombre o el CUIT propuesto con el valor y el motivo. Ver el módulo."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=CORRECT_OPERATION,
                            channel=channel)
    detail = {"draft": draft_id, "action": "correct", "field": field}
    try:
        reason = (reason or "").strip()
        if not reason:
            raise ReasonRequired("Escriba el motivo de la corrección.", field)
        if field not in FIELDS:
            raise ProposalRefused("Ese dato no se puede corregir.", field, "unknown_field")
        with transaction.atomic():
            draft = _get_draft(draft_id, lock=True)
            _check_pending(draft)
            proposal = draft.proposal
            corrected = _clean_value(field, value)
            entry = {"field": field, "proposed": proposal["fields"][field]["proposed"],
                     "previous": _effective(proposal)[field], "corrected": corrected,
                     "reason": reason, "by": _username(user), "by_id": user.pk,
                     "at": timezone.now().isoformat(timespec="seconds")}
            proposal["corrections"] = [*proposal.get("corrections", []), entry]
            draft.proposal = proposal
            draft.save(update_fields=["proposal"])
            audit.record(EventType.OFFER_PROPOSAL, outcome=Outcome.OK, channel=channel,
                         user=user, detail={**detail, **entry})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft


def _origin_document(proposal, field, loaded):
    """El documento cargado de donde salió el dato (por la huella de su cita); el primero si
    el dato se corrigió o no tiene cita."""
    corrected = any(item["field"] == field for item in proposal.get("corrections", []))
    citation = proposal["fields"][field].get("citation")
    if citation and not corrected:
        for document in loaded:
            if document.file_sha256 == citation.get("file_sha256"):
                return document
    return loaded[0]


def approve(user, draft_id, *, channel=Channel.SCREEN):
    """Aprueba la propuesta y crea la oferta. Ver el módulo. Devuelve el borrador aprobado
    (con `.offer`)."""
    require_commission_role(user, CommissionRole.EVALUATOR, operation=APPROVE_OPERATION,
                            channel=channel)
    detail = {"draft": draft_id, "action": "approve"}
    try:
        with transaction.atomic():
            draft = _get_draft(draft_id, lock=True)
            _check_pending(draft)
            proposal = draft.proposal
            values = _effective(proposal)
            for name in FIELDS:
                if not values[name]:
                    raise IncompleteProposal(
                        f"Falta {FIELD_NAMES[name]}: no está determinado en los archivos. "
                        "Corríjalo con su motivo para poder aprobar.", name)
            procedure = draft.procedure
            if PortalOfferData.objects.filter(offer__procedure=procedure,
                                              cuit=values["cuit"]).exists():
                raise DuplicateBidder(
                    "Ese CUIT ya tiene una oferta en este procedimiento.", "cuit")
            message = _pending_elsewhere(
                procedure, list(draft.files.values_list("file_sha256", flat=True)),
                exclude_draft=draft.pk)
            if message:
                raise DuplicateFiles(message, "files")
            try:
                offer = offers_service.register_offer(user, procedure, bidder=values["bidder"],
                                                      channel=channel)
                loaded = [
                    offers_service.load_document(
                        user, offer, data=bytes(item.content), file_name=item.file_name,
                        channel=channel).document
                    for item in draft.files.order_by("id")]
            except offers_service.OfferRefused as error:
                if isinstance(error, offers_service.DuplicateBidder):
                    raise DuplicateBidder(str(error), error.field) from error
                raise ProposalRefused(str(error), error.field, error.reason) from error
            origin = _origin_document(proposal, "cuit", loaded)
            PortalOfferData.objects.create(offer=offer, cuit=values["cuit"], document=origin)
            draft.state = ProposalState.APROBADO
            draft.offer = offer
            draft.save(update_fields=["state", "offer"])
            audit.record(
                EventType.OFFER_PROPOSAL, outcome=Outcome.OK, channel=channel, user=user,
                detail={**detail, "offer": offer.pk, "procedure": procedure.pk,
                        "documents": [document.pk for document in loaded],
                        "cuit_document": origin.pk, "values": values,
                        "proposed": {name: proposal["fields"][name]["proposed"]
                                     for name in FIELDS},
                        "citations": {name: proposal["fields"][name]["citation"]
                                      for name in FIELDS},
                        "corrections": proposal.get("corrections", [])})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft


def reject(user, draft_id, reason, *, channel=Channel.SCREEN):
    """Descarta la propuesta de una oferta mal leída. Ver el módulo. Devuelve el borrador."""
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
            audit.record(EventType.OFFER_PROPOSAL, outcome=Outcome.OK, channel=channel,
                         user=user, detail={**detail, **entry,
                                            "files": [f.file_sha256 for f in draft.files.all()]})
    except ProposalRefused as error:
        _record_refusal(user, channel, error, detail)
        raise
    return draft
