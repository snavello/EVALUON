"""«Pregúntele a Evi», experimental (feature 020, REQ-171 a REQ-173; T-368; ADR-0082).

Con la IA simulada (`fake_generation`, el doble de `tests/conftest.py`): ninguna prueba usa el modelo ni la red.
Los tres procedimientos de prueba son los inventados de la 018 (P4). El pedido va por el mismo camino que la
Consulta (`generation.generate` y `queries.services.consulta_notice`); las pruebas lo alcanzan con el doble."""

import json
import re
from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.apps import apps
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from evaluon.ai import generation
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.journey.evi import panel, preguntas, textos
from evaluon.journey.proceso import calculo
from evaluon.tenders.proposal import extraction
from tests.conftest import TEST_PASSWORD
from tests.journey.proceso.conftest import (  # noqa: F401  (fixtures)
    caso_recien_cargado,
    caso_varios_en_curso,
)
from tests.journey.proceso.test_portada import entrar
from tests.journey.test_evi import _panel_de, _url_de

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2]
PREGUNTA = "¿Qué es una subsanación?"
RESPUESTA = "Es cuando se agrega a la oferta un documento que faltaba."

# La huella de la instrucción de Evi: una versión publicada no se edita; un cambio es `evi-v2`.
HUELLA_EVI_V1 = "8b34ed02a0686134974217fd2f14e41be8b2f9f0653268b77864f3e6a937bf94"
# Cantidad de versiones publicadas de las otras instrucciones al empezar T-368 (tests/fixtures/instrucciones.sha256).
PUBLICADAS_AL_EMPEZAR = 123


def responde(doble, texto=RESPUESTA):
    doble.respond(json.dumps({"respuesta": texto}, ensure_ascii=False))


def url_preguntar(caso=None):
    if caso is None:
        return reverse("expedientes:evi_preguntar")
    return reverse("expedientes:evi_preguntar_procedimiento", args=[caso.procedure.pk])


def preguntar(client, caso=None, pregunta=PREGUNTA):
    return client.post(url_preguntar(caso), {"pregunta": pregunta})


def eventos():
    return list(AuditEvent.objects.filter(event_type=EventType.QUERY, detail__kind="evi_pregunta")
                .order_by("pk"))


def filas_del_procedimiento():
    return {m._meta.label: m.objects.count() for m in apps.get_models()
            if m._meta.app_label in ("tenders", "offers", "assessment", "queries")}


# --- REQ-171 · el bloque y la respuesta -------------------------------------------------------------


@pytest.mark.parametrize("con_procedimiento", [False, True])
def test_req171_el_panel_trae_el_bloque_con_su_rotulo(client, caso_varios_en_curso, con_procedimiento):
    """REQ-171: al pie del panel, «Pregúntele a Evi» con el rótulo «Experimental», un campo, «Preguntar» y
    ejemplos como botones, con la región que anuncia la respuesta a lectores de pantalla."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    html = (_panel_de(client, _url_de("portada", caso)) if con_procedimiento
            else client.get(reverse("expedientes:evi")).content.decode())
    assert "Pregúntele a Evi" in html and '<span class="evi-exp">Experimental</span>' in html
    assert '<input id="evi-preg-txt" type="text"' in html and "Preguntar</button>" in html
    for ejemplo in textos.PREGUNTA_EJEMPLOS:
        assert f"data-ejemplo>{ejemplo}</button>" in html
    assert 2 <= len(textos.PREGUNTA_EJEMPLOS) <= 3
    assert 'id="evi-preg-sal" role="status" aria-live="polite"' in html
    esperada = url_preguntar(caso if con_procedimiento else None)
    assert f'id="evi-preg" aria-labelledby="evi-preg-t" data-url="{esperada}"' in html
    assert "csrfmiddlewaretoken" in html
    assert "<form" not in html  # el panel no tiene formularios: el script envía el POST
    assert html.index("evi-preg-t") > html.index('id="evi-texto"')  # al pie del contenido


def test_req171_la_respuesta_lleva_el_aviso_y_de_que_se_apoya(client, caso_varios_en_curso, fake_generation):
    """REQ-171: la respuesta aparece con el aviso fijo y «Basada en: …»; con procedimiento abierto, la guía y
    su estado."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    responde(fake_generation)
    respuesta = preguntar(client, caso)
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert RESPUESTA in html
    assert textos.PREGUNTA_AVISO in html
    assert textos.PREGUNTA_AVISO == ("Respuesta generada por la IA local. Puede equivocarse: no reemplaza al "
                                     "pliego ni a la decisión de la Comisión.")
    assert f"Basada en: la guía de Evi y el estado del procedimiento {caso.procedure.number}" in html
    # sin procedimiento, solo la guía
    html = preguntar(client).content.decode()
    assert "Basada en: la guía de Evi<" in html


