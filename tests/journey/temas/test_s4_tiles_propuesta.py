"""Tablero de Evaluación, parte 1: resultado por oferta, no cumple, no determinado y cumplimiento
por tipo (REQ-126, REQ-141; plan 017, «Evaluación y dictamen»; T-327).

Las cifras salen solo de las celdas guardadas (P3): cada prueba calcula lo esperado leyendo los
`Result` y las `Decision` de la base, sin pasar por el código del tema. Los resultados se guardan
directo, sin el modelo; todo el material es inventado (P4)."""

import dataclasses
import time
from collections import Counter

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.journey import memo, sections, temas
from evaluon.journey.sections.base import Item
from evaluon.journey.tablero import charts
from evaluon.journey.tablero.tiles import Tile
from evaluon.offers.services import sheets
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    decide,
    evaluated,
    requirement,
    three,
)
from tests.journey.test_tablero_secciones import Pagina, revisar

pytestmark = pytest.mark.django_db

DETALLE = "d-s4-propuesta"
CLAVES = ["resultado", "nocumple", "nodeterminado", "tipo"]


def tema():
    return temas.by_key("s4_propuesta")


def pedido(rf, user, query=""):
    request = rf.get("/" + query)
    request.user = user
    return request


@pytest.fixture
def tableros(rf, operator_user, procedure):
    """`tableros()`: los cuatro mosaicos de la propuesta, por clave, tal como los arma la vista
    (el contexto del tema se calcula una vez y `tiles()` lo reusa)."""

    def build(query=""):
        request = pedido(rf, operator_user, query)
        ctx = tema().context(operator_user, procedure, request)
        return {t.key: t for t in tema().tiles(operator_user, procedure, ctx)}

    return build


def pagina(client, user, procedure, query=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    response = client.get(reverse("expedientes:evaluacion", args=[procedure.pk]) + query)
    assert response.status_code == 200
    return response.content.decode()


def esperado(offer, procedure):
    """Lo que dicen las celdas guardadas de `offer`: cuenta cada resultado vigente (con la
    última decisión de estado, si la hay) sin pasar por el tema. Una celda sin resultado, con la
    propuesta rechazada o a la espera del informe técnico es pendiente."""
    version = procedure.matrix_versions.get(number=1)
    total = len(sheets.firm_requirements(version))
    cuenta = Counter()
    for result in am.Result.objects.filter(offer=offer).select_related("requirement"):
        decision = (am.Decision.objects.filter(
            result=result, action__in=("confirmar", "corregir", "rechazar"))
            .order_by("-at", "-pk").first())
        if decision is None or decision.action == "confirmar":
            outcome = result.outcome
        else:
            outcome = decision.outcome_after or None
        if outcome is None:
            continue
        if result.facts.get("aplica") is False and outcome == result.outcome:
            cuenta["na"] += 1
        elif outcome == "no_determinado" and result.doubt == "pendiente_informe_tecnico":
            cuenta["pe"] += 1
        elif outcome == "cumple":
            cuenta["ok"] += 1
        elif outcome in ("no_cumple", "sin_documento"):
            cuenta["no"] += 1
        else:
            cuenta["nd"] += 1
    cuenta["pe"] += total - sum(cuenta.values())
    return cuenta, total


def donas(tile):
    return {i.label: i for i in tile.chart.items}


# --- REQ-141: sin evaluación ------------------------------------------------------------------


def test_sin_evaluacion_cada_mosaico_dice_pendiente_y_no_muestra_valor(
        procedure, matrix, offer, tableros):
    """REQ-141: con ofertas pero sin evaluación, los cuatro mosaicos dicen «Pendiente» y no
    traen cifra ni gráfico."""
    mosaicos = tableros()
    assert list(mosaicos) == CLAVES
    for tile in mosaicos.values():
        assert isinstance(tile, Tile)
        assert not tile.has_data and tile.missing == "Pendiente", tile.key
        assert tile.detail == DETALLE


def test_sin_evaluacion_la_pagina_no_dibuja_cifras_ni_graficos(client, procedure, matrix, offer,
                                                               operator_user):
    """REQ-141: de punta a punta, los mosaicos de la propuesta dicen «Pendiente»."""
    html = pagina(client, operator_user, procedure)
    partes = html.split('<a class="tile')[1:]
    mios = [p.split("</a>")[0] for p in partes if 'data-detail="d-s4-propuesta"' in p]
    assert len(mios) == 4
    for parte in mios:
        assert 'class="missing">Pendiente<' in parte
        assert 'class="big' not in parte and 'class="ch"' not in parte


def test_sin_ofertas_ni_matriz_tampoco_hay_cifras(client, procedure, operator_user, tableros):
    """REQ-141: un procedimiento sin nada cargado no inventa un cero."""
    assert not any(t.has_data for t in tableros().values())


# --- Las cifras son las de las celdas -----------------------------------------------------------


def test_las_cifras_coinciden_con_las_celdas_guardadas(evaluated, procedure, tableros):
    """REQ-126, P3: la dona de cada oferta, «No cumple» y «No determinado» salen de las celdas:
    se comparan con el conteo directo de los resultados guardados."""
    mosaicos = tableros()
    dona = donas(mosaicos["resultado"])
    suma_no = suma_nd = 0
    for oferta in evaluated:
        cuenta, total = esperado(oferta, procedure)
        item = dona[f"Of. {oferta.number}"]
        assert (item.ok, item.no, item.nd, item.pe) == (
            cuenta["ok"], cuenta["no"], cuenta["nd"], cuenta["pe"]), oferta.number
        assert item.total + cuenta["na"] == total
        suma_no += cuenta["no"]
        suma_nd += cuenta["nd"]
    assert mosaicos["nocumple"].big == suma_no == 2  # B no cumple una; C no encontró una
    assert mosaicos["nodeterminado"].big == suma_nd == 1
    assert mosaicos["resultado"].big == 3
    assert mosaicos["resultado"].unit.startswith("de 3")


def test_el_resto_de_los_requisitos_sin_resultado_es_pendiente(evaluated, procedure, tableros):
    """P3: los requisitos que la evaluación no resolvió no se cuentan como cumplidos."""
    item = donas(tableros()["resultado"])[f"Of. {evaluated[0].number}"]
    assert item.ok == 3 and item.pe == item.total - 3 > 0


def test_cero_es_un_dato(procedure, matrix, three, operator_user, tableros):
    """REQ-141: si hay evaluación y nadie incumple, «No cumple» muestra 0 (no «Pendiente»)."""
    declaracion = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, three[0], {declaracion: "cumple"})
    mosaicos = tableros()
    assert mosaicos["nocumple"].big == 0 and mosaicos["nocumple"].has_data
    assert mosaicos["nodeterminado"].big == 0 and mosaicos["nodeterminado"].has_data


