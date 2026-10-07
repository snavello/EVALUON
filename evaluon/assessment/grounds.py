"""Fundamentos de un requisito: el texto vigente del pliego, las unidades de norma que la matriz
ya asocia y las respuestas de la Comisión que aplican (REQ-053, REQ-055; plan 004, "Qué
recibe y qué devuelve el modelo"; ADR-0040; T-150).

- **Texto del requisito.** El de cada cita de la matriz; si una circular la modificó, el texto
  vigente es el de la última modificación (por fecha) y el original queda al lado. Una cita que
  la última circular suprime se muestra con su texto y la marca de suprimida.
- **Normas.** No hay búsqueda normativa nueva: las unidades que la matriz validada ya trae
  para el requisito (respaldo normativo y fundamentos de la consecuencia elegida o, si no hay,
  de las sugeridas), hasta `ASSESSMENT_NORM_UNITS_MAX`.
- **Respuestas de la Comisión.** La vigente de cada pregunta (la última) cuyo alcance aplica
  al par, hasta `ASSESSMENT_ANSWERS_MAX`; si hay más, el reranker elige las más cercanas al
  requisito. Una pregunta sin respuesta no es fundamento (P3).
- **Normativa de la evaluación (P8).** Régimen y versión de la normativa de la propuesta de la
  matriz; sin propuesta (una matriz armada a mano), el régimen a la fecha de autorización.
"""

import re
from dataclasses import dataclass, field

from django.conf import settings

from evaluon.ai import reranker
from evaluon.assessment.models import Answer, AnswerScope
from evaluon.norms import indexing
from evaluon.norms.models import Unit
from evaluon.tenders.models import (
    ConsequenceOrigin,
    ConsequenceType,
    NormSupport,
    QuoteScope,
    RequirementClass,
    SourceEffect,
)
from evaluon.tenders.services.procedures import regime_for

# Máximo de caracteres que se le dan al modelo de una unidad de norma tomada de la consecuencia
# (las del respaldo normativo ya son una cita corta).
NORM_UNIT_MAX_CHARS = 1500


# Cuánto del texto del tramo anterior a la cita se mira como encabezado (T-175).
LEAD_MAX_CHARS = 200
_PATH_SEPARATOR = " › "
# Fin de una oración: un punto seguido de mayúscula (no el de «11.8.» ni el de «219/2018.»).
_SENTENCE_END = re.compile(r"(?<!\d)\.\s+(?=[A-ZÁÉÍÓÚÑ]|$)")
_UNTITLED_PART = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?|(?:párrafo|tabla|viñeta|no ubicado)\b.*)$", re.IGNORECASE)


def segment_heading(quote, *, titles=True):
    """El título del tramo del pliego del que sale la cita (T-175; REQ-063): el encabezado del
    tramo, el título del apartado más cercano de su ruta y el texto del tramo que antecede a
    la cita (hasta `LEAD_MAX_CHARS`), porque el pliego a veces pone el título en la misma línea
    que la condición («Declaración jurada de habilidad para contratar: el oferente deberá
    completar…») y la cita recorta solo la condición. Con `titles=False`, solo lo que antecede a
    la cita en el tramo. Vacío si la cita no tiene tramo."""
    segment = getattr(quote, "segment", None)
    if segment is None:
        return ""
    parts = []
    label = (segment.label or "").strip()
    if titles and label and not _UNTITLED_PART.match(label):
        parts.append(label)
    for part in reversed((segment.path or "").split(_PATH_SEPARATOR) if titles else []):
        if part.strip() and not _UNTITLED_PART.match(part.strip()):
            parts.append(part.strip())
            break
    lead = (segment.text or "")[:max(quote.char_start - segment.char_start, 0)]
    # Solo la oración en que empieza la cita: lo anterior es otra condición del tramo.
    lead = _SENTENCE_END.split(lead)[-1]
    if lead.strip():
        parts.append(lead.strip()[-LEAD_MAX_CHARS:])
    return " ".join(dict.fromkeys(parts))


@dataclass
class QuoteText:
    """Una cita del requisito con su texto vigente."""

    quote: object
    text: str
    original: str = ""
    suppressed: bool = False

    @property
    def scope_label(self):
        return QuoteScope(self.quote.scope).label if self.quote.scope else ""


@dataclass
class RequirementText:
    requirement: object
    quotes: list = field(default_factory=list)

    @property
    def item(self):
        items = self.requirement.items
        if self.requirement.category == RequirementClass.TECNICO and items:
            return items[0]
        return None

    @property
    def label(self):
        category = RequirementClass(self.requirement.category).label
        item = f" · renglón {self.item}" if self.item is not None else ""
        return f"requisito {self.requirement.number}, {category.lower()}{item}"

    @property
    def text(self):
        """El texto vigente de todas sus citas, para buscar y para reordenar."""
        return " ".join(q.text for q in self.quotes)

    @property
    def context(self):
        """El título del tramo de cada cita y su texto vigente: lo que mira la regla de los
        externos (T-175). El pedido al modelo y la búsqueda siguen con `text`."""
        return " ".join(part for q in self.quotes
                        for part in (segment_heading(q.quote), q.text) if part)

    @property
    def opening(self):
        """Lo que antecede a cada cita en su tramo y su texto vigente: lo que mira la regla del
        Portal además del texto (T-175). Sin los títulos de la ruta, que alcanzan a toda una
        sección."""
        return " ".join(part for q in self.quotes
                        for part in (segment_heading(q.quote, titles=False), q.text) if part)

    def render(self):
        """El bloque del requisito al final del pedido."""
        head = f"Requisito del pliego ({self.label})"
        if self.item is not None:
            head = f"Renglón {self.item} del pliego ({self.label})"
        lines = [head + ":"]
        for q in self.quotes:
            tag = f" [{q.scope_label}]" if q.scope_label and len(self.quotes) > 1 else ""
            lines.append(f"«{q.text}»{tag}")
            if q.original:
                lines.append(f"(Texto original, antes de la circular: «{q.original}»)")
            if q.suppressed:
                lines.append("(Una circular posterior suprimió este texto.)")
        return "\n".join(lines)


