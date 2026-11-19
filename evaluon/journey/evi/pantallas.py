"""Qué paso o pasos resuelve cada pantalla (REQ-165; feature 020, T-367).

Cada pantalla de un procedimiento se declara acá por el nombre de su ruta. El punto de partida es
`pasos.DESTINOS` (dónde se resuelve cada paso): de ahí salen los pasos de cada pantalla, así que
una pantalla que cambie de lugar en `DESTINOS` cambia también acá. La portada del procedimiento
(la lista de los siete pasos) marca los mismos que «Indicadores», el primer panel (1 y 5); el par
que se abre desde el cuadro de cumplimiento marca los del cuadro (4 y 6).

Las pantallas de un procedimiento que no resuelven ningún paso (las normativas del procedimiento)
quedan con la tupla vacía: Evi muestra los estados pero no marca ninguno. Las pantallas sin
procedimiento (el inicio, el alta, las normativas generales, la consulta, el perfil) no figuran.
No consulta la base: sólo mira el nombre de la ruta.
"""

from evaluon.journey.proceso import pasos

NAMESPACE = "expedientes"


def _pasos_de(ruta):
    """Los pasos que `DESTINOS` resuelve en la pantalla `expedientes:<ruta>`."""
    return tuple(n for n, (r, _) in pasos.DESTINOS.items() if r == ruta)


# Nombre de ruta (dentro de `expedientes:`) -> pasos que se resuelven ahí.
PANTALLAS = {
    "portada": _pasos_de("procedimiento"),
    "procedimiento": _pasos_de("procedimiento"),
    "pliego": _pasos_de("pliego"),
    "ofertas": _pasos_de("ofertas"),
    "cuadro": _pasos_de("cuadro"),
    "s4_par": _pasos_de("cuadro"),
    "evaluacion": _pasos_de("evaluacion"),
    "normativas": (),
}


def de_la_ruta(match):
    """`(procedure_id, pasos)` de la ruta resuelta de un pedido: `procedure_id` es `None` si la pantalla no
    cuelga de un procedimiento (entonces `pasos` está vacío). Sin consultas."""
    if match is None or match.namespace != NAMESPACE:
        return None, ()
    procedure_id = match.kwargs.get("procedure_id")
    if procedure_id is None:
        return None, ()
    return procedure_id, PANTALLAS.get(match.url_name, ())


def pasos_pedidos(texto):
    """Los pasos de `?pasos=1,5`: enteros de 1 a 7, sin repetir y en orden; lo demás se ignora."""
    salida = set()
    for parte in (texto or "").split(","):
        parte = parte.strip()
        if parte.isdigit() and 1 <= int(parte) <= 7:
            salida.add(int(parte))
    return tuple(sorted(salida))
