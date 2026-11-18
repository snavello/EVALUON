"""Las líneas de «Qué se puede hacer ahora» contra lo que el sistema ya calcula (REQ-146, REQ-147,
REQ-157; T-344). Los tres casos son los de `conftest.py` (caso chico inventado, P4)."""

import dataclasses
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from evaluon.journey.proceso import acciones, pasos
from evaluon.journey.sections import sections_for
from evaluon.journey.sections.base import Item, group_items
from evaluon.journey.tablero import ingreso
from evaluon.tenders.models import Job, JobKind, JobStatus

pytestmark = pytest.mark.django_db

HOY = date(2026, 10, 21)
TEMAS = Path(__file__).resolve().parents[3] / "evaluon" / "journey" / "temas"
LOS_TRES = ["caso_recien_cargado", "caso_varios_en_curso", "caso_todo_hecho"]


def _ids(lista):
    return [a.id for a in lista]


def _armar(caso, **kwargs):
    overview = sections_for(caso.user, caso.procedure)
    return overview, acciones.armar(caso.user, caso.procedure, overview, **kwargs)


def _pendientes_de_hoy(overview):
    """El contador de hoy sin Normativas (la sección 5 no es de un paso)."""
    return overview.pending - overview.get("normativas").pending


def _pendientes(lista):
    return [a for a in lista if a.tipo == pasos.PENDIENTE]


def _sin_cubrir(overview):
    """Los `Missing` de las secciones 1 a 4 que SÍ son una línea de faltante, escritos acá
    aparte para que el test no repita el código: los cubiertos por un pendiente o un cierre son
    los del Portal, el acta, el informe, el dictamen y los de una etapa."""
    cubiertos_por_accion = {("s2_documentos", "Tomar del Portal"),
                            ("s3_ofertas", "Agregar oferta desde el Portal")}
    cubiertos_por_tema = {"s3_circulares", "s4_informe", "s4_dictamen"}
    return [m for s in overview.sections if s.key != "normativas" for m in s.tema_missing
            if not m.origen.startswith("etapa:") and m.origen not in cubiertos_por_tema
            and (m.origen, m.action) not in cubiertos_por_accion]


# --- (a) la suma de las líneas de pendientes es el contador de hoy ---------------------------------


def test_req147_recien_cargado_lista_literal(caso_recien_cargado):
    """REQ-147: recién cargado no tiene pendientes (suma 0 = contador); la lista es proponer la
    matriz y los dos faltantes sueltos; ningún cierre de más."""
    overview, lista = _armar(caso_recien_cargado)
    assert sum(a.cuenta for a in _pendientes(lista)) == _pendientes_de_hoy(overview) == 0
    assert _ids(lista) == ["2-cierre-proponer_matriz", "1-faltante-datos",
                           "3-faltante-sin_ofertas"]
    assert [a.texto for a in lista] == [
        "Proponer la matriz", "Tomar del Portal lo que falta de los datos (2)",
        "Subir los archivos de una oferta"]
    assert all(a.cuenta == 0 for a in lista) and all(a.marca == "" for a in lista)
    assert acciones.advertencias(overview) == {
        1: ["Falta el expediente, el cronograma y las garantías",
            "Faltan los renglones con su cantidad"],
        3: ["Todavía no hay ofertas"]}


def test_req147_varios_en_curso_lista_literal(caso_varios_en_curso):
    """REQ-147: en «varios en curso» la suma de cuentas es el contador (19) y el paso 6 se parte
    en 6 no determinados, 1 «no cumple» y 5 «cumple» propuestos (las 6 filas técnicas esperan
    el informe y cuentan en el paso 4)."""
    overview, lista = _armar(caso_varios_en_curso)
    assert overview.pending == 19
    assert sum(a.cuenta for a in _pendientes(lista)) == _pendientes_de_hoy(overview) == 19
    assert [(a.paso, a.tipo, a.texto, a.cuenta) for a in lista] == [
        (4, "pendiente", "Cargar el informe técnico del área (falta en 2 ofertas)", 2),
        (6, "pendiente", "Resolver 1 descarte propuesto", 1),
        (6, "pendiente", "Contestar 4 preguntas", 4),
        (6, "pendiente", "Decidir 6 puntos no determinados", 6),
        (6, "pendiente", "Revisar 1 «no cumple»", 1),
        (6, "pendiente", "Confirmar 5 propuestas «cumple»", 5),
        (4, "cierre", "Evaluar las ofertas", 0),
        (1, "faltante", "Tomar del Portal lo que falta de los datos (2)", 0),
        (3, "faltante", "Subir la hoja de compliance (2 ofertas)", 0)]


