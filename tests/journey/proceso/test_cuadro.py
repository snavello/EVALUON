"""El cuadro de cumplimiento (REQ-143, REQ-152, REQ-156; T-352): requisitos en filas agrupados por
tipo, ofertas en columnas, estado de cada celda con su texto, y un pie con los mismos números que
el mosaico «Resultado por oferta». Material inventado (P4)."""

import re
import time
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment import not_applicable
from evaluon.journey import memo
from evaluon.journey.proceso import pasos
from evaluon.journey.temas import s4_propuesta
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.views import cuadro as vista
from evaluon.tenders import models as m
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import add_run, open_matrix
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


def entrar(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def url_de(procedure, query=""):
    return reverse("expedientes:cuadro", args=[procedure.pk]) + query


def texto_de(html, offer_id, requirement_id):
    """El texto de la celda (sin el rótulo para lector de pantalla), con «sin confirmar» al final."""
    found = re.search(rf'id="c-{offer_id}-{requirement_id}"[^>]*>(.*?)</(?:a|span)>\s*</td>', html, re.S)
    assert found, (offer_id, requirement_id)
    inner = re.sub(r'<span class="cu-sr">.*?</span>', "", found.group(1), flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", inner).split())


def sintetico(procedure, user, requisitos, ofertas, na=()):
    """Una matriz validada nueva con `requisitos` filas (60 % formales, 20 % económicas, 20 %
    técnicas) y `ofertas` ofertas con un resultado por par, salvo una de cada seis (sin resultado).
    Devuelve `(version, requisitos, ofertas)`."""
    base = procedure.matrix_versions.get(number=1)
    modelo = base.requirements.exclude(category="tecnico").first().quotes.first()
    version = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, status=m.VersionStatus.DRAFT, created_by=user)
    filas = []
    for n in range(1, requisitos + 1):
        corte = n / requisitos
        categoria = "formal" if corte <= 0.6 else ("economico" if corte <= 0.8 else "tecnico")
        fila = m.Requirement.objects.create(
            version=version, number=n, category=categoria,
            items=[n] if categoria == "tecnico" else [],
            origin=m.RequirementOrigin.AGREGADO, state=m.RequirementState.CONFIRMADO)
        m.RequirementQuote.objects.create(
            requirement=fila, order=1, segment=modelo.segment, char_start=modelo.char_start,
            char_end=modelo.char_end, text=modelo.text)
        filas.append(fila)
    version.status = m.VersionStatus.VALIDATED
    version.validated_at = base.validated_at
    version.validated_by = user
    version.save(update_fields=["status", "validated_at", "validated_by"])
    open_matrix()
    nd = am.Outcome.NO_DETERMINADO
    ciclo = [am.Outcome.CUMPLE, am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE, (nd, am.Doubt.DUDA),
             (nd, am.Doubt.PENDIENTE_INFORME_TECNICO), None]
    hechas = []
    for j in range(ofertas):
        oferta = make_offer(procedure, user, f"Oferente {j + 1} Sintético",
                            {"oferta.pdf": [f"Texto inventado de la oferta {j + 1}."]})
        resultados = {fila: ciclo[(i + j) % 6] for i, fila in enumerate(filas)
                      if ciclo[(i + j) % 6] is not None and (i, j) not in na}
        add_run(user, procedure, oferta, resultados, version=version)
        run = am.Run.objects.get(offer=oferta)
        for i, fila in enumerate(filas):
            if (i, j) in na:  # «cumple» con `facts.aplica = false`: así se guarda un «no aplica»
                assert ciclo[(i + j) % 6] == am.Outcome.CUMPLE
                am.Result.objects.create(
                    run=run, offer=oferta, requirement=fila, outcome=am.Outcome.CUMPLE,
                    exigence=am.Exigence.CONDICION, explanation="No aplica a la oferta.",
                    facts={"aplica": False, "regla": not_applicable.GUARANTEE_RULE})
        hechas.append(oferta)
    return version, filas, hechas


def test_la_ruta_es_la_que_arma_cuadro_url(caso_varios_en_curso):
    """REQ-154: `expedientes:cuadro` y la dirección que usan las decisiones son la misma."""
    procedure = caso_varios_en_curso.procedure
    esperada = reverse("expedientes:cuadro", args=[procedure.pk])
    assert acciones.cuadro_url(procedure, 3, 4).split("?")[0] == esperada
    assert esperada == f"/expedientes/{procedure.pk}/cuadro/"


def test_el_cuadro_del_caso_en_curso(client, caso_varios_en_curso):
    """REQ-152: una fila por requisito en tres grupos, una columna por oferta, el estado de cada
    celda en texto y «sin confirmar» solo debajo de «Cumple» y «No cumple» que nadie confirmó."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    response = client.get(url_de(caso.procedure))
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('<th scope="row" class="cu-req">') == 10  # 9 requisitos y el pie
    assert [g["label"] for g in response.context["groups"]] == ["Formales", "Económicos", "Técnicos"]
    assert [len(g["rows"]) for g in response.context["groups"]] == [4, 2, 3]
    assert len(response.context["columns"]) == 2
    textos = {c["text"] for g in response.context["groups"] for r in g["rows"] for c in r["cells"]}
    assert textos == {"Cumple", "No cumple", "A decidir", "Espera informe"}
    for g in response.context["groups"]:
        for r in g["rows"]:
            for c in r["cells"]:
                assert c["unconfirmed"] == (c["key"] in ("ok", "no"))  # nadie confirmó nada
    a, b = caso.offers
    tecnico = caso.procedure.matrix_versions.get(number=1).requirements.get(category="tecnico", items=[1])
    assert texto_de(html, a.pk, tecnico.pk) == "Espera informe"
    assert "sin confirmar" in html


def test_los_totales_del_pie_son_los_del_mosaico(client, caso_varios_en_curso):
    """REQ-152: el total de cada oferta es el del mosaico «Resultado por oferta» (`figures_of`);
    el pie cuenta las mismas celdas que se dibujan, así que difiere del mosaico solo en las filas
    técnicas sin el ok del informe (T-361): ahí el mosaico cuenta la propuesta y el pie «Espera
    informe». Lo que sale del pie de más es exactamente lo que entra en «Espera informe»."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    response = client.get(url_de(caso.procedure))
    with memo.scope():
        mosaico = next(t for t in s4_propuesta.tiles(caso.user, caso.procedure, None)
                       if t.key == "resultado")
        figuras = s4_propuesta.figures_of(memo.matrix_page(caso.user, caso.procedure.pk))
    donas = {d.label: d for d in mosaico.chart.items}
    assert len(response.context["columns"]) == len(donas) == 2
    for columna in response.context["columns"]:
        dona = donas[f"Of. {columna['number']}"]
        assert columna["count"] == dona.ok + dona.no + dona.nd + dona.pe
        assert columna["ok"] <= dona.ok and columna["no"] <= dona.no and columna["nd"] <= dona.nd
        assert columna["waiting"] + columna["without"] >= dona.pe
        assert (dona.ok - columna["ok"]) + (dona.no - columna["no"]) + (dona.nd - columna["nd"])             == columna["waiting"] + columna["without"] - dona.pe
    assert [o.ok for o in figuras.offers] == [3, 2]
    html = response.content.decode()
    for columna in response.context["columns"]:
        assert f"<b>{columna['ok']} de 9</b>" in html


def test_los_seis_textos_y_su_clave():
    """REQ-156: los seis textos de la decisión del responsable, cada uno con su clase."""
    assert {k: v[0] for k, v in vista.TEXTO_CELDA.items()} == {
        "ok": "Cumple", "no": "No cumple", "nd": "A decidir", "esp": "Espera informe",
        "pe": "Sin resultado", "na": "No aplica"}
    na = SimpleNamespace(result=object(), effective_outcome=am.Outcome.CUMPLE,
                         effective_key=not_applicable.KEY, reason="")
    assert vista.estado_de(na) == "na"
    sin = SimpleNamespace(result=None, effective_outcome=None, effective_key=None, reason="")
    assert vista.estado_de(sin) == "pe"
    espera = SimpleNamespace(result=object(), effective_outcome=am.Outcome.NO_DETERMINADO,
                             effective_key=am.Outcome.NO_DETERMINADO,
                             reason=am.Doubt.PENDIENTE_INFORME_TECNICO)
    assert vista.estado_de(espera) == "esp"


def test_27_requisitos_y_3_ofertas(client, procedure, evaluator_user, fake_ai):
    """REQ-152: 27 requisitos y 3 ofertas dan 27 filas en 3 grupos y 3 columnas; cada celda dice su
    estado con texto; el pie coincide con `figures_of` y con el mosaico; «Sin resultado» no es un
    enlace y los demás sí."""
    sintetico(procedure, evaluator_user, 27, 3)
    entrar(client, evaluator_user)
    response = client.get(url_de(procedure))
    html = response.content.decode()
    grupos = response.context["groups"]
    assert [len(g["rows"]) for g in grupos] == [16, 5, 6]
    assert sum(len(g["rows"]) for g in grupos) == 27 and len(response.context["columns"]) == 3
    celdas = [c for g in grupos for r in g["rows"] for c in r["cells"]]
    assert len(celdas) == 81
    assert {c["text"] for c in celdas} == {"Cumple", "No cumple", "A decidir", "Espera informe",
                                          "Sin resultado"}
    assert all(bool(c["url"]) == (c["key"] != "pe") for c in celdas)
    with memo.scope():
        figuras = s4_propuesta.figures_of(memo.matrix_page(evaluator_user, procedure.pk))
    for columna, ofertas in zip(response.context["columns"], figuras.offers):
        assert columna["figures"] == ofertas
        assert columna["count"] == ofertas.ok + ofertas.no + ofertas.nd + ofertas.pe
        assert f"<b>{columna['ok']} de {columna['count']}</b>" in html
    # Las filas técnicas sin el ok del informe esperan el informe (T-361); las demás son las del mosaico.
    tecnicas = [r for g in grupos if g["kind"] == "tecnico" for r in g["rows"]]
    assert all(c["key"] in ("esp", "pe", "na") for r in tecnicas for c in r["cells"])
    for estado, clave in (("Cumple", "ok"), ("No cumple", "no"), ("A decidir", "nd")):
        por_oferta = [sum(1 for g in grupos if g["kind"] != "tecnico" for r in g["rows"]
                          if r["cells"][i]["key"] == clave) for i in range(3)]
        assert por_oferta == [c[clave] for c in response.context["columns"]], estado


def test_filas_tecnicas_sin_ok_esperan_informe_en_todas_las_cuentas(
        client, procedure, evaluator_user, fake_ai):
    """REQ-152, REQ-156 (T-361, H-6): 6 filas técnicas × 3 ofertas ya evaluadas por el sistema y sin
    ok del informe técnico se ven «Espera informe» (aunque tengan propuesta), entran en el filtro
    «Esperan informe técnico» y en el pie, y no en «A decidir» ni en «sin confirmar»; el paso 4 y el
    paso 6 cuentan lo mismo que el pie."""
    from collections import Counter

    from evaluon.journey.proceso import calculo
    from evaluon.journey.proceso import pasos as pasos_mod
    sintetico(procedure, evaluator_user, 30, 3)
    entrar(client, evaluator_user)
    response = client.get(url_de(procedure))
    grupos = response.context["groups"]
    tecnicas = [r for g in grupos if g["kind"] == "tecnico" for r in g["rows"]]
    assert len(tecnicas) == 6
    hay_resultado = [c for r in tecnicas for c in r["cells"] if c["text"] != "Sin resultado"]
    assert hay_resultado and all(c["key"] == "esp" and not c["unconfirmed"] for c in hay_resultado)
    filtros = {f["clave"]: f["n"] for f in response.context["filtros"]}
    # Las filas que dejan los filtros salen de las mismas celdas: ninguna fila técnica en «A decidir».
    a_decidir = client.get(url_de(procedure, "?filtro=a-decidir")).context["groups"]
    assert not [g for g in a_decidir if g["kind"] == "tecnico"]
    espera = client.get(url_de(procedure, "?filtro=espera-informe")).context["groups"]
    assert filtros["espera-informe"] == sum(len(g["rows"]) for g in espera)
    assert {r["number"] for r in tecnicas} <= {r["number"] for g in espera for r in g["rows"]}
    # El pie y el paso 4 cuentan igual (ok/no/nd sin las técnicas, `esp` aparte).
    columnas = response.context["columns"]
    with memo.scope():
        vistos = s4_propuesta.visible_counts(memo.matrix_page(evaluator_user, procedure.pk))
        proceso = calculo.proceso_de(evaluator_user, procedure)
    for c in columnas:
        assert (c["ok"], c["no"], c["nd"], c["waiting"], c["without"]) == tuple(
            vistos[c["number"]][k] for k in ("ok", "no", "nd", "esp", "pe"))
    total = sum(vistos.values(), Counter())
    paso4 = next(p for p in proceso.pasos if p.numero == 4)
    assert paso4.dato.startswith(f"{total['ok']} cumplen · {total['no']} no · {total['nd']} a decidir")
    assert f"{total['esp']} esperan informe" in paso4.dato and pasos_mod.POR_NUMERO[4]


def test_cada_estado_lleva_el_texto_y_el_nombre_de_los_siete_pasos(client, caso_varios_en_curso):
    """REQ-143, REQ-156: los siete nombres de `pasos.py`, en su orden, y ninguna celda sin texto."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = client.get(url_de(caso.procedure)).content.decode()
    posiciones = [html.index(f"Paso {p.numero} · {p.nombre}") for p in pasos.PASOS]
    assert posiciones == sorted(posiciones)
    celdas = re.findall(r'<(?:a|span) class="cu-cel [^"]*"[^>]*>(.*?)</(?:a|span)>\s*</td>', html, re.S)
    assert len(celdas) == 18
    for celda in celdas:
        limpio = " ".join(re.sub(r"<[^>]+>", " ", re.sub(r'<span class="cu-sr">.*?</span>', "", celda)).split())
        assert limpio.split(" sin confirmar")[0] in {"Cumple", "No cumple", "A decidir",
                                                     "Espera informe", "Sin resultado",
                                                     "No aplica"}


def test_el_cuadro_tarda_menos_de_dos_segundos_con_60_requisitos_y_10_ofertas(
        client, procedure, evaluator_user, fake_ai):
    """Criterio numérico del plan: ≤ 2 s con un procedimiento sintético de 60 × 10."""
    sintetico(procedure, evaluator_user, 60, 10)
    entrar(client, evaluator_user)
    client.get(url_de(procedure))  # calienta las importaciones y el caché de plantillas
    medidas = []
    for _ in range(3):
        inicio = time.perf_counter()
        response = client.get(url_de(procedure))
        medidas.append(time.perf_counter() - inicio)
        assert response.status_code == 200
    assert len(response.context["columns"]) == 10 and response.context["total_rows"] == 60
    assert min(medidas) <= 2.0, medidas


def test_sin_sesion_el_cuadro_manda_a_ingresar(client, caso_varios_en_curso):
    """REQ-075: sin sesión no se abre."""
    response = client.get(url_de(caso_varios_en_curso.procedure))
    assert response.status_code == 302 and response["Location"].startswith("/ingresar/")


def test_un_procedimiento_inexistente_da_404(client, evaluator_user):
    entrar(client, evaluator_user)
    assert client.get(reverse("expedientes:cuadro", args=[999999])).status_code == 404


def test_sin_ofertas_dice_que_falta(client, procedure, evaluator_user):
    """El cuadro de un procedimiento sin ofertas no se rompe: dice qué falta."""
    entrar(client, evaluator_user)
    response = client.get(url_de(procedure))
    assert response.status_code == 200
    assert "ofertas cargadas" in response.content.decode()


def test_la_hoja_y_la_plantilla_no_traen_colores_sueltos_ni_estilos_en_linea():
    """REQ-156, ADR-0076: `cuadro.css` usa solo tokens, la plantilla no lleva `style=` y cada
    estado de celda tiene su símbolo además del color."""
    from pathlib import Path

    raiz = Path(vista.__file__).resolve().parents[2]
    css = re.sub(r"/\*.*?\*/", "", (raiz / "static/journey/cuadro.css").read_text(encoding="utf-8"), flags=re.S)
    plantilla = (raiz / "templates/journey/cuadro.html").read_text(encoding="utf-8")
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", css) == []
    assert not re.search(r"\sstyle=", plantilla) and "<script" not in plantilla
    for clase in ("ok", "no", "nd", "esp", "sin"):
        assert f".cu-cel.{clase}::before" in css, clase


def test_la_linea_secundaria_del_pie_dice_cada_cifra_en_su_lugar(client, caso_varios_en_curso):
    """REQ-152: «No cumple N · A decidir N · Espera informe N» de cada oferta, con cada cifra en su
    lugar (Oferta 1: 1, 2, 3; Oferta 2: 0, 4, 3); si se cruzan dos, falla."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = client.get(url_de(caso.procedure)).content.decode()
    assert "No cumple 1 · A decidir 2 · Espera informe 3" in html
    assert "No cumple 0 · A decidir 4 · Espera informe 3" in html
    assert "Sin resultado" not in html[html.index("<tfoot>"):]  # ninguna oferta tiene pares sin resultado


def test_las_celdas_no_aplica_se_muestran_y_no_entran_en_los_totales(
        client, procedure, evaluator_user, fake_ai):
    """REQ-152, decisión P5: «No aplica» está escrito en la celda y no suma ni en «N de M» ni en el
    resto del pie; el pie sigue siendo el de `figures_of`."""
    na = {(0, 0), (1, 0), (6, 0)}  # filas 0, 1 y 6 de la oferta 1 (todas «cumple» en el ciclo)
    sintetico(procedure, evaluator_user, 12, 1, na=na)
    entrar(client, evaluator_user)
    response = client.get(url_de(procedure))
    html = response.content.decode()
    celdas = [c for g in response.context["groups"] for r in g["rows"] for c in r["cells"]]
    assert sorted(c["key"] for c in celdas).count("na") == 3
    assert all(c["text"] == "No aplica" for c in celdas if c["key"] == "na")
    with memo.scope():
        figuras = s4_propuesta.figures_of(memo.matrix_page(evaluator_user, procedure.pk))
    oferta = figuras.offers[0]
    assert oferta.na == 3
    assert f"<b>{oferta.ok} de {oferta.ok + oferta.no + oferta.nd + oferta.pe}</b>" in html
    assert oferta.ok + oferta.no + oferta.nd + oferta.pe == 12 - 3
    assert response.context["columns"][0]["count"] == 9
    assert "No aplica" in html[html.index("<tbody>"):html.index("<tfoot>")]
    assert "No aplica" not in html[html.index("<tfoot>"):html.index("</tfoot>")]


def test_un_tecnico_con_cita_no_repite_el_renglon(client, caso_varios_en_curso):
    """La fila técnica lee su renglón una sola vez: lo que dice la cita del pliego."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = client.get(url_de(caso.procedure)).content.decode()
    assert "Renglón 1 · 1." not in html
    assert re.search(r"<span class=\"cu-num\">6\.</span> 1\. RENGLÓN N° 1 - RESMA", html)
