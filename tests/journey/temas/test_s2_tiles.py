"""El tablero de la sección Pliego y matriz (REQ-126, REQ-129, REQ-141; plan 017, «Pliego y
matriz»; T-325). Los resultados de la evaluación se guardan directo, sin el modelo; todo el
material es inventado (P4)."""

import dataclasses
import datetime
import itertools
import time
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.journey import memo, sections, temas
from evaluon.journey.sections.base import Item
from evaluon.journey.tablero import charts
from evaluon.portal import models as p
from evaluon.tenders.models import Document, Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures)
    evaluated,
    three,
)
from tests.journey.test_tablero_secciones import Pagina, revisar

pytestmark = pytest.mark.django_db

_n = itertools.count(1)
DOCUMENTOS = temas.by_key("s2_documentos")
MATRIZ = temas.by_key("s2_matriz")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:pliego", args=[procedure.pk])


@pytest.fixture
def bare(operator_user):
    return Procedure.objects.create(
        number=f"TILES-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)


def tiles_of(user, procedure, rf, query=""):
    """Los mosaicos de la sección, calculados como los calcula la vista."""
    request = rf.get("/" + query)
    request.user = user
    found = {}
    with memo.scope():
        for tema in (DOCUMENTOS, MATRIZ):
            ctx = tema.context(user, procedure, request)
            for tile in tema.tiles(user, procedure, ctx):
                found[tile.key] = tile
    return found


def portal_lists(procedure, user, names):
    link = p.PortalLink.objects.create(url=f"https://portal.ejemplo.test/{next(_n)}?qs=1",
                                       procedure=procedure, created_by=user)
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    page_row = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                           url=link.url, sha256="c" * 64, content=b"x")
    for key, name in names:
        p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.DOCUMENTO, key=key,
                                    payload={"nombre": name, "clase": "anexo"},
                                    content_sha256="d" * 64, page=page_row)


# --- Sin pliego (REQ-141) ----------------------------------------------------------------------


def test_sin_pliego_ningun_mosaico_muestra_cifra_y_el_de_cumplimiento_dice_pendiente(
        bare, operator_user, rf):
    """REQ-141: sin pliego, los mosaicos dicen «Falta el pliego» y el de cumplimiento dice
    «Pendiente»; ninguno trae cifra ni gráfico."""
    found = tiles_of(operator_user, bare, rf)
    assert list(found) == ["documentos", "requisitos", "versiones", "cumplimiento"]
    for tile in found.values():
        assert not tile.has_data and tile.chart is None, tile.key
    assert found["documentos"].missing == "Falta el pliego"
    assert found["requisitos"].missing == "Falta el pliego"
    assert found["versiones"].missing == "Falta el pliego"
    assert found["cumplimiento"].missing == "Pendiente"


def test_con_pliego_y_sin_matriz_el_mosaico_de_requisitos_dice_que_falta_la_matriz(
        bare, operator_user, rf):
    """REQ-141: hay un documento cargado, así que no falta el pliego; falta la matriz."""
    Document.objects.create(procedure=bare, kind="pliego", title="Pliego", file_name="p.pdf",
                            file_format="pdf", file_size=1, file_sha256="a" * 64,
                            loaded_by=operator_user)
    found = tiles_of(operator_user, bare, rf)
    assert found["documentos"].big == 1 and found["documentos"].unit == "cargado"
    assert found["requisitos"].missing == "Falta la matriz" and not found["requisitos"].has_data
    assert found["versiones"].missing == "Falta la matriz"


# --- Con el caso chico -------------------------------------------------------------------------


def test_requisitos_cuenta_la_matriz_por_tipo_y_dice_la_version(procedure, matrix, operator_user,
                                                                rf):
    """REQ-126: la cantidad de requisitos vivos, su versión y la barra por tipo."""
    found = tiles_of(operator_user, procedure, rf)
    tile = found["requisitos"]
    live = matrix.version.requirements.exclude(state__in=("quitado", "sugerido"))
    assert tile.big == live.count() and tile.unit == "requisitos"
    assert tile.width == 2 and tile.detail == "d-s2-matriz"
    assert f"Versión {matrix.version.number}" in tile.sub
    assert isinstance(tile.chart, charts.Stack)
    assert sum(part.value for part in tile.chart.parts) == live.count()
    assert [part.label for part in tile.chart.parts] == ["Formales", "Económicos", "Técnicos"]


