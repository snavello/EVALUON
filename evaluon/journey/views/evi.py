"""El contenido del panel de Evi (feature 020, REQ-163 a REQ-170; T-367).

El botón está en toda pantalla con sesión, pero el contenido del panel no se calcula con la página: el
navegador lo pide al abrir Evi (así el botón no suma consultas a ninguna pantalla). `expedientes/evi/`
da el circuito general (sin estados ni marca) y `expedientes/<id>/evi/` el de un procedimiento: los
mismos estados que la portada (`calculo.proceso_de`) y «Qué hacer acá». `?pasos=1,5` dice qué pasos
resuelve la pantalla desde donde se abre. Solo lectura: ninguna escritura (REQ-169, P3). No dibuja
enlaces: el rol que mira no tiene nada que no pueda abrir."""

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.journey import memo
from evaluon.journey.evi import panel, pantallas, preguntas, textos
from evaluon.journey.proceso import calculo
from evaluon.journey.views.portada import overview_of, reading

TEMPLATE = "journey/_evi_contenido.html"
RESPUESTA = "journey/_evi_respuesta.html"
KIND = "evi_pregunta"  # el `detail["kind"]` del hecho de auditoría de cada pregunta (P6)


@require_GET
def general(request):
    """El circuito general: los siete pasos y sus textos, sin marca ni estados."""
    return render(request, TEMPLATE, _con_preguntas(panel.contexto(), None))


@require_GET
@memo.scoped
@reading
def procedimiento(request, procedure_id):
    """El circuito de un procedimiento: 404 si no existe; 403 sin rol, como la portada."""
    overview = overview_of(request, procedure_id)
    proceso = calculo.proceso_de(request.user, overview.procedure, overview)
    aqui = pantallas.pasos_pedidos(request.GET.get("pasos"))
    return render(request, TEMPLATE, _con_preguntas(panel.contexto(proceso, aqui), procedure_id))


def _con_preguntas(contexto, procedure_id):
    """Suma al contexto del panel el bloque «Pregúntele a Evi» (T-368): solo si el ajuste lo enciende."""
    contexto["preguntas"] = settings.EVI_QUESTIONS_ENABLED
    contexto["preguntar_url"] = (reverse("expedientes:evi_preguntar_procedimiento", args=[procedure_id])
                                 if procedure_id else reverse("expedientes:evi_preguntar"))
    contexto["preguntas_textos"] = {
        "titulo": textos.PREGUNTA_TITULO, "rotulo": textos.PREGUNTA_ROTULO, "ayuda": textos.PREGUNTA_AYUDA,
        "ejemplos": textos.PREGUNTA_EJEMPLOS, "pensando": textos.PREGUNTA_PENSANDO,
        "falla": textos.PREGUNTA_FALLA, "maximo": preguntas.MAX_QUESTION_CHARS}
    return contexto


def _responder(request, procedure, proceso):
    """La pregunta enviada: valida, pide a la IA local, deja el hecho de auditoría (P6) y devuelve el
    fragmento con la respuesta. Escribe solo el registro."""
    if not settings.EVI_QUESTIONS_ENABLED:
        raise Http404("Las preguntas a Evi no están disponibles.")
    pregunta = request.POST.get("pregunta", "")
    problema = preguntas.validar(pregunta)
    if problema:
        return render(request, RESPUESTA, {"problema": problema}, status=400)
    resultado = preguntas.preguntar(pregunta, proceso)
    audit.record(
        EventType.QUERY, outcome=Outcome.OK if resultado.ok else Outcome.FAILED, channel=Channel.SCREEN,
        user=request.user,
        detail={"kind": KIND, "procedure_id": procedure.pk if procedure else None, "question": pregunta,
                "answer": resultado.respuesta, "failure": resultado.motivo, "model": resultado.modelo,
                "prompt_version": resultado.version, "context_chars": resultado.contexto_caracteres,
                "seconds": resultado.segundos})
    contexto = {"resultado": resultado, "aviso": textos.PREGUNTA_AVISO, "falla": textos.PREGUNTA_FALLA,
                "parrafos": [p.strip() for p in resultado.respuesta.splitlines() if p.strip()]}
    return render(request, RESPUESTA, contexto)


@require_POST
def preguntar_general(request):
    """Una pregunta sin procedimiento abierto: responde solo con la guía."""
    return _responder(request, None, None)


@require_POST
@memo.scoped
@reading
def preguntar_procedimiento(request, procedure_id):
    """Una pregunta con un procedimiento abierto: la guía y su estado. Mismos permisos que ver el panel."""
    overview = overview_of(request, procedure_id)
    proceso = calculo.proceso_de(request.user, overview.procedure, overview)
    return _responder(request, overview.procedure, proceso)
