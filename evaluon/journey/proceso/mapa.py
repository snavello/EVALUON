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

Falla seguro: la estimación puede equivocarse (otra tipografía, letra agrandada, un texto raro), así que no es
ella la que impide que dos tarjetas se pisen. `mapa.css` fija como alto máximo de cada tarjeta el escalón de su
fila (`--alto-a`, `--alto-b`) y corta lo que sobra entre tarea y tarea: lo peor que pasa es que una tarjeta muestre
menos y mande a la lista. Los textos muy largos se acortan con «…» en la tarjeta (`acortar`; completos en el
`title` y en la lista).

Formas de conector, todas con codos redondeados:
- recto (mismo `y`): 1→2, 2→4, 4→6 y 3→5;
- codo por el hueco que precede a la columna de destino: 3→4 (sube) y 4→7 (baja);
- lazo en la misma columna (4→5, 6→7): sale por el borde derecho, baja por el hueco de la derecha y
  entra por el borde derecho de la tarjeta de abajo, con la punta hacia la izquierda; 4→5 y 4→7 bajan por
  troncos separados 8 px (`TRONCOS_SEPARADOS`) para que cada flecha se siga de punta a punta.
"""

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from math import ceil

ANCHO = 252
HUECO = 32  # entre dos columnas; también el aire a la derecha del lienzo, donde pasa el lazo 6→7
MARGEN = 8
X_COLUMNA = tuple(MARGEN + i * (ANCHO + HUECO) for i in range(4))  # 8, 292, 576, 860
ANCHO_LIENZO = X_COLUMNA[3] + ANCHO + HUECO - 1  # 1143: así a 1262 px de ventana el lienzo entra justo en su caja de 1143
Y_ARRIBA = MARGEN
SEPARACION_FILAS = 12  # entre el alto estimado de la fila de arriba y el comienzo de la de abajo
# (columna, fila) de cada tarjeta: fila 0 arriba, fila 1 abajo
CASILLAS = {1: (0, 0), 2: (1, 0), 3: (0, 1), 4: (2, 0), 5: (2, 1), 6: (3, 0), 7: (3, 1)}
FILA_ARRIBA = (1, 2, 4, 6)
FILA_ABAJO = (3, 5, 7)
CONECTORES = ((1, 2), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (4, 7), (6, 7))

# Altos de fila que se pueden elegir (px, de 12 en 12): de una tarjeta casi vacía a una de tres tareas de tres líneas
# con etiquetas. Un alto estimado mayor que el último se queda en el último.
ESCALONES = tuple(range(120, 433, 12))

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
VENTANA_MINIMA = ANCHO_LIENZO + 2 * 16 + 2 * 36 + 15  # 1262

# --- Estimación del alto de una tarjeta ------------------------------------------------------------------
# Ancho de cada carácter en décimas de px, medido en Chrome CON la fuente de la aplicación ya cargada
# (Hanken Grotesk, `document.fonts.load`; sin esperarla se mide la de respaldo y salen anchos más chicos) a
# 12 px en peso 400 y a 13 px en peso 600, y aumentado 8 % por carácter. Solo se suman anchos: el ajuste de
# pares (kerning) solo los reduce. Una letra con tilde no listada usa la de su letra base; un carácter
# desconocido (emojis, escrituras no latinas) usa `ANCHO_DESCONOCIDO`, más ancho que cualquiera medido.
# Si cambia la tipografía o el tamaño de letra de la tarjeta hay que volver a medir (un test compara el
# estimado con alturas medidas una vez en Chrome).
_CODIGOS = (*range(32, 127), *range(160, 384), 8208, 8209, 8210, 8211, 8212, 8213, 8216, 8217, 8218, 8220, 8221, 8222, 8224, 8225, 8226, 8230, 8240, 8249, 8250, 8364, 8482, 8592, 8594, 8722, 10003, 10005)
_REGULAR = (
    34, 32, 44, 91, 73, 97, 89, 23, 29, 29, 52, 73, 32, 43, 32, 55, 73, 73, 73, 73, 73, 73, 73,
    73, 73, 73, 32, 32, 73, 73, 73, 67, 114, 83, 78, 92, 89, 76, 74, 95, 88, 32, 72, 83, 65,
    109, 88, 97, 72, 101, 78, 74, 77, 86, 86, 125, 84, 79, 76, 34, 59, 34, 72, 53, 38, 70, 77,
    68, 77, 70, 44, 67, 71, 30, 30, 69, 35, 108, 71, 75, 77, 77, 53, 61, 45, 71, 68, 97, 68, 68,
    62, 31, 34, 31, 73, 34, 32, 73, 73, 80, 73, 34, 75, 50, 108, 65, 61, 73, 0, 82, 48, 55, 73,
    55, 54, 39, 71, 75, 44, 39, 36, 69, 61, 93, 98, 104, 45, 83, 83, 83, 83, 83, 83, 117, 92,
    76, 76, 76, 76, 32, 32, 32, 32, 89, 88, 97, 97, 97, 97, 97, 73, 97, 86, 86, 86, 86, 79, 82,
    83, 70, 70, 70, 70, 70, 70, 113, 68, 70, 70, 70, 70, 30, 30, 30, 30, 81, 71, 75, 75, 75, 75,
    75, 73, 75, 71, 71, 71, 71, 68, 82, 68, 84, 66, 84, 66, 84, 66, 81, 60, 81, 60, 81, 60, 81,
    60, 91, 88, 91, 77, 66, 68, 66, 68, 66, 68, 66, 68, 66, 68, 89, 77, 89, 77, 89, 77, 89, 77,
    93, 74, 93, 74, 35, 32, 35, 32, 35, 32, 35, 32, 35, 30, 81, 65, 47, 32, 76, 65, 65, 62, 32,
    62, 32, 62, 40, 62, 41, 62, 36, 97, 74, 97, 74, 97, 74, 79, 97, 74, 98, 76, 98, 76, 98, 76,
    133, 121, 78, 46, 78, 46, 78, 46, 69, 55, 69, 55, 69, 55, 69, 55, 68, 44, 68, 58, 68, 44,
    90, 74, 90, 74, 90, 74, 90, 74, 90, 74, 90, 74, 122, 94, 72, 63, 72, 74, 59, 74, 59, 74, 59,
    32, 52, 52, 70, 54, 138, 130, 35, 35, 38, 57, 57, 51, 49, 49, 46, 87, 157, 32, 32, 73, 91,
    112, 112, 73, 98, 106,
)
_NEGRITA = (
    37, 35, 51, 98, 79, 104, 98, 27, 37, 37, 57, 79, 34, 46, 34, 59, 79, 79, 79, 79, 79, 79, 79,
    79, 79, 79, 34, 34, 79, 79, 79, 73, 123, 93, 86, 100, 95, 82, 79, 104, 97, 37, 78, 92, 71,
    120, 97, 106, 79, 110, 86, 81, 83, 93, 94, 137, 93, 87, 84, 41, 65, 41, 85, 66, 43, 77, 82,
    74, 82, 76, 49, 74, 79, 34, 34, 78, 39, 118, 79, 81, 82, 82, 59, 67, 51, 79, 75, 106, 75,
    75, 67, 38, 38, 38, 79, 37, 35, 79, 79, 86, 79, 38, 84, 56, 115, 68, 73, 79, 0, 87, 51, 59,
    79, 58, 57, 45, 79, 85, 45, 41, 37, 72, 65, 106, 111, 117, 55, 93, 93, 93, 93, 93, 93, 129,
    100, 82, 82, 82, 82, 37, 37, 37, 37, 95, 97, 106, 106, 106, 106, 106, 79, 106, 93, 93, 93,
    93, 87, 88, 91, 77, 77, 77, 77, 77, 77, 121, 74, 76, 76, 76, 76, 34, 34, 34, 34, 86, 79, 81,
    81, 81, 81, 81, 79, 81, 79, 79, 79, 79, 75, 87, 75, 95, 74, 95, 74, 95, 74, 88, 67, 88, 67,
    88, 67, 88, 67, 101, 99, 101, 86, 73, 75, 73, 75, 73, 75, 73, 75, 73, 75, 98, 85, 98, 85,
    98, 85, 98, 85, 104, 82, 104, 83, 41, 37, 41, 37, 41, 37, 41, 37, 41, 34, 97, 77, 56, 37,
    86, 74, 74, 69, 37, 69, 37, 69, 47, 69, 52, 69, 41, 108, 82, 108, 82, 108, 82, 86, 108, 82,
    107, 84, 107, 84, 107, 84, 141, 130, 88, 52, 88, 52, 88, 52, 77, 61, 77, 61, 77, 61, 77, 61,
    78, 51, 78, 58, 78, 51, 99, 82, 99, 82, 99, 82, 99, 82, 99, 82, 99, 82, 136, 107, 82, 72,
    82, 83, 66, 83, 66, 83, 66, 38, 57, 57, 78, 60, 149, 141, 38, 38, 41, 64, 64, 60, 55, 55,
    53, 97, 173, 38, 38, 79, 101, 122, 122, 79, 106, 115,
)
ANCHO_DESCONOCIDO = (200, 220)  # (regular, negrita) en décimas de px: más que un emoji (16,5 px)
_TABLAS = (dict(zip(_CODIGOS, _REGULAR)), dict(zip(_CODIGOS, _NEGRITA)))

COLUMNA_NOMBRE = 202  # px de texto del nombre: 252 − 2 de borde − 16 de relleno − 24 del número − 8 de separación
COLUMNA_TEXTO = 234  # px de texto del dato
COLUMNA_TAREA = 218  # px de texto de una tarea: 234 − 12 del marcador − 4 de separación
HOLGURA_LINEA = 2  # px que se le quitan a cada ancho útil
HOLGURA_ALTO = 14  # una línea de tarea de holgura por tarjeta, por lo que ninguna tabla de anchos prevé
LIMITE_TAREA = 110  # caracteres de una tarea en la tarjeta; lo que pasa se corta con «…» (completo en la lista)
LIMITE_DATO = 90  # ídem para el dato del paso y para la fila «espera»


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
    return arriba + tareas_px + (27 if resto else 0) + HOLGURA_ALTO


def acortar(texto, limite):
    """`texto` tal cual si cabe en `limite` caracteres; si no, cortado en el último espacio que deje al menos
    la mitad y con «…» (el texto completo queda en el `title` y en la lista de pasos)."""
    if len(texto) <= limite:
        return texto
    corte = texto[:limite - 1]
    espacio = corte.rfind(" ")
    if espacio >= limite // 2:
        corte = corte[:espacio]
    return corte.rstrip(" ,;:.·-—") + "…"

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
    radio: int = RADIO  # el de sus codos


def _n(valor):
    return f"{valor:g}"


# Los dos conectores que salen de la tarjeta 4 hacia abajo (4→5 y 4→7) bajan por troncos separados 8 px,
# para que cada flecha se siga de punta a punta: 4→5 baja a 12 px del borde derecho de la 4 y vuelve a
# entrar por el de la 5; 4→7 baja a 12 px del borde izquierdo de la 7. Con ese poco hueco los codos son de
# radio 4 (el tramo final mide 12 = radio + punta). `(distancia del tronco al borde, radio)`.
TRONCOS_SEPARADOS = {(4, 5): (12, 4), (4, 7): (12, 4)}


def trazo(origen, destino, posiciones):
    """El conector de la tarjeta `origen` a la `destino`. Sale del borde derecho a `y + SALIDA_Y`.
    Si el destino está en otra columna, entra por su borde izquierdo a `y + SALIDA_Y`: recto si es el
    mismo `y`; si no, con un codo de radio `RADIO` por el medio del hueco que precede a la columna del
    destino. Si está en la misma columna, hace un lazo por el hueco de la derecha y entra por el borde
    derecho, con la punta hacia la izquierda. 4→5 y 4→7 usan troncos separados (`TRONCOS_SEPARADOS`)."""
    ox, oy = posiciones[origen]
    dx, dy = posiciones[destino]
    x0, y0 = ox + ANCHO, oy + SALIDA_Y
    y1 = dy + SALIDA_Y
    sentido = 1 if y1 > y0 else -1
    tronco, radio = TRONCOS_SEPARADOS.get((origen, destino), (HUECO // 2, RADIO))
    if dx == ox:  # lazo: vuelve a entrar por el borde derecho
        x1 = dx + ANCHO
        xm = x0 + tronco
        punta = ((x1, y1), (x1 + PUNTA, y1 - PUNTA_MEDIO_ANCHO), (x1 + PUNTA, y1 + PUNTA_MEDIO_ANCHO))
        d = (f"M {_n(x0)} {_n(y0)} H {_n(xm - radio)} Q {_n(xm)} {_n(y0)} {_n(xm)} {_n(y0 + sentido * radio)} "
             f"V {_n(y1 - sentido * radio)} Q {_n(xm)} {_n(y1)} {_n(xm - radio)} {_n(y1)} H {_n(x1)}")
        tramos = (((x0, y0), (xm, y0)), ((xm, y0), (xm, y1)), ((xm, y1), (x1, y1)))
        return Conector(origen, destino, d, punta, tramos, radio)
    x1 = dx
    punta = ((x1, y1), (x1 - PUNTA, y1 - PUNTA_MEDIO_ANCHO), (x1 - PUNTA, y1 + PUNTA_MEDIO_ANCHO))
    if y0 == y1:
        return Conector(origen, destino, f"M {_n(x0)} {_n(y0)} H {_n(x1)}", punta,
                        (((x0, y0), (x1, y1)),))
    xm = x1 - tronco
    d = (f"M {_n(x0)} {_n(y0)} H {_n(xm - radio)} Q {_n(xm)} {_n(y0)} {_n(xm)} {_n(y0 + sentido * radio)} "
         f"V {_n(y1 - sentido * radio)} Q {_n(xm)} {_n(y1)} {_n(xm + radio)} {_n(y1)} H {_n(x1)}")
    tramos = (((x0, y0), (xm, y0)), ((xm, y0), (xm, y1)), ((xm, y1), (x1, y1)))
    return Conector(origen, destino, d, punta, tramos, radio)


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
