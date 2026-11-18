"""Correcciones de la verificación de T-348 (H1 a H9; REQ-146, REQ-147): la nota del paso 4 cuenta
todos los cruces y suma; un solo cálculo por pedido (contado en los dos módulos); el paso 5 dice de
qué depende una vez; el paso 3 en curso muestra lo que falta con su enlace; comillas angulares; el
botón de cada línea dice su verbo. Material inventado (P4)."""

import re
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import viewing
from evaluon.journey import memo
from evaluon.journey.proceso import calculo
from evaluon.journey.temas import s4_propuesta
from evaluon.journey.views import portada as vista
from tests.journey.proceso.test_portada import html_de

pytestmark = pytest.mark.django_db


def fila_de(html, numero):
    """El HTML de la fila del paso `numero` de la lista (hasta la fila siguiente o el final)."""
    desde = html[html.index(f'data-paso="{numero}"'):]
    siguiente = desde.find('data-pieza="paso"')
    return desde if siguiente == -1 else desde[:siguiente]


def test_req146_un_solo_calculo_por_pedido_contado_en_los_dos_modulos(
        client, caso_varios_en_curso, monkeypatch):
    """Plan 018 (H2): una llamada a `sections_for` desde la vista, NINGUNA desde `calculo` y una a
    `proceso_de`. Si la vista no le pasa el `Overview`, `proceso_de` lo recalcula y `calculo` da 1."""
    cuenta = {"vista": 0, "calculo": 0, "proceso_de": 0}
    real_vista, real_calculo, real_proceso = (
        vista.sections_for, calculo.sections_for, calculo.proceso_de)

    def desde_la_vista(*a, **k):
        cuenta["vista"] += 1
        return real_vista(*a, **k)

    def desde_calculo(*a, **k):
        cuenta["calculo"] += 1
        return real_calculo(*a, **k)

    def proceso(*a, **k):
        cuenta["proceso_de"] += 1
        return real_proceso(*a, **k)

    monkeypatch.setattr(vista, "sections_for", desde_la_vista)
    monkeypatch.setattr(calculo, "sections_for", desde_calculo)
    monkeypatch.setattr(calculo, "proceso_de", proceso)
    html_de(client, caso_varios_en_curso)
    assert cuenta == {"vista": 1, "calculo": 0, "proceso_de": 1}


def test_req146_la_nota_del_paso_4_cuenta_todos_los_cruces_y_suma(client, caso_varios_en_curso):
    """REQ-146 (H1): «De 18 cruces…»: 5 + 1 + 6 + 6 = 18 pares (2 ofertas × 9 requisitos), de las
    mismas cifras que el cuadro (`figures_of`)."""
    caso = caso_varios_en_curso
    cuatro = fila_de(html_de(client, caso), 4)
    nota = re.search(r'<p class="pr-nota">(De \d+ cruces[^<]*)</p>', cuatro).group(1)
    assert nota == ("De 18 cruces requisito–oferta: 5 cumplen, 1 no cumple, 6 a decidir y "
                    "6 esperan el resultado o el informe técnico.")
    total = int(re.match(r"De (\d+)", nota).group(1))
    partes = [int(n) for n in re.findall(r"(\d+) (?:cumplen|no cumple|a decidir|esperan)", nota)]
    assert sum(partes) == total
    with viewing(caso.user):
        cifras = s4_propuesta.figures_of(memo.matrix_page(caso.user, caso.procedure.pk))
    assert total == cifras.requirements * len(cifras.offers)


def test_req146_la_nota_de_cruces_suma_con_cualquier_reparto():
    """REQ-146 (H1): los números de la frase suman el total que la encabeza; «no aplica» solo si hay."""
    def oferta(ok, no, nd, pe, na):
        return SimpleNamespace(ok=ok, no=no, nd=nd, pe=pe, na=na)

    for ofertas in ([oferta(3, 1, 2, 3, 0)], [oferta(1, 0, 0, 0, 0)],
                    [oferta(0, 0, 0, 7, 2), oferta(4, 1, 1, 1, 1)]):
        nota = vista.nota_de_cruces(SimpleNamespace(offers=ofertas))
        total = int(re.match(r"De (\d+)", nota).group(1))
        patron = r"(\d+) (?:cumple|no cumple|a decidir|espera|no aplica)"
        assert sum(int(n) for n in re.findall(patron, nota)) == total
        assert total == sum(o.ok + o.no + o.nd + o.pe + o.na for o in ofertas)
    assert "no aplica" not in vista.nota_de_cruces(SimpleNamespace(offers=[oferta(1, 1, 1, 1, 0)]))
    assert vista.nota_de_cruces(None) == ""


