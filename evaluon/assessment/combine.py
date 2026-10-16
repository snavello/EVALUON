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
   en todos, no hay páginas sin leer ni documentos sin lectura, se leyeron todos los grupos y
   **ninguno es ese documento** (T-285, D-283-5): ningún grupo ubicó un texto de la oferta sobre
   el requisito ni concluyó (`GroupResult.found`) y ninguno marcó la condición como de una opción
   que la oferta no usa (`option_use`); "no determinado" `lectura_incompleta` si hay algo sin leer;
   `sin_dato` si la exigencia es una condición y se leyó todo, si la condición es de una opción
   (la regla de `options.py` decide si aplica) o si la lectura señaló un texto sobre el documento
   exigido (con ese texto citado y la pregunta de si el documento está).

Un "cumple" o "no cumple" va después al contraste (`apply_contrast`): si no contesta `si`, es
"no determinado" `sin_corroborar` con las mismas citas. Un "no determinado" que falta un dato
(`sin_dato`, `lectura_incompleta`) siempre lleva una pregunta para la Comisión. `externo` no lleva ninguna. Lo que se decide por regla (externos del
catálogo y páginas ilegibles) lo aplica `rules.py` después de esta unión (T-166).

Preguntas (REQ-105; T-235): este módulo no escribe el texto de ninguna. Deja en `Combined.question`
la pregunta que escribió el modelo (o la de una regla) y en `Combined.ask` si el caso exige una;
`compose_question` arma la pregunta final, con el requisito, la conclusión y el texto de la oferta
(documento y página), dirigida a la Comisión. La pregunta del modelo se acepta solo si no se dirige
al oferente; si no, la arma el código. No hay preguntas de texto fijo genérico.

Tres salidas por celda (REQ-120; T-277; ADR-0070, punto 5): toda celda termina en «cumple» con
fundamento, «no cumple» con cita o fundamento, o «no determinado» con la pregunta a la Comisión o el
documento que falta nombrado. «No se encontró el documento» es la forma de «no determinado» cuando el
pliego exige un documento y se leyeron todos: lleva siempre su pregunta (la del modelo si la escribió) y
el documento exigido nombrado en ella. `compose_question` arma una pregunta para todo «no determinado»
que no nombre ya un documento faltante (`externo`, `pendiente_informe_tecnico`, `no_se_pudo_leer`), con
el texto de `_default_ask` por motivo. `cell_problem` es la comprobación de la forma: la usan los tests
(`test_tres_salidas.py`) y la medida (`medir_evaluacion`).
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
PENDING_REPORT = "pendiente_informe_tecnico"
MISMATCH = "falta_coincidencia"
IN_PORTAL = "en_portal"

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
    # T-285 (D-283-5): si la lectura señaló algo sobre el requisito aunque el grupo quede «no
    # consta» (una cita que el sistema ubicó, un dato del Portal o una conclusión del modelo), y las
    # citas ubicadas de ese grupo (`seen`): con eso no se afirma que el documento falte.
    found: bool = False
    seen: list = field(default_factory=list)
    # Lo que el modelo marcó en `usa_opcion` ("si", "no", "no_consta" o "").
    option_use: str = ""


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
# conclusión que el contraste no corroboró. Desde T-277 (REQ-120) las lleva todo «no determinado»
# que no nombre un documento (`asks_commission`); la lista queda como la de las que la regla fija.
ASKED_DOUBTS = (NO_DATA, INCOMPLETE, UNCORROBORATED)

# «No determinado» que ya nombra un documento o una consulta que falta (REQ-120): la hoja de
# compliance, el informe técnico del área o la página ilegible. No se les arma una pregunta genérica:
# `externo` no lleva ninguna (la acción es subir la hoja, REQ-063) y los otros dos solo la que escribe
# su regla.
DOCUMENT_DOUBTS = (EXTERNAL, PENDING_REPORT, UNREADABLE)


QUESTION_CLIP = 280

# T-285 (D-283-5): los dos «no consta» que no son «no se encontró el documento».
OPTION_NOTE = ("La condición vale solo para quien usa una opción y la lectura de la oferta no "
               "muestra que la use: no falta un documento.")
