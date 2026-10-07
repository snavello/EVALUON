"""No se pudo leer (REQ-064; plan 004, "No se pudo leer"; ADR-0043; T-166).

El **informe de lectura** (las páginas «no se pudo leer» que quedan después de la lectura con
visión, `offers/vision.py`) dice qué páginas no se leyeron; no lo decide el modelo. Para atar una
página ilegible a un requisito, el modelo devuelve el campo `ilegible` con el alias del
documento que **debería** responder el requisito pero tiene una página marcada «no se pudo
leer». El sistema comprueba que ese documento figure en el informe como no leído (`resolve`):

- si figura, el resultado del par es "no determinado" con el motivo `no_se_pudo_leer`, con
  `facts.ilegible = {documento, pagina}` y la pregunta fija de abajo; lo verifica la Comisión
  contra el original (decisión literal: «lo del pagare es ilegible se informa asi y ese si lo
  chequea la comision»);
- si no figura, el alias se descarta con una anomalía y el par sigue su camino (la regla de
  `combine.py` lo deja en `lectura_incompleta`).

**Propagación (T-172, H-4).** Si el modelo señaló un documento ilegible en un par, los demás
pares de la misma oferta que dependen de ese documento (los que nombran la misma forma de
garantía, pagaré con pagaré o póliza con póliza, o la misma obligación, y ninguna distinta: una
«garantía técnica», «de fábrica», «de impugnación» o «de cumplimiento» no lo recibe) y no llegaron a una conclusión con otro documento quedan igual en
"no se pudo leer", con el mismo documento y la misma página: `facts.ilegible.propagado = True`.
Lo que depende de un documento ilegible no se puede evaluar aunque el modelo no lo haya señalado
en cada par. No se propaga a un par con conclusión (cumple o no cumple) ni a otros documentos.

Un documento ilegible no es un documento ausente: no se mezcla con "no se encontró el
documento". Una conclusión con cita ubicada en otro documento no se pisa.
"""

import re
from dataclasses import replace

from evaluon.assessment import combine
from evaluon.assessment.externals import fold

RULE = "ilegible_informe"
ANOMALY_NOT_BACKED = "ilegible_no_avalado"


def resolve(piece, unread):
    """`{documento, documento_id, archivo, pagina, paginas}` si el informe de lectura avala que
    el documento de `piece` tiene páginas sin leer; `None` si no. `unread` es la lista de
    páginas sin leer de la oferta (`OfferText.unread`). Si el documento se leyó por ventanas,
    se prefiere una página de la ventana que se le mostró al modelo."""
    document = piece.doc.document
    pages = sorted(u["page"] for u in unread if u["document"] == document.pk)
    if not pages:
        return None
    if piece.windowed:
        inside = [p for p in pages if piece.first_page <= p <= piece.last_page]
        first = (inside or pages)[0]
    else:
        first = pages[0]
    return {"documento": document.title, "documento_id": document.pk,
            "archivo": document.file_name, "pagina": first, "paginas": pages}


# Qué documento de garantía nombra un texto (texto sin acentos): la forma (pagaré, póliza,
# fianza, aval) y la obligación a la que sirve. Se propaga por el documento, no por la palabra
# «garantía» (T-172, H-B).
FORMS = {
    "pagare": re.compile(r"\bpagares?\b"),
    "poliza": re.compile(r"\bpolizas?\b|\bcaucion\b|seguros? de caucion"),
    "fianza": re.compile(r"\bfianzas?\b"),
    "aval": re.compile(r"\baval(?:es)? bancarios?\b|\bcarta de credito\b"),
}
GUARANTEE = re.compile(r"garantia|pagare|poliza|caucion|fianza|aval bancario")
OBLIGATIONS = {
    # La garantía que se integra con la oferta.
    "oferta": re.compile(r"mantenimiento de (?:la )?oferta|(?:con|presentar(?:se)?|presentacion de)"
                         r" (?:la )?oferta"),
    "cumplimiento": re.compile(r"cumplimiento (?:del? )?contrato|cumplimiento del contrato"),
    "impugnacion": re.compile(r"impugnacion"),
    "tecnica": re.compile(r"garantia (?:tecnica|de fabrica|del fabricante|del bien|de calidad"
                          r"|de funcionamiento)"),
}


def forms_of(text):
    folded = fold(text)
    return {name for name, pattern in FORMS.items() if pattern.search(folded)}


def obligations_of(text):
    folded = fold(text)
    if not GUARANTEE.search(folded):
        return set()
    return {name for name, pattern in OBLIGATIONS.items() if pattern.search(folded)}


def depends_on(mine, other):
    """El texto `mine` depende del mismo documento que `other` (ambos: `(formas, obligaciones)`):
    nombra la misma forma de garantía o la misma obligación, y no sirve a una obligación
    distinta de la del documento señalado."""
    forms, obligations = mine
    other_forms, other_obligations = other
    if obligations and other_obligations and not obligations & other_obligations:
        return False
    return bool(forms & other_forms or obligations & other_obligations)


def kinds_of(text):
    return forms_of(text), obligations_of(text)


def collect(pairs):
    """Los documentos que el modelo señaló como ilegibles (avalados por el informe) en algún
    par, con sus formas y obligaciones: `[{"found": {...}, "kinds": (...)}]`. Se arma una vez por oferta, antes de
    aplicar las reglas."""
    flagged = []
    for pair in pairs:
        found = next((g.unreadable for g in pair.groups if g.unreadable), None)
        if found is None:
            continue
        kinds = kinds_of(pair.text.text)
        if kinds[0] or kinds[1]:
            flagged.append({"found": found, "kinds": kinds})
    return flagged


def question(where):
    """La pregunta fija a la Comisión (REQ-064)."""
    return (f"¿Lo que exige este requisito está en la página {where['pagina']} de "
            f"«{where['documento']}»? Hay que revisar el original.")


def rule(pair, ctx):
    """La regla 3 de `rules.py`: devuelve el resultado nuevo del par o `None`. Solo rige si el
    par no llegó a una conclusión (cumple o no cumple) ni a una contradicción entre
    documentos."""
    combined = pair.combined
    if combined.outcome in (combine.OUT_CUMPLE, combine.OUT_NO_CUMPLE):
        return None
    if combined.doubt == combine.CONTRADICTION:
        return None
    found = next((g.unreadable for g in pair.groups if g.unreadable), None)
    propagated = False
    if found is None:
        found = _propagated(pair, ctx)
        propagated = found is not None
    if found is None:
        return None
    note = (f"No se pudo leer la página {found['pagina']} de «{found['documento']}», que "
            "podría responder este requisito.")
    return replace(
        combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.UNREADABLE,
        explanation=note, question=question(found),
        facts={**combined.facts, "regla": RULE,
               "ilegible": {"documento": found["documento"], "pagina": found["pagina"],
                            "documento_id": found["documento_id"],
                            "archivo": found["archivo"], "paginas": found["paginas"],
                            **({"propagado": True} if propagated else {})}})


def _propagated(pair, ctx):
    """El documento ilegible señalado en otro par, si este par depende del mismo documento."""
    mine = kinds_of(pair.text.text)
    if not (mine[0] or mine[1]):
        return None
    for entry in getattr(ctx, "unreadable_flags", None) or []:
        if depends_on(mine, entry["kinds"]):
            return entry["found"]
    return None
