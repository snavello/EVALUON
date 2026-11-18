"""Los pasos 1 a 3 de `proceso_de` (REQ-144, REQ-145; plan 018, T-345): estado propio de cada
paso, advertencias que no cambian el estado, «Con error», dependencias y un solo cálculo por
pedido. Los tres casos son los de `conftest.py` (caso chico inventado, P4). Los pasos 4 a 7 son
provisionales hasta T-346 y acá no se prueban salvo que sigan siendo «Todavía no»."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from evaluon.audit.models import Channel
from evaluon.journey.proceso import acciones, calculo, pasos
from evaluon.offers.models import Offer
from evaluon.tenders import models as m
from evaluon.tenders.models import Job, JobKind, JobStatus
from evaluon.tenders.services import documents as tender_documents
from evaluon.tenders.services import procedures as tender_procedures

from .tabla_a_mano import CASOS, TABLA

pytestmark = pytest.mark.django_db

FIXTURE = {"recien_cargado": "caso_recien_cargado", "varios_en_curso": "caso_varios_en_curso",
           "todo_hecho": "caso_todo_hecho"}


def _textos(proceso, numeros=(1, 2, 3)):
    return {p.numero: p.estado.texto for p in proceso.pasos if p.numero in numeros}


@pytest.mark.parametrize("nombre", CASOS)
def test_req144_estados_de_los_pasos_1_a_3_de_la_tabla(nombre, request):
    """REQ-144: los pasos 1, 2 y 3 de cada caso dan el estado de la tabla firmada."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    esperado = {n: celdas[nombre][0] for n, _, celdas in TABLA if n <= 3}
    assert _textos(proceso) == esperado


@pytest.mark.parametrize("nombre", CASOS)
def test_req144_los_siete_pasos_sin_paso_actual(nombre, request):
    """REQ-144: siete pasos con los nombres de `pasos.py`; ningún «paso actual». (Los pasos 4 a 7
    dejaron de ser provisionales en T-346; sus estados los prueba `test_pasos_4_a_7.py`.)"""
    caso = request.getfixturevalue(FIXTURE[nombre])
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    assert [(p.numero, p.nombre) for p in proceso.pasos] == [
        (d.numero, d.nombre) for d in pasos.PASOS]
    assert not hasattr(proceso, "paso_actual")