# T-285 (H-285-1, decisión del Coordinador): la marca del modelo nunca decide «no aplica»; la
# pregunta le pide a la Comisión que lo confirme.
OPTION_QUESTION = ("El requisito parece la condición de una opción que la oferta no usa: ¿la Comisión "
                   "lo confirma? Si la oferta no usa la opción, el requisito no aplica a esta oferta.")
SEEN_NOTE = ("La lectura no identificó el documento que el pliego exige, pero señaló un texto de la "
             "oferta sobre el requisito: no se afirma que el documento falte.")
SEEN_QUESTION = ("¿Está en la oferta el documento que exige este requisito? La lectura no lo "
                 "identificó, pero señaló el texto citado; la Comisión confirma si está.")

# T-285 (H-285-5): la lectura concluyó sobre el documento sin citar ningún texto: no se dice que
# señaló uno.
CONCLUDED_NOTE = ("La lectura no identificó el documento que el pliego exige y concluyó sobre él sin "
                  "citar un texto de la oferta: no se afirma que el documento falte.")
CONCLUDED_QUESTION = ("¿Está en la oferta el documento que exige este requisito? La lectura concluyó "
                      "sobre él sin citar un texto de la oferta; la Comisión confirma si está.")

# El motivo que lleva la explicación de un «no determinado» cuando el modelo no escribió ninguna
# (REQ-120: una celda sin decidir siempre dice por qué).
NO_REASON = {
    DOUBT: "El modelo no pudo decidir este requisito con lo que leyó de la oferta.",
    NO_CITATION: ("El modelo concluyó, pero la cita que dio no se encontró letra por letra en los "
                  "documentos de la oferta: sin ella no se da por concluido."),
    NO_DATA: "Falta el dato que el requisito exige.",
    INCOMPLETE: "Hay partes de la oferta que no se pudieron leer.",
    CONTRADICTION: "Distintos documentos de la oferta dicen cosas opuestas sobre este requisito.",
    EXTERNAL: "Falta la hoja de compliance: este requisito se verifica fuera de la oferta.",
}


def _plain(text):
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


_ROLE = (r"(?:oferentes?|proveedor(?:es)?|empresas?|firmas?|licitantes?|participantes?"
         r"|cotizantes?|postor(?:es)?|adjudicatari[oa]s?|adjudicad[oa]s?|contratistas?"
         r"|concursantes?|vendedor(?:es)?|presentantes?)")
# Formas del imperativo o del subjuntivo con que se le da una orden a alguien («aclare», «presenten»).
_SUBJ = (r"(?:aclare|informe|presente|indique|confirme|adjunte|envie|aporte|explique|detalle"
         r"|especifique|complete|subsane|acompane|remita|justifique|acredite|proporcione"
         r"|manifieste|declare|certifique|precise|amplie|ratifique|rectifique|responda|conteste"
         r"|diga|haga)n?")
# Verbos con que se le pide u ordena algo a alguien: modales, de pedido, de obligación y las
# formas de la orden. No entran las formas del indicativo («presentó», «presentada»): «¿El
# oferente presentó la garantía?» es una pregunta de hecho.
_ASK = (r"(?:podr\w+|pued\w+|deb\w+|tendr\w+|tenga\w*|requer\w+|solicit\w*|pid\w+|ruego"
        rf"|rogamos|exig\w+|invit\w+|intim\w+|emplaz\w+|notific\w+|oblig\w+|{_SUBJ})")
# Verbos sin sujeto con que una pregunta le habla a alguien: «¿Puede aclarar…?», «¿Cuenta con…?».
_ADDRESSING_START = (r"(?:pued[eo]\w*|podr\w+|deb[eo]\w*|deber\w+|tien[ea]\w*|tendr\w+"
                     r"|cuent[ae]\w*|dispon[ge]\w*|poseen?|conoc[ea]\w*|sab[eo]\w*"
                     r"|desea\w*|quisier\w+)")

