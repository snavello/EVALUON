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

# T-257 (D-257-1, decisión del Coordinador): la ausencia vale solo para una **lista cerrada** de
# formas: las prohibiciones sobre lo que dice la oferta (no condicionarla, no formularla con
# reservas, no fijar precios que se ajusten) y las reglas supletorias (el plazo de mantenimiento y su
# prórroga automática). Cada forma tiene su nombre y su expresión (texto sin acentos).
ABSENCE_FORMS = {
    # la oferta condicionada («no se aceptarán ofertas condicionadas…», «sin condicionamientos»)
    "condicionar": re.compile(r"\bcondicionad[oa]s?\b|\bcondicionar\w*|\bcondicionamientos?\b"),
    # la oferta con reservas («no se admitirán ofertas con reservas», «sin reservas»)
    "reservas": re.compile(r"\b(?:con|sin) reservas?\b|\breservas? (?:alguna|sobre)\b"),
    # precios que no se ajustan («fijos e inamovibles»)
    "precio_fijo": re.compile(r"\bfij[oa]s? e inamovibles?\b|\binamovibles?\b|\bprecios? fijos?\b"),
    # el plazo de mantenimiento de la oferta (rige el del pliego si la oferta no fija otro)
    "mantenimiento": re.compile(
        r"\bmanten(?:er|dra|dran|ga|gan|ener)\w*\b(?:\W+\w+){0,8}?\W+(?:su |sus |la |las )?"
        r"ofertas?\b(?:\W+\w+){0,12}?\W+(?:plazo|dias|meses)\b|\bplazo de mantenimiento\b"),
    # su prórroga automática
    "prorroga": re.compile(r"\bprorrogad\w* automaticamente\b|\bprorroga automatica\b"),
}
# Lo que nunca es ausencia (D-257-1): un documento pedido en negativo («no se aceptarán ofertas sin
# la constancia», «que carezcan de», «que omitan», «desprovistas de», «que no incluyan»), un tope o
# un mínimo de un valor («no podrá superar»), que se compara con un dato, y la garantía (se evalúa
# con su monto y su forma).
_NOT_ABSENCE = re.compile(
    r"\bsin (?:el|la|los|las|su|sus|un|una)\b|\bcarezc\w*|\bcarec\w*|\bomit\w*|\bdesprovist\w*"
    r"|\bfalta de\b|\bque no\b"
    r"|\bno podra(?:n)? (?:superar|exceder|ser (?:menor|inferior|mayor|superior))\b"
    r"|\bgarantia\b|\bpagare\b|\bpoliza\b|\bcaucion\b")
# Lo que la oferta puede decir sobre el precio y que frena el criterio del IVA (D-257-3).
PRICE_TALK = re.compile(r"\biva\b|alicuotas?|impuestos?|tributos?|\bajust\w*|\bactualiz\w*"
                        r"|\brevis\w*|\bvariaci\w*|\bindexa\w*|\bredetermin\w*")
# Las dudas que frenan la ausencia y el IVA (D-257-2, D-257-3): el contraste no corroboró, partes sin
# leer, una cita que no se ubicó, textos que se contradicen, o una «duda» sin motivo.
DOUBTFUL = ("sin_corroborar", "lectura_incompleta", "sin_cita", "contradiccion", "duda",
            "externo", "no_se_pudo_leer")


def names_tax(text):
    """Si el texto (de una condición o del requisito) nombra el impuesto que va en el precio."""
    return bool(TAX.search(fold(text)))


def absence_form(text):
    """El nombre de la forma de la lista cerrada (`ABSENCE_FORMS`) que tiene el texto, o `""` si
    no tiene ninguna o es algo que nunca es ausencia (D-257-1)."""
    folded = fold(text)
    if _NOT_ABSENCE.search(folded):
        return ""
    return next((name for name, pattern in ABSENCE_FORMS.items() if pattern.search(folded)), "")


def by_absence(text):
    """Si el texto (del requisito o de una condición) es negativo o supletorio de la lista cerrada:
    se cumple si la oferta no dice algo en contra (decisión del 2026-10-12)."""
    return bool(absence_form(text))


def offer_citations(pair):
    """Los textos de la oferta que el sistema ubicó para el par: los del resultado, los de cada grupo
    y los de cada condición."""
    combined = pair.combined
    texts = [c.text for c in getattr(combined, "citations", None) or []]
    for group in getattr(pair, "groups", None) or []:
        texts += [c.text for c in getattr(group, "citations", None) or []]
    for item in conditions_of(pair):
        cite = item.get("cita")
        if isinstance(cite, dict) and cite.get("tipo") == "oferta":
            texts.append(cite.get("texto", ""))
    return texts


def unverified(pair):
    """Por qué no se puede verificar la ausencia ni aplicar el IVA (D-257-2, D-257-3), o `""`: el
    contraste rechazó una conclusión del modelo, la lectura está incompleta, una cita no se ubicó,
    hay una duda, un grupo concluyó, o el modelo citó un texto de la oferta (en el grupo o en una
    condición)."""
    combined = pair.combined
    if not complete(combined):
        return "la lectura de la oferta está incompleta"
    if combined.doubt in DOUBTFUL or combined.proposed:
        return "hay un texto dudoso o el contraste no corroboró una conclusión"
    if any(getattr(g, "result", "") in ("cumple", "no_cumple")
           for g in getattr(pair, "groups", None) or []):
        return "el modelo concluyó con un texto de la oferta"
    if offer_citations(pair):
        return "el modelo citó un texto de la oferta sobre el requisito"
    return ""


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
