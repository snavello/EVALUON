"""Filtros, grupos resumidos y «Siguiente a decidir» del cuadro (REQ-153, REQ-154; T-355).
Material inventado (P4)."""

import re
from pathlib import Path

import pytest

from tests.journey.proceso.test_cuadro import entrar, sintetico, url_de

pytestmark = pytest.mark.django_db

CSS = Path(__file__).parents[3] / "evaluon/static/journey/cuadro.css"
HTML = Path(__file__).parents[3] / "evaluon/templates/journey/cuadro.html"


def _filas(response):
    return [r for g in response.context["groups"] for r in g["rows"]]


def test_a_decidir_deja_solo_las_filas_con_una_celda_a_decidir(client, caso_varios_en_curso):
    """REQ-153: con 6 celdas a decidir, el filtro deja las filas que tienen alguna."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    todas = client.get(url_de(caso.procedure))
    filtrada = client.get(url_de(caso.procedure, "?filtro=a-decidir"))
    esperadas = [r for r in _filas(todas) if any(c["key"] == "nd" for c in r["cells"])]
    assert esperadas and len(_filas(filtrada)) == len(esperadas) < len(_filas(todas))
    assert all(any(c["key"] == "nd" for c in r["cells"]) for r in _filas(filtrada))
    cantidades = {f["clave"]: f["n"] for f in filtrada.context["filtros"]}
    assert cantidades["a-decidir"] == len(esperadas)
    assert cantidades["todos"] == len(_filas(todas))
    html = filtrada.content.decode()
    assert 'aria-current="true"' in html and "A decidir <b>" in html


def test_los_otros_filtros_dejan_lo_suyo(client, caso_varios_en_curso):
    """REQ-153: no cumple y espera informe técnico filtran por su tipo de celda."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    for filtro, clave in (("no-cumple", "no"), ("espera-informe", "esp")):
        filas = _filas(client.get(url_de(caso.procedure, f"?filtro={filtro}")))
        assert filas and all(any(c["key"] == clave for c in r["cells"]) for r in filas)
    pend = _filas(client.get(url_de(caso.procedure, "?filtro=pendiente")))
    assert all(any(c["pendiente"] for c in r["cells"]) for r in pend)


def test_la_cuenta_del_paso_6_y_las_celdas_del_filtro_coinciden(client, caso_varios_en_curso):
    """REQ-153: «Decidir N puntos» cuenta las celdas que el filtro «A decidir» deja visibles."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    from evaluon.journey.proceso import acciones
    r = client.get(url_de(caso.procedure, "?filtro=a-decidir"))
    celdas = sum(1 for row in _filas(r) for c in row["cells"]
                 if c["key"] in ("nd", "pe", "na") and c["pendiente"])
    assert acciones._pares_por_estado(caso.user, caso.procedure)[acciones.K_DECIDIR][0] == celdas == 6


def test_un_grupo_todo_cumple_sale_en_una_linea(client, caso_todo_hecho):
    """REQ-153: si todas las ofertas cumplen todo, el grupo se resume en un `<details>`."""
    caso = caso_todo_hecho
    entrar(client, caso.user)
    r = client.get(url_de(caso.procedure))
    resumidos = [g for g in r.context["groups"] if g["resumido"]]
    assert resumidos
    html = r.content.decode()
    assert html.count('<tr class="cu-resumen">') == len(resumidos)
    assert "todas las ofertas cumplen todo" in html


def test_un_grupo_con_pendientes_no_se_resume(client, caso_varios_en_curso):
    """REQ-153: el resumen es solo para lo que está todo cumplido."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    r = client.get(url_de(caso.procedure))
    assert not any(g["resumido"] for g in r.context["groups"])


def test_siguiente_avanza_en_el_orden_del_cuadro_y_conserva_el_filtro(client, caso_varios_en_curso):
    """REQ-154: «Siguiente a decidir ›» lleva a la próxima celda a decidir en el orden del cuadro."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    r = client.get(url_de(caso.procedure, "?filtro=a-decidir"))
    orden = [c for g in r.context["groups"] for row in g["rows"] for c in row["cells"]
             if c["key"] == "nd"]
    vistos = []
    actual = orden[0]
    for _ in range(len(orden)):
        vistos.append(actual["id"])
        pagina = client.get(actual["url"].split("#")[0])
        sig = pagina.context["siguiente"]
        assert "Siguiente a decidir ›" in pagina.content.decode() or not sig
        if not sig:
            break
        assert "filtro=a-decidir" in sig
        siguiente = next((c for c in orden if c["id"] == sig.split("#")[1]), None)
        if siguiente is None:  # ya no queda ninguna a decidir: pasa a la próxima con algo pendiente
            break
        actual = siguiente
    assert vistos == [c["id"] for c in orden]


def test_columna_fija_pista_y_leyenda_de_12_px():
    """REQ-152/153: la primera columna queda fija, la caja da una pista y «sin confirmar» >= 12 px."""
    css = CSS.read_text(encoding="utf-8")
    assert re.search(r"\.cu-cuadro th\.cu-req \{[^}]*position: sticky; left: 0", css)
    assert re.search(r"\.cu-nota \{[^}]*font-size: \.75rem", css)
    assert "cu-pista" in HTML.read_text(encoding="utf-8")


def test_con_10_ofertas_la_pista_aparece(client, procedure, evaluator_user, fake_ai):
    """REQ-153: con muchas ofertas la tabla avisa que se desplaza."""
    sintetico(procedure, evaluator_user, 12, 10)
    entrar(client, evaluator_user)
    html = client.get(url_de(procedure)).content.decode()
    assert "se desplaza hacia los costados" in html


def test_T361_C1_con_filtro_siguiente_no_sale_del_filtro(client, caso_varios_en_curso):
    """REQ-154 (T-361, C-1): con un filtro puesto, «Siguiente a decidir ›» solo sigue dentro de ese
    filtro; en la última celda dice que no hay otro punto en el filtro (no lleva a una celda que la
    tabla filtrada no muestra)."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    r = client.get(url_de(caso.procedure, "?filtro=a-decidir"))
    ultima = [c for g in r.context["groups"] for row in g["rows"] for c in row["cells"]][-1]
    celdas = [c for g in r.context["groups"] for row in g["rows"] for c in row["cells"]]
    en_filtro = {c["id"] for c in celdas if c["key"] == "nd"}
    for c in celdas:
        if c["id"] in en_filtro:
            sig = client.get(c["url"].split("#")[0]).context["siguiente"]
            assert not sig or sig.split("#")[1] in en_filtro
    ultima_nd = [c for c in celdas if c["id"] in en_filtro][-1]
    pagina = client.get(ultima_nd["url"].split("#")[0])
    assert pagina.context["siguiente"] == ""
    assert "No hay otro punto en este filtro." in pagina.content.decode()
    assert ultima
