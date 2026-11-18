"""Geometría constante del mapa del proceso y hitos de la línea de plazos (REQ-158, ADR-0080).

Solo constantes y funciones puras: sin consultas, sin plantillas. El grafo es fijo (siete
tarjetas, ocho dependencias); lo que cambia es el estado y las tareas, que salen de `Proceso`.
Las posiciones de `mapa.css` (clases `pos-1` … `pos-7`) repiten estos números y un test las
compara. Las coordenadas están en píxeles del lienzo, con el origen arriba a la izquierda.

Disposición (T-363, decisión del responsable del 2026-11-18: «Tarjetas más anchas y a medida»):
cuatro columnas de 252 px, con huecos de 32, y dos carriles. El carril de arriba es el camino principal (1 → 2 → 4 → 7);
el de abajo lleva lo que se bifurca (3, 5 y 6). Cada tarjeta mide lo que ocupa su contenido y crece
hacia abajo desde su `y`; por eso los conectores entran y salen a `SALIDA_Y` del borde superior, un punto
que el alto no mueve, y las posiciones se calculan con el alto MÁXIMO posible de una tarjeta
(`ALTO_MAXIMO`, la suma de `PRESUPUESTO`): ni dos tarjetas ni un conector y una tarjeta se pisan
aunque todas lleguen a ese máximo.

Tres formas de conector, todas con codos redondeados:
- recto: mismo `y` (1→2, 2→4, 4→7, 3→5);
- codo entre columnas distintas, por el medio del hueco que las separa (3→4 sube, 4→6 baja);
- lazo en la misma columna (4→5, 6→7): sale por el borde derecho, baja o sube por el hueco de la
  derecha y vuelve a entrar por el borde derecho del destino, con la punta hacia la izquierda.
"""

from dataclasses import dataclass

ANCHO = 252
HUECO = 32  # entre dos columnas; también el aire a la derecha del lienzo, donde pasan los lazos
MARGEN = 8
X_COLUMNA = tuple(MARGEN + i * (ANCHO + HUECO) for i in range(4))  # 8, 292, 576, 860
SEPARACION_CARRILES = 14

# Presupuesto de alto de una tarjeta (px): el caso más alto que puede darse. Nombre del paso en
# dos líneas, dato en dos líneas, tres tareas de dos líneas, la etiqueta «Vence hoy» o «Vencido» de
# UNA tarea (solo una acción por paso puede llevarla: `vencimientos.marca_de`) y el renglón de
# «+ N más» con las advertencias. Los números repiten los de `mapa.css`; un test los recalcula.
PRESUPUESTO = (("borde y relleno", 22), ("encabezado (nombre en 2 líneas)", 32), ("dato (2 líneas)", 36),
               ("estado", 30), ("tareas (3 × 2 líneas)", 8 + 3 * 41), ("etiqueta de una tarea", 19),
               ("«+ N más» y advertencias", 27))
ALTO_MAXIMO = sum(alto for _, alto in PRESUPUESTO)  # 297
PRESUPUESTO_ALTO = ALTO_MAXIMO

Y_ARRIBA = MARGEN
Y_ABAJO = Y_ARRIBA + ALTO_MAXIMO + SEPARACION_CARRILES
LIENZO = (X_COLUMNA[3] + ANCHO + HUECO, Y_ABAJO + ALTO_MAXIMO + MARGEN)  # (ancho, alto)
POSICIONES = {1: (X_COLUMNA[0], Y_ARRIBA), 2: (X_COLUMNA[1], Y_ARRIBA), 3: (X_COLUMNA[1], Y_ABAJO),
              4: (X_COLUMNA[2], Y_ARRIBA), 5: (X_COLUMNA[2], Y_ABAJO), 6: (X_COLUMNA[3], Y_ABAJO),
              7: (X_COLUMNA[3], Y_ARRIBA)}  # esquina superior izquierda (x, y)
COLUMNAS = (("Publicación", X_COLUMNA[0]), ("Requisitos y ofertas", X_COLUMNA[1]),
            ("Cruce y comparación", X_COLUMNA[2]), ("Evaluación y dictamen", X_COLUMNA[3]))
CONECTORES = ((1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7))

SALIDA_Y = 24  # el conector sale y entra a esta altura desde el borde superior de la tarjeta
RADIO = 8  # radio del codo
PUNTA = 8  # largo de la punta de flecha
PUNTA_MEDIO_ANCHO = 4

# Ancho mínimo de la ventana para ver el lienzo entero: el lienzo, el relleno de la caja del mapa
# (2 × 16), los márgenes de la página (2 × 36: el contenido llega a 1176 px y no crece más) y una barra
# de desplazamiento clásica (15). Con ventanas más anchas el lienzo ocupa justo el ancho de la caja.
VENTANA_MINIMA = LIENZO[0] + 2 * 16 + 2 * 36 + 15


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
    """El conector de la tarjeta `origen` a la `destino`. Sale del borde derecho a `y + SALIDA_Y`.
    Si el destino está en otra columna, entra por su borde izquierdo a `y + SALIDA_Y` (recto si es
    el mismo `y`; si no, con un codo de radio `RADIO` por el medio del hueco). Si está en la misma
    columna, hace un lazo por el hueco de la derecha y entra por el borde derecho, con la punta
    hacia la izquierda."""
    ox, oy = POSICIONES[origen]
    dx, dy = POSICIONES[destino]
    x0, y0 = ox + ANCHO, oy + SALIDA_Y
    y1 = dy + SALIDA_Y
    sentido = 1 if y1 > y0 else -1
    if dx == ox:  # lazo: vuelve a entrar por el borde derecho
        x1 = dx + ANCHO
        xm = x0 + HUECO // 2
        punta = ((x1, y1), (x1 + PUNTA, y1 - PUNTA_MEDIO_ANCHO), (x1 + PUNTA, y1 + PUNTA_MEDIO_ANCHO))
        d = (f"M {_n(x0)} {_n(y0)} H {_n(xm - RADIO)} Q {_n(xm)} {_n(y0)} {_n(xm)} {_n(y0 + sentido * RADIO)} "
             f"V {_n(y1 - sentido * RADIO)} Q {_n(xm)} {_n(y1)} {_n(xm - RADIO)} {_n(y1)} H {_n(x1)}")
        tramos = (((x0, y0), (xm, y0)), ((xm, y0), (xm, y1)), ((xm, y1), (x1, y1)))
        return Conector(origen, destino, d, punta, tramos)
    x1 = dx
    punta = ((x1, y1), (x1 - PUNTA, y1 - PUNTA_MEDIO_ANCHO), (x1 - PUNTA, y1 + PUNTA_MEDIO_ANCHO))
    if y0 == y1:
        return Conector(origen, destino, f"M {_n(x0)} {_n(y0)} H {_n(x1)}", punta,
                        (((x0, y0), (x1, y1)),))
    xm = (x0 + x1) / 2
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
