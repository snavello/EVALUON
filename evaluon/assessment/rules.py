"""Lo que se decide sin el modelo, y en qué orden (plan 004, "Qué se decide sin el modelo y en
qué orden"; ADR-0043; REQ-061 a REQ-064; T-166).

`evaluate.py` llama a `apply(pair, ctx)` **después** de unir los grupos y del contraste y
**antes** de guardar. La función aplica la primera regla de `RULES` que corresponde al par y deja
en `facts` cuál fue (`regla`) y con qué versión (`version_reglas`, `ASSESSMENT_RULES_VERSION`):
con eso se reconstruye por qué un par quedó como quedó (P6). Lo que no entra en ninguna regla
sigue el flujo de la 004 (cumple, no cumple, "no se encontró el documento", "no determinado" con
su motivo).

Orden (cada regla es una función `(pair, ctx) -> Combined | None` en su módulo):

1. forma de garantía no elegida (`guarantee_form.py`, T-240): el requisito de una forma de
   garantía no aplica a la oferta que eligió otra («Requisito de la forma elegida», decisión del
   2026-10-10). Va antes que la de externos (T-257, H-C2-1): un requisito de la póliza que el
   catálogo marca externo (la Superintendencia) no aplica a la oferta con pagaré;
2. opción no usada (`options.py`, T-257): la condición de una opción que la oferta no usa no
   aplica (la matriz nombra la opción en `Requirement.proposed["opcion"]`);
3. presentación física (`presentation.py`, T-257, decisión del 2026-10-12): lo que hay que
   presentar en la Mesa de Entrada y no consta es «no cumple», con el aviso de que puede faltar
   cargarlo;
4. externo (`externals.py`, REQ-063): siempre "falta la hoja de compliance";
5. técnico (`technical.py`, REQ-061): hechos y «pendiente del informe técnico» (T-167);
6. no se pudo leer (`unreadable.py`, REQ-064);
7. Portal (`portal_facts.py`, REQ-062): T-169, con los criterios del 2026-10-12 (T-257);
8. cumple por ausencia (`absence.py`, T-257, decisión del 2026-10-12): el requisito negativo o
   supletorio que nada de la oferta contradice.

Una regla nueva se suma en su lugar de la lista, nada más.

Tres salidas (REQ-120; T-277, `reglas-v13`): lo que cualquiera de estas reglas deja es «cumple» con
fundamento, «no cumple» con cita (o decidido por la regla) o «no determinado» con la pregunta a la
Comisión o el documento que falta nombrado. Las reglas del Portal (`portal_facts.py`) que dejan
condiciones abiertas (`portal_cubre_parte`, `portal_falta_coincidencia`) escriben una pregunta que
nombra la condición y el dato del Portal que sí hay; el resto de los «no determinado» sin pregunta
la recibe de `combine.compose_question`. `combine.cell_problem` comprueba la forma de cada celda.
"""

from django.conf import settings

from evaluon.assessment import (
    absence,
    externals,
    guarantee_form,
    options,
    portal_facts,
    presentation,
    technical,
    unreadable,
)

RULES = (
    guarantee_form.rule,
    options.rule,
    presentation.rule,
    externals.rule,
    technical.rule,
    unreadable.rule,
    portal_facts.rule,
    absence.rule,
)


def apply(pair, ctx):
    """Aplica la primera regla que corresponde y deja el resultado en `pair.combined`.
    Devuelve el nombre de la regla (`facts["regla"]`) o `None` si ninguna rigió."""
    for rule in RULES:
        decided = rule(pair, ctx)
        if decided is None:
            continue
        decided.facts = {**decided.facts, "version_reglas": settings.ASSESSMENT_RULES_VERSION}
        pair.combined = decided
        return decided.facts["regla"]
    return None