def test_versiones_abre_el_mismo_detalle_que_requisitos(procedure, matrix, operator_user, rf):
    """REQ-127: «Versiones» y «Requisitos» abren el detalle de la matriz (`d-s2-matriz`)."""
    found = tiles_of(operator_user, procedure, rf)
    assert found["versiones"].detail == found["requisitos"].detail == "d-s2-matriz"
    assert found["versiones"].big == f"v{matrix.version.number}"
    assert "Validada" in found["versiones"].sub


def test_documentos_dice_cuantos_estan_cargados_y_el_de_n_solo_si_el_portal_los_lista(
        procedure, matrix, operator_user, rf):
    """REQ-126: «N cargados»; el «de N» aparece solo cuando el Portal lista documentos que no se
    tomaron."""
    cargados = procedure.documents.filter(kind__in=("pliego", "anexo", "especificaciones")).count()
    sin_portal = tiles_of(operator_user, procedure, rf)["documentos"]
    assert sin_portal.big == cargados and not sin_portal.unit.startswith("de ")
    assert sin_portal.detail == "d-s2-documentos"
    portal_lists(procedure, operator_user, [("a3", "Anexo III inventado")])
    con_portal = tiles_of(operator_user, procedure, rf)["documentos"]
    assert con_portal.big == cargados and con_portal.unit == f"de {cargados + 1}"
    assert "Anexo III inventado" in con_portal.sub


# --- Cumplimiento por tipo y oferta ------------------------------------------------------------


def test_sin_evaluacion_el_cumplimiento_dice_pendiente_y_enlaza_a_la_propuesta(
        procedure, matrix, offer, operator_user, rf):
    """REQ-141: con ofertas y sin evaluación el mosaico dice «Pendiente», sin cifra, y enlaza a
    la propuesta de la sección Evaluación."""
    tile = tiles_of(operator_user, procedure, rf)["cumplimiento"]
    assert not tile.has_data and tile.missing == "Pendiente"
    assert tile.width == 4 and tile.detail == ""
    assert tile.href == reverse("expedientes:evaluacion", args=[procedure.pk]) + "#d-s4-propuesta"


def test_con_evaluacion_el_cumplimiento_es_una_tabla_de_calor_con_las_cuentas_reales(
        evaluated, procedure, matrix, operator_user, rf):
    """REQ-126, P3: cada celda cuenta los resultados vigentes que cumplen sobre los requisitos del
    tipo; la cifra grande es el total de los que cumplen."""
    tile = tiles_of(operator_user, procedure, rf)["cumplimiento"]
    assert isinstance(tile.chart, charts.Heat) and tile.chart.has_data
    assert tile.chart.columns == [f"Of. {o.number}" for o in evaluated]
    cumplen = am.Result.objects.filter(outcome="cumple").count()
    assert tile.big == cumplen and cumplen > 0
    by_label = {row.label: row for row in tile.chart.rows}
    formal = by_label["Formales"]
    for offer, cell in zip(evaluated, formal.cells):
        mine = am.Result.objects.filter(offer=offer, requirement__category="formal")
        assert cell.value == mine.filter(outcome="cumple").count()
        assert cell.total == matrix.version.requirements.filter(category="formal").exclude(
            state__in=("quitado", "sugerido")).count()
    assert tile.href.endswith("#d-s4-propuesta")


def test_una_oferta_sin_evaluar_deja_su_columna_vacia(evaluated, procedure, operator_user,
                                                       rf, three):
    """REQ-141: una oferta sin evaluación no inventa ceros: sus celdas quedan vacías."""
    from tests.offers.conftest import make_offer
    make_offer(procedure, operator_user, "Oferente sin evaluar",
               {"oferta.pdf": ["Texto de la oferta."]})
    tile = tiles_of(operator_user, procedure, rf)["cumplimiento"]
    assert len(tile.chart.columns) == 4
    assert all(row.cells[3] is None for row in tile.chart.rows)


# --- Qué abre cada consulta --------------------------------------------------------------------


@pytest.mark.parametrize("query, abre", [("", None), ("?historial=retirados", "d-s2-documentos"),
                                         ("?docs=x", "d-s2-documentos")])
def test_opens_de_documentos(rf, query, abre):
    """REQ-127: el historial y el resultado de una subida abren el detalle de documentos."""
    assert DOCUMENTOS.opens(rf.get("/" + query)) == abre


@pytest.mark.parametrize("query, abre", [("", None), ("?filtro=falta", "d-s2-matriz"),
                                         ("?tipo=formal", "d-s2-matriz"),
                                         ("?q=garantia", "d-s2-matriz"),
                                         ("?aviso=x", "d-s2-matriz")])
