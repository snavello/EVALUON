"""Las seis etapas del recorrido, en orden, y el cálculo del conjunto (plan 013)."""

from dataclasses import dataclass

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.journey.stages import (
    base,
    evaluacion,
    matriz,
    matriz_evaluacion,
    ofertas,
    pliego,
    portal,
)

OPERATION = "evaluon.journey.stages.stages_for"

STAGES = (portal, pliego, matriz, ofertas, evaluacion, matriz_evaluacion)


@dataclass(frozen=True)
class Journey:
    """Las seis etapas de un procedimiento, la etapa actual y la suma de lo que espera a la
    Comisión. `current` es la primera etapa que no está lista, salvo la del Portal cuando es
    opcional y está pendiente; `None` si todas están listas."""

    procedure: object
    stages: tuple
    current: object
    pending: int
    suggestions: int


def stages_for(user, procedure, *, channel=None):
    """Calcula las seis etapas. Lanza `RoleRejected` sin rol de la Comisión (REQ-069)."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=channel)
    stages = tuple(module.compute(user, procedure) for module in STAGES)
    current = next((s for s in stages
                    if s.state != base.LISTA
                    and not (s.optional and s.state == base.PENDIENTE)), None)
    return Journey(procedure=procedure, stages=stages, current=current,
                   pending=sum(s.pending for s in stages),
                   suggestions=sum(s.suggestions for s in stages))
