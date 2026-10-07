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
pares de la misma oferta que dependen de ese documento (los del mismo tema: la garantía, con su
pagaré, su póliza o su fianza) y no llegaron a una conclusión con otro documento quedan igual en
"no se pudo leer", con el mismo documento y la misma página: `facts.ilegible.propagado = True`.
Lo que depende de un documento ilegible no se puede evaluar aunque el modelo no lo haya señalado
en cada par. No se propaga a un par con conclusión (cumple o no cumple) ni a otros temas.

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


# Temas con que se decide qué pares dependen de un mismo documento (texto sin acentos).
TOPICS = {
    "garantia": re.compile(r"garantia|pagare|poliza|caucion|fianza|aval bancario"),
}


def topics_of(text):
    folded = fold(text)
    return {name for name, pattern in TOPICS.items() if pattern.search(folded)}


def collect(pairs):
    """Los documentos que el modelo señaló como ilegibles (avalados por el informe) en algún
    par, con su tema: `[{"found": {...}, "topics": {...}}]`. Se arma una vez por oferta, antes de
    aplicar las reglas."""
    flagged = []
    for pair in pairs:
        found = next((g.unreadable for g in pair.groups if g.unreadable), None)
        if found is None:
            continue
        topics = topics_of(pair.text.text)
        if topics:
            flagged.append({"found": found, "topics": topics})
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
    """El documento ilegible señalado en otro par del mismo tema, si este par depende de él."""
    mine = topics_of(pair.text.text)
    if not mine:
        return None
    for entry in getattr(ctx, "unreadable_flags", None) or []:
        if mine & entry["topics"]:
            return entry["found"]
    return None
