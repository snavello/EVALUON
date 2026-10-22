"""Tablero de Evaluación, parte 2: informe técnico, dictamen, descartes, preguntas y exportar
(REQ-126, REQ-129, REQ-141; plan 017, «Evaluación y dictamen»; T-328).

Las cifras salen solo de lo guardado (P3): cada prueba compara el mosaico con lo que dicen la base
o los servicios, no con el código del tema. Las acciones de dictamen, descartes y preguntas siguen
a mano (P6): ningún mosaico ni pendiente decide por la persona. Todo el material es inventado
(P4)."""

import time

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import discards as discards_service
from evaluon.assessment.services import technical
from evaluon.journey import memo, temas
from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Tile
from evaluon.portal import models as pm
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    evaluated,
    open_matrix,
    requirement,
    three,
)
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401  (fixtures y ayudas)
from tests.assessment.test_technical_report import (  # noqa: F401  (fixtures y ayudas)
    FULL,
    model,
    offers,
    read_queue,
    report_pdf,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_descartes import proposed  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_dictamen import portal_dictamen, post_upload as subir_dictamen
from tests.journey.temas.test_s4_informe import post_upload as subir_informe
from tests.journey.temas.test_s4_preguntas import asked  # noqa: F401  (fixture)
from tests.journey.test_tablero_secciones import revisar

pytestmark = pytest.mark.django_db

CLAVES = {"informe": "s4_informe", "dictamen": "s4_dictamen", "descartes": "s4_descartes",
          "preguntas": "s4_preguntas", "exportar": "s4_exportar"}


def pedido(rf, user, query=""):
    request = rf.get("/" + query)
    request.user = user
    return request


@pytest.fixture
def mosaicos(rf, operator_user, procedure):
    """`mosaicos()`: los cinco mosaicos de esta parte, por clave, tal como los arma la vista (el
    contexto de cada tema se calcula una vez y `tiles()` lo reusa)."""

    def build(user=None, query=""):
        user = user or operator_user
        found = {}
        for tema in (temas.by_key(key) for key in CLAVES.values()):
            ctx = tema.context(user, procedure, pedido(rf, user, query))
            found.update({t.key: t for t in tema.tiles(user, procedure, ctx)})
        return found

    return build


def pagina(client, user, procedure, query=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    response = client.get(reverse("expedientes:evaluacion", args=[procedure.pk]) + query)
    assert response.status_code == 200
    return response.content.decode()


def html_del_mosaico(html, clave):
    return html.split(f'id="m-{clave}"')[1].split("</a>")[0]


# --- Contrato ---------------------------------------------------------------------------------------


def test_cada_tema_abre_su_propio_detalle_con_el_contrato_completo(mosaicos):
    """REQ-126: cada tema declara su mosaico, con el detalle `d-s4-…` de su parcial y sin color
    fuera de las clases del componente."""
    found = mosaicos()
    assert set(found) == set(CLAVES)
    for clave, tema_key in CLAVES.items():
        tile = found[clave]
        assert isinstance(tile, Tile)
        assert tile.detail == "d-" + tema_key.replace("_", "-")
        assert tile.tone != "dark"
        assert tile.title


# --- REQ-141: lo que no hay se dice, no se inventa ---------------------------------------------------


def test_un_procedimiento_vacio_dice_pendiente_en_cada_mosaico(client, procedure, operator_user,
                                                               mosaicos):
    """REQ-141: sin ofertas, evaluación ni dictamen ningún mosaico trae cifra ni gráfico; el
    del dictamen dice «Pendiente»."""
    for clave, tile in mosaicos().items():
        assert not tile.has_data, clave
        assert tile.chart is None, clave
        assert tile.missing, clave
    html = pagina(client, operator_user, procedure)
    revisar(html)
    dictamen = html_del_mosaico(html, "dictamen")
    assert 'class="missing">Pendiente' in dictamen and 'class="big' not in dictamen
    for clave in CLAVES:
        tarjeta = html_del_mosaico(html, clave)
        assert 'class="big' not in tarjeta and 'class="ch"' not in tarjeta, clave


# --- Dictamen ---------------------------------------------------------------------------------------


def test_sin_dictamen_el_mosaico_dice_pendiente_y_no_muestra_valor(mosaicos):
    """REQ-141: sin dictamen cargado ni publicado, «Pendiente»."""
    tile = mosaicos()["dictamen"]
    assert not tile.has_data and tile.missing == "Pendiente"
    assert "Portal" in tile.sub or "dictamen" in tile.sub.lower()


def test_un_dictamen_del_portal_sin_aprobar_sigue_pendiente_y_dice_que_falta_aprobar(
        procedure, operator_user, mosaicos):
    """REQ-141, REQ-129: el Portal publicó uno el 06/10/2026 pero no está aprobado: no es un
    dictamen cargado, y el mosaico lo dice sin darlo por tomado."""
    portal_dictamen(procedure, operator_user, published="2026-10-06")
    tile = mosaicos()["dictamen"]
    assert not tile.has_data and tile.missing == "Pendiente"
    assert "06/10/2026" in tile.sub and "aprobar" in tile.sub


def test_un_dictamen_aprobado_del_portal_muestra_que_esta_cargado_con_su_fecha(
        procedure, operator_user, mosaicos):
    """REQ-126: aprobada la carga, el mosaico lo muestra cargado y de dónde salió."""
    portal_dictamen(procedure, operator_user, state=pm.ItemState.APROBADO,
                    published="2026-10-06")
    tile = mosaicos()["dictamen"]
    assert tile.has_data and tile.big == "Cargado"
    assert "Portal" in tile.sub and "06/10/2026" in tile.sub


def test_un_dictamen_subido_muestra_que_esta_cargado_y_quien_lo_subio(
        client, procedure, operator_user, mosaicos):
    """REQ-126: el dictamen que sube la Comisión figura cargado, como subido por la Comisión."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    assert subir_dictamen(client, procedure).status_code == 302
    tile = mosaicos()["dictamen"]
    assert tile.has_data and tile.big == "Cargado"
    assert "Subido por la Comisión" in tile.sub


def test_el_ancla_dictamen_subir_de_la_014_abre_su_detalle(client, procedure, operator_user):
    """Funciones de la 014: `#dictamen-subir` y `#s4-dictamen` están dentro del detalle del
    dictamen, así que el tablero los abre."""
    html = pagina(client, operator_user, procedure)
    pagina_ = revisar(html)
    ids = pagina_.details["d-s4-dictamen"]["ids"]
    assert "dictamen-subir" in ids and "s4-dictamen" in ids
    from evaluon.journey.sections import s4
    assert s4.upload_url(procedure, operator_user).endswith("#dictamen-subir")


# --- Informe técnico --------------------------------------------------------------------------------


def test_sin_ofertas_con_renglones_tecnicos_el_informe_esta_pendiente(mosaicos):
    """REQ-141: sin renglones técnicos evaluados no hay informe que contar."""
    tile = mosaicos()["informe"]
    assert not tile.has_data and tile.missing == "Pendiente" and tile.chart is None


def test_con_renglones_tecnicos_y_sin_informe_dice_que_falta_y_en_que_ofertas(
        offers, mosaicos):
    """REQ-141: las ofertas piden el informe y no se subió: «Falta el informe», sin cifra, y
    el mosaico nombra las ofertas."""
    a, b = offers
    tile = mosaicos()["informe"]
    assert not tile.has_data and tile.missing.startswith("Falta el informe")
    assert f"{a.number}" in tile.sub and f"{b.number}" in tile.sub


def test_informe_subido_y_sin_leer_dice_en_espera_y_no_inventa_paginas(
        client, offers, procedure, evaluator_user, model, mosaicos):
    """REQ-141: subido el informe y antes de leerlo, el mosaico dice que espera lectura y no
    trae una cantidad de páginas ni una propuesta."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    assert subir_informe(client, procedure).status_code == 302
    tile = mosaicos()["informe"]
    assert tile.has_data and tile.big == "En espera"
    assert "pág" not in tile.sub and "apto" not in tile.sub.lower()
    assert tile.chart is None


def test_informe_leido_cuenta_apto_y_no_apto_de_lo_guardado_y_las_paginas_conocidas(
        client, offers, procedure, evaluator_user, model, mosaicos):
    """REQ-126, P3: leído el informe, el mosaico dice «Leído», cuenta lo que propone (5 aptos
    y 1 no apto de seis renglones, según el guion) y las páginas leídas; es una propuesta."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    subir_informe(client, procedure, data=report_pdf(*FULL))
    read_queue()
    verdicts = [p.verdict for offer in offers for p in technical.proposals_of(offer).values()]
    tile = mosaicos()["informe"]
    assert tile.has_data and tile.big == "Leído"
    assert verdicts.count("apto") == 5 and verdicts.count("no_apto") == 1
    assert "5 apto" in tile.sub and "1 no apto" in tile.sub and "propuesta" in tile.sub.lower()
    assert "pág" in tile.sub and "Ok de la Comisión: 0 de 6" in tile.sub
    assert isinstance(tile.chart, charts.Stack)
    assert {p.label for p in tile.chart.parts} >= {"Apto", "No apto"}
    assert sum(p.value for p in tile.chart.parts if p.label in ("Apto", "No apto")) == 6


def test_las_paginas_del_informe_repetido_en_cada_oferta_se_cuentan_una_vez(
        client, offers, procedure, evaluator_user, model, mosaicos):
    """P3: el mismo archivo cargado en dos ofertas es un solo informe; no se suman sus páginas
    dos veces."""
    from evaluon.offers.models import Document, DocumentKind
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    subir_informe(client, procedure, data=report_pdf(*FULL))
    read_queue()
    docs = Document.objects.filter(kind=DocumentKind.INFORME_TECNICO)
    assert docs.count() == 2 and len({d.file_sha256 for d in docs}) == 1
    reading = docs.first().readings.order_by("-sequence").first()
    data = reading.pages
    listed = data.get("pages", []) if isinstance(data, dict) else data
    tile = mosaicos()["informe"]
    assert (f"{len(listed)} págs." if len(listed) != 1 else "1 pág.") in tile.sub


def test_los_pendientes_del_informe_dicen_por_que_importan(offers, procedure, operator_user):
    """REQ-129: cada renglón suelto del informe trae su motivo; ninguno decide con un clic."""
    from evaluon.journey.temas import s4_informe
    estado = s4_informe.status(operator_user, procedure)
    assert estado.pending_items
    for item in estado.pending_items:
        assert item.why.strip(), item.text
        assert item.post is None


# --- Descartes --------------------------------------------------------------------------------------


def test_sin_evaluacion_los_descartes_estan_pendientes(three, mosaicos):
    """REQ-141: con ofertas y sin evaluar no hay descartes que contar ni que decir «cero»."""
    tile = mosaicos()["descartes"]
    assert not tile.has_data and tile.missing == "Pendiente"


def test_los_descartes_por_decidir_son_los_que_propuso_el_sistema_y_no_decidio_la_comision(
        client, proposed, procedure, evaluator_user, mosaicos):
    """REQ-126, P3: el mosaico cuenta los descartes propuestos sin decidir, igual que el
    servicio; confirmar uno lo baja y suma a los decididos."""
    page = memo.matrix_page(evaluator_user, procedure.pk)
    found = discards_service.units(page)
    pendientes = [u for u in found if u.state == discards_service.PROPOSED]
    assert len(pendientes) == 2
    tile = mosaicos()["descartes"]
    assert tile.has_data and tile.big == 2 and "por decidir" in tile.unit
    b = proposed[1]
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    done = client.post(reverse("expedientes:s4_decidir_descarte", args=[procedure.pk]),
                       {"offer": b.pk, "line": "", "action": "confirmar", "note": ""})
    assert done.status_code == 302
    tile = mosaicos()["descartes"]
    assert tile.big == 1 and "1 confirmado" in tile.sub


def test_sin_descartes_propuestos_el_cero_es_un_dato(client, three, procedure, operator_user,
                                                     mosaicos):
    """REQ-141: una evaluación sin motivos de descarte dice 0 (el cero es dato), no «Pendiente»."""
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    for offer in three:
        add_run(operator_user, procedure, offer, {declaration: "cumple"})
    tile = mosaicos()["descartes"]
    assert tile.has_data and tile.big == 0
    html = pagina(client, operator_user, procedure)
    assert 'class="big">0' in html_del_mosaico(html, "descartes")


def test_los_pendientes_de_descartes_dicen_por_que_importan_y_se_deciden_a_mano(
        proposed, procedure, operator_user):
    """REQ-129, P6: cada descarte por decidir trae su motivo y su enlace al renglón; no hay
    botón de un clic: la decisión es de la Comisión, con su formulario."""
    from evaluon.journey.temas import s4_descartes
    estado = s4_descartes.status(operator_user, procedure)
    assert len(estado.pending_items) == 2
    for item in estado.pending_items:
        assert item.why.strip(), item.text
        assert item.post is None
        assert "#desc-" in item.url


# --- Preguntas --------------------------------------------------------------------------------------


def test_sin_evaluacion_las_preguntas_estan_pendientes(three, mosaicos):
    """REQ-141: sin evaluación no se muestra «0 preguntas»."""
    tile = mosaicos()["preguntas"]
    assert not tile.has_data and tile.missing == "Pendiente"


def test_las_preguntas_cuentan_lo_que_espera_una_respuesta_o_una_decision(
        asked, procedure, operator_user, mosaicos):
    """REQ-126: una abierta y una subsanación por decidir esperan a la Comisión, y una está
    respondida: el mosaico dice 2 y «1 resuelta»."""
    tile = mosaicos()["preguntas"]
    assert tile.has_data and tile.big == 2
    assert "1 resuelta" in tile.sub
    assert "por resolver" in tile.unit


def test_las_preguntas_no_tienen_pendientes_propios(asked, procedure, operator_user):
    """REQ-129: los pendientes de preguntas los lista `s4_propuesta` (con su `why`); este tema
    no los duplica."""
    from evaluon.journey.temas import s4_preguntas
    assert s4_preguntas.status(operator_user, procedure).pending_items == ()


def test_el_filtro_de_preguntas_abiertas_abre_su_detalle(rf, operator_user):
    """REQ-127: `?preg=abiertas` abre el detalle de las preguntas; sin él no abre nada."""
    tema = temas.by_key("s4_preguntas")
    assert tema.opens(pedido(rf, operator_user)) is None
    assert tema.opens(pedido(rf, operator_user, "?preg=abiertas")) == "d-s4-preguntas"
    assert tema.opens(pedido(rf, operator_user, "?preg=otra")) is None


def test_el_filtro_de_preguntas_no_cambia_las_cifras(asked, procedure, operator_user, rf):
    """P3: filtrar la tabla no cambia el mosaico."""
    tema = temas.by_key("s4_preguntas")
    sin = tema.tiles(operator_user, procedure, tema.context(operator_user, procedure,
                                                           pedido(rf, operator_user)))
    con = tema.tiles(operator_user, procedure, tema.context(
        operator_user, procedure, pedido(rf, operator_user, "?preg=abiertas")))
    assert sin == con


# --- Exportar ---------------------------------------------------------------------------------------


def test_exportar_sin_ofertas_esta_pendiente(mosaicos):
    """REQ-141: sin ofertas no hay qué exportar."""
    tile = mosaicos()["exportar"]
    assert not tile.has_data and tile.missing == "Pendiente"


def test_exportar_con_ofertas_ofrece_los_dos_documentos(three, mosaicos):
    """REQ-126: con ofertas hay dos documentos (planilla y cuadro), en Excel y en PDF."""
    tile = mosaicos()["exportar"]
    assert tile.has_data and tile.big == 2 and "Excel" in tile.sub and "PDF" in tile.sub


# --- La sección --------------------------------------------------------------------------------------


def test_los_mosaicos_son_enlaces_y_no_deciden_nada(client, proposed, procedure, operator_user):
    """REQ-129, P6: ningún mosaico trae formularios ni botones: abrir un detalle no cambia nada;
    la decisión sigue en los formularios del detalle."""
    html = pagina(client, operator_user, procedure)
    for clave in CLAVES:
        tarjeta = html_del_mosaico(html, clave)
        assert "<form" not in tarjeta and "<button" not in tarjeta, clave


def test_cada_mosaico_abre_un_detalle_que_existe_con_sus_formularios(
        client, proposed, procedure, evaluator_user):
    """REQ-126, REQ-127: los cinco detalles existen, sin repetirse, y traen las anclas de la
    014 de cada tema."""
    pagina_ = revisar(pagina(client, evaluator_user, procedure))
    ahora = {t["data-detail"] for t in pagina_.tiles if "data-detail" in t}
    assert {"d-s4-informe", "d-s4-dictamen", "d-s4-descartes", "d-s4-preguntas",
            "d-s4-exportar"} <= ahora
    anclas = {"d-s4-informe": "s4-informe", "d-s4-dictamen": "s4-dictamen",
              "d-s4-descartes": "s4-descartes", "d-s4-preguntas": "s4-preguntas",
              "d-s4-exportar": "s4-exportar"}
    for detalle, ancla in anclas.items():
        assert ancla in pagina_.details[detalle]["ids"], detalle


def test_el_dictamen_aprobado_desde_el_pendiente_cambia_el_mosaico(
        client, procedure, operator_user, mosaicos):
    """REQ-129, REQ-126: tomar el dictamen del Portal (acción a mano) lo pasa de «Pendiente» a
    «Cargado»."""
    portal_dictamen(procedure, operator_user)
    assert not mosaicos()["dictamen"].has_data
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    client.post(reverse("expedientes:s4_dictamen_tomar", args=[procedure.pk]))
    assert mosaicos()["dictamen"].big == "Cargado"


def test_los_mosaicos_reusan_el_contexto_de_cada_tema(proposed, procedure, operator_user, rf,
                                                      monkeypatch):
    """Plan 017: `tiles()` usa lo que ya calculó `context()`; no vuelve a armar la matriz."""
    contexts = {}
    for key in CLAVES.values():
        tema = temas.by_key(key)
        contexts[key] = tema.context(operator_user, procedure, pedido(rf, operator_user))

    def prohibido(*args, **kwargs):
        raise AssertionError("tiles() volvió a calcular la matriz")

    monkeypatch.setattr(memo, "matrix_page", prohibido)
    for key in CLAVES.values():
        tema = temas.by_key(key)
        assert tema.tiles(operator_user, procedure, contexts[key])


def test_la_seccion_se_arma_en_dos_segundos_con_el_caso_chico(client, proposed, procedure,
                                                              operator_user):
    """T-328: sección en 2 s o menos con el caso chico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:evaluacion", args=[procedure.pk])
    client.get(url)  # calienta las plantillas
    inicio = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - inicio < 2.0