def test_req147_todo_hecho_solo_faltantes(caso_todo_hecho):
    """REQ-147: con todo resuelto y el dictamen cargado no hay pendientes ni cierres: quedan los
    dos faltantes sueltos del caso (sin cronograma y sin hojas de compliance)."""
    overview, lista = _armar(caso_todo_hecho)
    assert _pendientes_de_hoy(overview) == 0 and not _pendientes(lista)
    assert [(a.paso, a.tipo, a.texto) for a in lista] == [
        (1, "faltante", "Tomar del Portal lo que falta de los datos (2)"),
        (3, "faltante", "Subir la hoja de compliance (2 ofertas)")]


def test_el_par_se_parte_igual_que_las_cuentas_de_la_etapa(caso_varios_en_curso):
    """REQ-147: los tres renglones del paso 6 suman los pares que cuenta la etapa de la matriz de
    evaluación (sin los de las filas técnicas)."""
    from evaluon.journey import memo
    from evaluon.journey.stages import matriz_evaluacion

    _, lista = _armar(caso_varios_en_curso)
    pares = sum(a.cuenta for a in lista if a.paso == 6 and a.kind in
                (acciones.K_DECIDIR, acciones.K_NO_CUMPLE, acciones.K_CUMPLE))
    page = memo.matrix_page(caso_varios_en_curso.user, caso_varios_en_curso.procedure.pk)
    assert pares == matriz_evaluacion.counts(page).pairs == 12


@pytest.mark.parametrize("nombre", LOS_TRES)
def test_ningun_renglon_queda_sin_paso(nombre, request):
    """REQ-147: el origen de cada pendiente y de cada faltante de las secciones 1 a 4 tiene paso."""
    caso = request.getfixturevalue(nombre)
    overview = sections_for(caso.user, caso.procedure)
    for s in overview.sections:
        if s.key == "normativas":
            continue
        for uno in (*s.pending_items, *s.tema_missing):
            assert uno.origen in acciones.PASO_DE_ORIGEN or uno.origen.startswith("etapa:"), uno


@pytest.mark.parametrize("nombre", LOS_TRES)
def test_los_ids_son_unicos_y_tienen_la_forma_del_contrato(nombre, request):
    """REQ-147: `"<paso>-<tipo>-<kind>"`, sin repetir."""
    _, lista = _armar(request.getfixturevalue(nombre))
    assert len(set(_ids(lista))) == len(lista)
    assert all(a.id == f"{a.paso}-{a.tipo}-{a.kind}" for a in lista)


# --- El renglón agrupado pierde su `kind`: se recupera por el sustantivo ---------------------------


def test_los_sustantivos_siguen_en_los_temas():
    """REQ-147: cada sustantivo de `NOMBRES_DE_TIPO` está escrito igual en algún tema (si un tema
    lo cambia, un renglón agrupado dejaría de reconocerse)."""
    fuentes = " ".join(p.read_text(encoding="utf-8").replace("\n", " ")
                       for p in TEMAS.glob("s*.py"))
    for noun in acciones.NOMBRES_DE_TIPO:
        assert f'"{noun}"' in fuentes, noun


@pytest.mark.parametrize("noun,kind", sorted(acciones.NOMBRES_DE_TIPO.items()))
def test_un_renglon_agrupado_recupera_su_kind(noun, kind):
    """REQ-147: tras `group_items` (que borra el `kind`) la línea sigue siendo la misma."""
    items = [Item(f"x{i}", "/x", 1, kind=kind, noun=noun, group_url="/g", origen="s4_x")
             for i in range(9)]
    (agrupado,) = group_items(items)
    assert agrupado.kind == "" and agrupado.count == 9
    assert acciones._kind(agrupado) == kind


# --- (b) cada cierre aparece si y solo si se cumple su disparador ----------------------------------


