"""Lo que dibuja el panel de Evi (REQ-164, REQ-165, REQ-167, REQ-168; feature 020, T-367).

Arma, para la plantilla, los siete nodos del gráfico con sus textos fijos (`textos.py`) y, con un
procedimiento abierto, el estado de cada paso y «Qué hacer acá». Nada se calcula acá por cuenta
propia: nombres y número de paso salen de `pasos.PASOS`, las uniones de `mapa.CONECTORES`, el lugar
de cada nodo de `mapa.CASILLAS` y el estado, el dato, el resumen, las tareas y las advertencias del
`Paso` que ya calculó `calculo.proceso_de` (los mismos que muestra la portada). Solo lee (REQ-169).
"""

from dataclasses import dataclass, field

from evaluon.journey.evi import textos
from evaluon.journey.proceso import mapa, pasos

PASOS = pasos.PASOS


@dataclass
class Aca:
    """«Qué hacer acá» de un paso: las frases del procedimiento abierto."""

    resumen: str = ""
    espera: str = ""
    pendientes: list = field(default_factory=list)  # los textos de las tareas, tal cual los de la portada
    avisos: list = field(default_factory=list)
    nada: bool = False  # sin nada pendiente: el paso lo dice


@dataclass
class Nodo:
    numero: int
    nombre: str
    corto: str
    columna: int  # 1 a 4
    fila: int  # 1 o 2
    textos: object
    viene: str = ""
    habilita: str = ""
    estado: str = ""  # «hecho», «en_curso», «todavia_no», «con_error»; vacío sin procedimiento
    estado_texto: str = ""
    dato: str = ""
    aqui: bool = False
    aca: object = None


def _lista(numeros):
    """«paso 3», «pasos 1 y 2», «pasos 1, 2 y 3»."""
    if not numeros:
        return ""
    if len(numeros) == 1:
        return f"paso {numeros[0]}"
    return "pasos " + ", ".join(str(n) for n in numeros[:-1]) + f" y {numeros[-1]}"


def _mayuscula(texto):
    return texto[:1].upper() + texto[1:]


def _aca(paso):
    """Las frases de «Qué hacer acá» de un `Paso` ya calculado. Mismas reglas que la lista de la portada
    (`portada._fila`): se muestran los pendientes y los cierres, y los faltantes solo si el paso no está
    hecho; una advertencia que el resumen ya dice no se repite."""
    pendientes = [t.texto for t in paso.tareas
                  if t.tipo != pasos.FALTANTE or paso.estado is not pasos.Estado.HECHO]
    avisos = [a for a in paso.advertencias if a.rstrip(".") not in paso.resumen]
    espera = ""
    if paso.espera and paso.espera not in paso.resumen:
        espera = _mayuscula(paso.espera) + "."
    return Aca(resumen=paso.resumen, espera=espera, pendientes=pendientes, avisos=avisos,
               nada=not pendientes)


def nodos(proceso=None, aqui=()):
    """Los siete nodos en orden. Con `proceso` (un `calculo.Proceso`), cada uno trae su estado, su dato y
    su «Qué hacer acá»; sin él, solo los textos fijos. `aqui`: los pasos de la pantalla abierta."""
    por_numero = {p.numero: p for p in proceso.pasos} if proceso else {}
    salida = []
    for definicion in PASOS:
        n = definicion.numero
        columna, fila = mapa.CASILLAS[n]
        nodo = Nodo(n, definicion.nombre, textos.CORTOS[n], columna + 1, fila + 1, textos.PASOS[n],
                    viene=_lista([o for o, d in mapa.CONECTORES if d == n]),
                    habilita=_lista([d for o, d in mapa.CONECTORES if o == n]),
                    aqui=n in aqui)
        paso = por_numero.get(n)
        if paso is not None:
            nodo.estado, nodo.estado_texto = paso.estado.value, paso.estado.texto
            nodo.dato, nodo.aca = paso.dato, _aca(paso)
        salida.append(nodo)
    return salida


def contexto(proceso=None, aqui=()):
    """El contexto de `journey/_evi_contenido.html`."""
    return {
        "nodos": nodos(proceso, aqui),
        "conectores": [f"{o}-{d}" for o, d in mapa.CONECTORES],
        "procedure": proceso.procedure if proceso else None,
        "aqui": list(aqui),
        "aqui_texto": ("al " if len(aqui) == 1 else "a los ") + _lista(list(aqui)),
        "primero": aqui[0] if aqui else 0,
        "circuito": {"titulo": textos.CIRCUITO_TITULO, "que_es": textos.CIRCUITO_QUE_ES,
                     "como_se_lee": textos.CIRCUITO_COMO_SE_LEE, "quien_decide": textos.CIRCUITO_QUIEN_DECIDE,
                     "para_recorrer": textos.CIRCUITO_PARA_RECORRER},
        "estados": [(e.value, e.texto) for e in pasos.Estado],
        "estados_significado": {"titulo": textos.ESTADOS_TITULO, "lista": textos.ESTADOS_SIGNIFICADO},
    }