_TO_OFFEROR = [
    # 1. Un destinatario nombrado: «al oferente», «a la empresa», «para el adjudicatario».
    re.compile(rf"\b(?:a|al|para)\s+(?:(?:el|la|los|las)\s+)?{_ROLE}\b"),
    # 2. Un rol junto a un verbo de pedido u obligación: «el oferente deberá…», «podría el
    #    cotizante aclarar…», «queda obligado el adjudicatario».
    re.compile(rf"\b{_ROLE}\W+(?:\w+\W+){{0,3}}?{_ASK}\b"),
    re.compile(rf"\b{_ASK}\W+(?:\w+\W+){{0,3}}?{_ROLE}\b"),
    # 3. Un pedido impersonal o en primera persona: «se requiere…», «solicitamos…», «favor de…».
    re.compile(r"\bse\s+(?:le\s+|les\s+|lo\s+)?(?:requier\w+|solicit\w+|pid\w+|ruega\w*|exig\w+"
               r"|invit\w+|intim\w+|notific\w+|emplaz\w+|necesit\w+)\b"),
    re.compile(r"\b(?:solicitamos|pedimos|requerimos|rogamos|invitamos|instamos|exigimos"
               r"|necesitamos|agradec\w+|agradeceremos|apreciar\w+)\b"),
    # 4. Segunda persona y cortesía: «usted», «por favor», «sírvase», «favor de».
    re.compile(r"\busted(?:es)?\b|\bvos\b|\bpor\s+favor\b|\bfavor\s+de\b|\bsirva\w*\b"
               r"|\b(?:puedes|podes|podrias|tienes|tenes|sabes|conoces|nos\s+informe|nos\s+"
               r"remita|nos\s+confirme)\b"),
]
# 5. Una orden o un verbo que le habla a alguien, al empezar la oración.
_SENTENCE_START = re.compile(
    rf"^(?:{_SUBJ}|sirva\w*|favor|{_ADDRESSING_START}"
    r"(?!\s+(?:la|el)\s+(?:comision|comite|evaluador|sistema)))\b")


def addresses_offeror(text):
    """Si la pregunta se dirige al oferente (o a otro tercero: el adjudicatario, la empresa, el
    cotizante…) en lugar de a la Comisión (REQ-105). Es la única definición: la usan
    `compose_question` y la medida de la forma de las preguntas (`evaluation.question_form`).
    Rechaza el imperativo dirigido a otro, la segunda persona, el pedido impersonal y cualquier
    mención de un rol como destinatario; acepta una pregunta de hecho o una dirigida a la Comisión
    («¿La Comisión confirma…?», «¿El oferente presentó la garantía?»). Ante la duda rechaza: el
    código arma entonces la pregunta."""
    plain = _plain(text)
    if any(pattern.search(plain) for pattern in _TO_OFFEROR):
        return True
    for sentence in re.split(r"(?<=[.?!:;])\s+|\n+", plain):
        sentence = re.sub(r"^[\W_]+", "", sentence)
        if _SENTENCE_START.search(sentence):
            return True
    return False


def asks_the_offeror(question):
    """Si la pregunta, sin lo que cita entre «», se dirige al oferente (`addresses_offeror`). Lo que
    la pregunta copia del pliego o de la oferta («El oferente deberá…») no cuenta, como en la medida
    de la forma de las preguntas (`evaluation.question_form`)."""
    return addresses_offeror(re.sub(r"«[^»]*»", " ", question or ""))


def _clip(text, size):
    text = " ".join((text or "").split())
    if len(text) <= size:
        return text
    return text[:size].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


clip = _clip


def _sentence(text):
    return text.rstrip(" .") + "."


def _conclusion(combined):
    from evaluon.assessment.models import Doubt

    if combined.outcome == OUT_SIN_DOCUMENTO:
        base = "no se encontró el documento que el pliego exige"
    elif combined.doubt == UNCORROBORATED and combined.proposed:
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


def _named_conditions(conditions):
    """Las condiciones que quedaron sin resultado (las del modelo, ya controladas), entre comillas,
    para nombrar el dato que falta en la pregunta (T-285, D-283-7)."""
    names = [(c.get("condicion") or "").strip(" .") for c in conditions or ()
             if c.get("resultado") not in ("cumple", "no_cumple")]
    return " y ".join(f"«{name}»" for name in names if name)