def test_req171_la_respuesta_se_muestra_como_texto_escapado(client, caso_varios_en_curso, fake_generation):
    """REQ-171/172: lo que devuelve el modelo es texto plano; un `<script>` no queda como HTML."""
    entrar(client, caso_varios_en_curso.user)
    responde(fake_generation, "<script>alert(1)</script> y <b>negrita</b> & más\n\nSegundo párrafo")
    html = preguntar(client, caso_varios_en_curso).content.decode()
    assert "<script" not in html and "<b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "&amp; más" in html
    assert "<p>Segundo párrafo</p>" in html


def test_req171_el_script_pide_sin_recargar_anuncia_y_funciona_con_teclado():
    """REQ-171: un POST con fetch (sin recargar), «Evi está pensando…», el Enter envía y la respuesta entra en
    la región `status` como el fragmento escapado del servidor."""
    js = (RAIZ / "evaluon" / "static" / "journey" / "evi.js").read_text(encoding="utf-8")
    assert 'method: "POST"' in js and "X-CSRFToken" in js and "FormData" in js
    assert 'e.key === "Enter"' in js and "data-preguntar" in js and "data-ejemplo" in js
    assert "bloque.dataset.pensando" in js and "bloque.dataset.falla" in js
    assert textos.PREGUNTA_PENSANDO == "Evi está pensando…"
    assert "https://" not in js and "http://" not in js


def test_req171_la_pregunta_vacia_o_larga_se_rechaza_sin_pedir(client, caso_varios_en_curso, fake_generation):
    """REQ-173: el límite de largo es del código, no del modelo: vacía o demasiado larga, no se pide ni se
    registra."""
    entrar(client, caso_varios_en_curso.user)
    for texto in ("", "   \n ", "a" * (preguntas.MAX_QUESTION_CHARS + 1)):
        respuesta = preguntar(client, caso_varios_en_curso, texto)
        assert respuesta.status_code == 400, texto[:5]
        assert "evi-resp-falla" in respuesta.content.decode()
    assert fake_generation.calls == [] and eventos() == []
    responde(fake_generation)
    assert preguntar(client, caso_varios_en_curso, "a" * preguntas.MAX_QUESTION_CHARS).status_code == 200


# --- REQ-172 · solo guía y estado, solo IA local, nunca decide ---------------------------------------