def test_una_correccion_de_la_comision_cambia_la_cifra(evaluated, procedure, operator_user,
                                                      evaluator_user, tableros):
    """P3: la cifra es la del resultado vigente: una corrección mueve el par de «no cumple» a
    «cumple»; un rechazo lo deja pendiente."""
    declaracion = requirement(procedure, "declaración jurada")
    registro = requirement(procedure, "constancia de inscripción")
    b, c = evaluated[1], evaluated[2]
    decide(evaluator_user, am.Result.objects.get(offer=b, requirement=declaracion),
           "corregir", outcome_after="cumple", note="Lo presentó fuera del sobre.")
    decide(evaluator_user, am.Result.objects.get(offer=c, requirement=registro),
           "rechazar", note="Hay que evaluarla de nuevo.")
    mosaicos = tableros()
    dona = donas(mosaicos["resultado"])
    for oferta in (b, c):
        cuenta, _ = esperado(oferta, procedure)
        item = dona[f"Of. {oferta.number}"]
        assert (item.ok, item.no, item.nd, item.pe) == (
            cuenta["ok"], cuenta["no"], cuenta["nd"], cuenta["pe"])
    assert dona[f"Of. {b.number}"].no == 0
    assert mosaicos["nocumple"].big == 0  # B corregida; C rechazada: sin resultado hasta evaluar


def test_a_la_espera_del_informe_tecnico_es_pendiente_y_no_determinado_no(
        procedure, matrix, three, operator_user, tableros):
    """P3: el par que espera el informe del área se muestra como pendiente, como en la tabla."""
    declaracion = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, three[0], {
        declaracion: ("no_determinado", "pendiente_informe_tecnico")})
    cuenta, total = esperado(three[0], procedure)
    item = donas(tableros()["resultado"])[f"Of. {three[0].number}"]
    assert item.nd == cuenta["nd"] == 0 and item.pe == total
    assert tableros()["nodeterminado"].big == 0


def test_un_requisito_que_no_aplica_no_cuenta_como_cumple(procedure, matrix, three,
                                                         operator_user, tableros):
    """P3 (T-240): un par guardado como «cumple» con `aplica = false` no es un cumplimiento ni
    entra en el total; el mosaico lo dice."""
    declaracion = requirement(procedure, "declaración jurada")
    registro = requirement(procedure, "constancia de inscripción")
    guardado = add_run(operator_user, procedure, three[0],
                       {declaracion: "cumple", registro: "cumple"})
    am.Result.objects.filter(pk=guardado[registro.pk].pk).update(
        facts={"aplica": False, "regla": "opcion_no_usada"})
    cuenta, total = esperado(three[0], procedure)
    mosaico = tableros()["resultado"]
    item = donas(mosaico)[f"Of. {three[0].number}"]
    assert cuenta["na"] == 1 and item.ok == cuenta["ok"] == 1
    assert item.total == total - 1
    assert "1 no aplica" in mosaico.sub