def _default_ask(combined, conditions=()):
    """La pregunta que arma el código cuando el modelo no escribió una válida (REQ-105, REQ-120):
    un texto por motivo, dirigido a la Comisión. T-285 (D-283-7): nombra el dato que falta (las
    condiciones sin resultado, si se conocen) y no le pide a la Comisión un texto que la oferta no
    tiene por qué traer."""
    if combined.outcome == OUT_SIN_DOCUMENTO:
        return ("¿Consta en la oferta el documento que exige este requisito? El sistema leyó todos "
                "los documentos de la oferta y no lo encontró; la Comisión confirma si falta.")
    if combined.doubt == UNCORROBORATED:
        word = {OUT_CUMPLE: "cumple", OUT_NO_CUMPLE: "no cumple"}.get(combined.proposed)
        what = f"la conclusión «{word}»" if word else "la conclusión del sistema"
        return f"¿La Comisión confirma, corrige o rechaza {what}?"
    if combined.doubt == INCOMPLETE:
        return ("¿Lo que exige este requisito consta en las partes sin leer? La Comisión debe "
                "revisar el original.")
    if combined.doubt == NO_DATA:
        named = _named_conditions(conditions)
        if named:
            return (f"¿Cómo resuelve la Comisión {named}? La lectura de la oferta no trae ese "
                    "dato.")
        return ("¿Cómo resuelve la Comisión este requisito? La lectura de la oferta no trae el dato "
                "que pide la oración del pliego citada arriba.")
    if combined.doubt == CONTRADICTION:
        return ("¿Cuál de los documentos de la oferta rige para este requisito? Dicen cosas "
                "opuestas y la Comisión debe decidir cuál vale.")
    if combined.doubt == NO_CITATION:
        return ("¿La Comisión confirma lo que concluyó la lectura de la oferta para este requisito? "
                "La cita que lo sostenía no se encontró letra por letra en los documentos.")
    if combined.doubt == MISMATCH:
        return ("¿Cuál rige para este requisito: el dato del Portal o el texto de la oferta? No "
                "coinciden y la Comisión verifica cuál vale.")
    if combined.doubt == IN_PORTAL:
        return ("¿El dato del Portal alcanza para este requisito? La Comisión confirma si el "
                "documento que está en el Portal responde a lo que exige.")
    if combined.doubt == UNREADABLE:
        return ("¿Lo que exige este requisito está en la parte ilegible del documento? La Comisión "
                "debe revisar el original.")
    if combined.doubt == PENDING_REPORT:
        return "¿La Comisión da el ok del informe técnico del área para este requisito?"
    if combined.citations or combined.portal:
        return "¿Cómo resuelve la Comisión este requisito con el texto citado?"
    return ("¿Qué determina la Comisión sobre este requisito? El sistema no pudo decidirlo con "
            "los documentos leídos.")


def asks_commission(combined):
    """Si el resultado lleva una pregunta a la Comisión (REQ-120): «no se encontró el documento» y
    todo «no determinado» que no nombre ya un documento o una consulta que falta. Los de
    `DOCUMENT_DOUBTS` solo la llevan si su regla la escribió; `externo` nunca (REQ-063)."""
    if combined.outcome == OUT_SIN_DOCUMENTO:
        return True
    if combined.outcome != OUT_NO_DETERMINADO or combined.doubt == EXTERNAL:
        return False
    if combined.doubt in DOCUMENT_DOUBTS:
        return bool((combined.question or "").strip())
    return True