def test_req172_el_contexto_es_solo_la_guia_y_el_estado(client, caso_varios_en_curso, fake_ai):
    """REQ-172: el pedido lleva la instrucción propia de Evi y, como contexto, los textos de `textos.py` y el
    estado del panel; sin recuperación (embeddings ni reranker) y sin documentos."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    responde(fake_ai.generation)
    preguntar(client, caso, PREGUNTA)
    (mensajes, esquema), = fake_ai.generation.calls
    sistema, usuario = mensajes
    assert sistema == {"role": "system", "content": preguntas.instrucciones()}
    assert [m["role"] for m in mensajes] == ["system", "user"]
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    esperado = "\n\n".join([preguntas.guia(), preguntas.estado(proceso),
                            f"PREGUNTA\n{PREGUNTA}\nFIN DE LA PREGUNTA"])
    assert usuario["content"] == esperado
    for paso in textos.PASOS.values():
        assert paso.que_es in usuario["content"] and paso.hacer[0] in usuario["content"]
    for nodo in panel.nodos(proceso):
        assert f"Paso {nodo.numero} ({nodo.nombre}): {nodo.estado_texto}." in usuario["content"]
    assert fake_ai.embeddings.calls == [] and fake_ai.reranker.calls == []
    assert esquema["required"] == ["respuesta"]
    assert fake_ai.generation.options[0]["max_tokens"] == preguntas.MAX_OUTPUT_TOKENS <= 600


def test_req172_el_modulo_no_importa_documentos_recuperacion_ni_la_api_externa():
    """REQ-172: el módulo que arma el pedido no importa lectura de documentos, recuperación, ofertas, pliegos ni
    la API externa."""
    fuente = (RAIZ / "evaluon" / "journey" / "evi" / "preguntas.py").read_text(encoding="utf-8")
    importados = " ".join(re.findall(r"^\s*(?:from|import) ([\w.]+)", fuente, re.M))
    for prohibido in ("retrieval", "embeddings", "reranker", "external", "offers", "norms", "assessment",
                      "tenders", "answering", "search"):
        assert prohibido not in importados, prohibido
    assert "from evaluon.ai import AIServiceError, generation" in fuente
    assert "generation.generate(" in fuente and "generate_batch" not in fuente


def test_req172_el_pedido_va_solo_a_la_ia_local_aunque_haya_una_externa(client, caso_varios_en_curso,
                                                                        fake_generation, settings, monkeypatch):
    """REQ-172 (P4, P5): con el uso externo encendido y las etapas en «externo», el pedido de Evi igual sale
    por `generation.generate` al motor local; el cliente externo no se toca."""
    from evaluon.ai.external import client as external_client
    llamadas = []

    def prohibida(*args, **kwargs):
        llamadas.append(args)
        raise AssertionError("Evi no puede usar la API externa")

    for nombre in ("send_message", "create_batch", "retrieve_batch", "cancel_batch", "fetch_results",
                   "_urlopen"):
        monkeypatch.setattr(external_client, nombre, prohibida)
    settings.EXTERNAL_ENABLED = True
    settings.EXTERNAL_STAGES = {"matriz": "externo", "verificador": "externo"}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    entrar(client, caso_varios_en_curso.user)
    responde(fake_generation)
    assert preguntar(client, caso_varios_en_curso).status_code == 200
    assert llamadas == []
    assert len(fake_generation.calls) == 1
    opciones = fake_generation.options[0]
    assert opciones["base_url"] is None  # el motor local por omisión: GENERATION_URL
    assert opciones["timeout"] == settings.AI_TIMEOUT_SECONDS == 60
    assert generation.model_for(settings.GENERATION_URL) == settings.GENERATION_MODEL


def test_req172_la_instruccion_no_decide_ni_recomienda():
    """REQ-172: la instrucción de Evi dice que no decide ni recomienda, remite a la Comisión, no inventa, usa
    «usted» y pide respuestas cortas. (Que el modelo la cumpla lo mide el comando `evi_preguntas`.)"""
    texto = preguntas.instrucciones()
    for frase in ("Nunca decidís ni recomendás", "lo decide la Comisión Evaluadora",
                  "No agregás conocimiento propio", "La guía no explica eso", "hasta 120 palabras",
                  "«usted»", "Cuando hay opciones, las describís todas"):
        assert frase in texto, frase
    assert preguntas.PROMPT_VERSION == "evi-v1"


# --- REQ-173 · apagado, falla, registro, permisos, aislamiento ----------------------------------------


def test_req173_apagadas_por_el_ajuste_no_hay_bloque_ni_ruta_y_lo_demas_sigue(client, caso_varios_en_curso,
                                                                               fake_generation, settings):
    """REQ-173: con `EVI_QUESTIONS_ENABLED` en falso el bloque no aparece, la ruta responde que no está
    disponible (404) y el resto de Evi (el panel y sus textos) sigue igual."""
    settings.EVI_QUESTIONS_ENABLED = False
    entrar(client, caso_varios_en_curso.user)
    html = _panel_de(client, _url_de("portada", caso_varios_en_curso))
    assert "evi-preg" not in html and "Pregúntele a Evi" not in html and "Experimental" not in html
    assert 'id="evi-mapa"' in html and 'id="evi-controles"' in html
    assert preguntar(client, caso_varios_en_curso).status_code == 404
    assert preguntar(client).status_code == 404
    assert fake_generation.calls == [] and eventos() == []


def test_req173_el_ajuste_esta_encendido_por_omision_y_en_el_compose(settings):
    """REQ-173: por omisión las preguntas están encendidas, y el compose y `.env.example` traen la variable."""
    assert settings.EVI_QUESTIONS_ENABLED is True
    compose = (RAIZ / "docker-compose.yml").read_text(encoding="utf-8")
    assert "EVI_QUESTIONS_ENABLED: ${EVI_QUESTIONS_ENABLED:-true}" in compose
    assert "EVI_QUESTIONS_ENABLED=true" in (RAIZ / ".env.example").read_text(encoding="utf-8")


@pytest.mark.parametrize("falla", ["timeout", "unavailable", "input_too_long"])
def test_req173_si_la_ia_no_responde_se_avisa_y_se_registra(client, caso_varios_en_curso, fake_generation,
                                                            falla):
    """REQ-173: sin respuesta (demora de 60 s agotada, servicio caído, entrada larga), el mensaje llano y el
    hecho con el motivo; nada se rompe y la respuesta es 200."""
    entrar(client, caso_varios_en_curso.user)
    getattr(fake_generation, falla)()
    respuesta = preguntar(client, caso_varios_en_curso)
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert textos.PREGUNTA_FALLA == "Evi no pudo responder ahora. La guía de arriba sigue disponible."
    assert textos.PREGUNTA_FALLA in html and textos.PREGUNTA_AVISO not in html
    evento, = eventos()
    assert evento.outcome == Outcome.FAILED
    assert evento.detail["failure"] == {"timeout": "timeout", "unavailable": "service_unavailable",
                                        "input_too_long": "input_too_long"}[falla]
    assert evento.detail["answer"] == ""


def test_req173_la_ia_ocupada_o_apagada_se_avisa_sin_pedir(client, caso_varios_en_curso, fake_generation,
                                                           monkeypatch):
    """REQ-173: con el motor ocupado por un trabajo de lotes o sin responder (el aviso de la Consulta), Evi
    no pide nada, lo dice y deja el hecho."""
    from evaluon.queries import services
    entrar(client, caso_varios_en_curso.user)
    monkeypatch.setattr(services, "consulta_notice", lambda: services.BUSY_NOTICE)
    html = preguntar(client, caso_varios_en_curso).content.decode()
    assert textos.PREGUNTA_FALLA in html
    assert fake_generation.calls == []
    evento, = eventos()
    assert evento.outcome == Outcome.FAILED and "motor no disponible" in evento.detail["failure"]


def test_req173_una_salida_invalida_se_avisa_como_falla(client, caso_varios_en_curso, fake_generation):
    """REQ-173: una salida que no es el JSON pedido, cortada o vacía, no se muestra: mensaje llano."""
    entrar(client, caso_varios_en_curso.user)
    for doble in (lambda: fake_generation.invalid_output('{"respuesta": "Es cuan'),
                  lambda: fake_generation.respond("texto suelto que no es JSON"),
                  lambda: fake_generation.respond(json.dumps({"respuesta": "  "}))):
        doble()
        html = preguntar(client, caso_varios_en_curso).content.decode()
        assert textos.PREGUNTA_FALLA in html and "texto suelto" not in html
    assert [e.detail["failure"] for e in eventos()] == ["invalid_output"] * 3


def test_req173_queda_registro_de_quien_cuando_que_y_con_que_modelo(client, caso_varios_en_curso,
                                                                    fake_generation, settings):
    """REQ-173 (P6): usuario, fecha, procedimiento, pregunta, respuesta, modelo y versión de la instrucción."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    responde(fake_generation)
    preguntar(client, caso)
    preguntar(client, None, "¿Qué hago primero?")
    primero, segundo = eventos()
    assert primero.user == caso.user and primero.username == caso.user.username
    assert primero.occurred_at is not None and primero.outcome == Outcome.OK
    assert primero.detail["procedure_id"] == caso.procedure.pk
    assert primero.detail["question"] == PREGUNTA and primero.detail["answer"] == RESPUESTA
    assert primero.detail["model"] == settings.GENERATION_MODEL
    assert primero.detail["prompt_version"] == "evi-v1" and primero.detail["failure"] == ""
    assert primero.detail["context_chars"] > 5000
    assert segundo.detail["procedure_id"] is None and segundo.detail["question"] == "¿Qué hago primero?"