def requirement_text(requirement):
    """El requisito con el texto vigente de cada una de sus citas."""
    quotes = list(requirement.quotes.select_related("segment").order_by("order"))
    sources = list(requirement.sources.exclude(quote=None).order_by("issued_on", "pk"))
    out = RequirementText(requirement=requirement)
    for quote in quotes:
        chain = [s for s in sources if s.quote_id == quote.pk
                 and s.effect in (SourceEffect.MODIFICA, SourceEffect.SUPRIME)]
        if chain and chain[-1].effect == SourceEffect.MODIFICA:
            out.quotes.append(QuoteText(quote, text=chain[-1].text, original=quote.text))
        elif chain:
            out.quotes.append(QuoteText(quote, text=quote.text, suppressed=True))
        else:
            out.quotes.append(QuoteText(quote, text=quote.text))
    return out


# --- Normas ----------------------------------------------------------------------------------


@dataclass
class NormGround:
    unit: object
    label: str
    text: str


def norm_grounds(requirement, limit=None):
    """Las unidades de norma que la matriz asocia al requisito (sin repetir), hasta
    `limit` (`ASSESSMENT_NORM_UNITS_MAX`)."""
    limit = limit or settings.ASSESSMENT_NORM_UNITS_MAX
    grounds, seen = [], set()
    supports = NormSupport.objects.filter(requirement=requirement).select_related("unit") \
        .order_by("-score", "pk")
    for support in supports:
        if support.unit_id not in seen:
            seen.add(support.unit_id)
            grounds.append(NormGround(support.unit, support.unit_label, support.text))
    consequences = list(requirement.consequences.exclude(
        consequence_type=ConsequenceType.NO_DETERMINADA).order_by("pk"))
    chosen = [c for c in consequences if c.chosen]
    suggested = chosen or [c for c in consequences if c.origin == ConsequenceOrigin.SISTEMA]
    for consequence in suggested:
        for ground in consequence.grounds:
            unit_id = ground.get("unit") if isinstance(ground, dict) \
                and ground.get("source") == "norma" else None
            if unit_id is None or unit_id in seen:
                continue
            unit = Unit.objects.select_related("reading__document__norm").filter(
                pk=unit_id).first()
            if unit is None:
                continue
            seen.add(unit_id)
            grounds.append(NormGround(
                unit, indexing.passage_header(unit.reading.document.norm, unit),
                unit.text[:NORM_UNIT_MAX_CHARS]))
    return grounds[:limit]


# --- Respuestas de la Comisión ---------------------------------------------------------------


def _applies(answer, requirement, offer):
    question = answer.question
    if answer.scope == AnswerScope.PAR:
        return question.offer_id == offer.pk and question.requirement_id == requirement.pk
    if answer.scope == AnswerScope.REQUISITO:
        return question.requirement_id == requirement.pk
    return True  # procedimiento


def applicable_answers(requirement, offer, limit=None):
    """Las respuestas vigentes de la Comisión que aplican al par `(offer, requirement)`, de la
    más antigua a la más reciente, hasta `limit` (`ASSESSMENT_ANSWERS_MAX`). La respuesta
    vigente de una pregunta es la última; con más de `limit`, el reranker elige las más
    cercanas al texto del requisito."""
    limit = limit or settings.ASSESSMENT_ANSWERS_MAX
    latest = {}
    answers = Answer.objects.filter(question__procedure_id=offer.procedure_id) \
        .select_related("question", "answered_by").order_by("answered_at", "pk")
    for answer in answers:
        latest[answer.question_id] = answer
    found = [a for a in latest.values() if _applies(a, requirement, offer)]
    if len(found) <= limit:
        return found
    query = requirement_text(requirement).text
    scores = reranker.rerank(query, [f"{a.question.text}\n{a.text}" for a in found])
    best = sorted(range(len(found)), key=lambda i: (-scores[i], i))[:limit]
    return [found[i] for i in sorted(best)]


# --- Normativa de la evaluación (P8) -----------------------------------------------------------


def norms_record(version):
    """Régimen, fecha de autorización y versión de la normativa de la matriz."""
    procedure = version.procedure
    source = version
    while source.run is None and source.based_on is not None:
        source = source.based_on
    run = source.run
    if run is not None:
        regime, corpus_version = run.regime, run.corpus_version
    else:
        regime, corpus_version = list(regime_for(procedure.authorization_date)), None
    return {"regime": regime, "authorization_date": procedure.authorization_date.isoformat(),
            "corpus_version": corpus_version, "matrix_version": version.number,
            "from_proposal": run is not None}
