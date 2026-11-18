"""La portada del procedimiento (REQ-143, REQ-144, REQ-146, REQ-147, REQ-148; plan 018, «Portada
del procedimiento»; T-348): orden de los bloques, los siete pasos con su estado y su enlace, «Abrir
indicadores» y «Volver al proceso», el usuario de lectura sin botones, un solo cálculo por pedido y
el criterio de 15 piezas. Material inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.db import connection
from django.template.loader import render_to_string
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.journey.proceso import calculo, pasos
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

FIXTURE = {"recien": "caso_recien_cargado", "varios": "caso_varios_en_curso",
           "hecho": "caso_todo_hecho"}
NOMBRES = ["Carga de pliego", "Matriz de requisitos de pliego", "Recepción de ofertas",
           "Cumplimiento de ofertas (matriz)", "Comparación de ofertas", "Evaluación Comisión",
           "Dictamen"]


def entrar(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def url_de(caso):
    return reverse("expedientes:portada", args=[caso.procedure.pk])


def html_de(client, caso):
    entrar(client, caso.user)
    respuesta = client.get(url_de(caso))
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def piezas_antes_del_tercer_paso(html):
    """Cuántos `data-pieza` hay antes del tercer paso de la lista (la primera pantalla)."""
    posiciones = [m.start() for m in re.finditer(r'data-pieza="paso"', html)]
    corte = posiciones[2]
    return len(re.findall(r'data-pieza="', html[:corte]))


@pytest.mark.parametrize("nombre", sorted(FIXTURE))
def test_req146_responde_200_con_los_siete_pasos_en_orden(nombre, client, request):
    """REQ-143: la portada ya no redirige y dice los siete nombres, en el orden de lectura."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    html = html_de(client, caso)
    lista = html[html.index('class="pr-pasos"'):]
    encontrados = [lista.index(n) for n in NOMBRES]
    assert encontrados == sorted(encontrados)
    assert len(re.findall(r'data-pieza="paso"', html)) == 7


def test_req146_el_orden_de_los_bloques(client, caso_varios_en_curso):
    """REQ-146: título con «Abrir indicadores», «Qué se puede hacer ahora» y después los pasos."""
    html = html_de(client, caso_varios_en_curso)
    marcas = ['id="portada-titulo"', "Abrir indicadores", 'id="ahora-titulo"', 'id="pasos-titulo"']
    posiciones = [html.index(m) for m in marcas]
    assert posiciones == sorted(posiciones)
    assert "<svg" not in html[html.index("Abrir indicadores"):html.index('id="ahora-titulo"')]


def test_req144_los_pasos_en_curso_traen_su_enlace_y_su_estado_escrito(
        client, caso_varios_en_curso):
    """REQ-144, REQ-149: con 3, 4, 5 y 6 «En curso» a la vez, cada paso de la lista trae su
    enlace y su estado con texto; ninguna cadena habla de un «paso actual»."""
    caso = caso_varios_en_curso
    html = html_de(client, caso)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    for paso in proceso.pasos:
        fila = re.search(rf'<li class="pr-paso [^"]*" data-pieza="paso" data-paso="{paso.numero}">'
                         r'.*?</li>\s*(?=<li class="pr-paso|</ol>)', html, re.S).group(0)
        assert f'href="{paso.destino}"' in fila
        assert f'>{paso.estado.texto}</span>' in fila
    estados = re.findall(r'class="pr-estado ([a-z-]+)"', html)
    assert estados == ["hecho", "hecho", "en-curso", "en-curso", "en-curso", "en-curso",
                       "todavia-no"]
    assert not re.search(r"paso actual|va por el paso|vas por el paso", html, re.I)


def test_req144_cada_paso_en_curso_lista_lo_que_falta_con_su_boton(client, caso_varios_en_curso):
    """REQ-146: el paso 6 en curso muestra sus cinco líneas (descarte, preguntas y tres de puntos)
    con botón, y una nota que explica por qué «0 de 12 puntos decididos» y las líneas dicen 6, 1 y
    5 (aviso de T-346)."""
    html = html_de(client, caso_varios_en_curso)
    fila = html[html.index('data-paso="6"'):html.index('data-paso="7"')]
    assert "0 de 12 puntos decididos" in fila
    assert "Los puntos sin decidir son 6 sin determinar, 1 «no cumple» y 5 «cumple» sin confirmar." in fila
    assert fila.count('<li class="pr-accion') == 5 and "Lo que falta" in fila
    assert fila.count('class="btn primario chico"') == 5
    cuatro = html[html.index('data-paso="4"'):html.index('data-paso="5"')]
    assert "De 18 cruces requisito–oferta" in cuatro


