"""Evi, el botón y el panel con el circuito (feature 020, REQ-163 a REQ-170; T-367).

Se prueban las pantallas con los tres procedimientos inventados de la 018 (`caso_recien_cargado`,
`caso_varios_en_curso`, `caso_todo_hecho`; P4). El contenido del panel se pide aparte
(`expedientes/<id>/evi/`), así que cada prueba pide primero la página, lee del botón desde dónde se pide
el panel y qué pasos resuelve esa pantalla, y recién entonces pide el contenido: es el mismo camino que
sigue el navegador."""

import html as html_lib
import re
from pathlib import Path

import pytest
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from evaluon.assessment import models as am
from evaluon.journey import context as journey_context
from evaluon.journey.evi import pantallas, textos
from evaluon.journey.proceso import calculo, mapa, pasos
from tests.journey.proceso.conftest import (  # noqa: F401  (fixtures)
    caso_recien_cargado,
    caso_todo_hecho,
    caso_varios_en_curso,
)
from tests.journey.proceso.test_portada import entrar
from tests.journey.proceso.test_sin_esquema import ULTIMAS

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2] / "evaluon"
CASOS = ("caso_recien_cargado", "caso_varios_en_curso", "caso_todo_hecho")

# Pantalla -> pasos que resuelve (REQ-165). La tabla del informe de T-367.
PANTALLAS = [("portada", (1, 5)), ("procedimiento", (1, 5)), ("pliego", (2,)), ("ofertas", (3,)),
             ("cuadro", (4, 6)), ("evaluacion", (7,)), ("normativas", ()), ("s4_par", (4, 6))]


def _texto(html):
    """El texto visible: sin etiquetas, con las entidades resueltas y los espacios juntos."""
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _url_de(nombre, caso):
    pk = caso.procedure.pk
    if nombre == "s4_par":
        oferta = caso.offers[0]
        resultado = am.Result.objects.filter(offer=oferta).order_by("pk").first()
        return reverse("expedientes:s4_par", args=[pk, oferta.pk, resultado.requirement_id])
    return reverse(f"expedientes:{nombre}", args=[pk])


def _boton(html):
    """`(data-url, data-pasos)` del botón de Evi de una página."""
    m = re.search(r'<button type="button" class="evi-boton"[^>]*data-url="([^"]*)" data-pasos="([^"]*)"', html)
    assert m, "la página no tiene el botón de Evi"
    return m.group(1), m.group(2)


def _panel_de(client, url_pagina):
    """El contenido del panel, pedido como lo pide el navegador desde esa página."""
    pagina = client.get(url_pagina)
    assert pagina.status_code == 200, url_pagina
    url, pasos_ = _boton(pagina.content.decode())
    respuesta = client.get(url, {"pasos": pasos_} if pasos_ else {})
    assert respuesta.status_code == 200, url
    return respuesta.content.decode()


def _nodos(panel):
    """`{n: {"estado", "aqui", "etiqueta", "nombre"}}` de los siete nodos del gráfico."""
    salida = {}
    for m in re.finditer(r'<button type="button" class="evi-nodo ([^"]*)" data-n="(\d)" aria-label="([^"]*)">(.*?)</button>',
                         panel, re.S):
        clases, n, etiqueta, cuerpo = m.groups()
        estado = re.search(r"\bs-(\w+)", clases)
        salida[int(n)] = {"estado": estado.group(1) if estado else "", "aqui": 'class="aqui">' in cuerpo,
                          "etiqueta": etiqueta, "nombre": re.search(r'class="nombre">([^<]*)<', cuerpo).group(1)}
    return salida


def _sin_preguntas(panel):
    """El panel sin el bloque «Pregúntele a Evi» (T-368): lo fijo de la T-367 se comprueba sin él, que tiene su
    propio título, su aviso y sus pruebas (`test_evi_preguntas.py`)."""
    return re.sub(r'<section class="evi-preg".*?</section>', "", panel, flags=re.S)


def _seccion_de_paso(panel, n):
    inicio = panel.index(f'<div class="evi-paso" data-n="{n}"')
    fin = panel.find('<div class="evi-paso" data-n=', inicio + 10)
    return panel[inicio:fin if fin != -1 else len(panel)]


