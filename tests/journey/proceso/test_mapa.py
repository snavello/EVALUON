"""El mapa del proceso en la portada (REQ-146, REQ-156, REQ-157, REQ-158; plan 018, «Mapa del
proceso»; T-350): siete tarjetas con el estado de su fila de la lista, conectores llenos o punteados
según el paso de origen, hasta 3 tareas y «+ N más», sin porcentaje ni barra de avance, línea de
plazos y marcas con texto. Material inventado (P4)."""

import re
from pathlib import Path
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


def geometria_de(html):
    """La `mapa.Geometria` que la portada eligió: sus escalones salen de las clases del lienzo."""
    k, m = re.search(r'<div class="mp-lienzo fila-b-(\d+) alto-b-(\d+)">', html).groups()
    return mapa.geometria(int(k), int(m))


def test_req158_las_lineas_llenas_salen_de_un_paso_hecho(client, caso_varios_en_curso):
    """REQ-158: el conector es lleno si el paso de origen está «Hecho» y de rayas si no; el `d` es
    exactamente el de la geometría que eligió la portada (`mapa.geometria`)."""
    caso = caso_varios_en_curso
    html = html_de(client, caso)
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    assert [p.estado for p in proceso.pasos[:2]] == [pasos.Estado.HECHO] * 2
    g = geometria_de(html)
    for c in g.trazos:
        hallado = re.search(
            rf'<path d="([^"]+)" class="(lleno|punt)" data-conector="{c.origen}-{c.destino}"/>', html)
        assert hallado, (c.origen, c.destino)
        assert hallado.group(1) == c.d
        esperado = "lleno" if proceso.pasos[c.origen - 1].estado is pasos.Estado.HECHO else "punt"
        assert hallado.group(2) == esperado
    assert len(re.findall(r'data-conector="', html)) == 8
    assert f'viewBox="0 0 {g.lienzo[0]} {g.lienzo[1]}"' in html


