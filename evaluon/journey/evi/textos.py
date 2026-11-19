"""Los textos fijos de Evi (REQ-167, REQ-170; feature 020, T-367): los siete pasos, el circuito
completo y los seis términos. Es el ÚNICO lugar donde se escriben; el responsable los aprueba acá.
Trato de «usted», lenguaje llano, sin términos de programación. Salen del prototipo aprobado
(`docs/diseno/evi/index.html`), sin lo que ese prototipo marcaba como «requiere desarrollo».

Los nombres de los pasos NO se escriben acá: salen de `evaluon/journey/proceso/pasos.py`. Lo que sí
vive acá es el nombre corto que se usa en pantallas angostas (`CORTOS`) y los textos de cada paso.
Los textos describen y explican qué hay que completar; ninguno decide ni recomienda (REQ-169).
"""

from dataclasses import dataclass, field

SHY = "­"  # guion blando: el navegador parte la palabra solo si no entra

# Nombre corto de cada paso, para el gráfico en pantallas angostas (el nombre completo es el de `pasos.py`).
CORTOS = {1: "Pliego", 2: "Matriz", 3: "Ofertas", 4: f"Cumpli{SHY}miento", 5: f"Compa{SHY}ración",
          6: f"Evalua{SHY}ción", 7: "Dictamen"}


@dataclass(frozen=True)
class Termino:
    """Un recuadro de «Qué es …»: el título y una explicación de dos frases."""

    titulo: str
    texto: str


@dataclass(frozen=True)
class TextosPaso:
    que_es: str
    sirve: str
    hacer: tuple
    terminos: tuple = field(default_factory=tuple)


CIRCUITO_TITULO = "De la carga del pliego al dictamen"
CIRCUITO_QUE_ES = ("Un procedimiento recorre siete pasos: se cargan los datos y el pliego, se arma la matriz de "
                   "requisitos, se reciben las ofertas, se revisa si cumplen, se comparan los precios, la "
                   "Comisión decide y se carga el dictamen.")
CIRCUITO_COMO_SE_LEE = ("No hace falta ir en orden: varios pasos pueden estar en marcha a la vez, y cada uno "
                        "muestra su propio estado.")
CIRCUITO_QUIEN_DECIDE = Termino("Quién decide", "El sistema propone y la Comisión decide.")
CIRCUITO_PARA_RECORRER = ("Con un procedimiento abierto, cada paso muestra qué falta en ese procedimiento. "
                          "Para recorrer el circuito, toque un paso del gráfico o use «Siguiente».")