# --- REQ-163 · el botón ---------------------------------------------------------------------------


def test_req163_el_boton_esta_en_las_pantallas_con_sesion(client, caso_varios_en_curso):
    """REQ-163: el inicio, la lista, la portada, el cuadro, las secciones, el alta y las normativas generales
    tienen el botón, con el nombre accesible «Evi», chico y con el logo."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    urls = ["/", reverse("expedientes:index"), reverse("expedientes:nuevo"),
            reverse("expedientes:normativas_general")]
    urls += [_url_de(nombre, caso) for nombre, _ in PANTALLAS]
    for url in urls:
        respuesta = client.get(url)
        assert respuesta.status_code == 200, url
        html = respuesta.content.decode()
        assert html.count('class="evi-boton"') == 1, url
        assert 'id="evi-boton" aria-label="Evi"' in html, url
        assert re.search(r'<svg class="evi-logo" width="44" height="44"', html), url
        assert 'aria-controls="evi-panel"' in html and 'id="evi-panel"' in html, url


def test_req163_sin_sesion_no_hay_boton(client):
    """REQ-163: la pantalla de ingreso no lleva el botón ni su contenido."""
    respuesta = client.get(reverse("accounts:login"))
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "evi-boton" not in html and "evi-panel" not in html and "evi.js" not in html


def test_req163_el_panel_pedido_sin_sesion_pide_ingresar(client, caso_recien_cargado):
    """REQ-163/169: el contenido del panel no se sirve sin sesión."""
    for url in (reverse("expedientes:evi"),
                reverse("expedientes:evi_procedimiento", args=[caso_recien_cargado.procedure.pk])):
        respuesta = client.get(url)
        assert respuesta.status_code == 302 and "ingresar" in respuesta["Location"]


def test_req163_la_galera_saluda_una_vez_y_no_hay_bucle():
    """REQ-163: el saludo se dispara al cargar, al pasar y al enfocar, una sola vez cada uno; con menos
    movimiento no hay animación. Nada en bucle (ni `infinite` ni `setInterval`)."""
    css = (RAIZ / "static" / "journey" / "evi.css").read_text(encoding="utf-8")
    js = (RAIZ / "static" / "journey" / "evi.js").read_text(encoding="utf-8")
    assert ".evi-boton:hover .sombrero" in css and ".evi-boton:focus-visible .sombrero" in css
    assert ".evi-boton.saluda .sombrero" in css and "evi-saludo 1s var(--e-io) 1;" in css
    assert "infinite" not in css and "setInterval" not in js
    assert "prefers-reduced-motion: reduce" in css and "animation: none !important" in css
    assert "reducido()" in js and "saludar" in js


# --- REQ-164 · el gráfico -------------------------------------------------------------------------


@pytest.mark.parametrize("caso_nombre", CASOS)
def test_req164_siete_pasos_y_ocho_conectores_con_los_nombres_de_pasos_py(
        caso_nombre, client, request):
    """REQ-164: el panel dibuja los siete pasos con los nombres de `pasos.py` y los ocho conectores de
    `mapa.CONECTORES`."""
    caso = request.getfixturevalue(caso_nombre)
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    nodos = _nodos(panel)
    assert sorted(nodos) == list(range(1, 8))
    assert [nodos[p.numero]["nombre"] for p in pasos.PASOS] == [p.nombre for p in pasos.PASOS]
    assert re.findall(r'<g data-a="(\d-\d)"', panel) == [f"{o}-{d}" for o, d in mapa.CONECTORES]
    assert len(mapa.CONECTORES) == 8


@pytest.mark.parametrize("caso_nombre", CASOS)
def test_req164_los_estados_son_los_de_proceso_de_y_los_de_la_portada(caso_nombre, client, request):
    """REQ-164: con un procedimiento abierto, cada paso trae el estado de `calculo.proceso_de`, igual que
    la portada (mismo texto, mismo orden)."""
    caso = request.getfixturevalue(caso_nombre)
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    panel = _panel_de(client, _url_de("portada", caso))
    nodos = _nodos(panel)
    for paso in proceso.pasos:
        assert nodos[paso.numero]["estado"] == paso.estado.value
        assert f"{paso.estado.texto}." in nodos[paso.numero]["etiqueta"]
        seccion = _seccion_de_paso(panel, paso.numero)
        assert f'class="pill {paso.estado.value}">{paso.estado.texto}<' in seccion
    portada = client.get(_url_de("portada", caso)).content.decode()
    en_portada = re.findall(r'class="pr-estado [^"]*">([^<]+)<', portada)
    assert en_portada[:7] == [p.estado.texto for p in proceso.pasos]


def test_req164_los_estados_distintos_de_los_tres_casos(client, caso_varios_en_curso):
    """REQ-164: el caso con varios pasos en curso muestra hechos, en curso y todavía no a la vez."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    estados = {n["estado"] for n in _nodos(_panel_de(client, _url_de("portada", caso))).values()}
    assert estados == {"hecho", "en_curso", "todavia_no"}


