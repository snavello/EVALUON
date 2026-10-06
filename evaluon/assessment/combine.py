"""Unir los grupos y el contraste en un resultado (REQ-052, REQ-053, REQ-055, REQ-060; plan 004,
"Unir grupos y contrastar" y "Abstención"; ADR-0038; T-150).

Funciones puras, sin base ni modelo: reciben el resultado de cada grupo (con sus citas ya
ubicadas por el sistema) y devuelven el resultado del par. El modelo no decide "no se encontró el
documento": lo decide la regla de abajo sobre lo leído.

Reglas, en este orden:

1. Si algún grupo señala que el requisito se verifica fuera de la oferta: "no determinado",
   `externo` (el sistema no infiere hojas de compliance, P9; falta la hoja).
2. "Cumple" y "no cumple" en grupos distintos: "no determinado", `contradiccion`, con las
   citas de ambos.
3. Una conclusión (con cita ubicada) y "no consta" en los demás grupos: queda la conclusión. Si
   otro grupo duda ("no determinado"), no se concluye: "no determinado", `duda`.
4. Sin conclusión: "no determinado" si algún grupo duda (`sin_cita` si lo que falló fue la
   cita; si no, `duda`; con partes de la oferta sin leer, una `duda` pasa a
   `lectura_incompleta`: puede venir de ahí y se le pregunta a la Comisión).
5. Todos los grupos "no consta": "no se encontró el documento" si la exigencia es `documento`
   en todos, no hay páginas sin leer ni documentos sin lectura y se leyeron todos los grupos;
   "no determinado" `lectura_incompleta` si hay algo sin leer; `sin_dato` si la exigencia es
   una condición y se leyó todo.

Un "cumple" o "no cumple" va después al contraste (`apply_contrast`): si no contesta `si`, es
"no determinado" `sin_corroborar` con las mismas citas. Un "no determinado" que falta un dato
(`externo`, `sin_dato`, `lectura_incompleta`) siempre lleva una pregunta para la Comisión: la
del modelo o una fija del sistema.
"""

from dataclasses import dataclass, field, replace

from django.conf import settings

from evaluon.assessment.prompting import (
    CUMPLE,
    NO_CUMPLE,
    NO_DETERMINADO,
)

# Resultados del par (los de `assessment_result.outcome`) y motivos de la duda.
OUT_CUMPLE = "cumple"
OUT_NO_CUMPLE = "no_cumple"
OUT_SIN_DOCUMENTO = "sin_documento"
OUT_NO_DETERMINADO = "no_determinado"

DOUBT = "duda"
UNCORROBORATED = "sin_corroborar"
CONTRADICTION = "contradiccion"
INCOMPLETE = "lectura_incompleta"
EXTERNAL = "externo"
NO_CITATION = "sin_cita"
NO_DATA = "sin_dato"

# Dudas que siempre llevan una pregunta a la Comisión (REQ-055).
ALWAYS_ASK = (EXTERNAL, NO_DATA, INCOMPLETE)


@dataclass
class GroupResult:
    """Lo que dijo un grupo, con las citas ya controladas contra el texto canónico. Una
    conclusión cuyas citas no se ubicaron llega como `no_determinado` con `doubt=sin_cita`;
    una salida inválida después del reintento, como `no_determinado` con `doubt=duda`."""

    index: int
    result: str
    doubt: str = ""
    exigence: str = ""
    citations: list = field(default_factory=list)
    supports: list = field(default_factory=list)
    explanation: str = ""
    question: str = ""
    external: bool = False


@dataclass
class Combined:
    """El resultado de un par antes del contraste y de guardarlo."""

    outcome: str
    doubt: str = ""
    exigence: str = ""
    citations: list = field(default_factory=list)
    supports: list = field(default_factory=list)
    explanation: str = ""
    question: str = ""
    unread_warning: bool = False

    @property
    def needs_contrast(self):
        return self.outcome in (OUT_CUMPLE, OUT_NO_CUMPLE)


def _merge(groups, only=None):
    """Citas y fundamentos de los grupos (sin repetir), hasta el máximo de citas."""
    citations, supports, seen = [], [], set()
    for group in groups:
        if only is not None and group.result not in only:
            continue
        for cite in group.citations:
            if cite.span not in seen:
                seen.add(cite.span)
                citations.append(cite)
        for support in group.supports:
            if all(support is not other for other in supports):
                supports.append(support)
    return citations[:settings.ASSESSMENT_MAX_CITATIONS], supports


def _first(groups, name):
    return next((getattr(g, name) for g in groups if getattr(g, name)), "")


def unread_text(unread):
    """Las páginas sin leer para una pregunta: «documento, página n»."""
    return "; ".join(f"{u['title']}, página {u['page']}" for u in unread)