def compose_question(number, requirement, combined, *, documents=(), unread=(), conditions=()):
    """La pregunta final a la Comisión por un par "no determinado" o «no se encontró el documento»
    (REQ-105, REQ-120; T-235), o `""` si no corresponde (`asks_commission`). Lleva el requisito (cita
    del pliego), la conclusión del sistema y el texto de la oferta (documento y página); cierra con
    la pregunta del modelo si no se dirige al oferente, y si no, con una que arma el código.
    `documents`: títulos de los documentos leídos; `unread`: las partes sin leer (`{"title",
    "page"}`); `conditions`: las condiciones del par ya controladas (T-285: la pregunta por defecto
    nombra las que quedaron sin resultado)."""
    if not asks_commission(combined):
        return ""
    asked = " ".join((combined.question or "").split())
    closing = (asked if asked and not asks_the_offeror(asked)
               else _default_ask(combined, combined.facts.get("condiciones") or conditions or ()))
    head = f"Requisito {number}" + (f": «{_clip(requirement, QUESTION_CLIP)}»" if requirement
                                    and requirement.strip() else "")
    return "\n".join([
        _sentence(head),
        f"Conclusión del sistema: {_conclusion(combined)}",
        f"Texto de la oferta: {_evidence(combined, documents, unread)}",
        closing])


# Las formas que no cumplen las tres salidas (REQ-120), por nombre.
PROBLEM_NO_QUESTION = "sin_documento_sin_pregunta"
PROBLEM_UNNAMED = "no_determinado_sin_nombrar"
PROBLEM_NO_REASON = "no_determinado_sin_motivo"
PROBLEM_NO_GROUND = "cumple_sin_fundamento"
PROBLEM_NO_QUOTE = "no_cumple_sin_cita"

# Lo que dice la explicación de un «no determinado» que espera un documento o una consulta (se
# comprueba sin tildes ni mayúsculas).
_DOCUMENT_NAMES = {EXTERNAL: "hoja de compliance", PENDING_REPORT: "informe",
                   UNREADABLE: "pagina"}


def cell_problem(outcome, *, doubt="", has_question=False, has_citation=False, facts=None,
                 explanation=""):
    """La comprobación de las tres salidas de una celda (REQ-120; ADR-0070, punto 5). Devuelve `""`
    si cumple una de las formas y, si no, el nombre de lo que falla:

    - «cumple» con fundamento: una cita de la oferta o del Portal, un criterio de la Comisión
      (`facts["criterios"]`: la ausencia verificada, el IVA), el ok del informe técnico o el motivo de
      un «no aplica» (`facts["aplica"]` falso, con su explicación);
    - «no cumple» con cita (de la oferta o del Portal) o decidido por una regla (`facts["regla"]`: la
      presentación física, el Portal, el ok técnico);
    - «no determinado» con su motivo en la explicación y con la pregunta a la Comisión o, si espera un
      documento o una consulta (`DOCUMENT_DOUBTS`), con ese documento nombrado en la explicación;
    - «no se encontró el documento» con su pregunta (y el requisito, que nombra el documento exigido).

    `has_citation` es si la celda tiene citas de la oferta o del Portal; `has_question`, si tiene la
    pregunta a la Comisión."""
    facts = facts or {}
    if outcome == OUT_SIN_DOCUMENTO:
        return "" if has_question else PROBLEM_NO_QUESTION
    if outcome == OUT_NO_DETERMINADO:
        if not (explanation or "").strip():
            return PROBLEM_NO_REASON
        if has_question:
            return ""
        needle = _DOCUMENT_NAMES.get(doubt)
        return "" if needle and needle in _plain(explanation) else PROBLEM_UNNAMED
    if outcome == OUT_CUMPLE:
        grounded = (has_citation or facts.get("criterios") or facts.get("technical_ok")
                    or (facts.get("aplica") is False and (explanation or "").strip()))
        return "" if grounded else PROBLEM_NO_GROUND
    if outcome == OUT_NO_CUMPLE:
        grounded = has_citation or facts.get("regla") or facts.get("technical_ok")
        return "" if grounded else PROBLEM_NO_QUOTE
    return PROBLEM_NO_GROUND


