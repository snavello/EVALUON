"""Geometría constante del mapa del proceso y hitos de la línea de plazos (REQ-158, ADR-0080).

Solo constantes y funciones puras: sin consultas, sin plantillas. El grafo es fijo (siete
tarjetas, ocho dependencias); lo que cambia es el estado y las tareas, que salen de `Proceso`.
Las posiciones de `mapa.css` (clases `pos-1` … `pos-7`) repiten estos números y un test las
compara. Las coordenadas están en píxeles del lienzo, con el origen arriba a la izquierda.
"""

from dataclasses import dataclass

LIENZO = (1130, 740)  # (ancho, alto)
ANCHO = 172
ALTO = 240  # el mismo para las siete tarjetas
POSICIONES = {1: (10, 140), 2: (245, 140), 3: (245, 490), 4: (480, 250),
              5: (715, 490), 6: (715, 10), 7: (950, 250)}  # esquina superior izquierda (x, y)
COLUMNAS = (("Publicación", 10), ("Requisitos y ofertas", 245), ("Cruce", 480),
            ("Análisis y decisión", 715), ("Cierre", 950))
CONECTORES = ((1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7))

SALIDA_Y = 28  # el conector sale y entra a esta altura desde el borde superior de la tarjeta
RADIO = 12  # radio del codo
PUNTA = 8  # largo de la punta de flecha
PUNTA_MEDIO_ANCHO = 4

# Presupuesto de alto de una tarjeta: todo lo que crece se recorta o va a la lista.
PRESUPUESTO = (("relleno", 22), ("encabezado", 36), ("dato", 34), ("pie con estado", 30),
               ("tareas (3 × 30)", 3 * 30), ("+ N más", 26))
PRESUPUESTO_ALTO = sum(alto for _, alto in PRESUPUESTO)  # 238 ≤ ALTO


@dataclass(frozen=True)
class Conector:
    origen: int
    destino: int
    d: str  # trazo del <path> (con codo redondeado)
    punta: tuple  # tres puntos (x, y) del triángulo; el primero es la punta
    tramos: tuple  # segmentos rectos ((x1, y1), (x2, y2)) del recorrido, sin redondear


def _n(valor):
    return f"{valor:g}"


def trazo(origen, destino):
    """El conector de la tarjeta `origen` a la `destino`: sale del borde derecho a `y + 28`,
    hace un codo de radio 12 en el medio del hueco entre las dos columnas y entra por el borde
    izquierdo a `y + 28`, con punta de flecha."""
    ox, oy = POSICIONES[origen]
    dx, dy = POSICIONES[destino]
    x0, y0 = ox + ANCHO, oy + SALIDA_Y
    x1, y1 = dx, dy + SALIDA_Y
    punta = ((x1, y1), (x1 - PUNTA, y1 - PUNTA_MEDIO_ANCHO), (x1 - PUNTA, y1 + PUNTA_MEDIO_ANCHO))
    if y0 == y1:
        return Conector(origen, destino, f"M {_n(x0)} {_n(y0)} H {_n(x1)}", punta,
                        (((x0, y0), (x1, y1)),))
    xm = (x0 + x1) / 2
    sentido = 1 if y1 > y0 else -1
    d = (f"M {_n(x0)} {_n(y0)} H {_n(xm - RADIO)} Q {_n(xm)} {_n(y0)} {_n(xm)} {_n(y0 + sentido * RADIO)} "
         f"V {_n(y1 - sentido * RADIO)} Q {_n(xm)} {_n(y1)} {_n(xm + RADIO)} {_n(y1)} H {_n(x1)}")
    tramos = (((x0, y0), (xm, y0)), ((xm, y0), (xm, y1)), ((xm, y1), (x1, y1)))
    return Conector(origen, destino, d, punta, tramos)


# Calculados una vez al importar el módulo.
TRAZOS = tuple(trazo(o, d) for o, d in CONECTORES)

SEPARACION = 12.0  # a menos de este % de distancia, el segundo hito baja un nivel


@dataclass(frozen=True)
class Hito:
    key: str
    etiqueta: str
    texto: str  # «21/11»
    posicion: float  # 0 a 100, proporcional a la fecha
    nivel: int  # 0 = sobre el eje; 1 = segundo nivel
    estado: str  # past | now | future | pending
    nota: str = ""


@dataclass(frozen=True)
class SinFecha:
    key: str
    etiqueta: str
    motivo: str


@dataclass(frozen=True)
class Eje:
    hitos: tuple
    sin_fecha: tuple


def hitos_en_eje(events):
    """Pone los hitos con fecha sobre el eje en proporción a la fecha (del primer al último día,
    «hoy» incluido). Si dos quedan a menos de 12 % uno del otro, el segundo baja un nivel. Los
    hitos sin fecha no se dibujan: van aparte, con su motivo. `events` son los `Terms` de
    `tablero.ingreso.plazos()` (key, label, day, date_text, state, note)."""
    con_fecha = [e for e in events if e.day is not None]
    sin_fecha = tuple(SinFecha(e.key, e.label, e.note or e.date_text) for e in events if e.day is None)
    if not con_fecha:
        return Eje((), sin_fecha)
    primero = min(e.day for e in con_fecha)
    total = (max(e.day for e in con_fecha) - primero).days
    puestos, ocupados = [], []  # ocupados: (posición, nivel) de los ya puestos
    for e in sorted(con_fecha, key=lambda e: e.day):  # estable: a igual fecha, el orden dado
        pos = 50.0 if total == 0 else round((e.day - primero).days / total * 100, 2)
        nivel = 0
        while any(n == nivel and abs(pos - p) < SEPARACION for p, n in ocupados):
            nivel += 1
        ocupados.append((pos, nivel))
        etiqueta = f"Hoy · {e.date_text}" if e.key == "hoy" else e.label
        puestos.append(Hito(e.key, etiqueta, e.date_text, pos, nivel, e.state, e.note))
    return Eje(tuple(puestos), sin_fecha)