def _cierres(lista):
    return {a.kind for a in lista if a.tipo == pasos.CIERRE}


def test_proponer_la_matriz_solo_con_pliego_leido_y_sin_version(caso_recien_cargado):
    """REQ-147: pliego leído, sin versión y sin pedido corriendo ⇒ «Proponer la matriz»; con el
    pedido corriendo, no."""
    _, lista = _armar(caso_recien_cargado)
    assert acciones.K_PROPONER in _cierres(lista)
    Job.objects.create(kind=JobKind.PROPOSE_MATRIX, procedure=caso_recien_cargado.procedure,
                       requested_by=caso_recien_cargado.user, status=JobStatus.RUNNING,
                       started_at=timezone.now())
    _, lista = _armar(caso_recien_cargado)
    assert acciones.K_PROPONER not in _cierres(lista)


def test_proponer_la_matriz_no_aparece_con_la_matriz_hecha(caso_varios_en_curso):
    """REQ-147: con una versión validada, ya no se propone."""
    _, lista = _armar(caso_varios_en_curso)
    assert acciones.K_PROPONER not in _cierres(lista)


def test_resolver_el_error_con_el_pedido_fallido(caso_recien_cargado):
    """REQ-147: un pedido fallido de la matriz deja «Resolver el error: «…»» en el paso 2 y saca
    «Proponer la matriz»."""
    caso = caso_recien_cargado
    job = Job.objects.create(kind=JobKind.PROPOSE_MATRIX, procedure=caso.procedure,
                             requested_by=caso.user)
    Job.objects.filter(pk=job.pk).update(
        status=JobStatus.FAILED, started_at=timezone.now() - timedelta(seconds=20),
        finished_at=timezone.now(), error="sin memoria")
    _, lista = _armar(caso)
    errores = [a for a in lista if a.kind.startswith(acciones.K_ERROR)]
    assert [(a.paso, a.tipo, a.cuenta) for a in errores] == [(2, "cierre", 0)]
    assert errores[0].texto.startswith("Resolver el error: «") and errores[0].texto.endswith("»")
    assert acciones.K_PROPONER not in _cierres(lista)


def test_evaluar_las_ofertas_con_un_documento_cargado_despues(caso_varios_en_curso):
    """REQ-147: «varios en curso» tiene un documento cargado después de evaluar ⇒ aparece."""
    _, lista = _armar(caso_varios_en_curso)
    assert acciones.K_EVALUAR in _cierres(lista)


def test_evaluar_las_ofertas_no_aparece_con_todo_evaluado(caso_todo_hecho):
    """REQ-147: dos ofertas evaluadas con todos sus documentos ⇒ no se propone evaluar."""
    _, lista = _armar(caso_todo_hecho)
    assert acciones.K_EVALUAR not in _cierres(lista)


def test_un_documento_sin_usar_por_la_evaluacion():
    """REQ-147: con la lista `Run.documents` registrada, falta el documento que no figura; sin
    lista (corridas que no la guardaron) se compara la fecha de carga con la de la evaluación."""
    from types import SimpleNamespace as S

    ahora = timezone.now()
    corrida = S(documents=[{"document": 1}], built_at=ahora)
    assert acciones._sin_usar(S(pk=2, loaded_at=ahora - timedelta(days=1)), corrida)
    assert not acciones._sin_usar(S(pk=1, loaded_at=ahora + timedelta(days=1)), corrida)
    sin_lista = S(documents=[], built_at=ahora)
    assert acciones._sin_usar(S(pk=9, loaded_at=ahora + timedelta(seconds=1)), sin_lista)
    assert not acciones._sin_usar(S(pk=9, loaded_at=ahora - timedelta(seconds=1)), sin_lista)


