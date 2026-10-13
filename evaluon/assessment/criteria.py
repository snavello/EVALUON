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

# T-257, reverificación (decisión del Coordinador, estricta): la ausencia rige solo si la ORACIÓN
# ENTERA del requisito es una de estas formas cerradas (patrones de oración completa sobre el texto
# sin acentos, sin el número de la cláusula y sin el punto final), nunca por palabras sueltas:
# - la prohibición de condicionar la oferta;
# - el plazo de mantenimiento de la oferta, con su cómputo y su prórroga automática.
_LEGAL = r"(?:(?:de acuerdo con|conforme(?: a| con)?|segun) [^.]*?, )?"
_SUBJECT = r"(?:(?:los|las|el|la) (?:oferentes?|proponentes?) )?"
# Tercera pasada (Q1, Q2, Q13): el complemento de «condicionadas a …» no admite otra exigencia
# (sin coma, sin «y»/«e», sin otro verbo de lo que pide el pliego, hasta 80 caracteres), y el plazo es
# un número (en letras o en cifras), no un texto libre.
_OTHER_VERB = (r"(?:cotiz|deber|debe|presentar|indic|inform|acompan|adjunt|ofrec|ofert|inclu|expres"
               r"|mantener|mantendr|establez|fij|consign|detall|suscrib|firm|entreg|acredit)\w*")
_COMPLEMENT = (r"(?: a (?=[a-z ]{1,80}$)(?!(?:.*\s)?(?:y|e)\s)(?!(?:.*\s)?" + _OTHER_VERB + r"\b)"
               r"[a-z ]+?)?")
_NUMBER = (r"(?:(?:uno|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece"
           r"|catorce|quince|veinte|veinticinco|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta"
           r"|noventa|cien|ciento|y) ){1,4}(?:\(\d+\) )?|\d+ ")
_DAYS = (r"(?:(?:un |el )?(?:plazo|termino|lapso) de )?(?:" + _NUMBER + r")dias"
         r"(?: corridos| habiles(?: administrativos)?)?")
_FROM = (r"(?:,? (?:contados?|computados?) (?:a partir|desde) (?:de )?(?:la fecha (?:del|de) |el |la )?"
         r"(?:acto de )?apertura(?: de (?:las )?ofertas)?|,? desde (?:la fecha (?:del|de) |el |la )?"
         r"(?:acto de )?apertura(?: de (?:las )?ofertas)?)?")
ABSENCE_FORMS = {
    "condicionar": [
        re.compile(r"no se (?:aceptaran|admitiran|consideraran|tomaran en cuenta)(?: las)? ofertas"
                   r"(?: que (?:esten|se encuentren))? condicionadas" + _COMPLEMENT),
        re.compile(r"(?:la|las) ofertas? no (?:podra|podran|debera|deberan) (?:estar|ser|encontrarse)"
                   r" condicionadas?" + _COMPLEMENT),
        re.compile(r"(?:el|los) (?:oferentes?|proponentes?) no (?:podra|podran) condicionar (?:su|sus|la"
                   r"|las) ofertas?" + _COMPLEMENT),
    ],
    "mantenimiento": [
        # el plazo de mantenimiento con su cómputo
        re.compile(_LEGAL + _SUBJECT + r"(?:(?:debera|deberan) )?(?:mantener|mantendra|mantendran)"
                   r"(?: y garantizar)?(?:, en (?:el|los) casos? que corresponda,)? (?:la validez de )?"
                   r"(?:su|sus|la|las) ofertas? (?:por|durante) " + _DAYS + _FROM),
        re.compile(r"(?:la validez de )?(?:la|las) ofertas? se mantendr(?:a|an) (?:por|durante) "
                   + _DAYS + _FROM),
        re.compile(r"el dia de (?:la )?apertura quedara excluido del computo del plazo"),
        # su prórroga automática, y la voluntad de no renovarla (que solo usa quien quiere)
        re.compile(r"(?:la|las) ofertas? se considerar(?:a|an) prorrogadas? automaticamente(?: por un"
                   r" (?:lapso|plazo|periodo) igual(?: al inicial)?)?(?: y asi sucesivamente)?"),
        re.compile(r"(?:si el oferente no manifestara [a-z ,]+?, )?se producira la prorroga"
                   r" automatica(?: por un (?:lapso|plazo|periodo) igual al inicial)?"),
        re.compile(r"si el oferente (?:quisiera|deseara|decidiera) manifestar su voluntad de no renovar"
                   r" [a-z0-9 ,()]+"),
    ],
}
_CLAUSE_NUMBER = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s*)+")
_SENTENCES = re.compile(r"(?<!\d)\.\s+(?=[a-z0-9])")
# Lo que nunca es ausencia (D-257-1): un documento pedido en negativo («no se aceptarán ofertas sin
# la constancia», «que carezcan de», «que omitan», «desprovistas de», «que no incluyan»), un tope o
# un mínimo de un valor («no podrá superar»), que se compara con un dato, y la garantía (se evalúa
# con su monto y su forma).
_NOT_ABSENCE = re.compile(
    r"\bsin (?:el|la|los|las|su|sus|un|una)\b|\bcarezc\w*|\bcarec\w*|\bomit\w*|\bdesprovist\w*"
    r"|\bfalta de\b|\bque no\b|\bdeclaracion\w*|\bcertificad\w*|\bconstancia\w*|\bformulario\w*"
    r"|\bnota\b|\bdocument\w*|\bcopia\w*|\boriginal\w*|\bplanilla\w*|\bacompan\w*|\badjunt\w*"
    r"|\bindiqu\w*|\bindicar\w*|\binform\w*|\bconsign\w*|\bdetall\w*|\bpresentar\b"
    r"|\bpresentacion\b|\bsuscri\w*|\bfirm\w*|\bentreg\w*|\bmesa de entradas?\b"
    r"|\bno podra(?:n)? (?:superar|exceder|ser (?:menor|inferior|mayor|superior))\b"
    r"|\bgarantia\b|\bpagare\b|\bpoliza\b|\bcaucion\b")