def fixed_question(doubt, unread=(), explanation=""):
    """La pregunta del sistema cuando el modelo no formuló una (REQ-055)."""
    if doubt == EXTERNAL:
        return ("Este requisito se verifica con una consulta fuera de la oferta. ¿Se cuenta "
                "con la hoja de compliance de la oferta para este requisito?")
    if doubt == INCOMPLETE:
        where = unread_text(unread)
        suffix = f" ({where})" if where else ""
        return ("Hay partes de la oferta que no se pudieron leer" + suffix + ". ¿Lo que "
                "exige este requisito está ahí? Se necesita revisar el original.")
    if doubt == NO_DATA:
        detail = f" {explanation}" if explanation else ""
        return ("Para este requisito falta un dato que no consta en la oferta ni en la "
                "normativa." + detail + " ¿Qué determina la Comisión?")
    if doubt == UNCORROBORATED:
        return ("El sistema llegó a una conclusión con el texto de la oferta, pero no pudo "
                "corroborarla. ¿La Comisión la confirma, la corrige o la rechaza?")
    return ""


def combine(groups, *, unread, without_reading=(), unread_groups=0):
    """El resultado del par a partir de lo que dijo cada grupo (`GroupResult`). `unread` son
    las páginas sin leer de la oferta (`{"title", "page"}`), `without_reading` los
    documentos sin lectura y `unread_groups` cuántos grupos pasaron del tope y no se leyeron."""
    warning = bool(unread or without_reading or unread_groups)
    complete = not warning
    question = _first(groups, "question")

    def done(outcome, doubt="", only=None, exigence=None, explanation=None, ask=True,
             pool=None):
        if doubt == DOUBT and warning:
            # Con partes de la oferta sin leer, una duda puede venir de ahí: se dice así y se
            # pregunta a la Comisión (no se supone que la respuesta no estaba).
            doubt = INCOMPLETE
        citations, supports = _merge(pool if pool is not None else groups, only)
        text = explanation if explanation is not None else _first(
            pool if pool is not None else groups, "explanation")
        # Una conclusión no lleva pregunta: solo la lleva un "no determinado".
        asked = question if outcome == OUT_NO_DETERMINADO else ""
        if not asked and ask and doubt in ALWAYS_ASK:
            asked = fixed_question(doubt, unread, text)
        return Combined(
            outcome=outcome, doubt=doubt,
            exigence=exigence if exigence is not None else _first(groups, "exigence"),
            citations=citations, supports=supports, explanation=text, question=asked,
            unread_warning=warning)

    if not groups:
        return done(OUT_NO_DETERMINADO, INCOMPLETE, explanation=(
            "La oferta no tiene documentos leídos."), exigence="")
    if any(g.external for g in groups):
        flagged = [g for g in groups if g.external]
        return done(OUT_NO_DETERMINADO, EXTERNAL, pool=flagged + [
            g for g in groups if not g.external])
    conclusions = [g for g in groups if g.result in (CUMPLE, NO_CUMPLE)]
    kinds = {g.result for g in conclusions}
    if len(kinds) == 2:
        return done(OUT_NO_DETERMINADO, CONTRADICTION, explanation=(
            "Distintos documentos de la oferta dicen cosas opuestas sobre este requisito."))
    doubtful = [g for g in groups if g.result == NO_DETERMINADO]
    if kinds:
        if doubtful:
            return done(OUT_NO_DETERMINADO, DOUBT, only=(CUMPLE, NO_CUMPLE),
                        exigence=conclusions[0].exigence)
        outcome = OUT_CUMPLE if kinds == {CUMPLE} else OUT_NO_CUMPLE
        return done(outcome, only=(CUMPLE, NO_CUMPLE), exigence=conclusions[0].exigence,
                    pool=conclusions)
    if doubtful:
        failed_citation = all(g.doubt == NO_CITATION for g in doubtful)
        return done(OUT_NO_DETERMINADO, NO_CITATION if failed_citation else DOUBT)
    # Todos los grupos dijeron "no consta".
    exigence = "documento" if all(g.exigence == "documento" for g in groups) else "condicion"
    if complete and exigence == "documento":
        return done(OUT_SIN_DOCUMENTO, exigence=exigence, ask=False, explanation=(
            "Se leyeron todos los documentos de la oferta y ninguno es el documento que el "
            "pliego exige."))
    if not complete:
        return done(OUT_NO_DETERMINADO, INCOMPLETE, exigence=exigence, explanation=(
            "No se puede afirmar que el documento falta: hay partes de la oferta que no se "
            "pudieron leer."))
    return done(OUT_NO_DETERMINADO, NO_DATA, exigence=exigence)


def apply_contrast(combined, answer, reason=""):
    """El resultado después del contraste. Si el contraste no contesta `si`, el "cumple" o el
    "no cumple" pasa a "no determinado" `sin_corroborar`, con las mismas citas."""
    if not combined.needs_contrast or answer == "si":
        return combined
    note = f"El contraste no corroboró la conclusión ({answer}): {reason}".rstrip(": ")
    explanation = f"{combined.explanation} {note}".strip()
    return replace(combined, outcome=OUT_NO_DETERMINADO, doubt=UNCORROBORATED,
                   explanation=explanation,
                   question=fixed_question(UNCORROBORATED))
