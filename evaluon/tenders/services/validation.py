"""Validar la matriz, descartar un borrador y abrir versiones nuevas (REQ-027; plan 003,
"Revisión, validación y versiones" y "Roles"; principio P3; T-082).

- `validate`: solo el evaluador. Condiciones (decisión del responsable): ningún pendiente sin
  resolver y cada requisito no quitado con su consecuencia elegida por un evaluador. Los
  requisitos que seguían propuestos quedan confirmados por la validación, cada uno con su
  fila de historial y su hecho `requirement_change`; esas actualizaciones van antes de pasar
  la versión a `validated`, en la misma transacción, porque después la base rechaza todo
  cambio sobre ella. Deja el hecho `matrix_validation`, con las cuentas de filas
  descartadas por el sistema y de devueltas (REQ-033).
- `discard`: solo el evaluador. El borrador queda `discarded`, visible y fijo, y deja el hecho
  `matrix_version`.
- `open_new_version`: el operador o el evaluador. Sobre la última versión validada abre un
  borrador con el número siguiente que copia requisitos (también los quitados, con su
  estado), citas, fuentes, la consecuencia elegida de cada uno y los pendientes resueltos;
  cada requisito copiado apunta al suyo con `previous`. La versión de origen no cambia. Hereda
  su nivel (REQ-030). Deja el hecho `matrix_version`.

Como en la revisión, el rol se comprueba antes de toda transacción; lo demás se valida antes
de escribir y un pedido rechazado deja solo un hecho en resultado `rejected` con su motivo.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    ChangeAction,
    Consequence,
    JobKind,
    JobStatus,
    MatrixVersion,
    NormSupport,
    PendingItem,
    Procedure,
    Requirement,
    RequirementQuote,
    RequirementSource,
    RequirementState,
    VersionStatus,
)
from evaluon.tenders.services import discarded, review, suggestions

VALIDATE_OPERATION = "evaluon.tenders.services.validation.validate"
DISCARD_OPERATION = "evaluon.tenders.services.validation.discard"
OPEN_OPERATION = "evaluon.tenders.services.validation.open_new_version"


class ValidationRefused(review.ReviewRefused):
    """No se validó, descartó ni abrió. `reason` queda en el registro; el mensaje es para
    la persona."""


def _numbers(requirements):
    return ", ".join(str(r.number) for r in requirements)


def _groups(requirements):
    """Las claves de los tramos citados por las filas, sin repetir y en orden."""
    keys = {q.segment.key for r in requirements
            for q in r.quotes.select_related("segment") if q.scope in ("", "propia")}
    return ", ".join(sorted(keys))


def _refuse_record(error, event_type, user, channel, detail):
    audit.record(event_type, outcome=Outcome.REJECTED, channel=channel, user=user,
                 detail={**detail, "reason": error.reason, "message": str(error)})


def _run(user, role, operation, event_type, channel, detail, work):
    require_commission_role(user, role, operation=operation, channel=channel)
    try:
        with transaction.atomic():
            return work()
    except ValidationRefused as error:
        _refuse_record(error, event_type, user, channel, detail)
        raise
    except review.ReviewRefused as error:
        refused = ValidationRefused(str(error), error.reason, error.field)
        _refuse_record(refused, event_type, user, channel, detail)
        raise refused from error


# --- Validar -------------------------------------------------------------------------------------


def validate(user, version_id, *, channel=Channel.SCREEN):
    """El evaluador valida el borrador `version_id`. Devuelve la versión validada."""
    detail = {"version": version_id}

    def work():
        version = review._lock_draft(version_id)
        requirements = list(version.requirements.select_for_update().order_by("number"))
        active = [r for r in requirements if r.state != RequirementState.QUITADO]
        if not active:
            raise ValidationRefused(
                "No se puede validar: la matriz no tiene ningún requisito vigente.",
                "empty_matrix", "requirements")

        open_pending = version.pending_items.filter(resolved_at__isnull=True).count()
        if open_pending:
            raise ValidationRefused(
                f"No se puede validar: quedan {open_pending} tramos pendientes de revisión "
                "sin resolver.", "pending_unresolved", "pending")
        undecided = suggestions.undecided(version)
        if undecided:
            raise ValidationRefused(
                f"No se puede validar: quedan {len(undecided)} sugerencias sin decidir "
                f"(en {_groups(undecided)}). Pase cada una a requisito o quítela.",
                "suggestions_undecided", "suggestions")
        chosen = set(Consequence.objects.filter(
            requirement__in=active, chosen=True).values_list("requirement_id", flat=True))
        missing = [r for r in active if r.pk not in chosen]
        if missing:
            raise ValidationRefused(
                "No se puede validar: falta elegir la consecuencia de los requisitos "
                f"{_numbers(missing)}.", "consequence_missing", "consequence")

        confirmed = []
        for requirement in active:
            if requirement.state != RequirementState.PROPUESTO:
                continue
            requirement.state = RequirementState.CONFIRMADO
            requirement.save(update_fields=["state"])
            review._record(requirement, ChangeAction.CONFIRMAR,
                           {"state": RequirementState.PROPUESTO},
                           {"state": RequirementState.CONFIRMADO}, user, channel,
                           {"by_validation": True})
            confirmed.append(requirement.pk)

        by_state, by_class = {}, {}
        for requirement in requirements:
            by_state[requirement.state] = by_state.get(requirement.state, 0) + 1
            by_class[requirement.category] = by_class.get(requirement.category, 0) + 1
        discarded_total, restored = discarded.counts(version)
        accepted = sum(1 for r in requirements if r.changes.filter(
            action=ChangeAction.ACEPTAR_SUGERENCIA).exists())
        removed = sum(1 for r in requirements
                      if r.state == RequirementState.QUITADO and r.doubt_reason)
        version.status = VersionStatus.VALIDATED
        version.validated_at = timezone.now()
        version.validated_by = user
        version.save(update_fields=["status", "validated_at", "validated_by"])
        audit.record(
            EventType.MATRIX_VALIDATION, outcome=Outcome.OK, channel=channel, user=user,
            detail={"procedure": version.procedure_id, "version": version.pk,
                    "version_number": version.number, "by_state": by_state,
                    "by_class": by_class, "confirmed_by_validation": confirmed,
                    "discarded": discarded_total, "restored": restored,
                    "suggestions_accepted": accepted,
                    "suggestions_removed": removed})
        return version

    return _run(user, CommissionRole.EVALUATOR, VALIDATE_OPERATION,
                EventType.MATRIX_VALIDATION, channel, detail, work)


# --- Descartar un borrador -----------------------------------------------------------------------


def discard(user, version_id, *, channel=Channel.SCREEN):
    """El evaluador descarta el borrador `version_id`: queda visible y fijo."""
    detail = {"version": version_id, "action": "discarded"}

    def work():
        version = review._lock_draft(version_id)
        version.status = VersionStatus.DISCARDED
        version.discarded_at = timezone.now()
        version.discarded_by = user
        version.save(update_fields=["status", "discarded_at", "discarded_by"])
        audit.record(
            EventType.MATRIX_VERSION, outcome=Outcome.OK, channel=channel, user=user,
            detail={"procedure": version.procedure_id, "version": version.pk,
                    "version_number": version.number, "action": "discarded"})
        return version

    return _run(user, CommissionRole.EVALUATOR, DISCARD_OPERATION,
                EventType.MATRIX_VERSION, channel, detail, work)


# --- Versión nueva -------------------------------------------------------------------------------


def latest_validated(procedure):
    return procedure.matrix_versions.filter(
        status=VersionStatus.VALIDATED).order_by("-number").first()


def _copy(source, new):
    """Copia a `new` las filas de `source`. Devuelve cuántas de cada tabla."""
    quote_map, count = {}, {"requirements": 0, "quotes": 0, "sources": 0,
                            "consequences": 0, "pending": 0,
                            "norm_supports": 0}
    for old in source.requirements.order_by("number"):
        copy = Requirement.objects.create(
            version=new, number=old.number, category=old.category, items=old.items,
            origin=old.origin, state=old.state, proposed=old.proposed, previous=old,
            step=old.step, passes=old.passes, restored_from=old.restored_from,
            doubt_reason=old.doubt_reason, doubt=old.doubt)
        count["requirements"] += 1
        for quote in old.quotes.order_by("order"):
            quote_map[quote.pk] = RequirementQuote.objects.create(
                requirement=copy, order=quote.order, segment=quote.segment,
                char_start=quote.char_start, char_end=quote.char_end, text=quote.text,
                scope=quote.scope, quote_flag=quote.quote_flag)
            count["quotes"] += 1
        for support in old.norm_supports.order_by("id"):
            NormSupport.objects.create(
                requirement=copy, unit=support.unit, unit_label=support.unit_label,
                char_start=support.char_start, char_end=support.char_end,
                text=support.text, score=support.score, regime=support.regime,
                corpus_version=support.corpus_version, step=support.step)
            count["norm_supports"] += 1
        for src in old.sources.order_by("id"):
            RequirementSource.objects.create(
                requirement=copy, quote=quote_map.get(src.quote_id), effect=src.effect,
                segment=src.segment, char_start=src.char_start, char_end=src.char_end,
                text=src.text, issued_on=src.issued_on, step=src.step,
                original_segment=src.original_segment,
                original_char_start=src.original_char_start,
                original_char_end=src.original_char_end)
            count["sources"] += 1
        for cons in old.consequences.filter(chosen=True):
            Consequence.objects.create(
                requirement=copy, consequence_type=cons.consequence_type,
                grounds=cons.grounds, origin=cons.origin, step=cons.step, chosen=True,
                chosen_by=cons.chosen_by, chosen_at=cons.chosen_at,
                chosen_note=cons.chosen_note)
            count["consequences"] += 1
    for item in source.pending_items.filter(resolved_at__isnull=False):
        PendingItem.objects.create(
            version=new, segment=item.segment, reason=item.reason,
            resolved_by=item.resolved_by, resolved_at=item.resolved_at,
            resolution=item.resolution)
        count["pending"] += 1
    return count


def open_new_version(user, procedure_id, *, channel=Channel.SCREEN):
    """Abre un borrador sobre la última versión validada del procedimiento. Devuelve la
    versión nueva."""
    detail = {"procedure": procedure_id, "action": "opened"}

    def work():
        try:
            procedure = Procedure.objects.select_for_update().get(pk=procedure_id)
        except Procedure.DoesNotExist:
            raise ValidationRefused("No hay un procedimiento con ese número.",
                                    "procedure_not_found", "procedure")
        source = latest_validated(procedure)
        if source is None:
            raise ValidationRefused(
                "El procedimiento no tiene una matriz validada: no hay sobre qué abrir "
                "una versión nueva.", "no_validated_version")
        if procedure.matrix_versions.filter(status=VersionStatus.DRAFT).exists():
            raise ValidationRefused(
                "Ya hay un borrador abierto: termínelo o descártelo antes de abrir otra "
                "versión.", "draft_open")
        if procedure.jobs.filter(
            kind=JobKind.PROPOSE_MATRIX, status__in=(JobStatus.QUEUED, JobStatus.RUNNING)
        ).exists():
            raise ValidationRefused(
                "Ya hay una propuesta de la matriz en espera o en curso para este "
                "procedimiento: espere a que termine.", "request_in_progress")
        number = procedure.matrix_versions.aggregate(last=Max("number"))["last"] + 1
        new = MatrixVersion.objects.create(
            procedure=procedure, number=number, status=VersionStatus.DRAFT,
            level=source.level, process=source.process, run=None, based_on=source,
            created_by=user)
        copied = _copy(source, new)
        audit.record(
            EventType.MATRIX_VERSION, outcome=Outcome.OK, channel=channel, user=user,
            detail={"procedure": procedure.pk, "version": new.pk,
                    "version_number": new.number, "based_on": source.pk,
                    "based_on_number": source.number, "action": "opened",
                    "copied": copied})
        return new

    return _run(user, CommissionRole.OPERATOR, OPEN_OPERATION, EventType.MATRIX_VERSION,
                channel, detail, work)
