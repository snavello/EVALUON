"""Unir los grupos y el contraste en un resultado (REQ-052, REQ-053, REQ-055, REQ-060; plan 004,
"Unir grupos y contrastar" y "Abstención"; ADR-0038; T-150).

Funciones puras, sin base ni modelo: reciben el resultado de cada grupo (con sus citas ya
ubicadas por el sistema) y devuelven el resultado del par. El modelo no decide "no se encontró el
documento": lo decide la regla de abajo sobre lo leído.

Reglas, en este orden:

1. Si algún grupo señala que el requisito se verifica fuera de la oferta: "no determinado",
   `externo` (falta la hoja de compliance; el sistema no la infiere, P9). Gana sobre todas las
   demás, sin pregunta a la Comisión: la acción es subir la hoja (REQ-063, T-166).
2. "Cumple" y "no cumple" en grupos distintos: "no determinado", `contradiccion`, con las
   citas de ambos.
3. Una conclusión (con cita ubicada) y "no consta" en los demás grupos: queda la conclusión. Si
   otro grupo duda ("no determinado"), no se concluye: "no determinado", `duda`.
4. Sin conclusión: "no determinado" si algún grupo duda (`sin_cita` si lo que falló fue la
   cita; si no, `duda`; con partes de la oferta sin leer, una `duda` pasa a
   `lectura_incompleta`: puede venir de ahí y se le pregunta a la Comisión).
   Un "no cumple" técnico sin cláusula del pliego que lo contradiga llega acá como duda
   `sin_dato` (T-156, `clause_supported`).
5. Todos los grupos "no consta": "no se encontró el documento" si la exigencia es `documento`
   en todos, no hay páginas sin leer ni documentos sin lectura y se leyeron todos los grupos;
   "no determinado" `lectura_incompleta` si hay algo sin leer; `sin_dato` si la exigencia es
   una condición y se leyó todo.

Un "cumple" o "no cumple" va después al contraste (`apply_contrast`): si no contesta `si`, es
"no determinado" `sin_corroborar` con las mismas citas. Un "no determinado" que falta un dato
(`sin_dato`, `lectura_incompleta`) siempre lleva una pregunta para la Comisión. `externo` no lleva ninguna. Lo que se decide por regla (externos del
catálogo y páginas ilegibles) lo aplica `rules.py` después de esta unión (T-166).

Preguntas (REQ-105; T-235): este módulo no escribe el texto de ninguna. Deja en `Combined.question`
la pregunta que escribió el modelo (o la de una regla) y en `Combined.ask` si el caso exige una;
`compose_question` arma la pregunta final, con el requisito, la conclusión y el texto de la oferta
(documento y página), dirigida a la Comisión. La pregunta del modelo se acepta solo si no se dirige
al oferente; si no, la arma el código. No hay preguntas de texto fijo genérico.
"""

import re
import unicodedata
from dataclasses import dataclass, field, replace

from django.conf import settings

from evaluon.assessment.prompting import (
    CUMPLE,
    NO_CUMPLE,
    NO_DETERMINADO,
)
from evaluon.tenders.proposal import quotes

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
UNREADABLE = "no_se_pudo_leer"

# Dudas que siempre llevan una pregunta a la Comisión (REQ-055). `externo` ya no: falta la hoja
# de compliance y la acción es subirla (REQ-063).
ALWAYS_ASK = (NO_DATA, INCOMPLETE)


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
    # El documento que el modelo señaló como ilegible y el informe de lectura avala
    # (`unreadable.resolve`), o `None` (REQ-064).
    unreadable: dict | None = None
    # Datos del Portal que el modelo citó con su alias `P…` (T-235): `Datum.citation()`.
    portal: list = field(default_factory=list)


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
    # Lo verificado por regla y la regla que decidió (`rules.py`; P6).
    facts: dict = field(default_factory=dict)
    # Opinión informativa de una fila técnica (REQ-061): nunca es el resultado.
    opinion: str = ""
    # Datos del Portal que se citan (`portal_facts.py`, `technical.py`): cada uno es
    # `{"item": id del ítem, "kind": clase, "text": texto, "label": rótulo}`.
    portal: list = field(default_factory=list)
    # El caso exige una pregunta a la Comisión aunque el modelo no la haya escrito (T-235).
    ask: bool = False
    # Lo que el sistema había concluido antes de que el contraste no lo corroborara.
    proposed: str = ""

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


def _merge_portal(groups, only=None):
    """Los datos del Portal que citaron los grupos, sin repetir."""
    cites, seen = [], set()
    for group in groups:
        if only is not None and group.result not in only:
            continue
        for cite in group.portal:
            key = (cite["item"], cite["kind"], cite["text"])
            if key not in seen:
                seen.add(key)
                cites.append(cite)
    return cites


def _first(groups, name):
    return next((getattr(g, name) for g in groups if getattr(g, name)), "")


