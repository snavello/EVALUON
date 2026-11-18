"""Cada paso y cada acción de la portada llevan al lugar donde se resuelven (REQ-149, REQ-154;
T-353): la página responde 200 Y el ancla o la celda de destino existe en el HTML. Y de la portada
al panel de una celda a decidir, con pliego y oferta lado a lado, hay un solo clic. Material
inventado (P4)."""

import html as htmllib
import re
from urllib.parse import urlsplit

import pytest
from django.urls import reverse

from evaluon.journey.proceso import calculo, pasos
from evaluon.portal import models as pm
from tests.journey.proceso.test_portada import FIXTURE, entrar, html_de
from tests.journey.temas.test_s4_dictamen import portal_dictamen

pytestmark = pytest.mark.django_db

# El criterio numérico de la spec (REQ-154): de la portada a pliego y oferta lado a lado.
CLICS_MAXIMOS = 2


def abrir(client, url):
    """GET de `url` (sin su ancla) que debe responder 200 sin redirigir; devuelve `(html, ancla)`."""
    partes = urlsplit(url)
    camino = partes.path + (f"?{partes.query}" if partes.query else "")
    respuesta = client.get(camino)
    assert respuesta.status_code == 200, url
    return respuesta.content.decode(), partes.fragment


def comprobar_destino(client, url, marca_de_pagina="seccion-titulo"):
    """200 y el ancla existe como `id`; sin ancla, la página trae su marca (`id` del título)."""
    cuerpo, ancla = abrir(client, url)
    buscado = ancla or marca_de_pagina
    assert re.search(rf'\bid="{re.escape(buscado)}"', cuerpo), f"falta el ancla #{buscado} en {url}"
    return cuerpo


def accion_de(proceso, id_):
    return next(a for a in proceso.acciones if a.id == id_)


# --- Los siete pasos y todas las acciones, en los tres casos ---------------------------------------


@pytest.mark.parametrize("nombre", sorted(FIXTURE))
def test_req149_cada_paso_y_cada_accion_responde_200_y_su_ancla_existe(nombre, client, request):
    """REQ-149: en los tres casos, el destino de cada uno de los siete pasos y la URL de cada acción
    (salvo las de un solo clic, que son un POST) responden 200 y traen el ancla o la celda."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    assert [p.numero for p in proceso.pasos] == [1, 2, 3, 4, 5, 6, 7]
    for paso in proceso.pasos:
        assert paso.destino, paso.numero
        comprobar_destino(client, paso.destino)
    for accion in proceso.acciones:
        if accion.post is not None:
            continue
        assert accion.url, f"{accion.id} no tiene destino"
        comprobar_destino(client, accion.url)


def test_req149_los_pasos_llevan_a_donde_se_resuelven(caso_varios_en_curso):
    """REQ-149: los destinos de los siete pasos, uno por uno: el 4 y el 6 al cuadro (REQ-154), el
    1 al pliego en Procedimiento, el 2 a la matriz, el 3 a las ofertas, el 5 a Indicadores y el 7
    al dictamen; ninguno es la portada ni un paso intermedio."""
    caso = caso_varios_en_curso
    p = caso.procedure.pk
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    esperado = {
        1: f"/expedientes/{p}/procedimiento/#s1-pliego",
        2: f"/expedientes/{p}/pliego/#s2-matriz",
        3: f"/expedientes/{p}/ofertas/#s3-ofertas",
        4: f"/expedientes/{p}/cuadro/",
        5: f"/expedientes/{p}/procedimiento/#indicadores-titulo",
        6: f"/expedientes/{p}/cuadro/",
        7: f"/expedientes/{p}/evaluacion/#s4-dictamen",
    }
    assert {x.numero: x.destino for x in proceso.pasos} == esperado
    assert pasos.destino_por_omision(4, caso.procedure) == reverse("expedientes:cuadro", args=[p])


def test_req149_cargar_el_informe_tecnico_llega_al_lugar_donde_se_sube(client, caso_varios_en_curso):
    """REQ-149: «Cargar el informe técnico del área» lleva a `evaluacion/#s4-informe` y ahí está el
    bloque donde se sube, sin pasos intermedios."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    accion = accion_de(calculo.proceso_de(caso.user, caso.procedure), "4-pendiente-informe_falta")
    assert accion.texto.startswith("Cargar el informe técnico del área")
    assert accion.url == f"/expedientes/{caso.procedure.pk}/evaluacion/#s4-informe"
    cuerpo = comprobar_destino(client, accion.url)
    assert 'id="s4-informe-subir"' in cuerpo  # el formulario de subida, en esa misma página


