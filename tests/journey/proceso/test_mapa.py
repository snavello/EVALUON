"""El mapa del proceso en la portada (REQ-146, REQ-156, REQ-157, REQ-158; plan 018, «Mapa del
proceso»; T-350): siete tarjetas con el estado de su fila de la lista, conectores llenos o punteados
según el paso de origen, hasta 3 tareas y «+ N más», sin porcentaje ni barra de avance, línea de
plazos y marcas con texto. Material inventado (P4)."""

import re
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.journey.proceso import calculo, mapa, pasos
from evaluon.journey.tablero import ingreso
from tests.journey.proceso.test_portada import FIXTURE, entrar, html_de, url_de

pytestmark = pytest.mark.django_db
HOY = date(2026, 11, 18)


def tarjetas(html):
    """`{número: HTML de la tarjeta}` del mapa."""
    return {int(m.group(1)): m.group(0) for m in re.finditer(
        r'<li class="mp-nodo[^"]*" data-tarjeta="(\d)">.*?</li>\s*(?=<li class="mp-nodo|</ol>)',
        html, re.S)}


def estado_de_fila(html, numero):
    fila = html[html.index(f'data-paso="{numero}"'):]
    return re.search(r'<span class="pr-estado ([a-z-]+)">([^<]+)</span>', fila).groups()


@pytest.mark.parametrize("nombre", sorted(FIXTURE))
def test_req158_siete_tarjetas_con_el_estado_de_su_fila_de_la_lista(nombre, client, request):
    """REQ-158: siete tarjetas, en orden 1 a 7, con el nombre del paso y el MISMO estado escrito que
    la fila de la lista."""
    caso = request.getfixturevalue(FIXTURE[nombre])
    html = html_de(client, caso)
    cartas = tarjetas(html)
    assert sorted(cartas) == [1, 2, 3, 4, 5, 6, 7]
    orden = [int(n) for n in re.findall(r'data-tarjeta="(\d)"', html)]
    assert orden == [1, 2, 3, 4, 5, 6, 7]
    for p in calculo.proceso_de(caso.user, caso.procedure).pasos:
        clase, texto = estado_de_fila(html, p.numero)
        carta = cartas[p.numero]
        assert f'class="mp-estado {clase}">{texto}</span>' in carta
        assert p.nombre in carta and f"Paso {p.numero}: " in carta


def test_req158_el_mapa_va_entre_el_titulo_y_las_acciones_con_su_aria(client, caso_varios_en_curso):
    """REQ-158: título, mapa (`<ol>` con nombre), plazos y luego «Qué se puede hacer ahora»; el SVG
    es decorativo."""
    html = html_de(client, caso_varios_en_curso)
    marcas = ['id="portada-titulo"', 'class="mp mp-mapa"', 'aria-label="Mapa del proceso"',
              "Plazos importantes", 'id="ahora-titulo"']
    pos = [html.index(m) for m in marcas]
    assert pos == sorted(pos)
    assert html.count('<svg class="mp-hilos"') == 1
    assert re.search(r'<svg class="mp-hilos"[^>]*aria-hidden="true"', html)
    assert html.count('data-pieza="mapa"') == 1


def test_req158_sin_porcentaje_ni_barra_de_avance_ni_style(client, caso_varios_en_curso):
    """REQ-158: ni «%» ni barra de avance en el mapa; nada de `style=` (ADR-0076)."""
    html = html_de(client, caso_varios_en_curso)
    mp = html[html.index('class="mp mp-mapa"'):html.index('id="ahora-titulo"')]
    assert "%" not in mp and "progress" not in mp and 'class="av"' not in mp
    assert "style=" not in mp


