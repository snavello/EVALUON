"""El estado de cada uno de los siete pasos y el `Proceso` que dibujan las pantallas (REQ-143,
REQ-144, REQ-145; plan 018, «Cómo se calcula el estado de cada paso»; T-345).

`proceso_de(user, procedure, overview=None)` es la única entrada: llama UNA vez a `sections_for`
(si no recibe el `Overview`), pide las acciones a `acciones.py` y deriva el estado de cada paso de
lo que las etapas y las secciones ya calcularon. Solo lee: no guarda ninguna fase ni consulta
fuera de lo que el plan nombra (REQ-145); no existe un «paso actual».

Reglas comunes (aceptadas por el responsable el 2026-11-17):

- R1 **Con error**: alguna etapa del paso quedó `CON_ERROR`.
- R2 **Hecho**: se cumplen las condiciones de la tabla «Está Hecho cuando» de la spec Y el paso no
  tiene ningún pendiente ni acción de cierre abierta. Los faltantes (tipo `faltante`) no cambian
  el estado: salen como advertencias del paso (N1, opción A).
- R3 **En curso**: el paso ya empezó o tiene un pendiente o una acción de cierre disponible ahora
  (también si no empezó pero se puede empezar: 2 con el pliego leído).
- R4 **Todavía no**: no empezó y no tiene nada que hacer ahora; `espera` dice de qué depende.

Pasos 1 a 3 (esta tarea). Los pasos 4 a 7 quedan PROVISIONALES: «Todavía no», sin `dato`,
`resumen` ni `espera`; los completa T-346 (con `pasos_4_y_6_hechos` real para el cierre «Cargar el
dictamen», `Proceso.terminado` y `Proceso.vencimiento`). Todos traen ya sus `tareas`, las mismas
`Accion` de `Proceso.acciones`, sus advertencias y su marca de vencimiento.
"""

from evaluon.journey import memo
from evaluon.journey.proceso import acciones, pasos, vencimientos
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import base as stage_base
from evaluon.journey.tablero import ingreso
from evaluon.journey.temas import s2_documentos, s2_matriz, s3_circulares, s4_dictamen
from evaluon.journey.window import plain_reason
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import DocumentKind as OfferDocumentKind
from evaluon.tenders.models import DocumentKind, RequirementState, VersionStatus
from evaluon.tenders.services import circular_version

ABIERTAS = (pasos.PENDIENTE, pasos.CIERRE)
E = pasos.Estado


class _Contexto:
    """Lo que todos los pasos leen, calculado una vez."""

    def __init__(self, user, procedure, overview, todas):
        self.user, self.procedure, self.overview = user, procedure, overview
        self.etapas = {stage.key: stage for stage in overview.journey.stages}
        self.todas = todas

    def tareas(self, numero):
        return [a for a in self.todas if a.paso == numero]

    def abiertas(self, numero):
        """Pendientes y acciones de cierre del paso (los faltantes no cuentan: N1)."""
        return [a for a in self.tareas(numero) if a.tipo in ABIERTAS]


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _con_error(paso, *etapas):
    """R1: si alguna de las etapas falló, el paso queda «Con error» con el motivo."""
    fallida = next((e for e in etapas if e.state == stage_base.CON_ERROR), None)
    if fallida is None:
        return False
    paso.estado = E.CON_ERROR
    motivo = plain_reason(fallida.error).rstrip(".")
    paso.resumen = f"{fallida.detail} {motivo[:1].upper()}{motivo[1:]}.".strip()
    return True


# --- Paso 1 · Carga de pliego ---------------------------------------------------------------------


def _paso1(c):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[1], c.procedure)
    etapa, portal = c.etapas["pliego"], c.etapas["portal"]
    documentos = s2_documentos.documents_of(c.procedure)
    hay_pliego = any(d.kind == DocumentKind.PLIEGO for d in documentos)
    anexos = sum(1 for d in documentos if d.kind != DocumentKind.PLIEGO)
    circulares = len(s3_circulares._states(c.procedure))
    paso.dato = (f"Pliego, {_plural(anexos, 'anexo', 'anexos')}, "
                 f"{_plural(circulares, 'circular', 'circulares')}" if hay_pliego
                 else "Sin pliego cargado")
    if _con_error(paso, etapa, portal):
        return paso
    abiertas = c.abiertas(1)
    if hay_pliego and etapa.state == stage_base.LISTA and not abiertas:
        paso.estado = E.HECHO
        paso.resumen = "El pliego está cargado y leído; no hay circulares sin revisar."
    elif (abiertas or documentos or etapa.state == stage_base.EN_CURSO
            or portal.state == stage_base.EN_CURSO):
        paso.estado = E.EN_CURSO
        if not hay_pliego:
            paso.resumen = "Todavía falta cargar el pliego. " + etapa.detail
        elif etapa.state != stage_base.LISTA:
            paso.resumen = etapa.detail
        else:
            paso.resumen = "El pliego está leído; hay documentos o datos del Portal por tomar."
    else:
        paso.estado = E.TODAVIA_NO
        paso.resumen = "Todavía no se cargó el pliego: faltan los documentos."
    return paso


# --- Paso 2 · Matriz de requisitos de pliego ------------------------------------------------------


