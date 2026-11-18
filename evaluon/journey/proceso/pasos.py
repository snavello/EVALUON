"""Los tipos y los nombres de los siete pasos del proceso (REQ-143; plan 018, «Contrato»; T-343).

Es el único lugar donde se escriben los nombres de los pasos y los textos de los estados: las
demás tareas (cálculo, acciones, pantallas) los leen de acá. Solo datos: no consulta nada.
"""

from dataclasses import dataclass, field
from enum import Enum

from django.urls import reverse


class Estado(str, Enum):
    """El estado de un paso, con el texto que se escribe en pantalla."""

    HECHO = "hecho"
    EN_CURSO = "en_curso"
    TODAVIA_NO = "todavia_no"
    CON_ERROR = "con_error"

    @property
    def texto(self):
        return TEXTOS_ESTADO[self]


TEXTOS_ESTADO = {
    Estado.HECHO: "Hecho",
    Estado.EN_CURSO: "En curso",
    Estado.TODAVIA_NO: "Todavía no",
    Estado.CON_ERROR: "Con error",
}

# Tipos de acción (la lista «Qué se puede hacer ahora»).
PENDIENTE = "pendiente"
CIERRE = "cierre"
FALTANTE = "faltante"
TIPOS_ACCION = (PENDIENTE, CIERRE, FALTANTE)

# `kind` de las acciones que `vencimientos.marca_de` reconoce (REQ-157).
KIND_DICTAMEN = "dictamen"  # «Cargar el dictamen» / «Aprobar el dictamen…» (paso 7)
KIND_ACTA = "acta"  # «Agregar las ofertas del acta» (paso 3)

# Marcas de vencimiento (REQ-157).
MARCA_HOY = "hoy"
MARCA_VENCIDO = "vencido"
TEXTOS_MARCA = {MARCA_HOY: "Vence hoy", MARCA_VENCIDO: "Vencido"}


@dataclass(frozen=True)
class DefPaso:
    """La definición fija de un paso. Dónde se resuelve lo dice `DESTINOS`."""

    numero: int
    clave: str
    nombre: str


PASOS = (
    DefPaso(1, "pliego", "Carga de pliego"),
    DefPaso(2, "matriz", "Matriz de requisitos de pliego"),
    DefPaso(3, "ofertas", "Recepción de ofertas"),
    DefPaso(4, "cumplimiento", "Cumplimiento de ofertas (matriz)"),
    DefPaso(5, "comparacion", "Comparación de ofertas"),
    DefPaso(6, "evaluacion", "Evaluación Comisión"),
    DefPaso(7, "dictamen", "Dictamen"),
)

POR_NUMERO = {p.numero: p for p in PASOS}
POR_CLAVE = {p.clave: p for p in PASOS}


# Dónde se resuelve cada paso (REQ-149, REQ-154): `(ruta de expedientes:, ancla)`. El ancla es un
# `id` que la página trae siempre. Los pasos 4 y 6 se resuelven en el cuadro de cumplimiento; el 5
# se mira en «Indicadores» (el primer panel).
DESTINOS = {
    1: ("procedimiento", "#s1-pliego"),
    2: ("pliego", "#s2-matriz"),
    3: ("ofertas", "#s3-ofertas"),
    4: ("cuadro", ""),
    5: ("procedimiento", "#indicadores-titulo"),
    6: ("cuadro", ""),
    7: ("evaluacion", "#s4-dictamen"),
}


def destino_por_omision(numero, procedure):
    """La URL (con su ancla) del lugar donde se resuelve el paso `numero` del `procedure`."""
    ruta, ancla = DESTINOS[numero]
    return reverse(f"expedientes:{ruta}", args=[procedure.pk]) + ancla


@dataclass
class Accion:
    """Una línea de «Qué se puede hacer ahora». `paso` es el número del paso (1 a 7); `id` es
    estable: `"<paso>-<tipo>-<kind>"`. `cuenta` suma al contador de pendientes solo en las de
    tipo `pendiente`. `post` es `(url, ((campo, valor), ...))` de una acción de un solo clic.
    `marca`: `""`, `"hoy"` o `"vencido"`."""

    paso: int
    tipo: str
    kind: str
    texto: str
    cuenta: int = 0
    boton: str = ""
    url: str = ""
    post: tuple | None = None
    marca: str = ""

    @property
    def id(self):
        return f"{self.paso}-{self.tipo}-{self.kind}"


@dataclass
class Paso:
    """Un paso calculado. `tareas` son los mismos objetos `Accion` que `Proceso.acciones`
    (REQ-158); `advertencias` son textos; `espera` dice de qué otro paso depende."""

    numero: int
    nombre: str
    estado: Estado = Estado.TODAVIA_NO
    dato: str = ""
    resumen: str = ""
    espera: str = ""
    advertencias: list = field(default_factory=list)
    tareas: list = field(default_factory=list)
    marca: str = ""
    destino: str = ""

    @classmethod
    def vacio(cls, definicion, procedure=None):
        """Un paso «Todavía no», con su nombre y su destino por omisión."""
        destino = destino_por_omision(definicion.numero, procedure) if procedure else ""
        return cls(definicion.numero, definicion.nombre, destino=destino)


@dataclass
class Proceso:
    """Lo que las pantallas dibujan de un procedimiento: se calcula una vez por pedido."""

    procedure: object
    pasos: list = field(default_factory=list)
    acciones: list = field(default_factory=list)
    terminado: bool = False
    vencimiento: object = None
