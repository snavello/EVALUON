"""Decidir las sugerencias de condición: pasar a requisito o quitar, una por una o por
grupo (REQ-035, REQ-034, REQ-026; plan 003, "Qué hace la Comisión con una sugerencia";
ADR-0022; T-110).

- `accept_suggestion`: el evaluador pasa una fila de `sugerido` a `propuesto`.
  La fila `aceptar_sugerencia` del historial guarda quién, cuándo, el motivo de la duda y el
  respaldo normativo tal como estaban, y se registra el hecho `requirement_change`.
- `accept_suggestions_group`: lo mismo para las filas `sugerido` de un grupo (la clave de
  REQ-034), en una transacción, una fila de historial por requisito con `via_grupo`.
- `remove_suggestions_group`: quita las `sugerido` de un grupo con la función de quitar de
  `review`. Quitar una sola es `review.remove`, que admite el estado `sugerido`; restituirla
  la deja `propuesto`; confirmar una sugerencia se rechaza (`review.confirm`).

La norma no decide: nada de esto se hace solo. Solo en un borrador (`version_not_draft`).
"""

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.tenders.models import ChangeAction, Requirement, RequirementState
from evaluon.tenders.services import review
from evaluon.tenders.services.review import ReviewRefused, Reviewed

ACCEPT_OPERATION = "evaluon.tenders.services.suggestions.accept_suggestion"
ACCEPT_GROUP_OPERATION = "evaluon.tenders.services.suggestions.accept_suggestions_group"
REMOVE_GROUP_OPERATION = "evaluon.tenders.services.suggestions.remove_suggestions_group"


def _support_view(support):
    return {"unit": support.unit_id, "unit_label": support.unit_label,
            "char_start": support.char_start, "char_end": support.char_end,
            "text": support.text, "regime": support.regime,
            "corpus_version": support.corpus_version, "score": support.score}


def _accept_one(requirement, user, channel, done, via_group=None):
    """Pasa a requisito una sugerencia ya bloqueada. Es la misma función para la decisión
    individual y la de un grupo."""
    if requirement.state != RequirementState.SUGERIDO:
        raise ReviewRefused("Solo una sugerencia se pasa a requisito.",
                            "not_a_suggestion", "requirement")
    before = {
        "state": requirement.state,
        "doubt_reason": requirement.doubt_reason,
        "doubt": requirement.doubt,
        "norm_support": [_support_view(s) for s in
                         requirement.norm_supports.order_by("id")],
    }
    requirement.state = RequirementState.PROPUESTO
    requirement.save(update_fields=["state"])
    change, event = review._record(
        requirement, ChangeAction.ACEPTAR_SUGERENCIA, before,
        {"state": requirement.state}, user, channel,
        {"via_grupo": via_group} if via_group else None)
    done.requirements.append(requirement)
    done.changes.append(change)
    done.events.append(event)


def accept_suggestion(user, requirement_id, *, channel=Channel.SCREEN):
    """Pasa a requisito la sugerencia `requirement_id`. Solo el evaluador."""

    def work():
        requirement, _ = review._lock_requirement(requirement_id)
        done = Reviewed(requirements=[])
        _accept_one(requirement, user, channel, done)
        return done

    return review._run(user, CommissionRole.EVALUATOR, ACCEPT_OPERATION,
                       ChangeAction.ACEPTAR_SUGERENCIA, channel,
                       {"requirement": requirement_id}, work)


def accept_suggestions_group(user, version_id, group, *, channel=Channel.SCREEN):
    """Pasa a requisito las sugerencias del grupo `group` de la versión. Cada una deja su
    historial y su hecho, igual que la decisión individual, con `via_grupo` en el hecho.
    Una sola transacción."""

    def work():
        review._lock_draft(version_id)
        key, rows = review._group_rows(version_id, group, RequirementState.SUGERIDO)
        done = Reviewed(requirements=[])
        for requirement in rows:
            _accept_one(requirement, user, channel, done, via_group=key)
        return done

    return review._run(user, CommissionRole.EVALUATOR, ACCEPT_GROUP_OPERATION,
                       ChangeAction.ACEPTAR_SUGERENCIA, channel,
                       {"version": version_id, "via_grupo": group}, work)


def remove_suggestions_group(user, version_id, group, *, channel=Channel.SCREEN):
    """Quita las sugerencias del grupo `group`. Solo el evaluador."""
    return review.remove_group(user, version_id, group,
                               state=RequirementState.SUGERIDO, channel=channel)


def undecided(version):
    """Las sugerencias sin decidir de la versión, por número."""
    return list(Requirement.objects.filter(
        version=version, state=RequirementState.SUGERIDO).order_by("number"))
