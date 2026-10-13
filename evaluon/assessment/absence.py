"""«Cumple por ausencia, con fundamento» (REQ-104; spec 015, decisiones del 2026-10-12 «Cumple
por ausencia, con fundamento» y «En la misma fila del plazo»; ADR-0058; constitución 1.4, P3;
T-257).

Un requisito negativo (lo que la oferta no puede traer: condicionamientos, reservas) o supletorio
(rige lo del pliego si la oferta no dice otra cosa: el plazo de mantenimiento y su prórroga
automática, precios fijos) se cumple si la oferta no dice algo en contra. La regla (última del orden
de `rules.py`) propone «cumple» nombrando los documentos leídos y diciendo que ninguno lo contradice,
cuando:

- el requisito es negativo o supletorio (`criteria.by_absence`, catálogo versionado);
- el modelo revisó sus condiciones y cada una que no cumple con su propio dato es también negativa o
  supletoria (una fila que además pide un dato, como el valor unitario, no se resuelve por
  ausencia);
- nada de la oferta lo contradice: ningún grupo ni ninguna condición concluyó «no cumple», tampoco
  uno que el contraste no corroboró (`criteria.contradicted`); si algo lo contradice, queda el
  «no cumple» del flujo de la 004, con su cita y su contraste;
- la lectura fue completa (sin páginas sin leer ni documentos sin lectura): la ausencia se verifica
  en la lectura completa de la oferta (P3);
- el modelo no dudó sobre un texto: una condición «no determinado» con una cita ubicada (hay algo
  sobre el tema, pero no alcanza) o una cita que no se ubicó (`sin_cita`) no es ausencia, y queda
  la duda con su pregunta.

Un «cumple» que el modelo ya sostiene con su cita (la oferta dice que se formula sin reservas) no
cambia. El «cumple» por ausencia no lleva citas de la oferta (su fundamento es que ninguna lo
contradice; una cita que el contraste no corroboró no se muestra como si lo sostuviera); la cita del
pliego queda. `facts` registra el criterio, los documentos leídos, la regla y la versión de las
reglas (P6).
"""

from dataclasses import replace

from evaluon.assessment import combine, criteria

RULE = "cumple_por_ausencia"


def _pending(records):
    """Las condiciones que no cumplen con su propio dato."""
    return [r for r in records if r.get("resultado") != "cumple"]


def rule(pair, ctx):
    """La regla de `rules.py`: devuelve el resultado nuevo del par o `None`."""
    combined = pair.combined
    if combined is None or combined.outcome == combine.OUT_CUMPLE:
        return None
    if combined.doubt in (combine.EXTERNAL, combine.CONTRADICTION, combine.UNREADABLE,
                          combine.NO_CITATION):
        return None
    text = pair.text.text
    if not criteria.by_absence(text) or not criteria.complete(combined):
        return None
    records = criteria.conditions_of(pair)
    if not records or criteria.contradicted(pair):
        return None
    pending = _pending(records)
    if any(not criteria.by_absence(r.get("condicion", "")) for r in pending) and len(records) > 1:
        return None
    if any(r.get("cita") for r in pending):
        # Hay un texto de la oferta sobre la condición y el modelo no pudo concluir con él.
        return None
    titles = criteria.documents_read(ctx)
    note = criteria.absence_note(titles)
    shown = []
    for item in records:
        if item.get("resultado") != "cumple":
            item = {**item, "resultado": "cumple", "por_ausencia": True}
        shown.append(item)
    return replace(
        combined, outcome=combine.OUT_CUMPLE, doubt="", question="", ask=False, proposed="",
        citations=[], portal=[], explanation=note,
        facts={**combined.facts, "regla": RULE, "condiciones": shown,
               "criterios": [criteria.record(criteria.ABSENCE, documentos_leidos=titles)]})
