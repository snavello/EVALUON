"""Geometría del mapa del proceso y hitos de la línea de plazos (REQ-158, ADR-0080 y su enmienda de T-363).

Solo constantes y funciones puras: sin consultas, sin plantillas. El grafo es fijo (siete tarjetas,
ocho dependencias); lo que cambia es el estado y las tareas, que salen de `Proceso`. Las posiciones de
`mapa.css` (clases `pos-N`, `fila-b-N`, `alto-b-N`) repiten estos números y un test las compara. Las
coordenadas están en píxeles del lienzo, con el origen arriba a la izquierda.

Disposición (T-363): cuatro columnas de 252 px, con huecos de 32, y dos filas; se lee de izquierda a
derecha y de arriba abajo, y termina en Dictamen, abajo a la derecha:

    fila de arriba:  1 ──► 2 ──────────► 4 ──► 6
    fila de abajo:   3 ·········(libre)···► 5     7      (3→5 pasa por debajo de la tarjeta 2)

Cada tarjeta mide lo que ocupa su contenido y crece hacia abajo desde su `y`; por eso los conectores
entran y salen a `SALIDA_Y` del borde superior, un punto que el alto no mueve. Lo único que depende del
contenido es DÓNDE EMPIEZA la fila de abajo y cuánto mide el lienzo: `alto_estimado` calcula, con
anchos de letra prudentes, el alto máximo que puede tener cada tarjeta; la fila de arriba se redondea
hacia arriba al próximo de `ESCALONES` (`fila-b-N`) y la de abajo igual (`alto-b-N`). Como el alto
estimado es siempre mayor o igual que el real, ni dos tarjetas ni un conector y una tarjeta se pisan.
`geometria(k, m)` devuelve posiciones, lienzo y conectores para un par de escalones; es determinista.

Formas de conector, todas con codos redondeados:
- recto (mismo `y`): 1→2, 2→4, 4→6 y 3→5;
- codo por el hueco que precede a la columna de destino: 3→4 (sube) y 4→7 (baja);
- lazo en la misma columna (4→5, 6→7): sale por el borde derecho, baja por el hueco de la derecha y
  entra por el borde derecho de la tarjeta de abajo, con la punta hacia la izquierda; 4→5 y 4→7 comparten
  el tronco y se bifurcan abajo (una flecha hacia 5 y otra hacia 7).
"""

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from math import ceil

ANCHO = 252
HUECO = 32  # entre dos columnas; también el aire a la derecha del lienzo, donde pasa el lazo 6→7
MARGEN = 8
X_COLUMNA = tuple(MARGEN + i * (ANCHO + HUECO) for i in range(4))  # 8, 292, 576, 860
ANCHO_LIENZO = X_COLUMNA[3] + ANCHO + HUECO  # 1144
Y_ARRIBA = MARGEN
SEPARACION_FILAS = 16  # entre el alto estimado de la fila de arriba y el comienzo de la de abajo
# (columna, fila) de cada tarjeta: fila 0 arriba, fila 1 abajo
CASILLAS = {1: (0, 0), 2: (1, 0), 3: (0, 1), 4: (2, 0), 5: (2, 1), 6: (3, 0), 7: (3, 1)}
FILA_ARRIBA = (1, 2, 4, 6)
FILA_ABAJO = (3, 5, 7)
CONECTORES = ((1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7))

# Altos de fila que se pueden elegir (px): de una tarjeta casi vacía a una de tres tareas de tres líneas
# con etiquetas. Un alto estimado mayor que el último se queda en el último.
ESCALONES = tuple(range(120, 433, 24))

SALIDA_Y = 24  # el conector sale y entra a esta altura desde el borde superior de la tarjeta
RADIO = 8  # radio del codo
PUNTA = 8  # largo de la punta de flecha
PUNTA_MEDIO_ANCHO = 4

# Presupuesto de alto de una tarjeta (px): el caso más alto que puede darse con el texto que pide la
# decisión del responsable (nombre y dato en dos líneas, tres tareas de dos líneas, la etiqueta
# «Vence hoy» o «Vencido» de UNA tarea —solo una acción por paso puede llevarla: `vencimientos.marca_de`—
# y el renglón de «+ N más» con las advertencias). Los números repiten los de `mapa.css`; un test los
# recalcula. `alto_estimado` los usa tal cual.
PRESUPUESTO = (("borde y relleno", 22), ("encabezado (nombre en 2 líneas)", 32), ("dato (2 líneas)", 36),
               ("estado", 30), ("tareas (3 × 2 líneas)", 8 + 3 * 41), ("etiqueta de una tarea", 19),
               ("«+ N más» y advertencias", 27))
