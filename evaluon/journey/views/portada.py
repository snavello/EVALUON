"""Vistas de la aplicación por secciones (plan 014, «Rutas»): lista de expedientes, portada del
procedimiento, las cinco secciones, y los bloques que pide el sondeo (la barra y la ventana del
proceso). Solo traducen y llaman a `sections_for`: no tienen formularios de decisión (P3)."""

import re
from dataclasses import dataclass, field
from functools import wraps

from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role, viewing
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.proceso import acciones, calculo, mapa, pasos
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import base as stage_base
from evaluon.journey.stages import is_viewer
from evaluon.journey.tablero import ingreso
from evaluon.journey.tablero.ingreso import KEY as INGRESO_KEY
from evaluon.journey.tablero.tiles import build_board
from evaluon.journey.temas import s4_propuesta
from evaluon.journey.window import window_for
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import DocumentKind as OfferDocumentKind
from evaluon.offers.models import Reading
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.portada.lista"
ROLE_LABELS = {CommissionRole.NONE: "Solo lectura",
               CommissionRole.OPERATOR: "Operador de la Comisión",
               CommissionRole.EVALUATOR: "Evaluador de la Comisión"}
DROPDOWN_LIMIT = 25


def overview_of(request, procedure_id):
    """Las cinco secciones del procedimiento. 404 si no existe; `RoleRejected` (403) sin rol."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    return sections_for(request.user, procedure, channel=Channel.SCREEN)


def shell(request, overview, active=""):
    """Lo que necesita el encabezado y la barra en toda pantalla del procedimiento."""
    procedure = overview.procedure
    return {
        "overview": overview, "procedure": procedure, "active": active,
        "procedures": Procedure.objects.order_by("-created_at", "-pk")[:DROPDOWN_LIMIT],
        "role_label": ROLE_LABELS.get(request.user.commission_role, ""),
        "portal_link": procedure.portal_links.order_by("-pk").first(),
        "bar_url": reverse("expedientes:barra", args=[procedure.pk]),
        "login_url": reverse("accounts:login"),
    }


# Un formulario de acción (POST), salvo el de salir y los de preferencias (la clase `preferencia`:
# el selector de tema, REQ-134; ADR-0074). Las acciones del usuario de lectura no se dibujan: el
# servicio igual lo rechazaría (403), pero un botón que no funciona confunde.
_ACTION_FORM = re.compile(
    r'<form(?=[\s>])(?=[^>]*method="post")(?![^>]*(?:logout-form|preferencia))[^>]*>.*?</form>',
    re.S | re.I)


# Los enlaces «Subir …» llevan a un formulario que el usuario de lectura no tiene (D-3 de T-227).
_UPLOAD_LINK = re.compile(r"<a\s[^>]*>\s*Subir[^<]*</a>", re.S | re.I)


def without_actions(response):
    """La respuesta HTML sin los formularios de acción ni los enlaces para subir."""
    if response.status_code == 200 and "text/html" in response.get("Content-Type", ""):
        html = _ACTION_FORM.sub("", response.content.decode())
        response.content = _UPLOAD_LINK.sub("", html)
    return response


def reading(view):
    """La vista solo lee: el usuario de lectura la ve entera y sin acciones."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        with viewing(request.user):
            response = view(request, *args, **kwargs)
        if not request.user.commission_role:
            response = without_actions(response)
        return response
    return wrapper


@require_GET
def lista(request):
    if not is_viewer(request.user):
        require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                                channel=Channel.SCREEN)
    rows = [sections_for(request.user, p, channel=Channel.SCREEN)
            for p in Procedure.objects.order_by("-created_at", "-pk")]
    return render(request, "journey/expedientes.html", {"rows": rows})


@dataclass
class _Linea:
    """Una línea de «Qué se puede hacer ahora»: la acción y el nombre de su paso."""

    accion: object
    paso_nombre: str

    @property
    def boton(self):
        """El rótulo del botón: el verbo de la línea."""
        return self.accion.boton or ("Aprobar" if self.accion.post else "Ver")

    @property
    def etiqueta(self):
        """El nombre accesible del botón: el texto de la línea, con el verbo delante solo si la
        línea no empieza ya por él («Proponer la matriz», no «Proponer: Proponer la matriz»)."""
        texto = self.accion.texto
        return texto if texto.lower().startswith(self.boton.lower()) else f"{self.boton}: {texto}"


@dataclass
class _Fila:
    """Un paso de la lista, con lo que la plantilla necesita: la clase de su etiqueta, lo que
    falta (pendientes y cierres abiertos; los faltantes menores van como advertencias) y las notas
    que aclaran un dato que de otro modo confunde (REQ-146)."""

    paso: object
    clase: str
    faltan: list = field(default_factory=list)
    nota: str = ""
    advertencias: list = field(default_factory=list)
    espera: str = ""
    sin_leer: list = field(default_factory=list)  # [(texto, url)] documentos que nadie leyó