def test_cada_oferta_suma_todos_los_requisitos(evaluated, procedure, tableros):
    """P3: cumple + no cumple + no determinado + pendiente (+ no aplica) = requisitos de la
    matriz: ninguna celda se pierde ni se cuenta dos veces."""
    version = procedure.matrix_versions.get(number=1)
    total = len(sheets.firm_requirements(version))
    for item in donas(tableros()["resultado"]).values():
        assert item.total == total


def test_una_oferta_sin_evaluar_no_se_dibuja_y_se_nombra(procedure, matrix, three, operator_user,
                                                        tableros):
    """P3: la oferta que todavía no se evaluó no aparece como una dona de ceros: se nombra."""
    declaracion = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, three[0], {declaracion: "cumple"})
    mosaico = tableros()["resultado"]
    assert list(donas(mosaico)) == [f"Of. {three[0].number}"]
    assert mosaico.big == 1 and "de 3" in mosaico.unit
    assert f"{three[1].number}" in mosaico.sub and f"{three[2].number}" in mosaico.sub
    assert "sin evaluar" in mosaico.sub.lower()


# --- Cumplimiento por tipo ----------------------------------------------------------------------


def test_el_cumplimiento_por_tipo_coincide_con_las_celdas(evaluated, procedure, tableros):
    """REQ-126: la tabla de calor cuenta los pares que cumplen por clase de requisito y oferta;
    sumando las clases da lo mismo que la dona de cada oferta."""
    mosaico = tableros()["tipo"]
    assert isinstance(mosaico.chart, charts.Heat)
    assert mosaico.chart.columns == [f"Of. {o.number}" for o in evaluated]
    version = procedure.matrix_versions.get(number=1)
    clase = {r.pk: r.category for r in sheets.firm_requirements(version)}
    for j, oferta in enumerate(evaluated):
        por_clase = Counter()
        totales = Counter()
        for result in am.Result.objects.filter(offer=oferta):
            if result.outcome == "cumple":
                por_clase[clase[result.requirement_id]] += 1
        for fila in mosaico.chart.rows:
            celda = fila.cells[j]
            assert celda is not None
        # Lo que cumple, por clase, coincide con los resultados guardados.
        etiquetas = {"Formales": "formal", "Económicos": "economico", "Técnicos": "tecnico"}
        vistos = {etiquetas[f.label]: f.cells[j].value for f in mosaico.chart.rows}
        for categoria, valor in vistos.items():
            assert valor == por_clase[categoria], (oferta.number, categoria)
        for f in mosaico.chart.rows:
            totales[etiquetas[f.label]] = f.cells[j].total
        assert sum(totales.values()) == len(clase)
        assert sum(vistos.values()) == donas(tableros()["resultado"])[
            f"Of. {oferta.number}"].ok


def test_la_celda_sin_requisitos_de_esa_clase_queda_vacia(procedure, matrix, three,
                                                         operator_user, tableros):
    """REQ-141: no hay un «0/0»: la clase sin requisitos no tiene fila."""
    declaracion = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, three[0], {declaracion: "cumple"})
    fila_labels = [f.label for f in tableros()["tipo"].chart.rows]
    assert len(fila_labels) == len(set(fila_labels))
    assert all(label in ("Formales", "Económicos", "Técnicos") for label in fila_labels)


# --- La página ------------------------------------------------------------------------------------


def test_la_pagina_abre_con_el_tablero_y_el_detalle_conserva_el_fundamento(
        client, evaluated, procedure, operator_user):
    """REQ-126, REQ-141 (P3): los cuatro mosaicos abren `d-s4-propuesta`, que sigue trayendo la
    tabla con el fundamento y la cita de cada propuesta."""
    html = pagina(client, operator_user, procedure)
    p = revisar(html)
    mios = [t for t in p.tiles if t.get("data-detail") == DETALLE]
    assert [t["id"] for t in mios] == [f"m-{k}" for k in CLAVES]
    assert "Lo dice el texto." in p.text_of(DETALLE)
    assert "Declaro ba" in p.text_of(DETALLE) and "página 1" in p.text_of(DETALLE)
    assert "Explicación del sistema (no es texto de la oferta ni del pliego)" in p.text_of(DETALLE)
    assert "s4-propuesta" in p.details[DETALLE]["ids"]


