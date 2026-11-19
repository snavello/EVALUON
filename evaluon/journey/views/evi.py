"""El contenido del panel de Evi (feature 020, REQ-163 a REQ-170; T-367).

El botón está en toda pantalla con sesión, pero el contenido del panel no se calcula con la página: el
navegador lo pide al abrir Evi (así el botón no suma consultas a ninguna pantalla). `expedientes/evi/`
da el circuito general (sin estados ni marca) y `expedientes/<id>/evi/` el de un procedimiento: los
mismos estados que la portada (`calculo.proceso_de`) y «Qué hacer acá». `?pasos=1,5` dice qué pasos
resuelve la pantalla desde donde se abre. Solo lectura: ninguna escritura (REQ-169, P3). No dibuja
enlaces: el rol que mira no tiene nada que no pueda abrir."""

from django.shortcuts import render
from django.views.decorators.http import require_GET

from evaluon.journey import memo
from evaluon.journey.evi import panel, pantallas
from evaluon.journey.proceso import calculo
from evaluon.journey.views.portada import overview_of, reading

TEMPLATE = "journey/_evi_contenido.html"


@require_GET
def general(request):
    """El circuito general: los siete pasos y sus textos, sin marca ni estados."""
    return render(request, TEMPLATE, panel.contexto())


@require_GET
@memo.scoped
@reading
def procedimiento(request, procedure_id):
    """El circuito de un procedimiento: 404 si no existe; 403 sin rol, como la portada."""
    overview = overview_of(request, procedure_id)
    proceso = calculo.proceso_de(request.user, overview.procedure, overview)
    aqui = pantallas.pasos_pedidos(request.GET.get("pasos"))
    return render(request, TEMPLATE, panel.contexto(proceso, aqui))
