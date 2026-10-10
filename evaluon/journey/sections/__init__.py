"""Las cinco secciones de la aplicación y el cálculo de su estado (plan 014, ADR-0047).

`sections_for(user, procedure)` reutiliza `stages_for` (las seis etapas de la 013, con su
comprobación de rol y el rechazo registrado) y arma las cinco secciones con sus cuentas.
"""

from dataclasses import dataclass

from evaluon.accounts import permissions
from evaluon.journey import memo
from evaluon.journey.sections import s1, s2, s3, s4, s5
from evaluon.journey.sections.base import Section, build_section
from evaluon.journey.stages import stages_for

SECTIONS = (s1, s2, s3, s4, s5)


@dataclass(frozen=True)
class Overview:
    """Las cinco secciones de un procedimiento y la suma de sus cuentas."""

    procedure: object
    journey: object
    sections: tuple
    pending: int
    suggestions: int

    def get(self, key):
        return next(s for s in self.sections if s.key == key)


def sections_for(user, procedure, *, channel=None):
    """Calcula las cinco secciones. El usuario de lectura (sin rol de la Comisión) las ve sin acciones; un anónimo recibe 403."""
    with memo.scope(), permissions.viewing(user):
        journey = stages_for(user, procedure, channel=channel, viewer=True)
        by_key = {stage.key: stage for stage in journey.stages}
        built = tuple(build_section(module, user, procedure, by_key) for module in SECTIONS)
    return Overview(procedure=procedure, journey=journey, sections=built,
                    pending=sum(s.pending for s in built),
                    suggestions=sum(s.suggestions for s in built))


__all__ = ["SECTIONS", "Overview", "Section", "sections_for"]