def test_req164_el_gafico_entra_en_360_px_sin_desplazamiento_horizontal():
    """REQ-164: el CSS pasa a la grilla de 4 × 2 con nodos chicos hasta 760 px, la grilla no se pasa de su
    caja (`minmax(0, 1fr)`) y el panel ocupa el ancho de la pantalla con 8 px de margen. La medición real,
    en Chrome sin cabeza a 360, 1280 y 1440 px, está en el informe de la tarea."""
    css = (RAIZ / "static" / "journey" / "evi.css").read_text(encoding="utf-8")
    angosto = css[css.index("@media (max-width: 760px)"):]
    assert "repeat(4, minmax(0, 1fr))" in css
    assert ".evi-panel { left: 8px; right: 8px; width: auto;" in angosto
    assert ".evi-nodo .corto { display: block;" in angosto and ".evi-nodo .nombre" in angosto


def test_req164_sin_procedimiento_el_circuito_es_general_sin_estados(client, caso_varios_en_curso):
    """REQ-164/165: en el inicio el circuito va sin estados, sin marca y sin «Qué hacer acá»."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    for url in ("/", reverse("expedientes:index"), reverse("expedientes:normativas_general"),
                reverse("expedientes:nuevo")):
        panel = _panel_de(client, url)
        nodos = _nodos(panel)
        assert sorted(nodos) == list(range(1, 8)), url
        assert all(n["estado"] == "" and not n["aqui"] for n in nodos.values()), url
        assert "Usted está aquí" not in panel and "Qué hacer acá" not in panel, url
        assert 'data-estados="0"' in panel and 'data-aqui=""' in panel, url


# --- REQ-165 · «Usted está aquí» ------------------------------------------------------------------


@pytest.mark.parametrize("nombre,esperados", PANTALLAS)
def test_req165_usted_esta_aqui_marca_los_pasos_de_la_pantalla(
        nombre, esperados, client, caso_varios_en_curso):
    """REQ-165: en cada pantalla de un procedimiento, el panel marca exactamente el o los pasos que ella
    resuelve (todos, si son más de uno); las demás no llevan marca."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de(nombre, caso))
    marcados = tuple(n for n, nodo in sorted(_nodos(panel).items()) if nodo["aqui"])
    assert marcados == esperados
    assert panel.count('class="aqui-chip">Usted está aquí<') == len(esperados)
    assert all("Usted está aquí." in _nodos(panel)[n]["etiqueta"] for n in esperados)
    assert [n["estado"] != "" for n in _nodos(panel).values()] == [True] * 7  # estados aun sin marca


def test_req165_la_tabla_sale_de_destinos_de_pasos_py():
    """REQ-165: una pantalla que cambia de lugar en `pasos.DESTINOS` cambia también en Evi."""
    for numero, (ruta, _) in pasos.DESTINOS.items():
        assert numero in pantallas.PANTALLAS[ruta], (numero, ruta)
    assert pantallas.PANTALLAS["cuadro"] == (4, 6) and pantallas.PANTALLAS["procedimiento"] == (1, 5)


def test_req165_el_inicio_no_lleva_marca_ni_estados(client, caso_varios_en_curso):
    """REQ-165: en el inicio el botón no declara pasos y el panel no dice «Usted está aquí»."""
    entrar(client, caso_varios_en_curso.user)
    pagina = client.get("/").content.decode()
    url, pasos_ = _boton(pagina)
    assert pasos_ == "" and url == reverse("expedientes:evi")
    assert "Usted está aquí" not in client.get(url).content.decode()