def test_tomar_del_portal_y_agregar_el_acta(caso_recien_cargado, monkeypatch):
    """REQ-147: documentos que el Portal lista y no se tomaron ⇒ «Tomar del Portal…» (paso 1,
    cuenta 0, suma de documentos y circulares); ofertas del acta sin agregar ⇒ «Agregar las
    ofertas del acta» (paso 3). Sin ellos, ninguno."""
    _, lista = _armar(caso_recien_cargado)
    assert not {acciones.K_TOMAR, pasos.KIND_ACTA} & _cierres(lista)
    monkeypatch.setattr(acciones.s2_documentos, "missing_from_portal", lambda p: ["a", "b"])
    monkeypatch.setattr(acciones.s3_circulares, "missing_from_portal", lambda p: ["c"])
    monkeypatch.setattr(acciones.s3_ofertas, "portal_offers", lambda p: ["x", "y"])
    _, lista = _armar(caso_recien_cargado)
    por_kind = {a.kind: a for a in lista if a.tipo == pasos.CIERRE}
    assert (por_kind[acciones.K_TOMAR].paso, por_kind[acciones.K_TOMAR].cuenta) == (1, 0)
    assert por_kind[acciones.K_TOMAR].texto.endswith("(3)")
    assert (por_kind[pasos.KIND_ACTA].paso, por_kind[pasos.KIND_ACTA].cuenta) == (3, 0)
    assert por_kind[pasos.KIND_ACTA].texto == "Agregar las ofertas del acta"


def test_el_dictamen_espera_a_los_pasos_4_y_6(caso_varios_en_curso):
    """REQ-147: sin los pasos 4 y 6 hechos y sin mantenimiento que venza, no se ofrece cargar el
    dictamen; con ellos hechos, sí."""
    _, lista = _armar(caso_varios_en_curso)
    assert pasos.KIND_DICTAMEN not in _cierres(lista)
    _, lista = _armar(caso_varios_en_curso, pasos_4_y_6_hechos=True)
    cargar = [a for a in lista if a.id == "7-cierre-dictamen"]
    assert [(a.texto, a.cuenta, a.marca) for a in cargar] == [("Cargar el dictamen", 0, "")]


def test_con_el_dictamen_cargado_no_se_ofrece(caso_todo_hecho):
    """REQ-147: con un dictamen cargado no hay «Cargar el dictamen», aunque 4 y 6 estén hechos."""
    _, lista = _armar(caso_todo_hecho, pasos_4_y_6_hechos=True)
    assert "7-cierre-dictamen" not in _ids(lista)


def test_dictamen_del_portal_sin_aprobar_lo_cubre_el_pendiente(caso_varios_en_curso):
    """REQ-147: si el Portal publicó un dictamen sin aprobar, la línea de pendiente reemplaza al
    cierre (no se ofrece cargar uno encima)."""
    caso = caso_varios_en_curso
    overview = sections_for(caso.user, caso.procedure)
    evaluacion = overview.get("evaluacion")
    aprobar = Item("Aprobar el dictamen publicado en el Portal", "/d", 1, "Aprobar",
                   post=("/post", (("aprobar", "item:1"),)), origen="s4_dictamen")
    cambiada = dataclasses.replace(evaluacion, pending_items=(*evaluacion.pending_items, aprobar))
    falso = dataclasses.replace(overview, sections=tuple(
        cambiada if s.key == "evaluacion" else s for s in overview.sections))
    lista = acciones.armar(caso.user, caso.procedure, falso, pasos_4_y_6_hechos=True)
    assert "7-pendiente-dictamen" in _ids(lista) and "7-cierre-dictamen" not in _ids(lista)
    linea = next(a for a in lista if a.id == "7-pendiente-dictamen")
    assert linea.post == ("/post", (("aprobar", "item:1"),)) and linea.cuenta == 1


def _abrir_borrador(caso):
    """Abre una versión nueva (borrador) con el servicio de siempre."""
    from evaluon.tenders.services.validation import open_new_version

    open_new_version(caso.user, caso.procedure.pk)


def test_validar_la_matriz_solo_sin_renglones_por_resolver(caso_varios_en_curso):
    """REQ-147: un borrador abre «Validar la matriz» (cierre) si no queda nada por resolver, y si
    queda, la línea «Validar la matriz: N por resolver»; nunca las dos a la vez."""
    caso = caso_varios_en_curso
    assert "2-cierre-validar_matriz" not in _ids(_armar(caso)[1])  # ya validada
    _abrir_borrador(caso)
    _, lista = _armar(caso)
    pendiente = [a for a in lista if a.id == "2-pendiente-matriz"]
    cierre = [a for a in lista if a.id == "2-cierre-validar_matriz"]
    assert bool(pendiente) != bool(cierre)
    if pendiente:
        assert pendiente[0].texto == f"Validar la matriz: {pendiente[0].cuenta} por resolver"
    assert (cierre[0].paso, cierre[0].cuenta) == (2, 0) if cierre else True