ALTO_MAXIMO = sum(alto for _, alto in PRESUPUESTO)  # 297
PRESUPUESTO_ALTO = ALTO_MAXIMO

# Ancho mínimo de la ventana para ver el lienzo entero: el lienzo, el relleno de la caja del mapa
# (2 × 16), los márgenes de la página (2 × 36: el contenido llega a 1176 px y no crece más) y una barra
# de desplazamiento clásica (15). Con ventanas más anchas el lienzo ocupa justo el ancho de la caja.
VENTANA_MINIMA = ANCHO_LIENZO + 2 * 16 + 2 * 36 + 15

# --- Estimación del alto de una tarjeta ------------------------------------------------------------------
# Ancho de cada carácter en décimas de px, medido en Chrome con la fuente de la aplicación (Hanken
# Grotesk, con la de respaldo del sistema si no carga) a 12 px en peso 400 y a 13 px en peso 600, y
# aumentado 3 %. Solo se suman anchos: el ajuste de pares (kerning) solo los reduce. Una letra con tilde
# usa la de su letra base; un carácter desconocido usa `ANCHO_DESCONOCIDO` (más ancho que cualquiera).
_CODIGOS = (32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 161, 170, 171, 176, 183, 186, 187, 191, 193, 201, 205, 209, 211, 218, 220, 225, 233, 237, 241, 243, 250, 252, 8211, 8212, 8230, 8364)
_REGULAR = (
    34, 36, 49, 74, 67, 102, 99, 29, 38, 38, 52, 85, 27, 50, 27, 49, 67, 67, 67, 67, 67, 67, 67,
    67, 67, 67, 27, 27, 85, 85, 85, 56, 119, 80, 71, 77, 87, 63, 61, 85, 88, 33, 45, 72, 59,
    111, 93, 94, 70, 94, 74, 66, 65, 85, 77, 116, 73, 69, 71, 38, 47, 38, 85, 52, 34, 63, 73,
    58, 73, 65, 39, 73, 70, 30, 30, 62, 30, 107, 70, 73, 73, 73, 43, 53, 42, 70, 60, 90, 57, 60,
    56, 38, 30, 38, 85, 36, 49, 63, 47, 27, 54, 63, 56, 80, 63, 33, 93, 94, 85, 85, 63, 65, 30,
    70, 73, 70, 70, 62, 124, 91, 67,
)
_NEGRITA = (
    37, 41, 59, 80, 75, 113, 96, 35, 45, 45, 59, 93, 33, 54, 33, 56, 75, 54, 75, 75, 78, 75, 75,
    72, 75, 75, 33, 33, 93, 93, 93, 60, 128, 90, 81, 84, 97, 70, 68, 94, 99, 40, 54, 82, 66,
    124, 103, 102, 79, 102, 84, 73, 74, 95, 86, 130, 83, 78, 79, 45, 55, 45, 93, 56, 39, 70, 81,
    63, 81, 72, 47, 81, 78, 35, 35, 71, 35, 119, 79, 80, 81, 81, 50, 58, 49, 79, 68, 102, 68,
    69, 63, 45, 38, 45, 93, 41, 54, 73, 51, 33, 60, 73, 60, 90, 70, 40, 103, 102, 95, 95, 70,
    72, 35, 79, 80, 79, 79, 67, 134, 109, 75,
)
ANCHO_DESCONOCIDO = (140, 150)  # (regular, negrita) en décimas de px
_TABLAS = (dict(zip(_CODIGOS, _REGULAR)), dict(zip(_CODIGOS, _NEGRITA)))

COLUMNA_NOMBRE = 202  # px de texto del nombre: 252 − 2 de borde − 16 de relleno − 24 del número − 8 de separación
COLUMNA_TEXTO = 234  # px de texto del dato
COLUMNA_TAREA = 218  # px de texto de una tarea: 234 − 12 del marcador − 4 de separación
HOLGURA_LINEA = 2  # px que se le quitan a cada ancho útil


def _ancho(palabra, tabla):
    total = 0
    for letra in palabra:
        ancho = _TABLAS[tabla].get(ord(letra))
        if ancho is None:
            base = unicodedata.normalize("NFD", letra)[0]
            ancho = _TABLAS[tabla].get(ord(base), ANCHO_DESCONOCIDO[tabla])
        total += ancho
    return total / 10