def test_req149_tomar_del_portal_los_datos_lleva_al_procedimiento_que_se_mira(
        client, caso_recien_cargado):
    """REQ-149: «Tomar del Portal lo que falta de los datos» ya no lleva al alta de un procedimiento
    nuevo (`/expedientes/nuevo/`) sino al bloque del Portal de ESTE procedimiento."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    datos = [a for a in proceso.acciones if a.kind == "datos"]
    assert datos, "el caso recién cargado debía traer el faltante de datos"
    for accion in datos:
        assert accion.url == f"/expedientes/{caso.procedure.pk}/procedimiento/#s1-portal"
        assert "/nuevo/" not in accion.url
        comprobar_destino(client, accion.url)


def test_req147_el_dictamen_del_portal_fallido_tiene_su_accion(client, caso_varios_en_curso):
    """REQ-147, REQ-149: el paso 7 «Con error» por un dictamen del Portal que falló ofrece
    «Resolver el error», con el motivo, y lleva al bloque del dictamen."""
    caso = caso_varios_en_curso
    item = portal_dictamen(caso.procedure, caso.user, pm.ItemState.FALLIDO)
    pm.PortalItem.objects.filter(pk=item.pk).update(failure="archivo dañado")
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    siete = proceso.pasos[6]
    assert siete.estado is pasos.Estado.CON_ERROR
    accion = accion_de(proceso, "7-cierre-error_dictamen")
    assert accion in siete.tareas and accion.texto.startswith("Resolver el error: «")
    assert accion.url == f"/expedientes/{caso.procedure.pk}/evaluacion/#s4-dictamen"
    comprobar_destino(client, accion.url)
    # Con el dictamen aprobado el error desaparece: no queda una acción de más.
    pm.PortalItem.objects.filter(pk=item.pk).update(state=pm.ItemState.APROBADO)
    assert not any(a.id == "7-cierre-error_dictamen"
                   for a in calculo.proceso_de(caso.user, caso.procedure).acciones)


# --- Las tres líneas del paso 6 y los dos clics ----------------------------------------------------


def primera_celda_del_cuadro(client, caso, texto):
    """`(oferta, requisito)` de la primera celda con ese texto, en el orden en que el cuadro
    dibuja sus filas, leída del HTML del cuadro sin celda elegida (no del código bajo prueba)."""
    cuerpo, _ = abrir(client, reverse("expedientes:cuadro", args=[caso.procedure.pk]))
    for fila in re.findall(r"<tr\b.*?</tr>", cuerpo, re.S):
        for oferta, req, inner in re.findall(
                r'id="c-(\d+)-(\d+)"[^>]*>(.*?)</(?:a|span)>\s*</td>', fila, re.S):
            visible = " ".join(re.sub(r"<[^>]+>", " ", re.sub(
                r'<span class="cu-sr">.*?</span>', "", inner, flags=re.S)).split())
            if visible.startswith(texto):
                return int(oferta), int(req)
    raise AssertionError(f"no hay celda «{texto}» en el cuadro")


def test_req154_decidir_lleva_en_un_clic_al_panel_de_la_primera_celda_a_decidir(
        client, caso_varios_en_curso):
    """REQ-154, criterio de 2 clics o menos: en la portada, «Decidir N puntos no determinados» es
    un enlace al cuadro con `filtro=a-decidir` y la PRIMERA celda «A decidir» (en el orden del
    cuadro) abierta. Un clic y ya están el texto del pliego y el de la oferta lado a lado."""
    caso = caso_varios_en_curso
    portada = html_de(client, caso)  # la portada, clic cero
    accion = accion_de(calculo.proceso_de(caso.user, caso.procedure), "6-pendiente-decidir")
    # De los 12 no determinados del caso, 6 son filas técnicas (esperan el informe): quedan 6.
    assert accion.texto == "Decidir 6 puntos no determinados"
    oferta, req = primera_celda_del_cuadro(client, caso, "A decidir")
    assert accion.url == (f"/expedientes/{caso.procedure.pk}/cuadro/"
                          f"?filtro=a-decidir&celda={oferta}-{req}#c-{oferta}-{req}")
    # El enlace está en la portada (la acción y, dentro del mapa, la tarea del paso 6).
    assert f'href="{htmllib.escape(accion.url)}"' in portada
    clics = 1  # el único: el clic en ese enlace
    cuerpo = comprobar_destino(client, accion.url)
    assert clics <= CLICS_MAXIMOS
    panel = cuerpo[cuerpo.index('id="cu-panel"'):]
    assert "Lo que exige el pliego" in panel and "Lo que presentó la oferta" in panel
    assert re.search(r'class="punto-donde">[^<]+', panel)  # la ubicación en el pliego
    assert re.search(rf'id="c-{oferta}-{req}"[^>]*aria-current="true"', cuerpo)


def test_req154_las_tres_lineas_del_paso_6_llevan_al_cuadro_con_su_filtro_y_su_celda(
        client, caso_varios_en_curso):
    """REQ-154: «Decidir», «Revisar “no cumple”» y «Confirmar “cumple”» llevan al cuadro, cada una
    con su filtro y la primera celda de su grupo abierta (200 y la celda existe en el HTML)."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    filtros = {"6-pendiente-decidir": ("a-decidir", "A decidir"),
               "6-pendiente-no_cumple": ("no-cumple", "No cumple"),
               "6-pendiente-cumple": ("pendiente", "Cumple")}
    for id_, (filtro, texto) in filtros.items():
        accion = accion_de(proceso, id_)
        partes = urlsplit(accion.url)
        assert partes.path == reverse("expedientes:cuadro", args=[caso.procedure.pk])
        assert f"filtro={filtro}" in partes.query and "celda=" in partes.query
        cuerpo = comprobar_destino(client, accion.url)
        celda = re.search(r"celda=(\d+)-(\d+)", partes.query)
        assert partes.fragment == f"c-{celda.group(1)}-{celda.group(2)}"
        assert 'id="cu-panel"' in cuerpo  # el panel de la celda abierta
        # La celda elegida es una de ese grupo.
        visto = re.search(rf'id="{partes.fragment}"[^>]*>(.*?)</(?:a|span)>\s*</td>', cuerpo, re.S)
        assert texto in " ".join(re.sub(r"<[^>]+>", " ", visto.group(1)).split()), id_


def test_req154_el_paso_6_y_el_4_enlazan_al_cuadro_desde_la_portada(client, caso_varios_en_curso):
    """REQ-154: en la portada, el nombre de los pasos 4 y 6 es un enlace al cuadro."""
    caso = caso_varios_en_curso
    portada = html_de(client, caso)
    cuadro = reverse("expedientes:cuadro", args=[caso.procedure.pk])
    for numero in (4, 6):
        assert re.search(rf'<h3 id="paso-{numero}"><a href="{cuadro}">', portada), numero