def test_opens_de_la_matriz(rf, query, abre):
    """REQ-127: los filtros y el aviso de una acción abren el detalle de la matriz."""
    assert MATRIZ.opens(rf.get("/" + query)) == abre


# --- La página ---------------------------------------------------------------------------------


def test_la_pagina_abre_con_su_tablero_y_conserva_las_anclas_de_la_014(
        client, procedure, matrix, operator_user):
    """REQ-126, REQ-129: cuatro mosaicos; los detalles traen las anclas de la 014 (subir archivo,
    tabla de la matriz, filtros) y las acciones a mano."""
    log_in(client, operator_user)
    response = client.get(tab(procedure))
    assert response.status_code == 200
    pagina = revisar(response.content.decode())
    assert [t.get("id") for t in pagina.tiles] == [
        "m-documentos", "m-requisitos", "m-versiones", "m-cumplimiento"]
    assert pagina.tiles[3].get("href").endswith("#d-s4-propuesta")
    assert "data-detail" not in pagina.tiles[3]
    assert {"d-s2-documentos", "d-s2-matriz"} == set(pagina.details)
    assert {"s2-documentos", "s2-subir"} <= set(pagina.details["d-s2-documentos"]["ids"])
    assert {"s2-matriz", "t-matriz"} <= set(pagina.details["d-s2-matriz"]["ids"])


def test_la_pagina_sin_pliego_dice_falta_y_no_muestra_cifras(client, bare, operator_user):
    """REQ-141: sin pliego, de punta a punta, ningún mosaico dibuja cifra."""
    log_in(client, operator_user)
    html = client.get(tab(bare)).content.decode()
    mosaicos = html.split('<a class="tile')[1:]
    assert len(mosaicos) == 4
    for mosaico in mosaicos:
        mosaico = mosaico.split("</a>")[0]
        assert 'class="big' not in mosaico and 'class="ch"' not in mosaico
        assert 'class="missing"' in mosaico
    assert "Falta el pliego" in html and "Pendiente" in html


def test_un_filtro_de_la_matriz_abre_su_detalle(client, procedure, matrix, operator_user):
    """REQ-127: `?filtro=falta` llega con el detalle de la matriz ya desplegado."""
    log_in(client, operator_user)
    html = client.get(tab(procedure) + "?filtro=falta").content.decode()
    assert Pagina(html).root["data-abre"] == "d-s2-matriz"


def test_la_seccion_carga_en_menos_de_dos_segundos_con_el_caso_chico(
        client, evaluated, procedure, matrix, operator_user):
    """Umbral de la 017: la sección completa, con evaluación, en 2 s o menos."""
    log_in(client, operator_user)
    client.get(tab(procedure))  # la primera carga calienta cachés de plantillas
    empezo = time.perf_counter()
    assert client.get(tab(procedure)).status_code == 200
    assert time.perf_counter() - empezo <= 2.0


# --- Por qué importa ---------------------------------------------------------------------------


@pytest.mark.skipif("why" not in {f.name for f in dataclasses.fields(Item)},
                    reason="`Item.why` lo agrega T-318")
def test_los_pendientes_de_la_matriz_dicen_por_que_importan(procedure, matrix, operator_user):
    """REQ-129: los renglones de la matriz en borrador traen su «por qué importa»."""
    from evaluon.tenders.models import Requirement, RequirementState
    from evaluon.tenders.services import validation
    opened = validation.open_new_version(operator_user, procedure.pk)
    draft = opened if hasattr(opened, "requirements") else procedure.matrix_versions.get(
        status="borrador")
    first = draft.requirements.order_by("number").first()
    Requirement.objects.filter(pk=first.pk).update(state=RequirementState.PROPUESTO)
    pending, _, _ = MATRIZ._decision_items(draft)
    assert pending and all(item.why for item in pending)


def test_la_seccion_trae_los_cuatro_mosaicos_de_sus_temas(procedure, matrix, operator_user, rf):
    """Definición compartida 2: `Section.tiles` junta los de `s2_documentos` y `s2_matriz`."""
    section = sections.sections_for(operator_user, procedure).get("pliego")
    request = SimpleNamespace(GET={})
    with memo.scope():
        contexts = {t.KEY: t.context(operator_user, procedure, rf.get("/")) for t in section.temas}
        assert [t.key for t in section.tiles(operator_user, procedure, contexts)] == [
            "documentos", "requisitos", "versiones", "cumplimiento"]
    assert section.opens(request) is None