def unread_text(unread):
    """Las páginas sin leer para una pregunta: «documento, página n»."""
    return "; ".join(f"{u['title']}, página {u['page']}" for u in unread)


# Dudas que llevan pregunta aunque el modelo no la escriba (REQ-055): las dos de siempre y la
# conclusión que el contraste no corroboró.
ASKED_DOUBTS = (NO_DATA, INCOMPLETE, UNCORROBORATED)

QUESTION_CLIP = 280


def _plain(text):
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


_ROLE = r"(?:oferentes?|proveedor(?:es)?|empresas?|firmas?|licitantes?|participantes?)"
_MODAL = (r"(?:podr\w+|pued\w+|deb\w+|aclare\w*|informe\w*|presente\w*|confirme\w*|indique\w*"
          r"|adjunte\w*|envie\w*|aporte\w*|explique\w*|detalle\w*|especifique\w*|complete\w*"
          r"|subsane\w*)")
# Una pregunta dirigida al oferente: le pide algo («solicitamos al oferente…»), le habla de usted o
# le da una orden o un permiso («¿Podría el oferente aclarar…?», «el oferente deberá informar…»).
_TO_OFFEROR = re.compile(
    rf"\b(?:solicit\w*|pid\w*|requer\w*|ruego|rogamos|invit\w*|instamos)\b[^.?!]{{0,40}}?\b{_ROLE}"
    rf"|\b{_MODAL}\s+(?:el|la|los|las)\s+{_ROLE}\b"
    rf"|\b(?:el|la|los|las)\s+{_ROLE}\s+{_MODAL}\b"
    r"|\busted(?:es)?\b|\bpor favor\b|\bsirva(?:se|n)?\b")


def addresses_offeror(text):
    """Si la pregunta se dirige al oferente en lugar de a la Comisión (REQ-105)."""
    return bool(_TO_OFFEROR.search(_plain(text)))


def _clip(text, size):
    text = " ".join((text or "").split())
    if len(text) <= size:
        return text
    return text[:size].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _sentence(text):
    return text.rstrip(" .") + "."


def _conclusion(combined):
    from evaluon.assessment.models import Doubt

    if combined.doubt == UNCORROBORATED and combined.proposed:
        word = "cumple" if combined.proposed == OUT_CUMPLE else "no cumple"
        base = f"el sistema propuso «{word}», pero el contraste no lo corroboró"
    else:
        label = Doubt(combined.doubt).label.lower() if combined.doubt else "sin motivo"
        base = f"no determinado ({label})"
    detail = _clip(combined.explanation, 240)
    return _sentence(f"{base}: {detail}" if detail else base)


def _evidence(combined, documents, unread):
    if combined.citations:
        first = combined.citations[0]
        more = len(combined.citations) - 1
        text = (f"«{_clip(first.text, QUESTION_CLIP)}» ({first.document.title}, página "
                f"{first.page})" + (f" y {more} cita{'s' if more > 1 else ''} más" if more else ""))
        return _sentence(text)
    if combined.portal:
        return _sentence("dato del Portal: «" + _clip(combined.portal[0]["text"], QUESTION_CLIP)
                         + "»")
    where = f" en los documentos leídos ({', '.join(documents)})" if documents else ""
    parts = f"no hay un texto de la oferta que responda al requisito{where}"
    if unread:
        parts += f"; partes sin leer: {unread_text(unread)}"
    return _sentence(parts)


def _default_ask(combined):
    if combined.doubt == UNCORROBORATED:
        word = {OUT_CUMPLE: "cumple", OUT_NO_CUMPLE: "no cumple"}.get(combined.proposed)
        what = f"la conclusión «{word}»" if word else "la conclusión del sistema"
        return f"¿La Comisión confirma, corrige o rechaza {what}?"
    if combined.doubt == INCOMPLETE:
        return ("¿Lo que exige este requisito consta en las partes sin leer? La Comisión debe "
                "revisar el original.")
    if combined.doubt == NO_DATA:
        return "¿Qué determina la Comisión sobre este requisito, con el dato que falta?"
    return "¿Cómo resuelve la Comisión este requisito con el texto citado?"


def compose_question(number, requirement, combined, *, documents=(), unread=()):
    """La pregunta final a la Comisión por un par "no determinado" (REQ-105; T-235), o `""` si no
    corresponde. Lleva el requisito (cita del pliego), la conclusión del sistema y el texto de la
    oferta (documento y página); cierra con la pregunta del modelo si no se dirige al oferente, y
    si no, con una que arma el código. `documents`: títulos de los documentos leídos; `unread`:
    las partes sin leer (`{"title", "page"}`)."""
    if combined.outcome != OUT_NO_DETERMINADO or combined.doubt == EXTERNAL:
        return ""
    asked = " ".join((combined.question or "").split())
    if not asked and not (combined.ask and combined.doubt in ASKED_DOUBTS):
        return ""
    closing = asked if asked and not addresses_offeror(asked) else _default_ask(combined)
    return "\n".join([
        _sentence(f"Requisito {number}: «{_clip(requirement, QUESTION_CLIP)}»"),
        f"Conclusión del sistema: {_conclusion(combined)}",
        f"Texto de la oferta: {_evidence(combined, documents, unread)}",
        closing])