def test_req165_los_pasos_pedidos_se_leen_con_cuidado():
    """REQ-165: `?pasos=` sólo acepta enteros de 1 a 7, sin repetir."""
    assert pantallas.pasos_pedidos("5,1") == (1, 5)
    assert pantallas.pasos_pedidos("1,1,9,0,x,-3, 7") == (1, 7)
    assert pantallas.pasos_pedidos("") == () and pantallas.pasos_pedidos(None) == ()


def test_req165_cada_ruta_de_expedientes_con_procedimiento_esta_en_la_tabla_o_es_una_accion():
    """REQ-165: toda ruta de `expedientes:` que sólo lleva el procedimiento y se dibuja como pantalla está
    declarada en la tabla. Las demás son acciones de un tema (`s1_` a `s5_`: POST, que redirigen), fragmentos
    que pide el navegador o el propio panel de Evi."""
    from django.urls import get_resolver
    sin_pantalla = {"barra", "fila", "ventana", "avance", "evi_procedimiento"}
    resolver = get_resolver().namespace_dict["expedientes"][1]
    pantallas_de_procedimiento = set()
    for patron in resolver.url_patterns:
        nombre = getattr(patron, "name", None)
        if not nombre or nombre in sin_pantalla or re.match(r"s\d_", nombre) and nombre != "s4_par":
            continue
        if str(patron.pattern).startswith("<int:procedure_id>/") and str(patron.pattern).count("<") == 1:
            pantallas_de_procedimiento.add(nombre)
    assert pantallas_de_procedimiento == {"portada", "cuadro", "procedimiento", "pliego", "ofertas", "evaluacion",
                                          "normativas"}
    assert pantallas_de_procedimiento <= set(pantallas.PANTALLAS) and "s4_par" in pantallas.PANTALLAS


def test_req165_el_boton_no_suma_consultas_a_la_pagina(caso_varios_en_curso, rf):
    """REQ-163/Rendimiento: el botón sólo mira el nombre de la ruta; no consulta la base."""
    for nombre in ("portada", "cuadro", "ofertas"):
        url = reverse(f"expedientes:{nombre}", args=[caso_varios_en_curso.procedure.pk])
        with CaptureQueriesContext(connection) as consultas:
            datos = journey_context._evi(resolve(url))
        assert len(consultas) == 0
        assert datos["url"] == reverse("expedientes:evi_procedimiento",
                                       args=[caso_varios_en_curso.procedure.pk])
    assert journey_context._evi(None) == {"url": reverse("expedientes:evi"), "pasos": ""}


# --- REQ-166 · el recorrido ---------------------------------------------------------------------


def test_req166_el_panel_trae_los_controles_y_el_script_el_teclado(client, caso_recien_cargado):
    """REQ-166: Anterior, Siguiente, Ver el circuito completo, Pausar y Detener; el script maneja Escape (cierra y
    devuelve el foco al botón), las flechas, Inicio y Fin."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    for texto in ("Anterior", "Siguiente", "Ver el circuito completo", "Pausar", "Detener"):
        assert texto in _texto(panel)
    assert 'data-accion="volver"' in _seccion_de_paso(panel, 2)  # «Volver al paso de mi pantalla»
    js = (RAIZ / "static" / "journey" / "evi.js").read_text(encoding="utf-8")
    assert 'e.key === "Escape"' in js and "boton.focus()" in js
    for tecla in ("ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"):
        assert tecla in js
    assert re.search(r'<button type="button" class="evi-nodo ', panel)  # los pasos son botones: Tab y Enter


def test_req166_los_siete_pasos_traen_su_explicacion_para_cambiar_con_cada_clic(client, caso_recien_cargado):
    """REQ-166: cada paso tiene su propia explicación (para que cambie con «Siguiente» seis veces)."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    explicaciones = [_texto(_seccion_de_paso(panel, n)) for n in range(1, 8)]
    assert len(set(explicaciones)) == 7
    assert 'data-n="0"' in panel  # y la del circuito completo, para cuando no hay paso elegido


# --- REQ-167 · los textos ----------------------------------------------------------------------