_CLASE_DE_ESTADO = {estado: estado.value.replace("_", "-") for estado in pasos.Estado}


def _enumerar(partes):
    """«a», «a y b», «a, b y c»."""
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def nota_de_cruces(cifras):
    """La nota del paso 4: de cuántos cruces requisito–oferta habla el dato y dónde cae cada uno.
    Sale de las mismas cifras que el cuadro (`figures_of`), sin cálculo paralelo: los números de la
    frase suman el total que la encabeza. Vacía sin evaluación."""
    if cifras is None:
        return ""
    ofertas = cifras.offers
    cuentas = [(sum(o.ok for o in ofertas), "cumple", "cumplen"),
               (sum(o.no for o in ofertas), "no cumple", "no cumplen"),
               (sum(o.nd for o in ofertas), "a decidir", "a decidir"),
               (sum(o.pe for o in ofertas), "espera el resultado o el informe técnico",
                "esperan el resultado o el informe técnico"),
               (sum(o.na for o in ofertas), "no aplica", "no aplican")]
    total = sum(n for n, _, _ in cuentas)
    partes = [f"{n} {uno if n == 1 else varios}" for n, uno, varios in cuentas
              if n or uno != "no aplica"]
    return (f"De {total} cruce{'' if total == 1 else 's'} requisito–oferta: "
            f"{_enumerar(partes)}.")


def _nota_del_paso(paso, cifras):
    """El desglose que explica el dato de un paso (avisos de T-345/T-346). El «D de T puntos
    decididos» del paso 6 cuenta como pendientes los «cumple» y «no cumple» que nadie confirmó; el
    dato del paso 4 es de otra cuenta, los cruces requisito–oferta."""
    if paso.numero == 6:
        cuentas = {t.kind: t.cuenta for t in paso.tareas}
        partes = [formato.format(cuentas[kind]) for kind, formato in (
            (acciones.K_DECIDIR, "{} sin determinar"), (acciones.K_NO_CUMPLE, "{} «no cumple»"),
            (acciones.K_CUMPLE, "{} «cumple» sin confirmar")) if cuentas.get(kind)]
        return f"Los puntos sin decidir son {_enumerar(partes)}." if partes else ""
    if paso.numero == 4 and "cumplen" in paso.dato:
        return nota_de_cruces(cifras)
    return ""


_DEPENDE_DE_UN_PASO = re.compile(r"depende del paso (\d)\b")


def _espera(paso, nombres):
    """Lo que el paso espera, dicho una sola vez y con el nombre real del otro paso; vacío si su
    resumen ya lo dice («Todavía no: depende de …»)."""
    if not paso.espera or paso.espera in paso.resumen:
        return ""
    uno = _DEPENDE_DE_UN_PASO.match(paso.espera)
    if uno:
        return f"Depende del paso {uno[1]}, {nombres[int(uno[1])]}."
    return paso.espera[:1].upper() + paso.espera[1:] + "."


def _sin_leer(overview, procedure):
    """Los documentos de las ofertas que nadie leyó, por oferta, con su enlace al lugar de la
    sección Ofertas donde está (la fila de la oferta). Si la lectura corre, lo dice."""
    etapa = next(e for e in overview.journey.stages if e.key == "ofertas")
    leyendo = etapa.state == stage_base.EN_CURSO
    ofertas = {o.pk: o.number for o in memo.offers(procedure)}
    cuentas = {}
    for oferta_id in (OfferDocument.objects.filter(offer__in=list(ofertas))
                      .exclude(kind=OfferDocumentKind.INFORME_TECNICO)
                      .annotate(leido=Exists(Reading.objects.filter(document=OuterRef("pk"))))
                      .filter(leido=False).values_list("offer_id", flat=True)):
        cuentas[oferta_id] = cuentas.get(oferta_id, 0) + 1
    base = reverse("expedientes:ofertas", args=[procedure.pk])
    lineas = []
    for oferta_id, n in sorted(cuentas.items(), key=lambda kv: ofertas[kv[0]]):
        documentos = f"{n} documento" + ("" if n == 1 else "s")
        texto = (f"Se está leyendo {documentos} de la Oferta {ofertas[oferta_id]}." if leyendo else
                 f"Falta leer {documentos} de la Oferta {ofertas[oferta_id]}.")
        lineas.append((texto, f"{base}#s3-anexos-oferta-{ofertas[oferta_id]}"))
    return lineas