def test_la_pagina_muestra_las_cifras_de_las_celdas(client, evaluated, procedure,
                                                    operator_user):
    """REQ-126: lo que ve la persona en los mosaicos es lo que dicen las celdas."""
    html = pagina(client, operator_user, procedure)
    partes = {p.split('id="m-')[1].split('"')[0]: p.split("</a>")[0]
              for p in html.split('<a class="tile')[1:] if 'id="m-' in p}
    assert 'class="big">2<small>' in partes["nocumple"]
    assert 'class="big">1<small>' in partes["nodeterminado"]
    assert 'class="big">3<small>de 3 ofertas evaluadas</small>' in partes["resultado"]
    assert "Of. 1" in partes["resultado"] and "<svg" in partes["resultado"]
    assert "<svg" in partes["tipo"]


def test_los_mosaicos_no_usan_estilos_en_linea_ni_graficos_de_estado_en_tono_negro(
        client, evaluated, procedure, operator_user, tableros):
    """Guía visual: sin `style=` ni scripts en línea y ningún mosaico negro con gráficos de
    estado (`g-ok`, `g-no`, `g-nd`, `g-pe`)."""
    html = pagina(client, operator_user, procedure)
    tablero = html.split('class="tablero"')[1].split('class="detalles"')[0]
    assert "style=" not in tablero and "<script" not in tablero
    assert all(t.tone != "dark" for t in tableros().values())


def test_opens_abre_el_detalle_con_los_filtros_de_la_propuesta(rf, operator_user, client,
                                                               evaluated, procedure):
    """REQ-127: `?ver=` y `?tipo=` abren el detalle de la propuesta; sin ellos no abre nada."""
    assert tema().opens(pedido(rf, operator_user)) is None
    assert tema().opens(pedido(rf, operator_user, "?ver=abiertas")) == DETALLE
    assert tema().opens(pedido(rf, operator_user, "?tipo=formal")) == DETALLE
    html = pagina(client, operator_user, procedure, "?ver=nocumple")
    assert Pagina(html).root["data-abre"] == DETALLE


def test_los_filtros_no_cambian_las_cifras(client, evaluated, procedure, operator_user):
    """P3: filtrar la tabla no cambia las cifras del tablero."""
    def cifras(html):
        return [p.split("</a>")[0] for p in html.split('<a class="tile')[1:]
                if 'data-detail="d-s4-propuesta"' in p]
    sin = cifras(pagina(client, operator_user, procedure))
    con = cifras(pagina(client, operator_user, procedure, "?ver=nocumple&tipo=formal"))
    assert sin == con


def test_el_orden_de_la_seccion_arranca_con_los_mosaicos_de_la_propuesta(
        evaluated, procedure, operator_user, rf):
    """Plan 017: la sección 4 abre con el resultado, sin esperar a los demás temas."""
    section = sections.sections_for(operator_user, procedure).get("evaluacion")
    assert [t.KEY for t in section.temas][0] == "s4_propuesta"
    request = pedido(rf, operator_user)
    contexts = {t.KEY: t.context(operator_user, procedure, request) for t in section.temas}
    claves = [t.key for t in section.tiles(operator_user, procedure, contexts)]
    assert claves[:4] == CLAVES


def test_el_contexto_pesado_se_calcula_una_vez(evaluated, procedure, operator_user, rf,
                                              monkeypatch):
    """Plan 017: `tiles()` reusa el contexto de `context()`; no vuelve a armar la matriz."""
    request = pedido(rf, operator_user)
    ctx = tema().context(operator_user, procedure, request)

    def prohibido(*args, **kwargs):
        raise AssertionError("tiles() volvió a calcular la matriz")

    monkeypatch.setattr(memo, "matrix_page", prohibido)
    assert [t.key for t in tema().tiles(operator_user, procedure, ctx)] == CLAVES


def test_la_seccion_se_arma_en_dos_segundos_con_el_caso_chico(client, evaluated, procedure,
                                                              operator_user):
    """T-327: sección en 2 s o menos con el caso chico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:evaluacion", args=[procedure.pk])
    client.get(url)  # calienta las plantillas
    inicio = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - inicio < 2.0


# --- Los pendientes dicen por qué importan ----------------------------------------------------------


def test_los_pendientes_de_la_propuesta_dicen_por_que_importan(evaluated, procedure,
                                                               operator_user):
    """REQ-129 (T-318 agrega `Item.why`): cada par por decidir y cada pregunta abierta trae el
    texto que escribe el tema. Mientras `Item` no tiene el campo, no hay dónde escribirlo."""
    if "why" not in {f.name for f in dataclasses.fields(Item)}:
        pytest.skip("`Item.why` llega con T-318; este tema lo escribe cuando exista.")
    estado = tema().status(operator_user, procedure)
    assert estado.pending_items
    for item in estado.pending_items:
        assert item.why.strip(), item.text
