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

Pasos 4 a 7 (T-346):

- 4 Cumplimiento: etapa `evaluacion` lista, ningún resultado espera el informe técnico o su ok y
  ninguna evaluación dejó afuera un documento vigente (eso lo dice la acción «Evaluar las
  ofertas»). Sin matriz validada u ofertas con documentos: «Todavía no» con su `espera`.
- 5 Comparación: todas las ofertas tienen su total (`PortalOfferData`, nunca `len(order.totals)`:
  un «no cumple» formal saca la oferta del orden) y el paso 4 está «Hecho». Sin ofertas, «Todavía
  no». Nunca «Con error».
- 6 Evaluación Comisión: alguna oferta evaluada y ningún par, pregunta ni descarte por resolver
  (`matriz_evaluacion.counts`; lo que espera el informe técnico cuenta en el paso 4). Nunca «Con
  error».
- 7 Dictamen: `dictamen_cargado`. «En curso» si hay un dictamen del Portal sin aprobar o si la
  acción «Cargar el dictamen» está disponible (pasos 4 y 6 hechos, o el mantenimiento vence hoy o
  ya venció: REQ-157). «Con error» si el dictamen del Portal quedó `fallido`.

Como «Cargar el dictamen» depende de que los pasos 4 y 6 estén hechos y ellos dependen de las
acciones, `acciones.armar` se llama una vez; solo si los pasos 4 y 6 quedan hechos, el dictamen
falta y la acción todavía no estaba, se vuelve a llamar con `pasos_4_y_6_hechos=True`.