def test_validar_la_matriz_aparece_al_quedar_sin_renglones(caso_varios_en_curso):
    """REQ-147: con el borrador abierto, «N por resolver» (9 consecuencias sin elegir) cubre al
    cierre; al quitar esos renglones del cálculo (nada por resolver) queda «Validar la matriz»."""
    caso = caso_varios_en_curso
    _abrir_borrador(caso)
    overview = sections_for(caso.user, caso.procedure)
    assert "2-pendiente-matriz" in _ids(acciones.armar(caso.user, caso.procedure, overview))
    pliego = overview.get("pliego")
    resuelta = dataclasses.replace(pliego, pending_items=tuple(
        i for i in pliego.pending_items if i.origen != "s2_matriz"))
    falso = dataclasses.replace(overview, sections=tuple(
        resuelta if s.key == "pliego" else s for s in overview.sections))
    lista = acciones.armar(caso.user, caso.procedure, falso)
    assert "2-cierre-validar_matriz" in _ids(lista) and "2-pendiente-matriz" not in _ids(lista)


def test_sin_matriz_validada_y_con_ofertas_no_hay_acciones_de_evaluacion(caso_varios_en_curso,
                                                                       monkeypatch):
    """REQ-147: sin matriz validada y con ofertas cargadas aparece «Validar la matriz» (o su
    pendiente) y ninguna acción de los pasos 4 y 6. (Una versión validada no se puede volver
    borrador en la base: se simula que no hay ninguna validada vigente.)"""
    caso = caso_varios_en_curso
    _abrir_borrador(caso)
    monkeypatch.setattr(acciones, "latest_validated", lambda procedure: None)
    _, lista = _armar(caso)
    assert not [a for a in lista if a.paso in (4, 6)]
    assert any(a.id in ("2-cierre-validar_matriz", "2-pendiente-matriz") for a in lista)


# --- (c) cada faltante aparece si y solo si está en `Section.tema_missing` -------------------------


@pytest.mark.parametrize("nombre", LOS_TRES)
def test_cada_faltante_esta_en_tema_missing_y_ninguno_falta(nombre, request):
    """REQ-147: los faltantes sueltos son, uno por uno, los `Missing` de `Section.tema_missing`
    que no cubre otra línea; ninguno de más, ninguno de menos (las advertencias son sus textos)."""
    caso = request.getfixturevalue(nombre)
    overview, lista = _armar(caso)
    esperados = [m.text for m in _sin_cubrir(overview)]
    todas = acciones.advertencias(overview)
    assert sorted(t for textos in todas.values() for t in textos) == sorted(esperados)
    faltantes = [a for a in lista if a.tipo == pasos.FALTANTE]
    assert {a.paso for a in faltantes} == set(todas)
    en_secciones = {m.text for s in overview.sections for m in s.tema_missing}
    assert set(esperados) <= en_secciones


@pytest.mark.parametrize("nombre", LOS_TRES)
def test_los_faltantes_y_cierres_no_cambian_el_conteo_de_pendientes(nombre, request):
    """REQ-147 / N1: la suma de todas las cuentas iguala al contador de hoy: las de faltante y
    cierre valen 0."""
    caso = request.getfixturevalue(nombre)
    overview, lista = _armar(caso)
    assert all(a.cuenta == 0 for a in lista if a.tipo != pasos.PENDIENTE)
    assert sum(a.cuenta for a in lista) == _pendientes_de_hoy(overview)


# --- REQ-157 con `ingreso.plazos()` real -----------------------------------------------------------


def _mantenimiento(monkeypatch, due):
    """El mantenimiento calculable para `due`; todo lo demás sale de `ingreso.plazos()` real."""
    monkeypatch.setattr(ingreso, "today", lambda: HOY)
    monkeypatch.setattr(ingreso, "maintenance", lambda p: ingreso.Maintenance(
        "computed", due=due, days_left=(due - HOY).days))


