"""«Qué se puede hacer ahora» en la portada (REQ-147, REQ-156, REQ-157; plan 018, «Orden de las
líneas y cuántas se ven»; T-348): 6 líneas a la vista y «ver las N restantes», el orden, el botón de
cada línea y las etiquetas con texto. Material inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.template.loader import render_to_string

from evaluon.journey.proceso import acciones, calculo, pasos
from evaluon.journey.views.portada import _Linea
from tests.journey.proceso.test_portada import entrar, html_de, url_de

pytestmark = pytest.mark.django_db


def accion(paso, kind, texto, tipo=pasos.PENDIENTE, marca="", url="/x/", post=None):
    return pasos.Accion(paso, tipo, kind, texto, 0, "Ver", url, post, marca)


def dibujar(visibles, restantes=(), actuar=True):
    nombres = {d.numero: d.nombre for d in pasos.PASOS}
    return render_to_string("journey/_acciones.html", {
        "visibles": [_Linea(a, nombres[a.paso]) for a in visibles],
        "restantes": [_Linea(a, nombres[a.paso]) for a in restantes],
        "puede_actuar": actuar, "next_url": "/expedientes/1/"})


def test_req147_mas_de_6_lineas_muestran_6_y_ver_las_n_restantes():
    """REQ-147: con 9 líneas se ven 6 con pieza propia y las otras 3 quedan dentro de un
    `<details>` «ver las 3 restantes», en el mismo orden y sin `data-pieza`."""
    todas = [accion(3, f"k{i}", f"Línea {i}") for i in range(9)]
    visibles, restantes = acciones.cortar(todas)
    html = dibujar(visibles, restantes)
    assert html.count('data-pieza="accion"') == 6
    assert "<details" in html and "ver las 3 restantes" in html
    dentro = html[html.index("<details"):]
    assert re.findall(r"<span>(Línea \d)</span>", dentro) == ["Línea 6", "Línea 7", "Línea 8"]
    assert "data-pieza" not in dentro


def test_req147_con_6_lineas_o_menos_no_hay_ver_las_restantes():
    """REQ-147: hasta 6 líneas no hay `<details>`."""
    html = dibujar([accion(3, f"k{i}", f"Línea {i}") for i in range(6)])
    assert "<details" not in html and "restantes" not in html


def test_req147_sin_acciones_lo_dice():
    """REQ-147: sin nada para hacer, la sección lo dice (no queda vacía)."""
    assert "No hay nada para hacer ahora." in dibujar([])


def test_req147_cada_linea_dice_su_paso_y_trae_su_identificador():
    """REQ-147: cada línea nombra su paso y trae el `data-accion` estable de la `Accion`."""
    a = accion(6, "decidir", "Decidir 12 puntos no determinados")
    html = dibujar([a])
    assert f'data-accion="{a.id}"' in html
    assert "Paso 6 · Evaluación Comisión" in html


def test_req147_la_accion_de_un_clic_es_un_formulario_post_con_csrf_y_next():
    """REQ-147: «Aprobar el dictamen» es un POST de un clic que vuelve a la portada."""
    a = accion(7, "dictamen", "Aprobar el dictamen publicado en el Portal",
               post=("/expedientes/1/dictamen/aprobar/", (("item", "5"),)))
    html = dibujar([a])
    assert 'method="post" action="/expedientes/1/dictamen/aprobar/"' in html
    assert 'name="item" value="5"' in html and 'name="next" value="/expedientes/1/"' in html


def test_req147_el_usuario_de_lectura_no_ve_botones_pero_si_las_lineas():
    """REQ-147: sin `puede_actuar` no se dibuja ningún botón ni formulario; la línea sigue."""
    a = accion(7, "dictamen", "Aprobar el dictamen", post=("/p/", ()))
    html = dibujar([a, accion(3, "k", "Subir los archivos de una oferta")], actuar=False)
    assert "<form" not in html and "<a " not in html and "<button" not in html
    assert "Aprobar el dictamen" in html and 'data-pieza="accion"' in html


def test_req157_las_etiquetas_llevan_siempre_el_texto():
    """REQ-156, REQ-157: «Vence hoy» (lila) y «Vencido» (rojo) se dibujan con su texto, en la línea."""
    html = dibujar([accion(7, "dictamen", "Cargar el dictamen", marca="hoy"),
                    accion(3, "acta", "Agregar las ofertas del acta", marca="vencido")])
    assert '<li class="pr-accion hoy"' in html and '<span class="pr-hoy">Vence hoy</span>' in html
    assert '<li class="pr-accion vencido"' in html and '<span class="pr-vencido">Vencido</span>' in html


def test_req156_las_plantillas_escriben_el_texto_de_cada_marca():
    """REQ-156: la hoja no puede obligar a que la etiqueta diga «Vence hoy» o «Vencido»: acá se
    comprueba que cada uso de `pr-hoy` / `pr-vencido` en las plantillas trae su texto."""
    carpeta = Path(__file__).resolve().parents[3] / "evaluon" / "templates" / "journey"
    for nombre in ("portada", "_acciones", "_foto_pasos"):
        fuente = (carpeta / f"{nombre}.html").read_text(encoding="utf-8")
        usos_hoy = re.findall(r'class="pr-hoy">([^<]*)<', fuente)
        usos_vencido = re.findall(r'class="pr-vencido">([^<]*)<', fuente)
        assert all(t == "Vence hoy" for t in usos_hoy), nombre
        assert all(t == "Vencido" for t in usos_vencido), nombre
        todos = len(re.findall(r'class="pr-(?:hoy|vencido)"', fuente))
        assert todos == len(usos_hoy) + len(usos_vencido), nombre


def test_req147_el_orden_de_la_portada_es_el_de_acciones_ordenar(client, caso_varios_en_curso):
    """REQ-147: las líneas de la portada salen en el orden de `proceso.acciones` (vencido, hoy,
    pendientes, cierres, faltantes) y las 6 primeras son las visibles."""
    caso = caso_varios_en_curso
    html = html_de(client, caso)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    bloque = html[html.index('id="ahora-titulo"'):html.index('id="pasos-titulo"')]
    ids = re.findall(r'data-accion="([^"]+)"', bloque)
    assert ids == [a.id for a in proceso.acciones]
    assert bloque.count('data-pieza="accion"') == min(6, len(proceso.acciones))


def test_req147_el_operador_ve_el_boton_de_cada_linea(client, caso_varios_en_curso):
    """REQ-147: el evaluador ve un botón o enlace por cada línea que tiene destino."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = client.get(url_de(caso)).content.decode()
    bloque = html[html.index('id="ahora-titulo"'):html.index('id="pasos-titulo"')]
    lineas = bloque.count('<li class="pr-accion')
    assert lineas >= 1
    assert bloque.count('class="btn primario chico"') == lineas