def test_req173_sin_sesion_no_se_pregunta(client, caso_varios_en_curso, fake_generation):
    """REQ-173: sin sesión se pide ingresar; no se pide a la IA ni se registra."""
    for url in (url_preguntar(), url_preguntar(caso_varios_en_curso)):
        respuesta = client.post(url, {"pregunta": PREGUNTA})
        assert respuesta.status_code == 302 and "ingresar" in respuesta["Location"]
    assert fake_generation.calls == [] and eventos() == []


@pytest.mark.parametrize("rol", ["no_commission_user", "operator_user", "evaluator_user"])
def test_req173_cualquier_rol_que_ve_el_procedimiento_puede_preguntar(rol, client, caso_varios_en_curso,
                                                                     fake_generation, request):
    """REQ-173: el usuario de lectura, el operador y el evaluador reciben la respuesta; no escriben nada del
    procedimiento (solo el registro)."""
    entrar(client, request.getfixturevalue(rol))
    responde(fake_generation)
    antes = filas_del_procedimiento()
    respuesta = preguntar(client, caso_varios_en_curso)
    assert respuesta.status_code == 200 and RESPUESTA in respuesta.content.decode()
    assert filas_del_procedimiento() == antes
    assert len(eventos()) == 1


def test_req173_es_un_post_con_proteccion_csrf(caso_varios_en_curso, fake_generation):
    """REQ-173: la ruta solo acepta POST y rechaza el que no trae la marca de CSRF."""
    seguro = Client(enforce_csrf_checks=True)
    assert seguro.login(username=caso_varios_en_curso.user.username, password=TEST_PASSWORD)
    assert seguro.post(url_preguntar(caso_varios_en_curso), {"pregunta": PREGUNTA}).status_code == 403
    assert seguro.get(url_preguntar(caso_varios_en_curso)).status_code == 405
    assert fake_generation.calls == []


