"""Las líneas de «Qué se puede hacer ahora» (REQ-146, REQ-147, REQ-157; plan 018, «Acciones»; T-344).

Se arman desde el `Overview` que devuelve `sections_for` (secciones 1 a 4; Normativas queda fuera)
y desde el `matrix_page` de la evaluación. No consultan nada que el sistema no calcule ya, no
escriben y no deciden estados (P3). Tres familias, todas con un `Accion` (`pasos.Accion`):

- **Pendientes** (`tipo = pendiente`): los renglones de `pending_items`, repartidos en un paso por
  su `origen` (`PASO_DE_ORIGEN`) y agrupados por `(paso, kind)` con la cuenta sumada. La suma de
  sus cuentas es `Overview.pending` menos las de Normativas. El `par` de la evaluación (paso 6)
  se parte con `s4_propuesta._bucket`, la definición única del estado de una celda, en «Decidir N
  puntos no determinados», «Revisar N “no cumple”» y «Confirmar N propuestas “cumple”».
- **Cierres** (`tipo = cierre`, cuenta 0): siete acciones, cada una con su disparador.
- **Faltantes** (`tipo = faltante`, cuenta 0): los `Missing` de `Section.tema_missing` que ninguna
  línea de pendiente o de cierre cubre. No cambian el estado del paso: cada uno es además una
  advertencia del paso (`advertencias`).

Orden: lo vencido, lo que vence hoy, y después pendientes, cierres y faltantes; dentro de cada
grupo, por paso. `cortar` deja las primeras `TOPE_VISIBLES` y el resto para «ver las N restantes».
Una acción que depende de otra todavía no hecha no se lista: sin matriz validada no hay acciones
de los pasos 4 y 6 (salvo resolver un error).

El renglón agrupado de `group_items` pierde su `kind`; `_kind` lo recupera por el sustantivo con
que se arma su texto (`NOMBRES_DE_TIPO`), que `test_acciones.py` compara con los temas.
"""

from dataclasses import dataclass, field

from django.urls import reverse

from evaluon.accounts import permissions
from evaluon.assessment.models import Run
from evaluon.assessment.services import matrix as matrix_service
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.proceso import pasos, vencimientos
from evaluon.journey.stages import base as stage_base
from evaluon.journey.tablero import ingreso
from evaluon.journey.temas import s2_documentos, s3_circulares, s3_ofertas
from evaluon.journey.temas import s4_dictamen, s4_informe, s4_propuesta
from evaluon.journey.window import plain_reason
from evaluon.offers.models import DocumentKind as OfferDocumentKind
from evaluon.offers.services import document_history
from evaluon.offers.services.offers import offer_ids_with_documents
from evaluon.tenders.services.validation import latest_validated

TOPE_VISIBLES = 6

# Las secciones que arman la lista (la 5, Normativas, no es de un paso).
SECCIONES = ("procedimiento", "pliego", "ofertas", "evaluacion")

# A qué paso pertenece el renglón de cada origen (`Item.origen`, `Missing.origen`).
PASO_DE_ORIGEN = {
    "etapa:portal": 1, "s1_portal": 1, "s1_datos": 1, "etapa:pliego": 1, "s2_documentos": 1,
    "etapa:matriz": 2, "s2_matriz": 2, "s3_circulares": 2,
    "etapa:ofertas": 3, "s3_ofertas": 3, "s3_ficha": 3, "s3_anexos": 3,
    "etapa:evaluacion": 4, "s4_informe": 4,
    "etapa:matriz_evaluacion": 6, "s4_propuesta": 6, "s4_descartes": 6, "s4_preguntas": 6,
    "s4_dictamen": 7,
}
# Respaldo si aparece un origen nuevo: el paso por omisión de su sección.
PASO_DE_SECCION = {"procedimiento": 1, "pliego": 2, "ofertas": 3, "evaluacion": 6}
# La etapa de la 013 que falló, y el paso al que pertenece su error.
PASO_DE_ETAPA = {"portal": 1, "pliego": 1, "matriz": 2, "ofertas": 3, "evaluacion": 4,
                 "matriz_evaluacion": 6}

# Sustantivo (lo que sigue a la cuenta en el texto de un renglón agrupado) -> `kind`.
NOMBRES_DE_TIPO = {
    "pares por decidir": "par",
    "preguntas abiertas": "pregunta",
    "ofertas sin el ok del informe técnico": "informe_ok",
    "ofertas sin informe técnico": "informe_falta",
    "descartes propuestos por decidir": "descarte",
    "ofertas con filas de la ficha por confirmar": "ficha",
    "ofertas subidas con nombre y CUIT para aprobar": "oferta_borrador",
    "ofertas subidas que no se pudieron leer": "oferta_borrador_fallida",
}

