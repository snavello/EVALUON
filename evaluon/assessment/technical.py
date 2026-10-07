"""Filas técnicas por renglón: se verifica, no se opina (REQ-061; plan 004, "Filas técnicas por
renglón"; ADR-0043; T-167).

Decisiones literales del responsable: «Lo tecnico verificamos que exista y que en caso de tener
renglones si tiene o no tiene oferta»; «La parte tecnica ya te dije que venia del area
correspondiente»; «la comision debiera dar el ok de que tiene el informe tecnico aprobado».

La regla rige por la **categoría** de la fila (`tecnico`, con renglón o sin él), no por lo que
diga el modelo. Verifica dos hechos y deja el resultado en espera del informe del área:

- `documento_tecnico`: `hay` solo con un documento técnico real (clasificado como técnico, con
  nombre o texto de ficha, hoja o especificación); una línea de precio u otra cita de la
  cotización no cuenta (T-172, H-3). `no_se_encontro` si `combine.py` concluyó "no se encontró el
  documento" (regla 5) o si la lectura fue completa y no hay ninguno (H-6); `no_determinado` si
  hay partes sin leer.
- `renglon_ofertado` (solo en una fila de un renglón): `si` si el Portal tiene una cotización
  con precio del renglón para la oferta (las tablas locales de la 012, sin red) o la lectura
  citó el renglón; `no` si el Portal no la tiene y la lectura completa no lo encontró;
  `no_determinado` si no.

El resultado es `no_determinado` con el motivo `pendiente_informe_tecnico` (o `sin_documento` si
el documento técnico no se encontró). El "cumple" o "no cumple" que producen la lectura y el
contraste por cláusula pasa a `opinion`: es información, nunca el resultado ni un descarte.

Si el renglón tiene un ok vigente de la Comisión al informe técnico (`services/technical.py`,
T-168), la fila se guarda con lo que dice ese informe (apto: cumple; no apto: no cumple), para que
una reevaluación no pierda el ok. Es la misma fila que escribe `give_ok` (mismos `facts`).
"""

import re
from dataclasses import replace

from django.utils import timezone

from evaluon.assessment import combine
from evaluon.assessment.portal_facts import _amount
from evaluon.assessment.models import TechnicalAction, TechnicalVerdict
from evaluon.offers.models import DocumentKind
from evaluon.portal.models import PortalOfferData, PortalQuote
from evaluon.tenders.models import RequirementClass

RULE = "tecnico_hechos"
RULE_OK = "ok_informe_tecnico"

HAY = "hay"
NO_SE_ENCONTRO = "no_se_encontro"
SI = "si"
NO = "no"
NO_DETERMINADO = "no_determinado"

# Lo que dice cada resultado del par, en la opinión (`sin_documento` no es una opinión).
OPINIONS = {combine.OUT_CUMPLE: "cumple", combine.OUT_NO_CUMPLE: "no_cumple",
            combine.OUT_NO_DETERMINADO: "no_determinado"}

PENDING = "pendiente_informe_tecnico"


def item_of(requirement):
    """El renglón de la fila (`None` si no es de un renglón o no es un número)."""
    items = requirement.items or []
    if not items:
        return None
    try:
        return int(items[0])
    except (TypeError, ValueError):
        return None


def _cited(pair):
    return bool(pair.combined.citations) or any(g.citations for g in pair.groups)


# Lo que dice un documento técnico real: ficha, hoja técnica, especificación técnica, folleto,
# catálogo. Se busca en el nombre del archivo, en el título y en el texto citado.
_TECHNICAL_DOCUMENT = re.compile(
    r"ficha[\s_-]+t[eé]cnica|hoja[\s_-]+t[eé]cnica"
    r"|especificaci(?:ón|on|ones)[\s_-]+t[eé]cnicas?"
    r"|data\s*sheet|folleto|cat[aá]logo|ficha|hoja\s+de\s+(?:datos|producto)",
    re.IGNORECASE)


def _is_technical_document(document):
    if document is None:
        return False
    if document.kind == DocumentKind.TECNICA:
        return True
    return bool(_TECHNICAL_DOCUMENT.search(f"{document.title} {document.file_name}"))


def _has_technical_document(pair, ctx):
    """Hay un documento técnico real: uno clasificado como técnico, uno que se llama como una
    ficha, hoja o especificación, o una cita de la lectura con ese texto. Una línea de precio u
    otra cita de la cotización no es un documento técnico (T-172, H-3)."""
    if any(_is_technical_document(d.document)
           for d in getattr(ctx.offer_text, "documents", []) or []):
        return True
    cited = [*pair.combined.citations, *(c for g in pair.groups for c in g.citations)]
    return any(_is_technical_document(c.document) or _TECHNICAL_DOCUMENT.search(c.text or "")
               for c in cited)


def document_state(pair, ctx):
    """`hay`, `no_se_encontro` o `no_determinado` (el documento técnico de la oferta).

    `no_se_encontro` cuando la regla 5 de `combine.py` lo concluyó o cuando la lectura fue
    completa (sin páginas ni documentos sin leer) y no hay ningún documento técnico (T-172,
    H-6); con partes sin leer no se afirma que falta."""
    if _has_technical_document(pair, ctx):
        return HAY
    if pair.combined.outcome == combine.OUT_SIN_DOCUMENTO:
        return NO_SE_ENCONTRO
    if pair.groups and not pair.combined.unread_warning:
        return NO_SE_ENCONTRO
    return NO_DETERMINADO


