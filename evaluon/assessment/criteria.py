"""Los criterios de la Comisión del 2026-10-12 que la evaluación aplica por regla (REQ-103,
REQ-104; spec 015, decisiones literales del 2026-10-12; ADR-0058; constitución 1.4, P3; T-257).

Decisiones literales del responsable (spec 015):

- **IVA.** «Precio del Portal = final con IVA»: salvo que la oferta diga lo contrario, el precio
  cotizado en el Portal se toma como precio final con IVA incluido; el sistema propone «cumple»
  citando el Portal y este criterio, registrado como criterio de la Comisión.
- **Ausencia.** «Cumple por ausencia, con fundamento»: un requisito negativo o supletorio (por
  ejemplo, no condicionar la oferta, mantenerla el plazo del pliego) se propone «cumple» diciendo
  qué documentos se leyeron y que ninguno lo contradice; si alguno lo contradice, «no cumple» con la
  cita.
- **Prórroga.** «En la misma fila del plazo»: el plazo de mantenimiento y su prórroga automática se
  evalúan por ausencia salvo que la oferta limite el plazo o rechace la prórroga.

Este módulo tiene lo que comparten las reglas que los aplican (`portal_facts.py` y `absence.py`):
qué condición nombra un impuesto, qué requisito o condición es negativo o supletorio (un catálogo
corto sobre el texto, versionado con `ASSESSMENT_RULES_VERSION`, como el de `externals.py`), las
condiciones que revisó el modelo para el par y el registro de cada criterio en `facts` (P6).

La ausencia es fundamento solo si la lectura de la oferta fue completa (sin páginas sin leer, sin
documentos sin lectura y con todos los grupos leídos: `Combined.unread_warning` falso) y ninguna
condición ni ningún grupo concluyó «no cumple» (P3, constitución 1.4).
"""

import re

from django.conf import settings

from evaluon.assessment.externals import fold

IVA = "iva_precio_final_portal"
ABSENCE = "ausencia_verificada"

DECISIONS = {
    IVA: "2026-10-12, «Precio del Portal = final con IVA»",
    ABSENCE: "2026-10-12, «Cumple por ausencia, con fundamento»",
}
NOTES = {
    IVA: ("Criterio de la Comisión (2026-10-12): el precio cotizado en el Portal se toma como "
          "precio final con IVA incluido, salvo que la oferta diga lo contrario."),
}

# El impuesto que el pliego pide incluido en el precio.
TAX = re.compile(r"\biva\b|alicuotas?|impuestos?|tributos?")

# Un requisito negativo sobre la oferta: lo prohibido («no se aceptarán ofertas condicionadas»,
# «no se admitirán ofertas con reservas», «sin condicionamientos»).
NEGATIVE = re.compile(
    r"\bno se (?:aceptar|admitir|considerar|tomar)\w*\b(?:\W+\w+){0,4}?\W+ofertas?\b"
    r"|\bofertas?\b(?:\W+\w+){0,3}?\W+(?:condicionad\w*|con reservas?|sujetas? a)\b"
    r"|\bsin (?:reservas?|condicionamientos?)\b|\bcondicionamientos?\b")
# Un requisito supletorio: rige lo del pliego si la oferta no dice otra cosa (el plazo de
# mantenimiento y su prórroga automática; precios fijos e inamovibles).
SUPPLETORY = re.compile(
    r"\bmanten(?:er|dra|dran|ga|gan)\w*\b(?:\W+\w+){0,8}?\W+(?:su |sus |la |las )?ofertas?\b"
    r"|\bprorrogad\w* automaticamente\b|\bprorroga automatica\b"
    r"|\bfij[oa]s? e inamovibles?\b|\binamovibles?\b|\bprecios? fijos?\b")
# Lo que no es ausencia aunque se diga en negativo: un tope o un mínimo de un valor («no podrá
# superar»), que se compara con un dato, y la garantía (se evalúa con su monto y su forma).
_NOT_ABSENCE = re.compile(
    r"\bno podra(?:n)? (?:superar|exceder|ser (?:menor|inferior|mayor|superior))\b"
    r"|\bgarantia\b|\bpagare\b|\bpoliza\b|\bcaucion\b")


def names_tax(text):
    """Si el texto (de una condición o del requisito) nombra el impuesto que va en el precio."""
    return bool(TAX.search(fold(text)))


def by_absence(text):
    """Si el texto (del requisito o de una condición) es negativo o supletorio: se cumple si la
    oferta no dice algo en contra (decisión del 2026-10-12)."""
    folded = fold(text)
    if _NOT_ABSENCE.search(folded):
        return False
    return bool(NEGATIVE.search(folded) or SUPPLETORY.search(folded))


def conditions_of(pair):
    """Las condiciones que revisó el modelo para el par, ya controladas por el sistema (REQ-104):
    las del grupo que sostiene el resultado (el que concluyó lo mismo que el par) o, si ninguno, las
    del primer grupo que las tiene. Lista vacía si no hay (salida anterior a `evaluacion-v6` o un
    par que no leyó el modelo)."""
    combined = getattr(pair, "combined", None)
    wanted = (getattr(combined, "proposed", "") or getattr(combined, "outcome", "")) if combined \
        else ""
    by_group = getattr(pair, "conditions", None) or {}
    first = []
    for group in getattr(pair, "groups", None) or []:
        records = by_group.get(group.index) or []
        if not records:
            continue
        if group.result == wanted:
            return [dict(r) for r in records]
        first = first or records
    return [dict(r) for r in first]


def complete(combined):
    """La lectura de la oferta fue completa: sin páginas sin leer, sin documentos sin lectura y con
    todos los grupos leídos."""
    return not getattr(combined, "unread_warning", False)


def contradicted(pair):
    """Si algo de la oferta contradice el requisito: un grupo o una condición concluyó «no cumple»
    (también uno que el contraste no corroboró)."""
    combined = pair.combined
    if combined.outcome == "no_cumple" or combined.proposed == "no_cumple":
        return True
    if any(getattr(g, "result", "") == "no_cumple" for g in getattr(pair, "groups", None) or []):
        return True
    return any((r.get("resultado_modelo") or r.get("resultado")) == "no_cumple"
               for r in conditions_of(pair))


def documents_read(ctx):
    """Los títulos de los documentos de la oferta que se leyeron (para decir qué se leyó)."""
    offer_text = getattr(ctx, "offer_text", None)
    if offer_text is None:
        return []
    return [d.document.title for d in offer_text.documents]


def record(name, **extra):
    """El registro del criterio en `facts` (P6): cuál, qué decisión literal lo fija y la versión de
    las reglas."""
    return {"nombre": name, "decision": DECISIONS[name],
            "version_reglas": settings.ASSESSMENT_RULES_VERSION, **extra}


def absence_note(titles, what=""):
    """La explicación de un «cumple» por ausencia: qué se leyó y que ninguno lo contradice."""
    read = ", ".join(f"«{t}»" for t in titles) if titles else "todos los documentos de la oferta"
    subject = f" {what}" if what else ""
    return (f"Cumple por ausencia{subject}: se leyeron todos los documentos de la oferta ({read}) "
            "y ninguno lo contradice.")
