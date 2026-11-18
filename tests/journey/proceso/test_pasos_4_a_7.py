"""Los pasos 4 a 7 de `proceso_de` (REQ-143 a REQ-147; plan 018, T-346): dependencias,
«Todavía no» con su `espera`, el total de la oferta con `PortalOfferData`, «D de T puntos
decididos», el dictamen y la excepción del mantenimiento, `terminado` y `vencimiento`. Datos
inventados (P4)."""

from datetime import date, timedelta

import pytest

from evaluon.assessment import models as am
from evaluon.assessment.services import technical
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.proceso import calculo, pasos
from evaluon.journey.tablero import ingreso
from evaluon.journey.temas import s4_propuesta
from evaluon.portal import models as pm
from evaluon.tenders import models as tm
from evaluon.tenders.models import VersionStatus
from evaluon.tenders.services import document_history
from tests.assessment.test_matrix import decide
from tests.journey.temas.test_s4_dictamen import portal_dictamen
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

HECHO, EN_CURSO, TODAVIA_NO, CON_ERROR = (
    pasos.Estado.HECHO, pasos.Estado.EN_CURSO, pasos.Estado.TODAVIA_NO, pasos.Estado.CON_ERROR)
HOY = date(2026, 11, 18)


def _proceso(caso):
    return calculo.proceso_de(caso.user, caso.procedure)


def _paso(proceso, numero):
    return proceso.pasos[numero - 1]


def _mantenimiento(monkeypatch, due):
    """El mantenimiento calculable para `due`; todo lo demás sale de `ingreso.plazos()` real."""
    monkeypatch.setattr(ingreso, "today", lambda: HOY)
    monkeypatch.setattr(ingreso, "maintenance", lambda p: ingreso.Maintenance(
        "computed", due=due, days_left=(due - HOY).days))


# --- Paso 4 ---------------------------------------------------------------------------------------


def test_req147_matriz_sin_validar_con_ofertas_el_paso_4_depende_de_la_matriz(
        caso_recien_cargado):
    """REQ-147: con ofertas cargadas y la matriz todavía en borrador, el paso 4 dice «Todavía no:
    depende de la matriz de requisitos» y la acción que sí se puede hacer, «Validar la matriz»,
    es del paso 2; no hay acciones de los pasos 4 ni 6."""
    caso = caso_recien_cargado
    tm.MatrixVersion.objects.create(procedure=caso.procedure, number=1,
                                    status=VersionStatus.DRAFT, created_by=caso.user)
    for nombre in ("Oferente A Sintético", "Oferente B Sintético"):
        make_offer(caso.procedure, caso.user, nombre,
                   {"oferta.pdf": ["Declaro bajo juramento que me encuentro habilitado."]})
    proceso = _proceso(caso)
    cuatro = _paso(proceso, 4)
    assert cuatro.estado is TODAVIA_NO
    assert cuatro.espera == "depende de la matriz de requisitos"
    assert cuatro.resumen == "Todavía no: depende de la matriz de requisitos."
    assert [t for t in proceso.acciones if t.paso in (4, 6)] == []
    assert any("Validar la matriz" in t.texto for t in _paso(proceso, 2).tareas)
    assert _paso(proceso, 6).estado is TODAVIA_NO


def test_req144_oferta_nueva_sin_evaluar_pasa_el_paso_4_a_en_curso(caso_todo_hecho):
    """REQ-145: una oferta con documentos y sin evaluar con la matriz vigente reabre el paso 4
    (acción «Evaluar las ofertas»); el paso 5 deja de estar hecho."""
    caso = caso_todo_hecho
    assert _paso(_proceso(caso), 4).estado is HECHO
    make_offer(caso.procedure, caso.user, "Oferente C Sintético",
               {"oferta.pdf": ["Declaro bajo juramento que me encuentro habilitado."]})
    proceso = _proceso(caso)
    assert _paso(proceso, 4).estado is EN_CURSO
    assert "4-cierre-evaluar" in [t.id for t in _paso(proceso, 4).tareas]
    assert _paso(proceso, 5).estado is EN_CURSO