# `kind` de las acciones (el id es `"<paso>-<tipo>-<kind>"`).
K_PORTAL = "portal"
K_CIRCULAR_VALIDAR = "circular_validar"
K_CIRCULAR_ABRIR = "circular_abrir"
K_MATRIZ = "matriz"
K_BORRADORES = "borradores"
K_FICHA = "ficha"
K_INFORME_FALTA = "informe_falta"
K_INFORME_OK = "informe_ok"
K_DECIDIR = "decidir"
K_NO_CUMPLE = "no_cumple"
K_CUMPLE = "cumple"
K_PREGUNTA = "pregunta"
K_DESCARTE = "descarte"
K_ETAPA = "etapa"
K_PROPONER = "proponer_matriz"
K_VALIDAR = "validar_matriz"
K_TOMAR = "tomar_portal"
K_EVALUAR = "evaluar"
K_ERROR = "error"
K_DATOS = "datos"
K_SIN_BAJAR = "documentos_sin_bajar"
K_COMPLIANCE = "compliance"
K_SIN_OFERTAS = "sin_ofertas"

# Los `Missing` que ya cubre una línea de pendiente o de cierre (no se repiten como faltante).
_CUBIERTOS = {
    "s3_circulares", "s4_informe", "s4_dictamen",  # tomar del Portal / informe falta / dictamen
}
_ACCION_TOMAR = "Tomar del Portal"
_ACCION_ACTA = "Agregar oferta desde el Portal"


@dataclass
class Lista:
    """Lo que dibuja el bloque: todas las acciones en orden y el corte de 6."""

    todas: list = field(default_factory=list)
    visibles: list = field(default_factory=list)
    restantes: list = field(default_factory=list)


def _plural(n, uno, varios):
    return f"{n} {uno if n == 1 else varios}"


def _kind(item):
    """El `kind` de un renglón; si se agrupó (perdió el `kind`), el que dice su sustantivo."""
    if item.kind:
        return item.kind
    return NOMBRES_DE_TIPO.get(item.text.partition(" ")[2], "")


def _paso_de(origen, seccion):
    return PASO_DE_ORIGEN.get(origen) or PASO_DE_SECCION[seccion.key]


def _secciones(overview):
    return [s for s in overview.sections if s.key in SECCIONES]


# --- Pendientes -----------------------------------------------------------------------------------


def _pares_por_estado(user, procedure):
    """`{decidir, no_cumple, cumple}`: los pares `propuesto` de las filas no técnicas, partidos por
    `s4_propuesta._bucket`. Los de las filas técnicas se deciden con el ok del informe."""
    with permissions.viewing(user):
        page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    tecnicas = s4_propuesta._technical_cells(page)
    cuentas = {K_DECIDIR: 0, K_NO_CUMPLE: 0, K_CUMPLE: 0}
    for clave, celda in page.cells.items():
        if celda.state != matrix_service.PENDING or clave in tecnicas:
            continue
        balde = s4_propuesta._bucket(celda)
        cuentas[{"ok": K_CUMPLE, "no": K_NO_CUMPLE}.get(balde, K_DECIDIR)] += 1
    return cuentas


def _texto_pares(kind, n):
    if kind == K_DECIDIR:
        return f"Decidir {_plural(n, 'punto no determinado', 'puntos no determinados')}"
    if kind == K_NO_CUMPLE:
        return f"Revisar {_plural(n, '“no cumple”', '“no cumple”')}"
    return f"Confirmar {_plural(n, 'propuesta “cumple”', 'propuestas “cumple”')}"


def _agrupar(overview):
    """`{(paso, kind): {"cuenta", "primero", "items"}}` con los renglones de pendientes."""
    grupos = {}
    for seccion in _secciones(overview):
        for item in seccion.pending_items:
            paso = _paso_de(item.origen, seccion)
            kind = _kind(item)
            if item.origen in ("s2_matriz", "etapa:matriz"):
                kind = K_MATRIZ
            elif item.origen == "s3_circulares":
                kind = K_CIRCULAR_VALIDAR if item.action == "Validar" else K_CIRCULAR_ABRIR
            elif item.origen in ("s1_portal", "etapa:portal"):
                kind = K_PORTAL
            elif item.origen == "s3_ofertas":
                kind = K_BORRADORES
            elif item.origen == "s4_dictamen":
                kind = pasos.KIND_DICTAMEN
            elif item.origen.startswith("etapa:") or not kind:
                kind = K_ETAPA if item.origen.startswith("etapa:") else (kind or K_ETAPA)
            grupo = grupos.setdefault((paso, kind), {"cuenta": 0, "primero": item, "items": []})
            grupo["cuenta"] += item.count
            grupo["items"].append(item)
    return grupos