# Lo que la oferta puede decir sobre el precio y que frena el criterio del IVA (D-257-3).
PRICE_TALK = re.compile(r"\biva\b|alicuotas?|impuestos?|tributos?|\bajust\w*|\bactualiz\w*"
                        r"|\brevis\w*|\bvariaci\w*|\bindexa\w*|\bredetermin\w*|\bnet[oa]s?\b"
                        r"|\bgravad\w*|\bgravamen\w*|\bgravar\w*|\bexent\w*|\bpercepci\w*"
                        r"|\bretenci\w*")
# «I.V.A.», «I. V. A.»: la sigla con puntos se lee como «iva» antes de buscar (tercera pasada, Q7).
_DOTTED_VAT = re.compile(r"\bi\s*\.\s*v\s*\.\s*a\b\.?")


def _talks_about_price(text):
    folded = _DOTTED_VAT.sub("iva", fold(text))
    return bool(PRICE_TALK.search(folded))


def price_talk(pair, ctx=None):
    """Si la oferta dice algo sobre el impuesto o sobre el precio («netos», «sin IVA», «más IVA»,
    «se ajustarán»): en sus documentos (si están a mano), en lo que el modelo citó y en el dato o la
    explicación del modelo. Con eso el precio del Portal no se presume final con IVA (reverificación
    de T-257, decisión del Coordinador)."""
    texts = list(offer_citations(pair))
    texts += [r.get("dato") or "" for r in conditions_of(pair)]
    offer_text = getattr(ctx, "offer_text", None) if ctx is not None else None
    for document in getattr(offer_text, "documents", None) or []:
        for page in getattr(document, "pages", None) or []:
            texts.append(page.get("text", "") if isinstance(page, dict)
                         else getattr(page, "text", ""))
    return any(_talks_about_price(t) for t in texts if t)
# Las dudas que frenan la ausencia y el IVA (D-257-2, D-257-3): el contraste no corroboró, partes sin
# leer, una cita que no se ubicó, textos que se contradicen, o una «duda» sin motivo.
DOUBTFUL = ("sin_corroborar", "lectura_incompleta", "sin_cita", "contradiccion", "duda",
            "externo", "no_se_pudo_leer")


def names_tax(text):
    """Si el texto (de una condición o del requisito) nombra el impuesto que va en el precio."""
    return bool(TAX.search(fold(text)))


def _sentences(text):
    """Las oraciones del texto, sin acentos, sin el número de cláusula, sin comillas y sin el punto
    final."""
    folded = fold(text).replace("«", "").replace("»", "").replace('"', "")
    out = []
    for part in _SENTENCES.split(folded):
        part = _CLAUSE_NUMBER.sub("", part).strip().rstrip(".;").strip()
        if part:
            out.append(" ".join(part.split()))
    return out


def absence_form(text):
    """El nombre de la forma cerrada (`ABSENCE_FORMS`) que tiene **cada** oración del texto, o `""`
    si alguna oración no es una forma de la lista, si mezcla dos formas, o si nombra un documento o
    un dato (`_NOT_ABSENCE`). Patrones de oración completa, no palabras sueltas."""
    folded = fold(text)
    if _NOT_ABSENCE.search(folded):
        return ""
    found = set()
    sentences = _sentences(text)
    if not sentences:
        return ""
    for sentence in sentences:
        names = [name for name, patterns in ABSENCE_FORMS.items()
                 if any(pattern.fullmatch(sentence) for pattern in patterns)]
        if not names:
            return ""
        found.add(names[0])
    return found.pop() if len(found) == 1 else ""


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