MIN_CLAUSE_WORDS = 2   # palabras de tres letras o más que debe tener una cláusula citada
NO_CLAUSE_NOTE = ("El sistema no encontró una cláusula del pliego que contradiga lo ofrecido: "
                  "una descripción sin el dato que la cláusula pide no alcanza para decir que "
                  "no cumple.")


def clause_supported(clause, requirement_text):
    """Regla de cierre de un "no cumple" técnico (T-156): vale solo si el modelo citó una
    cláusula que está, letra por letra, en el texto del requisito del pliego (con los espacios
    colapsados, como toda cita). Sin ella el "no cumple" pasa a "no determinado" `sin_dato`."""
    text = " ".join((clause or "").strip(" «»\"").split())
    # Una cláusula tiene contenido: un tramo trivial ("de", "3.1", "Renglón 3") no alcanza.
    words = re.findall(r"[^\W\d_]{3,}", text)
    if len(words) < MIN_CLAUSE_WORDS:
        return False
    return quotes.locate(requirement_text or "", text) is not None


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
        # Falta la hoja de compliance: no hay nada que preguntar, hay que subirla (REQ-063).
        asking = outcome == OUT_NO_DETERMINADO and doubt != EXTERNAL
        asked = question if asking else ""
        return Combined(
            outcome=outcome, doubt=doubt,
            exigence=exigence if exigence is not None else _first(groups, "exigence"),
            citations=citations, supports=supports, explanation=text, question=asked,
            unread_warning=warning, ask=asking and ask and doubt in ALWAYS_ASK,
            portal=_merge_portal(pool if pool is not None else groups, only))

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
        if any(g.doubt == NO_DATA for g in doubtful):
            # Un "no cumple" técnico sin cláusula que lo contradiga (`clause_supported`).
            return done(OUT_NO_DETERMINADO, NO_DATA,
                        pool=[g for g in doubtful if g.doubt == NO_DATA])
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
                   explanation=explanation, question="", ask=True, proposed=combined.outcome)


# Un motivo que habla de la calidad de la lectura no es una contradicción de la oferta (T-164).
READING_QUALITY = re.compile(
    r"transcripci|escane|\bocr\b|ilegible|reconocimiento|mala lectura|lectura (?:defectuosa|"
    r"deficiente)|cortad[oa]|borros|error(?:es)? de lectura", re.IGNORECASE)


def apply_clauses(combined, rows, question, requirement_text):
    """Contraste por cláusula de un "cumple" técnico (T-158, T-164). `rows`: `(cláusula,
    estado, motivo)` o `(cláusula, estado, motivo, cita)`, con `cita` la `Located` que el
    sistema ubicó en el texto canónico de la oferta. "No cumple" exige las dos cosas: la
    cláusula copiada letra por letra del requisito y una cita de la oferta ubicada que la
    contradiga; con un motivo que habla de la calidad de la lectura (escaneo, OCR) o sin esa
    cita, la cláusula cuenta como no confirmada. Si no, con alguna cláusula no confirmada
    (no aparece, ilegible o contradicha sin respaldo): "no determinado" `sin_dato` con
    pregunta. Solo si todas coinciden queda el "cumple" (y sigue al contraste común)."""
    if combined.outcome != OUT_CUMPLE:
        return combined
    rows = [(*row, None) if len(row) == 3 else row for row in rows]
    contradicted = [(c, why, located) for c, state, why, located in rows
                    if state == "contradice" and located is not None
                    and clause_supported(c, requirement_text)
                    and not READING_QUALITY.search(why or "")]
    if contradicted:
        clause, why, located = contradicted[0]
        note = f"Cláusula del pliego contradicha: «{clause}» {why}".strip()
        spans = {located.span}
        citations = [located] + [c for c in combined.citations if c.span not in spans]
        return replace(combined, outcome=OUT_NO_CUMPLE, doubt="", question="",
                       citations=citations[:settings.ASSESSMENT_MAX_CITATIONS],
                       explanation=f"{note} (revisión por cláusula)")
    missing = [(c, why) for c, state, why, _ in rows if state != "coincide"]
    if missing:
        names = "; ".join(f"«{c}»" for c, _ in missing)
        note = f"El sistema no pudo confirmar estas cláusulas con la oferta: {names}."
        explanation = f"{combined.explanation} {note}".strip()
        return replace(combined, outcome=OUT_NO_DETERMINADO, doubt=NO_DATA,
                       explanation=explanation, question=question, ask=True)
    return combined