PASOS = {
    1: TextosPaso(
        que_es=("Es donde se cargan los datos del procedimiento y el pliego de bases y condiciones, con sus "
                "anexos y circulares. Se toman del Portal de Compras o, si no están ahí, de un archivo."),
        sirve="Todo el resto del trabajo se apoya en lo que se cargue acá.",
        hacer=("Pegue el enlace del procedimiento en el Portal de Compras.",
               "Mire lo que el sistema encontró y apruebe lo que esté bien. Nada se carga hasta que se aprueba.",
               "Si algo no está en el Portal, súbalo desde un archivo.",
               "Revise las circulares nuevas, si las hay."),
        terminos=(Termino("Qué es una circular",
                          "Es un aviso que se publica después del pliego para aclararlo o para cambiarlo. Si "
                          "cambia un requisito, se abre una versión nueva de la matriz y hay que validarla "
                          "otra vez."),)),
    2: TextosPaso(
        que_es=("Es la lista de lo que el pliego le exige a cada oferta, ordenada en formales, económicos y "
                "técnicos. Cada requisito cita el texto del pliego que lo pide."),
        sirve="Es la vara con la que después se mide cada oferta.",
        hacer=("Pida al sistema que proponga la matriz a partir del pliego.",
               "Revise cada requisito: confirme, corrija, quite o agregue.",
               "Decida las sugerencias dudosas del sistema. Con una sin decidir, no se puede validar.",
               "Valide la matriz. Queda fija: si algo cambia, se abre una versión nueva."),
        terminos=(Termino("Qué es la matriz de requisitos",
                          "La propone el sistema y la valida una persona de la Comisión. Mientras no esté "
                          "validada, se puede ver e imprimir, pero siempre con la leyenda «BORRADOR "
                          "INCOMPLETO»."),)),
    3: TextosPaso(
        que_es=("Es donde se registran las ofertas recibidas. Cada oferta tiene sus documentos: propuesta "
                "económica, declaraciones juradas, garantías, constancias y anexos técnicos."),
        sirve="El sistema solo puede revisar lo que está cargado.",
        hacer=("Agregue las ofertas del acta de apertura desde el Portal, o suba los archivos de cada una.",
               "Controle que cada oferta tenga todos sus documentos.",
               "Suba la hoja de compliance de cada oferta (se explica en el paso 4).",
               "Si llega un documento nuevo, por ejemplo una subsanación, súbalo a su oferta.")),
    4: TextosPaso(
        que_es=("El sistema revisa cada oferta contra cada requisito de la matriz y propone un resultado: "
                "cumple, no cumple o no determinado. Cada propuesta cita el texto del pliego y el de la oferta."),
        sirve="Le ahorra buscar a mano en cada documento. Es una propuesta: todavía no decide nada.",
        hacer=("Pida evaluar las ofertas. Se evalúan todas juntas, con la matriz validada.",
               "Suba la hoja de compliance de cada oferta.",
               "Cargue el informe técnico del área para las filas técnicas.",
               "Cuando el informe técnico esté aprobado, dé el ok."),
        terminos=(
            Termino("Qué es una hoja de compliance",
                    "Es un documento que se sube una vez por oferta. Reúne los chequeos que la Comisión hace "
                    "en sistemas externos: registro de proveedores, sanciones, deudas y validez de la póliza. "
                    "Vale para todos los requisitos externos de esa oferta. También se sube una hoja que diga "
                    "que no cumple. Es información reservada: se procesa solo en este equipo."),
            Termino("Qué es el informe técnico",
                    "Es el informe del área que pidió la compra. Las filas técnicas por renglón las resuelve "
                    "ese informe, no la Comisión punto por punto. La Comisión solo da el ok de que tiene el "
                    "informe aprobado."))),
    5: TextosPaso(
        que_es=("Ordena las ofertas por precio: el total y el precio de cada renglón, con la cotización del "
                "Portal cuando la hay. Muestra cuál es la más baja y cuál la más alta."),
        sirve=("Permite ver qué oferta conviene económicamente. El orden es una propuesta: lo decide la "
               "Comisión."),
        hacer=("Controle que cada oferta tenga su total.",
               "Mire el orden y los precios por renglón.",
               "Tenga en cuenta que, si las ofertas están en monedas distintas, no hay orden.",
               "Complete el cumplimiento (paso 4) para dar este paso por hecho.")),
    6: TextosPaso(
        que_es=("Es donde la Comisión revisa lo que propuso el sistema y decide. En cada punto puede confirmar "
                "la propuesta, corregirla o rechazarla. Cada decisión queda registrada con quién la tomó y "
                "cuándo."),
        sirve="Acá se resuelve lo que el sistema no puede decidir solo. La decisión es siempre de la Comisión.",
        hacer=("Abra el cuadro de cumplimiento y empiece por los puntos «no determinados».",
               "Revise los «no cumple» que propuso el sistema.",
               "Confirme los «cumple».",
               "Conteste las preguntas y resuelva los descartes propuestos."),
        terminos=(Termino("Qué es una subsanación",
                          "Si el pliego pide un documento y la oferta no lo trae, el resultado es «no se "
                          "encontró el documento», no «no cumple». La Comisión puede pedir que se subsane. "
                          "Cuando el oferente presenta el documento, se agrega a la oferta y ese requisito se "
                          "evalúa de nuevo."),)),
    7: TextosPaso(
        que_es=("Es el documento donde la Comisión deja asentado el resultado de su evaluación. Se toma del "
                "Portal cuando se publica, o se sube desde un archivo."),
        sirve="Cierra el procedimiento: con el dictamen cargado, pasa a «Terminados».",
        hacer=("Termine los pasos 4 y 6.",
               "Cargue el dictamen: tómelo del Portal o suba el archivo.",
               "Si el Portal ya publicó uno, apruebe su carga.",
               "Exporte la planilla y el cuadro comparativo si los necesita."),
        terminos=(Termino("Qué es un dictamen",
                          "Lo redacta la Comisión; el sistema no lo escribe. Una vez cargado, el procedimiento "
                          "sale de la lista de abiertos."),)),
}