def _fila(paso, proceso, nombres, cifras, overview):
    faltan = [_Linea(t, paso.nombre) for t in paso.tareas
              if t.tipo != pasos.FALTANTE or paso.estado is not pasos.Estado.HECHO]
    # Una advertencia que el resumen del paso ya dice no se repite.
    advertencias = [t for t in paso.advertencias if t.rstrip(".") not in paso.resumen]
    sin_leer = (_sin_leer(overview, proceso.procedure)
                if paso.numero == 3 and paso.estado is not pasos.Estado.HECHO else [])
    return _Fila(paso, _CLASE_DE_ESTADO[paso.estado], faltan, _nota_del_paso(paso, cifras),
                 advertencias, _espera(paso, nombres), sin_leer)


def _resumen(proceso, cantidad_ofertas):
    """«N ofertas · X pasos hechos, Y en curso, Z sin empezar» (y los que tienen error)."""
    cuentas = {estado: sum(1 for p in proceso.pasos if p.estado is estado)
               for estado in pasos.Estado}
    hechos = cuentas[pasos.Estado.HECHO]
    partes = [f"{hechos} hecho" + ("" if hechos == 1 else "s"), f"{cuentas[pasos.Estado.EN_CURSO]} en curso",
              f"{cuentas[pasos.Estado.TODAVIA_NO]} sin empezar"]
    if cuentas[pasos.Estado.CON_ERROR]:
        partes.append(f"{cuentas[pasos.Estado.CON_ERROR]} con error")
    ofertas = f"{cantidad_ofertas} oferta" + ("" if cantidad_ofertas == 1 else "s")
    return f"{ofertas} · {', '.join(partes)}"


TARJETA_TAREAS = 3  # tareas que muestra una tarjeta del mapa; el resto es «+ N más»
VISTAS = ("mapa", "lista")


@dataclass
class _Tarjeta:
    """Una tarjeta del mapa: el mismo `Paso` y las mismas líneas que la lista (REQ-158). Nada se
    calcula en la plantilla: `tareas` son las primeras de `_Fila.faltan` y `depende` sale de
    `mapa.CONECTORES`."""

    fila: object
    tareas: list
    mas: int
    depende: list

    @property
    def paso(self):
        return self.fila.paso


@dataclass
class _Mapa:
    """Todo lo que `_mapa.html` y `_plazos.html` dibujan. `vista` es `mapa` o `lista`; nunca se
    guarda (ni cookie ni sesión): viene de `?vista=`."""

    vista: str
    tarjetas: list
    conectores: list  # [(Conector, lleno)]
    geometria: object  # `mapa.Geometria`: posiciones, lienzo y conectores para el contenido de ESTA portada
    eje: object
    sin_fecha: list  # los hitos sin fecha, con su motivo (el dictamen sin fecha no se lista)
    niveles: int  # el nivel más bajo de la línea de plazos (0, 1 o 2)
    marca_mantenimiento: str
    leyenda_marcas: list
    url_mapa: str
    url_lista: str


def _alto_de(tarjeta):
    """El alto estimado (siempre por encima del real) de una tarjeta: lo mismo que dibuja `_mapa.html`."""
    paso, fila = tarjeta.paso, tarjeta.fila
    tareas = [(t.accion.texto, bool(t.accion.marca)) for t in tarjeta.tareas]
    if not tareas and paso.espera:
        tareas = [(paso.espera, False)]
    return mapa.alto_estimado(paso.nombre, paso.dato, tareas, bool(tarjeta.mas or fila.advertencias))


def _geometria_de(tarjetas):
    """Los escalones de la fila de arriba y de la de abajo, según el alto estimado de sus tarjetas."""
    altos = {t.paso.numero: _alto_de(t) for t in tarjetas}
    return mapa.geometria(mapa.escalon(max(altos[n] for n in mapa.FILA_ARRIBA)),
                          mapa.escalon(max(altos[n] for n in mapa.FILA_ABAJO)))


def _vista(request):
    """`?vista=mapa|lista`; cualquier otro valor es el mapa."""
    pedida = request.GET.get("vista", "")
    return pedida if pedida in VISTAS else "mapa"


def _mapa_de(request, proceso, filas, nombres):
    """Las tarjetas, los conectores y la línea de plazos de la portada, de ESE `Proceso` y de las
    mismas filas que dibuja la lista."""
    tarjetas = [_Tarjeta(f, f.faltan[:TARJETA_TAREAS], max(0, len(f.faltan) - TARJETA_TAREAS),
                         [f"{o}. {nombres[o]}" for o, d in mapa.CONECTORES if d == f.paso.numero])
                for f in filas]
    geometria = _geometria_de(tarjetas)
    conectores = [(c, proceso.pasos[c.origen - 1].estado is pasos.Estado.HECHO)
                  for c in geometria.trazos]
    marcas = {p.marca for p in proceso.pasos} | {t.marca for t in proceso.acciones}
    hay = [(clave, texto) for clave, texto in pasos.TEXTOS_MARCA.items() if clave in marcas]
    base = request.path
    eje = mapa.hitos_en_eje(ingreso.plazos(proceso.procedure).events)
    return _Mapa(
        vista=_vista(request), tarjetas=tarjetas, conectores=conectores, geometria=geometria,
        eje=eje, sin_fecha=[s for s in eje.sin_fecha if s.key != "dictamen"],
        niveles=max((h.nivel for h in eje.hitos), default=0),
        marca_mantenimiento=proceso.pasos[6].marca, leyenda_marcas=hay,
        url_mapa=f"{base}?vista=mapa", url_lista=f"{base}?vista=lista#pasos")