def test_req145_documento_nuevo_que_la_evaluacion_no_uso_reabre_el_paso_4(caso_todo_hecho):
    """REQ-145: un documento vigente cargado después de la última evaluación (que no figura en
    `Run.documents`) vuelve el paso 4 a «En curso» y lo dice."""
    from evaluon.offers.models import Document as OfferDocument
    from evaluon.offers.models import DocumentFile as OfferDocumentFile

    caso = caso_todo_hecho
    nuevo = OfferDocument.objects.create(
        offer=caso.offers[0], title="anexo.pdf", file_name="anexo.pdf", file_format="pdf",
        file_size=1, file_sha256="e" * 64, loaded_by=caso.user)
    OfferDocumentFile.objects.create(document=nuevo, content=b"%PDF-sintetico")
    cuatro = _paso(_proceso(caso), 4)
    assert cuatro.estado is EN_CURSO
    assert "no tuvo en cuenta" in cuatro.resumen


def test_req144_un_ok_tecnico_retirado_es_del_paso_4_y_no_del_6(caso_todo_hecho):
    """REQ-144: si se retira el ok del informe técnico de una oferta, el resultado vuelve a esperar
    el informe: lo cuenta el paso 4 («En curso», con el ok pendiente); el paso 6 sigue «Hecho»."""
    caso = caso_todo_hecho
    technical.withdraw_ok(caso.user, caso.offers[0], note="se pidió una aclaración")
    proceso = _proceso(caso)
    cuatro = _paso(proceso, 4)
    assert cuatro.estado is EN_CURSO and _paso(proceso, 6).estado is HECHO
    assert "informe técnico" in cuatro.resumen
    assert _paso(proceso, 5).estado is EN_CURSO


# --- Paso 5 ---------------------------------------------------------------------------------------


def test_req144_el_total_se_cuenta_con_portal_offer_data_y_no_con_el_orden(
        caso_varios_en_curso):
    """REQ-144 (aviso de T-340): el «no cumple» formal saca una oferta del orden económico
    (`order.totals` trae 1 de 2) pero las dos tienen su total: el paso 5 no dice que falte
    ninguno."""
    caso = caso_varios_en_curso
    with memo.scope():
        assert len(memo.matrix_page(caso.user, caso.procedure.pk).order.totals) == 1
    assert pm.PortalOfferData.objects.filter(offer__in=caso.offers, total__isnull=False).count() == 2
    cinco = _paso(_proceso(caso), 5)
    assert "Falta el total" not in cinco.dato and "Falta el total" not in cinco.resumen


def test_req144_oferta_sin_total_deja_el_paso_5_en_curso(caso_todo_hecho):
    """REQ-144: con el paso 4 hecho pero una oferta sin total, el paso 5 queda «En curso» y dice
    cuántas faltan; con el total cargado vuelve a «Hecho»."""
    caso = caso_todo_hecho
    assert _paso(_proceso(caso), 5).estado is HECHO
    datos = pm.PortalOfferData.objects.get(offer=caso.offers[1])
    total = datos.total
    pm.PortalOfferData.objects.filter(pk=datos.pk).update(total=None)
    cinco = _paso(_proceso(caso), 5)
    assert cinco.estado is EN_CURSO and cinco.dato == "Falta el total de 1 oferta"
    assert _paso(_proceso(caso), 4).estado is HECHO
    pm.PortalOfferData.objects.filter(pk=datos.pk).update(total=total)
    assert _paso(_proceso(caso), 5).estado is HECHO


def test_req144_sin_ofertas_el_paso_5_todavia_no(caso_recien_cargado):
    """REQ-144: sin ofertas, paso 5 «Todavía no», sin acciones y nunca «Con error»."""
    cinco = _paso(_proceso(caso_recien_cargado), 5)
    assert cinco.estado is TODAVIA_NO and cinco.dato == "Sin ofertas" and cinco.tareas == []
    assert cinco.espera == "depende de que haya ofertas"


# --- Paso 6 ---------------------------------------------------------------------------------------