def test_req146_el_paso_7_con_error_muestra_el_motivo_aunque_no_tenga_accion(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-146 (aviso de T-346): un paso que el cálculo deja «Con error» sin acción muestra su
    resumen con el motivo, sin botón."""
    caso = caso_varios_en_curso
    real = calculo.proceso_de

    def con_error(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        siete = proceso.pasos[6]
        siete.estado = pasos.Estado.CON_ERROR
        siete.resumen = "No se pudo tomar el dictamen del Portal. El Portal no respondió."
        siete.tareas = []
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", con_error)
    html = html_de(client, caso)
    fila = html[html.index('data-paso="7"'):]
    assert "No se pudo tomar el dictamen del Portal. El Portal no respondió." in fila
    assert 'class="pr-estado con-error"' in fila and ">Con error</span>" in fila
    assert "Lo que falta" not in fila


def test_req148_abrir_indicadores_lleva_al_primer_panel_con_su_titulo(client, caso_varios_en_curso):
    """REQ-148: «Abrir indicadores» lleva a `procedimiento/`, que se titula «Indicadores», tiene
    «Volver al proceso» y conserva sus mosaicos."""
    caso = caso_varios_en_curso
    html = html_de(client, caso)
    destino = reverse("expedientes:procedimiento", args=[caso.procedure.pk])
    assert f'href="{destino}">Abrir indicadores</a>' in html
    panel = client.get(destino)
    assert panel.status_code == 200
    contenido = panel.content.decode()
    assert ">Indicadores</h2>" in contenido
    assert f'href="{url_de(caso)}">Volver al proceso</a>' in contenido
    assert 'id="ingreso"' in contenido and 'id="detalles"' in contenido


def test_req146_la_portada_no_recuerda_el_ultimo_procedimiento(client, caso_varios_en_curso):
    """Plan 018: ni la portada ni las secciones fijan la cookie del «último visto»."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    for ruta in (url_de(caso), reverse("expedientes:pliego", args=[caso.procedure.pk])):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 200
        assert not [c for c in respuesta.cookies if c.startswith("evaluon_ultimo")]


def test_req147_el_usuario_de_lectura_ve_la_portada_sin_botones(
        client, caso_varios_en_curso, read_user):
    """REQ-147: el usuario de lectura ve las líneas y los pasos, pero ningún botón ni formulario."""
    caso = caso_varios_en_curso
    assert not read_user.commission_role
    entrar(client, read_user)
    respuesta = client.get(url_de(caso))
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert 'data-pieza="accion"' in html
    assert 'class="btn primario chico"' not in html and "<form" not in html.split("<main")[1]


def test_req146_el_procedimiento_que_no_existe_da_404(client, evaluator_user):
    """El procedimiento inexistente da 404 (como antes)."""
    entrar(client, evaluator_user)
    assert client.get(reverse("expedientes:portada", args=[999999])).status_code == 404


@pytest.mark.parametrize("nombre", sorted(FIXTURE))
def test_criterio_de_15_piezas_en_la_primera_pantalla(nombre, client, request):
    """Criterio numérico 3: a lo sumo 15 `data-pieza` antes del tercer paso, con los tres casos."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    assert piezas_antes_del_tercer_paso(html_de(client, caso)) <= 15


def test_criterio_de_15_piezas_con_muchas_lineas(client, caso_varios_en_curso, monkeypatch):
    """Con más de 6 líneas, las ocultas no llevan `data-pieza` y el total sigue en 15 o menos."""
    caso = caso_varios_en_curso
    real = calculo.proceso_de

    def muchas(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        proceso.acciones = proceso.acciones + [
            pasos.Accion(3, pasos.FALTANTE, f"extra{i}", f"Línea de más {i}", 0, "Ver", "/x/")
            for i in range(8)]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", muchas)
    html = html_de(client, caso)
    assert piezas_antes_del_tercer_paso(html) <= 15
    assert html.count('data-pieza="accion"') == 6
    assert re.search(r"ver las \d+ restantes", html)


def test_cantidad_de_consultas_de_la_portada(client, caso_varios_en_curso):
    """Se mide y se acota: la portada no multiplica las consultas por paso (aviso de T-346)."""
    entrar(client, caso_varios_en_curso.user)
    with CaptureQueriesContext(connection) as capturadas:
        assert client.get(url_de(caso_varios_en_curso)).status_code == 200
    print(f"CONSULTAS portada varios_en_curso: {len(capturadas)}")
    assert len(capturadas) <= 400


def test_la_barra_de_siete_pasos_dice_el_estado_escrito():
    """REQ-143, REQ-156: `_foto_pasos.html` (para el inicio) trae número, nombre y estado con texto."""
    siete = [pasos.Paso.vacio(d) for d in pasos.PASOS]
    siete[0].estado, siete[2].estado = pasos.Estado.HECHO, pasos.Estado.EN_CURSO
    siete[6].marca = pasos.MARCA_HOY
    html = render_to_string("journey/_foto_pasos.html", {"pasos": siete})
    assert [m for m in re.findall(r"<b>(\d) ([^<]+)</b>", html)] == [
        (str(d.numero), d.nombre) for d in pasos.PASOS]
    assert re.findall(r'pr-foto-estado">([^<]+)<', html) == [
        "Hecho", "Todavía no", "En curso", "Todavía no", "Todavía no", "Todavía no", "Todavía no"]
    assert '<span class="pr-hoy">Vence hoy</span>' in html


def test_las_plantillas_no_tienen_estilos_ni_scripts_en_linea():
    """ADR-0076: sin `style=` ni `<script>` en las plantillas de la portada."""
    carpeta = Path(__file__).resolve().parents[3] / "evaluon" / "templates" / "journey"
    for nombre in ("portada", "_acciones", "_foto_pasos"):
        fuente = (carpeta / f"{nombre}.html").read_text(encoding="utf-8")
        assert " style=" not in fuente and "<script" not in fuente
