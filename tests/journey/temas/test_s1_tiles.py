"""Mosaicos de la sección Procedimiento (T-323; REQ-126, REQ-127, REQ-129, REQ-141; plan 017,
«Tablero: mosaicos y detalle» y D-5). Todo el material es inventado (P4); el Portal es el simulado."""

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.journey.sections import sections_for
from evaluon.journey.temas import s1_datos, s1_pliego, s1_portal
from evaluon.portal.models import ItemState, PortalItem, PortalLine
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s1_pliego import proposed
from tests.journey.temas.test_s1_portal import loaded  # noqa: F401
from tests.journey.test_tablero_secciones import Pagina, revisar
from tests.portal.fakeportal import (  # noqa: F401
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.portal.test_documents import docs_portal  # noqa: F401

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[3]
HOJAS = ["evaluon/static/journey/s1.css", "evaluon/static/journey/s1_pliego.css"]
PARCIALES = [
    "evaluon/templates/journey/temas/s1_datos.html",
    "evaluon/templates/journey/temas/s1_pliego.html",
    "evaluon/templates/journey/temas/s1_portal.html",
]
HEXA = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def pagina(client, procedure, query=""):
    respuesta = client.get(reverse("expedientes:procedimiento", args=[procedure.pk]) + query)
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def tiles_de(tema, user, procedure, rf):
    request = rf.get("/")
    request.user = user
    return {t.key: t for t in tema.tiles(user, procedure, tema.context(user, procedure, request))}


# --- REQ-126: la sección abre con su tablero y cada mosaico tiene su detalle ---------------------


def test_la_seccion_1_abre_con_sus_tres_mosaicos_y_cada_uno_su_detalle(
        client, procedure, operator_user):
    """REQ-126, D-5: datos, Portal y alta desde el pliego son mosaicos y abren el parcial de su
    tema; las anclas de la 014 viven dentro de su detalle."""
    log_in(client, operator_user)
    html = pagina(client, procedure)
    p = revisar(html)
    # El primer panel (T-321) suma antes sus propios mosaicos; acá se miran los de los temas.
    temas = [t["data-detail"] for t in p.tiles if t.get("data-detail", "").startswith("d-s1-")]
    assert temas[-3:] == ["d-s1-datos", "d-s1-portal", "d-s1-pliego"]
    assert {"d-s1-datos", "d-s1-portal", "d-s1-pliego"} <= set(p.details)
    assert {"s1-datos", "s1-renglones"} <= set(p.details["d-s1-datos"]["ids"])
    assert "s1-portal" in p.details["d-s1-portal"]["ids"]
    assert {"s1-pliego", "s1-pliego-subir"} <= set(p.details["d-s1-pliego"]["ids"])
    assert 'id="seccion-detalle"></div>' in html  # ningún tema queda fuera del tablero: el contenedor va vacío


def test_los_mosaicos_salen_de_los_tres_temas_en_su_orden(procedure, operator_user, rf):
    """REQ-126: la sección junta los mosaicos de sus tres temas, en el orden de los temas."""
    seccion = sections_for(operator_user, procedure).get("procedimiento")
    request = rf.get("/")
    request.user = operator_user
    contextos = {t.KEY: t.context(operator_user, procedure, request) for t in seccion.temas}
    claves = [t.key for t in seccion.tiles(operator_user, procedure, contextos)]
    # Los mosaicos propios del primer panel (T-321) van primero; los de los temas siguen en su orden.
    assert claves[-3:] == ["datos", "portal", "pliego"]


# --- REQ-141: sin datos, falta -----------------------------------------------------------------------


def test_a_mano_y_sin_nada_ningun_mosaico_muestra_cifra(procedure, operator_user, rf):
    """REQ-141: un procedimiento cargado a mano, sin renglones, sin Portal y sin pliegos, no
    inventa ninguna cifra: cada mosaico dice qué falta."""
    for tema in (s1_datos, s1_portal, s1_pliego):
        for tile in tiles_de(tema, operator_user, procedure, rf).values():
            assert not tile.has_data, f"{tema.KEY}/{tile.key} muestra {tile.big!r}"
            assert tile.missing


def test_el_cero_es_un_dato_en_el_mosaico_del_portal(loaded, operator_user, evaluator_user,  # noqa: F811
                                                     rf):
    """REQ-141: con el Portal vinculado y todo resuelto, «sin aprobar» vale 0 y se dibuja."""
    antes = tiles_de(s1_portal, operator_user, loaded, rf)["portal"]
    assert antes.has_data and antes.big > 0
    PortalItem.objects.filter(state=ItemState.PROPUESTO).update(
        state=ItemState.APROBADO, decided_by=evaluator_user, decided_at=timezone.now())
    despues = tiles_de(s1_portal, operator_user, loaded, rf)["portal"]
    assert despues.has_data and despues.big == 0


# --- Con datos: cada cifra sale del dato ---------------------------------------------------------------


def test_el_mosaico_de_datos_cuenta_los_renglones_del_procedimiento(
        loaded, operator_user, rf):  # noqa: F811
    """REQ-126: la cifra son los renglones cargados; el apoyo dice la apertura del cronograma y
    las garantías que consigna el Portal."""
    tile = tiles_de(s1_datos, operator_user, loaded, rf)["datos"]
    assert tile.has_data and tile.big == PortalLine.objects.filter(procedure=loaded).count()
    assert tile.unit == "renglones" and tile.width == 2 and tile.detail == "d-s1-datos"
    request = rf.get("/")
    request.user = operator_user
    ctx = s1_datos.context(operator_user, loaded, request)
    if ctx["opening"]:
        assert ctx["opening"][1] in tile.sub
    if ctx["guarantees"]:
        assert f"{len(ctx['guarantees'])} garant" in tile.sub


def test_el_mosaico_del_portal_cuenta_lo_sin_aprobar_igual_que_la_seccion(
        loaded, operator_user, rf):  # noqa: F811
    """REQ-126, REQ-129: «sin aprobar» es la propuesta más las novedades, lo mismo que cuenta la
    sección; el detalle es el del Portal."""
    tile = tiles_de(s1_portal, operator_user, loaded, rf)["portal"]
    propuesta, novedades, _ = s1_portal._counts(loaded)
    assert tile.big == propuesta + novedades and tile.detail == "d-s1-portal"
    assert tile.unit == "sin aprobar"
    assert f"{propuesta} de la propuesta" in tile.sub and f"{novedades} novedades" in tile.sub


def test_el_mosaico_del_pliego_cuenta_los_borradores_que_esperan(client, procedure, operator_user,
                                                                 rf):
    """REQ-126: los pliegos leídos que esperan aprobación son la cifra; sin ninguno, falta."""
    assert not tiles_de(s1_pliego, operator_user, procedure, rf)["pliego"].has_data
    proposed(client, operator_user)
    con = tiles_de(s1_pliego, operator_user, procedure, rf)["pliego"]
    assert con.has_data and con.big == 1 and con.detail == "d-s1-pliego"


# --- Qué detalle abre cada consulta --------------------------------------------------------------------


@pytest.mark.parametrize("tema, parametro, detalle", [
    (s1_portal, "portal", "d-s1-portal"), (s1_pliego, "pliego", "d-s1-pliego")])
def test_el_aviso_de_una_accion_abre_el_detalle_de_su_tema(tema, parametro, detalle):
    """REQ-127: al volver de una acción con `?portal=` o `?pliego=` se abre el detalle de su
    tema; sin el parámetro, ninguno."""
    assert tema.opens(SimpleNamespace(GET={parametro: "x"})) == detalle
    assert tema.opens(SimpleNamespace(GET={})) is None


def test_la_pagina_con_el_aviso_pide_abrir_el_detalle(client, procedure, operator_user):
    """REQ-127: `data-abre` lleva al detalle del Portal cuando la consulta trae su aviso."""
    log_in(client, operator_user)
    aviso = s1_portal.pack([s1_portal.entry("Listo")])
    assert Pagina(pagina(client, procedure, "?portal=" + aviso)).root.get(
        "data-abre") == "d-s1-portal"
    assert "data-abre" not in Pagina(pagina(client, procedure)).root


# --- REQ-129: por qué importa ---------------------------------------------------------------------------


def test_los_pendientes_del_portal_dicen_por_que_importan(loaded, operator_user):  # noqa: F811
    """REQ-129: la propuesta y las novedades traen el motivo, escrito por el tema que lo sabe."""
    seccion = sections_for(operator_user, loaded).get("procedimiento")
    items = [i for i in seccion.pending_items if "Portal" in i.text]
    assert items
    for item in items:
        assert item.why and len(item.why) > 20, item.text


# --- Estilos y velocidad --------------------------------------------------------------------------------


def test_los_parciales_y_hojas_de_la_seccion_no_tienen_estilos_en_linea_ni_hexadecimales():
    """ADR-0076: sin `style=`, sin scripts en línea y sin colores en hexadecimal."""
    for ruta in HOJAS + PARCIALES:
        texto = (RAIZ / ruta).read_text(encoding="utf-8")
        assert "style=" not in texto, ruta
        assert "<script" not in texto, ruta
    for ruta in HOJAS:
        assert not HEXA.search((RAIZ / ruta).read_text(encoding="utf-8")), ruta


def test_la_seccion_con_el_caso_chico_se_arma_en_dos_segundos(client, procedure, operator_user):
    """Umbral del plan: 2 s o menos hasta verse completa (mediana de tres cargas)."""
    log_in(client, operator_user)
    pagina(client, procedure)
    tiempos = []
    for _ in range(3):
        inicio = time.perf_counter()
        pagina(client, procedure)
        tiempos.append(time.perf_counter() - inicio)
    assert sorted(tiempos)[1] <= 2.0, tiempos