def test_req167_los_siete_pasos_traen_sus_tres_textos(client, caso_recien_cargado):
    """REQ-167: «Qué es», «Para qué sirve» y «Qué tiene que hacer», con el texto aprobado de `textos.py`."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    for n in range(1, 8):
        seccion = _seccion_de_paso(panel, n)
        texto = _texto(seccion)
        for rotulo in ("Qué es", "Para qué sirve", "Qué tiene que hacer"):
            assert f"<h4>{rotulo}</h4>" in seccion, (n, rotulo)
        t = textos.PASOS[n]
        assert html_lib.unescape(t.que_es) in texto and t.sirve in texto
        for linea in t.hacer:
            assert linea in texto
        assert len(t.hacer) == 4


def test_req167_los_seis_terminos_estan_explicados(client, caso_recien_cargado):
    """REQ-167: circular, matriz de requisitos, hoja de compliance, informe técnico, subsanación y dictamen."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    texto = _texto(_panel_de(client, _url_de("portada", caso)))
    for titulo in ("Qué es una circular", "Qué es la matriz de requisitos", "Qué es una hoja de compliance",
                   "Qué es el informe técnico", "Qué es una subsanación", "Qué es un dictamen"):
        assert titulo in texto
    todos = [t for p in textos.PASOS.values() for t in p.terminos]
    assert len(todos) == 6 and all(len(t.texto) > 60 for t in todos)


def test_req167_los_textos_salen_de_un_solo_archivo():
    """REQ-167: ninguna otra plantilla ni módulo repite los textos de los pasos."""
    muestras = [textos.PASOS[n].que_es[:60] for n in range(1, 8)] + [textos.PASOS[n].sirve for n in (1, 3)]
    muestras += [t.texto[:50] for p in textos.PASOS.values() for t in p.terminos]
    for archivo in list(RAIZ.rglob("*.py")) + list(RAIZ.rglob("*.html")) + list((RAIZ / "static").rglob("*.js")):
        if archivo.name == "textos.py" and archivo.parent.name == "evi":
            continue
        contenido = archivo.read_text(encoding="utf-8")
        for muestra in muestras:
            assert muestra not in contenido, (archivo.name, muestra)


def test_req167_ningun_texto_usa_terminos_de_programacion():
    """REQ-167: lenguaje llano, sin jerga técnica."""
    prohibidas = re.compile(r"\b(API|JSON|endpoint|base de datos|servidor|script|HTML|URL|token|backend|"
                            r"query|SQL|log|cache|caché|bug|framework|IA|LLM|modelo de lenguaje)\b", re.I)
    junto = " ".join([textos.CIRCUITO_TITULO, textos.CIRCUITO_QUE_ES, textos.CIRCUITO_COMO_SE_LEE,
                      textos.CIRCUITO_PARA_RECORRER, textos.CIRCUITO_QUIEN_DECIDE.texto])
    for t in textos.PASOS.values():
        junto += " " + " ".join([t.que_es, t.sirve, *t.hacer, *[x.texto for x in t.terminos]])
    assert prohibidas.findall(junto) == []


# --- REQ-168 · Qué hacer acá --------------------------------------------------------------------


def _numeros(texto):
    return re.findall(r"\d+", texto)


@pytest.mark.parametrize("caso_nombre", CASOS)
def test_req168_que_hacer_aca_usa_los_mismos_numeros_que_la_portada(caso_nombre, client, request):
    """REQ-168: cada frase de «Qué hacer acá» (el resumen, las tareas y los avisos del paso) está tal cual en la
    portada, y no hay en Evi ningún número que la portada no muestre."""
    caso = request.getfixturevalue(caso_nombre)
    entrar(client, caso.user)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    portada = _texto(client.get(_url_de("portada", caso)).content.decode())
    panel = _panel_de(client, _url_de("portada", caso))
    for paso in proceso.pasos:
        seccion = _seccion_de_paso(panel, paso.numero)
        aca = _texto(seccion[seccion.index('<section class="aca"'):seccion.index("</section>")])
        assert paso.resumen in aca and paso.resumen in portada
        for tarea in paso.tareas:
            if tarea.tipo != pasos.FALTANTE or paso.estado is not pasos.Estado.HECHO:
                assert tarea.texto in aca and tarea.texto in portada, (paso.numero, tarea.texto)
        assert set(_numeros(aca)) <= set(_numeros(portada)) | {str(paso.numero)}, paso.numero