def test_req158_las_lineas_llenas_salen_de_un_paso_hecho(client, caso_varios_en_curso):
    """REQ-158: el conector es lleno si el paso de origen está «Hecho» y punteado si no; el `d` es
    exactamente el de `mapa.TRAZOS`."""
    caso = caso_varios_en_curso
    html = html_de(client, caso)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    assert [p.estado for p in proceso.pasos[:2]] == [pasos.Estado.HECHO] * 2
    for c in mapa.TRAZOS:
        hallado = re.search(
            rf'<path d="([^"]+)" class="(lleno|punt)" data-conector="{c.origen}-{c.destino}"/>', html)
        assert hallado, (c.origen, c.destino)
        assert hallado.group(1) == c.d
        esperado = "lleno" if proceso.pasos[c.origen - 1].estado is pasos.Estado.HECHO else "punt"
        assert hallado.group(2) == esperado
    assert len(re.findall(r'data-conector="', html)) == 8


def test_req158_las_dependencias_se_dicen_en_texto(client, caso_varios_en_curso):
    """REQ-158: «Depende de: …» en texto oculto, desde `CONECTORES` (4 depende de 2 y 3)."""
    cartas = tarjetas(html_de(client, caso_varios_en_curso))
    assert ('<p class="sr-only">Depende de: 2. Matriz de requisitos de pliego, '
            '3. Recepción de ofertas.</p>') in cartas[4]
    assert "Depende de" not in cartas[1]