`Proceso.terminado` = dictamen cargado (REQ-150) y `Proceso.vencimiento` = el más próximo
(`vencimientos.proximo`). Cada paso trae sus `tareas`, las mismas `Accion` de `Proceso.acciones`,
sus advertencias y su marca de vencimiento.
"""

from evaluon.accounts import permissions
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.proceso import acciones, pasos, vencimientos
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import base as stage_base
from evaluon.journey.stages import matriz_evaluacion
from evaluon.journey.tablero import ingreso
from evaluon.journey.temas import s2_documentos, s2_matriz, s3_circulares, s4_dictamen
from evaluon.journey.temas import s4_propuesta
from evaluon.journey.window import plain_reason
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import DocumentKind as OfferDocumentKind
from evaluon.portal.models import ItemState, PortalOfferData
from evaluon.tenders.models import DocumentKind, RequirementState, VersionStatus
from evaluon.tenders.services import circular_version
from evaluon.tenders.services.validation import latest_validated

ABIERTAS = (pasos.PENDIENTE, pasos.CIERRE)
E = pasos.Estado


class _Contexto:
    """Lo que todos los pasos leen, calculado una vez."""

    def __init__(self, user, procedure, overview, todas, plazos=None, hoy=None, portal=None):
        self.user, self.procedure, self.overview = user, procedure, overview
        self.etapas = {stage.key: stage for stage in overview.journey.stages}
        self.todas = todas
        self.plazos, self.hoy, self.portal = plazos, hoy, portal
        self._pagina = self._cuentas = None

    @property
    def pagina(self):
        """La matriz de evaluación del pedido (la misma que ya calcularon las secciones)."""
        if self._pagina is None:
            with permissions.viewing(self.user):
                self._pagina = memo.matrix_page(self.user, self.procedure.pk,
                                                channel=Channel.SCREEN)
        return self._pagina

    @property
    def cuentas(self):
        """`matriz_evaluacion.Counts` de la página (pares, preguntas, informes y descartes)."""
        if self._cuentas is None:
            self._cuentas = matriz_evaluacion.counts(self.pagina)
        return self._cuentas

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
    circulares = len(s3_circulares.states(c.procedure))
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
    circulares = circular_version.pending(c.procedure, s3_circulares.states(c.procedure))
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


# --- Paso 4 · Cumplimiento de ofertas (matriz) ---------------------------------------------------


def _informes_pendientes(c):
    """`(sin informe, con informe esperando el ok)`: ofertas con una fila técnica evaluada y sin
    ok vigente, partidas por si tienen o no un informe técnico cargado."""
    estados = matriz_evaluacion._technical_pending_offer_statuses(c.pagina)
    sin = sum(1 for e in estados if not e.reports)
    return sin, len(estados) - sin


def _paso4(c):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[4], c.procedure)
    etapa = c.etapas["evaluacion"]
    cifras = s4_propuesta.figures_of(c.pagina)
    paso.dato = ("Todavía sin evaluar" if cifras is None else
                 f"{sum(o.ok for o in cifras.offers)} cumplen · {sum(o.no for o in cifras.offers)}"
                 f" no · {sum(o.nd for o in cifras.offers)} a decidir")
    if _con_error(paso, etapa):
        return paso
    abiertas = c.abiertas(4)
    sin_informe, sin_ok = _informes_pendientes(c)
    if etapa.state == stage_base.LISTA and not abiertas and not (sin_informe or sin_ok):
        paso.estado = E.HECHO
        paso.resumen = ("Todas las ofertas están revisadas con la matriz vigente y ningún "
                        "resultado espera el informe técnico.")
    elif (abiertas or sin_informe or sin_ok or etapa.state == stage_base.EN_CURSO
            or any(s.evaluated for s in c.pagina.statuses)):
        paso.estado = E.EN_CURSO
        partes = []
        if etapa.state != stage_base.LISTA:
            partes.append(etapa.detail)
        elif any(a.kind == acciones.K_EVALUAR for a in abiertas):
            partes.append("Hay un documento que la última evaluación no tuvo en cuenta.")
        if sin_informe:
            partes.append("Falta el informe técnico del área en "
                          f"{_plural(sin_informe, 'oferta', 'ofertas')}.")
        if sin_ok:
            partes.append("Falta dar el ok al informe técnico de "
                          f"{_plural(sin_ok, 'oferta', 'ofertas')}.")
        paso.resumen = " ".join(partes) or "Hay ofertas por evaluar."
    else:
        paso.estado = E.TODAVIA_NO
        paso.espera = ("depende de la matriz de requisitos" if latest_validated(c.procedure) is None
                       else "depende de que haya ofertas con documentos")
        paso.resumen = f"Todavía no: {paso.espera}."
    return paso


# --- Paso 5 · Comparación de ofertas --------------------------------------------------------------


def _paso5(c, cuatro):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[5], c.procedure)
    ofertas = memo.offers(c.procedure)
    if not ofertas:
        paso.dato = "Sin ofertas"
        paso.espera = "depende de que haya ofertas"
        paso.resumen = f"Todavía no: {paso.espera}."
        return paso
    con_total = set(PortalOfferData.objects.filter(offer__in=ofertas, total__isnull=False)
                    .values_list("offer_id", flat=True))
    sin_total = len(ofertas) - len(con_total)
    orden = c.pagina.order
    primera = next((f for f in (orden.totals if orden else [])
                    if f.amount is not None and f.position == 1), None)
    if sin_total:
        paso.dato = f"Falta el total de {_plural(sin_total, 'oferta', 'ofertas')}"
    elif orden is not None and orden.warning:
        paso.dato = "Ofertas en monedas distintas: sin orden"
    elif primera is not None:
        paso.dato = f"La más baja: Oferta {primera.offer.number}"
    else:
        paso.dato = "Sin orden económico"
    if not sin_total and cuatro.estado is E.HECHO:
        paso.estado = E.HECHO
        paso.resumen = "Todas las ofertas tienen su total y el cumplimiento está completo."
        return paso
    paso.estado = E.EN_CURSO
    if sin_total:
        paso.resumen = (f"Falta el total de {_plural(sin_total, 'oferta', 'ofertas')}: "
                        "sale del acta de apertura.")
    else:
        paso.resumen = "El orden económico está listo; falta completar el cumplimiento."
    if cuatro.estado is not E.HECHO:
        paso.espera = "depende del paso 4 (cumplimiento de ofertas)"
    return paso


# --- Paso 6 · Evaluación Comisión -----------------------------------------------------------------


def _decididos(c):
    """`(decididos, total)` de los puntos no técnicos con resultado: «D de T puntos decididos».
    Los pares de las filas técnicas se deciden con el ok del informe (paso 4)."""
    tecnicas = s4_propuesta._technical_cells(c.pagina)
    decididos = sum(1 for clave, celda in c.pagina.cells.items()
                    if clave not in tecnicas and celda.state not in
                    (matrix_service.UNEVALUATED, matrix_service.PENDING))
    return decididos, decididos + c.cuentas.pairs


def _paso6(c):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[6], c.procedure)
    cuentas = c.cuentas
    evaluada = any(s.evaluated for s in c.pagina.statuses)
    decididos, total = _decididos(c)
    paso.dato = f"{decididos} de {total} puntos decididos" if total else "Sin evaluación"
    abiertas = c.abiertas(6)
    if not evaluada:
        paso.espera = "depende de que se evalúe alguna oferta (paso 4)"
        paso.resumen = f"Todavía no: {paso.espera}."
    elif not (cuentas.pairs or cuentas.questions or cuentas.discards or abiertas):
        paso.estado = E.HECHO
        paso.resumen = ("No quedan puntos por decidir, preguntas sin contestar ni descartes "
                        "por resolver.")
    else:
        paso.estado = E.EN_CURSO
        partes = []
        if cuentas.pairs:
            partes.append(_plural(cuentas.pairs, "punto sin confirmar", "puntos sin confirmar"))
        if cuentas.questions:
            partes.append(_plural(cuentas.questions, "pregunta abierta", "preguntas abiertas"))
        if cuentas.discards:
            partes.append(_plural(cuentas.discards, "descarte por resolver",
                                  "descartes por resolver"))
        paso.resumen = ("Falta: " + "; ".join(partes) + ".") if partes else "Hay decisiones por tomar."
    return paso


# --- Paso 7 · Dictamen ----------------------------------------------------------------------------


def _paso7(c, cuatro, seis, cargado):
    paso = pasos.Paso.vacio(pasos.POR_NUMERO[7], c.procedure)
    evento = next((e for e in c.plazos.events if e.key == "dictamen"), None)
    dia = evento.day if evento is not None else None
    paso.dato = ((f"Dictamen cargado el {dia:%d/%m/%Y}" if dia else "Dictamen cargado")
                 if cargado else "Sin dictamen")
    abiertas = c.abiertas(7)
    if cargado and not abiertas:
        paso.estado = E.HECHO
        paso.resumen = "El dictamen está cargado."
    elif not cargado and c.portal is not None and c.portal.state == ItemState.FALLIDO:
        paso.estado = E.CON_ERROR
        motivo = plain_reason(c.portal.failure).rstrip(".")
        paso.resumen = f"No se pudo tomar el dictamen del Portal. {motivo[:1].upper()}{motivo[1:]}."
    elif abiertas:
        paso.estado = E.EN_CURSO
        mant = c.plazos.maintenance
        if cargado:
            paso.resumen = "El dictamen está cargado; hay uno del Portal sin aprobar."
        elif any(a.kind == pasos.KIND_DICTAMEN and a.tipo == pasos.PENDIENTE for a in abiertas):
            paso.resumen = "El Portal publicó un dictamen: falta aprobar su carga."
        elif cuatro.estado is E.HECHO and seis.estado is E.HECHO:
            paso.resumen = "Los pasos 4 y 6 están hechos: falta cargar el dictamen."
        elif mant.state == "computed" and mant.due == c.hoy:
            paso.resumen = "El mantenimiento de las ofertas vence hoy: falta cargar el dictamen."
        else:
            paso.resumen = "El mantenimiento de las ofertas ya venció: falta cargar el dictamen."
    else:
        faltan = [n for n, p in ((4, cuatro), (6, seis)) if p.estado is not E.HECHO]
        paso.espera = ("depende de los pasos 4 y 6" if len(faltan) == 2
                       else f"depende del paso {faltan[0]}")
        paso.resumen = f"Todavía no: {paso.espera}."
    return paso


# --- El proceso -----------------------------------------------------------------------------------


def proceso_de(user, procedure, overview=None):
    """El `Proceso` de `procedure` para `user`: los siete pasos, cada uno con su estado propio,
    y la lista de acciones de «Qué se puede hacer ahora». Se llama una vez por pedido; con
    `overview` (el de `sections_for`) no se vuelven a calcular las secciones."""
    with memo.scope():
        if overview is None:
            overview = sections_for(user, procedure)
        hoy = ingreso.today()
        plazos = ingreso.plazos(procedure)
        subidos = s4_dictamen.uploaded_dictamenes(procedure)
        portal = s4_dictamen.portal_dictamen(procedure)
        cargado = s4_dictamen.dictamen_cargado(procedure, subidos, portal)
        pedido = {"plazos": plazos, "hoy": hoy, "dictamen_cargado": cargado}
        todas = acciones.armar(user, procedure, overview, **pedido)
        contexto = _Contexto(user, procedure, overview, todas, plazos, hoy, portal)
        uno, dos, tres, cuatro = (_paso1(contexto), _paso2(contexto), _paso3(contexto),
                                  _paso4(contexto))
        cinco, seis = _paso5(contexto, cuatro), _paso6(contexto)
        if (cuatro.estado is E.HECHO and seis.estado is E.HECHO and not cargado and not any(
                a.paso == 7 and a.kind == pasos.KIND_DICTAMEN and a.tipo == pasos.CIERRE
                for a in todas)):
            # Recién ahora se sabe que 4 y 6 están hechos: aparece «Cargar el dictamen».
            todas = acciones.armar(user, procedure, overview, pasos_4_y_6_hechos=True, **pedido)
            contexto.todas = todas
        siete = _paso7(contexto, cuatro, seis, cargado)
        calculados = {1: uno, 2: dos, 3: tres, 4: cuatro, 5: cinco, 6: seis, 7: siete}
        advertencias = acciones.advertencias(overview)
        lista = []
        for definicion in pasos.PASOS:
            paso = calculados[definicion.numero]
            paso.tareas = contexto.tareas(definicion.numero)
            paso.advertencias = list(advertencias.get(definicion.numero, []))
            paso.marca = vencimientos.marca_de(paso, plazos, hoy, dictamen_cargado=cargado)
            lista.append(paso)
        vencimiento = vencimientos.proximo(plazos, hoy, dictamen_cargado=cargado)
    return pasos.Proceso(procedure=procedure, pasos=lista, acciones=todas, terminado=cargado,
                         vencimiento=vencimiento)