def test_req168_los_numeros_del_caso_con_varios_pasos_en_curso(client, caso_varios_en_curso):
    """REQ-168: los números del caso de la maqueta A, dichos como los dice la portada."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    portada = _texto(client.get(_url_de("portada", caso)).content.decode())
    seis = _texto(_seccion_de_paso(panel, 6))
    for frase in ("Decidir 6 puntos no determinados", "Contestar 4 preguntas", "Revisar 1 «no cumple»",
                  "Confirmar 5 propuestas «cumple»", "Resolver 1 descarte propuesto"):
        assert frase in seis and frase in portada
    cuatro = _texto(_seccion_de_paso(panel, 4))
    assert "Cargar el informe técnico del área (falta en 2 ofertas)" in cuatro
    assert "0 de 12 puntos decididos" in seis


def test_req168_un_paso_sin_nada_pendiente_lo_dice(client, caso_todo_hecho):
    """REQ-168: un paso hecho sin pendientes dice que no hay nada pendiente; uno que espera a otro, que por
    ahora no hay nada para hacer. Los avisos que no frenan nada se dicen aparte."""
    caso = caso_todo_hecho
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    for n in range(1, 8):
        assert "No hay nada pendiente en este paso." in _texto(_seccion_de_paso(panel, n)), n
    assert "Hay 2 avisos que no frenan nada:" in _texto(_seccion_de_paso(panel, 1))
    assert "Falta el expediente, el cronograma y las garantías" in _texto(_seccion_de_paso(panel, 1))


def test_req168_los_pasos_que_esperan_a_otro_lo_dicen(client, caso_recien_cargado):
    """REQ-168: recién cargado, los pasos 4 a 7 todavía no tienen nada para hacer y dicen de qué dependen."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    panel = _panel_de(client, _url_de("portada", caso))
    for n in (4, 5, 6, 7):
        texto = _texto(_seccion_de_paso(panel, n))
        assert "Por ahora no hay nada para hacer en este paso." in texto and "Todavía no: depende de" in texto
    assert "Proponer la matriz" in _texto(_seccion_de_paso(panel, 2))


# --- REQ-170 · sin presentaciones ---------------------------------------------------------------


@pytest.mark.parametrize("pantalla", ["inicio", "portada", "cuadro"])
def test_req170_el_titulo_es_evi_y_no_hay_texto_que_lo_presente(pantalla, client, caso_varios_en_curso):
    """REQ-170: el panel se titula «Evi»; ni el panel ni su contenido dicen qué es, para qué sirve ni lo
    presentan (sin subtítulo, lema ni pie)."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    url = "/" if pantalla == "inicio" else _url_de(pantalla, caso)
    pagina = client.get(url).content.decode()
    cascara = pagina[pagina.index('<section class="evi-panel"'):pagina.index("</section>", pagina.index('<section class="evi-panel"'))]
    assert re.search(r'<h2 id="evi-titulo" tabindex="-1">Evi</h2>', cascara)
    assert _texto(cascara) == "Evi Cargando…"  # solo el título y la espera; el botón de cerrar lleva su nombre accesible
    assert cascara.count("<h2") == 1 and "<h1" not in cascara and "<footer" not in cascara
    contenido = _texto(_sin_preguntas(_panel_de(client, url)))
    assert not re.search(r"\bEvi\b", contenido)
    assert not re.search(r"asistente|guía|ayud|bienvenid|soy |sirve para ayudarle|le voy a", contenido, re.I)


# --- REQ-169 · solo lectura, sin decidir, sin enlaces prohibidos ---------------------------------


def _filas_por_tabla():
    cuentas = {}
    for modelo in apps.get_models():
        cuentas[modelo._meta.label] = modelo._default_manager.count()
    return cuentas


@pytest.mark.parametrize("caso_nombre", CASOS)
def test_req169_abrir_y_pedir_evi_no_escribe_en_la_base(caso_nombre, client, request):
    """REQ-169: abrir Evi en el inicio y en cada pantalla de un procedimiento deja igual la cuenta de filas de
    todas las tablas."""
    caso = request.getfixturevalue(caso_nombre)
    entrar(client, caso.user)
    urls = [reverse("expedientes:evi")]
    urls += [reverse("expedientes:evi_procedimiento", args=[caso.procedure.pk]) + f"?pasos={p}"
             for p in ("", "1,5", "4,6", "7")]
    antes = _filas_por_tabla()
    for url in urls:
        assert client.get(url).status_code == 200, url
    assert _filas_por_tabla() == antes


def test_req169_ningun_texto_dice_que_el_sistema_decidio_ni_recomienda(client, caso_varios_en_curso):
    """REQ-169: en ningún paso ni en el circuito aparece que el sistema decidió, resolvió, recomienda, sugiere o
    elige un ganador."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    texto = _texto(_sin_preguntas(_panel_de(client, _url_de("portada", caso))))
    prohibidas = r"el sistema (decidi|resolvi|eligi|determin[óo] que|adjudic)|recomend|recomiend|suger(?!encia)|sugier|adjudicar a|le aconsej"
    assert not re.search(prohibidas, texto, re.I)
    assert "la decide la Comisión" in texto or "lo decide la Comisión" in texto