def portal_quote(offer, item):
    """La cotización con precio del renglón para la oferta, de las tablas locales de la 012
    (`portal_quote`); `None` si no hay."""
    return (PortalQuote.objects.filter(offer=offer, line__procedure_id=offer.procedure_id,
                                       line__number=item, price__isnull=False)
            .select_related("line").first())


def quote_citation(offer, quote):
    """La cotización como dato citado del Portal (clase `cotizacion`); `None` si la oferta no
    tiene el ítem de origen de sus datos."""
    data = PortalOfferData.objects.filter(offer=offer).first()
    if data is None:
        return None
    return {"item": data.item_id, "kind": "cotizacion",
            "label": f"Portal: cotización del renglón {quote.line.number}",
            "text": (f"Renglón {quote.line.number}: precio {_amount(quote.price)}, "
                     f"cantidad {_amount(quote.quantity)}")}


def line_state(pair, quote):
    """`si`, `no` o `no_determinado` (si el renglón tiene oferta)."""
    if quote is not None or _cited(pair):
        return SI
    combined = pair.combined
    complete = not combined.unread_warning
    nothing_found = bool(pair.groups) and all(g.result == "no_consta" for g in pair.groups)
    if complete and nothing_found:
        return NO
    return NO_DETERMINADO


def _explanation(item, document, line, quote):
    parts = ["Lo técnico lo resuelve el informe del área correspondiente: la Comisión da el ok "
             "de que lo tiene aprobado. El sistema solo verificó lo que sigue."]
    parts.append({HAY: "Hay documento técnico en la oferta.",
                  NO_SE_ENCONTRO: "No se encontró el documento técnico de la oferta.",
                  NO_DETERMINADO: "No se pudo determinar si hay documento técnico."}[document])
    if item is not None:
        parts.append({
            SI: f"El renglón {item} tiene oferta" + (" (cotización del Portal)." if quote
                                                      else " (la oferta lo menciona)."),
            NO: f"El renglón {item} no tiene oferta: el Portal no lo cotiza y la oferta no "
                "lo menciona.",
            NO_DETERMINADO: f"No se pudo determinar si el renglón {item} tiene oferta."}[line])
    return " ".join(parts)


def _ok_row(pair, ctx, item):
    """El ok vigente del informe técnico para el renglón, con su veredicto; `None` si no hay."""
    if item is None:
        return None
    from evaluon.assessment.services import technical as ok_service  # evita un ciclo
    row = ok_service.ok_of(ctx.offer, item)
    if row is None or row.action != TechnicalAction.DAR_OK:
        return None
    verdict = (row.verdicts or {}).get(str(item))
    return row if verdict in TechnicalVerdict.values else None


def _from_ok(combined, row, item, facts, opinion):
    verdict = row.verdicts[str(item)]
    who = f"{row.user.get_username()} el {timezone.localtime(row.at).strftime('%d/%m/%Y %H:%M')}"
    outcome = (combine.OUT_CUMPLE if verdict == TechnicalVerdict.APTO
               else combine.OUT_NO_CUMPLE)
    return replace(
        combined, outcome=outcome, doubt="", question="", opinion=opinion,
        explanation=f"informe técnico aprobado, ok de la Comisión por {who}",
        facts={**facts, "regla": RULE_OK, "technical_ok": row.pk,
               "usuario": row.user.get_username(), "dictamen": verdict})


def rule(pair, ctx):
    """La regla 2 de `rules.py`: devuelve el resultado nuevo de una fila técnica o `None` si la
    fila no es técnica."""
    if getattr(pair.requirement, "category", None) != RequirementClass.TECNICO:
        return None
    combined = pair.combined
    item = item_of(pair.requirement)
    opinion = OPINIONS.get(combined.outcome, "")
    document = document_state(pair, ctx)
    facts = {**combined.facts, "documento_tecnico": document}
    quote, line = None, None
    if item is not None:
        quote = portal_quote(ctx.offer, item)
        line = line_state(pair, quote)
        facts.update(renglon=item, renglon_ofertado=line)
    portal = []
    if quote is not None:
        cited = quote_citation(ctx.offer, quote)
        if cited is not None:
            portal.append(cited)
    ok = _ok_row(pair, ctx, item)
    if ok is not None:
        return replace(_from_ok(combined, ok, item, facts, opinion), portal=portal)
    explanation = _explanation(item, document, line, quote)
    if opinion and combined.explanation:
        explanation += (" La opinión del sistema (información, no es el resultado): "
                        f"{combined.explanation}")
    # `sin_documento` solo si `combine.py` lo concluyó; si no, la fila queda pendiente del informe.
    outcome, doubt = ((combine.OUT_SIN_DOCUMENTO, "")
                      if document == NO_SE_ENCONTRO
                      and combined.outcome == combine.OUT_SIN_DOCUMENTO
                      else (combine.OUT_NO_DETERMINADO, PENDING))
    if outcome == combine.OUT_SIN_DOCUMENTO:
        explanation = (f"{explanation} La Comisión decide si pide que se subsane.")
    return replace(combined, outcome=outcome, doubt=doubt, question="",
                   explanation=explanation, opinion=opinion, portal=portal,
                   facts={**facts, "regla": RULE})
