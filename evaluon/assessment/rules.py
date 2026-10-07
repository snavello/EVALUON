"""Lo que se decide sin el modelo, y en qué orden (plan 004, "Qué se decide sin el modelo y en
qué orden"; ADR-0043; REQ-061 a REQ-064; T-166).

`evaluate.py` llama a `apply(pair, ctx)` **después** de unir los grupos y del contraste y
**antes** de guardar. La función aplica la primera regla de `RULES` que corresponde al par y deja
en `facts` cuál fue (`regla`) y con qué versión (`version_reglas`, `ASSESSMENT_RULES_VERSION`):
con eso se reconstruye por qué un par quedó como quedó (P6). Lo que no entra en ninguna regla
sigue el flujo de la 004 (cumple, no cumple, "no se encontró el documento", "no determinado" con
su motivo).

Orden (cada regla es una función `(pair, ctx) -> Combined | None` en su módulo):

1. externo (`externals.py`, REQ-063): siempre "falta la hoja de compliance";
2. técnico (`technical.py`, REQ-061): hechos y «pendiente del informe técnico» (T-167);
3. no se pudo leer (`unreadable.py`, REQ-064);
4. Portal (`portal_facts.py`, REQ-062): T-169.

Una regla nueva se suma en su lugar de la lista, nada más.
"""

from django.conf import settings

from evaluon.assessment import externals, portal_facts, technical, unreadable

RULES = (
    externals.rule,
    technical.rule,
    unreadable.rule,
    portal_facts.rule,
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