@pytest.mark.parametrize("rol", ["no_commission_user", "operator_user", "evaluator_user"])
def test_req169_ningun_rol_recibe_enlaces_en_evi(rol, client, caso_varios_en_curso, request):
    """REQ-169: Evi no ofrece enlaces; así un usuario sin rol de la Comisión no recibe ninguno que le dé
    «acceso denegado». El usuario de lectura lo abre con 200."""
    caso = caso_varios_en_curso
    entrar(client, request.getfixturevalue(rol))
    for url in (reverse("expedientes:evi"), reverse("expedientes:evi_procedimiento", args=[caso.procedure.pk])):
        respuesta = client.get(url, {"pasos": "4,6"})
        assert respuesta.status_code == 200, (rol, url)
        html = respuesta.content.decode()
        assert "<a " not in html and "href=" not in html and "<form" not in html, (rol, url)


def test_req169_el_procedimiento_que_no_existe_da_404(client, caso_recien_cargado):
    """REQ-169: pedir el panel de un procedimiento inexistente no calcula nada y da 404."""
    entrar(client, caso_recien_cargado.user)
    assert client.get(reverse("expedientes:evi_procedimiento", args=[999999])).status_code == 404


def test_req169_solo_se_pide_con_get(client, caso_recien_cargado):
    """REQ-169: el panel no acepta POST (nada que escribir)."""
    entrar(client, caso_recien_cargado.user)
    url = reverse("expedientes:evi_procedimiento", args=[caso_recien_cargado.procedure.pk])
    assert client.post(url).status_code == 405
    assert client.post(reverse("expedientes:evi")).status_code == 405


# --- Restricciones de la tarea --------------------------------------------------------------------


def test_sin_migraciones_nuevas():
    """T-367: Evi no cambia el esquema; la última migración de cada app es la de siempre."""
    base = Path(RAIZ)
    encontrado = {}
    for carpeta in sorted(base.glob("*/migrations")):
        nombres = sorted(p.stem for p in carpeta.glob("[0-9][0-9][0-9][0-9]_*.py"))
        encontrado[carpeta.parent.name] = (nombres[-1], len(nombres))
    assert encontrado == ULTIMAS


def test_sin_recursos_de_afuera_ni_estilos_en_linea_en_lo_nuevo():
    """T-367: todo lo de Evi lo sirve la aplicación: sin direcciones externas, sin `style=`, sin scripts en línea."""
    archivos = [RAIZ / "static" / "journey" / "evi.css", RAIZ / "static" / "journey" / "evi.js",
                RAIZ / "templates" / "journey" / "_evi_boton.html",
                RAIZ / "templates" / "journey" / "_evi_contenido.html"]
    for archivo in archivos:
        texto = archivo.read_text(encoding="utf-8")
        assert "http://" not in texto and "https://" not in texto, archivo.name
        if archivo.suffix == ".html":
            assert " style=" not in texto and "<style" not in texto and "onclick=" not in texto, archivo.name
            assert not re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", texto), archivo.name
    css = archivos[0].read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", re.sub(r"/\*.*?\*/", "", css, flags=re.S))  # colores: solo tokens