def test_req158_la_geometria_sale_del_contenido_y_no_es_la_maxima(client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (T-363): la fila de abajo empieza donde lo pide el alto estimado de la de arriba; con tarjetas
    llenas de tareas largas el escalón sube, y el estimado nunca es menor que el del contenido."""
    corta = geometria_de(html_de(client, caso_varios_en_curso))
    assert corta.arriba < len(mapa.ESCALONES) - 1 and corta.fila_b < mapa.Y_ARRIBA + mapa.ALTO_MAXIMO
    larga = "Resolver el punto número 1 que quedó pendiente de revisión por la Comisión"
    real = calculo.proceso_de

    def lleno(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        for p in proceso.pasos:
            p.tareas = [pasos.Accion(p.numero, pasos.PENDIENTE, f"x{i}", larga, 1, "Ver", "/x/") for i in range(5)]
            p.advertencias = ["Una", "Otra"]
        proceso.acciones = [t for p in proceso.pasos for t in p.tareas]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", lleno)
    llena = geometria_de(html_de(client, caso_varios_en_curso))
    assert llena.arriba > corta.arriba and llena.lienzo[1] > corta.lienzo[1]
    assert mapa.ESCALONES[llena.arriba] >= 240  # 3 tareas de dos líneas, el dato y el renglón de «+ N más»


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
    assert "Ver las 5 tareas" in carta and "+ 2 más" not in carta  # T-361 (A-2): el total, no un resto que la red de seguridad puede dejar corto
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
        enlaces.update(h for h in re.findall(r'<a href="([^"]+)"', carta) if not h.startswith("#"))
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


def test_req157_los_plazos_dicen_vencido_y_vence_hoy_con_texto(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157 (H4): la línea de plazos lleva la etiqueta con texto, «Vencido» o «Vence hoy», sola
    (no vale la de la tarjeta) y nunca la del otro caso."""
    _fechas(monkeypatch, HOY - timedelta(days=1))
    html = html_de(client, caso_varios_en_curso)
    plazos = html[html.index('class="mp-plazos"'):html.index('data-pieza="acciones"')]
    assert '<span class="mp-vencido">Vencido</span>' in plazos and "mp-hoy" not in plazos
    _fechas(monkeypatch, HOY)
    html = html_de(client, caso_varios_en_curso)
    plazos = html[html.index('class="mp-plazos"'):html.index('data-pieza="acciones"')]
    assert '<span class="mp-hoy">Vence hoy</span>' in plazos and "mp-vencido" not in plazos


def test_req157_la_tarea_marcada_se_lee_entera_y_la_etiqueta_va_debajo(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-157 (H2): en «Cargar el dictamen» la etiqueta va en el mismo cuerpo, debajo del texto, y no
    en la fila, donde se comía el ancho y dejaba «Cargar e…»."""
    for due, clase, etiqueta in ((HOY, "hoy", "Vence hoy"), (HOY - timedelta(days=1), "vencido", "Vencido")):
        _fechas(monkeypatch, due)
        siete = tarjetas(html_de(client, caso_varios_en_curso))[7]
        tarea = re.search(rf'<li class="mp-tarea {clase}".*?</li>', siete, re.S).group(0)
        assert (f'<span class="mp-cuerpo"><span class="mp-txt">Cargar el dictamen</span>'
                f'<span class="mp-{clase}">{etiqueta}</span></span>') in tarea
    css = (Path(__file__).resolve().parents[3] / "evaluon/static/journey/mapa.css").read_text(encoding="utf-8")
    assert re.search(r"\.mp-cuerpo\s*\{[^}]*flex-direction:\s*column", css)


def test_req158_mas_n_mas_dice_y_hace_lo_mismo(client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (A2): «+ N más» lleva a la fila del paso en la lista de abajo y su `title` lo dice."""
    _con_tareas(monkeypatch, 5)
    html = html_de(client, caso_varios_en_curso)
    carta = tarjetas(html)[6]
    assert ('<a class="mp-mas" href="#paso-6" title="Ver todas las tareas del paso 6 en la lista de '
            'abajo">Ver las 5 tareas</a>') in carta
    assert 'id="paso-6"' in html[html.index('id="pasos"'):]


# --- T-363: tarjetas anchas y sin recorte, advertencia enlazada, texto que dice lo que se ve -----------

def test_req158_la_advertencia_es_un_enlace_a_la_lista_del_paso_y_sigue_el_orden_de_tabulacion(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (T-363): «N advertencias» es un `<a>` enfocable a `#paso-N` (con el paso dicho para el lector
    de pantalla); en la tarjeta el orden de tabulación es nombre, tareas, «+ N más» y advertencias."""
    _con_tareas(monkeypatch, 5, adv=("Una", "Otra"))
    html = html_de(client, caso_varios_en_curso)
    carta = tarjetas(html)[6]
    assert re.search(r'<a class="mp-adv" href="#paso-6" title="Una · Otra"><i aria-hidden="true">!</i>'
                     r'2 advertencias<span class="sr-only"> del paso 6: ver en la lista</span></a>', carta)
    enlaces = [m.start() for m in re.finditer(r"<a ", carta)]
    nombre, tarea, mas, adv = (carta.index('<h3 class="mp-nom">'), carta.index('<li class="mp-tarea'),
                               carta.index('class="mp-mas"'), carta.index('class="mp-adv"'))
    assert nombre < tarea < mas < adv and len(enlaces) == 1 + 3 + 1 + 1
    assert 'id="paso-6"' in html[html.index('id="pasos"'):]  # el destino existe


def test_req158_el_resumen_del_titulo_dice_1_hecho_en_singular(client, caso_recien_cargado):
    """REQ-158 (H-A4, T-363): con un solo paso hecho dice «1 hecho», nunca «1 hechos»."""
    uno = html_de(client, caso_recien_cargado)
    assert "1 hecho, 1 en curso" in uno and "1 hechos" not in uno


def test_req158_el_resumen_del_titulo_dice_hechos_en_plural(client, caso_varios_en_curso):
    """REQ-158 (H-A4, T-363): con dos pasos hechos dice «2 hechos»."""
    assert "2 hechos, 4 en curso" in html_de(client, caso_varios_en_curso)


def test_req158_la_leyenda_dice_rayas_y_no_punteada(client, caso_varios_en_curso):
    """REQ-158 (T-363): el conector que todavía puede cambiar se dibuja de rayas; la leyenda lo dice así."""
    html = html_de(client, caso_varios_en_curso)
    mp = html[html.index('class="mp mp-mapa"'):html.index('id="ahora-titulo"')]
    assert "Línea de rayas: todavía puede cambiar" in mp and "unteada" not in mp


def test_req148_sin_fechas_la_linea_de_plazos_es_corta_y_con_fechas_dibuja_el_eje(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-148 (H-B6, T-363): con menos de dos fechas la regla no ocupa su alto de eje (clase `corta`); con
    apertura y vencimiento sí se dibuja el eje completo."""
    sin = html_de(client, caso_varios_en_curso)
    assert 'class="mp-regla niveles-0 corta"' in sin
    _fechas(monkeypatch, HOY + timedelta(days=23))
    con = html_de(client, caso_varios_en_curso)
    assert 'class="mp-regla niveles-0"' in con and "corta" not in con[con.index('class="mp-plazos"'):con.index('id="ahora-titulo"')]
    css = (Path(__file__).resolve().parents[3] / "evaluon/static/journey/mapa.css").read_text(encoding="utf-8")
    assert re.search(r"\.mp-regla\.corta\s*\{\s*height:\s*auto", css)


def test_req158_ninguna_tarea_lleva_recorte_en_su_html(client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (T-363): el texto de cada tarea y del dato va entero en el HTML (el recorte, si lo hubiera, sería
    de la hoja, que un test aparte vigila); una frase de 74 caracteres no se corta."""
    larga = "Resolver el punto número 1 que quedó pendiente de revisión por la Comisión"
    real = calculo.proceso_de

    def hecho(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        proceso.pasos[5].tareas = [pasos.Accion(6, pasos.PENDIENTE, "x0", larga, 1, "Ver", "/x/")]
        proceso.acciones = [t for p in proceso.pasos for t in p.tareas]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", hecho)
    carta = tarjetas(html_de(client, caso_varios_en_curso))[6]
    assert f'<span class="mp-txt">{larga}</span>' in carta and "…" not in carta


# --- T-363 (correcciones de la verificación): texto acortado, «Ver todo en la lista», accesibilidad ------

def test_req158_el_numero_de_la_tarjeta_es_decorativo_y_el_nombre_lo_dice_con_su_numero(
        client, caso_varios_en_curso):
    """REQ-158 (H-A5): el círculo con el número lleva `aria-hidden="true"` (el nombre ya dice «Paso N: »)."""
    cartas = tarjetas(html_de(client, caso_varios_en_curso))
    for n, carta in cartas.items():
        assert f'<span class="mp-n" aria-hidden="true">{n}</span>' in carta
        assert f'<span class="sr-only">Paso {n}: </span>' in carta


def test_req158_un_texto_larguisimo_se_corta_en_la_tarjeta_con_puntos_y_va_entero_en_el_title_y_en_la_lista(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (H-A2, T-363): una tarea de 220 caracteres (un error de etapa, por ejemplo) se muestra en la
    tarjeta cortada en el último espacio con «…», con el texto completo en el `title` y en la lista de pasos;
    la tarjeta, que quedó pasada del último escalón, trae «Ver todo en la lista» enlazado a `#paso-N`."""
    largo = "Resolver el error: «" + "la oferta no trae el documento pedido por el pliego " * 4 + "»"
    assert len(largo) > 200
    real = calculo.proceso_de

    def hecho(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        seis = proceso.pasos[5]
        seis.tareas = [pasos.Accion(6, pasos.PENDIENTE, f"x{i}", largo, 1, "Ver", f"/x/{i}/") for i in range(3)]
        proceso.acciones = [t for p in proceso.pasos for t in p.tareas]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", hecho)
    html = html_de(client, caso_varios_en_curso)
    carta = tarjetas(html)[6]
    corto = mapa.acortar(largo, mapa.LIMITE_TAREA)
    assert corto.endswith("…") and len(corto) <= mapa.LIMITE_TAREA and largo.startswith(corto[:-1])
    assert carta.count(f'<span class="mp-txt">{corto}</span>') == 3
    assert f'title="{largo}"' in carta  # el texto completo, en el title...
    assert html.count(largo) >= 4  # ...y en la lista de pasos (lo que no está en el title de la tarjeta)
    assert "Ver todo en la lista" not in carta  # con el tope de largo la tarjeta entra: no hace falta


def test_req158_si_la_estimacion_pasa_del_ultimo_escalon_la_tarjeta_manda_a_la_lista(
        client, caso_varios_en_curso, monkeypatch):
    """REQ-158 (H-A2, T-363): si el alto estimado de una tarjeta pasa del último escalón (432 px; aquí, sin el tope
    de largo) la tarjeta lleva «Ver todo en la lista» enlazado a `#paso-N` en su último renglón, y solo ella;
    la hoja la corta entre tarea y tarea en el alto de su fila."""
    largo = "Resolver el error: «" + "la oferta no trae el documento pedido por el pliego " * 6 + "»"
    monkeypatch.setattr(mapa, "LIMITE_TAREA", 1000)
    real = calculo.proceso_de

    def hecho(user, procedure, overview=None):
        proceso = real(user, procedure, overview)
        seis = proceso.pasos[5]
        seis.tareas = [pasos.Accion(6, pasos.PENDIENTE, f"x{i}", largo, 1, "Ver", f"/x/{i}/") for i in range(3)]
        proceso.acciones = [t for p in proceso.pasos for t in p.tareas]
        return proceso

    monkeypatch.setattr(calculo, "proceso_de", hecho)
    html = html_de(client, caso_varios_en_curso)
    carta = tarjetas(html)[6]
    assert ('<a class="mp-mas" href="#paso-6" title="Esta tarjeta no muestra todo: ver el paso 6 completo en la '
            'lista de abajo">Ver todo en la lista</a>') in carta
    assert "Ver todo en la lista" not in tarjetas(html)[1]
    assert geometria_de(html).abajo == len(mapa.ESCALONES) - 1 or geometria_de(html).arriba == len(mapa.ESCALONES) - 1


def test_req158_acortar_corta_en_un_espacio_y_no_toca_lo_que_cabe():
    """REQ-158 (H-A2): `acortar` deja intacto lo que cabe, corta en el último espacio que deje al menos la mitad
    y, si no hay espacio, corta duro; siempre termina en «…» y nunca pasa del límite."""
    assert mapa.acortar("Cargar el dictamen", 110) == "Cargar el dictamen"
    justo = "x" * 110
    assert mapa.acortar(justo, 110) == justo
    corto = mapa.acortar("uno dos tres " * 20, 60)
    assert corto.endswith("…") and len(corto) <= 60 and not corto[:-1].endswith(" ")
    assert mapa.acortar("x" * 300, 60) == "x" * 59 + "…"
    assert mapa.acortar("palabra " * 3 + "y" * 200, 40).endswith("…")