@require_GET
@memo.scoped
@reading
def portada(request, procedure_id):
    """La portada del procedimiento (REQ-143, REQ-146, REQ-147, REQ-148; plan 018): el título con
    su resumen y «Abrir indicadores», «Qué se puede hacer ahora» (6 líneas y «ver las N
    restantes») y la lista de los siete pasos con su estado propio. El mapa del proceso va arriba de
    «Qué se puede hacer ahora» (T-350). Un solo `sections_for` y un solo `proceso_de` por pedido;
    la plantilla no calcula nada. El procedimiento que no existe da 404."""
    overview = overview_of(request, procedure_id)
    procedure = overview.procedure
    proceso = calculo.proceso_de(request.user, procedure, overview)
    nombres = {p.numero: p.nombre for p in proceso.pasos}
    visibles, restantes = acciones.cortar(proceso.acciones)
    vencimiento = proceso.vencimiento
    with viewing(request.user):
        cifras = s4_propuesta.figures_of(
            memo.matrix_page(request.user, procedure.pk, channel=Channel.SCREEN))
    filas = [_fila(p, proceso, nombres, cifras, overview) for p in proceso.pasos]
    context = shell(request, overview)
    context.update({
        "proceso": proceso,
        "resumen": _resumen(proceso, len(memo.offers(procedure))),
        "visibles": [_Linea(a, nombres[a.paso]) for a in visibles],
        "restantes": [_Linea(a, nombres[a.paso]) for a in restantes],
        "filas": filas, "mapa": _mapa_de(request, proceso, filas, nombres),
        "vencimiento": vencimiento,
        "vencimiento_paso": nombres[vencimiento.paso] if vencimiento else "",
        "puede_actuar": bool(request.user.commission_role),
        "next_url": request.path,
        "indicadores_url": reverse("expedientes:procedimiento", args=[procedure.pk]),
    })
    return render(request, "journey/portada.html", context)


@require_GET
@memo.scoped
@reading
def seccion(request, procedure_id, key):
    overview = overview_of(request, procedure_id)
    section = overview.get(key)
    contexts = {tema.KEY: tema.context(request.user, overview.procedure, request)
                for tema in section.temas}
    context = shell(request, overview, active=key)
    if section.ingreso_template:
        # El primer panel (T-321): foto, datos principales y pendiente general. Los mosaicos
        # propios de la sección lo leen de `contexts`.
        ingreso = section.ingreso_context(request.user, overview.procedure, request, overview)
        contexts[INGRESO_KEY] = ingreso
        context.update(ingreso)
    context.update({
        "section": section,
        "pending_rows": [(section, item) for item in section.pending_items],
        "suggestion_rows": [(section, item) for item in section.suggestion_items],
    })
    board = build_board(section, request.user, overview.procedure, contexts, request)
    # Cada detalle se dibuja acá, con el contexto completo de la página (los parciales usan
    # `procedure`, `section` y el pedido), y llega a la plantilla como HTML.
    context.update({
        "board": board.tiles, "abre": board.abre,
        "details": [{"id": d.id, "title": d.title, "html": render_to_string(
            d.template, {**context, **d.context}, request=request)} for d in board.details],
        "blocks": [{"key": tema.KEY, "partial": tema.PARTIAL, "t": contexts[tema.KEY]}
                   for tema in board.leftover],
    })
    return render(request, "journey/seccion.html", context)


@require_GET
@memo.scoped
@reading
def barra(request, procedure_id):
    """Solo la barra de las cinco secciones, lo que pide el sondeo (ADR-0045). Sin `base.html`:
    así no consume el aviso de fin de pedidos."""
    overview = overview_of(request, procedure_id)
    active = request.GET.get("activa", "")
    response = render(request, "journey/_barra.html", {"overview": overview, "active": active,
                                                       "bar_url": request.path})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
@memo.scoped
@reading
def ventana(request, procedure_id):
    """Solo la ventana del proceso, para el sondeo de la portada."""
    overview = overview_of(request, procedure_id)
    response = render(request, "journey/_window.html",
                      {"window": window_for(overview.procedure)})
    response["Cache-Control"] = "no-store"
    return response
