"""Los tres cuadros de indicadores que abren cada sección y el primer panel (T-337; REQ-126,
REQ-129, REQ-132, REQ-141; plan 017). Van arriba de los mosaicos de la sección y, como ellos, se
abren con un clic en un detalle debajo de su fila (`Tile` y `Detail` de `tiles.py`; `tablero.js`):

- **Qué hay y qué falta**: «Hay: …» y «Falta: …» en corto; el detalle lleva el resumen completo y
  cada faltante con su acción (`_hay_falta.html`).
- **Pendientes de decidir**: la cifra total y, si las filas agrupan varios pendientes, cuántos
  grupos son; el detalle lista las filas, cada una con cuántos pendientes suma.
- **Sugerencias del sistema**: su cifra; el detalle, la lista.

Solo usan lo que la vista ya calculó (`Section.pending`, `suggestions`, `summary`, `tema_missing`
y los renglones de pendientes): ninguna consulta nueva. Un cero es un dato y lo que no hay se dice
(REQ-141). Solo lee: las decisiones siguen en las acciones de cada renglón (P3).
"""

import re

from evaluon.journey.tablero.tiles import Detail, Tile

KEY_HAY_FALTA = "hay-falta"
KEY_PENDING = "pendientes"
KEY_SUGGESTIONS = "sugerencias"
DETAIL_HAY_FALTA = "d-hay-falta"
DETAIL_PENDING = "d-pendientes"
DETAIL_SUGGESTIONS = "d-sugerencias"

SHORT_TEXT = 70  # letras de un renglón del cuadro; el resto va al detalle
SHORT_MISSING = 2  # faltantes que el cuadro nombra; los demás, «y N más»


def _cut(text, limit=SHORT_TEXT):
    """El texto en una línea: sin el punto final y, si pasa de `limit`, cortado en una palabra."""
    text = " ".join(str(text).split()).rstrip(". ")
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;: ") + "…"


def _first_sentence(text):
    return re.split(r"(?<=[a-záéíóúñ0-9\)»])\.\s", " ".join(str(text).split()), maxsplit=1)[0]


def short_hay(summary):
    """«Hay» en corto: la primera oración de cada parte del resumen, unidas con « · »."""
    parts = [_cut(_first_sentence(detail)) for _, detail in summary if str(detail).strip()]
    return " · ".join(p for p in parts if p) or "nada todavía"


def _without_falta(text):
    text = str(text).strip()
    for prefix in ("Falta ", "Faltan "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text[:1].upper() + text[1:]


_PER_OFFER = re.compile(r"^Oferta (\d+) \(.*?\): (.+)$")


def _collapse(texts):
    """Los faltantes que repiten la misma cosa en varias ofertas («Oferta 1 (…): falta la hoja de
    compliance», «Oferta 2 (…): …») pasan a una sola línea con la cuenta: «La hoja de compliance
    de 2 ofertas». Lo demás queda como está."""
    per_offer, order = {}, []
    for text in texts:
        found = _PER_OFFER.match(text)
        key = found.group(2) if found else text
        if key not in per_offer:
            per_offer[key] = []
            order.append((key, bool(found)))
        if found:
            per_offer[key].append(found.group(1))
    collapsed = []
    for key, is_offer in order:
        offers = per_offer[key]
        if not is_offer:
            collapsed.append(key)
        elif len(offers) == 1:
            collapsed.append(f"{_without_falta(key)} de la oferta {offers[0]}")
        else:
            collapsed.append(f"{_without_falta(key)} de {len(offers)} ofertas")
    return collapsed


def short_falta(missing):
    """«Falta» en corto: los dos primeros faltantes sin su «Falta» inicial y, si hay más, «y N
    más». Sin faltantes, «nada»."""
    texts = [" ".join(str(one.text).split()) for one in missing if str(one.text).strip()]
    found = [_cut(_without_falta(text)) for text in _collapse(texts)]
    if not found:
        return "nada"
    shown = " · ".join(found[:SHORT_MISSING])
    more = len(found) - SHORT_MISSING
    return shown + (f" y {more} más" if more > 0 else "")


def hay_falta_tile(summary, missing):
    """El cuadro «Qué hay y qué falta»."""
    return Tile(key=KEY_HAY_FALTA, title="Qué hay y qué falta", detail=DETAIL_HAY_FALTA, width=2,
                lines=(("Hay", short_hay(summary)), ("Falta", short_falta(missing))))


def _groups_sub(total, rows, quiet):
    count = len(rows)
    if not total:
        return quiet
    if count < total:
        return f"en {count} {'grupo' if count == 1 else 'grupos'}"
    return "uno por uno"


def pending_tile(total, rows):
    """El cuadro «Pendientes de decidir»: la cifra total y, si hay filas que agrupan, en cuántos
    grupos. Cero es un dato."""
    return Tile(key=KEY_PENDING, title="Pendientes de decidir", detail=DETAIL_PENDING, big=total,
                sub=_groups_sub(total, rows, "Nada espera una decisión"))


def suggestion_tile(total, rows):
    """El cuadro «Sugerencias del sistema»."""
    return Tile(key=KEY_SUGGESTIONS, title="Sugerencias del sistema", detail=DETAIL_SUGGESTIONS,
                big=total, sub=_groups_sub(total, rows, "Sin sugerencias por ahora"))


# --- De dónde sale cada dato ----------------------------------------------------------------------


def _source(section, contexts):
    """Totales y renglones del cuadro: los de la sección o, en el primer panel, los de las cinco
    (el contexto del ingreso, `tablero/ingreso.py`)."""
    own = (contexts or {}).get("ingreso") or {}
    if getattr(section, "ingreso_template", None) and "pending_items" in own:
        return {"pending_total": own["pending_total"], "pending_rows": own["pending_items"],
                "suggestion_total": own["suggestion_total"],
                "suggestion_rows": own["suggestion_items"], "show_section": True}
    return {"pending_total": section.pending,
            "pending_rows": [(section, i) for i in section.pending_items],
            "suggestion_total": section.suggestions,
            "suggestion_rows": [(section, i) for i in section.suggestion_items],
            "show_section": False}


def tiles(section, contexts=None):
    """Los tres cuadros de `section`, en su orden."""
    found = _source(section, contexts)
    return [hay_falta_tile(section.summary, section.tema_missing),
            pending_tile(found["pending_total"], found["pending_rows"]),
            suggestion_tile(found["suggestion_total"], found["suggestion_rows"])]


def details(section, contexts=None):
    """Los detalles de esos cuadros. El de Hay/Falta lee `section` de la página; los otros dos,
    sus renglones."""
    found = _source(section, contexts)
    return [
        Detail(DETAIL_HAY_FALTA, "Qué hay y qué falta", "journey/_hay_falta.html"),
        Detail(DETAIL_PENDING, "Pendientes de decidir", "journey/_detalle_pendientes.html", found),
        Detail(DETAIL_SUGGESTIONS, "Sugerencias del sistema", "journey/_detalle_sugerencias.html",
               found)]