@pytest.mark.parametrize("nombre", CASOS)
def test_req158_las_tareas_son_las_mismas_acciones(nombre, request):
    """REQ-158: `Paso.tareas` son los mismos objetos `Accion` que `Proceso.acciones`, repartidos por
    paso; la unión es toda la lista."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    ids = [id(a) for a in proceso.acciones]
    for paso in proceso.pasos:
        assert all(id(t) in ids and t.paso == paso.numero for t in paso.tareas)
    assert sorted(id(t) for p in proceso.pasos for t in p.tareas) == sorted(ids)


def test_req146_faltantes_son_advertencias_y_no_cambian_el_estado(caso_recien_cargado):
    """REQ-146 (N1): recién cargado tiene faltantes sueltos en los pasos 1 y 3 (sin expediente,
    sin cronograma, sin ofertas) y aun así el paso 1 es «Hecho» y el 3, «Todavía no»."""
    proceso = calculo.proceso_de(caso_recien_cargado.user, caso_recien_cargado.procedure)
    uno, dos, tres = proceso.pasos[:3]
    assert uno.estado is pasos.Estado.HECHO and len(uno.advertencias) == 2
    assert "Falta el expediente, el cronograma y las garantías" in uno.advertencias
    assert tres.estado is pasos.Estado.TODAVIA_NO and tres.advertencias == [
        "Todavía no hay ofertas"]
    assert dos.estado is pasos.Estado.EN_CURSO and dos.advertencias == []


def test_req144_paso_2_se_puede_empezar_es_en_curso(caso_recien_cargado):
    """REQ-144: el paso 2 de un procedimiento recién cargado no empezó pero se puede empezar
    («Proponer la matriz»): «En curso», con esa acción entre sus tareas."""
    proceso = calculo.proceso_de(caso_recien_cargado.user, caso_recien_cargado.procedure)
    dos = proceso.pasos[1]
    assert dos.estado is pasos.Estado.EN_CURSO
    assert [t.texto for t in dos.tareas if t.tipo == pasos.CIERRE] == ["Proponer la matriz"]
    assert dos.dato == "Sin versión de la matriz"


def test_req144_sin_pliego_nada_empezo(evaluator_user, expected, fake_ai):
    """REQ-144: un procedimiento sin ningún documento: pasos 1, 2 y 3 «Todavía no»; el 2 dice
    de qué depende (R4) y el 1 dice que falta cargar el pliego (sin acción de cargarlo)."""
    matrix = expected.matrix
    procedure = tender_procedures.register_procedure(
        evaluator_user, number=matrix["procedimiento"], procedure_type=matrix["tipo"],
        subject=matrix["objeto"], authorization_date=matrix["fecha_autorizacion"],
        channel=Channel.COMMAND).procedure
    proceso = calculo.proceso_de(evaluator_user, procedure)
    assert _textos(proceso) == {1: "Todavía no", 2: "Todavía no", 3: "Todavía no"}
    uno, dos, _ = proceso.pasos[:3]
    assert "pliego" in uno.resumen and uno.dato == "Sin pliego cargado"
    assert dos.espera and "pliego" in dos.espera
    assert "Todavía no" in dos.resumen


def test_req145_documento_sin_leer_del_pliego_reabre_el_paso_1(caso_recien_cargado):
    """REQ-145: un anexo recién cargado y todavía sin lectura vuelve el paso 1 a «En curso»; el
    paso 2, que necesita el pliego leído, queda «Todavía no» con su dependencia."""
    caso = caso_recien_cargado
    tender_documents.load_document(
        caso.user, caso.procedure, data=b"%PDF-1.4 anexo sintetico", file_name="anexo.pdf",
        kind=m.DocumentKind.ANEXO, title="Anexo nuevo (inventado)")
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    uno, dos, _ = proceso.pasos[:3]
    assert uno.estado is pasos.Estado.EN_CURSO
    assert dos.estado is pasos.Estado.TODAVIA_NO and "pliego" in dos.espera


def test_req144_lectura_fallida_es_con_error_y_trae_su_cierre(caso_recien_cargado):
    """REQ-144 (R1): la lectura de un documento falló sin resultado posterior: paso 1 «Con
    error» con el motivo; la acción «Resolver el error» es una tarea del paso 1."""
    caso = caso_recien_cargado
    documento = tender_documents.load_document(
        caso.user, caso.procedure, data=b"%PDF-1.4 anexo roto", file_name="roto.pdf",
        kind=m.DocumentKind.ANEXO, title="Anexo ilegible (inventado)").document
    Job.objects.filter(kind=JobKind.READ_DOCUMENT, document=documento).update(
        status=JobStatus.FAILED, finished_at=timezone.now(), error="archivo dañado")
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    uno = proceso.pasos[0]
    assert uno.estado is pasos.Estado.CON_ERROR
    assert uno.resumen.startswith("No se pudo leer «Anexo ilegible (inventado)».")
    assert ". O" in uno.resumen  # el motivo en lenguaje llano, con mayúscula inicial
    assert any(t.kind.startswith("error_") for t in uno.tareas)


def test_req144_oferta_sin_documentos_deja_el_paso_3_en_curso(caso_todo_hecho):
    """REQ-144: una oferta nueva sin documentos aún no cumple «todas tienen sus documentos»:
    el paso 3 deja de ser «Hecho»."""
    caso = caso_todo_hecho
    assert calculo.proceso_de(caso.user, caso.procedure).pasos[2].estado is pasos.Estado.HECHO
    Offer.objects.create(procedure=caso.procedure, number=len(caso.offers) + 1,
                         bidder="Oferente sin documentos (inventado)",
                         created_by=caso.user)
    tres = calculo.proceso_de(caso.user, caso.procedure).pasos[2]
    assert tres.estado is pasos.Estado.EN_CURSO and "sin documentos" in tres.resumen


@pytest.mark.parametrize("nombre", CASOS)
def test_un_solo_calculo_de_secciones_y_de_acciones(nombre, request, monkeypatch):
    """Plan 018 (una sola fuente): `proceso_de` llama una vez a `sections_for` y una a
    `acciones.armar`; con el `Overview` ya calculado no vuelve a calcular las secciones."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    llamadas = {"sections": 0, "armar": 0}
    real_sections, real_armar = calculo.sections_for, acciones.armar

    def contar_sections(*a, **k):
        llamadas["sections"] += 1
        return real_sections(*a, **k)

    def contar_armar(*a, **k):
        llamadas["armar"] += 1
        return real_armar(*a, **k)

    monkeypatch.setattr(calculo, "sections_for", contar_sections)
    monkeypatch.setattr(acciones, "armar", contar_armar)
    overview = real_sections(caso.user, caso.procedure)
    calculo.proceso_de(caso.user, caso.procedure)
    assert llamadas == {"sections": 1, "armar": 1}
    calculo.proceso_de(caso.user, caso.procedure, overview)
    assert llamadas == {"sections": 1, "armar": 2}


@pytest.mark.parametrize("nombre", CASOS)
def test_proceso_de_no_escribe_nada(nombre, request):
    """REQ-145: calcular el proceso solo lee (ningún INSERT, UPDATE ni DELETE)."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    calculo.proceso_de(caso.user, caso.procedure)  # calienta cachés de ContentType, etc.
    with CaptureQueriesContext(connection) as consultas:
        calculo.proceso_de(caso.user, caso.procedure)
    escrituras = [q["sql"][:40] for q in consultas
                  if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert escrituras == []