def test_req144_puntos_decididos_sube_al_confirmar(caso_varios_en_curso):
    """REQ-144: confirmar un par «cumple» propuesto pasa el conteo de «0 de 12» a «1 de 12»."""
    caso = caso_varios_en_curso
    assert _paso(_proceso(caso), 6).dato == "0 de 12 puntos decididos"
    resultado = next(r for r in caso.resultados[caso.offers[0].pk].values()
                     if r.outcome == am.Outcome.CUMPLE)
    decide(caso.user, resultado, am.Action.CONFIRMAR)
    seis = _paso(_proceso(caso), 6)
    assert seis.dato == "1 de 12 puntos decididos" and seis.estado is EN_CURSO


def test_req144_todo_hecho_tiene_todos_los_puntos_decididos(caso_todo_hecho):
    """REQ-144: «todo hecho»: 12 de 12 puntos decididos y paso 6 «Hecho»."""
    seis = _paso(_proceso(caso_todo_hecho), 6)
    assert seis.dato == "12 de 12 puntos decididos" and seis.estado is HECHO


def test_req144_una_pregunta_abierta_reabre_el_paso_6(caso_todo_hecho):
    """REQ-145: una pregunta abierta nueva vuelve el paso 6 a «En curso» y lo dice."""
    caso = caso_todo_hecho
    resultado = am.Result.objects.filter(offer=caso.offers[0]).exclude(
        requirement__category="tecnico").first()
    am.Question.objects.create(
        procedure=caso.procedure, requirement=resultado.requirement, offer=caso.offers[0],
        result=resultado, text="¿El documento presentado está vigente?", reason="externo")
    seis = _paso(_proceso(caso), 6)
    assert seis.estado is EN_CURSO and "1 pregunta abierta" in seis.resumen


def test_req144_sin_evaluacion_el_paso_6_todavia_no(caso_recien_cargado):
    """REQ-144: sin ninguna oferta evaluada, paso 6 «Todavía no» con su dependencia."""
    seis = _paso(_proceso(caso_recien_cargado), 6)
    assert seis.estado is TODAVIA_NO and seis.dato == "Sin evaluación"
    assert seis.espera == "depende de que se evalúe alguna oferta (paso 4)"


# --- Paso 7, terminado y vencimiento --------------------------------------------------------------


def test_req150_terminado_es_dictamen_cargado(caso_todo_hecho):
    """REQ-150: `terminado` = dictamen cargado; al retirarlo, vuelve a abierto y el paso 7 ofrece
    «Cargar el dictamen» (los pasos 4 y 6 están hechos)."""
    caso = caso_todo_hecho
    proceso = _proceso(caso)
    assert proceso.terminado is True and _paso(proceso, 7).estado is HECHO
    document_history.withdraw(caso.user, caso.dictamen, "error de carga")
    proceso = _proceso(caso)
    siete = _paso(proceso, 7)
    assert proceso.terminado is False and siete.estado is EN_CURSO
    assert siete.dato == "Sin dictamen"
    assert siete.resumen == "Los pasos 4 y 6 están hechos: falta cargar el dictamen."
    assert "7-cierre-dictamen" in [t.id for t in siete.tareas]
    assert "7-cierre-dictamen" in [a.id for a in proceso.acciones]


def test_req157_mantenimiento_que_vence_hoy_habilita_el_dictamen(caso_varios_en_curso,
                                                                  monkeypatch):
    """REQ-157: sin dictamen y con el mantenimiento venciendo hoy, el paso 7 está «En curso»
    aunque 4 y 6 no estén hechos, con la marca «hoy»; al día siguiente, «vencido»."""
    caso = caso_varios_en_curso
    _mantenimiento(monkeypatch, HOY)
    proceso = _proceso(caso)
    siete = _paso(proceso, 7)
    assert siete.estado is EN_CURSO and siete.marca == pasos.MARCA_HOY
    assert siete.resumen == "El mantenimiento de las ofertas vence hoy: falta cargar el dictamen."
    assert proceso.vencimiento.marca == pasos.MARCA_HOY and proceso.vencimiento.paso == 7
    _mantenimiento(monkeypatch, HOY - timedelta(days=1))
    siete = _paso(_proceso(caso), 7)
    assert siete.estado is EN_CURSO and siete.marca == pasos.MARCA_VENCIDO
    assert "ya venció" in siete.resumen