def lineas(texto, ancho_util, negrita=False):
    """Cuántas líneas ocupa `texto` en `ancho_util` px con relleno por palabras, SIEMPRE por encima de las
    reales: anchos de letra prudentes, y una palabra más ancha que la línea (que el navegador parte donde
    llega) se cuenta desde una línea nueva y con una letra ancha de margen en cada línea."""
    tabla = 1 if negrita else 0
    ancho_util -= HOLGURA_LINEA
    palabras = texto.split()
    if not palabras:
        return 0
    espacio = _TABLAS[tabla][32] / 10
    n, actual = 1, 0.0
    for palabra in palabras:
        w = _ancho(palabra, tabla)
        if w > ancho_util:
            if actual:
                n += 1
            partes = ceil(w / (ancho_util - 12))
            n += partes - 1
            actual = w - (partes - 1) * (ancho_util - 12)
        elif not actual:
            actual = w
        elif actual + espacio + w <= ancho_util:
            actual += espacio + w
        else:
            n += 1
            actual = w
    return n


def alto_estimado(nombre, dato, tareas, resto):
    """El alto máximo, en px, de una tarjeta con ese contenido (mismas medidas que `mapa.css`).
    `tareas` es una lista de `(texto, lleva_etiqueta)` (las visibles, y la fila «espera» si no hay
    tareas); `resto` es verdadero si hay «+ N más» o advertencias."""
    encabezado = max(24, 16 * lineas(nombre, COLUMNA_NOMBRE, negrita=True))
    arriba = 22 + encabezado + 6 + 15 * lineas(dato, COLUMNA_TEXTO) + 8 + 22
    tareas_px = 8 + sum(13 + 14 * lineas(texto, COLUMNA_TAREA) + (19 if etiqueta else 0)
                        for texto, etiqueta in tareas)
    return arriba + tareas_px + (27 if resto else 0)


def escalon(alto):
    """El índice del menor escalón que alcanza para `alto` (el último si no hay uno)."""
    for i, valor in enumerate(ESCALONES):
        if alto <= valor:
            return i
    return len(ESCALONES) - 1


@dataclass(frozen=True)
class Conector:
    origen: int
    destino: int
    d: str  # trazo del <path> (con codo redondeado)
    punta: tuple  # tres puntos (x, y) del triángulo; el primero es la punta
    tramos: tuple  # segmentos rectos ((x1, y1), (x2, y2)) del recorrido, sin redondear


def _n(valor):
    return f"{valor:g}"


def trazo(origen, destino, posiciones):
    """El conector de la tarjeta `origen` a la `destino`. Sale del borde derecho a `y + SALIDA_Y`.
    Si el destino está en otra columna, entra por su borde izquierdo a `y + SALIDA_Y`: recto si es el
    mismo `y`; si no, con un codo de radio `RADIO` por el medio del hueco que precede a la columna del
    destino. Si está en la misma columna, hace un lazo por el hueco de la derecha y entra por el borde
    derecho, con la punta hacia la izquierda."""
    ox, oy = posiciones[origen]
    dx, dy = posiciones[destino]
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
    xm = x1 - HUECO // 2
    d = (f"M {_n(x0)} {_n(y0)} H {_n(xm - RADIO)} Q {_n(xm)} {_n(y0)} {_n(xm)} {_n(y0 + sentido * RADIO)} "
         f"V {_n(y1 - sentido * RADIO)} Q {_n(xm)} {_n(y1)} {_n(xm + RADIO)} {_n(y1)} H {_n(x1)}")
    tramos = (((x0, y0), (xm, y0)), ((xm, y0), (xm, y1)), ((xm, y1), (x1, y1)))
    return Conector(origen, destino, d, punta, tramos)


@dataclass(frozen=True)
class Geometria:
    """Posiciones, lienzo y conectores de un par de escalones (fila de arriba, fila de abajo)."""

    arriba: int  # índice en ESCALONES
    abajo: int
    fila_b: int  # `y` de la fila de abajo
    lienzo: tuple  # (ancho, alto)
    posiciones: dict  # {n: (x, y)}
    trazos: tuple

    @property
    def clases(self):
        return f"fila-b-{self.arriba} alto-b-{self.abajo}"


def y_fila_b(arriba):
    """La `y` de la fila de abajo para el escalón `arriba`."""
    return Y_ARRIBA + ESCALONES[arriba] + SEPARACION_FILAS


@lru_cache(maxsize=None)
def geometria(arriba, abajo):
    """La geometría para el escalón `arriba` (alto de la fila de arriba) y `abajo` (el de la de abajo)."""
    fila_b = y_fila_b(arriba)
    posiciones = {n: (X_COLUMNA[columna], Y_ARRIBA if fila == 0 else fila_b)
                  for n, (columna, fila) in CASILLAS.items()}
    lienzo = (ANCHO_LIENZO, fila_b + ESCALONES[abajo] + MARGEN)
    trazos = tuple(trazo(o, d, posiciones) for o, d in CONECTORES)
    return Geometria(arriba, abajo, fila_b, lienzo, posiciones, trazos)


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
