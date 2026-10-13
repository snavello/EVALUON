"""«Cumple por ausencia, con fundamento» (REQ-104; spec 015, decisiones del 2026-10-12 «Cumple
por ausencia, con fundamento» y «En la misma fila del plazo»; ADR-0058; constitución 1.4, P3;
T-257).

Un requisito negativo (lo que la oferta no puede traer: condicionamientos, reservas) o supletorio
(rige lo del pliego si la oferta no dice otra cosa: el plazo de mantenimiento y su prórroga
automática, precios fijos) se cumple si la oferta no dice algo en contra. La regla (última del orden
de `rules.py`) propone «cumple» nombrando los documentos leídos y diciendo que ninguno lo contradice,
cuando:

- el requisito es de la **lista cerrada** de formas (`criteria.ABSENCE_FORMS`: no condicionar la
  oferta, sin reservas, precio fijo, el plazo de mantenimiento y su prórroga automática); un
  documento pedido en negativo («No se aceptarán ofertas sin…», «que carezcan / omitan /
  desprovistas de…») nunca lo es: pide el documento (verificación de T-257, D-257-1);
- **cada** condición que revisó el modelo, también la única, es de esa lista (D-257-4);
- (a) el modelo no encontró nada que la contradiga: ninguna cita de la oferta en el resultado, en
  los grupos ni en las condiciones, ningún grupo concluyó y ninguna condición dio «no cumple»;
  (b) el contraste no rechazó una conclusión del modelo: un «cumple» sin corroborar queda «no
  determinado» con su pregunta; (c) la lectura fue completa (sin páginas sin leer ni documentos
  sin lectura). Cualquier duda (una cita sin ubicar, una «duda», partes sin leer) frena la regla
  (decisión del Coordinador sobre D-257-2 y D-257-3);
- se sabe qué documentos se leyeron: la explicación los nombra y dice «ninguno lo contradice»
  solo cuando eso se verificó.

Un «cumple» que el modelo ya sostiene con su cita (la oferta dice que se formula sin reservas) no
cambia. El «cumple» por ausencia no lleva citas de la oferta (su fundamento es que ninguna lo
contradice; una cita que el contraste no corroboró no se muestra como si lo sostuviera); la cita del
pliego queda. `facts` registra el criterio, los documentos leídos, la regla y la versión de las
reglas (P6).
"""

from dataclasses import replace

from evaluon.assessment import combine, criteria

RULE = "cumple_por_ausencia"


def rule(pair, ctx):
    """La regla de `rules.py`: devuelve el resultado nuevo del par o `None`.

    T-257, verificación (D-257-1 a D-257-4, decisión del Coordinador): la ausencia rige solo si se
    cumplen las tres cosas: (a) el modelo no encontró nada que la contradiga, sin ninguna cita de la
    oferta en el resultado, en los grupos ni en las condiciones, y sin una conclusión de un grupo;
    (b) el contraste no rechazó una conclusión del modelo (un «cumple» sin corroborar queda «no
    determinado» con su pregunta); (c) la lectura está completa. El requisito y **cada** condición
    (también la única) tienen que ser de la lista cerrada de formas (`criteria.ABSENCE_FORMS`). Ante
    la duda, la regla no decide: queda el «no determinado» con su pregunta."""
    combined = pair.combined
    if combined is None or combined.outcome not in (combine.OUT_NO_DETERMINADO,
                                                    combine.OUT_SIN_DOCUMENTO):
        return None
    if combined.doubt not in ("", combine.NO_DATA):
        return None
    if not criteria.by_absence(pair.text.text):
        return None
    records = criteria.conditions_of(pair)
    if not records or criteria.contradicted(pair) or criteria.unverified(pair):
        return None
    if any(not criteria.by_absence(r.get("condicion", "")) for r in records):
        return None
    titles = criteria.documents_read(ctx)
    if not titles:
        # Sin saber qué documentos se leyeron no se puede decir que ninguno lo contradice.
        return None
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