def combined_problem(combined):
    """`cell_problem` de un `Combined` ya con su pregunta final (`compose_question`)."""
    return cell_problem(
        combined.outcome, doubt=combined.doubt, has_question=bool((combined.question or "").strip()),
        has_citation=bool(combined.citations or combined.portal), facts=combined.facts,
        explanation=combined.explanation)


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
             pool=None, fallback_question=""):
        if doubt == DOUBT and warning:
            # Con partes de la oferta sin leer, una duda puede venir de ahí: se dice así y se
            # pregunta a la Comisión (no se supone que la respuesta no estaba).
            doubt = INCOMPLETE
        citations, supports = _merge(pool if pool is not None else groups, only)
        text = explanation if explanation is not None else _first(
            pool if pool is not None else groups, "explanation")
        if not (text or "").strip():
            # REQ-120: una celda sin decidir dice por qué, aunque el modelo no lo haya escrito.
            text = NO_REASON.get(doubt, "") if outcome == OUT_NO_DETERMINADO else ""
        # Una conclusión no lleva pregunta: la lleva un "no determinado" y «no se encontró el
        # documento» (REQ-120: nunca sin su pregunta). Falta la hoja de compliance: no hay nada
        # que preguntar, hay que subirla (REQ-063).
        asking = ((outcome == OUT_NO_DETERMINADO and doubt != EXTERNAL)
                  or outcome == OUT_SIN_DOCUMENTO)
        asked = (question or fallback_question) if asking else ""
        return Combined(
            outcome=outcome, doubt=doubt,
            exigence=exigence if exigence is not None else _first(groups, "exigence"),
            citations=citations, supports=supports, explanation=text, question=asked,
            unread_warning=warning,
            ask=asking and (outcome == OUT_SIN_DOCUMENTO or (ask and doubt in ALWAYS_ASK)),
            portal=_merge_portal(pool if pool is not None else groups, only))

    if not groups:
        return done(OUT_NO_DETERMINADO, INCOMPLETE, explanation=(
            "La oferta no tiene documentos leídos."), exigence="")
    if any(g.external for g in groups):
        flagged = [g for g in groups if g.external]
        # La regla `externals.rule` reemplaza la explicación; acá queda la de siempre (REQ-120).
        return done(OUT_NO_DETERMINADO, EXTERNAL, explanation=NO_REASON[EXTERNAL],
                    pool=flagged + [g for g in groups if not g.external])
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
    option = any(g.option_use == "no" for g in groups)
    seen = any(g.found for g in groups)
    if complete and exigence == "documento" and not option and not seen:
        return done(OUT_SIN_DOCUMENTO, exigence=exigence, ask=False, explanation=(
            "Se leyeron todos los documentos de la oferta y ninguno es el documento que el "
            "pliego exige."))
    if not complete:
        return done(OUT_NO_DETERMINADO, INCOMPLETE, exigence=exigence, explanation=(
            "No se puede afirmar que el documento falta: hay partes de la oferta que no se "
            "pudieron leer."))
    if option:
        # T-285 (D-283-5): la condición de una opción que la oferta no muestra usar no es un
        # documento faltante; si aplica o no lo decide la regla de la opción (`options.py`).
        return done(OUT_NO_DETERMINADO, NO_DATA, exigence=exigence, explanation=OPTION_NOTE,
                    fallback_question=OPTION_QUESTION)
    if exigence == "documento" and seen:
        # T-285 (D-283-5): la lectura señaló un texto de la oferta sobre el documento exigido: no se
        # afirma que falte; se cita ese texto y se pregunta. Si no citó ninguno (concluyó sin cita),
        # se dice eso (H-285-5).
        cited = any(g.seen for g in groups)
        return done(OUT_NO_DETERMINADO, NO_DATA, exigence=exigence,
                    explanation=SEEN_NOTE if cited else CONCLUDED_NOTE,
                    pool=[replace(g, citations=list(g.seen)) for g in groups],
                    fallback_question=SEEN_QUESTION if cited else CONCLUDED_QUESTION)
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
        # REQ-120: la pregunta nombra las cláusulas que faltan; la del modelo vale solo si se
        # dirige a la Comisión.
        asked = " ".join((question or "").split())
        if not asked or asks_the_offeror(asked):
            single = len(missing) == 1
            word, verb = ("la cláusula", "confirmarla") if single else ("las cláusulas",
                                                                         "confirmarlas")
            asked = (f"¿Qué determina la Comisión sobre {word} {names}? El sistema no pudo "
                     f"{verb} con el texto de la oferta.")
        return replace(combined, outcome=OUT_NO_DETERMINADO, doubt=NO_DATA,
                       explanation=explanation, question=asked, ask=True)
    return combined
