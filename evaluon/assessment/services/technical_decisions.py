"""Las decisiones guardadas sobre filas técnicas por renglón (REQ-162; plan 019; T-365).

Solo lectura: no escribe en la base ni deja hecho de auditoría. Con una consulta trae las
`Decision` cuyo requisito es de clase técnica y filtra en Python con `sheets.is_item_row`, la misma
definición de fila técnica por renglón que usa el resto (no se copia). Incluye todas las acciones.
"""

from dataclasses import dataclass
from datetime import datetime

from evaluon.assessment.models import Decision
from evaluon.offers.services import sheets
from evaluon.tenders.models import RequirementClass


@dataclass(frozen=True)
class TechnicalDecision:
    procedure_number: str
    offer_number: int
    bidder: str
    requirement_number: int
    items: list
    action: str
    username: str
    at: datetime


def technical_row_decisions():
    """Las decisiones sobre filas técnicas por renglón, ordenadas por procedimiento, oferta,
    requisito y momento."""
    decisions = (
        Decision.objects
        .filter(result__requirement__category=RequirementClass.TECNICO)
        .select_related("result__offer__procedure", "result__requirement", "user")
        .order_by("result__offer__procedure__number", "result__offer__number",
                  "result__requirement__number", "at", "pk")
    )
    return [
        TechnicalDecision(
            procedure_number=decision.result.offer.procedure.number,
            offer_number=decision.result.offer.number,
            bidder=decision.result.offer.bidder,
            requirement_number=decision.result.requirement.number,
            items=decision.result.requirement.items,
            action=decision.action,
            username=decision.user.get_username(),
            at=decision.at,
        )
        for decision in decisions
        if sheets.is_item_row(decision.result.requirement)
    ]