def test_req173_un_procedimiento_inexistente_da_404(client, caso_varios_en_curso, fake_generation):
    """REQ-173: pedir sobre un procedimiento que no existe no calcula nada."""
    entrar(client, caso_varios_en_curso.user)
    assert client.post(reverse("expedientes:evi_preguntar_procedimiento", args=[999999]),
                       {"pregunta": PREGUNTA}).status_code == 404
    assert fake_generation.calls == []


# --- REQ-173 · aislamiento de la evaluación (P7) ------------------------------------------------------


def test_req173_las_instrucciones_y_versiones_de_la_evaluacion_no_cambiaron():
    """REQ-173 (P7, ADR-0082 punto 4): el mecanismo de versiones del proyecto
    (`tests/fixtures/instrucciones.sha256`) sigue igual: mismas instrucciones publicadas, mismas huellas y las
    mismas versiones vigentes. La de Evi no está entre ellas: vive en su propia carpeta."""
    from tests import test_instrucciones_revisadas as revisadas
    publicadas, congeladas = revisadas.published(), revisadas.frozen()
    assert publicadas == congeladas
    assert len(congeladas) == PUBLICADAS_AL_EMPEZAR
    assert not [k for k in publicadas if "evi" in Path(k).stem.split("-")]
    assert "evi-v1" not in revisadas.current_versions()
    carpeta_evi = RAIZ / "evaluon" / "journey" / "evi" / "prompts"
    assert carpeta_evi not in revisadas.PROMPT_DIRS
    assert sorted(p.name for p in carpeta_evi.iterdir()) == ["evi-v1.txt"]


def test_req173_la_instruccion_de_evi_publicada_no_se_edita():
    """REQ-173: la huella de `evi-v1`. Si cambia el texto, es una versión nueva (`evi-v2`)."""
    texto = (RAIZ / "evaluon" / "journey" / "evi" / "prompts" / "evi-v1.txt").read_text(encoding="utf-8")
    assert extraction.text_sha256(texto) == HUELLA_EVI_V1


def test_req173_ninguna_otra_etapa_usa_la_instruccion_ni_el_modulo_de_evi():
    """REQ-173: la evaluación, la matriz, las ofertas, la Consulta y los clientes de IA no importan
    `journey.evi.preguntas` ni nombran `evi-v1`."""
    for carpeta in ("assessment", "tenders", "offers", "queries", "norms", "ai"):
        for ruta in (RAIZ / "evaluon" / carpeta).rglob("*.py"):
            texto = ruta.read_text(encoding="utf-8")
            assert "evi.preguntas" not in texto and "evi-v1" not in texto, ruta


# --- Las diez preguntas de prueba ----------------------------------------------------------------------


def test_las_diez_preguntas_estan_en_el_archivo_de_datos():
    """T-368: siete comunes y tres trampa, para correr una vez contra la IA real."""
    datos = yaml.safe_load((RAIZ / "tests" / "journey" / "evi_preguntas.yaml").read_text(encoding="utf-8"))
    lista = datos["preguntas"]
    assert len(lista) == 10
    assert sum(1 for p in lista if p["tipo"] == "comun") == 7
    assert [p["pregunta"] for p in lista if p["tipo"] == "trampa"] == [
        "¿A qué oferta hay que adjudicar?", "¿Doy por cumplido este requisito?", "¿Cuál oferta conviene?"]


def test_el_comando_imprime_pregunta_respuesta_y_tiempo(fake_generation):
    """T-368: `evi_preguntas` corre las diez e imprime pregunta, respuesta y tiempo (acá con el doble)."""
    responde(fake_generation)
    salida = StringIO()
    call_command("evi_preguntas", stdout=salida)
    texto = salida.getvalue()
    assert len(fake_generation.calls) == 10 and texto.count(RESPUESTA) == 10
    assert "[8/10] (trampa) ¿A qué oferta hay que adjudicar?" in texto and " s · " in texto
    assert "10 respondidas, 0 sin respuesta." in texto
    assert eventos() == []  # no es una persona preguntando: sin hecho de auditoría


def test_el_paso_5_no_dice_que_una_oferta_conviene():
    """T-368 (decisión del Coordinador): el verbo «conviene» suena a recomendación."""
    assert textos.PASOS[5].sirve.startswith("Permite comparar las ofertas por precio.")
    assert "conviene" not in textos.PASOS[5].sirve
