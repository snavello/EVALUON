"""Los grupos de la revisión por cláusula o tramo, para las pantallas (REQ-034, REQ-035;
plan 003, "Revisión por grupos"; T-105 y T-112).

Son las mismas reglas que aplican los servicios de `review` y `suggestions`: una fila es de
un grupo si lo son los tramos de sus citas propias. La pantalla cuenta con ellas lo que
tocaría cada botón, para que el número del botón sea el de las filas que se cambian.
"""

from evaluon.tenders.models import RequirementState
from evaluon.tenders.services import review


def clause_of(key):
    """La cláusula de primer nivel de la clave de un tramo: `sec-i/3.1.2` es de `sec-i/3`;
    las claves no tienen más niveles que la sección y la cláusula."""
    head = "/".join(key.split("/")[:2])
    for separator in (".", "#"):
        head = head.split(separator)[0]
    return head


def entries(version, state=RequirementState.PROPUESTO):
    """`[(requisito, [claves de sus citas propias])]` de las filas de la versión en el
    estado `state` (`propuesto` o `sugerido`)."""
    found = []
    for requirement in version.requirements.filter(state=state).order_by("number"):
        keys = [q.segment.key for q in requirement.quotes.select_related("segment")
                if q.scope in ("", "propia")]
        found.append((requirement, keys))
    return found


def proposed_entries(version):
    """Las filas `propuesto` con sus claves."""
    return entries(version, RequirementState.PROPUESTO)


def suggested_entries(version):
    """Las filas `sugerido` con sus claves."""
    return entries(version, RequirementState.SUGERIDO)


def in_group(keys, group):
    """Si una fila con esas claves es del grupo (la regla de `services.review`)."""
    return bool(keys) and all(review.in_group(key, group) for key in keys)