def test_req157_dictamen_vence_hoy_en_lila(caso_varios_en_curso, monkeypatch):
    """REQ-157: el mantenimiento vence hoy y falta el dictamen ⇒ «Cargar el dictamen» aparece
    aunque 4 y 6 no estén hechos, con la marca «hoy» y primero en la lista."""
    _mantenimiento(monkeypatch, HOY)
    _, lista = _armar(caso_varios_en_curso)
    assert lista[0].id == "7-cierre-dictamen" and lista[0].marca == pasos.MARCA_HOY


def test_req157_dictamen_vencido_en_rojo(caso_varios_en_curso, monkeypatch):
    """REQ-157: al día siguiente sigue faltando ⇒ la misma acción, ahora «vencido»."""
    _mantenimiento(monkeypatch, HOY - timedelta(days=1))
    _, lista = _armar(caso_varios_en_curso)
    assert lista[0].id == "7-cierre-dictamen" and lista[0].marca == pasos.MARCA_VENCIDO


def test_req157_con_el_dictamen_cargado_no_hay_marca_ni_accion(caso_todo_hecho, monkeypatch):
    """REQ-157: con el dictamen cargado (valor real de `dictamen_cargado`) no hay acción ni marca."""
    _mantenimiento(monkeypatch, HOY)
    _, lista = _armar(caso_todo_hecho)
    assert "7-cierre-dictamen" not in _ids(lista) and all(a.marca == "" for a in lista)


def test_req157_sin_vencimientos_no_hay_nada_marcado(caso_varios_en_curso, monkeypatch):
    """REQ-157: mantenimiento futuro o sin fecha ⇒ ninguna línea marcada."""
    _mantenimiento(monkeypatch, HOY + timedelta(days=5))
    _, lista = _armar(caso_varios_en_curso)
    assert all(a.marca == "" for a in lista)


# --- Correcciones de la verificación (H1, H2, duplicado, vigilancia de kinds y orígenes) -----------


def _inyectar(overview, **por_seccion):
    """El mismo `Overview` con renglones armados a mano: `por_seccion` es
    `{clave de la sección: {"items": [...], "faltantes": [...]}}`; los suma a los reales."""
    secciones = []
    for s in overview.sections:
        extra = por_seccion.get(s.key)
        if extra:
            s = dataclasses.replace(
                s, pending_items=(*s.pending_items, *extra.get("items", ())),
                tema_missing=(*s.tema_missing, *extra.get("faltantes", ())))
        secciones.append(s)
    return dataclasses.replace(overview, sections=tuple(secciones))


def _con_renglones(caso, **por_seccion):
    overview = _inyectar(sections_for(caso.user, caso.procedure), **por_seccion)
    return acciones.armar(caso.user, caso.procedure, overview)


def _faltante(texto, origen):
    from evaluon.journey.sections.base import Missing

    return Missing(texto, "/x", "Ir", origen=origen)


def _linea(lista, id_):
    return next(a for a in lista if a.id == id_)


def test_h2_textos_y_paso_de_las_lineas_de_pendientes(caso_varios_en_curso):
    """REQ-147: portal (origen `s1_portal`, paso 1), circular «Validar» y «Abrir» por separado
    (paso 2), borradores y ficha (paso 3) e `informe_ok` (paso 4): texto, paso y cuenta."""
    lista = _con_renglones(
        caso_varios_en_curso,
        procedimiento={"items": [Item("Propuesta del Portal: 3 sin aprobar", "/p#s1-propuesta",
                                      3, "Aprobar", origen="s1_portal")]},
        pliego={"items": [
            Item("C1: la versión 2 falta validarla", "/m", 2, "Validar", origen="s3_circulares"),
            Item("C2: falta abrir la versión nueva", "/c", 1, "Abrir", origen="s3_circulares")]},
        ofertas={"items": [
            Item("Oferta subida (X)", "/b", 1, "Revisar", kind="oferta_borrador",
                 origen="s3_ofertas"),
            Item("Oferta subida: no se pudo leer", "/b2", 1, "Revisar",
                 kind="oferta_borrador_fallida", origen="s3_ofertas"),
            Item("Oferta 1: 4 filas", "/f", 4, "Resolver", kind="ficha", origen="s3_ficha")]},
        evaluacion={"items": [Item("Oferta 1: falta el ok", "/o", 1, "Resolver",
                                   kind="informe_ok", origen="s4_informe")]})
    visto = {a.id: (a.paso, a.texto, a.cuenta) for a in lista}
    assert visto["1-pendiente-portal"] == (
        1, "Aprobar lo que leyó el sistema del Portal (3)", 3)
    assert visto["2-pendiente-circular_validar"] == (
        2, "Validar la versión con la circular (2)", 2)
    assert visto["2-pendiente-circular_abrir"] == (2, "Abrir la versión nueva de la matriz", 1)
    assert _linea(lista, "2-pendiente-circular_validar").url == "/m"
    assert _linea(lista, "2-pendiente-circular_abrir").url == "/c"
    assert visto["3-pendiente-borradores"] == (3, "Revisar 2 ofertas subidas por archivos", 2)
    assert visto["3-pendiente-ficha"] == (3, "Confirmar 4 filas de la ficha", 4)
    assert visto["4-pendiente-informe_ok"] == (4, "Dar el ok al informe técnico (1 oferta)", 1)