def test_req146_el_paso_5_dice_de_que_depende_una_sola_vez(client, caso_varios_en_curso):
    """REQ-146 (H3): «Depende del paso 4, Cumplimiento de ofertas (matriz).», una vez y con el
    nombre real del paso."""
    cinco = fila_de(html_de(client, caso_varios_en_curso), 5)
    assert cinco.count("Depende del paso 4, Cumplimiento de ofertas (matriz).") == 1
    assert "Depende de otro paso" not in cinco and "depende del paso" not in cinco


def test_req146_el_paso_3_en_curso_muestra_lo_que_falta_con_su_enlace(client, caso_varios_en_curso):
    """REQ-146 (H4): el paso 3 «En curso» trae «Lo que falta»: el documento sin leer, con enlace a
    la fila de su oferta en Ofertas (el ancla existe), y la hoja de compliance con su botón."""
    caso = caso_varios_en_curso
    tres = fila_de(html_de(client, caso), 3)
    assert "Lo que falta" in tres
    assert "Falta leer 1 documento de la Oferta 2." in tres
    ofertas = reverse("expedientes:ofertas", args=[caso.procedure.pk])
    assert f'<a href="{ofertas}#s3-anexos-oferta-2">Ver la oferta</a>' in tres
    assert 'data-accion="3-faltante-compliance"' in tres
    assert 'id="s3-anexos-oferta-2"' in client.get(ofertas).content.decode()


def test_req146_un_paso_hecho_muestra_advertencias_y_no_lo_que_falta(client, caso_varios_en_curso):
    """REQ-146: el paso 1 «Hecho» muestra sus advertencias, no una lista de «Lo que falta»."""
    uno = fila_de(html_de(client, caso_varios_en_curso), 1)
    assert "2 advertencias" in uno and "Lo que falta" not in uno


def test_h5_comillas_angulares_en_toda_la_pantalla(client, caso_varios_en_curso):
    """H5: ni comillas curvas ni mezcladas: la portada usa « » en acciones, pasos y notas."""
    html = html_de(client, caso_varios_en_curso)
    cuerpo = html[html.index('id="portada-titulo"'):]
    assert "“" not in cuerpo and "”" not in cuerpo
    assert "Revisar 1 «no cumple»" in cuerpo and "Confirmar 5 propuestas «cumple»" in cuerpo


def test_h7_cada_boton_dice_el_verbo_de_su_linea(client, caso_varios_en_curso):
    """H7: los botones de acciones distintas no dicen todos «Resolver»."""
    html = html_de(client, caso_varios_en_curso)
    bloque = html[html.index('id="ahora-titulo"'):html.index('id="pasos-titulo"')]
    patron = r'data-accion="([^"]+)".*?class="btn primario chico"[^>]*>([^<]+)<'
    por_id = dict(re.findall(patron, bloque, re.S))
    assert por_id["6-pendiente-decidir"] == "Decidir"
    assert por_id["6-pendiente-no_cumple"] == "Revisar"
    assert por_id["6-pendiente-cumple"] == "Confirmar"
    assert por_id["6-pendiente-pregunta"] == "Contestar"
    assert por_id["4-pendiente-informe_falta"] == "Subir"
    assert list(por_id.values()).count("Resolver") <= 1


def test_h7_el_nombre_accesible_no_repite_el_verbo(client, caso_recien_cargado):
    """H7: «Proponer la matriz», no «Proponer: Proponer la matriz»."""
    html = html_de(client, caso_recien_cargado)
    assert 'aria-label="Proponer la matriz"' in html and "Proponer: Proponer" not in html


def test_h7_el_nombre_accesible_suma_el_verbo_si_la_linea_no_lo_dice(client, caso_varios_en_curso):
    """H7: «Subir: Cargar el informe técnico…»: el verbo del botón va delante si el texto no lo trae."""
    assert 'aria-label="Subir: Cargar el informe técnico del área' in html_de(
        client, caso_varios_en_curso)


def test_h9_el_paso_3_sin_ofertas_no_dice_lo_mismo_dos_veces(client, caso_recien_cargado):
    """H9: «Todavía no hay ofertas» está en el resumen y no se repite como advertencia."""
    tres = fila_de(html_de(client, caso_recien_cargado), 3)
    assert tres.count("Todavía no hay ofertas") == 1 and "advertencia" not in tres