def _url_evaluacion(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def _linea_pendiente(paso, kind, grupo, procedure):
    """`(texto, boton, url, post)` de un grupo de pendientes."""
    n, primero = grupo["cuenta"], grupo["primero"]
    url, boton, post = primero.group_url or primero.url or "", primero.action or "Ver", None
    ev = _url_evaluacion(procedure)
    if kind == K_PORTAL:
        texto, url, boton = f"Aprobar lo que leyó el sistema del Portal ({n})", primero.url, "Aprobar"
    elif kind == K_CIRCULAR_VALIDAR:
        texto, url = "Validar la versión con la circular" + (f" ({n})" if n > 1 else ""), primero.url
    elif kind == K_CIRCULAR_ABRIR:
        texto, url = "Abrir la versión nueva de la matriz" + (f" ({n})" if n > 1 else ""), primero.url
    elif kind == K_MATRIZ:
        base = reverse("expedientes:pliego", args=[procedure.pk])
        texto, url, boton = f"Validar la matriz: {n} por resolver", f"{base}?filtro=falta#s2-matriz", "Resolver"
    elif kind == K_BORRADORES:
        texto, boton = f"Revisar {_plural(n, 'oferta subida', 'ofertas subidas')} por archivos", "Revisar"
        url = primero.url if len(grupo["items"]) == 1 else (primero.group_url or primero.url)
    elif kind == K_FICHA:
        texto, boton = f"Confirmar {_plural(n, 'fila', 'filas')} de la ficha", "Resolver"
    elif kind == K_INFORME_FALTA:
        texto = f"Cargar el informe técnico del área (falta en {_plural(n, 'oferta', 'ofertas')})"
        url, boton = f"{ev}{s4_informe.ANCHOR}", "Subir"
    elif kind == K_INFORME_OK:
        texto = f"Dar el ok al informe técnico ({_plural(n, 'oferta', 'ofertas')})"
        url, boton = f"{ev}{s4_informe.ANCHOR}", "Resolver"
    elif kind == "pregunta":
        texto, url, boton = f"Contestar {_plural(n, 'pregunta', 'preguntas')}", f"{ev}?preg=abiertas#s4-preguntas", "Responder"
    elif kind == "descarte":
        texto, boton = f"Resolver {_plural(n, 'descarte propuesto', 'descartes propuestos')}", "Resolver"
    elif kind == pasos.KIND_DICTAMEN:
        texto, post = "Aprobar el dictamen publicado en el Portal", primero.post
        url = primero.url or ""
    else:  # el renglón genérico de una etapa
        texto = " · ".join(i.text for i in grupo["items"])
    return texto, boton, url or "", post


def _pendientes(user, procedure, overview):
    acciones = []
    grupos = _agrupar(overview)
    for (paso, kind), grupo in sorted(grupos.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if kind == "par":
            continue  # se parte por estado de la celda
        texto, boton, url, post = _linea_pendiente(paso, kind, grupo, procedure)
        acciones.append(pasos.Accion(paso, pasos.PENDIENTE, kind, texto, grupo["cuenta"], boton,
                                     url, post))
    if (6, "par") in grupos:
        base = grupos[(6, "par")]["primero"]
        url = base.group_url or base.url or ""
        for kind, n in _pares_por_estado(user, procedure).items():
            if n:
                acciones.append(pasos.Accion(6, pasos.PENDIENTE, kind, _texto_pares(kind, n), n,
                                             "Resolver", url))
    return acciones


# --- Cierres --------------------------------------------------------------------------------------


def _etapas(overview):
    return {stage.key: stage for stage in overview.journey.stages}


def _sin_usar(documento, corrida):
    """Si la última evaluación de la oferta dejó afuera este documento vigente. Una evaluación
    guarda los documentos que usó en `Run.documents`; si esa lista está vacía (corridas que no la
    registraron) se compara por fecha: el documento se cargó después de armarse."""
    usados = {entrada.get("document") for entrada in (corrida.documents or [])}
    if usados:
        return documento.pk not in usados
    return documento.loaded_at > corrida.built_at


def _hay_que_evaluar(procedure, version, ofertas):
    """Alguna oferta con documentos sin evaluación de la versión validada, o con un documento
    vigente que su última evaluación no tuvo en cuenta (`stages/evaluacion.py`, plan punto 3)."""
    con = offer_ids_with_documents(ofertas)
    for oferta in (o for o in ofertas if o.pk in con):
        corrida = (Run.objects.filter(offer=oferta, matrix_version=version)
                   .order_by("-built_at", "-pk").first())
        if corrida is None:
            return True
        vigentes = document_history.current_documents(oferta).exclude(
            kind=OfferDocumentKind.INFORME_TECNICO)
        if any(_sin_usar(d, corrida) for d in vigentes):
            return True
    return False


def _cierres(procedure, overview, pendientes, plazos, hoy, dictamen_cargado, hechos_4_y_6):
    etapas = _etapas(overview)
    acciones = []
    pliego_url = reverse("expedientes:pliego", args=[procedure.pk])
    # «Validar la matriz» no se repite si ya hay un pendiente que lleva al mismo lugar: los
    # renglones de la matriz por resolver o la validación de la versión con una circular.
    cubre_validar = any(a.paso == 2 and a.kind in (K_MATRIZ, K_CIRCULAR_VALIDAR)
                        for a in pendientes)

    matriz = etapas.get("matriz")
    if (matriz is not None and matriz.state == stage_base.PENDIENTE
            and etapas["pliego"].state == stage_base.LISTA):
        acciones.append(pasos.Accion(2, pasos.CIERRE, K_PROPONER, "Proponer la matriz", 0,
                                     "Proponer", pliego_url))
    if matriz is not None and matriz.state == stage_base.A_DECIDIR and not cubre_validar:
        acciones.append(pasos.Accion(2, pasos.CIERRE, K_VALIDAR, "Validar la matriz", 0,
                                     "Validar", pliego_url))

    faltan = (len(s2_documentos.missing_from_portal(procedure))
              + len(s3_circulares.missing_from_portal(procedure)))
    if faltan:
        acciones.append(pasos.Accion(
            1, pasos.CIERRE, K_TOMAR, f"Tomar del Portal lo que lista y no se tomó ({faltan})",
            0, _ACCION_TOMAR, s2_documentos.portal_url(procedure)))

    acta = s3_ofertas.portal_offers(procedure)
    if acta:
        acciones.append(pasos.Accion(
            3, pasos.CIERRE, pasos.KIND_ACTA,
            "Agregar las ofertas del acta", 0, "Agregar",
            f"{s3_ofertas.tab_url(procedure.pk, 'alta=portal')}#s3-alta-portal"))

    version = latest_validated(procedure)
    if (version is not None and etapas["evaluacion"].state != stage_base.EN_CURSO
            and _hay_que_evaluar(procedure, version, memo.offers(procedure))):
        acciones.append(pasos.Accion(4, pasos.CIERRE, K_EVALUAR, "Evaluar las ofertas", 0,
                                     "Evaluar", _url_evaluacion(procedure)))

    for clave, etapa in etapas.items():
        if etapa.state == stage_base.CON_ERROR:
            acciones.append(pasos.Accion(
                PASO_DE_ETAPA[clave], pasos.CIERRE, f"{K_ERROR}_{clave}",
                f"Resolver el error: «{plain_reason(etapa.error)}»", 0, "Ver", etapa.view_url or ""))

    if not dictamen_cargado and not s4_dictamen_pendiente(overview):
        mant = plazos.maintenance
        vence = mant.state == "computed" and mant.due <= hoy
        if hechos_4_y_6 or vence:
            acciones.append(pasos.Accion(
                7, pasos.CIERRE, pasos.KIND_DICTAMEN, "Cargar el dictamen", 0, "Subir",
                f"{s4_dictamen._tab(procedure)}{s4_dictamen.ANCHOR}"))
    return acciones


def s4_dictamen_pendiente(overview):
    """Si el Portal publicó un dictamen sin aprobar: esa línea de pendiente cubre al cierre."""
    return any(i.origen == "s4_dictamen" for i in overview.get("evaluacion").pending_items)


# --- Faltantes ------------------------------------------------------------------------------------


def _faltantes_sueltos(overview):
    """`[(paso, Missing)]` de `Section.tema_missing` que ninguna línea de pendiente o de cierre
    cubre. Los de una etapa (`etapa:*`) son el estado de esa etapa, que cubre un cierre o la
    dependencia entre pasos."""
    sueltos = []
    for seccion in _secciones(overview):
        for m in seccion.tema_missing:
            if m.origen.startswith("etapa:") or m.origen in _CUBIERTOS:
                continue
            if m.origen == "s2_documentos" and m.action == _ACCION_TOMAR:
                continue
            if m.origen == "s3_ofertas" and m.action == _ACCION_ACTA:
                continue
            sueltos.append((_paso_de(m.origen, seccion), m))
    return sueltos


def advertencias(overview):
    """`{paso: [texto, ...]}`: cada faltante suelto es una advertencia de su paso (REQ-146)."""
    por_paso = {}
    for paso, m in _faltantes_sueltos(overview):
        por_paso.setdefault(paso, []).append(m.text)
    return por_paso


def _faltantes(overview):
    grupos = {}
    for paso, m in _faltantes_sueltos(overview):
        kind = {"s1_datos": K_DATOS, "s2_documentos": K_SIN_BAJAR, "s3_anexos": K_COMPLIANCE,
                "s3_ofertas": K_SIN_OFERTAS}.get(m.origen, f"falta_{m.origen}")
        grupos.setdefault((paso, kind), []).append(m)
    acciones = []
    for (paso, kind), lista in sorted(grupos.items()):
        n, primero = len(lista), lista[0]
        if kind == K_DATOS:
            texto = (primero.text if n == 1
                     else f"Tomar del Portal lo que falta de los datos ({n})")
        elif kind == K_SIN_BAJAR:
            texto = "Subir los documentos que no se pudieron bajar"
        elif kind == K_COMPLIANCE:
            texto = f"Subir la hoja de compliance ({_plural(n, 'oferta', 'ofertas')})"
        elif kind == K_SIN_OFERTAS:
            texto = "Subir los archivos de una oferta"
        else:
            texto = primero.text if n == 1 else f"{primero.text} ({n})"
        acciones.append(pasos.Accion(paso, pasos.FALTANTE, kind, texto, 0,
                                     primero.action or "Ver", primero.url or ""))
    return acciones


# --- Orden y corte --------------------------------------------------------------------------------

_GRUPO_MARCA = {pasos.MARCA_VENCIDO: 0, pasos.MARCA_HOY: 1}
_ORDEN_TIPO = {pasos.PENDIENTE: 0, pasos.CIERRE: 1, pasos.FALTANTE: 2}


def ordenar(acciones):
    """Vencido, vence hoy, pendientes, cierres y faltantes; dentro de cada grupo, por paso. Es
    estable: a igual grupo y paso se conserva el orden en que se armaron."""
    return sorted(acciones, key=lambda a: (_GRUPO_MARCA.get(a.marca, 2),
                                           _ORDEN_TIPO[a.tipo] if a.marca == "" else 0, a.paso))


def cortar(acciones, tope=TOPE_VISIBLES):
    """`(visibles, restantes)`: las primeras `tope` y el resto, en el mismo orden."""
    return list(acciones[:tope]), list(acciones[tope:])


def _depende_de_la_matriz(accion):
    return accion.paso in (4, 6) and not accion.kind.startswith(K_ERROR)


def armar(user, procedure, overview, *, pasos_4_y_6_hechos=False, plazos=None, hoy=None,
          dictamen_cargado=None):
    """Todas las acciones de «Qué se puede hacer ahora», ordenadas y con su marca de vencimiento.

    `pasos_4_y_6_hechos` lo calcula quien arma los pasos (T-345/T-346): sin él, «Cargar el
    dictamen» solo aparece si el mantenimiento vence hoy o ya venció. `plazos`, `hoy` y
    `dictamen_cargado` se leen del procedimiento si no se pasan."""
    hoy = hoy or ingreso.today()
    plazos = plazos if plazos is not None else ingreso.plazos(procedure)
    if dictamen_cargado is None:
        dictamen_cargado = s4_dictamen.dictamen_cargado(procedure)
    pendientes = _pendientes(user, procedure, overview)
    todas = (pendientes
             + _cierres(procedure, overview, pendientes, plazos, hoy, dictamen_cargado,
                        pasos_4_y_6_hechos)
             + _faltantes(overview))
    if latest_validated(procedure) is None:
        todas = [a for a in todas if not _depende_de_la_matriz(a)]
    for accion in todas:
        accion.marca = vencimientos.marca_de(accion, plazos, hoy, dictamen_cargado=dictamen_cargado)
    return ordenar(todas)


def lista(user, procedure, overview, **kwargs):
    """`armar` con el corte de 6 ya hecho."""
    todas = armar(user, procedure, overview, **kwargs)
    visibles, restantes = cortar(todas)
    return Lista(todas, visibles, restantes)
