"""El Portal le llega al modelo como bloque citable `[P…]` (REQ-103, REQ-104; plan 015, "Flujo de IA";
ADR-0053, punto 4 bis; T-235).

Hasta ahora el modelo recibía solo los PDF de la oferta: un precio que estaba en el Portal y no en
los PDF se leía como «la oferta no incluye una cotización». Este módulo arma, con las lecturas de
`portal_facts` (tablas locales de la 012, sin red, P4), un bloque con los datos del Portal de esa
oferta (total y moneda, garantías, precios por renglón), cada uno con su alias `P1`, `P2`…, que va
en el pedido antes del requisito.

El alias es citable, pero el texto de la cita no lo escribe el modelo: lo escribe el sistema desde
las columnas del Portal (`Datum.citation()`, cita de clase Portal). Un alias que no existe se
descarta como los demás (`evaluate.py`).
"""

from evaluon.assessment import portal_facts

ALIAS_PREFIX = "P"
# Cuántos datos del Portal se le muestran al modelo como máximo (los precios por renglón pueden ser
# muchos). Los que no entran no se pueden citar; la regla del Portal los compara igual.
MAX_ITEMS = 40
HEADER = ("Datos del Portal de Compras de esta oferta (fuente oficial; se citan por su alias, el "
          "sistema escribe el texto de la cita):")

# Qué datos entran, en este orden (el CUIT lo compara la regla, no hace falta para leer la oferta).
KINDS = (portal_facts.TOTAL, portal_facts.GARANTIA, portal_facts.COTIZACION)


def alias(number):
    return f"{ALIAS_PREFIX}{number}"


def build(offer):
    """`(texto, {alias: Datum})` de los datos del Portal de la oferta. Vacío (`("", {})`) si el
    Portal no tiene datos de la oferta."""
    data = []
    for kind in KINDS:
        data.extend(portal_facts.read(offer, kind, "", []))
    data = data[:MAX_ITEMS]
    if not data:
        return "", {}
    blocks, aliased = [], {}
    for number, datum in enumerate(data, start=1):
        name = alias(number)
        aliased[name] = datum
        blocks.append(f"[{name}]\n{datum.text} ({datum.label})\n[/{name}]")
    return HEADER + "\n\n" + "\n\n".join(blocks), aliased