def _con_tareas(monkeypatch, cuantas, adv=()):
    real = calculo.proceso_de

    def hecho(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        seis = proceso.pasos[5]
        seis.tareas = [pasos.Accion(6, pasos.PENDIENTE, f"x{i}", f"Tarea de prueba {i}", 1, "Ver",
                                    f"/x/{i}/") for i in range(cuantas)]
        seis.advertencias = list(adv)
        proceso.acciones = [t for p in proceso.pasos for t in p.tareas]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", hecho)


def test_req158_hasta_tres_tareas_y_mas_n_mas(client, caso_varios_en_curso, monkeypatch):
    """REQ-158: con 5 tareas la tarjeta muestra 3 y «+ 2 más»; con 3, ningún «más»."""
    _con_tareas(monkeypatch, 5)
    carta = tarjetas(html_de(client, caso_varios_en_curso))[6]
    assert re.findall(r'data-accion="(6-pendiente-x\d)"', carta) == [
        f"6-pendiente-x{i}" for i in range(3)]
    assert "+ 2 más" in carta
    _con_tareas(monkeypatch, 3)
    carta = tarjetas(html_de(client, caso_varios_en_curso))[6]
    assert len(re.findall(r'data-accion="', carta)) == 3 and "más" not in carta


def test_req158_advertencias_y_espera_se_distinguen(client, caso_varios_en_curso, monkeypatch):
    """REQ-158: la advertencia lleva su texto («2 advertencias»); el paso que espera a otro lleva la
    fila «espera» y no una tarea."""
    _con_tareas(monkeypatch, 4, adv=("Una", "Otra"))
    carta = tarjetas(html_de(client, caso_varios_en_curso))[6]
    assert "2 advertencias" in carta and 'class="mp-resto con-mas"' in carta
    _con_tareas(monkeypatch, 1, adv=("Una",))
    cartas = tarjetas(html_de(client, caso_varios_en_curso))
    assert "1 advertencia<" in cartas[6]
    assert 'class="mp-tarea espera"' in cartas[7] and "mp-adv" not in cartas[7]


def test_req158_cada_tarea_y_cada_tarjeta_llevan_a_su_destino(client, caso_varios_en_curso):
    """REQ-158: el enlace del nombre de cada tarjeta y los de sus tareas responden 200."""
    html = html_de(client, caso_varios_en_curso)
    enlaces = set()
    for carta in tarjetas(html).values():
        enlaces.update(re.findall(r'<a href="([^"]+)"', carta))
    assert len(enlaces) >= 3
    for destino in enlaces:
        assert client.get(destino).status_code == 200, destino


def _fechas(monkeypatch, due, apertura=HOY - timedelta(days=30)):
    monkeypatch.setattr(ingreso, "today", lambda: HOY)
    monkeypatch.setattr(ingreso, "opening_moment", lambda p: apertura)
    monkeypatch.setattr(ingreso, "maintenance", lambda p: ingreso.Maintenance(
        "computed", due=due, days_left=(due - HOY).days))


def test_req148_plazos_con_apertura_hoy_y_vencimiento(client, caso_varios_en_curso, monkeypatch):
    """REQ-148: apertura, hoy y vencimiento sobre el eje, en orden de fecha y con su texto."""
    _fechas(monkeypatch, HOY + timedelta(days=23))
    html = html_de(client, caso_varios_en_curso)
    plazos = html[html.index('class="mp-plazos"'):html.index('id="ahora-titulo"')]
    assert "Apertura de ofertas" in plazos and "Hoy · 18/11" in plazos
    assert "Vence el mantenimiento de las ofertas" in plazos and "faltan 23 días" in plazos
    assert plazos.index("Apertura de ofertas") < plazos.index("Hoy ·") < plazos.index(
        "Vence el mantenimiento")
    assert "mp-hito x-0 " in plazos and "mp-hito x-100 " in plazos
    assert "Vence hoy" not in html and "Vencido" not in html.split('id="pasos"')[0]


def test_req148_el_motivo_cuando_falta_una_fecha(client, caso_varios_en_curso):
    """REQ-148: sin fechas del Portal queda «Hoy» y el motivo en texto; nunca una fecha inventada."""
    html = html_de(client, caso_varios_en_curso)
    plazos = html[html.index('class="mp-plazos"'):html.index('id="ahora-titulo"')]
    assert "Falta la apertura en el cronograma" in plazos and "Sin fechas del Portal" in plazos
    assert plazos.count('class="mp-hito ') == 1 and "mp-hito x-50 " in plazos


def test_req157_vence_hoy_con_texto_en_tarjeta_tarea_y_plazos(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157: «Vence hoy» (lila) en la tarjeta del paso 7, en su tarea y en el eje, con texto."""
    _fechas(monkeypatch, HOY)
    html = html_de(client, caso_varios_en_curso)
    siete = tarjetas(html)[7]
    assert "marca-hoy" in siete and siete.count('<span class="mp-hoy">Vence hoy</span>') == 2
    assert '<li class="mp-tarea hoy" data-accion="7-cierre-dictamen">' in siete
    assert '<span class="mp-hoy">Vence hoy</span>' in html[html.index('class="mp-plazos"'):]
    assert "mp-vencido" not in html
    assert '<i class="mp-k hoy"' in html


def test_req157_vencido_con_texto(client, caso_varios_en_curso, monkeypatch):
    """REQ-157: al día siguiente, rojo brillante con el texto «Vencido»."""
    _fechas(monkeypatch, HOY - timedelta(days=1))
    html = html_de(client, caso_varios_en_curso)
    siete = tarjetas(html)[7]
    assert "marca-vencido" in siete and siete.count('<span class="mp-vencido">Vencido</span>') == 2
    assert "mp-hoy" not in html


def test_req158_el_rol_de_lectura_ve_el_mapa(client, caso_varios_en_curso, read_user):
    """REQ-158: el usuario de lectura ve el mapa (enlaces, sin formularios)."""
    entrar(client, read_user)
    html = client.get(url_de(caso_varios_en_curso)).content.decode()
    assert len(tarjetas(html)) == 7 and "<form" not in tarjetas(html)[6]


def test_cantidad_de_consultas_con_el_mapa(client, caso_varios_en_curso):
    """El mapa no suma consultas por tarjeta: se mide y se acota."""
    entrar(client, caso_varios_en_curso.user)
    with CaptureQueriesContext(connection) as q:
        assert client.get(url_de(caso_varios_en_curso)).status_code == 200
    print(f"CONSULTAS portada con mapa varios_en_curso: {len(q)}")
    assert len(q) <= 400