def _paso2(c):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[2], c.procedure)
    etapa, pliego = c.etapas["matriz"], c.etapas["pliego"]
    version = s2_matriz.latest_version(c.procedure)
    circulares = circular_version.pending(c.procedure, s3_circulares._states(c.procedure))
    if version is None:
        paso.dato = "Sin versión de la matriz"
    else:
        n = (version.requirements.exclude(
            state__in=(RequirementState.QUITADO, RequirementState.SUGERIDO)).count())
        validada = version.status == VersionStatus.VALIDATED
        paso.dato = (f"{_plural(n, 'requisito', 'requisitos')} · versión {version.number} "
                     f"{'validada' if validada else 'en revisión'}")
    if _con_error(paso, etapa):
        return paso
    abiertas = c.abiertas(2)
    if circulares:
        paso.resumen = (f"Hay {_plural(len(circulares), 'circular modificatoria', 'circulares modificatorias')} "
                        "posterior a la matriz: falta una versión nueva validada.")
    if (version is not None and version.status == VersionStatus.VALIDATED
            and not circulares and not abiertas):
        paso.estado = E.HECHO
        paso.resumen = f"La versión {version.number} está validada."
    elif (version is not None or abiertas or circulares
            or etapa.state == stage_base.EN_CURSO or pliego.state == stage_base.LISTA):
        paso.estado = E.EN_CURSO
        if not paso.resumen:
            paso.resumen = (etapa.detail if version is not None or etapa.state != stage_base.PENDIENTE
                            else "El pliego está leído: se puede proponer la matriz.")
    else:
        paso.estado = E.TODAVIA_NO
        paso.espera = "depende de que el pliego esté cargado y leído"
        paso.resumen = f"Todavía no: {paso.espera}."
    return paso


# --- Paso 3 · Recepción de ofertas ----------------------------------------------------------------


def _paso3(c):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[3], c.procedure)
    etapa = c.etapas["ofertas"]
    ofertas = memo.offers(c.procedure)
    propios = list(OfferDocument.objects.filter(offer__in=ofertas)
                   .exclude(kind=OfferDocumentKind.INFORME_TECNICO)
                   .values_list("offer_id", flat=True))
    con_documentos = set(propios)
    paso.dato = (f"{_plural(len(ofertas), 'oferta', 'ofertas')} · "
                 f"{_plural(len(propios), 'documento', 'documentos')}" if ofertas
                 else "Sin ofertas")
    if _con_error(paso, etapa):
        return paso
    abiertas = c.abiertas(3)
    if (ofertas and len(con_documentos) == len(ofertas) and etapa.state == stage_base.LISTA
            and not abiertas):
        paso.estado = E.HECHO
        paso.resumen = (f"{_plural(len(ofertas), 'oferta', 'ofertas')} con todos sus documentos "
                        "cargados y leídos.")
    elif ofertas or abiertas or etapa.state == stage_base.EN_CURSO:
        paso.estado = E.EN_CURSO
        sin = len(ofertas) - len(con_documentos)
        paso.resumen = (f"{_plural(sin, 'oferta sin documentos', 'ofertas sin documentos')}. "
                        if ofertas and sin else "") + (
            etapa.detail if etapa.state != stage_base.LISTA else "")
        paso.resumen = paso.resumen.strip() or "Hay ofertas por recibir o revisar."
    else:
        paso.estado = E.TODAVIA_NO
        paso.resumen = "Todavía no hay ofertas: se reciben al abrirse el acta o se suben a mano."
    return paso


# --- El proceso -----------------------------------------------------------------------------------


def _provisorio(numero, c):
    """Pasos 4 a 7 hasta T-346: «Todavía no», sin dato, resumen ni espera."""
    return pasos.Paso.vacio(pasos.POR_NUMERO[numero], c.procedure)


def proceso_de(user, procedure, overview=None):
    """El `Proceso` de `procedure` para `user`: los siete pasos, cada uno con su estado propio,
    y la lista de acciones de «Qué se puede hacer ahora». Se llama una vez por pedido; con
    `overview` (el de `sections_for`) no se vuelven a calcular las secciones."""
    with memo.scope():
        if overview is None:
            overview = sections_for(user, procedure)
        hoy = ingreso.today()
        plazos = ingreso.plazos(procedure)
        cargado = s4_dictamen.dictamen_cargado(procedure)
        todas = acciones.armar(user, procedure, overview, plazos=plazos, hoy=hoy,
                               dictamen_cargado=cargado)
        contexto = _Contexto(user, procedure, overview, todas)
        calculados = {1: _paso1(contexto), 2: _paso2(contexto), 3: _paso3(contexto)}
        advertencias = acciones.advertencias(overview)
        lista = []
        for definicion in pasos.PASOS:
            paso = calculados.get(definicion.numero) or _provisorio(definicion.numero, contexto)
            paso.tareas = contexto.tareas(definicion.numero)
            paso.advertencias = list(advertencias.get(definicion.numero, []))
            paso.marca = vencimientos.marca_de(paso, plazos, hoy, dictamen_cargado=cargado)
            lista.append(paso)
    return pasos.Proceso(procedure=procedure, pasos=lista, acciones=todas)