def _corrida_registrada(caso, oferta, documentos):
    """Una evaluación nueva de la oferta con `Run.documents` en el formato de `evaluate.py`
    (`OfferText.record()`: una entrada por documento, con la clave `"document"`)."""
    from evaluon.assessment import models as am

    version = caso.procedure.matrix_versions.get(number=1)
    pedido = am.Request.objects.create(
        procedure=caso.procedure, matrix_version=version, offers=[oferta.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=caso.user)
    registro = [{"document": d.pk, "title": d.title, "file": d.file_name, "reading": None,
                 "sha256": d.file_sha256, "pages": 1, "unread_pages": [], "tokens": 10,
                 "page_tokens": [10], "copy_of": None, "windows": [], "vision_pages": []}
                for d in documentos]
    return am.Run.objects.create(
        request=pedido, offer=oferta, matrix_version=version,
        number=am.Run.objects.filter(offer=oferta).count() + 1, channel=am.Channel.SCREEN,
        documents=registro, norms={}, models_used={}, parameters={}, prompt_versions={})


def test_h2_run_registrado_de_verdad_y_el_informe_tecnico_no_cuenta(caso_todo_hecho):
    """REQ-147: la evaluación registra los documentos sin el informe técnico (clave `document`,
    como `evaluate.py`); aunque la oferta tenga un informe técnico vigente no se pide evaluar de
    nuevo. Si la evaluación dejó afuera los otros documentos, sí."""
    caso = caso_todo_hecho
    assert any(d.kind == "informe_tecnico" for o in caso.offers for d in o.documents.all())
    for oferta in caso.offers:
        propios = [d for d in oferta.documents.order_by("pk") if d.kind != "informe_tecnico"]
        _corrida_registrada(caso, oferta, propios)
    _, lista = _armar(caso)
    assert acciones.K_EVALUAR not in _cierres(lista)
    # Una evaluación nueva que registró un documento ajeno y dejó afuera los de la oferta.
    ajeno = [d for d in caso.offers[1].documents.all() if d.kind != "informe_tecnico"]
    _corrida_registrada(caso, caso.offers[0], ajeno)
    _, lista = _armar(caso)
    assert acciones.K_EVALUAR in _cierres(lista)


def test_h1_no_se_ofrece_evaluar_con_una_evaluacion_corriendo(caso_varios_en_curso):
    """REQ-147: con un pedido de evaluación corriendo no se ofrece «Evaluar las ofertas»."""
    caso = caso_varios_en_curso
    assert acciones.K_EVALUAR in _cierres(_armar(caso)[1])
    Job.objects.create(kind=JobKind.EVALUATE_OFFERS, procedure=caso.procedure,
                       requested_by=caso.user, status=JobStatus.RUNNING,
                       started_at=timezone.now())
    assert acciones.K_EVALUAR not in _cierres(_armar(caso)[1])


def test_h2_un_faltante_de_etapa_no_genera_linea_ni_advertencia(caso_varios_en_curso):
    """REQ-147: un `Missing` con origen `etapa:*` en `tema_missing` lo cubre un cierre o la
    dependencia entre pasos: no es faltante. El mismo texto con origen de tema, sí."""
    caso = caso_varios_en_curso
    texto = "Todavía no hay ofertas cargadas."
    base = sections_for(caso.user, caso.procedure)
    de_etapa = _inyectar(base, ofertas={"faltantes": [_faltante(texto, "etapa:ofertas")]})
    assert texto not in sum(acciones.advertencias(de_etapa).values(), [])
    lista = acciones.armar(caso.user, caso.procedure, de_etapa)
    assert not [a for a in lista if a.tipo == pasos.FALTANTE and "etapa" in a.kind]
    de_tema = _inyectar(base, ofertas={"faltantes": [_faltante(texto, "s3_anexos")]})
    assert texto in acciones.advertencias(de_tema)[3]


def test_h3_con_la_circular_por_validar_no_se_repite_validar_la_matriz(caso_varios_en_curso):
    """REQ-147: un borrador sin nada por resolver y una circular que espera su validación dan una
    sola línea para validar (el pendiente de la circular), no dos que llevan al mismo lugar."""
    caso = caso_varios_en_curso
    _abrir_borrador(caso)
    overview = sections_for(caso.user, caso.procedure)
    base = dataclasses.replace(overview, sections=tuple(
        dataclasses.replace(s, pending_items=tuple(
            i for i in s.pending_items if i.origen != "s2_matriz")) if s.key == "pliego" else s
        for s in overview.sections))
    circular = Item("C1: la versión 2 falta validarla", "/m", 1, "Validar",
                    origen="s3_circulares")
    sola = acciones.armar(caso.user, caso.procedure, base)
    assert "2-cierre-validar_matriz" in _ids(sola)  # control: sin circular, el cierre está
    con = acciones.armar(caso.user, caso.procedure,
                         _inyectar(base, pliego={"items": [circular]}))
    assert "2-pendiente-circular_validar" in _ids(con)
    assert "2-cierre-validar_matriz" not in _ids(con)


# --- Vigilancia: un tipo u origen nuevo no pasa en silencio ----------------------------------------


def test_todo_kind_agrupable_de_los_temas_esta_en_nombres_de_tipo():
    """REQ-147: cada `Item(kind=…, noun=…)` escrito en los temas tiene su sustantivo en
    `NOMBRES_DE_TIPO` (si no, agrupado caería a una línea genérica sin aviso). Los de la matriz
    se reconocen por origen y la sugerencia `ficha_arma` no es un pendiente."""
    import ast

    reconocidos_por_origen = {"req", "tramo", "consec", "sug", "ficha_arma"}
    visto = 0
    for ruta in sorted(TEMAS.glob("s[1-4]_*.py")):  # Normativas (s5) no es de un paso
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if not (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") in
                    ("Item", "_with_why")):
                continue  # los `Missing` agrupados no son pendientes
            claves = {k.arg: k.value for k in nodo.keywords}
            if "kind" in claves and "noun" in claves:
                kind, noun = claves["kind"], claves["noun"]
                if not (isinstance(kind, ast.Constant) and isinstance(noun, ast.Constant)):
                    continue  # lo arma `s2_matriz._item` con variables: va por origen
                visto += 1
                if kind.value in reconocidos_por_origen:
                    continue
                assert acciones.NOMBRES_DE_TIPO.get(noun.value) == kind.value, (
                    ruta.name, kind.value)
    assert visto >= 8


def test_todo_origen_de_los_temas_y_etapas_tiene_paso():
    """REQ-147: cada tema de las secciones 1 a 4 que produce renglones y cada etapa de la 013
    están en `PASO_DE_ORIGEN`; un tema nuevo hace fallar este test hasta que se le dé un paso."""
    from evaluon.journey.sections import s1, s2, s3, s4

    sin_renglones = {"s1_pliego", "s4_exportar"}  # su `status()` no aporta pendientes ni faltantes
    for modulo in (s1, s2, s3, s4):
        for tema in modulo.TEMA_KEYS:
            if tema not in sin_renglones:
                assert tema in acciones.PASO_DE_ORIGEN, tema
        for etapa in modulo.STAGE_KEYS:
            assert f"etapa:{etapa}" in acciones.PASO_DE_ORIGEN, etapa