def test_req157_mantenimiento_futuro_no_habilita_el_dictamen(caso_varios_en_curso, monkeypatch):
    """REQ-157: un vencimiento futuro no cambia nada: paso 7 «Todavía no», sin marca."""
    _mantenimiento(monkeypatch, HOY + timedelta(days=5))
    proceso = _proceso(caso_varios_en_curso)
    siete = _paso(proceso, 7)
    assert siete.estado is TODAVIA_NO and siete.marca == ""
    assert proceso.vencimiento.marca == "" and proceso.vencimiento.paso == 7


def test_req157_con_el_dictamen_cargado_no_hay_marca_ni_vencimiento(caso_todo_hecho,
                                                                     monkeypatch):
    """REQ-157: con el dictamen cargado, el mantenimiento vencido no marca nada."""
    _mantenimiento(monkeypatch, HOY - timedelta(days=3))
    proceso = _proceso(caso_todo_hecho)
    assert all(p.marca == "" for p in proceso.pasos) and proceso.vencimiento is None


def test_req144_dictamen_del_portal_sin_aprobar_es_en_curso(caso_varios_en_curso):
    """REQ-144: un dictamen publicado en el Portal y sin aprobar pone el paso 7 «En curso» (su
    pendiente «Aprobar el dictamen…»), aunque 4 y 6 no estén hechos; el procedimiento no está
    terminado."""
    caso = caso_varios_en_curso
    portal_dictamen(caso.procedure, caso.user, pm.ItemState.PROPUESTO)
    proceso = _proceso(caso)
    siete = _paso(proceso, 7)
    assert siete.estado is EN_CURSO and not proceso.terminado
    assert siete.resumen == "El Portal publicó un dictamen: falta aprobar su carga."
    assert "7-pendiente-dictamen" in [t.id for t in siete.tareas]


def test_req144_dictamen_del_portal_aprobado_termina_el_procedimiento(caso_varios_en_curso):
    """REQ-150: el dictamen del Portal aprobado es dictamen cargado: paso 7 «Hecho» y terminado."""
    caso = caso_varios_en_curso
    portal_dictamen(caso.procedure, caso.user, pm.ItemState.APROBADO)
    proceso = _proceso(caso)
    assert _paso(proceso, 7).estado is HECHO and proceso.terminado


def test_r1_dictamen_del_portal_fallido_es_con_error(caso_varios_en_curso):
    """REQ-144 (R1): el dictamen del Portal en `fallido` y sin otro cargado deja el paso 7 «Con
    error», con el motivo en lenguaje llano."""
    caso = caso_varios_en_curso
    item = portal_dictamen(caso.procedure, caso.user, pm.ItemState.FALLIDO)
    pm.PortalItem.objects.filter(pk=item.pk).update(failure="archivo dañado")
    siete = _paso(_proceso(caso), 7)
    assert siete.estado is CON_ERROR
    assert siete.resumen.startswith("No se pudo tomar el dictamen del Portal.")


def test_req144_las_filas_tecnicas_no_entran_en_los_puntos_decididos(caso_todo_hecho):
    """REQ-144: los pares de las filas técnicas se deciden con el ok del informe (paso 4) y no
    cuentan en «D de T puntos decididos»: T = celdas no técnicas con resultado, no todas."""
    caso = caso_todo_hecho
    pagina = memo.matrix_page(caso.user, caso.procedure.pk, channel=Channel.SCREEN)
    tecnicas = s4_propuesta._technical_cells(pagina)
    assert tecnicas, "el caso debe tener filas técnicas para que la prueba diga algo"
    esperado = len(pagina.cells) - len(tecnicas)
    assert 0 < esperado < len(pagina.cells)
    assert _paso(_proceso(caso), 6).dato == f"{esperado} de {esperado} puntos decididos"


def test_req144_dictamen_subido_con_el_del_portal_sin_aprobar_es_en_curso_y_terminado(
        caso_todo_hecho):
    """REQ-144, REQ-150: con el dictamen cargado (el procedimiento está terminado) y un dictamen
    del Portal sin aprobar, el paso 7 es «En curso» y `terminado` sigue verdadero."""
    caso = caso_todo_hecho
    portal_dictamen(caso.procedure, caso.user, pm.ItemState.PROPUESTO)
    proceso = _proceso(caso)
    assert proceso.terminado is True and _paso(proceso, 7).estado is EN_CURSO
